# L68 — Deploying AI Apps to Azure with Terraform Infrastructure as Code

> **Week 3 · Day 1** · ⏱️ ~10 min

---

## 🎯 TL;DR

Week 3 Day 1 ka last part: hum apne cyber-security agent (jo Docker container mein MCP server spawn karta hai) ko **Terraform** ke through **Azure Container Apps** par deploy karte hain — `terraform init → workspace select → az login → resource providers register → terraform plan → terraform apply`.

---

## 🗣️ Hinglish Explanation

### Recap: hum kahan hain

Yeh Week 3 ka Day 1 ka **part two**, "home stretch" hai. Pichle lectures mein humne ek **cyber security analyst agent** banaya (OpenAI Agents SDK + ek **Semgrep MCP server**), usse locally chalaya, phir Docker container mein chalaya. Ab final step: usi container ko **Azure** par cloud deployment karna — par is baar manually console se nahi, balki **Terraform (Infrastructure as Code)** se.

> Reminder: **Semgrep** ek static code analysis (SAST) tool hai jo code mein security vulnerabilities dhundta hai. MCP (Model Context Protocol) ek standard hai jisse agent external tools/servers se baat karta hai. Humara agent ek Semgrep **MCP server** ko container ke andar **standard IO** par spawn karta hai.

### Step 0: Pre-flight checks

Sabse pehle confirm karo ki Terraform installed hai. Naya terminal kholo aur:

```bash
terraform version
```

Agar version print ho gaya — installed hai. Warna terraform.io se download karo.

Phir **environment variables** load karo `.env` file se. Mac/Linux aur Windows ke alag commands hain (repo mein dono diye hain). Ye do secrets shell mein load hote hain:

```bash
# Mac / Linux example — .env se shell environment mein export
export $(grep -v '^#' .env | xargs)

# verify (optional)
echo $OPENAI_API_KEY
echo $SEMGREP_APP_TOKEN
```

- `OPENAI_API_KEY` → agent ka LLM call ke liye
- `SEMGREP_APP_TOKEN` → Semgrep cloud se authenticate karne ke liye

> **Kyun shell mein load karte hain?** Terraform secrets ko hardcode nahi karte. Hum env vars set karte hain, phir `terraform apply` ke time `-var` flag se inhe inject karte hain (neeche dekho). Isse secrets code/git mein commit nahi hote.

### Step 1: Terraform directory structure samjho

`week3/terraform` folder ke andar do sub-directories hain:

```
terraform/
├── azure/      ← aaj ka kaam
│   ├── main.tf          (providers + resources + outputs + variables sab ek file mein)
│   └── (.terraform/, *.tfstate — git-ignored internal state)
└── gcp/        ← kal (Day 2)
```

> **Terraform state files** (`.tfstate`) Terraform ka "memory" hain — wo track karta hai ki real cloud par kya-kya resources bana rakhe hain, taaki next `apply`/`destroy` par farak (diff) samajh sake. Ye git-ignored hote hain kyunki sensitive data ho sakta hai.

### Step 2: `main.tf` ke andar kya hai

Ed bolta hai ki tum khud isse padho aur Google karke samajh lo — par walkthrough deta hai. `main.tf` mein ye blocks hain:

```hcl
# 1) Providers setup — Azure + Docker
terraform {
  required_providers {
    azurerm = { source = "hashicorp/azurerm" }
    docker  = { source = "kreuzwerker/docker" }
  }
}
provider "azurerm" { features {} }
provider "docker" {}

# 2) Azure Container Registry (ACR) — image yahan push hogi
resource "azurerm_container_registry" "acr" {
  name                = "cyberanalyzeracr"
  resource_group_name = var.resource_group
  location            = var.location
  sku                 = "Basic"
  admin_enabled       = true
}

# 3) Docker image build — Terraform khud docker command run karta hai
resource "docker_image" "app" {
  name = "${azurerm_container_registry.acr.login_server}/cyber:${var.image_tag}"
  build {
    context  = "../../"
    platform = "linux/amd64"   # ⚠️ CRITICAL — mac par bhi amd64 build karo
  }
}

# 4) Log Analytics + Container App Environment
resource "azurerm_log_analytics_workspace" "logs" { ... }
resource "azurerm_container_app_environment" "env" { ... }

# 5) The main resource — Azure Container App
resource "azurerm_container_app" "app" { ... }
```

**Bohot important line:** `platform = "linux/amd64"`. Week 1 mein Ed ne is par emphasis diya tha — jab tum Docker image build karte ho, to **target platform** sahi hona chahiye. Agar tum **Mac (Apple Silicon / ARM)** par ho aur ye nahi doge, to image ARM ke liye banegi aur cloud (jo amd64 hota hai) par crash karegi. Best practice: hamesha explicit `linux/amd64`.

> **Naya concept:** Week 1/2 mein humne ek **alag shell script** likha tha jo Docker ko call karke image package karta tha. Is baar **koi script nahi** — Terraform ka `docker_image` resource khud Docker command chalaata hai. Yaani build bhi IaC ka hissa ban gaya.

`main.tf` ke aakhir mein **outputs** aur **variables** bhi hain (Terraform sab kuch squash kar deta hai, alag file zaroori nahi):

```hcl
# outputs
output "app_url"          { value = azurerm_container_app.app.latest_revision_fqdn }
output "acr_login_server" { value = azurerm_container_registry.acr.login_server }
output "resource_group"   { value = var.resource_group }

# variables
variable "project_name"     { default = "cyber-analyzer" }
variable "location"         { default = "East US" }
variable "resource_group"   {}
variable "openai_api_key"   { sensitive = true }
variable "semgrep_app_token"{ sensitive = true }
variable "image_tag"        { default = "latest" }
```

### Step 3: Terraform init + workspace

```bash
# Azure directory mein jao
cd azure

terraform init
```

Successful message milega (providers download ho jaate hain). Ab **workspace** select karo. Workspaces se ek hi config ke alag-alag environments (Azure vs GCP, ya dev vs prod) manage hote hain:

```bash
# Pehli baar — naya workspace banao (Ed already bana chuka tha)
terraform workspace new azure

# Ed ne sirf select kiya
terraform workspace select azure

# Confirm karo kaunse workspace mein ho
terraform workspace show     # → azure
```

### Step 4: Azure CLI login

```bash
az login
```

Browser khulega → Azure account se sign in karo. Agar already logged-in ho to seedha ho jaayega. Login ke baad **subscription select** karna padta hai — Ed se prompt "enter a number" aaya, usne `1` chuna (uske paas ek hi subscription thi).

```bash
az account show --output table
```

Ye confirm karta hai ki tum sahi subscription mein ho.

### Step 5: Resource Providers register karna (Azure ka IAM-jaisa concept)

AWS mein humne **IAM user permissions** ke through Lambda/S3 ka access diya tha. Azure mein analogous cheez hai **Resource Providers** — par alag tarike se sochi gayi hai:

- Azure mein tumhe explicitly **resource providers register** karne padte hain
- Ek baar register kar do, phir us subscription mein us type ke resources bana sakte ho
- Ye ek **one-time setup** hai — aur **FREE** hai (paise tab lagte hain jab actual resources use karo)

Ed ka opinion: ye IAM se **simpler construct** hai — kam granularity, zyada workable (bhale IAM zyada powerful/flexible hai).

```bash
# Container Apps ke liye
az provider register --namespace Microsoft.App

# Log Analytics (monitoring) ke liye
az provider register --namespace Microsoft.OperationalInsights

# Status check
az provider show --namespace Microsoft.App --query registrationState
az provider show --namespace Microsoft.OperationalInsights --query registrationState
```

Pehli baar register hone mein **1-2 minutes** lag sakte hain. Dono ka status `Registered` dikhna chahiye, tabhi aage badho.

### Step 6: `terraform plan` — preview (naya command!)

`terraform plan` batata hai ki **agar tum apply karoge to kya banega** — bina kuch banaye. Dry-run / preview samjho:

```bash
terraform plan \
  -var "openai_api_key=$OPENAI_API_KEY" \
  -var "semgrep_app_token=$SEMGREP_APP_TOKEN"
```

Yahan hum do variables pass kar rahe hain (jo `variables` mein declared the), **environment variables se set karke** (jo abhi `.env` se load kiye the). Dots connect ho gaye?

Output mein resources list honge jo banenge:
- Container App **Environment**
- Container **Registry** (ACR)
- **Log Analytics** workspace
- **Docker image**
- aur main wala — **Container App**

Bohot saari values `(known after apply)` dikhengi — yaani exact value tab pata chalegi jab actually banega (jaise auto-generated URL).

### Step 7: `terraform apply` — deploy!

```bash
terraform apply \
  -var "openai_api_key=$OPENAI_API_KEY" \
  -var "semgrep_app_token=$SEMGREP_APP_TOKEN"
```

Phir se plan dikhayega aur confirmation maangega → `yes` type karo. Off it goes — resources Azure par create hone lagenge. Ye 1-2 minute (ya thoda zyada) lega.

Ed ka point: ye sab **Azure console se manually bhi ho sakta hai** (aur AWS jaise manually karna ek baar sikhne ke liye accha practice hai), par aaj-kal Terraform ke saath ye zaroori nahi — Terraform ki "magic" se ek command mein ho jaata hai. Agle lecture mein dekhenge ki app live ho gayi.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Terraform (IaC)** | Infrastructure as Code — cloud resources ko config file (`main.tf`) se declare karke banao/destroy karo |
| **`terraform version`** | Check karta hai Terraform installed hai ya nahi |
| **Terraform state (`.tfstate`)** | Terraform ka memory — real cloud par kya bana hai uska record (git-ignored) |
| **Azure Container Registry (ACR)** | Azure ka private Docker image registry — AWS ke ECR jaisa |
| **`docker_image` resource** | Terraform khud Docker build/push chalata hai — alag script ki zaroorat nahi |
| **`platform = "linux/amd64"`** | Image target platform — Mac (ARM) par build karte waqt CRITICAL |
| **Azure Container Apps (ACA)** | Serverless container hosting — yahan humara app deploy hota hai |
| **Terraform workspace** | Ek config ke alag environments (azure/gcp) manage karna |
| **`az login`** | Azure CLI se account login + subscription select |
| **Resource Providers** | Azure ki IAM-jaisi cheez — service use karne se pehle one-time register karo (free) |
| **`terraform plan`** | Dry-run — apply se pehle dikhata hai kya banega |
| **`terraform apply`** | Actual deployment — resources cloud par banata hai |
| **`-var "key=$ENV"`** | Secrets ko env vars se Terraform mein inject karna (hardcode nahi) |

---

## 💼 Backend Dev Ke Liye Note

Python backend dev ke liye yeh lecture **multi-cloud IaC** ka practical hai. Tum shayad AWS Terraform dekh chuke ho (Week 2) — yahan **same Terraform tool, alag provider (`azurerm`)** hai, jo dikhata hai ki IaC ki asli power **portability** hai: provider blocks badlo, baaki workflow (`init → plan → apply → destroy`) identical rehta hai. `docker_image` resource ko Terraform ke andar daalna ek important pattern hai — tumhara CI/CD ab "build + push + deploy" sabko ek declarative graph mein dependency-order ke saath chalata hai (ACR pehle, phir image us registry par, phir container app us image se). Secrets handling note karo: `-var "openai_api_key=$OPENAI_API_KEY"` — ye **12-factor config** ka classic example hai (config environment se aata hai, code se nahi), aur Terraform `sensitive = true` se inhe plan output mein mask karta hai. Azure **Resource Providers** ko AWS service-enablement ka simpler analog samjho — coarse-grained per-subscription opt-in vs AWS ki fine-grained IAM policies.

---

## ✅ Takeaway

- Multi-cloud deployment same Terraform workflow se hota hai — sirf provider badalta hai (`azurerm`)
- `platform = "linux/amd64"` Mac par build karte waqt MUST hai, warna cloud par container crash karega
- Azure mein **Resource Providers** register karna AWS IAM ka analog hai — one-time, free, per-subscription
- `terraform plan` ek safe dry-run hai — `apply` se pehle hamesha check kar sakte ho kya banega
- Secrets ko `.env` → shell env vars → `terraform -var` ke through inject karo, kabhi hardcode mat karo

---

<details>
<summary>📜 Full Transcript (English)</summary>

Okay. So back in the week three folder we're going down to day one part two. We're in the home stretch. The last part for today. So we begin with a quick terraform. Check that it's installed. Open up a new terminal and type Terraform version. There we go. Terraform is installed and otherwise download it. And next up we're going to set the environment variables in this shell so that they are loaded in from the dot EMV file. There we go I've loaded mine in. There's a mac version and a windows version right here Mac or Linux. And now I've loaded the open AI key and the Semgroup app token into my shell. And you can run this echo if you want to prove it, but I'm quite sure that I've got them in. All right. Next up we're going to start by going into the Azure directory in Terraform. So CD Terraform. And I should show you actually before I go into Azure let me just show you this is the Terraform directory. It's got an Azure and it's got a GCP directory for tomorrow the Azure directory. It has a few of these uh git ignored files which are the the internal state of Terraform if you remember. And then it's got a main terraform and a terraform. You're now somewhat familiar with these. Let's just quickly take a look at it. So this is something which is setting up the providers, uh, which you remember sets up the providers. And then it sets up some resources, uh, the Azure Container Registry. Does that sound familiar? I hope so. Sounds like the Elastic Container Registry, does it not? And then we're going at Provider Docker. Now this is something a bit different here this time. You remember when we first did this we wrote a script which called Docker to package up what we were working with. Well you can also do this with Terraform. And so this time we don't have a script at all. We're using Terraform to run the docker command. And you'll note this super important line right here, which was the thing I focused on in week one, which is that when you build the Docker image, you need to make sure you build it for the right target platform. And particularly if you're working on a mac, it will cause you problems if you don't give this. But it's a good practice for everything. And then we're also setting up some log analytics and a container app environment, building these resources and then the Azure Container app. And so I'm just giving you this teaser for, for the right, uh, terraform that I've got here. You should look through this in your own time and satisfy yourself with what's going on. Do some googling and learn a bit about what's happening. And, uh, here are the outputs. By the way, you remember before we had outputs in a separate file. But as I told you, Terraform just squashes everything together anyway, so there's no harm in putting the outputs right in the same file, the app URL, the ACR login server, the the container registry, and the resource group the outputs. And over here the variables project name, location, resource group, open API key, grab app token and Docker image tag. Um, okay. So that is the Terraform script setup. And as I say, go through it, do some research, look it up. Uh, satisfy yourself that this makes sense. So anyways, back here again we now CD into Azure, which is the directory we were just looking at. So we are now in Terraform in Azure. And we can initialize Terraform. Remember that the commands are terraform init terraform apply uh and then terraform destroy at the end of it. Uh but we are going to start by doing terraform init. That's good. Nice successful message. And we're now going to select this workspace. So we say Terraform workspace. And I'm not actually going to do this new command. You should do this new command. But I've done it before. This is not my first rodeo. So I'm uh I'm going to just do the select Azure. Select Azure Terraform Workspace. Show. Show. This tells me which workspace am I in? I am in Azure. That's just as well. Okay. And now it's time to log in to the Azure CLI. And and then make sure that we've, we've got everything set up. I'm just going to explain about resource providers in just a second. So let me do a AZ login. And it brings me over to this. This is where I sign in with my account. Uh, and I'm already logged in. So that all worked great. Let me just move this window. So you see, it just popped this up, and it it would have had me do a login flow if I weren't already logged in. So now when I come back here, I am logged in, and you can see that all of that worked nicely. Uh, and I can also do this Azure account show minus minus output table. Uh oh. Hang on. Sorry. Oh, I have to select. I didn't see that it was saying enter a number. Number one is what I was meant to do. Sorry. So when you do that AZ log in you then have to select which subscription you want to be logging into. We only have one, so you do one. Uh, and uh, hope that made sense to you. And now I can do this. There we go. And all looks good. Uh, that is showing as your subscription one. My only subscription, which is what I am logged in as. So again, when you do a login, it will redirect you to a web page or bring up for you to log into Azure if you're not already logged in. And then you'll come back here and find you've been returned to this screen. It's going to ask you to select one of your subscriptions. Probably like me, you only have one and that's the one you pick. And then you are in. All right. And then we're just going to talk for a second about resource providers. So you may remember in AWS when we were getting access to things like being able to use Lambda or S3, the way we did it was by controlling the permissions of our IAM user, which had access to the, to the console. Uh, and so that was the process that we went through to give access. This is a somewhat analogous process. It's thought of differently in Azure, and the way it works is by enabling the services as Azure resources. So, um, once, uh, you need to explicitly register resource providers. And then once you've done that, you can then create resources of that type in that particular subscription. So it's like it's it's as it says here. It's like a one time setup. You do it once to say that this subscription is allowed, for example, to create container apps. And that's how how it how it works. And as it says, doing that is free. You only pay when you actually use the resources. So I actually think this is a simpler construct than the IAM permissions. I understand that IAM is super powerful and gives you so much flexibility, but this this level of granularity feels more workable to me. You have subscriptions. Within subscriptions, you enable different resource providers and then you can go ahead and do that, create containers. So that's what we do right now. So these commands are going to to enable just that. Let me bring back our terminal um AZ provider register Microsoft app and then this that, that gave us access to the container apps. This gives us access to the log analytics. And now we can just check that we have that oops check that we have that access. This could take a few minutes. Registered. Uh, I already had access because I've done this before, but I'm pretty sure the first time I did it, it did take like a minute or two before this came through and said registered for both, but now it says it right away. There we go. It says 1 to 2 minutes the first time, and they must both show registering for you to be ready to go ahead. Now actually this next command is a new one I haven't told you about before. Terraform plan. Terraform plan tells you what would be created if you did Terraform apply without actually doing Terraform apply. So it's sometimes worth doing just to. Just just to understand what happens. And you can see we're passing in two variables which get set as variables you might have seen were declared in variables, the OpenAI API key and the Semgroup app token. And we're setting them from our environment variables. And we a moment ago set those environment variables from our env file. Hope that all connects the dots for you. All right so there's the Terraform plan command running right now to tell us okay Terraform when we do an apply what are you going to do. So open this up and it's apply. And there we go. So it lists out here what are the things. What are the resources that it will create. Uh it says it will create uh, for example a container app environment and a container registry and uh, log analytics, a Docker image. Uh, and, uh, I was hoping to see where I probably missed it up here somewhere. Let's find it. And the container app, that is the main one that will be created. And you can see a lot of this as known after apply. So this gives you a good sense of what will be created when we run, uh, the, the the next command. Well, there we go. It tells us what we should see. And we're then going to run Terraform. Apply to actually make this happen. Okay. So here we go. I'm going to run Terraform. Apply. Copy that. Come down here. Paste. Run. Let's see what happens. See what happens when we run Terraform. Apply. It's going to again give us this plan and prompt us to say yes. If we're happy with this, which we are. Yes. And off it goes. Now it does its thing. Resources are being created. And of course, all of this is possible through the Azure console. And in some ways it is a good practice, just as we did with AWS to put yourself through, going through and doing this the manual way. But these days with Terraform, it's not necessary. Uh, you can make it do its thing all through the magic of Terraform. So we'll let it do its thing. It's probably going to take a minute or two, and I will see you on the other side.

</details>
