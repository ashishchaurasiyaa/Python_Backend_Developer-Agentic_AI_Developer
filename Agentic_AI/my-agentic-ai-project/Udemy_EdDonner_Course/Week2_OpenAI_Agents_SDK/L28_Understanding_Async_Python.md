# L28 — Day 1: Understanding Async Python — The Foundation for Agent Frameworks

> **Week 2 — OpenAI Agents SDK** · ⏱️ ~12m · 🎥 Lecture 28 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49820287

---

## 🎯 Ek Line Mein (TL;DR)

Week 2 (OpenAI Agents SDK) shuru karne se pehle Ed ek **must-know sidebar** deta hai — **asyncio (async Python)** — kyunki **saare agent frameworks** isi pe bane hain; `async def` se bana **coroutine** call karne par run nahi hota, **`await`** karne par **event loop** use schedule karta hai, aur **IO-wait (LLM API calls)** ke dauraan doosre coroutines chalte rehte hain.

---

## 📝 Hinglish Explanation (Detailed)

- **Week 2 ki shururat:** Ye week pura **OpenAI Agents SDK** pe hai — jo pehle **Swarm** ke naam se jaana jaata tha, recently release hua, agent frameworks me **sabse naya arrival**.
- **Lekin pehle ek sidebar:** SDK shuru karne se pehle Ed ko ek important topic cover karna hai — **asynchronous Python (asyncio)**:
  - Ye **saare agent frameworks me common** hai — har framework asyncio use karta hai.
  - Aap bina samjhe bhi kaam chala sakte ho — bas 2 rules follow karo aur "it just works". **Par Ed kehta hai ye unsatisfactory hai** — sirf **aadha ghanta** lagao, ek baar deeply samajh lo, aur baar-baar jab ye samne aayega to aap completely comfortable rahoge.
  - Course ke saath ek **detailed guide** bhi hai jo asyncio ko thrash out karti hai — koi question na bache.
- **asyncio kya hai (short version):**
  - Python likhne ka ek tarika jo **multithreading ka lightweight version** hai.
  - Python **3.5** me introduce hua tha.
  - **OS-level threads use nahi karta**, aur **multiprocessing bhi nahi** (multiple Python processes spawn karna).
  - Kyunki super lightweight hai — **hazaaron ya dasiyon-hazaar (10k+) coroutines** ek saath chal sakte hain, bina zyada resources consume kiye.
  - **IO-bound kaam ke liye best** — jaise network pe wait karna. Jab ek code piece network pe wait kar raha hai, doosre chal sakte hain.
- **LLM/agents se connection — kyun zaroori hai:**
  - Jab aap **paid APIs (jaise OpenAI)** call karte ho, **zyada-tar time cloud model ke response ka wait** hota hai — yaani heavy **IO-bound waiting**.
  - **Multi-agent frameworks** me to kai agents alag-alag APIs hit kar rahe hote hain — concurrency ka perfect use-case.
  - Isi liye **saare frameworks** (jo hum dekhenge) **asyncio** use karte hain.
- **asyncio = do cheezein:**
  - Ek **package** (`import asyncio`) jo aap import kar sakte ho.
  - Aur **language constructs** jo Python me baked-in hain — **do keywords: `async` aur `await`**.
- **Short version ke 2 rules:**
  - Jo function concurrently chal sakta hai, uske aage **`async`** lagao: `def do_some_processing()` → `async def do_some_processing()`.
  - Use call karte waqt **`await`** lagao: `result = await do_some_processing()` — baaki sab same.
  - Bas itna follow karo aur kaam chal jaayega — but ab **deeper story**.
- **Real story — coroutines:**
  - **Multithreading OS level** pe implement hoti hai — CPU level pe programs ke beech switch hota hai. **asyncio different hai**.
  - `async def` likhte hi wo cheez **technically function nahi rahi — ab wo "coroutine" hai** (log "function" hi bolte hain, Ed bhi, but strictly speaking coroutine).
  - Coroutine **special hai kyunki Python use pause aur resume kar sakta hai**.
  - **Sabse badi baat:** coroutine ko **call karne par wo run NAHI hota** — normal function call karte hi run ho jaata hai, but coroutine call sirf ek **coroutine object return** karta hai, execute kuch nahi hota.
  - Run karne ke kuch tarike hain, but sabse common (jo hum hamesha use karenge): **`await`** karo — ye coroutine ko **execution ke liye schedule** karta hai.
- **Event loop — asli engine:**
  - asyncio library me ek **event loop** hota hai — basically ek **while loop** jo iterate karta hai, coroutine uthata hai aur execute karna shuru karta hai.
  - Event loop **ek waqt me sirf EK coroutine execute** karta hai — multithreading jaisa parallel nahi.
  - **Magic tab hota hai jab coroutine block ho jaaye** — e.g. OpenAI ko call kiya aur response ka wait hai. Tab event loop us coroutine ko **pause** karke apni waiting list ke **doosre coroutine ko run** kar deta hai. Wo bhi IO pe atke to teesra, ya pehla resume.
  - Ed isse **"manual multithreading"** kehta hai — multithreading manually implement ki gayi, code level pe, jo sirf tab kaam karti hai jab koi cheez **IO pe blocked** ho. Isi simplicity ki wajah se ye **lightweight** hai aur **agentic frameworks me ubiquitous**.
- **Example — beat it to death:**
  - `async def do_some_processing()` jo kaam karke `"done"` string return karta hai.
  - `my_coroutine = do_some_processing()` — naya banda soche ki ye run hoga, **but NO** — sirf **coroutine object** variable me jaata hai.
  - `my_result = await my_coroutine` — **ab** run hota hai, aur `"done"` `my_result` me aata hai.
  - Shortcut (jo hum hamesha karte hain): `my_result = await do_some_processing()` — ek hi line me.
- **`asyncio.gather()` — asli concurrency:**
  - Sirf `await coroutine` se concurrency nahi milti — har `await` **block** karta hai jab tak wo complete na ho, fir next line. Sequential hi hua na?
  - Isliye asyncio me aur constructs hain — sabse important (jo **is week ke code me use hoga**): `results = await asyncio.gather(coro1, coro2, coro3)`.
  - Event loop **teeno schedule** karta hai — jaise hi ek block hua (IO wait), doosra chalne lagta hai, fir teesra... saare execute hote hain.
  - Result: **list of results** — teeno coroutines ke outputs ek list me.
- **Final mental model:** Ye ek tarah ka **"fake/brute-force multithreading"** hai — OS level pe nahi, balki **event loop ke through almost manually implement** kiya hua, jo IO-blocking handle karke next coroutine schedule karta hai. Aise hi socho.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **asyncio** | Python ka lightweight concurrency system — package + language keywords (`async`/`await`), Python 3.5 se |
| **`async def`** | Function ko coroutine banata hai — "ye concurrently chal sakta hai" ka declaration |
| **Coroutine** | `async def` se bana special "function" jo Python **pause/resume** kar sakta hai; call karne par run nahi hota |
| **Coroutine object** | Coroutine ko call karne par jo return hota hai — execution abhi hua nahi, bas object mila |
| **`await`** | Coroutine ko event loop pe **schedule** karta hai aur complete hone tak block karta hai; result return karta hai |
| **Event loop** | asyncio ka engine — ek while loop jo ek waqt me ek coroutine chalata hai, IO-block pe switch karta hai |
| **IO-bound waiting** | Network/disk ka wait — LLM API calls me zyada-tar time yahi hai; asyncio ka sweet spot |
| **`asyncio.gather()`** | Multiple coroutines ko ek saath schedule karo — sab concurrently chalte hain, results ki list milti hai |
| **Multithreading vs asyncio** | Threads OS-level pe heavy hote hain; asyncio code-level pe lightweight — 10k+ coroutines easily |
| **Multiprocessing** | Multiple Python processes spawn karna — asyncio ye bhi nahi hai, usse bhi halka hai |
| **Swarm** | OpenAI Agents SDK ka purana naam — experimental framework jo SDK me evolve hua |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Aap FastAPI use karte ho to ye sab pehle se jaante ho** — FastAPI ke `async def` endpoints, uvicorn ka event loop, `httpx.AsyncClient` — bilkul wahi model. Naya angle sirf ye hai: **agent frameworks me ye optional nahi, foundation hai** — har `Runner.run()` (Agents SDK) ek awaitable hai, kyunki har agent call = LLM API call = IO wait.
- **GIL ka confusion clear rakho:** asyncio GIL ko bypass nahi karta — ye **single-threaded cooperative multitasking** hai. CPU-bound kaam (heavy parsing, embeddings locally) event loop ko **freeze** kar dega — wahan `run_in_executor`/threads chahiye. Agents me 95% kaam IO-bound hai isliye asyncio perfect fit hai.
- **`asyncio.gather()` = multi-agent fan-out ka backbone:** jaise aap N downstream microservices ko parallel `httpx` calls karte ho, waise hi is week N agents ko parallel LLM calls karwayenge (e.g. 3 models se ek saath drafts) — latency max(N) hoti hai, sum(N) nahi.
- **Hands-on lab:** is lecture ka code khud chalane ke liye `Practical/lab1_agents_sdk_basics.py` run karo (is repo me, `uv run` se chalta hai, **Groq pe FREE**). Note: hamare labs OpenAI ki jagah free Groq use karte hain (`OpenAIChatCompletionsModel` + `base_url` trick) — to lecture me jahan paid OpenAI API ka wait dikhe, hamare labs me wahi IO-wait Groq pe hota hai, concept same.

---

## 🧠 Takeaway (yaad rakho)

1. **Saare agent frameworks asyncio pe bane hain** — LLM calls = IO-bound waiting, isliye concurrency free me milti hai; aadha ghanta laga ke deeply samjho.
2. **`async def` = coroutine, function nahi** — call karne par run nahi hota, sirf coroutine object milta hai; **`await` karne par event loop pe schedule hota hai**.
3. **Event loop ek waqt me ek hi coroutine chalata hai** — but jaise hi koi IO pe block hota hai (e.g. OpenAI response ka wait), doosra chal padta hai — "manual multithreading".
4. **`asyncio.gather(c1, c2, c3)`** se asli concurrency — multiple coroutines parallel schedule, results ki list — is week ke multi-agent code me directly use hoga.
5. **Lightweight hone ki wajah se** 10k+ coroutines chal sakte hain — na OS threads, na multiprocessing — isi liye ye multi-agent systems ke liye ideal hai.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Well. I am so excited to welcome you to week two of our time together in this journey into Agents Land. And as well, you know, week two is all about OpenAI Agents SDK, formerly known as Swarm, released very recently, the newest of our arrivals into the agents framework land and one that I cannot wait to tell you all about.

But first, isn't there always a but first, but first, before we can do OpenAI Agents SDK, I have a sidebar, a topic that I have to cover with you, a very important topic, and it's to talk to you about asynchronous Python, asyncio. It's something which is common across all of the agent frameworks. So all of them make use of asynchronous Python, and it's something which you can get by without really understanding. There's a couple of rules that you can learn and then you just follow those rules always. And it will just kind of work and that's okay. But I'm here to tell you that that's unsatisfactory and that it's much better to just take half an hour to get to the bottom of this, to really understand it, to thrash it out until you're like, okay, I get asynchronous Python, I understand it, and if you do this, if you take the half an hour, you will thank me. It will again and again you will come across this and you will be completely comfortable with it. And it's only half an hour. And so I've put a guide and the guides that will take you through this, so that you can be left with no questions in your mind at all about what it means to write asynchronous Python. And I'm also now going to cover it just very briefly at a high level. Let's talk asyncio.

Well, look, first of all there is like a short version, a simple version. This is what I mean when I say you can get by without really understanding it. So asyncio is a way of writing Python code, which is a kind of lightweight version of multithreading. So many people from a software engineering background will be familiar with the idea of multithreading. When you write code that can run concurrently, you can have multiple threads which are each executing code together, and there's often a lot of baggage that comes with that, some sort of framework stuff that comes with it. Well, asyncio, which was introduced I think, in Python 3.5, is this very lightweight way of doing it, which doesn't actually involve threads at an operating system level. And it also doesn't involve what's called multiprocessing, which is when you spawn multiple Python processes and they all run together. This is another way of doing it that is super lightweight. And because it's super lightweight, it means that you can have thousands or tens of thousands of these things all running without consuming much resources at all. So it's a simple, easy peasy, lightweight way of writing code that can run concurrently.

And particularly it's good when you have code that makes use of input output, like waiting on networks. It allows other things to be running whilst one bit of code is waiting on network, and when you're running LLM requests, you're mostly — if you're using paid APIs like OpenAI, most of the time is being spent waiting for stuff to feed back from a model running on the cloud. So there's a lot of waiting on networks, a lot of IO bound waiting. And as a result, asynchronous code is great to use. And when you're thinking of multi-agent frameworks, when potentially you have lots of these all hitting different APIs, it makes so much sense to be using it. And that is why all of the frameworks we'll look at use asyncio.

Okay. So with that preamble this is the short version. The short version is asyncio is actually two things. It's a package called asyncio that you can import, and it's also some language constructs baked into Python. And those language constructs include two keywords that you see right here. And one of those keywords is the word async. And anytime that you have a function which is potentially going to be able to run in a way that allows other things to happen concurrently, you simply put the word async before it like this: async def do_some_processing, so def do_some_processing becomes async def do_some_processing. That's how you say this is a function which can run asynchronously. And when you call that function you don't just call do_some_processing like you're used to. You have to put the word await before it. So you say await do_some_processing and if do_some_processing returns a string, then you can't just say result equals do_some_processing. You have to say result equals await do_some_processing. But otherwise it's just the same. So that's the short version. And if you wanted to get by without really understanding it, you could just follow those rules and keep going and it might be enough. But now let me tell you the bigger story.

Okay. Now we're going to go a little bit deeper and talk about the real story with asyncio. So look as I say, it's a lightweight alternative to multithreading or multiprocessing. Something like multithreading is implemented at the OS level. And it supports concurrent execution of different programs where the CPU, the CPU level that's being managed to sort of switch between these two programs and treat them as if they're running at the same time. This is different in the case of asyncio. So there are some special keywords. There's this keyword async. If you define a function as async def and then the function instead of just def the function, then this thing is no longer actually called a function. It's known as a coroutine. Now most people still use the word function. You'll hear me saying function, but strictly speaking, anytime you see async def, you should say, okay, that's not a function, it is a coroutine. And that means it's something special that Python can pause and resume.

When you call a coroutine, it doesn't run, unlike any other function that you call that does run. When you call a coroutine, it just returns a coroutine object, but nothing is executed to actually run that coroutine object. There are a few ways to do it, but the most common one, and the one that we will use all the time is to await it. So you say await, and then the coroutine object and that schedules it for execution.

What does it mean to say it's scheduled for execution? Well, there is this piece of code written in the asyncio library, which does what's known as an event loop, which means it's a kind of while loop that iterates and it takes this coroutine and it starts executing it, and it can only execute one coroutine at a time. It's not like multithreading. It's going to be executing this coroutine, except if this coroutine gets to a point when it's stopped and it's waiting for something like it's waiting for IO. Perhaps it's made a call to OpenAI and it's waiting for OpenAI to respond. At that point, the event loop can put that on pause and start executing a different one of the coroutines that's in its sort of list of coroutines waiting to be run. And if that hits a point when it's waiting on IO, then the event loop can run another one or it can continue the first one. So it's a sort of manual way of handling multithreading. It's a manual approach to implementing multithreading, but only really working when something is blocked waiting on IO. And because of this, because it's sort of written at a code level and it's super simple and very easy to understand, it's also lightweight. You can have thousands or tens of thousands of these things. And so it's really easy and quick to get this running. And that is why it's so popular. And that is why it's used so ubiquitously across agentic frameworks. So I hope, obviously I've only given you a bit of detail here, but I hope that gives you some perspective on what's going on.

And when we look back now at this, you can see that whilst a simple interpretation is just to say, okay, whenever I use async I've got to use await, the deeper interpretation is to understand that when I say async def do_some_processing, that's no longer a function, it's now a coroutine do_some_processing. We need to call await do_some_processing in order to schedule that coroutine. And that is now blocking until that completes and the result will go into that variable result. I hope that made some sense, but if not, as I say, there's a whole guide. You should go and look at the guide now.

And so just to beat this one to death, I'll give you a couple more examples. And then hopefully you've really got this. So look at this again. This is back to the async def do_some_processing. It's going to do some work. And then it's going to return the string "done". If I just say like my_coroutine equals do_some_processing, you might, you know, if you didn't know already about this, you might think that that will run do_some_processing. But of course it will not. It will return a coroutine object and that's what will go into the variable my_coroutine. In order to actually run it you have to call await. So you'd say my_result equals await my_coroutine. It's now going to run. And the result, the string "done", is going to go into my_result. So that is the point. That's how it works. And of course you don't need to do that. It's simpler than that. You can just say my_result equals await do_some_processing, which is what we always do.

And then just to hopefully sort of connect the dots to make this really click for you. There are other constructs — you don't just have to call await and then the name of a coroutine, because if that's all you could do, you might think, you might say to me, okay, hang on. But in that case there's nothing concurrent happening here. Every time I call await and then a coroutine, it will block until that finishes and then it will go on to the next. Well, there are a few other constructs in the asyncio package that allow us to do more interesting things, and this is one of them, and it's one that we will use this week in our code. And it's where you can say results, plural, results equals await, and then call this function asyncio dot gather. And you can then pass in multiple coroutines. And I'm sure you can imagine what happens. But the event loop is going to schedule all three. And as soon as one of them is blocking, the others will start running, or one of the others will run until it's blocking, and then the third one will run. And so all three of those coroutines will run, will execute. And the results as a list will go into the variable results, a list of each of the three results from each of those three coroutines.

So in some ways it's kind of fake multithreading. It's sort of brute force multithreading. It's multithreading not at the operating system level, but multithreading implemented almost manually with this event loop, and just handling things like IO blocking and being able to schedule the next one. That's how to think about it.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
