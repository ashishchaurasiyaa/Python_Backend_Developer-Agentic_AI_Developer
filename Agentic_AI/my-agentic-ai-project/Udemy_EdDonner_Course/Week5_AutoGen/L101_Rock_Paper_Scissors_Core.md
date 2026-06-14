# L101 — Day 3: Standalone Agents — Rock Paper Scissors

> **Week 5 — AutoGen** · ⏱️ ~7m · 🎥 Lecture 101 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821631

---

## 🎯 Ek Line Mein (TL;DR)

Ed **AutoGen Core** ka asli point demo karte hain — teen **RoutedAgent** (Player 1 = GPT-4o-mini, Player 2 = local **ollama llama3.2**, aur ek Judge) **SingleThreadedAgentRuntime** pe register hote hain, aur Judge runtime ke through dono players ko **discover karke message bhejta hai** — Rock Paper Scissors khelte hain, jo dikhata hai ki Core ka core business hai **agent-to-agent interaction**, na ki khud agents banana.

---

## 📝 Hinglish Explanation (Detailed)

- **Pantomime ek baar aur:** Pichle lecture ka disagreeable agent demo Ed ek round aur chalate hain — nice LLM agent "Hi there" bolta hai, **disagreeable agent** disagree karta hai, phir GPT-4o-mini politely handle karta hai: *"I appreciate your feedback. How would you prefer I greet you?"* Aap chahein to ise loop me cruel banake chala sakte ho.
- **Runtime hygiene:** Khelne ke baad **`runtime.stop()` aur phir `runtime.close()`** karna zaroori hai — AutoGen Core team insist karti hai ki naya runtime start karne se pehle purana properly band karo. Good citizen bano.
- **Ab main example — Rock Paper Scissors:** Ye koi commercial use case nahi hai, sirf **platform ko action me dikhane** ke liye hai. Point ye illustrate karna hai ki **collaboration / interaction hi AutoGen Core ka asli kaam hai**.
- **Player 1 agent:** Ek **`RoutedAgent` ka subclass** hai jiske paas:
  - **`OpenAIChatCompletionClient`** as `_delegate` (underscore wala private attribute),
  - Ek **`AssistantAgent`** jo us client ko **model client** ki tarah use karta hai,
  - Ek **`@message_handler`** wala `handle_my_message_type` method jo `Message` object leta hai aur response return karta hai.
  - Matlab — **super vanilla LLM routing**: jo message aaya, usko LLM se answer karwa do. No system prompt, no opinion.
- **Player 2 agent:** **Bilkul same code**, sirf ek tiny difference — **`OllamaChatCompletionClient`** use hota hai `OpenAIChatCompletionClient` ki jagah. Yani Player 2 ek **local model** pe chalta hai: **llama 3.2 (3B variant)**. Spot-the-difference game: ek line ka farq, aur agent cloud se local ho gaya.
- **Teesra agent — Judge (RockPaperScissors agent):** Iske paas thodi zyada logic hai:
  - **Instruction banata hai:** *"You are playing rock paper scissors. Respond only with one word: rock, paper or scissors."* — ise ek `Message` me wrap karta hai.
  - **Agent discovery by AgentId:** Player 1 ke **type** ka **default key/ID** lookup karta hai, same Player 2 ke liye. Yani **`AgentId(type, "default")`** se runtime me agents ko **naam se dhundta** hai — direct object reference nahi, **runtime ke through addressing**.
  - Apne message handler ke andar dono players ko **`send_message` dispatch** karta hai (haan, yahan hard-coded hai, "choose" nahi kar raha — but pattern wahi hai).
  - Jo responses aate hain, unse ek **judgment prompt** banata hai: *"You are judging a game of rock paper scissors. The players have made these choices… Who wins?"* — Player 1 aur Player 2 ki choices slip-in karke.
  - Ye judgment apne **khud ke model (GPT-4o-mini)** ko bhejta hai aur final result return karta hai.
- **Summary — 3 agents, sab wrappers:** Ed clarify karte hain ki ye teeno **"agent managers" / agent wrappers** hain — ye khud "real agents" nahi, ye **real agents ko delegate** karte hain:
  - **Player 1** → GPT-4o-mini ko delegate (no prompt, jo bola wahi karta hai),
  - **Player 2** → llama 3.2 ko delegate (same, promptless),
  - **Judge** → dono players ko instruction bhejta hai, responses judge karta hai, outcome return karta hai.
- **Commercial imagination:** RPS superficial hai, but pattern serious hai — **Week 6 me financial trading setup** banayenge jahan agents argue kar sakte hain ki koi **equity good investment hai ya poor**. Jab bhi aapko **autonomy + inter-agent interaction** chahiye, ye framework us commercial logic ko hold kar sakta hai. *"That is what AutoGen Core is for. Not for playing rock paper scissors."*
- **Run karna:**
  - **`SingleThreadedAgentRuntime`** banao — simple **local/standalone** runtime.
  - **`register()`** karo Player 1, Player 2, aur Judge — registration runtime ko ye **ability deta hai ki wo agents instantiate kar sake** (factory pattern — lazy creation).
  - **`runtime.start()`** karo, Judge ka default AgentId nikaalo, "go" message bhejo.
- **Result:** Agents baat karte hain, stuff happens — *Player 1 said rock, Player 2 said scissors, Player 1 wins because rock beats scissors.* Done.
- **Key takeaway from demo:** Judge ne players ko **runtime ke through naam se discover** kiya, messages bheje, aur AutoGen Core ne pura interaction **manage** kiya.
- **Standalone vs Distributed:** Aaj **standalone** runtime dekha (single-threaded, local). **Kal distributed** (gRPC wala) dekhenge. Ed phir stress karte hain — ye Core deep-dive course ke main agent-building ke liye essential nahi, but **flavor + comparison** ke liye important hai.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **RoutedAgent** | AutoGen Core ka base class — messages type ke hisaab se sahi handler method pe route hote hain |
| **`_delegate` pattern** | Agent wrapper ke andar asli kaam karne wala object (model client / AssistantAgent) — wrapper sirf routing karta hai |
| **OpenAIChatCompletionClient** | OpenAI-compatible model client — Player 1 isse GPT-4o-mini call karta hai |
| **OllamaChatCompletionClient** | Local model client — Player 2 isse llama 3.2 (3B) chalata hai, ek line ka farq |
| **AgentId (type + key)** | Agent ka address: `AgentId("player1", "default")` — runtime me naam se lookup, direct reference nahi |
| **`send_message` dispatch** | Ek agent ka handler doosre agents ko runtime ke through message bhejta hai — yahi inter-agent interaction hai |
| **Judge agent** | Teesra agent jo instruction banata hai, dono players ko bhejta hai, phir responses ko apne LLM se judge karwata hai |
| **SingleThreadedAgentRuntime** | Simple local (standalone) runtime — agents register karo, start karo, messages flow hone do |
| **`register()` (factory)** | Runtime ko agent banane ki *ability* dena — agent turant nahi banta, zarurat pe instantiate hota hai |
| **`stop()` / `close()`** | Runtime hygiene — naya runtime shuru karne se pehle purana properly band karna (AutoGen Core team ka insist) |
| **Standalone vs Distributed** | Aaj sab ek process me (single-threaded); kal gRPC pe alag-alag processes/machines me |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Ye pura demo actor model + service discovery hai:** `AgentId(type, key)` bilkul waise hai jaise aap Kafka me topic name ya service mesh me service name se address karte ho — Judge ke paas Player objects ka **reference nahi hai**, sirf **address** hai, aur runtime (broker) message deliver karta hai. Isi liye kal yahi code distributed (gRPC) pe bina logic change kiye chal jayega — location transparency, jaise Erlang/Akka actors me.
- **`register()` = DI container me factory registration:** Aap runtime ko class nahi, **factory lambda** dete ho — runtime lazily instantiate karta hai jab pehla message us AgentId pe aata hai. Ye Spring/FastAPI `Depends` ke lazy providers jaisa hai, singleton-per-key semantics ke saath (`"default"` key = default instance).
- **Ek-line client swap (OpenAI ↔ ollama) hi asli flex hai:** Model client ek **interface** hai — Player 1 cloud pe, Player 2 local 3B model pe, Judge ko farq nahi padta. Aapke `Repository` interface ke peeche Postgres vs SQLite swap karne jaisa.
- **🧪 Hands-on lab:** Is lecture ka code khud chalane ke liye **`Practical/lab3_autogen_core_rps.py`** run karo (is repo me, `uv run` se chalta hai, **Groq pe free** via `OpenAIChatCompletionClient` + `base_url` + `ModelInfo`). Difference: lecture me Player 2 **ollama (local llama 3.2)** use karta hai — hamare lab me dono players **Groq** ke alag models pe chalte hain (no local install needed), aur hamara AutoGen 0.7.5 hai vs course ka 0.5.1 (same API family).

---

## 🧠 Takeaway (yaad rakho)

1. **AutoGen Core ka point = interaction, not agents** — teen promptless wrappers + ek runtime, aur poora multi-agent game chal gaya.
2. **Agents address se discover hote hain** — `AgentId(type, "default")` lookup karke `send_message` bhejo; direct object references kabhi nahi.
3. **Player 1 vs Player 2 me sirf model client ka farq** — OpenAI cloud vs ollama local, baaki code identical. Client interface = swappable backend.
4. **`register()` factory deta hai, instance nahi** — runtime lazily agents banata hai; aur kaam khatam hone pe `stop()` + `close()` karna mat bhoolo.
5. **Aaj standalone (SingleThreadedAgentRuntime), kal distributed (gRPC)** — same code, alag deployment; Week 6 me yahi pattern financial trading me serious banega.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Did I just say that I'd stop this pantomime? Well, I take that back. We'll do the pantomime one more time. I've just added in another response from the nice LLM agent. So I'm going to have the LLM agent respond to "Hi there." I'm going to have the disagreeable agent disagree, and then I'll put it back to GPT-4o mini to see how it handles the disagreement. Let's see how this little conversation goes. "Hi there." "Hello. How can I assist you today?" "You said hello, how can I assist you today, and I disagree." Then GPT-4o mini says, "I appreciate your feedback. How would you prefer I greet you or assist you?" So if you want to be cruel, you can keep this going and just have it continually disagreeing and see how GPT-4o mini handles that.

And once you've had your fun, then you should do this — this stops the runtime and then closes the runtime, which the Autogen core people insist that we do before we start another. So we will do that and be good to it.

Okay. But for one more example, and I'm afraid this time we're not going to have sort of true commercial examples because I think this is just one to show the platform at work, and you can take this away and figure out what you'd like to do with it. But for this example, we're going to play rock, paper, scissors between a few agents, because I just want to illustrate the fact that this collaboration, this interaction is what it's all about.

So very simply, we have a player one agent that is a subclass of RoutedAgent. And it has an OpenAI chat completion client as its underscored delegate. It has an assistant agent that uses that as the model client, and then it has handle my message type that takes messages and returns the response. So this is a super vanilla kind of LLM routing that will just simply respond to the message that is given in the message object.

Okay. We got a player two which is exactly the same thing, but with one tiny difference. Can you spot it? Can you spot the difference between those two? Well, the difference is that this has an ollama chat completion client instead of OpenAI chat completion client. So we're going to use ollama. We're going to use a local model. And we are going to see which model that we pick. For this one we're going to pick llama 3.2, the 3 billion variant of llama 3.2. So these are a couple of agents.

And now we're going to have a third one, a third agent. And this is going to be a rock paper scissors agent. So this one is going to have a little bit more of an instruction. "You are playing rock paper scissors," first of all. So first of all it comes up with this instruction: "You're playing rock paper scissors. Respond only with one word, one of the following: rock, paper or scissors." And it puts that together into a message. It looks up the default ID, the default key for player one, that type, and it looks up the default for player two, that type. And it's looking them up. And then as part of handling its message, it dispatches off a message to these other agents. So it's just choosing to — it's not choosing, it's like coded here — but it is sending those messages off.

And with what comes back, with the result, it then puts together a little piece of text called judgment, which says, "You are judging a game of rock, paper, scissors. The players have made these choices." And then it ends with "Who wins?" — question mark — after slipping in the player one's choice and player two's choice. And then that gets dispatched off to my model, which is GPT-4o mini. And we return the response.

So just to summarize, we have a total of three agents that we've defined here. Three of these like agent managers, these agent wrappers — they're not real agents, they delegate to real agents. One is called player one and it delegates to OpenAI, to GPT-4o mini. One is called player two and it delegates to llama 3.2. And they don't have any prompts. They just do whatever instructions they're told. And then there's one called judge. And judge very clearly sends an instruction to each of player one and two saying pick rock or paper or scissors. And then with what comes back, it then judges them and returns the outcome.

So there we have a simple setup for a game of rock, paper, scissors. And you can of course make this something more interesting. You can have it be something that's entertaining, or you can have it be something that's serious, it's commercial. Like when we're thinking next time in week six, we're going to be building like a financial trading setup. You could imagine this could be something where different agents can interact and can argue about something like whether or not a particular equity is a good investment or a poor investment. You could imagine that's the kind of interactions that could be going on. So whilst we're using this here for a superficial exercise, there's plenty of ways you can imagine anytime when you'd want a sort of autonomy and the ability for different agents to be interacting — you could build that kind of commercial logic into this kind of framework. And that is what Autogen core is for. Not for playing rock, paper, scissors. But anyways, rock paper scissors is the cards you've been dealt and so you might as well play them.

Let's give it a shot. And quite simply, we create a single threaded agent runtime, which is the simple kind of local runtime. We register player one, we register player two and give it the ability to instantiate players one and two. And then we register the judge, the rock paper scissors, and have everything ready to go. And we start our runtime. We've registered everything and this is where we do it. We are going to find our rock paper scissors default agent. We are going to say go and set it going and let's see what happens.

Off it runs. Agents are talking, stuff is happening, and there we go. Player one said rock. Player two said scissors. Player one wins because rock beats scissors. Done. And there you have it. There you have agents being organized and interacting and agents being discovered. The rock paper scissors agent discovered these two agents by name, by identifying them through sending a message through the runtime. And we saw agents interacting in a game of rock, paper, scissors and being judged, managed by Autogen core.

And so again, there are these two types: standalone and distributed. Today we did standalone. Tomorrow we'll do distributed. And I just want to stress again that this is to give you a flavor. It's not necessarily as essential for the building of agents that we're doing mostly on this course, but it's good for you to get this insight and to see it and compare it with the other offerings out there. So with that, that wraps up day three. And as I say, tomorrow we get to distributed. I'll see you then.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
