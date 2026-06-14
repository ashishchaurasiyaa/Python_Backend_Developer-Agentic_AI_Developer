# L29 — Day 1: OpenAI Agents SDK Fundamentals — Creating, Tracing & Running Agents

> **Week 2 — OpenAI Agents SDK** · ⏱️ ~5m · 🎥 Lecture 29 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49820365

---

## 🎯 Ek Line Mein (TL;DR)

**OpenAI Agents SDK** ek **lightweight, unopinionated** framework hai jo tool-calling ka saara **JSON boilerplate** khud handle karta hai — sirf 3 concepts (**Agent**, **Handoff**, **Guardrail**) aur 3 steps (**Agent banao → `with trace` → `await Runner.run()`**) yaad rakho.

---

## 📝 Hinglish Explanation (Detailed)

- Sidebars khatam — ab **main business** shuru: **OpenAI Agents SDK** ka intro.

- **Framework ka character — lightweight aur unopinionated:**
  - **Opinionated framework** = aisa framework jo apne saath bahut saare **constructs** aur "yahi tarika hai kaam karne ka" wali soch lekar aata hai (jaise CrewAI). Ye hamesha bura nahi hota — design patterns enforce hote hain, cheezein fast build hoti hain.
  - Lekin Ed ka personal bias: **less prescriptive** frameworks better lagte hain — zyada **flexibility** ki tum apne tarike se kaam karo. OpenAI Agents SDK exactly isi ilk ka hai.

- **Sabse badi value — boilerplate ka khatma:**
  - Week 1 mein humne tools ke liye jo **JSON schema ka gunk** likha tha (tool definitions, `if` statement se tool-call handle karna, results wapas bhejne ka loop) — wo saara **faffing around with JSON** ye SDK khud kar deta hai.
  - Ye **abstraction "in the way" hai, but in a good way** — kyunki ye wahi useless repetitive boilerplate hai jo har baar likhna padta, framework ke liye perfect kaam.

- **Ed ka favorite framework — aur 2 reasons ki ye pehle kyun aa raha hai:**
  1. Saare frameworks great hain, har ek ke **pros/cons** aur apne best-fit **use cases** hain — lekin course ke projects dheere-dheere **beefier** hote jayenge, complexity badhegi, isliye simple/flexible se start karna logical hai.
  2. Ye framework **wapas aayega** — **Week 6 mein MCP** (jo ek **protocol** hai, framework nahi) ke saath OpenAI Agents SDK ko **more hardcore way** mein use karenge. Toh crescendo bhi isi ka hoga — start bhi, finish bhi.

- **SDK ki terminology — sirf 3 concepts (minimal hai):**
  - **Agent** — LLM calls ke around ek **package/wrapper** jiska solution mein ek **particular role/purpose** hota hai.
  - **Handoff** — agents ke beech **interaction** ka OpenAI wala naam. Ye term baar-baar alag contexts mein aayega.
  - **Guardrail** — wo **checks & controls** jo ensure karte hain ki agent wahi kare jo tum chahte ho, aur **off the rails** na jaye. (Normal software engineering mein bhi common word hai.)

- **Agent run karne ke 3 steps:**
  1. **`Agent` ka instance create karo** — ye tumhare solution ka ek role hoga (name, instructions, model).
  2. **`with trace` use karo** — saare interactions ka **log** rakhne ke liye. Technically **required nahi hai**, lekin course mein hamesha aise hi karenge — isse **OpenAI ke monitoring tools** (traces dashboard) mein sab kuch dikh jata hai.
  3. **`Runner.run()` call karo** — yahi actually agent ko run karta hai. Ye ek **async function — yaani coroutine** — hai, isliye isse **`await`** karna padega: `await Runner.run(...)`.

- Agla step: notebook mein ye 3 steps **live karke dikhana**.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **OpenAI Agents SDK** | Lightweight, flexible, unopinionated agent framework — Ed ka favorite; Week 2 aur Week 6 (MCP) dono mein use hoga |
| **Opinionated framework** | Jo apne constructs/patterns thopta hai — fast build hota hai par flexibility kam (Agents SDK iska ulta hai) |
| **Agent** | LLM calls ke around package jiska ek particular role/purpose hai solution mein |
| **Handoff** | Agents ke beech interaction ka OpenAI terminology — ek agent doosre ko kaam pass karta hai |
| **Guardrail** | Checks & controls jo agent ko "off the rails" jaane se rokte hain |
| **`with trace`** | Context manager jo interactions ko log karta hai — OpenAI monitoring dashboard mein dikhta hai (optional but recommended) |
| **`Runner.run()`** | Agent ko actually execute karne wala call — coroutine hai, `await` karna zaroori |
| **Coroutine** | Async function jo await kiye bina chalti nahi — `await Runner.run(...)` pattern |
| **MCP (Week 6 teaser)** | Protocol (framework nahi) — uske saath Agents SDK hardcore mode mein wapas aayega |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Tool-calling boilerplate vs SDK** = raw `requests` se REST API banana vs FastAPI use karna. Week 1 ka manual JSON schema + `if tool_call:` loop wahi hai jaisa har endpoint ke liye haath se request parsing likhna — Agents SDK ka `@function_tool` decorator FastAPI ke route decorator jaisa hai: function signature + docstring se schema auto-generate (pydantic-style introspection).
- **`Runner.run()` coroutine hai** — aapke asyncio experience se directly map hota hai: ye `aiohttp.ClientSession.get()` jaisa awaitable hai, fire-and-forget nahi. Notebook (Jupyter) mein event loop already running hota hai isliye direct `await` chal jata hai; plain script mein `asyncio.run()` chahiye hoga.
- **`with trace("...")`** ko distributed tracing ke lens se dekho — ye OpenTelemetry span/correlation-ID jaisa hai: ek logical operation ke saare LLM calls ek trace ID ke under group ho jaate hain, phir OpenAI dashboard pe waterfall view milta hai. **Note:** tracing OpenAI platform ka feature hai (OpenAI API key chahiye traces dekhne ke liye) — hamare free Groq labs mein hum isko skip/no-op karte hain.
- **Hands-on lab:** is lecture ka code khud chalane ke liye is repo ka `Practical/lab1_agents_sdk_basics.py` run karo (`uv run` se chalta hai, Groq pe free). Hamare labs OpenAI ki jagah **FREE Groq** use karte hain — `OpenAIChatCompletionsModel` + `base_url` trick se same SDK, zero cost.

---

## 🧠 Takeaway (yaad rakho)

1. OpenAI Agents SDK = **lightweight + unopinionated** — minimum constructs, maximum flexibility; tool-calling ka saara JSON boilerplate SDK khud handle karta hai.
2. Sirf **3 terms**: **Agent** (LLM ka role-wrapper), **Handoff** (agent-to-agent interaction), **Guardrail** (checks/controls).
3. Run karne ke **3 steps**: `Agent(...)` instance → `with trace(...)` → `await Runner.run(...)`.
4. `Runner.run()` **coroutine** hai — `await` mandatory; `with trace` optional hai par monitoring ke liye hamesha use karenge.
5. Ye framework **Week 6 mein MCP ke saath wapas** aayega — isliye ise achhe se seekh lo, ye course ka backbone hai.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Okay, enough with the sidebars. It's on to the main business. It is on to introducing OpenAI Agents SDK. Now let me start by teeing this up. So this is a framework which as I've already mentioned, is super lightweight, very flexible. One of the things I love about it is that it's not what they call opinionated. Opinionated is how some frameworks are described when they come with a lot of constructs, a way of doing things that you are then sort of expected to adhere to. Now, that's not always a bad thing because that can help build particular design patterns. It can allow you to build things really, really quickly. But my personal bias is I often prefer things that are less prescriptive and which give you more flexibility to choose how you want to work with this. And very much OpenAI Agents SDK is of that ilk.

It also is very good at the same time at making some of the everyday stuff, like using tools, much simpler. So if you think of all of that gunk that we had to do with the JSON around tools, all of that faffing around with JSON objects. Well, OpenAI Agents SDK just does all that for you. So that kind of stuff is very much it is in the way, but in a good way. It just does all of that JSON stuff and it handles the whole, if you remember the if statement and then my fancy version of it, it does all of that so that you just don't need to worry about it. And that's one way where it is good to have some abstraction, because that's the useless boilerplate stuff that you have to repeat every single time that you want a framework to do for you.

And as you can probably tell from the way I'm saying this, OpenAI Agents SDK is my favorite. And yeah, I'm really looking forward to this week. And I enjoy working with OpenAI Agents SDK. And you might be thinking, why? Why are you showing us your favorite one? First, why don't you want to end with your favorite one? You should work up to it. And I have two answers for you there. So first of all, I do want to point out that whilst OpenAI Agents SDK is my favorite, all of the frameworks are great, and they all have pros and cons, and each of them have use cases where they are the best for that particular kind of problem. So in some ways they're all my favorites. But but uh, no, that's not true. OpenAI, you're my favorite. Uh, they're all good. And so, uh, but they also get that during the course of our journey, they're going to get more and more complex. And so it's going to make sense to do it the way we do. And our projects are going to get beefier and beefier. So that's the first reason.

The second reason is that whilst this is the framework that we are starting with, we are also going to finish with it as well, because in week six, when we work with MCP, which is a protocol, not really a framework, in the same way we are going to be using OpenAI Agents SDK again in a more hardcore way. So it's going to come back. It's going to make a triumphant return in week six. So you don't need to worry. The crescendo will be there.

Now, one thing that all of the frameworks have in common is that they come with some terminology, some constructs, and each one is of course slightly different. And we will be learning each of the different terminologies as we go. But of course OpenAI's terminology is pretty minimal. It's fairly simple stuff. There are three, three concepts, three terms I'm going to go through with you. The first of them is just an agent. Agents represent their sort of package around calls to LLMs which have a particular role, a particular purpose in this solution. Obviously handoffs — this is their name for the interactions between agents. So handoff is a term that they use a fair amount and we'll see it come up in different contexts. But that's what it means. It is an interaction. And guardrails is their terminology for the kinds of checks and controls that you put around making sure that an agent is doing what you want it to do and isn't going off the rails. Guardrails is a pretty common word in normal software engineering anyway. But it's one of the three terms to take on board for using OpenAI Agents SDK.

So in order to actually run an agent, there are three steps that you have to take. And here they are. Here are the three steps. You create an instance of agent. That's going to be the thing that you're going to set up to be one of the roles in your solution. You use something called with trace to be able to keep a log of all of your interactions with that agent. This isn't required. But it's going to be the way we will do it. And we will always do it this way. And it's going to allow us to look in OpenAI's monitoring tools and see everything that's going on. And then you call something called runner dot — and runner dot run is the thing that will actually run the agent as you will see. And runner run, the thing that actually runs the agent, is of course an async function. Or I should say it's a coroutine. And so as a result, it's something that we will need to await in order to get it to actually run. So we are going to need to do something that's going to look like await runner run. And these are the three steps. And without further ado, let's go and do those three steps right now.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
