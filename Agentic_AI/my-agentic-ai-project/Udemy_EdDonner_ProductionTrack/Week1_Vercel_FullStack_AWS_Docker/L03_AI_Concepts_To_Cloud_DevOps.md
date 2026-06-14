# L03 — From AI Concepts to Cloud Deployment: Navigating the DevOps Landscape

> **Week 1 · Day 1** · ⏱️ ~6 min

---

## 🎯 TL;DR

Ed apna intro deta hai (Nebula.io CTO, ex-JPMorgan MD, Untapped founder) aur phir course ka **sabse bada expectation-reset**: AI-in-production ka **70-80% kaam DevOps/platform engineering hai**, AI concerns sirf ~20-30%. Course **T-shaped** hai — breadth sab providers ki, depth **AWS** mein.

---

## 🗣️ Hinglish Explanation

### Ed Donner kaun hai? (Credibility intro)

Repeat students ke liye Ed khud bolta hai *"put me on 2x"* — same intro, same jokes. Naye logon ke liye:

- **Abhi**: Co-founder & **CTO of Nebula.io** — AI startup (talent/recruitment AI space mein)
- **Pehle**: Career ka zyada hissa **JP Morgan** mein — wahan **MD (Managing Director)** bane, **~300 technologists ki team** lead ki
- **Journey**: London (origin — accent se pata chalta hai) → Tokyo (kuch great months) → **NYC** (ab wahan rehta hai)
- **Untapped**: Nebula se pehle ek aur AI startup founded ki — **acquired ho gayi** kuch saal pehle. Acquisition announcement **Times Square billboard** par aaya tha — Ed ka favorite flex (squint karo toh billboard mein khud Ed ke "few pixels" dikhte hain 😄). Aur funnily, Ed Times Square se ek block door hi rehta hai.
- **Hobby joke**: plane ke saamne photo — par Ed confess karta hai ki hand-eye coordination zero hai. *"LLM skills surpassed only by my complete inability to fly planes"* — agar cockpit mein Ed dikhe toh parachute dhoondo; agar LLM production course mein dikhe, toh sahi jagah ho.

**Backend dev ke liye yeh background kyon matter karta hai:** Ed sirf AI educator nahi — usne enterprise scale par (JPMorgan) aur startup scale par (2 companies) **dono taraf production systems** chalaye hain. Isi liye course "real world" oriented hai.

### THE BIG RESET: yeh course jitna AI lagta hai, utna hai nahi

Yeh lecture ka core message hai, dhyan se samjho. Yeh Ed ka **most requested course** hai (survey mein majority ne yahi manga). Par log ek **misconception** ke saath aate hain:

**Logon ki expectation:**
- ~80% deep AI concerns — agents deploy karna, agents ka aapas mein baat karna, agentic app productionization
- ~20% DevOps/cloud side work (AWS security, scaling components)

**Reality (Ed ke according):**
- **70-80% platform engineering / DevOps** — cloud providers configure karna, deployments set karna, infrastructure
- **20-30% AI concerns**

Ed ka killer observation, jo abhi Vercel exercise se prove hua: jo Python code tum deploy kar rahe ho, wo `"hello from production"` return kare ya **LLM ko call kare** — **deployment ke kaam mein koi khaas farak nahi padta**. Pipeline same hai: build config, routing, server, scaling, security. AI sirf payload hai.

### Toh "AI lens" kahan hai?

DevOps-heavy hone ka matlab yeh nahi ki AI gayab hai. Har component **AI-flavored** hoga:

| Generic DevOps | Is course mein (AI lens) |
|---|---|
| Koi bhi database | **Vector databases** (embeddings ke liye) |
| Koi bhi API | **Bedrock, SageMaker** — LLM APIs |
| Generic monitoring | **Observability for LLMs** (super important topic) |
| Generic services | **MCP servers** deploy karna (very hot area) |

Toh formula: **traditional cloud platform engineering (bulk) + AI-specific components (lens)**. Ed seedha bolta hai: *"you are signing up for a lot of DevOps over the next four weeks... and you better believe it. But that's quite interesting too."*

**Context ke liye** (standard industry gyaan): yeh baat industry mein bhi sach hai — "AI Engineer in production" roles ka major hissa hota hai IAM policies, container builds, CI/CD pipelines, cost monitoring, networking — model ke around ka **scaffolding**. Famous saying: *ML code is the smallest box in the ML system diagram* (Google ke "Hidden Technical Debt in ML Systems" paper ka idea). Ed wahi reality set kar raha hai.

### T-shaped course structure

Course **T-shape** follow karta hai — yeh skill-development ka classic model hai:

- **Horizontal bar (breadth)**: bahut saare providers aur tools touch karenge — **AWS, GCP, Azure**, **CI/CD, GitHub Actions**, multiple frameworks
- **Vertical bar (depth)**: ek stripe mein deep jaayenge — **AWS**

**AWS hi kyun?** Kyunki industry mein **sabse common cloud provider AWS hai**, aur Ed ka goal hai tumhe **industry ke liye best prep** dena. Par GCP/Azure ignore nahi honge — Ed parallels batata chalega (e.g. AWS Lambda ↔ GCP Cloud Functions ↔ Azure Functions type mapping), taaki skills transferable rahein.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Nebula.io** | Ed ki current AI startup (co-founder, CTO) |
| **JP Morgan MD** | Ed ka enterprise background — 300 technologists ki team lead ki |
| **Untapped** | Ed ki pehli AI startup — acquired (Times Square billboard moment) |
| **80/20 reality** | Production AI = ~70-80% DevOps/platform engineering, ~20-30% AI concerns |
| **Platform engineering** | Cloud providers configure karna, deployment pipelines, infra setup — course ka bulk |
| **AI lens** | Generic components ki jagah AI-flavored: vector DBs, Bedrock, SageMaker, MCP, observability |
| **Observability** | Production AI ka health/behavior monitor karna — course mein super important topic |
| **MCP servers** | Model Context Protocol servers — agents ko tools dene ka standard; hum deploy karenge |
| **T-shape** | Breadth (sab providers/tools) + Depth (AWS) ka learning model |
| **AWS focus** | Industry ka most common provider — isliye depth wahan |

---

## 💼 Backend Dev Ke Liye Note

Yeh lecture tumhare liye **best news** hai: production AI ka 70-80% DevOps hona ka matlab — tumhari existing backend skills (APIs, databases, deployment, networking, security) **direct head-start** hain. Jo "AI Engineer" role door lagta tha, wo actually **backend engineering + AI components** hai. Tumhe sirf delta seekhna hai: vector DBs (Postgres+pgvector jaisa socho), LLM APIs (ek aur external API dependency, bas latency/cost/streaming alag), observability for non-deterministic systems, aur MCP. Aur T-shape advice tumhare career par bhi apply hoti hai: **AWS mein deep jao** (job market ka default), GCP/Azure ke equivalents conceptually map karke rakho — interviews mein "transferable skills" wahi dikhti hain.

---

## ✅ Takeaway

- Production AI course ka **70-80% DevOps/platform engineering** hai — expectation abhi set kar lo, "AI kahan hai?" wala frustration nahi hoga
- Code `"hello"` return kare ya LLM call kare — **deployment pipeline same hai**; AI sirf payload hai
- AI lens har jagah rahega: **vector DBs, Bedrock, SageMaker, MCP servers, observability**
- Course **T-shaped** hai: breadth = AWS+GCP+Azure+CI/CD, depth = **AWS** (industry standard)
- Ed ka background = enterprise (JPMorgan, 300-person team) + startup (2 founded, 1 acquired) — dono perspectives course mein milengi

---

<details>
<summary>📜 Full Transcript (English)</summary>

and now let me introduce myself to convince you I'm actually qualified to talk to you about this with apologies to those that have heard my intro about three times before. It's going to be exactly the same. I'm going to make the same exact jokes. Put me on 2x. Zoom through this, please. But for those new to me, I'm Ed Donner. I am the co-founder, CTO of an AI startup called Nebula.io. Go check us out. Before that, most of my career, I was at JP Morgan where I ended up as an MD leading a team of about 300 technologists. I started out in London, which is where I'm from originally, as you can probably tell from my accent. I spent a few great months in Tokyo where I had an amazing time and then ended up in NYC, which is where I live now. Before Nebula, where I work now, I founded an AI startup called Untapped and it was acquired a few years ago. This here is the picture from Times Square of our acquisition being announced. This is a magical moment for me. In fact, if you squint, if you look really carefully and you squint, then what you can see right here, that is a picture of me. You don't need to take my word for it. You can look at the few pixels that are there. Okay, a bit of a leap of faith, but that is in fact me right there on the Times Square billboard at that moment. And the other reason I show you this photo, not just to show off at that moment, also because in fact, I do live right there. I live about one block from Times Square, that away. I live kind of behind that guitar. So I'm actually not in New York right now, I'm in London, but when I am in New York, you will find me right there looking out at you. So that's a little bit about me. And it's customary with these things to show some sort of personal picture of a hobby or something. So here's a picture of me in front of a plane that I just flew. And you might think that this is my attempt to tell you that this is something I'm very skilled at, but quite the contrary. My great skills when it comes to LLMs is only surpassed by my complete inability to do anything requiring hand-eye coordination. And so in fact, I'd suggest to you, if you're getting on a plane and you're going perhaps to a conference or perhaps on holiday, and you look in the cockpit and the flight deck, and you see that it's me standing and sitting there with the stick, the yoke there about to control your jet, then you want to be looking for a parachute very quickly. If however, you've turned up on a course to take a course about building and deploying LLMs, gen AI and agentic AI in production, then luckily you've come to the right place. That is in fact, my skill set. Let's get on with the course. So I just want to set your expectations about something that you might not be expecting. So a lot of people have asked for this course. It's by far the most requested topic for me. And I ran a survey and more than the majority asked for this course. But I think that people might be under a bit of a misconception. I think that when people think about deploying AI software to production, people are expecting a course which is say about 80% is going to be deep in the weeds of artificial intelligence concerns, what it takes to deploy agentic apps into production with agents connecting and talking and stuff. And they people I think are aware that there's going to be some DevOps work, some cloud deployment work and dealing with AWS security dealing with with scaling different componentry. And so people are expecting that that work as well in the mix. But I think the reality is a bit different from that. I think that the reality is more like this. Sure, there's some AI concerns, we're going to be talking about deploying AI. But I got to tell you, 80%, maybe 70% of what we're going to be doing is going to be about platform engineering, it's going to be DevOps, it's going to be configuring these different cloud providers, it's going to be as we just saw from Vercel, not that it was an AI app. But a lot of it was about configuring and setting up deployments in production. And whether the Python code you're deploying is saying, welcome to production, hello from production, or whether it's calling an LLM and doing something related to generative or agentic AI, turns out to not be a major factor in what you're doing. Now, for sure, throughout this course, we'll have the AI lens on, we won't be working with any old database in production, we'll be working with vector databases. And we won't be working with any old API, we'll be working with things like Bedrock and SageMaker, looking at LLM APIs. But nonetheless, it's important to take note that you are signing up for a lot of DevOps over the next four weeks. That's a big part of deploying AI to production. So as I say, there's going to be a lot of AI related concerns, we'll be talking about things like observability, which is super important. We'll be deploying MCP servers, which is a very hot area. But the bulk of what we're going to be doing is traditional cloud platform engineering, and you better believe it. But that's quite interesting, too. All right, one of the points to make about the course is that I've tried to structure this to follow what people talk of as the T shape, which is that we're going to cover a lot of breadth, we're going to cover lots of different providers, we're going to cover things like CICD and GitHub Actions. And we're going to go deep in one particular stripe, which is I've picked AWS. So whilst I do plan to give you exposure to all the major cloud providers, to AWS and to Google Cloud Platform, and to Microsoft Azure, we're going to be focusing most of our attention on Amazon AWS, because that is the most common of the providers used in industry, and I want to prep you best for industry. But I'll talk about the parallels between them as we go as well.

</details>
