# L02 — Day 1: AI Agent Frameworks Explained (OpenAI SDK, Crew AI, LangGraph & AutoGen)

> **Week 1 — Foundations** · ⏱️ ~12 min · 🎥 Lecture 2 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49770319

---

## 🎯 Ek Line Mein (TL;DR)

Ye lecture poore course ka **roadmap** hai — Ed batate hain ki 6 weeks mein kya-kya seekhenge (theory + 4 frameworks + MCP) aur kaunse **8 projects** banayenge (career alter-ego se lekar autonomous trading floor tak). Saath mein apna short intro bhi dete hain.

---

## 📝 Hinglish Explanation (Detailed)

### 1. Course mein 3 cheezein karenge
Ed kehte hain course basically **3 cheezon** ka mix hai:
1. **Theory** — agents kya hote hain, agentic architecture kaisi dikhti hai.
2. **Frameworks** — actual platforms jisse hum agents build aur deploy karenge.
3. **Hands-on Projects** — sleeves upar karke khud banana. Kuch projects entertaining honge, kuch commercial (real business functionality) — par sab fun honge.

### 2. 6 Weeks ka structure (har week pichhle pe build karta hai)
Curriculum **6 modules = 6 weeks** mein bata hai. Har week pichhle week pe build karta hai, toh order important hai. Har week mein **5 days** (Sat-Sun off 😄). Aap apni pace se kar sakte ho — fast karo toh aur accha.

| Week | Naam | Kya hai | Code level |
|------|------|---------|-----------|
| **1** | Foundations | Sirf **LLMs ko natively interact** karwa ke agent banana — **bina kisi framework** ke. Grounding + basics. | Pure code |
| **2** | OpenAI Agents SDK | Pehla framework — **simple, elegant, flexible**. Guardrails bhi add karenge. | Light framework |
| **3** | CrewAI | **Fan favourite**, low-code. Thodi configuration likho aur apni "crew of agents" define karo jo task solve kare. | Low-code |
| **4** | LangGraph | **Sophisticated, complex, very powerful** — full-code end. Iski poori power use karenge. | Full code |
| **5** | Microsoft AutoGen | Powerful framework jahan agents **remotely collaborate** kar sakte hain. (AutoGen kai cheezein hai, sab dekhenge.) | Full code |
| **6** | MCP (Capstone) | **Model Context Protocol** (Anthropic ka, open-source). Alag models ek **common protocol** se connect + collaborate + capabilities share karte hain. Pichhle saare weeks ka gyaan yahan combine hota hai. | Protocol + capstone |

> 💡 Spectrum samjho: **OpenAI SDK (simple)** → **CrewAI (low-code)** → **LangGraph (full-code, powerful)**. MCP week 6 mein isliye hai kyunki ye sab kuch ek saath laata hai.

### 3. The 8 Projects 🚀
Course mein **8 projects** banenge. Ed kehte hain **projects 5, 6, 7, 8** sabse exciting hain:

- **Project 1 (end of Week 1) — Career Alter Ego:** apna khud ka agent jo aapke career ke baare mein sawaalon ke jawab de. Resume ki jagah website pe daal do — log aapse "baat" karke aapka experience, challenges waghaira jaan sakein. Deploy bhi karenge (production).
- **Deep Research (Week 2):** ek bahut accha research app.
- **CrewAI projects (Week 3):** crew seekhke kuch projects.
- **Project 5 — Engineering Team:** ek agentic platform jo **poori engineering team** represent kare — frontend developer, backend developer, engineering lead, aur tester — jo **aapas mein collaborate karke software likhein**.
- **Project 6 — "Sidekick":** ek agent jo **browser open karke aapke saath us browser mein kaam kare**. (Chinese startup **Manus** jaisa, par Manus cloud box mein chalta hai jise control nahi kar sakte — yeh aapke apne machine pe, side-by-side.)
- **Project 7 — "Creator":** ek agentic framework jo **khud naye agents bana sake** (agents jo agents ko janm dein). Thoda commercial angle bhi add karenge.
- **Project 8 — Capstone — Financial Trading Simulation:** multiple agents jo **investment decisions** lein — internet pe financial news search karein, **real-time stock prices** dekhein, company annual reports + SEC filings padhein, aur **buy/sell** decisions lein. Account-tracking ka code (simulated part) **Project 5 ki engineering team** ne likha hoga, humne nahi! ⚠️ Yeh sirf illustrative hai — **real investment ke liye use mat karna**.

**Do goals har project ke:** (1) **Educational** — skill badhe, (2) **Commercial** — business mein (B2B/B2C) turant apply kar sako.

### 4. Ed Donner ka quick intro
- Career ka zyada time **J.P. Morgan** mein — ~300 logon ki engineering & science teams chalayi.
- London (origin) → Tokyo → ab **New York**.
- Abhi **CTO & co-founder of an AI startup "Nebula"**.
- Pehle apna startup **"Untapt"** banaya tha — **2021 mein acquire** hua (Times Square billboard wali magical photo).
- Ek aur Udemy course hai **"LLM Engineering"** (60,000+ students).
- Mazaak: AI/LLM mein expert hain par hand-eye coordination (jaise plane udaana) mein zero 😂 — "agar cockpit mein main dikhun toh parachute dhoondh lena, par agentic AI course mein main instructor hoon toh aap sahi jagah aaye ho."

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Foundations (Week 1)** | Bina framework ke, sirf LLMs ko aapas mein interact karwa ke agent banana. |
| **OpenAI Agents SDK** | Simple, elegant, flexible framework — Week 2. |
| **CrewAI** | Low-code, config-based "crew of agents" — fan favourite, Week 3. |
| **LangGraph** | Full-code, powerful, complex framework — Week 4. |
| **AutoGen** | Microsoft ka framework; agents remotely collaborate — Week 5. |
| **MCP** | Model Context Protocol (Anthropic) — models/tools ek common protocol pe connect karte hain. Week 6 capstone. |
| **Career Alter Ego** | Project 1 — aapka personal agent jo aapke career ke baare mein baat kare. |
| **Capstone** | Final project (8) — autonomous financial trading simulation. |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- Ye course ka structure aapke favour mein hai: **pehle raw code (Week 1)**, fir frameworks. Matlab aap "magic" ke peeche ka mechanism samjhoge — jo ek experienced backend dev ke liye perfect hai (black-box use karne se behtar).
- **Frameworks ko backend libraries ki tarah dekho:** OpenAI SDK = lightweight lib, CrewAI = opinionated/config-driven (Django jaisa "convention over configuration"), LangGraph = low-level + powerful (jaise raw asyncio/state machines), AutoGen = distributed systems flavour (remote agents = microservices/message-passing).
- **Project 8 (trading sim)** aapke domain (`main.py` mein aapne banking/concurrency ke questions bhi pooche the) se relate karta hai — real-time data + decision logic + account state management. Ye aapke backend strengths ke saath perfectly overlap karta hai.

---

## 🧠 Takeaway (yaad rakho)

1. **6 weeks = Foundations → OpenAI SDK → CrewAI → LangGraph → AutoGen → MCP.** Har week pichhle pe build karta hai.
2. **8 projects**, climax = **autonomous trading floor (capstone)**.
3. Har project **educational + commercial** dono hai.
4. Week 1 ka project = **Career Alter Ego** (deployable agent).

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

> Note: Auto-captions ki spelling lightly cleaned (LangGraph, Manus, Ed Donner, LLM, Untapt, etc.).

So, as promised, I'm coming back now to tell you what this course is actually about. We're going to be doing three things. We're going to be working on theory, talking about what agents are and what an agentic architecture looks like. We're going to be talking about frameworks — working with actual platforms that allow us to build and deploy AI agents. And of course, we're going to be getting hands on, rolling our sleeves up, building some projects. Some of the projects will be more on the sort of entertaining side. Some of them will be much more on the commercial side, building real functionality. All of them will be fun.

So I've organized the curriculum into six modules that I call the weeks — week one through to week six. And I do that because I want to give you some motivation to be pushing on through this and keep up the drive. But you can take it at whatever pace you like, and if you can do it faster than six weeks, then so much the better. But that's how I've structured it, and each week builds on the last.

The first week that we're on right now is called foundations. And it's all about grounding — building out the basics, talking about what it takes to have an agentic architecture, how different LLMs can interact. And we're going to be building an agentic solution just with LLMs interacting natively, not going through a framework.

But in week two, we introduce our first framework, the OpenAI Agents SDK, which is a beautiful framework because it's so simple and elegant and flexible, and we'll build some things with it. We'll add guardrails. It's going to be really great.

In week three, though, we move to the very popular Crew. I'd say that Crew is the fan favorite. People love Crew. It's on the sort of low-code end of the spectrum. It allows you to write some configuration and use that to define your crew of agents that will solve your task. And it's a lot of fun to work with.

Perhaps on the opposite end of the scale in terms of code — of low-code to full-code — is LangGraph, which is very sophisticated, quite complex, very powerful. And we will be using all of its power.

And in week five, another powerful one is Microsoft's AutoGen. AutoGen is actually a couple of different things, and we'll look at all of them. But one of the things it is, is like an environment where agents can collaborate remotely. And that's going to be fun.

And we wrap it up in week six with our capstone project and introducing MCP, the Model Context Protocol from Anthropic. Incredibly exciting. And it's really taking off in a big way. This is an open source way that different models can connect and collaborate, share each other's capabilities using a common protocol. So I'm really excited to show it to you. It makes a lot of sense to have that in week six, because we're going to draw on a lot of the things we've learned about in prior weeks. It's all going to come together, and that's very much the idea of this structure. Each week builds on the last as you build up your capabilities and you upskill all the way through to the end of week six, when you will have mastered engineering AI agents.

And each week consists of five days — five different sets of lectures to build up your skill sets. During that week I give you Saturday and Sunday off. So just to show you what it looks like — I'm not going to talk to what we're going to do on every single one of the days. I want to give you that sense of: there's a lot going on. We're going to cover a lot of stuff. And this is color coordinated to match an earlier slide. That orange represents some theory. Yellow is the project.

And that first project we're going to do at the end of this week is going to be really cool, really fun — something that you'll be able to put into practice, building your own agent that you'll be able to deploy into production, that is able to answer career questions about yourself. It will be like your career alter ego that you can put on your website. Instead of having a resume, people can talk to you and talk about your experience and your challenges and so on. Isn't that cool? We're going to be doing that in the next few days. That's week one.

Week two, we're going to be, as I say, OpenAI Agents SDK. You'll see that the blue here — blue boxes represent a new framework that we are learning. And again, the yellow are the projects, including deep research, which will be a great app.

Week three with Crew. You can see we're going to learn about Crew and then build a couple of different projects with Crew. Week four is LangGraph. Week five is AutoGen, and then week six is MCP and the capstone project, which is going to come at the end of this course, bringing everything together.

So as I say, I'm not putting this up here to show you every single box. I'm doing it so you see we've got a lot of material to cover. There's a lot of areas in which we'll be growing skills, and by the end of it you'll have ticked off everything you see here on this screen — the complete curriculum. And you will have true expertise in the world of AI agents.

And I'm now just going to color in the boxes which represent the delivery of major projects. And in particular, I would say that the numbers five, six, seven and eight are some of the really exciting ones I have in store for you. I've just finished building them and I had so much fun doing it, and I can't wait to share it with you.

And just to show you that it's definitely worth hanging on in there for the next few weeks, let me tell you about those last four projects. One of them is writing an agentic platform that's going to represent a whole engineering team — a team of different people, a front end developer, a back end developer, an engineering lead, and a tester — that will collaborate together to write some software for us, and we'll see them all in action.

One of them will be — I call it Sidekick. It's going to be an agentic platform that will be able to bring up a browser and interact in that browser together with you. So you will have your own sidekick that can do things with you. It's a bit like Manus, if you know Manus — of course, the Chinese agentic startup that's really caused a lot of excitement. But Manus runs its platform in a sort of cloud box that you can't control; you can just watch it doing its thing. You'll have something a bit like that, but it will be on your box and you can work with it side by side. A true sidekick.

Project seven I call Creator, and this one isn't particularly commercial. It's just really interesting — this is one where we will build an agentic framework that is itself able to create new agents. It will actually give rise to agents — an agentic platform that generates agents. And we're going to have those agents doing some commercial stuff, just so there is a commercial angle to it.

And project eight, the capstone project — it's something that I've wanted to build for so long, and I'm so happy to get to do it. This is a financial markets trading simulation where we will have multiple agents that can actually go off and make investment decisions — searching the internet for financial news, looking up stock prices (real, true, real-time stock prices) and company information, and reading company annual reports, SEC filings, and then making buy and sell decisions, trading on the market. Now that part is the simulated part — we'll have some code that will just keep track of their accounts. And by the way, the code that we'll have keeping track of their accounts is code that will have been written by project five, by our engineering team, not by us. Just to add an extra dimension to this, some of the code would have been written by our agentic engineering team.

But what you see here in this screenshot is the results of this running, just running yesterday. And it was actually a terrible day on the stock market. So all three agents lost money this day. But hopefully by the time that we get to week six, they will have recovered, and we'll be able to actually show some profits that we're making in our virtual world. And of course, I should say now, and I will say then, that this should not be used for any real investment decisions. Of course, this is purely illustrative. But as an illustrative project, it's going to be a lot of fun.

And while I hope that all of these projects will be entertaining, I will be trying to achieve two things from them. One of them is to have them be highly educational — each project should allow you to upskill your capabilities and your expertise. The other is that I want them to be commercial — they should help you to have ideas of how you can apply this skill in business, whether it's a B2B or B2C kind of project. This should equip you to be able to put this into practice immediately the very next day on commercial projects.

So now, just to introduce myself very quickly, just to show you that I am actually qualified to be talking to you about this stuff. My name is Ed Donner. I spent most of my career at JP Morgan, where I ran engineering and science teams of about 300 people. I started out in London, which is where I'm from originally (if you couldn't tell from the accent). And then I moved to Tokyo for a bit, and now I am based in New York, and I am currently the CTO co-founder of an AI startup called Nebula. You can go and check it out. And prior to that, I founded my own AI startup called Untapt. And actually Untapt was acquired in 2021, and this picture on the bottom left is a picture from the billboard in Times Square announcing our acquisition, which was a particularly magical day for me. So that was really an incredible moment.

But I don't just show you this picture to show off about my moment in Times Square, but also because I happen to live about one block away. If that guitar weren't there in the Hard Rock Cafe, you'd be able to see my apartment building. And I'm actually facing the window right now that is facing there. So in some way, if that guitar weren't there and this was some kind of a live feed, then you would see me waving at you right now or something.

Another thing that I do is I love to be a speaker and instructor on all things LLM. And I have another Udemy course called LLM Engineering, which has got 60,000 plus people on it and has been just an absolute joy. And I hope that some people that are on this now have actually taken that LLM Engineering course — in which case, I must apologize to you, because you heard almost exactly this same introduction when you took that course too. So sorry. I hope you sped through it this second time around. Maybe it gets better on the second time, I don't know.

Anyway, final thing to say, which I also said last time, is that here's a picture of me about to fly a plane. And you might think I'm showing you this because I am fabulously capable at flying planes. But no — au contraire. I'm showing you this because my great skills in the field of LLM and AI is only surpassed by my complete inability to do anything requiring hand-eye coordination. So in fact, if you find yourself in a plane and you look in the cockpit and you see that it's me there in front of the stick, then you want to be looking for a parachute as quickly as you can. But by contrast, if you find yourself taking a course about agentic AI and I am the course instructor, then you've come to the right place. This is completely in my wheelhouse. All right, let's get to it.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
