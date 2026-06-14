# L80 — Building Cost-Effective Vector Storage with S3 and Lambda Ingestion

> **Week 3 · Day 4** · ⏱️ ~7 min

---

## 🎯 TL;DR

Alex capstone ka tisra ingestion guide shuru — hum **S3 Vectors** (AWS ka naya native vector store, OpenSearch se ~90% sasta) ka bucket banate hain, ek **ingest Lambda** function (text → vector → S3 Vectors) aur uske deployment package (`package.py` se `lambda_function.zip`) taiyaar karte hain. API Gateway + API key authentication baad ke lecture mein.

---

## 🗣️ Hinglish Explanation

### Recap: hum kahan hain Alex project mein

Yeh **Week 3, Day 4** hai aur hum **Alex** capstone par kaam kar rahe hain — Ed ka agentic financial planner SaaS. Ab tak (pichle lectures mein) humne ek **SageMaker embedding endpoint** deploy kiya hai jo text ko vectors mein convert karta hai (model: `all-MiniLM-L6-v2`, jo **384-dimensional** vectors banata hai). Aaj ka kaam: us endpoint ke upar ek **data ingestion pipeline** banana — jisse text aaye, vectorize ho, aur ek vector database mein store ho jaaye.

Ed project ke andar `guides` folder kholta hai aur **third guide** padhta hai: *"Ingest MD — ingestion pipeline with S3 vectors"*. Is guide mein 3 cheezein deploy hongi:

1. **S3 Vectors** — cost-effective vector storage (OpenSearch se ~90% sasta)
2. **Lambda function** — document ingestion ke liye
3. **API Gateway with API key authentication** — SageMaker embedding endpoint ke saath integration

API Gateway use karne ki wajah: yeh **bulletproof, production-grade construct** hai jo right kind of security deta hai (galat log randomly tumhare endpoint ko hit na kar saken).

### S3 Vectors kya hai (background)

Pehle samajh lo cheezein:

- **S3 (Simple Storage Service)** — AWS ka object storage. Tum files/blobs (objects) buckets mein daalte ho. Har bucket ka naam **globally unique** hona chahiye kyunki S3 ka namespace saare AWS users ke beech shared hai.
- **Vector database** — embeddings (numeric vectors) store karta hai aur **similarity search** allow karta hai (e.g. cosine similarity se "is text ke sabse milte-julte documents kaun se hain"). RAG (Retrieval Augmented Generation) ke liye core piece.
- **S3 Vectors** — AWS ka **naya native vector storage** product. Naam dekhne mein "S3 vectors" jaisa lagta hai par yeh **alag service** hai normal S3 se. Iska bada selling point: **OpenSearch jaisi managed vector search se ~90% sasta**. Capstone ke budget-friendly approach ke liye perfect.

> Ed clarify karta hai: *"S3 vectors is their new native vector storage solution... it is different to S3."* Matlab confuse mat hona — yeh classic S3 object storage nahi hai, alag vector-specific service hai.

### Step 1: S3 Vector bucket banao (manually, Terraform se NAHI)

Important design decision: yeh bucket **Terraform se nahi banayenge**.

**Kyun manual?** Kyunki yeh ek **one-time, long-lived resource** hai. Hum chahte hain ki yeh bucket **survive kare** even jab tum baaki infrastructure ko `terraform destroy` se neeche le aao aur dobara `terraform apply` karo. Agar Terraform isse manage karta toh `destroy` ke saath tumhara saara vector data ud jaata. Iska matlab yeh bhi hai ki course khatam hone ke baad tumhe ise **manually delete** karna padega (Resources Explorer se), Terraform automatically clean nahi karega.

Manual steps (AWS Console):

1. AWS Console mein **IAM user** ke roop mein login karo (Ed ka user: `ai-engineer` — note: `editor` wala admin user nahi, balki restricted engineering user)
2. Search bar mein **S3** type karo → S3 mein jao
3. Left sidebar mein neeche **Vector buckets** dhoondo → select karo → **S3 Vectors** screen
4. **Create vector bucket** button dabao
5. Bucket ka naam do is format mein:

```
alex-vectors-<your-account-id>
```

- `<your-account-id>` isliye taaki naam **globally unique** rahe
- Agar yeh exact naam already kisi ne le liya hai, toh aakhir mein ek letter/number jod do — bas safe jagah note kar lo apna naam
- Buckets ek region ke andar unique hone chahiye

6. **Default encryption** rehne do (change mat karo)
7. Ek **index** set up karo with:
   - **Dimensions: 384** ← yeh exactly sahi hona chahiye, kyunki `all-MiniLM-L6-v2` model 384-dimensional vectors banata hai. Mismatch = error.
   - **Distance metric: cosine** (cosine similarity — sabse common similarity calculation, vectors ki "direction" compare karta hai)
   - **Index name: `financial-research`**

Ho jaane par tumhe Console mein dikhega: `alex-vectors-...` bucket ke andar ek index `financial-research`, status running. Bas yahi chahiye.

### Step 2: ingest Lambda function samjho

**AWS Lambda** (background): serverless compute. Tum ek function likhte ho, AWS use **on-demand** chalata hai (request aaye tabhi), tumhe server provision/maintain nahi karna padta. Pay-per-invocation. Week 2 mein Lambda detail mein cover hua tha.

Ab project structure:

- `backend/ingest/` folder — yeh ek **poora apna UV project** hai (apna `venv`, apna `pyproject.toml`)
- **`ingest_s3_vectors.py`** — important Python module jismein ek **`lambda_handler`** function hai

`lambda_handler` ka logic (transcript ke according):

1. Environment se padhta hai: **vector bucket ka naam**, **SageMaker endpoint ka naam**, aur **index name** (default `financial-research` agar specify na ho)
2. Jab call hota hai (text ke saath): text ko **vector mein convert** karta hai (SageMaker endpoint call karke)
3. Us vector ko **S3 Vectors bucket** mein store kar deta hai

Bas — "does what it says on the tin". Ek serverless endpoint jo text leta hai aur vector store kar deta hai.

```python
# backend/ingest/ingest_s3_vectors.py (reconstructed shape)
import os

def lambda_handler(event, context):
    vector_bucket = os.environ["VECTOR_BUCKET"]
    sagemaker_endpoint = os.environ["SAGEMAKER_ENDPOINT"]
    index_name = os.environ.get("INDEX_NAME", "financial-research")

    text = event["text"]                       # incoming text to ingest
    vector = embed_via_sagemaker(text, sagemaker_endpoint)  # text -> 384-dim vector
    store_in_s3_vectors(vector, vector_bucket, index_name)  # write to S3 Vectors
    return {"statusCode": 200, "body": "ingested"}
```

### Step 3: Lambda ko package karo — `package.py`

Lambda par deploy karne ke liye code ko ek **zip** mein bundle karna padta hai. Iske liye `backend/ingest/package.py` hai — ek **cross-functional Python script** jo Lambda ko package + upload-ready bana deta hai.

`package.py` kaise kaam karta hai:

1. Ek temporary directory banata hai jiska naam **`build`**
2. `build` mein wo sab cheezein copy karta hai jo Lambda function ko chahiye — including `ingest_s3_vectors.py` module
3. Us sab ko zip karta hai ek file mein: **`lambda_function.zip`**
4. Temporary `build` directory delete kar deta hai

Yeh ek **standard approach** hai: apna Python module likho jo function ka kaam kare, phir ek packaging script likho jo use zip mein bundle kare upload ke liye. Week 2 mein bilkul aisa hi pattern tha.

### Step 4: package script chalao

Terminal kholo, project root se navigate karo:

```bash
cd backend/ingest
uv run package.py
```

- `uv run` — UV (fast Python package manager) ka command jo project ke virtual environment ke andar script chalata hai
- Script kuch print statements dikhata hai aur **`lambda_function.zip`** create karta hai
- Zip ka size ~**15 MB** hota hai (dependencies ki wajah se thoda bhaari)

Output:

```
lambda_function.zip   (~15 MB)
```

Ab Lambda deployment package taiyaar hai. **Agla step: Terraform** (next lecture) — jo is zip ko upload karega aur API Gateway + IAM + Lambda resources wire karega.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **S3 Vectors** | AWS ka native vector storage; OpenSearch se ~90% sasta; classic S3 se alag service |
| **Vector bucket** | S3 Vectors ka container; globally-unique naam chahiye (`alex-vectors-<account-id>`) |
| **Index (384 dims, cosine)** | Vector index — dimensions `all-MiniLM-L6-v2` se match (384), similarity = cosine |
| **`lambda_handler`** | Lambda ka entry-point function — text → SageMaker se vector → S3 Vectors mein store |
| **Manual (non-Terraform) bucket** | Long-lived resource; `terraform destroy` se survive kare; course end par manually delete |
| **`package.py`** | Packaging script: `build/` temp dir → copy code → zip → `lambda_function.zip` → cleanup |
| **`uv run`** | UV se project venv ke andar script run karne ka command |
| **API Gateway + API key** | Production-grade secure entry point (next lecture mein wire hoga) |

---

## 💼 Backend Dev Ke Liye Note

Python backend dev ke liye yeh ek **classic data-ingestion microservice** hai, bs serverless avatar mein. `lambda_handler(event, context)` = tumhara request handler; `event` = request payload (yahan `{"text": ...}`), aur business logic = "embed + persist". Jis tarah tum ek Flask/FastAPI endpoint likhte jo DB mein row insert karta, yahan tum text ko vector banakar S3 Vectors mein write kar rahe ho. Do production patterns yaad rakho: (1) **config injection via environment variables** (bucket/endpoint/index names hardcode nahi, env se aate hain — 12-factor app principle), aur (2) **build artifact = zip** — Lambda ka deployment unit ek immutable zip hota hai, bilkul Docker image ki tarah. `package.py` tumhara `Dockerfile`/CI build-step ka equivalent hai. Aur architecture call note karo: stateful, long-lived data store (vector bucket) ko ephemeral infra (Terraform-managed Lambda/API) se **alag lifecycle** mein rakhna — yeh production mein critical hai taaki infra rebuild se data destroy na ho.

---

## ✅ Takeaway

- **S3 Vectors** = AWS native vector store, OpenSearch se ~90% sasta — cost-conscious RAG ke liye ideal
- Vector bucket **manually** banao (Terraform se nahi) taaki vo `destroy/apply` cycles survive kare; index = **384 dims + cosine**, naam `financial-research`
- **ingest Lambda** (`ingest_s3_vectors.py` ka `lambda_handler`): text → SageMaker embed → S3 Vectors store; saari config env vars se
- **`uv run package.py`** se ~15 MB ka `lambda_function.zip` banta hai — Lambda ka deployment artifact
- Agla step: **Terraform** se Lambda + API Gateway + API-key auth deploy karna

---

<details>
<summary>📜 Full Transcript (English)</summary>

So here we are in the Alex project. And we're going to start by going into guides. And it's time for us to look at the third guide. Ingest MD ingestion pipeline with S3 vectors. Okay. In this guide we're going to deploy a cost effective vector storage solution S3 vectors 90% cheaper than OpenSearch uh, and a lambda function for the document ingest and API gateway with API key authentication and integration with the SageMaker embedding endpoint. And the reason so we're we're going to be using this API gateway because this is the kind of bulletproof production, uh, type of, of construct that you'd have in place to make sure that you've got the right kind of security. Okay. So, uh, let's get started. There's there's a little bit of an explanation there that S3 vectors is their new native vector storage solution. Uh, and it is a different to S3, S3 vectors or one word like that. Okay. So the first thing we're going to do is create our S3 vector bucket. And we're not going to use Terraform for this, because this is going to be like a one time thing that will survive, even if you bring down and bring up the infrastructure. We want to keep this bucket sitting around. And so this will also be something that once you're done with the course, you will need to come in and delete the old fashioned way, which we'll see in the Resources Explorer because we don't we want this to be done uh, the manual way. So let's go now to the AWS console to create this bucket. Okay. So here I am in as my IAM user, as you can see from AI engineer over there, not editor I'm going to come in, I'm going to search for S3 and go into S3. And then I'm going to come down here to vector buckets and select vector buckets on the left to see S3 vectors. And here we go. Now you won't see this because you won't have created it. You have to press Create Vector bucket to create your vector bucket. And the name you should give it should be hyphen vectors hyphen. And then your account ID because it's got to be unique. Unique. The the uh S3 buckets have uh global Namespace. So they need to be unique across all users. So this is a good way to do it. If for some reason your one is taken, someone else has taken a bucket with this name exact name with your account ID, then just pick a different number. Uh, put a put a letter at the end of it. That's fine. You just need to be put somewhere safe for you. Um, I think they have to be unique across one, one region. Uh, so, uh, then if you if you follow the instructions, it explains that you set up that as your bucket name. Uh, you keep the default encryption, you then have to come in and set up a index. Uh, and it has to have 384 dimensions. You need to get that right, because that's the number of dimensions in the all mini LLM, L6, v2 model and the distance metrics. How it judges whether vectors are similar should be cosine, the cosine similarity calculation which is the most common one uh, and call it financial research. So if we come back into my screen, you'll see that if I click in on Alex Vectors, I do indeed have one index. It's called financial research. It's been set up and it's running and you should have the same. So we are now going to deploy a lambda function. And it's a lambda function called ingest. And let's take a look at what ingest does. It's in its own folder in backend called ingest. And if we look in that folder you'll see that it's an entire UV project on its own. Right. It's got like a venv of its own, a virtual environment. It's got a py project.toml in there, and it has an important Python module called ingest S3 vectors py. And let's just look at this for a second. It's open right here. So this is something which is basically it's it's one of these Python modules that has a lambda handler function, which you may remember from week two. Hopefully you remember from week two. Uh, this is something that we'll be able to deploy and call as a serverless endpoint. And it's something which is going to expect some text and it's going to write it out to S3. Uh, so it, it looks in the environment for the name of a vector bucket for a SageMaker endpoint, and for an index name that will be financial research if it's not specified. And basically when this lambda handler is called, cold. It's going to do just what it says on the tin. It is going to change the text into a vector, and it's then going to store that vector in the S3 vectors bucket. It's going to do all of that operation. That's it. And that's coming under the lambda handler function in this module. Now let's see how we deploy that. So now I want to show you one other Python module in this in this directory in just called package.py package.py is like a cross-functional Python script that will package up our lambda function and upload it. So how does it work? Well, it creates a temporary directory called build and in build it first of all will will package up everything that we need for this, this Python function, this lambda function. So it copies in the ingest S3 vectors.py, which is the class we were just looking at the module we were just looking at a second ago. It then zips that up into a zip file, and that zip file is going to be called lambda Function dot zip. And then it deletes the stuff that it had as a temporary directory. So that's what package dot Pi does. And this is a pretty standard kind of approach. You write your Python module to do your function, and then you write something which will package it up into a zip file and be able to upload it. It's very similar to stuff we did in week two. Now it's time to run it okay. So bring up a new terminal window. Here we go. And now we're in the project root. Let's go into backend and let's go into ingest. Okay. We're in ingest. And now we're just going to UV run package dot Pi which is the module we were just looking at a second ago. And it's going to do the various print statements that you may have seen there. And it's already happened. It packaged up that lambda function. It created a deployment package called Lambda function, which we should see right there. Lambda function zip. And it's about 15MB in size. And it's ready. Uh, and as it tells us, about 15 megs. Okay. It's now time for us to do the terraform part.

</details>
