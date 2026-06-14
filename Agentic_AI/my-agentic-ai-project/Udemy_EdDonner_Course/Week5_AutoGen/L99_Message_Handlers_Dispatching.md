# L99 — Day 3: Message Handlers & Dispatching

> **Week 5 — AutoGen** · ⏱️ ~9m · 🎥 Lecture 99 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821623

---

## 🎯 Ek Line Mein (TL;DR)

**AutoGen Core** ka core idea = agent ki **logic** ko **message delivery** se decouple karna — framework sirf agents ki **lifecycle + messaging** handle karta hai, aur aap **RoutedAgent** subclass banakar **@message_handler** decorated coroutines likhte ho jinme messages **type signature ke basis pe auto-dispatch** hote hain.

---

## 📝 Hinglish Explanation (Detailed)

- **Core idea — decoupling:** AutoGen Core ka fundamental philosophy ye hai ki **agent kya karta hai (logic)** aur **messages usko kaise deliver hote hain (interplay)** — ye dono alag concerns hain. Framework sirf **creating aur communicating** handle karta hai: agent ki **poori lifecycle** (create, manage, refer, message) aur agents ke beech **communication**. **Logic likhna aapki responsibility hai** — wo AutoGen Core ka mandate nahi. Framework bas "letting them play" karta hai.

- **Do types ke runtime:** Runtime = wo "world" jisme agents interact karte hain. Do kinds:
  - **Standalone** — simple, aapke apne box pe run hota hai. (Aaj ka topic.)
  - **Distributed** — **remote agents** ek dusre se interact kar sakte hain, potentially duniya bhar se. (Kal ka topic — gRPC wala.)
  - Dono ko thoda alag tarike se code karte hain.

- **Ed ka disclaimer — high-level hi rahenge:** Ed honestly bolte hain ki ye section **breeze through** hoga, examples **superficial** rahenge. Reason: kaafi frameworks pe already deep detail ho chuki hai (LangGraph waale level pe nahi jayenge), aur AutoGen Core har kisi ke use case pe directly applicable nahi. Goal = **flavor dena**, ecosystem me iski **positioning** samjhana. Agar relevant lage to khud **R&D** karo — Ed starting points denge. Aur haan, sabko **MCP** (Week 6) ka intezaar hai, isliye fast move karenge.

- **Lab 3 — AutoGen Core:** Cursor me 5th folder (AutoGen), **lab 3**. Ye ab tak ke sab labs se **different** hai. Imports + good old `load_dotenv()`, kernel restart karke fresh start.

- **Step 1 — apna Message object define karo:** Sabse pehle hum **apna khud ka message object** banate hain — information ko agents ke beech transport karne ke liye. Ye ek **`@dataclass`** hai:
  - Dataclass = aisi class jisme **methods nahi, sirf data** hota hai — makes sense, kyunki message ka kaam functionality nahi, **information transport** karna hai.
  - **LangGraph ka parallel:** LangGraph ek **state machine** hai, to wahan sabse pehle **State** define karte the. AutoGen Core ka fundamental idea **messaging** hai, to yahan sabse pehle **Message** define karte ho. Framework ki philosophy uske first define hone wali cheez se jhalakti hai.
  - Aaj ka message super simple: ek hi field — `content: str`. Lekin aap experiment kar sakte ho — much more **sophisticated** messages with all sorts of fields.

- **Step 2 — Core agent ≠ AgentChat agent (tongue twister alert):** Jo agent hum AutoGen Core me banane wale hain, wo **AgentChat ke `AssistantAgent` se bilkul different** hai:
  - Core agent ek **wrapper / management object** hai — "ye ek cheez hai jise message kiya ja sakta hai, create kiya ja sakta hai, manage kiya ja sakta hai, refer kiya ja sakta hai".
  - **Iske andar kya hota hai, wo aapki responsibility hai** — aap kisi cheez ko delegate karoge (LLM ho, AgentChat agent ho, ya plain code).
  - Ye **na LLM hai, na AgentChat agent** — bas ek management holder object.

- **AgentId = type + key:** Har agent ka ek **unique ID** hota hai jiske **do parts** hain — **type** aur **key**:
  - **type + key ka combination unique** hai aur agent ko precisely identify karta hai.
  - Distributed runtime imagine karo — duniya bhar se agents collaborate kar rahe hain, lekin **har ek ka unique type+key** hai. Koi bhi agent kisi dusre se baat kar sakta hai agar uska **name/ID (type + key)** pata ho.
  - Ye aapko system ke **"fabric"** ka sense deta hai.

- **Step 3 — pehla Core agent: `SimpleAgent`:**
  - **`RoutedAgent` ka subclass** — ye typical parent/superclass hai jo aap use karte ho.
  - Sirf **do methods**:
    1. **`__init__`** (constructor) — bas parent ko apna naam pass karta hai: `"simple"`. That's it.
    2. **`on_my_message`** — ek **async coroutine**, jo **`@message_handler`** se decorated hai. **Yahi decorator matter karta hai.**

- **`@message_handler` kaise kaam karta hai:**
  - Jo bhi method aap `@message_handler` se decorate karte ho, wo **potentially messages receive** kar sakta hai.
  - AutoGen Core handle karta hai ki ye **register** ho jaye aur **runtime** ise manage kare.
  - Agar koi mere **name + ID** pe message bhejta hai, to wo **yahan land karega** — *lekin tabhi* jab dispatch kiya gaya message **isi class ka ho** (signature match).

- **Pro feature — dispatch by type signature:** Aap **multiple message classes** bana sakte ho aur har type ke liye alag handler:
  - Example: ek **TextMessage** aur ek **ImageMessage**, do **separate handlers**.
  - Sirf **different method signatures** ki wajah se AutoGen Core **automatically right message ko right method (right coroutine) pe dispatch** karega.
  - "It's all about dispatching messages properly" — yahi framework ka core kaam hai.

- **SimpleAgent ka behaviour:** Message receive karta hai, message return karta hai (LangGraph nodes ka parallel — wahan state in/state out, yahan **message in/message out**):
  - Is agent me **koi LLM nahi, koi AI nahi** — pure code.
  - Wo apne **ID/key** se khud ko identify karta hai aur input ko replay karta hai: *"This is <id>. You said <input>... and I disagree."*
  - Ed mazak me bolte hain — ise **"disagreeable agent"** bulana chahiye tha.
  - Point: AutoGen Core ko **farak nahi padta** ki andar LLM hai ya plain code — **use sirf message handling se matlab hai**.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Decoupling (Core idea)** | Agent ki logic alag, message delivery alag — framework sirf delivery + lifecycle dekhta hai, logic aap likhte ho |
| **Runtime** | Wo "world" jisme agents create, manage aur message hote hain |
| **Standalone runtime** | Simple, single-machine runtime — aapke box pe locally chalta hai |
| **Distributed runtime** | Remote agents (potentially worldwide) ko interact karne deta hai — gRPC based, agla lecture |
| **Message (dataclass)** | Aapka khud ka data-only object jo agents ke beech information transport karta hai — Core me sabse pehle yahi define hota hai |
| **`@dataclass`** | Methods-less class, sirf data fields — message ke liye perfect kyunki functionality nahi chahiye |
| **Core agent vs AgentChat agent** | Core agent = management wrapper (messageable, creatable, manageable), LLM nahi — AgentChat ka AssistantAgent isse bilkul alag cheez hai |
| **AgentId (type + key)** | Har agent ka 2-part unique ID — type+key combination se duniya ka koi bhi agent precisely address ho sakta hai |
| **RoutedAgent** | Typical superclass jise subclass karke aap Core agent banate ho — routing/dispatch capability deta hai |
| **`@message_handler`** | Decorator jo kisi async method ko message receiver bana deta hai — runtime ise register + manage karta hai |
| **Dispatch by type signature** | Multiple message classes + multiple handlers — method signature dekh ke Core khud sahi handler pe message bhejta hai |
| **SimpleAgent** | Lecture ka demo agent — no LLM, bas "You said X... and I disagree" reply karta hai (the "disagreeable agent") |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Ye pura pattern Actor Model hai** (Erlang/Akka/Orleans waala): har agent ek actor — apna mailbox, async message receive, runtime hi creation/lifecycle/delivery own karta hai. **AgentId (type+key)** bilkul Orleans ke **grain identity** ya Kafka ke **(topic, partition-key)** jaisa addressing scheme hai — type = "kaun si class ka actor", key = "kaun sa instance". Aap RabbitMQ/Kafka consumers likh chuke ho, to "broker delivery handle karta hai, handler logic aap likhte ho" wala separation ghar jaisa lagega.

- **`@message_handler` + dispatch by type signature** = Python me **`functools.singledispatch`** ka framework-managed version, ya Java/C# ke **method overloading-based routing** jaisa. Web framework analogy: jaise FastAPI me route decorator + Pydantic type se request sahi handler pe jati hai, waise hi yahan message ki **dataclass type** hi "route" hai. TextMessage vs ImageMessage → alag handlers, zero if/else.

- **Core vs AgentChat layering** ko aise socho: Core = **asyncio event loop + message bus** (infrastructure), AgentChat = **uske upar built high-level framework** (jaise Django ORM vs raw DB driver). Core agent me LLM hona optional hai — wo bas ek **messageable unit** hai, andar plain function bhi chal sakta hai. Ye testing ke liye bhi sweet hai: LLM-less SimpleAgent jaise deterministic actors se pura message-flow unit-test ho jata hai.

- **Hands-on lab:** is lecture ka code khud chalane ke liye **`Practical/lab3_autogen_core_rps.py`** run karo (is repo me, `uv run` se chalta hai, **Groq pe free** via `OpenAIChatCompletionClient` + `base_url` + `ModelInfo`). Ek difference: hum **AutoGen 0.7.5** pe hain (course 0.5.1, same API family) — RoutedAgent/message_handler/AgentId ka API identical hai, bas version naya.

---

## 🧠 Takeaway (yaad rakho)

1. **AutoGen Core = decoupling:** framework sirf agent **lifecycle + message delivery** handle karta hai; **logic aapki responsibility** hai.
2. **Do runtimes:** **standalone** (local, simple — aaj) aur **distributed** (remote agents, gRPC — kal); dono thode alag code hote hain.
3. Core me sabse pehle **Message dataclass** define karo (LangGraph me State define karne ka parallel) — data-only transport object.
4. Core agent = **RoutedAgent subclass** + **`@message_handler`** decorated async coroutines; ye **management wrapper** hai, LLM nahi — har agent ka unique **AgentId = type + key**.
5. **Dispatch by type signature:** alag message classes ke liye alag handlers banao, Core **method signature dekh ke automatically** sahi coroutine pe message bhejta hai — "it's all about dispatching messages properly."

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

So here's the core idea behind Autogen core. And I've already alluded to this idea, and it's that it's all about decoupling the logic of an agent, what it actually does from how messages get delivered to it, from the interplay between them. The framework deals with creating and communicating. It deals with creating agents, the whole life cycle of an agent, and the messages, the communication between them and the agents themselves or us as the people coding the agents. We're responsible for the logic. It's not the mandate of Autogen core. It just deals with with letting them play.

And there's two ways that it lets them play. Two types of runtime. The runtime is the kind of world in which agents interact and the two types. One of them is called standalone, which basically essentially means it sort of runs on your box in a simple way. And the other distributed is that it runs in a way that could allow remote agents to interact with each other. So these are the two kinds, and you code them both a bit differently. We are going to look at the standalone one today, and we're going to go to the distributed one tomorrow.

And look, I have to tell you, I'm only going to do this at a high level. We're going to breeze through this quite quickly and the examples will be somewhat superficial. And there's a reason for this. I feel like we've done enough detail on lots of frameworks and actually building agents. I'm not sure how applicable this is going to be to your use case. I think it's good for you to get a feel for it, and to get a good sense of how this is positioned and where it might be useful. And that's my goal. Give you a flavor, give you, give you that kind of sense of where it fits in the ecosystem and if it's relevant for you, if this is something that you do want to put into practice, then you should carry out more R&D and work on this a bit more yourself. And I'll give you plenty of starting points for that. But I'm not going to go so deep into this as some of the other frameworks as like LangGraph last time, but enough so you get a feel for it. And then and then we, uh, we, we move on because I know you're anxious to get to MCP.

All right. Let's let's do a lab. So here we are in good old Cursor going to the fifth folder for Autogen, and we are going to lab three Autogen core. Uh, so this this is where we begin. Uh, there's, there's, as I say, something a little different. This is going to be different to anything we've looked at before. Um, okay. So there's a bunch of, uh, imports, including a good old, uh, load dot env. Let me just restart this, make sure it's fresh. Do, uh, do the load dot env.

All right. So the first thing we do is we define our own object which is going to be used for passing information around the place, our own message object. And it is a type of, uh, I don't know if it's if this is required, but a dataclass means it's a class that's not going to have any methods. All it is, is something that holds data in, uh, and that makes sense because the message is not going to be something with functionality. It's going to be used to transport information between our agents. And in a way, like doing this is sort of analogous to when we were in LangGraph. We started by defining a state. LangGraph is a state machine. It's very focused on what is the state and making sure that that's something that you can move backwards and forwards in. And it's interesting that, you know, Autogen core's fundamental idea is all about messaging. And so the thing that you start by defining is your message. And in our case, we're going to have a very simple one that just has one field which is content, which is a string. But you can experiment with what you pass between your agents being something much more sophisticated with all sorts of different bits of information. So there we have it. We have a message with a string, and that's all the message we'll be using for today.

So now we get to define our agent in Autogen core. And it's important to bear in mind that the agent that we're about to create in Autogen core is different to the agent that we just created in Agent Chat. It's different. It's like a tongue twister to say all of this. It's hard to keep your mind on it. You're like, what? How is it different? Well, look, the agent that you define in Autogen core is just like a wrapper. It's like saying this is a thing that can be messaged, it can be created, it can be managed, it can be referred to and it can be messaged. But what you do with this is your responsibility and you're going to have to delegate to something. But this, this, this is like a management object, if you will, a management object which you're going to use.

And it has amongst other things, it has an agent ID and every agent has a unique ID, and that ID has two, two parts to it, a type and a key. So every single agent has a type and a key. And that combination of type and key is then unique and can uniquely identify it. So if you imagine when we in the future look at a distributed runtime in that runtime, there could be agents from from all over the world collaborating in this distributed runtime, but every one of them will have a unique type plus key that that identifies it precisely, and any agent will be able to talk to another one if it knows it's its name and its ID, or its key and its type. So this gives you a sort of good sense of the fabric of it, and that an agent class that you make is not actually an LLM. It's not an Autogen agent chat agent. It's just this management holder object, something which has a type and a key.

So here is our first Autogen core agent. It's called Simple Agent. As you will see it is a subclass of something called RoutedAgent, which is the typical the thing that you that you have as your as your parent as your superclass. And it only has two, two methods. One of them is the init that the constructor. And all it does is it calls its its parents passing in its name. Simple. That's all it does. Then it has another, uh, method called on my message, which is an async. Uh, so it's a coroutine. It's an async method. It is an async coroutine. It is a coroutine. Uh, and it's decorated with message_handler. And that's what matters. Any method that you decorate with message_handler means that potentially this is something that will receive messages and Autogen core handles. The fact that you'll be able to register this, and a runtime is going to manage this. And if someone sends a message to something with my name and my ID, then it's going to end up here. At least it's going to end up here. If what they dispatch is a message of this class.

So this is a bit of a pro thing, but you can have multiple different classes and you can use that to be able to handle different types of message. Uh this may be more detail than you need, but you you could, for example, have a text message and an image message and have two separate handlers. And just by virtue of the different signatures, the different method signatures, Autogen core will automatically dispatch the right message to the right method, the right coroutine. That's that's what it does. It's all about dispatching messages properly.

Uh, and so this, this simple, uh, agent is going to return a, it's going to receive a message and it's going to return a message is now that I said it is a bit like this idea that in LangGraph we, uh, took in our nodes, took a state and returned a state. But this is just like a parallel thing. But it's all about messages. It receives a message, and it. And it returns a message. Um, and it's an async. It's a coroutine, as I said. So it receives a message. And this one isn't going to do anything with the message it receives. There's no LLM, there's nothing here. It simply returns, uh, a message which has this is and gives my ID and my key. So it's sort of identifying itself as saying this is blah, blah, blah. You said and I'm going to I'm going to replay back what what the person said. So I do actually I do, I do use this. You said blah blah blah and I disagree. Uh, so that is simple agent. Maybe I should call it a disagreeable agent. Uh, that's that's what it does. There's no LLM there's no AI involved in this at all. It's, uh, you know, it's just a piece of code, but that that doesn't matter to Autogen core. Autogen core just cares about the handling of messages.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
