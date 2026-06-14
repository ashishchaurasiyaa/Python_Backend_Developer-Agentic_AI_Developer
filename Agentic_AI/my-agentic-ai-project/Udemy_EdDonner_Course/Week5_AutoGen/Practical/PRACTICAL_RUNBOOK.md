# Week 5 Practical Runbook — Microsoft AutoGen (Hinglish Hands-On Guide)

> Ed Donner's Agentic AI course — **Week 5 (Lectures L91–L107)** ke run-verified labs.
> Audience: experienced Python backend dev. Week 1–4 runbooks already kar chuke ho — wahi style, ab **AutoGen** ke saath: agents ko **message-passing actors** ki tarah design karna.
>
> Official course code: **github.com/ed-donner/agents** → folder **`5_autogen`**

---

## 1. Learning Loop — Kaise Padhna Hai

Har lab ke liye yahi cycle repeat karo:

```
Lecture dekho  →  Note padho (parent Week5_AutoGen folder ke L91-L107 notes)
      →  Matching lab `uv run` karo  →  Code ke Hinglish comments padho
      →  Kuch tweak karo (naya tool jodo, termination badlo, naya message type banao)  →  Next lab
```

- **Lecture pehle**, taaki "AutoGen alag kyon hai?" clear ho — yeh framework AgentChat (high-level) aur Core (actor-model) do levels pe sochta hai, mental model baaki frameworks se distinct hai.
- **Lab ka output dekho**, phir code padho — har lab mein bade Hinglish comment blocks hain jo lectures se directly map karte hain.
- **Tweak zaroori hai** — lab1 mein DB mein nayi city + naya tool jodo, lab2 mein evaluator ka approval criteria sakht karo, lab3 mein best-of-5 rounds banao, lab4 mein Creator se 5 personas banwao. Message types ko haath se modify kiye bina actor-model ka feel nahi aayega.

---

## 2. Lab → Lecture Mapping Table

Sab commands **project root** se chalao:

```bash
cd /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/my-agentic-ai-project
```

| Lab File | Lectures | Concept | Run Command |
|---|---|---|---|
| `lab1_agentchat_basics.py` | L91–L94 | AutoGen ka **3-layer architecture** (core / agentchat / ext); pehla **`AssistantAgent`** via `agent.run(task=...)`; **tools as plain functions** (SQLite ticket-price lookup) + `reflect_on_tool_use=True`; **multi-turn statefulness** via `on_messages()` + `TextMessage` + `CancellationToken` | `uv run Udemy_EdDonner_Course/Week5_AutoGen/Practical/lab1_agentchat_basics.py` |
| `lab2_primary_evaluator.py` | L95–L97 | **Structured output** via `output_content_type=FlightQuote` (pydantic); **primary + evaluator feedback loop** in `RoundRobinGroupChat` with `TextMentionTermination("APPROVE") \| MaxMessageTermination(10)`; httpx `fetch_page` tool researcher (free MCP-fetch substitute — real MCP Week 6 mein) | `uv run Udemy_EdDonner_Course/Week5_AutoGen/Practical/lab2_primary_evaluator.py` |
| `lab3_autogen_core_rps.py` | L98–L101 (+L102–L104 gRPC note comments mein) | **autogen_core actor model**: dataclass message types (PlayRequest/PlayResponse/JudgeRequest/JudgeResponse), `RoutedAgent` subclasses + `@message_handler`, `SingleThreadedAgentRuntime` ka register → start → `send_message` → `stop_when_idle` lifecycle — Rock-Paper-Scissors with LLM players + pure-python judge + LLM commentary | `uv run Udemy_EdDonner_Course/Week5_AutoGen/Practical/lab3_autogen_core_rps.py` |
| `lab4_agent_creator.py` | L105–L107 | **Creator pattern (safe version)**: LLM **personas generate karta hai** (name + system_prompt), executable code nahi — personas factory closures se runtime pe dynamically `RoutedAgent` ban ke register hote hain; typed messages (IdeaRequest/IdeaResponse/RefineRequest) se 3 collaboration rounds: own idea → neighbour refine → VC synthesizer verdict | `uv run Udemy_EdDonner_Course/Week5_AutoGen/Practical/lab4_agent_creator.py` |

Side-effect files: lab1 → `Practical/output/tickets.db` (4 cities, har run pe reseed, idempotent), lab4 → `Practical/output/generated_agents.json` (LLM-generated personas) + `Practical/output/ideas_summary.md` (full collaboration transcript).

---

## 3. AutoGen Core Concepts — Cheat Sheet

| Concept | 1-2 Line Hinglish Explanation |
|---|---|
| **3 layers: `autogen_core` / `autogen_agentchat` / `autogen_ext`** | Core = low-level actor-model runtime (messages, agents, routing). AgentChat = uske upar high-level "ready-made agents + teams" API (Core pe hi bana hai). Ext = third-party integrations (model clients jaise OpenAI/Groq, MCP, code executors). |
| **`AssistantAgent`** | AgentChat ka workhorse — ek LLM-backed agent jisko system_message, model_client, aur tools de do. Week 2 ke Agents SDK `Agent` ka AutoGen equivalent. |
| **Tools = plain functions** | Koi decorator nahi chahiye — normal Python function (with type hints + docstring) ko `tools=[...]` list mein daal do, AutoGen khud schema bana leta hai. Backend dev ke liye: zero-ceremony function calling. |
| **`reflect_on_tool_use=True`** | Tool result aane ke baad LLM ek aur pass karta hai — raw tool output ko natural-language answer mein convert karta hai. Iske bina agent kabhi-kabhi raw JSON hi thok deta hai. |
| **`run()` vs `on_messages()` + `TextMessage`** | `agent.run(task="...")` = one-shot convenience (task do, result lo). `on_messages([TextMessage(...)], CancellationToken())` = lower-level multi-turn API — agent **stateful hai**, pichhle turns yaad rakhta hai (lab1: naam dobara bhejne ki zaroorat nahi padi). |
| **`RoundRobinGroupChat`** | Sabse simple team: agents fixed order mein baari-baari bolte hain, sab messages sabko dikhte hain. Lab2 ka primary↔evaluator loop isi pe chalta hai. |
| **`TextMentionTermination` / `MaxMessageTermination`** | Team kab ruke: specific text mention hone pe (e.g. "APPROVE") ya max messages hit hone pe. **`\|` operator se combine** hota hai (0.7.5 pe verified) — OR semantics, jo pehle ho. Safety cap hamesha rakho. |
| **`output_content_type=PydanticModel`** | AssistantAgent ka structured output — result message ka `.content` directly pydantic object hota hai (lab2: `FlightQuote` with destination + price_usd). Model-dependent hai, fallbacks section 7 dekho. |
| **`RoutedAgent` + `@message_handler`** | Core ka agent: class banao, har message **type** ke liye ek async handler likho — type hints se routing automatic hoti hai. Backend analogy: typed message queue consumer. |
| **`SingleThreadedAgentRuntime`** | Core ka local runtime/event-loop: `register()` se agent factories do, `start()` karo, messages bhejo, `stop_when_idle()` se gracefully band karo. Saare agents isi ke andar live hote hain. |
| **`AgentId(type, key)`** | Agent ka address — runtime pe message **kisko** bhejna hai yeh batata hai. Same type + different key = alag-alag instances (lazy created). |
| **`send_message(msg, recipient)`** | Direct point-to-point RPC-style messaging: ek agent doosre ko typed message bhejta hai aur **response await** karta hai. Lab3/lab4 ka poora flow yahi hai. |

**Framework comparison (ek line each):** Agents SDK = ek **loop** (framework chalata hai), CrewAI = ek **team** (roles ko delegate karo), LangGraph = **explicit graph** (har node/edge tum likhte ho), **AutoGen = message-passing actors** — agents typed messages se baat karte hain, aur kyunki sab kuch messages hai, **same code gRPC distributed runtime pe multi-process/multi-machine scale ho sakta hai** (AutoGen ki unique story).

---

## 4. Provider Setup Note (Groq Free, Versions, Skipped Extras)

- **Groq free tier via `OpenAIChatCompletionClient`** (from `autogen_ext.models.openai`) — `base_url="https://api.groq.com/openai/v1"` + Groq key. Non-OpenAI model ke liye **`model_info=ModelInfo(...)`** dena **mandatory** hai (vision/function_calling/json_output/family flags), warna ValueError. Primary model `llama-3.3-70b-versatile`, structured output ke liye `openai/gpt-oss-120b`.
- **Version note** — course recordings **AutoGen 0.5.1** pe hain, hum **0.7.5** pe hain. Core APIs same hain (`run`, `on_messages`, `RoundRobinGroupChat`, `RoutedAgent` sab unchanged); jahan farak relevant tha wahan labs ke comments mein note hai. Termination ka `|` operator 0.7.5 pe verified working.
- **No OpenAI key needed** — poora Week 5 free Groq (+ optional Gemini) pe chalta hai. Har LLM call 3-attempt retry wrapper mein hai (free-tier transients).
- **Skipped extras (jaan-boojh ke):**
  - **MCP fetch server** — Ed lab2-equivalent mein MCP fetch tool use karta hai; humne httpx `fetch_page` plain-function substitute banaya (same concept, zero setup). **Real MCP Week 6 mein aayega** — wahan properly karenge.
  - **gRPC distributed runtime** — `GrpcWorkerAgentRuntime` se agents alag processes/machines pe chal sakte hain. API **bilkul same** hai (`register`/`send_message`), sirf runtime class badalti hai — isliye `SingleThreadedAgentRuntime` se concept poora cover ho jaata hai (lab3 comments mein note hai).
  - **Multimodal** — image-input demos ke liye vision model chahiye; hamare free Groq text models pe applicable nahi. Concept note kar lo: AgentChat `MultiModalMessage` support karta hai.

---

## 5. Recommended Order

1. **lab1 (agentchat basics)** — single agent + tools + multi-turn memory: AutoGen ka "hello world", 3-layer map ke saath — baaki sab isi foundation pe hai.
2. **lab2 (primary + evaluator team)** — structured output aur pehli **team**: termination conditions ke saath ek real feedback loop chalte dekho (draft → critique → rewrite → APPROVE).
3. **lab3 (core RPS)** — AgentChat ke neeche utro: raw actor model — typed messages, handlers, runtime lifecycle — yahi samajhna AutoGen ko baaki frameworks se alag karta hai.
4. **lab4 (agent creator)** — capstone mind-bender: ek agent **naye agents runtime pe create/register** karta hai aur unse collaborate karwata hai — Core ki dynamic registration ka payoff.

---

## 6. Milestone

> **Week 5 done = aap message-passing multi-agent systems bana sakte ho — including agents jo naye agents create karte hain.** High-level AgentChat teams (termination-gated feedback loops, structured output, tool use) se le kar low-level Core actors (typed messages, routed handlers, runtime lifecycle, dynamic agent registration) tak — aur yeh sab ek aise runtime pe jo distributed (gRPC) ho sakta hai bina code badle.

Compare karne ke liye Ed ka original code dekho: **github.com/ed-donner/agents → `5_autogen/`**.

---

## 7. Common Errors & Fixes

| Error / Symptom | Reason | Fix |
|---|---|---|
| **`ValueError: model_info is required`** on client create | Non-OpenAI model (Groq llama etc.) ke liye AutoGen capabilities nahi jaanta | `OpenAIChatCompletionClient(..., model_info=ModelInfo(vision=False, function_calling=True, json_output=True, family="unknown", structured_output=True))` explicitly pass karo (sab labs mein pattern hai) |
| **429 / RateLimitError / transient 5xx** on Groq | Free tier per-minute limits — teams aur multi-round flows mein calls jaldi stack hoti hain | Retry with sleep — sab labs mein 3-attempt retry wrapper built-in hai; phir bhi fail ho to 1 min ruk ke re-run |
| **400 `tool_use_failed`** on Groq llama | Llama kabhi-kabhi malformed tool call generate karta hai — provider reject kar deta hai | Transient hai — retry usually theek kar deta hai (lab1 run 1 mein real mein hua aur recover hua) |
| **400 on structured output** (`response_format: json_schema`) | Groq **llama-3.3-70b json_schema support nahi karta** | Structured output ke liye **`openai/gpt-oss-120b`** use karo (lab2/lab4 mein primary), fallback Gemini; last resort = `json_object` mode + manual pydantic parse (lab4 path 2) |
| **Gemini 429 daily quota** | Free-tier daily limit exhaust | Cheap probe call se pehle check karo, fail pe Groq gpt-oss-120b pe fallback (lab2 pattern — cross-model review phir bhi milta hai) |
| **Script hang ho jaata hai, kabhi exit nahi karta** | Core runtime mein `await runtime.stop_when_idle()` (ya `stop()`) bhool gaye — event loop chalta rehta hai | `start()` ↔ `stop_when_idle()` pair hamesha — `stop_when_idle` saare in-flight messages process hone tak wait karke cleanly band karta hai (lab3/lab4 pattern) |
| **Failed team retry pe turant khatam ho jaati hai** | Team fail hone ke baad uski group-chat state **"stopped"** rehti hai — same object reuse nahi kar sakte | Retry pe team **fresh rebuild** karo, purani team pe dobara `run()` mat karo (lab2 mein baked in) |
| **Agent raw JSON/tool output return karta hai, natural answer nahi** | `reflect_on_tool_use` default off | `AssistantAgent(..., reflect_on_tool_use=True)` set karo (lab1) |
| **Team kabhi rukti hi nahi / quota burn** | Sirf `TextMentionTermination` lagaya aur model ne magic word kabhi bola hi nahi | Hamesha `\| MaxMessageTermination(n)` safety cap combine karo (lab2: APPROVE ya 10 messages, jo pehle ho) |
| **Multi-turn memory kaam nahi kar rahi** | Har turn pe `agent.run()` se naya context, ya naya agent object bana diya | **Same agent instance** pe `on_messages()` use karo — state agent object mein hoti hai (lab1 demo 3: turn 2 ko naam yaad tha) |

---

*Happy building! Week 5 ke saath paanchon frameworks (direct API → Agents SDK → CrewAI → LangGraph → AutoGen) cover — next stop: Week 6 MCP.*
