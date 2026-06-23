# Modern Topics — Doc 7: AI Coding Tools (Deep Dive) 🛠️⭐

> **Goal:** `00_ai_tools_landscape.md` ki §4 ka **deep dive**. AI coding tools = tumhari daily reality (tum abhi Claude Code use kar rahe ho). Yahan har major tool ka **kya / kab / kyun**, comparison tables, aur backend dev ke liye practical advice.
>
> Ye agentic AI ka hi applied form hai: ReAct loop (Level 6) + tool use (Level 4) + MCP (Level 7) → ek IDE/CLI me packed.

---

## 1. AI coding tools ki 5 families 🧠

Sab tools 5 buckets me aate hain — pehle ye samjho, phir tool yaad rakhna aasan:

| Family | Kya karta hai | Examples |
|---|---|---|
| **1. Autocomplete** | Tum type karte ho, ye next line suggest karta hai | Copilot, Codeium, Tabnine |
| **2. Chat-in-IDE** | Editor me sidebar chat (code samjhao, fix karo) | Copilot Chat, Cursor chat |
| **3. Agentic IDE** | AI khud multi-file edit + run + fix karta hai | Cursor, Windsurf |
| **4. CLI agent** | Terminal me agent (no IDE) | Claude Code, Aider, Codex CLI |
| **5. App/UI builder** | Prompt → poora running app/UI | v0, Bolt, Lovable, Replit Agent |

> Bonus: **autonomous SWE** (Devin) = goal do, ye PR tak khud banata hai. Family 4 ka super-agent.

---

## 2. The big comparison table 🎯

| Tool | Family | Best for | Model | Tier |
|---|---|---|---|---|
| **Claude Code** | CLI agent | Terminal-first, multi-file, large refactors, agents | Claude | Paid (sub/API) |
| **Cursor** | Agentic IDE | All-round daily driver, VS Code feel | Multi (Claude/GPT) | Free + Pro |
| **GitHub Copilot** | Autocomplete + chat | Inline suggestions, GitHub/Office | Multi | Paid (free tier) |
| **Windsurf** | Agentic IDE | Agent "flows" (Cascade), clean UX | Multi | Free + paid |
| **Aider** | CLI agent | Git-native pair programming, scriptable | Multi (your key) | Free (OSS) |
| **Codeium** | Autocomplete | Free Copilot alternative | Own/multi | Free + paid |
| **Tabnine** | Autocomplete | Privacy/self-host, enterprise | Own/multi | Paid |
| **v0 (Vercel)** | UI builder | React/Tailwind components from prompt | GPT-ish | Free + paid |
| **Bolt.new** | App builder | Full-stack app in browser | Multi | Free + paid |
| **Lovable** | App builder | Non-coder → web app | Multi | Free + paid |
| **Replit Agent** | App builder | Build + host in one place | Multi | Paid |
| **Devin** | Autonomous SWE | Hands-off tickets → PR | — | Paid (pricey) |

> "Multi" = tum model choose kar sakte ho (Claude / GPT / Gemini). Backend kaam ke liye **Claude models** generally best coding pe.

---

## 3. Family-by-family deep dive

### 3.1 Autocomplete (Copilot, Codeium, Tabnine)
- **Kaam:** cursor pe context dekh ke greyed-out suggestion → `Tab` se accept.
- **Strength:** boilerplate, loops, tests, repetitive code super fast.
- **Weakness:** poore project ka plan nahi banata; sirf local context.
- **Pick:** Copilot (mainstream), Codeium (free), Tabnine (privacy/self-host).

### 3.2 Agentic IDE (Cursor, Windsurf)
- **Kaam:** "is feature ko add karo" → AI khud relevant files dhoondh ke multi-file edit karta hai, diff dikhata hai, test chala sakta hai.
- **Cursor:** VS Code ka fork — familiar, fast, `Cmd+K` inline edit, agent mode, codebase chat.
- **Windsurf:** "Cascade" agent flows, thoda zyada autonomous feel.
- **Pick:** zyadatar log **Cursor** se start karte hain (VS Code muscle memory).

### 3.3 CLI agent (Claude Code, Aider, Codex CLI)
- **Kaam:** terminal me agent — repo me changes, commands run, git, tests. No GUI.
- **Claude Code:** strong multi-step planning, MCP tools, subagents, hooks, skills. Large refactors/migrations ke liye accha.
- **Aider:** lightweight, git-commit har change pe, apni API key.
- **Strength:** scriptable, CI me chal sakta hai, headless automation.
- **Pick:** tum already **Claude Code** pe ho — yahi tumhara primary banao.

### 3.4 App/UI builders (v0, Bolt, Lovable, Replit Agent)
- **Kaam:** plain prompt → working frontend/app (preview ke saath).
- **v0:** UI components (React + Tailwind + shadcn) — designer/frontend ke liye.
- **Bolt / Lovable:** full app in-browser, instant preview, deploy.
- **Caveat:** prototypes ke liye great; production-grade backend pe inhe blindly trust mat karo.

### 3.5 Autonomous SWE (Devin)
- **Kaam:** Jira/GitHub ticket do → ye plan, code, test, PR khud banata hai.
- **Reality (2026):** impressive but supervision chahiye; scoped tasks pe best, ambiguous pe struggle.

---

## 4. Backend engineer ke liye kya use karu? 🟢

```
Daily driver  : Claude Code (CLI agent — tum yahi seekh rahe ho)  ✅
IDE me kaam   : Cursor (jab GUI/diff/visual chahiye)
Inline speed  : Copilot ya Codeium (autocomplete, optional)
Prototyping   : v0/Bolt (sirf jab quick frontend/demo chahiye)
```

**Stack ban gaya:** Claude Code (heavy lifting) + Cursor (visual edits) + ek autocomplete. Isse zyada tools = context-switching waste.

---

## 5. In tools ke andar kya chalta hai? (interview gold) 🎯

Ye sab "magic" nahi — tumhare course ke patterns hi hain:

| Concept | Tool me kahan |
|---|---|
| **ReAct loop** (Level 6) | Agent: Thought → Action (edit/run) → Observation (output) → repeat |
| **Tool use** (Level 4) | read_file, write_file, run_bash, search — ye sab "tools" hain |
| **MCP** (Level 7) | Tool ko external systems (DB, browser, APIs) se jodna |
| **Context / RAG** (Level 5) | Codebase ko index/embed karke relevant files dhoondhna |
| **Memory** (Level 6) | Project conventions, past edits yaad rakhna |
| **Guardrails** (Level 8) | Permissions, sandboxing, "ye command chalau?" confirm |

**Interview line:** "AI coding agents are just a ReAct loop over file-system + shell tools, with codebase retrieval for context — same patterns as any agent, specialized for software tasks."

---

## 6. Best practices — AI coding tools effectively use karo

1. **Chhota scope do.** "Pura app banao" se "is function me pagination add karo" 10x behtar result.
2. **Context do.** Relevant files/error mention karo; agent ko guess mat karne do.
3. **Diff padho, blindly accept mat karo.** Tum reviewer ho — AI junior dev hai.
4. **Tests pehle/saath.** Agent ko verify loop do ("test chalao, fix karo").
5. **Conventions file rakho** (`CLAUDE.md`/rules) — agent uske hisaab se likhega.
6. **Secrets/permissions sambhalo.** Agent ko prod creds/destructive commands na do bina dekhe.
7. **Plan → execute.** Bade kaam me pehle plan maango, phir code (Level 6 pattern).

---

## 7. Pitfalls ⚠️

- **Hallucinated APIs** — AI gair-maujood function/library bana deta hai. Verify karo.
- **Outdated knowledge** — model ka cutoff; naye library versions galat ho sakte hain.
- **Over-trust** — "works on my machine" demo ≠ production-ready.
- **Tool sprawl** — 6 tools = 0 mastery. 2-3 fix karo.
- **Skill atrophy** — fundamentals khud bhi likhte raho; warna debugging weak ho jaati hai (interview me dikhta hai).

---

## 8. Interview Q&A 🎯

**Q: AI coding tools kaise kaam karte hain?**
A: ReAct-style agent loop — LLM plans, calls tools (read/write file, run shell, search codebase), observes output, iterates. Codebase retrieval (embeddings) context deta hai. MCP external systems connect karta hai.

**Q: Cursor vs Claude Code?**
A: Cursor = agentic IDE (visual, VS Code-based, diffs). Claude Code = CLI agent (terminal-first, scriptable, headless/CI, large multi-file refactors). IDE workflow → Cursor; terminal/automation/big refactor → Claude Code. Often dono together.

**Q: Autocomplete vs agent?**
A: Autocomplete = local next-token suggestion (Copilot). Agent = multi-step, multi-file, runs commands, self-corrects (Claude Code/Cursor agent). Pehla speed, doosra autonomy.

**Q: Production me AI-generated code pe kaise bharosa karo?**
A: Treat as junior PR — review diffs, run tests, lint/type-check, security scan, no blind merge. Tum accountable ho.

---

## TL;DR

- **5 families:** autocomplete · chat-in-IDE · agentic IDE · CLI agent · app builder.
- **Tumhara stack (backend):** Claude Code (primary) + Cursor (visual) + optional autocomplete.
- Andar sab **ReAct + tool use + RAG + MCP** hi hai — naya kuch nahi, applied form.
- **Tum reviewer ho, AI junior dev hai.** Scope chhota, diff padho, tests chalao.

➡️ Related: `00_ai_tools_landscape.md` (full map) · `06_playwright_browser_automation.md` (browser tool) · Level 6 (agent patterns) · Level 7 (MCP, frameworks)
