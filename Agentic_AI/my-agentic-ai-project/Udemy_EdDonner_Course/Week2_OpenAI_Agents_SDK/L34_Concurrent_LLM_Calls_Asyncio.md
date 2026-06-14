# L34 — Day 2: Concurrent LLM Calls — Implementing Asyncio for Parallel Execution

> **Week 2 — OpenAI Agents SDK** · ⏱️ ~9m · 🎥 Lecture 34 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49820441

---

## 🎯 Ek Line Mein (TL;DR)

**`asyncio.gather()`** se 3 sales agents ko **parallel** mein run karaya (multithreading nahi — **event loop** I/O waits ke time pe switch karta hai), phir ek 4th **sales picker agent** ne best email choose ki — aur end mein dikhaaya ki **`@function_tool` decorator** kaise Week 1 wala saara JSON boilerplate khatam kar deta hai.

---

## 📝 Hinglish Explanation (Detailed)

- **Setup:** Pichle lecture mein 3 sales agents banaye the (professional, engaging/humorous, busy/concise). Ab in sabko ek saath chalana hai. `asyncio` ka import top pe daala — Ed ka style hai imports top pe rakhna.

- **Parallel runs with `asyncio.gather()`:**
  - Instruction: "write a cold sales email" — yahi teeno agents ko diya.
  - `await asyncio.gather(...)` se **3 runs ek saath** fire kiye. Ye **multithreading nahi** hai — CPU time-slicing nahi ho rahi.
  - Asal mein **event loop** kaam karta hai: jab ek coroutine **I/O pe pause** hota hai (LLM ka response wait kar raha), tab event loop doosre ko chalata hai. Kyunki LLM calls ~99% time bas network I/O pe wait karti hain, teeno effectively **parallel mein OpenAI se baat** kar rahi hoti hain.
  - `gather` se **collection of results** wapas aata hai — har result pe `.final_output` call karke print kiya.
  - Output: 3 alag emails — teesri wali concise thi kyunki us agent ki instructions mein "concise" likha tha.

- **Trace wrapping:** Poora flow ek `trace(...)` block ke andar wrap kiya, taaki **saare 3+1 agent runs ek hi trace** mein dikhein OpenAI traces UI pe.

- **Sales Picker — workflow pattern:**
  - Naya agent banaya: **sales_picker** — "best cold sales email pick karo from given options. Imagine you're a customer — jis pe respond karoge wo choose karo. **No explanation. Reply with the selected email only.**"
  - Ed ka prompting tip: **system prompt ko constraint/limitation se end karna** classic technique hai (model ko output format pe lock karta hai).
  - Flow: 3 agents parallel mein emails likhte hain → outputs gather hote hain → 4th agent (picker) best choose karta hai → print.
  - Ed bola: socho ye **Week 1 ke kaunse pattern** ka variation hai — ye basically **parallelization + evaluator/judge** type ka **workflow** hai. Pure Python code hai, step-by-step: "call three agents in parallel, take the output, call another agent."
  - Total ~30 seconds laga, single best email print hui.

- **Trace mein verify kiya:** Trace "Selection from salespeople" mein chaaron calls dikhin — professional agent, engaging agent, busy agent, phir sales picker. Har ek ke **actual prompts** trace mein padh sakte ho.

- **Honest reality check (important!):** Ab tak kuch "magical" nahi hua. Agent constructs bas **lightweight wrappers** hain — humne effectively sirf **4 LLM calls** kiye (3 writers + 1 picker). Elegance traces aur clean abstractions mein hai, "agentic magic" mein nahi. Asli agentic cheez ab shuru hogi: **tools**.

- **Week 1 flashback — tools ka dard:**
  - Week 1 mein tool banane ke liye **chunky JSON boilerplate** likhna padta tha — function ke parameters, types, description sab manually describe karo.
  - Phir `handle_tool_calls` function likhna padta tha — wo "hokey if statement" wala **gunk** (Ed ka technical word 😄).

- **Agent ke andar kya hai:** Sales agent object ko inspect kiya — usme `name`, `instructions`, `tool_choice`, aur **`tools` ki list** hoti hai (abhi empty). Yehi constructs hain jinse hum kaam kar rahe hain — under the covers perfectly simple.

- **Tool banana — `send_email` function:**
  - Ek plain Python function: `send_email(body: str)` — **docstring** ke saath: "Send out an email with the given body to all sales prospects."
  - **SendGrid API** use karta hai. `from_email` wo hona chahiye jo SendGrid mein **verified sender** hai, warna email send hi nahi hogi. `to_email` apna koi email rakho (Ed ne request ki ki uska Gmail mat use karo, warna flood ho jayega 😄).
  - Body de do, SendGrid bhej deta hai, "success" return — bilkul Week 1 jaise function tool.

- **`@function_tool` — magic decorator:**
  - Week 1 mein next step hota: JSON ka pahad likhna. **OpenAI Agents SDK mein bas function ke upar `@function_tool` decorator lagao** — bas!
  - Decorator lagane ke baad `send_email` ab **function nahi raha** — wo ek **FunctionTool object** ban gaya:
    - `name` = "send_email"
    - `description` = **docstring se automatically** uthaya
    - `params_json_schema` = wo saara JSON boilerplate **auto-generated** — function signature aur type hints padh ke khud figure out kar liya
  - Ed ka framework philosophy: **"Take out the boilerplate but leave us in full control"** — yahi ek acche framework ki nishani hai.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **asyncio.gather()** | Multiple coroutines ko ek saath fire karke saare results ek collection mein wapas lena |
| **Event loop** | Single thread pe scheduler — jo coroutine I/O pe wait kar raha ho use pause karke doosre ko chalata hai (multithreading nahi) |
| **I/O-bound parallelism** | LLM calls zyada time network wait karti hain, isliye async se "parallel" feel hota hai bina threads ke |
| **trace() wrapper** | Poore multi-agent flow ko ek hi trace mein group karna — OpenAI UI pe sab calls ek jagah dikhti hain |
| **Sales picker (judge agent)** | Ek aur LLM agent jo multiple outputs mein se best choose karta hai — evaluator/parallelization pattern |
| **Constraint-ending prompt** | System prompt ko limitation se khatam karna ("reply with email only, no explanation") — output control ka classic trick |
| **@function_tool** | Decorator jo plain Python function ko FunctionTool bana deta hai — JSON schema + description auto-generate |
| **params_json_schema** | Tool ke parameters ka JSON schema — Week 1 mein hath se likhte the, ab decorator se free |
| **Verified sender (SendGrid)** | SendGrid mein registered email jisse hi mail bhej sakte ho — warna send fail |
| **Lightweight wrappers** | Agent/Runner constructs bas thin abstraction hain — andar simple LLM calls hi hain |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **`asyncio.gather` yahan exactly waisa hi hai jaisa aap `aiohttp`/`httpx` se 3 downstream APIs ko fan-out karte ho** — LLM call bhi bas ek slow HTTP POST hai. GIL ka koi issue nahi kyunki sab I/O-bound hai. Mental model: `gather(*[Runner.run(agent, msg) for agent in agents])` == parallel fan-out + join.
- **`@function_tool` ko FastAPI ke route decorator jaisa samjho:** jaise FastAPI function signature + type hints + docstring se **OpenAPI schema** auto-generate karta hai, waise hi ye decorator **params_json_schema** generate karta hai. Andar pydantic hi kaam kar raha hai. Decorator function ko replace karke ek object (FunctionTool) return karta hai — classic decorator-returns-different-type pattern.
- **3 writers + 1 picker = "scatter-gather + reducer" pattern** jo aap distributed systems mein use karte ho — yahan reducer deterministic code nahi, ek LLM judge hai. Ye abhi bhi **workflow** hai (Anthropic definition), agent nahi — control flow aapke Python code mein hardcoded hai.
- **Hands-on lab:** is lecture ka code khud chalane ke liye ye lab run karo — `Practical/lab2_sales_agents_handoffs.py` (is repo me, `uv run` se chalta hai, **Groq pe free**). Note: hamare labs OpenAI ki jagah FREE Groq use karte hain (`OpenAIChatCompletionsModel` + `base_url` trick), aur lecture wala **SendGrid** (paid/signup) hamare lab mein nahi hai — email send ko simulate kiya gaya hai; OpenAI **traces UI** bhi Groq setup pe nahi dikhega, to trace wala part lecture demo se hi samjho.

---

## 🧠 Takeaway (yaad rakho)

1. **`asyncio.gather()` se multiple agent runs parallel** — event loop I/O waits exploit karta hai, multithreading nahi chahiye.
2. **Poora flow `trace()` mein wrap karo** — saare agents (3 writers + picker) ek hi trace mein dikhte hain, debugging easy.
3. **Judge/picker agent pattern:** parallel outputs generate karo, phir ek aur LLM se best select karao — system prompt ko constraint se end karo ("reply with email only").
4. **Ab tak sab lightweight hai** — bas 4 LLM calls in elegant wrappers; asli agentic power tools se aati hai.
5. **`@function_tool` decorator** = Week 1 ka saara JSON boilerplate + handler gunk gone — docstring se description, signature se schema, **full control intact**.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Pressing on. So what we're now going to do is call this. It looks like I'm going to need to import asyncio there. Hang on. Let's do that. Missed an import at the start. Actually let's do this properly. I'm going to take this out just so that it's nice and clean for you. I'm going to put that async import right up at the top there and rerun that cell. I like to do my imports at the top. I know people have different views on this stuff.

Okay, so we are now going to say we want to write a cold sales email. That's going to be our instruction. And what we're going to do now is we're going to call this asyncio. Do you remember this? I showed this to you back when we had the async briefing, that this is where you start to see the power of asyncio. We're going to be running three different runs at the same time. And of course again it's not multithreading. It's not like the CPU is actually time slicing between them in some ways. But rather it's going to be using an event loop, which will run each one, and whenever it's pausing waiting on I/O it will let another one run. And because most of what these things are doing is pausing on I/O, that will allow all three of them to sort of alternate and be talking to an LLM, to OpenAI, in parallel, and then we will collect back the results. What comes back from this await gather is a collection of results. And we will call final output on each one and print it. So we will let that run. And you can see that I've wrapped all of this in a trace, which means that we should see all of this in one trace. We will do in a little bit, but no surprise. Hopefully what you'll see down here is I have to click here to get a scrollable element, and you'll see that we can scroll through and read a bunch of emails. And the third one, of course, is very concise because we asked our third email writer to be concise.

Okay, so so far all we've really done is multiple calls to LLMs. And now the final piece of the puzzle. This is just a simple workflow of calling LLMs. See if you can remember which one of the patterns this is, but it's a sort of variety of one of them. And we are going to create a new agent called sales picker. And sales picker picks the best cold sales email from the given options. Imagine you're a customer. Pick the one you're most likely to respond to. Don't give an explanation. Reply with the email you select only. It's a classic kind of prompting. You know that you often end with the constraint. With any limitation is a good way to end a system prompt.

All right. So that's the message, the user prompt: write a cold sales email. We again have this same construct. We're going to run three agents in parallel to craft three messages. We're going to gather the outputs and then we just simply call another agent. So this is just Python code step by step. Call three agents in parallel. Take the output. Call another agent. It's just a Python script that runs these things in order, and it will then print the best email at the end of it. And because we've got the whole thing under one trace, we hope to see all of this in a single trace. So this is probably going to take I think like 30s in total. So I'll have to keep the sentence running if we want to see this live. And at the end of it we'll be able to go into the trace it's run.

So here is a single email that's been returned. And it is apparently the best one. But let's now go and have a look at the trace to see if we believe it. Okay. So this was our email. Now this is a link to go to see the traces in OpenAI. Here it comes. So at the top, trace is "selection from salespeople". Let's go and have a look into this trace. What you'll see is that, sure enough, it called the professional sales agent, and you can read the actual prompts that went in. It called the engaging sales agent. It called the busy sales agent, and then it called the sales picker. And you can go through this in the trace and see what's going on.

So it's worth pointing out that we've really not done anything very magical so far. It's nice. It's elegant that we've had these wrappers, these agent constructs around things, but they're very lightweight wrappers. We've essentially simply called a total of four LLMs. We've called the three sales LLMs, and then we've called the one at the end to pick the email it preferred. And it's sort of elegant that you can go into the traces and see what's going on. But now it's time to get a bit more agentic and start talking about tools.

So as we get into tools, let me remind you, have a think back to what we did in week one, when we had to build some boilerplate JSON to describe a function that we wanted to use as like a tool. It's quite chunky JSON that described the parameters and various other things about it. And then we had to write a function called handle tool calls, which is the one that had the hokey if statement that I then tried to write into something a bit more fancy, but which was still a fair amount of sort of gunk, to use a technical word. And what we're now going to see is how that whole stuff can be super simplified without taking any flexibility away from us.

So first of all, we're just going to recap. We've got these three sales agents: the professional, the engaging and the busy ones. And there they are. And let me just look at one of these sales agents. So if I look into it you can see that it's got a name. It's got the instructions. And you can see that it has things like tool choice, tools, and it has like a list of tools that it has access to, which right now is empty. So just to give you a sense of what's going on under the covers, it's perfectly simple. But these are the constructs we're working with.

So what we're now going to do is have a tool. So this is a function send email. It takes an email body which is a string. And it has like a docstring: send out an email with the given body to all sales prospects. Now what I've got in here is the from email. And this email needs to be what's called the verified sender, the email address that you've set up in SendGrid that you're allowed to send from. Otherwise it won't actually send. So you'll need to update this, and then to email — you should put that to be an email where you don't mind it receiving an email. I would prefer that you change it from my Gmail here. Otherwise I will get flooded with emails from people doing this. So maybe I'll change it before I commit this to GitHub. But yes, send that to another of your email addresses. Or you could probably just send it to yourself. I'm not sure, but send it to somewhere where you don't mind receiving cold sales emails, there'll only be 1 or 2. We're not going to send a mass of them. And then this is SendGrid's API. It's perfectly simple. It's SendGrid. And you give it a body so you can look through this. But it's honestly just a boilerplate to send an email to a recipient and we respond with success.

So this is very much like the tools that we wrote last time. It's like a function to do it. And if you remember, the next step was to write a ton of JSON to describe this. But all we need to do with OpenAI is put one of these decorators above it: at function tool. If you're not sure how decorators work, again, that's in the guides, or just ask ChatGPT to explain it. But that allows OpenAI to write some code to sort of do something with this function. And all we need to care about is we simply put that decorator above the function that we want to treat as a tool. And so we will just simply define that function — doesn't look like we've done anything, but let's look at this thing called send email. Now we think it's a function, right? But no, it's not a function, because we have this decorator it's been converted into something called a function tool. It has a name, send email. It has a description. And that description is taken from the docstring comment we had right here. Look at that. It's just turned that into a tool description. And then — and this is the great stuff — params JSON schema. This stuff is all of the boilerplate JSON that we had to write last time. It's just done it for us because it's read this and it's figured out what's needed. And that's basically it. So just by simply adding that decorator function tool, all of the work of faffing around with these JSON objects has been taken away from us, which is great. That's what a good framework should do. Take out the boilerplate but leave us in full control.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
