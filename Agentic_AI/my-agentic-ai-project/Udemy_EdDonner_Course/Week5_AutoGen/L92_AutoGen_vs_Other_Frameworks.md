# L92 — Day 1: AutoGen vs Other Frameworks

> **Week 5 — AutoGen** · ⏱️ ~6m · 🎥 Lecture 92 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821583

---

## 🎯 Ek Line Mein (TL;DR)

**AutoGen** ek single library nahi, ek **umbrella** hai — neeche **AutoGen Core** (generic, distributed agent **runtime**/fabric), uske upar **AutoGen AgentChat** (lightweight agent abstraction, OpenAI Agents SDK / Crew jaisa), aur sabse upar **Studio** (low-code UI) + **Magentic-One** (ready-made console app) — aur ye sab **Microsoft Research** ka pure open-source contribution hai, monetisation-driven roadmap nahi.

---

## 📝 Hinglish Explanation (Detailed)

- Ed yaad dilate hain ki **AutoGen** frameworks ki series ka **last framework** hai — kyunki Week 6 ka **MCP** technically framework nahi hai (wo ek protocol hai).
- Baaki frameworks ki tarah AutoGen bhi **ek naam ke neeche kai alag cheezein** hai. Stack ko 3 layers me samjho:
  - **AutoGen Core** — sabse neeche ki layer. Ye **framework-agnostic** hai: jo bhi agents/LLMs use ho rahe hain, Core ko farak nahi padta. Ye ek **generic framework for scalable multi-agent systems** hai jo **messaging between agents** manage karta hai — **chahe agents alag-alag jagah distributed hi kyun na ho**. Ed isse "**a fabric for agents to run within**" bolte hain — yaani ek **agent runtime**. Isme **LangGraph** se kuch similarity hai, par ye **much, much simpler** hai.
  - **AutoGen AgentChat** — Core ke **upar** built. Ye wala part aapko bahut **familiar** lagega kyunki ye **OpenAI Agents SDK** aur **CrewAI** jaisa hai: ek **lightweight, simple abstraction** jisme LLM ko agent construct me wrap karte ho, **tools** use karwate ho, aur agents ko **aapas me interact** karwate ho.
  - **AgentChat ke upar 2 offerings**:
    - **AutoGen Studio** — **low-code/no-code app** jisme visually agent systems construct kar sakte ho.
    - **Magentic-One** — ek **canned product/console application** jo command line se chalti hai aur out-of-the-box kaam karwa deti hai. Ed kehte hain ye basically wahi cheez hai jo humne Week 4 ke end me khud banayi thi — hamara **Sidekick** co-worker.
- **Positioning ka difference**: Crew aur LangChain me **monetisation/commercialisation** product roadmap drive karti dikhti thi. AutoGen me angle alag hai — ye **Microsoft Research ka community ke liye** open-source project hai, contributors duniya bhar se. Isliye **Studio aur Magentic-One ko "research environment" bola gaya hai — production-ready NAHI** — aur wo ye baat clearly state karte hain.
- **Course focus**: Hum **AgentChat + Core** pe focus karenge. **Studio** (low-code) skip — "we're coders, that's what we do". **Magentic-One** try karne layak hai par essential nahi. Mostly **AgentChat** karenge kyunki wahi **Crew / OpenAI Agents SDK / LangGraph ke agent-interaction part** ka direct comparable hai; **Core** thoda kam, mainly curiosity/experimentation ke liye — aur jab Core karenge tab bhi AgentChat saath use hoga.
- **AgentChat ke core building blocks** (sab familiar lagenge):
  - **Models** — dusre platforms ke **LLMs** wale concept jaisa hi.
  - **Messages** — ye naya hai ki ise ek **first-class core concept** banaya gaya hai. Message ho sakta hai: **user → model**, **agent ↔ agent**, ya **agent ke andar ke events** (jaise **tool calls**) — sab kuch "message" hi hai.
  - **Agents** — wahi jo hum jaante hain: piche ek **model**, aur user ya dusre agent ki request pe **series of tasks** carry out karne ki ability.
  - **Teams** — **Crew ke "crew"** jaisa: agents ka group jo mil ke ek goal achieve karta hai.
- Aur bhi building blocks hain, par intro ke liye yahi 4 kaafi hain. **Aaj (Day 1)** pehle 3 — **models, messages, agents** — quickly use karke ek example banayenge, aur naya twist: example me **SQL** involve hoga, kyunki wo kai logon ke liye useful hai.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **AutoGen** | Microsoft Research ka open-source agent ecosystem — ek umbrella naam jiske neeche kai layers hain |
| **AutoGen Core** | Sabse nichli layer: framework/LLM-agnostic **agent runtime** ("fabric") jo agents ke beech messaging handle karta hai, distributed agents ke liye bhi; LangGraph jaisa idea par much simpler |
| **AutoGen AgentChat** | Core ke upar lightweight agent abstraction — OpenAI Agents SDK / CrewAI ka direct comparable; course ka main focus |
| **AutoGen Studio** | AgentChat ke upar **low-code/no-code** visual builder app — research environment, production-ready nahi |
| **Magentic-One** | Out-of-the-box canned **console application** (command line agent assistant) — hamare Week 4 Sidekick jaisi cheez |
| **Models** | AgentChat ka LLM wala concept — model jo agent ke piche hota hai |
| **Messages** | First-class concept: user→model, agent↔agent, aur agent ke internal events (tool calls) — sab messages hain |
| **Agents** | Model + tools wala construct jo user/dusre agent ki request pe tasks karta hai |
| **Teams** | Agents ka group jo interact karke ek goal achieve kare — Crew ke "crew" jaisa |
| **Research positioning** | Microsoft isse community contribution ke roop me run karta hai — monetisation-driven roadmap nahi, isliye kuch parts explicitly "not production-ready" |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Core vs AgentChat = messaging infra vs application framework.** AutoGen Core ko **Kafka/RabbitMQ + actor model** ki tarah socho — ek message-passing fabric jo distributed "actors" (agents) ke beech routing karta hai, payload ke content se agnostic. AgentChat us fabric ke upar ka **opinionated app framework** hai — jaise broker ke upar Celery/Spring. Isliye "AgentChat is built on Core" sun ke aapko layered architecture turant click karega.
- **"Sab kuch message hai"** — tool calls, agent replies, user input — ye exactly **event-driven systems** ka mindset hai jahan har interaction ek typed event hota hai. Week 5 me aage isi se **RoutedAgent + handler dispatch by message type** niklega, jo aapke type-based event handler registration (pub-sub consumers) jaisa hai.
- **OSS positioning ka fark business decision hai**: Crew/LangChain VC-backed hain to platform/monetisation roadmap dikhti hai; AutoGen MSR ka research OSS hai — fayda: no paywall pressure; nuksan: Studio/Magentic-One jaisi cheezein **explicitly not production-ready**. (Side note: isi research-vs-product tension se **AG2 fork** drama bhi nikla — aage ke lectures me.)
- **Hands-on lab**: is lecture ka code khud chalane ke liye is repo me `Practical/lab1_agentchat_basics.py` run karo (`uv run` se chalta hai, **Groq pe free** via `OpenAIChatCompletionClient` + `base_url` + `ModelInfo`). Note: hamare labs course se thode alag — hum **AutoGen 0.7.5** use karte hain (course 0.5.1, same API family).

---

## 🧠 Takeaway (yaad rakho)

1. **AutoGen = 3-layer stack**: Core (distributed agent runtime/fabric) → AgentChat (lightweight agent abstraction) → Studio + Magentic-One (apps on top).
2. **AgentChat** hi Crew / OpenAI Agents SDK ka direct comparable hai — course ka main focus; **Core** sirf curiosity-level explore hoga.
3. **Microsoft Research OSS** positioning: community contribution, no monetisation push — par Studio/Magentic-One **production-ready nahi** (clearly stated).
4. **4 building blocks**: Models (LLMs), Messages (user↔model, agent↔agent, tool-call events — sab messages), Agents, Teams (Crew ke crew jaisa).
5. Day 1 me **models + messages + agents** se quick example banega — with a **SQL** twist.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

And so with that, I'll just move on to talk about what Autogen actually is. Let's remind you, these are the frameworks we've been going through. Autogen the last of the frameworks, uh, before, because MCP isn't really a framework. Uh, okay. So what is autogen? So Autogen, as with the others, it's a bunch of different things all wrapped under one autogen umbrella name. It's first of all, something called Autogen core. And Autogen core is something which is like, uh, it's agnostic to the, to the framework that the actual agents and LLMs that are being used. It is like a general generic framework for building scalable multi-agent systems, something that manages things like messaging between agents, even if they're distributed in different places. So it's like a fabric for agents to, to run within. It's something different. It's got some stuff in common with, with an idea like LangGraph, but much, much simpler. It's got uh, but but basically it's like a runtime, an agent runtime for running agents together. That is Autogen core.

Autogen agentchat. It's quite a mouthful. Autogen agent chat. That is a framework that is going to be very familiar to you, because it's very similar to OpenAI agents SDK and to crew. It is a lightweight, simple abstraction for putting together LLMs in an agent construct to allow them to use tools to allow them to interact with each other, that is, Autogen agent chat and then built on top of Autogen agent chat. Agent chat itself is built on top of core. Built on top of agent chat are a couple of offerings. There's something called studio, which we've heard that name a few times now that is Autogen low code, no code app for sort of constructing things visually. And there's also something called Magentic one, which is like a product. It is a console. It's something you use in the command line, which can take care of things for you and do them. So it's like an application. It's a it's a application to run an agent framework that's out of the box that's canned, that runs from the command line. So these are the various bits and pieces that make up Autogen.

And uh, all of this is part of open source. It's part of it's sort of managed by Microsoft Research, but it's available. There are people who contribute from all all over the place. And it's an interesting point that whilst when we talked about crew and and LangChain, we saw that there was perhaps the possibility that that monetisation commercialisation was driving some of their product roadmap. There's a different angle here with Microsoft. This is all a Microsoft research for the community kind of thing. And so you don't necessarily see that things like Studio and Magentic One, Magentic studio is considered like a research environment. It's not it's not considered ready for production. And they state that very clearly all over it. So it is a different positioning. This is a big open source contribution, uh, through and through.

And of course, no surprise what we're going to be focusing on is going to be the, uh, agent, uh, Autogen core and the Autogen agent chat, those two parts of the puzzle. We're less interested in the low code. No code, because we're coders. That's what we do. Uh, and, uh, magentic one, it seems, seems like a cool thing to try out, but it's. I guess it's a bit like, uh, someone building what we've already built. Uh, in the end of last week, uh, with with our co-worker that we have our sidekick. Our personal sidekick. Uh, so one more point to make here is that we're going to be focusing mostly on Autogen agent chat. Uh, because that is the sort of direct comparable with Crew and with OpenAI agents SDK and with the sort of agent interactions part of LangGraph. We will also look at Autogen core some pretty cool things about it, but but more to give you some interest in it and to experiment a bit. Um, not as much as agent chat. And even when we do, we'll be using agent chat as well. So that's the lay of the land.

And to talk about the concepts behind, uh, the, the Autogen framework and particularly behind Agent Chat that we're now going to talk about. What are the building blocks here? Well, they're going to be very familiar to you. They are straightforward and things that we've already met before. So they have a concept called models. And their concept called models is similar to LLMs that we've seen in other platforms. Messages I guess it's new that they identify this as a core concept. Messages that can represent messages between agents, or it can represent events that happen within an agent's interactions, which which really is referring to, like calling tools. Those are also considered messages. And so we'll see some some stuff about messages that can be from a user to the model. It can be between agents. It can be within an agent when it's calling tools. But those are called messages and agent. It's going to be what we're used to. It's something which has a model behind it and something which is able to carry out a series of tasks on behalf of, of a request, on behalf of a user or another agent and then teams again. That's familiar. This is like a crew from crew. Uh, it'd be a group of agents that can interact to achieve some goal. So these are the sort of core building blocks and there are others. But but I think these are probably the ones to introduce. And for today we're going to look at the first three models messages and agents very briefly very quickly to set up a quick example. But we'll do something new. We'll involve some SQL in it because I know that's that's going to be useful for some people. So let's do that right now.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
