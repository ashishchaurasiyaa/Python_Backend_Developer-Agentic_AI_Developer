# L123 — Day 4: UI for Trading Activity

> **Week 6 — MCP** · ⏱️ ~11m · 🎥 Lecture 123 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 50768327

---

## 🎯 Ek Line Mein (TL;DR)

Is lecture me hum trading floor capstone ke **do agents** banate hain — ek **Researcher agent** (web research karta hai) aur ek **Trader agent** ("Ed") — jisme researcher ko **`as_tool()`** se tool banakar trader use karta hai, aur trader apna **account + strategy** MCP **resources** se padhkar real trades execute karta hai.

---

## 📝 Hinglish Explanation (Detailed)

- **Setup recap:** pichle lecture me humne saare MCP server **params** ek list me gather kiye the. Ab un params se actual **MCP servers instantiate** karte hain, har ek pe **30 second timeout** ke saath. Ek saath kai servers ready ho jaate hain.

- **Do agents ka plan:** ek **Trader** (trading decisions leta hai) aur ek **Researcher** (market research karta hai). Trader researcher ko use karega. Week 2 (OpenAI Agents SDK) yaad karo — jab ek agent doosre agent ko use kare, to **best pattern** hai us doosre agent ko **tool me convert** kar dena. Wahi yahan karte hain.

- **Researcher agent:** system prompt = "you're a financial researcher, web search karo interesting news ke liye, phir deeper research karke findings do." **Current date prompt me directly daal dete hain** — Ed ka funda: date ke liye alag tool banana extra complexity hai; date hamesha pass karni hi hai to seedha prompt me daalo. Phir MCP servers pass karte hain — researcher ready.

- **`as_tool()` construct:** researcher pe `as_tool()` call karke usse **naam + description** ke saath tool bana dete hain. Ab koi bhi doosra agent isse normal tool ki tarah call kar sakta hai. Ye **OpenAI Agents SDK ka very common pattern** hai.

- **Pehle direct test:** tool banane se pehle researcher ko directly call karke check karte hain — "What's the latest news on Amazon?"

- **Context manager ka alternative:** normally hum `async with MCPServerStdio(...)` likhte the. Lekin yahan **bahut saare servers** hain — nested `with` blocks clunky ho jaate. Isliye is baar manually **connect** karte hain (loop me). Caveat: aise karo to **cleanup bhi khud karna chahiye**; Jupyter lab me chal raha hai isliye yahan chalta hai.

- **`max_turns=30`:** `Runner.run()` me naya parameter — **max_turns**. Default **10** hai (yaani max 10 rounds of tool calls). **Deep research** ke liye zyada chahiye, to 30 diya. Ulta bhi kar sakte ho — chhota number do agar agent ko **overthinking loop** me jaane se rokna ho. Ye ek aur control knob hai jo yaad rakhna chahiye.

- **Trace dekho (researcher):** trace me dikhta hai — **Brave search** → kai **web page fetches** → ek aur Brave search → aur fetches → final answer. Ed bolta hai: khud jaake trace dekho, samjho agent research me kya kar raha hai.

- **Trader ki strategy:** har trader ko ek **strategy** dete hain jo **account me store** hoti hai. Store isliye karte hain kyunki traders ko **autonomy** deni hai — wo chahein to apni strategy **evolve** kar sakein. Ed ki initial strategy: *"day trader jo news aur market conditions ke basis pe aggressively buy/sell karta hai."* `reset` function se Ed ka account fresh start pe: **$10,000 cash**, empty transactions, empty portfolio.

- **MCP resources in action:** trader agent banate waqt **account details** aur **strategy** dono **MCP resources** se **read** hote hain — hamara khud ka **MCP client** (jo do din pehle banaya tha) MCP server ko call karta hai jo business logic se resource return karta hai. **Key idea: MCP sirf tools ke liye nahi, resources ke liye bhi hai.**

- **Resource ka matlab kya?** Bahut simple — **resource = text jo prompt me shove karte ho**. Extra context for decisions. System prompt: "You're a trader named Ed, your investment strategy is `<strategy resource>`, your current holdings and balance: `<account JSON>`." Ed: **"LLMs love JSON"** — JSON seedha prompt me daal do, model ko totally samajh aayega.

- **Trader run:** saare MCP servers connect → researcher ko **tool** banao → trader agent banao (instructions + researcher-tool + **full MCP servers list**) → model **GPT-4o mini** (Ed suggest karta hai: ab dekh rahe ho to **GPT-4.1 mini** use karo) → `Runner.run(trader, prompt, max_turns=30)`.

- **Result:** market closed hone ke bawajood trader ne trades karne ka decide kiya (tool diya tha, to use kiya!). Summary me — research results, executed trades (shares buy/sell), current portfolio status, next steps.

- **Trace dekho (trader):** Ed ka mantra — **"You always have to go and check out the traces."** Trace me: trader → **researcher tool** (green = tool call, ~half time research me gaya) → MCP tools listing → Brave search + fetches → phir market data: **tickers, last trades, quotes, close-of-market prices, previous close** → finally buy/sell execute.

- **Funny behaviour:** trader ne **50 Disney shares kharide, turant 25 bech diye**, phir **30 Tesla** kharide. Hugely intelligent nahi, lekin humne hi bola tha "aggressive day trader" — to wo wahi kar raha hai, bas instantly!

- **Final check:** MCP client se **resource dobara read** karke verify — cash balance kam hua, 25 Disney shares portfolio me hain. Trades sach me account state me persist hue.

- **Next:** ab in notebooks ko proper **Python modules** me convert karenge.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **`as_tool()`** | Ek agent ko tool me convert karna taaki doosra agent usse call kar sake — agent-as-tool collaboration pattern (OpenAI Agents SDK) |
| **Researcher agent** | Financial researcher — web search + page fetch karke news/research findings deta hai |
| **Trader agent ("Ed")** | Portfolio manage karne wala agent — strategy + account resources padhkar trades execute karta hai |
| **`max_turns`** | `Runner.run()` ka limit — kitne rounds of tool calls allowed (default 10; deep research ke liye 30) |
| **MCP resource** | MCP se mila text/data jo seedha **prompt me daala** jaata hai as context (tools ki tarah execute nahi hota) |
| **Strategy (stored)** | Trader ki investment strategy jo account me persist hoti hai — agent ise khud evolve kar sakta hai (autonomy) |
| **Manual connect (no `with`)** | Bahut saare MCP servers ho to nested context managers ki jagah loop me `connect()` — par cleanup ka dhyan rakho |
| **Trace** | Run ke baad hamesha trace check karo — kaunse tools chale, kitna time research me gaya, kya trades hue |
| **"LLMs love JSON"** | Account state JSON ke roop me prompt me shove karna perfectly fine hai — model use aaram se samajhta hai |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Agent-as-tool = service composition:** researcher ko `as_tool()` karna waise hi hai jaise ek microservice doosri service ko **RPC client** ke through call kare — caller (trader) ko sirf naam + description (interface contract) dikhta hai, implementation (poora agent + uske MCP servers) hidden rehta hai.
- **MCP resources ≈ REST GET / config injection:** tools = POST (side-effects, execution), resources = GET (read-only context). Aur "resource ko prompt me shove karna" basically **dependency/context injection at request time** hai — jaise template render se pehle DB se state fetch karke context dict me daalna.
- **Manual connect without context managers** = wahi trade-off jo aiohttp sessions ya DB connections me hota hai: `async with` safe hai par N servers pe nested ho jaata hai; manual `connect()` flexible hai par **cleanup/`close()` ki zimmedari tumhari** — production me `AsyncExitStack` use karo, Jupyter me chalta hai.
- **`max_turns` = retry/recursion budget:** ye waise hi hai jaise circuit breaker ya max-retries config — bina iske agent infinite tool-call loop me ja sakta hai. Cost aur latency dono pe direct cap.
- **Hands-on lab:** is lecture ka code khud chalane ke liye `Practical/lab4_trading_floor.py` run karo (is repo me, `uv run` se chalta hai, Groq pe free). Hamare lab me ek difference: course ke **Brave Search + fetch (node/npx) servers** ki jagah hum **Python FastMCP servers** (`servers/` folder) use karte hain, aur **Polygon paid market data** ki jagah **simulated market server** — concepts (agent-as-tool, resources, max_turns) bilkul same hain.

---

## 🧠 Takeaway (yaad rakho)

1. **Agent collaboration ka best pattern (OpenAI Agents SDK): doosre agent ko `as_tool()` se tool bana do** — trader ne researcher ko aise hi use kiya.
2. **MCP sirf tools nahi — resources bhi:** account + strategy resources se padhe gaye, aur resource ka matlab simple hai — **text jo prompt me jaata hai** (JSON bhi chalega, LLMs love JSON).
3. **`max_turns` default 10 hai** — deep research ke liye badhao (30), overthinking loops rokne ke liye ghatao.
4. **Bahut saare MCP servers ho to manual connect karo** nested `with` ki jagah — par cleanup yaad rakho.
5. **Hamesha traces check karo** — wahi pata chala ki trader ne 50 Disney kharid ke turant 25 bech diye (aggressive strategy literally follow ki!).

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Okay, so we've gathered up our parameters into these params lists. What we're now going to do is create MCP servers. We're going to instantiate MCP servers with each of those params and with the 30 second timeout. And so we do all of that. And we've just built a bunch of these MCP servers ready to go okay.

So we're going to have two different agents that we're going to define. We're going to have a trader that's able to make trading decisions, and a researcher that does market research, and the trader will use that researcher. And you may remember from week two in OpenAI Agents SDK that when you want to have that kind of collaboration where one agent uses another, the best way to do it is to have that other agent, the research agent, be like a tool, convert it into a tool so that that agent can just be used as a tool by the trader agent. And that's exactly what we're going to do now.

So we start by defining our researcher agent. So here's the system prompt the instruction. You're a financial researcher, you search the web for interesting news, and then you carry out deeper research and respond with your findings. And we tell it the current date. And you remember I said, it's better to do this than to have a tool to look up the date, because you might as well always pass it on and not add extra complexity to the agent to force it to come back and run a tool. So we just provide the current date right in there, and then we pass in, of course, our MCP servers and that defines our researcher.

And then you'll remember this construct. This is how we say we want to use this as a tool. We simply call as tool on that researcher. And we give the tool a name and a description. And that means that this agent will be available for use by other agents that want to be able to treat this like it's a tool. And that is a very common pattern with OpenAI Agents SDK.

Well, before we use the research agent as a tool, let's just try calling it directly to check it works. Uh, so we're going to ask the question, what's the latest news on Amazon? And we're going to, first of all, go through and connect with all of our MCP servers. Now you'll notice this is a bit different. I normally have like with MCP stdio. And then I do it that way with a context manager. So why am I doing it differently this time? Because if you've got a bunch of these, we'd have to have lots of withs all nested, and that would be quite clunky. And so this is just another way of doing it. You should also clean up if you do this. But because we're just running in a Jupyter lab anyway, it doesn't really matter.

So we're connecting to the server here. Uh, we're then getting our research agent and then we're calling runner run for the research agent passing in the agent. And the question and this is new. I'm also passing in something called max turns in here. And that's because the default is ten, which means that it can by default do up to ten sets of tool calls. But if we wanted to do deep research, we might want it to take longer than that. So we might want to give it up to 30 possible maximum turns. So that's why I'm setting it that way. And it's good to know that that's another thing that you can control. And you can also of course have that be a smaller number if you don't want to let your agents go off and potentially get into a loop of overthinking about things. But 30 seems to have done the trick for us, and probably we didn't need anything like that. And we got back a bunch of information about Amazon.

Let's go in and look at the trace to see what happened behind the scenes. So if we come in to the trace and we come into the researcher, you'll see that it did a Brave search. It did a bunch of fetching of web pages. It did another Brave search and some more fetching of web pages before responding with its answer. And you should do this and go back and have a look and see what it does and what kind of searching and fetching the agent is doing as part of its research into Amazon.

Okay. So now let's look at our trader. So I'm going to start by giving our trader a strategy because that's something that we store in the account. And the reason that I give the trader a strategy which is stored is that I want traders to be able to change that strategy, should they wish. We're going to give each of our traders a unique strategy to set them going, but we want to give them some autonomy to choose to evolve their strategy if they want to. But for me, Ed's initial strategy, I'm going to be a day trader that aggressively buys and sells shares based on news and market conditions. And I'm going to call this reset function to get Ed off to a good start. And that's that — read, use these resources to read my account and my strategy at this starting position. So here we go. My starting position is I have $10,000 ready to invest there. There is my description and I have empty transactions and nothing in my portfolio and everything is ready, ready for business.

It's now time to create our trader agent that is going to take this persona and be able to make trades as a result. Okay, so this is our trader agent right here. It's called Ed. And, uh, the account details, it's reading in a resource. And the strategy, it's reading a resource. What is this reading a resource? This is of course, calling the MCP client that we created ourselves a couple of days ago. It's calling an MCP client that then calls the MCP server that provides the resource by calling our business logic. So it's kind of cool. We're using this resource side of MCP. The fact that you don't just need to use MCP for tools, you can use it for resources as well.

And so what does it mean to use MCP for resources? What do you do with these resources? Well, it's just text that you shove in the prompt. You just add it to the prompt to give your agent more context to be able to make its decisions. And that's exactly what we do here. So we call these two resources. And then we put together our system prompt. You're a trader that manages a portfolio of shares. Your name's Ed, your account's under your name. You have access to tools to do your job. Your investment strategy is — and then we shove in the strategy from this call here — your account, your current holdings and balance is — and we just shove in the account details right here. And then we tell it to make decisions based on its tools. So if we run that and we print the instructions, we'll see that when it prints out, we get things like the current holdings and balance included in our prompt. This is our resource. And you can see I'm just shoving JSON in there because LLMs love JSON. It's going to be great with this. It'll make total sense to it.

And so with that we can kick off our trader. So set this running while I speak. So we connect to each of the MCP servers. We then turn our research agent into a tool, and we get our research agent as a tool. We then create our trader agent. We give it its instructions. We pass in as tools, we pass in our researcher tool, which is a wrapper around the agent. For MCP servers, we pass in the full set of MCP servers. We're using GPT-4o mini in here. You might want to update that to GPT-4.1 mini if you're looking at that now. And then we call runner dot run and we pass in the trader and the prompt. And again I'm adding to max turns. I'm not going with the default of ten. I'm giving it up to 30 turns to really go to town and be requesting across things.

And now typically this takes a minute. So I'm drawing out this explanation as long as I possibly can in the hope that it finishes before. And it may well observe that the markets are closed right now so it can't make trading decisions. It's possible that it will do that, or it might decide that it wants to make some trading decisions anyway, even though the markets are closed. But we will soon find out. Uh, so here we go. It's — no, it has decided that it has. We gave it the tool to do it, and so it's decided to do it. It's got a bunch of different summary actions, the results of the research and the trades that were executed, that it bought shares and sold shares. And that's the current portfolio status. And it's got some next steps at the bottom. So that is the result of our trader agent running using the research agent and being able to execute its tools, and also being armed with the resources that we included in the prompt.

And I wouldn't be doing my job if I didn't say that we have to go and look at the traces. You always have to go and check out the traces and make sure you're happy with what's going on. And it shows here that this was Ed, the trader agent going to the researcher, the researcher agent that we're using as a tool. You can see that about half the time is spent in research mode. It used the tool — that green shows it's using a tool called researcher. That's then using our agent. We're listing the MCP tools. And we're then doing a Brave search. We're doing the fetches. This is like before and that's coming back. We have to press load more because it's such a long thing here. We're then getting some tickers. We're getting the last trades, we're getting some quotes, we're getting some close of market prices. It's doing plenty. It's getting the previous close prices. Uh, and then it ends up buying some shares and selling some shares just like it told us it did.

If we click here we can see that it's bought Disney. And uh, it's also sold 25 shares of Disney. So it's not hugely intelligent of it to buy shares and sell so quickly. But I guess we did tell it that I'm an aggressive trader that likes to buy and sell. I mean, that's super fast to do it instantly like that, but I guess that is what it wants to do. So it bought 50 and then it sold, and then it bought 30 Tesla and it sold 25 of the Disney shares that it just bought. So there you have it. That is our trace that is showing our trader in action. It's showing the collaboration between two different agents. One of them is a tool and it's showing the use of the MCP servers.

Well let's just quickly look at the results of the trading by reading the resource again using the MCP client. And you can see that I've got less in my cash balance, uh, and that I have my remaining 25 shares of Disney. And that is the, uh, the various details we have there about what's going on. All right. We're now going to look at some Python modules.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
