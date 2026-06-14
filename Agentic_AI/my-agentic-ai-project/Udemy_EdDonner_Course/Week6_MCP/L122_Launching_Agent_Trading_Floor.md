# L122 — Day 4: Launching Our Agent Trading Floor

> **Week 6 — MCP** · ⏱️ ~8m · 🎥 Lecture 122 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 50768309

---

## 🎯 Ek Line Mein (TL;DR)

Capstone project shuru — **Autonomous Traders**: 4 trader agents + har trader ka apna **researcher agent**, sab **5 MCP servers** (accounts, market data, push, fetch, memory + Brave search) ke tools/resources se powered, jo apne aap financial markets analyze karke **synthetic account** me trades karte hain.

---

## 📝 Hinglish Explanation (Detailed)

- **Capstone project intro** — Week 6, Day 4 pe hum course ke **final section** me enter kar rahe hain: **Autonomous Trading**. Agents khud decide karenge ki financial markets ko kaise analyze karna hai, aur trades karenge us **synthetic account** me jo humne **Week 3** me apni agents ki team se banwaya tha.

- **Project commercial kyun hai?** Ed ka observation: zyada tar modern agentic AI projects bahut **technical** hote hain (jaise teams of coders banana), kyunki possibilities open-ended hoti hain. Ed chahta tha ki capstone ek **true commercial problem** dikhaye — financial markets ko analyze aur understand karna. Isliye trading direction choose ki.

- **Project ke 4 pillars:**
  - **Commercial** — real business problem (market analysis), sirf tech demo nahi.
  - **5 different MCP servers** — tools + resources, jinhe hum count karenge (bahut saare tools honge!).
  - **Agent interactions** — agents aapas me interact karenge.
  - **Autonomy** — agents ko "choose their own adventure" ki freedom — kai decisions wo khud lenge.

- ⚠️ **Disclaimer (Ed baar-baar bolega):** Is project ko **actual trading decisions** ke liye use mat karo! Ye purely **experimental project** hai. Yacht chahiye to autonomous agentic solutions **bech ke** kamao, traders ko markets me "run amok" karwa ke nahi. 😄

- **Setup — lab 4:** Cursor me Week 6 folder → **lab 4** — "Autonomous Traders: an Equity Trading Simulation". Simulation me eventually **4 traders** honge, aur **har trader ka apna ek researcher** hoga, sab MCP servers se powered.

- **Kaun se MCP servers? (recap of the week):**
  - **Accounts server** — humara **homemade/homegrown** accounts MCP server (Day 2 wala) — account read/write karne ke liye.
  - **Fetch** — Day 1 wala web-page fetch server.
  - **Memory** — SQL-based **relationship/knowledge-graph memory** jo pehle dekha tha.
  - **Brave Search** — web search ke liye.
  - **Polygon** — financial market data.

- **Lab-first workflow (Ed ki favourite practice):** pehle **lab/notebook me experiment** karo, phir wahi cheez `traders.py` **module** me pull together karo. Ye Ed ke million-times-repeated point se judta hai — agent projects ko **data scientist ke hat** ke saath approach karo: pehle **investigate & understand**, seedha engineering/building me mat kudo.

- **Polygon decision logic (paid vs free):**
  - Agar **paid Polygon plan** hai → directly **Polygon ka official MCP server** use karo, uske poore tool set ke saath.
  - Agar **free plan** hai → Ed ka **handcrafted tiny `market_server`** use hota hai. Do reasons:
    1. Free plan pe model ko **bahut saare tools se overwhelm** nahi karna chahte.
    2. `market_server` me **previous day's data caching** ka trick hai taaki Polygon free plan ke **rate limits** exceed na hon.

- **Push server — naya homegrown MCP server:**
  - Single tool: **`push`** — ek **push notification** bhejta hai (Ed ko push notifications pasand hain — agent jab khud message bhejta hai to bahut "autonomous" feel hota hai!).
  - Tool ek chhota **pydantic object** leta hai — "a brief message to push".
  - Important design note: yahan **saari logic ek hi Python module me** hai — koi alag business-logic layer ko delegate nahi kar rahe. Ye dikhata hai ki ek chhota tool likh ke use **MCP server ke roop me expose** karna kitna easy hai.
  - **Honest admission:** kyunki hum ye tool **locally khud hi** use kar rahe hain, isko plain **function tool** banana actually **better** hota — MCP server ki yahan koi zaroorat nahi. But practice ke liye MCP server banaya — "why not?"

- **Do alag tool-sets, do alag agents:**
  - **Trader MCP servers** = accounts + market data (Polygon ya market_server) + push notifications.
  - **Researcher MCP servers** = **Brave Search** (brave key ke saath) + **fetch** (web pages padhne ke liye).
  - Dono sets milke model ko equip karenge — next step: inhe **use** me lana.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Capstone project** | Course ka final, sabse bada project — Autonomous Trading floor |
| **Autonomous Traders** | Agents jo khud market analyze karke synthetic account me trades karte hain |
| **Synthetic account** | Week 3 me banaya hua nakli/simulated trading account — real paisa nahi |
| **Trader agent** | Wo agent jo trade decisions leta hai (4 honge eventually) |
| **Researcher agent** | Har trader ka helper agent jo market research karta hai (search + fetch) |
| **Accounts MCP server** | Homegrown server — account read/write tools + resources |
| **market_server** | Ed ka handcrafted tiny MCP server — free Polygon plan ke liye, caching ke saath |
| **Polygon MCP server** | Polygon ka official server — paid plan pe full tool set milta hai |
| **Push server** | Single-tool homegrown MCP server jo push notification bhejta hai |
| **pydantic input model** | Tool ka input schema — "brief message to push" wala typed object |
| **Rate-limit caching** | Previous day's data cache karna taaki free API limits cross na hon |
| **Lab-first practice** | Pehle notebook me experiment, phir `traders.py` module me productionize |
| **Data scientist's hat** | Pehle investigate/understand karo, seedha engineering mat karo |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Paid-vs-free server switch** classic **adapter pattern + feature flag** hai: same MCP interface, do implementations (official Polygon server vs handcrafted `market_server`). Aapne ye DB drivers/payment gateways ke saath kiya hoga — yahan extra twist ye hai ki **tool count bhi ek cost hai**: zyada tools = zyada prompt tokens + confused model. API surface ko consumer ke hisaab se trim karna (jaise BFF pattern) yahan bhi apply hota hai.
- **`market_server` ki caching** = aapka jana-pehchana **rate-limit + cache-aside** pattern (Redis ke saamne slow upstream API). Free-tier upstream ke aage cache layer lagana backend me daily routine hai — MCP server bhi bas ek service hai jiske andar yahi tricks chalte hain.
- **Push server ka confession** ek badi architecture lesson hai: **protocol overhead tabhi justify hota hai jab boundary cross karni ho.** Locally use hone wale tool ke liye MCP server banana waise hi hai jaise ek hi process ke 2 functions ke beech gRPC daal dena — demo ke liye theek, production me plain function tool better. Boundary ho (alag repo/team/process/language) tabhi MCP layer lagao.
- **Hands-on lab:** `Practical/lab4_trading_floor.py` (is repo me, `uv run` se chalta hai, Groq pe free) — is lecture ka code khud chalane ke liye ye lab run karo. Ek difference: lecture ke node/npx servers + paid Brave Search/Polygon ki jagah hamare labs **Python FastMCP servers** (`servers/` folder) aur free substitutes (Wikipedia-style memory server + simulated market server) use karte hain.

---

## 🧠 Takeaway (yaad rakho)

1. Capstone = **Autonomous Trading floor**: 4 traders + per-trader researcher, **5 MCP servers**, agent interactions, aur real **autonomy** (agents khud decisions lete hain).
2. Trader tools = **accounts + market data + push**; Researcher tools = **Brave Search + fetch** — alag agents ke liye alag, curated tool-sets.
3. Free Polygon plan pe **tiny handcrafted `market_server`** use hota hai — kam tools (model overwhelm na ho) + **caching** (rate limits bach jayein).
4. **Push server lesson:** local-only tool ke liye MCP server overkill hai — plain tool better hota; MCP tab jab boundary cross karni ho.
5. **Lab-first, data-scientist mindset:** pehle notebook me experiment karke samjho, phir `traders.py` jaise module me engineer karo. Aur haan — **real trading ke liye use mat karo!**

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

It feels like just a second ago that we were starting this thing, and somehow we're already on week six, day four. We are heading into the final, final section with the capstone project, and let's make sure that we end this thing in style. This is going to be a great project. Welcome. Welcome to the Capstone project. Welcome to Autonomous Trading. We are going to build agents that can make their own decisions about analyzing financial markets, and that can make trades in a synthetic account that we have created ourselves in week three with our other team of agents.

Okay, so autonomous traders, then let me tell you a few things about the project that I have in store for you. So first of all, it's something that is commercial. One of the things that I've noticed about a lot of the modern agentic AI projects is that they're quite technical in nature, because they're so open to possibilities that one tends to build things like teams of coders and stuff like that. I really wanted our capstone project to be something that showed how you could apply it to a true commercial problem, like analyzing and understanding financial markets. And that's why I've gone in that direction. It's going to involve having five different MCP servers with tools and resources, and we will count them up. And there's going to be a lot of them. Look forward to it. There's going to be interactions between agents. And there's also going to be autonomy in this. We're going to allow our agents to choose their own adventure. They're going to be given the freedom to make various decisions themselves.

And then most importantly, something that I may say once or twice, please don't use this for actual trading decisions. Uh, this is something which, uh, yes. I don't don't want to, uh, get in trouble if you go and put your all of your life savings into this. This is, of course, an experimental project and nothing more than that. Having said that, of course, if you make a massive fortune on this and you're off sailing your yacht, then I do expect an invitation. Uh, but no, do not, do not, do not use it. Do not get your yacht this way. Get your yacht by building autonomous agentic solutions for people. Not by having your traders run amok with financial markets. Anyway, with that introduction, we're going to spend most of our time sleeves rolled up in code. And let's get started now.

Okay, here we go. Back in cursor. We're going into the folder for week six. And we're going into lab 4, our Autonomous Traders project — an Equity Trading Simulation to illustrate autonomous agents powered by tools and resources from MCP servers. Okay. So we are going to create a simulation. We are going to have four different traders eventually. And one researcher actually — each trader will have their own researcher — powered by a bunch of MCP servers. We're going to have our homemade accounts MCP server that you remember that we did in the second day. We will use fetch that we used in the first day, we'll use memory. We'll use the SQL based relationship memory that we looked at. We'll use the Brave search and we'll use the financial data courtesy of Polygon.

So what we're going to go through now is build this in the lab. And then we're going to look at the code, the module traders.py. That will take the same thing pulled together. And it shows you a practice which I like to do, which is to work initially in the lab while you experiment. And it ties to a point that I know I make a million times that I'll make again at the end, which is how important it is to approach agent projects with a data scientist's hat on. First and foremost, be looking to experiment and understand what you're doing. Uh, not just jumping straight into engineering and building building. It's important to start by investigating and understanding what you're doing. One other thing that's important to do is not use this for trading decisions. If I haven't already mentioned that, uh, so one more warning for that.

Okay. Let's get going. Let's do our imports and set our env. And let's look at the Polygon situation. Do we have an API key? And have you said whether or not we are in a paid plan? We are in paid plan. For me, you may be false there and we're not using the real time Polygon. Okay. What we're going to be doing in the next few cells is collecting together the different MCP server parameters for all of the MCP servers that we're going to equip our model with. So first of all, I've got a little decision here. If we're using any of the paid Polygon plans then we are going to directly use Polygon's MCP server with its whole set of different tools. If not, we're just going to use that tiny MCP server that I handcrafted in market_server. And that's because if you're using the free plan, we don't want to overwhelm the model with lots of different tools. And there's another reason for it too, which is that here I'm using that trick of caching the previous day's data so that we don't exceed our rate limits with Polygon on the free plan. So that's why we've got the little decision there.

And then we're also going to include in our parameters the accounts server. So this is our homegrown MCP server to read and write from accounts. And then there's a new one — push server. I wonder what that could possibly be. Let's just run this. And then we're going to take a quick look at push server. It's another homegrown MCP server. What could it possibly be doing? Let's have a look. Here it is. Push server. Push server of course is going to send a push notification. You know how I like the push notifications because it makes it feel so autonomous when it's like messaging you suddenly. And so we're going to have it pushing. We're going to arm it with an MCP tool. Um, and this is an example of a case where we're writing this MCP server and we're not delegating on to some business logic, we're just putting all the logic right here in this single Python module. It's an MCP server. It has a single tool. It's called push. And it takes a little pydantic object that we've set up here to say that it is a brief message to push, and that is the message that we give. So this is a clear example of how you can write a little tool and expose it as an MCP server.

Now, as I said before, really there's absolutely nothing stopping you from just having this as a tool. In fact, that would be the better way of doing it. There's no point in having an MCP server like this when we're just using the tool ourselves locally, but we want to get into the practice of making MCP servers, so why not? Okay, so with that, we have now also included our push notification as well as the accounts and the market data as our trader MCP servers. So that's set up the MCP servers that our trader will use. But we'll have another agent called the researcher that's able to do market research. And we also want to arm that agent with tools as well. And for that one we will use the Brave key and we'll give it fetch as well. We'll give it the ability to fetch web pages. Um, and so both of these two together are going to be some of the tools that we will equip our model with. All right. And now it's going to be time to put these to use.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
