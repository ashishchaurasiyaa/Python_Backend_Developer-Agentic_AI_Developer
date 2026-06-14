# L17 — Day 4: Resources vs. Tools — Two Ways to Enhance LLM Capabilities in Agentic AI

> **Week 1 — Foundations** · ⏱️ ~8 min · 🎥 Lecture 17 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49771189

---

## 🎯 Ek Line Mein (TL;DR)

LLM ko powerful banane ke **2 tarike** — **Resources** (prompt mein extra relevant context/data daalna, jiska fancy version **RAG** hai) aur **Tools** (LLM ko actions perform karne ki "power" dena) — aur tool calling ka **asli secret**: koi magic nahi, bas **JSON responses + if statements**.

---

## 📝 Hinglish Explanation (Detailed)

- **Resources = extra context in the prompt**
  - Resources matlab LLM ki effectiveness badhana usse **zyada context / zyada information** dekar — taaki uski "expertise" improve ho.
  - Mechanism bilkul simple hai: question se **relevant data utha kar prompt mein shove kar do**.
  - Example: aap ek **airline customer support agent** bana rahe ho → prompt mein saare **ticket prices** daal do. Ab LLM answer dete waqt us info ko refer kar sakta hai. Bas — yahi resource hai.
  - **Thoda fancy version:** saare ticket prices daalne ki jagah, sirf **us question ke relevant** prices daalo. "Sabse relevant context kaise dhundhein" ke clever tricks (kabhi-kabhi dusre LLMs ki madad se) — ye poora field hai **RAG (Retrieval Augmented Generation)**.
    - RAG ek **super hot topic** hai, Ed ke dusre course mein covered hai — is course ke liye deep dive zaroori nahi, par concept "resources" ke under hi aata hai.
  - Aaj ke lab mein hum **resources hi use karenge**.
- **Tools = LLM ko actions ki power dena (agentic AI ka heart)**
  - Tool = LLM ko **kuch karne ki ability** dena, aur wo us tool ko **apne discretion par** use kar sakta hai → yahi **autonomy** dene ki key trick hai.
  - Examples: database par **SQL query** chalana, dusre LLM ko message bhejna, calculator, ya Ed ke piche wali **lights on/off** karna.
  - Pehli baar sunne par creepy lagta hai: "Cloud par baitha OpenAI ka model **mere computer se connect** hokar **meri database query** karega?!" — sounds crazy.
- **Reality check: tool calling ek "conjuring trick" hai (magic nahi)**
  - **Theory:** aapka code LLM (e.g. GPT-4o mini on cloud) ko prompt bhejta hai, LLM ko tool execute karne ki ability di gayi hai, aur wo uske basis par response deta hai.
  - **Practice (asli mechanism):** prompt mein aap LLM ko bolte ho — *"ye kuch actions hain jo main tumhare behalf par kar sakta hoon (e.g. `turn_on_lights`). Agar tumhe koi chahiye, to **JSON mein reply karo** batate hue kaunsa action chahiye. Main wo karke result ke saath wapas aaunga."*
  - Yani prompt mein **available tools ki list** + "respond in JSON" ka instruction — bas itna hi.
  - SDK ka **tool calling code ye sab package** kar deta hai, isliye aapko JSON plumbing dikhti nahi — par andar yahi ho raha hai.
  - Phir aapke code mein ek **if statement** (ya dispatch logic): *"agar LLM ko X chahiye → X chalao → result ke saath **LLM ko dobara call karo**"*. That's it.
- **Concrete demo (Ed ka ChatGPT conversation):**
  - System-style prompt: *"You're a support agent for an airline... You have the ability to query ticket prices. Just respond: 'Use tool to fetch ticket price for <city>'."*
  - User: *"I'd like to go to Paris. How much is a flight?"*
  - GPT-4 ka reply: **"Use tool to fetch ticket price for Paris."** — bas, yahi tool use hai!
  - Aap price fetch karke **second call** mein answer include karte ho → final response milta hai.
- **Interpretation:** hum ChatGPT ko **autonomy de rahe hain** ki wo khud decide kare tool use karna hai ya nahi — sounds mystical, par end of the day it's **JSON and if statements**.
- **Lab plan:** aaj **tools NAHI** banayenge (bad news 😄) — aaj **resources** ka lab hai, jo kal ke **tool use lab** ka setup karega.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Resources** | Prompt mein extra relevant data/context daalna taaki LLM better expert ban jaye. |
| **RAG (Retrieval Augmented Generation)** | Sirf question-relevant context smartly retrieve karke prompt mein daalna — resources ka advanced/clever version. |
| **Tools** | LLM ko actions (SQL query, calculator, lights on/off) perform karne ki power dena, jo wo apni marzi se use kare. |
| **Tool/Function Calling** | Asli mechanism: prompt mein tools list karo → LLM JSON mein bole "ye tool chalao" → aap chalao → result ke saath dobara call karo. |
| **Autonomy** | LLM khud decide karta hai ki tool use karna hai ya nahi — agentic AI ki key trick. |
| **"JSON + if statements"** | Ed ka punchline: tool calling mein koi magic nahi — structured response + dispatch logic. |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Tool calling = RPC pattern ulta:** normally client server ko call karta hai; yahan LLM ek **"intent" (JSON payload)** return karta hai aur **aapka code hi executor** hai. LLM kabhi aapke system ko directly touch nahi karta — wo sirf ek structured request emit karta hai. Security model samajhne ke liye ye crucial hai.
- **"If statement" ko aap dispatch table samjho:** production code mein ye `dict[tool_name, callable]` + Pydantic se args validate karna hota hai — wahi pattern jo aap webhooks/command handlers mein use karte ho. Frameworks (OpenAI SDK, LangGraph) bas ye boilerplate hide karte hain.
- **Resources vs Tools = read vs write/execute:** Resources context injection hai (jaise request middleware mein user data attach karna), Tools side-effects hain. RAG essentially **query-time SELECT + prompt templating** hai — DB-backed API banane wale ke liye familiar territory.
- **Round-trip cost yaad rakho:** har tool call = **2+ LLM API calls** (intent → execute → final answer). Latency/cost budget karte waqt ye multiplier count karo, jaise N+1 queries count karte ho.

---

## 🧠 Takeaway (yaad rakho)

1. **Resources** = prompt mein relevant extra context daalna; iska smart version **RAG** kehlata hai.
2. **Tools** = LLM ko actions ki power dena, **at its discretion** — yahi agentic AI ke heart mein hai.
3. Tool calling ka secret: LLM kuch execute **nahi** karta — wo **JSON mein bolta hai** "ye tool chalao", aapka code chalata hai, phir result ke saath **second LLM call** hoti hai.
4. "It's just **JSON and if statements**" — mystical nahi, pedestrian hai, par kaam zabardast karta hai.
5. Aaj ka lab **resources** par hai; **tools** kal ke lab mein aayenge.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Now I want to talk about resources. So resources are a way that you can get more out of your agents, that you can equip your agents to be able to solve your problems better, along with tools that will come to you in a second. And resources is really just a fancy way of saying that you can improve the effectiveness of an LLM by providing it with more context, more information to improve its expertise. And the way that you do that is just grab some relevant data to the question and shove it in the prompt. So it's just a matter of saying, like, if this is going to be a question that's going to be particularly — we're going to prompt the LLM to ask something about the company that we work at. Maybe it's to be a flight airline customer support agent. We could shove into the prompt all the information about ticket prices. And then when it's answering a question, it would be able to refer to any of that information as part of giving its answer. That would be an example of a resource. And so it's nothing more fancy than just saying we can just put extra context, extra information in the prompt we send an LLM, and think of that as a resource we're providing the LLM.

And when I say it's nothing more fancy than that, there is a bit more fancy than that. You can use clever techniques that will allow you to, rather than just shoving all the ticket prices, just put the ticket prices relevant to that question. So coming up with clever tricks for ways to figuring out the best, most relevant context — tricks perhaps that can even use other LLMs to help with that. That is all part of the whole field that's called RAG: Retrieval Augmented Generation. That's about retrieving relevant context. It is, of course, a super hot topic. It's covered on my other course. It's not relevant for this course particularly, but it's very interesting. But that whole side of things — figuring out how to pick relevant extra resource information to put in the prompt — falls under the heading of resources. And we'll be doing some of that today.

And with that, let's turn to the main topic of the day, which is tools. So tools. We've said it a few times now. It's clear that this is really at the heart of agentic AI. Tools is when you give an LLM the power to do something, to use a tool, and it really can use that tool at its discretion. And so it's one of the key tricks to giving an LLM some autonomy. So what does this actually mean? So we're going to give an LLM the power, the ability, to carry out different actions — like do a SQL query of a database or send a message to another LLM to do something.

So the first time that you heard about this — if you've heard about tools and function calling — it might sound like it's kind of crazy. It's sort of creepy. We're going to be interacting with OpenAI on a cloud, and we're going to say, hey, you have a tool you can use, you can query my database, and it's going to be able to, like, connect back to my computer and query the database as part of giving its response. That's what tools are all about. And it's like, okay, how exactly is it going to do that? Like, that sounds crazy. Well, the truth is actually rather more mundane. And people that know about tools know this already, but sadly it has a sense of being very magical. But the reality is a bit of a conjuring trick, as I will now show you.

So in theory, what's going on with tool calling? We've written some code. Our code is sending a prompt to an LLM, like OpenAI, like GPT-4o mini running on the cloud, and that LLM is being given the ability to execute a tool of some sort, which might be a SQL query, it might be a calculator, it might be a tool which turns on and off the lights that are stringing around me from the first episode. So that's the kind of thing that it's able to do. And based on that, it will give its response. So this is it in theory. The practice has just one tiny deviation from this, but it reveals everything.

This is what actually happens. You prompt the LLM and you say, you know, I want to turn on my lights or whatever. And you say, but I would like you to tell me if you want me to take care of a few actions that I can do on your behalf, and one of them is called "turn on the lights". And if you reply "turn on the lights", then I will do that and I will get back to you with "I turned on the lights". So basically, in the prompt to the LLM, you just list out everything that it's able to ask for, and you tell it to respond in JSON. And in that JSON response it should say what it wants to do. Now the tool calling code sort of packages all that away from me, so you don't need to worry about the fact that it's being called and responding in JSON. But that's what's really happening. It's all that's happening. It's really just clever stuff about getting JSON back from the LLM if it wants you to do something. And at the end of the day, you have to write an if statement in your code. You can be fancier than an if statement, but it's like an if statement that's like: if the LLM wants to do X, then do X, and then call the LLM a second time with the results. And so that's what it comes down to — asking the LLM if it wants to run a tool, and if so, then running the tool. So if you knew that already, then I'm just emphasizing what you already know. If you didn't know it, it might be a kind of aha moment when you realize that actually it's not that clever. It's pretty pedestrian, but it works, and it works really well.

And just to show you, just to make this concrete for you, check this out. Look at this conversation that I had with GPT-4. I said: you're a support agent for an airline. You answer users' questions. You have the ability to query ticket prices. Just respond "Use tool to fetch ticket price for London" to retrieve the ticket price for London, or for a city that you name. Here's the user question. User: I'd like to go to Paris. How much is a flight? And look at what ChatGPT replies: "Use tool to fetch ticket price for Paris." That's all there is to it. You write code that prompts a bit like this. You get back "use tool to fetch ticket price for Paris", and then you send the question a second time, but with the answer to that included in the question. And you've just seen tool use in action.

So the way that we can interpret this, of course, is to say that we are giving ChatGPT the autonomy to decide that it wants to make use of this tool should it wish to. And that all sounds very mystical and powerful, but at the end of the day it's JSON and if statements. That's how it works.

Okay, so with that, it's now time to go back to the lab. But I have bad news. We're not actually going to do a tool today, even though we've just been talking about tools. We are going to be using resources. So we are going to tie to that. And in the next lab tomorrow we are going to actually use tools. So for now I want you to put on hold that thinking about tool use and if statements, because we will come to that. But for now we're going to be building something with resources, and it's going to be fun, and it's going to set things up for the tool use that will come next time. I'll see you in the lab.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
