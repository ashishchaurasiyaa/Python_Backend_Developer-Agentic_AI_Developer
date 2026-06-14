# Week 6 Practical Runbook — MCP (Hinglish Hands-On Guide) — THE FINAL WEEK 🎓

> Ed Donner's Agentic AI course — **Week 6 (Lectures L108–L131)** ke run-verified labs. **Yeh course ka aakhri week hai** — Model Context Protocol + **Trading Floor grand capstone**.
> Audience: experienced Python backend dev. Week 1–5 runbooks kar chuke ho — wahi style, ab **MCP** ke saath: tools/resources ko ek **standard protocol** se share karna, framework se nahi.
> Sab labs **Groq pe FREE** chalte hain, saare MCP servers **pure Python (FastMCP)** hain — node/npx ki zaroorat nahi. ✅ Chaaron labs live runs se verified hain (**real MCP stdio subprocesses + real Groq calls**).
>
> Official course code: **github.com/ed-donner/agents** → folder **`6_mcp`**

---

## 1. Learning Loop — Kaise Padhna Hai

Har lab ke liye yahi cycle repeat karo:

```
Lecture dekho  →  Note padho (parent Week6_MCP folder ke L108–L131 notes)
      →  Matching lab `uv run` karo  →  Code ke Hinglish comments padho
      →  Kuch tweak karo (server mein naya tool jodo, naya trader persona banao)  →  Next lab
```

- **Lecture pehle**, taaki "MCP framework kyon NAHI hai" wala mental model set ho — yeh protocol hai, agents banane ka tool nahi.
- **Lab ka output dekho, phir code padho** — har lab aur har server file mein bade Hinglish comment blocks hain jo lectures se directly map karte hain.
- **Tweak zaroori hai** — lab1 ke `greeter_server.py` mein ek naya `@mcp.tool()` jodo aur dekho agent use khud discover kar leta hai (yahi MCP ka magic hai: client code mein ZERO change). Lab2 mein naya symbol/price jodo, lab3 mein nayi entity yaad karwao, lab4 mein George Soros (contrarian) persona add karo.

---

## 2. Lab → Lecture Mapping Table

Sab commands **project root** se chalao:

```bash
cd /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/my-agentic-ai-project
```

| Lab File | Lectures | Concept | Run Command |
|---|---|---|---|
| `lab1_mcp_intro.py` | L108–L113 | **MCP basics**: USB-C analogy, HOST/CLIENT/SERVER roles, stdio transport; same server **do tarike se consume**: (A) raw `mcp` `ClientSession` — handshake, `tools/list` with JSON schemas, `call_tool`, `read_resource` haath se; (B) Agents SDK `MCPServerStdio` + `Agent(mcp_servers=[...])` — boilerplate gayab; marketplaces + supply-chain security note | `uv run Udemy_EdDonner_Course/Week6_MCP/Practical/lab1_mcp_intro.py` |
| `lab2_custom_accounts_server.py` | L114–L117 | **Apna MCP server banao** — Week-3 capstone `Account` business logic (`servers/accounts.py`, JSON persistence + guards) ko thin FastMCP wrapper (`servers/accounts_server.py`) se expose karna: 7 `@mcp.tool()` + 1 `@mcp.resource("accounts://report/{name}")`; agent deposit/buy karta hai, phir **disk-level state verify** hoti hai | `uv run Udemy_EdDonner_Course/Week6_MCP/Practical/lab2_custom_accounts_server.py` |
| `lab3_memory_market_servers.py` | L112, L118–L121 | **Multiple servers ek agent mein** — `mcp_servers=[memory, market]`; 3 MCP server types (L118); disk-backed memory server (`save_memory`/`recall_memories`/`list_entities`) + simulated market server (`get_price`/`get_prices`/`market_summary`); Task 2 ka **fresh `Runner.run`** disk se fact recall karta hai = persistence proof | `uv run Udemy_EdDonner_Course/Week6_MCP/Practical/lab3_memory_market_servers.py` |
| `lab4_trading_floor.py` | L122–L127 | **🏆 GRAND CAPSTONE — Trading Floor**: 3 persona traders (Warren=value, Cathie=growth, Ray=systematic; Soros comments mein) — har trader ka apna agent + **DO MCP servers** (`mcp_servers=[accounts, market]`), autonomous tool-driven trading round, markdown floor report with P&L | `uv run Udemy_EdDonner_Course/Week6_MCP/Practical/lab4_trading_floor.py` |

**`servers/` folder — 5 FastMCP Python servers** (sab stdio, sab labs inhe subprocess ki tarah spawn karte hain):
- `greeter_server.py` — lab1 ka teaching server (2 tools + 1 resource)
- `accounts.py` (pure business logic, no MCP) + `accounts_server.py` (thin FastMCP wrapper — 7 tools + 1 resource) — lab2 + lab4
- `memory_server.py` (JSON entity store — course ke knowledge-graph memory ka free substitute) — lab3
- `market_server.py` (seeded deterministic simulated prices — Polygon ka free substitute) — lab3 + lab4

**Side-effect files** (`Practical/output/`): `accounts.json` (lab2 + lab4 accounts), `memory.json` + `market_quotes.json` (lab3), `trading_report.md` (lab4 ka final report).

---

## 3. MCP Concepts — Cheat Sheet

| Concept | 1-2 Line Hinglish Explanation |
|---|---|
| **Protocol, NOT framework** | MCP se agents NAHI bante — yeh tools/resources/prompts ko **standard tarike se share** karne ka protocol hai. "USB-C of agentic AI": ek baar server bana, har MCP-compatible host use kar sakta hai. |
| **HOST** | Aapki agent application — Claude Desktop, ya hamare labs mein Agents SDK wala Python process. LLM yahin chalta hai. |
| **CLIENT** | Host ke andar ka connector — **har server ke liye ek dedicated 1-to-1 client**. Hamare labs mein `MCPServerStdio` yahi role karta hai. |
| **SERVER** | Alag process jo tools/resources/prompts expose karta hai. Counter-intuitive baat: zyada-tar MCP servers **aapke hi machine pe locally** chalte hain, remote nahi. |
| **stdio transport** | Client server ko **subprocess** spawn karta hai aur stdin/stdout pe JSON-RPC baat karta hai — sabse common, sab labs yahi use karte hain. |
| **SSE transport** | HTTP(S) streaming — **remote/hosted** servers ke liye. Rare hai; concept jaano, zaroorat padegi tab use karna. |
| **tools vs resources vs prompts** | **Tools** = functions jo LLM khud call karna decide karta hai (actions). **Resources** = read-only context/data jo aap prompt mein daalte ho (`accounts://report/{name}`). **Prompts** = server ke ready-made prompt templates. |
| **FastMCP** | `from mcp.server.fastmcp import FastMCP` → `mcp = FastMCP("name")` → function pe `@mcp.tool()` lagao (name + docstring + type hints se JSON schema auto-banta hai) → `mcp.run(transport="stdio")`. Bas — server ready. |
| **Logic vs wrapper split** | Business logic alag file mein rakho (`accounts.py` — plain Python, unit-testable), MCP server sirf **thin wrapper** ho (`accounts_server.py`). Backend dev analogy: service layer vs controller. |
| **Agents SDK integration** | `MCPServerStdio(params={"command": "uv", "args": ["run", abs_path]}, client_session_timeout_seconds=60)` → `async with` mein kholo → `Agent(..., mcp_servers=[server])`. SDK handshake + discovery + tool-call routing sab khud karta hai. |
| **Tool discovery** | Connection pe client `tools/list` bhejta hai — server apne tools **schemas ke saath advertise** karta hai. Isliye server mein naya tool jodo to client/agent code mein kuch change nahi karna padta. |
| **Marketplaces** | mcp.so, smithery.ai, glama — hazaron ready-made servers (GitHub, Slack, databases...). |
| **⚠️ SECURITY (L113)** | Kisi aur ka MCP server chalana = **arbitrary code apke machine pe** = `pip install` jaisa supply-chain risk. Sirf trusted publishers (Anthropic/Microsoft/official vendor) use karo; stars, community activity, source code check karo. |

**Framework series mein MCP kahan fit hota hai:** Agents SDK/CrewAI/LangGraph/AutoGen = agents **banane** ke tarike; MCP = un agents ko **tools/context dene** ka standard. Dono complementary hain — lab mein Agents SDK agent MCP servers consume karta hai.

---

## 4. Provider Setup & Free Substitutes

- **Groq free tier** har lab mein (`AsyncOpenAI(base_url="https://api.groq.com/openai/v1")` + `OpenAIChatCompletionsModel`), tracing disabled — koi OpenAI key nahi chahiye.
- **Groq quotas PER-MODEL hote hain** — isliye har lab mein retry + **model fallback chain** built-in hai (e.g. `llama-3.3-70b-versatile` → `openai/gpt-oss-120b` → `llama-4-scout` → `llama-3.1-8b-instant`). Verification ke dauraan 70b ka daily quota khatam hua tha — labs fallback se cleanly pass hue.

| Course mein | Hamare labs mein | Kyun |
|---|---|---|
| node/npx MCP servers (fetch, playwright, filesystem — L111) | **Pure Python FastMCP servers** (`servers/`) | node dependency hi nahi; concept same (stdio subprocess) |
| Brave Search MCP server (API key — L119) | **Zaroorat nahi padi** | memory + market apne servers se concept cover ho gaya |
| Polygon market data (API key/paid — L120-L121) | `market_server.py` — **seeded simulated prices** | free + deterministic, MCP shape bilkul same |
| Knowledge-graph memory server (L118) | `memory_server.py` — **JSON entity store** | same save/recall semantics, zero setup |
| OpenAI models + traces UI | Groq free + fallback chain, tracing disabled | OPENAI_API_KEY nahi hai |
| 4+ traders + scheduler (har 60 min — L127) | 3 traders, **single round** (scheduler/cron comments mein explained) | free Groq rate limits; production pattern document hai |

---

## 5. Recommended Order

1. **lab1 (mcp intro)** — MCP ka mental model + raw protocol vs SDK dono routes dekhna: pehle haath se handshake karoge to SDK ki value samajh aayegi.
2. **lab2 (custom accounts server)** — **apna server banana hi MCP ka asli skill hai** — logic/wrapper split + disk verification ke saath.
3. **lab3 (memory + market)** — multiple servers compose karna + cross-run persistent memory: capstone ke dono ingredients.
4. **lab4 (trading floor)** — sab kuch milakar grand capstone: personas × multiple MCP servers × autonomous trading 🏆

---

## 6. Milestone — COURSE COMPLETE! 🎓

> **Week 6 done = COURSE COMPLETE 🎓 — aap MCP servers bana/use kar sakte ho aur ek autonomous multi-agent trading floor chala sakte ho.** FastMCP se apne tools expose karna, kisi bhi MCP server ko Agents SDK agent mein plug karna, multiple servers compose karna, aur persona-driven autonomous agents se end-to-end system chalana — sab haath se kar chuke ho.

Compare karne ke liye Ed ka original code: **github.com/ed-donner/agents → `6_mcp/`**.

**Course ka final advice (L128–L129, ek line mein):** Framework-selection par mat atko — **simple se shuru karo (direct API ya Agents SDK), complexity tabhi jodo jab problem demand kare**; prompts aur traces par focus karo, scientist ki tarah experiment karo. Pura note: `L128_Framework_Selection_Advice.md` + `L129_10_Essential_Lessons.md`.

**Pura safar:** Week 1 direct API → Week 2 Agents SDK → Week 3 CrewAI → Week 4 LangGraph → Week 5 AutoGen → **Week 6 MCP**. 107+ notes, 21 labs, 6 runbooks — sab free-tier pe, sab run-verified. 🎉

---

## 7. Common Errors & Fixes

| Error / Symptom | Reason | Fix |
|---|---|---|
| **MCP server spawn/handshake timeout** | `MCPServerStdio` ka default session timeout (5s) `uv run` cold-start ke liye kam hai | `client_session_timeout_seconds=60` pass karo (sab labs mein already hai) |
| **Server file not found / spawn fail** | Subprocess ka cwd aapke script se alag ho sakta hai | `MCPServerStdio` params mein **absolute path** do (labs `Path(__file__).parent` se banate hain) |
| **Groq `429 RateLimitError` / daily TPD quota** | Free tier limits per-model hote hain | Labs mein retry + model-fallback chain built-in hai; phir bhi fail ho to 1–2 min ruko ya chain mein aur models jodo |
| **`accounts.json` / `memory.json` corrupt ya purana state** | Pichle run ka leftover, ya parallel writes | `output/` se file delete karo — agle run pe fresh ban jayegi (labs apne accounts start pe reset bhi karte hain) |
| **stderr pe server INFO logs ka shor** | FastMCP default INFO logging stdio ke saath mix hoti hai | `FastMCP("name", log_level="WARNING")` (ya `"ERROR"`) — servers mein pattern hai |
| **Trading report mein "round failed"** | Rate limit round ke beech aaya | Dobara chalao — lab4 mein per-trader failure isolation hai, baaki traders ka report ban jaata hai |
| **Subprocess zinda reh gaya / script hang** | `async with` context exit nahi hua | Servers ko hamesha `async with MCPServerStdio(...)` mein kholo; stuck ho to Ctrl+C — context manager cleanup karta hai |
| **Tool call ke args strings mein aaye (`{"amount": "10000"}`)** | LLM kabhi-kabhi numbers ko strings bhejta hai | FastMCP type hints se coerce kar leta hai — apne tools mein bhi defensively `float(amount)` pattern rakho |

---

*Educational simulation — real trading/financial advice nahi. Congratulations on finishing the course! 🎓🎉*
