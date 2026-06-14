# L89 — Multi-Agent vs Single-Agent Architectures for Production AI Systems

> **Week 4 · Day 1** · ⏱️ ~7 min

---

## 🎯 TL;DR

Week 4 ki shuruaat agent architecture theory se: **workflows vs agents**, aur agents ke andar **multi-agent (planner + workers)** vs **single-agent-with-loop** patterns. Golden rule — architecture pehle mat socho, **commercial problem + measurable metric pehle**, aur hamesha **simplest (1 LLM call) se start** karke zaroorat padne par hi complexity badhao.

---

## 🗣️ Hinglish Explanation

### Week 4 ka scope — "humongous" week

Yeh course (#6 of Ed's 6-course curriculum) ki **sabse badi week** hai. Ed teen big words se frame karta hai: **agents, scale, enterprise**. Paanch din ka plan:

- **Day 1 (aaj)**: multi-agent architecture theory + capstone ka database build
- **Day 2**: paanch agents jo collaborate karenge (Lambda functions)
- **Day 3**: front end + API layer
- **Day 4**: enterprise characteristics — observability, monitoring, security, scalability, APIs
- **Day 5**: agentic AI platforms (Bedrock AgentCore) ko compare karna jo humne build kiya uske saath

Aaj ka lecture pure **architecture** par hai.

### Pehla principle: architecture par jaldi mat kudo

Ed ka common pushback yeh hai ki log **agentic AI mein architecture par bahut jaldi jump** kar jaate hain. Sahi tareeka:

1. **Commercial/business problem ko samjho** — actually kya solve karna hai?
2. **Success kaise measure karoge** — ek metric define karo
3. Phir agents ko socho — Ed kehta hai: *"LLM calls with prompts that you will engineer"* — yahi se decide hota hai kaunsa architecture chahiye

Maan lo tumne yeh kaam kar liya hai — problem clear hai, solution ka idea hai. Ab sawaal: **right agent architecture kaise build karein?**

### Terminology: Workflows vs Agents (Anthropic ka blog)

Agentic AI naya aur evolving field hai — koi fixed standards nahi. Par **Anthropic ne ek seminal blog post** likhi jisne terms clear kiye. Wo do cheezein distinguish karti hai:

- **Workflows** → systems jahan models aur tools **strict code paths** ke through orchestrate hote hain. Tum code likhte ho: "yeh LLM call karo, phir yeh LLM call karo." Flow tumhare code mein hardcoded hai.
- **Agents** → systems jahan **LLM khud decide karta hai** kaunse processes call ho, kab, aur flow kaise orchestrate ho. Control LLM ke haath mein hai, code ke nahi.

Us post mein common agent design patterns bhi cover hote hain. Lekin uske baad ek **naya distinction** emerge hua — yahi aaj ka main point hai.

### Agents ke andar do design styles

Jab tum "agents" (LLM controls flow) ki baat karte ho, tab bhi do alag designs dikhte hain:

#### 1. Multi-agent architecture

- Ek **planner / orchestrator** hota hai — ek LLM core jo decide karta hai ki kaunse **other agents** (doosre LLMs / prompt sets) kab call honge.
- Wo har agent ko alag **context aur prompt** ke saath build karta hai jo us specific sub-problem ko frame karta hai.
- Planner orchestrate karta hai, har worker agent ko apna scoped task deta hai.

```
        ┌─────────────┐
        │   PLANNER    │  (orchestrator LLM)
        └──────┬───────┘
     ┌────┬────┼────┬────┐
     ▼    ▼    ▼    ▼    ▼
  Agent1 Agent2 ... AgentN   (har ek apna context + prompt)
```

#### 2. Single agent with loop (agentic loop)

- Sirf **ek LLM** hota hai aur ek **lambi, meaty context prompt**.
- Yeh prompt LLM ko enable karta hai ki wo **to-do list manage** kare, items ek-ek karke tick off kare.
- Ek simple **loop** hota hai — agent baar-baar khud ko call karta hai jab tak wo convince na ho jaaye ki task complete ho gaya.

**Best example: Claude Code.** Agar tumne Claude Code use kiya hai (Ed umeed karta hai kiya hoga), tumne yeh experience firsthand feel kiya hai — ek agent jo apni hi to-do list manage karta hai aur loop mein khud ko repeatedly call karke figure out karta hai kaunsa workflow follow karna hai.

### Reality: yeh binary nahi hai

Ed khud point out karta hai ki Claude Code mein bhi tum **different agents configure** kar sakte ho jo main looping agent call kar sake. Toh:

- **Single agent with loop** doosre agents ko call kar sakta hai
- **Multi-agent** mein planner ko bahut autonomy ho sakti hai — same worker ko multiple baar call kar sakta hai, yaani **uska bhi ek loop** ho sakta hai

Toh yeh do **extremes** hain; **reality aksar beech mein** hoti hai. Distinction tumhe do design styles ka sense deta hai, par koi hard boundary nahi.

### Kaunsa pattern chunein? — No fixed answers

Ed ka classic answer: **koi fixed answer nahi hai.** (Yeh production repo ke `guides` folder mein **guide 12** mein bhi likha hai.) Approach:

1. **Business problem + potential solution** ready rakho
2. **Ek metric** define karo — performance kaise measure hogi
3. **Different agent architectures try karo** — experimentally pata karo kaunsa best perform karta hai

### Golden rule: START SIMPLE

Successful hone ki key — **sabse simple approach se start karo**:

- Typically **ek agent, loop mein bhi nahi** — sirf **ek LLM call**.
- Phir tab hi other agents break out karo, business functionality add karo, concerns separate karo, ya loops introduce karo — **jab problem solve karne ke liye zaroorat ho**.

Flow:
1. Ek agent (1 LLM call) se start
2. Performance bar tak nahi pahunchi (tumhare criteria meet nahi hue)
3. Thoda complex config explore karo — kuch responsibility alag agent mein break out karo
4. Dekho performance par kya asar pada
5. Repeat jab tak metric satisfy na ho

*"That is always the trick"* — start simple, measure, incrementally complex banao.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Workflow** | Models/tools strict code paths se orchestrate — flow tumhare code mein hardcoded |
| **Agent** | LLM khud decide karta hai kaunse processes call ho, kab, kaise orchestrate ho |
| **Multi-agent architecture** | Planner/orchestrator jo alag-alag worker agents (apne context/prompt ke saath) ko coordinate karta hai |
| **Single agent with loop** | Ek LLM + lambi prompt, to-do list manage karke khud ko loop mein call karta hai |
| **Planner / Orchestrator** | Multi-agent ka central LLM jo decide karta hai kaunsa worker kab chale |
| **Agentic loop** | Agent baar-baar khud ko call karta hai jab tak task complete na ho (Claude Code style) |
| **Anthropic seminal post** | Wo blog jisne workflows vs agents terminology aur design patterns define kiye |
| **Start simple** | 1 LLM call se shuru, metric measure karke hi complexity badhao |

---

## 💼 Backend Dev Ke Liye Note

Python backend dev ke liye yeh distinction directly **service decomposition** se map karta hai. **Workflow** = tumhara classic orchestration code (ek function jo service A call kare, phir B, fixed sequence) — basically a **DAG/state machine** jo tum control karte ho. **Multi-agent** = microservices jisme ek **API gateway/orchestrator** dynamically downstream services route karta hai, har service ka apna bounded context (yahaan "context" = system prompt + data). **Single agent with loop** = ek **recursive/iterative worker** jo apni hi work queue manage karta hai.

"Start simple" wala principle bilkul **YAGNI + premature optimization** wala mindset hai — pehle monolith/single-call se solve karo, profiling (yahaan: ek eval metric) ke baad hi services break out karo. Aur "metric pehle define karo" = test-driven / observability-first thinking: jaise tum SLO/latency budget pehle set karte ho code likhne se pehle, waise hi yahaan eval metric pehle define karo, phir architecture tune karo. Anti-pattern jo Ed warn karta hai — "team of human-like agents" socho — wo **over-engineering by analogy** hai, jaise har domain noun ke liye ek separate microservice bana dena bina load/coupling dekhe.

---

## ✅ Takeaway

- **Architecture par jaldi jump mat karo** — pehle commercial problem samjho, phir measurable metric define karo
- **Workflows** (code controls flow) vs **agents** (LLM controls flow) — Anthropic ka seminal distinction
- Agents ke andar do styles: **multi-agent (planner + workers)** vs **single agent with loop**; reality aksar beech mein
- **Start simple**: 1 LLM call se shuru, metric measure karo, zaroorat padne par hi agents/loops add karo
- Guide 12 (production repo) mein detail hai — experimentation hi sahi architecture chunne ki key hai

---

<details>
<summary>📜 Full Transcript (English)</summary>

Welcome to the biggest week of the biggest course I've ever made. I don't use the word humongous often, but it's very fitting. Now this is a humongous week with a humongous project and I can't wait to get started. Let's get going! And the three big words for this week are agents, scale, and enterprise. We're going to be doing a fair bit of all three. This is what I have in store for you for the five days. You'll see plenty of purple here because we're going to be doing a lot of AI. We've also got some blue because we're going to be doing a lot of capstone project build today is going to be about talking about the multi-agent architecture. Then we're going to work on the capstone projects. Most of the Atlantic part of it and then the front end. Then we're going to talk about enterprise characteristics like observability, monitoring, security, scalability, APIs. And then we're going to end by talking about agentic AI platforms and comparing them with what we've already done. So much to do. And I'm going to start by talking about architectures for genetic projects. Now, one of the things I often push back on is when people jump too quickly to architecture, which I find very common in, particularly in the field of genetic AI. It's very important always when working on business problems, to start by focusing on the commercial problem, understand the problem you're working on, understand how you will measure success and think about agents first and foremost. As Lem calls with prompts that you will engineer and use that as your way to determine what kind of agent architecture you will use. But let's assume that you've done that. You've worked on your problem. You know what kind of solution you need to build. And you're wondering, now, how do I build the right kind of agent architecture to solve that problem effectively? And let's talk about that. So to start with, I want to to remind you for, for for those that already know it or to explain some of the terminology around agent architectures, and this is something which it's it's ambiguous out there. There aren't necessarily standards. A lot of Agentic AI is new and evolving, and so there are emerging terms that people use in different ways. But anthropic wrote a phenomenal blog post, a seminal blog post which laid out some different terms. And they distinguish between workflows systems where models and tools are orchestrated through strict code paths that you code up. You say, call this LLM and then call this LLM. That would be a workflow. And they distinguish that from agents, which are systems where the LLM itself decides which processes should be called, when and how to orchestrate the flow. And in that seminal anthropic post they cover different common agent design patterns. But since then, something new has emerged since Anthropic's post came out. Which is that even when you're talking about agents, even when you're talking about systems where llms control the flow, you do see these two different kinds of design. Let's talk about them. One of them, one of the common patterns is multi-agent architectures. And this is where you have an agent, an LM core that's often called the planner or the orchestrator. And that itself is responsible for deciding which agents, which other LMS or other sets of prompts get called in different circumstances. It orchestrates making each of those different calls, and you build out separate agents with context, with prompts that frame exactly the problem that that agent is solving. And that kind of architecture is known as multi-agent architecture. And then there is a different architecture which goes by different names. But but if you say single agent with an agent loop Agentic loop, then people know what you mean. And this is one where you only have one LM and one usually quite long, quite meaty context prompt. And in that prompt it's able to do things like managing a to do list and then ticking off the to do items one by one. And there's simply a loop where it comes back to itself repeatedly until it's convinced itself that it has completed the task at hand. And that is is sometimes known as a single agent with loop, for obvious reasons. And if you've if you've had experience working with Claude Code and I hope you have, it's amazing. Uh, you you will have felt this firsthand. You really have felt that experience of one agent that you're interacting with that is able to manage its own to do list and work through a task calling itself repeatedly in a loop while it figures out what what kind of workflow to follow. And it's interesting that I would give Claude code as my example there, because you're probably thinking, aha, hang on a second, Ed, you missed something there because in Claude code, you can actually configure different agents that the main agent in a loop can call out to. And so yes, this is yet another example of where I'm giving you two different extremes. But the reality is often somewhere in the middle, you can have a single agent with a loop that's still able to call out to different agents, and you can have the architecture on the left, but have the planner agent still have a lot of autonomy over which worker it calls when, and potentially calling the same worker multiple times. So it can also have a kind of a loop as well. So it's not as binary as there being multi-agent or single agent with loop, because multi-agent architecture can have loops, and the single agent with loop can have other agents, it's in between the two. But it does give you a sense of these two different styles, these two different design patterns that you can incorporate in your solutions. And I know what you're thinking. You're thinking, okay, fair enough. So there are these two different patterns and there's stuff in between the two. But how do we know which one to pick for our particular problem at hand? To which of course, my answer, as it often is, is that there are no fixed answers to this, just as I as I put in guide 12 in the guides folder, I believe in the production repo. This. This is something which you need to experiment with. You need to try out different approaches and see which performs best for your problem at hand. When you have your business problem, you have your potential solution. You need a metric. How will you measure the performance of your solution? And then try different agent architectures to find out experimentally which one solves the problem best. And key to doing that successfully is to start simple. Start with a very simplest approach you can. Typically that is one agent, not even in a loop. Start with one. In other words, one LM call. Start by calling an LM and start breaking out other agents and adding in more business functionality, separating concerns and considering loops only when you need to solve a problem to do so. So you start simple. You start with one agent. You find that the performance isn't where you wanted it to be. You're not. You're not meeting the bar that you set yourself your criteria. And so then you explore slightly more complex configurations of breaking out some agent responsibility to see how it affects performance. That is always the trick.

</details>
