# L51 — Day 1: Crew AI & LiteLLM — Multiple LLMs

> **Week 3 — CrewAI** · ⏱️ ~5m · 🎥 Lecture 51 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821129

---

## 🎯 Ek Line Mein (TL;DR)

CrewAI under the hood **LiteLLM** use karta hai — ek super-lightweight library jisse aap sirf `"provider/model"` string pass karke **koi bhi LLM** (OpenAI, Anthropic, Gemini, Groq, Ollama, OpenRouter) plug-in kar sakte ho; aur CrewAI projects ke liye `crewai create crew` ek poora **scaffolded uv project** (config YAMLs + `crew.py` + `main.py`) generate karta hai.

---

## 📝 Hinglish Explanation (Detailed)

- **CrewAI ka LLM layer = LiteLLM.** Crew ki ek badi khoobi ye hai ki underlying LLMs se baat karne ka approach bahut **flexible aur lightweight** hai. Under the hood ye **LiteLLM** framework use karta hai jo actual providers aur models se connect karta hai.
- Ed ko LiteLLM isliye pasand hai kyunki ye **simple aur vanilla** hai — **LangChain** ke saath unka thoda **love-hate relationship** hai kyunki LangChain apne saath kaafi structure/abstraction lekar aata hai. **LiteLLM bilkul doosra extreme hai** — "almost nothing there", aap turant kisi bhi LLM se connect kar sakte ho.
- **Crew me usage pattern:** bas ek `LLM` object banao aur **model name** pass karo. Format hai — **`provider/model`** (provider ka naam, phir slash, phir model). Examples:
  - `openai/gpt-4o-mini` — GPT-4o mini ke liye
  - `anthropic/claude-3-5...` ya `claude-3-7...` — Claude ke liye (3.5, 3.7, jo chahiye)
  - Gemini Flash bhi isi tarah
  - **Groq with a Q** (fast inference provider) — aur **Grok with a K** (xAI ka model) bhi same pattern se use ho sakta hai. Dono alag cheezein hain, spelling ka dhyaan rakho!
  - **Ollama** — agar model **locally** chala rahe ho, to provider `ollama` rakho aur ek **base URL** supply karo
  - **OpenRouter** — jo khud ek abstraction-on-LLMs service hai, usko bhi configure kar sakte ho
- **Ed ka argument:** is flexibility ki wajah se Crew ko **OpenAI Agents SDK pe ek edge** milta hai — model switch karna bahut simple hai, ek string change karo aur ho gaya.
- **Dusra topic: CrewAI Projects (scaffolding).** Pichle weeks me hum notebooks (Cursor me) ya kabhi-kabhi plain Python modules me kaam karte the. **CrewAI aise kaam nahi karta** — ye har crew ke liye ek **poora project + directory structure** banata hai, matlab thoda zyada scaffolding.
- **Framework install:** `uv tool install crewai` — ye command pehle se chala hua hai, to repo clone karte hi CrewAI framework available hai.
- **Naya project banana:** `crewai create crew my_crew` — ye ek poora directory structure generate karta hai. Side note: agar aapko **fixed workflows** chahiye to `crewai create flow my_project` bhi hai (Flows), lekin course me hum **Crews** pe hi stick karenge.
- **Generated structure (nested hai):**
  - Top level: `my_crew/` (ya jo bhi naam diya)
  - Uske andar `src/` → uske andar **phir se project ka naam** (`my_crew/`)
  - Uske andar **`config/`** directory — yahan **YAML files** jaati hain: by default **`agents.yaml`** aur **`tasks.yaml`** (agents aur tasks ka configuration)
  - **`crew.py`** module — yahan sab kuch **decorators** ke saath ek saath aata hai, yahi pe actual crew create hota hai
  - **`main.py`** module — yahan se hum run **kick off** (initiate) karte hain
- **Run karna:** `crewai run` type karo — behind the scenes ye basically `uv run main.py` hi karta hai.
- **uv projects within uv projects:** `crewai create crew` ek **uv project** setup karta hai (CrewAI khud uv use karta hai — humare liye great kyunki hum bhi uv use kar rahe hain). To `my_crew/` directory me uv project config files bhi dikhengi — matlab course ke bade uv project ke andar **chhote nested uv projects** honge. Action me dekhne pe ye aur clear hoga.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **LiteLLM** | Super-lightweight library jo 100+ LLM providers ko ek unified interface deti hai; CrewAI ise under the hood use karta hai |
| **`provider/model` format** | CrewAI me LLM specify karne ka tarika — provider ka naam + slash + model name, e.g. `groq/llama-3.3-70b` |
| **Groq (with a Q)** | Fast inference provider (LPU hardware) — open-source models free/sasta chalata hai |
| **Grok (with a K)** | xAI (Elon Musk) ka LLM — Groq se bilkul alag cheez |
| **Ollama** | Locally models chalane ka tool — CrewAI me base URL ke saath configure hota hai |
| **OpenRouter** | Ek hosted service jo khud multiple LLMs pe abstraction hai — LiteLLM ke through use ho sakti hai |
| **`crewai create crew <name>`** | Naya CrewAI project scaffold karne ka command — poora directory structure + uv project bana deta hai |
| **`crewai create flow <name>`** | Crews ki jagah fixed workflows (Flows) wala project banane ka variant |
| **`config/agents.yaml`, `config/tasks.yaml`** | Agents aur tasks ka declarative configuration — code se alag |
| **`crew.py`** | Wo module jahan decorators ke saath agents/tasks/crew assemble hote hain |
| **`main.py` + `crewai run`** | Entry point; `crewai run` behind the scenes `uv run main.py` karta hai |
| **uv tool install crewai** | CrewAI CLI ko globally install karne ka command (uv tool ke roop me) |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **LiteLLM = LLM-world ka SQLAlchemy/DB-API analogy:** jaise aap connection string (`postgresql://...`) change karke DB switch karte ho, waise hi yahan `"provider/model"` string change karke LLM switch hota hai — ek unified interface, zero vendor lock-in. LangChain vs LiteLLM ko aap "full ORM framework vs thin DB driver" ki tarah socho.
- **`crewai create crew` = cookiecutter/`django-admin startproject` jaisa scaffolding:** opinionated `src/` layout, `config/` me declarative YAML (agents/tasks), aur `crew.py` me wiring — config aur code ka clean separation, bilkul jaise aap settings ko code se alag rakhte ho. Nested uv projects ka concept monorepo me sub-packages jaisa hai.
- **`crewai run` ek thin wrapper hai** `uv run main.py` ke upar — jaise `npm start` package.json script ko wrap karta hai. Magic kuch nahi, bas convention.
- **Hands-on lab:** is lecture ka code khud chalane ke liye `Practical/lab1_crewai_debate.py` run karo (is repo me, `uv run` se chalta hai, **Groq pe free via LiteLLM** — yahi `provider/model` pattern live dekhoge). Note: hamare labs course se thoda alag hain — **self-contained code-style** rakha hai, `crewai create crew` wala YAML scaffolding nahi (sab kuch ek hi file me Agent/Task/Crew objects se).

---

## 🧠 Takeaway (yaad rakho)

1. CrewAI **LiteLLM** use karta hai — LLM specify karne ka format hai **`provider/model`** (e.g. `groq/...`, `anthropic/...`, `ollama/...` + base URL).
2. Ye lightweight multi-LLM flexibility CrewAI ko **OpenAI Agents SDK pe edge** deti hai — model swap = ek string change.
3. **Groq (Q) ≠ Grok (K)** — pehla fast-inference provider, doosra xAI ka model; dono LiteLLM se chal jaate hain.
4. CrewAI notebooks me nahi chalta — `crewai create crew my_crew` se **poora scaffolded project** banta hai: `src/<name>/config/` (agents.yaml, tasks.yaml) + `crew.py` + `main.py`.
5. `crewai run` = behind the scenes `uv run main.py`; har crew apna **nested uv project** hota hai bade course-repo uv project ke andar.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

One of the things that's really nice about Crew is that it has a very flexible, lightweight approach to interacting with underlying LLMs. It uses a framework called LiteLLM under the hood, which it uses to interact with the actual providers and with the LLMs themselves. And I love LiteLLM because it's so simple. It's so vanilla. You may know I have a somewhat love hate relationship with LangChain, which comes with a fair amount of structure to it. LiteLLM is almost the other extreme where there's almost nothing there. You can just immediately connect with any LLM you can imagine. And that really is reflected in the way it's used in Crew.

Within Crew, you can just create an LLM, you pass in a model name, and the structure is that it should have the provider's name followed by a slash followed by the model. And you can just use that to be working with GPT-4o mini, with Claude through Anthropic — you can use 3.5, 3.7, whatever you want — Gemini Flash, Groq with a Q. And you could also use Grok with a K in the same way. Ollama if you're running the model locally — that's how you'd set it up and supply a base URL. And if you wanted to use OpenRouter, which itself is a kind of abstraction onto other LLMs, but it's an actual service running, then this is how you would configure OpenRouter as an example. But really the idea is very lightweight, very flexible, allows you to really connect and switch around whichever models are running underneath your crew. And I would argue that in this way, Crew really has an edge over OpenAI Agents SDK, that this is really flexible and simple and I love it.

And so the final topic before we get to do some coding and some crew making is to talk about CrewAI projects. So in previous weeks we have just been coding within Python notebooks within Cursor. And then occasionally we've gone to real Python modules. CrewAI doesn't work that way. With CrewAI, you do need to work with Python code, and in fact, CrewAI builds an entire project and directory structure for each of your crews. So it comes with a bit more scaffolding than we're used to. And there's a particular way that you need to use it.

Now, the CrewAI framework itself is already actually installed because I typed this command here: uv tool install crewai. And that means that when you've cloned the repo you've already got the CrewAI framework right there. But when you want to create a new project — you actually want a crew of your own — you type this command: crewai create crew my_crew, or my project or whatever, to create that project. And by the way, as a side note, you could say crewai create flow my_project if you wanted to use the flow idea, the workflows, the more fixed workflows rather than a crew. But we're going to be sticking with crews. So crewai create crew my_crew.

And what that does is it's going to create a whole directory structure that's going to appear immediately. There's going to be at the top, my_crew or my project, whatever you call it. And then a subdirectory source, src, and within that subdirectory will be the name of your project again, my_crew or whatever. And then under that it's a bit nested. Under that will be a directory called config which is where you put your YAML files. And we'll see — in particular by default there'll be an agents YAML and a tasks YAML, which is where we can put our configuration for our agents and tasks. And then there's a module crew.py. And that module is the one I just showed you, which is where it all comes together with the decorators and the place we actually create our crew. And then there's a module called main. And that module is where we actually kick off. We initiate the run.

And when we actually want to run it we just type crewai run. And that will actually do that. It will execute main — I think behind the scenes it just simply does uv run main.py. And that does bring up a good point that this whole thing, when you do this, when you type crewai create crew my_crew, it sets up a uv project. Crew uses uv, which is great for us since we're using uv as well. But it makes a project. So you'll also see in this my_crew directory you'll see some of the uv project configuration files as well. So we're going to be having these uv projects within our bigger uv project for the whole course. And that will make more sense when you see it in action. And what better time to see it in action than right now. Let's go and give this a try.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
