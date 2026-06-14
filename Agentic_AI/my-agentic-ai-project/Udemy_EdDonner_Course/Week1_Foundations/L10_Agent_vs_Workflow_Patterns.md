# L10 — Day 2: Understanding Agent vs Workflow Patterns in LLM Application Design

> **Week 1 — Foundations** · ⏱️ ~7m · 🎥 Lecture 10 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49770903

---

## 🎯 Ek Line Mein (TL;DR)

**Workflow patterns** mein path fixed hota hai, lekin **Agent patterns** mein **LLM khud apna path decide karta hai** — ek **open-ended feedback loop** mein environment ke saath interact karke. Yeh zyada powerful hai par **unpredictable** bhi — isliye **monitoring** aur **guardrails** mandatory mitigations hain.

---

## 📝 Hinglish Explanation (Detailed)

- Pichhli lecture mein humne **workflow patterns** dekhe the (prompt chaining, routing, parallelization, etc.) — ab Ed dusri category pe aate hain: **Agent patterns**.

- **Agent pattern ki defining characteristics:**
  - Process **open-ended** hai — yeh chalti reh sakti hai, koi fixed end-point nahi.
  - Ismein **feedback loops** hote hain — information **wapas aakar multiple times process** hoti hai.
  - **Koi fixed path nahi** hota design ke through — workflow patterns jaise step-by-step series nahi, balki kuch **fluid aur dynamic**.
  - Result: yeh **much more powerful** hai — bahut bade aur harder problems tackle kar sakta hai.
  - Lekin trade-off: **less predictable** — isliye **robustness**, **guardrails**, aur production guarantees (jaise "yeh certain time mein complete hoga") ke concerns aate hain.

- **Agent ka generic diagram** (Anthropic-style):
  - **Human** request bhejta hai → **LLM** ko.
  - Output ki jagah ab **Environment** hai — koi bhi outside world jisse interact kiya ja sake.
  - LLM environment pe **actions** leta hai, aur environment se **feedback** wapas milta hai.
  - Yeh ek **repeating loop** hai — LLM baar-baar actions le sakta hai, feedback process kar sakta hai, aur **jab chahe khud decide karke ruk sakta hai**.

- **Koi specific sub-patterns kyun nahi?**
  - Kyunki agent pattern khud hi ek **open-ended "meta design"** hai — yeh keh raha hai ki **LLM khud apna design choose karega** problem solve karne ke liye.
  - Ed mante hain ki yeh thoda **hand-wavy** lagta hai, lekin yahi workflow vs agent ka **core distinction** hai.
  - Workflow patterns (jaise evaluator-optimizer) bhi technically forever chal sakte hain, lekin unmein **clear certainty** hoti hai ki kya ho raha hai aur kyun — agentic patterns inherently **fluid** hote hain.

- **Agentic AI ke drawbacks / challenges** (agent developers ko face karne padenge):
  - **Unpredictable path** — pata nahi tasks kis order mein honge, ya konse tasks honge hi.
  - **Unpredictable output** — koi guarantee nahi ki great output milega; quality unknown.
  - **Task complete hoga ya nahi** — yeh bhi unknown; kitna time lagega, yeh bhi unknown.
  - **Unpredictable costs** — kyunki duration unknown hai, **API bills** kitne banenge yeh bhi unknown — bada bill ban sakta hai.
  - Yeh sab **LLMs ko autonomy dene ki inherent uncertainty** hai — isi flexibility se hi bade problems solve hote hain.

- **Do critical mitigations** (coming weeks mein detail mein):
  - **Monitoring** — behind-the-scenes **visibility** ki kya ho raha hai, especially jab **multiple agents interact** kar rahe hon:
    - **OpenAI Agents SDK** mein **trace** feature — different agents ki interactions dekh sakte hain.
    - **LangGraph** ke saath **LangSmith** tooling — under-the-hood visibility.
  - **Guardrails** — software mein likhi gayi **protections** jo ensure karti hain ki models wahi karein jo karna chahiye, aur set constraints (rails) ke bahar na jaayein:
    - OpenAI Agents SDK ka quote: guardrails ensure karte hain ki agents *"behave safely, consistently and within the boundaries that you wish."*
    - Hum **Week 2 mein khud guardrails build** karenge.

- **Day 2 wrap-up:**
  - Theory-heavy day tha, lekin ab clarity honi chahiye ki **agent kya hota hai** — definition mein ambiguity hai, par ab aapke paas **autonomy** aur **"plot your own path"** ke terms mein sochne ka framework hai.
  - **Day 3 preview:** **Orchestrating LLMs** — zyada coding, zyada hands-on, bahut saari **APIs** ke saath build karenge. Uske baad **Tools** pe move karenge.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Agent Pattern** | Open-ended design jismein LLM khud decide karta hai kya karna hai — koi fixed path nahi, feedback loops ke saath |
| **Workflow Pattern** | Fixed, predefined path — steps pehle se code mein decide hote hain (predictable but limited) |
| **Environment** | Outside world jisse agent interact karta hai — actions leta hai, feedback wapas milta hai |
| **Feedback Loop** | Information wapas aakar multiple baar process hona — agent ka core mechanism |
| **Autonomy** | LLM ko apna path khud choose karne ki freedom — power ka source, aur uncertainty ka bhi |
| **Monitoring / Tracing** | Agent systems ke andar visibility — OpenAI SDK ka trace, LangGraph ke saath LangSmith |
| **Guardrails** | Software protections jo ensure karti hain ki model boundaries ke andar safely/consistently behave kare |
| **Unpredictable Cost** | Agent kitna time/API calls lega unknown — isliye bill bhi unknown (production concern) |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Workflow vs Agent** ko aise socho: workflow = aapka **orchestrated DAG/state machine** (jaise Airflow ya Celery chains — control flow code mein hardcoded), agent = ek **event loop jismein dispatch decision runtime pe LLM karta hai**, dispatch table nahi. `while not done:` loop with non-deterministic branching.
- **Agent loop** structurally wahi hai jo aap distributed systems mein dekh chuke ho — **action → observe → decide → repeat** — lekin yahan "decide" step deterministic code nahi, LLM inference hai. Isliye retry/timeout/idempotency ki jagah ab **guardrails + tracing** aapke reliability primitives hain.
- **Unpredictable cost** ko waise hi treat karo jaise unbounded recursion ya runaway queue consumers — production mein **max-iterations cap, token budgets, aur timeouts** lagana utna hi zaroori hai jitna circuit breakers lagana.
- **Monitoring/tracing** (LangSmith, OpenAI traces) conceptually **distributed tracing (Jaeger/OpenTelemetry)** jaisa hi hai — har agent interaction ek span; multi-agent systems mein iske bina debugging impossible hai.

---

## 🧠 Takeaway (yaad rakho)

1. **Agent pattern = open-ended loop** — LLM environment pe actions leta hai, feedback leta hai, aur khud decide karta hai kab rukna hai; koi fixed path nahi.
2. **Yeh ek "meta design" hai** — LLM khud apna design choose karta hai, isliye workflow jaise specific sub-patterns exist nahi karte.
3. **Power ka price uncertainty hai** — unknown path, unknown output quality, unknown completion time, unknown cost.
4. **Do mandatory mitigations:** **Monitoring/Tracing** (OpenAI SDK trace, LangSmith) aur **Guardrails** (Week 2 mein khud build karenge).
5. Workflow patterns clear lagte hain aur agents loose — yeh normal hai; **real agent environments code karne pe yeh concrete ho jayega**.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

And so with this, we now turn to the other category, the second category of agents. So by contrast with the workflow patterns, with agents, the process is more open ended. It's something that can keep going. It has feedback loops. It's typically a design that allows for information to come back and be processed multiple times. And importantly, there's no fixed path through the design pattern. It's not like there's a series of steps as we had in those prior patterns, but rather it's something that's fluid and dynamic. And as a result, it's something which can be much more powerful. There's many more — there's a much greater kind of problem that could be taken on by this sort of agent pattern, but it's less predictable. And so there are absolutely concerns about robustness, about guardrails, about how do you get the best out of this kind of flexibility, but still have a system that can run in production and be guaranteed to complete in a certain time and so on.

And this is the diagram that I would bring up, which is a fairly generic kind of diagram that's just meant to show that you have the inputs and outputs now shown as a human. But we don't really have output anymore. We have environment that's meant to reflect some sort of outside world that can be interacted with, such as the lights that I wore around me, that the human can make a request that goes to an LLM. The LLM is able to take actions on the environment, as you can see, and the LLM is able to get back information from the environment in some way. And then this is simply a repeating loop. The LLM can continually make other actions and get back feedback, and at such time as it desires, it can choose to stop. And so this is the diagram.

And there aren't more specific design patterns because it is in itself this sort of open ended design pattern. It's saying this is a — it's almost a sort of meta design. It's saying the LLM gets to choose its own design for how it's going to solve the problem. And that's really — it's quite hand-wavy, but that's the way to distinguish it. If we look back at this pattern, I mean, this pattern arguably also could keep going forever. It's not as if this has a fixed stop, but there's clearly more certainty about what's happening for what reason than with the agentic patterns, where it is more fluid by its nature.

So that's really the core idea behind the agent patterns, that there is much more flexibility that allows us to be able to solve much more complex problems where LLMs can really plot their own paths. But it does introduce some new issues, such as not knowing how long it will take before it will complete its task, not knowing whether it will complete its task at all, not knowing what kind of quality outputs we will get, and not knowing how much it will cost. These are all the kinds of challenges that agent developers like ourselves need to face, and they are the sorts of things that we will be tackling in the coming weeks. And so if this feels a bit unsatisfying that the design patterns for workflows are so clear, and now this looks just so loose, then all I can say is, as we put this into practice, as we code different real agent environments, this is going to become more and more concrete, and you're going to be able to — you'll see this as second nature before too long.

Now let's just quickly say a few more words about some of the drawbacks that I alluded to a second ago with using agent frameworks and agentic AI and design patterns. So obviously there is this sense that you have an unpredictable path. You don't actually know what order tasks will take place in, or even what tasks will happen. You don't know what the output will be. There's no guarantees that you're going to get a great output. Now, this whole agentic architecture allows us to take on much bigger, harder problems than we've ever been able to take on before. But it does have this inherent uncertainty associated with giving LLMs autonomy over how they tackle problems. There's also unpredictable costs. I alluded to that as well a moment ago, but because you don't know how long it's going to take, you don't know how much it's going to cost in terms of running the APIs and potentially building up a big bill.

And so as a result, there's a couple of mitigations that are incredibly important, both of which we will spend plenty of time on in the coming weeks. One of them is, of course, monitoring — being sure that you have the kinds of visibility into what's going on behind the scenes so you can understand what's going on with your models, with their interactions, particularly when you have potentially many agents all interacting. And we're going to see that with OpenAI SDK — we're going to see the trace, the ability to watch different agents interacting. When we look at LangGraph, we're going to see LangSmith, their tooling. So we're going to see a lot of the ways that you can have this visibility into what is going on under the hood in your agent systems.

And then guardrails. Guardrails is the name for the kinds of protections that you can write in software that makes sure that your models are doing what they should be doing, or that they're not sort of leaving some constraints, some rails that you put in place. And in fact, that quote that I put here comes straight from the OpenAI Agents SDK, which has a ton of functionality dedicated to guardrails, and they say that it ensures they behave safely, consistently and within the boundaries that you wish. And so we will be building those guardrails ourselves in week two.

And with that, that does actually conclude the day two lectures. As I promised you, it was shorter than day one. And I hope you didn't mind that we covered a lot of theory. It's really interesting stuff, these agentic design patterns. I hope now you've got some clarity on what agents are and that there is ambiguity on this, but ways that you can talk about it and think about what it means to be autonomous and what it means to be able to plot your own path — let an LLM decide the path that things will take. And so with that, congratulations on completing day two. And day three, we're going to talk about orchestrating LLMs. It's going to be more and more coding, more hands on, which will be fun. We're going to build with a lot of APIs, and get ready for that. And after that we're going to move on to tools. So I will see you next time.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
