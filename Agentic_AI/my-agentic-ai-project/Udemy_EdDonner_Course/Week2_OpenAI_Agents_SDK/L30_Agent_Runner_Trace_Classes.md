# L30 — Day 1: Introduction to Agent, Runner, and Trace Classes

> **Week 2 — OpenAI Agents SDK** · ⏱️ ~9m · 🎥 Lecture 30 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49820381

---

## 🎯 Ek Line Mein (TL;DR)

OpenAI Agents SDK ke **3 core building blocks** — **`Agent`** (LLM + system prompt ka package), **`Runner.run()`** (async execution engine), aur **`trace`** (monitoring/observability context manager) — inse pehla agent banaya, joke bulwaya, aur OpenAI platform pe trace dekha.

---

## 📝 Hinglish Explanation (Detailed)

- Hum **Cursor** me hain, folder `2_openai` → **lab 1** ("First look at OpenAI Agents SDK"). Ed ne **official docs** ka link diya hai — docs itne clear hain ki Ed mazak me bolta hai "mera job hi khatre me hai" 😄. Is week ke liye docs padhna hi kaafi hai, aage ke weeks harder honge.

- **Imports** — sabse pehle `from dotenv import load_dotenv` (environment variables ke liye), aur phir OpenAI ke package se:
  - Package ka naam hai **`agents`** — haan, itna **generic naam** hai ki Ed bhi bolta hai ye thoda strange choice hai, kyunki bahut log apne khud ke packages ko `agents` naam dete hain, to import conflicts ho sakte hain.
  - Isme se 3 cheezein import ki: **`Agent`**, **`Runner`**, aur **`trace`**.

- `load_dotenv(override=True)` — ab tak second nature hona chahiye, env vars (API keys) load karne ke liye.

- **Pehla Agent banana** — `agent = Agent(...)` — class ka instance, jisme 3 main arguments:
  - **`name`** — agent ka naam, yahan `"Jokester"`.
  - **`instructions`** — ye essentially **system prompt** hai. Har agent ko aap soch sakte ho ek **LLM + ek particular system prompt** ke roop me, jo use **ek specific task** ke around organize karta hai. Yahan: `"You are a joke teller"`.
  - **`model`** — yahan `"gpt-4o-mini"`.

- **Important question**: kya Agents SDK sirf OpenAI models ke saath chalta hai? **Nahi!** SDK **not opinionated** hai — is week me hi hum **different models** (non-OpenAI) use karenge isi framework ke saath. Bas **default** ye hai ki agar sirf model ka naam (string) pass karo, to wo assume karta hai OpenAI model hai.

- Agent object ko print karke dekha to usme dikhe:
  - **`handoffs`** — agents ke beech interaction/delegation ka concept (Week 2 me aage aayega).
  - **`input_guardrails`** / **`output_guardrails`** — safety checks, baad me cover honge.
  - Model + bunch of settings — apne time pe explore karne layak.

- **Agent ko run karna — `Runner.run(agent, message)`**:
  - 2 cheezein pass karte ho: **agent** khud, aur ek message jo essentially **user prompt** hai (`"Tell a joke about autonomous AI agents"`).
  - Direct call karke print kiya to **joke nahi mila** — mila ek **coroutine object**! Kyunki `Runner.run` ek **async method** hai — async function call karne se execution nahi hota, **coroutine** return hota hai.
  - Fix: **`result = await Runner.run(agent, message)`** — ab coroutine **event loop** pe schedule hota hai, `await` use execute karta hai aur completion tak hold karta hai.
  - Output milta hai **`result.final_output`** me — print karo to joke milta hai. ("Why don't autonomous agents ever get lost? Because they're always following their own self-driving instructions." — Ed: OpenAI agent frameworks me jokes se behtar hai 😅)

- **Honest note from Ed**: abhi tak kuch "special agentic" nahi kiya — bas ek system prompt + user prompt hai. Lekin ye sirf **basic construct** dikhane ke liye tha; week me aage real agentic magic aayega.

- **`trace` — monitoring with a context manager**:
  - Syntax: **`with trace("Telling a joke"):`** — Runner.run call ko is **context manager** ke andar wrap karo.
  - Ye OpenAI ko bolta hai: in **agent interactions ko record karo** is heading ("Telling a joke") ke under.
  - Power tab dikhega jab **sophisticated multi-agent workflows** honge — saare agent calls **ek heading ke under package** ho jayenge OpenAI ke monitoring tools me.

- **Trace dekhna**: `platform.openai.com` pe jao → left side me **Traces** click karo → "Telling a joke" top pe dikhega. Andar jao to dikhega: ek LLM call hua, **system instructions** = "You are a joke teller", **user prompt** = "Tell a joke...", aur **assistant ka response**. Simple example me profound nahi lagta, lekin future me complex workflows debug karne ke liye **invaluable** hoga.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **`agents` package** | OpenAI Agents SDK ka pip package — generic naam, isi se `Agent`, `Runner`, `trace` import hote hain |
| **`Agent` class** | Ek LLM + ek system prompt ka package, ek specific task ke liye organized |
| **`instructions`** | Agent ka **system prompt** — SDK ki terminology me "instructions" |
| **`name`** | Agent ka label (e.g. "Jokester") — traces/monitoring me identify karne ke liye |
| **`model`** | Konsa LLM use hoga; sirf string doge to default OpenAI assume hota hai |
| **`Runner.run(agent, msg)`** | Agent execute karne ka tarika — `msg` user prompt hai; **async** hai, `await` zaroori |
| **Coroutine** | Async function ko call karne pe jo object milta hai — execute tabhi hota hai jab `await` karo |
| **`result.final_output`** | Run complete hone ke baad agent ka final response |
| **`trace`** | Context manager (`with trace("heading"):`) jo agent interactions ko OpenAI platform pe record karta hai |
| **Handoffs** | Agents ke beech ek-dusre ko kaam delegate karne ka mechanism (agent object pe dikha, aage aayega) |
| **Guardrails** | Input/output safety checks (agent object pe `input_guardrails`/`output_guardrails`, baad me cover) |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **`Runner.run` async hai** — bilkul waise hi jaise FastAPI me `async def` endpoint ya `httpx.AsyncClient` call. Coroutine object milna aur `await` bhoolna — wahi classic `RuntimeWarning: coroutine was never awaited` wala scene. Jupyter me top-level `await` chalta hai (kernel ka apna event loop hai), lekin plain script me `asyncio.run()` chahiye hoga.
- **`with trace(...)` = distributed tracing ka LLM version** — bilkul OpenTelemetry/Jaeger ke span jaisa socho: ek context manager jo apne andar ke saare LLM calls ko ek parent span/heading ke under group karta hai. Multi-agent workflow = multi-service request trace.
- **`Agent` = configured client, not running process** — `Agent(...)` banana waise hi hai jaise ek configured `requests.Session` ya DB connection pool object banana; actual execution `Runner` karta hai. Stateless config vs execution engine ka clean separation.
- **Hands-on lab**: is lecture ka code khud chalane ke liye `Practical/lab1_agents_sdk_basics.py` run karo (is repo me, `uv run` se chalta hai, **Groq pe free**). Note: hamare labs OpenAI ki jagah FREE Groq use karte hain (`OpenAIChatCompletionsModel` + `base_url` trick) — isliye lecture ka **OpenAI Traces dashboard wala part** hamare lab me nahi dikhega (tracing OpenAI platform ka feature hai, OpenAI API key chahiye); concepts (Agent/Runner/await/final_output) sab same chalenge.

---

## 🧠 Takeaway (yaad rakho)

1. **3 core classes**: `Agent` (LLM + instructions + model), `Runner` (execution), `trace` (monitoring) — sab `agents` package se import hote hain.
2. **Agent = LLM + system prompt** ek specific task ke liye; `instructions` hi system prompt hai.
3. **`Runner.run()` async hai** — `await` karna mat bhoolo, warna coroutine object milega, joke nahi.
4. SDK **model-agnostic** hai — default OpenAI hai, lekin koi bhi model laga sakte ho (aage seekhenge).
5. **`with trace("heading"):`** se saare agent calls OpenAI platform ke Traces me ek heading ke under record hote hain — complex workflows me debugging ke liye invaluable.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Welcome back to Cursor, where we are ready to go with OpenAI Agents SDK. So you'll see that we have the folders on the left here, the directories. And we are now going into number two, OpenAI, and into lab number one. Here it is. First look at OpenAI Agents SDK. I've included a link to the docs for OpenAI. And I will say that it does almost concern me showing you these docs because they're so clearly written and so easy that I rather wonder what my job is in all this. I will say that for the next few weeks, I think I definitely have a job. It gets a lot harder, but for this one you'd be doing well just to read the docs and it'll be very clear to you. So anyway, I'll keep going regardless.

So let's do some imports to get us started. So we will say from dotenv import load_dotenv. We know we got to do that. And now we're going to do some imports from OpenAI's package. And that package is called agents. And from that package we are going to import Agent. We're going to import this thing called Runner. And we're going to import this thing called trace. These are the three things I told you about that we were going to use today. And the OpenAI package is called agents. That's the one. I do sometimes think that it's a bit strange that they use such a generic name for it, because I imagine a lot of people use the name agents for their own packages. I often do, and so you have to then start messing around with different kinds of imports. But still they did. It's called agents. And this is how we import these three key things: Agent, Runner and trace.

All right. So the usual starting point. Hopefully this is second nature to you. We need to run load_dotenv with override is true to bring in our environment variables. They are in, okay.

We are now going to make an agent. We're going to create our first agent, our first agent from a framework of this course. And so we're going to have an agent and say agent equals — it's going to be an instance of the class Agent. So we're creating an instance of Agent, OpenAI's class. Now it has some parameters. We need to use some arguments. And one of them is name. We give it a name and we're going to call it the Jokester. And then we give it something called instructions. I like the way this is just filled in. I'll just press tab. Put me out of my misery. So we pass in some instructions. The instructions are basically the system prompt for this call to the LLM. So each of these agents you can think of as being an LLM with one particular system prompt designed to organize it around one particular task. And so our system prompt, called the instructions, in this case: you are a joke teller. And you also pass in a model, which in this case is GPT-4o mini.

And you might be thinking in your mind a very good question, which is: does this mean that OpenAI Agents SDK always uses OpenAI's models? You might, you know, that might sound like it's a sensible conclusion, but no, definitely not. The Agents SDK is very much able to work with many models, as we will later in this week explore using different models with the OpenAI Agents SDK. It's not opinionated. You can use different models with this same framework, but by default, if you just pass in a model name, it assumes you mean OpenAI.

Okay, so now we're going to execute this. And now we have our first agent. Let's just look at what it looks like. It is an agent with name Jokester, instructions: you're a joke teller. And it's got some things here. Handoffs — you remember that was the concept that relates to the interactions between agents. It's got a model and it's got a bunch of settings and other things that you can look at in your own time. It'd be worth looking at. It has guardrails, input guardrails and output guardrails that we will look at later.

Okay. So I mentioned that Runner.run is the way to run one of these things. So we can say perhaps result equals Runner.run. And when you run an agent you pass in two things. You pass in the agent itself to be run by the Runner. And you pass in what is essentially the user prompt. It is the message that you are sending the agent. Let's say: tell a joke about autonomous agents. Autonomous AI agents. Okay, so now we are going to run this. It seems pretty simple. What do you think is going to happen? What's going to be in result? I will print result. Let's see what we get. If we do this and we print result — do you have any ideas? Here it is. We get a coroutine object, because Runner.run is an async method, which means an async function, which means that it returns a coroutine object. It's not a function, it's a coroutine. And so hopefully you're expecting that, or you guessed that. What does that mean? That means that we can't just call run and expect that to work. We have to call await.

And I'm going to restart this kernel and start again from the top so that we don't have one hanging out there, not scheduled. We will come through. We will do this. We will create our agent. And there it is. And now we're going to say await. We're going to say result equals await Runner.run, like that. And so now what we know is that Runner.run, that coroutine, is going to be queued by the event loop. And when we call await, it's going to execute it. And it will hold until it's completed execution. And the results will go into the variable result. And then we are going to print result.final_output. And this is now hopefully going to work and tell us a joke. See what happens. Why don't autonomous agents ever get lost? Because they are always following their own self-driving instructions. Okay, so OpenAI is rather better at dealing with lightweight agents frameworks than it is at telling jokes. But we'll accept it, so it works.

Now you can be forgiven for saying, all right, we haven't done anything particularly special here to do with agents. All we've done is have a system prompt and a user prompt. But never fear, there'll be plenty of time for that later in the week. What we're doing right now is just showing you the basic construct.

And for my final part of this, I'm going to wrap this in a trace. So for trace you wrap this in a context manager. So I say with trace "Telling a joke". And then I just need to put that like that. If you're not familiar with context managers then look in the guides. But I imagine that you are. And what this does is it's telling OpenAI that we would like it to record these agent interactions, which is only one, and record it under the kind of heading "Telling a joke". And this allows you to have sophisticated agent interactions with many different agent calls involved, and have it all packaged up and available in their monitoring tools under one kind of heading. So let's run this. We'll get another joke. Why did the autonomous agent break up with its human partner? It just couldn't handle the emotional bandwidth. Okay. I guess it's not got a whole lot to do with agents, except it's put it in there with the human partner. That's all right. I'll let you be the judge of it.

But now we can go and look at this trace. If we go to platform — here it comes — Traces. It's actually, you can just go to platform.openai.com and then just click on Traces in the left, and you'll see that "Telling a joke" is the top trace up here. And if I go into this trace we will see what happened: there was one endpoint called, the system instructions was "you are a joke teller" — that's the system message that was just called instructions. The user prompt was "tell a joke about autonomous AI agents". And then this was what the assistant responded. So true to its word, it's giving us a clear trace of the single call to an LLM that happened as part of this agentic workflow, but it's packaged it up under the heading "Telling a joke". And this has allowed us to come into Traces and see this. And as you can imagine, it's not particularly profound with this very simple example. But there will come cases in the future when this is going to be invaluable.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
