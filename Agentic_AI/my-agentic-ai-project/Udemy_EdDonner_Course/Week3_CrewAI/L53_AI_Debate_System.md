# L53 — Day 1: AI Debate System Using Crew AI

> **Week 3 — CrewAI** · ⏱️ ~12m · 🎥 Lecture 53 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821137

---

## 🎯 Ek Line Mein (TL;DR)

Pehla full CrewAI project complete — **tasks.yaml** mein 3 tasks (`propose`, `oppose`, `decide`) define kiye, **crew.py** mein `@agent`/`@task`/`@crew` decorators se sab wire kiya, **main.py** se `kickoff(inputs=...)` chalaya — aur OpenAI debaters ke beech **Anthropic Claude judge** bana, motion: "strict laws to regulate LLMs".

---

## 📝 Hinglish Explanation (Detailed)

- **Tasks define karna (tasks.yaml):** default scaffolding mein `research_task` aur `reporting_task` aate hain — unhe replace karke 3 custom tasks banaye:
  - **`propose` task** — `description`: "you are proposing the motion {motion}, come up with a clear argument in favor, be very convincing". `expected_output`: "your clear argument in favor of the motion in a concise manner". `agent: debater` — yahi line task ko ek agent se **associate** karti hai.
  - **`output_file`** — task ke YAML mein `output_file: output/propose.md` de sakte ho, to CrewAI us task ka result automatically ek **markdown file** mein save kar dega (subdirectory `output/` mein).
  - **`oppose` task** — copy-paste + Cursor autocomplete: "you are in opposition to the motion, come up with a clear argument against, be very convincing" → `output/oppose.md`.
  - **`decide` task** — "review the arguments presented by the debaters and decide which side is more convincing"; expected output: "your decision on which side is more convincing and why" → `output/decide.md`. Ye task `judge` agent ko assign hota hai.
- **Naming gotcha (important tip):** task ka naam aur agent ka naam **same nahi ho sakta** — conflicting names ka problem aata hai. Isliye task ko `judge` nahi bula sakte kyunki agent ka naam already `judge` hai. Safe convention: `propose_task`, `oppose_task` jaise suffix lagao (Ed ne short rakha, par decide ko "judge" naam nahi de paya).
- **crew.py — the wiring module:**
  - Scaffolding ek class banata hai (project name se — `Debate`) jiske upar **`@CrewBase` decorator** hota hai.
  - Generated code mein bahut saare **comments/boilerplate** hote hain (before/after hooks, links etc.) — Ed inhe delete karke clean rakhna prefer karta hai.
  - Class ke andar **`agents_config`** aur **`tasks_config`** variables hote hain jo `config/` folder ke YAML files ko point karte hain — alag config files chahiye to bas path change kar do.
  - **`@agent` decorator** — har method jo `Agent` return karta hai: `Agent(config=self.agents_config['debater'], verbose=True)`. `verbose=True` se run hote waqt nice print/trace milta hai. Dusra agent: `judge`.
  - **`@task` decorator** — `Task(config=self.tasks_config['propose'])` — bas ek line! `output_file` yahan repeat karne ki **zaroorat nahi** kyunki wo already YAML config mein hai. Ed ne sab one-liners mein tidy kiya — config-driven approach ka yahi benefit hai ki Python code minimal rehta hai.
  - **`@crew` decorator** — `Crew(agents=self.agents, tasks=self.tasks, process=Process.sequential, verbose=True)`. Magic: **`self.agents` aur `self.tasks` lists automatically ban jaati hain** `@agent`/`@task` decorators se — manually collect karne ki zaroorat nahi. `Process.sequential` choose kiya (hierarchical bhi option hai jisme ek manager agent hota hai).
- **main.py — run locally:**
  - File khud kehti hai: "intended to run your crew locally, refrain from adding unnecessary logic."
  - **`inputs` dictionary** yahan define hoti hai — YAML mein jo **`{motion}` template placeholder** dala tha, uski actual value yahan set hoti hai: `inputs = {"motion": "There needs to be strict laws to regulate LLMs"}`.
  - Run: `result = Debate().crew().kickoff(inputs=inputs)` aur phir **`print(result.raw)`** — `.raw` final task (decide) ka raw output deta hai jo final agent (judge) ne produce kiya.
- **Multi-LLM twist:** dono agents OpenAI pe the — Ed ne judge ko **`anthropic/claude-3-7-sonnet-latest`** pe switch kiya. Ab **Anthropic, OpenAI ke debates ko judge kar raha hai** — LiteLLM ki wajah se sirf model string badalni padi, code same.
- **Run karna:** terminal mein project directory (`crew/debate`) mein jao aur **`crewai run`** type karo. First run pe **uv** environment build karta hai (one-time), uske baad instantly chalta hai.
- **Result:** proposer ne argue kiya, opposer ne counter kiya, phir Claude ne socha aur decide kiya — **"arguments in favor of the motion are more convincing"** — yaani LLM khud bol raha hai ki LLMs pe strict regulation honi chahiye! Verbose mode mein thinking ka trace dikhta hai.
- **Output folder:** run ke baad `output/` directory create hoti hai jisme `propose.md` (ethical/safety/social challenges → regulation needed), `oppose.md` (regulation hinders creativity/innovation), aur `decide.md` (judge ka final verdict) — teeno readable markdown files.
- **Recap of the full flow:** YAMLs set kiye (agents + tasks with `{motion}` template) → `crew.py` mein decorators se wiring → `main.py` mein inputs dict + `kickoff()` → `crewai run`. Ed encourage karta hai: yahi project khud banao ya at least `crewai run` se chala ke feel lo.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Task (YAML)** | `description` + `expected_output` + `agent` — kaam ki definition jo ek agent ko assign hoti hai |
| **`agent:` field in task** | Task ko kis agent se associate karna hai — YAML mein hi mapping ho jaati hai |
| **`output_file`** | Task ke result ko automatically file mein save karna (e.g., `output/propose.md`) |
| **Task/Agent name conflict** | Task aur agent ka same naam nahi ho sakta — `propose_task` jaise suffix safe hai |
| **`@CrewBase`** | Class-level decorator jo poori crew class ko CrewAI ka scaffolding deta hai |
| **`agents_config` / `tasks_config`** | Class variables jo `config/` folder ke YAML files ko load karte hain |
| **`@agent` decorator** | Method ko agent factory banata hai; sab agents auto-collect hokar `self.agents` mein aate hain |
| **`@task` decorator** | Same for tasks — `Task(config=...)` one-liner, auto-collected in `self.tasks` |
| **`@crew` decorator** | Final assembly — `Crew(agents, tasks, process, verbose)` return karta hai |
| **`Process.sequential`** | Tasks ek ke baad ek chalte hain (vs `hierarchical` jisme manager agent delegate karta hai) |
| **`verbose=True`** | Run ke dauran agents ki thinking/trace screen pe print hoti hai |
| **`inputs` dict + `{motion}`** | YAML ke template placeholders ki values jo `kickoff(inputs=...)` se inject hoti hain |
| **`result.raw`** | Kickoff result ka raw text — final task ke final agent ka output |
| **`crewai run`** | Project run karne ki CLI command — first time uv se environment build karta hai |
| **LiteLLM model switch** | Judge ko `anthropic/claude-3-7-sonnet-latest` pe shift karna = bas string change |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **`@agent`/`@task`/`@crew` decorators = class-level registry pattern** — bilkul waise jaise pytest fixtures ya Flask ke route decorators methods ko collect karte hain. `@CrewBase` metaclass-style magic se decorated methods ko scan karke `self.agents`/`self.tasks` lists auto-populate karta hai — isliye crew() mein manually list banane ki zaroorat nahi.
- **YAML config + `{motion}` templating = 12-factor config separation** — prompts (data) YAML mein, orchestration (code) Python mein. `kickoff(inputs=...)` runtime pe template render karta hai, jaise Jinja2 context inject karna. Naming conflict wala gotcha waise hi hai jaise ek module mein same naam ke do symbols clash karte hain.
- **`output_file` declarative side-effect hai** — task ka artifact disk pe auto-persist hota hai, code mein file-handling likhe bina. CI pipelines ke artifact outputs jaisa mental model rakho.
- 🧪 **Hands-on lab:** is lecture ka code khud chalane ke liye `Practical/lab1_crewai_debate.py` run karo (is repo me, `uv run` se chalta hai, Groq pe free via LiteLLM). Note: hamare labs course se thoda alag hain — self-contained code-style hai (YAML scaffolding nahi), aur lecture wale "OpenAI debaters + Anthropic judge" split ki jagah free Groq models use hote hain; concepts (Agent/Task/Crew/sequential/kickoff) same hain.

---

## 🧠 Takeaway (yaad rakho)

1. Task YAML = `description` + `expected_output` + `agent` (+ optional `output_file`) — aur task ka naam agent ke naam se **alag** rakhna zaroori hai.
2. `crew.py` mein 3 decorators sab kuch karte hain: `@agent` aur `@task` factories register karte hain, `@crew` unhe `Process.sequential` ke saath assemble karta hai.
3. `main.py` sirf inputs set karta hai — `{motion}` jaise YAML placeholders `kickoff(inputs={...})` se fill hote hain; `result.raw` final output deta hai.
4. LiteLLM ki wajah se judge ko Anthropic pe switch karna one-line change tha — multi-provider crews trivially easy hain.
5. `crewai run` se project chalao (first run pe uv env banata hai); results `output/` folder mein markdown files ke roop mein milte hain.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

And now we move on to tasks. And here you'll see that there is a research task and a reporting task. By default. But we're going to change this and we're going to have a few different tasks. We're going to have a task called propose. This is of course going to be the task which is about proposing a motion. And so the description what is this task. It's going to be your proposing the motion and then the motion that gets passed in when we do that part. Come up with a clear argument in favor of the motion. Be very convincing. Then we're going to have an expected output, which is going to be quite simple. The expected output is going to be your clear argument in favor of the motion in a concise manner. The agent. So this is where you associate a task with an agent. And obviously this is going to be associated with the debater agent. And then there's one other thing we can do here which is an output file. We want to put this in a subdirectory output and we will call it propose.md. And so there you have our proposal task.

So now we're going to have another task which I'm going to copy and paste. And this one is going to be oppose. This is the debater that's saying no. Description: instead of proposing you are in opposition to the motion, come up with a clear argument against the motion. Looks like Cursor can help there. It does help. Be very convincing. Your clear argument against the motion. And that should be oppose. It's amazing, isn't it? So Cursor does all the work for us.

And now we have our final task, which is going to be called decide. And uh, as a little tip here, something which is worth knowing is that you cannot call your tasks the same thing as you call your agents, or you will have a problem with conflicting names. So sometimes it's better to call this like propose_task, oppose_task. But I've kept it short. But we couldn't, for example, call this task judge. Otherwise that would conflict with the agent that we called judge. All right. So description we will say review. Let me see. Now review the arguments. Here we go. Review the arguments presented by the debaters and decide which side is more convincing. And we'll just change this to delete all of this. We don't need any of that. We just need to say the expected output is your decision on which side is more convincing. And let's say and why. All right. And then this should go please to a folder output and decide. All right. That seems good. So there are our tasks.

Okay. So the final step really is — is the final steps is — setting up crew.py and main.py. And then we'll be ready to go. So this is the default module crew.py. And you can see it's got some stuff in here based on the standard scaffolding. It has created a class. And it's got this crew base decorator around it. And this class is named the same as the name of our project, debate. So it's set that for us and it called it Debate Crew, which is exactly right. Now one of the things I dislike a bit is that it does generate all of this scaffolding code, all this standard code with lots of comments, and you can read some of the comments and follow the links. And it's got stuff like there's ways that you can add in functions that get called at the beginning and end and stuff like that. But I do find that these comments get in the way a bit, and I usually start by coming through and deleting everything in these just to keep it nice and clean.

But what you'll see that it's done that is nice is that it brings in the agent's config and the tasks config. It just brings them in from the config folder right here. So those are set as variables for this class. And you can see how it refers directly to our configuration. And of course, that means that if you had different configuration files, then you could bring them in just like that. Then this is stuff about how you can bring in your own tools. And then this is where we set up our agents. So obviously we don't have an agent called researcher. We have an agent called debater. And the agent decorator is telling Crew that this is an agent. It's going to return an agent, the config. We're going to want to change that to debater and we'll leave it verbose. True. Which means that we'll get a nice sort of print as it's running with what's going on. And then we'll have another agent and remember the name of this guy. Well, even if you don't, luckily Cursor does and it's filled it in in both places. There we go. The judge is our other agent.

All right. And now I'm getting rid of the comments about tasks. But it tells you about how you can do things like track outputs and dependencies and the like. But we're going to go on and define our tasks. They have, again, the decorator task. And now we're going to have a task called propose. And there we go. Cursor fills it in. Now it has an output file listed there. But we don't need that because it's already specified in our config file. So that's not actually needed. And you know now that I look at this I do — I have to say I think this would be cleaner if we have this all on one line like this, we don't need to be on multiple lines. And now you can see how very simple this whole function is going to look. And look, Cursor is going to do it for us. And then we can just delete that. Sorry I'm tidying this all up — when you see how much better it is when this is in JupyterLab. And you don't have to watch me doing all this. So don't hate me. I'll be quick, but I think it's nicer if we have it looking nice and sharp like that. You see how nice and simple and clean this is? And that's the benefit of using the config — that we don't need to have too much here. And then the other task is oppose. And obviously it brings in the config for oppose. And then the final one is decide. And there we go. Thank you Cursor for filling that in for us. So those are our two agents and three tasks. And we are down to the final section here.

Okay. So now we create the crew. And this is in the function crew. And it has the decorator crew. And I'm going to take out the piece there which we will be coming to later. So we just simply have to create an instance of Crew. We populate the agents with agents and as CrewAI helpfully tells us, this is automatically created by the agent decorator. We populate it with the tasks that are similarly created. This is where we choose to be sequential rather than hierarchical in our process, and that we want to be verbose. And then there's some stuff about being hierarchical if you want to. Okay, that's it for our crew object. We're almost finished. That was our crew module.

We're now going to the main module where we finish things off. So this is the — again there's all of this stuff that you can read. This main file is intended to run your crew locally. So refrain from adding unnecessary logic. Gotcha. So inputs — when we're running the crew, this is where we choose those template values that we put in our YAML file. This is where we choose what we want them to be. And so what we want them to be here is we want to have a motion and we want to give ourselves a nice motion. We don't have this — we only have the one field motion. And what motion? What do we think that we would like them to debate? Let's have the motion: there needs to be strict laws to regulate LLMs. There we go. That's a nice meaty topic for them to debate. And then we've got our stuff down here. We will come back to this stuff. We don't care about any of that. That is all it should take. We should now be ready to run our first crew just based on that.

Actually, just before we run, let me make another little change that in this main module. I'm just going to make sure we print the result to the screen just to be satisfying. It will be saved to a file as well. Result equals debate crew kickoff. And then we will print result dot raw. That will print the raw output from the final task sent to the final agent. And then maybe one other little change I'll make is I realize we're right now sending both the debater and the judge to be OpenAI, but it would be more interesting to switch this one up. Let's flip it. As Cursor suggests, let's use Claude 3.7 Sonnet latest. The latest Claude 3.7 model so that we have Anthropic judging OpenAI's debates. And this also means that we'll be using Anthropic this time, which was harder for us last time.

Okay, so with that now I think we should be ready. We can bring up a terminal. Here it is. We will want to change into the directory for crew and then the directory for debate. And now we simply type crewai run to kick off the run. And the first time you do this, it's going to do some uv stuff to build the environment. But I've already done it, so it's running right away. You can see it's executing tasks. The debater — each of the agents is running its debate right now. The debater for the proposer has already said — the against is now debating. And now we're deciding on the winner of the debate based on the arguments. It is Anthropic that is thinking. And with any luck, we will soon see whether Anthropic decides for or against the motion. Here we go. Let me see. In evaluating, I found the arguments in favor of the motion to be more convincing. So the view is that there should be strict laws to regulate large language models, such as the very one that is making the judgment here.

Okay. So that ran. And look, that's quite a wordy response that came from Anthropic. There you get to see in here the trace of the thinking that happened. And you'll see that an output directory has been created. And if we open this up — and if I close this terminal so it's not in the way — we can go into the output, and you'll see that there is a weighty argument in favor of LLM law regulation that you can read about, about the ethical, safety and social challenges necessitating strict regulatory frameworks. And then the opposing thinking as well. It's no doubt going to be about hindering creativity. Yes. Very good. And I'm sure there's some compelling arguments there, too. And then the decision is the thing that we already saw printed a moment ago that came from Anthropic.

And so that is our first experiment into the world of Crew. We set up our YAMLs. We set up our overall module for crew, the crew module. And then the main.py was where we set the motion, which was the thing that was templated in the various YAML documents. And we actually ran our debates with debate crew kickoff, passing in the inputs, this dictionary of the templated keys with their values. So I hope you enjoyed our first foray into CrewAI, and I very much encourage you to do the same thing. Well, of course you will actually see this debates project in there, but you can go and make a second one. Or just run this by typing crewai run and get a handle — get a good sense for how CrewAI works.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
