# L60 — Setting Up GitHub Actions for Automated AI Agent Deployments

> **Week 2 · Day 5** · ⏱️ ~9 min

---

## 🎯 TL;DR

Terraform ka **S3 backend** configure karke remote state setup poora karte hain, GitHub repo mein **3 secrets** (role ARN, default region, account ID) add karte hain, aur phir `.github/workflows/` folder mein **`deploy.yaml`** aur **`destroy.yaml`** banake apni CI/CD pipeline ki bunyaad rakhte hain — ab `git push` se deployment trigger hoga.

---

## 🗣️ Hinglish Explanation

Yeh **Week 2 ka Day 5 ka lab** ka aakhri configuration piece hai. Pichhle lectures mein humne Terraform se infrastructure banana seekha, aur ek-do **temporary Terraform files** ke through GitHub Actions ke liye zaroori infra setup kiya — S3 buckets, DynamoDB lock table, aur ek IAM role + policies. Ab last puzzle piece: Terraform ko bolna ki apna **state** kahan store kare, aur GitHub ko credentials dena taaki wo AWS mein log in karke deploy kar sake.

### Terraform "state" aur "backend" kya hota hai

Terraform ek **state file** maintain karta hai (`terraform.tfstate`) jismein wo track karta hai ki abhi tak kaun-kaun se resources create ho chuke hain. Yahi state ki wajah se Terraform jaanta hai ki:
- Naya resource banana hai ya purana update karna hai
- Kya cheez delete karni hai
- Kya pehle se exist karti hai (duplicate na bane)

By default yeh state file **locally** machine par hoti hai. Lekin CI/CD mein problem aati hai — GitHub Actions har baar ek **fresh ephemeral VM** par chalta hai, jiske paas tumhari local state file nahi hoti. Isliye state ko ek **shared remote location** par rakhna padta hai jahan se har run usse padh/likh sake. Isi ko Terraform **backend** kehta hai.

- **S3 backend** → state file ko ek S3 bucket mein store karta hai (centralized, durable)
- **DynamoDB lock table** → **state locking** ke liye. Agar do log/process ek saath Terraform chalayein toh state corrupt ho sakti hai. DynamoDB ek lock leta hai taaki ek time par sirf ek hi `terraform apply` chale (race condition se bachao)

### Step 1: `backend.tf` banao

Terraform directory mein ek nayi file banao — naam `backend.tf`. Ed clarify karta hai: **file ka naam koi matter nahi karta** — yeh content `main.tf` mein bhi ja sakta tha. Terraform saari `.tf` files ko ek saath padhta hai. Alag file rakhna sirf **organization** ke liye hai.

⚠️ Important: yeh **temporary file nahi hai** — yeh "for reals" hai. Yeh permanent rehni hai kyunki Terraform ko isi se pata chalta hai ki S3 ko backend ke roop mein use karna hai.

```hcl
# backend.tf
terraform {
  backend "s3" {
    bucket         = "twin-terraform-state-<your-unique-suffix>"
    key            = "twin/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "twin-terraform-locks"
    encrypt        = true
  }
}
```

- `bucket` → wahi S3 bucket jo humne temporary Terraform file se banaya tha
- `key` → bucket ke andar state file ka path
- `dynamodb_table` → lock table ka naam
- `encrypt = true` → state file at-rest encrypt ho (state mein secrets ho sakte hain, isliye encryption best practice)

### One-time setup ka recap

Ed ne jo flow follow kiya wo samajhna zaroori hai:

1. Do **temporary** Terraform files banayi:
   - Ek S3 buckets + DynamoDB lock table banane ke liye
   - Ek IAM **role + policies** banane ke liye (taaki GitHub Actions AWS mein log in kar sake)
2. Dono ko **ek baar** run kiya — saara infra ban gaya
3. Temporary files **delete** kar di (kaam ho gaya)
4. Ab permanent `backend.tf` banaya

Yeh sab **one-time setup per repo** hai. Ek baar repo properly GitHub Actions se hook ho gaya, toh dobara karne ki zaroorat nahi.

### Step 2: GitHub mein 3 Secrets add karo

GitHub Actions ko AWS mein deploy karne ke liye **credentials** chahiye, par hum unhe code mein hardcode nahi karte — wo **Secrets** mein jaate hain (encrypted, repo settings mein).

GitHub par jaao → apni **twin** repo kholo → top nav mein **Settings** → scroll down → **Secrets and variables** → **Actions** → **New repository secret** (repository secret = poore repo par apply hota hai).

Teen secrets add karo (har naam **exactly** match hona chahiye):

| Secret Name | Value |
|---|---|
| `AWS_ROLE_ARN` | Wo role ARN jo temporary Terraform run se mila tha — GitHub ko batata hai AWS mein kaunsa role assume karna hai |
| `AWS_DEFAULT_REGION` | Tumhara default region (e.g. `us-east-1`) |
| `AWS_ACCOUNT_ID` | Tumhara 12-digit AWS account ID |

💡 **Pro hacks** Ed deta hai:
- **Copy-paste karo, type mat karo** — especially region. Ek chhoti typo baad mein ek obscure error de sakti hai jise track karna bahut mushkil hota hai.
- **Account ID** ka ek cheat: role ARN mein account ID already embedded hota hai (`arn:aws:iam::123456789012:role/...`) — wahin se nikaal sakte ho.

### IAM role aur OIDC — yeh kaise kaam karta hai

Background samajh lo: traditional tarika hota tha ki GitHub Actions ko long-lived AWS **access keys** (access key ID + secret) do. Yeh **insecure** hai — keys leak ho sakti hain, rotate karni padti hain. Modern best practice **OIDC (OpenID Connect)** hai:

- AWS mein ek **IAM role** banta hai jisme ek **trust policy** hoti hai jo GitHub ke OIDC provider par bharosa karti hai
- Jab workflow chalta hai, GitHub ek **short-lived token** deta hai, AWS use verify karta hai aur role ko **assume** karne deta hai
- Result: **koi long-lived secret AWS mein store nahi** hota. Sirf role ARN public-ish hai (secret bhi rakh sakte ho), aur temporary credentials minutes mein expire ho jaate hain

Isiliye humne secret mein `AWS_ROLE_ARN` rakha, na ki access keys.

### Step 3: Workflows folder + `deploy.yaml`

GitHub ke paas ab AWS mein log in karne ki **power** hai (credentials set ho gaye). Ab actual workflows banane hain.

1. Repo root mein nayi **top-level folder**: `.github`
2. Uske andar **subfolder**: `workflows`
3. Andar nayi file: `deploy.yaml` (Right-click → New File → `deploy.yaml`)

> Note: Cursor kabhi-kabhi `.github/workflows` ko ek hi line mein dikhata hai jab andar aur kuch na ho — yeh "compact folders" feature hai, settings se off kar sakte ho.

`deploy.yaml` mein guide se deployment script paste karo. Yeh ek typical GitHub Actions deployment workflow hai:

```yaml
name: Deploy Digital Twin

on:
  push:
    branches:
      - main
  workflow_dispatch:
    inputs:
      environment:
        description: 'Environment to deploy to'
        required: true
        default: 'dev'
        type: choice
        options:
          - dev
          - test
          - prod

permissions:
  id-token: write   # OIDC token ke liye zaroori
  contents: read

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Check out the code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install uv
        run: curl -LsSf https://astral.sh/uv/install.sh | sh

      - name: Set up Terraform
        uses: hashicorp/setup-terraform@v3

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_ARN }}
          aws-region: ${{ secrets.AWS_DEFAULT_REGION }}

      - name: Run deployment script
        env:
          AWS_ACCOUNT_ID: ${{ secrets.AWS_ACCOUNT_ID }}
          AWS_DEFAULT_REGION: ${{ secrets.AWS_DEFAULT_REGION }}
        run: |
          chmod +x scripts/deploy.sh
          ./scripts/deploy.sh
```

### Workflow ka anatomy — line by line

- **`name`** → workflow ka naam ("Deploy Digital Twin") jo GitHub Actions UI mein dikhega
- **`on`** → **trigger** — yaani kya cheez isse chalayegi. Yahan `push` (specific branch par) aur `workflow_dispatch` (manual button) dono hain
- **`permissions`** → workflow ke permissions, including OIDC token (`id-token: write`)
- **`jobs`** → key ingredient. Yahan ek hi job hai: `deploy`. Ek job ke andar kai **steps** hote hain
- **Steps** sequence:
  1. **Check out the code** — repo ka code VM par laao
  2. **Set up Python** — Python install karo
  3. **Install uv** — Python package manager (UV) install karo
  4. **Set up Terraform** — Terraform CLI install karo
  5. **Set up Node.js** — Next.js frontend build ke liye Node
  6. **Configure AWS credentials** — OIDC se role assume karo
  7. **Run the deployment script** — yeh main step hai: environment variables set karta hai (account ID + region, secrets se), deploy script ko executable banata hai (`chmod +x`), aur run karta hai

🔑 **Important detail** Ed batata hai: deploy script ka **Mac/Linux version** hi GitHub par chalta hai, **PC version nahi**. Yahi reason hai ki pichhle lectures mein bola gaya tha ki Mac version ko mat delete karo — kyunki GitHub runner Linux (`ubuntu-latest`) par chalta hai. PC version sirf tum locally use karte ho.

**YAML ki khoobi**: human-readable hai, indentation se structure banta hai — har step kya kar raha hai saaf dikhta hai. Time spend karke padho.

⚠️ **Save karna mat bhoolo!** White blob = unsaved file. Ed yahin pakadta hai ki usne save nahi kiya.

### Step 4: `destroy.yaml`

Ek doosra workflow bhi banana hai — `destroy.yaml` — jo ek environment ko **destroy** karta hai. Same workflows folder mein New File → `destroy.yaml` → guide se content paste → save.

```yaml
name: Destroy Environment

on:
  workflow_dispatch:
    inputs:
      environment:
        description: 'Environment to destroy'
        required: true
        type: choice
        options:
          - dev
          - test
          - prod
      confirm:
        description: 'Type the environment name to confirm'
        required: true

permissions:
  id-token: write
  contents: read

jobs:
  destroy:
    runs-on: ubuntu-latest
    steps:
      - name: Check out the code
        uses: actions/checkout@v4
      # ... (deploy jaise hi setup steps) ...
      - name: Run destroy script
        env:
          AWS_ACCOUNT_ID: ${{ secrets.AWS_ACCOUNT_ID }}
        run: |
          chmod +x scripts/destroy.sh
          ./scripts/destroy.sh ${{ github.event.inputs.environment }}
```

Khaas baat: `destroy.yaml` mein **koi automated trigger nahi** hai (no `push`). Yeh sirf **manual** (`workflow_dispatch`) chalta hai — galti se production destroy na ho jaaye, isliye ek confirmation input bhi hota hai jismein environment ka naam type karna padta hai.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Terraform backend** | Jahan Terraform apni state file store karta hai — yahan S3 (remote, shared) |
| **Terraform state** | Record ki kaunse resources exist karte hain — duplicate/update/delete decisions isi se |
| **DynamoDB lock table** | State locking — ek time par sirf ek `terraform apply` chale, race condition se bachao |
| **`backend.tf`** | Permanent Terraform config jo S3 backend point karti hai |
| **GitHub Secrets** | Encrypted values (role ARN, region, account ID) jo workflows use karte hain |
| **IAM role + OIDC** | Long-lived keys ke bina GitHub ko short-lived AWS credentials dene ka secure tarika |
| **`.github/workflows/`** | GitHub Actions folder — yahan `.yaml` workflow files rehti hain |
| **`on:` trigger** | Kya cheez workflow chalayegi — `push`, `workflow_dispatch` (manual), etc. |
| **jobs / steps** | Workflow ki building blocks — job ke andar sequential steps |
| **`deploy.yaml` / `destroy.yaml`** | Infra deploy karne / destroy karne wale workflows |

---

## 💼 Backend Dev Ke Liye Note

Python backend dev ke liye yeh lecture **DevOps fundamentals** ko AWS context mein laata hai. Agar tumne kabhi Jenkins, GitLab CI, ya CircleCI use kiya hai, toh `deploy.yaml` ka mental model wahi hai — bas YAML syntax GitHub-specific hai. Sabse important takeaway: **remote state + locking** ka concept. Yeh exactly waisa hi problem solve karta hai jaisa ek shared database mein concurrent writes — DynamoDB lock = distributed mutex. OIDC-based auth bhi note karo: production codebases mein ab access keys ko hardcode karna anti-pattern hai; short-lived assumed-role credentials standard hain (same principle jaisa app-level mein tum IAM roles via instance profiles ya IRSA use karte ho). Aur `chmod +x` + Mac/Linux script wali baat yaad rakho — CI runners almost hamesha Linux hote hain, isliye apne shell scripts ko cross-platform ya kam-se-kam Linux-compatible rakhna.

---

## ✅ Takeaway

- **Remote state** (S3 backend + DynamoDB locks) CI/CD ke liye must hai — local state ephemeral VM par kaam nahi karti
- GitHub mein **3 secrets**: `AWS_ROLE_ARN`, `AWS_DEFAULT_REGION`, `AWS_ACCOUNT_ID` — copy-paste karo, type mat karo (typos = obscure errors)
- **OIDC + IAM role** se GitHub ko long-lived keys ke bina secure AWS access milti hai
- Workflows `.github/workflows/` mein rehte hain — `deploy.yaml` (`push` par auto + manual) aur `destroy.yaml` (sirf manual, confirmation ke saath)
- Yeh sab **one-time per-repo setup** hai; Mac/Linux deploy script GitHub runner (Linux) par chalti hai, isliye usse delete mat karna

---

<details>
<summary>📜 Full Transcript (English)</summary>

And now the last piece of the puzzle is we just have to have one more Terraform file change here. Going to make a new Terraform configuration file called backend. Remember this could also just go in main.tf. There's no significance to having different file names. But the reason we're having this is we want to tell Terraform that for its backend it should be using S3. And so we go into our Terraform directory. We'll make a new file call it backend dot. There it is. Paste that in and save. And that's there. So and this this is not a temporary file. This is for reals. This Terraform needs this to tell it to use S3 as its backend. So we set up a couple of temporary Terraform files, one of them to allow us to build some useful S3 buckets and Dynamo S3 bucket and Dynamo databases for lock. And then we created one for to to set up the appropriate permissions, the role and policies. We ran both of them to one time to set up all that infrastructure. We deleted those Terraform files. We're done. We've set that up. And now we've just created this backend, uh, Terraform configuration right here, and we're almost ready for prime time. Uh, this is all, of course, just one time setup. You wouldn't ever have to do this again once. Uh, for any repo, you do it once for a repo so that it's then properly hooked up to GitHub actions. All right, back we go to the instructions. The next step is it's time to add some secrets to GitHub. GitHub has to know the secrets that we're going to use. Let's go and do that right now okay. So we're back in GitHub. We have gone to our twin repo. Here it is. We go to settings in this top nav scroll down here Secrets and variables. We go to actions. Here we go. These are the secrets of variables that apply to GitHub actions. And we want to repository secret. Secret that applies to the whole repo and press new repository secret. All right. What secrets do we want? The first one is AWS role Arn. AWS role Arn AWS role Arn. It is telling GitHub what role should it have in AWS? And there in my clipboard is the secret, the one that we we just took from running that Terraform thing once. This is the the value of the A around Arn that it should use for GitHub actions to deploy the twin add secret, everything has to be exactly right. Don't forget that. Uh, okay. Now what's the next secret? The next secret? Default AWS region. Well, that's a Perfectly. No mistakes. It's got to be your default region. It's got to be copy and paste it from somewhere rather than typing it like I did to make absolutely sure. Double check, because if you get something wrong, it's really hard to find out what's gone wrong. Later you may get some obscure error. All right. And then the oars account it. That's the final secret we need to add here. So back we go here and we go to new repository secret and oars account éd. And I can cheat. I can paste in the arn from before because my account ID is in there. Look at that. There we go. A nice little pro hack, that is. The oars accounted for me, and you should put in yours and press Add secret. And now we have three secrets oars, account éd. Oars role arn and default oars region. And they should all be good. And that has set us up for success. Now it's time to create the workflows. Okay, so as it says at this point, GitHub now has the ability, it has the power to log into our AWS account with the credentials that we set up for it. It's all ready to actually do something. So in over here in twin let's collapse some of these folders so it looks nice and clean. We need to create a new top level folder called dot GitHub GitHub. And within GitHub we're going to have a subfolder called workflows new folder workflows. There we go. And somewhat confusingly cursor shows it this way when there's nothing else but workflows. But you can actually turn that off if you wish. Uh, anyways, we're now going to create our first workflow and it's going to be called deploy YAML. So here we right click New File deploy dot YAML without the A just just like that. And now we're going back to the guide to get our deployment Script. So this is what a GitHub actions deployment script looks like. And I'm going to take all of this. You can see there's quite a lot to it. Copy that. And now I'm going to go back to deploy YAML and paste it in. Here it is. This is our first look at GitHub actions deployment script. We finally got to the point. We've we've set everything up. We've set up the backend S3 buckets and DynamoDB. We've set up the policy to log in. And this is now what will be run. So what does it look like? What does the script do? Well it begins with a name deploy digital twin. It says on and this has a description of the the the vent. What will cause this to be triggered. And it's on push. It says which branch and it says what to do about it. Um, it gives, uh, various stuff about the permissions. And then we've got the jobs. Remember, jobs was the sort of key ingredient. A job has a number of steps. We've got several jobs. One is, uh, we haven't got jobs. We've got one job. It's called deploy. And that one job has several steps. And the steps is check out the code set up Python install. You've set up Terraform, setup NodeJS and then look at this step here. Run the deployment script. It sets some environment variables the account ID and the default AWS region which it gets from its secrets. It makes the deploy script executable the same deploy script that is already in our scripts. The Mac version, because it's a mac and Linux version. And this is why PC people, I told you that you had to keep the Mac version, the deployment scripts, because even though you only run the PC version locally for you, when GitHub the the the oars roll Arne, so that it has the right roll. And we then get get the outputs from that. Um, and uh, so you can see everything that's going on in the script by looking through these steps, spend some time on it. YAML means that that it's, it's very human readable. So it's very clear and easy to see what's going on. And you can understand the script. One more thing I have to do though, I can see from that white blob there that I haven't saved it yet, so I need to make sure I save it before we go on our first GitHub workflow. But we have a second one to talk about too. We've got one called destroy. We're going to set up a destroy YAML which will destroy an environment. Let me just drag all of this. Select that. Copy it in this directory here. New file destroy dot. Yes there it is. Paste in the contents. Remember to save. And let's have a look at it. Uh, it uh doesn't have any, any automated reasons.

</details>
