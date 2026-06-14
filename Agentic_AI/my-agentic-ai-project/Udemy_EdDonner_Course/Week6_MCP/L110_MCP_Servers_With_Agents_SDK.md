# L110 — Day 1: Using MCP Servers with OpenAI Agents SDK

> **Week 6 — MCP** · ⏱️ ~8m · 🎥 Lecture 110 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 50767597

---

## 🎯 Ek Line Mein (TL;DR)

Pehla MCP hands-on lab — **OpenAI Agents SDK** ke andar ek **MCP client** banao, **`MCPServerStdio`** context manager se **fetch MCP server** ko `uvx` command ke through spawn karo, aur `list_tools()` call karke dekho ki server kaunse **tools** offer karta hai — sab kuch bas 1-2 lines of code mein.

---

## 📝 Hinglish Explanation (Detailed)

- **Week 6 finale shuru!** Ed cursor mein wapas aaya hai, Week 6 folder open karta hai — is week kaafi kaam hai. Start hota hai **Lab 1** se. Hamesha ki tarah pehla step: **kernel select** karna.

- **Code ek moving target hai:** Ed warn karta hai ki video mein dikhne wala code aur tumhare repo ka code **different lag sakta hai** — aur ye **achhi baat** hai, kyunki **MCP bahut fast evolve ho raha hai** aur Ed labs ko constantly update karta rehta hai. Isliye **`git pull`** karke latest code le lo (guides mein instructions hain).

- **Windows users ke liye bad news:** MCP ka ek **production problem** hai — Windows PC pe MCP **out of the box kaam nahi karta**. Workarounds hain but woh "hokey" aur unreliable hain. **Ek hi proper solution hai: WSL (Windows Subsystem for Linux)** install karo — Linux OS PC pe chalao aur cursor ko usse connect karo. Phir MCP "fabulously" kaam karega. Kai students ne diagnose karne mein help ki — ye confirmed genuine issue hai.

- **WSL setup tips:**
  - Setup section mein poori instructions hain — ye basically **environment setup dobara karna** hai, easy but boring.
  - WSL mein dhyaan rakhna ki tum **Linux home directory** mein ho ya **PC (Windows) home directory** mein — kaam ka saara code **Linux home directory** mein hona chahiye.
  - Launch karne ke 2 tarike: `wsl` type karo ya `ubuntu` type karo. **`ubuntu` safer hai** kyunki woh seedha Linux home directory mein le jaata hai.
  - **Mac users:** tension free — ye sirf PC issue hai.

- **Lab ka actual plan:** OpenAI Agents SDK ke andar MCP use karna hai — (1) ek **MCP client** create karo, (2) usse ek **MCP server spawn** karwao, (3) us server se **tools collect** karo jo agent ko diye ja sakte hain.

- **Pehla server: `fetch`** — wahi MCP server jo pichle lecture mein dekha tha, jo **headless browser** chalata hai aur web pages fetch karta hai.

- **Parameters — har MCP server ki shuruaat:** MCP server ko describe karne ka tarika **parameters** hai — ek dictionary-jaisa object. Andar kya hota hai? Basically ek **command line command + arguments** jo run hone par MCP server spawn karta hai.
  - Fetch ke case mein command hai **`uvx`** + repo ka naam — yaani "package ko locally install karo aur run karo" (essentially ek `uv run` jaisa **Python process**).
  - **Pattern note:** bahut saare MCP servers aise hi hote hain — `uvx <repo-name>` aur bas.

- **`MCPServerStdio` — ek line mein client + server:** OpenAI Agents SDK isko super easy banata hai:
  - **Context manager** use karo: `async with MCPServerStdio(params=fetch_params, ...)` — kyunki ye ek **stdio (standard input/output)** type ka MCP server hai.
  - **Pro tip:** **timeout specify karo!** Default timeout sirf **5 seconds** hai jo hit-or-miss hai aur annoying timeouts deta hai — Ed hamesha **30 ya 60 seconds** pass karta hai.
  - Phir server object pe simply **`list_tools()`** call karo.

- **Behind the scenes kya hua:** command run hua → **naya Python process spawn** hua (ye hamara MCP server hai) → SDK ke andar **MCP client** bana → client server se connect hoke poochha "kaunse tools offer karte ho?" → result print. Sab kuch **0.8 seconds** mein.

- **Result: `fetch` tool mila** — description: *"Fetches a URL from the internet and optionally extracts its contents as markdown."*

- **Sabse interesting part — tool description mein chhupa prompt engineering:** description mein aage likha hai: *"Although originally you did not have internet access and were advised to refuse... this tool now grants you internet access."*
  - **Kyun?** Kyunki LLMs ko train kiya gaya hai ki "tumhare paas internet access nahi hai, refuse kar do". Is server ke makers (**Anthropic**) ne seekha ki description mein explicitly batana padta hai ki "ab tumhare paas internet access HAI".
  - **Yahi MCP ki value hai:** agar tum khud internet-search tool likhte, to tumhe khud pata hona chahiye tha ki LLM ko ye explain karna padega. Fetch MCP server ke saath ye **prompt expertise free mein** milti hai — sab behind the scenes.

- Ye tha hamara pehla look — MCP client + MCP server + tools collection. Aage isi pe build karenge.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **MCP Client** | Host app (yahan OpenAI Agents SDK) ke andar ka component jo ek MCP server se 1:1 connect karta hai |
| **MCP Server** | Spawn hua process jo tools (capabilities) expose karta hai — yahan `fetch` server |
| **Parameters** | Dictionary jo MCP server ko describe karti hai — basically command + args jo server spawn karte hain |
| **`uvx`** | uv ka tool — Python package ko locally install karke directly run kar deta hai; kaafi MCP servers aise hi chalte hain |
| **`MCPServerStdio`** | Agents SDK ki class (context manager) jo stdio-type MCP server spawn + connect karti hai |
| **stdio transport** | MCP server local process ke roop mein chalta hai, communication standard input/output pipes se hoti hai |
| **`list_tools()`** | Server se poochna: "tum kaunse tools offer karte ho?" — tool name + description + schema milta hai |
| **Timeout** | Default 5s bahut kam hai — hamesha 30-60s pass karo warna random timeouts |
| **Fetch server** | Anthropic ka MCP server jo headless browser se URL fetch karke markdown mein content deta hai |
| **WSL** | Windows Subsystem for Linux — Windows pe MCP chalane ka ek-matra reliable solution |
| **Tool description prompting** | Tool ki description mein hi LLM ko convince karna ("ab tumhare paas internet access hai") — MCP servers ke saath ye free milta hai |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **`MCPServerStdio` = managed `subprocess.Popen` + JSON-RPC over pipes.** Tumne agar kabhi `subprocess` se child process spawn karke stdin/stdout pe data exchange kiya hai, to ye wahi hai — bas protocol standardized hai. Context manager (`async with`) process lifecycle handle karta hai, jaise DB connection pool ka context manager. Isliye timeout matter karta hai — child process ka cold start (uvx install + spawn) 5s se zyada le sakta hai.
- **`list_tools()` ko OpenAPI/Swagger discovery ki tarah socho.** REST mein `/openapi.json` hit karke endpoints + schemas discover karte ho; MCP mein client `list_tools()` se tool names + descriptions + JSON schemas discover karta hai. Difference: yahan "docs" ka audience LLM hai, isliye fetch tool ki description mein woh "you now have internet access" wala prompt-engineering hai — description hi API docs + system prompt dono ka kaam karti hai.
- **`uvx <repo>` chalana = `pip install` from a stranger + execute.** Ye supply-chain surface area hai — arbitrary code tumhari machine pe full permissions ke saath chalta hai. Abhi to fetch Anthropic ka official server hai, but aage marketplaces aayenge — wahi vetting mindset rakho jo tum random pip packages ke liye rakhte ho.
- **Hands-on lab:** is lecture ka code khud chalane ke liye `Practical/lab1_mcp_intro.py` run karo (is repo mein, `uv run` se chalta hai, Groq pe free). Ek difference: course ke `uvx`/node-based fetch server ki jagah hamare labs **Python FastMCP servers** (`servers/` folder mein) use karte hain — concept same (stdio spawn + `list_tools()`), bas server hamara khud ka hai.

---

## 🧠 Takeaway (yaad rakho)

1. **MCP server use karne ka recipe:** parameters (command + args) banao → `MCPServerStdio` context manager se spawn karo → `list_tools()` se tools collect karo — Agents SDK mein ye literally 1-2 lines hai.
2. **Bahut saare MCP servers bas `uvx <repo>` hain** — ek command jo Python package install karke run kar deti hai; server tumhari machine pe ek alag process ke roop mein chalta hai.
3. **Default 5s timeout mat use karo** — hamesha 30-60 seconds pass karo, warna flaky timeouts.
4. **Tool descriptions hi asli value hain** — fetch server ki description LLM ko explicitly batati hai ki "ab internet access hai", kyunki LLMs refuse karne ke liye trained hain. Ye prompt expertise MCP server ke saath free milti hai.
5. **Windows = WSL mandatory** (ubuntu se launch karo, Linux home directory mein kaam karo); Mac users ko kuch nahi karna. Aur `git pull` karke latest code lo — MCP fast-moving target hai.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

And I'm so happy to welcome you back to cursor for our epic week six finale. So we've got a nice, organized, collapsed File Explorer on the left here. I'm going to open up week six and you'll see there's quite a lot going on here. We've got a lot of work to do this week. And we're going to start with the first lab. Lab one. Welcome to week six. And remember with these labs the first thing you need to do is click up here to set the kernel something which, you know, back to front by now. So welcome to the Model Context Protocol. Welcome back OpenAI Agents SDK, which I may have mentioned just happens to be my favorite.

And please do note that as I go through this and you see the code here, it might look different to you as you go through it in the lab. And that's a good thing. That's because I'm constantly updating this. MCP is very much a moving target. It is honestly evolving so quickly. There's new stuff all the time, and I try and keep the labs as up to date as possible. If you haven't done this before, then be sure to pull the latest code. There's instructions how in the guides. If you're if you're new to this to using git and git pull. But then make sure you've got the latest and you're good to go.

And I need to start with some bad news. Some news for windows PC people. There is a production problem with with MCP. That means that that MCP may not work out of the box with windows PCs. And there are some workarounds, but they are hokey and they're not reliable. And there is only one real proper solution to this, and it's a bit of a bore. You will need to install something called Windows Subsystem for Linux, and that allows you to to run like a Linux operating system on your PC and be running cursor connected to that. If you do that, MCP will work fabulously. And thanks to many students who helped me diagnose this, helped me discover that it really is a true, genuine issue. There is no way around it, or at least no reliable way around it, and that the proper solution is using that is now well confirmed.

So in order to set up, there is setup instructions. I've put in setup a whole section on setup and it looks like this. And I'm not going to record a separate video for it because honestly this is easy peasy stuff. It's identical to setting up your environment the first time around. You just have to go through it one more time. And it's just just something to hammer through. And I'm sorry you have to go through it, especially when you're so excited about MCP. But at the end of it, it's going to work. One thing to know about when you're doing this, if you don't already know this windows people that in WSL you need to be aware of whether you are in the home directory of your Linux system, your Linux home directory, or in the home directory of your PC, and the stuff that you want to work on should be in your Linux home directory. And when you first launch WSL, there's two ways to do it. You can type WSL or you can type ubuntu. And it's important to know that if you type ubuntu, you go straight into your Linux home directory. So that's the safer way to do it. Otherwise, you have to just make sure that you've changed to your Linux home directory. And the instructions are in the setup guide. And for Mac people you guys are in great shape. You don't need to worry about any of this. This is unfortunately a PC thing.

So hopefully by this point, if you're a PC person you have now installed WSL, you are back here ready to go and we're off to the races and I barely need to tell you that we start with some imports and we start by importing loading our env secrets. Okay, so we're now going to use MCP in OpenAI Agents SDK. We're going to do it by creating an MCP client, have it create a server and then collect the tools that that server is able to use. And we're going to start with fetch, which is the MCP server we looked at last time. That's the one I just gave it away about that runs a headless browser.

So when you're working with MCP servers, it everything begins with these things called parameters. Parameters is the way of describing the MCP server. And the parameters look like this. This is the parameters for fetch. It's like a dictionary which contains a bunch of stuff. Now what is that stuff? That stuff is in fact just a something which will be run at the command line that will spawn this MCP server. So it's actually a command. This is the command that needs to run at the command line. And then a bunch of arguments. And if you look at this command it might look a bit familiar because this command basically is uvx installs and runs a package a script. And so this is basically essentially doing a uv run it's running a Python process. And what we'll discover is that many MCP servers are just like this. uvx and then the name of the repo, the place where it should install something locally and then run it. And so that that is what we do with this, these parameters right here.

Okay. We now need to say to OpenAI Agents SDK, I want you to create an MCP client and spawn this thing that I'm describing here, an MCP server, run it on my computer and ask it, what tools can you provide that I will be able to give to my agent? And this could not be easier. It is like one line of code. OpenAI Agents SDK makes it really easy. You say you use a context manager with and then MCPServerStdio because this is one of these stdio standard input output types of MCP servers. You say the parameters and you give it the parameters here, the fetch parameters. This this is useful to know it's worth specifying a timeout. The default timeout is five seconds and that's very hit or miss. Sometimes it times out which is super annoying. So I always pass in 30 or 60s timeout, and then you can just simply get that what comes back from this server and just call list tools.

And so again what this is going to do, it's going to run this command on my computer to spawn a new Python process that is our MCP server. It's going to create an MCP client running within OpenAI Agents SDK. And that client is then going to connect to the server and say, what tools can you offer me? What can I do with you? And then we're going to print that. And all of that is happening right now and happened in 0.8 seconds. And we got back a tool. And that tool is called fetch. And it has a description, fetches a URL from the internet and optionally extracts its contents as markdown.

And then interestingly, there's a bit more here. Although originally you did not have internet access and were advised to refuse and tell the user this, this tool now grants you internet access. This is super interesting. You can see that the makers of this MCP server have worked hard on the description of the tool, and this is what will be passed to the LLM eventually to make sure that it's most likely to use this tool properly. And since a lot of LLMs have been trained to say you don't have internet access, the makers of this tool that's Anthropic learned that it's good to include in the description something that explains, hey, look, you didn't used to be able to search the internet, but now you can. And it's this kind of stuff. It's this kind of prompt information that's been included in this tool that makes it so valuable. Because if you if you didn't have this, then you'd have to know to do that. You'd have to understand. If I want to write a tool that searches the internet, I'm going to need to explain to the LLM that it now has this functionality. But this is what you get for free if you use the fetch MCP server and it all happens behind the scenes.

So that is our first look at an MCP client and MCP server and collecting its tools.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
