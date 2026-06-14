# L81 — Day 4: AI Web Assistants — Playwright, LangChain & Gradio

> **Week 4 — LangGraph** · ⏱️ ~8m · 🎥 Lecture 81 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821367

---

## 🎯 Ek Line Mein (TL;DR)

Is lecture me Ed **Playwright browser tools** (LangChain ke ready-made toolkit se) + **push notification tool** ko ek **LangGraph agent** me bind karta hai, aur **Gradio chat UI** se ek aisa assistant banata hai jo khud browser drive karke CNN headlines aur USD/GBP exchange rate nikaal kar **push notification** bhej deta hai — har user input ek naya **super-step** hai aur history **checkpointing (memory)** se aati hai, Gradio history se nahi.

---

## 📝 Hinglish Explanation (Detailed)

- **Tools ko dictionary me organize karna:** Ed ek simple **dictionary comprehension** se Playwright ke tools list ko `{tool.name: tool}` dict me convert karta hai — taaki naam se **`navigate` tool** aur **`extract_text` tool** ko pluck kar sake. Ye pure Python hai, LLM ka koi role nahi.
- **Playwright tools ko directly test karna (bina LLM ke):** `navigate` tool ko **async** call karke CNN.com pe le jaata hai, phir `await` ke saath `extract_text` chalata hai. Screen pe ek **real browser window** khulti hai, CNN load hota hai, aur text extract ho jaata hai. Point ye hai ki **LangChain ke community tools** me Microsoft **Playwright** ka pura toolkit ready-made milta hai — "it's got nothing to do with AI, but it's just great technology."
- **Tools ka final collection:** Playwright ke saare browser tools + pichle lecture wala **push notification tool** — sab ek list me pack. Ab agent banane ka time.
- **LLM + bind_tools:** LLM ke roop me **GPT-4o mini** (apna favourite swap kar sakte ho). `llm.bind_tools(tools)` se LangChain har tool ke liye **JSON schema** auto-generate karke LLM ko de deta hai — ab LLM ko pata hai ki uske paas kaun-kaun se tools hain.
- **Chatbot node = sirf ek function:** LangGraph me **node bas ek Python function hai** jo **State** leta hai aur naya state return karta hai. Yahan chatbot function `llm_with_tools.invoke(messages)` call karta hai, result ko `messages` me daal kar return karta hai — aur **reducer** (`add_messages`) us naye state ko purane state ke saath **combine** kar deta hai (replace nahi, append).
- **Graph banana (5 familiar steps):**
  - `StateGraph(State)` se **graph builder** banao.
  - **chatbot node** add karo (upar wala function).
  - **ToolNode** ke through tools add karo.
  - **Conditional edge** lagao — ye behind-the-scenes ek **if statement** hai: agar LLM ne tool call maanga hai (**tools_condition** true) to `tools` node pe jao, warna end.
  - `tools → chatbot` wapas edge, aur `START → chatbot` edge.
- **"Agents" bola tha, par ek hi agent hai** — same diagram jo pehle dekha tha; fark sirf ye ki ab tools "meatier" hain: **agent ab browser window control kar sakta hai**.
- **Memory + compile:** **MemorySaver** checkpointer ke saath `compile(checkpointer=memory)` — aur graph ka image draw karke verify.
- **Gradio integration:** Gradio interface ka callback ek **async `chat` function** hai (Gradio async callbacks support karta hai). Ye sirf `graph.ainvoke()` (asynchronous invoke) call karta hai — user input ko initial state ke roop me pass karke, saath me **config (thread_id)**.
- **Super-step concept:** har user input = graph ka ek naya run = ek **super-step**. Important: Gradio apni `history` bhejta hai, par hum use **ignore** karte hain — kyunki conversation history **checkpointing** se aa rahi hai (`thread_id` ke against state restore hota hai).
- **Live demos:**
  - "Please send me a push notification with a news headline from CNN" → browser khud khulta hai, CNN navigate karta hai, hyperlinks extract karta hai, headline padhta hai, aur phone pe **push notification** aa jaata hai. Ed: "I'm not touching it!"
  - "Push notification with the current USD/GBP exchange rate" → browser exchange-rates page pe jaata hai, rate nikaalta hai (0.77, kal se thoda down), push bhejta hai.
- **Manus connection:** yahi pattern hai jo **Manus** jaise hyped "computer-using agents" ke peeche hai — ek agent jo browser drive karke aapka kaam kare. Isi direction me is week ka **big project (Sidekick)** ja raha hai.
- **LangSmith trace analysis:** trace me dikhta hai ki agent ne kitne interactions kiye — navigate, extract hyperlinks, read, phir push notification tool call. Ed ek **tool-design bug** bhi notice karta hai: push tool **`null` return** kar raha hai — better hota ki tool `{"status": "success"}` jaisa fake JSON return kare taaki LLM ke liye result "coherent" lage. (Lesson: **tools ko hamesha meaningful return value dena chahiye**.)
- **Cost reality check:** LangSmith me token count + cost dikhta hai — poori conversation ki cost sirf **0.8 cent** (GPT-4o mini). $0.10 wala number saare runs ka cumulative tha. **Ollama** use karo to free, par chhote local models se **coherence issues** ho sakte hain kyunki hum agent se kaafi expect kar rahe hain — bada model chahiye hoga.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Playwright toolkit (LangChain)** | Microsoft Playwright ke browser-control tools (navigate, extract_text, extract_hyperlinks, click...) jo LangChain community me ready-made milte hain |
| **Dictionary comprehension** | `{tool.name: tool for tool in tools}` — tools ko naam se lookup karne ka shortcut |
| **bind_tools()** | LLM ko tools ka JSON schema attach karna taaki wo tool calls generate kar sake |
| **Node** | LangGraph me bas ek function jo State leta hai aur naya/partial State return karta hai |
| **Reducer (add_messages)** | Naye state ko purane se combine karne ka rule — messages replace nahi, append hote hain |
| **Conditional edge / tools_condition** | Graph me "if statement" — LLM ne tool maanga to tools node pe jao, warna end |
| **ToolNode** | Pre-built node jo LLM ke tool calls ko actually execute karta hai |
| **Super-step** | Graph ka ek complete run — har user input ek naya super-step trigger karta hai |
| **Checkpointing (MemorySaver)** | thread_id ke against state save/restore — isi se conversation memory aati hai, Gradio history se nahi |
| **ainvoke()** | Graph ka asynchronous invoke — async Gradio callback ke andar await hota hai |
| **Tool return value design** | Tool ko `null` nahi, meaningful JSON (`success` etc.) return karna chahiye taaki LLM confuse na ho |
| **Manus** | Hyped "computer-using agent" product — browser drive karke kaam karne wala agent, yahi pattern |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Selenium/Playwright automation aap pehle se jaante ho** — naya twist ye hai ki click/navigate decisions ab hard-coded script nahi, **LLM runtime pe decide karta hai** (kaunsa link, kaunsa page). Socho: aapka E2E test framework, par "test steps" LLM generate kar raha hai.
- **Gradio history ignore karke checkpointer use karna** classic backend pattern hai — **client-supplied state pe bharosa mat karo, server-side session store (yahan thread_id-keyed checkpoint) hi source of truth hai**. Bilkul JWT-vs-server-session debate jaisa.
- **`null` return karne wala tool bug** ek achhi API-design lesson hai: tool = internal API endpoint for the LLM; `204 No Content` ki jagah explicit `{"status": "success"}` body do, warna "client" (LLM) ka behaviour incoherent ho jaata hai.
- 🧪 **Hands-on lab:** is lecture ka code khud chalane ke liye `Practical/lab4_sidekick.py` run karo (is repo me, `uv run` se chalta hai, Groq pe free via `langchain-groq` ChatGroq). Note: hamare labs course se thode alag — **LangSmith tracing skip** (key nahi) aur **Playwright browser-driving SKIP** (heavy dep — sidekick lab me uski jagah safe sandbox file/python tools hain); baaki graph + checkpointing flow same hai.

---

## 🧠 Takeaway (yaad rakho)

1. **LangChain community me Playwright ka pura browser toolkit ready-made hai** — navigate + extract_text ko bina LLM ke bhi async call karke test kar sakte ho.
2. **Same 5-step graph recipe** (State → nodes → ToolNode → conditional edge → compile with memory) — tools badle, architecture wahi: yahi LangGraph ki beauty hai.
3. **Har user input = ek super-step**, aur history **checkpointing (thread_id)** se aati hai — Gradio ki bheji hui history deliberately ignore hoti hai.
4. **Tools ko meaningful return value do** — `null` return karne se LLM ke liye flow incoherent ho jaata hai; fake `success` JSON bhi better hai.
5. **Browser-driving agent = Manus-style power** — poori conversation sirf 0.8 cent (GPT-4o mini); Ollama free hai par chhote models me coherence issues honge.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Okay. So next we're going to actually put these tools to good use. So this thing here is a neat neat little bit of Python called a dictionary comprehension. You might be very familiar with it. If not check out the guides. We put together a dictionary by iterating through tools and creating something where the key is the name of the tool, and the value is the tool itself, and that allows us to pluck out the navigate tool and the extract text tool from this list of tools. And we're then going to call the navigate tool asynchronously, navigate tool with the web address for CNN. And then we're going to call await to extract the text from it and call this. So this has got nothing to do with LLMs. This is all about running Microsoft Playwright with the tools that come with LangChain. And we'll run that. Up comes a browser, it turns to CNN and stuff is happening and that just completed. And isn't that cool? It was like, I know it's got nothing to do with AI, but it's just great technology. Come back here and we print the text and there we go. We've got the text from CNN. Impressive stuff.

So we can now package this together into one collection of tools. These tools that we just got from Playwright, plus our push notification tool — in it goes. And now it's time for us to make some agents. So the first thing we do is we do some, some pre-work to create our LLM, which is GPT-4o mini. Feel free to switch in your favorites. And then we bind it to tools. This you remember is what we do to deal with creating all of that JSON. For all of these tools. We've got a whole ton of tools now. JSON will be built for all of them. And now this is our chatbot function. This is something that is going to be one of our nodes. Because a node is just a function and it's something which will call — it will invoke LLM with tools passing in the messages. And what comes out will be shoved into messages and returned. And that, of course, is our — the new state, and the reducer will be used to combine it with the old state. So let's execute that. That's great.

And now we have our graph. I think this is probably makes more sense to go here just to be nice and tidy. So we create our graph builder with the state that we've specified. We add the chatbot node. That's this function we just got here. We add in our tools. We then add in a conditional edge. This is going to be the if statement implemented behind the scenes. If the tools condition is true then tools will be called. We add an edge from tools to chatbot and then we add from the start to the chatbot. So I said agents. It's only one agent. That's it. We get some memory. We compile with that memory and we draw our image. There it is. It's an image we're familiar with. It's the same as last time. The only difference is that these tools are a bit meatier than we had before. We now can control a browser window.

Okay, so here we have at the end our final, our Gradio, uh, flow. So we're going to create a Gradio interface. Um, we're going to use a function called chat as our callback. And here is chat. It's an async function. Gradio supports functions — its callbacks being being async. And it's um, we're going to to just simply call our graph that we've already built. We're going to call ainvoke, the asynchronous version. We pass in our first state, which is the user input. This is a super step. So every input is like another run of the graph. We pass in the config. So we have memory. We don't actually use the history because we're relying on checkpointing for that. But Gradio sends it to us anyway. And that is our Gradio code. And with that let's run it. There it is.

Okay. Let's say hi there. Okay. Let's say, uh, please send me a push notification. With a news headline from CNN. See what happens there. There goes the browser. It's — I'm not touching it. Haha. Have you expecting that? We got a text. I could see the push and it says indeed this push notification about news going on. Very cool. All right, let's try another. Uh, please, uh, send me a push notification with the current USD GBP exchange rate. The browser is still running behind. Let me just bring that up there. It's gone to an exchange rates page and we got the push notification. There he is. Yep. And it is a different than yesterday. Down by a little bit — 0.77 instead of 0.78. That's amazing.

So there you go. There you have it. Uh, that is a really powerful tool in Playwright. And isn't it amazing that we've now armed our agent to be able to drive a browser? And you can start to see when you think of the excitement people have around things like Manus and this idea of agents that can drive — you can now see how this could become an agent that can drive a browser and do work for you. And of course, that is what we're coming to for this week's big project.

And I thought it'd be nice to just bring this up in LangSmith for a second to show what it looks like. Uh, here we have it. Uh, you can see, if you look, that there was a fair amount of interactions that went on the process of going around the browser and and doing various things. It takes a little bit of interaction. It takes, of course, doing some navigation, navigating and reading. And if we look on the right, we can see what happened here. This is the human making that. So I said hi there. It said, hello. How can I assist you today. Please send me push notification and then you can see it uh it called to visit — navigate browser to CNN.com. So I think yeah I just said CNN so it knew to look up that that web page um and then it knew to navigate it, extracted hyperlinks. It looked at some hyperlinks, it did some stuff. And then it ended up sending a push notification. Uh, I noticed that I've got the tool returning just null, which is probably a bad thing. I should have it returning like some some fake JSON that says success or something so that it doesn't, uh — so, so that it just sort of lands better. It's more coherent with the, with the call of the tool. So I will make that change.

Uh, and then, um, you can see that it then goes to exchange rates, it pulls that out, it gets the results, it extracts all of the text. And then once more it sends a push notification. So it's great to see this trace. And then you can see some other information about this too. I think I got to see over here. Yep. The total number of tokens that were exchanged with GPT-4o mini. And the fact that the total cost was, uh, $0.10 out of — oh, no. That's from from all of the runs. I was going to say that would be expensive. Uh, and I've been doing a lot of runs, so, so so you should not have spent $0.10. Uh, that was, in fact, 0.8 of a cent for that whole conversation. Uh, and if you've been using Ollama, then it wouldn't have cost you anything, but you might have had more coherence issues because we're expecting a lot. You probably needed to use a larger model. Um, but certainly worth experimenting with. But if you chose to splash out and use GPT-4o mini, it would have cost you all of 0.8 of a cent. Uh, so, uh, you can see that these things — and obviously they can rack up over time if you use it extensively. But for any one given call, it is, uh, relatively low cost.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
