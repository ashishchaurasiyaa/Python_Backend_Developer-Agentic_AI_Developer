# L127 — Day 5: Key Settings and Launching the Trading System

> **Week 6 — MCP** · ⏱️ ~6m · 🎥 Lecture 127 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 50768387

---

## 🎯 Ek Line Mein (TL;DR)

Capstone ka launch moment — **`.env` ke 3 control settings** (`RUN_EVERY_N_MINUTES`, `RUN_EVEN_WHEN_MARKET_IS_CLOSED`, `USE_MANY_MODELS`) samjho, phir **`trading_floor.py`** ka chhota-sa orchestrator class dekho jo **`asyncio.gather` + `while True` loop** se charon traders ko parallel chalata hai — `uv run trading_floor.py` aur poora autonomous trading floor live!

---

## 📝 Hinglish Explanation (Detailed)

- Is lecture me do kaam hote hain: pehle **final code walkthrough** (settings + orchestrator class), phir actual **launch** of the trading floor.

### `.env` File Ki Key Settings
- **`RUN_EVERY_N_MINUTES=60`** — trading loop kitni der me repeat ho. Agar `.env` me nahi daala to **default 60 minutes** hai.
- **`RUN_EVEN_WHEN_MARKET_IS_CLOSED`** — ye guard hai taaki system **raat bhar / weekend pe har ghante trade na karta rahe** jab market band hai. Ed ne recording ke time `True` rakha hai kyunki Sunday tha aur use demo ke liye trading chahiye thi.
- **`USE_MANY_MODELS`** — agar `False` hai to **sab traders sirf GPT-4o mini** use karte hain (sasta/simple); agar `True` hai to har trader **alag-alag model** use karta hai (jo pichhle lecture me UI me dikhe the). Ed ne `True` rakha.

### `trading_floor.py` — Sab Kuch Jodne Wala Class
- Ye file **"wonderfully simple"** hai — poore course ka fitting conclusion. Steps:
  1. **Env variables collect** karo (upar wali teen settings).
  2. **Agent names** define hain — **Warren, George, Ray, Cathie** (famous investors pe based personas).
  3. **Traders create** karo — har name ke liye ek trader object ka collection.
- **`run_every_n_minutes()`** function hi asli engine hai:
  - Sabse pehle ek **trace register** hota hai — OpenAI Agents SDK ko bola jaata hai ki saare traces **custom log tracer** (pichhle lecture wala) se record kare, jo database me store hote hain.
  - Phir **`while True:`** loop — system **forever chalta rahega**.
  - Loop ke andar **`asyncio.gather`** — charon traders ka `trader.run()` **ek saath kick-off** hota hai. Ye multithreading jaisa lagta hai, par actually **async I/O** hai: jab bhi ek trader I/O pe wait kar raha hai (LLM response, MCP call), doosra run karta hai. Isliye sab parallel feel hote hain.
  - End me **sleep** for N minutes, phir loop repeat.
  - **`if __name__ == "__main__":`** se poora system kick-off hota hai.

### Launch — Trading Floor Live!
- Ed do terminals chalata hai: ek me **UI already running**, doosre me week-6 directory me jaake **`uv run trading_floor.py`**.
- Turant **UI ke panels me information "flying by"** — ye wahi custom traces hain jo humne khud intercept karke **database me store** kiye aur UI pe dikha rahe hain.
- **Color coding** ka matlab: alag colors = alag activities — **different MCP servers ko call karna, tools use karna**; **red = humara apna home-grown accounts MCP server** (business logic) call ho raha hai.
- **Push notification ka sound** bhi aata hai — jab bhi Warren/George/Ray/Cathie me se koi **trading decision** leta hai, Ed ko alert milta hai.
- **Async ki wajah se charon traders parallel** me apna thinking/research karte hain — typically few minutes lagte hain. Neeche UI me **current holdings aur recent transactions** dikhte hain.
- Live demo me trades hote dikhte hain: Warren ne **5 AMD shares sold**, account details retrieve kiye, **3 Qualcomm sold, 4 Nvidia bought** — Ed mazaak karta hai ki traders "love Nvidia" (researcher ka asar hoga!). Portfolio values bhi update hoti hain, aur Ed ko phone pe trade ke text messages aate rehte hain.
- **Learning point**: ye exercise isliye hai ki tumhe **visual, tangible sense** mile ki multiple agents ka kya matlab hai — agents calling other agents, **multiple MCP servers** use karke ek **commercial objective** achieve karna, aur traces se **LLM activity ko inspect/understand** karna. Ed kehta hai ye "super addictive" hai — fun + highly educational.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| `RUN_EVERY_N_MINUTES` | `.env` setting — trading loop ka interval; default 60 min agar set nahi kiya |
| `RUN_EVEN_WHEN_MARKET_IS_CLOSED` | Guard flag — `False` ho to market band hone pe (raat/weekend) trading skip |
| `USE_MANY_MODELS` | `False` = sab traders GPT-4o mini; `True` = har trader alag model |
| `trading_floor.py` | Entry-point orchestrator — env settings + traders create + forever loop |
| `asyncio.gather` | Charon traders ke async `run()` ko ek saath chalana — I/O wait pe context switch |
| `while True` loop | System forever chalta hai — run all traders → sleep N minutes → repeat |
| Custom log tracer | OpenAI Agents SDK ka trace processor jo traces DB me likhta hai (UI ke liye) |
| Color coding (UI) | Alag colors = alag MCP servers/tools; red = apna accounts MCP server |
| Warren/George/Ray/Cathie | Char trader agents — famous investors (Buffett, Soros, Dalio, Cathie Wood) ke personas |
| Push notification | Trader ke trade decision pe phone alert (notification MCP server se) |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **`while True` + sleep = poor-man's cron/Celery beat.** Production me aap isko cron job, Celery periodic task, ya APScheduler se replace karoge — saath me proper market-hours calendar check (jaise `RUN_EVEN_WHEN_MARKET_IS_CLOSED` ek crude feature flag hai). Pattern wahi hai jo aap scheduled workers me roz likhte ho.
- **`asyncio.gather` yahan classic I/O-bound concurrency hai** — har trader ka 90%+ time LLM/MCP responses ki wait me jaata hai, isliye single-threaded event loop pe bhi char traders "parallel" lagte hain. Bilkul waise hi jaise aap async web scraper ya fan-out API calls likhte ho; CPU-bound hota to `ProcessPoolExecutor` lagta.
- **Custom trace processor → DB → UI = apna khud ka observability pipeline.** Ye conceptually wahi hai jo aap OpenTelemetry exporter + Grafana se karte ho — spans intercept karo, store karo, visualize karo. Agentic systems me tracing optional nahi, essential hai (warna 4 autonomous agents debug karna impossible).
- **Hands-on lab:** is lecture ka code khud chalane ke liye ye lab run karo — `Practical/lab4_trading_floor.py` (is repo me, `uv run` se chalta hai, **Groq pe free**). Hamare labs course se thode alag: node/npx servers ki jagah **Python FastMCP servers** (`servers/` folder me), aur Brave Search/Polygon paid APIs ki jagah free substitutes (Wikipedia-style memory server + **simulated market server**) — to `USE_MANY_MODELS` jaisi multi-paid-model setting ki jagah sab kuch Groq ke free models pe chalta hai.

---

## 🧠 Takeaway (yaad rakho)

1. **Teen `.env` settings** poora behaviour control karti hain: `RUN_EVERY_N_MINUTES` (default 60), `RUN_EVEN_WHEN_MARKET_IS_CLOSED` (overnight trading guard), `USE_MANY_MODELS` (GPT-4o mini vs per-trader models).
2. **Orchestrator surprisingly chhota hai** — traders banao, trace register karo, `while True` me `asyncio.gather` se sab chalao, sleep karo, repeat. Complexity agents/MCP servers me hai, glue code me nahi.
3. **Async = parallel traders** — jab ek trader I/O pe waiting hai, doosra chalta hai; isliye charon ek saath kaam karte dikhte hain.
4. **Launch sirf `uv run trading_floor.py` hai** — UI pe traces flying, colors se pata chalta hai kaunsa MCP server/tool call ho raha hai (red = apna accounts server).
5. Asli learning point: **autonomy ko visually dekhna** — multiple agents + multiple MCP servers ek commercial objective pe kaam karte hue, aur traces se sab kuch inspectable.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

So first we take a look at some code and then we go and run our trading floor. So I wanted to point out that there are a few settings in the ENV file that you can control. You need to put these in there to make sure that things work properly. RUN EVERY N MINUTES just literally like that. Equals 60 will make sure that it that it runs every 60 minutes. Actually if you if you don't include it in your env file it will default to 60. Anyway, RUN EVEN WHEN MARKET IS CLOSED, is how you can make sure that it doesn't start trading all night overnight every every hour. And now I currently have this. True because it is Sunday right now. And I want to I want it to be trading and USE MANY MODELS. If it's false, it just uses GPT-4o mini. If it's true, it uses the models that we just saw in the user interface. And so obviously I have it as true.

All right. And now I need to show you the class that brings it all together. That is wonderfully simple and is a fitting conclusion to the other material that we've covered. So we collect the variables that I just mentioned from the env file. These are the names of our agents. And then we simply look how short this is. We create our traders. Uh, so we create a collection of traders for each of these different traders. And then here is the run every n minutes function. This is the one that that does everything. It all happens here. We start by adding this trace. This is where we register that we want OpenAI Agents SDK to record any traces using that log tracer that I created that I showed you a moment ago. We then create our traders as done here. And then there's a nice little while true, uh, thing here. So this will keep going forever. Um, it will then call async gather, which you remember means that all these async methods will happen at the same time. Trader run for each of our traders so all four traders will be kicked off at the same time, and asyncio will make sure that they all run as if as if it's multithreaded. But of course, what's going on is that anytime one of them is is locked on, IO is waiting for something to come back, another one will run that will allow them all to run. Uh, and uh, at the end of that, it will then sleep for the number of minutes that we specify. And finally there's this if name is main. And that's where we kick off this whole thing. So all that remains now is for me to actually kick this off. Let's do it.

And so the time has come now to launch our trading floor. See these agents in action and see in particular this while true loop running. So I'm going to bring up a terminal. This is our running user interface. I'm going to open a new terminal window to run. At the same time, I'm going to change to the sixth directory and I'm going to do uv run trading_floor.py. And this is now kicking off our agent process and running our various agents. So it's running four different traders and their researchers. And right away you can see I hope that the information in these panels has started flying by. And this of course is our user interface tracking the traces that we have intercepted and written ourselves so that we can be managing the logs. It's being stored to a database and and showing here visibly on the user interface. And it is terrific fun to watch this and see autonomy in action.

You'll see the different colors representing things like calling different MCP servers actually using tools. The red when you see it is when it's actually calling our accounts business logic, our own home grown MCP server and that noise, if I don't know if it comes through on this mic, but it just made a notification noise that one of our four traders of Warren or George or Ray or Cathie just made a trading decision and I got alerted about it, and they will now be off and running. It typically takes them a few minutes. Uh, thanks to the joys of async coding, they can run in parallel like this as they do their thinking. They will go through managing their portfolio, and down below you can see things like their current holdings and their recent transactions. So you can keep keep stock on what they're doing. Uh, and uh, yeah, as I say, it's uh, it's it's terrific. Terrific fun to see this.

Here we go. We can just see here. Sold five AMD shares, retrieving account details and then sold three Qualcomm and bought four Nvidia shares as Warren. Uh, they do tend to love Nvidia. Uh, so um, which must be something to do with the researcher and some other share activity going on, and an update there to our to the values of the portfolios. Oh, and another text message I just got, which is and another one which is trading going on AMD trade apparently. Uh, and yeah, as I say, this is super addictive. I absolutely love watching this.

Obviously the learning point here is to really get this very visual, very real, tangible sense of what it's like to have multiple agents working, uh, calling other agents and using a bunch of different MCP servers to achieve a commercial objective. Uh, and being able to use this as a way of inspecting what's going on and understanding the LLM activity that's happening behind the scenes to allow for this trading activity. So hopefully when you run this yourself and get this sense, uh, you'll find it, uh, highly, highly educational and insightful as well as being quite a lot of fun.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
