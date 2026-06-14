# Week 4 Practical Runbook — LangGraph (Hinglish Hands-On Guide)

> Ed Donner's Agentic AI course — **Week 4 (Lectures L68–L90)** ke run-verified labs.
> Audience: experienced Python backend dev. Week 1–3 runbooks already kar chuke ho — wahi style, ab **LangGraph** ke saath: agents ko explicit **graph** ki tarah design karna.
>
> Official course code: **github.com/ed-donner/agents** → folder **`4_langgraph`**

---

## 1. Learning Loop — Kaise Padhna Hai

Har lab ke liye yahi cycle repeat karo:

```
Lecture dekho  →  Note padho (parent Week4_LangGraph folder ke L68-L90 notes)
      →  Matching lab `uv run` karo  →  Code ke Hinglish comments padho
      →  Kuch tweak karo (naya node jodo, naya tool do, criteria badlo)  →  Next lab
```

- **Lecture pehle**, taaki "graph kyon?" ka why clear ho — LangGraph ka mental model baaki frameworks se alag hai.
- **Lab ka output dekho**, phir code padho — har lab mein bade Hinglish comment blocks hain jo lectures se directly map karte hain.
- **Tweak zaroori hai** — lab1 mein pipeline mein ek aur node jodo, lab2 mein naya `@tool` likho, lab3 mein evaluator ka hidden criterion badlo, lab4 mein sidekick ko nayi success criteria do. Graph ko haath se modify kiye bina edges/state ka feel nahi aayega.

---

## 2. Lab → Lecture Mapping Table

Sab commands **project root** se chalao:

```bash
cd /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/my-agentic-ai-project
```

| Lab File | Lectures | Concept | Run Command |
|---|---|---|---|
| `lab1_langgraph_basics.py` | L68–L74 | LangGraph ka mental model vs SDK/CrewAI; **State / Node / Edge / Reducer** vocab; super-step **immutable-state** model. DEMO A = LLM-free greet→shout→punctuate pipeline (pure graph mechanics), DEMO B = `add_messages` reducer (list 1 → 3 grow), DEMO C = canonical START→chatbot→END Groq chatbot + graph diagram | `uv run Udemy_EdDonner_Course/Week4_LangGraph/Practical/lab1_langgraph_basics.py` |
| `lab2_tools_checkpointing.py` | L75–L79 | **`@tool`** decorator (wiki_search via Wikipedia API + safe-AST calculator), `bind_tools`, **`ToolNode` + `tools_condition`** — Week 1 ka manual while-loop ab graph ke edges/cycle ban gaya; **`MemorySaver` + `thread_id`** super-step checkpointing; **`SqliteSaver`** disk persistence (fresh graph, same db = memory survive) | `uv run Udemy_EdDonner_Course/Week4_LangGraph/Practical/lab2_tools_checkpointing.py` |
| `lab3_worker_evaluator.py` | L80–L83 (+L89 commentary) | Anthropic ka **evaluator-optimizer pattern** as a LangGraph **CYCLE** — Worker (Groq llama-3.3) + Evaluator (Gemini structured output, `EvaluatorOutput` pydantic) + conditional edge (success → END / retry → worker / attempts≥3 → END); attempts counter + feedback state mein; "inside AI feedback loops" (L89) | `uv run Udemy_EdDonner_Course/Week4_LangGraph/Practical/lab3_worker_evaluator.py` |
| `lab4_sidekick.py` | L84–L90 | **Capstone: Sidekick** — 4 sandboxed tools (wiki_search, write_file/read_file path-guard ke saath, restricted run_python), worker→ToolNode loop→evaluator (Pydantic verdict + fallback chain), feedback-redo loop (max 3 rounds), MemorySaver multi-turn, **Gradio UI** per-session thread_id ke saath | `uv run Udemy_EdDonner_Course/Week4_LangGraph/Practical/lab4_sidekick.py` (Gradio ke liye end mein `ui` add karo) |

Side-effect files: lab2 → `Practical/output/memory.db` (SqliteSaver persistence proof), lab4 → `Practical/sandbox/langgraph_notes.md` (agent ka likha hua artifact).

---

## 3. LangGraph Core Concepts — Cheat Sheet

| Concept | 1-2 Line Hinglish Explanation |
|---|---|
| **State (`TypedDict`)** | Graph ka shared data — ek dict-shaped schema jo har node ko milta hai. Node state ko mutate nahi karta, sirf **updates return** karta hai; LangGraph merge karta hai. |
| **`Annotated` + reducer (`add_messages`)** | Reducer batata hai ki naya update purane field se **kaise merge** ho. `add_messages` = append (replace nahi) — isi se chat history aaram se grow hoti hai (lab1 DEMO B: 1 → 3). |
| **Node** | Ek plain Python function: `state in → partial state update out`. LLM call, tool call, ya pure logic — kuch bhi. Backend dev ke liye: ek pure-ish handler function. |
| **Edge** | Do nodes ke beech fixed wiring — "A ke baad hamesha B". `graph.add_edge("a", "b")`. |
| **Conditional edge** | Runtime pe decide hota hai agla node kaun — ek router function state dekh ke node ka naam return karta hai. Yahi LangGraph ka `if/else` hai (lab3 ka success/retry/END routing). |
| **`START` / `END`** | Reserved entry/exit markers. Har graph START se shuru, END pe khatam — explicit entry point, koi magic nahi. |
| **`StateGraph(...).compile()`** | Builder pattern: nodes + edges declare karo, phir `compile()` se runnable graph milta hai (`.invoke()` / `.stream()`). Checkpointer bhi yahin pass hota hai. |
| **`ToolNode` + `tools_condition`** | Prebuilt combo: LLM ne tool_calls maange to `tools_condition` ToolNode pe route karta hai, ToolNode tools execute karke wapas bhejta hai. Week 1 ka haath se likha while-loop ab **2 lines ka graph wiring** hai. |
| **Checkpointer (`MemorySaver` / `SqliteSaver`) + `thread_id`** | Har super-step ke baad state snapshot save hota hai. `MemorySaver` = RAM, `SqliteSaver` = disk (process restart ke baad bhi memory zinda — lab2 Demo 3). `thread_id` = kis conversation ka checkpoint load karna hai. |
| **Super-step** | Ek round of execution: active nodes chalte hain, updates reducers se merge hote hain, naya immutable state snapshot banta hai. Checkpointing isi granularity pe hoti hai. |
| **Graph cycles = loops** | Edge wapas pichhle node pe point kar sakta hai — yahi LangGraph mein "agent loop" hai. lab2 ka tool-loop aur lab3/lab4 ka worker↔evaluator loop dono cycles hain, conditional edge exit decide karta hai. |

**Framework comparison (ek line):** Agents SDK = ek **loop** (framework chalata hai), CrewAI = ek **team** (roles ko delegate karo), LangGraph = **explicit graph** (har node/edge tum likhte ho) — **sabse zyada control, sabse zyada learning curve**.

---

## 4. Provider Setup Note (Groq Free, Gemini, LangSmith Skip)

- **Groq free tier** via `ChatGroq` (`langchain-groq` package) — sab labs ka primary worker model `llama-3.3-70b-versatile` hai. Free tier transient errors deta hai, isliye har LLM/graph invoke **`invoke_with_retry`** (3 attempts + sleep) mein wrapped hai.
- **Gemini available** — lab3 ka evaluator `gemini-2.5-flash` use karta hai. Note: `gemini-2.0-flash` ka free quota ab 0 hai (429 deta hai), isliye **2.5-flash** use karo.
- **LangSmith tracing SKIP** — course mein Ed LangSmith dikhata hai (LangChain ka observability/tracing dashboard), lekin hamare paas key nahi hai. Koi functional fark nahi — sab labs bina tracing ke chalti hain. Key mil jaye to bas `LANGCHAIN_API_KEY` + `LANGCHAIN_TRACING_V2=true` env vars set karna hota hai.
- **Structured-output fallbacks** — structured output (pydantic verdict) free models pe flaky ho sakta hai, isliye fallback chains built-in hain: lab3 = Gemini → Groq `with_structured_output`; lab4 evaluator = Groq → `openai/gpt-oss-120b` → Gemini. Dono fallback paths real runs mein exercised/verified hain.
- **No OpenAI key needed** — poora Week 4 free Groq + Gemini pe chalti hai.

---

## 5. Recommended Order

1. **lab1 (basics)** — graph vocabulary (State/Node/Edge/Reducer) bina kisi noise ke; DEMO A to LLM-free hai, pure mechanics samajhne ke liye perfect.
2. **lab2 (tools + checkpointing)** — agent loop ko graph edges mein convert karna + memory (thread_id, RAM vs disk persistence) — LangGraph ke do sabse practical superpowers ek saath.
3. **lab3 (worker-evaluator)** — pehla **cycle** with conditional exit: AI ko AI se grade karwana aur feedback loop ko visibly chalte dekhna (attempt 1 FAIL → attempt 2 PASS).
4. **lab4 (sidekick)** — capstone: sab kuch combine — tools + evaluator loop + multi-turn memory + Gradio UI. Yahi pattern production agent ka skeleton hai.

---

## 6. Milestone

> **Week 4 done = aap explicit graph-orchestrated, stateful, tool-using, self-evaluating agents bana sakte ho** — state schema khud design karna, loops ko edges se wire karna, conversations ko disk pe persist karna, aur agent ke output ko ek evaluator se quality-gate karna. Yeh Agentic AI ka sabse "engineering-grade" framework hai.

Compare karne ke liye Ed ka original code dekho: **github.com/ed-donner/agents → `4_langgraph/`**.

**Course extras jo humne skip kiye (jaan-boojh ke):**
- **Playwright web-browsing** — Ed ka Sidekick real browser (Playwright) + real Python REPL use karta hai. Heavy dependency hai; humne lab4 mein keyless Wikipedia tool + restricted-exec `run_python` + sandboxed file tools se **same architecture** banaya. Pattern identical hai, sirf tool ka muscle chhota.
- **LangSmith** — tracing/observability dashboard, key nahi hai (Section 4). Concept note kar lo: production LangGraph apps mein debugging ke liye almost hamesha use hota hai.

---

## 7. Common Errors & Fixes

| Error / Symptom | Reason | Fix |
|---|---|---|
| **429 / RateLimitError / transient 5xx** on Groq | Free tier ke per-minute limits — tool-loops aur evaluator-cycles mein multiple LLM calls jaldi hit karti hain | Retry with sleep — sab labs mein `invoke_with_retry` (3 attempts + sleep) built-in hai; phir bhi fail ho to 1 min ruk ke re-run |
| **`SqliteSaver` ke saath "closed database" / kaam hi nahi karta** | `SqliteSaver.from_conn_string()` ek **context manager** hai — `with` block ke bahar use kiya to connection band | `with SqliteSaver.from_conn_string(db_path) as saver:` ke andar hi compile + invoke karo (lab2 Demo 3 pattern); fresh graph ko same db pe **recompile** karna padta hai |
| **Memory kaam nahi kar rahi — bot har turn pe bhool jaata hai** | `config={"configurable": {"thread_id": "..."}}` pass karna bhool gaye, ya har call pe naya thread_id de diya | Checkpointer + **same thread_id** dono chahiye; alag user/session = alag thread_id (lab2 Demo 2: thread 1 ko naam yaad, thread 2 ko nahi) |
| **Structured output flaky / validation error** on evaluator | Free llama models pydantic `with_structured_output` kabhi-kabhi reject/garble karte hain | Fallback chain use karo: Groq **`openai/gpt-oss-120b`** ya **`gemini-2.5-flash`** (lab3/lab4 mein already wired) |
| **429 `limit: 0`** on `gemini-2.0-flash` | Us model ka free-tier quota ab zero hai | `gemini-2.5-flash` use karo (verified working), ya Groq fallback |
| **`draw_ascii()` crash** on graph diagram | `grandalf` package installed nahi | Try/except mein wrap karke mermaid text print karo (lab1 pattern) — ya `uv add grandalf` |
| **Evaluator loop kabhi khatam nahi hota** | Conditional edge mein END-condition nahi, ya attempts counter state mein update nahi ho raha | Hamesha **max-attempts cap** rakho (lab3: attempts≥3 → END; lab4: max 3 redo rounds) — infinite LLM loop = infinite bill/quota burn |
| **DEMO C / LLM demos skip ho gaye** | `GROQ_API_KEY` env mein set nahi | `.env` mein `GROQ_API_KEY` daalo; lab1 gracefully skip karta hai taaki LLM-free demos (A/B) phir bhi chalein |
| **Gradio UI error on `Chatbot(type=...)`** | Gradio 6.x ne `type=` kwarg deprecate/remove kar diya | Kwarg hata do (lab4 mein already fixed) — `gr.Chatbot()` plain use karo |

---

*Happy building! Week 4 ke saath core course ke chaaron frameworks (direct API → Agents SDK → CrewAI → LangGraph) complete.*
