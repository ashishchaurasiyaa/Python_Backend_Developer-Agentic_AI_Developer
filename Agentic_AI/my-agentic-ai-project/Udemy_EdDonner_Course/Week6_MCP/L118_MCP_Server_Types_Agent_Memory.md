# L118 — Day 3: Types of MCP Servers and Agent Memory

> **Week 6 — MCP** · ⏱️ ~8m · 🎥 Lecture 118 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 50767765

---

## 🎯 Ek Line Mein (TL;DR)

MCP servers ke **3 deployment types** hote hain — **fully local**, **local-but-calls-remote-APIs** (sabse common), aur **hosted/managed remote** — aur is lecture mein hum type 1 ka ek killer example chalate hain: ek **knowledge-graph memory MCP server** jo agent ko **persistent memory** deta hai (entities, observations, relations) — kyunki MCP world mein memory koi magic construct nahi, bas **tools ka ek aur set** hai.

---

## 📝 Hinglish Explanation (Detailed)

- **Week 6 Day 3 start** — Ed kehte hain ki aaj ka din special hai kyunki aaj hum **MCP ecosystem ko explore** karna shuru karte hain. Pehle ek quick recap of core concepts.

- **MCP servers ke 3 configurations** (architecture diagram pe):
  1. **Fully local server** — server aapke machine pe banta/chalta hai aur **sirf local cheezein** use karta hai. Example: humara khud ka haath se likha **accounts MCP server** (pichhle lab ka), ya **local file system server**. Sabse simple type.
  2. **Local server + remote API calls** — server **locally run** hota hai (subprocess ki tarah) lekin andar se **internet pe APIs call** karta hai. Ye **sabse common pattern** hai — jaise fetch, web search, market data servers.
  3. **Managed / hosted MCP server** — server **remotely** chal raha hai kisi aur ke infrastructure pe. Ed kehte hain ye **common architecture nahi hai** abhi; hum bas examples dekh ke samjhenge, zyada use nahi karenge.

- **Important nuance**: Type 1 aur 2 mein bhi, mostly aap server **khud nahi likhte** — ye **publicly shared servers** hote hain jo aap `uvx` (Python) ya `npx` (Node) jaise commands se **online repo se download karke locally run** karte ho. Matlab: code aapke box pe chal raha hai, lekin source publically shared hai. (Yahi se **supply-chain security** ka concern aata hai — L113 yaad karo.)

- **Lab 3 — Memory MCP server (Type 1: fully local)**:
  - Ed ek **Node/JavaScript MCP server** pick karte hain jo agent ko **knowledge-graph based memory** deta hai — ek special memory jo **entities**, un entities ke baare mein **observations**, aur entities ke beech **relationships** samajhti hai.
  - **Memory pe Ed ka hot take**: log memory ko **ek single construct** samajhte hain (shayad isliye kyunki **LangChain** usko aise hi model karta hai — "the memory"). Lekin **MCP age mein memory = bas tools ka ek aur set** jo hum LLM ko de dete hain. Aap ek hi agent ko **multiple types of memory tools** de sakte ho. End mein sab kuch sirf **context** hai — ya to tool calls se request hota hai, ya prompt mein aa jata hai. Different techniques, same goal: **LLM ko zyada context dena**.

- **Server setup (parameters)**:
  - Hamesha pehle **MCP server ke parameters** specify karte ho. Yahan command = **`npx`** (Node version run ho raha hai).
  - Server hai **libSQL memory server** — ye memory ko ek **SQLite database** mein store karta hai. Ed note karte hain ki ye ek purane JSON-file-based memory server pe based hai, lekin **SQLite wala version zyada stable** hai, isliye prefer karte hain.
  - Ye server aapko **directory + database name** specify karne deta hai — matlab **alag-alag agents ke liye alag-alag memory stores** rakh sakte ho. Ed `memory/` folder mein `ed` naam ka database use karte hain (aur demo fresh start ke liye purana `ed` file delete kar dete hain).

- **Memory server ke tools** (list karke dekha):
  - `create_entities` — nayi entities store karo
  - `search_nodes` — graph mein search karo
  - `read_graph` — poora graph padho
  - `create_relations` — entities ke beech relationships banao
  - `delete_entity` / `delete_relation` — cleanup
  - Matlab agent **connectivity build kar sakta hai** un cheezon ke beech jo wo yaad rakhna chahta hai.

- **Demo run (same familiar pattern)**:
  - Instructions: *"Use your entity tools as persistent memory to store and recall information about your conversations."*
  - User message: *"My name is Ed. I'm an LLM engineer. I'm teaching a course about agents, including the incredible MCP protocol."*
  - Code pattern wahi hai jo ab tak dekha: **`async with MCPServerStdio(params, client_session_timeout_seconds=30)`** context manager → MCP client banta hai → **Agent** create karo (instructions + model + `mcp_servers`) → **`Runner.run(agent, request)`**.
  - Result: Agent reply karta hai ("Nice to meet you, Ed...") aur **left side mein `ed` database file create ho jati hai** — memory persist ho gayi!

- **Follow-up test (recall)**:
  - Naya agent, same instructions, same model, same MCP server. Question: *"My name is Ed. What do you know about me?"*
  - Agent: *"I know that you're Ed, an LLM engineer, you're teaching a course about AI agents, and in this course you're teaching about the MCP protocol."* — **Persistent memory across runs** working!

- **Trace check karna mat bhulo**: OpenAI Traces mein dikhta hai ki agent ne **`search_nodes`** call kiya, **"Ed" query** ki, aur wapas ek **JSON structure** mila jisme **entity type, observations** waghaira hain. Trace dekh ke samajh aata hai memory andar se kaise kaam karti hai — isi se aap **zyada sophisticated memory** design kar sakte ho apne projects ke liye.

- **Aage kya**: ab Type 2 server ka turn — **locally chalta hai lekin internet use karta hai** (fetch aur Playwright jaise, jo pehle dekh chuke hain) — agla example aane wala hai.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **3 MCP server types** | (1) Fully local, (2) Local server + remote API calls (most common), (3) Hosted/managed remote server (rare) |
| **uvx / npx** | Commands jo public repo se MCP server **download karke locally run** karte hain (Python / Node respectively) |
| **Knowledge-graph memory** | Memory jo **entities + observations + relations** ke graph ke roop mein store hoti hai, flat text nahi |
| **Memory = tools, not construct** | MCP world mein memory koi single magic cheez nahi — bas ek aur **tool set** jo LLM ko context deta hai |
| **libSQL memory server** | Node-based MCP server jo knowledge graph ko **SQLite database** mein persist karta hai (JSON wale se zyada stable) |
| **Per-agent memory stores** | Directory + DB name parameters se **har agent ki alag memory** rakh sakte ho (e.g. `memory/ed`) |
| **`search_nodes` / `read_graph` / `create_entities` / `create_relations`** | Memory server ke main tools — graph banao, search karo, padho |
| **MCPServerStdio** | Context manager jo MCP client banata hai aur server ko **stdio transport** pe subprocess ke roop mein launch karta hai |
| **Trace** | Run ke baad observability check — dikhta hai kaunse memory tools call hue aur kya JSON wapas aaya |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **3 types ko deployment topologies ki tarah socho**: Type 1 = local daemon (like a local Redis), Type 2 = **local sidecar/proxy jo upstream APIs call karta hai** (like an API gateway sidecar in a service mesh), Type 3 = fully managed SaaS endpoint. Sabka contract same (MCP protocol), sirf deployment alag — bilkul jaise ek hi REST API local, proxied, ya hosted ho sakti hai.
- **Memory-as-tools** aapke liye familiar pattern hai: ye **session state ko external store mein offload** karna hai. Knowledge-graph memory basically ek **triple store / graph DB ka CRUD API** hai (`create_entities` ≈ INSERT nodes, `create_relations` ≈ INSERT edges, `search_nodes` ≈ indexed query) — LLM khud decide karta hai kab read/write karna hai. SQLite-backed version JSON-file wale se isliye better hai jaise WAL-backed DB flat-file se better hota hai — durability + concurrent access.
- **`npx`/`uvx` se public server chalana = `pip install` + auto-execute combined** — supply-chain risk wahi hai jo unpinned dependencies ka hota hai. Memory server jaise stateful server ke saath extra dhyan: wo aapke disk pe persistent data likh raha hai.
- **Hands-on lab**: is lecture ka code khud chalane ke liye ye lab run karo — `Practical/lab3_memory_market_servers.py` (is repo me, `uv run` se chalta hai, Groq pe free). Difference: course ke node/npx servers (libSQL memory waghaira) ki jagah humne **Python FastMCP servers** likhe hain (`servers/` folder me) — memory ke liye Wikipedia-style free memory server aur market data ke liye simulated market server; Playwright skip kiya hai.

---

## 🧠 Takeaway (yaad rakho)

1. **MCP servers 3 flavours mein aate hain**: fully local, local-with-remote-APIs (sabse common), aur hosted/managed (rare). Pehle do bhi mostly `uvx`/`npx` se public repos se aate hain.
2. **Memory ek single construct nahi hai** — MCP age mein memory = tools ka ek aur set. Ek agent ko multiple memory types de sakte ho; sab end mein LLM ke liye context hi hai.
3. **Knowledge-graph memory** entities, observations aur relations store karti hai — libSQL server ise **SQLite mein persist** karta hai, aur directory/DB-name params se **per-agent memory stores** milte hain.
4. Code pattern same rehta hai: **`MCPServerStdio(params)` → `Agent(mcp_servers=[...])` → `Runner.run()`** — memory dena bas ek aur MCP server attach karna hai.
5. **Trace hamesha check karo** — `search_nodes` call aur returned JSON (entity type, observations) dekh ke hi samajh aayega memory actually kaise kaam kar rahi hai.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

And welcome to week six, day three, and I've been looking forward to today for a long time, because this is the day when we go crazy exploring what MCP has to offer first. As usual, a quick recap of the core concepts behind MCP. Looking at the architecture diagram that we've got here, we're going to be looking at the three different configurations of MCP servers. First of all, and the simplest of all is when you use an MCP server that's simply is created, runs on your local computer, only, uses stuff on your computer, and is something that you're using right there, just like the accounts MCP server that we just used, which was actually one that we hand wrote ourselves, and also one like the local file system. Okay. And then secondly, and this is perhaps the most common of all, we're going to look at MCP servers that are run locally on your computer, but make remote calls to APIs that take advantage of stuff that can be available online. And that's number two on this diagram. And that is of course super common. And then thirdly, and we're not going to do this too much. We're just going to have a look at what it means to have a managed MCP server or a hosted MCP server, which is running remotely, as I say, not a common architecture, but we'll just look at it and see some examples and understand it.

And it's worth pointing out that even numbers one and two, while it's possible to write your own most of the time when we're talking about MCP, these are MCP servers that have been made available online, and that through commands like uvx you are downloading it from an online public place and you are then running it locally on your box. So it's running on your box, but it's still something that's been shared online, made available for everyone to use. All right, that's enough. Intro. Let's go to the lab.

Here we are back in cursor and we're going into the week six. Of course. Which other week would we want to be in and into the third lab, and we're going to be experimenting with a bunch more MCP servers. So the first type of MCP server that I mentioned is one that you run locally and everything it does is local. Again, remembering we have downloaded it from, from a public repo from somewhere public. But we're going to run it. The server will be applied locally and we're going to pick another JavaScript one, a node one. And I want to pick this one, which is great. It is a way to give our agent memory and to give it knowledge graph based memory, a special kind of memory that understands about entities and observations about those entities and relationships between those entities.

It's worth — memory is a hot topic, and people often ask me questions about memory, and they think of memory like it's kind of one construct, perhaps because LangChain thinks of it that way, but like there is one memory. But in this MCP age, we think of memory just as being another set of tools that we can equip our LLM with. And in fact, it could have many different types of tools relating to memory. This in particular is giving it the ability to store information about things, observations and relationships. We could give it this and we could give it other kinds of context. All of this ends up just being information that it can request by tools, or that becomes available in its prompts. And so they're just different techniques to give the LLM more context.

Anyway, so these are the parameters. Remember you always start by specifying the parameters of your MCP server. And in this case it's npx because we're running a node version. And it's uh, we're going to be running this version called libSQL, which is a version, a memory that stores to a SQLite database. I've actually I've given a link here to one that this is closely based off, which is one that, uh, gives you access to a JSON file. Um, but doesn't actually store it to SQL. And I found that this is a little bit less stable. This is a better version of it that I prefer. It also allows you to specify a directory and a name for your memory. And this allows you to have different memory stores for different agents. So I find that quite handy. So I'm saying that looking looking somewhere called memory and look for database called ed. And I believe it might already exist. It does. So why don't we just delete this so that it doesn't have any memory to start with? We'll move that to trash starting from nothing. So if you have ed in in a folder there, then delete it. If you don't have a folder then then create one called memory.

All right. So first of all let's just find out what tools do we have uh associated with this. We have tools create entities, search nodes, read graph, create relations, delete entity and delete relation. So we're allowing it to build this kind of connectivity between the things it wants to remember.

All right let's see this in action. Okay. So now we have instructions. You use your entity tools as persistent memory to store and recall information about your conversations. My name is Ed. I'm an LLM engineer. I'm teaching a course about agents, including the incredible MCP protocol. And I say something about MCP and I give it a model and let's see how this gets on. So as before, this is hopefully a pattern that you're quite familiar with. We use this context manager with MCP Server Stdio, which we know is going to create the MCP client. We pass in the parameters. We give this timeout of 30s. And then as usual, we create our agent with instructions with the model and now with the MCP server. And now we call runner run with the agent and our request. And let's see what happens. Armed with these tools is it able to take this piece of information about me and do something with it? So it says, nice to meet you, Ed. It's great to know you're teaching a course about AI agents and MCP protocol, blah blah blah, blah blah. And if you look over on the left, it has created a file ed.

So now for the follow up question. We're coming back. We're creating an agent. We're giving it instructions. We're giving it the same asking for the same model, and we're giving it the same MCP server with access to the memory. And we're saying, my name is Ed. What do you know about me? And we'll see what this MCP server is able to do. I know that you're Ed, an LLM engineer. You're teaching a course about AI agents, and in this course, you're teaching about the MCP protocol. So there you go. It's a quick, simple example, but it shows you how we were so easily able to equip our agent with a memory that's able to handle relationships between things. And so this is just a great starting example, and we'll be using this memory in the future as well. And it could be handy for any of your projects too.

And of course, it's always a good idea to check the trace, which we should do. Come on in and conversation with our agent is right here and you will see that it called the search nodes. It did a query for Ed and it got back here a JSON structure that reflects the entity type, the observations and so on. And so you can look through this and get a sense for how the memory works. And you can use this to try and build up some more sophisticated memory about the different, uh, parts of your conversation that you want your agent to remember.

Okay. Now we're going to go on to another MCP tool, and this time it's going to be the second type, which is the type that runs locally but uses the internet, which we've already done with fetch and with Playwright. But let's do another and a handy one.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
