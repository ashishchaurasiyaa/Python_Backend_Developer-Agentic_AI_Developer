# L100 — Day 3: Agent Registration and Message Handling

> **Week 5 — AutoGen** · ⏱️ ~9m · 🎥 Lecture 100 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821629

---

## 🎯 Ek Line Mein (TL;DR)

Autogen core ka asli "meat": ek **SingleThreadedAgentRuntime** banao, agent ko **register()** karo (instance nahi — sirf **type + factory**), **AgentId (type + key)** se address karo, aur **send_message()** bhejo — runtime khud message ko sahi agent ke sahi **message handler** tak **type ke basis pe route** kar deta hai; LLM lagana tumhara kaam hai, core ka nahi.

---

## 📝 Hinglish Explanation (Detailed)

- **Runtime banana:** Ed ek **`SingleThreadedAgentRuntime`** create karte hain — ek **standalone runtime** jo local machine pe chalta hai aur agents ko **single-threaded** tarike se handle karta hai. (Distributed/gRPC wala version baad me aayega — yahan sirf local.)
- **`register()` — sabse important nuance:**
  - Hum **agent class pe hi `register()`** call karte hain — "runtime, main is type ka agent hoon, mujhe jaan lo."
  - **Ye agent CREATE nahi karta!** Ye sirf bolta hai: *"`simple_agent` naam ka ek agent TYPE exist karta hai jo spawn ho sakta hai."*
  - Register me 3 cheezein jaati hain: runtime, **type ka naam** (string, e.g. `"simple_agent"`), aur ek **factory function** — ek function jo naye instances **instantiate** kar sakta hai. Runtime baad me jab zaroorat ho, is factory se agent bana lega (**lazy instantiation**).
- **Runtime start:** `runtime.start()` — ab ye ek "proper runtime" hai, messages ke liye ready.
- **AgentId — type + key ka pair:**
  - Agent ko address karne ke liye ek **`AgentId`** object banta hai: **type** (e.g. `simple_agent`) + **key** (e.g. `"default"`).
  - `"default"` key maangne se runtime ensure karta hai ki us type+key ka **ek agent actually create ho jaye** (factory chal jaati hai agar pehle se instance nahi tha).
- **Pehla message:** `send_message()` se "Well hi there" bheja agent ko. Reply aaya: *"This is simple_agent default. You said 'Well hi there' and I disagree."* — type (`simple_agent`) + key (`default`) dono reply me dikh rahe hain. Charming.
- **Autogen core ka core philosophy (Ed ka punchline):**
  - Agent ke andar **LLM call karna, functionality dalna — wo TUMHARA kaam hai**, Autogen core ka nahi.
  - Core ka kaam: **messages ko type + ID ke basis pe lookup karke sahi jagah pahunchana**. Bas. Ye routing/dispatch hi framework ki value hai.
- **Ab LLM-backed agent — `MyLLMAgent`:**
  - Abhi bhi **RoutedAgent ka subclass** — koi naya infra nahi, "the fact that we're calling an LLM is almost of no consequence to the Autogen core framework."
  - LLM call karne ke liye seedha OpenAI client bhi use kar sakte the, lekin **Autogen AgentChat** use karte hain (autogen week hai, why not).
  - **`__init__`:** superclass call + ek **model client** (GPT-4o-mini) banao + ek **`AssistantAgent`** banao (name + model client — same as Day 1/2) aur usse **`self._delegate`** field me rakh lo.
  - **`_delegate` naming:** underscore prefix = "private" convention (Java ke `private` jaisa) — ye wo underlying object hai jisko hamara core agent **delegate** karega jab actual LLM-soch chahiye hogi. Delegate ki jagah kuch bhi ho sakta tha (random replies bhi).
- **Message handler — naam kuch bhi rakho, TYPE matter karta hai:**
  - Handler ka naam `handle_my_message_type` — Ed ne jaan-bujh ke aisa naam rakha taaki clear ho: **function ka naam irrelevant hai; jo matter karta hai wo hai message parameter ka TYPE**.
  - **Autogen core automatically route karta hai**: jis agent ke paas us message-type ka handler hai, message wahan deliver hota hai. Yahi "clever routing" hai.
  - **Direct send vs pub-sub:** abhi hum direct `send_message` kar rahe hain (specific AgentId ko), lekin core me ek poora **pub-sub system** bhi hai — **topics subscribe** karo, message **publish** karo, aur sab interested agents ko mil jayega.
  - In trivial examples me ye routing khud bhi code kar sakte the — lekin framework isliye, kyunki yahi cheez **scaled aur distributed** tarike se bhi chal sakti hai.
- **Confusing part — do alag "message" types:**
  - **`Message`** (hamara apna core dataclass) — jo Autogen core runtime ke through travel karta hai.
  - **`TextMessage`** — ye **Autogen AgentChat** ka message hai (wahi jo Day 1-2 me use kiya tha), jo `_delegate` (AssistantAgent) se baat karne ke liye chahiye.
  - Ed tip dete hain: clarity ke liye import ko `as AgentChatTextMessage` jaisa alias de sakte ho taaki **core vs agentchat** ka confusion na ho.
- **Handler ka flow:** core `Message` aaya → print "I received a message" → content se ek AgentChat **`TextMessage`** banao (`source="user"`) → `self._delegate.on_messages([text_message], cancellation_token)` call karo (wahi purana AgentChat pattern + **cancellation token**) → reply ka content nikalo → ek **naya core `Message`** bana ke return karo.
- **Final demo — do agents, ek relay:**
  - Naya runtime banao, **dono agents register** karo: `simple_agent` (LLM nahi — bas har baat se **disagree** karta hai) aur `LLM_agent` (jo `_delegate` se real **GPT-4o-mini** tak dispatch karta hai).
  - Runtime start → "Hi there" **LLM agent** ko bhejo → reply: *"Hello! How can I assist you today?"* (classic GPT-4o-mini) → wahi reply **forward karo simple agent ko** → *"This is simple_agent default. You said 'Hello! How can I assist you today?' And I disagree."*
  - "And with that, we will stop this pantomime." — demo complete: core = pure message plumbing, LLM = optional payload.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **SingleThreadedAgentRuntime** | Local, standalone runtime jo agents ko single thread me host/manage karta hai |
| **register()** | Agent CREATE nahi karta — runtime ko batata hai ki ye TYPE exist karta hai + factory deta hai |
| **Factory function** | Wo function jo naye agent instances bana sakta hai — runtime zaroorat pe isse call karta hai |
| **Agent type vs instance** | Register = type declare karna; instance tab banta hai jab AgentId se demand hoti hai |
| **AgentId** | Agent ka address = **type + key** (e.g. `simple_agent` + `default`) |
| **send_message()** | Runtime ke through kisi specific AgentId ko direct message bhejna |
| **RoutedAgent** | Core ka base class — subclass karke `__init__` + message handler likhte ho |
| **Message handler** | Function ka naam irrelevant; **message ke TYPE** se routing hoti hai |
| **Type-based routing** | Core ka clever kaam — message type dekh ke sahi agent ke sahi handler tak dispatch |
| **Pub-sub (topics)** | Direct send ke alawa: topics pe subscribe/publish — ek message, kai interested agents |
| **_delegate** | Underscore = private convention; core agent jo AgentChat AssistantAgent ko LLM-kaam delegate karta hai |
| **TextMessage vs Message** | TextMessage = AgentChat ka (delegate ke liye); Message = hamara core dataclass (runtime ke liye) |
| **on_messages() + cancellation token** | AgentChat AssistantAgent ko invoke karne ka wahi Day 1-2 wala pattern |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **`register(type, factory)` = DI container registration:** ye bilkul waise hai jaise Spring/FastAPI DI me aap class register karte ho aur container lazily instantiate karta hai. Type-string = service name, factory = provider function. `AgentId(type, key)` ka key actor-model ke **actor address** jaisa hai — Akka me `ActorRef`, ya Kafka me partition key se ek hi consumer pe sticky routing.
- **Type-based handler dispatch = typed message queues:** "function ka naam irrelevant, message ka TYPE routing decide karta hai" — ye RabbitMQ me exchange/routing-key binding, ya Python me `functools.singledispatch` jaisa hai. Aur pub-sub topics wala part to seedha Kafka topics + consumer groups mental model hai — isi liye ye design **distributed (gRPC) runtime** pe bina code badle scale hota hai.
- **`_delegate` = adapter/composition pattern:** core agent ek thin actor-shell hai jo asli kaam AgentChat `AssistantAgent` ko delegate karta hai — composition over inheritance. Do message types (core `Message` vs agentchat `TextMessage`) ka boundary-translation bilkul waisa hai jaise aap API DTO ko internal domain model me map karte ho; `import ... as AgentChatTextMessage` alias = namespacing hygiene.
- **Hands-on lab:** is lecture ka code khud chalane ke liye `Practical/lab3_autogen_core_rps.py` run karo (is repo me, `uv run` se chalta hai, Groq pe free via `OpenAIChatCompletionClient` + `base_url` + `ModelInfo`). Difference sirf itna: hum AutoGen **0.7.5** use karte hain (course 0.5.1, same API family) aur GPT-4o-mini ki jagah Groq ka free model — register/AgentId/RoutedAgent/handler flow bilkul same hai.

---

## 🧠 Takeaway (yaad rakho)

1. **register() ≠ create** — sirf type + factory declare hota hai; instance tab banta hai jab `AgentId(type, key)` se demand aati hai (lazy, factory-driven).
2. **AgentId = type + key** — `simple_agent` + `default` jaise pair se har agent uniquely addressable hai.
3. **Autogen core ka kaam sirf plumbing hai** — type + ID dekh ke message sahi handler tak pahunchana; LLM/functionality dalna aapka kaam hai.
4. **Handler ka naam irrelevant, message ka TYPE sab kuch hai** — aur direct send ke alawa pub-sub (topics) bhi available hai.
5. **LLM lagana = bas ek `_delegate` AssistantAgent** — core `Message` ↔ agentchat `TextMessage` translate karo, `on_messages()` + cancellation token se call karo, reply wapas core `Message` me lapet do.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Okay, so now we get to the meat of Autogen core. We are going to create a runtime, a SingleThreadedAgentRuntime it's called, which is a standalone runtime running on my computer, which as it says, will handle agents in a single threaded way. And the first thing that we're going to do is register. We call register on the agent itself to say, I want you to register yourself with this runtime. Now, this isn't creating an agent. This is just saying you are a type of agent. And I want you to tell the runtime that you are a type of agent that can be spawned, you can be created, and you are a type of agent of type simple agent that's going to be your type. And this, this thing here, this is a function which can generate new versions of you. It can instantiate you. It is a factory. And you pass that in as well. And so I will do this. It's now created a runtime and it's created a type of agent called a simple agent. We haven't actually yet built any of these. We haven't instantiated one. But the as a type of agent is now a known thing to our runtime. Our runtime knows that there are such things as simple agents. And we're now going to start our runtime. It is now running. It is a it is a proper runtime.

And now we are going to uh, we're going to first of all create an AgentId object to identify an agent. And we'll we'll do this properly. We'll say agent ID equals that, that is an ID that would identify this. And we are going to say that we want the default agent. Uh, because, because that, that will then, uh, we'll make sure that we have an agent created, and then we're going to send a message to, we're going to send a message to the, to the agent, which is called simple agent, The default ID and we're going to send a message. Well hi there to it. And then we will print whatever comes back. So any ideas what's going to come back I wonder. Uh, so uh it replied this is simple agent default. So it's simple agent is its type, which is the same one we registered and it default is the, uh, the, the key uh, and it said, you said, well hi there. And I disagree. Charming.

Uh, and that is uh, that's it. So there is a demo of Autogen core and that's what Autogen core does. And putting in agent functionality like having code in there that calls LLMs. That's your job or my job. That's not Autogen core's job. What it's there to do is to handle the passing of messages around by looking things up based on their type and their ID, and that's what it does.

So now I'll show you one which has an LLM behind it, but it shouldn't be any surprise to you because it's just the same infrastructure. The fact that we're calling an LLM is is almost of no consequence to, to, uh, the Autogen core framework. So what we're going to do is we're going to make a slightly more interesting one called my LLM agent, still a subclass of RoutedAgent. And we're going to use a proper LLM. And we could just call OpenAI directly using OpenAI dot create. We could just call the Python client library. But we can also use Autogen agent chat and we might as well since it's autogen week. So this is the same kind of thing, a subclass of RoutedAgent that's going to be two functions again init and handle my message. So the init just just calls the superclass. But it then creates a model client. But this could be doing anything. But this is the Autogen agent chat way. We're going to create one of these things, a GPT-4o mini model client. And we're going to set a field called underscore delegate, which we're just sort of holding on to. This is this is the the underlying. This is what our agent object is going to delegate to when it actually needs some code, some, some an LLM to run. And we could have anything we want. We could, we could do we could reply back with random things or we could create an instance of assistant agent. And that's what we're going to do. And that's where we put in. If you remember, when you create an assistant agent, there's the name of the agent and there's the model client, and there it is. And as a result in underscore delegate underscore often used to show sort of like private secret, uh, variables that other people should know about, like, like private in the, in the Java world. Um, so the this is being set to an assistant agent.

So, uh, now we just have to write our message handler. And as I say, it can be called anything you like. I'm calling it handle my message type. Um, and that's really to sort of draw your attention to the fact that what matters is what type of object comes in the message field, because Autogen core will automatically route messages to agents that should receive them based on the the finding a handler that that looks for a message of that type. That's how it works. That's the clever routing that it does. And by the way, you can send a message direct to an agent, which is what we're doing right now. But it also has a whole kind of pub sub thing there where you can subscribe to topics and you can publish out messages to lots of agents that are all interested in one particular topic. So the whole process of dispatching messages to the right agent and then calling the right handler, that's the clever stuff. That's what it does well. And why why we use a framework like this rather than coding it ourselves. But for some of these examples, it's pretty trivial. So we could equally code it ourselves. But you can imagine that this is done in a way that can be scaled and distributed.

So anyways, handle my message type. Uh, as long as, uh, message is sent to this agent with the ID and and type, and that the object that's sent is of this type, it will arrive at this function. And I'm going to say that I received a message and print the content. Then I'm going to now now this is confusing. This object here TextMessage looks subtly different to this object here. Message. Uh, do you know what's going on here? This TextMessage is text message from the, um, Autogen. It's this thing here. It's the agent chat messages. The TextMessage. The same thing we were using yesterday and the day before when we were interacting with agent chat agents. So this is a Autogen agent chat, uh, message, which can be a bit confusing. And you might. Yeah, there are ways you could you could get around that by, by giving it a different you can say like as agent chat text message if you wanted to to like make it so the code is a little bit clearer and you're distinguishing between the Autogen core and the Autogen agent chat.

All right. Anyways, so sorry. Back we go. So we create the sort of text message that you need for Autogen agent chat passing in the content of our message and the source is user. And this is the on_messages that we call in agent chat land with this text message and the cancellation token if you remember that thing. And then we get back the content. We say that that was the reply. And we return a new instance of message of our message, with the content being that reply. I hope you followed all that, or at least got enough of an idea of it.

Let's give this a shot. Let's create a new runtime, a single threaded agent runtime, standalone runtime. We're going to register two agents the simple agent and the LLM agent. The new one, Simple Agent, isn't really an LLM at all. It just disagrees with whatever it's told. And LLM agent is actually going to dispatch through this underscore delegate down to a true GPT-4o mini. So we're going to start the runtime. Then we are going to send a message. Hi there to the real agent. And with whatever it replies we're going to send that. We're going to forward that on to the other agent, to the simple agent and see what comes out there. So the LLM agent received hi there. And it said hello, how can I assist you today? A classic GPT-4o mini response. And, uh, the simple agent said, this is simple agent default. You said, hello, how can I assist you today? And I disagree, and there you go. Um, and with that, we will we will stop this pantomime.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
