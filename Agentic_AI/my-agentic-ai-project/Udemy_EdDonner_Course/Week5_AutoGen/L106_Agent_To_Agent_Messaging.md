# L106 — Day 5: Agent-to-Agent Messaging

> **Week 5 — AutoGen** · ⏱️ ~11m · 🎥 Lecture 106 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821665

---

## 🎯 Ek Line Mein (TL;DR)

Ed ek **crazy-but-educational project** dikhate hain — ek **Creator agent** jo `agent.py` template se **naye agents khud likhta, save karta, `importlib` se import karta aur runtime pe register karta hai**; phir wo agents **AutoGen Core ke pure messaging** se ek-dusre ko business ideas bhejte aur refine karte hain.

---

## 📝 Hinglish Explanation (Detailed)

- **Setup:** Hum Cursor me 5th directory me hain. Yahan teen main cheezein hain — `agent.py` (template), `messages` package, aur `creator` (agent jo agents banata hai).

- **`agent.py` = template / prototype:**
  - Ye file hum **dusre agent (Creator) ko denge** aur kahenge — "isko **model/example** maan, aur **iske jaise naye agents clone karke bana**." Matlab clone hum nahi banayenge, **ek agent banayega**.
  - **System message:** "You are a **creative entrepreneur**. Aapka task hai **Agentic AI use karke naya business idea** dena ya existing idea refine karna. Aapke interests kuch sectors me hain, aap **disruption** wale ideas pasand karte ho, pure **automation** wale kam. Aap optimistic, adventurous, risk-appetite wale, imaginative ho — kabhi kabhi zyada hi. Weaknesses: impatient, impulsive."
  - File ke top pe comment: **"Change the system message to reflect the unique characteristics of this agent"** — yani har clone apni **alag personality** rakhega.
  - Ek constant hai — **chances that I bounce idea off another = 0.5** (50% probability ki agent apna idea kisi aur agent ko refine karne bhejega).
  - Comment ye bhi kehta hai: **code ka behavior change kar sakte ho, lekin method signatures same rakhna** — warna runtime ke saath contract toot jayega.

- **Agent ka structure (jo clone hoga):**
  - **`__init__`:** **GPT-4o-mini** model client banata hai with **temperature 0.7** (thoda randomness), aur us model client + system message se ek **delegate** banata hai — ek **AssistantAgent** (Week 5 ka classic pattern: RoutedAgent ke andar AgentChat ka assistant wrap karna).
  - **`handle_message` (with `@message_handler` decorator):** Ed isko `handle_my_message_type` se rename karke `handle_message` kar dete hain — "fewer tokens is always good" 😄.
    - Ye **`messages.Message`** leta hai aur **`messages.Message`** return karta hai (type-annotated dispatch — AutoGen Core isi se decide karta hai kaunsa handler call hoga).
    - Pehle print karta hai: **"<type> received a message"** — yaad rakho, **`type` agent ka naam jaisa hota hai** (AgentId = type + key). Isse hum live dekh payenge kaun-sa agent message receive kar raha hai.
    - Incoming message se ek **TextMessage** banakar **delegate (underlying LLM)** ko bhejta hai — system prompt automatically saath jata hai kyunki wo delegate me set hai.
    - Response wapas aata hai = uska **business idea**.
  - **50% bounce logic:**
    - `random()` se 0–1 ke beech number; agar wo `0.5` se kam hai, to ek utility **`find_recipient()`** se **random dusra agent** dhundta hai.
    - Us recipient ko message bhejta hai: *"Here is my business idea. This might not be your specialty, but please refine it and make it better."*
    - Bhejne ke liye **`self.send_message(...)`** use hota hai — matlab agent apne **runtime** ke through directly dusre agent ko message karta hai (pure **agent-to-agent messaging**, koi team/orchestrator nahi).
    - Jo refined idea wapas aata hai, wahi return hota hai. To agent ya to **apna idea** return karega, ya **kisi aur agent se refined version**.

- **`messages` package:**
  - Wahi familiar **dataclass `Message`** hai jo hum har baar banate hain. Ed ne isko alag package me isliye rakha taaki **agent.py me kam-se-kam code ho** — generated clones me mistakes ke chances kam.
  - **`find_recipient()` — "super hacky" but works:** clones ka naam **agent1, agent2, agent3...** hota hai, to ye function bas **directory me dekh leta hai** kaunse agent files exist karti hain aur **randomly ek pick** karta hai. Funny bug: agent **khud ko bhi pick kar sakta hai** (khud se baat karega!) — Ed bolte hain fix kar sakte the, par "whatever, it doesn't matter" 😅.

- **`creator` — the agent that spawns agents (yahan magic hai):**
  - **System message:** "You are an agent that can create other agents. You receive Python code (Autogen Core + Autogen AgentChat use karta hai). Is **template** se ek naya agent banao with a **unique system message**. Goal same rakh sakte ho ya **completely different direction** me le ja sakte ho." — Ed: *"This is the part that's both edgy and risky haha."*
  - **Sirf 3 hard requirements:** class ka naam **`Agent`** ho, wo **`RoutedAgent`** se inherit kare, aur **`__init__`** method ho. Aur: **"Respond only with Python code."**
  - Ed ne abhi tak ye sirf **GPT-4o-mini** ke saath try kiya hai jo "a bit safe" hai — kuch off-the-rails nahi hua. Wo **DeepSeek** ya **Claude** (jo zyada creative mana jata hai) try karne ke liye tempted hain, dekhne ke liye kya wo agents me **alag logic / zyada smarts** daalte hain.
  - **Creator ka flow:**
    1. `agent.py` template file **open/read** karta hai.
    2. **Delegate LLM** ko bolta hai — is template ka **naya version** likho.
    3. Result ko **`agent1.py`, `agent2.py`...** ke naam se **save** karta hai (agent number message me aata hai — e.g. "agent5" bheja gaya to `agent5.py` banega).
    4. **`importlib`** se us just-written file ko **dynamically import** karta hai — effectively `import agent5` **on the fly, programmatically**!
    5. Imported module pe **`Agent.register(runtime, name, lambda: ...)`** call karta hai — **factory/lambda** jo demand pe naya instance banayegi.
    6. Print karta hai **"agent5 is live"** — live yahan deploy wala live nahi, **actually running** wala live.
    7. Phir us naye agent ko message bhejta hai: **"give me an idea"** — jo poora chain trigger karta hai: idea banao → 50% chance pe directory se random agent dhundo → usse refine karwao → result return karo.

- **Learning point (Ed ka main message):**
  - Ye project **imaginative, kind of crazy** hai, lekin **educational** — step through karke dekho kya ho raha hai.
  - **Async Python** ka ek important topic aage aa raha hai (next lecture).
  - Asli demonstration ye hai ki **AutoGen Core ek pure agent-messaging platform** hai: hum kisi bhi agent ko **AgentId se single out** karke directly message bhej sakte hain — ye ek tarah ka **inter-process communication** hai, bina ye soche ki andar wiring kaise hui hai.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **agent.py (template/prototype)** | Wo example file jise Creator agent clone karke naye agents banata hai — sirf system message/behavior badalta hai, method signatures same |
| **Creator agent** | Ek RoutedAgent jiska kaam hi **dusre agents ka Python code likhna, save karna, import karna aur register karna** hai |
| **Delegate (AssistantAgent)** | RoutedAgent ke andar wrap kiya hua AgentChat assistant — actual LLM call yahi karta hai (GPT-4o-mini, temp 0.7) |
| **`@message_handler`** | Decorator jo method ko message receiver banata hai; **type hints** (`messages.Message -> messages.Message`) se dispatch hota hai |
| **`self.send_message(msg, recipient_id)`** | Runtime ke through **directly kisi agent ko message** bhejna — pure agent-to-agent communication |
| **AgentId (type + key)** | Agent ka address; `type` agent ke naam jaisa — print logs me yahi dikhta hai ("agent3 received a message") |
| **`find_recipient()`** | Hacky utility — directory me agent files dekh ke **random recipient** pick karta hai (khud ko bhi pick kar sakta hai!) |
| **Bounce probability (0.5)** | 50% chance ki agent apna idea kisi random agent ko **refine** karne bhejega |
| **`importlib`** | Python feature — **runtime pe dynamically module import** karna (`import agent5` programmatically) |
| **`Agent.register(runtime, name, factory)`** | Naye (LLM-generated!) agent class ko runtime pe register karna with a **lambda factory** jo instance on-demand banati hai |
| **"Agent is live"** | Register + message bhejne ke baad agent actually runtime me chal raha hai — deploy wala live nahi, running wala live |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Ye pura system actor model + dynamic class loading ka mashup hai.** `Agent.register(runtime, name, lambda)` bilkul **DI container me factory register** karne jaisa hai (Spring beans / FastAPI dependencies), aur `importlib` wala move waisa hi hai jaise **plugin systems** (pytest plugins, Django apps, Celery task discovery) entry-points se modules runtime pe load karte hain. Naya twist: **plugin code khud LLM ne abhi-abhi likha hai.** Production me aap kabhi unreviewed generated code import nahi karoge — isliye hi ye "edgy and risky" hai.
- **`self.send_message(msg, recipient_id)` = point-to-point messaging, queue ke bina.** Socho RabbitMQ direct exchange with routing key, ya Erlang/Akka ka `actor_ref ! message` — sender sirf **address (AgentId = type + key)** janta hai, transport runtime handle karta hai. `find_recipient()` ka directory-scan ek **poor-man's service discovery** hai (jaise Consul/etcd lookup, bas filesystem pe).
- **Method signature contract** ("change behavior, but keep signatures same") wahi baat hai jo aap API versioning me karte ho — handler dispatch **type annotations** se hota hai (`messages.Message -> messages.Message`), to signature todna = consumer break karna. Aur 0.5 bounce probability ek tarah ka **probabilistic fan-out** hai — jaise sampled tracing ya canary routing.
- **Hands-on lab:** is lecture ka code khud chalane ke liye `Practical/lab4_agent_creator.py` run karo (is repo me, `uv run` se chalta hai, **Groq pe free** via `OpenAIChatCompletionClient` + `base_url` + `ModelInfo`). Ek important difference: course me Creator **arbitrary Python code generate karke `importlib` se execute** karta hai — hamare lab4 me **code-gen ki jagah SAFE persona-gen** hai (LLM sirf system-message/personality generate karta hai, generated code kabhi execute nahi hota). Baaki hamara stack AutoGen **0.7.5** hai (course 0.5.1, same API family).

---

## 🧠 Takeaway (yaad rakho)

1. **`agent.py` ek prototype hai** — Creator agent isse clone karke `agent1.py`, `agent2.py`... banata hai, har ek apni unique personality (system message) ke saath; bas class name `Agent`, `RoutedAgent` inheritance aur `__init__` fixed rehna chahiye.
2. **Creator ka pipeline:** template read → LLM se naya code → file save → **`importlib` se dynamic import** → **`register()` with lambda factory** → "agent is live" → pehla message bhejo.
3. **Agent-to-agent messaging ka core:** `self.send_message()` + AgentId — koi orchestrator/team nahi, **runtime ke through direct addressing**, jaise actor model me hota hai.
4. **50% bounce logic:** har agent apna idea ya to seedha return karta hai, ya random recipient se **refine** karwa ke — emergent collaboration bina kisi central planner ke.
5. **Main lesson:** AutoGen Core ek **pure agent messaging platform** hai — inter-process communication ki details runtime sambhalta hai; aur haan, **async Python** ka important topic next lecture me aa raha hai.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Okay, so here we are back in Cursor going to the fifth directory where there are a few things for me to show you. So, uh, where to begin? I am going to begin by telling you about agent.py. So agent.py is like our template. This is a file that we are going to give another agent and ask it to use this as its model, as its example, and to take this as a template and to make other agents like this. So it is quite simply, it's like a prototype. It is our the prototype that will be used. We will clone it and make various versions of it or we won't. An agent will.

So it does some some imports. It has a system message. You are a creative entrepreneur. Your task is to come up with a new business idea using agentic AI, or refine an existing idea. Your personal interests are in these sectors and there's a couple of sectors you're drawn to ideas that involve disruption. You are less interested in ideas that are purely automation. You are optimistic, adventurous, and have risk appetite. You're imaginative. Sometimes too much so. Your weaknesses. You're not patient, can be impulsive. You should respond with your business ideas and engaging in a clear way. And you can see at the top here there's a comment. Change the system message to reflect the unique characteristics of this agent. And then here, this constant chances that I bounce idea off another is 0.5. And here it says you can also change the code to make the behavior different. But be careful to keep the method signatures the same. Okay, so far so good.

And this agent that is going to be cloned. It has an init method which just simply sets GPT-4o mini with a temperature. Make it a bit a bit random 0.7. And of course it creates a delegate which is an assistant using that model client. And with this system message. Okay. And here we have our handle message. Uh, and it's a message handler. And, uh, it's, um, got, um, uh, maybe it would be clearer if I just call this handle message rather than handle my message type. Fewer tokens is always good. Uh, so, um, it takes, uh, of course, the message. And now this message is using our messages object, the thing that we always create. And I have separated that out into its own package, because I want to put as little code in here as possible to avoid mistakes. So I've got our message object in here. We'll look at that in a minute. And it so it takes a messages message and it returns a messages dot message.

It prints that this message with this type. Remember the type is like the agent's name. It's going to say received a message. So we will see as agents receive messages. It then makes a text message, um, and, uh, it, uh, then it takes, takes this, this message that it was sent and it, uh, sends that to the, its underlying LLM. So, so it sends on the message that it got. And that will of course, also have the system prompt as part of it because that's set right here. Uh, and it then says it waits until it gets back. The response it gets, it takes from the, the the response it makes that its business idea because it's asked to come up with a business idea. So what comes back from the delegate will be a business idea.

And now it picks a random number and sees it basically figures out if in this case, this random, not random gives you a number between 0 and 1. And so if it's a 50% chance, if it's if it's a, there's a 50% chance it'll be less than 0.5. So uh, that this, this logic works If there's in a 50% chance it will use a little utility function, find recipient that's going to find some other recipient, and then it will say, here is my business idea. This might not be your specialty, but please refine it and make this business idea better. And it sends this business idea as a message to the recipient. So some randomly picked recipient, how's it going to pick a random recipient? We will see a random recipient is going to get the request to refine this business idea that this agent just came up with. And then and only if the probability is is is within this. And if so, then it will take the refined business idea. It will do self dot send message, which means it uses the runtime that it's associated with to send a message to the recipient. And it gets back the idea and that is what it then returns. So it either returns its own idea or there's some probability that it will return a refined version of its own idea refined by another agent.

Okay, a lot to talk through. I hope that made sense. This is the template, the clone that's going to be used to create more agents. Let's see how. And I'm going to speed up. But but hang on in there because it's going to be great when you see this running. So wait for it. Don't don't don't lose me.

Uh, I'll just quickly show you the messages. This is the messages package, and it has that same data class that we know of. Uh, and then it has some code to deal this, find recipient, find another agent that will message. And how does it do that? Well, it's super hacky, but basically, as the clones start appearing, the clones are going to be named agent one, agent two, agent three, agent four. And so it basically just looks in this directory to see what other agents have already existed. And if it finds one, it returns a randomly selected other agent, and there's some chance that we'll return the agent itself. The agent might talk to itself that maybe I should should, uh, solve I should should fix that and not let it talk to itself. But I thought, whatever, it doesn't matter. So. So right now it might talk to itself as well. Okay.

So then the, uh, where life gets interesting is creator. Creator is the agent that creates and spawns agents. And I'll let you look through this. But basically the system message says just what you would think. You're an agent that can create other agents. You receive Python code and you create the user's Autogen core and Autogen agent chat. You should use this template to create a new agent with a unique system message. You can choose to keep the overall goal the same or change it. You can choose to take this agent in a completely different direction. This is the part that's both edgy and risky haha. The only requirement is that the class must be named agent, and it must inherit from from RoutedAgent and and it must have an init method. Respond only with Python code.

So, look, this is this is cool. There's no doubt we're building something that we're saying. You have a free reign to do what you want. And I've only tried this with GPT-4o mini, which is a bit safe with this stuff. It hasn't actually gone off the rails in an interesting way, and I am tempted to try it with DeepSeek. I'm slightly nervous with and with more creative agents, and maybe with Claude, because Claude is known for being more creative and see whether they look to include different logic in there to give this agent more smarts. But so far, whilst GPT-4o mini has definitely taken it in different directions, it hasn't done anything out there.

Okay, so the user prompt says much, much the same thing. And then, uh, you can you can trace through it. But this is pretty simple and it prints what it's doing. But it basically opens this file, name it, it then uh, calls uh the delegate to, to take this action to basically given this python file in agent py, make a new version of it, and then and then it saves that as like agent one, agent two, agent three, agent four. So it was save it as each of the different, uh, agent numbers, it's, it's called with an agent number. And it will, uh, it will save it with that agent number.

And then it does something that is super, uh, like, uh, out there. I use this Python feature, um, importlib to import the Python module that it just wrote. I import it here so that this creator agent imports that module, that it just wrote it effectively. If it just wrote a file called uh agent5.py and the word agent five will have actually have come in in this message right here. So agent five is what will have been sent to the creator. And that's how it knows that that's the agent it's making. So in that case, what this will do is it will effectively be the same as saying import agent5.py. That's what that does dynamically. Programmatically. It imports it on the fly. And then I take that module that we've just imported on the on the fly and I register it, I call agent dot register with my runtime with the agent's name and using the lambda that will spawn a new instance, a factory method that will create a new instance of that agent on demand. And then it says it prints agent whatever is live and and it means not just the kind of live that we say when we deploy software. It means that the agent is running.

Um, and it will then send a message to that agent saying, give me an idea. And that will then trigger that agent will then get that message. It will process it, it will work on an idea and potentially if the probability meets that criteria, it will then send on its idea to another agent that it will find in the directory, and ask that other agents to add feedback to it. And that's that's how it would all fit together, if you can believe it. That's what this does. So it's imaginative. It's a kind of crazy. And uh, as I say, the main the learning point here is that it is educational to step through it and see what's happening. And we've got something important about async Python coming up. Um, but this is definitely, uh, something to have you thinking about what it means to have agents interacting, messaging each other, and how this really demonstrates Autogen core's power as a pure agent messaging platform. We're able to to single out an agent, we are able just to get a recipient's agent ID and send it a message. So it allows for this kind of inter-process communication, uh, without without having to worry about the details of how that's actually strung together.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
