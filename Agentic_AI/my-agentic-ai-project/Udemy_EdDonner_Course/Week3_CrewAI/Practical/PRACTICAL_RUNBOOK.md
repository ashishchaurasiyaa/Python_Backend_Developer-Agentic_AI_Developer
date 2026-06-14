# Week 3 Practical Runbook — CrewAI (Hinglish Hands-On Guide)

> Ed Donner's Agentic AI course — **Week 3 (Lectures L49–L67)** ke run-verified labs.
> Audience: experienced Python backend dev. Week 1–2 runbooks already kar chuke ho — wahi style, ab **CrewAI** framework ke saath.
>
> Official course code: **github.com/ed-donner/agents** → folder **`3_crew`**

---

## 1. Learning Loop — Kaise Padhna Hai

Har lab ke liye yahi cycle repeat karo:

```
Lecture dekho  →  Note padho (parent Week3_CrewAI folder ke L49-L67 notes)
      →  Matching lab `uv run` karo  →  Code ke Hinglish comments padho
      →  Kuch tweak karo (motion badlo, company badlo, naya tool do)  →  Next lab
```

- **Lecture pehle**, taaki concept ka "why" clear ho.
- **Lab ka output dekho**, phir code ke comments padho — har lab mein bade Hinglish comment blocks hain jo lectures se directly map karte hain.
- **Tweak zaroori hai** — lab1 mein debate motion badlo, lab2 mein Tesla ki jagah koi aur company do, lab3 mein sector badlo, lab4 mein requirements badlo. Bina haath gande kiye CrewAI yaad nahi rahega.

---

## 2. Lab → Lecture Mapping Table

Sab commands **project root** se chalao:

```bash
cd /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/my-agentic-ai-project
```

| Lab File | Lectures | Concept | Run Command |
|---|---|---|---|
| `lab1_crewai_debate.py` | L49–L54 | CrewAI ka mental model vs Agents SDK: `Agent` (role/goal/backstory), `Task` (description/expected_output), `Crew` + `Process.sequential`, task `context=[...]` chaining, `{motion}` templating via `kickoff(inputs=...)`, multi-provider (Groq debaters + Gemini judge + fallback) | `uv run Udemy_EdDonner_Course/Week3_CrewAI/Practical/lab1_crewai_debate.py` |
| `lab2_financial_researcher.py` | L55–L57 | Custom **`BaseTool`** (free Wikipedia search — SerperDev ka keyless replacement), Agent ko tool dena, Researcher → Analyst context chaining, `output_file` se report disk pe save | `uv run Udemy_EdDonner_Course/Week3_CrewAI/Practical/lab2_financial_researcher.py` |
| `lab3_stock_picker.py` | L58–L60 | **`output_pydantic`** typed structured outputs (string parsing nahi, dot-access), custom **PushNotificationTool** (Pushover ya console+log fallback), 4-agent sequential crew, "act then format" pattern (Groq tools+JSON-mode ek saath nahi leta) | `uv run Udemy_EdDonner_Course/Week3_CrewAI/Practical/lab3_stock_picker.py` |
| `lab4_engineering_team.py` | L61–L67 | **Capstone**: 3-agent engineering team (Lead → Backend Engineer → Test Engineer) jo real Python files likhti hai, phir script khud `compile()` + `unittest` se SELF-VERIFY karti hai ki agent-generated code chalta hai | `uv run Udemy_EdDonner_Course/Week3_CrewAI/Practical/lab4_engineering_team.py` |

Side-effect files (sab `Practical/output/` mein): lab2 → `financial_report.md`, lab3 → `notifications.log`, lab4 → `design.md` + `accounts.py` + `test_accounts.py`.

---

## 3. CrewAI Core Concepts — Cheat Sheet

| Concept | 1-2 Line Hinglish Explanation |
|---|---|
| **`Agent`** | Role-play config: `role` (kaun ho), `goal` (kya achieve karna hai), `backstory` (personality/context). Agents SDK ke ek `instructions` string ki jagah CrewAI 3 fields mein todta hai — LLM ko role-play karwana hi iska core idea hai. |
| **`Task`** | Kaam ki unit: `description` (kya karna hai) + `expected_output` (output kaisa dikhna chahiye) + `agent` (kaun karega). Agents SDK mein task implicit tha (user message); yahan explicit first-class object hai. |
| **`context=[task1, task2]`** | Task chaining ka glue — in tasks ke outputs is task ke prompt mein inject ho jaate hain. Researcher ka output Analyst ko aise hi milta hai. |
| **`output_pydantic=Model`** | Task ka output typed Pydantic object banta hai — `result.pydantic.ticker` jaisa dot-access, koi string parsing nahi. Week 2 ke `output_type=` ka CrewAI equivalent. |
| **`output_file="output/report.md"`** | Task ka final output seedha disk pe save. Note: validator leading `/` strip kar deta hai (anti path-traversal), isliye **relative path** do. |
| **`Crew(agents=..., tasks=..., process=...)`** | Team assembly. `Process.sequential` = tasks list ke order mein ek-ke-baad-ek (humne sab labs mein yahi use kiya). `Process.hierarchical` = ek manager LLM decide karta hai kaun kya kare — flexible lekin unpredictable + costly. |
| **`crew.kickoff(inputs={...})`** | Run button. `inputs` dict se task/agent descriptions ke `{placeholders}` fill hote hain — ek hi crew alag-alag inputs (motion, company) ke saath reuse hota hai. |
| **`LLM("groq/llama-3.3-70b-versatile")`** | Course mein model strings LiteLLM format mein hain: `provider/model`. **Lekin hamare env mein litellm installed nahi hai** — Section 4 dekho, hum native provider route use karte hain. |
| **Custom `BaseTool`** | Subclass banao: `name` + `description` + `args_schema` (Pydantic) + `_run()` method. Agent ko `tools=[MyTool()]` mein de do — bas. Lab2 ka WikipediaSearchTool aur lab3 ka PushNotificationTool isi pattern pe hain. |

**YAML-config style vs hamara code-style:** Ed ke course/`crewai create` scaffold mein `@CrewBase` class + `config/agents.yaml` + `config/tasks.yaml` use hota hai (config alag, logic alag — teams ke liye accha). Humne labs mein **pure-Python code-style** rakha taaki ek file mein sab dikhe aur seekhna easy ho. **Dono 100% valid hain** — concepts same, sirf packaging alag. Har lab mein YAML pattern ka course-note comment bhi hai.

---

## 4. Provider Setup Note (Groq Free, Gemini Judge, Memory/Telemetry)

- **Course default:** OpenAI key + LiteLLM strings (`LLM(model="groq/...")`). **Hamari reality:** is env mein crewai 1.14.5 ke saath **litellm installed nahi hai** aur `uv add 'crewai[litellm]'` resolve nahi hota (litellm openai==2.24/2.30 pin karta hai vs openai-agents ko openai>=2.38 chahiye). Isliye `groq/...` strings `ImportError` dengi.
- **Working pattern (sab Week 3 labs yahi use karte hain)** — Groq ko CrewAI ke NATIVE openai provider se wire karo:
  ```python
  groq_llm = LLM(
      model="llama-3.3-70b-versatile",
      provider="openai",                              # explicit kwarg = model-name validation bypass
      base_url="https://api.groq.com/openai/v1",
      api_key=os.environ["GROQ_API_KEY"],
  )
  ```
  `provider=` explicitly dena zaroori hai, warna CrewAI model-name se provider guess karke validation fail karega.
- **Gemini bhi available:** `LLM(model="gemini-2.5-flash", provider="gemini", ...)` — bas **`GEMINI_API_KEY` set hona chahiye** (agar sirf `GOOGLE_API_KEY` hai to usi value se `GEMINI_API_KEY` bhi export kar do). Note: `gemini-2.0-flash` ka free quota ab 0 hai (429 deta hai) — **`gemini-2.5-flash` use karo**, verified working. Lab1 ka judge isi pe chalta hai, Groq fallback ke saath.
- **`memory=True` kyon skip kiya:** CrewAI ki memory by default **OpenAI embeddings + ChromaDB** maangti hai — OpenAI key nahi hai to crash. Alternative hai (Google embedder config karna), lab4 ke comments mein noted, lekin labs ke liye memory off rakha — concepts ke liye zaroori nahi.
- **Telemetry disabled:** CrewAI by default anonymous telemetry bhejta hai — labs `CREWAI_DISABLE_TELEMETRY=true` set karte hain. Clean runs, no surprise network calls.

---

## 5. Recommended Order

1. **lab1 (debate)** — CrewAI ka mental model banao: Agent/Task/Crew triangle, sequential process, kickoff inputs. Sab kuch isi foundation pe hai.
2. **lab2 (financial researcher)** — pehla custom `BaseTool` + `output_file`: agents ko duniya se connect karna aur kaam disk pe save karna.
3. **lab3 (stock picker)** — typed `output_pydantic` outputs + side-effect tool (push notification) + 4-agent pipeline: production-grade structured results.
4. **lab4 (engineering team)** — capstone: agents jo **code likhte hain** aur script khud verify karti hai ki wo code compile + test pass karta hai. Portfolio-worthy.

---

## 6. Milestone

> **Week 3 done = aap multi-agent CREWS bana sakte ho** — role-based teams with tools, typed outputs, aur code-writing agents. Debate panel se lekar self-verifying engineering team tak, sab sequential crews ke patterns aapke paas hain.

Compare karne ke liye Ed ka original code dekho: **github.com/ed-donner/agents → `3_crew/`** (wahan YAML/@CrewBase scaffold + OpenAI/SerperDev keys use hote hain; humne free Groq/Gemini + keyless Wikipedia tool se same patterns banaye).

---

## 7. Common Errors & Fixes

| Error / Symptom | Reason | Fix |
|---|---|---|
| **`ImportError`** on `LLM(model="groq/...")` | litellm installed nahi hai (crewai 1.14.5 env, dependency conflict — Section 4) | Native route: `LLM(model="llama-3.3-70b-versatile", provider="openai", base_url="https://api.groq.com/openai/v1", api_key=GROQ_API_KEY)` |
| **429 / RateLimitError** on free Groq | Free tier ke per-minute token limits — multi-agent crews mein jaldi hit hota hai | Thoda wait karke retry (labs mein 3-attempt retry + 20s sleep wrapper built-in hai), ya chhota model |
| **400** on `output_pydantic` task (Groq llama-3.3) | llama-3.3 `json_schema` response_format reject karta hai | Structured-output agents ke liye Groq ka **`openai/gpt-oss-120b`** use karo (lab3 pattern), ya prompt tighten karke "ONLY JSON" bolo |
| **400** jab tool + `output_pydantic` ek hi task mein | Groq tools aur JSON mode ek request mein allow nahi karta | **"Act then format"**: tool-use wala task plain text rakho, uske baad alag formatting task `output_pydantic` ke saath (lab3 tasks 3+4) |
| **`GEMINI_API_KEY` missing / auth error** on Gemini LLM | CrewAI `GEMINI_API_KEY` dhundhta hai, `GOOGLE_API_KEY` nahi | `export GEMINI_API_KEY=$GOOGLE_API_KEY` (ya code mein `api_key=` explicitly pass karo) |
| **429 `limit: 0`** on `gemini-2.0-flash` | Us model ka free-tier quota ab zero hai | `gemini-2.5-flash` use karo (verified working), ya Groq fallback |
| **chromadb / embeddings error** with `memory=True` | Memory ko OpenAI embeddings chahiye, key nahi hai | `memory` off rakho (labs default), ya Google embedder configure karo (lab4 comments mein note) |
| `output_file` ka path galat jagah save / leading `/` gayab | CrewAI validator leading `/` strip karta hai (anti path-traversal) | Script apne dir mein `chdir` karke **relative path** de (lab2 pattern: `output/financial_report.md`) |
| Lab4 mein "generated code needs fixing" print | Agent-generated test mein slip (e.g. arithmetic) — graceful-failure path | Re-run karo; test-task prompt mein arithmetic-check hint already added hai jo clean pass deta hai |

---

*Happy building! Week 4 (LangGraph) mein milte hain.*
