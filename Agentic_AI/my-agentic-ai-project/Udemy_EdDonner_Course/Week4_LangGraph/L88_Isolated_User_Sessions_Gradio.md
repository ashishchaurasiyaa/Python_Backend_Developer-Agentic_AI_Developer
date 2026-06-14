# L88 — Day 5: Isolated User Sessions in Gradio

> **Week 4 — LangGraph** · ⏱️ ~6m · 🎥 Lecture 88 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821435

---

## 🎯 Ek Line Mein (TL;DR)

Sidekick ka `app.py` tour — Gradio **callbacks** ka plumbing samjho, aur sabse important: **`gr.State`** use karke har user/browser-tab ko apna **alag Sidekick instance** (apna graph + apna Playwright browser) milta hai, taki multiple users ek hi global variables share na karein.

---

## 📝 Hinglish Explanation (Detailed)

- **`app.py` — sirf 2 imports**: `import gradio` aur `from sidekick import Sidekick` (humari class). Matlab saara LangGraph logic `sidekick.py` me encapsulated hai, UI layer bilkul thin hai.
- **Gradio app structure — `gr.Blocks`**: Blocks ke andar tum **fields** create karte ho — yahan ek **chatbot field** (jahan Sidekick ke replies dikhte hain), **message** textbox, **success criteria** textbox, ek **Go button** aur ek **Reset button**. (Ye Gradio class nahi hai, isliye Ed deep nahi jaata — bas intuition chahiye.)
- **Callbacks hi sab kuch hai**: Gradio ka mental model — har UI event ek **callback** hai. E.g. `go_button.click(fn, inputs, outputs)` — Go click hua → ye function call hoga, ye inputs milenge, return value in outputs me jayegi. Ek baar ye click ho gaya, pura Gradio "callbacks ki wiring" jaisa dikhne lagta hai.
- **Frontend vs server**: UI khud **browser me render/run** hota hai (frontend generated), lekin har callback **wapas tumhare actual server pe** call hota hai jahan Python chal raha hai. Classic client-server split.
- **`load` callback — session ka entry point**: Jab nayi screen load hoti hai (new browser tab/user), Gradio ka **`load`** event fire hota hai. Yahan hum apna **`setup`** callback call karte hain, jo ek **`Sidekick` instance return** karta hai.
- **`gr.State` — the big idea**: `setup` ka return value ek **state object** me store hota hai. `gr.State` ka matlab: ye variable **us particular user/screen ke saath associated** hai — tum ise callbacks ke through set karte ho aur callbacks me provide karte ho. Har user ka apna copy.
- **`delete` callback — resource cleanup**: Ed ne ek **delete callback** bhi register kiya hai jo `free_resources` call karta hai — taki session khatam hone pe us session ka **Playwright + Chromium browser** properly band ho jaye (warna har user ek zombie browser chhod jayega).
- **Ed ka confession — LLM Engineering course wala bug**: Apne purane Gradio projects (LLM engineering course ke final big project samet) me Ed ne `gr.State` properly use nahi kiya tha — matlab **multiple screens/users same global variables share** kar rahe the. Single-user ke liye chalta hai, lekin agar app deploy karo to users ek doosre ka state corrupt kar denge. Is baar carefully kiya gaya hai: **har user ko apna separate session + apne variables**.
- **`setup` callback kya karta hai**: Naya `Sidekick()` instantiate karta hai (init me bas lightweight prep), phir **`await sidekick.setup()`** — async method jo **bada kaam** karta hai: tools banana, **graph build karna** (nodes + edges wire karna), compile karna — graph **invoke hone se pehle**, kisi bhi **super-step** se pehle ke saare 5 steps yahin hote hain. Return hua sidekick → `gr.State` wale `sidekick` variable se hook ho jaata hai → UI load hote hi wo instance us session ka ho gaya.
- **Go button → `process_message`**: `go_button.click` callback **`process_message`** ko call karta hai with: user ka **message**, **success criteria**, aur pura **chat history**. Jo wapas aata hai wo **chat history** aur **sidekick state** dono me jaata hai.
- **State repopulate karna — shayad zaroori nahi**: Ed admit karta hai ki sidekick ko wapas state me daalna probably required nahi (object mutate hota hai, reference same rehta hai), lekin **consistency** ke liye aisa karna safer/cleaner lagta hai. Gradio experts isse pehchaan lenge.
- **`process_message` simple hai**: Bas Gradio se aaye inputs leta hai aur sidekick object pe **`run_superstep`** coroutine call karta hai (jo pichle lecture me dekha tha) — message, success criteria, history pass karke. Wo graph ka ek **super-step** run karta hai aur result user ko wapas return hota hai.
- **Notebook → app**: Ye wahi code hai jo notebook me tha, bas **zyada tools** aur thoda **built-out prompting** ke saath (Ed ko jo troubles aaye unhe handle karne ke liye — aur tumhe production me aur bhi karna padega). Ab is cheez ko chala ke dekhne ka time hai.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **`gr.Blocks`** | Gradio ka layout container — iske andar fields (chatbot, textbox, buttons) define hote hain |
| **Callback** | UI event → Python function mapping; e.g. `go_button.click(fn, inputs, outputs)` — Gradio ka core mental model |
| **`load` event** | Jab nayi screen/tab load hoti hai tab fire hone wala callback — yahan per-user setup hota hai |
| **`gr.State`** | Per-session variable — har user/screen ka apna copy, callbacks ke through set/read hota hai |
| **`setup` callback** | Naya `Sidekick()` banata hai + `await sidekick.setup()` — graph build (nodes/edges/compile) yahin hota hai |
| **`delete` callback / `free_resources`** | Session end pe resources (Playwright + Chromium browser) cleanup karne wala hook |
| **`process_message`** | Go button ka handler — message + success criteria + history leke `run_superstep` call karta hai |
| **`run_superstep`** | Sidekick ka coroutine jo graph ka ek super-step invoke karta hai aur results return karta hai |
| **Session isolation** | Har user ka alag Sidekick instance — shared globals nahi, warna multi-user me state corrupt |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **`gr.State` = server-side session store**: Ye bilkul Flask/Django ki session waali problem hai — globals me state rakhna ek worker, ek user tak hi safe hai. `gr.State` per-connection scoped object hai, jaise har request ke saath session dict aata hai. Ed ka "LLM engineering course me galat kiya tha" wala confession classic **shared mutable global state** bug hai jo single-user demo me kabhi nahi dikhta, deploy hote hi dikhta hai.
- **`delete` callback = context manager / `finally` at session level**: Har session apna Chromium process spawn karta hai — cleanup hook ke bina ye connection-pool leak jaisa hai (DB connections jo kabhi `close()` nahi hote). Lifecycle hooks (load → use → delete) ko `__enter__`/`__exit__` ki tarah socho.
- **Heavy init load pe, light handler pe**: Graph building (nodes, edges, compile, tools) `setup` me ek baar hota hai; `process_message` sirf `run_superstep` call karta hai. Ye wahi pattern hai jo aap app-startup pe DB engine/clients init karke request handlers me reuse karte ho — per-request graph rebuild mat karo.
- **Hands-on lab**: is lecture ka code khud chalane ke liye `Practical/lab4_sidekick.py` run karo (is repo me, `uv run` se chalta hai, Groq pe free via `langchain-groq` `ChatGroq`). Note: hamare labs course se thode alag hain — **Playwright browser-driving SKIP** kiya hai (heavy dep; sidekick lab me uski jagah safe sandbox file/python tools hain), LangSmith tracing skip, aur SerperDev ki jagah free Wikipedia search — to lecture wala Chromium-cleanup part lab me directly nahi dikhega, lekin `gr.State` per-session isolation wahi hai.

---

## 🧠 Takeaway (yaad rakho)

1. Gradio = **callbacks ki wiring**: UI browser me chalta hai, har event tumhare Python server pe callback hit karta hai (`go_button.click(fn, inputs, outputs)`).
2. **`gr.State` mandatory hai multi-user apps me** — global variables share karoge to har user ek doosre ka session corrupt karega; `load` event pe per-user `Sidekick` instance banao.
3. **Saara heavy kaam `setup()` me**: graph build, nodes/edges, tools — sab graph invoke/super-step se *pehle* ek baar; phir har message bas `run_superstep` call hai.
4. **`delete` callback se resources free karo** — har session ka Playwright/Chromium browser cleanup nahi kiya to process leaks milenge.
5. Sidekick ko wapas state me repopulate karna technically optional (same mutable object), par consistency ke liye Ed karta hai — defensible habit.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Okay, here we are looking at app dot py, which is our Gradio app. We only have two imports. Import Gradio and from sidekick. Import sidekick the class. And so uh, yeah, the idea is so. So this is the way that you build a Gradio app. Uh, you have, um, this blocks, um, and then you can create your fields. And as I said, it's not this isn't a gradio class. So I'm not going to go into too much detail. I want to give you some intuition that you create fields like a chatbot field, which is where we have our sidekick, we have our message and our success criteria, and we have a go button and a reset button, um, here.

And, uh, yeah, the thing I wanted to mention, the way that Gradio works is that you have a bunch of these callbacks that where you have things like, um, you have go button click, and that means if you click the go button, it will call this function, and it will call it with these inputs. And it will hook up these outputs. And when you get used to gradio, you see it all starts to click and you see how you can just simply think of everything in terms of these callbacks. And everything here is sort of generated and runs in the front end in a browser, except these callbacks are called back to your actual server that's running right here. And so that's how the whole thing works.

Now there is a callback called load, which is one that is called at the beginning when a new screen is brought up and loaded. And that's an important one for us here because that is when we're going to call a callback called setup, which is going to return something called sidekick. And that is a something that we're storing in the state of this gradio. So this is something the sidekick. It's a state. It means I'm going to set it through various callbacks, and I'm going to provide it in callbacks so that that's going to be associated with a particular user of this screen. Um, and I've also registered this delete callback free resources. And that's how I'm hoping to clean up this playwright and chromium browser that's running associated with this resource.

But because we've done it this way, we've done it quite carefully with Gradio, which I've I've not been careful with some of my prior Gradio projects. Also in the LLM engineering course, no one's called me on this yet. But but in the big thing we do at the end, I don't properly use gradio state, which means that if you brought up multiple screens or if you had different users trying to use your platform, and it is only intended to be used by the individual themselves, but you could get in trouble because everyone will be sharing the same like like variables. So this makes sure that different people using the screen, if you were to to supply this as an app, they would each have their own separate session with their own variables.

So in this case we initialize it by calling UI load. So if we go to the load callback sorry not not the it's called setup. It's the callback. Here it is uh setup. And what that does is it instantiates it creates a new instance of sidekick. And remember that that sets up it just has a bunch of of things in the init to get things ready. The big work is done in sidekick setup, the async method that we await right here. So that now populates all of the things in sidekick, including building the graph. So this is where all of the graph gets built. The nodes are put together. Everything happens here. These are all of the steps, the five steps that happen before the graph is invoked, before any super step. And then this callback returns sidekick. And that means that sidekick is hooked up to this, also called sidekick. This variable also because this is the state object associated with the session. So that means that the sidekick that we created right here gets associated whenever you load a user interface. That user interface is associated with this particular sidekick instance. Okay. Hope that made some sense. It doesn't need to make you just just get some intuition for it and understand the basic plumbing and that will that will be all that you need for now.

Okay. And then I just wanted to mention the big thing here is that there's a go button, and that go button says go on it. And if we look at go button.click we'll see what that does. It calls process message, which we're just going to look at in a second. That is a callback. And it calls that with the message that the user has just entered, which comes from from here, uh, with the success criteria which the user has entered, and with all of the chat history and what comes back needs to go to the chat history and to the sidekick object to make sure that we keep that updated in state. Uh, and so, uh, and I actually don't think you need to do this, but I feel like it's, it's, uh, more consistent to do it that way to, to repopulate that in the state. But if you're a gradio wiz, you know what's going on here, then? Probably like me, you know that this is probably not required. Um. But anyway, I digress.

This this is the process message. Uh, callback. It's perfectly straightforward. Uh, it takes everything that I just mentioned that's hooked up to to Gradio, and it simply calls the run super step method, a coroutine that we looked at just a second ago on our sidekick object. The thing that we that we instantiated so it calls run super step. It passes in the message, the success criteria and the history. And that is going to run a super step of our graph. And then it's going to return the results back to the user. And that that is the tour of the app. It's the same code that we had in the notebook, just with a bunch more tools, a bit of a built out prompting there to handle some some troubles that I had. And you will have to do a lot more, I'm sure. And with that, it's time for us to give this thing a drive.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
