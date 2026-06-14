# L125 — Day 4: Portfolio Management with Four Autonomous Agents

> **Week 6 — MCP** · ⏱️ ~10m · 🎥 Lecture 125 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 50768351

---

## 🎯 Ek Line Mein (TL;DR)

Lab ka code ab ek proper **`traders.py` module** ban gaya — ek **Trader class** jo **AsyncExitStack** se multiple MCP servers ek saath kholti hai, **researcher agent ko tool** ki tarah use karti hai, aur **trade ↔ rebalance** ke beech alternate karti hai; live run me total **6 MCP servers + 44 tools** use hue.

---

## 📝 Hinglish Explanation (Detailed)

- Ab time hai **`traders.py`** dekhne ka — wo module jisme hamare **trader agents define** hote hain. Lekin pehle Ed ek **fancy Python technique** explain karte hain jo first time dekhne pe confusing lag sakti hai.

- **Problem:** OpenAI **Agents SDK** me MCP server create karne ke liye **context manager** use karna padta hai — `async with MCPServerStdio(params) as server`. Ek-do servers ke liye theek hai, lekin humare paas **bahut saare servers** hain. Har server ke liye alag `with` statement + alag indentation level = code **out of control** ho jata hai (nested pyramid of withs).

- **Solution: `AsyncExitStack`** — ek advanced Python construct. Isse aap ek **list of MCP server params pe iterate** kar sakte ho aur har ek ke liye `enter_async_context()` call kar sakte ho — effectively har server ke liye `with` lag jata hai, **bina nesting ke**. Ed bolte hain: "Don't let it put you off" — agar suspicious ho to read up karo, ya manually nested `with with with` bhi kar sakte ho (simpler but ugly/nested).

- **Module me kya hai:**
  - **Multi-model switching** top pe — sirf OpenAI nahi, **DeepSeek, Grok, Google (Gemini)**, ya **OpenRouter** ke through **koi bhi model**. Jo choose karoge, uske hisaab se **different model provider** pick hota hai. `guides/` directory me iska pura guide hai.
  - Baaki sab **lab notebook ka same code**, bas ek **class `Trader`** me package kiya gaya — instance banao with a **name, agent, model name**, aur off it goes.
  - **Researcher agent as a tool** — trader agent ke andar research agent tool ki tarah wired hai (same pattern as before).

- **Trade vs Rebalance alternation (fun part):**
  - Trader ko ability di gayi hai ki wo **trading decisions** aur **portfolio rebalancing** ke beech **alternate** kare.
  - Agar **`do_trade` flag** set hai → **trade message** run hota hai; warna → **rebalance message** ("you should rebalance your portfolio to be optimized" — `templates.py` me dekho).
  - Bottom me **`run()`** — ye **business function** hai jo sab kickoff karta hai, run chalata hai, aur phir **`do_trade` flag flip** kar deta hai (toggle). Ek aur cheez hai jo Ed kal batayenge (teaser!).

- **Lab me live run:**
  - `Trader` class import karo, ek instance banao — naam **"Ed"** — name ke basis pe wo **same account** lookup karta hai (wahi jo pehle Disney shares buy/sell kar chuka tha).
  - **`trader.run()`** call karo — ye pura autonomous process kick off karta hai.
  - **Trace** me dekho: pehle **listing tools**, phir **researcher** ek **Brave web search** karta hai, phir **trader** bahut saare **tickers** lookup karta hai, **buying** karta hai — **Amazon, Apple, Microsoft** — aur end me kuch **selling** bhi (kyunki strategy aggressive hai), aur last me ek **push notification** bhejta hai.

- **Push notification "error" (interesting bug):**
  - Trace me dikha "error running the tool" — lekin Ed ke **phone pe notification actually aa gaya**, exact same message ke saath! Tool worked fine.
  - Ed ka guess: **method ne kuch return nahi kiya** (returned nothing), isliye error dikha. Just in case, unhone method change kar diya. Overall: **"wholehearted success"**.
  - Run total **48 seconds** me complete hua.

- **Verification:** **read accounts resource** call karke check kiya — account me ab **Amazon shares** hain, aur saari **transactions** trading activity ke consistent hain. Module + MCP servers + collaborating trader & researcher = sab kaam kar gaya.

- **Tool count (grand total):** `mcp_params` module se **trader + researcher params** import karo, add karo, iterate karke har server ke tools collect karo → total **6 MCP servers** aur **44 tools** do agents ke liye available the. "That's a lot of tools!"

- **Challenge:** **Aur tools add karo** — "the more the merrier". Agar aap **finance me kaam karte ho**, business knowledge hai, to ye sirf surface scratch hai — tons more capabilities add kar sakte ho. Lekin Ed ki strong advice: **pehle lab me experiment karo** (models kya kar sakte hain samjho), **phir** modules me daalo aur final architecture me run karo.

- **Day 4 wrap:** Bahut ground cover hua — khud replicate karo, code padho, **prompts tweak karo** (sab `templates.py` me hain) aur dekho trader ke characteristics kaise change hote hain. **Kal big moment:** full platform unveil + finishing touches + **big question ka answer — "itne saare agent frameworks me se mere project ke liye kaunsa choose karu?"** — grand finale!

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **`traders.py`** | Trader agents define karne wala Python module — lab notebook ka code class me packaged |
| **`AsyncExitStack`** | Python construct jo multiple async context managers ko loop me handle karta hai — N servers ke liye N nested `with` ki zaroorat nahi |
| **`enter_async_context()`** | AsyncExitStack ka method — har MCP server param ke liye effectively ek `async with` laga deta hai |
| **Trader class** | Reusable class — name + agent + model name do, autonomous trader ready |
| **Multi-model switching** | OpenAI ke alawa DeepSeek, Grok, Google, ya OpenRouter se koi bhi model use kar sakte ho |
| **OpenRouter** | Ek router service jo kisi bhi model provider se connect karne deti hai |
| **Researcher as tool** | Research agent trader agent ke andar ek tool ki tarah wrapped hai (agent-as-tool pattern) |
| **`do_trade` flag** | Toggle flag — set hai to trade message, warna rebalance message; har run ke baad flip hota hai |
| **Rebalance** | Portfolio ko optimize karne ka instruction — trading se alag ek maintenance action |
| **`templates.py`** | Saare prompts/messages ek jagah — yahi tweak karke trader ki personality change karo |
| **`run()`** | Business function — pura process kickoff karta hai aur do_trade flag flip karta hai |
| **Trace** | OpenAI platform pe run ki step-by-step visibility — tools listing, searches, buys/sells sab dikhta hai |
| **Read accounts resource** | MCP resource jisse account state (shares, transactions) verify karte hain |
| **6 servers / 44 tools** | Is run me trader + researcher ko total kitne MCP servers aur tools available the |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **`AsyncExitStack` = `contextlib.ExitStack` ka async cousin** — bilkul wahi pattern jo aap dynamic number of DB connections/file handles ke liye use karte ho. Cleanup **LIFO order** me hota hai (Go ke `defer` jaisa). N MCP servers = N subprocess pipes; stack ensure karta hai sab gracefully close ho, chahe beech me exception aaye.
- **Push notification "error" ka root cause classic API bug hai:** tool method ne **`None` return kiya**, side-effect (notification) ho gaya lekin caller ko empty response mila to error maan liya. Same as HTTP handler jo body return nahi karta aur client timeout/parse error maanta hai — **tools se hamesha explicit ack/result return karo**, sirf side-effect pe rely mat karo.
- **`do_trade` flag flip = poor-man's state machine scheduler** — cron-driven jobs me aap aksar alternating phases rakhte ho (ingest ↔ compact, write ↔ vacuum). Yahan wahi pattern: trade run ↔ rebalance run, state ek boolean me.
- **Hands-on lab:** `Practical/lab4_trading_floor.py` (is repo me, `uv run` se chalta hai, Groq pe free) — is lecture ka code khud chalane ke liye ye lab run karo. Difference: course ke node/npx servers + Brave Search ki jagah hamare labs me **Python FastMCP servers** (`servers/` folder) aur **free substitutes** hain (Wikipedia-style memory server + simulated market server), to tool count 44 nahi hoga — pattern same hai.

---

## 🧠 Takeaway (yaad rakho)

1. **Bahut saare MCP servers = nested `with` hell** → `AsyncExitStack` + `enter_async_context()` loop se flat aur clean code.
2. Lab notebook ka code production-style **`Trader` class/module** me package karo — name, agent, model name se instance banao.
3. Trader **trade ↔ rebalance alternate** karta hai (`do_trade` flag har run pe flip), aur **researcher agent ko tool** ki tarah use karta hai.
4. Live run: **6 MCP servers, 44 tools**, 48 seconds — buys (Amazon/Apple/Microsoft), sells, push notification — aur account resource se verify.
5. **Pehle lab me experiment, phir module/architecture me daalo** — aur prompts `templates.py` me tweak karke behavior change karo. Kal: full platform + framework-selection answer.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Okay. And with this, it's time for us to go and have a look at traders dot py, the module for defining our traders. And just before I do this, I want to mention that there's some fancy Python I've got in here, which looks a bit muddling the first time you see it. One of the slightly hokey things about working with OpenAI Agents SDK is that it's good to use the context managers to wrap creating a server, like I've got right here — this async with, and then the MCPServerStdio passing in the parameters as a server. But that can start to look super ugly if you have a bunch of servers, which we do — we have many. When you have many, you'd have to have a separate with statement, a separate context manager on each line indented, and it gets a little bit out of control.

And there is a Python technique, which is quite an advanced technique, for not having to have a stack like this, but just being able to iterate over lots of context managers, lots of withs, and it looks like this — and with async code as well. It's a little bit muddling, but you can have a with an AsyncExitStack. And then you can do this enter context for each in a list. So this construct that you're seeing here, this code is just taking the MCP server params and iterating over that and effectively doing a with for each of those in turn. So look into this if you wish. It's a construct. I use it to make the code a bit neater, but don't let it put you off. You could equally well just do it the manual way.

Okay, so with that little caveat, let's go and have a look at this. This is the module. It's just taking what we had in the lab and turning it into a Python module. There is some cool stuff at the top here that just allows it to switch different models. So we're not only relying on OpenAI, we can use DeepSeek, Grok, Google, or we can use OpenRouter to connect to any model of our choosing. And if you look in the guides directory, there's a whole guide that talks more about this use of different models. So based on which one you choose, it will pick a different model provider. And other than that, this is basically exactly what was in the lab in the notebook, turned into a class, into a Python module.

And just here is that funky stuff I was just talking about with the stacks. So, you know, if you're suspicious of this, then look into it a little bit more. Read up about this construct here and why I've done it this way. And if you dislike it, you can always manually have the with with with with with. Um, but it will be quite, quite nested. It will look a bit ugly, but it would be a bit simpler to do it that way.

But other than that, everything here simply involves creating a trader agent and using a research agent as a tool. And it's the same code that we had a second ago, and it's all packaged into a nice class Trader, so that we can create an instance of Trader giving it a name and an agent and a model name, and off it will go.

One other thing about it that's kind of fun is that I did have it alternating between making trading decisions and making decisions to rebalance its own portfolio. So I've given it that ability to either trade or rebalance as it wishes. So you can see here that if the do trade flag is set, then it will run a trade message. Otherwise it will run a rebalance message, which — you can look in the templates — is a message to say you should rebalance your portfolio to be optimized. And at the bottom here, in run, this is of course the business function. This is what kicks it all off. It kicks off a run and then it will switch that do trade flag. It will flip it the other way.

So that is the trader module. There's one thing about this I haven't told you yet, which I'm going to tell you about tomorrow. Uh, but this is basically showing you all of the stuff, all of the good stuff that we wanted to build around having an autonomous trader that alternates between trading and balancing its portfolio and uses a researcher agent to help it. And using a bunch of MCP tools.

Okay, so now back in the lab, let's actually see what this module does. So we're going to import that Trader, the class we were just looking at a second ago. We're going to create a new instance called ed of that Trader. So that's now called Ed. And because the name is ed, it's going to look up an account and have access to that same account — the thing that just bought Disney shares and then sold them again, some of them. Uh, and now we're going to call the trader dot run. This is the business. This is the thing that's actually going to kick it off and run this whole process.

Let me get on with it. So I kick that going, and while it's running, we'll let it run for a little bit so it gets started with its activity. We'll open up the trace. Let's see what's happening here. Here it is. And so it's off and running. It's listing tools. And it's thinking — uh, we'll see if we can just refresh it like that. Yep. It's doing a Brave web search and it's now going to take its time over this. So rather than sitting here thinking of what to say for a couple of minutes that will take, I will be right back with you.

Okay. Well, that just ran and it completed. It took 48 seconds. It didn't take too long. And it did end up by complaining that one of the tools had an error. Uh, so we can go and check that out. Um, but otherwise it seemed to do its thing. So let's go and have a look at the trace. Uh, so we'll come in here. Here we go. So it did. Listing tools. It starts with the researcher. The researcher does a Brave web search, and then it comes back. And now we're with the trader. It does a bunch of tickers. It does lots of tickers. It does some buying and some shares. What's it bought? It bought Amazon, um, and more — and Apple and Microsoft. And, uh, that's great. Uh, and then at the end here it does some selling and some shares as well — again, I guess because it's so aggressive. Uh, so, um, looking to sell some shares, and then it ends with a push notification.

And this is where our error happened. Uh, it said that there was an error running the tool, which is interesting, because that looks fine to me. And it's also interesting because I did actually get a push notification on my phone there. Just — it does indeed have exactly the same message. So I got the push notification. Uh, it came through. It worked fine. I'm not sure why the error appeared here. It may be because that method didn't return anything, so I just changed that just in case. But anyways, I'd say that that is a wholehearted success. Uh, agent just worked fine.

Uh, and now we can call our read accounts resource and check what happened. And you'll see, indeed, that we do now have, uh, Amazon shares. And we've done a bunch of these transactions, if you look in here, which are consistent with that trading activity. So it looks like things were successful. We've been able to run our trader agent using this code, using our module, and it's called a slew of MCP servers. And it had collaborating — a trader and also a researcher — to do it.

Okay. And finally, before we wrap up, let's just quickly count how many tools we just used in total. So from that MCP params module we can import the trader and researcher params, add them up and then iterate through them. And for each one, collect the tools and report on the total number of tools that we just made available to our two agents, our trader and researcher agent, in what we just did. And so we had a total of six MCP servers and 44 tools. That's a lot of tools. Uh, so yeah, that was great fun.

And of course, you know what I'm going to say — the challenge for you is that you can add more tools. The more the merrier. We can give more capabilities to our traders to allow them to do more. And of course, if you work in finance, if you have business knowledge of this area, then I'm scratching the surface of what we could achieve with this. And you can add in tons more capabilities than our 44 tools. But again, one more time, I would urge you to start by adding in those tools, working in the lab to understand what the models are capable of and to experiment with it, before you then go and put it into the modules and run it as part of the final architecture.

And that's a wrap on day four. Obviously, we covered a lot of ground, and it's super important that you go through and replicate this yourself and look at things — look at this code to get a good sense of how you go about building these sorts of agent solutions. And of course, make it your own. As always, tweak the prompts, experiment. Remember, they're all in that one module templates.py. So you can experiment with changing the prompts and see how that affects the characteristics of the trader.

But of course, the big moment is coming tomorrow. And we then unveil the full platform. We put the finishing touches on everything, and there's some really cool finishing touches where you bring it all together. And I also want to give some summaries on big picture thoughts on the big question, like: okay, we've covered all these different agent frameworks — so which one should I choose for my project? We'll answer that as well. All in our grand finale next time.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
