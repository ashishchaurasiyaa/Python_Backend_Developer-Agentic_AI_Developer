# L58 — Setting Up GitHub Actions for Automated AI Model Deployment

> **Week 2 · Day 5** · ⏱️ ~10 min

---

## 🎯 TL;DR

GitHub par naya `twin` repo banao (README/gitignore/license sab OFF), local repo ko `git remote add origin` + `git push -u origin main` se push karo. Phir GitHub Actions ke liye **remote Terraform state** chahiye — toh ek **temporary Terraform file** likh ke **S3 bucket + DynamoDB lock table** banao (state ka "shared drive"), aur banane ke baad temp file delete kar do.

---

## 🗣️ Hinglish Explanation

### Step 1: GitHub par naya repo banao

Ed `github.com` par apne username (Donna = ed-donner) par hai. Repositories tab → **New** button. Naye repo ki settings:

1. **Repo name**: `twin` suggest karta hai. Description: *"an AI digital twin version of me"*.
2. **Visibility**: public ya private. (Code public/private — yeh tumhare actual digital twin ke public/private hone se alag baat hai.) Ed **public** suggest karta hai taaki tum apna kaam dikhaa sako (assignment mein twin ko aur rich banaana hai — show off karne layak). Ed khud abhi **private** rakhta hai.
3. ⚠️ **CRITICAL**: **README, `.gitignore`, aur License — sab OFF/uncheck**. Kyunki humne already locally repo banaayi hai aur usmein cheezein hain. Agar GitHub inhe create kar de, toh **merge conflicts/nonsense** ho jaayega. Galti se on kiya toh trouble.
4. **Create repository** dabao → ab ek empty `twin` repo hai.

GitHub khud command line instructions dikhaata hai (jismein kaafi kuch hum already kar chuke hain). Do commands jo ab chalane hain wo Ed clipboard mein copy kar leta hai.

### Step 2: Local repo ko GitHub par push karo

Pehle **remote set** karo — local repo ko cloud wale GitHub repo ki taraf point karaao:

```bash
git remote add origin https://github.com/ed-donner/twin.git
```

- `git remote add` → ek remote (cloud copy ka reference) jodta hai.
- `origin` → remote ka conventional naam.
- URL do tareeke se de sakte ho:
  - **HTTPS**: `https://github.com/<username>/twin.git`
  - **SSH**: `git@github.com:<username>/twin.git`

Phir **push** karo:

```bash
git push -u origin main
```

- `git push` → local commits ko remote par bhejo.
- `-u origin main` → upstream set karo (`origin/main`), taaki future mein sirf `git push` kaafi ho.

GitHub par refresh → **Code** tab → poora project dikh raha hai: `backend`, `frontend`, `scripts`, `terraform`, `week2`, `.env.example`, `.gitignore`. `backend` mein saara Python code (including Lambda deploy script) hai par **`package/` folder aur `.zip` file nahi** (gitignore ne unhe chhod diya). `scripts` mein deployment script, aur Terraform scripts source control mein checked-in. Sab badhiya.

### Step 3: Remote Terraform state — "head scratcher"

Ye **GitHub Actions setup ka sabse fiddly part** hai. Problem samjho:

- Jab hum **Terraform locally** chalate the, state files (`.tfstate`) hamari machine par the — jo describe karte the ki real cloud mein kya hai.
- Ab hum **Terraform ko GitHub (runner VM) par** chalane waale hain. GitHub runner har run par fresh VM hota hai — uske paas state ko **permanently store** karne ki jagah nahi hai.
- GitHub ko ek **"shared drive"** chahiye jahan wo har run ke beech state ka permanent record rakh sake.

**Solution: S3 bucket ko remote backend banao.** S3 ek shared drive ki tarah kaam karta hai — yeh Terraform remote state ke liye **very common practice** hai. Aur **state locking** ke liye ek **DynamoDB table** chahiye — taaki do simultaneous Terraform runs state corrupt na karein (lock ek run ko block karta hai jab tak doosra complete na ho).

> **DynamoDB** = AWS ka fully-managed serverless **NoSQL** key-value database. Terraform ise sirf ek lightweight lock-record store ki tarah use karta hai (S3 native locking aane se pehle yeh standard pattern tha).

### Step 4: Temporary Terraform se backend banao

Console mein S3 bucket banaane ki jagah ("we don't like the console anymore"), hum **Terraform se hi** woh S3 bucket + DynamoDB banayenge jo baad mein GitHub Actions use karega. Thoda recursive lagta hai — *hum Terraform locally chalaa rahe hain taaki kuch banaayein jo GitHub Actions ke Terraform ke liye state rakhe.*

Ye file **temporary** hai — banao, run karo, baad mein delete. Cursor mein `terraform/` mein new file `backend-setup.tf`:

```hcl
# backend-setup.tf — TEMPORARY: creates S3 + DynamoDB for Terraform remote state

resource "aws_s3_bucket" "terraform_state" {
  bucket = "twin-terraform-state"
}

# Versioning on (state history rakhne ke liye — accidental overwrite se recovery)
resource "aws_s3_bucket_versioning" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id
  versioning_configuration {
    status = "Enabled"
  }
}

# DynamoDB table for state locking
resource "aws_dynamodb_table" "terraform_locks" {
  name         = "twin-terraform-locks"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }
}

output "state_bucket_name" {
  value = aws_s3_bucket.terraform_state.bucket
}
output "dynamodb_table_name" {
  value = aws_dynamodb_table.terraform_locks.name
}
```

Ye "store and lock" set up karta hai — S3 = store, DynamoDB = lock.

### Step 5: Sirf yeh resources apply karo

Terminal kholo aur **`terraform` directory mein jao** (mat bhoolna). Phir ensure karo tum **default workspace** mein ho (dev/test/prod nahi):

```bash
terraform workspace select default
terraform init
```

Ab — agar `terraform apply` aise hi chalaaya toh wo **saari** `.tf` files ke resources bana dega. Hum sirf backend-setup wale specific resources chahiye. Toh **targeted apply** karo:

```bash
terraform apply \
  -target=aws_s3_bucket.terraform_state \
  -target=aws_s3_bucket_versioning.terraform_state \
  -target=aws_dynamodb_table.terraform_locks
```

`-target` Terraform ko sirf specified resources create karne ko kehta hai. Confirm karne ke liye **`yes`** type karna padega (galat resources banne se bachne ke liye Terraform poochta hai). Apply hone ke baad S3 bucket + DynamoDB lock table ban jaate hain — yeh **shared resources** hain jo GitHub Actions use karega.

Outputs dekho:

```bash
terraform output
# state_bucket_name   = "twin-terraform-state"
# dynamodb_table_name = "twin-terraform-locks"
```

### Step 6: Temporary file delete karo

Ab woh temporary `backend-setup.tf` hata do (mental model: yeh sirf one-time backend banane ke liye tha):

```bash
rm terraform/backend-setup.tf   # ya Cursor mein "Move to Trash"
```

Gone. Drama over. Ab agla kaam: scripts ko update karna taaki wo is naye **remote backend** ko use karein (next lecture).

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **New GitHub repo** | README/gitignore/license OFF (warna local repo se conflict) |
| **`git remote add origin`** | Local repo ko cloud GitHub repo se link karo |
| **HTTPS vs SSH URL** | Repo refer karne ke do tareeke |
| **`git push -u origin main`** | Commits push + upstream set |
| **Remote Terraform state** | State ko shared storage mein rakhna (local ke bajaaye) |
| **S3 as backend** | Terraform state store karne ka common pattern |
| **State locking** | Simultaneous applies ko rokna — state corruption se bachaav |
| **DynamoDB lock table** | AWS NoSQL DB jo lock records rakhta hai |
| **Temporary `.tf` file** | One-time setup ke liye — run karke delete |
| **`terraform apply -target`** | Sirf specific resources apply karo (sab nahi) |
| **default workspace** | Backend banaate waqt dev/test/prod mein NAHI hona |

---

## 💼 Backend Dev Ke Liye Note

Yeh lecture remote-state concept introduce karti hai jo CI/CD-era Terraform ka non-negotiable hai. Local `.tfstate` tab tak theek hai jab tak sirf tum apne laptop se apply karte ho — par jaise hi pipeline (GitHub runner) ya teammate apply karne lagte hain, state ek **shared single-source-of-truth** honi chahiye, warna do applies same resource ko alag-alag samajh ke infra corrupt kar denge. S3 backend + DynamoDB lock pattern exactly yeh solve karta hai: S3 mein state JSON (versioning on = audit/recovery), DynamoDB `LockID` row = mutex jo concurrent applies ko serialize karta hai. Ek Python dev ke liye analogy: yeh wahi distributed-lock problem hai jo tum Redis `SETNX` ya DB advisory locks se solve karte ho — bas yahan infra-mutation ke liye. Note: naye Terraform versions (1.10+) mein S3-native locking (`use_lockfile`) aa gaya hai, toh DynamoDB optional ho raha hai — par bahut saare existing repos abhi bhi DynamoDB pattern use karte hain, isliye dono jaanna zaroori. Aur `-target` flag ko ek surgical escape-hatch samjho — production mein routinely avoid karo (full plan/apply behtar hai), par bootstrap (state backend khud banaane) jaise chicken-and-egg cases mein perfect.

---

## ✅ Takeaway

- GitHub par repo banaate waqt **README/gitignore/license OFF** rakho — warna local repo se merge conflict
- Push: `git remote add origin <url>` → `git push -u origin main`; verify GitHub par code, no `package/`/`.zip`
- GitHub Actions ke liye **remote state** chahiye — S3 bucket (store) + DynamoDB table (lock) ko **shared drive** ki tarah use karo
- Backend khud Terraform se banao (console nahi), ek **temporary `.tf`** likh ke `terraform apply -target=...` se sirf woh resources create karo
- Backend ban jaane par temp file **delete** kar do; `terraform output` se bucket/table names note karo

---

<details>
<summary>📜 Full Transcript (English)</summary>

And so here I am in GitHub. I'm on github.com. Donna, you should be not on this, but in your github.com your username. Presumably you have an account with GitHub. If not, create one. And then be there. And here I am. And one thing you'll notice right away is that I do most of my work on Saturdays, uh, which is probably not super healthy. Uh, that's because I have a day job. Uh, so, uh, that's when, uh, when you'll see me most active. Okay. And, uh, I have repositories. Let's go to repositories over here. And, uh, you can see the production one that you hopefully know well. And now I'm going to press the new button. You need to press the new button. So now over here you start with your repo name and I suggest you call it twin. Uh, twin is available. And you give it a description like a digital twin, uh, version of me. Let's call it an AI digital twin version of me. So choose visibility. You can make it public or private. This, of course, is not related to whether your actual twin is public or private. This is whether the code is public or private. I suggest you make it public because you want people to see the work you've done you. And of course, in the assignment, I'm going to be asking you to make this much more rich functionality for yourself. And so you're going to want to show this off. And when you have your digital twin running, remember to tag me and tell me about it so I can come in and talk to it. And I want to be wowed by how much functionality you have. Uh, but we will come to that later. Uh, I make mine private for now. Uh, now, here's the thing. You need to make sure that you have the readme and. Gitignore, and license all off because we've put that we've been building things in our repo, so, so we don't want, uh, this to create stuff or we're going to have like, merging nonsense. So, so if you do this by mistake, it's going to be trouble. So don't do it. Make sure Adeyemi is off. No. Gitignore and no license. And then press create repository. Uh. All right. Uh, and here we are. We are in, uh, the, the our new repository called twin. It is empty. And, uh, it tells you how to create a new repo on the command line, and you'll see that a lot of this is what we've already done. So we're looking in great shape. Uh, and these two commands here is what we're just about to run. Uh, so I might just just copy that right now into my clipboard so that it's, uh, convenient. And let's see now what else I want to show you. Um, I think that's probably it. I think we should go to the command line now and get get this on the road. Get this show on the road, is what I mean. Of course. So now here we are. Uh, we're going to push to GitHub. The first step is to add this repo to is to set the remote for this local repo to be pointing to GitHub in the cloud, to that repo that we just set up in GitHub. So we go git remote add origin. So I'm just typing this this line right here. And actually I'd already pasted this I'd already pasted this command in from the other screen. So just paste it in there. You can see there's actually a different ways that you can refer to a GitHub repo. This way the https, then github.com, then your username which would be Donna for me and then digital twin. Or we can do it this way I press enter. That's done. And now this is the git push command git push u origin main. All right here we go. Bam. Done. All happened. Looks good. Now let's go and check that out in GitHub. Here I am back at GitHub again. It looks much the same as it looked a second ago. Let's just click here on code and look at that. We've got our whole thing in here. We've got the back end, front end scripts. Terraform week two. We didn't need I guess, but but it's there. The env example and. Gitignore. And so our repo is there. And we can go in for example to backend. We can check that in here. We don't have that folder the the the package. And we don't have the zip file. We just have all of our Python code including the, the this this deploy which is about deploying the Lambda package. Um, and similarly in scripts we have our actual deployment script here, which is the one that actually builds the Terraform environment and deploys an environment. And here are our Terraform scripts checked in to source code control. All is looking great. And that brings us to part three. And part three is a little bit of a head scratcher. So so bear with me here. This is the one fiddly part of setting up our GitHub actions. So remember when we're running Terraform locally on our computers. We've got these Terraform state variables that describe the real infrastructure out there. The state is um, in this whole like like TF state folder and it controls, um, Terraform's view of what's actually out there. So we're about to do all of our Terraform script running on GitHub. And that means that GitHub needs to have somewhere where it can maintain all of the, the state to, um, so it needs like a sort of like a, like a shared drive where it can have all of this information. So every time we run it, it's got a permanent record of what the state is. And well, GitHub doesn't, doesn't necessarily come with that easily. And so we need to like make a shared drive. And it happens that we we know how to make shared drives because that's what an S3 bucket is. So we can use an S3 bucket as our way to describe Terraform state. That's very convenient, very easy and very common practice. Um, and so, uh, we could go into the console and futz around with the console to create a new S3 bucket. Uh, but but that we don't like the console anymore, so we might as well actually use Terraform to create the, the, the S3 bucket that we will then be using in GitHub actions, uh, in order to maintain state. So that's a little bit of a muddle there. We're going to run Terraform locally in order to create, uh, something which will be used by our GitHub actions. I hope you followed that. Uh, I think you probably did. Otherwise it's going to become clear when I actually do it. So we're going to temporarily set up a TF file, uh, in order to create this, this S3 bucket and also a DynamoDB, I should say we also need a database table. We're going to create that as well using DynamoDB, which is another AWS component that I'm not going to talk about in any detail, aside from the fact that we're creating this database component for our Terraform state, and we're going to run it. So this is the Terraform resource description. Let me just go through it. This sets up everything that we need in order to have the DynamoDB and the S3 bucket. And we're going to to create something called uh, back end dash setup, uh, which is the S3 bucket and dynamo table for our Terraform state. So, uh, here we go into Terraform. We do new file, we're going to call it backend setup. And you need to have the mental model. This is just temporary. We're going to create this run it and then delete it later when we're done with it. So that's been created. Take a look through and you can see the different things that we're using here. Uh a store and a lock uh, which is something that is going to be basically, uh, reflecting the store and the lock that we have here. Uh, and, um, back we go. Okay. And that's, that's the, uh, that set up the configuration and the next step will be to run it. Okay. So we bring up a terminal in cursor. The first thing we need to do is to go into the terraform directory. Don't forget to do that. Then it's important that we make sure that we're not in a workspace like dev test or prod. So we go to select the default workspace. We run terraform init. The terraform commands are terraform init followed by terraform apply. Now when we do terraform apply normally. If you do terraform apply, it just goes out there and creates everything described in Main.tf or in any of your TF files. We don't want to do that. In this case, we only want to create the specific resources that we listed out in that extra backend setup file. So we're just going to run this command which is only going to run Terraform. Apply for some specific resources. It asks us to type the word yes to absolutely confirm we know what we're doing. Uh, because it would hate to create the wrong resources. It goes out there and it creates it all and it's been done. We have just created a bunch of we've created an S3 bucket and some dynamo tables for locks, which are all set up. So these are like shared resources that GitHub can use for running its actions onwards. And so we can just type Terraform output which displays the outputs, uh, to tell us what happened. And it tells us that we created a DynamoDB table, uh, for our locks. And we created a state bucket name twin terraform state. And these are things that will be used by our, uh, GitHub actions in just a moment. But before we do that, we should remove this temporary Terraform file right here that we only had it there in order to create this, this back end. So we just delete, move to trash. There we go. It's gone. It was only temporary anyway. Okay, it's now time for us to update our scripts to use this new back end.

</details>
