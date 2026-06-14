# L47 — Day 5: Deep Research App — Gradio to Visualize & Monitor

> **Week 2 — OpenAI Agents SDK** · ⏱️ ~4m · 🎥 Lecture 47 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49820809

---

## 🎯 Ek Line Mein (TL;DR)

Deep Research app ko **`uv run deep_research.py`** se launch karke **Gradio UI** me live chalaya — `yield` se aane wale **status updates** UI me real-time dikhte hain, **20 searches parallel** me (asyncio) complete hoti hain, aur final **markdown report** seedha Gradio me render hoti hai + **trace** me poora agent pipeline visible hai.

---

## 📝 Hinglish Explanation (Detailed)

- **Setup — terminal aur uv:**
  - VS Code me naya terminal kholo (`Ctrl + backtick`, ya View menu → Terminal).
  - `cd` karke `2_openai` directory me jao, phir uske andar `deep_research` directory me.
  - Yahan plain `python deep_research.py` **mat** chalao — hum **uv** use kar rahe hain, isliye **`uv run deep_research.py`** chalao. `uv run` guarantee karta hai ki script **sahi virtual environment** ke andar chale (dependencies correct version ke saath).

- **Gradio UI launch:**
  - Run karte hi browser me **Deep Research screen** (Gradio UI) pop up hoti hai.
  - Ed ek research topic type karta hai: *"What are some of the most exciting commercial applications of autonomous agentic AI as of April 2025?"* — aur **Run** dabata hai.

- **Live trace link:**
  - Run karte hi UI me sabse pehle **"View the trace"** link dikhta hai — click karne par OpenAI Traces dashboard khulta hai jahan execution **live, beginning se** dikhna start hota hai.
  - Shuruaat me trace me kam dikhta hai kyunki pipeline abhi early stage me hai — jaise-jaise agents chalte hain, trace populate hota jaata hai.

- **`yield` se real-time status updates (is lecture ka core idea):**
  - Gradio UI me status messages appear hote hain ("planning searches...", "searching...", "writing report..." type updates).
  - Ye isliye possible hai kyunki humne apne **run coroutine** me har stage par **`yield`** kiya tha — har yield ek update ko **callback ke through Gradio tak surface** kar deta hai.
  - **Yahi reason tha yield use karne ka** — warna user blank screen ke saamne baith kar wonder karta ki andar kya chal raha hai. Long-running agent workflows me **progress visibility** UX ke liye critical hai.

- **Parallel searches — asyncio ka magic:**
  - **20 searches** dekhte hi dekhte complete ho gayin kyunki wo sab **parallel** me chali — `asyncio.gather` wala pattern jo pichle lectures me banaya tha.
  - Phir **writer agent** report likhta hai, aur uske baad **email agent** report email karta hai.

- **Result seedha Gradio me:**
  - Is baar email check karne ki zaroorat nahi — final report **Gradio app me hi beautiful markdown format** me render hoti hai.
  - Report me mila: introduction/overview, **cybersecurity** (threat detection, reduced workloads), **customer service**, **healthcare**, **automotive & transport**, **financial services** (market trends analyze karke real-time info par trades execute karna), **logistics & supply chain**, phir **ethical/regulatory** considerations, conclusions aur follow-up questions.

- **Trace verification:**
  - End me Ed traces dashboard me jaakar **research trace** dekhta hai — saare agents wahan visible hain, end me **writer agent** aur **email agent**, sab successfully run hue.
  - Ab ye ek **reusable deep research tool** hai jo aap khud use kar sakte ho.
  - Teaser: next lecture me discuss hoga ki ise **extend karke aur powerful** kaise banaya jaye.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **`uv run`** | Script ko sahi virtual environment ke andar chalata hai — plain `python` se environment mismatch ho sakta hai |
| **Gradio UI** | Python se quick web interface — yahan research topic input + live status + final markdown report dikhane ke liye |
| **`yield` (async generator)** | Run coroutine har stage par update yield karta hai; Gradio us stream ko UI me live dikhata hai |
| **Callback to Gradio** | Yielded updates callback ke through UI tak surface hote hain — progress visibility ka mechanism |
| **Parallel searches (asyncio)** | 20 web searches ek saath concurrently — total time ~1 search jitna |
| **Trace ("View the trace")** | OpenAI Traces dashboard ka link — har agent step (planner → searches → writer → email) live monitor karne ke liye |
| **Writer agent / Email agent** | Pipeline ke last steps — long markdown report likhna, phir use email karna |
| **Markdown rendering** | Gradio report ko formatted markdown me render karta hai — email kholne ki zaroorat nahi |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **`yield` se UI updates** = bilkul **SSE (Server-Sent Events) / streaming response** pattern jo aap FastAPI me `StreamingResponse` ya WebSocket se karte ho. Long-running job ko block karne ke bajaye async generator se progress events push karna — Gradio bas us generator ko consume karke UI repaint karta hai. Same mental model: **generator = event stream**.
- **20 parallel searches** wahi `asyncio.gather()` fan-out hai jo aap multiple downstream API calls ke liye use karte ho — I/O-bound LLM/search calls me concurrency almost free speedup hai. Sequential hota to 20x slow.
- **Trace dashboard** ko production observability ki tarah socho — jaise aap distributed tracing (Jaeger/OpenTelemetry) me request ka span-tree dekhte ho, waise hi yahan agent pipeline ka har step (planner → searches → writer → email) ek trace me dikhta hai. Multi-agent debugging ke liye ye must-have hai.
- 🧪 **Hands-on lab:** is lecture ka code khud chalane ke liye is repo me `Practical/lab4_deep_research.py` run karo (`uv run` se chalta hai, **Groq pe FREE**). Note: hamare labs OpenAI ki jagah free **Groq** use karte hain (`OpenAIChatCompletionsModel` + `base_url` trick), aur lab4 me OpenAI ke **paid `WebSearchTool`** ki jagah **free Wikipedia search tool** hai — isliye lecture wala SendGrid email step aur OpenAI traces dashboard lab me as-is nahi milega, par planner → parallel search → writer wala core deep-research flow same hai.

---

## 🧠 Takeaway (yaad rakho)

1. **`uv run script.py`** chalao, plain `python` nahi — tabhi sahi virtual environment guaranteed milta hai.
2. Long-running agent pipeline me **`yield` se status updates** stream karo — user ko kabhi blank screen par mat chhodo; Gradio in yields ko live UI updates bana deta hai.
3. **Asyncio parallelism** se 20 searches lagbhag ek search ke time me complete — agent workflows me fan-out hamesha concurrent karo.
4. **Trace dashboard** se poora pipeline (planner → searches → writer → email) verify karo — multi-agent system ka observability layer hai.
5. Final output **Gradio me markdown render** hota hai — email dependency optional ho jaati hai; ye ab ek reusable deep research tool hai jo aage extend hoga.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Okay, so first of all, we bring up a new terminal, which we do by pressing the control button and hitting the tick. And when we do that, up it comes. You can also get there by going to the view menu and choosing terminal. So we need to CD into the two OpenAI directory. And now we need to change again into the Deep Research directory because that's where our stuff is. And you might be thinking we now type Python deep_research.py. But that would not be right because we're working with UV. So you do UV and then run and deep_research.py because that will make sure that we're in our correct virtual environment. And that is what we do now. And it's then going to pop up a screen like this. This is our deep research screen. This is our Gradio UI. And make it a tiny bit bigger.

All right. What topic would you like to research? So how about this. How about we say, uh, what are some of the most exciting commercial applications of autonomous agentic AI as of April 2025? All right. That seems like a good question. Why not? Let's give it a whirl. Run!

So first of all, we get this popping up. View the trace. If we click there, it comes up and shows us it's just beginning. We're still at the very beginning stages. We'll hopefully in a moment see a bit more of what's going on. Not not yet. It's still in the early stages. What we're seeing here is an update appearing for what's going on, and that is because we are yielding these updates. And every time that we yield those updates in our run coroutine, that gets surfaced through to our callback and through to Gradio. And that's why it's appearing here because of those yields. That's why we did it. Otherwise we'd be sitting here wondering what's going on.

So it's already done the 20 searches, because they all happened in parallel, as you know, thanks to the magic of Asyncio. And now it is writing. It's written the report, it's now sending the email. And hopefully any moment now it will complete, which will be nice and we will get to see. And here it is. And we don't need to go to our email for a change, because it's all appearing here in the Gradio app and it's appearing in beautiful markdown format. It's got a nice introduction overview of autonomous agentic AI: cybersecurity, using it for threat detection, reduced workloads, customer service, obviously healthcare, automotive and transport, financial services, analyzing market trends and executing trades based on real time information. Maybe we're going to be doing some of that ourselves. Logistics and supply chain okay. And ethical. Regulatory. So now it's talking about about some of the sort of side effects or consequences and some conclusions and follow up questions. So there you have it. The result of our deep research right here for us to see.

Let's look at the traces and see how this is going now. This is the research trace. And sure enough there of course are our agents. And at the end is our writer agent and our email agent. It successfully ran. And this is now a tool that you can use and that you can refer to and have as a deep research tool. And there's still one more thing to talk about, which is how we can now extend this and make it more powerful.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
