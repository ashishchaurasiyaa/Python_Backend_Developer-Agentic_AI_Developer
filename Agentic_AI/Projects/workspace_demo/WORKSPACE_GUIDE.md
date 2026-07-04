# Workspace Guide — The Complete Walkthrough

> Your presentation companion. This explains **every file** in a Claude Code
> workspace, what is committed vs. gitignored, and exactly **how to add Skills
> and MCP servers**. Examples all come from this project.

---

## 1. What is a "workspace"?

Your **codebase doesn't change**. Claude Code adds a thin, version-controlled
**configuration layer** on top of it:

```
  your code  (backend/ + frontend/)        ← what you ship
  +  CLAUDE.md                              ← memory / instructions
  +  .claude/   (agents, skills, settings)  ← capabilities + governance
  +  .mcp.json                              ← external tool connections
  =  a Claude Code workspace
```

That config layer is what turns a plain repo into one Claude Code understands.

---

## 2. Internal files — what lives where (kya internal files hongi)

| File / folder | Committed? | Purpose |
|---|---|---|
| `CLAUDE.md` | ✅ yes | Project memory. Loaded **every session**. Build commands, architecture, conventions. |
| `.claude/settings.json` | ✅ yes | Permissions, env vars, hooks, model — shared with the team. |
| `.claude/settings.local.json` | ❌ no (gitignored) | **Personal** overrides. Your machine only. |
| `.claude/agents/*.md` | ✅ yes | Subagent definitions — one file per agent. |
| `.claude/skills/<name>/SKILL.md` | ✅ yes | Reusable workflows. A folder per skill. |
| `.claude/commands/*.md` | ✅ yes | Slash commands (e.g. `/ship-check`). |
| `.mcp.json` | ✅ yes | MCP servers for this project (the "tool plugins"). |
| `.env` | ❌ no (gitignored) | Secrets — your `ANTHROPIC_API_KEY`. |
| `.env.example` | ✅ yes | Template so others know which vars to set. |

**User scope mirror:** the same folders also exist globally at `~/.claude/`
(`~/.claude/agents/`, `~/.claude/skills/`, `~/.claude/settings.json`,
`~/.claude/CLAUDE.md`). Project scope is for the team; user scope is personal and
applies across all your projects. **Precedence on conflict:**
`managed > local > project (.claude/) > user (~/.claude/)`.

---

## 3. What goes in .gitignore (kya gitignore me file hongi)

Commit the shared config; keep secrets and personal/local files out:

```gitignore
.env                          # secrets — your API key
.env.*
!.env.example                 # but DO commit the template
.claude/settings.local.json   # personal settings, not the team's
.claude/agent-memory-local/   # local-scope subagent memory
__pycache__/ , .venv/         # Python junk
.DS_Store , node_modules/
```

Rule of thumb: **`.claude/` is committed** (the team shares it). Only the
`*.local.json` files, `.env`, and generated/cache folders are ignored.

---

## 4. Full project setup (poora project setup kaise)

```bash
# 1. dependencies
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. secrets (gitignored)
cp .env.example .env          # edit .env → paste ANTHROPIC_API_KEY

# 3. run
uvicorn backend.main:app --reload     # → http://127.0.0.1:8000

# 4. (first time in a fresh repo) let Claude write CLAUDE.md for you
#    run `/init` inside Claude Code — it scans the repo and generates one
```

The backend (`backend/main.py`) serves the frontend **and** the API. The
frontend (`frontend/app.js`) calls `POST /api/chat` → Claude → reply.

---

## 5. How to add a Skill (skills add karenge project me kaise)

A Skill is just a **folder with a `SKILL.md`** inside `.claude/skills/`.

```
.claude/skills/
└── my-skill/
    ├── SKILL.md            ← required (the only must-have)
    ├── reference/...       ← optional docs, loaded on demand
    └── scripts/...         ← optional helper scripts
```

`SKILL.md` is markdown with YAML frontmatter:

```markdown
---
name: My skill
description: What it does AND when to use it. This line is the trigger —
             Claude reads it to decide whether to load the skill.
allowed-tools: Bash(npm *)       # optional: tools usable without a prompt
---

# Steps
1. Do this…
2. Then this…
See reference/details.md for the long version.
```

**Steps to add one:**
1. `mkdir -p .claude/skills/my-skill`
2. Create `SKILL.md` with `name` + a sharp `description` (the description is how
   Claude knows when to use it — be specific).
3. (optional) Add `scripts/` or `reference/` files; reference them from `SKILL.md`.
4. That's it — no install. Claude auto-discovers it; you can also run `/my-skill`.

**Progressive disclosure (the key idea):** only the `name` + `description` stay
in context. The body loads when the skill triggers; bundled files (like
[`add-endpoint/reference/conventions.md`](.claude/skills/add-endpoint/reference/conventions.md))
load only when actually opened. → ship lots of skills cheaply.

**In this project:** `add-endpoint` (scaffold a route) and `run-app` (launch it).

---

## 6. How to add an MCP server (mcp add karenge claude me kaise)

MCP (Model Context Protocol) connects Claude to **external tools** — a database,
the web, GitHub, a browser. Project-scoped servers live in **`.mcp.json`** at the
repo root (committed, so the team shares them):

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "."]
    },
    "fetch": {
      "command": "uvx",
      "args": ["mcp-server-fetch"]
    }
  }
}
```

**Two ways to add one:**
- **CLI (easiest):** `claude mcp add fetch -- uvx mcp-server-fetch`
  (add `-s project` to write it into this `.mcp.json` for the team; default is
  your personal user scope).
- **By hand:** add an entry to `.mcp.json` as above.

Then inside Claude Code, run **`/mcp`** to see connection status and authenticate
(for servers that need OAuth). Secrets for MCP servers go in env vars or your
personal config — **never** commit tokens into `.mcp.json`.

Scopes: **project** (`.mcp.json`, shared) · **user/global** (`~/.claude.json`,
personal, all projects) · **local** (this project, just you).

---

## 7. Files that connect the project to Claude (project connection ki files)

These four are what "wire up" the repo to Claude Code:

| File | Role in the connection |
|---|---|
| `CLAUDE.md` | Tells Claude **what the project is** — instructions & memory, every session. |
| `.claude/settings.json` | Tells Claude **what it's allowed to do** — permissions, env, hooks. |
| `.mcp.json` | Tells Claude **what external tools** it can reach. |
| `.env` | Holds the **`ANTHROPIC_API_KEY`** the backend uses to call the model (this is the app↔API link, separate from Claude Code itself). |

Plus the capability files: `.claude/agents/` (specialized subagents) and
`.claude/skills/` (reusable workflows).

---

## 8. Agents vs. Skills — when to use which

| Reach for an **Agent** when… | Reach for a **Skill** when… |
|---|---|
| You need an isolated context / scoped tools | You have a repeatable procedure with set steps |
| Heavy work (deep search, full review) | You want to bundle scripts / reference docs |
| A constrained role (read-only reviewer) | You want it to auto-trigger by description |
| A different model for the job | You also want to run it as `/command` |

This project has both: agents `code-reviewer` + `api-tester`, skills
`add-endpoint` + `run-app`.

---

## 9. Demo flow for the presentation (suggested)

1. Show the folder tree — point out code vs. the `.claude/` layer.
2. Open `CLAUDE.md` — "this is loaded every session."
3. Open `.claude/skills/add-endpoint/SKILL.md` — explain frontmatter + progressive
   disclosure (the `reference/` file loads only when needed).
4. Open `.mcp.json` — "this is how Claude reaches external tools."
5. Show `.gitignore` — what's shared vs. private (`.env`, `settings.local.json`).
6. Run `uvicorn backend.main:app --reload`, open the browser, send a message.
7. (if a key is set) point out it's now talking to `claude-opus-4-8`.
