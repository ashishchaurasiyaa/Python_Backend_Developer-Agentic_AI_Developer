# L75 — Setting Up AWS Permissions and SageMaker for Production AI Agents

> **Week 3 · Day 3** · ⏱️ ~10 min

---

## 🎯 TL;DR

ALEX ke liye AWS foundations: hum root user se IAM mein ek **custom `Alex-S3-vectors-access` policy** banate hain (S3 Vectors abhi naya feature hai isliye pre-baked policy nahi), phir ek **`Alex-Access` group** (SageMaker + Bedrock + CloudWatch Events FullAccess + custom policy) banake `ai-engineer` user se attach karte hain. Phir CLI se permissions verify, `.env` file setup (account ID + region), aur SageMaker ke intro ka stage set.

---

## 🗣️ Hinglish Explanation

### Guide 1: Permissions (hamesha yahin se shuru)

Alex project mein `guides/` folder kholo, pehla guide = **permissions**. Right-click → **Open Preview** (markdown render). Ed ka pattern: *"we often start with looking at permissions."* Guide ALEX ka intro deta hai (Agentic Learning Equities eXplainer — AI-powered personal financial planner, portfolios + retirement planning) aur ek **architecture diagram** dikhata hai (abhi skip — permissions ke baad explain hoga).

### Mermaid diagrams ka extension (zaroori setup)

Guide mein architecture diagrams **Mermaid diagrams** hain. Agar Cursor mein properly render nahi ho rahe:

```
1. Extensions kholo: Cmd+Shift+X (Mac) / Ctrl+Shift+X (PC)
2. Search: "mermaid"
3. Install: "Markdown Preview Mermaid Support" extension
4. File explorer wapas: Cmd+Shift+E (Mac) / Ctrl+Shift+E (PC)
```

> **Mermaid** = text-based diagramming syntax (code likho, diagram banta hai) — README/markdown mein architecture/flowcharts embed karne ka popular tarika.

### Background: IAM, Policies, Groups, S3 Vectors

- **IAM (Identity and Access Management)** — AWS ka permission system: kaun (users/groups/roles) kya (services/actions) kar sakta hai.
- **Policy** — JSON document jo specific permissions define karta hai (kis service par kaunse actions allow). AWS-managed (pre-baked) ya **customer-managed** (apna custom JSON).
- **Group** — users ka collection jisse policies attach karte ho; group ke saare users ko wo permissions mil jaate hain. (Har user ko alag-alag policy attach karne se behtar.)
- **S3 Vectors** — AWS ka **naya feature**: vectors (embeddings) ko S3 par store karne ka cost-effective tarika, vector search ke liye. **Itna naya hai ki AWS ne abhi tak iska pre-baked managed policy nahi banaya** — isliye humein custom policy banani padegi (Ed ise "a bit of a pro move" aur "slightly hokey way" kehta hai).
- **SageMaker** — AWS ka managed ML platform (models train/deploy/host). Iss week iska use hoga.
- **Bedrock** — AWS ka managed foundation-model service (LLM access via API).
- **CloudWatch Events** — AWS ka monitoring/scheduling (events, alarms, scheduled triggers).

### Step 1: Custom S3 Vectors policy banao (root user)

```
1. AWS Console → sign in as ROOT user
2. IAM → Policies (left menu) → Create policy
3. JSON tab → paste guide ka content (S3 Vectors actions allow)
4. Name: "Alex-S3-vectors-access" → Create policy
```

Iska JSON kuch aisa dikhega (S3 Vectors ko allow karta hua):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AlexS3VectorsAccess",
      "Effect": "Allow",
      "Action": [
        "s3vectors:*"
      ],
      "Resource": "*"
    }
  ]
}
```

> Yeh policy ALEX ko AWS ke naye **S3 Vectors** use karne ki ability deti hai.

### Step 2: `Alex-Access` group banao

```
1. IAM → User groups → Create group
2. Group name: "Alex-Access"
3. Attach in policies:
   - AmazonSageMakerFullAccess
   - AmazonBedrockFullAccess
   - CloudWatchEventsFullAccess
   - Alex-S3-vectors-access   (jo abhi banaya — custom)
```

> **Pro tip (Ed ka)**: instructions mein sirf yeh **4 policies** hain, par Ed ke actual group mein aur bhi policies hain jo aage chahiye hongi. Ek **screen grab** le lo Ed ke group ka aur saari policies abhi add kar do — baad mein time bachega. (Permissions tab vs Users tab — Permissions tab attached policies dikhata hai.)

### Step 3: Group ko `ai-engineer` user se attach karo

```
4. Users tab → add user "ai-engineer" to the group
```

`ai-engineer` wo IAM user hai jo course bhar use ho raha hai (root nahi). Group attach hone ke baad `User groups` mein `Alex-Access` properly setup dikhna chahiye.

### Step 4: Root se sign out, ai-engineer se sign in

```
- AWS Console mein root user se SIGN OUT (root permission ke saath rukna mat)
- Wapas sign in as "ai-engineer"
```

> Security best practice: root ka use minimal rakho. Permissions setup ke baad turant wapas low-privilege IAM user (`ai-engineer`) par switch.

### Step 5: CLI se permissions verify karo

Cursor mein naya terminal kholo:

```bash
# 1. Kaun logged in hai?
aws sts get-caller-identity
# Output: UserId, Account (tumhara account number), Arn (.../ai-engineer)
# Agar expected nahi → aws configure chala ke sign in karo

# 2. SageMaker access check (abhi use nahi kar rahe, sirf permission test)
aws sagemaker list-endpoints
# Output: empty endpoints list — matlab access hai, koi endpoint abhi nahi
```

> `aws sts get-caller-identity` confirm karta hai ki CLI kis identity ke through call kar rahi hai (UserId + account + ARN). `list-endpoints` ka empty hona normal hai — hum aage **endpoints build** karenge (SageMaker mein endpoint = ek deployed model jise API se call karte ho).

### Step 6: `.env` file setup (project secrets)

ALEX root directory mein:

```bash
# env example ko copy karke .env banao (CLI ya right-click copy/paste dono chalega)
cp .env.example .env
```

> Naam **exactly `.env`** hona chahiye — kuch zyada/kam nahi, warna kaam nahi karega (classic Ed joke).

Phir `.env` edit karo aur do values daalo:

```bash
# .env
AWS_ACCOUNT_ID=<your-12-digit-account-id>   # apna daalo, Ed ka nahi
AWS_DEFAULT_REGION=us-east-1                 # jo region tumhare liye best ho (Ed: us-east-1)
# (aage agle 1.5 hafte mein aur values add hongi)
```

Apna account ID `aws sts get-caller-identity` se mil jaata hai (clipboard pe copy karo). Default region wo set karta hai jahan infra deploy hoga.

### Important: do alag jagah environment variables (confusing par by-design)

Ed ek **subtle but important** baat batata hai — ALEX ki complex infra mein **do alag jagah** env vars jaate hain:

| File | Kiske liye | Git mein? |
|---|---|---|
| **`.env`** | Local secrets jo **Python scripts/services** use karenge | git-ignored |
| **`terraform.tfvars`** | **Terraform infrastructure** ke variables | git-ignored |

> Dono git-ignored hain (galti se commit na ho jaaye). Matlab kabhi-kabhi **same value do jagah** daalni padegi. Real projects mein log scripts likhte hain jo variables auto-copy kar dete hain, par Ed deliberately manual rakh raha hai — *"that is itself error prone... I want to take things as simple as possible"* — taaki clear rahe kya kahan jaata hai, aur fail ho toh pata ho kahan dekhna hai.

### Aage kya: SageMaker ka big lab

Yeh permissions lab (Guide 1) ke **preliminaries** khatam. Aaj ka doosra lab = **SageMaker** ka bada lab (Guide 2). Agle lecture mein Ed explain karega **SageMaker actually hai kya**.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **IAM** | AWS ka permission system — kaun kya kar sakta hai |
| **Policy** | JSON permission document; AWS-managed ya customer-managed (custom) |
| **Group** | Users ka collection jisse policies ek saath attach hoti hain |
| **S3 Vectors** | Naya AWS feature — vectors S3 par store; itna naya ki pre-baked policy nahi (custom banani padi) |
| **`Alex-S3-vectors-access`** | Custom policy (`s3vectors:*`) jo Alex ko S3 Vectors use karne deti hai |
| **`Alex-Access` group** | SageMaker + Bedrock + CloudWatchEvents FullAccess + custom S3 Vectors policy |
| **SageMaker** | AWS managed ML platform (train/deploy/host models); endpoint = deployed model |
| **Bedrock** | AWS managed foundation-model (LLM) service |
| **`aws sts get-caller-identity`** | CLI kaun-si identity (UserId/Account/ARN) se call kar rahi hai — verify |
| **`aws sagemaker list-endpoints`** | Permission test; empty list = access hai, koi endpoint nahi |
| **`.env` vs `terraform.tfvars`** | Local Python secrets vs Terraform infra vars — dono git-ignored, kabhi same value duplicate |
| **Mermaid** | Text-based diagram syntax; Cursor mein extension chahiye render ke liye |

---

## 💼 Backend Dev Ke Liye Note

Yeh lecture production AWS access management ka textbook pattern hai jo har backend dev ko aana chahiye. **Group-based permission** (user ko direct policy attach karne ke bajaye group → user) = scalability + auditability: naya engineer aaye toh bas group mein daal do, saari permissions mil jaati hain; offboard karna ho toh group se hata do. **Least privilege** ka principle yahan dikhta hai — root sirf setup ke liye, baaki sab kaam low-privilege `ai-engineer` user se. Custom policy banana (jab AWS managed policy na ho, jaise naye `s3vectors:` actions) ek real skill hai — IAM action namespaces (`s3vectors:*`) samajhna padta hai. Sabse practical takeaway: **`.env` vs `terraform.tfvars` split**. Yeh do-config problem real hai — application runtime secrets (jo tumhara Python code `os.environ` se padhta hai) aur IaC variables (jo Terraform `var.x` se padhta hai) alag concerns hain, aur dono ko **git-ignore** karna non-negotiable hai (secrets repo mein leak = security incident). Ed ka "manual over auto-copy" choice debatable hai (DRY violate karta hai), par uska point valid hai — clever automation khud bugs introduce karti hai. Aur `aws sts get-caller-identity` — yeh tumhara pehla debugging command hona chahiye jab bhi "access denied" aaye: pehle confirm karo ki CLI kis identity se chal rahi hai.

---

## ✅ Takeaway

- **Permissions pehle**: root user se IAM → custom **`Alex-S3-vectors-access`** policy banao (S3 Vectors naya hai, pre-baked policy nahi) → **`Alex-Access` group** (SageMaker + Bedrock + CloudWatchEvents FullAccess + custom) → `ai-engineer` user se attach
- **Pro tip**: Ed ke group ka screen grab lo aur saari future policies abhi add karo — time bachega
- **Root se turant sign out**, low-privilege `ai-engineer` user se kaam karo; CLI par `aws sts get-caller-identity` + `aws sagemaker list-endpoints` se verify
- **`.env` setup**: `cp .env.example .env`, account ID + default region daalo (exactly `.env` naam, git-ignored)
- **Do jagah env vars**: `.env` (Python runtime secrets) vs `terraform.tfvars` (Terraform infra) — dono git-ignored, kabhi same value duplicate karni padti hai

---

<details>
<summary>📜 Full Transcript (English)</summary>

Okay, so let's get started. We're here in the Alex project. I'm going to go into the guides folder. And the first guide is called permissions. Uh and I'm going to right click and do open preview. And you know well that we often start with looking at permissions. So uh, this begins with a quick introduction about Project Alex, the Genetic Learning Equities explainer, an AI powered personal financial planner. And it tells you a little bit more about what I have in store for you, which I will talk more about in a minute, but, but, uh, or during the course of the next few days. But it's about understanding your portfolios, planning for retirement and so on. There's then an architecture diagram, and I want you to look the other way for this, because I am going to talk through the architecture. And we'll do that once we've got our permissions set up. You can take a quick peek while you go through it if you wish. Uh, but the first thing we're going to do is set up all the permissions that we're going to need in order to carry out this master plan. So, um, this also explains again about the infrastructure management, the fact that we're doing multiple Terraform deployments with separate directories for each piece. And it explains some of the pros and cons of doing it that way. And it says make sure you've got an AWS account. Of course you do with with root access because this is the one of the times when we use root access is to set up permissions, make sure your CLI is installed and you are you're ready to go, but I'm sure you are since we've got to this point. Oh yes. I also mentioned here that that uh, I've got this architecture diagram and there's a few other places where we have them. These are a type of diagram called a mermaid diagram. And this might not have appeared nicely for you, in which case you need to install an extension in cursor. Uh, and you need to install the extension that's written here, the markdown mermaid extension. You probably know this, but to install an extension, it's command shift X on a mac or control shift X on a PC, and it brings up the extension screen over here and you pick the mermaid one. Let me just do this. Now, if I do this now, uh, and I type mermaid, we'll see the one I have installed. It's, uh, this one right here, this markdown preview. Uh, mermaid one here. I have that installed, and that's the one that means that I can see mermaid diagrams. So remember to do that and then command shift E or control shift E brings back the File explorer. Okay. So with that it's time for us to go to the, uh, the the console sign in, go in as a root user and I will see you there. So here I am in the AWS console. And you can see I'm signed in there as my root user. So what are the instructions in the AWS console. Navigate to IAM and click policies. Create a new policy and paste in this content as a new policy. And then save it as Alex S3 vectors access. So this is a bit of a pro move. And this is because we're going to be using this way of storing data as vectors, which is called S3 vectors and which is relatively new. It's a fairly new feature in Amazon and AWS, which means that there aren't these kind of pre-baked policies for it, which is why we have to do this in this slightly hokey way. So let me show you this. We're going in here. We go to IAM. There it is. We come in here, we go to policies in the left. And you can see I've already set this one up, I believe. So if I scroll down, you can see I've already got it. Alex S3 vectors access. But you'll be pressing create policy to create this. And when you're in there, just as it says in the instructions, you'll come in and and and attach your JSON and it's going to look just like this. I can just press the JSON button there to see it. Uh, and it's allowing S3 vectors. So follow those instructions and save it as it's described here, to create your policy called Alex S3 vectors, which is access, which is going to give Alex the ability to be using the new S3 vectors from AWS. All right. And then the next step is we're going to create a new group. We did this before. So hopefully it's a little bit familiar to you. We're going to go to user groups create a group call it Alex Access and add in these guys SageMaker bedrock CloudWatch events Full Access. And then we're also going to have Alex S3 vectors access, which is the thing we just set up. So those four. So have a look at them. So if I go back here again we're going to user groups. Now you're going to press create group. But you can see I've already got Alex access in here. And the way it shows for me because I've already set it up. There's two tabs Permissions and users permissions is showing that I've got those those things I mentioned. There are some other policies in here too, which you may need to add later as we go. So if you want to give yourself a shortcut, then take a quick screen grab of this and add all of these, not just the four that are on the in the instructions, but all the ones only for the future. That's a pro tip that will save you some time later, but you'll see in here are the ones that were just mentioned SageMaker, which is we're going to be using today CloudWatch full events. Uh, and uh, yeah. The, the uh, the others uh, should be here and also the one that we just created. There it is. Sorry, Alex S3 vectors access the custom policy that we just created. So set up this and then make sure that you attach it to the user AI engineer just as it says. And then when you come back into it to look at it by going to user groups, you should see it set up just like mine is here. And then that is the setting up the the new group for Alex. Okay, so hopefully you followed the instructions here to create your Alex Access group and to make sure that it's associated with your IAM user AI engineer. And with that, you should now sign out please, as the root user in the AWS console. You shouldn't stick stick around with that kind of permission and sign back in as AI engineer. Okay? Now let's just check that everything is what we expect at the command line. So bring up a new terminal in cursor, and first run this command to check who is logged in. If this doesn't say what we expect then you should run AWS configure to sign in. But in my case it does. That's my user ID apparently my account number that I do recognize because we've done use it a million times, and the Arn, the AWS resource number of my user AI engineer. There it is. Next up we're going to run this command AWS SageMaker list endpoints. And you'd be forgiven for saying I don't want SageMaker is yet. Why am I calling it? But don't fear, we're just doing this to check that we can access it. Permissions are good, I can see it and I have no end points. We will be building endpoints. Well, an end point uh, and I will explain what SageMaker is in just a second. All right. But first some project setup stuff okay. So we're going to set up an environment file a env file. So from the uh Alex root directory I'd like you to copy an existing file called env example and make it your env file. Now you can either do this at the command line or you can just right click and copy and paste in the file explorer on the left there. But I'll do copy dot EMV dot example to be just dot env. And I'm sure you know the joke by now, but it has to be called exactly env nothing more, nothing less. Otherwise it won't work. Uh, then get your AWS account ID if you don't already know it off by heart. By this point in the course there is my ID. I copy that to the clipboard and edit the EMV file, which is just a template EMV file. These are all of the things we'll be filling in over the course of the next week and a half. We start by pasting in the account ID. There it is. That's mine. You should put in yours, not mine, but yours. And, uh, then also the default region. This is a good moment. Mine is US East one. You should pick the region that makes most sense for you. That will be the default, uh, for for setting up the infrastructure that we use. And with that, we will be we'll be adding more to this as we go through. It's worth mentioning right now something a bit confusing that there are two different places where environment variables are going to go, uh, which which is because we have a reasonably complex infrastructure here. The EMV file is what we will use for our local secrets that we'll be using in some of our Python scripts and services. There's also Terraform variables, terraform.tf vars which are used for Terraform infrastructure, and they're all get ignored so that we don't accidentally check them in. But we will be updating some things twice now. It's common in real projects to to to write yourself some scripts that will just automatically copy variables like this across, so you don't have to put them in two places. But I just figured doing something like that is itself error prone. And I want to just take things simple, as simple as possible. So even though occasionally we're going to have to put the same information into two different files, I would rather do it that way to be clean and simple. And so it's clear what goes where. And if things don't work, you know where to go. Uh, so that then does conclude the, uh, the first, uh, of our of our labs for this project. But it's only the preliminaries. We do have another lab for today, which is the big lab about SageMaker. And it's time for me to explain what SageMaker actually is.

</details>
