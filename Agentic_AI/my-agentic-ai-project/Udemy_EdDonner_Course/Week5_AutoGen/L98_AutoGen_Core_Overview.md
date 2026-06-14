# L98 — Day 3: AutoGen Core — Distributed Agent Communications

> **Week 5 — AutoGen** · ⏱️ ~5m · 🎥 Lecture 98 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821621

---

## 🎯 Ek Line Mein (TL;DR)

**AutoGen Core** = AutoGen stack ka **base layer** — ek **agent interaction framework** jo agents ke beech **messaging, creation aur distributed communication** handle karta hai, aur ye bilkul **agnostic** hai ki tumne agents kaise/kis language/kis framework me banaye hain (AgentChat use karo ya raw LLM calls — Core ko farak nahi padta).

---

## 📝 Hinglish Explanation (Detailed)

- Week 5 ka **Day 3** shuru — ab hum **AutoGen Core** me utar rahe hain. Yaad karo 3-layer stack: **AutoGen Core** sabse neeche ka **base** hai — ye **AgentChat** ke peeche ka **fundamental infrastructure** hai. Jo bhi high-level cheezein humne Day 1-2 me ki (AssistantAgent, teams waghaira), wo sab isi Core ke upar built hain.

- **Side note — Microsoft Semantic Kernel kahan fit hota hai?** Ed ek common confusion clear karte hain: Microsoft ka ek aur framework hai **Semantic Kernel**, to kya wo bhi agentic framework hai? Answer: **nahi, wo alag cheez hai** — wo **LangChain jaisa** hai:
  - **Semantic Kernel** ek reasonably **heavyweight glue code** hai jo **LLM calls ko wrap** karta hai.
  - Ye **memory** handle karta hai, **tool calling** apne framework ke through karta hai (tools ko ye **"plugins"** bolta hai), **structured outputs** deta hai, aur apna khud ka **prompt templating framework** bhi rakhta hai (templates build/populate karne ke liye).
  - Matlab — wo **business purposes ke liye LLM calls stitch karne** ka general toolkit hai, jaise LangChain.
  - **Overlap zaroor hai** (Semantic Kernel me kuch agent functionality bhi hai, Microsoft ko ye pata hai), lekin positioning alag hai: **AutoGen = exclusively autonomous agent applications** banane pe focused, high-level aur agent-first. Isiliye course me Semantic Kernel nahi dekh rahe — wo LangChain ke saath compare karne wali category hai.

- **To AutoGen Core exactly kya hai?** Microsoft khud ise **"agent interaction framework"** bolta hai. Key points:
  - Ye **agnostic** hai — tumhare agents kis platform/product/abstraction se bane hain, Core ko **parwah nahi**. Tum **directly LLMs call** kar rahe ho, ya koi framework/glue use kar rahe ho — dono chalega.
  - Core sirf **agents ke beech ke interactions** ke baare me hai.
  - Agar tum **AgentChat** ko apna agent abstraction banao to perfect — dono ek doosre ke liye **designed** hain (AgentChat Core ke upar built hai) — aur course me hum yahi karenge. Lekin Core ko AgentChat **require nahi** hota.

- **LangGraph se comparison (interesting parallel):**
  - Jaise **LangGraph ko LangChain ki zaroorat nahi** hoti (par saath use karna helpful hai kyunki thinking similar hai), waise hi **AutoGen Core ko AgentChat ki zaroorat nahi**.
  - Positioning bhi similar hai: LangGraph bhi argue kar sakte ho ki **agents ke interactions** ke baare me hai — bas wo sab kuch **graph of operations/dependencies (node graph)** ke terms me sochta hai. AutoGen Core bhi operations ke interactions ke baare me sochta hai.
  - LangGraph bhi Core ki tarah **care nahi karta** ki agents andar se kaise implemented hain.

- **Lekin BADA difference — emphasis alag hai:**
  - **LangGraph ka driving force** = **robustness aur repeatability** — time me peeche jaakar **replay** kar pana, checkpointing — pura design usi ke liye built hai.
  - **AutoGen Core ka driving force** = ek aisa **environment** banana jahan **diverse aur distributed agents** aapas me interact kar sakein:
    - Agents **bahut distributed jagahon** pe ho sakte hain — "all over the place".
    - **Different languages** me likhe ho sakte hain — ek **JavaScript** me, ek **Python** me.
    - **Different abstractions**, alag shapes and sizes ke ho sakte hain.
    - Fir bhi sab **AutoGen Core ki duniya me nicely play** karte hain, kyunki Core unke beech ke **interactions, creation aur messages** — sab **take care** karta hai.
  - Ed kehte hain LangGraph bhi arguably is type ki cheez sochta hai, par **emphasis ka difference** hai — AutoGen Core ka **real emphasis = interactions aur diverse interactions ko support karna**. Yahi iska thesis hai.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **AutoGen Core** | Stack ka base layer — "agent interaction framework" jo agents ke beech messaging, creation aur distributed communication sambhalta hai |
| **Agent interaction framework** | Microsoft ki official description — framework jo sirf interactions pe focus karta hai, agent implementation pe nahi |
| **Agnostic** | Core ko farak nahi padta tumne agent kaise banaya — raw LLM calls, AgentChat, ya koi aur abstraction |
| **AgentChat** | High-level layer jo Core ke upar built hai — dono ek doosre ke liye designed, par Core ko iski zaroorat nahi |
| **Semantic Kernel** | Microsoft ka LangChain-jaisa heavyweight glue framework — LLM call wrapping, memory, plugins (tools), structured outputs, prompt templating; agentic framework nahi |
| **Plugins** | Semantic Kernel ki tool-calling ka apna naam |
| **LangGraph parallel** | LangGraph bhi interactions framework hai (node graph terms me) aur LangChain require nahi karta — same relationship jaisa Core↔AgentChat |
| **Robustness/Repeatability** | LangGraph ka emphasis — replay back in time, checkpointing |
| **Distributed + diverse agents** | AutoGen Core ka emphasis — alag languages (JS/Python), alag jagah, alag abstractions wale agents ek saath interact karein |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **AutoGen Core ko ek message broker + actor runtime ki tarah socho**, application framework ki tarah nahi. Jaise Kafka/RabbitMQ ko farak nahi padta producer Java me hai ya consumer Python me — bas wire format pe agree karo — waise hi Core ko farak nahi padta agent JS me hai ya Python me, kaunsa LLM abstraction use karta hai. Core sirf **interaction contract** own karta hai (messages, routing, agent creation), business logic tumhara.
- **Semantic Kernel vs AutoGen** ko aise map karo: Semantic Kernel ≈ LangChain (LLM-call glue: wrappers, memory, "plugins" = tools, templating), AutoGen ≈ agent-first runtime. Tumhare microservices analogy me: Semantic Kernel ek HTTP client + ORM + utils library hai; AutoGen Core service mesh/broker hai jisme services (agents) baat karti hain.
- **LangGraph vs AutoGen Core trade-off yaad rakho**: LangGraph = deterministic replay/checkpointing (event-sourcing mindset), AutoGen Core = polyglot distributed messaging (broker mindset). System design interview me ye "durability-first vs interop-first" framing kaam aayegi.
- **Hands-on:** is lecture ka code khud chalane ke liye is repo ka lab run karo — `Practical/lab3_autogen_core_rps.py` (`uv run` se chalta hai, Groq pe free via `OpenAIChatCompletionClient` + `base_url` + `ModelInfo`). Note: hamare labs AutoGen **0.7.5** pe hain (course 0.5.1, same API family) — is lecture ke concepts me koi farak nahi padta.

---

## 🧠 Takeaway (yaad rakho)

1. **AutoGen Core = base layer** — AgentChat ke neeche ka fundamental infrastructure; Microsoft ise **"agent interaction framework"** kehta hai.
2. Core **agnostic** hai — agents raw LLM calls se bane ho ya AgentChat se, kisi bhi language (JS/Python) me ho — Core sirf **interactions, creation aur messages** handle karta hai.
3. **Semantic Kernel ≠ AutoGen** — Semantic Kernel LangChain jaisa LLM-glue framework hai (memory, plugins, templating); AutoGen exclusively autonomous agents ke liye hai.
4. **Core↔AgentChat ka rishta = LangGraph↔LangChain** — require nahi karta, par saath designed hai.
5. **Emphasis ka difference:** LangGraph = robustness + replay/repeatability; AutoGen Core = **distributed, diverse, polyglot agents** ka interaction environment.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

And welcome to our continuing exploits with Autogen. As we head into day three of week five and talk about Autogen core. So just to remind you, this is where Autogen core sits in the scheme of things. It is the kind of base. It is the basis of Autogen AgentChat. And it's the fundamental infrastructure behind it all, which is exciting.

One other thing I wanted to point out while we're on this screen is that you might have heard of something called Microsoft Semantic Kernel, and you might be wondering, where does Semantic Kernel fit into all this picture? Isn't that an agentic framework as well? And what's that got to do with all of these? Well, the answer is Semantic Kernel is a bit different. It is more akin to something like LangChain. Semantic Kernel is a reasonably heavyweight glue code that does things like wrapping calls to LLMs. It handles stuff like memory, it handles stuff like tool calling with its own sort of framework around that and its own name. It calls them plugins and, uh, and, you know, everything else, structured outputs and so on. So it's very much akin, analogous to LangChain. It even has its own like prompt templating framework as well for building templates and populating templates and prompts.

Um, so it's different. There is of course overlap. You can use Semantic Kernel to be managing things like tools and agent calls, and there is some agent functionality there. So there is some overlap that Microsoft's very aware of. But they would see it as a pretty different kind of offering. Autogen is a high level, more, very much more agent focused. All of this is very much focused only exclusively on the world of building autonomous agent applications, where Semantic Kernel is more about stitching together calls to LLMs, generally for business purposes. Well, I hope that gives you some context there and explains why we're not looking at Semantic Kernel for this course, because that's more something you might do alongside looking at LangChain or something like that. Okay. Onwards.

So what is Autogen core exactly? Well, here's a story. So it is an agent interaction framework — that is how they describe it. And that's what it is. It is agnostic. It doesn't care about the platform, the product you're using to actually code your agents. The actual abstraction you have around agents — you could be just calling LLMs directly, or you could be using an abstraction around them, some framework, some glue. Either way, doesn't matter to Autogen core. It is just about agents interacting. If you wish to use, uh, the AgentChat framework as your agent abstraction, that works well, and that's what we'll do. And they're clearly somewhat designed for each other. And we know that, uh, that AgentChat is built on top of Autogen core. So that makes sense, but it doesn't require it. Um, a bit like LangGraph doesn't require LangChain, but it helps if you use LangChain because there's lots of similar kinds of thinking there.

So in some ways it is actually similar positioning to LangGraph. LangGraph, you could argue, is also about interactions between agents, although very much thinking of things in terms of the graph of operations and dependencies, the node graph that now we know so well. Uh, but similarly, you could argue Autogen core is about interactions between operations. That's what it thinks about. And similar to LangGraph, Autogen core doesn't care about how you've implemented your agents. So there's definitely some parallels there.

Um, but the big difference is that LangGraph is all about this idea of robustness and repeatability. This idea of being able to replay back in time — everything that's been built around LangGraph is for that purpose, you can tell. Whereas it seems to me that the kind of the driving force behind Autogen core is more about building a kind of environment where agents can do things like interact with each other, where agents that could be in very distributed places — they could be all over the place and they could be very diverse. They could be written in different languages, they could use different abstractions. One could be written in JavaScript and one in Python. It could be from all sorts of different shapes and sizes, and they're all able to play nicely in the Autogen core world, because Autogen core takes care of the interactions between them, it takes care of creating them, and it takes care of messages between them. So that's the kind of thesis behind Autogen core. And arguably LangGraph also thinks about that kind of thing. I think it's just a different emphasis. This is the real emphasis of Autogen core. It's about the interactions and supporting diverse interactions.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
