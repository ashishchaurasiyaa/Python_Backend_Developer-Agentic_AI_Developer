# L76 — Day 3: LangSmith & Custom Tools

> **Week 4 — LangGraph** · ⏱️ ~7m · 🎥 Lecture 76 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821343

---

## 🎯 Ek Line Mein (TL;DR)

Lab 2 (Day 3) shuru — pehle **LangSmith tracing** setup karte hain (har LangGraph invoke ka input/output, errors, latency, cost, tokens dashboard pe dikhta hai), phir **LangChain `Tool` object** se do tools banate hain: ek off-the-shelf **GoogleSerperAPIWrapper** (web search) aur ek **custom Pushover push-notification tool** — JSON schema ka saara gumph LangChain khud handle karta hai.

---

## 📝 Hinglish Explanation (Detailed)

- **Setup phase — Week 4, Lab 2 (Day 3):** Ed Cursor me lab kholta hai. Hamesha ki tarah pehle **imports** aur **`load_dotenv()`** — env variables load karna mandatory ritual hai.

- **LangSmith setup (LangChain ka observability/tracing platform):**
  - Lab me LangSmith ka link diya hai — wahan jaake **free account** banao. Free tier ki limit kaafi high hai (course use ke liye easily enough).
  - Dashboard pe pehli baar aaoge to empty hoga — **"Set up tracing"** button dabao.
  - Ek **API key generate** karo — generate karte hi LangSmith tumhe required **env variables** ka block fill karke de deta hai (e.g. `LANGSMITH_TRACING`, `LANGSMITH_API_KEY` etc.).
  - Wo variables copy karke apni **`.env` file** me paste karo — **lekin OpenAI API key wali line mat lo** (wo already set hai, overwrite nahi karna).
  - `.env` update ke baad **`load_dotenv()` dobara run karo** taaki naye variables process me load ho jayein. Bas — LangSmith configured.

- **LangSmith dashboard me kya dikhta hai (kyun useful hai):**
  - Ed ne project ka naam **"mastering agents"** rakha (naam kuch bhi rakh sakte ho).
  - **Har LangGraph invoke ki ek entry** banti hai — **input aur output** dono visible.
  - **Errors** bhi capture hote hain (Ed ke khud ke 2-3 errors dashboard me dikhe).
  - **Timestamp** + **latency** — kab call hui, kitna time laga.
  - **Cost column** — har OpenAI call ka exact kharcha. Ed highlight karta hai: numbers **insanely small** hain — "fractions of fractions of a cent". Jo log API cost se darte hain, unke liye reality check: scaling tak pahunchne se pehle cost negligible hai (asli pain sirf upfront $5 deposit hai).
  - **Token counts** bhi dikhte hain (kuch zeros the — Ed ke ek bug ki wajah se, jo fix ho gaya).
  - Yaani LangSmith = **production-grade observability** for LLM apps, bina khud logging likhe.

- **Off-the-shelf tool: `GoogleSerperAPIWrapper` (from `langchain_community`):**
  - Ye **Serper API** (Google search) ke around ek convenient wrapper hai — Serper key already `.env` me hai (Week 2 me set ki thi).
  - Instance banao: `serper = GoogleSerperAPIWrapper()`, phir directly call karo — `serper.run("What is the capital of France?")` → **"Paris is the capital and largest city of France..."** internet search se.
  - Serper bhi free plan me **several thousand calls** included — OpenAI ke 2.5 cents/call ke comparison me free.
  - Note: ye goodness **LangChain** ki hai, LangGraph ki nahi — lekin **LangGraph LangChain ecosystem ko use karta hai**. LangChain pehle se simple agent abstractions/wrapper code deta hai, ye uska ek example hai.

- **Function ko `Tool` object me wrap karna (LangChain construct):**
  - `Tool(name="search", func=serper.run, description="...")` — bas teen cheezein:
    - **name** — tool ka identifier jo LLM dekhega,
    - **func** — actual Python function jo tool call hone pe chalega,
    - **description** — LLM ko batane ke liye ki ye tool kab use karna hai (isi se **JSON schema** banta hai).
  - **Sabse badi convenience:** OpenAI tools wala saara manual JSON banana (properties, parameters, types ka pura "gumph") — **LangChain ye sab auto-generate kar deta hai**.
  - Test: `tool_search.invoke("What is the capital of France?")` — wahi Paris wala answer, lekin ab **LangChain way** (`.invoke()`) se.

- **Custom tool from scratch — Pushover push notification:**
  - Wahi favourite tangible example: ek `push(text)` function jo **Pushover** package se Ed ke phone pe push notification bhejta hai.
  - Function ko proper **docstring** do (description ke liye important), phir same construct: `Tool(name="send_push_notification", func=push, description="...")`.
  - Test: `tool_push.invoke("me")` → phone pe "hello, me" notification. Custom tool ready.

- **Wrap-up:** Ab hamare paas **2 tools** hain — (1) off-the-shelf **search tool** (Serper) aur (2) **custom push-notification tool** (Pushover). Dono ko ek **list of tools** me daal do — agla step inhe actually LangGraph graph me use karna hai (next lecture).

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **LangSmith** | LangChain family ka **observability/tracing platform** — har LLM/graph call ka input, output, error, latency, cost, tokens dashboard pe |
| **Tracing** | Har invoke ki automatic logging — `.env` me LangSmith keys daalte hi on ho jaati hai, code change nahi chahiye |
| **`.env` + `load_dotenv()`** | API keys env file me; nayi keys add karne ke baad `load_dotenv()` dobara chalana padta hai |
| **`GoogleSerperAPIWrapper`** | `langchain_community` ka ready-made wrapper Serper (Google search) API ke liye — `serper.run(query)` |
| **`Tool` object** | LangChain ka construct: `Tool(name, func, description)` — function ko LLM-callable tool banata hai |
| **Auto JSON schema** | `Tool` wrap karne se tool-calling ka manual JSON (properties/types) LangChain khud bana deta hai |
| **`tool.invoke(...)`** | LangChain ka standard tarika kisi bhi tool/runnable ko call karne ka |
| **Custom tool** | Apna Python function (e.g. Pushover `push`) + docstring → `Tool` me wrap → ready |
| **Pushover** | Simple package/service jo phone pe push notification bhejta hai — tool-calling demo ke liye tangible example |
| **Tools list** | Saare tools ek list me — yahi list aage LLM ko bind hogi (`bind_tools`) aur **ToolNode** me jayegi |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **LangSmith = APM for LLMs.** Jaise tum backend me Datadog/New Relic/OpenTelemetry se request traces, latency aur error rates dekhte ho, LangSmith wahi LLM calls ke liye karta hai — plus **per-request cost**, jo normal APM me nahi hota. Best part: instrumentation **env-vars driven** hai (sidecar/agent pattern jaisa), code me ek line nahi badalni.
- **`Tool(name, func, description)` ek adapter/serializer hai.** Tum FastAPI me Pydantic models se OpenAPI spec auto-generate karwate ho — same idea: LangChain function ke signature + description se LLM ke liye **JSON tool schema** auto-generate karta hai. Manual JSON likhna = manually OpenAPI spec maintain karna; dono anti-pattern.
- **Docstring yahan load-bearing hai** — wo sirf documentation nahi, LLM ka **routing contract** hai (LLM description padhke decide karta hai kaunsa tool call karna hai). Bad docstring = wrong tool dispatch, jaise bad route pattern = 404.
- **Hands-on lab:** is lecture ka code khud chalane ke liye `Practical/lab2_tools_checkpointing.py` run karo (is repo me, `uv run` se chalta hai, Groq pe free via `langchain-groq` `ChatGroq`). Hamare labs course se thode alag: **LangSmith tracing skip** (key nahi) aur **SerperDev ki jagah free Wikipedia search** use kiya hai — concepts (Tool wrap, invoke, tools list) bilkul same.

---

## 🧠 Takeaway (yaad rakho)

1. **LangSmith setup = free account + API key + env vars + `load_dotenv()`** — uske baad har LangGraph invoke ka trace (input/output/error/latency/cost/tokens) dashboard pe automatic.
2. **API costs darawne nahi hain** — per call "fractions of fractions of a cent"; LangSmith cost column ye prove karta hai.
3. **`GoogleSerperAPIWrapper`** (`langchain_community`) = ready-made Google search tool — `serper.run(query)`, free tier me thousands of calls.
4. **`Tool(name=..., func=..., description=...)`** — LangChain ka wrap construct jo tool-calling ka saara manual JSON gumph khatam kar deta hai; call karo `.invoke()` se.
5. **Custom tool banana trivial hai** — koi bhi Python function + docstring → `Tool` me wrap → tools list me daalo → graph me use karo (next lecture).

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

And a very warm welcome to Cursor. Here we are. We are in week four. LangGraph, we're going to lab two, which is the lab for day three. It's confusing. Uh, so we're going to start with some imports as we do. And we are also going to do the load dot env that always needs to be done.

And we are now going to go and set up LangSmith. So there's a link to LangSmith here. When you follow this link you'll get to their website. And the first thing you'll need to do is create an account. Uh, and it's free. It's free as long as you stay within some very high number, which we definitely will. Uh, so you can set that up. And when you come in, you're going to get this sort of dashboard a bit like this, except it will be empty. And the first thing to do is to press the setup tracing button right here. And this is going to fly up. You have to generate an API key so that you've got an API key. And as soon as you press that it will then fill this in down here. And you just simply then want to copy that to your clipboard, all of your, uh, fields, all of the key variables that you'll see here. Um, but just don't obviously don't take the OpenAI API key as well. You don't need that, But you need this. And then you will it will actually populate that API key with whatever you generate right here, which is great. And then you will go into, uh, back back here into your ENV file, which is just there, and you will add this in to your ENV file so that we have these variables set. And then once you've done that come back and run load dot env again so that they load in. Maybe I should have done that in the other order. So that's great. Then you have LangSmith configured and you'll be able to see things.

Now before we, uh, go further, I will just just talk through a few of the things we can expect to see. Um, so I called the project mastering agents, but you can call it whatever you want. Of course. Um, and you can see in here there's there's lots of stuff that I've been doing. You'll see that it for every time that I've invoked LangGraph, I get some sort of a of an entry here. I get the input and the output. If there's an error, which I had a couple of errors, then we will see them. It tells you when it happened. It tells you the latency, which is very helpful. And there's a bunch of other useful stuff here too, which we don't often get to see. The cost in this column is telling us how much this cost us to make this call to OpenAI. And for those people that are concerned about about API costs, do have a look at how insanely small these numbers are. It just really brings it to life. I realize that the main problem people have is with the upfront $5 you have to put in at the beginning, but I hope that you see that that until you get to such point as you are scaling, we are talking about not just fractions of a cent, but fractions of fractions of a cent for most of these. Um, it also tells you the number of tokens, which is helpful to know. I'm not sure the zeros were because I had some bug that I luckily then fixed. Uh, so you get to see a bunch of stuff in here and this is going to be useful. And when we actually have things to to look at, we will come back and take a look at that. Okay. Onwards.

All right. So I found a useful function that's in the langchain community folder. Uh and it's called GoogleSerperAPIWrapper, which means that it's a nice little convenient wrapper around the same thing that we set up before the Serper API, where we already have the API key in our env file, which is convenient to use. And so we can create an instance of this thing GoogleSerperAPIWrapper. And we can call serper with something like what's the capital of France? And if we do this, then it will think for a moment. And indeed we get Paris is the capital and largest city of France, and with some stuff about it, from doing an internet search on this, which is great. And again, this is something that's part of what's free and included in the plan up until some several thousand calls. I think unlike OpenAI, which is charging us two and a half cents for each one. So that is, uh, that is good.

Now, this is showing you some of the nice stuff that's actually in LangChain rather than LangGraph, but LangGraph uses it too. I mentioned to you that LangChain already does sort of simple agent interactions. It already gives some some wrapper code, some abstraction code. And here is here is one of them. I kept the import here so we could see that it's from, from LangChain. So? So you can say that, uh, you can wrap a function like this with a Tool object. You give it a name like search a function serper run. That's what it will actually do when it needs to call this tool. And a description is what will be will be called in order to, um, when, when building the JSON around this tool. Uh, so that's wrapped it in a tool object, a LangChain Tool object. And as you can probably guess, this is going to take away all of the gumph about building that JSON object with all the stuff and the properties and everything else. It's going to take care of all of that for us, so we can now try out the same, the same question, what's the capital of France which we can do using tool search dot invoke the LangChain way we are calling this tool and there we go. We get an answer of the capital of France, same thing. But now we're doing it by calling invoke. Okay.

And now let's just show you what it's like to build a tool from scratch ourselves. It's super easy. Uh, so we'll use the same old thing that we like to do because it's nice. It's so tangible. Uh, using Pushover, this is the same kind of function that is able to send a push notification to me. So we give it the usual docstring, we give it, uh, the information about it. Um, and, uh, here we go. That's that. I put that into a tool again, the same construct, the LangChain construct. The name is send push notification. The function is push and that's a description. And now I can then call tool push invoke with me. There we go. Oh, yeah. Hello. Me. Uh, so now we have made, uh, a tool ourselves. A custom tool.

So now we have an off the shelf tool for searching using the Serper API. And we have a custom tool for sending a push notification using the nifty Pushover package. Okay. And we can put both of these tools in a list of tools. All right. Then we actually get to use it.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
