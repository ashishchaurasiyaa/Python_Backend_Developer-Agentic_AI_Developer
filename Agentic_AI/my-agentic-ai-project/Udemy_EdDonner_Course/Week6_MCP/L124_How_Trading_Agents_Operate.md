# L124 — Day 4: How Trading Agents Operate and Make Decisions

> **Week 6 — MCP** · ⏱️ ~7m · 🎥 Lecture 124 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 50768337

---

## 🎯 Ek Line Mein (TL;DR)

Pichle lecture ka "missing Tesla shares" mystery **traces** se solve hota hai (**insufficient funds error** — jo Week 3 ke **CrewAI agents** ne khud likha tha!), aur phir lab/notebook se **production Python modules** ki taraf move karte hain — `mcp_params.py` (MCP server configs) aur `templates.py` (prompt templates) ke saath **separation of concerns** ka demo.

---

## 📝 Hinglish Explanation (Detailed)

- **Pichle lecture ka hiccup solve:** Ed ne recording rokne ke baad notice kiya ki trace me trader ne **Tesla stock buy** kiya tha, lekin na final report me mention tha, na holdings me dikha. Kya hua?
- **Trace investigation:** Ed wapas trace me gaya, "load more" karke scroll down kiya — bottom me **2 buy attempts** mile: pehle **50 Disney shares**, phir **30 Tesla shares**.
- **Root cause — tool error:** Tesla wale buy pe tool se **error** wapas aaya: *"Insufficient funds to buy shares"*. Matlab trade execute hi nahi hua.
- **Sabse brilliant part:** Ye error message **Week 3 ke CrewAI agents ne khud likha tha**! Tab humne business requirement di thi ki user apni capacity se zyada shares na khareed paye — wahi guard-rail code (aur uska error message) ab MCP tool ke through surface ho raha hai. Pura system **end-to-end consistent** hai:
  - Isliye shares buy nahi huye
  - Isliye summary me mention nahi tha (sirf "monitor in next steps" likha)
  - Isliye holdings me bhi nahi dikha
  - Sab kuch **perfectly working** — bug nahi, feature hai!
- **Ed ka bada lesson — "Start in the lab":** Agentic solutions banane ka sahi tareeka:
  - **Notebook/lab me experiment karo pehle** — prompts, alag-alag agent configurations try karo
  - Samjho ki agent ko kitni capabilities de sakte ho ki wo **coherent** rahe aur instructions follow kare
  - **Autonomy vs coherence** ka balance practice se aata hai, theory se nahi
  - Log seedha "boxes with agents talking to each other" wala bada diagram banakar code likhna chahte hain — Ed kehta hai ye galat approach hai. Pehli baar me kaam nahi karega
  - **Little by little, start small** — experiments done? Ab Python modules me convert karo
- **Ab code structure — 3 files:** `mcp_params.py`, `templates.py`, aur `traders.py` (ye lecture pehle do cover karta hai).
- **File 1 — `mcp_params.py` (MCP server definitions):**
  - MCP params ko alag module me rakhna **mandatory nahi**, but tidy/organized practice hai — *right concerns in the right file*
  - **Market data ke liye choice:** ya to **official Polygon MCP server**, ya hamara **homegrown market server** jo results **cache** karta hai taki free Polygon plan ke **rate limits** exceed na ho — `.env` setup ke hisaab se pick hota hai
  - **Trader ke MCP servers (3):** ① **accounts server** (homegrown), ② **push server** (push notifications — Ed ka favourite), ③ **market data server**
  - **Researcher ke MCP servers (3, alag set):** ① **fetch** (Playwright browser se page fetch), ② **Brave Search** (free web search API), ③ **memory** (SQL-based)
  - **Per-trader memory:** Har trader/researcher ka **alag memory file** — trader ka naam pass hota hai aur wahi memory file ka naam banta hai. Matlab har trader ki **apni separate memory**!
- **File 2 — `templates.py` (prompt templates):**
  - Har function jo **prompt/instruction/string return** karta hai, is file me — taki functionality wale code me text ka clutter na ho
  - **Separation of concerns:** Prompts edit karne hain to ek hi jagah jaana hai
  - Opinionated frameworks (**LangChain**, **CrewAI**) ye separation force-type karte hain — Crew me **YAML files** hoti hain prompts ke liye. Hum wo frameworks use nahi kar rahe, lekin khud ye **discipline** apply kar sakte hain
  - Isme hai: **researcher instructions**, **research tool definitions**, **trader instructions**, aur **prompts**
  - **Pro tips jo Ed repeat karta hai:**
    - **Current date prompt me insert karo** — date-tool dene ki zaroorat hi nahi padti
    - **Strategy aur account details bhi directly prompt me daalo**

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Trace debugging** | OpenAI traces me scroll karke tool calls + errors dekhna — yahi se Tesla mystery solve hua |
| **Insufficient funds error** | Week 3 ke CrewAI-written accounts code ka guard-rail jo over-buying rokta hai |
| **"Start in the lab"** | Pehle notebook me prompts/configs experiment karo, phir Python modules likho — big-design-upfront mat karo |
| **Autonomy vs coherence** | Agent ko kitni freedom dein ki wo phir bhi instructions follow kare — ye balance practice se aata hai |
| **`mcp_params.py`** | Saare MCP server configurations ek alag module me — organized separation |
| **Homegrown market server** | Khud ka caching MCP server jo free Polygon plan ke rate limits bacha leta hai |
| **Trader servers (3)** | accounts + push notifications + market data |
| **Researcher servers (3)** | fetch (Playwright) + Brave Search + SQL-based memory |
| **Per-trader memory** | Trader ke naam se alag memory file — har agent ki apni yaaddasht |
| **`templates.py`** | Saare prompts/instructions return karne wale functions ek jagah — jaise CrewAI ki YAML files, but plain Python |
| **Date-in-prompt trick** | Current date prompt me hi inject karo, date-tool mat banao |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Error propagation across layers:** Week 3 ka domain-layer validation (`Insufficient funds`) MCP tool boundary se hokar LLM tak surface hua aur LLM ne us hisaab se report adjust kiya — bilkul waise jaise aapka service-layer exception REST API ke error response me aata hai aur client gracefully handle karta hai. Achhe **error messages LLM ke liye bhi API contract hain** — descriptive error = agent self-corrects.
- **`mcp_params.py` = connection-string config pattern:** Jaise aap DB/Redis/Kafka ke connection configs ko `settings.py`/env-based config me rakhte ho aur env ke hisaab se real vs mock service swap karte ho — yahan official Polygon server vs caching homegrown server ka swap exactly wahi **dependency-injection-by-config** pattern hai.
- **`templates.py` = Jinja2 templates folder ka equivalent:** Prompts ko code se alag rakhna waise hi hai jaise aap HTML/SQL ko business logic se alag rakhte ho. CrewAI ke YAML jaisa enforced nahi, but same discipline — prompts hi aapka "view layer" hain.
- **Hands-on lab:** `Practical/lab4_trading_floor.py` (is repo me, `uv run` se chalta hai, Groq pe free) — is lecture ka code khud chalane ke liye ye lab run karo. Note: hamare labs me lecture ke node/npx servers ki jagah **Python FastMCP servers** (`servers/` folder) hain, Brave Search/Polygon paid APIs ki jagah free substitutes (memory server + **simulated market server**), aur Playwright fetch skip kiya hai — concepts same, plumbing free-tier friendly.

---

## 🧠 Takeaway (yaad rakho)

1. **Traces are your debugger** — Tesla shares "gayab" nahi the, tool error tha; trace me scroll karke hi pata chala. Agentic systems me observability optional nahi hai.
2. **Pehle ka kaam compound hota hai** — Week 3 ke CrewAI agents ka likha validation aaj Week 6 ke MCP trading floor ko safe rakh raha hai.
3. **Lab-first development:** Prompts/configs notebook me experiment karo, phir hi Python modules banao — big diagram + long coding + pray = fail.
4. **Config aur prompts ko code se alag rakho:** `mcp_params.py` (server configs) + `templates.py` (prompt functions) = separation of concerns without framework lock-in.
5. **Practical defaults:** date prompt me inject karo, strategy/account details prompt me daalo, har trader ki alag memory file rakho.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Wait, did you spot that intentional little hiccup there? I was it was just after I stopped recording. I was thinking, and I'm like, hang on a second, hang on a second. We saw that that, uh, in the traces that it bought Tesla stock and it didn't report that it bought Tesla stock. And we didn't see that in our holdings at the end. So let's go back and see what happened there.

So I went back into the trace and I took a look and I scrolled down load more. Uh, and uh uh, sure enough, if we get down to the bottom here, you will see that there were indeed these two buying shares. First of all, it bought 50 Disney shares. And then as I remember it, bought 30 Tesla shares. What's going on? Well, then I scrolled down and saw that it got an error back from this error executing tool. Insufficient funds to buy shares. And what's kind of brilliant about this is that that error message is an error message that was written by our crew agents in week three. We asked it one of our business requirements is that it should put something in there that prevents the person from buying more shares than they can afford. And so that error message. Insufficient funds to buy shares was written by those crew agents. That's what's been surfaced back here. And that is why those shares weren't bought. And that's why it didn't include that on its summary. And indeed why why, although it does mention that it should be monitored in the next steps. And that's why, of course, it isn't in the holdings at the bottom. So there's a great explanation. And it's everything is working perfectly.

So we're now going to go and look at some Python modules, some Python code. And this really brings again this very important point that a great way to work with building agentic frameworks, so building agentic solutions to business problems, is to start in the lab. Start in a notebook like this experimenting with prompts and different agent configurations. And don't move to Python modules until you've done your experiments. I do get a lot of people asking me, how am I going to go about building this agent solution to the following commercial problem. And they want to dive straight into code and building lots of agents, and they want to build a diagram that shows boxes with agents all talking to each other. And I say to them, look, it's super important to begin by experimenting where that data science hat start in the lab, start by experimenting with prompts, understand what are the capabilities that you can give an agent, that it can stay coherent and it can follow instructions. And how can you give the right balance between autonomy and coherence and these kinds of decisions? They come through practice, and it doesn't come from designing a big picture and then coding for a long time, and then kicking it off and then complaining when it doesn't do what you want it to do because it won't the first time if you do it that way. And that's why the right way to approach this is little by little, starting small in the lab. So that's what we've done here. We've done that. We've been in the lab, we've built something, and it's now time for us to turn this into code. And we're going to do that. And I'm going to show you, piece by piece, three different files: MCP params, templates and traders.

So first of all MCP params is where we define our MCP servers. So here we go. We're in mcp_params.py. Now you don't need to have your MCP parameters specified in a python module separate to your other code, but I think this is an organized, tidy way of doing it to keep things nicely. The right concerns in the right file. So in this file, I'm setting up my different MCP parameters that I'll use later when I'm creating the MCP servers. So first of all, for market data I choose to either use the official Polygon MCP server or I use the little sneaky one that we made, market server, that caches results and makes sure that you can use free Polygon without exceeding your limits. So we pick one or the other depending on how your env is set up. Okay. And then the full set of MCP servers for our trader is the accounts server, our homegrown MCP server for accounts, the push server, another little homegrown server sending push notifications because you know I love them. And then the server for the market data.

Okay. And now we've got a separate set of MCP servers for our researcher. There are three of them. First of all fetch, the ability to fetch a page using Playwright browser behind the scenes. Then we're using the Brave search, again, our free Brave search API for web searches. And then this, the return of the memory. We're using our memory. We're using the SQL based memory. And you can see I'm actually going to try and have a separate memory file for each trader based on its name. So the name will be passed in. And that's what we will use here as the, the name of the of the memory file, so that every trader, every researcher has a separate set of memory. Okay. That is the MCP params module.

So the second module I wanted to show you is called templates. And here's the thing, templates.py is just where I have put any function which is returning like a prompt instruction or a string or something like that. And I've done this to be organized so that I don't have tons of text coded within the body of my functionality. And again, this is just a nice, good practice. It's good to separate concerns this way. It means that if I need to edit my prompts, I've got one place to go and do it. I've got effectively my my prompt templates. Uh, in many ways, if you if you think of some of the more opinionated frameworks like LangChain or like CrewAI for for an agent framework, they sort of force you to separate stuff like this? Uh, well, they don't force you. But there are ways around it. But but, uh, Crew, for example, of course, has the YAML files, which, uh, specifically takes away, takes to one side your text. But we're not we're not using those kinds of frameworks, but there's nothing stopping us from, uh, putting us through the discipline of putting all of our texts like this into a separate module. And that's why I've got it here. So I've got, uh, my researcher instructions, my research tool definitions, my trader instructions, and my prompts all here in these different functions. And you'll see I do things like inserting the current date in the prompts, which I said before was a was a very good practice, uh, to avoid having to equip it with the tool that it needs to call. Just put the date in the prompt, and you'll also see how I'm putting the strategy and the account details straight in there in the prompt. So that's templates.py that separates out our uh text into its own module.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
