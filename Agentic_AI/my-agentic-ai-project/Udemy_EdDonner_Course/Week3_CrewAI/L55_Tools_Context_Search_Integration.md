# L55 — Day 2: Tools, Context & Google Search Integration

> **Week 3 — CrewAI** · ⏱️ ~6m · 🎥 Lecture 55 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821161

---

## 🎯 Ek Line Mein (TL;DR)

Day 2 of CrewAI: pichle din ka recap (**Agent**, **Task**, **Crew** + 5-step project setup), aur aaj do nayi cheezein — **Tools** (agents ko capabilities dena) aur **Context** (ek task ka output doosre task ko pass karna) — saath mein **Serper** API se Google search integration, aur naya project `financial_researcher` create karna.

---

## 📝 Hinglish Explanation (Detailed)

- **Recap — Agent kya hai:** Agent CrewAI ka **smallest autonomous unit** hai. Iske saath ek **LLM** associated hota hai — technically zaroori nahi (LLM-less agent bhi ban sakta hai), but typically hota hai. Har agent ke paas **role**, **goal**, **backstory** hota hai, plus **memory** aur **tools** bhi attach ho sakte hain (jo abhi tak humne explore nahi kiye the — aaj tools dekhenge).
- **Recap — Task:** Ye wo concept hai jiska **OpenAI Agents SDK mein koi analog nahi** hai. Task = ek assignment with **description**, **expected_output**, optionally ek **output_file**, aur ye kisi specific **agent ko assigned** hota hai.
- **Recap — Crew:** Agents + Tasks ki team. Do **Process modes**: **sequential** (tasks order mein chalein) ya **hierarchical** (tab ek **manager LLM** assign karna padta hai jo decide kare kaunsa task kis agent ko jaye).
- **Recap — 5 setup steps** (pichli baar debate project mein kiye the):
  1. `crewai create crew my_project` — pura **file system scaffolding** auto-generate ho jata hai.
  2. `src/<project>/config/` mein jao — wahan **YAML files** milti hain (default: ek agents ke liye, ek tasks ke liye; naam custom rakh sakte ho). Inhe details se fill karo.
  3. `crew.py` module mein **decorators** wale pre-setup functions use karke agents, tasks, crew create karo. YAML config reference hota hai — **but optional hai**: chaaho to fields manually code mein pass kar sakte ho. YAML ka fayda: **prompting text code se alag** rehta hai — clean separation.
  4. `main.py` update karo — run parameters / **inputs** set karo (debate mein topic/motion AI regulation tha).
  5. Project folder ke andar se `crewai run` — behind the scenes run hota hai aur crew off to the races.
- **Aaj ke 2 naye topics:**
  - **Tools** — agents ko capabilities equip karna, "CrewAI style" mein dekhenge.
  - **Context** — CrewAI ko batana ki **ek task se doosre task tak kaun si information pass** honi chahiye.
- **Serper API signup (free!):** OpenAI Agents SDK ke experience se bilkul contrast — yahan **Serper** use karenge, jo code se **lightning-fast Google queries** chalane ka API hai, "unbeatable price" pe.
  - `serper.dev` pe sign up karo → **2500 free credits** milte hain — course ke liye more than enough.
  - API Key page se key copy karo → `.env` file mein **`SERPER_API_KEY`** naam se daalo (Cursor typing par prompt bhi karega).
  - **Naam ka funda:** SERP = **Search Engine Results Page** — is type ki services ka common naam.
  - ⚠️ **Confusion alert:** ek similar-named service hai **SerpAPI** — wo alag hai! Ensure karo ki **Serper** wali key hi use ho.
- **Naya project create karna:** debate folder band karo, week 3 ke crew folder mein fresh terminal kholo, teesre folder (crew) mein jao.
  - Command: `crewai create crew financial_researcher` (note: **crew**, not **flow** — flow alag cheez hai).
  - Setup wizard mein pehle ki tarah **OpenAI + GPT-4o-mini** choose karo, key setup **skip** karo.
  - `financial_researcher` project + pura scaffolding ready — yahin se aaj ka building start hoga.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Agent** | CrewAI ki smallest autonomous unit — role, goal, backstory + (optional) LLM, memory, tools |
| **Task** | Ek assignment: description + expected_output + (optional) output_file, kisi agent ko assigned; OpenAI SDK mein iska analog nahi |
| **Crew** | Agents + tasks ki team jo sequentially ya hierarchically chalti hai |
| **Hierarchical process** | Process mode jisme **manager LLM** decide karta hai kaunsa task kis agent ko jaye |
| **Tools** | Agents ko di gayi capabilities (e.g., web search) — aaj ka pehla naya topic |
| **Context** | Mechanism jisse ek task ka output doosre task ko input ke roop mein pass hota hai |
| **Serper** | serper.dev ka API — code se fast Google search; 2500 free credits |
| **SERP** | Search Engine Results Page — search-API services ka common naam |
| **`SERPER_API_KEY`** | `.env` mein daalne wali env variable (SerpAPI se confuse mat hona!) |
| **`crewai create crew <name>`** | Naya crew project + scaffolding generate karne ki CLI command (flow se alag) |
| **YAML config** | `config/` folder ki agents/tasks files — prompting text ko code se separate rakhti hain |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **YAML config vs code** wali baat aapko 12-Factor App jaisi lagegi — prompts ko config treat karna waise hi hai jaise aap DB URLs ko env/config mein rakhte ho, code mein hardcode nahi karte. CrewAI ka scaffolding (`crewai create crew`) basically **cookiecutter template** hai — ek command, pura project layout ready.
- **Task context** ko aap ek DAG/pipeline ki tarah socho — jaise Airflow mein ek task ka XCom output downstream task ka input banta hai. CrewAI mein `context=[task1]` declare karke aap explicitly data-flow edges define karte ho.
- **Serper** ek thin REST wrapper hai Google SERP ke upar — aapke liye ye bas ek aur third-party API hai jiski key `.env` mein jati hai. Lookalike-naming trap (Serper vs SerpAPI) waise hi hai jaise PyPI pe typosquatted packages — exact naam verify karo.
- **Hands-on lab:** is lecture ka code khud chalane ke liye `Practical/lab2_financial_researcher.py` run karo (is repo me, `uv run` se chalta hai, Groq pe free via LiteLLM). Hamare labs course se thoda alag hain: self-contained code-style (YAML scaffolding nahi), aur lecture ke SerperDev search ki jagah hum **free Wikipedia search tool** use karte hain — to Serper signup optional hai agar aap sirf lab chalana chahte ho.

---

## 🧠 Takeaway (yaad rakho)

1. CrewAI structure = **Agent** (role/goal/backstory + LLM/memory/tools) → **Task** (description/expected_output/output_file, agent-assigned) → **Crew** (sequential ya hierarchical + manager LLM).
2. Project setup ke **5 steps**: `crewai create crew` → YAML config fill → `crew.py` (decorators) → `main.py` (inputs) → `crewai run`.
3. Aaj ke do naye concepts: **Tools** (agent capabilities) aur **Context** (task-to-task information flow).
4. **Serper** (serper.dev) se free Google search API — 2500 credits, key `.env` mein `SERPER_API_KEY` naam se; **SerpAPI se confuse mat karna**.
5. Naya project: `crewai create crew financial_researcher` — `crew` likho, `flow` nahi; OpenAI GPT-4o-mini select, key setup skip.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

And a very warm welcome to day two of week three. Our second day playing with Crew, this time continuing doing some building and exploring the Crew framework. To quickly recap what we did last time, we learned about an agent. The agent being the smallest autonomous unit. It has an LLM associated with it. It doesn't actually need to. You can have an agent without an LLM, but they typically do. It has a role, a goal, a backstory. And it also has memory and tools. Not that we've looked at either of them just yet. And then a task. This is the concept which doesn't have an analog in OpenAI Agents SDK. A task is an assignment to be carried out with a description, expected output, perhaps an output file, and it's assigned to an agent. And then a crew, which is a team of agents and tasks together assigned to those agents. And they can run sequentially or hierarchically, in which case you'd have to assign a manager LLM to figure out which task is assigned to which agent. So that's the overall structure of Crew, which now should be pretty familiar to you.

And you'll remember that there are five steps that we went through when we set up our first crew project. First of all, we created a project. We did crewai create crew my_project, or we did debate, but it could be whatever we want and it will set up that whole file system structure for us. We then go into source and the name of the project and then config, and that is where we find the YAML files, which we can call them whatever we want. But by default there are two there, one for the agents, one for the tasks, and we fill them in with the details. We then go to the crew.py module in our source project folder, and we create the agents, the tasks and the crew using the functions that are already set up there for us and using the decorators. And we reference the YAML config, although we don't need to, we could actually manually create and pass in those fields when we create each of those objects. But the config file makes that easy for us and keeps some of this prompting text separate from our code, which is a nice separation. Then fourth, we update the main.py module to set the config to set up the run parameters that we did when we specify the inputs. The fact in our case that the topic of debate, the motion was, as it happens, about AI regulation. And then we can run, and the way we run is we type crewai run from within the project folder, which behind the scenes does a run, and then it's off to the races with our Crew framework.

Okay. So we're going to go a little bit deeper in two ways. And we're going to set up another project today. And one of those ways is with tools, something that we're very familiar with already — equipping agents with capabilities. We will see how to do that CrewAI style. And then the other one is about context. And this is how you tell Crew what information is to be passed from one task to another. So these are the two extra details we're going to get into today when we build our second crew. And let's go and do that right now.

So just before we go into Crew, there's another of these APIs that I need you to sign up for, but you'll be pleased to hear it's another free one. And this is going to be quite a contrast with our experience with OpenAI Agents SDK. We're going to use something called Serper, which is a fast way to run Google queries from code. It's an API to run lightning fast Google search at an unbeatable price, and indeed it is unbeatable. So you go to serper.dev and you sign up by pressing that button there, and I've already done so and so I can sign in with my account. And here I am. And the thing is that you get 2500 free credits, which is more than enough for this course, and this will allow us to do plenty of searches quite happily indeed. And you will go to API key, which I won't do now — you'll get my API key — but you go there to create your API key and as usual, copy it into your clipboard because that is something that you will need for your env file. And in your env file, you should have entered that in as SERPER underscore API underscore key. Cursor will actually prompt you for that if you start typing it. SERPER API key. And if you're interested where that comes from, SERP stands for Search Engine Results Page, which is the common name for these kinds of services. And there is another one that's called something similar to Serper. So be sure that you use SERPER API key. Not, I think, this one called SerpAPI or something, which is different. So be sure to have the right key there.

Okay, so with that, we are still in the debate folder. We will close that. Here we are in our crew folder in Cursor for week three, and we are going to go into bringing up a new terminal. It's still got what we had before. Let's clear this, let's exit that. Let's start a fresh terminal. Here it is. We're going to go into the third folder, crew. And it's time for us again to create a new project. Do you remember how to create a crew project? Well, here you do it. It's crewai create crew again, as opposed to a flow, which is different. And then we're going to make one that's called financial_researcher, somewhat inspired by the default one that's already there. Let's have a financial researcher. Let's create that right now. So we, as before, we just choose OpenAI and GPT-4o mini. And we skip setting up the key. And it has created the financial_researcher project and a bunch of scaffolding for us, which is great. And this is where we will get started.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
