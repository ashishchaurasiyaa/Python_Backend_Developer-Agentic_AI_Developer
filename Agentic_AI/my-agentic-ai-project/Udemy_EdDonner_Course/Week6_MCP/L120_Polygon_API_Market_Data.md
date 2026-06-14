# L120 — Day 3: Integrating Polygon API for Stock Market Data

> **Week 6 — MCP** · ⏱️ ~5m · 🎥 Lecture 120 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 50767791

---

## 🎯 Ek Line Mein (TL;DR)

Trading-floor capstone ke liye **real market data** chahiye — Ed **Polygon API** (free plan = previous day's close) use karta hai, free plan ke **rate limit (5 calls/min)** ko beat karne ke liye **full-market snapshot + in-memory cache** trick lagata hai, aur phir poore `market.py` ko ek chhota sa **FastMCP server** (`market_server`) bana deta hai jise agent tool ki tarah call karta hai.

---

## 📝 Hinglish Explanation (Detailed)

- **Is week ka main project:** ek **trading floor** banana — **autonomous agents** jo equities **buy/sell** karenge. Real trading nahi hogi — humara pehle se bana hua **simulated account management** (accounts MCP server) use hoga, **lekin market data REAL hoga**.
- Market data ke liye kai **MCP servers** available hain, lekin Ed ne sab try karke jo favorite chuna wo hai **Polygon** ka — ek **well-known professional financial markets data provider**.
- **Polygon ke plans:**
  - **Free plan** — data milta hai **previous day's business close** ka (yaani kal ke close ka stock price). Ed recommend karta hai: **free plan pe hi raho**.
  - **Paid plan (~$20–30/month)** — **15-minute delayed** prices + **unlimited API use**. (Ed khud is par hai kyunki use ye cheezein pasand hain.)
  - **Real-time data** — bahut zyada mehenga; jab tak aap actual trader nahi ho, **koi zaroorat nahi**.
- **Setup steps:** Polygon pe **sign up** karo → left navigation me **Keys** button → blue **New Key** button press karo → key copy karke apni **`.env` file** me **`POLYGON_API_KEY`** ke naam se daalo. Notebook me check chalao — agar "polygon API key is not set" message NAHI aaya, matlab key set ho gayi.
- **Direct client use:** Polygon ka **Python client** directly use kar sakte ho — unke website pe **great docs** hain. Example: **previous close** call se Apple ka price mila — **$195.27**.
- **`market.py` wrapper module + sneaky caching trick:**
  - Free plan **rate limited** hai — sirf **~5 API calls per minute** (Ed: "quite mean"). Matlab share price sirf 5 baar/min pooch sakte ho.
  - **Trick:** ek **full-market snapshot** call (saare stocks ke prices ek saath) bhi **sirf 1 call** count hoti hai! To Ed ka code: agar aap free plan pe ho aur Apple ka price maangte ho, to wo **poora market snapshot** (prior business day) fetch karta hai, use **in-memory cache** kar leta hai, aur subsequent calls **cache se** answer karta hai.
  - Code flow: `get_share_price()` → polygon key check → `get_share_price_polygon()` → paid/free plan check → free plan pe full-market-snapshot wala function → **same date ke liye cached** full market return.
  - **Proof:** Apple ka price `195` mila, phir Ed ne usi call ko **tight loop me 1000 baar** chalaya — har baar `195`, koi rate-limit problem nahi. Cache na hota to turant rate limit hit hoti.
- **`market_server` — ek aur chhota local MCP server:**
  - Same pattern as before: **`FastMCP` instance** banao → **`@mcp.tool` decorator** lagao → function **`lookup_share_price`** jo bas `get_share_price()` ko call karta hai → end me server **launch** karne wala standard block.
  - Itna **simple MCP server** — kuch hi lines me real market data tool-form me available.
- **Agent se test:**
  - Pehle server ke **tools list** kiye — expected: sirf `lookup_share_price`.
  - Phir agent banaya: instructions = *"You answer questions about the stock market"*, question = *"What's the share price of Apple?"*, model ko **latest model** pe upgrade kiya.
  - Same as before: **async context manager** me **MCP server pass** kiya, agent run kiya — agent ne **MCP tool call** kiya aur Apple ka share price bata diya. Ed: "This stuff is simple to you. Now you're an expert at this."

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Polygon** | Professional financial market data provider — stock prices ki API deta hai (free + paid plans) |
| **Free plan (Polygon)** | Previous business day ke **close prices** milte hain; ~5 API calls/min ka rate limit |
| **Paid plan (~$20–30/mo)** | 15-min delayed prices + unlimited API calls (optional, zaroori nahi) |
| **`POLYGON_API_KEY`** | `.env` file me daali jaane wali API key (Polygon dashboard → Keys → New Key) |
| **Rate limiting** | API provider ka rule: fixed time me limited calls allowed (free plan = ~5/min) |
| **Full-market snapshot** | Ek hi call me SAARE stocks ke prices — phir bhi 1 hi call count hoti hai (loophole!) |
| **In-memory cache** | Snapshot ko memory me store karna — same date ki repeat calls cache se serve hoti hain |
| **`market.py`** | Polygon calls ko wrap karne wala Python module (plan-detection + caching logic ke saath) |
| **`market_server`** | `market.py` ke upar bana chhota **FastMCP server** — `lookup_share_price` tool expose karta hai |
| **`@mcp.tool` decorator** | FastMCP me kisi Python function ko MCP tool banane ka tarika |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Caching trick = classic backend pattern:** ye wahi **batch-fetch + memoization** hai jo aap Redis ya `functools.lru_cache` se karte ho — N choti calls ki jagah 1 bulk call, phir cache se serve. Yahan cache key effectively **date** hai (prior business day), isliye stale data ka risk zero hai — data waise bhi din me ek hi baar change hota hai. Rate-limited third-party APIs ke saath ye pattern hamesha yaad rakho.
- **Layered architecture dhyan se dekho:** `polygon client` (SDK) → `market.py` (business logic + caching) → `market_server` (MCP transport layer). Ye bilkul waise hai jaise aap service layer ke upar ek thin **REST/gRPC controller** rakhte ho — MCP server sirf ek **protocol adapter** hai, logic plain Python me testable rehta hai.
- **Hands-on lab:** is lecture ka code khud chalane ke liye ye lab run karo — `Practical/lab3_memory_market_servers.py` (is repo me, `uv run` se chalta hai, Groq pe free). **Difference:** lecture wale Polygon API (key + free-plan rate limits) ki jagah humara lab ek **free simulated market server** (Python FastMCP, `servers/` folder me) use karta hai — caching/tool pattern same, paid API ki zaroorat nahi.
- **Secrets hygiene:** `POLYGON_API_KEY` `.env` me — MCP server subprocess ko env vars **explicitly pass** karni padti hain (stdio transport me parent process env inherit hota hai config ke through). Ye 12-factor app config pattern hi hai, bas subprocess boundary ke paar.

---

## 🧠 Takeaway (yaad rakho)

1. Trading floor capstone = **simulated accounts + REAL market data**; data source = **Polygon API** (free plan kaafi hai — previous day's close).
2. Free plan ka **5 calls/min rate limit** beat karne ka trick: **full-market snapshot = 1 call** → in-memory cache → baaki sab calls cache se (1000-call loop bhi safe).
3. `market.py` me logic, uske upar **`market_server`** — FastMCP + `@mcp.tool` decorator se bas ek tool: **`lookup_share_price`**.
4. Agent integration same purana pattern: context manager me MCP server pass karo → agent tool call karta hai → Apple ka price aa jata hai.
5. **MCP server = thin protocol adapter** over plain Python module — logic ko transport se alag rakho, testing aur reuse dono easy.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

So the main project for this week is to set up a trading floor, have autonomous agents that can buy and sell equities, and they're not going to really buy and sell equities. They're going to be using the simulated account management that we already built, but they will be using real market data. And there's a bunch of different MCP servers that can help provide you with market data. And after playing with a bunch of them, my favorite one is the one provided by the company, Polygon. That's a very well known professional provider of financial markets. Uh, and uh, yeah, I'll bring you to their website. Here they are. It's, uh, they're super well known and, uh, they one of the big benefits that they have is that they have both a free plan and a paid plan. So I recommend you stick with the free plan. But if you're a sucker for this stuff like I am, then for sure you can. You can spend a little. It's somewhere between 20 and 30 bucks a month, uh, to get more accurate market data. So with the free plan, you always get data as of the previous day's business close, stock prices as of yesterday's close. With the paid plan that I'm on, you get them on a 15 minute delay, but unlimited API use. And if you want to pay a lot more, you can get real time market data, but there's no need for that unless you're already a trader.

So this is Polygon. Uh, please come in and sign up. And once you're signed, signed in, select the keys button in the left hand navigation. You press a blue new key button. And then you take that key and you put it in your ENV file as POLYGON_API_KEY. And uh, the, uh, here we go. Just run this. And the fact that it didn't say polygon API key is not set means that it was set. Um, and then you can, for example, directly use the polygon client. And they've got great docs on their websites and it's very easy to use. So this previous close, uh, for Apple's stock price, for example, will tell me that the previous close for Apple was $195.27. And that is how you simply use polygon code directly.

Okay, so I have written a little Python module called market.py that wraps some of these calls to polygon. And I've done something a little bit sneaky. So the polygon API, if you're on the free plan, is what they call rate limited, which means you're only allowed to make that API call, I think it's five times a minute. It's quite, quite mean. Uh, and uh, so you would only be able to call for a share price that five times, but it turns out that that it also only counts it as one call if you make a call and ask for all the share prices in the market, a snapshot of every share price. And so I've done something that if you ask for a share price like Apple and you're on the free plan, it will call for all share prices. It will use that one call and then it will cache that in memory, and the subsequent times you call this, it will just return from the cache.

Let me show you that for a second. If we look in market.py, you'll see here that there's this get share price. Um, I checked you got a polygon key and then I call this get share price polygon. And I see if you're on the paid plan or not. If you're on the free plan, I call this function. If you're following me, and this function is basically going to end up getting the full market for the prior business day, and it will cache that. So if this has been called before with the same date, it will just return the same full market. So it's just a nice way of making sure that we can always get that share price, and we won't hit the rate limits. Let me show you that. If we get the share price for Apple, it's 195. And now I can put that in a tight loop and get it 1000 times, and we simply get 195. And I assure you that if this weren't being plucked from the cache, then we would have problems with that. We would hit the rate limit immediately. So that's just something to to understand. Just something that I've put in there.

Okay. And I've also made this into an MCP server as well. Another little local MCP server called market underscore server. So if you look at market server you will see that this is again a very simple MCP server. It just the same as before. You remember, you create the MCP and then you use the MCP tool decorator. And then here is the function lookup share price. And that just calls get share price. And this is the way that you actually launch the server. So it's really nice to see such an such a simple MCP server here that created.

That means that we can now call that as uh, we can first of all, look at the tools that it gives us. And this should exactly give us the lookup share price. And now we can ask an agent to tell us the share price of Apple. So we'll say you answer questions about the stock market. What's the share price of Apple. Let's upgrade this to be the latest model. And then just as before we use the context manager, we pass in that MCP server. This stuff is is simple to you. Now you're an expert at this. We call our MCP server. And sure enough it all worked great. It called the MCP tool and it told us the share price of Apple.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
