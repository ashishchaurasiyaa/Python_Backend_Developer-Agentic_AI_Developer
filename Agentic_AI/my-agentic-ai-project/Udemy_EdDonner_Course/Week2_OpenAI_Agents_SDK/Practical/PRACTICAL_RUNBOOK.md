# Week 2 Practical Runbook — OpenAI Agents SDK (Hinglish Hands-On Guide)

> Ed Donner's Agentic AI course — **Week 2 (Lectures L28–L48)** ke run-verified labs.
> Audience: experienced Python backend dev. Week 1 ka runbook already kar chuke ho — wahi style, ab framework ke saath.
>
> Official course code: **github.com/ed-donner/agents** → folder **`2_openai`**

---

## 1. Learning Loop — Kaise Padhna Hai

Har lab ke liye yahi cycle repeat karo:

```
Lecture dekho  →  Note padho (parent folder ke L28-L48 notes)
      →  Matching lab `uv run` karo  →  Code ke Hinglish comments padho
      →  Kuch tweak karo / exercise try karo  →  Next lab
```

- **Lecture pehle**, taaki concept ka "why" clear ho.
- **Lab ka output dekho**, phir code ke comments line-by-line padho — har lab mein bade Hinglish comment blocks hain jo lecture se directly map karte hain.
- **Tweak zaroori hai** — instructions badlo, naya tool add karo, model swap karo. Bina haath gande kiye SDK yaad nahi rahega.

---

## 2. Lab → Lecture Mapping Table

Sab commands **project root** se chalao:

```bash
cd /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/my-agentic-ai-project
```

| Lab File | Lectures | Concept | Run Command |
|---|---|---|---|
| `lab1_agents_sdk_basics.py` | L28–L32 | Async primer (sequential vs `asyncio.gather`), pehla `Agent` + `Runner.run()`, `@function_tool` × 2 (SDK ka built-in tool loop), tracing on/off | `uv run Udemy_EdDonner_Course/Week2_OpenAI_Agents_SDK/Practical/lab1_agents_sdk_basics.py` |
| `lab2_sales_agents_handoffs.py` | L33–L38 | Ed ka SDR project: 3 email-writer agents parallel mein, `.as_tool()` se agents-as-tools (Sales Manager picks best), phir **handoff** to Email Formatter + `send_email` mock (outbox.txt) | `uv run Udemy_EdDonner_Course/Week2_OpenAI_Agents_SDK/Practical/lab2_sales_agents_handoffs.py` |
| `lab3_multimodel_guardrails.py` | L39–L41 | Multi-model swap (Groq + Gemini, same Agent), structured outputs (`output_type=` Pydantic), `@input_guardrail` + tripwire | `uv run Udemy_EdDonner_Course/Week2_OpenAI_Agents_SDK/Practical/lab3_multimodel_guardrails.py` |
| `lab4_deep_research.py` | L42–L48 | **Capstone**: planner (structured plan) → 3 parallel search agents (free Wikipedia tool) → writer (markdown report) → optional Gradio UI | `uv run Udemy_EdDonner_Course/Week2_OpenAI_Agents_SDK/Practical/lab4_deep_research.py` (UI ke liye end mein `ui` add karo) |

Side-effect files: lab2 → `Practical/outbox.txt` (mock sent emails), lab4 → `Practical/sample_report.md` (real generated report).

---

## 3. SDK Core Concepts — Cheat Sheet

| Concept | 1-2 Line Hinglish Explanation |
|---|---|
| **`Agent`** | Ek lightweight config object: `name` + `instructions` (system prompt) + optional `tools`, `model`, `output_type`, `handoffs`. Khud kuch run nahi karta. |
| **`Runner.run(agent, input)`** | Yahi actual execution hai — async call jo LLM loop chalata hai (tool calls, handoffs sab handle karta hai) aur `result.final_output` deta hai. |
| **`@function_tool`** | Kisi bhi Python function ko LLM-callable tool bana deta hai — docstring + type hints se JSON schema auto-generate hota hai. Week 1 mein humne yeh loop haath se likha tha; ab SDK free mein deta hai. |
| **`.as_tool()` vs handoffs** | `.as_tool()`: ek agent doosre agent ko tool ki tarah call karta hai, **control wapas aata hai** (manager pattern). **Handoff**: poori conversation doosre agent ko **transfer** ho jaati hai, control wapas nahi aata. |
| **`output_type=` (Pydantic)** | Agent ko bolo "is exact schema mein jawab do" — `final_output` string nahi, typed Pydantic object milta hai. Week 1 ke L10 wali unpredictability ka ilaaj. |
| **`@input_guardrail` + tripwire** | Ek mini-agent jo main agent ke input ko pehle check karta hai; problem mili to `tripwire_triggered=True` → SDK `InputGuardrailTripwireTriggered` raise karta hai aur main agent run hi nahi hota. |
| **`set_tracing_disabled(True)`** | SDK by default traces OpenAI platform ko bhejta hai; hum non-OpenAI key (Groq) use kar rahe hain to 401 spam aata — isliye off. Production mein `set_tracing_export_api_key()` se proper OpenAI key de sakte ho. |

---

## 4. Provider Setup Note (Groq Default, Fallbacks Kab)

- **Default = Groq free tier.** SDK officially OpenAI ke liye bana hai, lekin har OpenAI-compatible API ke saath chalta hai:
  ```python
  client = AsyncOpenAI(base_url="https://api.groq.com/openai/v1", api_key=GROQ_API_KEY)
  model = OpenAIChatCompletionsModel(model="llama-3.3-70b-versatile", openai_client=client)
  agent = Agent(name="...", instructions="...", model=model)
  ```
- **Tracing disabled kyon:** traces OpenAI ko jaate hain, OpenAI key nahi hai → har run pe 401 errors ki spam. `set_tracing_disabled(True)` ek line mein fix.
- **Structured output fallback kab chahiye:** Groq ka `llama-3.3` `json_schema` response_format ko **400 se reject** karta hai. Labs mein fallback ladder hai:
  1. Groq `llama-3.3` (direct `output_type`) — fail hoga
  2. Groq `openai/gpt-oss-120b` — kabhi chalta hai, kabhi `json_validate_failed` (flaky)
  3. Gemini `gemini-2.5-flash` (OpenAI-compat endpoint) — `json_schema` support karta hai, quota allow kare to best
  4. **Manual fallback (sabse reliable):** Groq llama-3.3 ko "respond ONLY with JSON" bolo + `model_validate_json()` se parse karo — lab4 ka poora pipeline isi pe verified chala hai.
- Lab3/lab4 mein yeh ladder code mein implemented + Hinglish comments mein documented hai — first working provider cache bhi hota hai.

---

## 5. Recommended Order

1. **lab1** — SDK ka mental model banao: async, Agent/Runner, tool loop. Baaki sab isi foundation pe hai.
2. **lab2** — multi-agent patterns: parallel agents, agents-as-tools vs handoff ka difference yahin pakka hota hai.
3. **lab3** — production hygiene: model swap, typed outputs, guardrails — real systems mein yahi cheezein bugs rokti hain.
4. **lab4** — capstone: sab patterns ek deep-research pipeline mein combine + Gradio UI. Yeh portfolio-worthy project hai.

---

## 6. Milestone

> **Week 2 done = aap ek multi-agent, guardrailed, deep-research system bana sakte ho** — planner → parallel workers → writer, typed Pydantic outputs ke saath, input guardrails ke saath, kisi bhi OpenAI-compatible provider pe.

Compare karne ke liye Ed ka original code dekho: **github.com/ed-donner/agents → `2_openai/`** (wahan OpenAI key + hosted `WebSearchTool` use hota hai; humne free Groq + keyless Wikipedia tool se same patterns banaye).

---

## 7. Common Errors & Fixes

| Error / Symptom | Reason | Fix |
|---|---|---|
| Har run pe **401 error spam** (tracing/OpenAI) | SDK traces api.openai.com ko bhej raha hai, valid OpenAI key nahi | `from agents import set_tracing_disabled; set_tracing_disabled(True)` |
| **400: `json_schema` not supported** (Groq llama-3.3 + `output_type`) | Groq llama models structured response_format support nahi karte | Fallback ladder use karo (Section 4): gpt-oss-120b → gemini-2.5-flash → manual "ONLY JSON" prompt + `model_validate_json` |
| **400: `'required' present but 'properties' is missing`** | Groq zero-argument tools/default handoff tool ka empty schema reject karta hai | Tool ko kam-se-kam ek parameter do (lab1: `timezone: str`); handoff ke liye explicit `handoff(..., input_type=SomePydanticModel)` use karo (lab2) |
| **Invalid tool name** on handoff | Agent name mein space hai → auto tool name invalid | `handoff(agent, tool_name_override="transfer_to_email_formatter")` |
| **429 / RateLimitError** on free Groq tier | Free tier ke per-minute token limits, especially parallel runs mein | Thoda wait karke retry karo, chhota model use karo (e.g. `llama-3.1-8b-instant`), ya parallel calls kam karo |
| **429 RESOURCE_EXHAUSTED** on Gemini | Us model ka free-tier quota khatam (e.g. gemini-2.0-flash) | Doosra model try karo (`gemini-2.5-flash` verified working) ya Groq manual-JSON fallback pe gir jao |
| **`json_validate_failed`** intermittently (gpt-oss-120b) | Model flaky JSON deta hai kabhi-kabhi | Retry ya ladder mein next provider — labs yeh automatically karte hain |
| **Gradio port busy** (lab4 `ui` mode) | Port 7860 pe pehle se kuch chal raha hai | Purana process band karo, ya `demo.launch(server_port=7861)` set karo / `GRADIO_SERVER_PORT=7861` env var |

---

*Happy building! Week 3 mein milte hain.*
