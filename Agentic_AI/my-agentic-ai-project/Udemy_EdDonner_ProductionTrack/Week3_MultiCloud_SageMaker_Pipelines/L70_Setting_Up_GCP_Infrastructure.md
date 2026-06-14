# L70 — Setting Up GCP Infrastructure for Production AI Agent Deployment

> **Week 3 · Day 2** · ⏱️ ~10 min

---

## 🎯 TL;DR

Week 3 Day 2 ki shuruaat: wahi cyber-security agent ab **GCP (Google Cloud Platform)** par deploy karenge. Ye lecture GCP foundation set up karti hai — cloud services ka GCP equivalent (Cloud Run = container), GCP free trial ($300), uski **5-level hierarchy** (Account → Org → Billing → Project → Resources), naya **Cyber Analyzer project**, billing link, aur **budgets/alerts**.

---

## 🗣️ Hinglish Explanation

### Day 2 ka plan: same project, naya cloud

Week 3 Day 2 — Day 1 ka continuation, par topic switch: ab **GCP (Google Cloud Platform)**. Same kaam jaisa kal: cyber security project ko deploy karna, apne MCP server ke saath, par is baar GCP par.

Ed ka prediction (famous last words 😄): aaj **Day 1 se quick** hoga, kyunki groundwork ho chuka — container ready hai aur chal raha hai, ab bas **deploy** karna hai.

Day 2 ke do parts: (1) **GCP setup** (yeh lecture + agla), (2) actually deploy karna. Project ke ingredients:
- **Cloud engineering**: GCP deployment (GitHub Actions nahi, par tum extra ke roop mein add kar sakte ho)
- **Cyber analyst project** (kal wala, ab familiar)
- **AI**: OpenAI Agents SDK + MCP server (Cyber skills ke liye) + observability ke liye Traces

### Recap slide: 5 types of cloud services, ab GCP mein

Cloud services ke **paanch types** (Week 2 se familiar), teeno clouds mein mapping:

| # | Type | AWS | Azure | **GCP** |
|---|---|---|---|---|
| 1 | Traditional server | EC2 | Virtual Machines | **GCE** (Google Compute Engine) |
| 2 | Platform (PaaS) | Beanstalk / App Runner | App Service | **App Engine** (Google App Engine) |
| 3 | **Container** | ECS | **ACA** (Azure Container Apps) | **Cloud Run** ⭐ |
| 4 | Container orchestration | EKS | AKS | **GKE** (Google Kubernetes Engine) |
| 5 | Serverless functions | Lambda | Azure Functions | **Cloud Functions** |

Aaj humara focus: **container deployment** — sabse simple starting point, aur **MCP servers ke saath particularly accha** kaam karta hai (kyunki wo container ke andar spawn ho jaate hain). Ek baar container locally chal jaye, to bas `terraform apply` se cloud par push.

> **GCP Cloud Run** = fully managed serverless container platform. Tum ek container image do, Cloud Run usse run karta hai, auto-scale karta hai (zero tak bhi scale-down), aur per-request pay karte ho. AWS App Runner / Azure Container Apps ka GCP equivalent.

### Step 1: GCP account banao (free trial)

`cloud.google.com` se shuru karo (Cursor mein week3 → Day 2 → part one instructions).

1. `cloud.google.com/free` kholo → free tier info screen
2. Ed ko **$300 free credit** offer mila (tumhe bhi same milna chahiye)
3. **Start Free** press → Google Cloud signup → kuch screens
4. **Credit card number** dena padta hai (sirf setup ke liye — charge nahi karega, ye batayega bhi)
5. Cues follow karke information do

> Ed ko ek dikkat hui: uske paas pehle se **Google Workspace account** tha (email ke liye), to usse kuch hoops jump karne pade aur LLM se madad leni padi. Tumhe shayad ye na ho (rare case hai) — fresh Google Cloud account easy hota hai.

Signup ke baad tum **console landing page** par aaoge: `console.cloud.google.com`.

### Step 2: GCP hierarchy samjho (Azure se zyada nested)

Console par jaane se pehle Ed GCP ki structure samjhata hai — Azure se milti-julti hai par **zyada deeply nested** aur thodi complicated. **5 levels:**

```
1. Google Account        ← tumhara Gmail / Google Workspace (top level)
2. Organization          ← (optional) company-wide Google setup mein
3. Billing Account       ← ek payment method
4. Project               ← billing account se associated (≈ Azure Resource Group)
5. Resources             ← project se associated (containers, etc.)
```

Parallels:
- **Project** ≈ Azure ka **Resource Group**
- **Billing Account** ≈ Azure ka **Subscription**

### Step 3: Naya project banao — "Cyber Analyzer"

Console par top par **project dropdown** se naya project banao:

1. Project dropdown click → projects list dikhti hai → **New Project** button (top)
2. Name do: **`Cyber Analyzer`**
3. Organization aur location default rakho
4. **Create** press

(Ed ke paas already `Cyber Analyzer` project hai, isliye dobara nahi banata.)

### Step 4: Project ko billing se associate karo

Naya project automatically billing se linked nahi hota — manually karna padta hai. **Project selected** rakho (top selector mein), phir:

1. Left **hamburger menu** (☰) → **Billing**
2. Yahan project ko ek **billing account** se associate karo (pehli baar thoda confusing)
3. Ed ke paas **"Free Trial Account"** naam ka billing account hai
4. On-screen prompts follow karke project → billing account link karo

Setup ke baad **My Billing Account** dikhega, clearly batayega ki tum **Free Trial Account** se linked ho. Ed ko **$300 credit, 62 din remaining** dikha (use spend karna padega 😄).

### Step 5: Budgets aur Alerts set up karo

GCP mein budgets banana **particularly easy** hai (Azure jaisa). Hamburger menu → **Billing** → apna billing account select karo.

**Overview tab** par turant dikhta hai ki $300 free trial mein se kitna spend hua.

Ab **Budgets & alerts** par jao:

1. **Create Budget** press
2. Name: `monthly budget 3` (Ed ne kai banaye the, tumhe `3` likhne ki zaroorat nahi)
3. **Time range**: Monthly
4. **Scope**: sab par apply — all projects, all services, all organizations
5. **Next** → **Amount**: specified amount **$10**
6. **Next** → **Email alert triggers** set karo:
   - **50% of actual** → email
   - **90% of actual** → email
   - **100% of actual** → email
   - **+ extra threshold: 100% of forecast** → email (jab forecast dikhaye ki itna spend hoga)
7. Emails jaaye **billing admins and users** ko
8. **Finish** press → budget create ho gaya

### Step 6: Verify — Account Management

Left side **Account Management** (billing management ke liye) par jao:
- `My First Project` aur **Cyber Analyzer** project dikhte hain (jo abhi setup kar rahe hain)
- Right side: **billing account administrator** — Ed ka email dikhta hai
- Yahan edit kar sakte ho — sahi email/contact ensure karne ke liye

Budgets set ho gaye → material spend hone par email aayega. Aur **Overview** par regularly aao costs check karne ke liye. Agle lecture mein **Google Cloud CLI** install karenge.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **GCP** | Google Cloud Platform — teesra major cloud (AWS, Azure ke baad) |
| **GCE (Compute Engine)** | GCP ka traditional server / VM service (≈ EC2) |
| **App Engine** | GCP ka PaaS (≈ Beanstalk / Azure App Service) |
| **Cloud Run** ⭐ | GCP ka managed serverless container platform (≈ App Runner / ACA) |
| **GKE** | Google Kubernetes Engine — container orchestration (≈ EKS / AKS) |
| **Cloud Functions** | GCP ka serverless functions (≈ Lambda / Azure Functions) |
| **Free trial ($300)** | GCP naya account credit, ~90 din valid |
| **GCP hierarchy** | Account → Organization → Billing Account → Project → Resources (5 levels) |
| **Project** | GCP resource grouping (≈ Azure Resource Group) |
| **Billing Account** | Ek payment method (≈ Azure Subscription) |
| **Billing association** | Project ko billing account se link karna (manual step) |
| **Budgets & alerts** | Spend threshold (50/90/100% actual + 100% forecast) par email |

---

## 💼 Backend Dev Ke Liye Note

Backend dev ke liye yeh lecture **cloud abstraction equivalence** ka mental model deta hai — teeno cloud providers same 5 service tiers offer karte hain, sirf naam alag (EC2/VM/GCE, ECS/ACA/Cloud Run, Lambda/Functions/Cloud Functions). Yeh portability ki neeyat hai: agar tum apni service ko **container** (lowest-common-denominator) ke roop mein package karte ho, to vendor lock-in minimize ho jaata hai — same image AWS App Runner, Azure Container Apps, ya GCP Cloud Run par chal sakta hai. GCP ki **5-level hierarchy** ko ek access/billing boundary tree ki tarah dekho: **Project** tumhara deployment unit + IAM/quota boundary hai (≈ AWS account-per-environment ya Azure resource group), aur **Billing Account** cost rollup point. Production mein typical pattern: ek org, multiple billing accounts (team/cost-center wise), har project ek environment (dev/staging/prod) — taaki blast radius aur cost dono isolated rahein. Aur **budgets/alerts** (50/90/100% actual + forecast) ek non-negotiable production guardrail hai — har naye cloud account par pehla kaam yahi hona chahiye, taaki ek runaway resource (jaise Ed ka mahine-bhar chala container) bill na uda de.

---

## ✅ Takeaway

- Teeno clouds same 5 service tiers dete hain — GCP mein container = **Cloud Run**, jo aaj ka deployment target hai
- GCP free trial **$300 credit** deta hai (card chahiye setup ke liye, charge nahi hota)
- GCP hierarchy 5-level hai: Account → Org → **Billing Account** → **Project** → Resources (Project ≈ RG, Billing ≈ Subscription)
- Naya project banane ke baad usse **billing account se manually associate** karna padta hai
- Har naye account par turant **budgets + alerts** set karo (50/90/100% actual + 100% forecast) — production cost guardrail

---

<details>
<summary>📜 Full Transcript (English)</summary>

Well, a fabulous welcome to week three, day two, which is a continuation of week three, day one before we change topics. But this time of course, we are talking about GCP, Google Cloud Platform, and we are going to be doing the same as before, the cyber security project that will be deploying on GCP with its own MCP server. And uh, that's hopefully, hopefully maybe famous last words. It's going to be a quicker day than yesterday because we've done all the groundwork already this week. Since we've got a container and it's running, this should just be a matter of deploying. Uh, so again, just to recap on this is this is day two of the two days. Uh, it's got something for everyone. We've got the, the the cloud engineering part of it, which for today is going to be about GCP deployment. It's we're not using GitHub actions, but by all means you could add that in as a little extra. We are going to be using our cyber analyst project that we work with yesterday that you now know well. And the AI again we're going to be using OpenAI agents SDK. We're going to be using an MCP server for the Cyberskills. And also as we saw yesterday, we can just take a look at the observability framework traces to be able to monitor our agent activity in production. All right. Let's get to it. It all starts with me again showing you the little slide about cloud services. You remember the five different types server traditional server infrastructure as a service, the platform container, container orchestration and then serverless. And of course AWS. That's EC2, Beanstalk, app runner, ECS or EKS and Lambda. And you're now somewhat familiar with Azure because we work with Azure Container Apps ACA. But also these are the other equivalent components services, virtual machines, App Service and then AKS and Azure Functions. So what's it like in GCP land. Here we go. So the server side is known as GCE or Google Compute Engine. The platform side is called Google App Engine or just App Engine. The, uh, the container piece is called Google Cloud Run. Cloud run. Kubernetes one. The container orchestration is called GKE, Google Kubernetes Engine. And then the the functions are called cloud functions. And as you probably remember well, what we're doing today is all about the container deployment, which is often the simplest way to start. It works particularly well when you have MCP servers because they can be spawned within the container. And it's really great for quick deployments because once you've got the container working locally, it should just be a matter of Terraform apply to push that out to the cloud. So with that let's go back to cursor and talk GCP. And so here we are in the cyber repo again in cursor. Hopefully you have that cloned and open. And we're going to expand the week three folder. And we're going now to day two, part one. There are only our two parts today setting up GCP and then actually going and running it. So again we're going to be going through much a similar process to Azure. We're going to set up an account if you don't already have a GCP account. And you can get a free trial hopefully by going to Google Cloud.google.com. That's where you begin all of this. And uh, this link Cloud.google.com might work for you. Let's go there now. So I'm going to go to that Cloud.google.com free. It comes up, uh, it gives you this, this sort of screen to give you information about their free tier. It's, uh, $300 of free credit is what it's showing me here. Hopefully you get the same deal. Uh, press start Free, and it's going to have you start by signing up to Google Cloud, and you'll then go through a few screens. And that includes needing to enter in a credit card number, I believe, just to set it up. Uh, but it won't charge you as it will inform you. And be sure to to give it the information you need and take the cues. Uh. I had a bit of difficulty when I signed up for this free account, because I had an existing Google Workspace account already, like for email that I was using, and so I had to jump through a couple of hoops and needed an LLM to help me. Hopefully that doesn't happen to you. I think that's that's a that's probably rare because of my specific setup. I think you'll find it'll be quite easy to sign up for a new Google Cloud account and get in, but once you've done so, you should arrive at a at like the console landing page, which is console.cloud.google.com. And that is where we will go next. So actually just before we go to Console.cloud.google.com, which is where you will have been redirected to, let me just take a moment to walk you through Gcp's structure. It's similar to Azure, but it is a bit more deeply nested. So it's important to understand the terminology. The different the different levels and GCP can be quite complicated. I gotta tell you. Uh, okay. So, uh, gcp's hierarchy has these, like five levels to it. The top is your Google account, which is like like your Gmail, your Google Workspace. Some people call it that. That is your Google account at the top. Then there is a potentially something called organization under that which you may have if you're if you're doing this as part of a of a company with, with a Google setup, then you have a billing account. And that is one particular payment method. And then there are projects associated with that billing account and resources associated with the projects. So in some ways project is quite similar to a resource group in Azure. And billing account uh is is obviously somewhat similar to a subscription. So there's definitely parallels here. Uh, and uh, there's a little bit more to it explained just there. So what we're now going to do is go to the console and go to the, uh, project drop down to create a new project, which is going to be Cyber Analyzer with everything else as default. Let's go do that now. So up here is the projects tab. You can see I already have a project called Cyber Analyzer of course because I already created it. But when you click on here it brings up the projects and there's a new project button at the top here. This is where you give it the name Cyber Analyzer, which you already saw there. Keep it in your organization and location and then press create to set that up. I won't do it again. I won't set up a second cyber analyzer. But that's of course what I did to get to this point. All right. Next up we have to associate billing with this project. So with the project selected in this project selector up here, you go to the hamburger menu on the left. And you choose billing. And this is where you associate the project with a billing account, which is a little bit confusing the first time you do it and you do it there. I already have a billing account called Free Trial Account. It has like a name and so on. But you as following the instructions here, uh, as you were prompted on that screen the first time you come in, it should be clear how you're prompted to link this, to link this project to this billing account, so that when you're set up, you then see, uh, my billing account here. And it's very clear that the billing account that you're set up to is your free trial account. Um, and, uh, so you should get to this point, which is I've got lots of zeros on it, which I like to see. Uh, and it shows that I have my $300 credit with now 62 days remaining on it, I better I better spend them. And, uh, you've got many of the, the familiar kinds of settings right here. But let's now set up some budgets. So setting up budgets is particularly easy in GCP. And it's going to be very easy for you because it's similar to Azure. So as I said we've gone to to the hamburger menu. We've gone to billing and we've selected the billing account which is the only billing account that we've got set up, which is the one that we did in associated with our project. And here it is. And at the overview tab, you get an immediate view on what you've spent. Towards in this case, our $300 free trial. I haven't spent very much of it, it seems. Uh, but this is where you go to keep a healthy eye on your costs. We're going to go to Budgets and alerts. And you can see here this is where you set up alerts. You should have budgets. You will have nothing here. But you will after you press Create Budget and we give it a name and we'll call it monthly budget three. But you don't need to call it three. It's just I've made a few of them. Uh, time range, we'll say monthly. Uh, we will apply it to everything. All projects, all services, all organizations. Next we press the next button to give it an amount. The amount that we'll give, we'll say it's a specified amount of $10. And it appears right there. Next. And now we can set up what triggers an email alert. We're going to say 50% of actual, 90% of actual and 100% of actual any of those situations. We want to get an email. We'll also add another threshold, which will be 100% of the forecast when our forecast is showing that we will spend that amount. Let's get an email there. Let's have that email billing admins and users and press finish to create that. We've just created that in there as well. And let's just check we have everything set up right on this left here. Come down to account management for your billing management. And here you can see that I've got a my first project and the cyber analyzer project that we're about to set up together. And if I come over here to the right, this is where I can see the the billing account administrator. It is indeed my email. Uh, and, uh, you can come on in here and edit this should you need to, to make absolutely sure you've got the right email address, the right contact. Your budgets are set up. You'll be able to be emailed if you ever spend anything material. And you can also always come to overview, as you should regularly, to keep a close eye on the costs associated with your account.

</details>
