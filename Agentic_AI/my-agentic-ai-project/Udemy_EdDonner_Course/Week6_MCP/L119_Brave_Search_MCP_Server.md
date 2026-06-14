# L119 — Day 3: Brave Search API — MCP Server Calling the Web

> **Week 6 — MCP** · ⏱️ ~9m · 🎥 Lecture 119 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 50767775

---

## 🎯 Ek Line Mein (TL;DR)

**Brave Search** ek free web-search API hai (2000 searches/month) jise hum **Anthropic ke reference npx MCP server** se use karte hain — ye **Architecture Type 2** ka perfect example hai (MCP server **locally** chalta hai, par kaam **cloud API** ko call karke karta hai); saath hi Ed dikhate hain ki **Type 3 (remote SSE servers)** abhi rare aur flaky kyun hai.

---

## 📝 Hinglish Explanation (Detailed)

- **Ek aur search tool, par free wala:** Course me ab tak kai web-search options dekhe — Week 2 ka **OpenAI hosted WebSearchTool** (mehenga, ~2.5 cents per search), phir **Tavily** aur **Serper**. Ab **Brave Search** — ek company jo **API-driven search** me specialize karti hai, especially AI use-cases ke liye.
- **Pricing:** Free tier me approx **2000 searches/month** milte hain — kaafi generous. Sign-up me **credit card bhi nahi chahiye**. Ed khud paid plan pe hain kyunki wo heavily use karte hain, par free tier students ke liye enough hai.
- **Setup:** Brave Search pe account banao → **API key** lo → `.env` file me daalo → notebook me `load_dotenv` dobara run karo.
- **Naya twist — env vars in server params:** Is baar MCP server ke `params` me sirf `command`/`args` nahi, balki **`env` dictionary** bhi pass karte hain — taaki **Brave API key** subprocess tak pahunch jaye. Ye pehli baar hai jab hum server ko environment variables explicitly de rahe hain.
- **Ye bhi node/npx server hai:** Brave Search server ek **JavaScript/Node MCP server** hai jo `npx` se chalta hai. Important: ye **Anthropic ke official out-of-the-box reference implementations** me se ek hai.
- **Architecture Type 2 (samjho flow):** Code **online (npm registry)** pe hota hai → hum use **download karke locally run** karte hain → wo local server phir **Brave company ki cloud web service ko call** karta hai (hamari API key pass karke). Matlab: *server local, kaam remote*. Ed maante hain ki wo isse belabor kar rahe hain, par ye distinction core hai.
- **Connection same as always:** `MCPServerStdio` + params + timeout, phir `list_tools()` karke dekha:
  - **`brave_web_search`** — API se web search karta hai.
  - **`local_search`** — local businesses search karta hai (Ed ko shayad ye **paid plan** ki wajah se mila; free plan me probably nahi aata).
- **Fetch vs Brave — key difference:** **Fetch** me hum **local browser** chala ke ek specific **web address** pe jaate hain. **Brave** me hum ek **web call** karke usse bolte hain "Google-jaisa search chala do" — par wo Google nahi, **apna khud ka search engine** use karta hai aur query ke results lautata hai.
- **Demo:** Agent ko bola — "tum web search kar sakte ho, **Amazon stock price** ki latest news research karo" (current date bhi diya). `Runner.run` se chalaya → result aaya: Amazon ~**$217** + news. **Trace** check kiya — `brave_web_search` call hua, query thi "Amazon Stock Price News May 2025", results sahi aaye. End-to-end working.
- **Ab Type 3 — Remote MCP servers (SSE):** Server **khud remotely** chalta hai, aur aapko **SSE approach** se connect karna padta hai. Par ye **common nahi hai** aur **flaky** bhi — koi guarantee nahi ki server owner use chalu rakhega. Ed ke paas pehle ek free hosted remote MCP server ka example tha, par **wo server down ho gaya** aur wo code hatana pada.
- **Jo remote servers exist karte hain, wo paid/enterprise hain:** Anthropic docs me "remote MCP servers" section hai — companies jaise **Asana** (project management), **Intercom**, **PayPal** (commerce/seller accounts, personal nahi), **Square**, **Zapier**. In sab ke liye aapko **paying client** hona padta hai, isliye Ed demo nahi kar paye. Community me bhi iska zyada traction nahi dikha. Aur mazedaar baat — in commercial examples me se kai ke liye aap **local MCP server bhi chala sakte ho**, jo log typically karte bhi hain.
- **Cloudflare ka option:** Agar aap Cloudflare customer ho, to unke paas tools/sheets hain jisse aap **apna khud ka remote MCP server deploy** kar sakte ho — code walkthrough, running-status check, aur desktop ya **OpenAI Agents SDK** se connect karne ka tarika sab documented hai.
- **Authentication — MCP ka hot new area:** Agar aap hosted tool provide kar rahe ho, to users ko **authenticate** karne ka mechanism chahiye (prove karna ki wo wahi hain jo wo kehte hain). Remote servers ke saath ye critical ban jata hai.
- **Bottom line:** Aaj ki date me **common configuration** ye hai — provider (jaise Brave) se **API key** lo, aur use apne **local MCP server** me pass karo. Managed hosted MCP servers shayad future me boom karein ("I'll be eating my words"), par abhi rare hain. Next: Type 2 ka ek aur really cool example.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Brave Search API** | AI-friendly, API-driven search engine — free tier me ~2000 searches/month, credit card ki zaroorat nahi |
| **`env` in server params** | MCP server params me environment variables (API key) pass karna, taaki subprocess unhe padh sake |
| **Anthropic reference implementation** | Anthropic ke official sample MCP servers me se ek — Brave Search unhi me se hai |
| **Architecture Type 2** | MCP server **locally** chalta hai par actual kaam **cloud service** ko call karke karta hai |
| **`brave_web_search`** | Server ka main tool — Brave ke apne search engine se web search results lata hai |
| **`local_search`** | Local businesses search karne ka tool — mostly paid plan feature |
| **Fetch vs Brave** | Fetch = local browser se ek URL kholna; Brave = web API call jo search results lautati hai |
| **Architecture Type 3 (Remote/SSE)** | MCP server khud **cloud me** chalta hai, aap **SSE** se connect karte ho — rare, flaky, mostly paid enterprise (Asana, Intercom, PayPal, Square, Zapier) |
| **Cloudflare remote MCP** | Cloudflare customers apna remote MCP server deploy kar sakte hain, auth ke saath |
| **MCP Authentication** | Hosted MCP servers ke liye identity verify karne ka mechanism — MCP ka hot emerging area |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Hands-on lab:** is lecture ka code khud chalane ke liye ye lab run karo — `Practical/lab3_memory_market_servers.py` (is repo me, `uv run` se chalta hai, Groq pe free). Fark: lecture ke **node/npx Brave server + paid API key** ki jagah hamare labs **Python FastMCP servers** (`servers/` folder) use karte hain with free substitutes (Wikipedia-style memory server + simulated market server) — concept (local stdio server → external data) bilkul same hai.
- **API-key-via-env pattern jaana-pehchana hai:** Jaise Docker me `docker run -e API_KEY=...` ya systemd unit me `Environment=` — MCP params ka `env` dict bhi wahi hai: parent process subprocess ko **controlled environment** inject karta hai. Secret kabhi tool arguments me nahi, env me jata hai.
- **Type 2 vs Type 3 = sidecar vs SaaS:** Type 2 bilkul **sidecar/local-proxy pattern** hai (jaise `cloud-sql-proxy` — local process, remote backend). Type 3 pure **SaaS endpoint** hai — aur wahi classic SaaS problems: uptime aapke control me nahi (Ed ka demo server hi down ho gaya), auth zaroori, vendor lock-in. Isliye industry default abhi bhi "local server + API key" hai.
- **Trace = distributed tracing:** Ed har run ke baad OpenAI trace check karte hain (kaunsa tool, kya query, kya result) — ye wahi habit hai jo aap Jaeger/Zipkin spans ke saath rakhte ho. Agent ka claim mat maano, **span dekho**.

---

## 🧠 Takeaway (yaad rakho)

1. **Brave Search** = free (~2000/month), AI-focused search API — OpenAI hosted search ($0.025/call) se sasta alternative.
2. MCP server params me **`env` dict** se API keys pass hoti hain — naya twist is lecture ka.
3. **Type 2 architecture:** server local (npx se download + run), data cloud se — *"starts online, runs locally, calls the cloud"*.
4. **Type 3 (remote SSE) abhi rare hai** — sirf paid enterprise services (Asana, PayPal, Zapier...) offer karti hain; flaky bhi, kyunki uptime owner pe depend karta hai.
5. Common real-world config: **API key lo, local MCP server me daalo** — hosted MCP servers ka future ho sakta hai, present nahi.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

So there's been many times in the last few weeks that we have used tools that do internet searches. You probably remember the hosted tool with OpenAI that we used right back in week two, which was quite expensive. Was it two and a half cents for every single web search? And we've used, I think, Tavily and we've used Serper. Well, we're going to do another one. So sorry to make you set up another key, but this one's a really great one. It's called Brave Search, and it's a company that specializes in an API driven search, including for use with AI. And it's free again, at least I think you get 2000 free searches a month. So it's very generous. And I have set it up. I've actually got a paid account because I've been using it a lot, but you very much can stay on the free version. I've got a link here for where you go to set up your account. If I go up here, it brings up the Brave Search. You sign up, you go through and get an API key super easily without needing any credit card or anything like that.

So once you've done that, you come back, you take your Brave API key and you put it in your .env file as usual, and then you'll have to rerun load_dotenv up at the top. Okay. So then what we do is we collect our Brave API key. And this time you'll notice that when we specify the params for our MCP server, we're passing in these environment variables, these settings as well. So that's a new twist for this one so that we can tell Brave about our API key. And it's another node, another JavaScript MCP server. So we run it this way. And in fact this is one of Anthropic's out of the box reference implementations. So this is part of Anthropic's offerings, the Brave Search. And so again, even though we're running online searches, the MCP server is going to be running on my box. So the code for this is remote, is online. We are downloading that code and running it locally using npm. So it starts online, we bring it locally, we run it locally. And then of course, what that code actually does is it makes a call to a web service offered by the company Brave, and it passes in our key to that service. So that's why this is architecture two: MCP server running locally calling out to the cloud. And I'm probably belaboring this. You're probably like, yeah I get it, I get it, enough.

Okay. So MCPServerStdio again is how we do this. We pass in the parameters. Let's just see what tools we get with this. We get a brave web search tool which performs a web search with the API. And then a local search, searches for local businesses. I think I only get that because I'm paying the paid plan. I don't think that comes with the free plan, actually. So again, the key difference with something like fetch is that with fetch, we're running a browser locally and we're just going to a web address. With Brave, we're making a web call to Brave, to ask it to run like a Google search. But it's not using Google. It's using its own search engine and return the results of that query.

And so we're going to ask a question. You're able to search the web for information, research the latest news on the Amazon stock price, and give it the current date. And then we run the server right here. Okay. Here we go. Running that you'll see. As usual we're passing in the MCP server. We've got the timeout set and we're calling runner run, and back we get of course the results of running this web search with the current price of Amazon, apparently 217, and more information about it. And as always, we should go in and check out the trace. Let's have a look here and make sure that we're happy. Yep, it's calling a brave web search. The query was Amazon Stock Price News May 2025. And it got back these results. And so it seems to be working nicely end to end. That is another. That is an example of type two of the calling out to the web.

And so now to talk about the type three of the MCP servers, the ones where the server itself, the MCP server, is running remotely. And you must connect to it using the SSE approach. And now here's the thing. As I say, it's not that common. And it's also quite flaky because there's no guarantees that the people that you're connecting with are going to keep their server running. I used to have an example in here of an MCP server that I found, a hosted MCP server that you could connect to remotely, but it went down and now you can't connect to it. And that's why I had to take out that code at the top. So it's no longer running. So that example didn't work. And so I tried to look for some other examples. And the other examples that I found are all for paid business services where you are already paying for something, and it tends to be from sort of professional business plans.

So let me show you that, that the Anthropic docs have a section on remote MCP servers. That's what we're talking about here. And it says several companies have deployed remote servers that developers can connect to. And so here are some examples of them. And you'll see why I'm not able to demo one of these, because I'd have to be a paying client. So Asana, if you are a client of Asana, Asana like project management tool, then you could interact with Asana workspace by using this remote MCP server. And then similarly for these others like Intercom, like PayPal — if you use, not just PayPal for your personal PayPal, I have one of them, but I don't have commerce capabilities. I'm not a seller. And the others at Square and Zapier. I was going to try and set something up to show it, but you have to have a paid account. So it's honestly not common to be seeing this. It's only in these cases of, like, paid enterprise accounts where you don't want to run the MCP server yourself. You want to connect to it running on the cloud. And as I say, I really, I haven't seen much traction with this in the community. It's not like this is something that you come across often. And for many of those commercial examples, you can run an MCP server locally as well, which is what people typically do.

Cloudflare, which was actually on that list, has some tools for you to create and run your own remote servers. If you're a Cloudflare customer and you use Cloudflare for your own website, your own deployments, they have some really interesting sheets here which allow you to deploy a remote server that other people could connect to, and they actually make it really quite easy. They walk you through the code here and how you can check in their screens that it's running. And then they give you, of course, the way that you would then connect to it from, say, your desktop or indeed from your OpenAI Agents SDK. And this is then where you can add authentication, which is one of the hot new areas of MCP. If you are going to provide a hosted tool, then you would want to have a way that people can authenticate with it so that they can demonstrate that they are who they say they are.

But as I say one more time, then I'll shut up because you're fed up of me saying this. But it's not a common way of doing things. And indeed, if you're running something like the Brave Search that we just did, it would be more common for you to set up an API key with something like Brave and then pass in that API key when you call your local MCP server. That's the more common configuration. And of course, this might change any day — maybe managed hosted MCP servers will take off big time, and I'll be eating my words. But as of right now, it's not terribly common, but you certainly could follow the Cloudflare instructions and set up your own should you wish. So that wraps up the third type. And we're now going to go back to the second type for a really cool example.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
