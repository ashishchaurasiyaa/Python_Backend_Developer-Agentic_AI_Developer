# L58 — Day 3: Crew AI Stock Picker

> **Week 3 — CrewAI** · ⏱️ ~7m · 🎥 Lecture 58 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821179

---

## 🎯 Ek Line Mein (TL;DR)

Naya project **Stock Picker** start hota hai — 4 agents (**trending_company_finder**, **financial_researcher**, **stock_picker**, **manager**) aur 3 tasks YAML me define karte hain, aur is baar 3 nayi cheezein aayengi: **structured outputs (output_pydantic)**, **custom tool** (push notification), aur **hierarchical process** jisme manager agent tasks delegate karta hai.

---

## 📝 Hinglish Explanation (Detailed)

- Week 3, Day 3 — naya project: **Stock Picker**. Disclaimer clear hai: ye sirf learning/investigation ke liye hai, **real trading decisions ke liye use mat karo**.
- Pehle **5-step recipe** ka recap (har CrewAI project me same):
  1. `crewai create crew <project_name>` — scaffolding banao
  2. **YAML files** fill karo (`agents.yaml`, `tasks.yaml`)
  3. **crew module** (crew.py) complete karo
  4. **main.py** update karo — run ke inputs set karne ke liye
  5. `crewai run` — chalao
- Is project me **3 nayi cheezein** explore hongi:
  - **Structured outputs** — Week 2 (OpenAI Agents SDK) me dekha tha, ab CrewAI me wapas aayega (**output_pydantic**)
  - **Custom tool** — ek existing tool (search) ke saath apna khud ka tool banayenge (push notification bhejne ke liye)
  - **Hierarchical process** — ab tak sab **sequential** tha; is baar CrewAI khud manage karega ki kaunsa task kahan jaye. Ed bolte hain isme thoda "adventure" hoga (yaani perfectly smooth nahi chalega — spoiler!)
- Setup: Cursor me project directory `3_crew` me jaake terminal se `crewai create crew stock_picker`. Provider **OpenAI**, model **GPT-4o mini** choose kiya, env variables setup skip kiya.
- Phir `src/config` me jaake **agents.yaml** — is baar 4 agents:
  - **trending_company_finder** — news padhke kisi sector me **2-3 trending companies** dhundta hai (further analysis ke liye)
  - **financial_researcher** — trending companies ke details milne par **comprehensive analysis** deta hai; backstory: "financial expert with a proven track record of deeply analyzing hot companies"
  - **stock_picker** — researched companies ki list me se **best ek pick** karta hai, user ko notify karta hai, detailed report deta hai; goal me explicitly likha: **"Don't pick the same company twice"** (ye aage memory ke saath kaam aayega)
  - **manager** — naya concept! Bahut **simple/vanilla** rakha hai: "skilled project manager who can delegate tasks", goal = "pick the best company for investment". Hierarchical process me yahi delegation karega.
  - Sab agents ke liye **GPT-4o mini** — but Ed bolte hain different models substitute karke khelna fun rahega.
- Phir **tasks.yaml** — 3 tasks, aur Ed ka mantra: task descriptions **very clear, very simple** rakho:
  - **find_trending_companies** — "find top trending companies in the news in this sector by searching the latest news; find NEW companies you've not found before"; agent = trending_company_finder; **output_file = output/trending_companies.json** (JSON kyun? — structured outputs ki wajah se, agle lecture me clear hoga)
  - **research_trending_companies** — list milne par har company ka detailed analysis report me; agent = financial_researcher; **context = find_trending_companies** (yaani pichle task ka output input ban jata hai); output file bhi set
  - **pick_best_company** — research findings analyze karo, best company pick karo, **user ko push notification bhejo** (ye hi naya custom tool hoga!), 1-sentence rationale + detailed report (kyun chuna, kaunsi reject hui); agent = stock_picker; context = research_trending_companies
- Abhi tak **task ↔ agent ka 1-to-1 correspondence** hai (har task ka apna dedicated agent).
- **Pro tip (Ed ka tested):** agents aur tasks me **consistent language** use karo — jaise "trending companies" har jagah same phrase. Ed ne iterate karke dekha — inconsistent wording se **less stability** aati hai. Crisp, instructive prompts = coherent responses (although fully perfect coherence phir bhi nahi milti, as we'll see).

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **5-step crew recipe** | `crewai create crew` → YAML fill → crew.py → main.py inputs → `crewai run` |
| **Structured outputs** | LLM ka output free-text nahi, fixed **pydantic schema** me — CrewAI me `output_pydantic` se (isliye output file `.json` hai) |
| **Custom tool** | CrewAI ka built-in tool nahi, apna khud ka banaya tool — yahan push notification bhejne wala |
| **Hierarchical process** | Sequential ke bajaye ek **manager agent** decide karta hai kaunsa task kis agent ko delegate ho |
| **Manager agent** | Simple "project manager" agent — role/goal vanilla rakha, sirf delegation ke liye |
| **context (task)** | Ek task ko dusre task ka output input ke roop me dena — task chaining ka CrewAI tareeka |
| **output_file** | Task ka result disk pe save karna (e.g., `output/trending_companies.json`) |
| **Consistent language** | Agents + tasks me same terminology — prompt stability ka secret sauce |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **tasks.yaml ka `context` field = DAG dependency declaration** — bilkul Airflow ke `task_a >> task_b` jaisa. Sequential mode me ye explicit data-flow edges hain; hierarchical mode me manager (ek LLM) dynamically routing karta hai — yaani deterministic DAG vs runtime scheduler ka difference.
- **`output_file: *.json` + output_pydantic** — ye wahi pattern hai jo aap API responses me karte ho: response model pydantic se validate karo, phir serialize. LLM output ko "typed contract" dena hallucinated-format bugs ka best fix hai.
- **Manager agent ko deliberately vanilla rakhna** smart hai — wo ek orchestrator hai, domain worker nahi. Jaise Kubernetes scheduler ko business logic nahi pata hota; usse sirf "kya delegate karna hai" pata hona chahiye.
- **Hands-on lab:** is lecture ka code khud chalane ke liye `Practical/lab3_stock_picker.py` run karo (is repo me, `uv run` se chalta hai, Groq pe free via LiteLLM). Hamare lab me course se thoda difference hai: self-contained code-style hai (YAML scaffolding nahi), aur news search ke liye SerperDev ki jagah **free Wikipedia search tool** use kiya hai — concepts (4 agents, 3 tasks, context chaining, custom push-notification tool, hierarchical attempt) same hain.

---

## 🧠 Takeaway (yaad rakho)

1. CrewAI project ka **5-step recipe** ab muscle memory hona chahiye: create → YAML → crew.py → main.py → run.
2. Stock Picker me 3 nayi cheezein: **structured outputs**, **custom tool** (push notification), **hierarchical process** — teeno production-agent patterns hain.
3. **Task chaining `context` se hota hai** — pichle task ka output agle ka input; abhi 1 task = 1 agent mapping hai.
4. **Manager agent simple rakho** — sirf delegation goal, koi domain detail nahi.
5. **Consistent terminology** agents + tasks me use karo ("trending companies" everywhere) — Ed ka tested pro tip, warna output unstable hota hai.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

And welcome to Crew week three, day three. It is time for us to build a new project: the stock picker that I'm looking forward to showing you. A quick reminder on the five steps that we use to build a crew project from last time: we use crewai create crew, we fill in the YAML files, we complete the crew module, we update main.py to set any inputs for doing the run, and then we call crewai run.

This time we're going to be going deeper again in three new ways. First of all, structured outputs will have a comeback. We looked at them last week. We'll do them again with Crew. We'll use a custom tool — in addition to the tool that we'll use again, we'll also build our own tool. And then thirdly, we will try out the hierarchical process, allowing Crew to manage the process of what task goes where. And as you'll see, we'll have a bit of an adventure with that. All right. Let's get started.

Okay. Here we are back in Cursor, back in project directory three, crew. And let's open this up and we will bring up a terminal window again. As before, we'll go into that directory and we're going to create our new project, which is of course crewai create crew, and then the name of the project, which is going to be stock_picker — a project to create recommendations for investing in the stock market, bearing in mind that this is purely for our own investigatory purposes and you should not use this to make any trading decisions, please.

Okay. We're going to select OpenAI as our provider. And we're going to choose GPT-4o mini. And we're not going to set up any env variables. And the crew has been successfully created. All right. It's now first of all time for us to open up our stock picker. And as usual go into source, go into config. And the first step is to create our agents. So we will go ahead and do that now.

Okay. So here we are in agents YAML. And we're going to create the agents for this project. And there's going to be a few of them. So I'm going to bring them in an agent at a time so that we can talk them through. So the first agent is called the Trending Company Finder. And it's responsible for looking in the news and finding trending companies in a particular sector. So you read the news, you find 2 to 3 companies that are trending for further analysis. And we'll use GPT-4o mini here. But you can of course substitute in whichever model you'd like. And it might be fun to play around with different ones.

The next one we will use — and let me make sure I paste this in properly, there we go — is a financial researcher. The financial researcher: given details of trending companies, you provide comprehensive analysis. So: financial expert with a proven track record of deeply analyzing hot companies. Again we'll go with GPT-4o mini, as the backstory.

Okay, one more agent that we're going to work with, and that next agent is going to be a stock picker. So we've found trending companies in the news, we've researched those trending companies — what's left to do is to pick one. So the stock picker: given a list of researched companies with investment potential, you select the best one for investment, notifying the user and then providing a detailed report. Don't pick the same company twice. You're a meticulous, skilled financial analyst with a proven track record of equity selection. These are all great ideas for well crafted prompts to be using. And again, we'll use GPT-4o mini for now, and let's save that.

I'm going to add in one more agent as well — a new agent for us to be exploring this time. And the new agent is going to be a manager. But I'm going to keep this manager very simple. The role is a manager, and I'm saying you're a skilled project manager who can delegate tasks in order to achieve your goal, which is: your goal is to pick the best company for investment. And that's it. So very simple, vanilla description of that agent. And therein there is our four agents for this project. So far so good.

You like those four agents — it's time for us to define the tasks. And when defining tasks, the trick is to be very clear, very simple. And so the first task is a find trending companies task. Find the top trending companies in the news in this sector by searching the latest news. Find new companies that you've not found before. And the output: a list of trending companies in that sector. And we are going to assign it, of course, to the agent — the trending company finder is the agent that will work on this. And it will put it in an output file: trending companies, in output dot json. You may be wondering why that says JSON. It will become clear in one second.

Okay. So then going to have our next task. And our second task is going to be a research trending companies task. The description is: given a list of trending companies, provide a detailed analysis of each company in a report. And the agent of course will be the financial researcher, the second agent that we made. So there's this 1-to-1 correspondence between a task and an agent right now. And we're giving it — we're telling it to have some context. And the context is the find trending companies task. And we're asking it to put it in an output as well.

And you can see that already Cursor is one step ahead. But we're going to ignore Cursor, and I'm going to put it in myself. The pick best company task is the final task in the list. It's of course assigned to the stock picker agent, and it is to analyze research findings, pick the best company for investment, then send a push notification to the user. That's a new one. You can imagine that it's going to be the tool that we will add — a tool that we've used before, but the first time in Crew. And we'll ask for a one sentence rationale, and then respond with a detailed report on why you chose this company and which companies were not selected. And then the agent, I just said, was the stock picker. And the context is of course the research trending companies.

So there we have it. We've now defined our tasks. And again, it's worth noticing how I've made these prompts very instructive, very crisp. I've used consistent language with things like "trending companies". All of these — these are all small steps that help make sure you get coherent responses. Although as you'll see, it's not going to be perfectly coherent. But it definitely helps. And I've experimented with this a fair bit. And in previous versions, when I was iterating on this, I had inconsistent language between agents and tasks, and it definitely causes less stability. So I think that's a pro tip for you.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
