# L126 — Day 5: Which Agent Framework Should You Pick?

> **Week 6 — MCP** · ⏱️ ~9m · 🎥 Lecture 126 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 50768373

---

## 🎯 Ek Line Mein (TL;DR)

Capstone ka grand finale shuru — **4 autonomous traders** (Warren, George, Ray, Cathie) ka **trading floor**, har trader alag **LLM model** pe, **custom TracingProcessor** se traces SQLite me log hote hain, aur ek **Gradio UI** sab kuch live dikhata hai.

---

## 📝 Hinglish Explanation (Detailed)

- **Week 6, Day 5 — grand finale.** Ye capstone project ka conclusion hai, aur saath hi course-end ka bada sawaal bhi answer hoga: **"mere project ke liye kaunsa framework use karoon?"** (framework-selection discussion isi day ka part hai).
- Capstone me ab naye ingredients add ho rahe hain:
  - Single trader → **trading floor of 4 traders**.
  - Traders ko **autonomy** milegi apni **strategy evolve** karne ki (self-modifying strategy!).
  - **Multiple models** — har trader ek alag LLM pe chalega.
  - Ek **user interface (Gradio app)** banega, jisme ek **surprise extra component** hai — ek super important **extensibility** feature jo **OpenAI Agents SDK** se milta hai (tracing extensibility, neeche dekho).
- **Lab 5 setup:** week 6 folder me lab 5 zyada text-heavy hai. MCP servers sab dekh chuke hain — push notification, memory, market, etc. Recording ke time **6 MCP servers, 44 tools, 2 resources** the. Ed ka plan hai aur add karte rehna, aur wo chahta hai ki students bhi apne MCP servers add karein.
- **Char traders — industry legends ko homage:**
  - **Warren** → **Warren Buffett**: value-oriented investor, long-term wealth creation.
  - **George** → **George Soros**: aggressive **macro trader**.
  - **Ray** → **Ray Dalio**: **systematic, principles-based** approach with macro-economic insights.
  - **Cathie** → **Cathie Wood** (Ark Investments): **disruptive innovation**, especially crypto — lekin kyunki ye equity-trading project hai, **crypto ETFs** use hote hain.
- **`reset.py` module:** yahin har trader ki strategy (system-prompt style text) defined hai. `reset_traders()` run karne se sab traders **$10,000** starting balance ke saath fresh strategies pe set ho jaate hain. Ed khud reset nahi karta kyunki uske paas **2 weeks ki trading history** hai jo wo dikhana chahta hai — lekin students ko **reset line uncomment karke run** karna chahiye.
- **Traces — the surprise extensibility:** OpenAI Agents SDK lightweight hai, lekin LangGraph + **LangSmith** jaisi heavy observability plumbing nahi hai — default tracing "cheap and cheerful" hai (OpenAI dashboard me login karke dekho). **Lekin** tracing **very extensible** hai:
  - LangSmith se connect kar sakte ho, **Weights & Biases** se bhi.
  - Ya **khud extend** karo — programmatically trace data handle karke actions lo.
- **Custom TracingProcessor:** Ed ne `traces` module me OpenAI ki **`TracingProcessor`** class ko **subclass** kiya. **4 methods override** karne hote hain: **`on_trace_start`**, **`on_trace_end`**, **`on_span_start`**, **`on_span_end`**. Har method me ek object milta hai jo batata hai kya ho raha hai — usme se relevant info pluck karke jo chaaho karo.
- Ed ne isse apna **logging mechanism** banaya: name + type + message ke saath log **SQLite database** me store hota hai (`write_log`), per-trader. Isse agent framework ke andar ki tracing activity pe actions le sakte ho — aur sabse important: **UI pe display** kar sakte ho ki traders kya soch rahe hain, kya kar rahe hain.
- **Gradio UI (`app.py`):** Ed ko Gradio pasand hai, lekin course Gradio sikhane ke liye nahi hai, isliye detail me nahi gaya. Structure simple hai:
  - **`Trader` class** — ek trader ke around business rules / calls wrap karti hai.
  - **`TraderView` class** — us trader ke **visual elements** handle karti hai, **periodic screen refresh** ke saath.
  - **`create_ui()`** — final Gradio layout + launch.
- **Demo:** terminal me `uv run app.py` → 4 columns = 4 traders. Model assignment:
  - **Warren → GPT-4.1 mini**, **George → DeepSeek V3**, **Ray → Gemini 2.5 Flash**, **Cathie → Grok 3 mini** (crypto investor ke liye appropriately Grok!).
- **Results after ~2 weeks:** sab $10,000 se shuru hue, **chaaron profitable** hain (fortune nahi, thoda-thoda profit). **Cathie is winning.** 4 me se 3 traders ke portfolio me **Nvidia** stock hai. UI pe trace info + portfolio chart dikh raha hai (kuch din na chalane se performance me jump-down dikha).
- **Important catch:** abhi UI sirf **database ka snapshot** dikha raha hai — kuch **dynamic** nahi ho raha. Asli mazaa tab aayega jab traders ko **actually trade karne ke liye kick off** karenge — that's next.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Trading Floor** | 4 autonomous trader agents ka capstone setup — har ek alag persona + alag LLM model pe |
| **Warren / George / Ray / Cathie** | Buffett (value), Soros (macro), Dalio (systematic), Cathie Wood (disruptive/crypto ETFs) ko homage |
| **`reset.py` / `reset_traders()`** | Traders ki strategies define + reset karta hai; sab $10,000 se fresh start |
| **Strategy autonomy** | Traders ko apni investment strategy time ke saath khud evolve karne ki permission |
| **TracingProcessor** | OpenAI Agents SDK ki class jise subclass karke custom tracing/observability plug karte ho |
| **on_trace_start/end, on_span_start/end** | TracingProcessor ke 4 override methods — trace/span lifecycle hooks |
| **Trace / Span** | Trace = poora agent run; Span = uske andar ki individual step/operation |
| **LangSmith / Weights & Biases** | External observability platforms jinse OpenAI SDK tracing connect ho sakti hai |
| **SQLite log (`write_log`)** | Ed ka custom sink — trace events ko per-trader name+type+message ke saath DB me store karna |
| **Gradio `Trader` / `TraderView`** | Business-logic wrapper class vs visual-elements class (periodic refresh ke saath) |
| **`uv run app.py`** | Gradio trading-floor UI launch karne ki command |
| **Snapshot vs Dynamic** | Abhi UI sirf DB data dikhata hai; live trading kick-off agla step hai |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **TracingProcessor = OpenTelemetry ka SpanProcessor/custom exporter** wala hi pattern hai — lifecycle hooks (`on_span_start/end`) milte hain, aur tum apna sink (SQLite, W&B, LangSmith) plug karte ho. Agar tumne kabhi OTel me custom exporter likha hai, ye bilkul wahi mental model hai — vendor lock-in ke bajaye pluggable observability.
- **SQLite as log sink + Gradio polling** = classic "structured logging → dashboard polls DB" architecture. Production me ye Postgres + Grafana hota; yahan single-file SQLite kaafi hai kyunki sab kuch ek machine pe subprocess (stdio MCP servers) ke roop me chal raha hai.
- **Ek process, 4 personas, 4 alag LLM providers** — ye dependency-injection jaisa hai: trader ka "model" bas ek config value hai (OpenAI-compatible endpoints ki wajah se), business logic same rehta hai. Multi-vendor failover/AB-testing ka yahi pattern production agent systems me use hota hai.
- **Hands-on lab:** is lecture ka code khud chalane ke liye ye lab run karo — `Practical/lab4_trading_floor.py` (is repo me, `uv run` se chalta hai, Groq pe free). Hamare labs course se thode alag hain: node/npx wale servers ki jagah **Python FastMCP servers** (`servers/` folder me), aur Brave Search/Polygon paid APIs ki jagah free substitutes (Wikipedia-style **memory server** + **simulated market server**) — lecture wale memory/market MCP servers ka kaam yehi free versions karte hain.

---

## 🧠 Takeaway (yaad rakho)

1. Capstone finale = **4-trader trading floor**: Warren (Buffett), George (Soros), Ray (Dalio), Cathie (Cathie Wood) — har ek alag model pe (GPT-4.1 mini, DeepSeek V3, Gemini 2.5 Flash, Grok 3 mini).
2. **OpenAI Agents SDK ki tracing extensible hai** — `TracingProcessor` subclass karo, 4 lifecycle methods override karo, aur traces ko LangSmith/W&B/apne SQLite sink me bhejo.
3. Ed ne traces ko **SQLite me log** kiya taaki **Gradio UI** pe live dikha sake ki traders kya soch/kar rahe hain — observability ko product feature bana diya.
4. `reset.py` me strategies hain; **reset_traders() chalana mat bhoolna** ($10,000 fresh start), warna purani/empty state milegi.
5. 2 weeks me chaaron traders profitable, **Cathie winning**, 3/4 ke paas Nvidia — lekin abhi UI sirf snapshot hai; live trading kick-off next lecture me.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

While it's all been leading up to this. Welcome to the grand finale. Welcome to week six, day five, the conclusion of our capstone project, and also the time when we wrap up and answer the question of, okay, so which framework should I use for my project? But first, the capstone project, autonomous trading. We have some ingredients to add to the mix. We're going to turn it into a trading floor of four traders. We're going to give the traders autonomy to evolve their strategy. We're going to expand the number of models. You've already seen a little teaser of this, and we're going to build a user interface, which is going to have a surprise extra component, which is a super important piece of functionality extensibility that we can get through OpenAI Agents SDK. So without further ado, let's go back to the lab for the final time.

And here we are once more in Cursor for the last time. We go into the sixth folder and we go to lab five, which is really more of a text thing, but let's just talk about what we have here. So we've, uh, actually now we've already taken a look at all of the MCP servers that we're going to be playing with, but it includes, of course, things like the push notification and the memory and everything else. But I want to be adding more in time. And I would like you to as well. And so if you go in there and you look in the MCP servers, you might find that there are more there already. Uh, because I do plan to be adding more and if not, you should keep adding them in. As of the time I record this, there are currently, as we just saw, six MCP servers with 44 different tools and two resources, and I do hope to be adding to them in time.

Okay, so now to introduce you to the four traders that we have set up in our trading floor, we have four traders that are now known. They are named Warren, George, Ray and Cathie, and they are paying homage to four luminaries of the industry — Warren to the legend that is Warren Buffett, George to George Soros, Ray for Ray Dalio and Cathie, perhaps an odd one out for a more modern investor, for Cathie Wood of Ark Investments. And they each have investment strategies inspired by their namesakes. Uh, but also I've given them autonomy to be changing their strategy in time.

So let's look at this. So first of all, we need to go to a Python module called reset.py. And this is where the strategies are laid out. There is a Warren strategy. Uh, you are Warren. You are named in homage to your role model, Warren Buffett, a value oriented investor prioritizing long term wealth creation. George is named for George Soros, an aggressive macro trader. Ray, of course, systematic principles based approach, uh, with macro economic insights. And Cathie, who pursues disruptive innovation, particularly crypto. But I focused on crypto ETFs because this is all meant to be about equity trading. So ETFs is what we do. Um, and reset traders will reset these for people to have this strategy. Now I'm not going to run that reset method myself because I've already had this running for a couple of weeks. And I don't want to delete all that history. I want you to see how these traders have done for the last couple of weeks, because that's going to be fun. Um, so I won't reset, but you, of course should, so that you have the right strategies if you're looking at this. So you should uncomment this line right here and run reset traders so that everything is ready to begin.

And then I need to talk to you about traces. Okay. So I now want to tell you about traces. One of the things you might have thought about OpenAI Agents SDK is that whilst it is quite lightweight and simple, which is nice, it perhaps doesn't have the same level of resiliency and plumbing that something like LangGraph has with its connectivity to LangSmith. The trace functionality in OpenAI — it's a little bit sort of cheap and cheerful. You have to log in to your OpenAI screen and then see the tracing in there. Well, it happens that they thought of that. They've made the tracing functionality in OpenAI Agents SDK very extensible. You can, in fact, connect it to LangSmith to be able to look at your data in LangSmith. You can also connect it to things like Weights and Biases, which I teach in my other course, which is super useful. And indeed, you can extend it yourself to record trace information however you would like, so that you can programmatically handle that with your agent flow and take actions as a result of tracing. And that is really cool and it's very easy to do.

And I've done it here in this traces module. So you essentially make a subclass of an OpenAI class called TracingProcessor. And in that subclass you have to override four methods: on trace start, on trace end, on span start and on span end, and you get passed in an object that describes what's going on, and you can then choose to do what you want, record it in any way. And what gets passed in could be one of a number of different types of data, and you can pluck out relevant information and decide what to do with it. And so what did I use this for? What have I decided to do with it? I've decided to have my own little logging mechanism. And so I write this to my own log with a name and a type and a message, and I actually store this in SQLite. I have this write log, just writes it to a database based on this person's name, so that I can keep track of these logs, and that allows me to take some actions as a result of the tracing activity happening in my agent framework. And what would I like to do with that? Well, I'd like to display it. I'd like to be able to see on the user interface, what are our traders actually doing? What are they thinking, what's going on? And I'd like to be able to reflect what is effectively being recorded in OpenAI's traces on the user interface, and that is what we will be doing.

Okay, so we've talked about the user interface. Let's see what it is. Well, this is the code for it. It's a Gradio app. And you probably know that I love Gradio. Now the purpose of this course is not to teach you about Gradio. So I'm not going to go through this in a lot of detail, but it is very simplistic. Uh, I've got like a class Trader, which is going to wrap my various calls to, to organize the business rules around a trader for this screen. And then I've got a sort of companion class, TraderView, which deals with the visual elements associated with any trader. And it has something that periodically refreshes the screen. And then this ends with just the create UI that has the final Gradio code to create it, and something that launches the screen. So you can look at the UI code if you wish. It's not super important. What's important is what information it shows us. And let's take a look at that right now.

So I press control and backtick to open a terminal. I go into the sixth folder and now I type uv run app.py to launch our Gradio app for our autonomous traders. And here it is. Here in a nutshell is the UI for our traders. And I gotta tell you, I love this. So the four columns here represent our four traders. This is the TraderView object with the trader behind it — Warren. And in this case Warren is controlled by GPT-4.1 mini. George is DeepSeek V3, Ray is Gemini 2.5 Flash and Cathie is using, appropriately for a crypto investor, Grok 3 mini. Um, and one thing that's kind of fun is to see that this has been running for a few weeks, and all four of my traders are profitable. They all started with $10,000. That is what happens when you call reset, and none of them have made a fortune, but they have all made a little bit of money. And the winner right now is Cathie. Uh, the, uh, Cathie seems to be doing quite well with her portfolio. And it does look like three out of the four have Nvidia stock in their portfolios. Um, and you can see here some fun looking stuff that we're seeing the trace information about these traders. And of course we're seeing this chart here that shows what's been going on with their portfolios. Um, and I haven't actually run them for a few days, which is why there's been this sort of jump down of, of their performance. Uh, so this is pretty cool. This is the user interface that's looking at our traders. But if you're following, you'll realize that we're not actually seeing anything dynamic here. We're just seeing a snapshot of the data in the database that reflects our four traders. What we really want to see is what happens when they start trading, when we actually kick this off and run it. And that is what we're going to do right now.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
