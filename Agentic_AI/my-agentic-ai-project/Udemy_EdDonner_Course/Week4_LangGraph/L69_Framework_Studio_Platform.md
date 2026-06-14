# L69 — Day 1: Framework, Studio, and Platform Components

> **Week 4 — LangGraph** · ⏱️ ~6m · 🎥 Lecture 69 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821319

---

## 🎯 Ek Line Mein (TL;DR)

**LangGraph** actually **3 alag products** hai — **LangGraph framework** (open-source code library), **LangGraph Studio** (visual builder UI), aur **LangGraph Platform** (paid hosted deployment) — aur hum sirf **framework** use karenge; saath hi Ed ne Anthropic ka famous **"Building Effective Agents"** blog post dikhaya jo kehta hai ki frameworks ki **extra abstraction layers** se savdhaan raho, pehle **LLM APIs directly** use karo.

---

## 📝 Hinglish Explanation (Detailed)

- **LangGraph = 3 cheezein, ek nahi.** Ed clarify karte hain ki "LangGraph" naam ke under teen alag offerings aati hain:
  1. **LangGraph (framework)** — core open-source library jisme aap **graphs, nodes, edges, state** code mein define karte ho. Yehi asli "LangGraph" hai jo hum seekh rahe hain.
  2. **LangGraph Studio** — ek **visual builder / UI tool** jisme aap graphs ko visually hook up kar sakte ho (drag-and-drop type experience).
  3. **LangGraph Platform** — **hosted commercial solution** jo aapke agents ko **scale pe deploy aur run** karta hai LangChain ke environment mein.

- **CrewAI se direct analogy:**
  - LangGraph framework ↔ **CrewAI framework**
  - LangGraph Studio ↔ **CrewAI Studio**
  - LangGraph Platform ↔ **CrewAI Enterprise**

- **Commercialization angle:** Ed ka observation — **LangChain** (company) apne offerings **monetize** karna chahti hai, isliye unki website pe **LangGraph Platform** ko heavily promote kiya jata hai, jaise wahi "LangGraph" ho. Ye unka **enterprise play / core commercial idea** hai — agar aapne sab kuch LangGraph framework mein banaya hai, toh unke Platform pe deploy karna convenient hoga (vendor ke paas har cheez ke hooks hain).

- **Course ka focus:** Hum **sirf LangGraph framework** use karenge — apne graphs khud banayenge. Saath mein **LangSmith** bhi use karenge **observability** ke liye (kya ho raha hai andar, traces dekhne ke liye).

- **Anthropic ka "Building Effective Agents" blog post:** Ed ne Week 1 wale design patterns ka source dikhaya — Anthropic ki website ka ye **brilliantly written** blog post, jisse Ed ne **Anthropic design patterns** directly liye the. Ab ye relevant hai kyunki ye **frameworks vs direct API** debate pe Anthropic ka stance dikhata hai.

- **Anthropic ka argument (when and how to use frameworks):**
  - Frameworks (LangGraph included) **getting started easy** banate hain — LLM calls, **tool defining/parsing**, **chaining calls** jaise low-level tasks simplify karte hain.
  - **Lekin** — ye **extra abstraction layers** create karte hain jo **underlying prompts aur responses ko obscure** kar deti hain → **debugging harder** ho jati hai.
  - Frameworks **unnecessary complexity** add karne ka temptation bhi dete hain, jab ek **simpler setup** kaafi hota.
  - Anthropic ka point of view: unke paas ek simple API hai — **memory JSON objects se handle** ho sakti hai, **LLMs ko multiple direct calls** se chain kar sakte ho. Itna abstraction banana, jo aapko actual LLM se door le jaye, unko resonate nahi karta.
  - **Conclusion (Anthropic):** "Developers ko **LLM APIs directly** use karke start karna chahiye. Kai patterns **few lines of code** mein implement ho jate hain. Agar framework use karte ho, toh **underlying code zaroor samjho** — under the hood ke baare mein **incorrect assumptions** customer errors ka common source hain."

- **Do schools of thought:** Ye Anthropic wala approach LangGraph ki **structure-building philosophy** ke opposite hai. Ed dono perspectives balance karte hain — ye alternative view yaad rakhna useful hai.

- **Week 6 teaser:** Week 6 mein hum dekhenge Anthropic ka apna contribution — **MCP (Model Context Protocol)** — jo ek **alag thinking** hai: glue/abstraction **build** karne ke bajaye, cheezein **connect** karne ka ek **protocol**. Lekin abhi ke liye, hum LangGraph mein deep dive karenge.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **LangGraph (framework)** | Open-source core library — code mein graphs/nodes/edges/state define karne ke liye; course isi pe focus karta hai |
| **LangGraph Studio** | Visual builder UI — graphs ko visually hook-up karne ka tool (CrewAI Studio jaisa) |
| **LangGraph Platform** | LangChain ka paid hosted solution — agents ko unke environment mein scale pe deploy/run karna (CrewAI Enterprise jaisa) |
| **LangSmith** | Observability/tracing tool — agent runs ke andar kya ho raha hai dekhne ke liye; hum ise bhi use karenge |
| **Enterprise play / monetization** | LangChain company ka commercial strategy — Platform bech ke paisa kamana, isliye website pe heavy promotion |
| **"Building Effective Agents"** | Anthropic ka blog post — agentic design patterns ka source + frameworks ki abstraction pe warning |
| **Abstraction layers** | Framework ki extra parat jo prompts/responses ko chhupa deti hai → debugging mushkil |
| **Direct LLM API approach** | Anthropic ki salah — pehle raw API calls se patterns banao (few lines of code), framework baad mein, samajh ke |
| **MCP (Model Context Protocol)** | Anthropic ka protocol (Week 6) — glue build karne ke bajaye components connect karne ka standard |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Open-core business model** pehchano — ye bilkul **Elastic/Elasticsearch, HashiCorp/Terraform Cloud, MongoDB/Atlas** jaisa pattern hai: free OSS framework adoption lao, fir hosted Platform pe monetize karo. Hamare labs sirf **open-source LangGraph framework** use karte hain — Studio, Platform, ya paid offerings nahi (LangSmith sirf optional tracing ke liye).
- **Anthropic ka "understand the underlying code" warning** waise hi hai jaise **ORM vs raw SQL** debate — Django ORM convenient hai, lekin jo dev generated SQL nahi samajhta wo N+1 queries likhta hai. Frameworks ke saath bhi same: LangGraph use karo, par yeh jaano ki under the hood sirf **LLM API calls + JSON state + control flow** hai.
- **Abstraction leak ka cost production mein dikhta hai** — jab prompt debugging karni ho aur framework ne 3 layers mein wrap kar diya ho, toh ye waisa hi dard hai jaise middleware-heavy request pipeline mein ek header ka source dhoondhna. Isliye LangSmith jaisi tracing pehle din se laga lo.
- **MCP vs framework distinction** ko **protocol vs library** ki tarah socho — LangGraph ek library/orchestrator hai (glue aap build karte ho), MCP ek wire protocol hai (jaise HTTP/gRPC) jo interoperability standardize karta hai. Dono solve alag problems karte hain.

---

## 🧠 Takeaway (yaad rakho)

1. **LangGraph = 3 products**: framework (open-source library), Studio (visual builder), Platform (paid hosted deployment) — CrewAI ke framework/Studio/Enterprise ka direct analog.
2. Website pe **Platform** ko hi "LangGraph" jaisa promote kiya jata hai kyunki wahi **LangChain ka commercial play** hai — confuse mat hona.
3. Course mein hum sirf **LangGraph framework** + **LangSmith (tracing)** use karenge — apne graphs khud banayenge.
4. **Anthropic ka counter-view**: frameworks abstraction se debugging mushkil karte hain — **LLM APIs directly** se start karo, framework use karo toh **under-the-hood samjho**.
5. **Week 6 mein MCP** aayega — glue build karne ke bajaye connect karne ka **protocol** — ek bilkul alag philosophy.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

So there's one more thing to mention. One more way in which it's just slightly more complicated. And that is that LangGraph itself is, in fact three different things, as I alluded to this already. But LangGraph is in fact LangGraph itself, which is also thought of as the LangGraph framework. It's a user interface tool called LangGraph Studio, which is one of these kinds of ways that you can hook things up visually. So like a visual builder. And it's something called LangGraph Platform, which is the thing that they're sort of promoting on their website, as if that is LangGraph, uh, LangGraph Platform, which is their, um, hosted solution for deploying and running your agents at scale.

So, LangGraph, which is the framework which is analogous to CrewAI's framework, LangGraph Studio, I think in CrewAI it was also called CrewAI Studio, right? I think so. And then LangGraph Platform is analogous to CrewAI Enterprise. And so these are the three offerings. And I mean, I think to me, I would make the same point that I made with crew, which is that what what perhaps part of what's going on here is, of course, LangChain is looking for ways to commercialize and to monetize their offerings. And so looking for the enterprise play, the LangGraph Platform is about deploying and running your LangGraph your graphs in their environment, uh, taking advantage of the fact that they've they've got hooks into everything that they've built. So I'm sure that if you have built all of your software using LangGraph, then it will be very convenient to use LangGraph Platform. But I suspect that's what's going on, and I imagine that's why it is sort of promoted and framed so heavily on their site, as if LangGraph and LangGraph Platform are the same thing. Uh, it's probably because this is the core commercial idea, uh, for for LangChain and building this out.

But we are going to be focused, of course, uh, as you can imagine on LangGraph, the framework, that part of it, that's what we're building to. We're going to be building our own. And we'll also be using LangSmith as well to see what's going on. Uh, that's going to be interesting for us too.

Now, at this point, I also wanted to do something I wanted to show you the blog post about building effective agents on Anthropic's website that I mentioned way back in week one, when we were looking at design patterns. But I think it's interesting and relevant now because it does show Anthropic's sort of positioning on this, and it's useful for you to keep this in mind when you think about the difference between what we're going to do today and what we're going to be doing in week six.

So if we switch to building effective agents, then this this is the blog post you'll find on their website. And it's a brilliantly written post. I've got to tell you, it's really clear it contains within it the different design patterns that I mentioned. I hope I think I mentioned that I took the Anthropic design patterns right from here. I thought they're so clear, so, so well explained. Um, and in addition to that, it has some discussion about using abstraction layers. And that's really what I wanted to show you here.

So the, the, uh, um, it's says when and how to use frameworks. So they say there are many frameworks that make agentic systems easier to implement, including LangGraph from LangChain. They mention a few others that are not actually so popular, and not as far as I know, although I know of Vellum the business. But but I don't think that that quite is as big as things like CrewAI and Autogen and now OpenAI Agents SDK. But anyway, this is the point I wanted to make. These frameworks make it easy to get started by simplifying standard, low level tasks like calling LLMs, defining and parsing tools, and chaining calls together. However, they often create extra layers of abstraction and that can obscure the underlying prompts and responses, making them harder to debug. They can also make it tempting to add complexity when a simpler setup would suffice.

You can see what Anthropic's getting at. You can imagine from their point of view, they've got an API. They've got something that is relatively simple. Memory can be handled with JSON objects. LLMs can be hooked up simply by calling multiple times. And so for them, this this idea of building all of this abstraction around it, taking you further from actually working with the LLM itself isn't necessarily something that resonates strongly. And so they conclude with we suggest that developers start by using LLM APIs directly. Many patterns can be implemented in a few lines of code. If you do use a framework, ensure you understand the underlying code. Incorrect assumptions about what's under the hood are a common source of customer error. And by customer they mean us customers of Anthropic.

So there you go. I found this really interesting. It's obviously very clearly written and something that I'm very passionate about. It is an alternative, a different school of thought. It is, of course, somewhat, uh, not not in sync with the LangGraph, uh, philosophy thesis of building this kind of structure. Uh, so it's interesting to keep that in mind. And of course, in week six, we're going to see what Anthropic brings to the table in the form of MCP, which is a different way of thinking about it, a protocol, uh, for, for connecting things rather than building the actual glue itself. So I wanted to highlight that and give you that perspective, but it's not going to deter us from getting deep into LangGraph right now.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
