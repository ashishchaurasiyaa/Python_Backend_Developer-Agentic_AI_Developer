# L77 — Deploying SageMaker Embedding Models for Production RAG Systems

> **Week 3 · Day 3** · ⏱️ ~10 min

---

## 🎯 TL;DR

Hands-on lab: hum **Terraform** se ek **SageMaker serverless inference endpoint** deploy karte hain jo Hugging Face ka **all-MiniLM-L6-v2** embedding model chalata hai. `terraform init` + `terraform apply` se IAM role + SageMaker model + serverless endpoint ban jaate hain, phir backend se `vectorize.json` bhej kar test karte hain — text ka **384-dimensional vector** wapas aata hai.

---

## 🗣️ Hinglish Explanation

### Alex ki data-ingest picture (recap)

Ed Cursor mein Alex project ke **guides** folder mein **permissions guide** ka preview kholta hai, jahan top par ek **architecture picture** hai. Is week ki **data ingest** flow ka outline:

```
[ Scheduler ]  →  kicks off  →  [ App Runner (researcher) ]
                                        │ does research
                                        ▼
                                 [ Lambda function ]
                                        │ calls
                                        ▼
                          [ SageMaker endpoint ]  →  text → vector
                                        │
                                        ▼
                                 [ S3 Vectors ]  (knowledge base)
```

Yeh ek classic **RAG (Retrieval-Augmented Generation)** setup hai — store row-style knowledge base jise baad mein retrieval ke liye query kiya jata hai. (Agar RAG/vector storage/embeddings naye hain, toh Ed ka companion **LLM Engineering** course, Week 5 sab cover karta hai.)

### Aaj ka goal: SageMaker serverless embedding endpoint

Ed **second lab — SageMaker** mein jaata hai. Goal: ek **serverless SageMaker endpoint** deploy karna jo **embeddings** (vectors) generate kare Alex ke knowledge base ke liye.

Model choose: **all-MiniLM-L6-v2** — ek Hugging Face **sentence-transformers** model. Properties:
- **Bahut popular aur bahut fast** embedding model.
- Hugging Face se **directly download** ho jaata hai.
- Ed ke LLM Engineering course mein Week 8 mein use hota hai — familiar lag sakta hai.
- Output: **384-dimensional vector** (text ka meaning representation).

Endpoint **serverless** hoga, aur use **Terraform** se build karenge.

#### Serverless endpoint kya hota hai (background)

SageMaker do tarah ke endpoints deta hai:
- **Real-time (provisioned)** — ek instance hamesha chalta rehta hai, fast response, par idle hone par bhi paisa lagta hai.
- **Serverless** — koi instance idle nahi padta; request aaye toh SageMaker compute spin karta hai, kaam khatam toh band. **Pay-per-use**, intermittent/low-traffic workloads (jaise Alex ka periodic ingest) ke liye perfect aur **bahut sasta**. Trade-off: pehli request par thoda **cold start**.

### Step 1: Terraform variables configure karo

Terraform directory mein har guide ke liye **alag sub-directories** hain. Embedding lab ke liye **`2_sagemaker`** directory hai. Pehle us directory mein jao, phir example vars file ko copy karke real vars file banao:

```bash
cd terraform/2_sagemaker
cp terraform.tfvars.example terraform.tfvars
```

Naya `terraform.tfvars` kuch aisa hoga — apna AWS region bilkul sahi spelling se daalo:

```hcl
aws_region = "us-east-1"
```

⚠️ **Region exact spelling chahiye** — agar hyphen miss kar diya ya kuch galat likha (jaise `useast1` ya `us-east1`) toh trouble hogi. Ed ka mila `us-east-1`, tum apna daalo.

> **Terraform variables kyun?** `.tfvars` file environment-specific values (region, names, sizes) ko code se alag rakhti hai. `.example` file template hai jo repo mein commit hoti hai (no secrets); real `.tfvars` har developer apne values se banata hai aur usually git-ignore hota hai.

### Step 2: Terraform `main.tf` — kaunse resources ban rahe hain

`main.tf` Terraform definition file hai. Ed advise karta hai apne time mein padho. Andar yeh resources hain:

1. **Provider block** (top par) — AWS provider configure karta hai.
2. **IAM stuff — SageMaker role** — ek role jise SageMaker model assume karega (permissions: model artifacts pull karna, logs likhna, etc.).
3. **`aws_sagemaker_model`** — embedding model definition (kaunsa container image + model data).
4. **Serverless config** — memory size + max concurrent requests.
5. **Ek "sneaky" delay** — infrastructure properly set up hone ka wait (~15 sec). Iski tension nahi leni.
6. **`aws_sagemaker_endpoint`** — yeh **critical piece** hai. Asli endpoint jo upar wale serverless config se govern hota hai.

Reconstructed Terraform sketch (concept dikhane ke liye — actual repo file authoritative hai):

```hcl
provider "aws" {
  region = var.aws_region
}

# IAM role jise SageMaker assume karega
resource "aws_iam_role" "sagemaker_role" {
  name               = "alex-sagemaker-role"
  assume_role_policy = data.aws_iam_policy_document.sagemaker_assume.json
}

# Embedding model (Hugging Face all-MiniLM-L6-v2 container)
resource "aws_sagemaker_model" "embedding_model" {
  name               = "alex-embedding-model"
  execution_role_arn = aws_iam_role.sagemaker_role.arn

  primary_container {
    image = "<huggingface-inference-container-uri>"
    environment = {
      HF_MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
      HF_TASK     = "feature-extraction"
    }
  }
}

# Serverless inference config — memory + concurrency
resource "aws_sagemaker_endpoint_configuration" "embedding_config" {
  name = "alex-embedding-config"

  production_variants {
    model_name = aws_sagemaker_model.embedding_model.name

    serverless_config {
      memory_size_in_mb = 2048
      max_concurrency   = 5
    }
  }
}

# Sneaky delay taaki infra settle ho jaaye (~15s)
resource "time_sleep" "wait" {
  depends_on      = [aws_sagemaker_endpoint_configuration.embedding_config]
  create_duration = "15s"
}

# THE critical resource — the endpoint itself
resource "aws_sagemaker_endpoint" "embedding_endpoint" {
  name                 = "alex-embedding-endpoint"
  endpoint_config_name = aws_sagemaker_endpoint_configuration.embedding_config.name
  depends_on           = [time_sleep.wait]
}
```

### Step 3: Deploy — sirf do commands

Terraform mein deploy ke liye sirf do commands chahiye. `2_sagemaker` folder ke andar:

```bash
terraform init
```

`terraform init` pehli baar saari **state files**, dependencies set up karta hai aur providers locally install karta hai. Ed ka analogy: yeh **`uv init`** jaisa hai jo bhi locally setup/install karta hai. Pehli baar thoda time lega; dobara chalao toh kuch nahi karta (harmless to re-run).

```bash
terraform apply
```

`terraform apply` **the big command** hai jo sab kuch actually banata hai. Process:
1. Pehle **plan** dikhata hai — kya-kya create/change karne wala hai.
2. Tumse confirmation maangta hai — tum **`yes`** type karte ho.
3. Phir actually infrastructure build karta hai.

Ed ke liye yeh **2.5 minutes** mein complete hua (us 15-sec delay ke kaaran kam-se-kam itna toh lagega hi). Jo banaa:
- **IAM role**
- **SageMaker model** (sentence-transformers all-MiniLM-L6-v2)
- **Serverless endpoint**

### Step 4: Outputs aur `.env` file

Apply ke baad Terraform **outputs** print karta hai — including:
- **endpoint resource name**
- **endpoint ka naam** → `alex-embedding-endpoint`

Yeh endpoint name project ke **`.env`** file mein jaana chahiye. Default `.env` mein yeh already set hai (`alex-embedding-endpoint`). Agar tumne endpoint ka naam alag rakha hai, toh `.env` mein manually update karo:

```bash
SAGEMAKER_EMBEDDING_ENDPOINT=alex-embedding-endpoint
```

Output dobara dekhna ho toh:

```bash
terraform output
```

### Step 5: Endpoint test karo

Backend directory mein jao:

```bash
cd ../../backend
```

(Ed note karta hai: yeh commands cross-platform hain, par PC par path mein **backslash** `\` chahiye forward-slash ki jagah.)

`backend` folder mein ek file hai **`vectorize.json`** jismein bas text hai:

```json
{ "inputs": "vectorize me" }
```

Hum jaanna chahte hain: is text ka **vector kaisa dikhta hai**? Iske liye AWS CLI se freshly-deployed endpoint ko **invoke** karte hain:

```bash
aws sagemaker-runtime invoke-endpoint \
  --endpoint-name alex-embedding-endpoint \
  --content-type application/json \
  --body fileb://vectorize.json \
  output.json && cat output.json
```

Breakdown:
- `aws sagemaker-runtime invoke-endpoint` → SageMaker runtime ko inference ke liye call.
- `--endpoint-name alex-embedding-endpoint` → kaunsa endpoint (apna naam alag ho toh badlo).
- `--content-type application/json` → bata rahe hain ki payload JSON hai.
- `--body fileb://vectorize.json` → input file ka content.
- Result `output.json` mein, phir print.

**Bam — ek vector aata hai.** Ed confirm karta hai yeh **384-dimensional vector** hai jo is model ke liye "vectorize me" ke peeche ka **meaning** represent karta hai. Iska matlab: humne successfully ek **open-source model apne SageMaker endpoint par production mein deploy** kar diya, aur wo kaam kar raha hai.

### Cost aur cleanup

- Endpoint **extremely cheap** hai — par **hamesha current pricing check karo** (document likhe waqt ke prices badal sakte hain).
- Agar Alex constantly chale toh cost is order ka hoga (agar pricing same hai).
- ⚠️ Ed strongly suggest karta hai: **kaam ke baad infrastructure destroy karo** — `terraform destroy` se.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **all-MiniLM-L6-v2** | Hugging Face sentence-transformers embedding model — fast, popular, 384-dim output |
| **Embedding endpoint** | Live service jo text leta hai aur vector deta hai |
| **Serverless endpoint** | Idle par cost nahi; request par compute spin — pay-per-use, intermittent loads ke liye |
| **Terraform `.tfvars`** | Environment-specific values (region, names) code se alag |
| **`terraform init`** | State/providers locally setup karta hai (≈ `uv init`); re-run safe |
| **`terraform apply`** | Plan dikhata hai → `yes` → actual infra banata hai |
| **`aws_sagemaker_endpoint`** | Critical resource — asli deployed endpoint |
| **`invoke-endpoint`** | AWS CLI command endpoint ko inference ke liye call karne ke liye |
| **384-dimensional vector** | all-MiniLM output — text ke meaning ka numeric representation |
| **`terraform output`** | Apply ke outputs dobara dikhata hai |

---

## 💼 Backend Dev Ke Liye Note

Yeh lecture backend devs ke liye **IaC + microservice deployment** ka perfect example hai. Embedding endpoint ko ek **stateless inference microservice** ki tarah dekho: input JSON → output JSON, koi session state nahi. **Serverless config** (`memory_size`, `max_concurrency`) bilkul tumhare **Lambda/container concurrency tuning** jaisa hai — under-provision karoge toh throttling, over-provision karoge toh paisa barbaad. **IAM role** = service ki identity/permissions (least-privilege follow karo). Terraform ka **plan → apply → confirm** flow tumhare **DB migration ya deployment review** workflow jaisa hai — pehle diff dekho, phir commit. Aur `terraform.tfvars.example` vs `terraform.tfvars` ka pattern wahi hai jo `.env.example` vs `.env` — template commit hota hai, real values git-ignore. Cleanup discipline (`terraform destroy`) ko **ephemeral environments / teardown** ki habit ke roop mein lo — chalti hui idle infra = silent bill.

---

## ✅ Takeaway

- **all-MiniLM-L6-v2** ko ek **SageMaker serverless endpoint** par deploy kiya, poori tarah **Terraform** se
- Deploy = sirf do commands: **`terraform init`** (setup) + **`terraform apply`** (plan → `yes` → build); Ed ke liye 2.5 min laga
- Banaa: **IAM role + SageMaker model + serverless endpoint** (`alex-embedding-endpoint`)
- Test: AWS CLI `invoke-endpoint` se `vectorize.json` bheja → **384-dim vector** mila ✅
- Endpoint **bahut sasta** hai par pricing check karo aur **`terraform destroy`** se cleanup karo
- Endpoint ka naam **`.env`** mein jaata hai (default already set: `alex-embedding-endpoint`)

---

<details>
<summary>📜 Full Transcript (English)</summary>

And here we are in cursor in the Alex project going into guides. I'm just going to one more time show you open the preview on the permissions guide to show you at the top. Here was this picture. And this gives you now a little bit more insight. And again we're going to we're going to be talking more about this picture over time. But just just now you're starting to see something we're going to be doing this week. As I say the data ingest side of Alex. And so you're going to be seeing something where we're going to be kicking something off that is going to be calling App Runner, that's going to be doing some research. That's going to go into a Lambda function, that's going to end up calling a SageMaker endpoint to turn text into a vector. And that vector is getting stored in S3 vectors, a sort of standard row style knowledge base that we'll use for retrieval. And if you are new to Rag and vector storage and what embedding vectors are, then again, my my companion course LM engineering week five is when we cover all of this stuff, but hopefully this is all had to you. You know exactly what's going on. So anyway, we are going on to the second lab, SageMaker, to do our serverless deployment of SageMaker. Welcome back. Uh, in this this guy, we're going to deploy our SageMaker serverless endpoint to generate embeddings, vectors that will be used for Alex's knowledge base. Uh, and there's some, uh, information about why SageMaker, which you now know. Well, we're going to use a model called all mini LM v2, which is a hugging face model. And again, uh, you may be familiar with this if you've taken my LM engineering course because it's the one we use in week eight. Uh, it's a very popular and very fast, uh, one that we'll be able to download from Hugging Face directly. And we'll be using a serverless endpoint and will be endpoint will be building it using Terraform. And we've completed the first lab so we are ready to go. Okay let's do this. So step one is to configure our Terraform variables. So if you open up the Terraform directory now you will see that it has, as I promised you separate directories for each of the guides. We're going to open up the two underscore SageMaker directory that maps to this guide. And here are all of the details. And you'll see that there is a Terraform vars. There's there's an example one. Sorry I see you should first go into that directory. Uh so let's do that together. Go into Terraform. Uh go into the the two directory and now copy terraform.tf. Dot example and copy that to just be terraform.tf vars. Now I won't be able to do that because I've already run this. But you should do that now. And what will happen of course, is that you will now have a Terraform, for example. But you'll also have a terraform.tf vars and it will just say AWS region equals and there'll be something for you there. And mine is US East one. You should put in your one. And do note that it has to be spelled exactly right, and if you get anything wrong like you miss that hyphen, then there'll be trouble. So don't do that. Um, so, uh, back to the guide. Um, then once you've done that, it's just down to deploying the Terraform code. Let's see what's involved in that. So let's look for a moment at the main file, the Terraform definition. And this is where I advise you to to look through it in your own time. Get a sense of what we're creating. You'll see the usual provider stuff at the top. And then you will see that we are creating some IAM stuff SageMaker role. And then uh, we're creating a AWS SageMaker model and embedding model. And then we're making a, uh, embedding serverless config, which is giving it a memory size and how many concurrent requests can come in. We've got something in here which is sneaky, which is just doing a delay that makes sure that the infrastructure sets up properly. You don't need to worry too much about that. And then we've got here our AWS SageMaker endpoint. That's the critical piece of infrastructure we're making, the endpoint uh, and uh, it's configured by, by the serverless config that was defined above. And that's it. Those are the resources. So how do we actually make these happen. There's just two commands in Terraform that are just terraform init and then terraform apply. And that's all we have to do. We'll do that right now. So I'm in the two folder. Uh I'm going to type terraform init. Now terraform init won't do anything for me because I've run it before. It'll be super fast for you. It'll take a bit more time. Probably terraform init. You run it the first time, and it sets up the kind of all of the the state files, the things it needs, and it installs things locally. It's, uh, I guess it's a bit like doing UV init, which also sets things up and installs things locally so it gets everything ready for you. And if you've already run it, it doesn't do anything again. So it's harmless to run it twice. Okay. Uh, and now we're going to do terraform apply. And that is the big command which actually creates everything. It first plans what it's going to do, and it describes it right here. And then you have to type the word yes. And then it goes and actually builds it, which is what is happening right now. And so now that infrastructure our SageMaker endpoint is being created, it's going to be an endpoint which will allow us to run an open source model. The all mini Lmv two L6 v2 model will be able to run. It's an embedding model that will take text and turn it into a vector. And that is being created right now as an endpoint. and it will probably take a little bit. It may take the I think there's a 15 second delay in there that we saw. So we're expecting at least that. And at the end of it, we should have an endpoint that will be able to use in a quick test. And I will be back when it's created in a second. Well, that's completed for me. It took 2.5 minutes and I've got some output there. As it explains here, what was created was the IAM role, the SageMaker model, and the serverless endpoint for running this model. And the model is of course the sentence Transformers model, all mini LM, L6, v2, and it's outputted some important information for us, including the the endpoint resource name, but also the name of the endpoint that's being created. It's called Alex Embedding endpoint. And that is something that needs to go in our env file. And it's already there because that was part of the default one. Looks like that. But if for some reason you've called yours differently that's something other than Alex embedding endpoint, then you will need to go into your env file and update that. But if this printed out exactly what it's printed here, then there's no further action for you that is all set up in your env nicely, but you could go and check if you wish. Uh, okay. And it does mention here as well that if you ever want to see this output again, you can always run Terraform output as your way to get that again. Okay, it's time now for us to go and test this. Okay. So we're now going to go to our backend directory. So let's go up one up another and go into our backend. And I sometimes. So some of these instructions I'm, I'm a bit uh sloppy that for a PC of course it needs to be a backslash not a forward slash. But it didn't feel like this was worth having a PC and a mac version, because I think you will follow along now. But but these other commands should be cross-platform commands. So we're now in the backend directory. And what we want to do now is call something which is going to make use of a a, uh, file that I've already prepared called vectorize JSON. Uh, that is sitting around. Let's have a look. We are in right now. We're in the back end folder. So if I open the backend folder, uh, you will see there is indeed a file here called vectorize me. Let's see what it has. It just has some text vectorize me in it. And what we want to know is what does that look like as a vector? Uh, that's that's that's what we're about to do, uh, using our using our SageMaker endpoint that we just deployed. So this is, this is the code we're going to call AWS SageMaker runtime. We're going to invoke an endpoint. We're going to pass in the name Alex embedding endpoint. Obviously change that if you've given it a different name. Uh we're saying that it's JSON and we're going to pass in vectorize JSON. Uh, and then print the results to the output. So this is going to be the command that's going to be calling out to SageMaker right now to our freshly deployed endpoint and bam, there comes a vector. I do believe it's 384 dimensional vector, a vector which to this to this model represents the meaning behind the words vectorize me. And this is showing that we have successfully deployed an endpoint, an open source model that we're running on an endpoint of our own that we can access. It's called Alex embedding endpoint. And it is working. And it's also extremely cheap as this pricing should always check pricing because this was as of when this document was written. It may change, always check. But this should be very small indeed. Um, and if you were to run Alex constantly it would be this, this kind of amount if pricing hasn't changed. But I'm going to of course suggest that you destroy infrastructure after you've you've worked with it. So it's it's very cheap endpoint. But we have successfully deployed our SageMaker endpoint and we have a model running in production.

</details>
