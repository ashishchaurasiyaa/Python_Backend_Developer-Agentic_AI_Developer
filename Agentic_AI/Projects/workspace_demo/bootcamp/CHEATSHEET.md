# Claude Code Workspace — Cheat Sheet (1 page)

## The mental model
**Workspace = your code + a committed `.claude/` config layer.**
Your code is untouched; the layer teaches Claude the project.

## The files that matter
| File | Committed? | What it does |
|---|---|---|
| `CLAUDE.md` | ✅ | Project memory — loaded every session. Keep < 200 lines. |
| `.claude/settings.json` | ✅ | Permissions, env, hooks (team-shared). |
| `.claude/settings.local.json` | ❌ | Your personal overrides. |
| `.claude/agents/*.md` | ✅ | Subagents — one file each. |
| `.claude/skills/<name>/SKILL.md` | ✅ | Reusable workflows — a folder each. |
| `.claude/commands/*.md` | ✅ | Slash commands (`/ship-check`). |
| `.mcp.json` | ✅ | External tool connections. |
| `.env` | ❌ | Secrets (`ANTHROPIC_API_KEY`). |
| `.env.example` | ✅ | Template for env vars. |

**Scope precedence:** managed > local > project (`.claude/`) > user (`~/.claude/`).

## Commit vs. ignore
```gitignore
.env
.env.*
!.env.example
.claude/settings.local.json
```
Commit `.claude/`. Ignore secrets + `*.local.json` + caches.

## Agent file (`.claude/agents/x.md`)
```markdown
---
name: code-reviewer
description: When to delegate to this agent.   # required
tools: Read, Grep, Bash        # optional — omit = inherit all
model: sonnet                  # optional
---
System prompt for the agent…
```

## Skill (`.claude/skills/x/SKILL.md`)
```markdown
---
name: My skill
description: What it does AND when to use it.   # the trigger
allowed-tools: Bash(npm *)     # optional
---
Steps… (bundle scripts/ and reference/ alongside)
```
**Progressive disclosure:** name+description always loaded → body on trigger →
bundled files on demand.

## Add an MCP server
```bash
claude mcp add fetch -s project -- uvx mcp-server-fetch
```
…or edit `.mcp.json`. Then `/mcp` to check status. Never commit tokens.

## Run this demo app
```bash
pip install -r requirements.txt
uvicorn backend.main:app --reload      # → http://127.0.0.1:8000
```
No key → demo mode. Add key to `.env` (+ `pip install anthropic`) for real replies.

## Handy commands inside Claude Code
`/init` — generate CLAUDE.md · `/mcp` — manage MCP · `/agents` — manage agents ·
`/<skill-name>` — run a skill · `/ship-check` — this project's checklist

## Agents vs Skills vs MCP
- **Agent** → isolated context, scoped tools, heavy/bounded work.
- **Skill** → repeatable procedure, bundled scripts/docs, auto-triggers.
- **MCP** → connect external systems (web, DB, GitHub, browser).
