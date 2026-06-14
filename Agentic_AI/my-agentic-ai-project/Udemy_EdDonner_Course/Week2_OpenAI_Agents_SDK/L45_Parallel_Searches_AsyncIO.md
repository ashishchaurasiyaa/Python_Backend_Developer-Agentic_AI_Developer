# L45 — Day 4: Deep Research Agent — Parallel Searches with AsyncIO

> **Week 2 — OpenAI Agents SDK** · ⏱️ ~4m · 🎥 Lecture 45 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49820805

---

## 🎯 Ek Line Mein (TL;DR)

Deep research agent ka **final run** complete hua — pehle **3 parallel searches**, phir number ko **20 searches** tak scale karke ek zyada **substantive HTML email report** mili, aur **trace** me clearly dikha ki **asyncio** ne saare search agents **parallel** chalaye jabki **writer** aur **email agent** **sequential** rahe.

---

## 📝 Hinglish Explanation (Detailed)

- **Pipeline successfully complete hua:**
  - Pichle lecture wala run **3 searches** ke saath finish hua — terminal me "hooray" (success) print hua.
  - End result: ek **well-formatted HTML email** mili — achha **introduction/overview**, detailed analysis, aur bottom me **references with clickable links** (HTML email hai isliye links kaam karte hain).
  - Ed ne note kiya ki report me **CrewAI** top pe aaya — jo coincidentally **next week ka topic** hai.
  - Results me **couple of misses** the, par overall kaafi achha output.

- **Minimal scaffolding, maximum potential:**
  - Ed ka key point: **bahut hi kam code** se ye poora **deep research framework** ban gaya — "that's all there is".
  - Results bhale hi **simplistic** ho, par jo architecture banaya hai (planner → parallel searchers → writer → emailer) usme **expand karne ki bahut potential** hai.

- **Scaling up: 3 → 20 searches:**
  - Sabse simple expansion: **`HOW_MANY_SEARCHES` number turn up** karna.
  - Caution: har search **few cents** cost karti hai (OpenAI ka **WebSearchTool** paid hai — 2.5 cents per call), isliye students ke liye optional.
  - Ed ne number ko **20** set kiya, **planner agent recreate** kiya (kyunki instructions me search count baked hai), sab cells **rerun** kiye.
  - 20 searches me thoda zyada time laga, par output **clearly better**:
    - Same **key frameworks** identify hue, par har framework ke saath **applications and benefits** add hue.
    - End me **commercial implications** aur ek proper **conclusion** — pehle wale se "**a step up**", zyada **substantive**.

- **Trace me parallelism dekho (proof of asyncio):**
  - **OpenAI Traces** dashboard me research trace kholo:
    - **Planner agent** pehle akela chala (sequential start).
    - Phir **saare search agents ek saath, parallel** chale — trace me horizontally overlap karte dikhte hain.
    - End me **writer agent** aur **email agent** **sequentially** chale (kyunki unhe pehle saare search results chahiye).
  - Ye visual proof hai ki **`asyncio.gather()`** ne searches ko **concurrently** fire kiya — total time ≈ slowest search, not sum of all.

- **Homework / aage ka raasta:**
  - Socho: is deep research agent ko **more substantive** kaise banaoge? Kya beef up karoge? (e.g., multi-round search, follow-up queries, better planner, structured citations…)
  - **Kal (Day 5)** ka plan: isi ko ek **proper application** me daalna — ek "takeaway" deep research agent jo tum apne use ke liye le ja sako.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Deep Research Agent** | Multi-agent pipeline: planner → parallel web searches → writer → email — jo kisi topic pe detailed report banata hai |
| **AsyncIO parallel execution** | `asyncio.gather()` se saare search coroutines ek saath chalana — total time sum nahi, max hota hai |
| **Sequential vs Parallel steps** | Searches parallel chal sakti hain (independent), par writer/email sequential hain (unhe pehle saare results chahiye) |
| **HOW_MANY_SEARCHES** | Planner ke instructions me baked search count — 3 se 20 karne pe report zyada substantive ban jaati hai (par cost badhti hai) |
| **Trace (OpenAI Traces)** | Dashboard view jisme har agent ka timeline dikhta hai — parallelism visually verify kar sakte ho |
| **WebSearchTool cost** | OpenAI ka hosted search tool ~2.5 cents/call — isliye 20 searches = noticeable cost, free nahi hai |
| **HTML email output** | SendGrid se bheji gayi formatted report — headings, analysis, aur clickable reference links ke saath |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Trace = distributed tracing for agents.** Jaise aap Jaeger/Zipkin me ek request ke spans dekhte ho — parallel DB calls overlap karte hue aur downstream call unke baad — waise hi OpenAI trace me planner span pehle, search spans overlapping (parallel), aur writer/email spans end me sequential dikhte hain. Fan-out/fan-in pattern bilkul `asyncio.gather()` + final aggregation jaisa hai jo aap API aggregator services me likh chuke ho.
- **Scaling knob = config-driven behavior.** `HOW_MANY_SEARCHES` ko 3 → 20 karna waisa hi hai jaise worker pool size badhana — throughput/quality badhti hai par **cost linearly scale** hoti hai (har search = paid API call). Production me iska budget guardrail (max searches cap) zaroor rakhoge.
- **Parallel sirf independent steps ke liye.** Searches embarrassingly parallel hain, par writer ko saare results chahiye — ye classic DAG dependency hai (jaise Celery chord: parallel tasks → callback). Agent pipelines design karte waqt yahi socho: kaunse nodes independent hain, kaunse join points hain.
- **Hands-on lab:** is lecture ka code khud chalane ke liye ye lab run karo — `Practical/lab4_deep_research.py` (is repo me, `uv run` se chalta hai, **Groq pe free**). Note: hamare labs OpenAI ki jagah **free Groq** use karte hain (`OpenAIChatCompletionsModel` + `base_url` trick), aur lecture me jo **paid cheezein** hain — **WebSearchTool** (2.5¢/search), **SendGrid email**, aur **OpenAI trace dashboard** — unki jagah lab4 **free Wikipedia search tool** use karta hai aur output console pe print hota hai. Parallelism wala concept (`asyncio.gather`) lab me bhi same hai, bas bina cost ke.

---

## 🧠 Takeaway (yaad rakho)

1. **Minimal code, full framework** — sirf planner + parallel searchers + writer + emailer se ek working deep research agent ban gaya; agentic patterns me scaffolding chhota hota hai, power LLM + orchestration me hai.
2. **Search count badhao = quality badhao (with cost)** — 3 → 20 searches se report me applications, benefits, commercial implications add hue; har search paid hai, isliye consciously scale karo.
3. **Trace me parallelism verify karo** — planner sequential, searches parallel (overlapping spans), writer/email sequential — ye asyncio fan-out/fan-in ka visual proof hai.
4. **Dependencies decide karti hain kya parallel ho sakta hai** — independent searches parallel; writer ko saare results chahiye isliye wo join point hai.
5. **Next step:** is pipeline ko ek real application (takeaway deep research agent) me wrap karna — Day 5 ka topic.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Okay. It did indeed finish. It completed its three searches. It ended with hooray, which is success. And I received an email. And here it is. A nice HTML email, well formatted with a good introduction and overview, detailed analysis. CrewAI it's now putting at the top, which is in fact what we'll be doing next week. Look forward to that. And then there's generally some great information here. I would say that there's a couple of misses, but it's generally done pretty well. And then at the bottom are some references with links since it's an HTML email. And if I click on that it does appear to work, which is nice.

And I will say, I do find it very satisfying that with this minimal scaffolding with something that was really very simple indeed, there's not much code to this look. That's all there is with just this. We were able to build this whole deep research framework. And whilst, you know, maybe those those results are reasonably simplistic, I hope you appreciate how much potential there is with what we've just built, and can think of all the different ways that we could expand on this.

And in fact, one very simple way we can expand on this is just to turn up that number, which you may not want to do, because as I say, it will cost that few cents a piece, but there's no reason why I can't do it for you so that we can get some to show you what it looks like to have that deeper kind of research. So I will do that right now. We will change that to 20 and, uh, go through and make sure that we, um, hang on if I just set that properly. Yes, I have that has now recreated that planner agent. So now we will come back down here and just make sure that we rerun everything and rerun this. And now we will expect to do rather a lot more searches, 20 more searches. And this may take a moment longer and then I will come back and show you what results we get.

And that is completed after 20 searches. And I can show you the results, which actually it looks generally a bit similar. It's got the same key frameworks, but it's got more information laid around it. It has applications and benefits associated with each of the frameworks that I identified. And then it has some commercial implications at the end and a conclusion. And so it's certainly more substantive than the previous one. It's a step up. And obviously, should you wish, I would very much recommend that you experiment with this.

And we should also, of course, go in and look at our trace. And if we come in to the research trace, we will see that all of these agents ran and they all ran in parallel. The planner agent took took took that time to start with. Then there's load more. There's all of this and more. And then at the end was the writer agent and the email agent. So you can see everything. And it definitely gives you that sense of how asyncio ran all of these different searches in parallel at the same time. And then, of course, the writer and email were sequential.

And that then is the conclusion of this part of the deep research agent. The thing I'd like you to do is bear in mind, have a think about how you could make this more substantive. What more could be done? What would you like to do to beef this up? And then we'll do a quick wrap up before we launch into tomorrow. So I really hope you enjoyed that as much as I did, and that you appreciate how simple it was to build that framework around a deep research agent in your deeply puzzling over how you can make it better. But actually, what we're going to be spending tomorrow doing is putting this into an application and having it be something that is like a takeaway deep research agent. And I'm very excited for it. And I will see you then.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
