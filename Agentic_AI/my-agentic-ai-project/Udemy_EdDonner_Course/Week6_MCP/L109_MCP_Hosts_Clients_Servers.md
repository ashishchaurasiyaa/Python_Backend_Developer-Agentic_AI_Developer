# L109 — Day 1: Understanding MCP Hosts, Clients, and Servers

> **Week 6 — MCP** · ⏱️ ~9m · 🎥 Lecture 109 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 50767593

---

## 🎯 Ek Line Mein (TL;DR)

MCP ke 3 core concepts hain — **Host** (overall app jaise Claude Desktop ya tumhara agent code), **Client** (host ke andar chalne wala chhota plugin, har server ke liye ek), aur **Server** (host ke *bahar* chalne wala code jo **tools, context, prompts** provide karta hai) — aur biggest misconception: MCP servers **mostly tumhare apne machine pe locally** chalte hain (transport: **stdio** common, **SSE** remote ke liye), remote/hosted servers rare hain.

---

## 📝 Hinglish Explanation (Detailed)

- **MCP ke 3 core concepts** hain jo Ed clearly samjhana chahta hai — Host, Client, Server. Terminology confusing hai, isliye dhyan se.

- **1. MCP Host** = **overall application** jisme tum agent ko tools se equip kar rahe ho. Examples:
  - **Claude Desktop** — wo software jo tumhare computer pe chalta hai, Claude LLM ko manage karta hai aur chat karne deta hai.
  - **Hamara apna agent architecture** — jaise **OpenAI Agents SDK** use karke likha hua code jo agents aur tools run karta hai. Wo poora application/software hi **host** hai.

- **2. MCP Client** = host ke **andar** chalne wala **chhota sa software piece** — isko ek **plugin** ki tarah socho. Important rule: **har MCP client ek MCP server se 1-to-1 connect karta hai**. Matlab agar Claude Desktop me tum 5 alag MCP servers use kar rahe ho, to host ke andar **5 alag MCP clients** chal rahe honge — har server ke liye ek.

- **3. MCP Server** = **actual code jo capabilities provide karta hai**, aur ye **host ke bahar** run karta hai. Server 3 cheezein de sakta hai:
  - **Tools** — sabse important, sabse zyada excitement isi pe hai (agent actions le sakta hai).
  - **Context/Resources** — information lookup ke liye extra context.
  - **Prompt templates** — ready-made prompts.

- **Concrete example — `fetch` MCP server:** ye server internet search karke web page fetch kar sakta hai. Andar ka mechanism cool hai — ye ek **headless browser** (headless Chrome — browser jo dikhta nahi) launch karta hai aur **Microsoft ke Playwright** se us browser ko drive karta hai, page collect karta hai, contents padhta hai aur return karta hai. Ye tool MCP server me wrapped hai. Claude Desktop ko configure karo → host ke andar ek MCP client banta hai → wo fetch server se connect hota hai → ab Claude live web pages padh sakta hai. Aur fun fact: **pichle week AutoGen me humne yahi fetch MCP server use kiya tha!**

- **Architecture diagram (mentally banao):** ek box = tumhara computer. Box ke andar ek **host** chal raha hai (Claude Desktop ya hamara OpenAI Agents SDK code). Usi box me 2 **MCP servers** bhi chal rahe hain (jaise ek **local file system** wala, ek **weather** wala). Host ke andar **2 MCP clients** — har server ke liye ek.

- **⚠️ BIGGEST MISCONCEPTION (Ed 100 baar repeat karta hai):** "Server" word sunke lagta hai koi **remote machine** hogi — **galat!** **MCP servers almost always tumhare apne computer pe run karte hain.** Tum unhe kisi **public repo se download/install** karte ho (jaise fetch server Anthropic ke repository se aaya tha), but wo **tumhare box pe, host ke bahar** chalte hain, aur client locally connect karta hai.

- **Remote MCP servers** (alternative architecture) — possible hai ki MCP server kisi **doosri remote machine** pe ho aur tumhara client usse connect kare. Inhe **"hosted"** ya **"managed" MCP servers** bolte hain — but ye **quite rare** hai. Marketplaces me **thousands of MCP servers** hain jo sab local-run hote hain; remotely-connectable wale dhundhna mushkil hai.

- **Teesra (sabse common) configuration — local server jo internet call karta hai:** MCP server tumhare box pe chal raha hai, but uska kaam internet pe hai. Jaise:
  - File-write wala server = **pure local processing**.
  - Fetch server = local run hota hai but **web browser chalakar internet access** karta hai.
  - Weather server = local run hota hai but **remote web services call** karta hai.
  - Ye "**local MCP server + remote service call**" pattern **by far the most common** configuration hai. Isko "client → remote MCP server" wale rare case se **confuse mat karo**.

- **Transport mechanisms — 2 tarike** (official Anthropic spec ke according):
  - **stdio (standard input/output)** — **by far the most common** aur simplest. MCP client ek **separate process spawn** karta hai tumhare computer pe, aur us process se **stdin/stdout ke through communicate** karta hai. Jab hum apna khud ka MCP server banayenge, yahi technique use karenge.
  - **SSE (Server-Sent Events)** — **HTTPS connection** use karta hai aur results **stream back** karta hai — bilkul waise jaise LLMs se tokens stream hote dikhte hain (wo bhi SSE technology hai).

- **Transport rules:**
  - **Remote/hosted MCP server** se connect karna hai → **SSE mandatory** (stdio remotely possible hi nahi).
  - **Local MCP server** (common case) → **stdio ya SSE dono** chalega, but **stdio most common** hai.

- **Recap jo clear hona chahiye:** Host vs Client vs Server ka difference, **3 arrangements** (local server with local processing / local server calling internet services / remote hosted server), aur **stdio vs SSE**. Ab lab time — **OpenAI Agents SDK me MCP servers use karenge**.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **MCP Host** | Overall application jisme agent + tools chalte hain — jaise Claude Desktop, ya tumhara OpenAI Agents SDK code |
| **MCP Client** | Host ke andar chalne wala chhota plugin; **har server ke liye ek client** (1-to-1 connection) |
| **MCP Server** | Host ke bahar chalne wala actual code jo **tools, context, prompts** provide karta hai |
| **Tools / Context / Prompts** | Server ki 3 offerings — tools (actions, sabse hot), context/resources (info lookup), prompt templates |
| **fetch MCP server** | Anthropic ka server jo **headless Chrome + Playwright** se live web pages fetch karta hai (AutoGen week me use kiya tha) |
| **Local MCP server** | Public repo se download karke **apne machine pe** chalaya gaya server — **default/common case** |
| **Hosted/Managed (remote) MCP server** | Doosri machine pe chal raha server jisse remotely connect karte ho — **rare** |
| **stdio transport** | Client ek **subprocess spawn** karta hai, stdin/stdout pe baat karta hai — simplest, most common |
| **SSE (Server-Sent Events)** | **HTTPS streaming** transport — remote servers ke liye **mandatory**, local ke liye optional |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **"Server" without a socket:** stdio transport me MCP "server" koi listening port nahi kholta — client usse **subprocess ki tarah spawn** karke **stdin/stdout pipes** pe JSON-RPC messages bhejti hai. Bilkul jaise `subprocess.Popen(stdin=PIPE, stdout=PIPE)` se koi CLI tool drive karna — isliye "server running on your box" wali baat ekdum natural lagegi. SSE wala mode hi traditional HTTP server jaisa hai (wahi streaming jo tum LLM token streams me dekhte ho).
- **Host/Client/Server ko process boundaries me socho:** Host = parent process (tumhari app), Client = us process ke andar ek connector object (DB connection-pool client jaisa, per-server ek), Server = child process ya remote endpoint. 1-to-1 client↔server mapping waise hi hai jaise har database ke liye alag connection client.
- **Hands-on lab:** is lecture ka code khud chalane ke liye **`Practical/lab1_mcp_intro.py`** run karo (is repo me, `uv run` se chalta hai, Groq pe free). Difference: lecture wale node/npx + Playwright-based fetch server ki jagah hamare labs **Python FastMCP servers** (`servers/` folder me) use karte hain — concept (host/client/server + stdio) bilkul same.
- **Supply-chain alert (agle lectures me aayega):** "public repo se download karke locally run karo" = wahi risk profile jo random `pip install` ya `npx` package chalane ka hota hai — server tumhare machine pe full process hai, file system tak access possible. Marketplace se server lene se pehle source dekhna backend dev ki aadat honi chahiye.

---

## 🧠 Takeaway (yaad rakho)

1. **3 concepts:** Host (overall app) → Client (host ke andar, per-server plugin) → Server (host ke bahar, tools/context/prompts deta hai).
2. **MCP servers mostly LOCAL chalte hain** — public repo se download karke apne box pe run karte ho; remote/hosted servers rare hain.
3. **Most common pattern:** local MCP server jo internet pe koi remote service call karta hai (fetch, weather) — isse "remote MCP server" se confuse mat karo.
4. **2 transports:** **stdio** (subprocess + stdin/stdout, simplest, most common) aur **SSE** (HTTPS streaming, remote ke liye mandatory).
5. Har client ↔ server connection **1-to-1** hai — 5 servers use karoge to host me 5 clients chalenge.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

So there are three core concepts behind MCP that I need to explain to you about. First of all is what's known as the MCP host. The MCP host is the overall application in which you're going to be equipping an agent with tools. And so the host could be something like Claude Desktop, the piece of software that runs on your computer that manages Claude, the LLM, and lets you chat with Claude. It could be our agent architecture, a piece of software that we've written using perhaps the OpenAI Agents SDK that's going to run agents and tools. So that overall application, the piece of software running this agent framework, that is known as the host, the MCP host.

An MCP client is a small piece of software. Think of it like a plugin that runs inside that host, within the host. And each MCP client is going to connect 1 to 1 with something I'm about to explain called an MCP server. So if you're running Claude Desktop, for example, and you're using a bunch of different MCP servers, then you're going to have a little client, an MCP client running for each of those. So MCP client lives in the host. It connects to the server. The server runs outside the host.

So what is this server? The server is the actual piece of code that provides tools and context and prompts, these extra capabilities, to your agent. And as I say, tools is the one to really focus on. That's the one that's got the most excitement. But it can also, in addition to equipping an agent with tools, it can also provide extra context for looking up information, and it can provide prompt templates as well. That is something that would happen by the MCP server running outside the host.

Now let me make that concrete by telling you about a particular MCP server called fetch. So fetch then, it's an MCP server that is able to search the internet and fetch a web page. The way it actually does it is kind of cool. It runs a browser. It launches a browser, a headless browser, like a headless Chrome, as they call it, so that you don't actually see the browser, and it uses Playwright from Microsoft to drive that browser, to collect the page and to read its contents and return it. So that is a tool, and it's wrapped in an MCP server, and you can run that MCP server, and then you can configure Claude Desktop, the Claude Desktop application, so that within it it runs an MCP client that connects to that MCP server. So that Claude, if you're chatting with Claude, it's suddenly able to read web pages live. And that's what's happening behind the scenes. And in this case that I'm describing, that MCP server is also running on your computer. You're talking to Claude Desktop. It's able behind the scenes to connect to that MCP server, to run a headless browser, to collect a web page, and then to answer questions based on it. And in fact, we did that. We used the fetch MCP server already in Autogen last week. Hopefully you didn't skip last week because it was fun. And we used this very MCP server via Autogen and that's what it was doing.

And perhaps it will help clarify this to show you a diagram, an architecture diagram of how this fits together. Imagine this box is representing your computer, your machine. And within your machine you have a host running. So that host, it could be the Claude Desktop app. It could be software that we have written as part of this course that's using the OpenAI Agents SDK. And we have a couple of MCP servers running on your box. Maybe one of them is something that can connect to the local file system. Maybe one of them is something that can ask for the weather. And within that host you would have a couple of MCP clients, one MCP client for each of the MCP servers running on your computer.

You can also have a remote server. This is an alternative architecture. This is the second way of doing it. And you can have an MCP server running on that remote server, and you can connect to that remote server using an MCP client. But it's important to mention that this is in fact quite rare. This is not the way it's normally done. You hear the word like MCP server and you think, okay, that sounds like something that's like a remote server. And so you imagine it's like the diagram I've just shown you, but it's actually very rare to do it that way. Almost always in most of the examples that we'll look at, the MCP servers are things that run on your computer. They're running outside the host and you're connecting to it, but it's still running on your machine. Now you will have retrieved that from somewhere public. So it's been shared by somebody else, but it's been retrieved and installed on your computer. So like when we use the fetch MCP server, it was running on our machine. We were collecting it from actually Anthropic's repository. But we were then running the fetch MCP server on our machine outside the host, and we had a host which was Autogen. In this case, we'd written some code that acted as the client, and it was connecting to that server running on our computer. So using remote MCP servers is possible. It's a thing, but it's not common. And sometimes these are called hosted MCP servers. Sometimes they're called managed MCP servers, but they're not that common. And so that's a super important misconception and confusion that I really wanted to clarify: the fact that in most cases, MCP servers are things that you install from some remote repo, but it's running on your box.

Okay, but it's worth pointing out that there is another configuration here and that looks like this. The MCP server that you're running on your box, it might be doing something that just involves local processing on your computer, like it might be writing a file to your file system. But also there are many MCP servers that take advantage of functionality over the internet. The fetch MCP server that we just mentioned, of course, that actually runs a web browser and looks over the internet. You can also get MCP servers that check the weather. And of course they're doing that by calling some web servers. So it's very common to have an MCP server that is connecting online and calling some remote service. In fact, that is by far the most common of the configurations. But it's important in your mind to distinguish between that, what I've just shown you, and a case where your MCP client is calling a remote MCP server hosted on another machine, which is, as I say, less common.

So one more time, if I haven't stressed this enough: MCP servers mostly run on your box. You typically download them and you run them locally. And if you're wondering why I'm telling you this 100 times, it's because it really is — people do get very confused about this because the terminology is muddling, but that's the way it works. In fact, as I'll show you when we start looking at MCP marketplaces, there are thousands of MCP servers and they all run in a box, and there's not so many — it's quite hard to discover ones that are ones that you could connect to remotely.

Now there are two different technical mechanisms for how MCP servers can work, two different transport mechanisms, as they're called in the official Anthropic spec so far. The first of them, which is by far the most common, is called stdio, spelt like that, which stands for standard input output. And this is the simplest approach. And if you're using this approach, then basically your MCP client spawns a process, a separate process on your computer, and it communicates with that process over just standard input and output. And that's why it's called stdio. And this is the most common way of doing it. And we'll be exploring this a lot. And when we build our own MCP server, we'll be using this technique.

The other technique is called SSE, and SSE, which stands for Server Sent Events, uses an HTTPS connection and it streams back results much the way that you see stuff streaming back from LLMs — when you see the information flowing back, that also uses SSE technology. And if you're going to use one of these remote MCP servers, a hosted or managed MCP server, as in the picture on the top right there, then you need to use SSE. You can't use stdio for connecting remotely like that. It has to be SSE. If you're using local MCP servers, the common case, then it can be either stdio or SSE either way, and it's most common to be stdio.

Okay, so take a good look at this. Make sure that it's getting clear in your mind. You know the difference in a host and MCP client and server. The three different arrangements, SSE versus stdio. And now with that, it's time for our lab. Let's go and make use of MCP servers in the fabulous OpenAI Agents SDK.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
