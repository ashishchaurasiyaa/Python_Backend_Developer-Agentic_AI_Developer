# L116 — Day 2: Creating Client Code to Use Your MCP Server

> **Week 6 — MCP** · ⏱️ ~12m · 🎥 Lecture 116 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 50767643

---

## 🎯 Ek Line Mein (TL;DR)

Apne **custom accounts MCP server** ko pehle **Agents SDK** ke `MCPServerStdio` se use karo (2 lines, sab free milta hai), phir Ed dikhata hai **manual MCP client** likhna kaisa hota hai — **session plumbing**, **MCP-tool → OpenAI-tool mapping**, aur **resources** read karna — jo aaj sirf resources ke liye zaroori hai, kyunki tools ke liye SDK ne client likhna obsolete kar diya.

---

## 📝 Hinglish Explanation (Detailed)

- **Lab mein wapas — apne server ke parameters:** Pichle lecture mein jo `accounts_server.py` likha tha, ab uske liye **parameters** set karte hain. Command hai **`uv run accounts_server.py`** — exactly wahi jo tum command line pe type karte. Run hone par ye **FastMCP** server banata hai, `run()` call karta hai, aur kuch functions **`@mcp.tool()`** se decorated hain.

- **Step 1 — tools discovery:** Agents SDK ka **`MCPServerStdio`** context manager use karo, parameters pass karo (**timeout yaad rakhna!**), aur **`server.list_tools()`** call karo. Behind the scenes: ek **MCP client** banta hai → woh `uv run` command se hamara **MCP server spawn** karta hai → poochta hai "kaunse tools hain?" → print.
  - **1.4 seconds** mein result aa gaya — wahi decorated functions dikhe: **get_balance, get_holdings, buy_shares, sell_shares, change_strategy, is available**. Ed: *"It's not super easy, but it's also pretty easy."*

- **Step 2 — agent ke saath action:** Instructions: *"You're able to manage an account for a client and answer questions about the account."* Query: *"My name is Ed. My account is under the name Ed. What is my balance and my holdings?"* Latest model ke saath.
  - Same construct: `MCPServerStdio` + params + **`client_session_timeout=30`** → agent ko instructions + model do → run karo.
  - **Result:** *"Your current cash balance is 8000. Your holdings include six shares of Amazon."* — yaani hamara apna MCP server successfully call hua, jo hamari **business logic** call karta hai. 🎉

- **Ab manual MCP client — but pehle ek confession:** Aaj kal **MCP client khud likhna common task NAHI hai**. Ed ki story:
  - Jab Ed ne ye lab shuru kiya, **OpenAI Agents SDK natively MCP support nahi karta tha** — tumhe apna client likhna padta tha aur tools manually SDK mein feed karne padte the.
  - Jis din Ed ne project finish karke **GitHub pe push** kiya, **usi din 2-3 ghante baad** OpenAI ne SDK update release kiya jisne sab simplify kar diya — Ed ka saara code **useless** ho gaya! (Git timestamps check kar lo agar yakeen na ho.) Ed infuriated tha, but ye achhi cheez hai.
  - Ab bas **context manager construct** se SDK automatically client bana deta hai.
  - **Lekin:** ye free wala construct sirf **tools** ke liye hai — **resources** use karne ke liye **abhi bhi apna client likhna padta hai**. Plus, plumbing samajhna ek **great exercise** hai.

- **`accounts_client` module — manual client ka anatomy:**
  - **Top pe params:** wahi launch parameters jo server spawn karenge. Ye **configurable** banaya ja sakta hai (ek generic MCP client jo config leta hai), but abhi ye fixed client hai sirf accounts server ke liye.
  - **List tools function:** **Anthropic ka (MCP SDK) code** use hota hai — context managers se **session** manage karo, session **initialize** karo, phir `list_tools()` call karke tools return karo. Pure plumbing.
  - **Call tool function:** ek tool ko actually invoke karna.
  - **Read resource functions:** do functions jo dono **resources** read karte hain — resource ka naam specify karke.

- **Types — MCP tool vs OpenAI tool format:** MCP jo tools return karta hai woh **Week 1 wale standard JSON tool format jaisa hai, but identical NAHI** — kuch slight differences hain. Isliye apna client likhte waqt tumhe **MCP tool description → LLM-style JSON tool description** ka **mapping** likhna padta hai. Ed ne ye function "painstakingly" likha — aur ab ye sab **OpenAI Agents SDK mein free** packaged aata hai.

- **Manual client ko run karna:**
  - `list_account_tools()` call karo → server spawn → **MCP tools** wapas aate hain.
  - Phir mapping function se unhe **OpenAI function tools** mein **reconstitute** karo — bilkul waise jaise koi function `@function_tool` se decorate kiya ho.
  - Dono side by side print: upar raw **MCP tools** (descriptions + arguments), neeche wahi **function tools** ke roop mein.
  - Phir purane style mein agent ko **tools directly pass** karo (servers nahi). Trace + instructions + tools → run.
  - **Result:** "What's my balance?" ka jawab aa gaya. **Layers ka recap:** function tools → wrappers around MCP tools → MCP client → MCP server spawn → business logic → result wapas LLM tak. Kaafi kuch chal raha tha behind the scenes!

- **Resources example — yahan manual client zaroori hai:** `read_accounts_resource` client function se resource **"ed"** read karo → account ki **description/report** wapas aati hai. SDK ye free mein nahi deta.
  - **Comparison:** business logic ko **directly import** karke `report()` function call karo — **exactly same answer**.
  - **To phir wrap kyun karein?** Agar tum ye resource **dusron ke saath share** karna chahte ho — sabko ek **simple, streamlined access** mil jaata hai bina tumhari business logic ke internals samjhe.

- **Exercises (homework):**
  1. **Simple:** ek MCP server likho jo **current date** bataye, tool ke roop mein expose karo, OpenAI agent ko equip karo.
  2. **Harder:** us server ke liye **apna MCP client bhi** banao (accounts_client vs accounts_server wala approach copy karo).
  3. **Bare metal:** Week 1 jaisi **native LLM call** likho JSON tool ke saath — LLM + MCP client + MCP server, saare nuts and bolts khud. Sirf direct exposure ke liye — day-to-day mein kabhi nahi karna padega.
  - **Honest caveat:** current-date tool real world mein **achha tool nahi hai** — agar agent ko date chahiye to **prompt mein hi likh do**, taaki model ko extra tool-call ka kaam na karna pade. Isliye kuch zyada interesting banao — jaise **calculator** jo do inputs pe operation kare.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **`uv run accounts_server.py`** | Hamare custom MCP server ko spawn karne wali command — yahi parameters mein jaati hai |
| **`MCPServerStdio`** | Agents SDK ka context manager — client banata hai, server spawn karta hai, sab automatic |
| **`client_session_timeout`** | Default 5s flaky hai — 30s pass karo (Ed ka standard pro-tip) |
| **`list_tools()`** | Server se tools ka menu poochna — decorated functions schema ke saath wapas aate hain |
| **MCP Client (manual)** | Khud likha hua client — session initialize, tools list/call, resources read — ab mostly sirf seekhne ke liye |
| **Session** | Client-server ke beech ki initialized connection — Anthropic ke MCP SDK ke context managers se manage hoti hai |
| **MCP tool → OpenAI tool mapping** | MCP ka tool format standard LLM JSON tool format se *thoda* alag hai — manual client mein ye translation khud likhni padti hai |
| **Function tools (reconstituted)** | MCP tools ko OpenAI `function_tool` objects mein convert karke agent ko directly pass karna — purana (pre-SDK-support) tarika |
| **Resources** | MCP ka read-only data channel — **iske liye aaj bhi manual client chahiye**, SDK free mein nahi deta |
| **`report()` / resource "ed"** | Account ki description — resource se bhi milti hai aur business logic directly call karke bhi (same answer) |
| **Resource wrap karne ki wajah** | Sharing — dusre log streamlined tarike se data access karein bina tumhari logic ke internals jaane |
| **Current-date tool anti-pattern** | Date prompt mein daalna better hai — tool-call ka extra round-trip avoid hota hai |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **MCP-tool → OpenAI-tool mapping = schema transcoding layer.** Jaise gRPC-REST transcoding ya OpenAPI spec se internal DTO banana — dono taraf JSON Schema hai but dialects slightly alag. Ed ka "painstakingly written" mapper exactly woh adapter hai jo har integration framework eventually absorb kar leta hai — aur SDK ne kar bhi liya. Lesson: **protocol pe build karo, glue pe nahi** — glue code ka shelf life ghanton mein measure hota hai (Ed ka literally 2-3 ghante tha).
- **Manual client likhna = ORM ke neeche raw SQL dekhna.** `MCPServerStdio` jo magic karta hai — session initialize, JSON-RPC handshake, tool listing, format translation — woh sab `accounts_client` mein exposed hai. Production mein kabhi nahi likhoge, but debugging ke waqt (timeout? handshake fail? schema mismatch?) ye mental model hi kaam aayega — waise hi jaise FastAPI debug karte waqt WSGI/ASGI samajh kaam aati hai.
- **Resources via client = read-only endpoint expose karna vs DB access dena.** `report()` directly import karke bhi same answer milta hai — to MCP resource ka point kya? Wahi jo internal API ka hota hai: **stable contract**. Consumers ko tumhari business logic ke internals nahi jaanne padte — REST mein GET endpoint, MCP mein resource. Note: tools ke liye SDK sab karta hai, resources ke liye abhi bhi haath se client chahiye — protocol framework se aage hai yahan.
- **Hands-on lab:** is lecture ka code khud chalane ke liye `Practical/lab2_custom_accounts_server.py` run karo (is repo mein, `uv run` se chalta hai, Groq pe free). Ek difference: lecture OpenAI ka latest model use karta hai aur manual `accounts_client` walkthrough karta hai — hamara lab Python **FastMCP** servers (`servers/` folder) + SDK-route pe focus karta hai aur upar se `output/accounts.json` disk pe padhke **state verify** karta hai (LLM ki baaton pe nahi, side-effects pe bharosa).

---

## 🧠 Takeaway (yaad rakho)

1. **Apna MCP server use karna = 2 steps:** params (`uv run accounts_server.py`) + `MCPServerStdio` context manager — `list_tools()` se decorated functions dikhe, agent ne balance + 6 Amazon shares bata diye.
2. **MCP client khud likhna ab zaroori NAHI** — Agents SDK sab free deta hai. Ed ka manual client release ke 2-3 ghante baad hi obsolete ho gaya tha — frameworks glue code kha jaate hain.
3. **Exception: resources.** Tools SDK se free milte hain, but resources read karne ke liye aaj bhi manual client (session + read_resource) likhna padta hai.
4. **MCP tool format ≠ LLM JSON tool format** — similar but not identical; manual client mein ye mapping khud likhni padti hai, SDK mein free hai.
5. **Date-tool anti-pattern yaad rakho:** jo cheez har turn chahiye (jaise current date), woh prompt mein do — tool mat banao. Exercise ke liye calculator jaisa kuch meaningful banao.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

So here we are back in the lab. And what we're looking at here are parameters being set for our very own MCP server that we just wrote. So the command is uv run because that's exactly what we would type at a command line to run this module. uv run accounts_server.py. Just run the accounts_server.py that I just showed you. And we know that when that's called it's going to create an MCP server, a FastMCP. It's going to call run. And that we've got some functions decorated as MCP tools. All right. So then we use the OpenAI Agents SDK context manager with MCPServerStdio. And we pass in those parameters. Remember this timeout. And we then are going to call server list tools. So just by running this what's going to happen. It's going to create an MCP client. It's then going to spawn our MCP server by carrying out this instruction right here. And it's then going to ask it, what tools do you offer us? And we'll print them out. And we're hoping to see the things that we decorated. Uh, let's see if this works. Can it be that simple? Off it goes. Took 1.4 seconds. Let's just print that. And there we go. These are the functions that we just decorated. Get balance, get holdings. Buy shares. Sell shares. Change strategy. It's available. Wow. Um, so as you can see, it's not super easy, but it's also it's pretty easy.

Okay, let's try and put this to action. Let's have some instructions. You're able to manage an account for a client and answer questions about the account. My name is Ed. My account is under the name Ed. What is my balance and my holdings? So it's going to need to make use of these tools. And we'll give it the latest model. Why not. Uh, let's take that. And now this again is the same code as before. We use the context manager with MCPServerStdio. We pass in our parameters. Let's put in that timeout client session timeout is 30. Um, and uh, we will pass in our instructions, our model, and we will then run a run and display the output. We're hoping that it's going to spawn the server, call the tools and be able to tell me about my six Amazon shares, uh, and the balance and everything like that. So enter your current cash balance is 8000. Your holdings includes six shares of Amazon. If you need any further details then let me know. So that is us successfully calling our very own MCP server that then calls our business logic.

And now it's time to show you what it's like to write an MCP client. But I should first explain that it's not a common task to write an MCP client. You don't really need to do it anymore. When I when I first started working on this lab, the way that you worked with OpenAI Agents SDK, they didn't sort of natively support MCP. You had to write your own client and then provide the tools into OpenAI Agents SDK. And it was the day that I finished this project and checked it into GitHub and did the push that same day, about about 2 or 3 hours later, they released an update to OpenAI SDK that simplified everything and meant that all my code was useless. And you can, you can, you can look at the git timestamps if you don't believe me. It was crazy. I was I was infuriated, but it is a great thing. And basically it means that just with this, this context manager construct, you automatically get, uh, OpenAI SDK creating the client for you.

But anyway, it's a good exercise to show you what it's like to make a client. And also this this construct works for tools. But if you want to use resources, I think you still need to write a client. And it's not so common. But but but we'll do it anyway and you'll see how it works.

Okay. So this is in a Python module called accounts_client. And this this is where the magic happens. That is no longer needed really. Uh. So this is this is a this is an MCP client for use with my accounts MCP server. So at the top here I specify these are the parameters that will be used to launch the MCP server. Now this could be something configurable. You could make a sort of generic MCP client that takes this as configuration and then and then spawns it. But for now this is just a fixed client for our accounts MCP server. And so this is an accounts MCP client.

And so there are a few things we need to be able to do. We need to be able to list the tools. And so this first function here is an example of the function that lists tools. And we're basically using a bunch of Anthropic code here for our client. And you can see that there's some context managers that we manage a session. We initialize the session. And then we call list tools on the session and return the tools. And so it's just sort of plumbing stuff that that you need to know about. If you want to write something that will contact your server and list the tools. This second one is actually calling a tool. This is how you go about reading a one of the resources, and this is reading the other resources. You can see I specify the resource name right there.

Um, and then finally the types. The way that MCP returns tools is very similar to the JSON, the standard JSON that you use when you call a tool, as we did in week one. But it's not identical. There is some couple of slight differences. So if you're writing your own MCP client, you also have to know how to map between the MCP description of a tool and the kind of JSON description of a tool that's used generally when you're calling LLMs. And that is what this this function here does that I painstakingly wrote. But all of this comes for free packaged in OpenAI Agents SDK. So you don't need to do all of this, but you could look through it should you be interested and should you want to understand what does it mean to have your own MCP client?

Okay, so now it remains for us to actually run the MCP client that we just created. So I import from that module. We just looked at some of the functions we just saw. And the first function I call is the list account tools function, which is the one that's going to spawn an MCP server and ask it for its tools that will come back as MCP tools. I'm then going to call the other function I showed you, where I take the MCP tools, and I reconstitute them as OpenAI tools. I turn them into these function tools, just as if I'd had a function and decorated it with function tools. Same thing. And then I'm going to print that. So I'll print these two separately so you can see the results side by side. So this first line here, this is the actual MCP tools themselves with their description, the arguments of all the tools. And you can take a look at them should you wish. And underneath it is the same thing but reconstituted as a function tool, which is the kind of object that needs to be passed in to OpenAI.

And indeed, that's what I'm going to do right here. So this is the way you had to do it before OpenAI built this, so that you can now you can just pass in the MCP servers. You don't have to build a client and do all of this stuff. But before that, in fact, very recently this was the way to do it. You'd actually have to pass in the tools themselves. So we've used our MCP client to find the tools and then we're passing them in here. So as I say, you just follow along for interest to see what this is doing. But it's not like you'd need to do this yourself. So as always, I've got a trace, and then I'll pass in my instructions and I will pass in the tools that when these tools are called, it's actually going to call the MCP client. That's going to call the MCP server that's going to actually run our business logic. Okay. So now we're going to run our MCP client like this. So we're passing in the tools we are calling the model and it has now responded. I asked what's my balance? And it's responded with the balance. And so just as a recap, what's going on there, we provided it with some tools right here. Those tools are in fact wrappers around MCP tools, which actually created an MCP client which launched our MCP server and which ran our function through the business logic on the MCP server and got back the results to the LLM. So quite a lot was going on there behind the scenes with this. And as I say, you really shouldn't need to do this yourself because OpenAI Agents SDK does it all for you. But it's useful to see how the plumbing works behind the scenes.

Now here's another example of using the MCP client. This time we're using this read accounts resource client function that I wrote. And I think that you do need to do it this way. If you want to use resources, then that doesn't come for free with the OpenAI Agents SDK package. So this is an example of reading the resource called ed. So let's see what happens if we run that. Let's run it through our client, through our server. And that's what comes back. This is a description of my account. And just to show you, I could also, of course, just import the business logic directly. And this is ending up just calling this function report. So this should give exactly the same answer. You could see the same stuff. So essentially what we've done is we've taken this piece of business logic. We've wrapped it in an MCP server to be available at a certain resource. We've written an MCP client that allows you to expose that resource. And that is what this function is. And so you can call this MCP client to get this. You could also just call the business logic directly. Um, and so why would you want to do this. Again it's if you wanted to share this resource with other people, it gives everyone a simple, streamlined way to access your resources rather than having to understand how your business logic works.

Okay, that wraps up creating MCP servers and MCP clients with most of the emphasis on the servers. And I would now like to give you an exercise to go and create your own. So one super simple one to do would be to write an MCP server that can tell you the current date, give the current date, and you can expose it as a tool that you can equip OpenAI agent with so that it can find out the current date. And it can make sure that what it's the the content and the questions it's answering, it's doing so mindful of what the current date is.

Um, and uh, yeah. Then then as a harder exercise, you could not only build that MCP server, but also build an MCP client to accompany it. Taking a look at exactly how I just did that for the accounts client compared with the accounts server, same approach. And then you could actually write something that looks like a native call to OpenAI, as we did in week one, like a simple native call with a tool as a JSON. And then you're getting really bare metal and you're seeing how you can call an LLM and have an MCP client and an MCP server where you're writing all the nuts and bolts. The only real use of that is to give you some direct exposure to it. So only do that if you're if you're interested. You won't have to do that day to day. But but it's a it's an interesting exercise.

It's also worth pointing out that actually answering the current date isn't a great tool isn't super useful in the real world, because if you need to tell your agent about the current date, it's better just to state it in the prompt so that it always has it available so that the model doesn't have to go through the extra work of knowing to call your tool to collect the date. So if you feel like it, try make some more interesting tools. Have a shot at making a calculator that can do some calculation operation on two inputs or something like that. So. So try and make some interesting tool that appeals to you, and then write an MCP server and perhaps also explore writing an MCP client should you wish and enjoy that. And we will then go over to wrap up for today.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
