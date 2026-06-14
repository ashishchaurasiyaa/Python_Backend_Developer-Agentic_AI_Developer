# L09 — Day 2: 5 Essential LLM Workflow Design Patterns

> **Week 1 — Foundations** · ⏱️ ~9m · 🎥 Lecture 09 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49770901

---

## 🎯 Ek Line Mein (TL;DR)

Anthropic ne **5 workflow design patterns** define kiye hain — **Prompt Chaining**, **Routing**, **Parallelization**, **Orchestrator-Worker**, aur **Evaluator-Optimizer** — jo agentic systems ke building blocks hain; aur Ed ka point hai ki **workflow vs agent** ki line kaafi **blurred** hai, kyunki in patterns mein bhi LLM ko thodi **autonomy** milti hai.

---

## 📝 Hinglish Explanation (Detailed)

- Is lecture mein hum workflows ka onion aur peel karte hain — **Anthropic** ne apne (famous "Building Effective Agents") framework mein **5 design patterns** identify kiye hain jo workflow-based agentic systems mein milte hain.

- **Diagram convention pehle samajh lo:**
  - **Yellow boxes** = **LLM calls** (model ko call karna)
  - **Blue boxes** = **aapka likha hua code** (plain software, e.g. Python) — optional
  - Left/right **In/Out** = workflow ka start aur end

- **Pattern 1: Prompt Chaining**
  - Simple idea: ek LLM ek task karta hai → (optionally beech mein kuch code) → output dusre LLM ko jaata hai → phir teesre LLM ko → final output.
  - Ye bilkul wahi hai jo humne pichle lecture ke **commercial question exercise** mein kiya tha: pehle LLM se **sector** pick karwaya, phir us sector ka **pain point**, phir uska **solution**. 3 LLMs zaroori nahi — jitne chahe utne chain kar sakte ho.
  - Core idea: ek bade task ko **fixed set of subtasks** mein **decompose** karna.
  - **Kyun useful hai:** har LLM call ko aap **precisely frame** kar sakte ho — har subtask ke liye best possible prompt — aur poora process **guardrails** pe step-by-step, well-defined tasks ke through chalta hai.
  - **Ed ka important point:** Anthropic ise clearly **workflow** kehta hai, **agent pattern nahi** — lekin prompt chaining mein bhi LLM ko **discretion** mil sakti hai. Jaise hamare example mein pehla LLM jo topic choose karta hai, wahi topic LLM 2 aur 3 ka kaam decide karta hai. Matlab workflow vs agent ka distinction thoda **artificial** hai — dono ke beech **blurred line** hai, workflow pattern mein bhi **element of autonomy** ho sakta hai.

- **Pattern 2: Routing**
  - Input aata hai, aur ek **router LLM** decide karta hai ki kaun sa model is task ko handle karega — multiple **specialist models** (LLM 1, 2, 3) available hain jo alag-alag tasks mein achhe hain.
  - Router ka job: task ko **classify** karna aur samajhna ki kaun sa specialist best equipped hai.
  - Benefit: **separation of concerns** — alag-alag expertise wale LLMs, aur ek LLM jo unme route karta hai.
  - Ye bahut **common aur powerful** pattern hai. Yahan bhi Ed argue karta hai ki "no autonomy" kehna artificial hai — router clearly **decisions le raha hai**, bhale hi guardrails ke andar, fixed workflow follow karte hue.

- **Pattern 3: Parallelization**
  - Pehli nazar mein routing jaisa lagta hai, but key difference: yahan **blue box = code** (LLM nahi) task ko todta hai.
  - Aapka **Python code** task ko multiple pieces mein break karta hai jo **parallel/concurrently** run hote hain — teen LLMs ek saath teen alag activities karte hain.
  - Phir aur code (aggregator) un answers ko **stitch** karke combine karta hai.
  - **Anthropic ka extra point:** tasks alag hone zaroori nahi — aap **same task 3 baar** bhej sakte ho aur aggregator se average/consensus le sakte ho (reliability badhane ke liye). But most commonly ye multiple subtasks concurrently run karne ke liye use hota hai.
  - Routing vs Parallelization yaad rakhne ka tareeka: **routing mein LLM decide karta hai, parallelization mein code coordinate karta hai.**

- **Pattern 4: Orchestrator-Worker**
  - Parallelization jaisa hi dikhta hai — difficult task **break down** hota hai aur results **recombine** hote hain — but **subtle color change**: ab orchestration **code nahi, LLM kar raha hai**.
  - Ek **orchestrator LLM** complex task ko smaller steps mein todta hai, **worker LLMs** har expert task karte hain, aur ek **synthesizer LLM** results combine karke output banata hai.
  - Ye kaafi zyada **dynamic** system hai — orchestrator khud choose karta hai task kaise **divvy up** hoga, kitne LLMs ko kaam milega.
  - **Ed ka argument (phir se):** ise sirf "fixed workflow" kehna stretch hai — orchestrator ke paas clearly **discretion** hai. Haan, full agent flows se zyada **constraints** hain, but autonomy hai.

- **Pattern 5: Evaluator-Optimizer** *(Ed ka favourite — sabse zyada use hota hai)*
  - Ed ise simply **evaluator** ya **validation agent** bhi bolta hai.
  - Setup: ek **LLM Generator** actual kaam karta hai aur solution produce karta hai. Ek dusra **LLM Evaluator** uska kaam **check** karta hai — ise generate nahi karna, sirf evaluate karna hai (saara context/extra info isko diya jaata hai).
  - Evaluator solution ko **accept ya reject** karta hai:
    - **Accept** → output final.
    - **Reject** → reject ka **reason** ke saath wapas generator ke paas jaata hai → generator naya solution banata hai → phir evaluator ke paas → **feedback loop**.
  - **Kyun powerful hai:** production LLM systems ki biggest concern hai **accuracy, predictability, robustness**. Validation agents se aap output quality ke around **higher level of guarantee** build karte ho. (LLMs ke saath **full guarantee kabhi nahi** hoti, but ye pattern quality significantly improve karta hai.)
  - Ed ye pattern roz use karta hai, course mein bhi plenty of examples aayenge — aur aap ise apne **day job ke LLM solutions** mein turant apply karne ke baare mein soch sakte ho.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Prompt Chaining** | Ek bade task ko fixed subtasks mein todkar LLM calls ko sequence mein chain karna — har step ka precise prompt |
| **Routing** | Ek router LLM input ko classify karke decide karta hai ki kaun sa specialist LLM task handle karega |
| **Parallelization** | Aapka code task ko todkar multiple LLMs ko concurrently bhejta hai, phir code hi results aggregate karta hai |
| **Orchestrator-Worker** | Parallelization jaisa, but orchestration code nahi balki ek LLM karta hai — dynamic task breakdown + LLM synthesis |
| **Evaluator-Optimizer** | Generator LLM kaam karta hai, Evaluator LLM check karke accept/reject karta hai — reject pe reason ke saath feedback loop |
| **Validation Agent** | Evaluator LLM ka common industry naam — output quality verify karne wala agent |
| **Decomposition** | Complex task ko chhote well-defined subtasks mein todna |
| **Separation of Concerns** | Har specialist LLM apna expertise area handle kare — routing pattern ka core benefit |
| **Aggregator** | Wo code/LLM jo parallel results ko stitch/combine karta hai |
| **Guardrails** | Workflow ko predictable, well-defined path pe rakhna — autonomy ko bound karna |
| **Workflow vs Agent (blurred line)** | Anthropic ka distinction artificial hai — workflows mein bhi LLM ko discretion/autonomy mil sakti hai |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- Ye 5 patterns aapke familiar backend patterns ke LLM-avatars hain: **Prompt Chaining = pipeline/middleware chain**, **Routing = strategy pattern + dispatch table** (bas dispatch key string-match nahi, LLM classification se aati hai), **Parallelization = `asyncio.gather()` fan-out/fan-in**, **Orchestrator-Worker = dynamic task queue (Celery-style) jahan scheduler khud ek LLM hai**.
- **Evaluator-Optimizer** ko CI/CD gate ki tarah socho: generator = developer, evaluator = code reviewer jo merge block kar sakta hai with reasons, aur retry loop = "request changes" cycle. Production mein ise **Pydantic structured output** ke saath combine karo — evaluator se `{"accepted": bool, "reason": str}` schema enforce karwao taaki loop deterministic rahe.
- **Code vs LLM boundary hi asli design decision hai** (blue box vs yellow box): jo logic deterministic ho sakta hai use code mein rakho — cheaper, faster, testable. LLM sirf wahan lagao jahan judgment/classification chahiye. Ye wahi instinct hai jo aap "DB mein computation vs app layer mein" decide karte time use karte ho.
- Parallelization ka "same task 3 baar bhejo aur average lo" trick = **quorum/replication pattern** distributed systems se — non-deterministic service (LLM) pe reliability badhane ke liye redundant calls + consensus.

---

## 🧠 Takeaway (yaad rakho)

1. Anthropic ke **5 workflow patterns**: Prompt Chaining, Routing, Parallelization, Orchestrator-Worker, Evaluator-Optimizer — ye agentic systems ki core vocabulary hai.
2. **Yellow = LLM call, Blue = aapka code** — har pattern mein asli sawaal yahi hai ki decision LLM lega ya code.
3. **Parallelization vs Orchestrator-Worker** ka fark sirf itna hai: task ka breakdown **code** karta hai ya **LLM** — LLM karega to system zyada dynamic (aur zyada agent-like) ho jaata hai.
4. **Evaluator-Optimizer** sabse practically useful pattern hai — generator + evaluator feedback loop se production LLM systems mein accuracy/robustness ki higher guarantee milti hai (full guarantee kabhi nahi).
5. **Workflow vs Agent ki line blurred hai** — Anthropic in sabko "workflows" kehta hai, but routing/orchestration/chaining mein bhi LLM ko real discretion milti hai; ye ek spectrum hai, binary nahi.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Next we're going to peel back the onion a little bit more on workflows. Looking at different types of workflow, Anthropic identifies five different design patterns that you'll find when building agentic systems that have workflows in them. And let's go through each of them and talk about them.

This is the first one. They call it prompt chaining. And it's a simple one. What you're seeing here in this diagram obviously the in and the out on the left and the right is the beginning and the end of the workflow. The yellow boxes represent calls to models, to LLMs. And the blue boxes is where you potentially have just some code that you've written, some software, and it's optional. And what you'll see there is that this is simply saying you could have an LLM carry out some task and then potentially based on some code, you could then pass that to a second LLM, and that output could go to a third LLM. And that could be the conclusion. And actually this is really similar to what you just did. This is similar to that commercial question. When we ask an LLM first pick a sector, and then given that sector pick a pain point, and then pick a solution. And obviously it doesn't need to be three LLMs. It can be as many as you want, but this is the idea. You are chaining a series of LLM calls, decomposing into a fixed set of subtasks. And the reason you might want to do that is because you can take care to frame each LLM call very precisely to get the best, the most effective LLM response based on that prompt. So it allows you to really work on each of those tasks being very effective, and then keep your whole process, your workflow on guardrails by taking it step by step through a sequence of well-defined tasks.

Now I want to make a point that you might have already thought of. Whilst Anthropic is quite clear to define this as a workflow and not an agent pattern, it is perfectly possible for a prompt chaining workflow like this to be giving the LLM some discretion on what activities happen, because just as we did in our example, the first call to the LLM might come up with a topic, and it's that topic that gets worked on by LLMs two and three. So in some ways, the way that Anthropic distinguishes between workflows and agents, it's a little bit artificial. There is definitely a blurred line between them. It's perfectly possible for there to be an element of autonomy about a workflow pattern like this.

Onwards. The second design pattern is called routing, and this is where an input comes in, and an LLM has the task of deciding which of multiple possible models are selected to carry out this function. And the idea is that you might have specialist models in here. They're shown by LLM one, two and three. And they're each good at different tasks. And the router's job is to classify the task, understand which of the specialists will be best equipped to tackle this task. And it allows for, as I say here, separation of concerns — for being able to have different LLMs that have different levels of expertise, and have an LLM decide how to route to those experts. So this is a powerful model. It's very common. And it's something which again, I would say I would argue there is some — it's a bit artificial to say that there's no autonomy here, because clearly that router is able to make some decisions, albeit on guardrails. Again, it still has to follow a given workflow.

And on to the third design pattern. Parallelization, which at first blush might look quite similar to what we just talked about. But there is a lot in common with these design patterns. But the idea here is that you have — remember, the blue boxes represent code, our code, not an LLM. So we write some code that takes a task and breaks it down into multiple pieces that should all run in parallel. So in the previous design pattern it was an LLM doing the routing, and it was one of these three experts that was given the task. In this design pattern it's code. It's, let's say, Python code that's deciding what to do or how to coordinate. And in parallel, it's being sent to three LLMs to carry out three different activities concurrently. And then there's more code — maybe it's Python code — that takes those answers and stitches them together. And actually, Anthropic makes the point that these tasks don't necessarily need to be different tasks. You could imagine a situation where you send the same task and have it be done three times, and you use the aggregator perhaps to take the average or something like that. So there are various situations where this might be the same thing that you're doing three times — doesn't need to be different — but I think most commonly it's when there are multiple subtasks happening concurrently. That is the parallelization design pattern. Okay.

And now this one — orchestrator worker. This is when a difficult, challenging task is broken down and recombined. And you might be thinking, hang on, isn't that just what we just did? I just flick between them — don't these two slides, these two design patterns, look really similar? Well, you'll notice a subtle color change along with the change in terminology. The key point is that this is exactly like the prior design pattern, except it's no longer code that's doing the orchestration. It's an LLM. So you are using a model to break down a complex task into smaller steps, and then you are using a model to combine the results. And so this is a much more dynamic kind of system where the orchestrator can choose how to divvy up the task. And again, I would argue that it's quite artificial to categorize this as a workflow rather than an agent pattern that we'll look at in a minute, because clearly that orchestrator has discretion over how it divvies up the tasks, and it could choose how many different LLMs get assigned the activity. So saying that this is just a fixed workflow is perhaps a stretch. So, you know, I think you get the overall idea. There's certainly more constraints on this than when we come to the more flexible agent flows. But generally the idea here: LLM breaks down the task, LLMs carry out each expert task, LLM synthesizes the task for an output. That is the pattern for the orchestrator worker.

And now on to pattern five. The final workflow pattern and the one that I use most commonly. This is one that I come against all the time, and it's called an evaluator optimizer by Anthropic. I tend to call them just evaluators, or validation — validation agents, you hear that a lot. But the idea is, it's very simple. You have an LLM that's doing your job. Let's call it the LLM generator. It's doing something, and it comes up with a solution shown in this white arrow here. And you have a second LLM that's playing the role of evaluator. It's there to check the work of the first LLM. And it's given any extra information, any context — everything to arm itself to not be trying to generate content, but check the work of a prior LLM. And based on that it can choose to either accept or reject the work. If it accepts it, then that's it — goes to the output. If it rejects it, it should come up with a reason, and the rejection and the reason goes back to the LLM generator. And that can then choose to come up with another solution which comes back here. And so you can see this sort of feedback loop setup. It's very powerful. Of course, one of the key concerns of building production systems with LLMs is about accuracy, predictability, robustness of the responses, and having validation agents — having these kinds of evaluator optimizer flows in your LLM solutions — is a really powerful way to increase the accuracy and build more guarantees. There's never full guarantees with LLMs, but build a higher level of guarantee around the quality of the final output. So this is a really effective pattern. I use it all the time, and of course we'll have plenty of examples on the course, and you should be able to think about how you could apply this to LLM solutions in your day jobs right away.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
