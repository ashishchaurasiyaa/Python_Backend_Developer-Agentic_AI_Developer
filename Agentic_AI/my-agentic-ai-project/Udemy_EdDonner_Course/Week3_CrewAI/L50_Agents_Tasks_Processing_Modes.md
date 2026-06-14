# L50 — Day 1: Agents, Tasks & Processing Modes

> **Week 3 — CrewAI** · ⏱️ ~8m · 🎥 Lecture 50 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821125

---

## 🎯 Ek Line Mein (TL;DR)

CrewAI ke 3 core building blocks — **Agent** (role + goal + backstory wala LLM unit), **Task** (description + expected output, ek agent ko assigned), aur **Crew** (agents + tasks ki team) — jo **sequential** ya **hierarchical** process mode me chalti hai, aur definitions **YAML config + decorators** se aati hain.

---

## 📝 Hinglish Explanation (Detailed)

- **Agent = smallest unit of work.** Ek **autonomous unit** jo ek **LLM** ke upar bana hai. Iske paas hota hai:
  - **role** — ye kya karta hai uska description
  - **goal** — isko achieve kya karna hai
  - **backstory** — context/persona dene wali kahani
  - Optionally **memory** aur **tools** bhi attach ho sakte hain.
- **Task = naya concept** (OpenAI Agents SDK me iska koi analog nahi tha). Task ek **specific assignment** hai jisme:
  - **description** (kya karna hai)
  - **expected_output** (output kaisa dikhna chahiye)
  - **agent** (kaun karega) — yaani **task ek agent ko assign hota hai**, aur ek agent ke paas **multiple tasks** ho sakte hain.
- **Crew = team of agents + tasks.** Baaki dono ka **aggregate**. Crew do **process modes** me chal sakti hai:
  - **Sequential** — tasks jis order me laid out hain, usi order me ek-ek karke execute hote hain.
  - **Hierarchical** — ek **manager LLM** decide karta hai ki kaun sa task kis agent ko jayega (delegation).
- **CrewAI zyada opinionated hai** OpenAI Agents SDK ke comparison me — zyada terminology, zyada **prescriptive**:
  - Last week agents ke paas sirf **instructions** thi (basically raw **system prompt**) — bilkul unopinionated, jaise chaho waise socho.
  - CrewAI me **role + goal + backstory** dena *padta* hai, aur ye teeno milke internally system prompt banate hain — exact constitution beginner level pe **hidden** hai (templates se override possible hai, par dig karna padega).
- **Trade-off discussion (important!):**
  - **Benefit:** role/goal/backstory force karna acchi baat hai — ye sab **good prompting best practices** hain (context do, backstory do).
  - **Cost:** agar kisi case me backstory relevant nahi hai ya alag tarike se sochna hai, to harder hai. Aur **debugging** me system prompt pe wahi direct control nahi milta — bas pata hai ki in building blocks se ban raha hai.
  - Ed ka point: har framework adopt karne ke **trade-offs** samajhna zaroori hai — ye ek classic example hai.
- **YAML configuration — CrewAI ki nice feature:** Agents aur tasks ko do tarike se banaya ja sakta hai:
  - **Code se:** `my_agent = Agent(...)` me LLM, role, backstory sab pass karo.
  - **YAML file se:** human-readable markup me `researcher` jaise agent ka **role, goal, backstory, llm** define karo — prompts code se **separate** ho jaate hain.
  - **Pro:** prompts code me jagah-jagah buried nahi rehte, **separation of concerns**, prompts pe independently kaam kar sakte ho.
  - **Con:** thoda **scaffolding** hai jo CrewAI-specific hai, get used to karna padta hai.
- Code me phir aap pura agent define karne ki jagah bas **config reference** karte ho (`config=self.agents_config['researcher']`) aur saare fields auto-populate ho jaate hain. Ed ko ye pasand hai kyunki ye **lightweight** hai — koi hidden magic nahi, config ka reference code me clearly dikh raha hai.
- **`crew.py` — sabse important module** jahan sab kuch aata hai. Isme **decorators** ka use hota hai (last week se decorators ka experience already hai):
  - **`@CrewBase`** — poori class ke upar jo crew manage karti hai
  - **`@agent`** — har us function pe jo ek agent banata hai
  - **`@task`** — har us function pe jo ek task banata hai
  - **`@crew`** — final function pe jo `Crew` instance return karta hai, jisme agents, tasks aur **`process=Process.sequential`** (ya hierarchical) pass hota hai — yahi wo jagah hai jahan processing mode set hota hai.
- **`self.agents` kahan se aaya?** Ye `@agent` decorator ka kaam hai — jis bhi function pe wo decorator hai, uska agent automatically instance variable `agents` ki list me add ho jata hai. Isliye bottom me directly `self.agents` refer kar sakte ho. Same logic `self.tasks` ke liye.
- Next lectures me proper coding example ke saath ye sab concrete hoga.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Agent** | Smallest autonomous unit of work — LLM + role + goal + backstory (+ optional memory, tools) |
| **Role / Goal / Backstory** | Agent ka prescriptive 3-part prompt structure — internally milke system prompt banta hai |
| **Task** | Specific assignment — description + expected_output + assigned agent (OpenAI SDK me ye concept nahi tha) |
| **Crew** | Agents + Tasks ka aggregate — poori team |
| **Sequential process** | Tasks laid-out order me ek ke baad ek execute hote hain |
| **Hierarchical process** | Ek **manager LLM** tasks ko agents me assign/delegate karta hai |
| **Opinionated framework** | Framework jo sochne ka tarika prescribe karta hai (CrewAI > OpenAI SDK is maamle me) |
| **YAML config** | Agents/tasks ki definitions (role, goal, backstory, llm) code se bahar human-readable file me |
| **`crew.py`** | Central module jahan agents, tasks aur crew decorators ke saath define hote hain |
| **`@CrewBase` / `@agent` / `@task` / `@crew`** | Decorators — class ko crew-manager banate hain aur agents/tasks ko auto-register karke `self.agents`/`self.tasks` me daalte hain |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **YAML config vs code** — ye bilkul Django settings ya Kubernetes manifests wali philosophy hai: behaviour code me, *content/config* declarative file me. Prompts ko YAML me rakhna waise hi hai jaise SQL queries ko ORM ke bahar `.sql` files me rakhna — non-devs (ya future-you) code touch kiye bina prompts tune kar sakte hain.
- **`@agent`/`@task` decorators ka auto-collect pattern** — ye wahi **class registry** pattern hai jo pytest fixtures, Celery `@task`, ya Flask route decorators use karte hain: decorator function ko wrap karke side-table (list) me register kar deta hai, isliye `self.agents` "magically" populated milta hai. SQLAlchemy ke declarative base jaisa metaclass-lite trick samjho.
- **Opinionated trade-off** — role/goal/backstory ko ek framework-imposed prompt template samjho, jaise Rails ke conventions vs raw Flask. Productive ho, par jab debugging me exact system prompt dekhna ho to abstraction ke neeche utarna padega (jaise ORM-generated SQL log karna padta hai).
- **Hands-on lab:** is lecture ka code khud chalane ke liye `Practical/lab1_crewai_debate.py` run karo (is repo me, `uv run` se chalta hai, Groq pe free via LiteLLM). Note: hamare labs course se thoda alag hain — self-contained code-style hai, lecture wala YAML scaffolding (`crew.py` + config files) nahi; concepts (Agent/Task/Crew/Process) wahi same hain.

---

## 🧠 Takeaway (yaad rakho)

1. CrewAI ke **3 core concepts**: Agent (LLM + role/goal/backstory), Task (description + expected_output + agent), Crew (dono ka aggregate).
2. **Task** OpenAI Agents SDK me nahi tha — ye CrewAI ka naya building block hai, aur ek agent ke multiple tasks ho sakte hain.
3. Crew ke **do process modes**: `sequential` (order me execute) aur `hierarchical` (manager LLM delegate karta hai) — `Crew(...)` me set hota hai.
4. CrewAI **zyada opinionated** hai — role/goal/backstory acchi prompting practice enforce karte hain, par system prompt pe direct control kam milta hai (debugging trade-off).
5. **YAML config + `crew.py` decorators** (`@CrewBase`, `@agent`, `@task`, `@crew`) prompts ko code se separate karte hain aur agents/tasks auto-register hote hain.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

So much as we started week two, we're now going to go through the core concepts of CrewAI, the sort of building blocks to understand how it works, and there's some similarities. First of all, there is an agent. An agent is basically the smallest unit of work, an autonomous unit, which is related to an LLM. It has an LLM underneath it, and it has something called a role, a description of what it does, a goal and a backstory. And it can also have memory and it can have tools. And that is how an agent is defined. And you can remember back to the OpenAI Agents SDK definition.

There is something new here. A task is another thing. And there wasn't an analog in the last framework. A task is a specific assignment that is going to be carried out. It has a description, it has an expected output, and it has an agent. So a task is assigned to an agent. So that is the distinction: agents, and then tasks. And there can be multiple tasks for an agent. And then a crew is a team of agents and tasks, and that is simply so — a crew is the aggregate of the other two. And a crew has two different process modes. One of them is called sequential, and that is where it will simply execute each task in turn as it's laid out. And the other is called hierarchical, and that is where an LLM will be used — a manager LLM — in order to assign tasks to agents. So those are the two different modes that you can operate in. So that gives you — these are the three core concepts to keep in mind.

So how do we think about this? So these are lightweight concepts, and they're certainly reminiscent of last week. I would say that it is a bit more opinionated than the OpenAI Agents SDK. There's a bit more terminology. It's a bit more prescriptive. So as a clear example, if you look at the agent there — if you remember last week, agents just had instructions. An instruction was basically the system prompt, and you provided the instruction, and that's very unopinionated. You can choose to think about instructions however you want. Now with CrewAI, an agent has a role, a goal, and a backstory. So it's a bit more — you can see immediately, it's more prescriptive in terms of how one is supposed to prime this LLM, and how that is constituted into a system prompt is something that's not immediately available. There are, in fact, ways that you can choose to set that — you can sort of put in templates — but that's somewhat hidden from you, certainly at the beginner level. If you just use it out of the box, you have to provide the role, the goal, the backstory.

And I think this is a really good example of the trade-offs between these different frameworks, because obviously forcing us to think in terms of a role and a goal and a backstory is good, because these are all sort of good prompting practices — to think about the context, to give the backstory. This is a good best practice. At the same time — so that's the benefit — the trade-off is that we might have a specific situation where we don't want to give a backstory, that's not relevant; we want to think about it differently. And that is completely possible with CrewAI, but it's going to be harder. We're going to have to then dig in and find out what's going on. And also, if we're trying to debug a problem and we're not sure what's happening, we don't have the same control over the system prompt. We just know that it's being constituted based on these various building blocks. So hopefully I give you this color because I want you to have a good sense of what are the trade-offs in adopting these different platforms. And that's a pretty important one.

So a nice feature of CrewAI is that you can do a lot of the definition of things like agents and tasks using configuration, which allows you to sort of nicely separate some of the text rather than having it embedded all over your code. So when you think about agents and tasks — those are the two things that make up a crew — agents and tasks can be created by code. You can say agent equals my agent, my agent equals Agent, open brackets, and then pass in a lot of things like the LLM to use and the role and the backstory and so on. Or instead of that, you can write a YAML file that looks a bit like this. We'll look at many of them in the course of this week, but it's a YAML file. If you're not familiar with YAML, it's a very simple, easy-for-humans-to-read kind of markup file. And it looks a bit like this. And this is going to allow us to lay out a role, a goal, a backstory, and an LLM associated with an agent called researcher, in this example. And that will allow us to separate out the configuration from the code.

And whilst that is, in some ways — as always, there's some pros and cons. The con is that it's a bit of something to get used to. It's some scaffolding, it's specific to CrewAI. There's definitely a great benefit that this means that you don't have your various prompts buried within your code all over the place. You've got it nicely separated out and you can work on that somewhat independently. So I think it's a nice touch. In your code, you can then create something like an agent, and instead of specifying all of the fields of an agent — like the role, goal, backstory — you can just simply select the configuration, as it shows in this code right here, and they will all be populated for you. So I like it because it's lightweight. It's not like there's magic happening behind the scenes. You clearly refer to the config right there. It's clear what's going on. And it has this nice separation of concerns, allowing us to work on our prompts separately from our code.

And then in addition to the YAML files, there are a couple of Python files, and the most important one is called crew.py. And it's where everything comes together. It defines your crew, and it's going to look a bit like this. And we're going to of course go and look at a proper example in a second, but it has some decorators over it — and you've now got a bit of experience with decorators from last week. And sure enough, CrewAI has decorators as well. And you can see that there is a few of them. It has CrewBase as the decorator you put around the whole class that's going to manage your crew. And then there's a decorator agent for each of your functions which creates an agent, and there's a decorator task for each of your functions which creates a task. And then there's decorator crew for your final function that generates your crew. And you can see that it creates an instance of Crew and it returns — and it passes in the agents, the tasks, and this thing that's telling it that it is sequential, not hierarchical. It's where you set that important different mode of processing.

And you can see that there it says agents is self dot agents. And you might wonder, where is that coming from? Well, that's really one of the roles of this decorator at agent — that is making sure that any function that has that decorator, automatically the agent that comes from that will be associated with the instance variable agents, will be added to that list. So that's why you can just simply refer to it at the bottom. So anyway, this will be more concrete when we look at a proper coding example. My main point is that there is this very important module crew, and it's where you define your agents, tasks and crew, and it uses decorators.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
