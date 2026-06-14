# L93 — Day 1: AutoGen Agent Chat — Tools & Database

> **Week 5 — AutoGen** · ⏱️ ~10m · 🎥 Lecture 93 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821589

---

## 🎯 Ek Line Mein (TL;DR)

**AutoGen AgentChat** ke 4 core building blocks — **model client**, **TextMessage**, **AssistantAgent**, aur **on_messages()** — sirf 10 minute me cover, plus killer feature: **plain Python function ko directly tool bana do** (no decorator!) jo ek **SQLite database** se ticket prices query karta hai.

---

## 📝 Hinglish Explanation (Detailed)

- Week 5 ka pehla lab shuru — **AutoGen AgentChat**, jo AutoGen ka main/high-level part hai. Ye **CrewAI** aur **OpenAI Agents SDK** jaisa hi feel karega, kaafi consistent API. Aur hamesha ki tarah pehla step: **`load_dotenv()`** se env load karna.

- **Concept 1 — Model (model client):** Ye LLM ke around ek **wrapper** hai, bilkul waise jaise dusre frameworks me `LLM` concept tha. Import karte hain **`OpenAIChatCompletionClient`** aur bas model ka naam pass karte hain — yaha **GPT-4o mini**. Ed dikhata hai ki same idea se **ollama** ke through **local model (llama 3.2)** bhi chala sakte ho — baaki sab code bilkul same chalega, sirf client badal do. (Swappable backend — clean abstraction.)

- **Concept 2 — Message:** Ye AgentChat ka ek **alag/naya concept** hai. Tum ek **`TextMessage`** object banate ho jisme **`content`** ("I'd like to go to London") aur **`source`** ("user" — yaani main) hota hai. Print karo to dikhega: text message, source user, content. Bas — itna hi hai message.

- **Concept 3 — Agent:** Import hota hai **`AssistantAgent`** — AgentChat ka **sabse fundamental class**, ye baar-baar dikhega. Instance banate waqt dete hain:
  - **`name`** — e.g. "airline_agent"
  - **`model_client`** — underlying LLM wrapper
  - **`system_message`** — OpenAI SDK ke `instructions` jaisa: "You are a helpful assistant for an airline. You give a short humorous answer."
  - **`model_client_stream`** — results ko **stream** karne ke liye flag.

- **Concept 4 — `on_messages()` (sab kuch jodne wala glue):** Agent pe **`on_messages()`** call karte ho, messages ki **list** pass karte ho (humara single TextMessage list me), saath me ek **`CancellationToken`** — ye thoda *fiddly* cheez hai jisse framework ko pata chalta hai ki agent kab complete hua; Ed bolta hai zyada worry mat karo, bas pass kar do. Ye **async coroutine** hai, isliye **`await`** karna padta hai. Phir `result.chat_message.content` print karte hain.

- Output: *"Great choice. Just remember, if it starts raining, it's not a sign to panic. It's just London welcoming you!"* — humorous answer mil gaya. Ed point karta hai ki ye **OpenAI Agents SDK jaisa hi "lightweight abstraction" moment** hai — koi heaviness nahi, bas LLM calls ke around halka-sa wrapper.

- **Ab tools ka time — "it's always about tools":** Ek tool banayenge jo **ticket prices** lookup kare, aur agent ko arm karenge **SQLite database** query karne ki ability se. Note: sophisticated approach ye hoti ki agent khud **SQL likhe** (SQL-writing tool), lekin yaha simple lookup tool kaafi hai.

- **Database setup:** `sqlite3` import karo → purana `tickets.db` delete karo (re-run safety) → naya DB connect → **`cities` table** banao (city name + **round trip price**) → London, Paris, Rome, Madrid, Barcelona, Berlin ke tickets se populate karo.

- **Tool function — `get_city_price(city_name)`:** DB se connect, ek chhota **SELECT** statement city name pass karke, result return. Ed khud maanta hai: security-conscious log bolenge **input validation** karna chahiye (SQL injection waale concerns) — lekin ye **toy example** hai. Test: London → **299**, Rome → **499**. Kaam kar raha hai.

- **Smart agent (tool-armed):** Naya `AssistantAgent` — "smart_agent" — same client, same LLM, system message me add kiya ki uske paas round trip ticket lookup ki ability hai. Do nayi cheezein:
  - **`tools=[get_city_price]`** — bas **plain Python function directly pass** kar di!
  - **`reflect_on_tool_use=True`** — matlab tool ka raw result hi return mat karo; tool return hone ke **baad bhi LLM processing continue** kare jab tak final reply na de. Ed: *"rare hai ki tum ise False chahoge — practically default True maan lo."*

- **AutoGen ka chhota sa superiority point:** Dusre frameworks me tool ke liye **decorator** chahiye tha (OpenAI Agents SDK ka `@function_tool`) ya wrapper (LangGraph me tool me wrap karna). AutoGen me **kuch nahi** — abstraction code khud Python function ko dekhta hai, **docstring/comment se tool ka description** nikal leta hai. Learning curve thoda aur kam — "really nice".

- **Run + inner messages:** `smart_agent.on_messages([...])` same message ke saath ("I want to go to London"). Ed **`inner_messages`** bhi print karta hai — kyunki message construct sirf human→agent ke liye nahi hai, **agents ke beech aur agent ke andar** bhi messages flow karte hain. Output me dikha:
  1. **Function call** (inner message): `get_city_price(city_name="London")`
  2. **Tool result**: 299
  3. **Final response**: *"Ah, the city of tea and top hats! A round trip ticket to London will set you back $299..."*

- **Closing point:** Asli baat humorous answer nahi — asli baat ye ki **SQL-backed tool likhna itna simple tha**, aur ye bhi ki ab ye patterns tumhe itne familiar lag rahe hain ki **10 minute se kam me tum AgentChat ke expert** ban gaye.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **AutoGen AgentChat** | AutoGen ka main high-level layer — CrewAI/OpenAI Agents SDK jaisa agent framework |
| **`OpenAIChatCompletionClient`** | LLM ke around wrapper ("model client") — model ka naam pass karo, ready |
| **Model client** | LLM concept ka AutoGen version — swappable (GPT-4o mini ya ollama llama 3.2) |
| **`TextMessage`** | AgentChat ka message object — `content` + `source` (kaun bhej raha hai) |
| **`AssistantAgent`** | AgentChat ka sabse fundamental agent class — name, model_client, system_message |
| **`system_message`** | Agent ka persona/instructions — OpenAI SDK ke `instructions` jaisa |
| **`model_client_stream`** | Flag jo results ko stream back karwata hai |
| **`on_messages()`** | Agent ko messages ki list pass karne ka async call — `await` karna padta hai |
| **`CancellationToken`** | Fiddly-sa object jisse framework ko pata chalta hai agent kab complete hua |
| **Plain-function tools** | Python function **directly** `tools=[]` me pass — no decorator, docstring se description |
| **`reflect_on_tool_use=True`** | Tool result ke baad LLM aage process kare aur final answer de — practically default |
| **`inner_messages`** | Agent ke andar ke messages — function calls, tool results — debug/inspect ke liye |
| **SQLite tool** | `get_city_price` — DB me SELECT chala ke round trip price return karta hai |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Plain-function tools = reflection-based auto-registration.** Jaise FastAPI type hints + docstrings se OpenAPI spec generate karta hai, waise hi AutoGen function signature + docstring se **tool JSON schema** infer kar leta hai — decorator ki zaroorat hi nahi. OpenAI SDK ka `@function_tool` aur LangChain ka `@tool` wahi kaam explicit wrapper se karte hain.
- **`reflect_on_tool_use=True`** ko ek **post-processing middleware** ki tarah socho: tool ka raw DB result user ko nahi dikhana, LLM se usse final response banwana hai. False matlab tool output as-is return — bahut kam cases me chahiye.
- **`CancellationToken`** tumhe asyncio/gRPC se familiar lagega — cooperative cancellation ka standard pattern (C# devs ka `CancellationToken` literally same naam). Yaha framework completion-signalling ke liye use karta hai.
- Ed ka `get_city_price` me string-interpolated lookup wala disclaimer serious hai — production me **parameterized queries** mandatory, kyunki ab **LLM tumhare SQL tool ka input control kar raha hai** (prompt injection → SQL injection chain possible).
- **Hands-on lab:** is lecture ka code khud chalane ke liye `Practical/lab1_agentchat_basics.py` run karo (is repo me, `uv run` se chalta hai, **Groq pe free** via `OpenAIChatCompletionClient` + `base_url` + `ModelInfo`). Difference: hum **AutoGen 0.7.5** use karte hain (course 0.5.1, same API family) aur GPT-4o mini ki jagah Groq ka free model — baaki TextMessage/AssistantAgent/SQLite-tool flow bilkul same.

---

## 🧠 Takeaway (yaad rakho)

1. AgentChat ke **4 core concepts**: model client (`OpenAIChatCompletionClient`) → message (`TextMessage` with content+source) → agent (`AssistantAgent`) → execution (`await agent.on_messages([...], CancellationToken())`).
2. **Tools = plain Python functions** — koi decorator/wrapper nahi; docstring se description auto-pick hota hai. Ye AutoGen ka chhota sa edge hai dusre frameworks pe.
3. **`reflect_on_tool_use=True` hamesha rakho** — tool result ke baad LLM final natural-language answer banata hai.
4. **`inner_messages`** se agent ke andar ka flow dikh jata hai: function call → tool result → final response.
5. Model client **swappable** hai — same code GPT-4o mini ya ollama (llama 3.2) local, dono pe chalta hai.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

And welcome back to Cursor and welcome to week five directory. Here we go. We're going to the first lab. Week five day one Autogen Agent Chat, which is the main part of Autogen. That's sort of comparable with, say, Crew. And a lot of what we do right now is going to look very familiar because it's very consistent with Crew and OpenAI Agents SDK, particularly this first thing which we always do, which is to load the env as usual.

All right. So the first concept then is the model. And the model which is similar to concepts like LLM that we've had before. It's like a wrapper around calling a large language model. And here we import something called OpenAIChatCompletionClient, which is the wrapper for for the LLM we'll be using, which is GPT-4o mini. And this is how you create your model client as it's called. And it's very simple indeed. And you just pass in the name of your model. And so let's run that. And also I just want to show you here that you could do the same thing with ollama to run a local model like llama 3.2. It's just exactly the same idea. You could run that and you could continue all of this in exactly the same way, running locally instead of using GPT-4o mini. Okay, that is the first concept.

The second concept is the message. This is something which is a different concept for Autogen agent chat. It's this idea that you create an object called TextMessage. In this case that has the content. I'd like to go to London is my message right now. And the source is the user me. And so if we run that and print it, we see it's a text message. The source is the user. And the, uh, there's the content. And now that is all there is to it. That is the message.

The third concept is the agent. And it's very similar to things we've seen in the past. The the thing that we import is called AssistantAgent. That is the uh, you'll see this many times. This is the kind of most, the most fundamental class that will work with in in Autogen agent chat. So we create a new instance of AssistantAgent. We give it a name, airline agent, we give it a model client, the underlying LLM, we give it a system message rather like the instructions in OpenAI. You are a helpful assistant for an airline. You give a short humorous answer. So let's give it that to see what that does to it. Uh, and uh, model client stream is how we say that we want it to stream back the results. Uh, and so it's something that we've, we've already done from time to time, but that is an agent that has been created.

And then the thing that brings it all together is something called on_messages. That is what we call on an agent to pass in a bunch of messages, which we do right here. We just put our single message in a list. We pass that into on messages. You also have to pass in this thing called CancellationToken, which is how it knows when the messages are finished. That's a sort of fiddly thing about about agent chat, but but I wouldn't worry about it. You just call, uh. And of course it's an async. It's a coroutine, so we have to await it. Await agent on messages pass in the list. You pass in this cancellation token, which is how the framework is going to know when this agent is completed. And then I'm going to print the chat message content. So we're passing in this message. Um, the messages I'd like to go to London and the assistant is, uh, your helpful assistant for an airline. You give short, humorous answers. Let's see what happens if we do this. Great choice. Just remember, if it starts raining, it's not a sign to panic. It's just London welcoming you. Ha! A nice humorous answer, of course, from our agent, and it's worth pointing out that we're having a same kind of moment as with, uh, OpenAI Agents SDK. It's so easy to do this, to package it up and to make this call. It's really a nice, lightweight abstraction. There's not a lot of heaviness to this, just a lightweight abstraction around calling LLMs.

Well, let's take that a little bit further. Let's of course we have to bring in tools. It's always about tools. Let's bring in a tool, do something more interesting right now. Now we're going to make a tool that's going to get ticket prices. And we're going to arm our agent with the ability to look up ticket prices. And we might as well use like a SQLite database because people often like to think, say, say, okay, what would it be like if we had, uh, our agents being able to query the database? Now, there's there's sophisticated ways of doing it to actually write a SQL tool that gives agents the ability to write SQL. But in this case, it's perfectly simple. We can just write a tool that can just look up in the database. So let's do that right now.

So we're going to import sqlite3. We're going to create and we're going to delete tickets database if it already exists because we ran this before. And then once it's been deleted, we will then connect to a new database and create a table called cities, which has a city name and a round trip price. And uh, people that are familiar with this will know perfectly well that it's created a DB database that will now be empty. And we are going to populate our database with a bunch of tickets for to London, Paris, Rome, Madrid, Barcelona and Berlin. And that's been done. And we're going to write a simple query function get city price that takes a name, and it will get the round trip price to travel to the city. It will simply connect to the database and it will run a little select statement passing in the city name and return the result. And yes, for security conscious people, there's perhaps more things that I should do to make sure to validate this and make sure the city name is a city name and all the rest of it. But this is just a toy example for now. So we run this. We've got get city price. Let's just check it out. Let's try get city price for London. It's populated in the database. We get back 299. Let's do Rome and we get back 499. That does appear to be working.

And now check this out. This is the same as before. This, uh, creating an assistant agent. I'm calling it smart agent now because it's going to be smarter than before. Uh, otherwise that's the same. This is the same. We're passing in the same underlying client, the same underlying LLM the system message. Uh, I have actually added in, but I'm not sure if it's necessary to tell it that it has the ability to look for a round trip ticket. Um, we're streaming again. We're passing in this function as one of our tools in here. And there's also this slightly curious attribute reflect_on_tool_use, uh, which is a way of indicating that we don't just want it to return the tools results. We do want it to be able to take that and continue processing even after the tool has returned. True. We we continue until it replies. So that's like it's rare that you wouldn't want that to be true. So you should always assume that that will be your default, I think. Um, and that's I'm not thinking of something obvious.

So, so this is the way we do it. And there's something to point out here, which is a tiny difference from the other frameworks, a tiny way in which autogen maybe is a little bit better, a little bit superior, that you'll notice we're just passing in this Python function directly here. We didn't have any kind of decorator or anything. You remember in OpenAI Agents SDK, we had to put in a decorator. We've had to in things like LangGraph, you have to to, uh, wrap it in a, like a tool. We haven't had to do anything like that. It's, um, it's just really lightweight. And it's because, of course, they've just got a little bit of extra stuff in the abstraction code that sees this as a Python function. It uses this comment to figure out the description of the tool. So it just does a bit of that for you. It makes life a tiny bit easier. Removing some of the of the of the learning curve, which I think is really nice.

Um, so what we're now going to do is we're just simply going to call smart agent this guy on messages passing in our same message. I want to go to London. Um, and then just just for the for fun, I'm going to print the inner messages. I mentioned that the message construct isn't just for the human to the agent. It's also for what's going on between agents and inside the agent. So we can see that by printing its inner messages. And then we will print the result and let's run that. And this is what happens. So you can see first of all that there's been a function call. This was an inner message with city name set to London. And it's a get city price is the function call. Uh the results came back. The result was 299 and there we go. This is linked back to there, as you would hope. And then this is the final response from the model are the city of tea and top hats. A round trip ticket to London will set you back 299. Just remember, the only thing you should pack is your sense of humor, because the weather might require it. Very droll. There we go.

Uh, so, uh. Great. Great answer. But of course, more important than the great answer is the fact that it was so simple to write that tool, to have it make a SQL call to a database. That's right. Sitting right there. Uh, and to have that run use the tool, um, and it just shows, uh, first of all, um, how quick and simple agent chat is, but secondly, how good you're getting at understanding this stuff because honestly, this is so familiar to you now that this is just in a less than ten minutes, you're already an expert at agent chat.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
