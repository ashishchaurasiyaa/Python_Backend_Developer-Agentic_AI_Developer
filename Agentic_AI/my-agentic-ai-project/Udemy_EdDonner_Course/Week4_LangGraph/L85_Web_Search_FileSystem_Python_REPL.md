# L85 — Day 5: Add Web Search, File System & Python REPL

> **Week 4 — LangGraph** · ⏱️ ~6m · 🎥 Lecture 85 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821415

---

## 🎯 Ek Line Mein (TL;DR)

Sidekick project ka final day — agent ko **tools ka pura arsenal** milta hai: **Serper web search**, **push notifications**, **file system read/write**, **Wikipedia lookup**, aur **Python REPL** (bina Docker sandbox ke!) — Ed warn karta hai ki ye **experimental app hai, guardrails nahi hain**, apne risk pe chalao; code 3 modules me organized hai: `sidekick_tools.py`, `sidekick.py` (worker + evaluator + graph), aur `app.py` (Gradio UI).

---

## 📝 Hinglish Explanation (Detailed)

- **Day 5 of Week 4** — Sidekick project complete karne ka din. Ed bolte hain ki ye unka favourite project ban gaya hai aur ab wo **LangGraph ke full fan** hain.

- **Aaj ka theme: tools, tools aur more tools.** Sidekick agent ko ye sab capabilities milengi:
  - **Web search via Serper API** — browser navigate karna nahi, balki direct **web search** (Serper pehle bhi course me use hua hai, Week 2 me).
  - **Push notifications** — kyunki hum already jaante hain kaise bhejte hain (Pushover, Week 2 wala pattern).
  - **File system tool** — agent **files read/write** kar sake, taaki hamara "operator agent" / coworker actual deliverables (reports, files) bana sake.
  - **Wikipedia access** — cheezein look up karne ke liye.
  - **Python REPL** — agent **khud Python code run kar sakta hai**. Important: pehle (Week 3 me) Docker container me sandboxed tha, **is baar direct execution hai, no container**.

- **⚠️ Big warning — "use at your own risk":**
  - Sidekick ek **experimental app** hai, **guardrails nahi hain** — "open to the wild".
  - Hum agent ko apni machine pe **unfettered access** de rahe hain — "while we watch and while we monitor". Matlab human supervision mandatory hai.
  - Agar comfortable nahi ho to **Python REPL tool remove kar do**, aur even **browser navigation tools bhi hata do** jab tak samajh na aa jaye kya ho raha hai.

- **Safety boundaries jo built-in hain:**
  - Browser use karta hai to **Chromium** (Chrome ka open-source version) — **fresh instance**, tumhare **cookies, passwords (password manager), credit cards** ka access NAHI hai. Login nahi kar sakta.
  - **File manager ek specific directory ke andar restricted** hai — pure computer pe "roam free" nahi kar sakta.
  - **Python REPL sabse open/risky hai** — koi bhi Python chala sakta hai, theoretically damage kar sakta hai. Unlikely, but possible — isliye concerned ho to remove karo.

- **Sidekick = canvas, not product:**
  - Ed ne ise prompts + tools ke saath build kiya aur **real commercial work** isse karwaya — ek actual report produce hui jo unhone use ki. "It really works."
  - Lekin ye ek **starting point / canvas** hai — tumhe apne use-case ke hisaab se **tools add karne aur prompting tune karni** padegi.
  - Ed khud bolte hain: kabhi-kabhi agent **goes awry** (track se utar jaata hai), to prompts improve karne padte hain. **Experimentation required hai, aur wo pay dividends karta hai.**

- **"Build your own Manus" framing:**
  - Manus (Chinese startup ka famous agent product) jo apartments hunt karta tha, websites banata tha — Sidekick **tumhara apna version** hai jise **tum control karte ho**. Opportunity huge hai, but time + experimentation invest karna padega.

- **Code structure — 3 Python modules** (Cursor me, week 4 folder; notebooks nahi, proper **Python modules** — "which will please some people"):
  1. **`sidekick_tools.py`** — saare **tools ek jagah define** hote hain, nicely packaged. Agent ko "ton of tools" ka access yahin se milta hai.
  2. **`sidekick.py`** — ek **class `Sidekick`** jisme **worker, evaluator, aur graph building** ka code hai (worker-evaluator pattern jo pichle lectures me banaya). Ed admit karte hain ye module lamba hai, "maybe should be broken up a bit".
  3. **`app.py`** — **Gradio app**, UI side handle karta hai.

- Next lectures me Ed har module ka **walkthrough** karenge (code type nahi karenge, carefully read-through karenge).

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Serper API** | Google search results ka API — agent browser navigate kiye bina **web search** kar sakta hai |
| **Push notification tool** | Pushover-style notification bhejne wala tool (Week 2 pattern reuse) |
| **File system tool** | Agent ko ek **restricted directory** me files read/write karne ki capability |
| **Wikipedia tool** | LangChain community tool — agent Wikipedia pe lookup kar sakta hai |
| **Python REPL tool** | Agent ko **arbitrary Python execute** karne ki power — bina Docker sandbox ke (sabse risky tool) |
| **Unfettered access** | Bina guardrails ke machine access — isliye human monitoring zaroori |
| **Chromium** | Chrome ka open-source build — fresh browser, no cookies/passwords/credit-cards access |
| **Manus** | Chinese startup ka autonomous agent product — Sidekick "apna khud ka Manus" hai |
| **`sidekick_tools.py`** | Module jaha saare tools define hote hain (single place packaging) |
| **`sidekick.py`** | `Sidekick` class — worker node, evaluator node, aur LangGraph **graph build** ka code |
| **`app.py`** | Gradio UI module — user interface manage karta hai |
| **Canvas (not product)** | Sidekick ek starting point hai — apne tools/prompts se customize karna tumhara kaam |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Python REPL tool = `eval()` on user input, on steroids.** Jo instinct tumhe production me `exec`/`eval` se door rakhta hai, wahi yaha apply hota hai — LLM-generated code chalana untrusted input chalane jaisa hai. Week 3 ka Docker sandbox approach = containerized CI runner; ye REPL = host pe direct shell. Defence-in-depth ka classic trade-off: convenience vs blast radius.
- **3-module split ek clean layered architecture hai** jo tum roz likhte ho: `sidekick_tools.py` = integrations/adapters layer, `sidekick.py` = domain/service layer (state machine + orchestration), `app.py` = presentation layer. Tools ko ek jagah package karna dependency-injection jaisa hai — graph ko fark nahi padta tool list me kya hai, wo bas bind karta hai.
- **Restricted file-system directory = chroot/jail pattern**, aur fresh Chromium with no cookies = stateless headless browser jaise tum Selenium/Playwright CI me use karte ho — no session, no creds, isolated profile. Same mental model.
- **Hands-on lab:** is lecture ka code khud chalane ke liye `Practical/lab4_sidekick.py` run karo (is repo me, `uv run` se chalta hai, Groq pe free via `langchain-groq` `ChatGroq`). Note: hamare lab me course se differences hain — **LangSmith tracing skip** (key nahi), **Serper ki jagah free Wikipedia search**, aur **Playwright browser-driving SKIP** (heavy dep) — uski jagah lab me **safe sandboxed file/python tools** hain, jo is lecture ke file-system + REPL tools ko hi safer tarike se cover karte hain.

---

## 🧠 Takeaway (yaad rakho)

1. **Sidekick ko 5 naye tool categories milte hain:** Serper web search, push notifications, file read/write, Wikipedia, aur Python REPL — agent ab research + execute + deliver sab kar sakta hai.
2. **Python REPL is baar SANDBOXED NAHI hai** (no Docker) — sabse powerful aur sabse risky tool; uncomfortable ho to remove kar do. **Use at your own risk.**
3. **Built-in limits yaad rakho:** Chromium fresh hai (no cookies/passwords), file system ek directory me jailed hai — par REPL open hai.
4. **Sidekick ek canvas hai, finished product nahi** — apne tools + prompts se customize karo; experimentation pay dividends. Ye tumhara "apna Manus" hai.
5. **Architecture: 3 modules** — `sidekick_tools.py` (tools), `sidekick.py` (Sidekick class: worker + evaluator + graph), `app.py` (Gradio UI). Separation of concerns, production-style.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Would you believe it's already day five of week four? Here we are completing our sidekick project. I'm so happy! I love this project and I'm now such a fan of LangGraph. Over the course of the week, uh, we're going to be talking today about tools, tools and more tools we're going to be building in, uh, the same tool that we know and love already about searching the web, not navigating a browser, but doing the web search, uh, using the Serper API that we've used before. We're going to send push notifications because why not? We know how to do that. We're also going to add a tool to use the file system to be able to write files, so that we can have our operator agent that we're building our, our coworker that we have with our sidekick be able to read and write files from the file system. We're going to have it have access to Wikipedia so that it can look things up. And we're even going to give it the ability to run Python code itself. Not not in a Docker container like we did before. This time it's just going to have the ability to execute some Python. And so we're really giving it unfettered access to do things on our machine while we watch and while we monitor.

And that leads me to a big point. Uh, the sidekick app that we're about to build is an experimental app. It's something for you to work with and to monitor and watch and use it for your own purposes. This is this is an app for commercial purposes for you, for you to be able to get more and do more with an AI agent at your side. But in doing so, it doesn't have guardrails. It's something which is, uh, open to the wild. And as such, it needs to be treated with some caution. And that's the first thing I want to say. Use sidekick at your own risk. If you're not comfortable with this, if you're not sure about the technologies behind it and so on, then please do remove the Python REPL tool that we'll we'll add. You should remove it and even remove the online navigation tools until you're, you're comfortable with what's going on. And you can watch it. This is an agent that we are allowing to roam free.

Now of course when it's using the browser it's using it's using Chromium, the open source version of Chrome. And it doesn't have access to any of our cookies or any of our passwords in a password manager or something like that. So it's not able to do anything like log in or it doesn't have access to credit cards and so on. And the file manager is is within a certain directory, so it can't roam free on your computer. The Python REPL that's pretty open. It can run any Python it wants, which would allow it potentially to write something that could that could do uh, do some damage. Uh, so you could remove that if you're, if you're concerned. But it does seem extremely unlikely. But nonetheless you need to be comfortable with it. You need to do it at your own risk please.

The the other thing I want to say is that the sidekick app is a starting point. See it as a canvas. I've built something up with some prompts and some tools, and I've discovered that I can make it do great things for me. It actually did some work for me, some real work, some commercial work that I needed to do, and it did it for me and produced a report and it was something that I used. So. So it works. It really works. And it can deliver commercial benefit for you and be your own sidekick, let alone building it for other people. Uh, so see it that way. But you need to see it as this canvas. It's something which you need to to make suitable for yourself. You need to put in the sorts of tools and give it the kind of prompting you need. When I use it, I find that it sometimes goes awry, and I need to improve my prompts and make various changes to it to keep it on track. And that's what you have to do. It will require experimentation, and if you do so, it will pay dividends.

And that's my final point. There's so much opportunity with this. This really unleashes agentic AI. But this is like it's like you're building your own Manus. If you find if you find agents like, like Manus from the Chinese startup that that was able to do things like hunt for good, rent in apartments and build websites and things, this is like your very own one that you are building and you are controlling and so you can make it do great things. Um, but it requires effort put into it to and it will, it will take some investment of your time and experimentation. And so I see that see it that way, the good and the bad. It's a it's a canvas. It's not a completed product, but there's so much potential. Well let's get to it.

Here we are in uh, in Cursor, we're looking at, week four, of course, and now we're going to Python modules, which I know will please some people, but I'm not going to be typing code, but it's going to be looking at it but going through it carefully. So sidekick, the application is divided into three Python modules. There are they are here. And I'll first give you like a drive by of them. There is sidekick tools. And this is the module where we define the different tools that we will use. So it's nicely packaged up in one place that is going to get us access to a ton of tools, or it's going to give our agent access to a ton of tools, then sidekick. Now this is a bit of a long, a long, uh, module here, and maybe this should be broken up a bit. Um, but it contains a class Sidekick, and that has the code that includes our worker, our evaluator, and the building of the graph. And we'll come and look through this. And then thirdly, there is app.py, and that is our Gradio app that manages the user interface side of it. Okay. So with that, let's just spend a couple of minutes on each on each piece.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
