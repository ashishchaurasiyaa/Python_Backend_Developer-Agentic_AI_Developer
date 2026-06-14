# L103 — Day 4: Distributed AI Agents with gRPC Runtime

> **Week 5 — AutoGen** · ⏱️ ~10m · 🎥 Lecture 103 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821641

---

## 🎯 Ek Line Mein (TL;DR)

Autogen Core ka **distributed runtime**: ek **gRPC host** + **worker runtimes** ka combo, jisme kal wala SAME **RoutedAgent** code **bina ek line change kiye** alag-alag processes (ya even alag languages) me distributed chal jaata hai — agents ko pata hi nahi ki messages ab **gRPC** se network par ja rahe hain.

---

## 📝 Hinglish Explanation (Detailed)

- **Setup:** Ed Cursor me wapas hai, folder 5 (Autogen), **lab 4 — Autogen Core Distributed**. Ye sirf ek **teaser/flavor** hai kyunki Microsoft khud kehta hai ki ye distributed runtime abhi **experimental** hai — Ed sure nahi hai ki ye sabke liye relevant hoga, isliye deep dive nahi, sirf overview. (Agar zyada detail chahiye to usko note bhejo, wo aur content bana dega.)
- **Do modes:** Notebook me ek **flag** hai — `ALL_IN_ONE_WORKER` type ka — `True` matlab **all-in-one worker** (saare agents ek hi worker me), `False` matlab **multiple workers** (agents alag-alag workers me). Is lecture me pehle `True` wala run dikhaya gaya.
- **Message class:** Imports + `.env` load karne ke baad wahi **Message dataclass** define hoti hai jo pehle thi. Ed kehta hai ye **LangGraph ke State ka analogy** hai — bas yahan ye batata hai ki agents **aapas me kaise interact** karte hain (message contract), shared state nahi.
- **Distributed runtime = 2 parts: Host + Worker(s).**
  - **Host:** `GrpcWorkerAgentRuntimeHost` (autogen ext ke gRPC runtimes se) — ye **gRPC** (remote procedure call) use karke messages bhejta hai. Host **localhost:50051** par chalta hai aur `.start()` se running ho jaata hai.
  - **gRPC kya hai:** Ek **cross-language** technique jisme tum directly **ek function se doosre function ko call** kar sakte ho across process boundaries — "REST HTTP calls jaisa, par function-to-function". Industry me har jagah use hota hai jahan interactive messaging ko process boundaries cross karni hoti hai.
- **Old friend wapas — Serper tool:** **Serper search API** wala internet-search tool wapas aata hai, lekin **LangChain ke through**: pehle `GoogleSerperAPIWrapper` banao, usse ek **LangChain tool** banao, fir usko **LangChain tool wrapper** (autogen ext ka adapter) me wrap karo — ab wo ek **Autogen tool** ban gaya. Yaani LangChain ecosystem ke tools ko Autogen me reuse karne ka pattern.
- **Use case — frivolous se commercial:** Ed pehle distributed **rock-paper-scissors** karwane wala tha, par wo frivolous lagta; stock price comparison bhi socha par wo aage ek poora week aa raha hai. To final scenario: ek **business decision** — *"kya hume naye AI agent project me Autogen use karna chahiye?"*
  - **Agent 1 (player1):** web searches se Autogen ke **pros** research kare.
  - **Agent 2 (player2):** Autogen ke **cons/drawbacks** research kare.
  - **Judge agent:** dono ki research ko milake **decision + brief rationale** de — purely apni agent team ki research ke basis par.
  - Structure rock-paper-scissors jaisa hi hai: instruction 1, instruction 2, aur judge jo final call karega.
- **Agents — kal ke code ka copy-paste:** Player1/Player2 **RoutedAgent** classes bilkul kal jaisi hain (Ed khud kehta hai "this is basically a copy-paste job"). Do changes:
  - Dono ke liye **GPT-4o mini** use ho raha hai (ollama hata diya kyunki quality same nahi thi — fair comparison ke liye dono ko same model).
  - Player agents ko **Autogen Serper tool** pass kiya gaya hai + **reflect on tool use** on hai.
  - Ed admit karta hai ki technically **player1 aur player2 ki alag classes ki zaroorat nahi** — ek hi class me prompt se pros/cons switch ho sakta tha. Par do alag classes rakhi hain taaki tum chaaho to ek agent me **DeepSeek** jaisa doosra model laga sako.
- **Judge agent:** Wahi pattern — ek delegate **underlying LLM**, aur **@message_handler** decorated method jo dono messages collect karta hai, **player1 & player2 ko lookup** karta hai (type+key se), fir `self.send_message(...)` call karta hai. **Ye code kal ke local runtime wale code se identical hai.**
- **⭐ THE BIG POINT — code distributed hona "jaanta" nahi:**
  - Agent code me **kahin bhi distributed ka zikr nahi** — ye ab bhi rock-paper-scissors ho sakta tha. Hum bas `self.send_message` call karte hain.
  - Pehle (local runtime me) ye call basically Python ke direct if-statement-style dispatch se `handle_my_message` ko call karti thi; **ab wahi call gRPC ke through remotely** hoti hai, distributed runtime orchestrate karta hai — par humare liye **completely transparent** hai.
  - Agents alag **processes** me chal sakte hain, even alag **programming languages** me likhe ho sakte hain — messages ki saari stitching Autogen Core karta hai, sirf player1/player2 **AgentId lookup** ke basis par. **Yahi Autogen Core distributed ki power hai.**
- **All-in-one worker run (flag = True):**
  1. Ek naya **GrpcWorkerAgentRuntime** (worker) banao aur usse **host** (localhost:50051) par point karo, fir worker `.start()` karo.
  2. Us worker ke saath **3 agents register** karo — player1, player2, judge — registration me **factories** dete ho jo agents create karengi.
  3. Judge ka **AgentId** collect karo.
  4. Pehle jaisa hi **"go" message** judge ke AgentId par `send_message` karo.
- **Result:** Messages "fly" hote hain — GPT-4o mini do alag agent calls me pros aur cons nikaalta hai, judge sab combine karta hai.
  - **Pros:** memory, coherent context, ease of development, **scalability** (jo hum khud experience kar rahe hain), versatile applications.
  - **Cons:** limited AI capabilities, less customizable, less structured, potential bugs, lower-end models ke saath performance issues.
  - **Decision:** *"Recommend using Autogen"* — purely team research ke basis par.
- **Cleanup:** End me **workers stop** karo aur **host stop** karo. Bas — tumne distributed Autogen Core experience kar liya. (Multiple-workers wala mode — flag `False` — agla demo hai.)

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **gRPC** | Google ka high-performance RPC framework — cross-language, function-to-function calls across process boundaries; "REST jaisa par direct function call feel" |
| **GrpcWorkerAgentRuntimeHost** | Distributed setup ka **host** — central hub jo localhost:50051 par chalta hai aur saare workers ke beech messages route karta hai |
| **GrpcWorkerAgentRuntime (worker)** | Ek **worker runtime** jo host se connect hota hai; agents isi ke saath register hote hain (factories ke through) |
| **All-in-one worker vs multiple workers** | Flag se control: saare agents ek worker me, ya alag-alag workers (alag processes) me — agent code dono me SAME |
| **RoutedAgent** | Autogen Core ka base agent class — `@message_handler` methods par messages route karta hai |
| **@message_handler** | Decorator jo batata hai kaunsa method incoming message handle karega (type signature se dispatch) |
| **AgentId (type + key)** | Agent ka address — judge isi se player1/player2 ko lookup karke `send_message` karta hai |
| **Factory registration** | Agent register karte waqt class nahi, ek **factory function** dete ho jo agent instance banata hai |
| **LangChain tool wrapper** | Adapter jo LangChain ke tool (yahan `GoogleSerperAPIWrapper` wala search tool) ko **Autogen tool** bana deta hai |
| **Serper** | Google search API — agents iske through web research karte hain (pros/cons of Autogen) |
| **Message dataclass** | Agents ke beech ka contract — LangGraph ke State ka rough analogy, par interaction describe karta hai |
| **Experimental** | Microsoft khud distributed runtime ko abhi experimental bolta hai — isliye sirf flavor/teaser |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Hamara lab3 `SingleThreadedAgentRuntime` use karta hai — aur yahi is lecture ka punchline hai:** SAME RoutedAgent/`@message_handler`/`send_message` code **bina kisi change ke** gRPC distributed runtime par chal jaata hai; runtime swap karo, agent code untouched — yahi Autogen Core ka selling point hai. (Hamare labs ye gRPC wala part SKIP karte hain — experimental + extra deps.)
- **Ye classic actor model hai, Kafka/RabbitMQ vibes ke saath:** AgentId (type+key) = routing key/queue address, host = broker, workers = consumers, `send_message` = produce. Fark ye ki yahan **request-reply RPC semantics** bhi transparent hai — tumhe correlation IDs ya reply queues khud manage nahi karne padte.
- **gRPC vs REST jo tum jaante ho:** HTTP/2 + protobuf, binary, streaming, cross-language stubs — isliye Python ka agent .NET ke agent ko message bhej sakta hai, kyunki wire format language-agnostic hai. Local dispatch (Python if-statements) se network dispatch (gRPC) tak ka jump **interface ke peeche hide** hai — bilkul jaise tum repository pattern me in-memory store ko Postgres se swap karte ho.
- **Factory registration = DI container pattern:** `register(worker, "player1", factory)` me tum instance nahi, **factory** dete ho — runtime lazily/per-key instances banata hai. Aur LangChain tool ko wrapper se Autogen tool banana = adapter pattern across ecosystems, jo tum API client adapters me roz karte ho.

---

## 🧠 Takeaway (yaad rakho)

1. Distributed runtime = **host (`GrpcWorkerAgentRuntimeHost`, localhost:50051) + worker(s) (`GrpcWorkerAgentRuntime`)** — workers host se connect hote hain, agents workers par factories se register hote hain.
2. **Agent code ko distributed hona pata hi nahi** — wahi RoutedAgent + `@message_handler` + `self.send_message`, local runtime se gRPC runtime par zero code change. Yahi Autogen Core ki asli power hai.
3. gRPC **cross-language + cross-process** hai — agents alag processes/languages me ho sakte hain; message stitching Autogen Core handle karta hai AgentId lookup ke basis par.
4. **LangChain tools ko wrap karke Autogen tools** bana sakte ho (Serper search example) — ecosystems mix-and-match.
5. Demo: pros-agent + cons-agent (web research) + judge → decision **"Recommend using Autogen"**; end me workers aur host **stop** karna mat bhoolo. Ye sab abhi **experimental** hai — flavor lo, production bets mat lagao.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

And so here we are back in Cursor and in the number five folder for Autogen. And going to lab four, Autogen Core Distributed. I'm only giving a teaser of what this is about because, uh, I'm to be honest, I'm I'm not even sure how relevant this is to, to many, many of you. So I, you know, I'm going to give a flavor for it. If you do want me to go into more detail, if you want more content, then please do. Do, uh, send me a note, let me know. I can I can always go deeper into this, but I don't want to hold, uh, others up. Um, and, um, I think that particularly as Microsoft is saying, that it's, it's still experimental. It's better to get a flavor for it.

Okay. So I've done this and there's actually two different ways that I want to show you this working. Uh, one of them is what I'm calling all in one worker. And one of them is with multiple workers. And so I've got this flag here that you can set from true to false. And we're going to go through it once with it true, and then once with it at false. And you'll see what I mean. So we do some imports and we load the dot env. And we start with our message, uh, class as as before, which I'm going to clear all outputs and restart. Do this again. Sorry. Uh. Run this. I start as before, with our message class defining this thing. It's the sort of analogy to the state with with LangGraph, although it's to to describe how we interact between our agents.

Okay. And now I mentioned that the distributed runtime consists of these two things. One of them is the host. And this is how you create the host: Autogen runtimes gRPC, the GrpcWorkerAgentRuntimeHost. So this is something which uses gRPC, the remote procedure call technique, to be able to to send messages. And this host will run on my localhost on port 50051. And I will start it with this. So this is now going to be a running host. And gRPC of course, is a cross-language, uh, approach for sending, uh, function calls between different languages, and it's super powerful. It's used in many different, different places. You can think of it. It's like it's like making REST HTTP calls, except you're able to call directly from one function to another, and gRPC is used all over the place where, uh, where interactive messaging needs to be implemented that crosses process boundaries. So that is gRPC. We've started a host and it is running.

And what we're now going to do is, first of all, reintroduce an old friend. We're going to bring back the Autogen Serper tool using our Serper search API. And the reason we're the way we're doing it is through we're we're doing it through LangChain. So we're introducing a few things from, from before, uh, so we uh, we create the Google Serper API wrapper. We create a LangChain tool for internet search. Uh, this is the same tool that we used last week, and now we wrap that in a LangChain tool wrapper so that it becomes an autogen tool. And there it is, an autogen tool for searching the internet using the Serper API.

So originally I was going to have this play rock paper scissors in a distributed way, but I realized that it's a bit frivolous and we should be trying to at least have some commercial footing here. So I was going to make it do the the stock price comparison. And I thought, you know, we've already done some, some of them and we've got a whole week coming on that. So instead I've gone with this trying to we're trying to make a business decision. And let's say that business decision is whether we should use Autogen in a new AI agent project. And we want to have a two different agents, one agent research the pros of autogen by using web searches and the other agent research the cons, the negatives, the drawbacks. Uh, and so the two agents will go off and do their analysis, do their searching, and then they will come together and we will have a judge agent that must make a decision whether to use Autogen for a project. Uh, and, uh, it must be based purely on research from its team, from its agent team. Respond with the decision. Brief rationale. So this is sort of by analogy with the rock paper scissors. We've got instruction one for player one, instruction two for player two. And the judge that will make the call.

All right. And so now we have our agents. And this is again by analogy with last time. It's really very similar. Player one — I've kept calling it player one because I you know, this really is a copy paste job basically. Uh, except I'm using GPT-4o mini for both because I thought it wasn't fair to use, uh, ollama, we didn't get the same the same quality. Uh, so we've got GPT-4o mini, um, and, uh, so we are this is the the the the player one RoutedAgent, and we are passing in, uh, here we're using the Autogen Serper tool so that that is what we're doing. I realize even looking at this, that we don't actually need a player one and player two class. This could be done in a simpler way with just one. Uh, so uh, that's an obvious point. But anyways, for whatever reason, we we've got two, two agents here, two different types of agent, uh, that uh, but we're going to prompt it for whether it should find the pros or cons, but you could imagine you could switch in a different model here if you wanted, if you wanted to have DeepSeek do one of the research. So I'll keep it as two separate agents in case you choose to do that.

Um, okay. So other than that, this is exactly the same. Other than supplying the search tool, reflecting on tool use, everything here is the same. Uh, it delegates to its underlying LLM and the judge is the same. It also has a delegate, an underlying LLM, and in its message handler, the the method that's decorated message handler, it collects the two messages that we set up above. It puts them, it finds the two agents player one and player two. It uses this lookup and then it calls send message and this code is identical. This is all exactly the same as the code we just used yesterday with the runtime that was that was local.

And so the reason I do this, I want to show you that without changing anything I didn't. There's nothing here about it being distributed. It doesn't know that it's distributed. This this could still be doing rock, paper, scissors. It would be the same thing. We're just calling self dot send message. And what we don't realize is this is running remotely and it's running on a, on a runtime that's running on a port here. And uh, it's going to be the, the Autogen core is going to be handling calling the right function in the right, uh, agent. So these calls that appear to just be simply, uh, I'm calling send message, uh, right here, I call send message. And that is going to result in this handle my message getting called. And before that was just directly like some if statements in Python that we're just making that call. Now this is going to be happening using gRPC remotely, orchestrated by this distributed runtime. But that is completely unknown to us as far as we're concerned. We're just doing exactly the same thing. And that is the power of Autogen core distributed — that we don't have to worry about the fact that these are different processes running, and they could be written in different computer programming languages. And all of the stitching together of messages is happening for us, just based on looking up player one and player two. Um, everything is happening.

So enough prattle. Let's run that. Okay. And this is where this is where the meat happens. So I've got two different implementations that I want to show you. And we're starting with all in one worker. And here's how it works. We we, uh, first of all, say that we want to create a new worker agent runtime, and we point it at our host. This is the host. So this will be a new runtime connecting to that host and we will start that worker. We are then going to register, uh, three agents with that worker. Agent one a player one, player two. And the judge. Here they are. Player one. Player two, and the judge all being registered with this worker with this gRPC worker agent runtime at that host. And there we go. There is a player one, player two. And the, the the judge. These are the factories that will create them. And we are now um, now we, uh, collect the agent ID of the judge. So I'm going to run this. And because this is set to true, only this code here is going to run and it's done.

And now this is the same as before. It's just the same thing we're going to send go the go message to the agent ID that is that I've just that I set here to the judge, uh, and let's see what happens. So it's thinking, stuff is happening. I'm still thinking. Messages are flying. It's what we hope is happening is that OpenAI GPT-4o mini is coming up with pros and cons through two separate agent calls. And then a judge has put it all together, and this is what we get back. Pros of Autogen. Here are some advantages of using Autogen in your AI agent projects. The cons are right here. Uh, limited AI capabilities, less customizable, less structured, potential bugs and performance issues with lower end models. Okay, but based on this, basically there's also some, uh, some strengths that appears, uh, memory, coherent context, ease of development, scalability, which is what we're experiencing, and versatile applications. And the decision is recommend using Autogen. So the uh, based purely on this research, that is the decision. And with that we will then stop our workers and we stop our host. And we have just experienced distributed autogen core.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
