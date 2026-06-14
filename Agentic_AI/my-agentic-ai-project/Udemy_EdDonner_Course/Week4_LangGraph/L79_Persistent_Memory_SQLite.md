# L79 — Day 3: Persistent AI Memory with SQLite

> **Week 4 — LangGraph** · ⏱️ ~6m · 🎥 Lecture 79 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821359

---

## 🎯 Ek Line Mein (TL;DR)

**MemorySaver** (in-RAM) ko sirf **ek word change** karke **SqliteSaver** se replace karo — ab graph ka **checkpointing** ek **SQLite database** me jata hai, matlab kernel restart ke baad bhi agent ko **thread_id** ke basis pe poori conversation yaad rehti hai = **persistent memory**.

---

## 📝 Hinglish Explanation (Detailed)

- Pichle lecture me humne `MemorySaver` use kiya tha — wo **in-memory checkpointer** hai, process band hua to memory gayi. Ab Ed isse **SQL me store** karne wale hain — "next trick, last trick for today".
- Switch karna **bewakoofi level pe simple** hai: bas `MemorySaver` ki jagah **`SqliteSaver`** import karo, ek **`memory.db`** file se **connection** banao, aur graph compile karte waqt wahi checkpointer pass kar do. **Baaki code 100% same** — sirf variable ka naam/source change hua hai, approach bilkul wahi.
- Ed **thread_id** ko naya ID dete hain, kyunki SQLite file me unke **purane test runs ki memory** already saved hai — agar same thread_id use karte to purani conversation load ho jaati. Yaani: **thread_id = conversation ki key**, aur SQLite me wo key **process ke baahar bhi survive** karti hai.
- Quick test: "Hi there" → "What's my name?" → model ko nahi pata → "My name is Ed" bata diya. Ab asli demo shuru.
- **Asli proof — kernel restart:** Ed notebook ka **kernel restart** karte hain, **saare outputs clear**, sab kuch scratch se rebuild — imports, `load_dotenv`, **tools** (search + **Pushover** push-notification tool), **State object**, **graph builder** — sab fresh.
- Fresh process me "Hi there" bolte hi: **"Hello again Ed"** — agent ko naam yaad hai! Kyun? Kyunki directory me **SQLite database files** padi hain jisme saari state **checkpointed** thi. **Ek word change karke persistent memory mil gayi** — yahi impressive baat hai.
- Phir **tools + memory ka combined demo**: "Please send me a push notification with the current USD/GBP exchange rate" → agent search karta hai, **Pushover** se phone pe notification aata hai: **0.78**. Success.
- Memory test ke liye Ed bolte hain: **"Can you send that push notification again, please?"** — agent ne **dobara search NAHI kiya**, kyunki exchange rate already **conversation memory me tha**; usne sirf tool call karke wahi notification phir bhej di. Ek hi shot me **memory + tool calling dono** ka demo.
- **LangSmith verification:** trace me dikhta hai ki agent ne push-notification **tool use kiya**, search **skip kiya** (memory me answer tha), bottom me tool call + confirmation, aur upar **poori conversation history**. Jo chat me dikha, wahi trace me confirm hua.
- **Wrap-up picture (super-steps + checkpointing):** graph define karte ho → har interaction ek **super-step** hai → red lines = har super-step ke baad **checkpoint** save hota hai → isi wajah se hum **kisi bhi point se resume**, **state replay**, aur **time travel** kar sakte hain — aur ab ye sab **database me persist** hota hai, **thread_id** se keyed.
- Day 3 khatam — "meaty day". LangGraph ki **resilience, robustness aur discipline** ki feel aa gayi. Next: project **Sidekick** shuru hota hai.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **SqliteSaver** | Checkpointer jo state ko SQLite DB file me save karta hai — `MemorySaver` ka drop-in replacement |
| **MemorySaver** | In-RAM checkpointer; process/kernel restart pe sab kuch udd jata hai |
| **Persistent memory** | Conversation state jo process ke baahar (disk pe) survive kare — restart ke baad bhi yaad |
| **Checkpointing** | Har super-step ke baad graph ki state ka snapshot save karna |
| **thread_id** | Conversation ki unique key — isi se DB me sahi conversation ki state load hoti hai |
| **Super-step** | Graph ka ek execution round/interaction; har ek ke baad checkpoint banta hai |
| **Time travel / replay** | Kisi bhi purane checkpoint pe wapas jaake state dekhna ya wahan se resume karna |
| **Pushover tool** | Phone pe push notification bhejne wala tool — tool-calling demo ke liye |
| **LangSmith** | Tracing UI jahan tool calls, memory use aur poori history verify ki ja sakti hai |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Event sourcing vs DB snapshot wali analogy:** SqliteSaver har super-step ka checkpoint append karta hai — ye ek tarah ka **event-sourced state log** hai, na ki sirf latest-row snapshot. Isi liye "time travel" free me milta hai, bilkul jaise event store me kisi bhi event tak replay kar lete ho.
- **thread_id = session key:** ye web backend ke **session ID / Redis session store** jaisa hai — stateless process, state DB me, key se hydrate. Kernel restart = server pod restart; SQLite file = aapka session store. Production me SQLite ki jagah `PostgresSaver` socho (same interface, swap trivial).
- **Interface-driven design ka payoff:** `MemorySaver` → `SqliteSaver` ek-word swap isliye possible hai kyunki checkpointer ek **abstraction (BaseCheckpointSaver)** ke peeche hai — wahi DI/repository pattern jo aap service layer me karte ho.
- 🧪 **Hands-on lab:** is lecture ka code khud chalane ke liye `Practical/lab2_tools_checkpointing.py` run karo (is repo me, `uv run` se chalta hai, Groq pe free via `langchain-groq` ChatGroq). Note: hamare labs course se thode alag — **LangSmith tracing skip** (key nahi) aur **SerperDev ki jagah free Wikipedia search** use hota hai, baaki checkpointing flow same.

---

## 🧠 Takeaway (yaad rakho)

1. **`MemorySaver` → `SqliteSaver`** — bas import/connection change, baaki graph code bilkul same; persistent memory "one word change" me.
2. Memory **`thread_id` se keyed** hoti hai — wahi ID wapas do to kernel/process restart ke baad bhi conversation resume.
3. Har **super-step ke baad checkpoint** save hota hai — isi se **resume, replay, time travel** possible hai, ab DB me persisted.
4. Memory + tools saath kaam karte hain: agent ne **dobara search nahi kiya**, memory se rate uthake sirf push-notification tool call kiya.
5. **LangSmith** me trace dekh ke verify karo — kaunsa tool chala, kya skip hua, history kya thi.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

And now for my next trick. And our last trick for today. I'm going to switch it to store it in SQL instead. Our memory is going to be in a SQL database. And again this is impressive stuff. It's great that it's so simple and easy to switch to using SQL. We just import uh, this SqliteSaver instead. And uh we're going to write to a memory DB. We connect that way. Uh, we come in and it's just exactly the same code. But we're of course putting in the SQL memory instead of the memory before. I mean, it's just different name of a variable, but it's the exactly the same approach, uh, as we had before. Nothing different there at all. There we go. I'm going to make the thread ID a different ID because since it's SQL, it's kind of remember from my, my, my tests. Uh, but uh, then we can come in and we can say hi there and see. How can I assist you today? Uh, what's my name? And I don't have access. Uh, my name is Ed. Nice to meet you, Ed. How can I assist you today?

All right, so with that, uh, we can now go back here, and this time, we can just recreate the whole thing from scratch. It's like I could. I could restart my kernel. I should restart my kernel. Why don't I do that? You'll have to bear with me. We will clear. We will restart kernel, clear all outputs. We'll go all the way back up to the top, run our imports. We will load the dot env. Just check. I guess I should load in the tools again because we're going to use these do this, do this. Get the Pushover message me. My phone's on silent. Bring them together. Get our state object because we reuse that at various points. And now from this point onwards, I think now we can now go back here. So we're completely fresh. Uh, so now we're going to recreate this. We are going to rebuild our graph builder. There it is. And here we go. And hi there. Hello again Ed. Ha there you have it. Restart the kernel. Uh, completely bring everything fresh. And of course, it knows who I am. And it knows that because you can see right here in this directory, there's a bunch of database objects. It's storing it in a SQLite database. And so we have persistent memory with changing like one word uh from, from my code. And I think that is really impressive.

And I realized just before we, we closed this, I should also show that the tools are working and in action. So after saying this, I should let's do the same thing. Um. Please send me a push notification with the current USD GBP exchange rates. Let's let it do its thing. Off it goes. And I just got a push notification and it says 0.78. Ha ha ha! There we go. So, uh. Success. Uh, I think, um, maybe, uh. Interesting. Uh, what what if I say I can? I'm trying to think about how we can use memory as well. Can you send that? Can you send that push notification again, please? Let's try that. There we go. I got another push notification with the same thing. So there, there. I had to think for a moment. There's a demonstration of both memory and tool calling in one shot with the right answer. Success. And you can see the various calls happening down there. So that then is a wrap on this.

Um, and uh, it might be nice for us just to bring that up in LangSmith just to see those calls. And so here we are in LangSmith looking at that most recent request. And it's good to see that, as I was hoping to see it did use the tool to send the push notification. It didn't bother doing the search again because it had that in its memory. And you can see at the bottom here that it sends that push notification, and it then confirms back there that it did it as just as we saw in the chat. And you can see all of the history that it's got up above it. So you can see in LangSmith that true to its word, everything is working. The memory is working, the tool call is working. Uh, and it knew that it already knew the exchange rate. Uh, so I'd say that that is a success.

And to wrap up, let me show you one more time this great picture, which now I hope is lands nicely with you. We define our graph. We run each super step with each interaction, and these red lines are showing the checkpointing that's happening so that we can resume at any point. We can replay the state as it was. Then we can time travel back, and we can persist this in a database so that it maintains knowledge of the conversation. And it's keyed off this thread ID. And with that that concludes day three. And it was a meaty day. We covered a lot of ground. And I hope that you're building some of the same enthusiasms that I'm that I'm growing. As we get into this. For LangGraph, and seeing seeing the strengths, seeing how resilient, how robust it is, uh, and this, this discipline that it puts around the process. But that's enough of the, of the, of the learning and the concepts. Next time we launch into our project, our project called sidekick. And it's a really great one. I can't wait to show it to you. See you then.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
