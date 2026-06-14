# L111 — Day 1: Node-Based MCP Servers & Tool Access

> **Week 6 — MCP** · ⏱️ ~5m · 🎥 Lecture 111 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 50767605

---

## 🎯 Ek Line Mein (TL;DR)

Python (**uvx**) ke baad ab **JavaScript/Node based MCP servers** — **npx** se chalte hain. Do examples: **Playwright MCP server** (browser pe fine-grained control, ~ton of tools) aur **filesystem MCP server** (ek **sandbox directory** ke andar read/write) — same `MCPServerStdio` code construct, sirf command badal jaati hai.

---

## 📝 Hinglish Explanation (Detailed)

- Pichle lecture me humne **Python-based MCP server** dekha tha — jo **uvx** se chalta hai, yaani PyPI pe published package (jo aap pip install kar sakte ho) ko directly execute karna. Ab hum **JavaScript-based MCP server** use karenge.

- **JavaScript MCP servers = npx se run hote hain.** Python wale uvx se chalte hain, JS wale server-side JavaScript yaani **Node** se. Ed assume karta hai ki zyada tar log Node se familiar hain; agar installed nahi hai to lecture me ek link diya hai (ChatGPT instructions) — install karna super simple hai.

- **Recent Node version chahiye.** Agar aap pehle se Node user ho lekin purana version hai, to **NVM** (Node Version Manager) use karke recent version pe aa jao. Verify karo: `npx --version` chalake check karo ki good recent version mil raha hai.

- **Pehla Node-based server: Playwright MCP server.** Parameters me ab command **uvx nahi, npx** hai — package **npm** (node package manager) se aata hai, pip se nahi. Ye **Microsoft Playwright** (browser automation software) ka official aur particularly popular MCP server hai.

- **"Par fetch bhi to Playwright use karta tha?"** — Haan, pichla **fetch MCP server** bhi behind the scenes Playwright use karta hai. Lekin difference abhi clear hoga.

- **Code construct bilkul same:** `MCPServerStdio` ko **context manager** ke roop me use karo, parameters pass karo (**timeout dena important hai**), phir `server.list_tools()` call karo. Run karne pe npx package install karta hai aur tools list karta hai.

- **"Wowza" moment — fetch vs Playwright MCP:** Fetch ne sirf **1 tool** diya tha (ek web page fetch karna). Playwright MCP server **bohot saare granular tools** deta hai:
  - Browser **close / resize** karna
  - **Console messages** dekhna
  - **File upload**, **key press**
  - **Navigate back/forward**
  - **Screenshot** lena (super interesting!)
  - **Drag, click, hover, select**

- Matlab agent ko **browser window pe fine-grained control** mil jaata hai — bilkul waise hi jaise **Week 4 ke Sidekick** ne browser power kiya tha, lekin ab MCP ke through. Fetch simple tha (ek page collect karo); Playwright full browser-driving agent banane deta hai.

- **MCP ki asli khoobsurati: plug-and-play.** Agent ko ek **whole slew of servers** se equip karna bohot easy hai — jo interesting lage, bas add kar do. Isliye Ed ek aur server add karta hai.

- **Doosra Node-based server: filesystem MCP server.** Pehle ek **`sandbox` directory** ka path nikala jaata hai (current directory ke andar; agar exist nahi karti to khud banao). Phir parameters: command phir se **npx**, package hai **Anthropic ka reference MCP server `server-filesystem`** (npm pe official).

- **Tools list karne pe:** ye server local file system pe **read/write** karne deta hai — read a file, read multiple files, create directory, list directory, waghaira. **Lekin hamesha sirf specified sandbox path ke andar.**

- **Security angle:** agent ko file system tools milte hain, par wo ek **certain directory me isolated** rehta hai — agent puri machine pe likh nahi sakta, sirf sandbox me.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **npx** | Node ka package runner — npm package ko bina permanent install ke directly execute karta hai (JS world ka uvx) |
| **uvx** | Python ka equivalent — PyPI package ko directly run karna (pichle lecture wala fetch server isse chala tha) |
| **Node / npm** | Server-side JavaScript runtime aur uska package manager — JS-based MCP servers iske upar chalte hain |
| **NVM** | Node Version Manager — Node ke versions switch karne ke liye; recent version zaroori hai |
| **Playwright MCP server** | Microsoft Playwright ka official MCP server — browser pe fine-grained control ke dher saare tools (click, screenshot, navigate, console, upload...) |
| **fetch vs Playwright** | fetch = 1 simple tool (page fetch); Playwright = granular browser control ka pura toolkit |
| **`server-filesystem`** | Anthropic ka reference MCP server (npm) — sandbox directory ke andar file read/write/list/create tools |
| **Sandbox directory** | Wo isolated folder jiske bahar filesystem server agent ko jaane nahi deta — safety boundary |
| **MCPServerStdio** | OpenAI Agents SDK ka context manager jo stdio transport pe MCP server spawn + connect karta hai (timeout dena mat bhulo) |
| **`list_tools()`** | Server se poochna ki wo kaunse tools expose karta hai — discovery step |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **uvx vs npx = same pattern, alag ecosystem:** dono "package registry se fetch karo aur subprocess me run karo" wale runners hain. MCP yahan apni **protocol-not-framework** baat prove karta hai — host ko farak nahi padta server Python me likha hai ya JS me; **stdio pipes** pe JSON-RPC same hai. Bilkul jaise HTTP client ko server ka language matter nahi karta.
- **Sandbox-scoped filesystem server = chroot/Docker volume mount wali thinking:** agent ko full FS access dena `root` container chalane jaisa hai. `server-filesystem` ka sandbox path ek **explicit allowlist boundary** hai — production me bhi MCP servers ko least-privilege principle se hi mount karo.
- **Supply-chain alert:** `npx <package>` chalana arbitrary code execute karna hai — wahi risk jo random `pip install` me hota hai. Anthropic ke **official reference servers** (jaise `server-filesystem`) trust karne layak hain; random marketplace servers ke saath wahi caution jo aap unknown PyPI packages ke saath rakhte ho.
- **Hands-on lab:** is lecture ka code khud chalane ke liye ye lab run karo — `Practical/lab1_mcp_intro.py` (is repo me, `uv run` se chalta hai, Groq pe free). **Difference:** hamare labs me node/npx wale servers (Playwright, server-filesystem) ki jagah **Python FastMCP servers** hain (`servers/` folder me) aur Playwright browser automation skip hai — concepts (stdio spawn, list_tools, sandboxing) wahi ke wahi hain.

---

## 🧠 Takeaway (yaad rakho)

1. **Python MCP server = uvx, JavaScript MCP server = npx** — client-side code construct (MCPServerStdio + params + timeout + list_tools) dono ke liye identical rehta hai.
2. **Playwright MCP server fetch se kahin powerful hai** — 1 tool nahi, pura granular browser-control toolkit (click, screenshot, navigate, console, upload...).
3. **MCP servers stack karna trivially easy hai** — jo pasand aaye, params bana ke add kar do; agent ke paas tools ka whole slew aa jaata hai.
4. **`server-filesystem` (Anthropic reference, npm)** agent ko file read/write deta hai — lekin **sirf sandbox directory ke andar**, isolation built-in.
5. **Recent Node version mandatory** — `npx --version` se verify karo, purana ho to NVM se upgrade.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Okay, so now we're moving on to another MCP server before we come back and actually put this one to use. So this one, the first one we looked at, was an example of a Python based MCP server that we executed by calling uvx and passing in the name of something that is on PyPI that you could pip install that is able to run. Now, what we're going to do now is use a JavaScript based MCP server. And whilst Python based ones you typically run using uvx, JavaScript ones you run using server side JavaScript, which uses something called node that I imagine most of you are probably very familiar with, but you may not be. If you're not and you don't have node installed in your system, then please follow this link to follow ChatGPT's instructions. It is super simple, and installing node is like — what? So many people have that. And by the way, you do need to have a recent version of node. So following this, if you're a node person already and you've got an older version, then use NVM and make sure that you're on a recent new version of node, and make sure you can type like npx minus minus version, and that you get a good recent version.

So we're now going to use this to have a node based MCP server. So this time when we specify the parameters, the command we're going to run is not uvx but it's npx. We're using npm, the node package manager. And this isn't getting pip installed in the same way as before. This is now using npm. This is coming as an official node package. And we're using playwright, Microsoft's playwright, which is the browser automation software. And this is a particularly popular MCP server that runs with node using playwright. Now you might say to yourself, hang on a second, but isn't the fetch MCP server that we just did — didn't you mention that also uses playwright behind the scenes? And it's true, it does. But there's a benefit to using this MCP server, which will become very clear to you in just a second.

All right. So once we've specified the parameters, we then have exactly the same code construct. We take MCP server stdio, our context manager. We pass in the parameters. Again, remember this timeout is important to have. And then we call server tools again to find the tools that comes from this. And when I run this, it's going to call npx, which is going to then install that package and then call the tools on it. And wowza, this is what we get back. So this is the difference from fetch. Fetch — we just got one tool. This is actually giving you much more granular control over the playwright process. This is a ton of tools to do things like close the browser, resize the browser, see the console messages, upload a file, press a key, navigate back and forward, take a screenshot which is super interesting. Drag, click, hover, select. So this is giving fine grained control over the browser window to our agent, where fetch was a much simpler MCP server just to collect one web page. So this is pretty exciting. This is opening the ability for us to write agents that can power a browser window, much as our sidekick did in week four.

And now, one of the great things about MCP servers is that it's so easy to equip your agent with a whole slew of these. You can just find ones that interest you and just add it in, which is why we're going to go on and do another one. It's going to be another JavaScript based one, another node based one. And so you can see, first of all, I'm just going to use this just to quickly get the name of a directory. I'm going to get the name of a directory called sandbox inside this directory right over there. And if that doesn't already exist for you in your file system, you might need to create that sandbox folder right there, that directory. So I'm going to get that path. And then again I'm just going to create one of these parameters. The command is npx again to run node. And I'm passing in again the name of something that's an npm — that is another anthropic example reference MCP server. And it's called server filesystem. And it kind of does what you're probably expecting. But we'll make it list its tools again.

So now this is again running that node program, the server. It created a client. It spawned the server. It connected to it. It asked for tools. And this is what it got back. It's able to basically read and write from your local file system. It can read a file, read multiple files, create a directory, list directory, and so on, but always within the sandbox path that we specified. So this is allowing you to equip an agent with tools so that it can read and write from your file system, but keeping it isolated to within a certain directory.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
