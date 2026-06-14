# L105 — Day 5: Agents That Write & Deploy Other Agents

> **Week 5 — AutoGen** · ⏱️ ~5m · 🎥 Lecture 105 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821651

---

## 🎯 Ek Line Mein (TL;DR)

Week 5 ka wrap-up project: ek **Creator Agent** jo khud ek naya **Python module** likhega (template se), us module ke andar ek **naya AutoGen agent** hoga, aur Creator us agent ko **AutoGen Core runtime** pe **register/instantiate** karke launch kar dega — yaani **agents jo agents banate hain**, sab kuch **asyncio** se parallel.

---

## 📝 Hinglish Explanation (Detailed)

- Ye **Day 5 of Week 5** hai — AutoGen week ka **wrap-up project**, naam: **"Agent Creator"**. Ed kehte hain ye quick hoga lekin fun — thoda "out there" idea hai jiske **3 pluses aur 3 minuses** hain.

- **3 Pluses:**
  - **Educational** — framework ke **innards** dikhata hai; AutoGen ko ek bilkul alag tareeke se use karna sikhata hai (jo ab tak ke kisi project jaisa nahi hai).
  - **Entertaining** — intellectually mazedaar, edgy idea.
  - **In vogue** — aaj kal **autonomy aur agency** ke discussions me ye exact topic (self-creating agents) bahut hot hai.

- **3 Minuses:**
  - **Not commercial** — Ed normally commercial benefit pe focus karte hain; ye project directly commercial nahi hai (ek subtle twist hai, neeche dekho).
  - **Unreliable** — apne nature se hi ye project **kabhi-kabhi fail** kar sakta hai (LLM-generated code hamesha sahi nahi hota).
  - **Unsafe** — agent **Python code likhega aur usse execute karega**, generally **bina guardrails ke**. Matlab **apne risk pe chalao**.

- **Safety warning (seriously lo):**
  - LLM ka likha hua code **natively apne machine pe run** karna "not for the faint of heart" hai.
  - Ed bolte hain — agar comfortable nahi ho, to **sirf video me unhe run karte dekho**, khud mat chalao. **Eyes wide open.**
  - Docker container me daala ja sakta hai, lekin wo boring/painful hoga kyunki container me poora AutoGen install karna padega — to abhi ke liye native hi hai.

- **Big idea — kya banayenge:**
  - AutoGen ka **flexible, dynamic aspect** explore karenge.
  - Ek **Creator Agent** banayenge jo ek **Python module likh sakta hai**, ek **existing Python module ko template** ki tarah use karke.
  - Wo naya module khud ek **agent** hoga — ek **AgentChat agent jo AutoGen Core runtime me run karta hai** (yaani 2-layer combo: AgentChat agent, Core ke andar wrapped).
  - Creator us module ko **modify** karega taaki ek **naya, different agent** bane jo pehle exist nahi karta tha.
  - Phir Creator apni creation ko **distributed runtime (AutoGen Core) ke saath register** karega — technically: **instantiate** karega, taaki wo ek **running agent** ban jaye. (Ed mazak me kehte hain — "give birth"!)

- **Agents aapas me baat karenge:**
  - Template aise likha gaya hai ki created agents **ek doosre ko message** kar saken aur **interact** kar saken — Core ka messaging system use hoga.

- **Objective / commercial twist:**
  - Created agents ki **team ka goal**: **agentic AI se paise kamane ke business/commercial ideas** generate karna. Yahi subtle commercial angle hai — agents aapke liye money-making ideas sochte hain.
  - Aap objective **change** kar sakte ho — koi aur task de do, "quick buck" kisi aur tareeke se, kuch bhi. Idea ye hai: **initial seed plant karo**, ek **army of agents spawn** karo jo sochte aur interact karte hain, aur dekho kya hota hai.

- **Async Python heavily use hoga:**
  - Agar har agent serially (ek-ek karke) create ho aur message kare, to bahut slow hota.
  - **asyncio** se sab kuch **parallel "fly"** karega — ye bhi project ka educational part hai.

- End: "with that introduction, let's get to the code" — agla lecture code walkthrough hai.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Agent Creator** | Week 5 ka final project — ek agent jo doosre agents ka code likhta hai aur unhe deploy karta hai |
| **Creator Agent** | Wo specific agent jo template se naya Python module (= naya agent) generate karta hai |
| **Template module** | Ek existing Python module jisko Creator base/reference ki tarah use karke naya agent likhta hai |
| **Code generation + execution** | LLM Python code likhta hai aur wahi code natively run hota hai — powerful lekin **unsafe** (no guardrails) |
| **Register / Instantiate** | Naye agent ko AutoGen Core runtime ke saath register karke usse live running agent banana |
| **Distributed runtime (Core)** | AutoGen Core ka runtime jaha agents register hote hain aur messages se communicate karte hain |
| **Agent-to-agent messaging** | Created agents ek doosre ko Core ke through messages bhej kar interact karte hain |
| **Spawn an army of agents** | Ek seed se dynamically multiple agents create karke unhe sochne/interact karne dena |
| **asyncio** | Async Python — sab agents parallel me create/message hote hain, serial wait nahi |
| **Unreliable & unsafe** | Project ke 2 minuses — generated code fail ho sakta hai, aur native execution risky hai |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Runtime-pe-register karna = dynamic plugin loading + actor spawn ka combo.** Socho jaise `importlib` se runtime pe ek module load karna aur phir us class ko ek actor system (Akka/Erlang style) me spawn karna — Erlang me ye literally `spawn/3` hai aur OTP me supervisors children dynamically start karte hain. AutoGen Core ka `register()` wahi role play karta hai: type+factory do, runtime instances manage karta hai.

- **"LLM writes code, we exec it" = RCE by design.** Aap as a backend dev jaante ho `eval`/`exec` on untrusted input kitna dangerous hai — yaha "untrusted input" khud LLM hai. Production analogue hota sandboxing (Docker, gVisor, firecracker, restricted user) — Ed ne deliberately skip kiya for simplicity, isliye warning itni strong hai.

- **Async fan-out pattern wahi hai jo aap Kafka consumers / `asyncio.gather` me karte ho.** N agents ko serially banana O(N×latency) hota; asyncio se sab LLM calls concurrently nikalti hain — same reasoning jaise aap bulk API calls ko `gather`/`TaskGroup` me daalte ho.

- **Hands-on lab:** is lecture ka code khud chalane ke liye is repo ka `Practical/lab4_agent_creator.py` run karo (`uv run` se chalta hai, Groq pe free via `OpenAIChatCompletionClient` + `base_url` + `ModelInfo`). **Ek important difference:** lecture me Creator **arbitrary Python code generate karke execute** karta hai (unsafe, no guardrails) — hamare lab4 me iski jagah **SAFE persona-generation** hai: agent naye agents ke personas/configs generate karta hai, lekin hum LLM-generated code kabhi execute nahi karte. Same concept (agents creating agents + Core registration), zero RCE risk. (Baaki repo-wide diffs: AutoGen 0.7.5 vs course 0.5.1 — same API family.)

---

## 🧠 Takeaway (yaad rakho)

1. Week 5 ka finale project: **Creator Agent** jo template se **naya agent module likhta hai**, usse **Core runtime pe register/instantiate** karta hai, aur created agents **aapas me message** karte hain.
2. Project ke 3 pluses — **educational, entertaining, in vogue (autonomy)**; 3 minuses — **not commercial, unreliable, unsafe**.
3. **Safety first:** LLM-generated Python code natively execute hota hai bina guardrails ke — comfortable nahi ho to sirf dekho, khud mat chalao (hamara lab4 isliye safe persona-gen use karta hai).
4. Created agents ki team ka goal: **agentic AI se paise kamane ke ideas** — seed aap doge, objective change kar sakte ho.
5. **asyncio** zaroori hai — serial agent creation/messaging bahut slow hoti; async se sab parallel "fly" karta hai.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Well, have I got a treat in store for you? So welcome to day five of week five, the wrap up project for AutoGen week in the form of the agent creator. And, well, let me tell you about this project. It's going to be quite quick, but it's going to be fun. So look, it's this is the big idea. It's one of these things that has pluses and minuses. It's a bit of an out there project. Look, first of all this is designed to be primarily educational. So this is here to teach some of the innards of what you can do with this kind of framework and use AutoGen in a different way. So something that's different, unlike anything else that we've done. Secondly, it's entertaining. This is something that should be intellectually entertaining. This is quite, quite out there. And on that front it is it's an edgy idea and thing to try with. And it's very in vogue in terms of thinking about autonomy, agency and so on.

But those are the three pluses. There are also three minuses. It's not particularly commercial, so I do like to focus this whole course on commercial benefits. There is a twist that there is something a bit commercial about it, as you'll see, but it's a bit of a side benefit of it. Um, it's unreliable. The project that we're about to do, by its very nature is something that may sometimes fail, and also it's unsafe. So we are going to be building something that's going to be creating and running Python code, and it's going to be doing so in a, generally without guardrails on, which means you have to run this at your own risk, take whatever precautions you wish. Um, I may in time put this into a Docker container or something, but that would be quite a bore because you'd need to install all of AutoGen in the Docker container, so it wouldn't be easy. Um, but as it is, take it for what it is. You could just watch me run it. If you don't feel confident that you know what's going on and that you're comfortable taking the risk of letting an agent write Python code and then executing that Python code natively on your box, which is not for the faint of heart. So eyes wide open. You don't need to execute any code if you don't want to. And please do take that to heart. Run the code yourself only if you're comfortable with it.

Okay, well, hopefully I've intrigued you somewhat. Let me tell you what this idea is. So we're going to explore the flexible, dynamic aspect of AutoGen. We are going to make a creator agent — an agent, as I say, that can write a Python module. It will use an existing Python module as its kind of template. And that Python module is going to be an agent. It's going to be an AutoGen AgentChat agent that's running in AutoGen Core. So we're going to build an agent that can write a Python module of an agent. It's going to create an agent, and it's going to change it so that the Python module it makes is something new, a different agent that doesn't exist, and then the creator agent is actually going to register its creation with the distributed runtime with AutoGen Core. In other words, dare I say it, it's going to kind of — do I say give birth? It's going to. Let's get technical. It's going to instantiate the agent. That's going to be a running agent that was created by the creator agent.

And then it's also, as part of writing this agent based on the template it will use, its agents are going to be able to message each other. So it's going to be possible for agents to message each other and interact — these agents that have been created by the agent. And overall, they're going to have an objective of coming up with business ideas, commercial ideas for putting agentic AI into practice to make money. So there is a commercial angle subtly, because the overall objective of our team of created agents is to try and make you money by coming up with ideas. And of course, you can shift the overall objective. You can make it something different or, you know, maybe not money with agentic AI, but how to make a quick buck in some other way. You can assign it some other task and let it think, but the idea is that you can spawn this army of agents that can think about something and interact with each other, and you can help plant the initial seed and then see what happens.

And as part of the educational aspect of this, we're going to be heavily using asynchronous Python. It would be quite a drag if this thing had to happen in a serial way, with each agent being created and then messaging the others one by one. That would take quite a long time, but now we're going to use asyncio to make sure that things fly. And so with that introduction, let's get to the code.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
