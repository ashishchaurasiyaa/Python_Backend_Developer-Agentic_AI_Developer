# L33 — Cloud Deployment Architectures for Production AI Applications

> **Week 2 · Day 1** · ⏱️ ~8 min

---

## 🎯 TL;DR

Course ka "single most important topic" — cloud par deploy karne ke **5 main archetypes**: IaaS (traditional server), PaaS (platform), CaaS (container), Container Orchestration (Kubernetes), aur Serverless (functions) — har ek ka AWS equivalent (EC2, Beanstalk, App Runner, ECS/EKS, Lambda).

---

## 🗣️ Hinglish Explanation

Ed bolta hai yeh shayad poore course ka **single most important topic** hai — **cloud deployment architecture**. Aaj thodi theory + chhota lab; kal bada lab.

> **Terminology warning:** Cloud deployment ki terms (jaise "PaaS", "CaaS") log alag-alag contexts mein alag matlab mein use karte hain — ambiguous aur confusing hai. Ed sabse **common/typical** usage bata raha hai, par real life mein kabhi-kabhi pointed questions pooch ke samajhna padta hai ki banda kya keh raha hai.

5 main archetypes (simplest → most advanced):

### 1. IaaS — Infrastructure as a Service (Traditional Cloud Server)

Yeh sabse simple aur sabse purana tarika hai — "yahin se sab shuru hua".

- Tum cloud mein ek **computer / box rent** karte ho — ek server jo rent ke time tumhara hota hai.
- Tumhe **sab kuch khud setup karna padta hai**: OS choose karo, patches install karo, software install + configure karo, apne programs chalao.
- Remotely connect karke us server par jo chahe karo.

> **Background:** Pehle saare cloud deployments aise hote the — bunch of servers rent karo, ek par database install, doosre par app server, ek par cache, etc. Full control milta hai par maintenance burden bhi tumhara — OS updates, security patching, scaling sab manual.

**AWS offering: EC2** (Elastic Compute Cloud) — Amazon ki traditional compute, apna box.

### 2. PaaS — Platform as a Service

Tum sirf **code likhte ho** (business logic + functionality), baaki sab ek **platform handle karta hai** — wo tumhare code ko le ke internet par live kar deta hai.

- OS, server, scaling, SSL — sab platform ka kaam.
- Famous: **Heroku** ne is model ko popular banaya tha "back in the day".
- Sabse familiar example: **Vercel** — Week 1 mein hum ne `vercel.json` likha aur platform ne sab kar diya, ek URL de diya. Day 5 (manual AWS) ke comparison mein "pretty magical" tha.

**AWS offering: Beanstalk** (Elastic Beanstalk). *(Vercel AWS product nahi hai — Ed ne sirf isliye dikhaya kyunki tum use jaante ho.)*

### 3. CaaS — Container as a Service

Tum app ko ek **Docker image** mein package (containerize) karte ho, aur service baaki sab sambhaal leti hai — container ko internet par daal deti hai.

- Week 1 mein **AWS App Runner** se exactly yahi kiya tha.
- Common model hai.

> Note: kuch log "CaaS" aur "PaaS" ko alag contexts mein interchangeably use karte hain — par yeh sabse common meaning hai.

**AWS offering: App Runner** (jo hum ne use kiya).

### 4. Container Orchestration

Yeh ek **pro / advanced approach** hai — ek nahi, **bahut saare containers** manage karne ke liye jo aapas mein collaborate karte hain.

- Containers ke beech **messaging**, **scaling** manage karna, **monitor** karna, **restart** karna — yaani sab kuch **orchestrate** karna.
- Famous product: **Kubernetes** (extremely popular), jo yeh saari infrastructure cloud par chalata hai.
- Most advanced approach, large-scale companies ke liye. (Kuch log isse bhi "CaaS" bol dete hain — confusing.)

> **Course note:** Yeh course **Kubernetes cover nahi karega** — follow-on exercise ho sakta hai. Ed ke startup mein use hota hai, toh chhoti companies mein bhi use ho sakta hai, par mostly large-scale ke liye pro approach hai.

**AWS offerings (do hain):**
- **ECS** (Elastic Container Service) — Amazon ka apna orchestrator
- **EKS** (Elastic Kubernetes Service) — Kubernetes version
  - ⚠️ "EKS" sun ke **ECR** (Elastic Container **Registry**) yaad mat aana — wo image store karne ki jagah hai, alag cheez.

### 5. Serverless / Functions as a Service (FaaS)

"The hottest, the one everyone loves to talk about" — kuch saal pehle aaya, ab bahut bada ho gaya.

- Tum bahut **granular** ho jaate ho — sirf ek **particular function** likhte ho (jaise ek route, ya ek FastAPI handler).
- Wo function platform par upload hota hai aur **on-demand** chalta hai: jab koi web request aati hai jisko yeh function chahiye, ek server **spin up** hota hai, function run hota hai, phir server **shut down** ho jaata hai.
- Yeh **parallel** mein ho sakta hai, **scale** ho sakta hai.
- Agar koi request nahi → **kuch bhi nahi chalega → ek paisa nahi lagega**. Achanak bahut requests aayein → scale up karke handle kar leta hai.

**Do tarah ki flexibility:**
- **Scaling flexibility** — automatically scale up/down
- **Pricing flexibility** — sirf **used CPU** ka paisa (jab actually chal raha ho tabhi). "Start small, grow fast" companies ke liye super attractive.

Inka heavy use = **serverless architecture** kehlata hai (abhi "so hip").

**AWS offering: Lambda** — AWS ka function-in-the-cloud product.

> **Is course ka focus:** Hum mostly **Serverless functions (Lambda)** + **Container as a Service (App Runner)** use karenge — yahi do sabse zyada.

### Quick mapping recap (5 archetypes → AWS)

| Archetype | AWS |
|---|---|
| Traditional server (IaaS) | **EC2** |
| Platform (PaaS) | **Beanstalk** (Vercel non-AWS) |
| Container (CaaS) | **App Runner** |
| Container orchestration | **ECS** / **EKS** |
| Serverless functions (FaaS) | **Lambda** |

Ed bolta hai abhi acronyms memorize karne ki zaroorat nahi — "by the end you're going to be dreaming these things".

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **IaaS** | Raw server rent karo, sab khud setup karo — AWS EC2 |
| **PaaS** | Sirf code do, platform sab deploy kar de — Heroku/Vercel, AWS Beanstalk |
| **CaaS** | Docker image do, service deploy kar de — AWS App Runner |
| **Container Orchestration** | Bahut containers manage/scale/monitor — Kubernetes; AWS ECS/EKS |
| **Serverless / FaaS** | Ek function on-demand chale, idle par $0 — AWS Lambda |
| **EC2** | Elastic Compute Cloud — traditional VM/box |
| **Beanstalk** | AWS ka PaaS offering |
| **ECS vs EKS** | ECS = AWS native orchestrator; EKS = managed Kubernetes |
| **Pay-per-use** | Serverless ka USP — sirf actual CPU usage ka paisa |
| **Course focus** | Mostly Lambda (serverless) + App Runner (CaaS) |

---

## 💼 Backend Dev Ke Liye Note

Yeh lecture ek backend engineer ke liye **decision framework** hai — "kaunsi deployment model kab choose karein". Spectrum ko control vs convenience trade-off ke roop mein dekho: EC2 = max control + max ops burden; Lambda = min ops + constraints (cold starts, 15-min timeout, stateless, package size limits). Practical heuristic: long-running stateful workloads (DB, websocket server, background workers) → containers/orchestration; spiky/event-driven/bursty traffic with idle periods → serverless (kyunki idle par cost zero). Ek seasoned backend dev ke liye sabse load-bearing insight: **serverless ka pricing model architecture ko shape karta hai** — agar tumhara app mostly idle rehta hai (jaise ek chatbot jise occasional hits aati hain), Lambda dramatically sasta hai EC2/App Runner ke comparison mein jahan idle compute ka bhi paisa lagta hai. Iss week ka digital twin exactly yahi case hai. ECS vs EKS distinction bhi yaad rakho — agar tum already Kubernetes jaante ho toh EKS, warna ECS ka learning curve kam hai.

---

## ✅ Takeaway

- **5 deployment archetypes:** IaaS → PaaS → CaaS → Container Orchestration → Serverless (simple to advanced)
- AWS mapping yaad rakho: **EC2, Beanstalk, App Runner, ECS/EKS, Lambda**
- **Serverless (Lambda)** ka killer feature = pay-per-use, idle par $0, auto-scale — "start small grow fast" ke liye perfect
- Is course ka focus: **Lambda + App Runner**; Kubernetes (EKS) cover nahi hoga
- Terminology log alag matlab mein use karte hain — context se samjho (PaaS/CaaS/orchestration ka overlap hota hai)

---

<details>
<summary>📜 Full Transcript (English)</summary>

And now, perhaps for the single most important topic of the entire course, cloud deployment architecture, I'm going to be talking for a bit. There's going to be some theory today, then some lab today. Tomorrow will be the bigger lab. So there are a number of different ways that you can deploy software to the cloud. And it's ambiguous and it's confusing. And people use terms like pass in different situations to mean different things. So I'm going to tell you the most common and the most typical use of language. But be be aware of the fact that some people use these terms differently. So you may need to figure out what someone's talking about by asking a few pointed questions. But first and foremost, the simplest way that you can deploy to the cloud and the way we all started doing this, where it all came from, is what some people would call traditional cloud server. And it's also sometimes known as IaaS infrastructure as a service. And this is where you quite simply rent a computer in the cloud. You rent a box, you have access to a server, and you own that server while you're renting it. And that means you have to set up everything on that server. You have to choose the operating system that runs on it. You have to install patches on there, set up all the software and configure it, run your programs on it. But it's like you've got a server that you can remotely connect to and it's yours to run with. And back in the day, this is how we did all cloud deployments. We get a bunch of server compute. We'd set them all up. We'd install a database on one, we'd install an app server on another, and these would be servers running remotely in the cloud, on AWS or wherever. That's where it began. And next up is platform as a service or pass. And this is where you write some code to do your application, some business logic and some functionality, and then everything else is handled for you by a platform that's responsible for taking what you've done and dealing with everything else to put it online, live on the internet. And this was initially, I think, made most famous by Heroku back in the day, if you've heard of that. They were like the first people to really, uh, bring, bring the world to this model. And now it's very common. And you're most familiar with it because it is, of course, what Vercel is. Uh, this is exactly what we did last time. We wrote a bit of code. We wrote a vassal dot JSON file in day one, and it just dealt with everything else. It just put it up there on the internet and gave us a URL, and we were done compared with what we went through on day five. Uh, it was it was pretty magical. So that is pass. And then another thing that you've also got some experience with now is called container as a service or sometimes called CAS. And this is where you package up an app into a Docker image. So you've containerized it as they say, and then the service will take care of the rest. You made a container. It will then put that container on the internet. And that's what we did, of course, with AWS App Runner. And that is a common model. And I should say sometimes people do use CAS and pass in different contexts. But but this is the most common. Okay. And next up container orchestration. So this is something which is a pro uh, approach. Uh, and sometimes when people say CAS they're referring to this, it's confusing. But I would call it container orchestration. And that's probably what most people would say. This is where you want to manage not one container, but a large number of containers that all need to collaborate with each other in some way. There's some messaging they do between each other. You want to manage how they scale. You want to be able to monitor them. You want to be able to restart them. You want to be able to to orchestrate is the word, uh, everything that's going on with potentially many containers and doing that involves using typically a product like famously one called Kubernetes that's extremely popular, and running all of that infrastructure on the cloud. And this is known as container orchestration. And this is the most advanced approach and for large scale companies. And we will not be covering that on this course. If you want to use Kubernetes then that can be a follow on exercise for you. We do actually use it at my startup, so it can be used even at smaller companies. Um, and it is more of a, of a sort of pro approach for large scale applications. And then last of just of the five that we're going to cover, there are many more. But of the big five, last, definitely not least, in fact the hottest, the one that everyone loves to talk about is known as serverless architecture or serverless functions, sometimes called function as a service. Not so common, but you sometimes hear that and this the this this is the hot thing that came up a few years ago, but has just got bigger and bigger. And it's an idea where you get very granular as a developer. You just write one particular function that could be like like a route to call or a particular fast API server, and that function can be uploaded to to a platform, and it will be run on demand. When, when the outside world, when when a web request comes in that needs to use this function or in some other way, it needs to be called a server will be spun up and it will be run, and then the server will be shut down. And this can happen in parallel. It can be scaled. You can have none of them running at all, in which case you don't pay a penny, or if suddenly a whole bunch of requests come in, it could scale up and handle whatever demand you've got. So it's super flexible. It's flexible in terms of being able to scale effectively, and it's flexible in terms of pricing, because you only pay for the CPU that you use. You only pay when this thing is actually running and that makes it very attractive indeed, particularly for companies that want to be able to start small and grow fast. And generally making heavy use of these is known as a serverless architecture and is so hip at the moment. And that's definitely we're going to be using serverless functions a lot on this course, uh, along with uh, with containers as a service as well. Those will be the ones that we'll focus on more than any other. Uh, so that that gives you the lay of the land, the five main cloud deployment archetypes that you may come across. And then finally, just to layer on this diagram, what are the names of the AWS components for each? So for traditional cloud servers it's known as EC2. Now you don't need to memorize this though. We will cover some of these in a lot more. And by the end of it you're going to be dreaming these things. EC2 is the name of Amazon's, uh, Traditional compute where you can get your own compute box. I'm not gonna I'm not gonna tell you what the acronyms stand for yet. We will have plenty of time for that. Uh, the platform as a service pass. Amazon's offering there is known as Beanstalk. Of course, you already know Vercel and realize it's not an Amazon product. I put that on just because you know it. Well, uh, so, uh, Beanstalk is AWS is offering there for container as a service. We did this. As you know, this is app runner container orchestration. Amazon actually has two different offerings. One's called ECS and one's called X, which is the Kubernetes version of it. And you might say hang on, X sounds familiar. But no, you're thinking of ser, which would be the Elastic Container Registry. It just all rolls off the tongue, doesn't it? Uh, and then serverless functions, you've almost certainly heard of this already because it's so, so hot. Lambda is the name of AWS product for calling functions in the cloud.

</details>
