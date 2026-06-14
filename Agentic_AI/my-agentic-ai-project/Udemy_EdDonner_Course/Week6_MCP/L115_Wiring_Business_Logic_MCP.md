# L115 — Day 2: Wiring Business Logic into Your MCP Server

> **Week 6 — MCP** · ⏱️ ~6m · 🎥 Lecture 115 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 50767635

---

## 🎯 Ek Line Mein (TL;DR)

Is lecture me hum apna **khud ka MCP server** banate hain — week 3 ke **Crew agent team** ka likha hua `accounts.py` **business logic** ko **FastMCP** se wrap karke, **`@mcp.tool`** decorated functions + kuch **resources** ke saath, jo **stdio transport** pe run hota hai.

---

## 📝 Hinglish Explanation (Detailed)

- Hum wapas **Cursor** me hain, **week 6 folder** ke **Lab 2** me — goal: apna **khud ka MCP server aur client** banana. Ed ka point: ye **"pretty simple, but not super simple"** hai. MCP ka asli excitement **doosron ke tools use karne** ki aasani me hai, servers **banana** utna trivial nahi (par mushkil bhi nahi).
- Pehle ek **Python module `accounts`** dekhte hain — ek trading account manage karne ka pura **business logic**:
  - **Buy/sell shares** (market price pe), **balance** track karna
  - **Profit & loss (P&L)** calculate karna
  - **Transactions list** karna, **report** generate karna
- Twist: ye code **humne nahi likha** — ye **week 3 me hamari CrewAI engineering team** (agent crew) ne generate kiya tha! Ed mazaak karta hai ki code me **comments aur type hints** hain, isliye saaf pata chalta hai ki ye usne khud nahi likha (wo "hacky" hai) — **agents ne wonderful job** kiya.
- Ed ne sirf ek **chhota change** kiya: ab accounts ek **database me save** hote hain. Uske liye alag module **`database.py`** banaya — bilkul **vanilla SQLite**, jo accounts ko **JSON objects** ki tarah read/write karta hai, aur `accounts.py` se hook up hai. Baaki code **basically untouched** — agents ka likha hua.
- **Lab me demo** (pehle bina MCP ke, direct Python):
  - `account.get(name)` → us id ka account milta hai. Ed ke account me **$9,400 balance**, **3 Amazon shares**, kuch transactions.
  - `buy_shares()` call — 3 aur Amazon shares, aur ek **reason dena zaroori hai** ("this bookstore website looks promising" — clock rewind joke 😄). Ab 6 shares.
  - `report()` → account ki full info; `list_transactions()` → saare transactions.
  - Point: business logic **kaam karta hai** plain Python ki tarah — ab ise MCP server banana hai.
- **Ab MCP server time** — writing an MCP server is mostly **boilerplate**: jo code already hai usko wrap karna, Anthropic ki libraries (MCP **Python SDK**) use karke. Module: **`accounts_server.py`**:
  - **`from mcp.server.fastmcp import FastMCP`** type import — **FastMCP** class, plus apna business logic `accounts` import.
  - `mcp = FastMCP("account_server")` → is naam ka ek **naya FastMCP server** create.
  - Phir kai functions **`@mcp.tool()`** decorator ke saath — har ek ke liye:
    - Function (jaise **`get_balance`**)
    - **Docstring** se description (LLM ko yahi se pata chalta hai tool kya karta hai)
    - Body me sirf **delegation to business logic** — koi naya logic nahi
  - Tools list: **`get_balance`**, **`get_holdings`**, **`buy_shares`**, **`sell_shares`**, **`change_strategy`** (portfolio ki strategy badalne ke liye).
- **Resources bhi hain** — Ed bolta hai resources **tools jitne common nahi**, par dikhana chahta hai:
  - Account ke **naam** se uska **report** return hota hai; **strategy** resource se uski strategy.
  - Har resource ko ek **fake URL jaisa URI** milta hai (e.g. `accounts://accounts_server/{name}` style) — isi se describe hota hai ki **kaunsa resource** provide ho raha hai jab koi request kare.
- **Bottom of file** — final piece: jab ye Python script **run** hoti hai, to `mcp.run(transport="stdio")` call hota hai — **transport = stdio** (the usual). Matlab: script run → **MCP server launch** → business logic import → saare tools **ready to handle**.
- Closing: **"It's not super simple, but it's not hard at all"** — apne business logic ko MCP server me wrap karna easy hai. Agla step: ise **use karke dikhana** (client side).

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **`accounts.py`** | Trading-account business logic module — buy/sell, balance, P&L, transactions — **week 3 ke Crew agents** ka likha hua code |
| **`database.py`** | Naya chhota module — **SQLite** me accounts ko **JSON objects** ki tarah save/load karta hai |
| **FastMCP** | MCP Python SDK ki class — minimal boilerplate me MCP server banane ka high-level tareeka |
| **`@mcp.tool()`** | Decorator jo ek plain Python function ko **MCP tool** bana deta hai — docstring = tool description |
| **Delegation pattern** | Tool function ke andar koi logic nahi — bas imported **business logic ko call** karna |
| **MCP resource** | Tool nahi, **data exposure** — URI (fake-URL jaisa) se identify hota hai; yahan account report aur strategy resources hain |
| **Resource URI** | `scheme://path/{param}` style address jo batata hai kaunsa resource maanga ja raha hai |
| **`mcp.run(transport="stdio")`** | Script ke bottom ka entry point — run hote hi server **stdio transport** pe live ho jata hai |
| **stdio transport** | Host/client server ko **subprocess** ki tarah spawn karta hai, baat **stdin/stdout pipes** se hoti hai |
| **Boilerplate wrapper** | MCP server likhna = existing code pe thin wrapper; naya logic likhna nahi padta |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **FastMCP ≈ FastAPI for tools**: `@mcp.tool()` bilkul `@app.get()` jaisa feel karta hai — decorator + **type hints + docstring** se schema auto-generate hota hai (jaise FastAPI Pydantic se OpenAPI spec nikaalta hai). Yahan wahi spec LLM ke liye tool-definition ban jata hai.
- **Thin controller pattern**: tool functions me zero logic, sirf delegation — exactly jaise aap REST controllers ko thin rakhte ho aur service layer me logic. MCP server = transport/adapter layer, `accounts.py` = service layer. Isi wajah se same business logic plain Python, REST, ya MCP — teeno se serve ho sakta hai.
- **Resources vs tools** = **GET vs POST/RPC** wali mental model: resource = URI-addressable **read** (side-effect-free data, jaise REST resource), tool = **action/invocation**. Aur stdio transport ko socho ek subprocess ke stdin/stdout pe chal raha JSON-RPC — koi port, koi HTTP nahi.
- **Hands-on lab**: is lecture ka code khud chalane ke liye `Practical/lab2_custom_accounts_server.py` run karo (is repo me, `uv run` se chalta hai, **Groq pe free**). Hamare labs course se thode alag hain — node/npx servers ki jagah **Python FastMCP servers** (`servers/` folder me) aur paid APIs ki jagah free substitutes — par is lecture ka accounts server to waise bhi pure Python FastMCP hai, isliye lab almost 1:1 same hai (bas LLM OpenAI ki jagah Groq free tier).

---

## 🧠 Takeaway (yaad rakho)

1. **MCP server banana = boilerplate wrapper** — existing business logic ko `FastMCP` + `@mcp.tool()` se wrap karo, bas.
2. **Docstrings matter**: tool ka docstring hi LLM ke liye uska description hai — isko API documentation ki tarah seriously likho.
3. **Tools me logic mat likho** — sirf delegate karo; business logic alag module me rakho (testable, reusable).
4. **Resources = read-only data via URI**, tools = actions; resources kam common hain par pattern jaan lo.
5. `mcp.run(transport="stdio")` se script khud ek **spawnable MCP server** ban jati hai — aur fun fact: andar ka business logic **week 3 ke agents ka likha code** hai (agents writing code for agents!).

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

And we're right back in Cursor again, of course. And we're going into the week six folder and we're going to lab two to create our own MCP server and client, which as I put here, it's it's pretty simple, but it's not super simple. The reason people are excited about MCP is that it's so simple to use other tools, not necessarily to create MCP servers.

The first thing we're going to do, though, is we're going to look at a Python module. And I know that that many people would much rather spend more time with Python modules than in labs. And this week we'll be doing both. We'll be starting in labs. We will be moving to just Python code in modules. And there is a Python module called accounts, and it contains a ton of code for managing your account, where you can buy and sell shares, and where you have a balance, and where you can do things like calculate profit and loss, list transactions, and where you can do things like buy shares and sell shares based on a market price. Looks like some interesting business logic and hopefully you remember it seems familiar to you because this is, of course, code generated by our agent team in week three, our engineering team in CrewAI. I created this code right here, and you can tell because it's got sort of like comments and type hints. And you probably know that I'm a bit hacky with this stuff, and that I only write comments and type hints when I'm when I'm forced. But here the our agent crew did a wonderful job. Um, so it's cool that we are taking the code here that is being used by our agents.

Now, I've made a slight change to it that I've updated it so that it does save accounts in a database, and I've separated that out into a separate module called database. And this is just simply using SQLite. So this is very vanilla. But it allows you to read and write accounts as JSON objects. And that I've hooked up to accounts.py. But apart from making tiny changes like that, it is basically untouched code written by our engineering team of agents in week three.

All right, so back to our lab, uh, for, for, uh, today. Okay, so let's get started. We'll do some imports. We are now going to import this Python module account okay. So now I can call account dot get. And if I pass in a name it gets the account with that id here I am. This is my account. Apparently I have a balance of $9,400. I have three Amazon shares and I have some transactions. This is the coming back from the code written by our agents and I can call buy shares. I can buy three more shares of Amazon. And I have to give a reason. And we'll just rewind the clocks a bit and imagine this is a few years back and I'll say, I'm going to buy three shares of Amazon because this bookstore website looks promising. So there we go. Uh, yeah. If only I'd had that foresight. Uh, okay. So I bought three, and now I have six shares of Amazon in there. And I can call account report to get a report about it. Uh, and all sorts of information, um, about it. And I can also call account list transactions to see those transactions right there. So this is just showing that we've got some code. It was written by our agents. And we can operate it to do things like buying shares and listing transactions.

Now it's MCP server time. So writing an MCP server is pretty easy. It's just boilerplate code that you use to wrap code you've already got into an MCP server and you use some libraries provided by Anthropic. And let's have a look. I've created one, a Python module called accounts_server. Let's see what happens. So it begins by importing an Anthropic class called FastMCP. And we also import our business logic account. And we then create an MCP server by saying FastMCP account server that is creating a new FastMCP server with that name. What we then have is a number of functions listed here which are decorated with @mcp.tool. And for each of them we have a function like get balance. We describe that function. We give information about it here using standard docstrings. And then we actually do that function. And in our case we're just delegating to our business logic. But the idea is that this server will be spawned when we launch the MCP server. This will be launched, and these tools will all be tools that will be available. And they will work simply by calling the business logic that we've imported right here. So we have get balance, get holdings, buy shares, sell shares, change strategy if we want to change the strategy associated with the portfolio.

And then I've also got some resources here. As I say, resources are not as common as tools, but I do want to show you how they work. And here we have the ability to access a resource, the name of an account will just return its report, and the strategy of an account will return its strategy. And it gets like a sort of a fake URL, a URI like this, where you can describe what resource you want to provide. If something requests this resource, and then down at the very bottom, we have the final piece here, which is that when this script, this Python script is run, what it should actually do is call the run function on MCP and say that my transport mechanism is the usual stdio. And by because we've done that, when this Python script is run, it will launch that MCP server, it will import our business logic, and it will be ready to handle any of these tools. And as you can see, there's not much to this at all. It's not super simple, but it's not hard at all to write your own MCP server that wraps your business logic and launches a server like that, and now we just have to try and put it to use.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
