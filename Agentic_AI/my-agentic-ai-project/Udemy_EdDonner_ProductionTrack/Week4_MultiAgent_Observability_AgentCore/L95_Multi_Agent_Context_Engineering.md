# L95 — Building Multi-Agent Financial AI Systems with Context Engineering

> **Week 4 · Day 2** · ⏱️ ~9 min

---

## 🎯 TL;DR

Capstone "Alex" (Agentic Learning Equities eXplainer) ke 5 agents banane ka din — planner, tagger, reporter, charter, retirement. Lekin code se pehle Ed ek game-changing mindset sikhata hai: **context engineering** — prompt engineering ki jagah ab asli skill yeh hai ki agent ko *kaunsa context, kaunse tools, sahi format mein, sahi time par* diya jaaye.

---

## 🗣️ Hinglish Explanation

### Aaj ka mission: 5 agents jo Alex ka dimaag hain

Yeh Week 4 ka Day 2 hai — capstone project ko "in anger" (yaani serious, full-throttle) banane ke 2 din mein se pehla. **Alex** = **A**gentic **L**earning **E**quities e**X**plainer, ek financial planner SaaS commercial application. Story recap:

- **Last week (W3)**: research agent banaya tha jo market data scrape kar ke S3 Vectors (vector store) mein insights likhta hai.
- **Kal (W4 Day 1)**: database schema banaya — relational model:
  - `User` has many `Account`s
  - `Account` has many `Position`s
  - har `Position` ek `Instrument` (stock/ETF/fund) mein hai
  - aur `Jobs` table — yeh "things that can run" hain jo saari agent activity orchestrate karte hain
- **Aaj (Day 2)**: 5 agents banayenge jo Alex ki Agentic AI platform ke dil hain.

### Architecture: blue squares vs yellow squares

Ed ek busy diagram dikhata hai. Important visual mental-model:

- **Blue squares = agents running on Lambda** — yeh aaj banenge. Paanch agents, har ek apne alag AWS Lambda serverless function par.
- **Yellow squares (top-left) = frontend + backend API** — yeh **kal** banenge.
- Sab kuch **Bedrock** (LLM inference) aur **Aurora Serverless** (kal banaya database) se connect hoga.
- Diagram "whole story" nahi hai — Secrets Manager, API Gateways jaise pieces abhi nahi dikhaye gaye, par big building blocks yahi hain.

> Quick AWS refresher backend dev ke liye: **Lambda** = serverless compute — tum code dete ho, AWS ek function har invocation par spin karta hai, idle mein kuch nahi chalta (pay-per-invoke). **Bedrock** = AWS ka managed LLM service (Nova, Claude, etc. ek hi API se). **Aurora Serverless** = managed Postgres/MySQL jo demand par auto-scale hota hai, idle mein scale-to-zero kar sakta hai. **S3 Vectors** = S3 par sasta vector storage RAG ke liye.

### THE big idea: Context Engineering

Code likhne se pehle Ed ek naya, powerful concept introduce karta hai jo pichhle kuch mahino mein bahut important ho gaya hai — **context engineering** — aur yahi Alex ki poori agent architecture ko drive karta hai.

**Origin story**: Andrej Karpathy ne tweet kiya "+1 for context engineering" — isi se yeh term famous hua. Google DeepMind ke engineer **Philipp Schmid** (DevRel team — developers ke saath AI research par kaam karte hain) ne ek seminal blog post likhi jo bahut viral hui.

### Prompt engineering → Context engineering ka journey

Ed Schmid ki blog padh ke samjhata hai:

1. **Ek saal pehle**: "prompt engineering" hot topic tha. Sab "prompt engineer" banna chahte the.
2. **Phir pata chala**: prompt engineering basically "please explain", "please think step by step" jaise phrases the. Kuch acronyms bhi aaye. Lekin akhir mein farak utna nahi pada — bas prompts clearly likho, kaafi hai.
3. **Naya skill = context engineering**. Jab tum Agentic systems ke saath kaam karte ho, jo matter karta hai wo hai: prompt mein **kya** daalte ho, aur khaaskar **kaunsa context** agent ko dete ho jisse wo apna task solve kare.

### Context kis-kis cheez se banta hai

Ek agent ka "context" in sab ka aggregate hai:

- **System prompt / instructions** — agent ki personality + rules.
- **Long-term memory** — basically **RAG**: vector data store mein search kar ke purani saved information laana. (Alex mein yeh researcher agent ne S3 Vectors mein likha hua hai.)
- **Short-term memory** — conversation history, ya different agent interactions ka record.
- **Tools** — jo tum agent ko equip karte ho (function calls, APIs, MCP servers).
- **Task / user prompt** — actual kaam jo karwana hai.

> Ed: "Yeh terms — long-term/short-term memory — mein zyada uljhna important nahi. Asli sawaal yeh hai: is LLM call ka **task kya hai**? Success **kaise measure** karoge? Aur **context + information + tooling** ko kaise shape karoge taaki achha outcome mile?"

### Schmid ka killer quote (aur Ed ka favorite)

> "Building agents is less about the code you write or the framework you use."

Ed ko yeh line bahut pasand hai — log baar baar poochte hain "kaunsa framework use karoon?" Answer: *it's not important.* "A cheap demo aur a magical agent ke beech ka farak — wo hai **context ki quality** jo tum provide karte ho."

**Schmid ki crisp definition** (yaad rakhne layak):

> "Context engineering is the discipline of designing and building dynamic systems that provide the right information and tools, in the right format, at the right time, to give an LLM everything it needs to accomplish a task."

Dhyaan do: **dynamic systems** — yeh ek static prompt nahi hai, yeh ek engineering discipline hai jo runtime par sahi cheez assemble karti hai.

### Bonus reading: Rise of Subagents

Ed ko Schmid ki ek aur fresh blog post mili — **"Rise of Subagents"**:

- Subagents = jab tumhare paas multi-agent system ho aur ek **single-loop agent** ko chhote agents se equip karte ho jo alag-alag tasks karte hain.
- Pros/cons hain — hamesha achha idea nahi hota.
- Schmid ki best line: *"Even with subagent architecture, reliability is still a challenge. Breaking a complex task into smaller subagent functions can make them simpler. But don't over-engineer a solution today that a simpler or better model can solve tomorrow."* — Sage advice (Ed bookmark karne ko bolta hai).

### Aur ek must-follow: Simon Willison

Ed recommend karta hai **Simon Willison** ka blog follow karne ke liye — "it's gold". Wo bhi context engineering ki taraf-daari karta hai aur Karpathy ka tweet quote karta hai. (In-joke: Simon famous hai LLMs se "pelican on a bicycle" drawings banwane ke liye 🐦🚲.)

### Aaj banne wale 5 agents (preview)

Guide "6_agents" folder ke andar `The AI Agent Orchestra` document mein hai. Paanch agents:

| Agent | Kaam |
|---|---|
| **Planner** | Orchestrator — decide karta hai kaunsa agent kab chalega |
| **Tagger** | Instruments ko region/asset-class se classify/tag karta hai |
| **Reporter** | Portfolio ka financial report likhta hai (market insights tool ke saath) |
| **Charter** | Portfolio visualizations ke liye JSON charts banata hai |
| **Retirement** | Retirement readiness advice + simulation deta hai |

Baaki ka din mostly lab mein hoga — agents ka code, fir local testing, fir Lambda deployment.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Alex** | Capstone — Agentic Learning Equities eXplainer, financial planner SaaS |
| **Context Engineering** | Naya core skill — right info + tools, right format, right time LLM ko dena |
| **Prompt vs Context Eng.** | Prompt = perfect instructions; Context = poora dynamic info/tool system |
| **Long-term memory** | RAG — vector store se relevant past info laana (Alex: S3 Vectors) |
| **Short-term memory** | Conversation / agent-interaction history |
| **Subagents** | Single-loop agent ko chhote task-specific agents se equip karna |
| **Blue squares** | Lambda par chalne wale 5 agents (aaj banayenge) |
| **Yellow squares** | Frontend + backend API (kal banayenge) |
| **Jobs (DB)** | Table jo agent activity orchestrate karne wale runs ko track karta hai |

---

## 💼 Backend Dev Ke Liye Note

Python backend dev ke liye context engineering ko ek **dependency-injection + request-pipeline** problem ki tarah socho. Jaise tum ek HTTP handler ke liye request context (auth, DB session, config, headers) assemble karte ho, waise hi yahan tum LLM call ke liye context assemble kar rahe ho: system prompt (config), RAG results (DB query), conversation history (session state), tools (service clients), aur user task (request body). "Framework matters nahi" wala point bilkul backend wisdom jaisa hai — Flask vs FastAPI vs Django se zyada matter karta hai ki tumhara *data flow aur boundaries* saaf hain. Aur "don't over-engineer for a problem a better model solves tomorrow" — yeh wahi YAGNI principle hai jo hum API design mein follow karte hain.

---

## ✅ Takeaway

- **Context engineering** = aaj ki asli AI-engineering skill — prompt engineering se aage; right info + tools + format + time
- Schmid ki definition rato: "dynamic systems that provide the right information and tools, in the right format, at the right time"
- Framework (OpenAI SDK vs CrewAI vs LangGraph) **matter nahi karta** — context ki quality cheap demo aur magical agent ka farak hai
- Alex ke **5 agents** aaj banenge — planner, tagger, reporter, charter, retirement — sab Lambda par (blue squares)
- Reading: Philipp Schmid (context eng + Rise of Subagents) aur Simon Willison ka blog bookmark karo

---

<details>
<summary>📜 Full Transcript (English)</summary>

Welcome everyone to an epic day. Let's get straight into it. Today is the first of our two days looking at the capstone project in anger, and we are going to be building ourselves some agents, a reminder of what it is we're building. We're building Alex, the name of our Agentic Learning Equities explainer, a financial planner, a SaaS commercial application. What we've done, you know, last week we did our research agent. And this week yesterday we built out our database with the schema that we went through. User has many accounts, account has many positions. And each position is in an instrument. And we also have jobs which are things that can run to to orchestrate all of our agent activity. So today is the day that we build out the five agents at the heart of our Agentic AI platform. And as a reminder of the architecture, this was the quite busy diagram that I showed you. And it's not the whole story. It's not showing things like the Secrets manager and API gateways and stuff like that. But this is showing the big building blocks. The blue squares are our agents running on Lambda. That's what we're going to be building this time. And then tomorrow we're going to build out the yellow squares on the top left, the front end and back end API part of the puzzle. But for right now, we're going to be building out those blue squares. And of course we're going to need to to connect it to bedrock and to the Aurora serverless database that we built yesterday. All right. With that, let's get to the lab right away. And most of today is going to be in the lab. And the first thing I'm going to do is talk a bit about something, a new concept that's become so important in the last couple of months, which is the idea of context engineering, which is fundamentally what drives our agent architecture. Let's go to cursor and let's talk about context engineering. And so here we are back in cursor back in the Alex folder I'm going to open up guides. I'm going to go to six agents and open the guide in preview mode. The AI Agent orchestra. The most exciting part of building Alex a multi-agent AI system five agents. We're going to be building a planner, tagger, uh, reporter, charter and retirement. As I explained last time in this diagram here shows them all together. The planner, the tagger, writer, reporter, charter and retirement. Um. And, uh, yeah, make sure that you cover all of the prerequisites. So before we get into this, I want to say a few words about this idea. Context engineering, which was originally made famous by a few people. But but the the amazing Andrej Karpathy tweeted plus one for context engineering which got got people most excited about it. But this is a a new way of thinking. Um, and a Google DeepMind engineer called Philip Schmidt wrote a seminal post about it that really did the rounds. Uh, he's part of their Devrel team, so he's responsible for, for, uh, working with developers on AI research. And let's read his blog post and learn a bit more about what it means, uh, to work on context engineering. So a year ago, the term of the moment was prompt engineering. And everyone wanted to be a prompt engineer. And that became old hat when people discovered that prompt engineering was just saying things like, please explain, please think step by step in your prompts. And there were various acronyms that came up. And then it turned out it didn't make all that much difference. And you just have to write prompts clearly. Uh, but the the new the new skill, as it says right here in this blog post, make it a little bit bigger. The new skill is not prompting it's context engineering. And what this this blog lays out is that what matters when you're working with Agentic systems is what you put in the prompt, or more and more particularly, what context you give the agent with which to solve its problem with which to carry out its task. And that can be a combination of a system prompt instructions. It can be what we call long term memory, which is basically Rag. It's giving it access to search in a vector data store and find information that that it's put there in the past, which of course we've done through the researcher agent. It's using tools. It's also using a short term memory which can be just the history of the conversation. or it can be something about the different agent interactions it's had. Uh, it can be a number of, of tools that you equip your agent to have, and then the task itself, the user prompt. Um, and so all of this together in aggregate, forms the context that an agent has. And you really want to think about organizing your agent activities to maximize the context that you're giving each agent to perform a task. And that's the right mindset to have in. And it's explained really very well here. And it's not important to get hung up on these different terms like long term memory and and short term memory. It's really comes back again to thinking about what what performance what is the task you're assigning to this LM call? How will you measure success and what's the best way to shape the the context, the information and the tooling to make sure that it's most likely to deliver an outcome that performs well, that meets your criteria. So it covers here are some examples. And and really let me just read this out. Uh, building agents is less about the code you write or the framework you use. I love that he says this because the number of people that ask me which framework should I use? And and this is so key. It's not important. The difference between a cheap demo and a magical agent is about the quality of the context you provide. And then he works through some examples and an example of a magical agent that's given the right kind of context and tools to be able to do well. Uh, and then this section from prompt to context engineering, uh, which, which really takes you on that journey of we're no longer just focusing on crafting the perfect set of instructions. This is a much broader kind of task. And let's read his definition. Context engineering is the discipline of designing and building dynamic systems that provides the right information and tools in the right format, at the right time, to give an LM everything it needs to accomplish a task that's finally put. And I would very much encourage you to to read through all of this. Uh, and uh, also you can, you can Google search to see some, some other posts about context engineering that have been popular. But this, this one I think is, is the gem. And so do study this carefully. And while we're here, I actually just noticed that today, uh, Phil posted another blog post that looks very interesting and and topical for us. Uh, for me, today is September the 15th. Uh, and, uh, Rise of Subagents is the name of this, this post. And he says there's increasing use of subagents to reliably handle specific user goals. So and he mentions Claude Cove, which we talked about a minute ago. Uh, and yeah. So Subagents is what some people are calling when you have a multi-agent system and an agent with a single loop, and you're equipping that agent with a single loop with smaller agents to carry out different tasks. And so he gives an example of this. He gives a nice little diagram, uh, and he talks about the pros and cons, which, uh, yeah, definitely. There's a trade off there. It's not clear that it's always a good idea to do it. And he's got a really nice thing in the, um, in the conclusion. But even with the Subagent architecture, reliability is still a challenge for agentic systems. Breaking down a complex task into smaller subagent functions can make them simpler. But then he ends with saying don't overengineer a solution today that are simpler or better model can solve tomorrow. Sage advice. So not only read the the the context engineering blog post, but I would just take a look at this one two and maybe even bookmark this page because he's full of useful stuff. And since I mentioned looking online for more about this, I will just say Simon Willison is a wonderful writer to follow. His blog is another It's gold. Uh, and he mentions here context engineering and he says it's starting to gain traction and he likes it. And he gives the tweets from Andrej Karpathy right here. Plus one for context engineering over prompt engineering. Um, but generally look at Simon's blog. Lots of interesting stuff. He's famous for getting llms to draw pictures of pelicans on bikes. Uh, it's like it's almost like an in-joke of reading his blog. And I recommend it because it's wonderful.

</details>
