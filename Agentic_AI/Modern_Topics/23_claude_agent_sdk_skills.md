# Modern Topics — Doc 23: Claude Agent SDK + Agent Skills ⭐

> **Goal:** Claude Agent SDK = **Claude Code ko library bana ke apne app me use karna** — built-in tools (file read/write, bash, grep, web search), full agent loop, context management, sab ready-made. Agent Skills = reusable "expertise packages" (folder + `SKILL.md`) jo agent zaroorat padne pe load karta hai. 2026 me production-agent interviews me "how would you build a coding/filesystem agent" ka expected answer ab SDK-level hai, raw API loop nahi.

---

## 1. Sabse pehle — 4 tarike agent banane ke (confusion clear karo)

Anthropic ecosystem me agent banane ke **4 distinct approaches** hain. Interview me inko mix karna red flag hai:

| # | Approach | Tum kya likhte ho | Harness kaun deta hai | Tools | Kab use karo |
|---|----------|-------------------|----------------------|-------|--------------|
| 1 | **Claude API — manual loop** | `while stop_reason == "tool_use"` loop khud | Tum (harness + hosting dono) | Sirf tumhare defined tools | Full control chahiye, koi beta dependency nahi |
| 2 | **Claude API — Tool Runner** (`client.beta.messages.tool_runner`) | Sirf tool functions (`@beta_tool` decorator) | SDK loop deta hai; hosting tumhari | Sirf tumhare defined tools | Custom-tool agent bina loop likhe (most common) |
| 3 | **Managed Agents (CMA)** | Agent config + tool results | **Anthropic** — loop bhi, per-session sandbox container bhi | Hosted sandbox (bash, files, code exec) + MCP + custom | Anthropic hi sab host kare; versioned agent configs |
| 4 | **Claude Agent SDK** (`claude-agent-sdk`) | Ek prompt + options | SDK deta hai **Claude Code ka poora harness** + built-in tools; hosting tumhari | Built-in Read/Write/Edit/Bash/Glob/Grep/WebSearch/WebFetch + MCP + subagents | Batteries-included coding/filesystem agent apne infra pe |

**Key mental model:** do independent sawaal — (a) harness (agent loop + context management) kaun deta hai, (b) deployment kaun karta hai. Options 1, 2, 4 me deployment **tumhari** hai; sirf option 3 (CMA) me Anthropic dono deta hai.

> ⚠️ **Tool Runner ≠ Agent SDK** — naam similar lagte hain par alag packages hain. Tool Runner regular `anthropic` SDK ka helper hai (tumhare tools pe loop chalata hai, koi built-in tool nahi, koi filesystem access nahi). Agent SDK **Claude Code packaged as a library** hai — built-in tools, hooks, subagents, permissions, sessions sab included.

---

## 2. Claude Agent SDK — install + basic query

```bash
pip install claude-agent-sdk        # Python
# ya
npm install @anthropic-ai/claude-agent-sdk   # TypeScript
```

Simplest usage — `query()` ek async generator hai jo poora agent loop chala deta hai:

```python
import anyio
from claude_agent_sdk import query

async def main():
    async for message in query(prompt="Is folder ke saare Python files me TODO comments dhundo aur list karo"):
        print(message)

anyio.run(main)
```

Bas itna. Iske peeche SDK: prompt bheja → Claude ne Glob/Grep/Read tools use kiye (khud, bina tumhare implement kiye) → loop chalta raha jab tak task done → final result. Manual loop me yehi cheez 100+ lines hoti.

## 3. Options — model, tools, permissions, system prompt

```python
from claude_agent_sdk import query, ClaudeAgentOptions

options = ClaudeAgentOptions(
    model="claude-opus-5",                      # default latest; explicitly pin kar sakte ho
    system_prompt="You are a senior Python reviewer. Be terse.",
    allowed_tools=["Read", "Grep", "Glob"],     # sirf read-only tools — safe reviewer agent
    permission_mode="default",                  # ya "acceptEdits", "bypassPermissions", "plan"
    cwd="/path/to/repo",                        # agent ka working directory
    max_turns=20,
)

async for message in query(prompt="Review auth module for security issues", options=options):
    ...
```

**Permission modes** — production me sabse important knob:
- `default` — dangerous tools (Bash, Write) pe permission callback trigger hota hai
- `acceptEdits` — file edits auto-approve, baaki pooche
- `plan` — sirf plan banaye, execute na kare
- `bypassPermissions` — sab allow (sirf sandboxed env me!)

## 4. Multi-turn — `ClaudeSDKClient` (conversation state)

`query()` one-shot hai. Conversation continue karni ho to client use karo:

```python
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

async with ClaudeSDKClient(options=ClaudeAgentOptions(cwd="./myrepo")) as client:
    await client.query("Failing tests dhundo aur causes batao")
    async for msg in client.receive_response():
        print(msg)

    # Same session, context yaad hai
    await client.query("Ab pehla wala fix karo")
    async for msg in client.receive_response():
        print(msg)
```

## 5. Custom tools (in-process MCP) + hooks

Apne tools SDK me **in-process MCP server** ke through jaate hain — koi separate process nahi:

```python
from claude_agent_sdk import tool, create_sdk_mcp_server, ClaudeAgentOptions

@tool("get_order_status", "Fetch order status from our DB", {"order_id": str})
async def get_order_status(args):
    status = await db.fetch_status(args["order_id"])   # tumhara real code
    return {"content": [{"type": "text", "text": f"Order {args['order_id']}: {status}"}]}

server = create_sdk_mcp_server(name="shop-tools", tools=[get_order_status])

options = ClaudeAgentOptions(
    mcp_servers={"shop": server},
    allowed_tools=["Read", "Grep", "mcp__shop__get_order_status"],
)
```

**Hooks** — deterministic control points (Claude Code jaise hi): `PreToolUse` (tool chalne se pehle block/modify), `PostToolUse`, `Stop`, etc. Example: `PreToolUse` hook me `rm -rf` wale bash commands hamesha block karna — prompt-level guard nahi, code-level guarantee.

## 6. Subagents

Options me `agents` define karo — parallel/isolated sub-tasks ke liye:

```python
options = ClaudeAgentOptions(
    agents={
        "test-writer": {
            "description": "Writes pytest tests for a given module",
            "prompt": "You write thorough pytest tests. No source edits.",
            "tools": ["Read", "Write", "Grep"],
            "model": "haiku",     # sasta model sub-task ke liye
        },
    },
)
```

Main agent zaroorat pe `test-writer` ko delegate karega — apna context, apne tools, apna model.

---

## 7. Agent Skills — kya hain aur kyun

**Skill = ek folder** jisme `SKILL.md` (instructions) + optional scripts/references. Concept: **progressive disclosure** — skill ka sirf naam+description hamesha context me rehta hai (~2 lines); poori file tab load hoti hai jab task relevant ho. Isse 50 skills rakh sakte ho bina context bloat ke.

```
my-skill/
├── SKILL.md          # frontmatter (name, description) + instructions
├── references/       # optional deep-dive docs (aur bhi lazy-loaded)
└── scripts/          # optional runnable helpers
```

```markdown
---
name: pdf-invoice-extractor
description: Extract line items and totals from PDF invoices into structured JSON. Use when the user mentions invoices, bills, or PDF extraction.
---

# PDF Invoice Extraction

1. Use pdfplumber to extract text tables...
2. Validate totals: sum(line_items) == grand_total...
```

**Description sabse important hai** — usi se model decide karta hai skill kab load karni. Trigger conditions likho ("Use when..."), sirf kya karti hai nahi.

**Kahan-kahan chalti hain skills:**
- **Claude Code / Agent SDK** — `.claude/skills/` folder me rakho, automatically discover hoti hain
- **Claude API (Messages)** — `container={"skills": [{"type": "anthropic", "skill_id": "xlsx"}]}` + code-execution tool (betas: `code-execution-2025-08-25` + `skills-2025-10-02`); Anthropic ki pre-built skills: `pptx`, `xlsx`, `docx`, `pdf`
- **Managed Agents** — agent config ke `skills` array me (max 20)
- **Claude.ai** apps me bhi same format

**Skills vs MCP vs RAG (interview favourite):**

| | Skills | MCP | RAG |
|---|---|---|---|
| Kya deta hai | *Procedural* knowledge — "kaise karna hai" instructions | *Tools/connectivity* — external systems se baat | *Factual* knowledge — documents se retrieval |
| Load kab | Model khud decide karta hai (progressive disclosure) | Tool call pe | Query-time similarity search |
| Format | Folder + markdown | Protocol (JSON-RPC servers) | Vector DB + chunks |

Teeno complementary hain: MCP tool *access* deta hai, Skill batati hai us tool ko *expert ki tarah use kaise karna*.

---

## 8. Kab kya chuno — decision tree

```
Kya Anthropic hi hosting + sandbox de? ──yes──▶ Managed Agents (CMA)
        │ no
Kya filesystem/bash/coding agent chahiye? ──yes──▶ Claude Agent SDK
        │ no
Kya sirf apne custom tools ka loop chahiye? ──yes──▶ Tool Runner
        │ no (full control / no beta)
        ▼
   Manual loop
```

## 9. Interview Angle

**Q: Claude Agent SDK aur plain Anthropic SDK (Tool Runner) me kya farq hai?**
Tool Runner regular API SDK ka helper hai — tumhare define kiye tools pe request→execute→loop cycle automate karta hai, koi built-in tool nahi. Agent SDK Claude Code ka poora harness library form me hai — built-in file/bash/search tools, context management, hooks, subagents, permission system, sessions. Tool Runner = "loop likhne se bacho"; Agent SDK = "poora coding agent ready-made".

**Q: Skills context window kyun nahi bloat karti?**
Progressive disclosure — startup pe sirf har skill ka name+description (metadata) context me hota hai. Model task dekh ke relevant skill ki poori `SKILL.md` tab read karta hai jab zaroorat ho, aur `references/` files usse bhi lazy. 100 skills ≈ 100 chhoti description lines, not 100 full documents.

**Q: Production me Agent SDK agent ko safe kaise karoge?**
(1) `allowed_tools` allowlist — reviewer agent ko sirf Read/Grep/Glob, Write/Bash nahi. (2) `permission_mode` + `can_use_tool` callback — destructive actions pe human gate. (3) `PreToolUse` hooks — deterministic blocks (e.g. `.env` read block, `rm -rf` block) jo prompt injection se bypass nahi hote. (4) Sandboxed `cwd` / container me chalao. (5) `max_turns` + cost caps.

**Q: Agent SDK vs LangGraph?**
LangGraph = graph-based orchestration framework, model-agnostic, tum nodes/edges/state explicitly design karte ho. Agent SDK = opinionated single-agent harness (Claude Code ka), tools + loop built-in, orchestration model khud karta hai. Complex multi-agent DAGs with custom state → LangGraph; "ek capable agent jo files/code pe kaam kare" → Agent SDK me 10x kam code.

---

## Related
- MCP server development → [08_mcp_advanced_server_dev.md](08_mcp_advanced_server_dev.md)
- Coding-agent harness internals (loop, context mgmt) → [11_coding_agent_harness_deep_dive.md](11_coding_agent_harness_deep_dive.md)
- OpenAI ka equivalent stack → [24_openai_agentkit.md](24_openai_agentkit.md)
- AI security (tool poisoning, prompt injection — hooks kyun zaroori) → [09_ai_security_threats.md](09_ai_security_threats.md)
