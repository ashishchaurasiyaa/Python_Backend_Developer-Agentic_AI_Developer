# L52 — Automating AI Deployments with Terraform and Shell Scripts

> **Week 2 · Day 4** · ⏱️ ~10 min

---

## 🎯 TL;DR

Terraform ki "heavy lifting" khatam — ab hum `*.tfvars` default variables set karte hain, frontend ko **hardcoded `localhost:8000` se hata ke environment variable** par le jaate hain, aur ek **deploy shell script** banate hain jo Lambda package build → `terraform init`/workspace select/`apply` → frontend env var inject → static site push, sab ek hi command mein orchestrate karta hai.

---

## 🗣️ Hinglish Explanation

### Context: Terraform ka aakhri pieces

Day 4 mein hum apni "digital twin" app (FastAPI backend on **Lambda**, static **Next.js** frontend on **S3 + CloudFront**, **API Gateway** front-door, **S3** for conversation memory, **Bedrock** for the LLM) ko **Infrastructure as Code (IaC)** mein convert kar rahe hain. Pichhle lectures mein `main.tf`, `variables.tf` likh chuke — ab "final pieces" baaki hain. Yeh lecture teen kaam karta hai: (1) default variable values, (2) frontend ka ek tricky configuration fix, (3) deploy scripts.

### Step 1: Default variable values — `terraform.tfvars`

Terraform mein `variables.tf` sirf variables **declare** karta hai (naam + type + optional default). Actual values dene ke liye Terraform automatically ek special file padhta hai: **`terraform.tfvars`**. Iska naam exactly `terraform.tfvars` ho toh Terraform isse bina kuch bole load kar leta hai (auto-loaded).

Naya file banao Terraform folder mein:

```hcl
# terraform.tfvars  (default variable values)
project_name   = "twin"
environment    = "dev"
bedrock_model  = "micro"   # Amazon Nova Micro — sabse sasta default model
lambda_timeout = 60        # seconds
use_custom_domain = false  # default: koi custom domain nahi
```

Ed bolta hai: "by default project name is twin, environment is dev, hum **micro model** use karenge by default, timeout 60, aur **no custom domain**." Yeh saari settings un variables ke against hain jo `variables.tf` ke `variable` blocks mein declare kiye the. Matlab: ek hi config, lekin defaults yahan, aur baad mein environment-specific overrides (`prod.tfvars`) alag file mein.

> 💡 IaC concept: variables + tfvars ka pattern ekdam wahi hai jaise tum Python mein `settings.py` / `.env` rakhte ho — code aur config ko alag karna, taaki same code multiple environments mein chal sake.

### Step 2: Frontend ka tricky fix — hardcoded URL hatao

Yeh lecture ka **sabse important conceptual point** hai, aur Ed deliberately ruk ke explain karta hai kyunki yeh "hard" hai.

Problem: frontend component (`twin.tsx`) mein browser API ko call karta hai. Originally yeh URL **hardcoded `http://localhost:8000`** tha — kyunki sab kuch locally chal raha tha. Jab manually AWS par deploy kiya, tab hum aake yeh URL ko apne **API Gateway** ke URL se hardcode kar dete the. Lekin **repeatable** deployment chahiye toh hardcoding nahi chalega.

Kyun? Kyunki:
- **Terraform tumhara code edit nahi kar sakta.** Terraform infrastructure provision/configure karta hai (S3 bucket bana do, Lambda deploy kar do, CloudFront distribution khada kar do) — par yeh tumhari `.tsx` source file ke andar jaake string nahi badal sakta.
- API Gateway ka URL **deploy ke baad hi pata chalta hai** (Terraform `apply` ka output). Toh build-time par yeh dynamic hona chahiye.

Solution: **Next.js environment variable**. Next.js mein koi bhi env var jo `NEXT_PUBLIC_` se start hota hai, build ke time browser bundle mein inject ho jaata hai (client-side accessible). Toh `twin.tsx` mein hardcoded URL ki jagah:

```tsx
// frontend/components/twin.tsx — pehle (galat, hardcoded):
// const apiUrl = "http://localhost:8000";

// ab (configurable, build-time inject hota hai):
const apiUrl = process.env.NEXT_PUBLIC_API_URL;
```

Yeh ek aham IaC lesson hai: **Terraform sirf infrastructure provision karta hai. Jab kuch tumhare *code* ke andar configure karna ho (jaise yeh env var) ya data *push* karna ho (static files S3 par), wo kaam deploy script karta hai — Terraform nahi.** Yeh dono cheezein "stitch" karna deploy script ki zimmedari hai.

### Step 3: Deploy shell script banao

Ab `scripts/` naam ka ek top-level folder banao, aur usme `deploy.sh` (Mac/Linux) banao. Ed Mac par hai toh Mac wale script par focus karta hai; PC users ke liye `deploy.ps1` (PowerShell) bhi hai.

> 💡 Tip (Ed se): "PC user ho aur WSL hai toh personally main suggest karunga sab kuch **Ubuntu side** par karo — zyada consistent rahega."

Reconstructed `scripts/deploy.sh` ka flow (transcript ke description ke hisaab se):

```bash
#!/usr/bin/env bash
set -euo pipefail

# Pehla argument = workspace ka naam: dev / test / prod
WORKSPACE="$1"

# 1) Lambda package build karo (backend folder mein, deploy.py se)
cd backend
uv run deploy.py        # zip file banata hai Lambda ke liye ("py" likhna superfluous hai)
cd ..

# 2) Terraform setup
cd terraform
terraform init          # providers/modules download karta hai

# 3) Workspace select/create karo (namespace jaisa)
terraform workspace select "$WORKSPACE" || terraform workspace new "$WORKSPACE"

# 4) Actual deployment — saare AWS resources create/update
terraform apply -auto-approve

# 5) Apply ke output se API Gateway URL nikaalo
API_URL=$(terraform output -raw api_gateway_url)
cd ..

# 6) Frontend ka tricky part: env var set karo, static site build karo
cd frontend
export NEXT_PUBLIC_API_URL="$API_URL"
npm run build           # Next.js static export banta hai, URL bundle mein inject hota hai

# 7) Static site ko frontend S3 bucket par push karo
aws s3 sync ./out "s3://twin-${WORKSPACE}-frontend"
cd ..

echo "Deployment complete! 🎉"
```

Ed ke words mein flow:

1. **Build Lambda package** — yaad hai `uv run deploy.py`? Wahi zip banata hai. ("Python" likhna superfluous hai; `uv run deploy.py` kaafi hai.)
2. **`terraform init`** — Terraform ko start/setup karta hai.
3. **Workspace select** — ek variable se aaya naam (`dev`/`test`/`prod`). Yeh teen **workspaces** = teen alag environments banayenge.
4. **`terraform apply`** — yahan actual script run hota hai, saare resources bante hain.
5. **The hard part** — frontend directory mein jaake `NEXT_PUBLIC_API_URL` ko `apply` ke output (gateway URL) par set karo.
6. **Build + push** — static site build, phir frontend S3 bucket par push.
7. **Output results** — done.

> 🧠 Terraform Workspaces kya hain: Ek hi `.tf` code se **multiple isolated state files** rakhne ka tareeka. Har workspace ka apna state, toh `dev` ke resources `test` ke resources se alag track hote hain. Naming `twin-dev-s3`, `twin-test-memory`, etc. — workspace naam resource names mein inject hota hai. Console se manually 3 environments banana **kill** kar deta, Terraform se trivial hai.

### Step 4: PC ke liye PowerShell script + permissions

PC users ke liye `scripts/deploy.ps1` (PowerShell) bhi paste karo. Mac par yeh PowerShell extension na hone ki complaint karega — ignore karo. PC par ek plugin install prompt aayega syntax highlighting ke liye — install kar lena.

Mac/Linux par ek **last cheez**: script ko **executable** banana hai —

```bash
chmod +x scripts/deploy.sh
```

`chmod` (change mode) file permissions badalta hai; `+x` execute permission add karta hai. Iske bina `./scripts/deploy.sh` "permission denied" dega. PC pe `chmod` ki zaroorat nahi.

> ⚠️ Ed ka note: PC users ko bhi `deploy.sh` apne repo mein laana hoga — "even though you can't run it on your box" — reasons "will become clear later" (yeh Week 2 Day 5 ke GitHub Actions CI/CD ke liye hai, jahan Linux runner par `deploy.sh` chalega).

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **`terraform.tfvars`** | Auto-loaded file jo declared variables ko **default values** deti hai (project_name, environment, model, timeout) |
| **Frontend env var injection** | `NEXT_PUBLIC_API_URL` — hardcoded `localhost:8000` ki jagah build-time par inject hone wala env var |
| **`NEXT_PUBLIC_` prefix** | Next.js convention — yeh env vars browser bundle mein inject hote hain (client-side accessible) |
| **Deploy script** | Shell script jo build + Terraform + env injection + S3 push ko ek command mein "stitch" karta hai |
| **`uv run deploy.py`** | Backend mein Lambda deployment zip banane wali command |
| **`terraform init`** | Providers/modules download + backend setup |
| **`terraform apply`** | Actual provisioning — resources create/update |
| **Terraform workspace** | Isolated state per environment (dev/test/prod) — ek code, multiple parallel infra |
| **`chmod +x`** | Mac/Linux par script ko executable banana (PC pe zaroorat nahi) |
| **Terraform ≠ code editor** | Terraform infra provision karta hai; code config aur data push deploy script karta hai |

---

## 💼 Backend Dev Ke Liye Note

Yeh lecture ek backend dev ke liye **deploy automation ka core lesson** hai. Tumne shayad pehle bhi `deploy.sh` jaise scripts likhe honge — par yahan key insight yeh hai ki **IaC tool (Terraform) aur imperative glue script (bash) ke beech ki line kahan khinchi jaati hai**. Terraform declarative hai (desired state describe karo), par real-world deployments mein hamesha kuch imperative steps hote hain: artifact build (Lambda zip), output-dependent config (gateway URL ko frontend mein feed karna), aur data sync (S3 par static files). Yeh chaar-step pattern — *build artifact → provision infra → read infra output → inject into app → push data* — har serverless full-stack deploy mein repeat hota hai. `NEXT_PUBLIC_API_URL` ka concept tumhare Django/FastAPI `.env` + build-time config se exactly map karta hai: secrets/config ko code se bahar rakho, environment se inject karo. Aur `terraform.tfvars` ko apne `settings/dev.py`, `settings/prod.py` jaisa samjho — same codebase, environment-specific values.

---

## ✅ Takeaway

- **`terraform.tfvars`** = declared variables ke liye default values (dev environment, micro model, 60s timeout, no custom domain)
- Frontend ka hardcoded `localhost:8000` hatao → **`NEXT_PUBLIC_API_URL`** env var, jo build-time par inject hota hai
- **Terraform code edit nahi kar sakta** — wo infra deta hai; deploy script gateway URL inject karta hai aur static files S3 par push karta hai
- **`deploy.sh`** ek command mein: Lambda zip build → `terraform init` → workspace select → `apply` → frontend build with env var → S3 sync
- Mac/Linux par `chmod +x scripts/deploy.sh` chahiye; PC users ko bhi `deploy.sh` rakhna hai (CI/CD ke liye later)

---

<details>
<summary>📜 Full Transcript (English)</summary>

And that's the heavy lifting done for Terraform. We're in the final pieces now. We need to set some default variable values. And this goes into a file called Terraform vars the defaults. So terraform new file two. Dot t vars terraform variables. Paste that in. So by default the project name is twin environment is dev. We're going to use the micro model by default. And these are the other the other values like the timeout of 60 and so on. And don't use a custom domain that is our default okay. So these are settings that for for the the variables right. Right here under under variables. Um back to the the instructions. We also need to make a quick little update to the front end. Uh, the in the front end, we've actually got it hard coded to go to localhost 8000. Like that. We're going to have to just change this to a slightly more sophisticated version. Change this this URL to be right here. So I'm going to just copy this right here. That's going to replace the URL in twin TSX. This is the URL called by our static frontend to the server. We can't make this that that that manual 8000 line anymore. So let's go and make that change. That is in um 20 uh s which is in front end in components in TSX. Here it is. Uh, and of course we did. We already changed it to be going. We hardcoded not localhost of course, because otherwise nothing would have worked. We had hardcoded it to be the the execute before we tried that out. Uh and now we're going to paste in here this and save that. And now it's going to take this environment variable instead. Okay. Now let's go back to uh, the um the Terraform code. Uh, sorry, the guide, I mean, and now we are going to, uh, come down here and we're finally at the time to create our deployment scripts, which are the shell scripts that we will run locally to kick off the Terraform process. Let's do that next. Actually, before we go on, I want to take a moment to to step back and explain something that I think I glossed over because it's, it's hard. So, uh, the twin TS file, this is part of our front end. This is something that's statically turned into a website. And we put this we put it into the CloudFront distribution. It goes all over the world. And it includes this line here, which is the place where your browser makes a call to the API gateway. And originally when we wrote this, this was hard coded to look at localhost 8000. And and that's because we're running everything locally. And we needed our front end locally just to hit our local server when we deploy this to AWS. We first deployed Lambda and then the API gateway and set that up. And then we came back here and we put over here the, the the the URL of our gateway deployment. So that that was then hard coded in so that this would always, uh, when it was deployed to the browser, the browser would always fetch from our API gateway route. And that's how we did it. And then we deployed our front end. Now we need to be able to do this in a repeatable way. And this involves digging into our code. So that's not something that Terraform is going to be able to do. It can't like edit the code you've got. And that's why this is an example of something which which then then requires you to take a bit of a step back. We need to make sure that in our code this is something that's configurable. And we'll use like a, like a Next.js way of having a variable that can get changed when this is actually built. And this kind of, this kind of bringing together of how your deployment is going to work is the kind of thing that you have in your deploy scripts, which brings everything together, which is what we're just about to do now and which is responsible for kicking off your Terraform process. So with that, let me let me save this change. And I hope that change looks a bit more sense to you now. And you see why this is this is a tricky part of the whole process that stitches together our front end and our back end. Okay, I feel better about that now. Now that we've explained that, I now want to take you to the deployment scripts. So we have different scripts for Mac and Linux, uh, and scripts for PowerShell for, for PC users. And I'm going to start by focusing on the Mac scripts. And by the way, if you're a PC user and you have WSL, I would always personally suggest that you do things in your ubuntu side. It's just going to make things more consistent for you. Uh, but uh, but anyways, you can choose for sure, but I'm on a mac, so I'm going to take the Mac script and I'm going to put it, I'm going to make a new folder called scripts. So let me do that now. New folder. I'm going to call it scripts. It's a new top level folder. And in this I'm going to put a new script called Deploy new file deploy shell. There it is. And I'm going to paste in that whole script. Here we go. And uh, let's just take a quick look at this deployment script. Okay. So it builds it first goes ahead and builds that Lambda package. You remember when we went to to backend and we did UV run deploy. Py see that Python is a superfluous. You can have it, but it's not needed. UV run deploy py is what we want. Uh, and uh we're then going to go into the terraform directory and we call terraform init. That sets up terraform. That gets Terraform started. Uh we are then going to change the workspace uh to make we're going we're going to select a workspace that is going to be given by a variable. We'll pass in with this script. And that is going to be the word uh dev test or prod. Those are going to be our three workspaces for a development environment, a test environment and a production environment because we're actually going to build three different environments with this. Imagine if we had to do that through the console. It would kill us. Uh, but it's going to be wonderfully simple using Terraform. Uh, we then called Terraform apply. That is the next command I think I mentioned to you, you do terraform init and then terraform apply. And that is where it actually runs a Terraform script. And it's then going to do all of its stuff. Uh, we then are going to, to uh, do the part where we, uh, this is, this is the hard part that I mentioned to you. This is where we go into the front end directory, and we're going to set this variable next public API URL to be the API. Uh, that came out of the, the uh, Terraform apply. And then we are going to use that to then push to AWS the front end bucket. Does that make sense. We do the Terraform apply and then we see okay so what was the gateway URL. We put that into this this environment variable for Next.js. And then we build our static site. And we push that to the front end bucket. And then we will be done and we will output the results. And so that's why that's what you need to do with the deployment script. And that's how you can think about the difference between the Terraform sets up all the resources, configures all the environment, but where you have something that requires you to come in and configure something in your code, and then do like a push of your, of your, of your data, that's something you would typically do in a deployment script just like this. Okay. Let's now just quickly make the script for PC. So come in here I'm going to go to the PC side. And obviously if you're on a mac you don't need to do this. But I will do it for completeness. Deploy one. So I copy all of this copy and I go to scripts New file, deploy PS1 and paste that in there. And it complains that it doesn't have PowerShell because I'm on a mac. When you do this on a PC, it's also going to prompt you to install a plugin so that it can highlight it looking nicely like this. And you should go ahead and do that so you get nicely highlighted. Uh, PowerShell script. But now we have these two scripts. And since I'm on a mac, there is one final thing that I need to do. Um, which is I need to come in here, and I need to, uh, on a mac, you will need to run this chmod command, uh, from, uh, that means that we can actually run the deploy script. So if I just bring up a new terminal window. Here it comes, I CD, I don't need CD scripts. I can just run this from from twin. And this is something that, uh, you could Google it if you don't know what chmod does, but it makes sure that I can actually have permission to run that script only needs to be done on a mac or Linux. Uh, but for PC people, you will actually need to also bring across this deploy.sh for reasons that will become clear later. Even though you can't actually run it on your box, you might be wondering why. Uh, you will see. So those are our deployment scripts. We're getting very close to being done now.

</details>
