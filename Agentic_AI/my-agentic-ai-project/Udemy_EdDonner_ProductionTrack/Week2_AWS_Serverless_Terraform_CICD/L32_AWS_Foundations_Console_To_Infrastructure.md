# L32 — AWS Foundations for Production AI: From Console to Infrastructure

> **Week 2 · Day 1** · ⏱️ ~13 min

---

## 🎯 TL;DR

Week 2 ki kickoff: Week 1 ka recap (Next.js + FastAPI + Docker + App Runner), AWS root user se billing check + infra cleanup (App Runner + ECR delete), aur is hafte ka roadmap — Lambda, Bedrock, S3, API Gateway, CloudFront, Route 53, phir **Terraform (IaC)** aur **GitHub Actions (CI/CD)**.

---

## 🗣️ Hinglish Explanation

### Week 1 ka recap — kya seekha tha

Ed sleeves rolled up rakhne ko bolta hai — "huge week ahead, absolutely gigantic". Pehle Week 1 ka quick recap:

- **Front end app** banaya tha — ek **React** app **Next.js** framework ke saath (TypeScript variant, **pages router**), styling ke liye **Tailwind**. (Heads up: is hafte hum **app router** use karenge, pages router nahi.)
- **Back end app** banaya tha **FastAPI** se. **Clerk** use kiya tha user authentication + subscription plans ke liye (jo **Stripe** se hook ho sakte the). *Is hafte Clerk use nahi karenge* — future mein comeback ho sakta hai.
- Sab kuch ek **Docker container** mein package kiya, locally test kiya — front end aur back end ek hi container mein chal rahe the.
- Phir wo container cloud par deploy kiya **AWS App Runner** se. Clerk ke comparison mein yeh thoda "sweat" tha, par yeh **core AWS learning** hai.
- Beech mein hum ne ek **LLM call** kiya aur results **stream** karke wapas bheje — toh bhale 80% kaam platform engineering laga, ek **AI angle** bhi tha.

Ed assignment yaad dilata hai: app ko beef up karo (medical practice mein commercially useful banao), PR karo community contributions mein, ya LinkedIn par post karo (Ed ko tag karo toh wo amplify karega).

### Root user se billing check karna

Kuch bhi naya karne se pehle Ed bolta hai: **AWS mein root user ke roop mein wapas jao** aur costs check karo — koi surprise toh nahi.

> **Root user vs IAM user (background):** AWS account banate waqt jo email/account se sign up karte ho wo **root user** hai — uske paas unlimited, unrestricted access hota hai (billing band karna, account close karna, sab kuch). Best practice: daily kaam ke liye root user use **mat** karo; uske jagah ek **IAM user** banao limited permissions ke saath (Week 1 mein hum ne banaya tha). Par jab **verify** karna ho ki sab kuch band hai ya nahi, tab root user theek hai kyunki wo restricted nahi hota — tum sab kuch dekh sakte ho.

Flow:
1. `aws.amazon.com` → **Sign in to Console** → **Sign in as root user** button.
2. Top-right par dekho — "AI engineer" (IAM user) nahi, balki tumhara **naam / root user name** dikhega → confirm ki root mein ho.
3. **Billing and Cost Management** search karo (ya link click karo).
4. Spend dekho. Ed ne **$105** spend kiye (course prep mein, cheapest services figure out karte hue) — *students ko ideally $0 ya bahut minimal aana chahiye* kyunki free introductory plan mil jaata hai. Ed ko nahi mila kyunki uska credit card existing accounts se linked tha.

### Infrastructure cleanup — App Runner aur ECR delete

Ab running services band karne hain (warna paisa lagega):

**App Runner services delete karo:**
1. Console mein **App Runner** search karo.
2. Running services dikhenge. (Ed ke paas "Alex / Researcher" naam ka tha — wo final project ka naam hai, ignore.) Do **consultation services** the.
3. Service kholo → **Actions** → **Delete**.
4. Confirmation field mein literally `delete` type karo → **Delete** press → "operation in progress".
5. Baaki sab App Runner services bhi delete karo taaki clean rahe.

> Agar tumhara koi service genuinely paisa kama raha hai, toh chhodd sakte ho — warna delete kar do.

**ECR repository delete karo (chhota cost):**

> **ECR = Elastic Container Registry** — Docker images store karne ki jagah AWS par (Docker Hub ka AWS equivalent). Week 1 mein hum ne apni container image yahan push ki thi.

1. Console mein **Container Registry / ECR** search karo.
2. `consultation-app` repository dikhega (deployment se) → select → **Delete**.
3. Cost minimal hai, par clean rakhna ho toh delete kar do.

> Ed bolta hai: is hafte aage hum ek tarika dekhenge **saare resources** ek jagah dekhne ka, taaki bilkul pakka ho ki kya pay kar rahe ho. Abhi manually iss liye kar rahe hain taaki "feel" aaye.

### 25% milestone — ab tak kya skills aayi

Ed self-congratulatory moment leta hai (course ka 25% ho gaya):

- **Entrepreneur hat:** Vercel par AI web app deploy kar sakte ho — authentication + subscription ke saath, front end + back end.
- **Enterprise hat:** Foundational AWS knowledge — root user + IAM user setup + permissions, containers via **App Runner**, image on **ECR**, aur AWS console mein comfortable ho gaye (account ID, username, numbers dekhna).

### Is hafte ka roadmap (Week 2 preview)

Hum ek **AI app AWS par build + deploy** karenge. Naye words/services:

- **Lambda** — serverless functions
- **Bedrock** — Amazon ka LLM wrapping service
- **S3** — Simple Storage Service (cloud storage)
- **API Gateway** — APIs manage karne ke liye
- **CloudFront** — CDN (content delivery network)
- **Route 53** — DNS service

(Inko detail mein next lectures mein cover karenge.)

**Pehle manual, phir automated:** Ed bolta hai hum pehle sab kuch **AWS console + thode AWS CLI commands** se setup karenge — yeh laborious hai aur practice mein log aise nahi karte. Kyunki kuch saal pehle **Terraform** aa gaya:

> **Terraform / Infrastructure as Code (IaC):** Terraform ek tool hai jisse tum apni infrastructure ko **code** mein describe karte ho (declarative `.tf` files mein) — "mujhe yeh S3 bucket chahiye, yeh Lambda chahiye, yeh API Gateway chahiye" — phir Terraform khud AWS mein wo sab bana deta hai, bina console mein gaye. Environments ek command se up/down kar sakte ho. Yeh reproducible, version-controlled aur team-friendly hota hai.

**Toh seedha Terraform kyun nahi shuru kiya?** Kyunki agar sirf Terraform use karo, toh tumhe samajh hi nahi aata ki actually AWS mein kya ban raha hai — building blocks samajh nahi aate, aur kuch galat ho jaaye toh console mein ja ke debug karna nahi aata. Iss liye pehle manual ("traditional") way, phir Terraform.

> **AWS CDK note:** AWS ka apna IaC tool hai **CDK (Cloud Development Kit)** — par yeh AWS-only (proprietary) hai. Ed Terraform sikhayega kyunki wo **industry standard** hai aur AWS + **GCP** + **Azure** sabke liye chalta hai (multi-cloud — Week 3 mein kaam aayega). CDK par cover nahi karega, par bola: ek LLM aaram se Terraform ↔ CDK convert kar deta hai, toh CDK prefer karte ho toh kar sakte ho.

**CI/CD intro:** Hum **GitHub Actions** bhi use karenge — yeh **CI/CD (Continuous Integration / Continuous Deployment)** ke liye hai.

> **CI/CD (background):** Continuous Integration = har code change ko automatically build/test karna; Continuous Deployment = test pass hone par automatically production mein deploy karna. GitHub Actions GitHub repo ke andar `.github/workflows/*.yml` files se yeh automation chalata hai — push karo, pipeline khud build + deploy kar de.

Ed bolta hai yeh sab **core expertise** hai startup se enterprise tak — uske apne startup mein Terraform + cloud deployment use hota hai.

### Entrepreneur ke liye — kya AWS zaroori hai?

Agar tumhe Vercel pasand aaya aur soch rahe ho "Vercel kaafi hai, AWS kyun?" — Ed ka honest jawab: **shayad early stage par Vercel hi enough hai.** Par AWS samajhna phir bhi essential hai:
- Vercel yeh sab **behind the scenes** kar raha hai — proper cloud deployment kaise kaam karta hai yeh samajhna important hai.
- App grow karega toh ek point aayega jab Vercel **outgrow** ho jaayega — tab proper AWS/GCP/Azure deployment chahiye hoga.
- Architecture, pros/cons samajhna se pata chalega **kab** Vercel se proper cloud par move karna hai.

Entrepreneurs chahein toh sirf videos dekh sakte hain (saari deployments khud na karein), par yeh essential learning hai.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Root user** | AWS account ka unrestricted owner — sirf billing/sensitive ops aur verification ke liye use karo |
| **IAM user** | Limited-permission user, daily kaam ke liye (best practice) |
| **App Runner** | Container-as-a-Service — image do, AWS deploy kar de (Week 1 mein use kiya) |
| **ECR** | Elastic Container Registry — Docker images AWS par store karne ki jagah |
| **Billing & Cost Management** | AWS spend dekhne/manage karne ka console section |
| **Terraform / IaC** | Infrastructure ko code se describe + provision karne ka tool (multi-cloud) |
| **AWS CDK** | AWS ka proprietary IaC tool (AWS-only) — Ed Terraform prefer karta hai |
| **GitHub Actions** | CI/CD automation GitHub ke andar — push par auto build+deploy |
| **CI/CD** | Continuous Integration / Deployment — automated build, test, deploy pipeline |
| **Lambda / Bedrock / S3 / API Gateway / CloudFront / Route 53** | Is hafte ke main AWS services (functions, LLM, storage, API mgmt, CDN, DNS) |

---

## 💼 Backend Dev Ke Liye Note

Python backend dev ke liye yeh lecture **paradigm transition** set karta hai — managed PaaS (Vercel/App Runner) se proper cloud primitives ki taraf. Cleanup workflow (App Runner + ECR delete) yaad dilata hai ki cloud mein **orphaned resources = recurring cost** — production discipline mein teardown utna hi important hai jitna setup. Sabse bada takeaway: Ed deliberately **pehle manual console, phir Terraform** karwata hai — yeh exactly wahi mental model hai jo ek senior backend engineer ko chahiye: IaC tabhi powerful hai jab tumhe pata ho ki underlying resource (security group, IAM role, bucket policy) actually kya ban raha hai. Terraform ko `kubectl apply`/`docker compose up` jaisa declarative layer samjho — abstraction tabhi safe hai jab niche ka layer dikhta ho. CI/CD intro (GitHub Actions) backend devs ke `make deploy` / Jenkins pipeline ka modern, git-native version hai.

---

## ✅ Takeaway

- **Week 2 = AWS deep dive** — Lambda, Bedrock, S3, API Gateway, CloudFront, Route 53, phir Terraform + GitHub Actions
- Naya kaam shuru karne se pehle **root user se billing check + infra cleanup** (App Runner delete, ECR repo delete) — orphaned resources paisa khaate hain
- Ed ka teaching order intentional hai: **pehle manual console/CLI, phir Terraform** — taaki building blocks samajh aayen aur debugging aaye
- **Terraform > CDK** is course mein, kyunki multi-cloud (AWS/GCP/Azure) + industry standard
- Entrepreneurs ke liye bhi AWS samajhna essential — Vercel ek din outgrow hoga, tab proper cloud chahiye

---

<details>
<summary>📜 Full Transcript (English)</summary>

Well, do you have your sleeves rolled up? I hope you have your sleeves rolled up. I'm wearing a polo shirt, so my sleeves are naturally rolled up, but I hope you've got your sleeves firmly rolled up. We've got a huge week ahead. Absolutely gigantic. I've got so much to show you. No time to waste. Let's get straight into it. This week is all about AWS, and I can tell you it's going to be a bit gruelling, but overall it's going to be extremely fun. We have a lot to build and you're going to by the end of the week, you're going to be like a pro at AWS. I wouldn't say you're necessarily yet an expert. We'll wait until the end of the whole four weeks before you get to that point. But you're going to be a pro, you're going to know this stuff, and it's going to be great. And what you see here is a preview of everything I have in store for you this week, including building a product using bedrock, Terraform, GitHub actions so much. But first, we need to look back at what happened last week and the new skills that you've acquired as a result. We built a front end app. It was a react app. We used Next.js, the application framework. It was the TypeScript variant of it. We used the pages router. This week we're going to be using the app router. And we use tailwind for styling. We built a backend app using the fabulous fast API. We use Clark for user authentication and for building subscription plans that could also be hooked up to stripe. We are not going to be using that this week, but it might make a comeback in the future. Hang on in there and we package this into a Docker container. And for those new to Docker, we covered some of the basics and we tested it locally. And it worked front end and back end running in one container. And then we took that container and we deployed it to the cloud. We used AWS App Runner. And after how easy it was to do that with Clark, it was a it was it was a little bit of a sweat to go through all of the steps. But this is core AWS learning. And at the same time as doing all this, we should take note that we did in fact call an LM and stream back results. So whilst it felt like 80% of what we were doing is kind of core platform engineering work. There was an AI angle to it too, and I gave you an assignment to beef up the app to make it have more functionality, more capabilities, something that could actually be commercially useful in a medical practice. And I'm really hoping you did that. Something maybe you've shared a link to it and did a PR to community contributions so that other students can see what you've done. Maybe you posted about it on LinkedIn, in which case, if you tagged me, then I will come in and check it out, weigh in and make sure I amplify your success. That is what I'm here for. But before we do anything else, let's take a moment to go back into AWS as the root user and check that we've got the right kind of costs that we were expecting and there's no surprises. And then we will go and clean up the infrastructure. Let's go do that now. And so here I am at AWS Amazon.com screen I'm going to sign in to console. I already signed in, but you need to go in and press that sign in as root user button. So you're going in. And when you look on the top right, you don't see AI engineer, you see your name or your root user name. We're in as me and we're going to go billing and cost management. We should we should search for it here. But you can also click on the on the link. Just there. There it is billing and cost management. Up it comes. And let's check how much money we have spent. Now you'll notice that I have spent $105, which is uh, yes, it was very much unnecessary and you will not have done. I very much hope that you will, in fact, have spent zero at this point, because you almost certainly were able to sign up with free introductory plan. I couldn't, because I've been using AWS for a while. Uh, even though I actually set up a new account for this for this course. But it knew that I had existing accounts, I think probably because my, my credit card, uh, so I wasn't eligible. Hopefully you were. But even if you weren't, you should have spent a tiny amount at this point. I've spent so much because of all my time preparing for this course and figuring out what are the cheapest services that we could use. Uh, so hopefully you're looking at very good numbers here indeed. Um, and, uh, the next thing that we're going to do is just check that, uh, the, the various services that we've built are no longer running. Let's go and do that now. So I'm staying logged in as the root user because whilst you try and do as little as possible as the root user, if you're looking to check that everything has been brought down or something like that, you don't want to be restricted in any way. You want to be absolutely sure you're seeing everything. And I'm going to start by searching for App Runner, which was of course, the AWS app runner was the component that we used last time. Let's come in here and we can see that there are, for me, some things running. Uh, you can ignore. Alex. Researcher Alex is going to be the name of our final project, and you can see that I've already been playing around with what? What there is to build. So. So ignore that. But I have two consultation services, the original one I built and the second one I was doing while I was showing it to you. And so we need to now close these down. So let's go into one of them. Uh, and here we go. And then I'm going to go over to actions and I'm going to say delete. And it says to confirm deletion type delete in this field. And that's what I will do. And I will press delete. And it's saying operation in progress. And that will shortly delete that app runner. Of course you can feel free to keep it running if it's something that you're planning to make oodles of money off and you've built it up into something substantive. But otherwise the right thing to do is to delete it and do that to the other app service as well. You won't have to. If you have anything else, any other app runners running, then delete them so that this is nice and clean. And then I will see you back in a minute. But wait, before we go back to the slides, there is one other thing we might want to check. Uh, it's very, very small, but there is also a small cost for the space we're using up with the, uh, the Docker image that we put in ECR. Remember what ECR stands for, Elastic Container Registry where our container is. So if we go to the container registry. Here it is. We should find that in the container registry is indeed consultation app from our deployment can select it and press delete. I think we are talking about really really minimal costs here. But if you want to be, uh, clean about this, you should delete it. Later on this week, we'll look at a way to to see all of the resources you've got in Amazon, so you can be absolutely sure you know what you're paying for. This is we're just doing it this way for now so that you get a really good feel for it. Okay. And now back to the slides. So let's take a moment to be self-congratulatory. And we're 25% of the way through the course. What what skills have you already picked up at this point when you're wearing your your entrepreneurs hat? Remember I said that this this course applies to entrepreneurs and enterprise people and everyone in between. As an entrepreneur, you're now in the position where you can deploy an AI web app using Vercel with authentication subscription, you now know how to build your own app and deploy it, building an app with front end and back end and so on. That is a big box ticked. If you're an enterprise person working in a larger company, you have a lot of the foundational AWS knowledge you understand about AI, how to set up the root user and IAM user and give it permissions. And you also know about containers using AWS App Runner. Putting your container on ECR Elastic Container Registry. Uh, there's a lot of these acronyms to learn. So so you've got a lot of this foundational knowledge. And also you've worked with the AWS console quite a bit. You've got somewhat familiar with clicking around, looking at your your AWS account ID and your username and looking at these numbers and things like that. So I've got an enormous week in store for you this week. It's really going to be a lot of, of uh, we're going to cover so much of, of AWS. We're going to be building and deploying an AI app on AWS, on Amazon Web Services. And these are some of the words that we're going to be doing. We'll be using Lambda, bedrock, S3, API gateway, CloudFront, route 53, and some other things too. And there's going to be a lot of these words for you to take on board. So so be be mentally prepared for that. We're going to be doing this. We're going to be setting everything up through the AWS console and through a few commands, through some AWS commands. And that's going to be very laborious. And it's actually not the way people normally do it in practice, because several years ago, this amazing thing called Terraform came along, which was a way that you could write code to describe your infrastructure as known as infrastructure as code. And you can use Terraform to describe the AWS resources you want to build, and then just go and make them be built without going into the console at all. So you might wonder, why didn't we just do that from the beginning? And the reason is because if you just use Terraform and some people just go straight into Terraform, then you, you never really appreciate what's actually being built in AWS. And you don't understand the different building blocks. And if something were to go awry, you wouldn't know how to go into the console and find it and understand it. So I honestly think it's incredibly important to have built your first couple of apps, the sort of the standard, traditional way of setting them up in the screens and a bit of command line. And then we moved to Terraform, and you see how fabulous Terraform is and how it makes everything just happen so easily. And you can bring up environments and bring them down and up and down and yeah, just just for a few clicks rather than endless clicking around consoles. Uh, now AWS has its own version of Terraform called CDK, which is an AWS proprietary way of doing it, just for AWS. And I'm not planning to cover that on this course, because if you if you use CDK, then that will only work for Amazon. And we're going to use Terraform because that's more of an industry standard and because we'll be able to use it for AWS and also for GCP and Azure. And it's very widely used in the community. But everything we cover is possible with CDK and An LLM will easily convert between Terraform scripts and CDK. So if you'd rather be doing CDK, you absolutely can. But I do encourage Terraform. We'll also be using GitHub actions, which is a way of doing what's called CI, CD, continuous integration and deployment. And that's going to be really great too. So tons of things to cover. And this is all core expertise for an enterprise role or even a even a startup. At my startup we use Terraform and we deploy to the cloud with, with a lot of this stuff. So, so from startup to medium sized company to enterprise, this is the way it works for a scalable, robust, uh, industrial strength cloud application. But what about for an entrepreneur? If you're the entrepreneur you loved building with Vercel in week one and you might be thinking to yourself, okay, but Vercel kind of works for me. But do I need to do this? Why? Why don't I stick with vassal and look the. In all honesty, the answer might be maybe vassal is all you need, particularly at the early stage of starting a new business and building a product for the first time for sale can be perfect for you. But I'd argue that it's still essential for you to learn about how AWS works, how a proper cloud deployment actually works in practice. Vercel is doing all of this behind the scenes. It just does it all for you. And understanding. Understanding this, this scalable framework is something that will position you well for success later. As your app takes off, there's going to become a point when you will outgrow Vercel, and it's going to be time to deploy your product properly. And understanding the frameworks, understanding how cloud deployments work and the architecture and the pros and cons sets you up perfectly for that. And it helps you know when is the right moment to move from a vassal kind of thing into a proper AWS or GCP or Azure deployment. So I'd say entrepreneurs are welcome to. This is equally important for you. You could choose maybe not to do all the deployments yourself just to watch the videos, but this is going to be essential learning for you to.

</details>
