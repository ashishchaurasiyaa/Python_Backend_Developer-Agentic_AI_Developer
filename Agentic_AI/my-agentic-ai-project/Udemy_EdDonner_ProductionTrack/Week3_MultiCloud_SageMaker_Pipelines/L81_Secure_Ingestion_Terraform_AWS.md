# L81 — Setting Up Secure AI Ingestion Pipelines with Terraform and AWS

> **Week 3 · Day 4** · ⏱️ ~8 min

---

## 🎯 TL;DR

`lambda_function.zip` ko deploy karne ke liye Terraform ka **third (`3_ingestion`)** module set up karte hain — variables (`region`, SageMaker endpoint name) configure karke `main.tf` (S3 bucket + versioning + SSE + IAM + Lambda + API Gateway + API key) ko `terraform init && apply` se chala dete hain. Outputs se API endpoint aur **private API key** nikaal kar `.env` mein daalte hain. Ed ek pro-tip bhi deta hai: Terraform aaj-kal LLM se generate karke verify karna hi best practice hai.

---

## 🗣️ Hinglish Explanation

### Recap: Terraform aur IaC (background)

**Terraform** ek **Infrastructure as Code (IaC)** tool hai. Tum apni cloud infrastructure ko **code (HCL — HashiCorp Configuration Language)** mein declare karte ho (`.tf` files mein), aur Terraform usse **provision** kar deta hai. Fayde: version-controlled infra, reproducible deployments, `apply`/`destroy` se poora stack up/down. Week 2 mein yeh detail mein cover hua tha.

Pichle lecture mein humne `lambda_function.zip` (ingest Lambda) banaya tha. Ab usse actually AWS par deploy karna hai — Terraform se.

### Step 1: Terraform variables configure karo

Project ke Terraform folder mein left side **`3_ingestion`** naam ka third section hai — yahi aaj ka kaam.

Pehla step: variables set karna. Ek example file hoti hai `terraform.tfvars.example`. Use **duplicate** karke apni `terraform.tfvars` banao (yeh wo file hai jo actual values hold karti hai aur git se ignore rehti hai — secrets/per-environment values yahan jaate hain).

```bash
# 3_ingestion folder ke andar
cp terraform.tfvars.example terraform.tfvars
```

`terraform.tfvars` mein do cheezein set karo:

```hcl
region                  = "us-east-1"               # jo bhi region tum use kar rahe ho
sagemaker_endpoint_name = "alex-embedding-endpoint" # default; agar tumne alag naam diya tha toh wahi
```

- **`region`** — wahi AWS region jismein tumne SageMaker/S3 banaya
- **`sagemaker_endpoint_name`** — by default `alex-embedding-endpoint` (jo pichle din banaya tha); agar tumhare endpoint ka naam alag hai toh yahan update karo

### Step 2: `main.tf` ke andar kya hai (samajh ke liye)

`main.tf` woh Terraform code hai jo poori infrastructure banaata hai. Ed ek quick tour deta hai:

1. **Providers block** — usual stuff (AWS provider, region config)
2. **`aws_s3_bucket`** — vector bucket reference, naam `alex-vectors-<account-id>` (default; agar tumne alag naam chuna tha toh yahan daalo)
3. **`aws_s3_bucket_versioning`** — bucket par versioning (object ke versions track hote hain)
4. **Server-side encryption (SSE) configuration** — data at-rest encrypt
5. **IAM stuff** — IAM **role** + **policy** taaki Lambda ko zaroori services tak access mile (S3 Vectors write, SageMaker invoke, CloudWatch logs)
6. **`aws_lambda_function`** named **`ingest`** (function name `alex-ingest`):
   - **Role** = upar wala IAM role (jo permissions deta hai)
   - **Zip file location** = `../../backend/ingest/lambda_function.zip` (do directory upar jaake `backend/ingest/` mein)
   - **Handler** = entry point (`ingest_s3_vectors.lambda_handler` style — Week 2 se familiar)
   - **Timeout = 60s** (function ko 60 sec tak chalne ki ijaazat)
7. **API Gateway** — ek gateway naam `api` jo ingest ke liye use hoga. Iske routes Lambda ko hit karte hain.

```hcl
resource "aws_lambda_function" "ingest" {
  function_name = "alex-ingest"
  role          = aws_iam_role.lambda_role.arn
  filename      = "../../backend/ingest/lambda_function.zip"
  handler       = "ingest_s3_vectors.lambda_handler"
  runtime       = "python3.12"
  timeout       = 60
  # ... environment variables: VECTOR_BUCKET, SAGEMAKER_ENDPOINT, INDEX_NAME
}
```

### API Gateway + API key = bulletproof production endpoint

**API Gateway** (background): AWS ka managed service jo HTTP endpoints expose karta hai aur unhe backend (Lambda, etc.) se connect karta hai. Iske saath tum security, rate-limiting, auth wagairah add kar sakte ho — without apne code mein yeh sab likhe.

Yahan key idea: **API key authentication**.

- Endpoint sirf tabhi use ho sakta hai jab caller ke paas **approved API key** ho
- API key ke through tum **quota** (kitne requests total) aur **throttling** (per-second rate limit) bhi laga sakte ho — yaani control over "kitna data ingest hoga"
- Yeh **"bulletproof way to build production endpoints that scale"** hai — random log/bots tumhara expensive SageMaker+Lambda pipeline abuse nahi kar sakte

Ed bolta hai: yeh settings padho, LLM se aur detail mein explain karwa lo agar chahiye — *"another great rabbit hole"*.

### Step 3: Terraform run karo

```bash
cd terraform/3_ingestion
terraform init     # providers/modules download (Ed ne pehle se chala rakha hai)
terraform apply    # resources create karega
```

`terraform apply` kya karta hai:

1. Ek **plan** dikhata hai (kya-kya banega/badlega)
2. Confirm ke liye **`yes`** type karna padta hai
3. Phir banata hai (order roughly): IAM permissions → Lambda function (+ zip upload + handler set) → API Gateway (+ security/scalability constraints)

### Ed ka important pro-tip: Terraform LLM se generate karo

Ek natural sawaal: *"Ye saara Terraform aap dikha rahe ho — kya isi course ka point nahi tha ki main khud likhna seekhoon?"*

Ed ka jawaab (production reality):

> LLMs **Terraform generate karne mein bahut acche** hain. Ed bolta hai usne is course ka bahut saara Terraform aise hi banaya — usne resources describe kiye, LLM ne Terraform code likh diya, phir Ed ne **review/double-check** kiya. *"You should always check LLMs"* — par first pass turant mil jaata hai.

Iska matlab: har attribute/resource ko manually ratne ka point nahi. Workflow ban gaya hai: **LLM se first draft → run → verify** ki sab kuch waisa hi configure hua jaisa chahiye tha. Docs available hain par often zaroorat hi nahi padti.

### Step 4: Outputs aur `.env` setup

`apply` complete hone par Terraform **outputs** print karta hai:

1. **Vector bucket** — wahi bucket jo expect kiya tha
2. **API endpoint** — tumhara API Gateway ka URL
3. **API key retrieve karne ka command** — ek instruction (Ed isse run nahi karta on-camera, kyunki vo private key screen par dikha dega — insecure)

Private API key paane ke liye output mein diya gaya command chalao (shape):

```bash
aws apigateway get-api-key --api-key <key-id> --include-value --query value --output text
```

Yeh command turant tumhari **private API key** print kar dega.

Ab **`.env` file** update karo (project root mein). Part-3 section pehle se hoga; teen rows bharo:

```bash
# .env (part 3 section)
ALEX_VECTOR_BUCKET=alex-vectors-<account-id>      # Terraform output: vector bucket
ALEX_API_ENDPOINT=https://<api-id>.execute-api.<region>.amazonaws.com/...   # output: API endpoint
ALEX_API_KEY=<the-private-api-key>                # upar wale command ka output
```

- Ed bolta hai Mac wala `echo >> .env` instruction PC par achha nahi — **file browser se directly edit karna** behtar hai (cross-platform)
- Future mein agar yeh values bhool jao toh kabhi bhi **`terraform output`** chalaake dobara dekh sakte ho

Bas — `.env` set up, aur agle lecture mein hum end-to-end test karenge.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **`3_ingestion` Terraform module** | Day-4 ingestion stack ka IaC — Lambda + API Gateway + IAM + S3 wiring |
| **`terraform.tfvars`** | Actual variable values (region, SageMaker endpoint name); `.example` se copy karke banao |
| **`main.tf`** | Resources: S3 bucket, versioning, SSE, IAM role/policy, Lambda, API Gateway |
| **`aws_lambda_function`** | `alex-ingest` Lambda — zip path, handler, role, 60s timeout |
| **API Gateway + API key** | Secure entry point; key se quota + throttling = bulletproof, scalable endpoint |
| **`terraform init` / `apply`** | Init = providers download; apply = resources banao (`yes` confirm) |
| **`terraform output`** | Deploy ke baad values (bucket, endpoint, key command) dobara dekhne ka tareeka |
| **LLM-generated Terraform** | Ed ka pro-tip: LLM se draft → run → verify; manual ratna zaroori nahi |

---

## 💼 Backend Dev Ke Liye Note

Yeh lecture backend dev ke liye do tarike se relevant hai. Pehla: **secrets/config flow** — API key kabhi code mein hardcode nahi hoti, balki Terraform output → `.env` → runtime env var ke through inject hoti hai. Yeh bilkul wahi 12-factor discipline hai jo tum apne FastAPI/Django apps mein follow karte ho (`os.environ`, `.env` git-ignored). Dusra: **API Gateway ka API-key + quota + throttling** wo cheez hai jo tum app code mein middleware/decorator se karte (rate limiting, auth checks) — yahan vo **platform layer** par offload ho gaya, jo cleaner aur zyada robust hai. Aur Ed ka LLM-Terraform pro-tip seedhe tumhare daily workflow par lागू hota hai: boilerplate IaC/glue code LLM se generate karwao, par **review** ko skip mat karo — generated infra code production mein blindly trust karne wali cheez nahi. `terraform.tfvars` vs `main.tf` ka separation bhi note karo: code (logic) aur config (per-env values) alag rakhna — same principle as separating app code from `settings.py`/env config.

---

## ✅ Takeaway

- **`3_ingestion`** Terraform module deploy karta hai: S3 bucket + versioning + SSE + IAM + Lambda (`alex-ingest`, zip se) + API Gateway
- `terraform.tfvars.example` → copy → set `region` + `sagemaker_endpoint_name`; phir `terraform init && terraform apply` (`yes` confirm)
- **API key + quota + throttling** = production-grade secure, scalable endpoint (random callers block, cost control)
- **Outputs** se vector bucket, API endpoint, aur private-API-key command milte hain → **`.env`** mein teen rows bharo (`terraform output` se kabhi bhi dobara dekho)
- Ed ka pro-tip: **Terraform LLM se generate karo, phir verify karo** — manual nitty-gritty ratna zaroori nahi

---

<details>
<summary>📜 Full Transcript (English)</summary>

Okay, so now we just need to set up our Terraform. So if you come into Terraform on the left here and you see that there's a third section three ingestion. That's what we're working on right now. And the first step is to set up our Terraform variables. There's an existing file Terraform.tf example. You can take this copy it, duplicate it to make your own Terraform dot which you're going to then update. If we look in this, you'll see that you'll need to change the region to be whatever region you're using. And then the SageMaker endpoint name. It's by default Alex embedding endpoint. And that should be what you already have. If for some reason you had a different name of your endpoint, then that's what you should put in here. And then you've set up your Terraform variables and your you're almost ready for action. We should have a quick look at Main.tf, which is here, which is the Terraform code that creates this infrastructure. And what you'll see, it's got the usual providers stuff. And then we have the Terraform code that gets everything set up. There is the AWS S3 bucket and this has the bucket name of Alex vectors dash r account id. If for any reason you had to choose a different one, then you would put that in here. But otherwise this should work great. This is the the default. Uh, then um, we've got uh, the, the S3 bucket versioning. We've got some configuration here for server side encryption. Uh, and we've then got the IAM stuff that needs to be there so that Lambda has access, uh, and uh policy. And here is our AWS Lambda function called ingest. The function name is Alex Ingest. This is the role that we just created that it's it's IAM role that gives it access to to carry out the functions it needs. And this is where to find the zip file. So you go up two directories, you go into back end ingest. And then it's called lambda function zip. That's what we create it. And uh then we tell it what handle to use. If you remember this from week two and we we give it a timeout of 60s. And this is all that it needs to do what it needs to do. We also set up an API gateway. And this is where we're setting up a gateway called API that will be used to, to ingest, uh, and you can read some of the, the uh, the parts what the routes that are supported by this API gateway and using API gateway is a way to build bulletproof, secure production endpoints. And, uh, you can read in here that, uh, how it's configured to be using our endpoint. And, uh, you can see that we're setting up to have an API key. We want to make sure that you can only use this endpoint if you have an approved API key. And this is a way that we can also set quota and throttling around how much data is ingested. So so take a look through these settings. You can always ask an LLM to explain them in more detail if you'd like or do some research. It's another great rabbit hole. But this kind of approach of setting an API key that we'll have to retrieve in a second and use as part of our configuration, and having a quota and throttling around an endpoint like this. This is the kind of bulletproof way to build production endpoints that scale. Okay, so to recap, we've set our configuration variables the AWS region and the SageMaker endpoint name. And now it's time for us to run Terraform init Terraform. Apply those two commands. Let's open a new terminal. Let's go into the terraform directory. Let's go into the third directory. Here we are terraform init. I've already run it so it's not going to do too much for me. There it goes. And Terraform apply. It's now going to go off and create all of the resources we just looked at. Uh it does a plan and we have to type the word yes to confirm that that's what we want to build. It's now going to be creating the IAM permissions. It's then going to be creating the lambda function itself and uploading that zip file and setting up the handler. It's also then going to be setting up the API gateway so that we have this kind of bulletproof thing and security and scalability constraints around our endpoint. And when this is done, I'll be right back and we'll be able to give it a try. And now I just wanted to make a point. It's already it ran almost immediately after I stopped recording that. I want to make a point that you may be thinking, hang on a minute, hang on a minute. All this Terraform stuff you're showing us. Isn't that what the point of this course? Isn't this what I have to learn how to write myself? And? And you could be forgiven for thinking that. And what I will say to you is that it is remarkable how good llms are at generating Terraform code to configure different things that you want doing that you can then go through and check. So I have to say that that's the way that I built a lot of this. I went and I described the resources I needed and I got the Terraform code, the resources written immediately, and I checked through them. And then I do the kinds of double checking of things that I need to do. But because you should always check out Llms. But it turns out that they are really great at of this now, so there's little point in me going through and giving you all the nitty gritty of setting up the different resources and what attributes are allowed and not allowed. There are good docs for that, but you don't even need them. You can just use an LLM to generate the first pass of your Terraform scripts, and then run them and check that everything's configured the way you want. That's the way to do it. Okay. Anyway, with that preamble, let's have a look at what it's outputted. It's told us a few things. It's told us the vector bucket, which is the vector bucket that we expected the API endpoint. This is our API endpoint. And it's also told us an instruction for how we can get our private API key. So if we look on here we'll see that it says uh, what we now need to do is save our configuration in our EMV file. And the first thing we need to do is run this bit of code here. You can see it's of that form. We need to run this code to get our private API key. So I'm not going to run it because it will then show you my private API key which would be very insecure practice. So you should run that and it will immediately print below it an API key. Uh, and then we need to update our EMV file. Uh, and you can use this is like a mac instruction. So that that wouldn't be good for a PC, but it's equally easy and I recommend you do it simply using the file browser here. So you go to the project root and find your EMV file, and you click on it to edit it, and you need to add in three rows. You'll find already in the part three section in your EMV file. Already vector bucket needs to be the vector bucket. That's right here. Alex API endpoint needs to be the Alex API endpoint that's right here. See how convenient this is? And Alex API key is what you will get when you run this right here. When you run it it's going to give you the API key, the private API key for this endpoint. And that's what you need to put next in your dot EMV file. And remember you can always come back and see this by running Terraform output in the future. So with that please go ahead and do that. Set up your EMV file and I'll see you right back here.

</details>
