# L54 — Day 1: Building AI Debate Systems — Compare LLMs

> **Week 3 — CrewAI** · ⏱️ ~2m · 🎥 Lecture 54 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821139

---

## 🎯 Ek Line Mein (TL;DR)

Pehle **CrewAI debate project** ka recap — `crewai create crew debate` → **YAML config** (agents + tasks) → **decorators** wala crew → `crewai run` — aur phir assignment: **proposer aur opposer ko alag agents** banao taaki **alag-alag LLMs** (OpenAI vs DeepSeek waghaira) ko debate karwa ke compare kar sako.

---

## 📝 Hinglish Explanation (Detailed)

- **Recap of the debate project:** Jo abhi banaya wo ek **CrewAI project** tha, jo under the hood ek **uv project** hi hai. Ek hi command se bana: `crewai create crew debate`.
- **Directory structure** ab familiar honi chahiye: `debate/` → `src/` → `debate/` → `config/`. Yehi CrewAI ka standard scaffolding hai.
- **agents.yaml** mein humne har **agent** define kiya — including **kaunsa model** wo agent use karega. Matlab model selection bhi config-level pe hota hai, code mein nahi.
- **tasks.yaml** mein har **task** define kiya — jisme **`expected_output`** (output kaisa dikhna chahiye) aur **`output_file`** (result kahan save hoga) shamil tha.
- **crew.py** woh file hai jahan saare **decorators** (`@agent`, `@task`, `@crew`) the — yahin functions ke through agents, tasks aur crew sab kuch wire-up hota hai.
- **Process mode `sequential`** rakha tha — tasks ek ke baad ek order mein chale.
- Phir directory ke andar **`crewai run`** type kiya, poora pipeline kick off hua, **output generate** hua — aur successfully chala. (Verdict: LLMs pe "stricter regulation honi chahiye" — judge ne yehi decide kiya 😄)
- Ed ka suggestion: **apne pasand ke controversial topics** pe debate karwa ke dekho, aur **different models** try karo.
- **Assignment (main idea):** Abhi ek hi agent propose aur oppose dono kar raha tha. Isko **do alag agents** mein todo — ek **proposer**, ek **opposer** — aur tasks unko alag-alag assign karo.
- **Kyun?** Kyunki alag agents hone se har agent ko **alag model** dena easy ho jata hai. Phir aap **OpenAI vs DeepSeek** jaise matchups karwa sakte ho.
- **Swap karke dekho:** Kaun propose kar raha hai aur kaun oppose — ye roles switch karke dekho ki **outcome change hota hai ya nahi** (position bias check!).
- Ye ek **entertaining tarika hai LLMs ko battle karwane ka** — dekhna ki kaunsa model zyada **coherent aur persuasive arguments** banata hai jo judge model ko convince kar de.
- Isse aap apna khud ka chhota **"debate-skills leaderboard"** bana sakte ho — models ko ranking dena unki argumentation quality pe.
- Goal: CrewAI ke **minimal scaffolding** ke saath comfortable ho jao. Next lectures mein crew mein aur deep jayenge aur **aur crew projects** banayenge.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| `crewai create crew <name>` | Ek command jo poora project scaffolding generate karti hai (uv project under the hood) |
| **agents.yaml** | Agents ki config file — role/goal/backstory + kaunsa **model** use hoga |
| **tasks.yaml** | Tasks ki config — `expected_output` (output ka shape) aur `output_file` (result file) |
| **crew.py decorators** | `@agent`, `@task`, `@crew` — YAML config ko Python objects se wire karte hain |
| **Process: sequential** | Tasks ek ke baad ek order mein execute hote hain |
| `crewai run` | Project directory mein ye command poora crew kick off karti hai |
| **Multi-agent debate** | Proposer + Opposer alag agents → har ek pe alag LLM laga sakte ho |
| **LLM leaderboard (debate)** | Models ko ek-dusre ke against debate karwa ke ranking banana — judge bhi ek LLM |
| **Position bias check** | Proposer/Opposer roles swap karke dekhna ki verdict change hota hai ya nahi |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Per-agent model assignment** config mein hai — bilkul jaise microservices mein har service ka apna runtime/resource config hota hai. Ek YAML key change karo (`llm: openai/gpt-4o` → `llm: deepseek/...`), code untouched. **LiteLLM** ki wajah se provider swap karna sirf string change hai — DI container mein implementation swap karne jaisa.
- **Role swap experiment** asal mein ek **A/B test for position bias** hai — same input, swapped roles, observe output delta. LLM-as-judge systems mein ye ek known evaluation pattern hai (judge bhi biased ho sakta hai!).
- **Hands-on lab:** is lecture ka code khud chalane ke liye `Practical/lab1_crewai_debate.py` run karo (is repo me, `uv run` se chalta hai, **Groq pe free via LiteLLM**). Note: hamare labs course se thoda alag hain — **self-contained code-style** (YAML scaffolding nahi), to `crewai create`/`crewai run` wala flow lab me directly nahi dikhega, par Agent/Task/Crew concepts same hain.
- **Leaderboard idea** ko serious bana sakte ho: debate results SQLite mein store karo, Elo-style rating lagao — ekdum chess.com jaisa ranking system, bas players LLMs hain.

---

## 🧠 Takeaway (yaad rakho)

1. CrewAI project flow yaad rakho: `crewai create crew <name>` → **agents.yaml + tasks.yaml** edit → **crew.py decorators** → `crewai run`.
2. **Model selection YAML mein hota hai** — agents alag karo to har agent ko alag LLM dena trivially easy ho jata hai.
3. Assignment: **proposer aur opposer ko 2 alag agents** banao, alag models do (e.g., OpenAI vs DeepSeek), aur debate battle karwao.
4. **Roles swap karke** check karo ki outcome change hota hai — judge LLM ka position bias pakadne ka tarika.
5. Is pattern se aap apna **LLM debate leaderboard** bana sakte ho — playful, but real evaluation skill (LLM-as-judge).

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

And so to recap, we just experienced a CrewAI project, which is in fact a uv project under the hood. We created it by saying crewai create crew debate. It created this directory structure which now should land with you. You should be more familiar: debate, then src, then debate again, then config. We set up our agents YAML to define each of the agents, including the model. We set up the tasks that included the expected output and the output file. Crew is where we had the various decorators, and we brought it all together with our functions for agents, tasks and the crew. And we said that the process was sequential. And then we typed crewai run within our directory and it kicked the whole thing off, generated the output. And it was successful. And apparently there should be stricter regulation around LLMs.

I encourage you to try debating some more controversial points of your liking and choose different models. So yes, we'll of course be getting much deeper into Crew. But in the meantime, the assignment for you is to now play around with this. You could have a separate agent for the agent that is proposing and opposing the motion. Break that into two different agents and have the tasks going to them separately. And the reason to do that is that then it's easy to have a different model. So that you could have OpenAI debate with DeepSeek or something like that, and then switch who's opposing and who's proposing to see whether it changes the outcome.

And that's an amusing and entertaining way to battle LLMs together, to see which are better at forming coherent arguments, persuasive arguments that convince a different model that is being the judge. So that allows you to come up with your own little leaderboard based on debating skills. So please go away and enjoy yourself with that. Get a good handle, get comfortable with the framework around Crew and the sort of minimal scaffolding there. And next time we'll get a little bit deeper into Crew and start building some more crew projects. I will see you then.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
