# L78 — Day 3: Checkpointing — Memory Between Conversations

> **Week 4 — LangGraph** · ⏱️ ~9m · 🎥 Lecture 78 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821351

---

## 🎯 Ek Line Mein (TL;DR)

Reducers/state management ke bawajood graph ko **conversations ke beech memory nahi hoti** — kyunki har invocation ek alag **super-step** hai; iska solution hai **checkpointing**: ek **`MemorySaver`** banao, `graph.compile(checkpointer=memory)` karo, aur har invoke pe **`config = {"configurable": {"thread_id": "1"}}`** pass karo — bas, ab graph ko full conversation history yaad rehti hai, plus **`get_state_history`** + **checkpoint_id** se **time travel** (kisi bhi purane snapshot pe rewind/replay) bhi milta hai.

---

## 📝 Hinglish Explanation (Detailed)

- **LangSmith trace recap** — Ed pehle LangSmith me dikhate hain ki pichle run ka final GPT output trace ke bilkul neeche tha ("push notification with USD/GBP exchange rate sent") — yaani poore trace ka end wahan dikhta hai.
- **Problem demo — memory nahi hai:**
  - Chat me bolo *"My name's Ed"* → LLM: *"Nice to meet you, Ed"*. Phir poochho *"What's my name?"* → LLM: *"I don't have access to your personal information."*
  - Itna saara **state management**, **reducers**, clever structure — phir bhi **conversations ke beech koi memory nahi**!
- **Kyun? — Super-steps ki wajah se:**
  - **Har invocation = ek fresh, separate invocation.** State sirf **ek invocation ke andar** manage/maintain hota hai.
  - State management ka asli purpose: ek hi graph run me **multiple nodes parallel** chal sakein aur state poore graph me **reproducible** tareeke se flow kare. Ye power **within one super-step** ke liye hai.
  - **Alag-alag super-steps ke beech** ye kuch nahi karta — har super-step graph ki ek alag invocation hai.
- **Solution = Checkpointing** — yahi memory add karne ka tareeka hai:
  - Ed admit karte hain ki LangGraph kabhi-kabhi **heavyweight** lagta hai, par checkpointing wo moment hai jahan unko "I get it" feel hua — **elegant, simple, robust, repeatable**.
- **Step 1 — `MemorySaver` object banao:**
  - Naam confusing hai — iska matlab "memories save karna" nahi, balki **in-memory store me save karna** (disk ya database ke bajaye RAM me). Isliye "Memory"-Saver.
- **Step 2 — compile karte waqt checkpointer pass karo:**
  - Code **bilkul same** as before (Ed ne bas ek print statement add kiya inputs dekhne ke liye).
  - Sirf ek change: **`graph_builder.compile(checkpointer=memory)`** — wahi memory object pass karna. Graph diagram bilkul identical dikhta hai.
- **Step 3 — `config` dict with `thread_id`:**
  - Thoda "hacky/hokey" lagta hai, par pattern fixed hai: **`config = {"configurable": {"thread_id": "1"}}`**.
  - **`thread_id` ≠ technical OS thread** — ye ek **conversation thread** hai, memories ki ek grouping/slot jo aapas me connected rehni chahiye.
  - Graph invoke karte waqt **`config` pass karna zaroori** — tabhi invocation memory ke sahi slot se associate hoti hai. **Bas itna hi hai!**
- **Demo — ab memory kaam karti hai:**
  - *"Hi there"* → *"Hello!"*; *"My name is Ed"* → *"Nice to meet you, Ed"*; *"What's my name?"* → **"Your name is Ed."** 🎉
  - Print statement se dikhta hai ki har call pe **full history** inputs me ja rahi hai — yahi checkpointing in action hai, **har super-step ke beech memory maintain**.
- **"Big deal kya hai? Ye to global list of dicts se bhi ho jata"** — Ed ka jawab — asli power yahan hai:
  - **`graph.get_state(config)`** → ek **StateSnapshot** milta hai jisme messages + ab tak ki **complete conversation history**.
  - **`graph.get_state_history(config)`** → **har step in time** ka complete snapshot — har super-step, har invocation ka — **most recent top pe**, phir back in time.
- **Time Travel (LangGraph ka official naam):**
  - Config me `thread_id` ke saath ek **`checkpoint_id`** bhi pass kar sakte ho — kisi **previous moment pe rewind** karke wahan se graph **replay** kar sakte ho.
  - Matlab: **repeatable + robust systems** — agar kuch fail ho jaye, **kisi bhi snapshot se restart** kar sakte ho, aur har cheez ka **full tracking** milta hai. Simple but elegant abstraction.
- **Proof — ye Gradio ka kamaal nahi hai:**
  - Gradio UI ko **relaunch** karo (fresh UI), bolo *"hi there"* → *"hi again"* — **memory abhi bhi hai!** Ye Gradio ke chat UI variables me stored info nahi (jo pehle hamesha use karte the), balki **memory object ke andar checkpointing** hai.
- **Reset karna:**
  - **Naya `MemorySaver`** banao → graph **rebuild/recompile** karo with new memory → chat firse lao → *"What's my name?"* → nahi pata. Naya memory object = sab kuch reset.
- **Multiple threads:**
  - `thread_id = "2"` karo → *"What's my name?"* → nahi pata (alag thread, alag memory slot).
  - Wapas `thread_id = "1"` → *"Hi there"* → *"Hello again"* — **purani memory wapas!**
  - Dono threads ke **checkpoints alag-alag** dekh sakte ho, same structure se.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Super-step** | Graph ki ek complete invocation — state sirf iske **andar** manage hota hai, do super-steps ke beech nahi |
| **Checkpointing** | Har super-step ke baad state ka snapshot save karna — yahi conversations ke beech **memory** deta hai |
| **`MemorySaver`** | In-memory (RAM) checkpointer — "memory me save karne wala", disk/DB wala nahi |
| **`checkpointer=memory`** | `graph.compile()` me pass karna — bas itne se checkpointing on ho jati hai |
| **`config` dict** | `{"configurable": {"thread_id": "1"}}` — har invoke pe pass hota hai |
| **`thread_id`** | Conversation thread ka ID (OS thread nahi) — memory ka kaunsa slot use karna hai |
| **`graph.get_state(config)`** | Current **StateSnapshot** — messages + complete history |
| **`graph.get_state_history(config)`** | Har super-step ka snapshot, time me peeche jaate hue (latest first) |
| **`checkpoint_id`** | Config me pass karke kisi **purane moment** pe rewind kar sakte ho |
| **Time Travel** | LangGraph ka official naam — kisi bhi past snapshot se graph ko **replay/restart** karna |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Checkpointing = event sourcing, global variable nahi** — ek dict me history rakhna to "DB snapshot overwrite" jaisa hai; LangGraph har super-step ka **append-only snapshot log** rakhta hai (`get_state_history`), isliye aapko free me **audit trail + point-in-time recovery** milta hai — bilkul Postgres PITR ya Kafka offset rewind jaisa. `checkpoint_id` se replay karna = consumer offset reset karke messages re-process karna.
- **`thread_id` = session key** — wahi role jo web app me session ID/Redis session key ka hai: ek hi compiled graph (stateless app server jaisa) multiple conversations serve karta hai, state checkpointer (session store) me `thread_id` se partition hota hai. `MemorySaver` ≈ in-process dict session store (restart pe gone); production me SqliteSaver/Postgres checkpointer = Redis-backed sessions.
- **Failure recovery angle:** "kisi bhi snapshot se restart" wahi pattern hai jo aap retry-able background jobs me chahte ho — job crash hua to last checkpoint se resume, poora pipeline rerun nahi. LangGraph ye orchestration-level pe free deta hai.
- **Hands-on lab:** is lecture ka code khud chalane ke liye `Practical/lab2_tools_checkpointing.py` run karo (is repo me, `uv run` se chalta hai, LLM Groq pe free via `langchain-groq` `ChatGroq`). Note: lecture me Ed LangSmith trace dikhate hain — hamare lab me LangSmith tracing skip hai (key nahi), aur paid SerperDev search ki jagah free Wikipedia search use hota hai.

---

## 🧠 Takeaway (yaad rakho)

1. **Reducers ≠ memory** — state sirf **ek super-step (invocation) ke andar** flow karta hai; conversations ke beech memory ke liye **checkpointing** chahiye.
2. Recipe sirf 3 cheezein: **`MemorySaver()`** banao → **`compile(checkpointer=memory)`** → har invoke pe **`config = {"configurable": {"thread_id": "1"}}`**.
3. **`thread_id`** = conversation ka memory slot — alag ID = alag fresh conversation; wapas purani ID = purani memory wapas.
4. **`get_state`** se current snapshot, **`get_state_history`** se har super-step ka snapshot — aur **`checkpoint_id`** pass karke **time travel** (kisi bhi past point se replay).
5. Naya `MemorySaver` object banake graph rebuild karo = **full reset**; memory Gradio UI me nahi, **checkpointer object** me rehti hai.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

And I've come into LangSmith one more time just to show you. I think I've read from the wrong place that the final output from GPT was right down here. I have sent you a push notification with the current USD GBP exchange rate. So that's where you saw the end of the whole of the trace right down at the bottom there.

Okay, so here we are back in this chat. And now let me just show you something. Despite its incredible intelligence with this conversation, what we can now say is, uh, my name's Ed. Uh, nice to meet you, Ed. How can I assist you today? And I can say, what's my name? And it says I don't have access to your personal information. Uh, so I use this as a way of showing you that, uh, despite the fact that we have all of this state management, despite the fact that we've we've built up this, this, um, these reducers and this clever structure, it doesn't have any memory. It doesn't have the ability to remember between the different conversations.

And you might be thinking, well, I guess you're not thinking because I explained it already, but but if I hadn't explained it, you might be thinking. But but hang on. Uh, why? Uh, we've got all these reducers. We've got all of this stuff to handle state and to add in state. Then why, why isn't it, why isn't it just naturally remembering what's happening? And yes, it's all down to super steps. The point is that every invocation, every time we call this graph, it's like a separate fresh invocation and state is managed and maintained within any one invocation. That's what that's what it's there for. It's to handle so that you could have multiple nodes running in parallel. You could have all sorts of stuff happening, and the state would be managed through the whole graph in a, in a reproducible way. That's the power of the state management part. But that doesn't help you between separate super steps. Each super step is a different invocation of the graph. And the way that you do this is you use checkpointing. That's how you add memory.

Well, I have to tell you, I have some misgivings about LangGraph from time to time. How heavyweight it can be on occasion with some of the things we have to learn. But this is one case where I am very impressed indeed, and it's a moment for me when I get it. I realise why people like this so much and I can really appreciate the power of it. Checkpointing is very elegant, very simple and it leads to robust, repeatable processes. And you will see that too. And I imagine you'll be impressed like me at the end of it.

So we begin by creating a new object called MemorySaver. And a memory saver doesn't mean like a saving memories. It's talking about saving to to to in-memory stores, to in-memory, rather than to disk or to to a database. It's a bit confusing. So that's what MemorySaver means then. This is the same code we had before. Exactly the same code. I put in a print statement so we can see what it's doing and otherwise. The only change is when we compile the graph, we pass in checkpointer equals memory. We're passing in that memory object. But there's our graph. It looks identical exactly the same.

And now this is where we actually run the code. There's a little bit of stuff here which is a bit hacky a bit hokey, but but the the idea is you have to create this object called config. It's a dictionary with one field configurable, and then that field you have to put in a thread ID and thread ID doesn't mean like a technical thread, it's meant to be like a conversation thread, like it's something that refers to this, this thread of memories that needs to be connected together. And so that's how you specify that, that this is this particular grouping in memory. And then when you invoke the graph you have to pass in that config. That's how you make sure that when you're invoking the graph, it's being associated with the right sort of slot in memory. And that is all there is to it.

So with that, let's bring this up and we say hi there. Hello. How can I assist you today? My name is Ed. Nice to meet you, Ed. How can I help you? What's my name? I think it's gonna get it. Your name is Ed. How can I help you further? Ha, ha. And no surprise, you can see down here the print statement that I mentioned is printing out the the, uh, the inputs. And we're getting the full history each time, and that is all there is to it. That is checkpointing in action, maintaining memory between each of the calls, each of the super steps.

Now, I know what you're thinking. You're thinking, okay, what's the big deal? Why are you so impressed by this? I mean, it's just like you could also get there just by storing that list of dicts. Or we could take it from Gradio UI here and put it in a global and keep playing it in. Well, look, look at some of this stuff. So you can call graph.get_state. Given that the the config and we get back this thing called a state snapshot, and this has in it the messages and then the complete history the conversation so far. Yeah. All right. So so it's like a, like a global that that has this in it. But there's more you can get get_state_history for our config. And what we get now is each step in time, every super step, every time we invoke the graph, the complete, uh, snapshot at that moment, starting from most recent at the top and then going back in time.

And this is where it gets cool. And it's not like it's super sophisticated, but it's definitely a cool construct. LangGraph allows you to step back in time to any prior moment. When you're passing in that config, the configurable thread ID you can pass in a checkpoint ID to kind of rewind to a previous moment, and then replay that through the graph. Uh, and this, this gives you this ability to basically do what they call a time travel. That's the LangGraph official name for it, which is really to be able to move back, get your snapshot at any point in time and be able to rerun it from there. And this is this is really great because it allows you to build systems that are repeatable and robust. If something falls over, you can restart it from any snapshot, any point in time. And you've got this kind of full tracking on everything that happened. So yeah, it's it's it's simple but it's elegant. And this is a case of, of an abstraction that really makes sense to me. Uh, and is definitely something that I think is very valuable.

And I just want to show you as well that this has got nothing to do with, with Gradio and with kind of variables. I can come back in and I can I can just relaunch my Gradio UI right here and I can say like, hi there. It says hi again, and I was going to say, what's my name? But I don't need to. You can see right away it's got the memory. It's still got that memory. It's got nothing to do with the the information stored in Gradio's chat UI, which is what we've always used in the past with, with Gradio, but rather it is the memory, the checkpointing that's happening inside this, uh, this memory object.

And then I can actually I can come back and if I recreate, I can I can create a fresh new MemorySaver object and come in and then I have to re rebuild my graph with, with, uh, the new memory right there and then re bring up my chat interface. And now if I say uh hi there. And what's my name. It's obviously not going to know it. So that just explains that by recreating a new memory object we've reset everything. And that's, that gives you a good sense of what's going on. My name's Ed. Nice to meet you. How can I assist you today? Uh, what's my name? Just to prove the point, your name is Ed.

And then let me just show one more thing here. We can also change the thread ID to two. Let's rerun this and, uh, take a look here. Say hi there. Hello. How can I assist you? What's my name? And it says it doesn't know because the thread is two. If we now go back to the thread is one. I know you get this, but it's worth saying. And now. Hi there. Hello again. Ha ha. So there. You see it? It's a nice, elegant. It's it's relatively lightweight and simple, but very powerful. And that's a nice combination that I can get behind. And you can come in and look of course at the different checkpoints for either thread number one or thread number two. Uh, using the same this, this same structure.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
