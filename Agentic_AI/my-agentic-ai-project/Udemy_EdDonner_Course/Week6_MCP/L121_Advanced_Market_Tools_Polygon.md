# L121 — Day 3: Advanced Market Tools — Paid Polygon Plan

> **Week 6 — MCP** · ⏱️ ~6m · 🎥 Lecture 121 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 50768267

---

## 🎯 Ek Line Mein (TL;DR)

Agar **Polygon ka paid plan** ho to unka **official MCP server** (uvx se, seedha **GitHub repo** se run hota hai) tumhare agent ko **dozens of market tools** de deta hai — trades, crypto, FX, financials sab — bas due diligence karo aur `.env` me `POLYGON_PLAN=paid` set karo.

---

## 📝 Hinglish Explanation (Detailed)

- Pichle lecture me free plan wala simple price tool dekha tha. **Interesting part** ab hai: agar tumhare paas **paid Polygon plan** hai, to unka **full MCP server** use kar sakte ho with all capabilities. Ed bolte hain ye **totally optional** hai — chaaho to sirf 1 month ke liye sign up karke experience kar sakte ho.
- **MCP server params**: ye **uvx** se launch hota hai, matlab **Python-based MCP server** hai. Interesting baat — yahan **GitHub repo ka direct link** pass kiya jata hai jisme MCP server ka code hai. Yani server ko **pip-installable hona zaroori nahi** — `uvx` seedha repo se run kar leta hai (`mcp_polygon` from that repo).
- **Security / Due diligence** — kyunki tum kisi ka repo seedha chala rahe ho:
  - Check karo ki ye **genuinely official repo** hai Polygon (polygon.io ke peeche wali company) ka.
  - **Community traction** dekho — stars, support, activity.
  - Bilkul waise hi jaise tum kisi ka repo clone karne se pehle research karte ho. Ed ne khud ye check kiya hai, but **tumhe bhi karna chahiye**.
- Phir **Polygon API key** pass hoti hai, aur server se poochha jata hai: *"what tools do you provide?"* — Result: **"wowza"**, bahut saare tools! Examples:
  - **Last trade** nikalna
  - **Crypto data** aur **FX data**
  - **Market status**, **tickers**, **dividends**, **conditions**, **financials**
  - Yani agent ko **financial markets analyse karne ki direct capabilities** mil jaati hain.
- **Free plan catch**: tum saare tools agent ko de to sakte ho free plan pe bhi, **but** zyadatar tools call karne pe bolenge *"this tool isn't available for people on the free plan"* — bore ho jata hai. Solution:
  - Ya to sirf **ek tool** (`get_snapshot_ticker`) provide karo (jaise free plan example me kiya tha),
  - Ya **paid plan** le lo.
- **Live demo me agent unpredictability**: Ed ne explicitly bola tha ki sirf `get_snapshot_ticker` tool use karo, **but agent ne galat tool use kiya** pehli baar! Ed ne **model upgrade** kiya (more recent model) aur dobara run kiya — is baar **sahi tool use hua** aur latest share price **$195** mili.
  - Ed ne deliberately re-record nahi kiya — kyunki ye dikhana important hai ki **agentic AI me kabhi-kabhi ill behavior hota hai**, prompts correctly follow nahi hote, aur tumhe apne design me **iska account rakhna padta hai**.
  - More recent model upgrade karne se behavior better hua (though pakka nahi ki yahi fix tha).
- **`.env` configuration**:
  - `POLYGON_PLAN=paid` → paid plan ke right tools use honge (prices **15-minute delay** pe).
  - `POLYGON_PLAN=realtime` → premium **real-time plan** ke liye, saare real-time APIs use honge.
  - Ed paid plan pe hain, to unhone env file update ki, cell run kiya, aur confirmation mila: *"You've chosen to subscribe to the paid Polygon plan... prices on a 15 minute delay."*
- **Exercises (homework)** — MCP servers ki duniya explore karo:
  - **Marketplaces** pe jao, interesting tools dhoondo, yahin experiment karo.
  - **Teeno approaches** try karo — but practically tumhe milega ki **remote MCP servers easily available nahi hain** (unless tum already Asana jaise kisi service ke paying user ho). To pehli 2 approaches pe focus karo.
  - Aise servers dhoondo jo **purely local** chalein (sirf tumhare computer pe kaam karein), aise jo **web call** karein, aur **Python-based + JavaScript-based dono** try karo.
- **Wrap-up**: Day 3 of Week 6 complete! Ab next: **capstone project — Trading Floor** banana. Ed ke according "such a cool project".

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Polygon MCP server (official)** | Polygon.io ka full MCP server — paid plan ke saath dozens of market tools deta hai |
| **uvx from GitHub repo** | MCP server pip-installable hona zaroori nahi — uvx seedha GitHub repo se Python server run kar sakta hai |
| **Due diligence** | Repo run karne se pehle verify karo: official hai? Stars/traction/support kaisa hai? |
| **Tool gating by plan** | Free plan pe saare tools dikhte hain but call karne pe "not available" — isliye ya 1 tool do, ya paid plan lo |
| **`get_snapshot_ticker`** | Free plan pe kaam karne wala single price tool |
| **Agent unpredictability** | Explicit instruction ke baad bhi agent galat tool choose kar sakta hai — design me account karna padta hai |
| **`POLYGON_PLAN` env var** | `paid` (15-min delayed prices) ya `realtime` (premium real-time APIs) — code right tools pick karta hai |
| **Local vs web-calling servers** | Exercise: kuch MCP servers sirf local kaam karte hain, kuch web call karte hain — dono try karo |
| **Remote MCP servers (reality)** | Abhi easily available nahi — mostly tab useful jab tum Asana jaise kisi service ke paying user ho |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **`uvx` from a GitHub repo = `pipx run git+https://...` jaisa hai** — supply-chain risk wahi hai jo kisi unpinned `pip install` ka hota hai. Production me tum jaise dependency pin karte ho aur source verify karte ho, MCP servers ke saath bhi wahi karo — repo official hai ya typosquat, ye check karna **tumhari** zimmedari hai, kyunki ye process tumhari machine pe tumhare credentials (API keys) ke saath chalta hai.
- **Tool gating by plan** ek classic API design pattern hai — jaise REST API me 403/402 with "upgrade your plan". Lesson: agent ko sirf wahi tools expose karo jo actually kaam karenge, warna LLM failed calls pe waste tokens + confusion karega. Env-var-driven tool selection (`POLYGON_PLAN`) basically **feature-flagging for tool registration** hai.
- **Agent ne galat tool pick kiya despite explicit prompt** — ye distributed systems ke flaky network calls jaisa hai: retry logic, model upgrades, aur tool descriptions tighten karna tumhare "error handling" hain. Deterministic code ki guarantee yahan nahi milti.
- **Hands-on lab**: is lecture ka code khud chalane ke liye `Practical/lab3_memory_market_servers.py` run karo (is repo me, `uv run` se chalta hai, Groq pe free). Difference: hum Polygon paid API ki jagah ek **free simulated market server** (Python FastMCP, `servers/` folder me) use karte hain — concepts same, paise zero.

---

## 🧠 Takeaway (yaad rakho)

1. MCP server **pip-installable hona zaroori nahi** — `uvx` seedha GitHub repo se run kar sakta hai, but pehle repo ki **due diligence** karo (official? stars? support?).
2. Paid Polygon MCP server agent ko **dozens of market tools** deta hai — trades, crypto, FX, financials, dividends — free plan pe ye mostly "not available" bolenge.
3. **Agents unpredictable hote hain** — explicit instruction ke baad bhi galat tool use ho sakta hai; recent model + better prompts se improve hota hai, but design me iska account rakho.
4. `.env` me `POLYGON_PLAN=paid` (15-min delay) ya `realtime` set karke code right tools register karta hai — **config-driven tool selection**.
5. Exercise: marketplaces explore karo — **local-only, web-calling, Python-based, JS-based** sab try karo; remote MCP servers abhi rare hain. Next stop: **Trading Floor capstone**!

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

But that's not the interesting part of using Polygon. The interesting part is if you have a paid plan and you want to use their MCP server with all of the capabilities. And so I'm going to show this to you just so you get a sense for it and totally optional. But if you wish, you could sign up even just for the first month, to experience this for yourself.

So here are the parameters that we're providing for our MCP tool. It is uvx, so it's a Python based MCP server. And you can see interestingly that the way it works is that you can provide a link to the GitHub repo which contains this MCP server. And you can use that. So we're calling mcp_polygon from this repo. So it doesn't have to be something that's like pip installable. It can be something that is just straight from a repo. And obviously if you do something like this then you need to do your research. You need to go and check that this genuinely is the official GitHub repo for Polygon, the company behind polygon.io, and make sure you're comfortable with the community traction, the number of stars, the kind of support it has, and so on. Just as you would do if you were going to clone somebody else's repo. The same kind of due diligence. Exactly. And so I have done that, of course. And I'm satisfied with this myself. But you should too.

And then I'm passing in my Polygon key. And then I'm going to ask, what tools do you provide me, this MCP server. So we'll run this. And wowza, there's a lot of them. So there's a bunch of different tools. There's a lot that the model is going to be allowed to do. It includes doing things like getting the last trade. It has crypto data in here, as well as fx data, getting market status, tickers, dividends, conditions, financials. There's a lot to get here. And so this is something which equips our agent with lots of capabilities to analyse financial markets directly.

Now, you can give all of these tools to your agent, even if you're on the free plan. But if you do that, most of these will respond and say this tool isn't available for people on the free plan. So it's a bit of a bore. What you have to do is either just only provide the one tool, as I did for the free plan example, or sign up for the paid plan.

Okay. So let's try these out. So, as I say, because if you're on the free plan, we have to be specific that it should only use the get snapshot ticker tool. And so I will run this and have it hopefully use the right tool. So we're now equipping the agent with all of those tools that we just saw. And uh oh. And it hasn't used the right tool. That's super interesting. Actually let me also — I'm going to upgrade the model while I'm doing it, even though I said get snapshot ticker. Let's try it a second time. It's always good to see our agents being unpredictable. Let's see whether it gets it right the second time and uses the right ticker. It does. So I'm tempted to go and rerecord this, but I won't, because I think it's important to see that with agentic AI you do get this sometimes ill behavior when it doesn't correctly follow the prompts, and you need to be able to account for that in what you do. And also, I don't know if this is what fixed it, but upgrading to a more recent model did appear in this case to make it perform better. But now it did use the right tool, and it got the latest share price at $195.

Okay, so if you do have a paid plan then you can now add this to your env file. You just have to in your env file say POLYGON_PLAN equals paid. That makes sure that I switch it to use the right tools. And if you do decide to go all the way and have the premium real time plan, you can set this to realtime. And I'll be sure to use all of the real time APIs. But I have got just this paid plan, so I'm going to go and update my env file right now. Okay, so now if I now run this cell, it should confirm that I'm on the right plan. Let's see. Yep. You've chosen to subscribe to the paid Polygon plan. And so we'll be looking at prices on a 15 minute delay.

And that for the time being is our foray into MCP servers. But there are so many more and that's where I will get to with the exercises. So I would suggest that you go on to the marketplaces and look for tools which interest you and experiment with them right here. Try and use, I say here, all three approaches. You'll probably find, like me, that there actually aren't easily available approaches with remote MCP servers, so you might not want to go there unless you are already a paying user of something like Asana. But assuming that you're not, then go with those first two approaches. Find examples of MCP servers that will run locally and only stay locally, do things on your local computer. Find examples that call the web, and find examples of MCP servers that are Python based and those that are JavaScript based, and try them all out. Experiment with them and have fun giving capabilities to your agents and seeing them taking advantage of them.

Well, hopefully you took me up on that. You did some exercises and you've added more MCP servers. And that's a wrap on day three of week six. And that means that we're about to head into the capstone project of building a trading floor. And I can't wait to show you this. It's such a cool project. I'll see you next time.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
