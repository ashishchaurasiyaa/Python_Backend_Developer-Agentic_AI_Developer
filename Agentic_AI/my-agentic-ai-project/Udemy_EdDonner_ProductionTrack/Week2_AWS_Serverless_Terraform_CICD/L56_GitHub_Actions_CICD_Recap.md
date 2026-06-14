# L56 — Automating AI Infrastructure Deployments with GitHub Actions CI/CD

> **Week 2 · Day 5** · ⏱️ ~9 min

---

## 🎯 TL;DR

Week 2 ke last din ka opening: pehle Terraform ke 6 core terms ka quick refresher (provider, variables, resources, state, output, workspace), phir naya topic introduce — **GitHub Actions** (actions, workflows, jobs) jo `git push` par automatically build aur deploy karta hai (CI/CD). Plus ek aakhri baar poori serverless deployment architecture ka recap.

---

## 🗣️ Hinglish Explanation

### Context: Week 2 ka grand finale

Yeh Week 2 ka **Day 5** hai — Ed ise *"icing to the cake"* bolta hai. Pehle 4 din mein humne AWS console se manually deploy kiya, phir Bedrock se LLM connect kiya, phir Terraform se infrastructure-as-code likha. Aaj last piece add ho raha hai: **GitHub Actions** — taaki jab tum `git push` karo, toh app **automatically build aur deploy** ho jaaye. Yeh "core platform engineering with an AI lens" wala week complete kar deta hai.

Is lecture mein actual coding nahi hai — yeh ek **recap + concept introduction** hai. Do hisse: (1) Terraform ka 6-term refresher, (2) GitHub Actions ke 3 core terms.

### Part 1: Terraform ka 6-term refresher

**Terraform** ek **Infrastructure as Code (IaC)** tool hai (HashiCorp ka). Iska matlab: tum apni cloud infrastructure (S3 buckets, Lambda functions, API gateways) ko **code/config files** mein declaratively likhte ho, aur Terraform un resources ko real cloud mein create/update/delete karta hai. Manual console clicking ki jagah — sab kuch versioned, repeatable, reviewable code. Ed 6 key terms se Terraform refresh karta hai:

#### 1. `provider`

Provider block batata hai ki kaun se **plugins** use karne hain — yaani kis cloud se baat karni hai (AWS, GCP, Azure, etc.). Terraform khud cloud-agnostic hai; provider plugin actual cloud API calls karta hai.

```hcl
provider "aws" {
  region = var.aws_region
}
```

#### 2. `variables`

Variables wo **parameters** hain jo tumhare deployment ko configure karte hain. `.tf` files mein declare hote hain, aur values `.tfvars` files se aati hain. Ed yahan ek important detail clarify karta hai jo wo pehle theek se explain nahi kar paaya tha:

- **`terraform.tfvars`** → default/general variable values (auto-load hota hai).
- **`prod.tfvars`** (ya koi aur) → production-specific values.

Konsi file select hogi yeh **deploy script** mein decide hota hai — agar production deploy ho raha hai toh alternative `-var-file` provide hota hai:

```hcl
variable "aws_region" {
  type    = string
  default = "us-east-1"
}
```

```bash
# deploy script ke andar — environment ke hisaab se var file switch
if [ "$ENV" = "prod" ]; then
  terraform apply -var-file="prod.tfvars"
fi
```

#### 3. `resources`

Yeh **absolutely key ingredient** hai. Har resource block ek actual cloud service describe karta hai — S3 bucket, har Lambda function, API gateway — sab resources ke roop mein attributes ke saath likhe hote hain. Terraform "took care of all business" — yaani tum resource describe karo, baaki creation/wiring Terraform handle karta hai.

```hcl
resource "aws_s3_bucket" "frontend" {
  bucket = "twin-frontend-${terraform.workspace}"
}

resource "aws_lambda_function" "chat" {
  function_name = "twin-chat-${terraform.workspace}"
  runtime       = "python3.12"
  handler       = "lambda_function.handler"
  # ... aur attributes
}
```

#### 4. `state`

State wahan hai jahan Terraform **apni "version of reality"** record karta hai. Yeh state real cloud ke actual state se match honi chahiye. Ye `.tfstate` files mein hoti hai jo abhi tumhari local directory mein hain — aur **typically source control mein check-in nahi hoti** (kyunki ismein secrets aur sensitive resource details ho sakte hain, aur concurrent edits conflict create karte hain). State Terraform ki "samajh" hai ki cloud mein actually kya chal raha hai.

#### 5. `output`

Output wahan list karte ho jo **results** Terraform deploy ke baad nikalne hain — jaise CloudFront distribution URL, S3 bucket name, API Gateway endpoint. Deploy script Terraform chalata hai, phir **outputs collect** karta hai, aur unhe use karke software ke different parts ke beech **connections** banata hai (e.g. frontend ko bata do API gateway URL).

```hcl
output "cloudfront_url" {
  value = aws_cloudfront_distribution.frontend.domain_name
}
output "api_gateway_url" {
  value = aws_apigatewayv2_api.chat.api_endpoint
}
```

#### 6. `workspace`

Workspace ek tarah ka **namespace** hai — yeh tumhe **same config ko alag-alag "universes" mein** replicate karne deta hai, har ek ka apna alag state. Iska classic use: **dev**, **test**, **prod** environments. Naam kuch bhi rakh sakte ho.

```bash
terraform workspace new prod
terraform workspace select prod
```

#### Deploy script — sab kuch jodne wali jagah

Ed kehta hai humne Terraform commands khud command line par rarely chalaye — sab kuch ek **deploy script** mein wrap kiya. Sabse common 3 commands:

```bash
terraform init      # plugins/providers download, backend setup
terraform apply     # resources create/update (state ke against)
terraform destroy   # sab resources delete
```

> **Doubt ho toh deploy script dobara padho** — wahi sab Terraform commands ek jagah dikhaata hai.

### Part 2: GitHub Actions — naya topic

**GitHub Actions** GitHub ke andar built-in **automation/CI-CD platform** hai. Mostly automated deployments ke liye use hota hai, par aur bhi cheezein kar sakta hai. **CI/CD** = Continuous Integration / Continuous Deployment — yaani `git push` karte hi kuch automatically build aur deploy ho jaaye, bina manual steps ke. 3 core terms:

#### 1. Actions (the platform)

GitHub Actions GitHub ke andar ek **module/platform** hai — main navigation mein ek alag **"Actions" tab** hai. Yeh scripts ko **automatically** ya kisi **user action** (jaise ek button push) ke response mein chala sakta hai. Literally ek button hoga jise dabaakar script trigger kar sakte ho.

#### 2. Workflows

Workflow = **series of steps** jo kisi **event se trigger** hoti hai. Yeh **YAML files** mein configure hoti hain. YAML files ek special directory mein jaati hain: project root mein **`.github/workflows/`** — ismein jo bhi hai wo ek workflow represent karta hai.

```yaml
# .github/workflows/deploy.yml
name: Deploy to AWS
on:
  push:
    branches: [main]   # main par push hote hi trigger
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Terraform Apply
        run: ./scripts/deploy.sh prod
```

#### 3. Jobs

Job execution time par hota hai — jab workflow kick off hota hai. Job = **series of steps** jo GitHub ke cloud mein ek **virtual machine (runner)** par run hote hain. GitHub ek runner VM launch karta hai aur tumhare job ke steps carry out karta hai.

#### GitHub Actions sirf CI/CD ke liye nahi

Ed batata hai Actions se aur bhi kaam ho sakte hain: push par naye **API docs generate** karna, **AI code review** chalana, etc. Lekin sabse common use CI/CD hi hai.

Aur ek important point: **CI/CD ke liye GitHub Actions hi nahi**, bahut saare platforms hain. **Jenkins** is duniya ka "OG" hai — bahut purana, comprehensive aur robust (poore courses uspe bante hain). GitHub Actions popular hai kyunki **lightweight, simple, aur already GitHub mein built-in** hai — jaldi start ho jaata hai.

### Part 3: Deployment architecture ka aakhri recap

Ed ek aakhri baar poora serverless architecture dikhaata hai — ab yeh "completely clear" lagna chahiye. Yeh **serverless architecture** hai (no always-on servers; Lambda on-demand chalta hai):

1. User browser mein **CloudFront URL** kholta hai → CloudFront ek **static website** serve karta hai jo ek **S3 bucket** se aati hai (frontend ka static site, globally distributed).
2. Static website ke andar ek **`fetch` command** hai jo **API Gateway** se linked hai (deploy script ne yeh wiring ki).
3. User chat karta hai → `fetch` **`/chat`** route call karta hai → **API Gateway** ise **Lambda function** se integrate karta hai (routes set up the).
4. **Lambda** (business logic) har chat par chalta hai, aur ek **S3 bucket** se connected hai jo **conversation history** rakhta hai — har browser ke UUID ke liye alag JSON objects.
5. Lambda **Amazon Bedrock** se connect karke LLM run karta hai — model: **Amazon Nova** (taaki poora week AWS-native rahe).
6. Result aata hai → conversation history mein store hota hai → user ko return ho jaata hai.

Yeh sab pehle **AWS console se manually** banaaya ("traumatic process"), phir **Terraform scripts** se describe kiya, aur ek deploy script likha jo `terraform init` + `terraform apply` chalata hai (workspace dev/test/prod set karke). Result: poora infrastructure automatically ban jaata hai — *"and it just works"*.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Terraform** | Infrastructure as Code tool — cloud resources ko config files mein declaratively likho |
| **provider** | Kaun se cloud plugin (AWS/GCP/Azure) use karna hai |
| **variables** | Deployment configure karne wale parameters (`.tfvars` se values) |
| **resources** | Actual cloud services (S3, Lambda, gateway) ka description — Terraform ka core |
| **state** | Terraform ka "reality record" (`.tfstate`); source control mein nahi jaata |
| **output** | Deploy ke baad nikle results (URLs, names) — connections banane ke liye |
| **workspace** | Namespace — same config ke alag environments (dev/test/prod) |
| **GitHub Actions** | GitHub built-in automation/CI-CD platform |
| **Workflow** | Event-triggered steps; `.github/workflows/*.yml` mein define |
| **Job** | Runtime steps jo GitHub ke runner VM par execute hote hain |
| **CI/CD** | Continuous Integration/Deployment — push par auto build+deploy |
| **Runner** | GitHub cloud ki virtual machine jahan job steps chalte hain |
| **Serverless architecture** | No always-on server; Lambda on-demand request par chalta hai |

---

## 💼 Backend Dev Ke Liye Note

Python backend dev ke liye yeh lecture do mature engineering practices ko jodti hai jo tumhe production mein roz dikhengi. Pehla, **IaC** — agar tumne kabhi prod environment ko manual click-ops se banaaya hai toh jaante ho wo kitna fragile aur non-reproducible hota hai; Terraform ka declarative model (provider/resource/state) tumhare Django/FastAPI app ki infra ko `git diff`-able, peer-reviewable code bana deta hai. State file ko source control se bahar rakhna (aur baad mein remote backend use karna) ek classic gotcha hai — secrets leak aur concurrent-apply conflicts dono se bachata hai. Doosra, **GitHub Actions** tumhare familiar `pytest` + `git push` workflow ke upar ek deployment automation layer hai: same YAML mein tum lint → test → build → deploy chain kar sakte ho, taaki har merge ek consistent pipeline se guzre. `.github/workflows/` ka mental model rakho — har file ek pipeline, har job ek isolated runner (fresh Ubuntu VM), aur secrets/credentials GitHub Secrets se inject hote hain (next lectures mein OIDC se AWS auth dekhoge — long-lived keys se behtar).

---

## ✅ Takeaway

- Terraform ke 6 terms yaad rakho: **provider, variables, resources, state, output, workspace** — yeh poora IaC mental model hai
- `terraform init` / `apply` / `destroy` — 3 most-used commands, usually ek **deploy script** mein wrapped
- **GitHub Actions** = built-in CI/CD; 3 terms: **actions** (platform), **workflows** (`.github/workflows/*.yml`, event-triggered), **jobs** (runner VM par steps)
- CI/CD ke aur tools bhi hain (Jenkins = OG); GitHub Actions lightweight aur GitHub mein already built-in hone ki wajah se popular
- Architecture recap: CloudFront → S3 frontend → API Gateway → Lambda → Bedrock (Nova) + S3 conversation history — ek complete **serverless** AI app

---

<details>
<summary>📜 Full Transcript (English)</summary>

Today is a fitting conclusion to a huge week. Today is the day that we add icing to the cake. We are going to put GitHub actions in the mix. A way for us to automatically deploy when we do a git push, amongst other things. And that really wraps up this week of kind of core platform engineering, with an AI lens on top of it, to build an AI application and be able to automatically build environments and push them out. And so to launch straight in at first, a very quick recap of what we learned about Terraform, and the best way to give you a refresher on Terraform is to go through the six key terms that we learned about Terraform, starting with the provider. You remember when we had, like the Terraform script, that provider and an open curly. And this is where you give you describe the plugins that you want to use for this Terraform configuration, which is going to be related to AWS or GCP or Azure or whatever variables, which are the the parameters that configure your deployment. Remember the TF files? Um, and I think I don't think I explained this well but but there's like a, there was a terraform.tf vars that was the general ones, the default ones that were used. And then we had one that was called prod. And the place that that was selected was in the deploy script. If you look at the deploy script, you'll see where it says if they're deploying production, then provide this variables file as the alternative. And so that's how we switched in different variables for our different environment and then resources. And this of course is the absolutely key ingredient resources which are each of those resources followed by a curly. And they describe the each of the services that we wanted to set up in AWS, the S3 bucket, the, the, um, each of the Lambda functions, they were all described there as resources with attributes that configured them. And Terraform took care of all business. And then we use state. This is where Terraform Records its version of Reality and state. These needs to match what's really going on. And this is something which is like the private Terraform files that you'll see right now in your directory in your project, which don't typically get checked up into source control. Um, and they, they are terraform's understanding of what's actually going on out there. The output is where you list out the the results that will come from doing a Terraform deploy. That would include things like your CloudFront URL. Uh, and that's an example, your distribution URL. And that's an example of something which when we had a deploy script we ran Terraform. Then we collected the outputs. We used that to find out okay. So tell me now which S3 bucket, where is the S3 bucket that has the front end and what is the CloudFront distribution. And then what is the the API gateway. That's another output. And then be able to to use that to make the various connections between the different parts of our software that we need to make. So that's using outputs. And then finally, the last term that we met is the word workspace, which is the way that you can like set a completely different namespace for everything. It allows you to have all of your state replicated in different universes. And of course, we use that as it's usually used to have a development environment, a test environment, and a production environment called dev test and prod. You can call them whatever you want. And the deploy script was the place that kind of brought it all together. And if in doubt, look through that deploy script again. See the different Terraform commands that were made. We didn't run Terraform commands ourselves very often. The terraform init, terraform apply and terraform destroy are the ones that you would use most often if you ran terraform at the command line, but it's pretty common to wrap it up in a deploy script like that and do it all in a in a script. Okay, that's the quick refresher on Terraform, and it's my great pleasure to introduce you to the final topic, the final area of expertise to build for you this week GitHub actions. So GitHub actions is all about automating deployments using tooling built into GitHub. And you can do other things with it too. But it is mostly about automated deployments and CI CD continuous integration, continuous deployment, the ability to make it so you can do something like GitHub, a git push, and something will get automatically built and deployed to prod. So there are three terms to to talk about here. And the first of them is is actions itself. So GitHub actions it's like a it's a like a platform within GitHub. It's a separate tab on the main nav that we'll click on to go into the actions module. And it's something which allows you to run scripts either automatically or in response to to a user taking an action like this icon of pushing a button, there is almost literally going to be a button we can push. Uh, in order to kick off a script. Workflows are what they call a, uh, something which is like a series of steps that should be triggered by some event. And they are configured using a type of file called a YAML file, which you're probably familiar with, and and YAML files get put in a special directory. It is in a directory called GitHub, in your in your project root and a subdirectory workflows. Anything in there represents a workflow. And the final bit of terminology is jobs. A job. This is something that happens at execution time when when when a workflow is kicked off and is running, a job is run. It's a series of steps that get carried out and it gets carried out on a virtual machine in GitHub land. So in GitHub on the cloud, it launches a virtual machine called the runner and carries out the steps in your the in your job. The steps in your job get run when the workflow is triggered. And it's worth pointing out that GitHub actions can be useful for more than just ci CD. They can do stuff like generate new documentation. When you do a push, it can. It can run something that looks at your repo, generates API docs and puts them there. It can do an AI code review. You can hook up all sorts of things to GitHub actions. It is most commonly used for CI CD, but you can do all sorts of stuff with it. And of course, the corollary of that is also worth pointing out that there are many, many more platforms that do CI CD than GitHub actions. GitHub actions is popular because it's very lightweight, simple, and it's already there built into into GitHub. But I'm sure many of you are familiar with Jenkins. Jenkins is like the OG of this world of CI CD, been around for a long time and it's very, very comprehensive and robust and huge. And I'm sure it's the topic of many courses, uh, much more than four weeks long. GitHub actions much quicker to get started. And we'll be able to to be doing stuff in our lab today. And I wouldn't be doing my job if I didn't show you one more time. Our deployment architecture. You're probably not getting sick of this, so you know it. Well, it doesn't look nearly as confusing as I hope as it looked the first time you saw this. Uh, it's completely clear to you now that we have lambda in the middle of this. we are using serverless functions. This is a serverless architecture as they're known. We're using Lambda for our business logic that gets called every time the user makes it, makes a chat, says something. It hits slash chat here that is connected with an S3 bucket that contains our conversation history. It's just different JSON objects for each Uuid associated with the browser. Uh, and uh, we've, we've got an API gateway set up which is exposing this. We integrated the gateway with our Lambda function. We set up those routes. And we first of all did all of that manually. And then we put it into some resource Terraform code. And it's just magically happening for us. We've got a front end static site in another S3 bucket that's been put on a CloudFront distribution and sent all over the world, a browser, when it's connected, the URL that you put in that browser is CloudFront URL, and so it serves up the static website. But in that static website There is that fetch command which includes. Within that fetch command it is linked to our API gateway. Our deploy script made sure of that. And so when the user does a chat it then calls down here. And our Lambda business logic connects to bedrock. Our API here connects to bedrock to run an LM. And we chose Amazon's Nova Foundation model so that we could we could be all AWS native this week and we get back the result. We put that in the conversation history. We return it to the user and everything comes together. And after going through the traumatic process of building this ourselves through the AWS console, we then move to Terraform. We use Terraform scripts to describe the infrastructure we ran. We wrote a deploy script that calls Terraform, init, and Terraform apply. After setting a workspace to be either dev or test or prod, and as a result of that, the whole infrastructure gets built and it just works.

</details>
