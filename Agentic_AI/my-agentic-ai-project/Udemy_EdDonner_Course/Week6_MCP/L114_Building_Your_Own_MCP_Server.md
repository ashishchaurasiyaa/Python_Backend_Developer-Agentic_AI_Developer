# L114 — Day 2: Building Your Own MCP Server

> **Week 6 — MCP** · ⏱️ ~5m · 🎥 Lecture 114 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 50767625

---

## 🎯 Ek Line Mein (TL;DR)

Aaj hum apna khud ka **MCP client aur MCP server** banayenge — lekin Ed ka sabse bada lesson ye hai: **MCP server tab banao jab tool ko share karna ho**; agar tool sirf khud ke liye hai, to simple **function tool decorator** hi kaafi hai, MCP ka extra plumbing waste of time hai.

---

## 📝 Hinglish Explanation (Detailed)

- Week 6 ka **Day 2** shuru — aaj hum apna **MCP client** aur apna **MCP server** dono banayenge. Ed ka favourite analogy phir se: hum **"USB-A of agentic AI" nahi, "USB-C of Agentic AI"** bana rahe hain (yaani modern, universal standard wala connector).

- **Core concepts ka recap** (ab tak ye yaad ho jana chahiye):
  - **Host** = overall application, jaise **Claude Desktop** ya hamara apna **agent architecture**.
  - **Client** = host ke andar rehta hai, aur **one-on-one connection** rakhta hai (jaise input/output ke upar) ek MCP server ke saath.
  - **Server** = ek **separate process** jo host ke bahar chalta hai aur client ko **tools, contexts (resources), aur prompts** provide karta hai.
  - Zyada tar time hum **tools** ki baat karte hain, lekin journey me briefly **contexts (resources)** bhi use karenge. **Fetch** server ka example pehle dekh chuke hain.

- **Architecture ke 3 patterns** (diagram recap):
  1. **Fully local**: MCP client → MCP server jo **tumhare computer pe** chal raha hai, sab kuch locally hota hai — jaise **file writer** server jab humne **Banoffee Pie** recipe likhi thi.
  2. **Local server + remote service**: MCP server tumhare box pe chalta hai, lekin wo **kisi remote internet service ko call** karta hai — **Playwright** aur **Fetch** dono iske examples hain.
  3. **Hosted / Managed MCP server** (less common): MCP client **remotely** connect karta hai ek MCP server se jo **doosri machine pe** chal raha hai — iske liye **SSE transport** zaroori hai. Local wale servers **stdio ya SSE** dono use kar sakte hain, lekin **usually stdio** hote hain.

- **Servers kis language me likhe jaate hain?**
  - **Python** servers → launch command typically **`uvx`**.
  - **JavaScript** servers → launch command typically **`npx`**.
  - **Docker container** ke through bhi chala sakte ho, aur kuch aur tarike bhi hain — lekin **uvx aur npx by far sabse common** hain.

- **Why build an MCP server? (advantages)**:
  1. **#1 reason: SHARING.** Tumne kuch banaya hai jo doosre log apne agents ke saath use kar saken — tum tool ko describe karte ho, prompts/information set karte ho, aur log ise apne agents me integrate kar lete hain.
  2. Agar tumhare paas **resources** hain (jo thode **RAG context** jaise hote hain) aur **prompt templates** bhi (though wo kam use hote hain) — wo bhi share ho jaate hain.
  3. **Consistency** (thoda tenuous reason): agar hum agent system me bahut saare MCP servers use kar rahe hain, to apne khud ke tools bhi **MCP servers ke roop me consistently package** karna nice lagta hai — isi liye course me hum aise karenge.
  4. **Learning the plumbing**: nuts and bolts khud build karke samajhna useful hai.

- **Why NOT build an MCP server? (the BIG one)**:
  - Agar tool **sirf khud ke use ke liye** hai, to MCP server banana **time waste** hai.
  - Simple raasta: function ko **`@function_tool` decorator** se decorate karo (OpenAI Agents SDK), ya **week 1 wala JSON approach** use karo — function **tumhare current Python process me directly** call hoga.
  - MCP server ka matlab: ek **alag process spawn** hota hai, **stdio pe communicate** karta hai — ye sab **extra plumbing aur scaffolding** hai jo apne khud ke tool ke liye bilkul needed nahi.
  - **Clarity yaad rakho**: *MCP doesn't help with building your own tools — that's already easy. MCP is about SHARING tools.* Yahi asli benefit hai.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Host** | Overall application (jaise Claude Desktop ya hamara agent architecture) jisme MCP clients rehte hain |
| **MCP Client** | Host ke andar ka component, ek MCP server se 1:1 connection rakhta hai |
| **MCP Server** | Separate process jo tools, resources (contexts), aur prompts provide karta hai |
| **stdio transport** | Local servers ka default — standard input/output pipes pe communication |
| **SSE transport** | Server-Sent Events — remote/hosted MCP servers ke liye zaroori; local pe bhi chal sakta hai |
| **Hosted / Managed MCP server** | Doosri machine pe chal raha MCP server jise client remotely (SSE se) access karta hai |
| **uvx / npx** | Python (uvx) ya JavaScript (npx) MCP servers ko launch karne ke standard commands |
| **Resources** | MCP server ka data/context offering — RAG context jaisa feel |
| **Prompt templates** | MCP server ke pre-built prompts — kam use hote hain |
| **`@function_tool`** | OpenAI Agents SDK decorator — apne khud ke tool ke liye MCP se simpler, in-process raasta |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **"Library vs microservice" wala classic decision** hi hai ye: apna function in-process call karna (`@function_tool`) = library import; MCP server banana = us function ko separate process/service me nikaalna with IPC overhead. Jaise tum kisi internal helper ke liye REST microservice nahi banate, waise hi sirf apne use ke tool ke liye MCP server mat banao — **MCP = published API for external consumers (sharing)**.
- **uvx/npx ko `docker run` jaisa socho** — ek hi command me package fetch + ephemeral execution. Aur 3 deployment patterns map karte hain familiar cheezon pe: local stdio server ≈ sidecar/subprocess with pipes, local server calling internet ≈ API gateway/adapter, hosted SSE server ≈ proper remote service over HTTP.
- **Resources ≈ REST resources / read-only GET endpoints** (RAG-context jaisa data exposure), jabki tools ≈ POST/RPC actions — ye mental model aage ke lectures me kaam aayega.
- **Hands-on lab**: is lecture ka code khud chalane ke liye `Practical/lab2_custom_accounts_server.py` run karo (is repo me, `uv run` se chalta hai, Groq pe free). Hamare labs course se thode alag hain: node/npx servers ki jagah **Python FastMCP servers** (`servers/` folder me), aur lecture me jo Playwright/Fetch jaise examples aate hain unki jagah free substitutes (Wikipedia-style memory server + simulated market server), Playwright skip.

---

## 🧠 Takeaway (yaad rakho)

1. **Host → Client → Server**: client host ke andar, server alag process — tools/resources/prompts deta hai, 1:1 connection.
2. **3 architecture patterns**: fully local (stdio), local server + remote API call, aur hosted/managed remote server (**SSE mandatory**); local usually **stdio**.
3. **uvx (Python) aur npx (JavaScript)** sabse common launch commands hain; Docker bhi possible.
4. **MCP server banao SIRF sharing ke liye** — apne khud ke tool ke liye `@function_tool` / JSON approach kaafi hai, MCP ka separate-process plumbing overkill hai.
5. Course me hum apne tools bhi MCP servers banayenge — **consistency + plumbing samajhne** ke liye, not because it's required.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

And welcome to day two of week six as we get more into MCP. And this is the time that we build our own MCP client and MCP server. Remember today we're making our own. We're not making a USB-A of agentic AI. We're making USB-C of agentic AI.

And another reminder of these core concepts that probably now you're getting this. The host is the overall application like Claude Desktop or our agent architecture. The client lives inside the host and has a one on one connection, like over input output to an MCP server, which is a separate process running outside and providing the tools, the contexts, and the prompts to your MCP clients, to your host. And most of the time we're talking about tools, although briefly we'll use contexts as well in our journey. And there's the example of fetch that we'd used before.

And a reminder of the architecture again. On the bottom left is the idea that you could have an MCP client that connects to an MCP server running on your computer, and it does everything locally, like the file writer that we had in when we wrote Banoffee Pie. The second one along is an MCP client that connects to an MCP server running on your box that then calls out to some sort of remote internet service. And I guess the Playwright and fetch are both examples of that. And then less common, that third one, sometimes known as a hosted MCP server or a managed MCP server, is when you have an MCP client that connects remotely to the MCP server running on another machine. And that would need to be using the SSE transport mechanism, whereas ones running locally could be either stdio or SSE, and they're usually stdio.

And maybe it's also worth mentioning on this diagram that these MCP servers can be written in Python or JavaScript, in which case they're typically the parameters that describe them. Have uvx as the command to run or npx. They can actually also just be creating a Docker container. There's various other ways, but uvx and npx are by far the most common.

So with that we're going to go and create our own MCP server. But just before we do, I want to quickly take a moment to ask, why do we want to make an MCP server? What's the advantage of doing it? Well, the number one advantage is you make an MCP server if you want to share it. You've built something which you want other people to be able to use with their agents, because you're going to be describing it in a way. You're going to be working on the prompts and the information around your tool, and people will be able to integrate it with their agents. So simply, that's the number one reason. And also if it has resources which a bit like a RAG context and then prompt templates too, although that's not not used so often.

Also, I suppose there is a small benefit if we're building an agent system and we're using a bunch of MCP servers, it might be nice for us to treat our own tools consistently so that everything is packaged as MCP servers. This is a bit tenuous, but it's one reason we're going to do it this way, because we only want to use MCP servers, and it's also useful if you're doing it just so you can understand the plumbing, just so you can really build the nuts and bolts and do it yourself.

Now, you probably realize the reason I'm belaboring this point is because I want to say, why don't you want to make an MCP server. What are the reasons against. And there's one really important one. And it's this: if you're only building a tool for you to use yourself, if we're writing a function and we want to equip our LLM with that function, then there's no point in building an MCP server — that's wasting time. You can simply decorate that tool with function tool and then equip your LLM just by just by putting it in tools, you can just immediately provide it through the OpenAI Agents SDK or using the JSON approach from week one. And then that function will be called in in your current Python process, it will just be called as a tool. And that's easy.

Building an MCP server, which means that it gets spawned and runs as a separate process and communicates over standard input output, and is provided as an MCP server — that's a whole lot of extra plumbing and and scaffolding that's not needed if it's just to call your own tool. So it's important to have that that clarity that MCP doesn't help with building your own tools. That's already easy and you should just do it. MCP is about sharing tools. That's the benefit.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
