# L50 — Infrastructure as Code for AI: Deploying LLM Apps with Terraform

> **Week 2 · Day 4** · ⏱️ ~13 min

---

## 🎯 TL;DR

Pehle saare manually banaye AWS resources (Lambda, API Gateway, S3 buckets, CloudFront) ko console se **delete** karte hain, phir **Terraform** (HashiCorp ka Infrastructure-as-Code tool) introduce hota hai — uski philosophy (version-controlled, automated, repeatable) aur 6 core terms: **provider, variable, resource, state, output, workspace**, plus commands `terraform init / apply / destroy`.

---

## 🗣️ Hinglish Explanation

### Pehla kaam: manual resources delete karo (cleanup)

Welcome to Week 2, Day 4. Aaj **Terraform** hai. Par usse pehle ek **final time** AWS console mein jaana hai — saare manually banaye resources **delete** karne, taaki Terraform se fresh banaya jaa sake. Ed warning deta hai: "manual setup ki yeh trauma main jaan-bujhke karwa raha hoon taaki tum Terraform ki value samjho".

> **Important:** AWS mein log in karo as **IAM user** (AI engineer), root nahi. (Naya AWS feature: account color — useful identification ke liye.)

Console **Home → Recently visited** se shortcuts mil jaate hain. Sahi **order** mein delete karo (dependencies ka khayal rakho):

**1. Lambda function delete**
- Lambda → **twin API** → **Actions** → **Delete function** → confirm **Delete**
- Warning: "permanently removes its code". (Don't worry — Terraform se wapas aayega, aur easier!)

**2. API Gateway delete**
- API Gateway → **twin API** gateway select → **Delete**
- Yeh `confirmed` type karwata hai (extra safety) → **Delete**

**3. S3 buckets delete (frontend + memory)**
S3 bucket delete karne se pehle usse **empty** karna padta hai (non-empty bucket delete nahi hota):
- Bucket select → **Empty** → confirm karne ke liye `permanently delete` type karna hota hai
- **Pro trick:** confirmation text screen par hi likha hota hai — usse **copy-paste** kar do, manually type karne ki zaroorat nahi
- Empty hone ke baad → select → **Delete** → `delete <bucket-name>` (ya jo bhi confirmation phrase ho) copy-paste → **Delete bucket**
- Yeh dono buckets (memory, frontend) ke liye repeat karo

**4. CloudFront distribution delete (sabse last)**
CloudFront delete karne se pehle usse **disable** karna padta hai:
- CloudFront → twin distribution select → **Disable** → confirm
- Disabling **5–10 minutes** le sakta hai (status "Deploying" dikhega) — wait karo, refresh karte raho
- Disabled hone ke baad → select → **Delete** → permanently deletes

Sab clean! Ab fresh slate par Terraform try kar sakte hain.

> **Sidebar tip (agle lecture mein bhi):** cleanup ke baad root user se sign in karke **Billing / Cost Management** check karo — spend zero (free tier) hi hona chahiye, par hamesha verify karo.

### Terraform kya hai aur kyun

**Terraform** — HashiCorp ka product, **Mitchell Hashimoto** ne (co-founder) likha tha ~15 saal pehle. (HashiCorp ne Vagrant bhi banaya.) Terraform ferociously popular hai — "ek baar use karo, phir socho ki iske bina kaise survive karte the".

Core idea: **infrastructure ko code likhke describe karo**. Iss approach ko **Infrastructure as Code (IaC)** kehte hain. Teen bade reasons:

1. **Control / versioned** — config git mein check-in hoti hai. Software ka har version apne infra version ke saath chal sakta hai (e.g. naya DB config naye release ke saath). Branch, version-control, merge, review — sab code wali cheezein milti hain. Purane "deployment sheets" (massive checklists jahan tum console mein click-click karte the) ki jagah. Ek hyphen galat (`us-east-1` se `useast1`) toh "god help you" — code se yeh galti nahi hoti.
2. **Automated** — button dabao, environment "soda can" ki tarah bahar aa jaata hai. Sab inter-resource dependencies (e.g. S3 bucket ka naam Lambda ke env var mein set karna) khud handle hoti hain.
3. **Repeatable** — ek baar likho, jitni baar chahe run karo — hamesha **same environment** milta hai. Isliye test environment bana sakte ho, phir bilkul wahi production banaa sakte ho.

### Terraform vs alternatives

- **AWS CDK** — AWS ka apna IaC, sirf AWS ke liye, popular.
- **Terraform** — multi-cloud. Yahi reason hai ki Ed Terraform padha raha hai: aage Week 3 mein **GCP aur Azure** ke liye bhi yahi tool use hoga. Industry mein Terraform bahut common hai — **achha resume fodder** (CV par "experience with Terraform" likh sakte ho).

Ed front-end ki tarah Terraform mein bhi **deep nahi jaayega** — code copy-paste karega, intuition dega, baaki "exercise for the reader". Par terminology zaroor samjhayega.

### 6 core Terraform terms (likh lo!)

Ed kehta hai kaagaz-pen le aao, yeh 6 terms note karo:

**Sabse essential 3 (yeh git mein check-in hote hain — environment describe karte hain):**

| Term | Matlab |
|---|---|
| **Provider** | Cloud vendor / plugin — AWS, GCP, ya Azure. Terraform ko us provider par apply karna sikhata hai. |
| **Variable** | Setting / parameter jo deployment control karta hai. e.g. `bedrock_model_id`. |
| **Resource** | Infrastructure ka fundamental building block. e.g. ek S3 bucket. Har resource code mein defined hota hai. |

**Baaki 3:**

| Term | Matlab |
|---|---|
| **State** | Terraform ki "reality ki samajh" — abhi live infra par actually kya deployed hai. Private files (`.tfstate`) mein store; **git mein check-in NAHI** karte (constantly badalta hai, apply par based hai). |
| **Output** | Deployment ke results. e.g. CloudFront distribution URL jo tumhe chahiye. |
| **Workspace** | Isolated, separate set of state — jaise "cloud in a box". Alag worlds: dev / test / prod. Namespace jaisa concept; ek hi config ko alag-alag workspaces par apply karke alag environments mil jaate hain. |

### Terraform commands (jo abhi chalayenge)

```bash
terraform init      # provider plugins download + working dir initialize
terraform apply     # config ko real infra par apply (resources create/update)
terraform destroy   # sab resources teardown / bring down
```

(Workflow simple: init ek baar, apply jab badlo, destroy jab khatam.)

### Pura mental model

```text
Tumhara code (.tf files)         Terraform                AWS (reality)
─────────────────────────        ──────────               ──────────────
provider "aws"          ───►   reads config   ───►   creates/updates
variable "model_id"            compares with          actual resources
resource "...s3..."            STATE (.tfstate)        (Lambda, S3, etc.)
                                     │
                               git ✓ code              git ✗ state
                               (versioned)             (private, changes)
```

Ed: "Enough talk — chalo Terraform ke saath kaam karte hain." (Agla lecture: install + pehli config files.)

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Manual cleanup** | Lambda → API Gateway → S3 (empty first) → CloudFront (disable first) — sahi order mein delete |
| **Infrastructure as Code (IaC)** | Infra ko code se describe karna — versioned, automated, repeatable |
| **Terraform** | HashiCorp ka multi-cloud IaC tool (Mitchell Hashimoto) — AWS/GCP/Azure sab |
| **Provider** | Cloud vendor plugin (AWS/GCP/Azure) |
| **Variable** | Deployment-controlling setting (e.g. bedrock model ID) |
| **Resource** | Infra ka building block (e.g. S3 bucket) |
| **State** | Terraform ki view of live reality (`.tfstate`, git-ignored) |
| **Output** | Deployment results (e.g. CloudFront URL) |
| **Workspace** | Isolated state for dev/test/prod (namespace jaisa) |
| **`terraform init/apply/destroy`** | Initialize / create-update / teardown commands |

---

## 💼 Backend Dev Ke Liye Note

Backend dev ke liye yeh course ka ek **inflection point** hai: ab tak "ClickOps" (console mein manual clicking) thi, ab declarative IaC. Mental shift: Terraform **imperative nahi, declarative** hai — tum "yeh banao, phir woh banao" nahi likhte, tum **desired end-state** describe karte ho aur Terraform diff nikaal ke reconcile karta hai (jaise Kubernetes manifests ya Ansible-with-idempotency). Sabse crucial production concept jo Ed touch karta hai: **state file**. `.tfstate` Terraform ka source of truth hai "kya deployed hai" ka — isko **kabhi git mein commit mat karna** (secrets leak ho sakte hain + merge conflicts disaster). Real teams ise **remote backend** (S3 + DynamoDB lock, ya Terraform Cloud) mein rakhti hain taaki team-wide shared + locked rahe — yeh course mein local rahega, par job par yeh pehla cheez hai. Cleanup ki ordering (CloudFront disable-then-delete, S3 empty-then-delete) yaad rakho: yeh dependency-graph realities hain jo Terraform `destroy` mein khud handle karta hai, par manual mein tumhe pata honi chahiye. Aur "ek hyphen galat = god help you" — yahi argument hai code review + plan-before-apply ke liye, jo `terraform plan` deta hai (apply se pehle dry-run diff dekhna — production mein non-negotiable).

---

## ✅ Takeaway

- Terraform se pehle **manual cleanup**: Lambda → API Gateway → S3 (empty karke) → CloudFront (disable karke, 5-10 min wait) — sahi order zaroori
- **Terraform = Infrastructure as Code**: version-controlled, automated, repeatable — manual ClickOps se kaafi better
- 6 terms: **provider** (cloud), **variable** (setting), **resource** (building block), **state** (live reality, git-ignored), **output** (results), **workspace** (dev/test/prod isolation)
- Terraform **multi-cloud** hai (AWS/GCP/Azure) — isliye AWS CDK se behtar choice; great resume skill
- Commands: `terraform init` → `terraform apply` → `terraform destroy`
- **State file kabhi git mein commit mat karo** — woh constantly badalta hai aur secrets ho sakte hain

---

<details>
<summary>📜 Full Transcript (English)</summary>

Welcome. Welcome to week two, day four. I have something really great in store for you today. I have Terraform. That is what we'll be working on today and it's going to be terrific. We are in the, uh, the section after building all of our Amazon infrastructure. I've taken you through the trauma of setting up all these different resources. And now I'm going to show you how you can do it all just with some code, super easily. And you'll hate me for making you go through that. Uh, but first, before before we go and visit the magic of Terraform, we actually have to have our final time going through all of the AWS screens, because we need to delete the resources that we've already created manually. So let's go. Go right now to AWS logged in as our IAM user and delete us some resources. So here I am at the console home. And a lot of what we're going to do is now in the recently visited. So we can just click straight here to go to Lambda. And you should only see twin API right here. Oh look at that new feature account color. That actually might be quite useful, and it is a good moment to just note that we are logged in as AI engineer the IAM user as we should be. Go into twin API. Here we are in twin API. Go to actions at the top and delete function. It's going to say deleting permanently removes its code. We'll press delete and it's been successfully deleted. Uh, now never fear we're going to be creating it again if you're wondering. But what about my digital twin? It's going to come back and it's going to be so much easier. All right. Next up let's go and look at the let's go back to the home page. And let's go next for the um let's go to the API gateway. Next API gateway. Right here we are going to find the twin API gateway. Click into here. And actually we didn't need to click into there. Sorry. Go back here I think we click here and press delete. Uh proceeding with this action will immediately delete all resources. Can't recover. It makes you type confirmed to be absolutely sure you know what you're doing. There we go. Delete. Successfully deleted. It has gone. Next up we're going to go to S3 and have a look at our S3 buckets. And we have a couple of them. We have the front end and memory. Let's start with memory. And this is a bit of a pain. But you have to empty it before you delete it. So select it and press empty. And then uh, in order to confirm that you have to type permanently delete. But as it happens, you can also do a little hack here of copying that copy and paste and then empty. That's a little pro trick for you. Uh, and it's now empty. Uh, and now we want to to go back and then we select it. It was the memory I emptied right. Select memory and press delete. And it says to confirm deletion enter the and you can't type there. But what you can do is copy here copy paste delete bucket. And it's gone. And now do the same. Of course. To the front end. Front end. Empty. Permanently. Delete. Use this little trick. Empty and it's gone. And now go back and select it and press delete and delete. Front end. Here we go. Copy and paste and delete bucket and success. We've deleted a bunch of resources. There's one more to go. And do you remember what the last one is? What's the last resource we haven't cleared yet? Yes, it's the CloudFront distribution. Back we go. You see, that was that listening thing again. Uh, the new new feature in Udemy. Uh. Uh, okay. So now we go to CloudFront, uh, and, uh, come here, go into our CloudFront distribution, our twin distribution, and we want to delete this and to delete it. So I think we go back here actually again we select there. Uh, and before you can delete it, you have to disable it. So we start by pressing disable. Are you sure you want to disable? Disable? Let it do that. And then we select it again. Uh, it's not yet been disabled, so we can't delete it yet. Hang on. Let's refresh our distributions. It's in the process of disabling it, so we'll have to wait just a second for this to to complete. Go back to CloudFront. It says deploying. So this again I think disabling it is something that can take 5 to 10 minutes actually. So I will put you on hold uh, while I deploy that. And I will see you in five minutes, which will just be one second for you. It's like you've just time traveled five minutes into my future. Here I am at no time passed for you. Uh, so now it has been disabled. I checked that box. I pressed the delete button, and that will permanently delete our distribution. And we have now officially cleaned up our resources. So it is my great joy to unveil for you Terraform, the product that we'll be using to create environments going forwards. Terraform, which was written it's written by by someone called Mitchell Hashimoto. And he founded, uh with someone else, a company called HashiCorp. Uh, his name, uh, there must be about 15 years ago or something now. And they came out with Terraform amongst. They also wrote vagrant. Um, and Terraform has been ferociously popular. Uh, and it's one of those things that that uh, once it's been been around everywhere, you kind of wonder how anyone survived without Terraform. Uh, and, and I want to give you a kind of explanation of, of, uh, what makes it so powerful and then talk you through the terminology so you feel ready for the week ahead of building with Terraform. And we'll, we'll be doing that, of course, for the rest of the course. And hopefully you will do for all of your time building production environments. It's the only way to do it. So, uh, the idea is it's all about creating infrastructure services by writing code to describe the configuration of the services. And it's known as this. This whole approach is called infrastructure as code IAC. You see it written as. And there are many reasons for doing this. But the three that first come to mind, first of all, this gives you control over your infrastructure. Your some at least some of the configuration is something that you check in to git. So you have it versioned, and different versions of your software could go along with different versions of your infrastructure, so that if you have a new database configuration or something that changes along with your your product release, then the Terraform scripts that will go along with that release and be packaged with it, and it can be branched and it can be version controlled and merged and reviewed and everything else that comes with code, it makes so much sense. Instead of just having some kind of deployment sheet we used, we used to have those those massive deployment lists, which would involve you going into things like AWS and clicking around the console. And you know, if you made a mistake like you left out a hyphen from us East one, then. Then. Yeah. Then all help you. So, uh, it's, um, it's just such a better way of doing it. It's also, of course, automated. We've been clicking around these console screens, and it's been laborious, to say the least. And it's all something where you press the button and the soda can comes out. The environment, the new environment comes out of the box. It goes around and effectively clicks through all the different screens. It deals with the fact that you have to go back and set the cause variable that came from setting up this it, setting the S3 bucket name and everything else. It's just all handled for you and it's repeatable. You can run it once and then run it again as often as you like, and you should always have exactly the same environment. And that also means you can build an environment once for test and then build the same environment for production, which is of course, a great thing. Now, uh, Terraform is is one, one version, one type of infrastructure as code. There are others. Uh, so AWS itself has a product called CDK, which is built specifically for AWS and it is quite popular. But I'm I'm teaching I'm going through Terraform here because Terraform is something that's supported with other providers as well. So we'll be able to use Terraform for GCP and Azure. And I would say in in industry generally Terraform is very, very common indeed. It's a great skill. It's a it's a good resume fodder to have this as something you can put on your CV and say that you have experience with Terraform. Uh, and, and it's just terrific. So I'm very happy to be talking you through this today. And rather like front end development, I'm not going to be going deep on Terraform. I'm going to be leaving that as an exercise for the reader. For the viewer, I guess, uh, that will will be copying and pasting code again. Uh, and I'll be giving you some intuitions to it, but asking you to go away, read through it, understand it in your own time. But let me give you the terminology, the things that to look out for the constructs, and you might need to get a piece of paper and pen to write these down. This is a good, good thing to to keep note of or a notepad on your computer, or however you note things down. Take note. Here are the six bits of terminology that we will be coming across very shortly. First of all, the word provider a provider in Terraform is like a it's a cloud provider. It's a vendor. It's AWS or GCP or Azure. It's it's it's a like a plugin which configures Terraform to be able to apply itself to that provider. A variable is like a setting. It's a parameter that controls your deployment. It's going to maybe the bedrock model ID would be an example of a variable. We'll have a bunch of them. A resource is the fundamental building block of your infrastructure. Your infrastructure will consist of a number of different resources. So an S3 bucket would be an example of a resource. And we'll be setting up several resources in each one you'll see defined in code that's that's and these three terms provider variable and resource. These are the most essential terms. If you remember anything it's these three. And we use these. And information about these gets gets checked into git. And so this this will really describe our environment to Terraform. And then for three more terms for you to write down uh state. So the state is uh, terraform understanding of what is the reality right now. What do you actually have at the moment deployed on your live infrastructure and state are stored in private, private variables that we do not check in to source control, because that's something that would would change and is based on you applying Terraform. Uh, output are the results of a deployment. So after you do a deployment you have outputs. And they are things like CloudFront distribution URL that you want to go to. So so those are the outputs from Terraform and a workspace. And this is a probably a more pro term. But we will be using that. We'll be using workspaces today. Uh workspaces allow you to have a completely separate, uh, set of state in an isolated way. I've got, like, a cloud in a box in the icon. It's like it's a different, isolated box in which you have all of your your state separately. And this allows you to have a separate world for development and test and production. Each of them is considered a separate workspace that you could switch between. And when you switch to it, you're in this completely different world of a different state. So it gives you that kind of very similar to a namespace that that kind of concept that applies to everything that you're working with. And so it allows you to have like one configuration that you'll then be able to apply to different, different worlds. So those are the key terms. And as you'll see the commands that you'll use there's a terraform init Terraform apply. These are the these are the commands that you use to to set things going. I think in the last slide I just said terraform init. But it's terraform init and terraform apply and terraform destroy brings things down. So these are the commands that are about to be running. Uh right now let's let's go and do it. Let's. Enough talk. Let's go and work with Terraform.

</details>
