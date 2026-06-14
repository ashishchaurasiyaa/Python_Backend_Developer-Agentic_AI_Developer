# L74 — Building ALEX: Multi-Agent Financial AI System on AWS Infrastructure

> **Week 3 · Day 3** · ⏱️ ~14 min

---

## 🎯 TL;DR

Capstone project ki shuruaat — **ALEX** (Agentic Learning Equities eXplainer), ek production-grade agentic financial planner SaaS jo AWS par deploy hoga. Iss lecture mein hum naya `alex` repo clone karte hain, uska top-level structure (backend / frontend / guides / terraform) samajhte hain, aur Ed ki working philosophy explain karta hai: Claude Code + gameplan.md se kaam karna, single environment, no GitHub Actions, local Terraform state.

---

## 🗣️ Hinglish Explanation

### "A big moment in the course" — wapas AWS, wapas purple, capstone start

Ed bolta hai yeh Week 3 Day 3 dikhne mein normal lagta hai par actually **bada moment** hai, teen reasons se:
1. **Wapas AWS** par (GCP/Azure detour khatam)
2. **Wapas purple** (AI-focused content)
3. **Capstone project shuru** — agle ~1.5 hafte ka main project: **ALEX**

### ALEX kya hai?

**ALEX = Agentic Learning Equities eXplainer** (slightly forced acronym, X = e**x**plainer). Yeh ek **commercial SaaS financial planner** hai:
- **Retirement advisor / financial planning advisor** through agentic AI
- **Production-ready aur scale ke liye built**
- **Equity portfolio review** karega: kitna **diverse** hai, future/retirement ke liye kitna planning hai
- **Recommendations** dega

> Observant students ne console screens mein "Alex" naam pehle hi notice kar liya hoga. Yeh course ka centerpiece hai.

### Course philosophy: deploy karna sikho, code likhna nahi

Important framing: **"this course is not so much about building the code... it's more about deploying the code."** Bahut saara code **already baked** milega (repo mein ready). Hum code review karenge par focus **production deployment** par hai. Aaj ka kaam: (1) code investigate, (2) permissions setup, (3) **pehle costs check** karna.

### Step 1: AWS Costs check (root user)

```
1. AWS Console → sign in as ROOT user (costs + IAM ke liye root use karte hain)
2. Billing and Cost Management → costs review karo
3. Anomalies check karo — kuch unexpected toh nahi
```

Ed reminder deta hai: Azure aur GCP par bhi wapas jaake confirm karo ki **kuch run nahi ho raha** (free credits bhi consume nahi ho rahe), unless intentionally chhoda ho.

> **Root user** = AWS account ka master account (full access). Best practice: rozmarra kaam ke liye nahi, sirf billing/IAM jaise account-level tasks ke liye use karo. Baaki sab IAM users se.

### Step 2: Naya `alex` repo clone karo

Pehle context ke liye **production repo** dekho: `week3` folder ka README batata hai — Days 1-2 = cyber repo, Day 3 = naye `alex` repo par move karo.

```bash
# projects directory mein (production ke parallel)
cd ..                       # production se ek level upar, projects/ mein
git clone <alex-repo-url> alex
cd alex
ls                          # alex ka content dikhega
```

Phir Cursor mein: `File → New Window → projects/alex → Open Project`.

### Step 3: ALEX repo ka top-level structure

Ed warn karta hai: *"there's a lot going on... don't worry if it seems overwhelming at first. It's nicely organized."*

| Folder | Kya hai |
|---|---|
| **`backend/`** | Saara backend code — har subdirectory ek alag backend component (mostly apna **UV project** with `pyproject.toml`, Python version, virtual env, Python files). Components mostly **Lambda function** ya **App Runner** par map honge. |
| **`frontend/`** | Frontend code |
| **`guides/`** | **Recipes** for har deployment step — `guides 1` se `5` (aur zyada aayenge). Ek guide ek din ya multiple guides ek din. |
| **`terraform/`** | Multiple subdirectories — **har ek alag independent Terraform deployment** (separate `terraform init`, separate state). |
| (misc files) | Baad mein important honge |

### Backend structure: components → compute

Backend ke subdirectories course ke pichle patterns se map karte hain:
- **App Runner** — Week 1 (healthcare app) jaisa, container-based; GCP/Azure jaisa
- **Lambda function** — Week 2 (digital twin) jaisa, serverless

Har backend subdirectory **apna independent UV project** hai — apna `pyproject.toml`, apna virtualenv, apni Python files. Chhote-chhote standalone projects.

> **UV** = fast Python package/project manager (pip + venv + pip-tools ka modern replacement). Har component ka apna `pyproject.toml` matlab dependencies isolated hain.

### Terraform structure: separate deployment per component

Ed ne Terraform ko **alag-alag directories** mein toda hai — har directory mein **alag `terraform init`** aur **alag Terraform state**.

```
terraform/
  2_sagemaker/          # aaj iska kaam (guide 2 se map)
    .terraform/         # init ke baad banta hai
    main.tf             # deployment definition
    outputs.tf
    variables.tf        # kuch mein hota hai
  ... (aur components)
```

**Kyun separate?** Component architecture mein yeh common practice hai — har piece independently deploy karne se **methodical, step-by-step** progress hoti hai. (Tum chaaho toh sab ek bade Terraform script mein merge kar sakti ho, par Ed deliberately isolate kar raha hai clarity ke liye.)

> **Terraform state** = ek file jo track karti hai ki real infra mein kya-kya created hai (mapping between config aur actual cloud resources). Alag directories = alag state files = ek deployment doosre ko affect nahi karega.

### Guides ↔ Terraform tie-in

Guides aur Terraform directories ek-doosre se map karte hain. Aaj **Guide 1 + Guide 2** karenge:
- **Guide 2 (SageMaker)** → `terraform/2_sagemaker/` directory
- Guide padhte-padhte uska infra install hota jaata hai — neat parallel.

### Ed ki AI-assisted workflow: Claude Code + gameplan.md

Repo mein `.claude` files dikhenge — Ed ne **Claude Code** heavily use kiya hai (ya Cursor ke built-in agents). Required nahi hai course ke liye, par bahut helpful. Uska pattern:

1. **`guides/gameplan.md`** banaya — ek file jo model ke liye poore project ka context, structure, aur "plan of attack" likhti hai.
2. Claude Code start karo:

```bash
claude
```

3. Pehla prompt:

```
Please start by reading the file gameplan.md in the directory guides
and let me know when you're ready.
```

4. Ab Claude poore project pe **fully briefed** ho jaata hai. Phir specific guide read karne ko bolo — wo us guide par briefed ho jaata hai.

> Same approach Cursor agent ke saath bhi kaam karta hai: gameplan padhao → guide padhao → repo structure, approach, objectives samajh ke instantly help karega.

### Ed ki honest warnings

- **"You are going to have problems"** — Ed ne khud second install par issues face kiye (jaise ek Bedrock model ka temporary known error jisne ghante laga diye debug karne mein). Region, factors, moving parts — sab variable hain. **Yeh good hai** — problems track karke hi seekhoge.
- **"Don't trust Claude Code blindly"** — wo jaldi conclusions pe jump karta hai, same mistake repeat karta hai (gameplan mein warning daali phir bhi). Net **value-add hai**, par **sab carefully check karo**.

### Kya NAHI hai ALEX mein (deliberately simple)

Ed do simplifications batata hai:
1. **No multiple environments** (dev/test/prod) — sirf **ek environment**, jo directly test/production hai. Code seedha production par build+deploy hoga.
2. **No GitHub Actions (CI/CD)** — focus multi-agent production deployment par rakhne ke liye.

> Par ab tumhare paas Week 2 ke skills hain — **tum yeh add kar sakti ho** (excellent next step): multiple environments + GitHub Actions CI/CD. Aur dhyan do: **Terraform state local store ho raha hai** — production mein isse **S3 bucket par move** karo (Week 2 jaisa). Ed ne simplicity ke liye local rakha.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **ALEX** | Agentic Learning Equities eXplainer — capstone SaaS financial/retirement planner agent |
| **Capstone** | Course ka main project, ~1.5 hafte chalega, AWS production deployment |
| **Root user** | AWS master account — sirf billing/IAM jaise account-level kaam ke liye |
| **Repo structure** | `backend/` + `frontend/` + `guides/` + `terraform/` |
| **Backend component** | Har subdirectory ek independent UV project → Lambda ya App Runner par deploy |
| **Guides** | Step-by-step deployment recipes (guide 1..5+), Terraform dirs se mapped |
| **Separate Terraform dirs** | Har component ka independent `terraform init` + state (methodical deploys) |
| **Terraform state** | Config ↔ actual cloud resources ki mapping; alag dirs = alag state |
| **gameplan.md** | Project context file jo Claude Code/Cursor agent ko brief karti hai |
| **Single environment** | Koi dev/test/prod split nahi — directly to production (simplicity) |
| **No GitHub Actions** | CI/CD deliberately skip (Week 2 skills se khud add kar sakte ho) |

---

## 💼 Backend Dev Ke Liye Note

Yeh lecture ek real-world **monorepo + component architecture** ka blueprint hai jo har backend dev ko relate karega. `backend/` ke andar har component apna UV project (apna `pyproject.toml`, isolated deps) hona — yeh microservices-style isolation hai jisse ek service ki dependency dusri ko break nahi karti. Terraform ko per-component split karna (alag state per directory) production IaC ki ek deliberate trade-off hai: **blast radius chhota** rehta hai (ek component ka apply doosre ko touch nahi karta) aur deploys methodical rehte hain — par tumhe cross-component dependencies (jaise outputs) manually wire karne padte hain (yahan `.env` + `terraform.tfvars` dono mein values daalna). Ek strong production-readiness signal Ed ne diya: **local Terraform state production mein S3 par move karo** — local state team collaboration aur durability ke liye dangerous hai (state corrupt/lost ho sakta hai). Aur AI-assisted dev ki realistic framing — gameplan.md jaise context file rakhna (essentially "CLAUDE.md for the project") aur agent output ko hamesha review karna — yeh aaj ke production backend workflow ki sachhai hai.

---

## ✅ Takeaway

- **ALEX = capstone**: agentic financial/retirement planner SaaS, ~1.5 hafte, AWS production
- Repo structure: **`backend/`** (per-component UV projects → Lambda/App Runner) + **`frontend/`** + **`guides/`** (recipes) + **`terraform/`** (per-component separate state)
- Course ka focus **deploying** code par hai, likhne par nahi — bahut code already baked hai
- Ed ka workflow: **Claude Code + `guides/gameplan.md`** se brief karo, par output **carefully check** karo — "you will have problems, that's where you learn"
- Deliberate simplifications: **single environment, no GitHub Actions, local Terraform state** — par production mein state ko **S3 par move karo** aur CI/CD + multi-env add karna great next step hai

---

<details>
<summary>📜 Full Transcript (English)</summary>

Well, this is a big moment in the course, and I want to I want to welcome you and get you excited about what is to come. It feels like it's just any old day. It's week three. Day three. It doesn't sound like it's a major exciting moment, but it is for a few reasons. One is that we are returning to AWS. One is that we are starting back with purple again. We are going back to AI related activities, and one is that we are about to embark on the beginnings of the capstone project, which will take us through most of the next week and a half of activity. And it is called Alex. Now, the observant amongst you already were expecting something called Alex, because you probably saw it in some of the resources. When we were looking through some of the console screens, you knew that I'd been working on this thing, and now you're eager to find out what it is. So Alex slightly forced acronym as they sometimes are. It's a financial planner. Alex is going to be a commercial platform which is able to be, uh, a retirement advisor, a financial planning advisor through a genetic AI. So it is it stands for it's an acronym. It stands for the Agentic Learning Equities explainer, the X in explainer being Alex. So it's a bit forced. But Alex I thought was a good name for it. And the idea is that it is a SaaS commercial application that we will build that is ready for scale, that is deployed to production. It's going to act as a financial advisor. It's going to be able to review an equity portfolio, assess it for things like how how diverse is your portfolio, how much are you thinking about the future? How are you planning for retirement? And it will make recommendations. Um, the first step that we're all about to go through now is about getting you set up. It's going to be cloning a new repo. We're going to be cloning a repo. A lot of the code is going to be baked already for you, because this course is not so much about building the code. Although of course, again, we'll review it. It's more about deploying the code. And for what we're going to do today, we're going to be doing some investigation on how the code looks. And we're going to be setting up permissions. Uh, and first, before we do any of that, we are, of course, going to be looking at our costs to make sure everything is as we expected. So let's go and do that now. And welcome back to the AWS console. Did you miss it? Here it is I'm signed in. Of course it's my root user which you should do because we do that when we're looking at costs and and IAM stuff. You'll see that I'm here logged in where it has my name as my root user. And the first thing we'll do is go to billing and cost management, billing and cost management, something that you should do a lot and come in here make sure. No doubt you see that I've had my, uh, big month last month and now I'm spending rather less this month. You should look at your costs. Make sure they're what you expect. If you've got any anomalies, you should look at them and make sure you're happy with them and do this regularly. And this might be a good time for me to remind you to go back in and have a look at the same kind of thing that we saw in Azure and in GCP to make sure that you're not spending anything anymore. Everything is closed down. You're not even consuming your free credits. Unless of course, you decided to keep things running. Uh, so a good chance to do all of that. When you're done with that, it's time for us to switch over to look at our new repo for this week. And actually, the best way to show you the repo is to start by going back to the production repo. If you remember that the one where it all began, uh, and we're in week three, so we should look in the week three. There is a readme, and if we open the preview you'll see that this is for days one and two. Go to the cyber repo which is what we did. And now we're on day three. Please move over to the repo. So from our projects directory there's something to get clone. So we first bring up a new terminal window. We're inside the production directory so we want to go up one. Now we're inside the projects directory which has production amongst the others. And you now run this git clone command right here. And I'm not going to run it because I've already git cloned. Of course, it's already in the folder called Alex. If I do myself a CD Alex as you can do, and I have a look, there is some stuff for Alex. And now within cursor I'm going to go to file and New window and I'm going to select Alex. You can press Open Project. We can do that right now. Open project go into production. Sorry no go into projects. And then there's projects and then into Alex. There's Alex and then press open and it opens Alex. We'll make that a bit bigger. And let's talk through the repo that we're looking at here. So, look, I'm not gonna lie, there's a lot going on in the repo, and that's why we're going to spend a week and a half on it. So you're going to have plenty of time to get super familiar with this. So don't worry if it seems a little bit overwhelming at first. It's nicely organized, nicely structured. And we will definitely we will dig in. So I just want to start by telling you about the top level folder structure and a little bit about what's there, and then something about what's not there as well, just so that it's very clear to you. So at the top level you'll see that we have a folder called backend, which is going to contain all of the backend code, a folder called frontend. Shockingly, with front end code guides is where we will spend a lot of our time. This is where all of the recipes are for doing all the deployment we're going to be doing. The code is mostly already written. Terraform is a directory which contains within it a number of subdirectories. Each one is a different, Front, uh, Terraform setup that will go through in a second. Uh, and then we have a number of, uh, of other files that will become important later on. So let's just quickly look at two of these back end and Terraform to talk a bit more about what's involved. So the back end folder quite simply contains subdirectories for each of the different back end components that we'll be building. And many of these will map either to a Lambda function or a app runner. If you remember that app runner is what we did in the first week with our healthcare app. And similar to what we did with GCP and Azure, uh, whilst the Lambda function is serverless, architecture is what we did in the second week with the twin. So there are a bunch of these, each one of these directories, not all of them, but most of them are themselves like uh, their own UV project with their own pyproject.toml or in Python version, their own virtual environment, a whole setup with a bunch of Python files in most of these subdirectories, each one like a little independent project in its own right that is backend. And then I also wanted to talk a bit about Terraform. Terraform contains our different Terraform deployments. And the way I've structured it is I've actually broken it down into separate directories. And in each directory we'll be doing a separate Terraform init to set up its own terraform state within that directory. And that is a fairly common practice. It's quite common to do it this way. If you have multiple components in a in a component architecture, you might deploy each one with a separate Terraform kind of deployment in its own. You can also just do them all in one. But in our case, because we want to be able to step methodically through this process, I wanted to deploy each one independently of the other, and that's why everything is set up as an independent deployment, not as kind of one massive deployment that builds all of Alex in one script, but you can merge it that way should you wish you could create one big, uh, Alex Terraform if you wanted to? So you'll see within each one, like within this, this one SageMaker that we'll be doing today. If you open it up, you'll see that there is uh, the private the dot terraform folder. You'll see there is a main.tf with the definition of the terraform deployment and outputs. And some of them have have variables as well. So each one a separate Terraform deployment. And in all there are a bunch of them all in the Terraform directory. And then the other directory that we're going to live in really is guides. Guides has the kind of recipes for everything that we're going to do. There's a guides one through to five right here. And you will probably have a bunch more guides, uh, by the time I'm through with this. Uh, so it's not on some days we're going to do multiple guides on the same day. Like today, we're planning to do guides one and two. Uh, some days will just be devoted to a single guide. Each guide may map to a separate terraform directory. You can see that guy number two on SageMaker maps to the two SageMaker Terraform directory. Because as we're going through that guide, we'll be installing that infrastructure while we go. So you will see that nice tie in in, in both directories. Uh, and uh, so that's, that's the structure of the repo. Uh, and now let me finish with a couple of things that, that are there and are not there. So one of the things that is here that may interest you, that you might have seen from, from some of the others as well, is the existence of these dot clawed files and a few other hints that I have been using clawed code for a lot of this, and that's something which I personally addicted to clawed code. I don't know if you've tried it or not, it's certainly not something that is required for this course, but if you have it and if you have a subscription, it can be incredibly helpful, as can the agents that are built in to cursor. Um, but what I tend to do is heavily use files to help me, and so that it can be used for either Claude code or for cursors agents. I've made a file in guides called gameplan that really lists out in in a in a way that will make most sense to a model, what's going on in this whole project and what what what plan of attack we have for building this infrastructure. And what I do whenever I start Claude code is I begin. So if I, if I show you, you're probably familiar with this, but for those that don't know, you start Claude code by typing. Claude, if you've installed it, uh, and it says welcome. And then I'll say something like, please start by reading the file gameplan.md in the directory guides and let me know when you're ready. And when I do this, this means that, uh, that Claude is now going to educate itself on everything about what's going on. And what I'll then do is tell it to read. Uh, and it's talking about something which is an error that's now fixed, which was the last time I had it work on this. Uh, what it's going to do is it's going to read that whole game plan and be fully briefed on everything about this project, and you can then tell it to read a specific guide, and it will then be briefed on that guide in particular. So when you have problems with the infrastructure, then that's the way I recommend approaching it. And you can do exactly the same with the cursor agent. Tell it to read game plan, tell it to read the guide, and once it's read the game plan, it will understand the repo structure. It will know about how we're approaching this and our objectives of the project, and it will be able to help you immediately with any problem. And that leads me to to to the other thing, which is that you are going to have problems with this. Uh, I built all of this, and then I went back a second time to install it, and already I had problems because things had changed. It turns out that the the model I used the first time around has some problem in bedrock at the moment. That means that it's throwing some some error. That turns out to be a bedrock temporary problem, a known problem. Uh, and it took me it took me several hours to figure out that's what it was and to find a workaround. So this stuff is hard, and there are a lot of moving parts out there. There's a lot of variables like what region you're in and lots of other factors that might affect what happens when you do this. So you are going to have problems. But that's a good thing. That's that's where you will learn. You'll learn by tracking down the problems, by figuring out what they are and by solving them. And Claude code can help. I'm going to say one more time. I know I've said it several times that you shouldn't trust Claude code. It will often jump to a conclusions. I've got stuff in the game plan telling it not to jump to conclusions, but it still does. It often repeats the same mistake. It can be pretty frustrating, but as a net it is very much a value add. There is no question that I'm able to to work more productively hand in hand with Claude code, but I check everything carefully as we go. So, so that's that's an instruction for you. Finally, I wanted to mention something that's not here. I have not built Alex to have different environments like development, test and production. There is only one environment and it is our test or production environment, which is going to be building and deploying straight to production. And I'm also not using GitHub actions. The reason is because I just wanted to keep things simple and focus on a multi-agent production deployment. But now that you've got those skills from week two, you absolutely can incorporate that in this and it's a great step to make. Just remember I'm storing terraform state locally and you'll want to move that to be deployed in in AWS on an S3 bucket, just as we did in week two. But if you would like to do this with multiple environments and have it deployed through GitHub actions, then you should absolutely do that as we go. But I'm going to keep it simple for now. And we're just going to be using, uh, the one environment, no GitHub actions and deploying direct.

</details>
