# L64 — Multi-Cloud AI Deployment: Azure, GCP & Cybersecurity Agent Setup

> **Week 3 · Day 1** · ⏱️ ~12 min

---

## 🎯 TL;DR

Week 3 ka kickoff — Ed ise "smorgasbord" bolta hai: ek hi week mein Azure, GCP, MCP, SageMaker, vectors aur data pipelines ka taste. Aaj-kal (Day 1-2) hum **Cyber Security Analyst** project banayenge — Next.js + FastAPI + OpenAI Agents SDK + MCP, Docker mein packaged, Terraform se Azure aur GCP dono par deploy. Pehle hi lecture mein teen cloud providers ki **five-archetype mapping** (server/PaaS/CaaS/orchestration/serverless) compare karte hain.

---

## 🗣️ Hinglish Explanation

### Week 3 = smorgasbord (mixed platter)

Week 2 survive kar liya — ab Week 3. Ed ise **smorgasbord** kehta hai (Swedish buffet — sweet aur savory cheezon ka ek bada platter). Do reasons:

1. **Variety** — bahut saari alag-alag cheezein ek saath, entertain karne ke liye.
2. **Taste, not depth** — kisi ek cheez mein utna deep nahi jaayenge jitna AWS mein gaye; bas **exposure across the board** dena hai.

Week 3 ka roadmap:
- **Day 1-2** → Microsoft **Azure** + Google **Cloud Platform (GCP)**, MCP ke saath thoda AI tadka. AWS jitna deep nahi, par AI engineer ke liye in dono platforms ka exposure zaroori hai (clients/employers kabhi bhi Azure/GCP maang sakte hain).
- **Day 3-5** → "very AI, very purple" — Amazon **SageMaker**, **vectors** (data ingest with vectors), aur **data pipelines** with an agent + MCP. AWS par wapsi.

Ed apne color-coding ka reference deta hai: **yellow = cloud/platform engineering**, **blue = building a real app/project**, **purple = AI/agentic work**. Day 1-2 "mostly yellow" hai (platform engineering), par usme blue (project) aur purple (agentic AI) dono ka mix hai.

### Aaj-kal ka plan (Day 1-2 ka project)

- **Cloud platform engineering (yellow)** — Azure aur GCP ko rapidly explore karenge, AWS se zyada tez. Consoles bhi dekhenge par mostly **Terraform** se deploy karenge taaki screens/consoles ke chakkar mein na padein.
- **Terraform Workspaces ka clever use** — Week 2 mein humne workspaces se dev/test/prod environments alag kiye the. Is baar **same project ko do workspaces mein** rakhenge: ek workspace Azure ke liye, ek GCP ke liye. Har provider ke liye sirf **ek environment** — simple rakhenge.
- **No GitHub Actions** — Week 2 mein CI/CD ka idea aa gaya. Jise chahiye wo khud `git push` based pipeline laga sakta hai (ab tumhare skill set mein hai), baaki log usse skip kar sakte hain.

**Project (blue) = Cyber Security Analyst:**
- Ek file of code leke usme **security vulnerabilities** check karta hai.
- **Next.js front end** (app router ke saath).
- **FastAPI back end**.
- **Docker container** — front end aur back end dono ek hi container mein (bilkul Week 1 ke healthcare app jaisa).
- **Terraform** se packaged/deployed.

**AI part (purple):**
- OpenAI **Python client library nahi**, balki **OpenAI Agents SDK** use karenge (Ed ke baaki courses wale familiar hain).
- Ek **MCP server** se agent ko cybersecurity skills milengi.

### Cloud archetypes — teen providers ka comparison (THE core slide)

Week 2 mein Ed ne **five deployment archetypes** introduce kiye the. Yeh paanch hote kya hain, samjho:

1. **Traditional server / IaaS** — ek raw virtual machine milti hai, tum khud OS, runtime, sab manage karte ho. Sabse zyada control, sabse zyada maintenance.
2. **Platform as a Service (PaaS)** — tum sirf code do, platform server/scaling sambhaalta hai (Vercel ek PaaS hai).
3. **Container as a Service (CaaS)** — ek Docker container do, platform usse chala deta hai. Simplest container deployment.
4. **Container orchestration** — bahut saare containers ko manage/scale/heal karna (Kubernetes ki duniya).
5. **Serverless function** — ek function likho, har request par platform usse spin karta hai, idle par kuch nahi chalta.

Ab teen providers ki mapping (yaad karne ki zaroorat nahi, look up kar sakte ho, par sun lena achha hai):

| Archetype | AWS | Azure | GCP |
|---|---|---|---|
| **Server (IaaS)** | EC2 | Virtual Machines | Compute Engine (GCE) |
| **PaaS** | Elastic Beanstalk | App Service | App Engine |
| **Container (CaaS)** | App Runner | Container Apps (ACA) | Cloud Run |
| **Orchestration (K8s)** | ECS / EKS | Azure Kubernetes Service (AKS) | Google Kubernetes Engine (GKE) |
| **Serverless function** | Lambda | Azure Functions | Cloud Functions |

Ed ke notes:
- AWS naming thodi cryptic hai (EC2, ECS/EKS); Azure aur GCP ki naming **bahut down-to-earth** hai (Virtual Machines, Compute Engine, App Service, App Engine — naam se hi pata chalta hai).
- "EKS" ka **K = Kubernetes** (ECS = Elastic Container Service, EKS = Elastic Kubernetes Service).
- Log GKE ko hamesha "GKE" bolte hain, aur "Cloud Run"/"Cloud Functions" ko acronym nahi dete — bas naam se bulate hain.
- Yeh **far from the full landscape** hai — teeno providers ke paas services ka "monstrous slew" hai (humne AWS mein SQS, API Gateway, CloudFront waghaira dekhe). Yeh sirf har provider ke **big five** hain.

### Hum kaun-sa archetype use karenge?

**Middle wala — CaaS.** Yaani **Azure Container Apps (ACA)** aur **Google Cloud Run**. Plan:
1. Ek **Docker container** banao.
2. Use Azure par deploy karo.
3. Use GCP par deploy karo.

Container deploy karna sabse **simplest use case** hai (Week 1 ka healthcare app App Runner par yahi tha). Aur sabse important — ek baar Docker container ban jaaye toh teeno providers par deploy karna **sabse consistent** rehta hai. Ed ki general advice:

> Agar tumhare paas ek Agentic app hai aur deploy karne ka sochte ho — sabse simple pehla tareeka: Docker container mein daalo, locally ensure karo chalti hai, phir us container ko App Runner / ACA / Cloud Run par bhej do. Teeno bahut similar hain aur bas kaam kar jaata hai.

Ek catch: **Apple Silicon** (M1/M2/M3 Macs) par Docker container build karte waqt architecture mismatch ho sakta hai — `--platform linux/amd64` waghaira ka dhyaan rakhna padta hai. Yeh chhoti cheez off-guard pakad sakti hai; sahi build karoge toh bas kaam karega — yahi Docker ki beauty hai.

### Lab: repo clone karna

1. **Production repo** kholo (jo course shuru hua tha) → left mein **`week3`** folder → andar single file ka **README preview** kholo. Yeh first instructions deta hai.
2. README bolta hai: ek alag repo par move karo — **`cyber`** repo (Ed ka pre-built repo). GitHub par Ed ke page se bhi "cyber" search karke mil jaayega.
3. Pichhle weeks mein hum scratch se repo banake copy-paste karte the. Is baar Week 3 **productionizing** ke baare mein hai — Ed pre-built projects dega jo wo samjhaayega, aur saath milke production mein deploy karenge.
4. Terminal kholo. Wo usually **production** directory mein khulega — par humein **parent directory (ek upar)** chahiye jahaan saare projects rehte hain.
5. Wahaan se `git clone` command (README se exact copy) chalao taaki `cyber` repo tumhare projects directory mein clone ho jaaye:

```bash
# projects/ directory ke andar se
git clone <ed-ka-cyber-repo-url> cyber
```

6. Cursor mein **File > New Window** → **Open Project** → projects mein jaake **`cyber`** select karo → **Open**.
7. `cyber` repo khul gaya — yahi agle do din ka playground hai. Terminal band karke fresh shuru karo.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Smorgasbord** | Week 3 ka nature — variety + taste, har topic ka thoda exposure, deep dive nahi |
| **Five archetypes** | Server / PaaS / CaaS / Orchestration / Serverless — deployment ke 5 types |
| **CaaS (middle archetype)** | Container as a Service — Docker container do, platform chala deta hai (simplest) |
| **Azure Container Apps (ACA)** | Azure ka CaaS — AWS App Runner jaisa |
| **Google Cloud Run** | GCP ka CaaS — container deploy karne ka easiest tareeka |
| **Terraform Workspaces** | Ek hi project, alag-alag isolated states — yahaan Azure aur GCP ke liye 2 workspaces |
| **Cyber Security Analyst** | Day 1-2 ka project — code file ki vulnerabilities scan karne wala agentic app |
| **OpenAI Agents SDK** | Plain OpenAI client se aage — agents, tools, MCP support wala framework |
| **MCP server** | Agent ko bahari skills/tools dene ka protocol — yahaan cybersecurity scanning |
| **Apple Silicon Docker gotcha** | ARM Macs par container build karte waqt `linux/amd64` platform ka dhyaan |

---

## 💼 Backend Dev Ke Liye Note

Ek Python backend dev ke liye yeh lecture **cloud portability** ka mindset deta hai. Tumne shayad ek hi cloud (AWS) mein kaam kiya ho, par real-world mein clients/teams Azure ya GCP par bhi hote hain. Achhi khabar: **Docker container = lowest common denominator**. Ek bार apni FastAPI app ko cleanly containerize kar lo, toh App Runner / ACA / Cloud Run — teeno par wahi artifact deploy ho jaata hai, sirf wrapping (IaC + IAM/identity) provider-specific hoti hai. Yeh exactly woh "build once, deploy anywhere" promise hai jo CaaS deta hai. Aur Terraform Workspaces ka pattern note karo — production code mein same module ko alag backends/targets ke liye reuse karna ek powerful DRY technique hai (dev/test/prod ya yahaan Azure/GCP). Backend engineering perspective se, in providers ki naming-to-archetype mapping yaad rakhna interview aur architecture discussions mein kaam aata hai.

---

## ✅ Takeaway

- **Week 3 = smorgasbord** — Azure, GCP, MCP, SageMaker, vectors, pipelines ka mix; breadth over depth
- Teeno providers ki **five-archetype mapping** yaad karne layak hai (EC2/VM/GCE, App Runner/ACA/Cloud Run, Lambda/Functions/Cloud Functions)
- Hum **middle archetype = CaaS** use karenge: Docker container → ACA (Azure) + Cloud Run (GCP)
- Day 1-2 project = **Cyber Security Analyst** — Next.js + FastAPI + OpenAI Agents SDK + MCP, Docker-packaged, Terraform-deployed
- Pre-built **`cyber` repo** clone karo (scratch se nahi banaya is baar); ek **upar wali projects directory** se clone karna

---

<details>
<summary>📜 Full Transcript (English)</summary>

Well, you survived week two and I am now delighted to welcome you to week three. And week three is something that I might describe as a smorgasbord. Do you know what a smorgasbord is? This, this here is a smorgasbord, and I describe week three as a smorgasbord for two reasons. One of them is that it consists of a wide range, a selection of different things to to entertain you, a selection of sweet and savory items. And the other reason is that it is something of a taste of several different things. We're not going to go as deep, not as substantive in any one, but rather to give you some exposure across the board. And to demonstrate that, let me show you what I have in store for you this week. We're going to start by looking at Microsoft Azure, and then we'll move on to Google Cloud Platform. It's we're not going to go nearly as deep as we do with AWS. But it's important as AI engineers looking to to deliver AI solutions to production that you have some exposure to these other platforms, and we'll throw MCP into the mix just to make it a bit AI ish. And then for the next three days, we're going very AI. We're going to look at Amazon SageMaker. And we're back to Amazon again back to AWS. We'll be looking at using vectors, ingesting data with vectors and then data pipes with an agent and MCP. So a lot of purple a lot of AI topics to look forward to. I've got a great week ahead for you. So today and tomorrow we're going to be doing a project which is going to have something for everyone. It's going to be ticking a lot of boxes. It's going to be mostly a yellow day in that or yellow two days in that. We're going to be looking at cloud platform engineering first and foremost. Rapidly looking at Azure and GCP more quickly than AWS will be using Terraform to deploy so that we don't have to go through lots of screens and consoles. Although we will look at them, we're going to be using workspaces. We used Terraform Workspaces last week to separate the development, test and production environments, which is very common, and this time we're going to be using them cunningly to have the same project deployed to Azure and GCP in two different workspaces. Very convenient. And we're just going to have one environment for each. We're going to keep it simple. And we're not going to use GitHub actions because you got the idea we did that last week. If that's something you're really into for sure you can you can do this as part of this project as well. So you can just do a git push while the rest of us are envious. That's that's in your skill set now anyway. That's the main focus. It's yellow. But we've also got some blue that we are going to build a juicy project. We're going to build something called the Cyber Security Analyst. Uh, a little project which is able to take a file of code and check it for vulnerabilities. It's going to be a Next.js front end. Again with the app router. We're going to use a fast API back end. Of course, it's going to be packaged by Terraform. And we're going to use Docker again. We're going to have a Docker container with both the front end and back end in it, much as we did for the healthcare app in week one. but there's also a bit of purple. In the next two days. We're going to be doing some AI work as well, but we're not going to be using the OpenAI Python client library. We'll be using the OpenAI agents SDK that people from my course are very familiar with, and will be using an MCP server. We're going to be using an MCP server to give our agent to equip it with cybersecurity skills. And that's going to be great. So there's some agentic AI. There's there's a lot that we're going to be doing in the next two days. And it really ticks all the boxes. It's mostly yellow, but there's plenty of blue and purple in the mix to keep you entertained. All right. So prepare yourself for an important moment. In this course we're going to compare the different cloud services across the three big providers AWS, Azure and GCP. And this you remember are the five different archetypes, the five different types of deployment Architecture that we that we mentioned last week a traditional server. Infrastructure as a service like Amazon EC2. A platform as a service. Container as a service. Container orchestration. And then serverless. Function. And if we start by talking about AWS, let me quiz you now have I think I want you to say out loud, using that famous Udemy technology that listens to what you say and say out loud, what is each of the AWS components for these different things? What's the AWS component for server that we didn't actually use? But I talked about a few times, it's perhaps the original of the Amazon components. It is of course EC2. Uh, what is the platform component. So this would be like it's Vercel is a is a pass. Uh, Amazon has one two. We also didn't use it ourselves, but I mentioned it. So I won't be surprised if you if you don't know it. And it's also not that as well known as the others. Beanstalk is their product for that. The Container. Now, this one you should know because we used it in week one. The container as a service. You package a Docker container and off it goes. This is what we used for the healthcare SaaS app. And this is of course App Runner. Uh and now container orchestration. We didn't use that. You can be forgiven for not knowing this, but if you do know it then congratulations. It is of course ECS or EKS, the K for Kubernetes uh, rather than container. Uh, and uh, last but not least, definitely not least the one that is the talk of the town. What is the the AWS function? Yes, it is of course AWS Lambda, that is AWS roster. And now we're going to compare it with the other providers okay. Starting then with Azure bring Azure into the mixture. I'm just going to show them all together. So you you can you can compare them one on one. The equivalent of of EC2 C2 is virtual machines. It's actually very down to earth name uh, less to remember. Generally, Azure's naming is nice and GCP two actually is pretty clear. What's going on. The, uh, the the platform, the pass is called App Service. Uh, the container one, the one in the middle, uh, is called Azure Container Apps, also known as ACA. The container orchestration one for building and deploying large scalable cloud orchestration products that is called Azure Kubernetes Service. And then the one that is the equivalent of Lambda is called Azure Functions. That's that's a pretty easy to remember. And GCP actually also they don't have fancy names. Uh, the the server, the one on the left is called Google Compute Engine. It's sometimes called GCE Google Compute Engine. The next one along is called Google App Engine. So it makes sense, right? You either got compute or app. Uh, and yeah it's similar to Azure App Service. The the one that is for containers running is called Cloud Run or Google or GCP cloud run. Cloud run. The next one is called Google Kubernetes Engine. Although I almost always hear that just called GKE. People just say GKE for Google Kubernetes Engine. And then the equivalent of Lambda and Azure Functions in Google's world is called Google Cloud Functions. Google Cloud Functions. And I don't think I don't I don't think people give that an acronym. I think people just say Cloud Functions and Cloud Run as well. I don't know why, but that's what I always hear cloud run and cloud functions. So that is the full landscape of AWS, Azure and GCP. And when I say the full landscape, it is far from the full landscape. All three providers have a monstrous slew of different services and names and components. We will see a few others of them with AWS as we go. Like SQS and a few others. But, uh, these are these are the big five in each of the three providers. And, uh, yeah, you don't necessarily need to commit it to memory. You can always look it up, but it's good for you to have heard it. And we will have some experience coming up. So for the next two days we're going to be working with Azure and GCP. And you may be wondering which components we're going to work with. And the answer is the components we're going to work with are the ones in the middle. And we're going to be working with Azure Container Apps and Google Cloud Run. And these are you probably guessed this already from the introduction I gave before. We're going to make a container, a Docker container. And then we're going to deploy it to Azure and deploy it to GCP. And typically building a container and deploying it is the simplest use case. It's what we used in week one with the healthcare app. Uh, when we when we put it on App Runner, it's the simplest to package up and do it. And I wanted to give you a quick example with these other two. It's also the one which is, once you've done it once, it's most consistent to do it across the different providers. Another good reason to pick this. And typically it's what I recommend people start with first. If you've got an Agentic app that you're looking to deploy and you're wondering, how should I go about doing it? What's the first way to do it? Simplest way. Put it in a Docker container, make sure that works locally, and then deploy the container to the cloud using App Runner, ACA or Cloud Run. Pretty similar between the three, and it just tends to work with that little exception about Apple Silicon, which can catch you off guard about making sure you build the Docker container, right? As long as you do that, it should just work. And that's the beauty of Docker containers. And so that is what I have in store for you now. So look there's no time to waste. We're going to dive straight into the lab. I've gone back to the production repo. The repo we began in. And you should to open this up. There's a week three folder on the left. Open the preview of the single file inside it, the readme. And this gives us our first instructions. And that is quite simply that we're going to move to a different repo. We're going to move to a repo called Cyber Git. Uh, one of my repos. You could also just go to GitHub to my page and find cyber. And in the previous weeks, we've always built a new repo from scratch and copied and pasted into it. This time we're going to take a preexisting repo, because this week is all about productionizing. And so I'm going to give you like prebuilt projects that I'll talk through. And then together we will deploy them to production. So please bring up a terminal window. And when that terminal comes up it typically is in the production directory, the directory for this project. And we don't want to be there. We want to be in the parent directory one up. We want to be looking at all of your projects your projects project's directory or whatever similar directory structure you have. And it's in here that we want to type this git clone command exactly as it is here, so that we clone this repo into our project's directory. So copy that, paste it in here, run that command to clone that repo. And then once you've done that in cursor you can go to the file menu and do new window. It pops up like this. You then want to open a project open project. You go into your projects and then you find cyber. There it is. And you open cyber just by pressing open like this. And up comes cyber. Here it is. You see, I was already in there, so it was already open. Uh, and we are now in the cyber repo. Let's get rid of the terminal. So you see it nice and clean and fresh. This is going to be our playground for the next couple of days. And let's get started now with building the cyber project.

</details>
