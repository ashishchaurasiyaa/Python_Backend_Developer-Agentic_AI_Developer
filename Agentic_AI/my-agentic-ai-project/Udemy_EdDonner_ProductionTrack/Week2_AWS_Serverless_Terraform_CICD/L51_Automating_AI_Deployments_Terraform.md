# L51 — Infrastructure as Code: Automating AI Deployments with Terraform

> **Week 2 · Day 4** · ⏱️ ~13 min

---

## 🎯 TL;DR

Terraform **install** karte hain (Homebrew/PC), `.gitignore` set karte hain (state files git se bahar, `terraform.tfvars`/`prod.tf` git mein), aur phir `terraform/` folder banake teen `.tf` files likhte hain — **`versions.tf`** (providers), **`variables.tf`** (settings like bedrock model ID), aur ek bada **`main.tf`** jo poore twin infra (IAM roles, S3, Lambda, API Gateway, CloudFront) ko code mein describe karta hai.

---

## 🗣️ Hinglish Explanation

### Wapas project mein

Casa (ghar 😄) wapas, twin project mein. Achhi khabar: **ab AWS console mein jaana zaroori nahi** — sab automatic hoga. Sirf ek exception: **IAM setup** (root se IAM user/permissions banane ke liye console abhi bhi chahiye) — par woh abhi nahi karenge.

Week 2 folder → Day 4 → instructions ka preview kholo. **Part 1** (clean manual resources) ho chuka. **Recommended interlude:** root se sign in karke **Cost / Billing** check karo — free tier par zero hi hona chahiye, par hamesha verify karo (chahe expected zero ho).

**Part 2: Terraform code ka structure samjho.** Yeh wahi 6 concepts hain, par ab "code mein kya dhoondhna hai":

```hcl
# RESOURCE — building block (e.g. S3 bucket). Type + name, phir curly braces mein attributes
resource "aws_s3_bucket" "memory" {
  bucket = "twin-prod-memory-123456789012"
  # ... attributes ...
}

# PROVIDER — like AWS. 'provider' keyword + name + params
provider "aws" {
  region = "us-east-1"
}

# VARIABLE — settings that control config
variable "environment_name" {
  type = string
}
```

- **State** — Terraform ki real-world understanding, special file **`terraform.tfstate`** mein. `.tfstate` files = Terraform's view of the world.
- **Workspaces** — separate states for dev/test/prod.

### Step 1: Terraform install karo

**Mac (Homebrew):**

```bash
brew tap hashicorp/tap
brew install hashicorp/tap/terraform
```

(`hashicorp` = company; founder Mitchell **Hashimoto** ka last name.)

**PC:** instructions/link follow karo (course page par diya hai).

Verify (naya terminal kholke):

```bash
terraform --version
# expect: Terraform v1.13.x  (ek recent version)
```

Ed ko **1.13** mila.

### Step 2: `.gitignore` set karo

Project abhi git repo nahi hai, par jaldi ban jaayega. `.gitignore` zaroori hai taaki galat cheezein git mein na jaayein. Terraform ke liye:

- **Git mein DAALO:** zyादातर Terraform code (`.tf` files).
- **Git se BAHAR (ignore):**
  - **State files** (`*.tfstate`, `*.tfstate.backup`) — yeh live AWS reality reflect karte hain, constantly badalte hain. Version control ke liye appropriate nahi.
  - **Lock files** (Terraform internal lock).
  - Other private files.
  - **`*.tfvars`** — variables jo secrets ho sakte hain.

Par exceptions hain — `.gitignore` mein **`!` (bang/exclamation)** lagao to force-include:

```gitignore
# ── Terraform ──
*.tfstate
*.tfstate.*
.terraform/
.terraform.lock.hcl
*.tfvars
!terraform.tfvars      # general/default vars — yeh INCLUDE karo
!prod.tf               # prod config — yeh bhi INCLUDE karo

# ── Python / build ──
.venv/
__pycache__/
*.env                  # environment files (ek chhoti exception aage aayegi)
lambda_package/        # build directory
lambda_deployment.zip  # zip artifact

# ── Node / frontend ──
node_modules/          # npm-installed stuff
# static build outputs
out/
.next/
```

> Note: `.gitignore` mein `!terraform.tfvars` ka matlab "is file ko ignore mat karo, repo mein rakho". Default/general vars (jo secret nahi) aur `prod.tf` ko hum chahte hain ki versioned rahein. (Ed: "uv.lock bhi normally source control mein chahiye — woh hum baad mein fix karenge.")

Ed sab copy karke `.gitignore` mein paste + save karta hai.

### Step 3: Terraform configuration banao (`terraform/` folder)

Project mein naya top-level folder: **`terraform/`**. TF files **conventionally split** ki jaati hain (par internally Terraform sab `.tf` files ko ek lambi list mein merge kar deta hai — jitni files chahe rakho). Aaj simplicity ke liye ek bada file rakhenge, par typically multiple hote hain.

**File 1 — `versions.tf` (providers + versions):**

```hcl
terraform {
  required_version = ">= 1.13"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}
```

Yeh batata hai: AWS provider use kar rahe hain, **US East 1** region mein.

**File 2 — `variables.tf` (settings):**

```hcl
variable "bedrock_model_id" {
  description = "The Bedrock model to use for the twin"
  type        = string
  default     = "amazon.nova-lite-v1:0"   # default value
}

variable "lambda_timeout" {
  type    = number
  default = 60                            # 60 seconds
}

variable "use_custom_domain" {
  type    = bool
  default = false                         # abhi false; baad mein true kar sakte hain
}

# ... aur variables ...
```

- `bedrock_model_id` — Ed ne kaha tha yeh variable hoga; default value yahan set hai.
- `lambda_timeout` — 60s.
- `use_custom_domain` — abhi `false`; baad mein custom domain ke liye `true` ho sakta hai (preview: custom domains aa rahe hain).

**File 3 — `main.tf` (the big one):**

Yeh **poora infra describe** karta hai — wahi sab "clicking around the console" jo pichle dino mein manually kiya tha, ab code mein. Typically isse multiple files mein todte hain, par aaj ek massive file. Kuch examples Ed dikhata hai:

**(a) IAM roles — Lambda ko Bedrock + S3 access:**

```hcl
resource "aws_iam_role" "lambda_role" {
  name = "twin-lambda-role"
  # assume role policy ...
}

resource "aws_iam_role_policy_attachment" "bedrock_access" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonBedrockFullAccess"
}

resource "aws_iam_role_policy_attachment" "s3_access" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
}
```

(Yaad hai? Manually humne Lambda ko Bedrock full access + S3 full access diya tha — yeh wahi hai.)

**(b) S3 bucket (memory) — variable prefix + account ID:**

```hcl
resource "aws_s3_bucket" "memory" {
  bucket = "${var.prefix}-memory-${data.aws_caller_identity.current.account_id}"
}
```

`prefix` ek variable hai jo `twin-prod` / `twin-dev` / `twin-test` ban jaayega (environment ke hisaab se) — isi se environments separate honge. Account ID baad mein append hota hai (S3 bucket names globally unique hone chahiye).

**(c) Lambda function:**

```hcl
resource "aws_lambda_function" "api" {
  filename      = "../backend/lambda_deployment.zip"   # kahan se upload karna hai
  function_name = "twin-test-api"
  role          = aws_iam_role.lambda_role.arn
  handler       = "lambda_handler.handler"             # remember: lambda handler
  runtime       = "python3.12"
  architectures = ["x86_64"]                            # x86 architecture
  timeout       = var.lambda_timeout                    # variable use ho raha hai

  environment {
    variables = {
      CORS_ORIGIN     = var.use_custom_domain ? "https://..." : aws_cloudfront_distribution.twin.domain_name
      USE_S3          = "true"
      BEDROCK_MODEL_ID = var.bedrock_model_id
    }
  }

  depends_on = [aws_cloudfront_distribution.twin]       # distribution pehle exist kare
}
```

Dekho:
- `handler`, `runtime`, `architectures`, `timeout` — wahi sab jo manually set kiya tha, ab code.
- **CORS origin** logic: agar `use_custom_domain` false hai toh AWS-generated CloudFront distribution use hota hai; true hai toh custom domain switch in hota hai (thoda complex conditional).
- `USE_S3 = true`, `BEDROCK_MODEL_ID = var.bedrock_model_id` — variables wire ho rahe.
- **`depends_on`** — Lambda tab tak fully create nahi hoga jab tak CloudFront distribution exist na kare (kyunki uska domain CORS var mein chahiye). Ed note karta hai: "yeh strictly required nahi — Terraform khud cross-dependencies figure out kar leta hai (resource references se dependency graph banata hai) — par explicitly likhne mein koi harm nahi."

**(d) API Gateway, (e) CloudFront distribution** — bhi yahin defined hain: HTTP methods (DELETE, GET, HEAD, ...), CloudFront ka S3 bucket origin hookup, etc. Saare fields jo manually set kiye the, code mein.

### Assignment (Ed ka homework)

Ed kehta hai woh apna rule tod raha hai (deep nahi jaane wala tha par resist nahi kar paa raha). **Tumhara kaam:** `main.tf` poora padho, har resource samjho, Google karo, aur satisfy ho jao ki yeh file un saare resources ko describe karti hai jo AWS par banenge. Yeh "rabbit hole worth exploring" hai.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **`brew tap/install hashicorp/tap/terraform`** | Mac par Terraform install karne ka tareeka |
| **`terraform --version`** | Install verify (Ed: v1.13) |
| **`.gitignore` + `!` bang** | State/tfvars ignore; `!terraform.tfvars` aur `!prod.tf` force-include |
| **`.tfstate` files** | Terraform's view of live world — git mein NAHI jaate |
| **`versions.tf`** | Provider + version pinning (AWS, us-east-1) |
| **`variables.tf`** | Settings: `bedrock_model_id`, `lambda_timeout`, `use_custom_domain` |
| **`main.tf`** | Poora infra: IAM roles, S3, Lambda, API Gateway, CloudFront — sab code mein |
| **`resource "type" "name" { }`** | Terraform resource block ka syntax |
| **`var.prefix`** | `twin-prod`/`dev`/`test` — environments separate karne ke liye |
| **`depends_on`** | Explicit dependency ordering (Lambda CloudFront ke baad) |

---

## 💼 Backend Dev Ke Liye Note

Backend dev ke liye yeh lecture HCL (HashiCorp Configuration Language) ka pehla real exposure hai, aur kuch patterns directly tumhari practice se connect karte hain. (1) **`.gitignore` discipline** — `.tfstate` ko ignore karna utna hi critical hai jitna `.env` ya `node_modules` ko; aur `!` bang-include exactly woh "ignore everything, whitelist exceptions" pattern hai jo tum monorepo gitignores mein dekhte ho. (2) **Implicit vs explicit dependency graph** — Terraform resource references (`aws_iam_role.lambda_role.arn`) se khud DAG banata hai aur sahi order mein create karta hai; `depends_on` sirf tab chahiye jab dependency code se visible na ho. Yeh wahi mental model hai jo build tools (Make, Bazel) ya DI containers mein hota hai. (3) **Config-driven multi-env** — ek `prefix` variable se `twin-prod`/`twin-dev`/`twin-test` derive karna, plus workspaces, woh classic "same code, different env" pattern hai jo tum 12-factor apps mein env vars se karte ho — bas yahan infra level par. (4) Lambda block mein `filename = "../backend/lambda_deployment.zip"` dikhata hai ki **build artifact aur infra-as-code coupled** hain — production CI/CD mein yeh zip pehle build hoga, phir `terraform apply` use deploy karega (jo Week 2 Day 5 ka CI/CD topic hai). Aur `architectures = ["x86_64"]` yaad rakho — agar tumhara build machine ARM (M-series Mac) hai par Lambda x86 hai, toh L48 wala Docker-build parity issue yahin se judta hai.

---

## ✅ Takeaway

- Terraform install: Mac `brew tap hashicorp/tap` + `brew install hashicorp/tap/terraform`; verify `terraform --version` (v1.13)
- **`.gitignore`**: `.tfstate` aur `*.tfvars` ignore karo, par `!terraform.tfvars` + `!prod.tf` force-include (bang `!`)
- `terraform/` folder mein 3 files: **`versions.tf`** (provider/AWS/us-east-1), **`variables.tf`** (bedrock model, timeout, use_custom_domain), **`main.tf`** (poora infra)
- `main.tf` = saara console clicking ab **code** mein: IAM roles, S3 buckets (prefix se env-separated), Lambda, API Gateway, CloudFront
- Resource syntax: `resource "aws_s3_bucket" "memory" { ... }`; variables `var.bedrock_model_id` se wire hote hain
- **Assignment:** `main.tf` khud padho aur har resource samjho — yeh rabbit hole worth exploring hai
- Aage `terraform init/apply` se yeh sab ek command mein build hoga (agle lectures)

---

<details>
<summary>📜 Full Transcript (English)</summary>

And here we are back in Casa and we're back in the twin project. And the great news is that we won't be needing to go to the AWS console, because we're going to be doing things automatically. The only time you do still need to go to the AWS console, of course, is IAM setup. When you're setting up, like going in as root to set up the permissions that you'll be able to give your IAM that that is still needed, but we won't be doing that right now. Uh, okay. So we go to the week two folder. We're now on day four. We open the preview to see our instructions for the day, and it starts with stuff about what you'll learn. Part one is cleaning manual resources, which we already did. Uh, hope you did that too. That's very good. And then, uh, it does uh, it doesn't suggest it here, but it should suggest that this might also be a good juncture to go and check your spend, pause for a second, go in as root and just check what your, your, uh, your cost and billing looks like. Make sure that it's exactly what you expect. I imagine all of you are on the free AWS sign up plan, in which case your your cost will be right, right? Zero. But it's always important to check, uh, even if you think it should be zero. Go and have a look. Anyways, go do that now and then. We are back. Part two is understanding Terraform. Well, uh, this, uh, as it says here, it's about being a version controlled, automated and repeatable. And here are some of the key concepts again. But this is now what to look for in the code. So this this structure is what Terraform code looks like. Resources of course are these essential building blocks. A resource is like an S3 bucket. So here's an example resource AWS S3 bucket. And then it's got a name and it's got, it's got uh, then the the attributes of that resource listed inside curly braces, uh, the state. So the state is is terraform's understanding of what's actually out there in real life. And it's stored in a special file called Terraform state. So TF state files contain Terraform's view of the world. I mentioned a provider. The provider is like AWS. That's a provider. And you define that with the word provider and then the name and then some parameters in curlies. And I mentioned variables. This is where you set uh parameters that control your, your your configuration like this one which has a name, uh, an environment name. And the type is a string. And then I mentioned workspaces that allow you to have completely separate states, say for development, test and production. All right. First things first. We need to install Terraform. Uh, and for a mac and a PC, these are the ways to do it. Uh, on a mac, If you use homebrew, then it's just this and this brew tap HashiCorp. That is the name of the company. The the key author, Mitchell Hashimoto. It's his last name. Uh. And, uh. Yeah. So then once you've done this, you should be able to. Let's bring up a new terminal window. And if you've done the, the, the, the PC way, there's a link here. Or you can, uh, run. Sorry, here's the link for a PC and it tells you what to do. And when we're ready, we need to do terraform minus minus version. And just check that we have version 1.13. That's a pretty recent version. Uh, look at that. It says version 1.1. We have 1.13. All right. And now it's time for us to set some things in a dot git ignore. Now I don't think I mentioned a git ignore before because this isn't actually a repo, but it will be soon. Soon enough. And it's good to have a git ignore to make sure that things that shouldn't be sent to git. Don't get sent to git when it comes to terraform. You want lots of things about Terraform to go and get, but there's some things that you don't want. You don't want these terraform state files in git because they relate to the current world out there on AWS and changes all the time. Not not appropriate for version control. Um, there's some lock files you don't want there. Uh, other private files, um, and TF vars are the variables that could be used to control what's going on. And they could have some, some secrets in them. But there is we want to when you put a bang, an exclamation mark in a dot git ignore it means. But you should include this in the repo. Uh terraform.tf vars the general variables. The default variables. We do want to include that. And actually we do want to include prod tf as well as you will see. Okay. Uh, while we're at it we might as well set up our dot git ignore to be to be good, which means that we want to not put into source code, control our zip file and that whole directory lambda package. We never want environment files in there, actually, with one little exception that will come up against later. Uh, and we don't want node modules, which is stuff that's been npm installed and the static outputs, um, and uh, any of this stuff and obviously a virtual environment. Uh, actually, uh, I think we'll, we'll, uh, we fix this later. But you've lock is something that, that you do normally want in source code control. Anyway, I'm going to copy all of that. I'm going to go to git ignore paste all of this in and save. And that is now setting up my git ignore so that we are in good shape. Okay, it's now time to create our Terraform configuration okay. So the next step then is to create our Terraform configuration. So we're going to create a new top level folder in our project called Terraform. There it is. We're now underway. Uh, and, uh, we are going to. Yes, we do indeed have this directory structure. We are now going to make our first Terraform file called versions with this. This is your first look at Terraform code. Now TF files are the key files which describe your configuration in code. And you can have as many of these TF files as you want. Terraform actually internally just brings them all together into one one long list. Uh, so uh, there's some conventions like it's common to have versions. It's really up to you. Uh, it is common to, to split things out. And today we're going to have one pretty big Terraform file just to keep things simpler. But it would be more typical to divide it into multiple. But anyway, for our first file, our first file is called versions. Here it is versions. And we're going to paste this in. Let. Let me tell you what this does. It is setting up our providers and their versions. Here they are. And save that we're saying that we're using AWS uh, in US East one. Okay. Back we go. That's our first Terraform file. The next one is defining some variables. It's going to go into Variables.tf. Here they are. Let's select the variables variables.tf in Terraform new file variables and paste. And let's have a look at this. This is all sorts of stuff that we're going to have through our configuration. It's got things like bedrock model ID I told you it was a variable. Here it is. And that's the default value right there. Uh the lambda timeout of 60s, uh, and various other things here. Uh, there's a special one here that we're not going to be using yet, but we will use later called Use custom domain, which is set to false, first of all, But later we may consider setting that to true. Uh, you may be wondering about custom domains, but it's been coming. Uh, okay. So that is variables back we go to here. Uh, it's now time for the big guy, uh, main. And as I say, it will be more typical to divide this into multiple files, but we're just going to have one massive great file here that describes everything. This is all Terraform code, which is doing all the clicking around in the console that we were doing in the last couple of days. Look at all this. Uh, so yeah, I mean, you know, in some ways there's still work to be done. There's no getting around that. Uh, but of course, it's, uh, definitely more in, uh, our world to be writing that as code instead of writing that as clicking instead of instead of having to do it manually through screens, which feels much less predictable and repeatable. So Main.tf is what we're calling this file, and we're pasting in the full contents. And let's just take a look somewhere here to give you some examples. Uh, here here is the, uh, setting up the IAM roles that are telling Lambda that it is as access to bedrock and S3. Remember when we did that? This is giving Amazon Bedrock full access and Amazon S3 full access to our Lambda component. That's an example of something that we configured and where it's getting set up. And you can see let's find something else. Let's find something simpler than that. That was quite an advanced one to start with. Uh, let's just find an S3 bucket. Here is an S3 bucket, which is called memory. Uh, it has uh, it's been given a like a prefix before it as a variable name. Then the word memory and then the account ID coming after it. And this prefix I'll give you a preview is going to be like twin. And then either prod or dev or test depending on the environment we're in. That's how we will be separating things out. Um, okay. And uh, yeah, that's, that's really that's all there is to it. And that's not really all. There's a whole huge file. Uh, it's all I'm going to explain of it. The action for you is to go through this and look through it and and learn from it. And, uh, you could if this is definitely a rabbit hole worth exploring. If you'd like to find out more about, uh, how you configure the, uh, different AWS services using Terraform here, for example, is a super important one is where we define the Lambda function, uh, called API. And we give it the file name that it has to upload from. From here, uh, we give it the name of the function twin, uh, test API. We give it, uh, the role. This is the handler. Remember when we set up lambda? Lambda handler. Handler. Uh, we give it, uh, the runtime. We tell it the x86 architecture. And this is where we use the variable that we set up for lambda timeout that we saw just a second ago. This is where we set the cause origin that all the chestnut you can see that there's some stuff here. There's some some complicated stuff. Because when we use a custom domain we need to switch in a different, uh, origin. But you can see basically that if we're not using a custom domain, then it's going to use the CloudFront distribution that's been generated for AWS. That's what's going to go in there. Use S3 is true bedrock model ID is the bedrock model ID variable that you saw being defined earlier. And this depends on, just as the comment says means that lambda is going to wait, uh, before it's fully created until the distribution exists, because it needs to be able to set that in this, this variable here. Um, I actually think this isn't strictly required, because I think that Terraform figures out those kinds of cross dependencies for itself, but there's no harm in saying it if you know that it's there. Okay, as I say, and here's the AWS API gateway. I'm not I'm not obeying my own. I can't resist telling you about these things. Uh, come and have a look through each of these to see. See how it all works. The CloudFront distribution right here, and see how all of the fields that we set ourselves are created here. Uh, this is the, the, uh, methods delete get head, uh, and, uh, hooking up our CloudFront distribution, um, to make sure that it's going to, to, uh, take the S3 bucket that we set up. So look through it all that's the to do. That's your assignment. And, uh, come back when you are, uh, you've seen it, you've done some googling, you've satisfied yourself that Main.tf describes the resources that we will be building on AWS.

</details>
