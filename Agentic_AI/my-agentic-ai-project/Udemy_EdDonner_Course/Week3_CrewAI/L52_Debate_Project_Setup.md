# L52 — Day 1: Setting Up a Debate Project with GPT-4o mini

> **Week 3 — CrewAI** · ⏱️ ~9m · 🎥 Lecture 52 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821133

---

## 🎯 Ek Line Mein (TL;DR)

`crewai create crew debate` se **pehla CrewAI project scaffold** kiya — auto-generated folder structure (knowledge, src/debate, config YAML, tools, crew.py, main.py) samjha, aur **agents.yaml** me do agents define kiye: ek **debater** (role/goal/backstory + `{motion}` template variable) aur ek **judge**, model **GPT-4o mini** ke saath.

---

## 📝 Hinglish Explanation (Detailed)

- Ed Cursor me **week 3 ka `crew` folder** kholta hai — bilkul **empty**, kyunki CrewAI projects scratch se CLI tool ke through banaye jaate hain (notebooks nahi).
- Terminal kholo (Mac pe **Ctrl + backtick**, ya View menu → Terminal), `cd` karke crew directory me jao, aur run karo: **`crewai create crew debate`** — yaani naya crew project jiska naam `debate` hai.
- CLI turant ek **interactive setup** chalata hai — wo poochta hai kaunsa **provider/model** use karna hai. Ed chunta hai **OpenAI → GPT-4o mini** ("nice and cheap"). Ye **locked nahi** hai — baad me kabhi bhi change kar sakte ho.
- Jab CLI **API key** maange, to **bas Enter dabao** — wo tumhare liye `.env` file banane ki koshish kar raha hai, lekin hamare paas already **`.env` file** hai, isliye skip karo.
- Create hone ke baad CLI ek poora **scaffolding** (basic project framework) generate karta hai. Ek chhota Cursor/VSCode quirk: agar kisi folder ke andar **sirf ek hi subfolder** hai, to Explorer use **collapsed path** (`crew/debate`) ki tarah dikhata hai — confusing lag sakta hai. Ed isliye ek dummy `other` folder banata hai taaki tree alag-alag dikhe.
- **Generated project structure** (top-down):
  - **`knowledge/`** → `user_preference.txt` jaisi file — user ke baare me **background info** jo model ko di ja sakti hai (is project me use nahi karenge; ye optional scaffolding ka example hai).
  - **`src/debate/`** → **sabse important directory** — project ka asli code yahin hai (`src` ke neeche project-name wala subfolder).
  - **`src/debate/config/`** → **do YAML files: `agents.yaml` aur `tasks.yaml`** — yahi declarative config hai jisme agents/tasks define hote hain. Default me example agents (researcher, reporting analyst) pre-filled hote hain.
  - **`src/debate/tools/`** → custom tools ke liye scaffolding (is baar khaali chhodenge).
  - **`src/debate/crew.py`** → wo module jo **crew ko assemble** karta hai — yahin pe wo **decorators** (`@agent`, `@task`, `@crew`) use hote hain jo Ed ne pehle mention kiye the.
  - **`src/debate/main.py`** → entry point — yahin se crew **run** hota hai aur inputs set hote hain.
- Ab **`agents.yaml`** edit karte hain. Default researcher/analyst hata ke **sirf 2 agents** chahiye:
  - **Agent 1 — `debater`**: ek hi agent **dono sides** (for aur against) play karega — distinction **tasks** se aayega, agents se nahi.
    - **`role`**: "A compelling debater".
    - **`goal`**: "Present a clear argument either in favor of or against the motion. The motion is: **`{motion}`**".
    - **`{motion}` curly braces** = **template variable / placeholder** — runtime pe fill hota hai. Jab `crewai run` karoge, **`main.py` me `motion` ki value specify karni hogi** (debate ka proposal/topic).
    - **`backstory`**: "You're an experienced debater with a knack for giving concise but convincing arguments. The motion is: {motion}".
  - **Agent 2 — `judge`**:
    - **`role`**: "Decide the winner of the debate based on the arguments presented".
    - **`goal`** + **`backstory`**: "You're a fair judge with a reputation for weighing up arguments without factoring in your own views, and making a decision based purely on the merits of the argument..."
    - Fun fact: **Cursor ka autocomplete** in natural-language YAML fields ko khud suggest kar deta hai — agent definitions likhne me AI assist mil jaati hai.
- **Backstory kyun kaam karti hai — 2 mental models**:
  1. **Intuitive**: backstory = agent ka framing/persona — practically ye **system prompt** ka bada hissa ban jaata hai.
  2. **Scientific**: LLM bas **next most-likely token predict** karta hai. Agar input me ek specific backstory hai, to training data me aise backstories ke baad aane wale **consistent tokens ki probability badh jaati hai** — isliye persona-style prompting reliably kaam karta hai.
- Last me agent pe **model specify** kar sakte ho — `llm: gpt-4o-mini` likho ya fully-qualified **`openai/gpt-4o-mini`** (LiteLLM-style `provider/model` naming); default provider OpenAI assume hota hai.
- Agents YAML done — **next up: `tasks.yaml`** (agle lecture me).

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| `crewai create crew <name>` | CLI command jo poora project scaffolding (folders, YAML, crew.py, main.py) generate karta hai |
| Scaffolding | Auto-generated basic project framework — boilerplate jo aap fill/customize karte ho |
| `knowledge/` folder | User/background info files — model ko context dene ke liye (optional) |
| `src/<project>/` | Project ki sabse important directory — code + config yahin |
| `config/agents.yaml` | Agents ki declarative definition — role, goal, backstory, llm |
| `config/tasks.yaml` | Tasks ki declarative definition (agla step) |
| `crew.py` | Module jo decorators (`@agent`, `@task`, `@crew`) se crew assemble karta hai |
| `main.py` | Entry point — runtime inputs (jaise `motion`) yahin set hote hain |
| `role` / `goal` / `backstory` | Agent ke 3 core fields — identity, objective, persona/system-prompt framing |
| `{motion}` | YAML me curly-brace **template variable** — `crewai run` ke time `main.py` ke inputs se interpolate hota hai |
| Backstory (scientific view) | Input me persona dalne se output tokens us persona ke consistent hone ki probability badhti hai |
| `openai/gpt-4o-mini` | Fully-qualified model naming (`provider/model`) — LiteLLM convention; OpenAI default provider hai |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- `crewai create crew` bilkul **cookiecutter / `django-admin startproject`** jaisa hai — opinionated scaffolding, `src/` layout, config-as-YAML. Aap framework ke conventions follow karte ho, framework wiring karta hai.
- **agents.yaml + `{motion}`** = wahi pattern jo aap **Jinja2 templates ya `.format()`-style config interpolation** me use karte ho — declarative YAML me placeholders, runtime values `main.py` ke `inputs` dict se aati hain. Config (kya) aur code (kaise) ka clean separation.
- **`openai/gpt-4o-mini`** naming **LiteLLM** ka `provider/model` routing convention hai — ek string change karke pura crew Groq/Anthropic/Ollama pe shift ho jaata hai, jaise SQLAlchemy me sirf connection-string badalna.
- **Hands-on lab**: is lecture ka code khud chalane ke liye **`Practical/lab1_crewai_debate.py`** run karo (is repo me, `uv run` se chalta hai, **Groq pe free via LiteLLM**). Note: hamare labs course se thoda alag hain — **self-contained code-style** (YAML scaffolding nahi), to ye lecture ka `crewai create crew` + YAML wala flow lab me pure-Python `Agent(...)` objects se replicate hota hai — concepts same, packaging alag.

---

## 🧠 Takeaway (yaad rakho)

1. CrewAI projects **CLI se scaffold** hote hain: `crewai create crew debate` → knowledge/, src/debate/, config/ (agents.yaml + tasks.yaml), tools/, crew.py, main.py.
2. Agent ke 3 core fields: **role** (identity), **goal** (objective), **backstory** (persona) — backstory effectively **system prompt** ban jaati hai.
3. YAML me **`{motion}`** jaisa curly-brace placeholder runtime pe **`main.py` ke inputs** se fill hota hai — agents reusable templates ban jaate hain.
4. **Ek debater agent dono sides** argue karega — for/against ka distinction **tasks** se aayega, do alag agents banane ki zaroorat nahi.
5. Model per-agent specify hota hai: `gpt-4o-mini` ya **`openai/gpt-4o-mini`** (provider/model) — baad me ek line me swap possible.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

And welcome back to Cursor. And here we are in week three, the crew folder. How exciting. Let's open it up to see what treasures I have in store for you. And it's completely empty. It won't be empty for you, but it's empty for me. Because this is starting from nothing. The way that some of you like me to do it. Which is, uh, gonna happen this time. Because that's the way that Crew works.

So we will begin then by opening up a command line like this, a terminal, which you'll remember is control and the tick on a Mac. That is really the control button on the bottom left. And, uh, then, uh, or it's the view menu and terminal if you're using menus. So then what I'm going to do is I'm going to first change directory to go into the third directory. Right now we are in crew and I'm going to create a new crew project, which I do by saying crewai create crew. And then the name of the project. And we are going to call this project debate. For reasons that will become obvious, but probably already are, and it first asks us a question, and to read the question, I'll have to make this a bit larger. Um, and this is because when you first create a project, it puts in place, as I mentioned, some scaffolding, some sort of basic project framework. And in order to set that up, it wants to know which model would you like me to start with. So we're not necessarily fixing this, but we can start by saying OpenAI and we can always change it later. Select a model to use and we can choose GPT-4o mini to keep it nice and cheap. And then enter your key. Now at this point we should definitely just press enter because we already have a .env file. It's trying to build env files for us. We don't need that. We press enter and you'll see right here that it's created a bunch of files. And I'm going to remove the terminal for a second so that we can take a look at it, because they have appeared over on the left.

Now one thing to get in mind is that when when you're looking at the explorer in Cursor or in VSCode, if there's a directory like crew that only has one other directory called debate, then it shows like this. It doesn't bother showing multiple files, multiple folders under it. And that can be a little bit confusing. So we might go back into the terminal and just make a new directory. Let's let's make a directory and call it other. And when I do that you see what just happened. Now if we come in here, you'll see that there's both debate and there's an empty folder called other, which is going to make it a little bit easier on the eyes.

Okay. So now let's have a quick look at what has Crew created for us. So under debate, which is the name of our crew that we're about to make a debate crew, as you've probably guessed, there is a folder called knowledge and that has a file user preference, and that has some stuff about the person who's the the user. And you can change this. This would be background information that would be given to the model if we made it use of it, which we will not. So this is a sort of an example of some of the scaffolding that's created in case we need to use it. Then there is a folder called source. And under that folder there is a folder called debate. And again you're seeing it in this way in the explorer because there are no other folders other than debate under source. So sorry to recap. Under crew we have a folder called debate, which is the name of of the project that has a sub folder subdirectory source src and that has a subdirectory also with the project's name debate. And that is where we are right now. And this is the this is the most important directory of them all. This this directory named the project underneath source. And that has a few things in it. It has a config directory. The config directory has two YAML files agents and tasks. And here they are. And they're set up with some default example code in there that we will come back and look at in just a second. There is a tools folder that has just, again, some scaffolding, some some, some basic stuff here that we might want to fill in later that we won't do this time. And then if we come into the root folder of debate, you'll see that there is a file, a module called crew.py which has a bunch of scaffolding again, and then a main.py. So there we have it crew, the module, which is actually the one which brings together our crew, and it has the decorators that I mentioned to you, main. And then the two YAML files under config that has all been set up for us, ready for us to build our first crew.

All right. So we are now going to go and define our YAML, our configuration for our agents and our tasks, starting over here with the agents YAML file. And this contains some default some sort of scaffolding. Some example agents that are called the researcher and the reporting analyst are the two examples that's given. And we're going to change these to being what we're looking to build. And of course, we're looking to build a debate team. And in fact, we only need two agents for what we're looking to do. We want an agent that will be the debater. Our one agent is going to play both roles of being for and against the the motion. And then we will have a judge and those will be our two agents.

And now we need to describe what they are. And so the, the role is the first thing that we say here. And we're going to say a compelling debater right there okay. And now the goal is what what it's it's looking to achieve the objectives. And so let's see I'm going to actually copy across one that I did earlier. So you don't have to watch me typing everything. But we're going to present a clear argument either in favor of or against the motion. And the motion is and this is important, this little thing in in curly braces. Here is where you can effectively make this a template. That is something that's going to get defined when you run this agent framework. When we end up saying, crewai run, we are going to specify what we want motion to be, and we're actually going to specify that in main.py. So keep that in mind. In main.py we're going to have to set what is motion, the motion of the debate. The thing that we're putting forward the proposal that they will debate. Okay. And so now we have a back story, which is where we set the the it's really we know that this is the system prompt or a big part of it. But in Crew land, we want to think of this as the, as the sort of framing of this, of this agent, the back story. You're an experienced debater with a knack for giving concise but convincing arguments. The motion is so on. So that is the definition of our agent, our debater agent. And that will apply both for one that is presenting for an argument and against it. And of course we'll be using tasks to distinguish between them.

But now let's define our judge. So we are going to give the judge a role. And the role we will say is decide the winner of the debate. Look at how Cursor even suggests what this should be. Let's say based on the arguments presented, let's keep it short. And then the goal I will take one that I wrote earlier because it's a couple of sentences. You can see that that amazingly Cursor comes up with natural language. It's just great for these things already. So you can even define your agents just by letting Cursor describe them. And the backstory here I'm going to copy and paste in a nice juicy backstory, and here it is. You're a fair judge with a reputation for weighing up arguments without factoring in your own views and making a decision based purely on the merits of the argument. The motion is blah. So that's the sort of good way to set things like the backstory.

And again, on the one hand, one way of thinking about this is that this is the kind of backstory that an LLM is going to take into account in setting the context for this role. The other, more scientific way is just to always keep in mind that what LLMs are doing is predicting the most likely next token to follow an input. And the point is that if this backstory is part of the input, then you are increasing the probability that the output tokens will be consistent with this, because things that are seen at training time that have that kind of backstory often predict tokens consistent with that backstory. So that's the the more scientific way of thinking about why this tends to work really well.

All right. And then the final thing I'm going to add in here is you can also specify what model to use. And you can actually you can just have GPT-4o mini. Or if you want to really spell it out then you say openai/gpt-4o-mini, but it assumes OpenAI by default for that model. And this then is our YAML definition of the agents. Next up is tasks.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
