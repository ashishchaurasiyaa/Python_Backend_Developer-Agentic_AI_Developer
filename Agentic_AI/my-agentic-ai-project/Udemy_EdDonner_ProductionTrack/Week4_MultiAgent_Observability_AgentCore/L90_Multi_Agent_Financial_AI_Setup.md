# L90 — Building Multi-Agent Financial AI: Database Architecture & AWS Setup

> **Week 4 · Day 1** · ⏱️ ~9 min

---

## 🎯 TL;DR

Capstone **Alex** (AI financial planner SaaS) wapas — is week multi-agent architecture banegi: **planner + 4 workers (tagger, reporter, charter, retirement)**. Sab agents alag **Lambda functions** honge, sab **Bedrock** use karenge, database **Aurora Serverless v2** hoga, aur ek naya piece — **SQS queue** — front end se planner tak requests bhejega.

---

## 🗣️ Hinglish Explanation

### Alex wapas aa gaya

**Alex** capstone project Week 3 Day 3 par shuru hua tha, aur ab Week 4 mein continue ho raha hai. Yeh ek **SaaS subscription platform** hai — ek AI financial planner jahaan users apne **account details, stocks, brokerage accounts** enter karte hain aur predictions paate hain — jaise **concentration risk** (portfolio ek hi cheez mein zyada concentrated toh nahi?) aur **retirement planning**.

Ed ek confession deta hai: wo apne hi rule (L89 wala "start simple") follow **nahi** karega. Wo seedha **multi-agent architecture** se start karega. Tumhe **leap of faith** lena padega — maan lo Ed ne pehle 1 call try kiya tha aur paaya ki multi-agent zyada effective hai.

### Week 3 mein kya bana tha (recap)

Pichle week humne **research flow** banaya tha:
- Ek **research agent**
- **Data ingest pipelines** jo web search (SMTP server ke through) se data pull karte hain
- Us data ko **vectors** mein convert karke **S3 Vectors** mein store karte hain
- Yeh hamari **research capability** thi, **Bedrock + SageMaker** use karke
- Ek **scheduler** har kuch ghanto mein yeh spin up karta tha (AWS console mein dikhega; cost bachane ke liye band bhi kar sakte the)

### Is week ka plan (5 din)

- **Day 1 (aaj)**: database side build karo
- **Day 2**: 5 agents jo collaborate karke financial planner banenge
- **Day 3**: app ka front end (mostly) + ek API layer
- **Day 4**: enterprise-grade / production-grade — security, resiliency, scalability, aur importantly **observability**

### Multi-agent architecture: 5 agents

Total **5 agents** — 1 planner + 4 workers. Har ek ki **distinct commercial functionality** hai, taaki har agent **separately build, test, evaluate** ho sake (yeh achha rule of thumb hai — decoupled deployment).

| Agent | Kaam |
|---|---|
| **Planner** | Orchestrator — baaki 4 agents ke beech activities coordinate karta hai |
| **Tagger** | Ek instrument (stock) leta hai aur uska **geographic distribution + asset class** figure out karta hai — equities / fixed income / commodities. Result database mein daalta hai |
| **Reporter** | Main financial planning agent — portfolio ka **report** banata hai, diversification risks detail mein dekhta hai |
| **Charter** | "Bit of fun" — portfolio ko alag-alag tareekon se depict karne wale **charts/graphics** generate karta hai |
| **Retirement** | Alag team member jaise — **retirement prospects** par focus, kya tum saalon baad ke liye sahi plan kar rahe ho |

### Red flag: agents ko zyada anthropomorphize mat karo

Ed ek important warning deta hai. Wo khud is trap mein gir raha hai — "yeh hamari **agent team** hai, yeh team member retirement planner hai." Yeh sound karta hai sahi, par **usually a trap** hai.

Hamesha grounded raho: **yeh sab LLM calls hain.** Jo matter karta hai wo hai us LLM call ka **context** — system prompt, information, aur context jo tum equip karte ho task carry out karne ke liye.

Best agentic results paane ke liye: socho ki **context kaise organize** kar rahe ho taaki har task best perform kare, aur aggregate mein business problem best solve ho. Aksar yeh human-like agents (jaise "retirement") mein translate ho jaata hai — **par start business problem se karo, human-team analogy se nahi.**

- **Sahi tareeka**: 1 LLM call se start. Agar retirement info weak/off-base lage, toh **measure** karo, phir usse alag LLM call mein separate karo with explicit context + examples → retirement analysis improve hoga.
- **Galat tareeka**: pehle hi keh do "mere multi-agent team mein ek retirement person hai, isliye retirement agent banao" — human-like thinking se.

*"Act as a data scientist first"* — business problem par measured way mein kaam karo.

### Deployment architecture

Ab actual deployment kaisa dikhega:

- Sab **5 agents = alag Lambda serverless functions**. (Common pattern: agents ya toh **Lambda** ya **App Runner** hote hain — App Runner tab jab MCP server spawn karna ho, jo yahaan nahi.)
- Sab agents **Bedrock** use karenge frontier model calls ke liye
- Database: **Aurora Serverless v2** (agle lecture mein detail)

### Supporting infrastructure

Mostly familiar (Week 2 jaisa), par **SQS naya** hai:

```
[Next.js front end] → static site build
        ↓
   [S3 bucket] → [CloudFront distribution] → world ko serve
        ↓ (API calls)
   [API Gateway]
        ↓
   [Backend API = Lambda]
        ↓ (request submit)
   [SQS queue]  ← NAYA piece
        ↓
   [Planner agent (Lambda)] → orchestrates 4 workers → Aurora
```

Flow step-by-step:
1. **Next.js front end** se ek **static site** generate hoti hai
2. Static site **S3 bucket** mein jaati hai
3. **CloudFront distribution** usse poori duniya mein push karta hai (yeh front end hai)
4. Front end **API Gateway** ke through API calls karta hai
5. API Gateway **backend API** (ek aur Lambda serverless function) ko hit karta hai
6. Backend API requests ko **planner** tak submit karta hai — naye **SQS (queuing system)** ke through

Aur bahut AWS infra jo diagram mein nahi dikhaya wo bhi "along for the ride" aata hai — **API Gateway** (jaante ho), aur **Secrets Manager** (shayad nahi jaante — secrets securely store karne ka tareeka). Yeh ek high-level diagram hai jisse "lay of the land" mil jaaye — agle din yeh sab build hoga.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Alex** | Capstone — AI financial planner SaaS, subscription platform |
| **Planner agent** | Orchestrator jo 4 worker agents coordinate karta hai |
| **Tagger / Reporter / Charter / Retirement** | 4 workers — asset tagging / portfolio report / charts / retirement planning |
| **Anthropomorphize trap** | Agents ko human team maan lena; sahi: yeh LLM calls hain, context matter karta hai |
| **Lambda for agents** | Har agent ek serverless function (alternative: App Runner) |
| **Aurora Serverless v2** | Scalable managed relational DB jo agents use karenge |
| **SQS** | Naya queuing system — backend API se planner tak requests bhejta hai |
| **Secrets Manager** | AWS service secrets securely store karne ke liye |
| **CloudFront** | CDN jo S3 ki static site globally distribute karta hai |

---

## 💼 Backend Dev Ke Liye Note

Yeh lecture ek classic **microservices + event-driven architecture** blueprint hai jise tum pehchaan loge. Har agent = ek **stateless microservice** (Lambda), single responsibility (tagger/reporter/charter/retirement) — bilkul **bounded context per service** wala domain-driven design. Planner = **orchestrator/saga coordinator**.

Sabse important backend insight — **SQS ka introduction**. Ed front end → backend API → planner ke beech ek **message queue** daal raha hai. Yeh **synchronous request ko async decouple** karta hai: agentic jobs lambe chalte hain (multiple LLM calls), toh HTTP request ko block nahi karte — backend API queue par message daal ke turant return karta hai, planner background mein consume karta hai. Yeh wahi pattern hai jo tum Celery/RabbitMQ/Kafka ke saath karte ho — **fire-and-forget + worker pool**. Aurora Serverless v2 = managed RDS jo idle par scale-down ho jaata hai (serverless billing), toh tumhe connection-pooling/sizing ki chinta kam.

Ed ka **"don't anthropomorphize"** warning practically yeh hai: agents ko **prompt/context boundaries** se decompose karo, na ki "yeh kaam human kaun karta hai" se — yaani service boundaries **data flow + evaluability** se decide karo, organizational chart se nahi.

---

## ✅ Takeaway

- **Alex multi-agent** = 1 planner + 4 workers (tagger, reporter, charter, retirement), har ek alag **Lambda**, sab **Bedrock** use karte
- Agents ko **decoupled** rakho taaki independently build/test/evaluate ho sakein
- **Anthropomorphize mat karo** — yeh LLM calls hain; context engineering matter karti hai, human-team analogy nahi
- Deployment: Next.js → S3 → CloudFront front end; API Gateway → backend Lambda → **SQS** → planner → Aurora
- **SQS** is week ka naya building block; **Secrets Manager** bhi "along for the ride"

---

<details>
<summary>📜 Full Transcript (English)</summary>

And now at this point, I am thrilled to bring it back. Alex, the financial planner, our capstone project that we began on week three, day three, and we're going to continue it this week. And we will be building a multi-agent architecture. And I'm not going to be following my own rules. I'm not going to be able I'm not going to be starting simple and then building out more agents as we go. We're just going to go with a multi-agent architecture. And you'll have to to to take a leap of faith and imagine that I have, in fact, tried it with one call and discovered that this is a more effective approach. So what is Alex? Again, it is, of course, a SaaS application, a subscription platform, which will allow us to to let people have a AI financial planner that they'll have access to, where they can enter in their their account details, their stock, their brokerage accounts and get predictions about, uh, things like concentration risks and talk about their retirement plans and the like, an AI based financial planner. And last week we built the research flow of this a research agent, and we built data ingest pipes that can pull in data from searching on the web using an SMTP server, and then turn it into vectors, use S3 vectors, um, and giving us our research capability. And hopefully that has been running. And every couple of hours it's been it's been spinning up. You should be able to see it in the AWS console if you have a look. Um, but of course you could also brought it down if you didn't want to spend that cost. But but either way, we got that built. What we're going to do this week is build out our main agentic flow for the product itself. On day one, which is today, we're going to build the database side of it. Then tomorrow in day two, we're going to build out five different agents that will collaborate to be the financial planner. On day three, we're going to build out the app, the front end of it mostly, but also like an API layer as well. And on day four, we're going to talk about making it enterprise grade production grade, which is going to be things like security, Resiliency, scalability, and importantly, observability. All of that is to come. And before we cover what we're going to build this week, let me remind you of what we built last week. This is what it looked like. Remember this? I hope the, uh, the scheduler uh, that then called researcher called ingest pipes, put it in S3. We used bedrock and SageMaker. So what are we going to do this week? Well, to start with we're going to have a multi-agent architecture. And this is what it's going to look like. We are indeed going to have a planner agent, an orchestrator that is responsible for coordinating activities across four agents that we'll talk to. So for a total of five agents and they are called the tagger, the reporter, the charter and the retirement. And I've organized them so that each one has distinct commercial functionality, so that in theory, you could build each one separately, you could have it tested and evaluated separately, work on the prompts and the context separately. And this is always a good rule of thumb. You want to try and organize your agents so that you can evaluate their performance independently from each other so that you could you could build them and deploy them somewhat in a somewhat decoupled way. So planner, as I say, is the one that does. The orchestration tagger is an agent that has quite specific functionality that it's able to take an instrument, a stock, and it's able to figure out what is its geographic distribution. Is it is it representing equities or fixed income or commodities. So what what kind of different asset classes does it cover for people that know this finance stuff? It's the kind of thing that a financial planner cares about. Uh, and, uh, yeah, that the tagger will do all of that and put it in the database. The reporter is the main, uh, the main agent that is able to do financial planning. It builds a report of your portfolio, looking in detail at the different things like diversification risks. The charter is is a bit of fun, really. The charter is going to be an independent agent that is there to create graphics depicting your portfolio in different ways. So it generates charts. And then retirement is a separate agent that you can think of as a separate team member that's focusing on your retirement prospects. Are you planning correctly for, for uh, for years out there, uh, when it's time for you to retire, based on on all of the AI that you put in production? Uh, and it's planning for that. So that is the, the the agent orchestra, uh, the way that we are coordinating different LM calls to solve this business problem. And this is a moment to point out one other red flag that I often have when talking about agent architectures with, with with students and with with with team members, which is when I notice when people overly anthropomorphize, uh, agents, which is a trap that I'm sort of falling into here. I'm saying things like, this is our agent team, and we have a team member that is the retirement planner. And it's easy to do that because you're thinking in terms of agents. And it sounds right that you'd have different agents with with different human like responsibilities, but it's usually a trap because you should always start by by keeping in mind. Stay grounded on the fact that these are LM calls. These are LM calls, and what matters is the context of that LM call. The way that the system prompt the the way that you the information you're giving it and the context that you're equipping it with in order to carry out its task and to get the best results from an agentic system, you want to be thinking about how you're organizing your context so that you get the best performance from each task that you need to carry out, so that in aggregate, you can solve the business problem in the best possible way. And often that will translate to having human like agents like retirement. But start from the point of view of the business problem you're trying to solve, the commercial problem and how you will get, how you will get the best performance and start, as I said before, with with one LM call with one agent. And if you're finding that the retirement information is, is is is weak and is somewhat off base, that might be a moment to try and measure that and then separate that out to a different LM call, providing it with more explicit context and examples so that your retirement analysis improves. So that would be an example of the right way to go about doing this. The wrong way is to start by saying, all right, my team, my multi-agent architecture team for financial planning includes someone that's focused on retirement. Therefore, I should have a retirement agent that is trying to to think of it in a human like way. And it's very tempting, but I would urge you not to do it that way. Act as a data scientist first and foremost, work on the business problem you're solving in a measured way. And if that ends up being quite similar to having a team that's almost like a human team, then so be it. But start from the data science and from evaluating a problem to be solved. So this is our agent architecture. Now let's look at the deployment architecture of how this will actually get deployed. Well all of these agents will be different lambda serverless functions. It's a common pattern. It's common for agents to either be Lambda or App Runner. If they need to do something like spawn an MCP server, we won't be for these. They will all be lambda serverless functions, and all of them will make use of bedrock for making frontier model calls. And we will use a database called Aurora serverless v2. And I will introduce that database in a moment. And in addition to this, we're going to need some more infrastructure as well to be able to interact with it. And here is that infrastructure. It looks like this. It's something which mostly you're familiar with. The SQS piece is new. We're going to have a front end, which again, as we did in week two, seems like an age ago. It's going to be a website, a static website generated from an XJS front end. We're going to generate a static site. We're going to put that in an S3 bucket. And then we're going to make that. We're going to do a CloudFront distribution so that it's pushed out to the world. And that will be our front end. And that is going to be able to make API calls through API gateway, of course, To a back end API, which will be another Lambda service. A serverless function. So we'll have a backend API. And that backend API is going to be able to submit requests to our planner. And it's going to do that through a new type of AWS infrastructure. We'll look at the queuing system SQS. And that's going to be one of the building blocks for us this week. And of course, there's a lot of AWS infrastructure that I'm not even showing here that kind of comes along for the ride. Like, you know about API gateway. That of course is going to feature here. And you also, we actually probably don't know about Secrets Manager that will be using as a secure way to store secrets. And there's a bunch of other stuff too that's going to, as I say, come along for the ride. So this is more of a of a high level diagram to give you the lay of the land. And do take a moment to look at this and take this in, because we're going to be building all this stuff. And for it to really, really land for you, it's going to be useful to have a good sense of what it is that we're going to be building. So take a moment, take this in, and then we're going to be ready to get going. But just before we do, I want to talk to you about databases.

</details>
