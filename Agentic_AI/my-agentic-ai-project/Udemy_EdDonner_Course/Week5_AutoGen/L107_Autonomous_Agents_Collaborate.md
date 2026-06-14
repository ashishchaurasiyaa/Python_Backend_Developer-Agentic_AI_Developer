# L107 — Day 5: Autonomous AI Agents that Collaborate

> **Week 5 — AutoGen** · ⏱️ ~12m · 🎥 Lecture 107 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821669

---

## 🎯 Ek Line Mein (TL;DR)

Week 5 ka grand finale — **world.py** (ek plain Python script, agent nahi) **asyncio.gather** se **20 agents parallel** me create karwata hai via **Creator agent**, sab **gRPC distributed runtime** pe chalte hain, agents khud ideas banate hain aur ek-dusre ko **feedback** dete hain — yani **agents-creating-agents** ka live demo, fully autonomous.

---

## 📝 Hinglish Explanation (Detailed)

- **Project ka last piece: `world.py`** — ye **agent NAHI hai**, sirf ek **plain Python script** hai jo pura show orchestrate karta hai. Ab tak jo bhi dekha (agent.py prototype, creator.py) wo sab agents the; ye sirf launcher hai. Yahi **AutoGen Core ka fundamental point** hai — *messaging/communication/creation of agents* ek **separate concern** hai *agent implementation* se.
- **`create_and_message` coroutine** — ek async function jo `worker`, `creator_id` aur `i` (agent number 1, 2, 3...) leta hai. Ye **Creator agent ko message bhejta hai** ("agent N.py banao"), aur result ko `idea_N.md` file me likhta hai.
- **`HOW_MANY_AGENTS` variable important hai** — ye decide karta hai kitne agents ek saath kick off honge. Ed ne **20 agents** chalaye.
- **Cost + safety warning**:
  - Real APIs hit hoti hain — 20 agents pe Ed ko ~**couple of cents** laga (GPT-4o **mini**); 3 agents pe almost free.
  - **Risk**: Creator agent *theoretically* **model requirement change kar sakta hai** — generated agent expensive model (GPT-4o mini ki jagah kuch mehenga) use karne ka decide kar sakta hai. Very unlikely, but not impossible — generated code execute karne ka classic danger.
- **Main async function ka flow**:
  1. **gRPC Worker Agent Runtime Host** create + start (notebook jaisa hi).
  2. **Worker** create + start.
  3. **Creator register** karo (creator.py se import) — id `creator:default`.
- **asyncio.gather ka smart use** — agar loop me har `create_and_message` ko `await` karte, to sab **serial** chalta: ek file banti, message jata, answer aata, phir agla. Boring. Instead:
  - **Bina `await` ke coroutines ki list gather karo** (coroutine objects, abhi run nahi hue).
  - Phir **`asyncio.gather`** se sab ek saath await karo — sab **parallel** chalte hain.
  - **Ye multithreading NAHI hai** — CPU threads me nahi chop ho raha. Sab **event loop** me chalte hain: jab ek coroutine OpenAI (network) ka wait kar raha hota hai, dusra run karta hai. OpenAI **rate limits** ke andar raho to plenty parallel chal sakte hain.
  - End me host/worker **stop**, aur exceptions print.
- **Async Python ko CLI se kaise chalate hain** — main file me `asyncio.run(main())` pattern chahiye jo **event loop initiate** karke coroutine run kare.
- **Teen pieces ka recap**: `agent.py` = **prototype** (jo clone hota hai), `creator.py` = **cloner** (agent-by-agent, one by one call hota hai), `world.py` = **orchestrator** (agent nahi, plain Python).
- **Live run**: `cd` into week 5 folder, **`uv run world.py`** (Python module ki tarah nahi). Kuch **gRPC/threads warnings** aaye but kaam nahi rukta. Output: "agent 16 is live", "agent 17 is live"... — phir messages agents ke beech udne lagte hain.
- **Generated agents kaise dikhte hain**: har ek alag **persona + parameters** ke saath —
  - Tech-savvy innovator (entertainment, gaming, film, VR) — **0.3 handoff chance**, **0.8 temperature**.
  - Futuristic technology solutions — short system message, 0.8 / 0.4.
  - Agent 16 — **finance industry**: fintech, e-commerce, digital transformation.
- **Result — idea_16.md ("FinBuddy")**: file ke top pe feedback header dikhata hai ki ye idea **dusre agent ko bheja gaya tha refinement ke liye** — "I absolutely love the vision behind FinBuddy... let's refine and elevate". Final idea: **AI-powered financial companion** for underserved communities — contextual financial advisor, localized community support hubs, **micro-investment pools**, gamification with real rewards (local business partnerships). Sab kuch **20 agents + conversations + 20 ideas, minutes me, autonomously**.
- **Goal**: ek **live agentic platform** jahan agents create hote hain, collaborate karte hain, autonomously interact karte hain — itna autonomous ki **wo khud ek agent ne create kiye**.
- **End-of-week challenge (optional, kyunki ye experimental/researchy week tha)**:
  - Project ko **robust + safe** banao — e.g., **dockerize** it (generated code container me sandboxed chale).
  - **Super meta idea**: Creator sirf naye agents nahi, **apna naya version** bhi likh sake — apni hi file ko **tool se read** karke khud ko **rewrite/replicate** kare, logic thoda change karke. Creators creating creators... creating creators. Mind blown.
- **Week 5 wrap-up**: AutoGen ek **experimental, futuristic, forward-thinking** platform hai — frontier of Agentic AI. Ab **Week 6**: **MCP** + **OpenAI Agents SDK** (Ed ka still-favorite framework, CrewAI aur LangGraph enjoy karne ke baad bhi) — "legendary week" promise.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **world.py** | Orchestrator — plain Python script (agent nahi) jo host/worker start karke Creator se 20 agents banwata hai |
| **create_and_message** | Coroutine jo Creator ko "agent N banao" message bhejta hai aur result `idea_N.md` me save karta hai |
| **asyncio.gather** | Coroutines ki list ko ek saath await karna — sab event loop me parallel chalte hain (threads nahi) |
| **Event loop concurrency** | Jab ek coroutine network (OpenAI) pe wait karta hai, dusra run karta hai — I/O-bound parallelism |
| **gRPC Worker Agent Runtime Host** | Distributed runtime ka server — workers isse connect hote hain, agents uspe register hote hain |
| **Creator agent** | RoutedAgent jo naye agents ka code generate karke unhe runtime pe register/launch karta hai |
| **agent.py (prototype)** | Template agent jo clone hota hai — har clone alag persona, temperature, handoff-chance ke saath |
| **HOW_MANY_AGENTS** | Kitne agents parallel kick off honge — cost aur scale dono isi se control hote hain |
| **Model-change risk** | Generated code theoretically expensive model use kar sakta hai — generated-code execution ka inherent risk |
| **uv run world.py** | Script chalane ka tarika — uv environment manage karta hai, `asyncio.run(main())` event loop start karta hai |
| **Self-replicating creator (challenge)** | Creator apna code tool se padh ke apna naya version likhe — creators creating creators |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **`asyncio.gather` pattern aap production me roz use karte ho** — ye wahi "fan-out N HTTP calls concurrently" trick hai jo aiohttp/httpx ke saath karte ho. Yahan har "call" ek pura agent-creation conversation hai. Key insight wahi: **I/O-bound work ke liye event loop > threads** — GIL ki tension hi nahi kyunki sab network-wait hai.
- **world.py vs agents = Kubernetes manifest vs pods wali feeling** — orchestration (kaun create hoga, kitne, kab) declaration/launcher me hai; behavior (agent kya karta hai) implementation me. AutoGen Core ka core pitch yahi **separation of concerns** hai — messaging infra alag, agent logic alag, bilkul jaise Kafka cluster vs consumers.
- **Generated-code-execution = supply chain risk in miniature** — Creator jo .py file likhta hai wo `import` hoke execute hota hai (dynamic loading, importlib-style). Isliye Ed ka "model change kar sakta hai" warning aur dockerize-it challenge — aap isse `eval()` on user input jaisa treat karo: **sandbox, resource limits, allowlisted models**.
- **Hands-on lab**: `Practical/lab4_agent_creator.py` (is repo me, `uv run` se chalta hai, Groq pe free via `OpenAIChatCompletionClient` + `base_url` + `ModelInfo`) — **is lecture ka code khud chalane ke liye ye lab run karo**. Difference: lecture me Creator real Python code generate karke execute karta hai (GPT-4o mini, paid); hamara lab4 **SAFE persona-generation** karta hai — arbitrary generated code execute nahi karte, sirf personas/params generate hoke fixed agent template me inject hote hain (AutoGen 0.7.5 vs course 0.5.1, same API family).

---

## 🧠 Takeaway (yaad rakho)

1. **world.py agent nahi hai** — plain Python orchestrator jo gRPC host + worker start karke Creator register karta hai aur 20 creation-requests bhejta hai.
2. **Parallelism ka trick**: coroutines ko bina `await` ke list me jama karo, phir **`asyncio.gather`** — event loop me sab concurrent, threads ke bina.
3. **Agents-creating-agents kaam karta hai**: 20 agents, unique personas/temperatures/handoff-chances, ideas + cross-agent feedback — sab minutes me, ~2 cents me.
4. **Risk samjho**: generated code real API hit karta hai aur model badal sakta hai — sandbox/dockerize karna challenge hai; lab4 isliye safe persona-gen use karta hai.
5. **AutoGen Core ka point**: agent **communication/creation** ko agent **implementation** se alag rakhna — aur next stop: **Week 6 = MCP + OpenAI Agents SDK**.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

All right, we're nearly there. We're nearly there. I've just got one more thing to show you, which is world.py, which is quite short, which is the overall thing. Creator.py — you have to send it. It's an agent, and you have to send creator a message like agent one, agent two, agent three, and it will create them. So this is where it all comes together. world.py is not an agent. This is just a Python script. Everything else you've seen has been agents. This is just a Python script, but it uses async Python in quite an interesting way.

So there is this async function, this coroutine create_and_message which takes a worker, and a creator id and an i, which is going to be the agent number going 1, 2, 3, 4, 5. Um, this "how many agents" up here is a pretty important one to look at. This is how many of these it's going to kick off at the same time. And the other thing that's unsafe about this, of course, is cost — that this is going to hit the real APIs. And for me it's cost like a couple of cents when I run this for 20 agents, which is pretty cheap, all things considered. And obviously if you do it for like three agents, it costs nothing. But there's a risk there that we are allowing, in theory, the agent creator could change the model requirements. It could decide to use an expensive model instead of GPT-4o mini. And so that's just something to watch for. It's very unlikely. Uh, but it's not like it's not impossible.

Anyways, we've got 20 agents here, so we've got this async method create_and_message — it says it takes this worker and it sends a message to the agent number whatever dot py. Um, and then it writes the results to idea whatever dot markdown. Um, that's what all this thing here does. Okay. So now we go to our main async method, our main async function, our coroutine. So it creates a host, a gRPC worker agent runtime host, as we did in the notebook before. It starts the host, it creates a worker and it starts the worker. It then registers the creator. So it registers the creator from creator.py that was imported here. So that will launch a creator. And this is its id: creator, default.

Then this is the async thing. So I don't want to have a loop and call this, creating worker after worker — sorry, creating agent after agent — because then it will be serial, or will happen one after another. If I do like an await and then I call this coroutine, then we'll be waiting there. It will create one file. It will send it a message. Back will come the answer. Maybe it'll send it somewhere else, and then it will go on to the next. And we'll be sitting here waiting and it won't be exciting. But what you can do with coroutines, as you hopefully remember from — we briefly talked about this — is that you can get a whole stash of coroutines together. So I haven't got the word await here, which you need if this is actually going to run. I'm just gathering a whole list of coroutines and then I await them using asyncio gather, and asyncio gather runs them all in parallel. And as hopefully you remember, it's not like multithreading. They're not going to be actually running on different threads, like with the CPU chopping between them, but rather they're running in the event loop. That's how asyncio Python works. They run in an event loop so that every time it's waiting on OpenAI, which means it's waiting on a network connection, another one can be running, and that means they all get to run at the same time. And as long as I stay within my rate limits with OpenAI, we'll be able to run plenty in parallel.

And so it does all of that. And then at the end it stops, and any exceptions it will print them, and that's it. This is, by the way, how you run async Python from the command line or from a Python module. Your main file needs to do this, which initiates an asyncio event loop and then runs your async method, your coroutine. So that is how it hangs together. And I do believe this is it. I don't think I've got anything else to show you. I think you've seen everything. You've seen agent, which is the prototype, the thing that gets cloned; creator, which does the cloning agent by agent — it's called one by one. And world.py — this is not an agent. It's just Python code which will orchestrate, which will launch the whole process running. Okay. All that remains to do is to actually show you this thing working. Let's see if it does work. See you in a sec.

Okay, let's give this a whirl. So we'll bring up a command line. We'll make it nice and big so we see what's going on. We will go into the fifth directory and now we don't say Python and then a module, but rather we say uv run, and then world.py is our script that will call creator 20 times for 20 different creations. You're expecting to see Python modules appearing over time as it builds the Python agents. And then you should see ideas starting to appear as well, after the conversations have happened. It might take a bit of time. We'll see what happens. Do you think it's going to work?

Some problems — some messages about threads and gRPC. I don't know what that's about, but it doesn't seem to stop it. And then off it goes, and you will see that it says agent 16 is live, agent 17 is live, agent nine is live. Lots of things going on. And now you'll see messages going between agents and lots, lots of stuff here. Let's take a look at some of these agents. You'll also start to see ideas are appearing here. We look at these agents. Here is a tech savvy innovator in the field of entertainment, gaming, film and virtual reality — 0.3 chance that he speaks to someone else, or she, and a 0.8 temperature. Let's try this one here. It's also another — this one is futuristic technology solutions. Very short system message, 0.8, 0.4. 16 — finance industry, this one. Innovate within the finance industry: fintech, e-commerce and digital transformations. I wonder what this one will be. Agent 16 — we should go and look at idea 16. It's already finished the 20 ideas. So it's very fast.

And that's the great thing about this. We just created 20 agents. They just came up with ideas. Many of them will have had conversations. It all just happened while you were watching. And I do hope that this was worth your time investment for this, and that you see the entertainment value and the educational value of going through this. Let's take a look at agent 16 and see the financial services ideas. Uh, let's open a preview and let's get rid of this. Oh, and the fact that we've got this — "I absolutely love the vision behind FinBuddy" — this thing at the top here tells us that this was sent to another agent for feedback. At least one agent added feedback to this. So this went through a couple of people. So: "I absolutely love the vision behind FinBuddy. It's a powerful concept, the potential to make significant impact on financial literacy and accessibility for underserved communities. Let's refine it and elevate the idea even further." Refined concepts. So this is great. It's an idea for applying Agentic AI to financial services that's been refined by another agent. FinBuddy, your AI powered financial companion for empowerment and inclusivity. Uh, so it's basically an education platform for people who are underserved in financial services. Contextual financial advisor. Localised community support hubs. Micro investment pools — users can join collaborative investment pools, collectively decide on small scale investments. That is cool. And engagement driven gamification with real rewards — partner with local businesses. Very interesting, very interesting. Well, I might give this a read on my own. You might not hear from me again.

Uh, so anyway, the goal of this is to give you a live agentic platform where agents are created and agents collaborate and interact in an autonomous way — in such an autonomous way that they were even created by another agent. And I hope you find this as satisfying as I do, and I hope it was worth it. I hope it was worth the half an hour investment to get here, and do take a look through the code if nothing else. As I say, it's definitely got some interesting ideas built in there about how to use things like Autogen for this kind of messaging between agents. And if nothing else, if you give it a run, if you feel bold, you will find a bunch of ideas. And maybe, maybe you'll be off on your yacht before too long. All right, I'll see you for the wrap up.

Well, thank you for indulging me for the last half an hour of going through that project. I do hope that you at least found it somewhat interesting, educational. And, yeah, it's opened your eyes a bit into some of what's possible at the frontier of Agentic AI, which is very much where Autogen is. It's very much an experimental and futuristic platform, as we've seen ourselves first hand.

So the challenge for you, the end of week challenge, is an optional one, because this week has been experimental and a researchy week. But should you wish to invest some more time in this idea, see if you can work with me on making it a bit more robust and something that it's safer for people to run, perhaps by dockerizing it. But in particular, something which I think would be fascinating would be to have it so that the creator is not only able to write new agents, but it's also able to write a new version of itself. It can create a new creator, modeling it off its own template, of its own file, which it can also read. It might be interesting to turn that into a tool, rather than just having it be there in the Python code — have it be able to run a tool that reads in its own code, and it can then rewrite itself, making a replica, something which itself is able to create new agents. And perhaps it could change its own logic slightly in some interesting way. So I think that would be fascinating. Super meta. It's something that creates creators. And then, I mean, if it creates itself, then in theory it can create creators of creators. Uh, so. Yeah. Mind blows. Uh, interesting, interesting project. A great way, importantly, to be experimenting with interactions between agents in this kind of idea of an environment where the messaging, the communication and creation of agents is a separate concern from the implementation of the agents, which is, of course, the fundamental point of Autogen core.

All right. And with that, finally, I'll stop yammering away about this. We're — the agent creator is done, and we are on to week six. The fantastic, the exciting conclusion. And it is going to be a legendary week. Uh, I can't wait to show you everything that MCP is about and can offer, and I can't wait to return to OpenAI Agents SDK. Still my favorite, even after enjoying all of the others — enjoying Crew and LangGraph a lot, and being generally entertained by Autogen and by its forward thinking-ness. But OpenAI Agents SDK is next, with MCP. I'll see you then.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
