# L83 — Building AI Research Agents with MCP Servers and Data Pipelines

> **Week 3 · Day 5** · ⏱️ ~5 min

---

## 🎯 TL;DR

Week 3 Day 5 — Alex ka data pipeline poora karenge ek **researcher agent** banaake (OpenAI Agents SDK + **Playwright MCP server**) jo internet se research karke `ingest` Lambda ko data bhejega. Saath mein **data engineering** ka intro: ETL, Spark/Beam, aur medallion (bronze/silver/gold) architecture. Agent ek container mein chalega (App Runner-style), Terraform se deploy hoga, aur ek scheduler har 2 ghante mein use trigger karega.

---

## 🗣️ Hinglish Explanation

### Recap: Alex ab tak

Yeh **Week 3, Day 5** hai — Ed ke words mein *"tisra purple day in a row, full of AI"*. Alex = financial planner jo ek din SaaS product ban sakta hai. Ab tak banaya:

1. **SageMaker endpoint** — text → vectors (`all-MiniLM-L6-v2`, 384-dim)
2. **ingest Lambda** — text ko us endpoint se vectorize karke **S3 Vectors** mein store karta hai

Aaj banayenge: **researcher** naam ka agent jo actual **research** karega — internet browse karke, data gather karke, phir `ingest` Lambda ko call karke us data ko pipeline mein daalega. Yeh **data pipeline ka source** complete karta hai.

### Aaj ka tech stack

- **OpenAI Agents SDK** — agent banane ka framework (tools, instructions, agent loop). Ed ke Agentic course wale isse jaante hain.
- **Playwright MCP server** — **MCP (Model Context Protocol)** ek standard hai jisse LLM/agents external tools se connect hote hain. **Playwright** ek browser-automation library hai; **Playwright MCP server** agent ko **internet browse karne** ki capability deta hai (pages kholna, content padhna). Ed bolta hai yeh wahi MCP hai jo course wale "fondly" yaad karte hain.
- **Container + App Runner-style deployment** — agent ko ek **Docker container** mein wrap karke deploy karenge. Yeh wahi pattern hai jo is week ke Day 1-2 mein use hua (Azure Container Apps, GCP Cloud Run) — container ke andar MCP server spawn hota hai. Container locally build karenge, phir deploy.
- **Frontier model in Bedrock** — agent ki "brain" ke roop mein AWS **Bedrock** ka ek frontier model (foundation model managed service).
- **Terraform** — deployment automate karne ke liye.

### Data engineering ka intro (Ed ka aside)

Ed ek topic chhoo ke nikalta hai — **data engineering** — bolte hue ki yeh "surface scratch" hai (poora discipline / course series ho sakta hai). Core concepts:

**1. Data engineering kya hai** — data pipes banane ka discipline jo **bulletproof** ho aur **scale** kare.

**2. ETL — Extract, Transform, Load:**

- **Extract** — source se data nikaalo
- **Transform** — use target representation mein map/normalize karo
- **Load** — final jagah par daalo jahan models use kar saken

**3. Scalable data processing frameworks:**

- **Apache Spark** aur **Apache Beam** — distributed compute use karke massive datasets par ETL karte hain
- Repeatable, fail hone par **retry**, often **real-time** (streaming) ya **batch mode**

**4. Medallion architecture** — enterprise-grade data architecture jismein data 3 versions mein store hota hai:

| Layer | Matlab |
|---|---|
| **Bronze** | Raw source data, jaisa aaya waisa (untouched) |
| **Silver** | Normalized/mapped/transformed — consistent format |
| **Gold** | Final, consumption-ready versions (models/queries ke liye taiyaar) |

Yeh **staging-area approach** real enterprise-scale data engineering ka example hai.

Ed connect karta hai: hamare pipes **relatively simple** hain — agent = data **source**, ingest Lambda = **transform** (vectorize), S3 Vectors = **load/store**. Par tum imagine kar sakte ho: alag-alag Lambda functions ek doosre ko hand-over karte, cleansing + bronze→silver→gold staging karte, phir final DB. Ed data engineers ko Udemy Q&A mein contribute karne ko bulata hai.

```
[researcher agent]      →  SOURCE   (data gather karta hai)
        │
        ▼
[ingest Lambda]         →  TRANSFORM (text → 384-dim vector)
        │
        ▼
[S3 Vectors]            →  LOAD / STORE
```

### Aaj ka full architecture

Pichli baar wali simplified architecture par ingest function (SageMaker call + S3 Vectors store) **top** par tha — aaj usse upar wala part build karenge:

1. **Scheduler** — har **2 ghante** mein wake up hota hai (background job / cron-style trigger)
2. Scheduler ek **Lambda function** call karta hai
3. Vo Lambda **researcher** (App Runner container mein chal raha) ko kick off karta hai
4. **researcher** (App Runner mein) ek **Bedrock frontier model** use karta hai (reasoning/brain)
5. researcher ke paas **Playwright MCP server** hai (container ke andar) — internet research
6. researcher gather kiya hua data **`ingest` Lambda** ko call karke pipeline mein daal deta hai

```
[Scheduler]  (har 2 ghante)
     │ triggers
     ▼
[Lambda]  (kicks off researcher)
     │
     ▼
[researcher in App Runner container]
   ├─ Bedrock frontier model   (reasoning)
   └─ Playwright MCP server     (internet research)
     │ calls
     ▼
[ingest Lambda]  →  SageMaker (vectorize)  →  S3 Vectors (store)
```

Sab kuch ek **container** ke andar banega: hum locally container build karenge, phir deploy karenge, aur **Terraform** se yeh sab wire hoga. Agla step: lab — chalo build karte hain.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **researcher agent** | OpenAI Agents SDK se bana agent jo internet research karke ingest Lambda ko data deta hai |
| **OpenAI Agents SDK** | Agent framework (tools, instructions, agent loop) |
| **Playwright MCP server** | MCP server jo agent ko browser-automation/internet-browsing capability deta hai |
| **Bedrock frontier model** | AWS Bedrock ka foundation model — researcher ka "brain" |
| **App Runner container** | Agent + MCP server ek Docker container mein; week ke Day 1-2 wala same pattern |
| **Scheduler (har 2 ghante)** | Cron-style trigger jo Lambda ke through researcher ko kick off karta hai |
| **ETL** | Extract → Transform → Load (data pipeline ka core flow) |
| **Spark / Beam** | Distributed compute frameworks for large-scale ETL (real-time/batch) |
| **Medallion (bronze/silver/gold)** | Raw → normalized → consumption-ready; enterprise staging architecture |

---

## 💼 Backend Dev Ke Liye Note

Yeh lecture backend dev ko **event-driven / scheduled pipeline** architecture dikhata hai — vahi pattern jo tum cron jobs, Celery beat, ya AWS EventBridge se banate ho. Flow ko deconstruct karo: **scheduler (trigger) → Lambda (orchestrator) → long-running worker (researcher container) → downstream service (ingest Lambda)**. Note karo ki **kyun** researcher Lambda mein nahi balki **App Runner container** mein hai — Lambda ka ~15 min execution limit aur cold-start constraints ek agent loop + browser automation (Playwright, jo poora Chromium chalata hai) ke liye fit nahi; isliye long-running container chahiye, aur Lambda sirf **trigger/orchestrator** ka role nibhata hai. Yeh "right compute for the right job" decision production design ka core hai. Data-engineering side: **ETL** aur **medallion (bronze/silver/gold)** patterns tumhare data pipelines mein directly applicable hain — raw landing zone (bronze) ko kabhi mutate mat karo, transformations alag staged layers mein rakho taaki reproducibility aur debugging easy rahe. Aur **MCP** ko ek standardized "tool interface" ki tarah dekho — bilkul jaise tum apne services ke beech ek well-defined API contract rakhte ho, MCP agent aur tools ke beech vahi standard contract hai.

---

## ✅ Takeaway

- Day 5 ka goal: **researcher agent** (OpenAI Agents SDK + **Playwright MCP** + **Bedrock** model) jo internet research karke **ingest** Lambda ko feed karta hai — data pipeline ka **source** complete
- Agent ek **App Runner container** mein chalega (Lambda nahi, kyunki long-running + browser automation chahiye); week ke Day 1-2 wala same container+MCP pattern
- **Scheduler har 2 ghante** → Lambda → researcher container → ingest Lambda → SageMaker → S3 Vectors
- **Data engineering** intro: **ETL** (extract/transform/load), **Spark/Beam** (distributed processing), **medallion** (bronze/silver/gold staging)
- Sab kuch **Terraform** se deploy hoga; agla step lab mein container build karna

---

<details>
<summary>📜 Full Transcript (English)</summary>

Well, I don't understand where all the time has gone. How can we already be at day five of week three? Well, we're at a crucial moment. We've got tons to do today. It is our third purple day in a row full of AI. We are completing the data pipeline side of our Alex Capstone project, and this time we're going to be using an agent. We're using OpenAI agents SDK, and we're going to be having it have an MCP server. Let's get into it. And like you need a reminder of what Alex is. You know well that Alex is our financial planner. That can be a SaaS product one day. And what we built so far, we built a SageMaker endpoint that can take text and turn it into vectors. And we built an ingest lambda function, lambda function called ingest that can vectorize text using that endpoint and store it in S3 vectors. And what we're going to do today is create an agent called researcher that's able to carry out some research. It's going to use OpenAI agents SDK, as I say, and MCP server to with playwright to to browse the internet, do some research and then call our ingest lambda function. And the way we're going to do it is similar to the way that we had MCP servers on days one and two of this week when when we built things in Azure and GCP, we used the container. We used their equivalent of App Runner uh, to have uh, something which could spawn an MCP server inside that container. And we're going to use the same approach today and say a few words about data engineering. It's another topic that I'm really only scratching the surface of. Data engineering itself could be an entire course or a series of courses, as could front end, as could Docker, as could so many things that we touch on Terraform, for sure. Uh, so what is data engineering? Well, it's really a whole discipline around building data pipes that, that are, that are bulletproof and that can scale. Uh, and it's probably a lot more than that. Data engineer is probably saying, but it's also, uh, so, so some of the things it involves is what's known as ETL, extract, transform and load, which is about really bringing a data source, mapping it to being in a target representation and then loading it into the the the the place where models will be able to use it. Uh, it's also about using many of the scalable data processing frameworks that you hear about. So Spark and Beam are some of them. You may have heard of that allow you to make use of distributed compute to to do things like ETL, massive data sets very quickly and in a way that can be repeated and the things that fail will be retried and so on. Uh, often real time as data flows in, it goes through these frameworks and gets transformed, or some of them run in batch mode. And then another thing which which data engineers might work on is known as the medallion architecture. This is an example of a real sort of enterprise grade data architecture, where you bring in data and you transform it and store it in three different versions of it. Bronze is the kind of source data as it came in in its raw form. Silver is after you've normalized it and mapped it, transformed it into a consistent format right, for your systems. And then gold is the final versions in data stores that are ready to be consumed. So this kind of staging area approach is an example of a real enterprise scale data engineering architecture. So this gives you a sort of a slight sense of data engineering. The pipes that we're building are relatively straightforward. We've got an agent that is a sort of source of data. We've got the the ingest that's then responsible for vectorizing it, which is a bit of a transform. And then we are storing that in S3 vectors. But you can imagine you could have these different lambda functions handing over to each other and having like a, like a pipeline of different steps in which the data is cleansed and perhaps brought through this kind of bronze, silver, gold staging before it's put in the final database, ready for our model. So that gives you just just a feel for data engineering. But by all means, do some more research. If this interests you and you'd like to know more about it. And if you are a data engineer and you've got lots more to say, then by all means add to the Q&A on Udemy and share anything else that you consider part of the of the data engineering profession. And then just to bring you back to the architecture we built last time, this is the simplified architecture of what we're doing here. The ingest function we built that cause SageMaker and stores in the vectors. It's that part at the top there that I just brought to the surface, which is what we'll be working on today. We're actually going to have the scheduler, something that wakes up every two hours and it is going to kick off. It's actually going to call the lambda function. That is going to kick off. Our researcher in App Runner. And our researcher in App Runner will use a frontier model in bedrock, which it's going to use to then call our ingest function. So this is how it's all going to fit together. That researcher we're going to use OpenAI agents SDK. It's going to have an MCP server that's going to be the playwright MCP server that people on my course will remember fondly. That's going to be running all within a container. We will build the container locally and then deploy it, and we'll use Terraform to do it. And that's enough chit chat. Let's let's go to the lab. Let's go and build this.

</details>
