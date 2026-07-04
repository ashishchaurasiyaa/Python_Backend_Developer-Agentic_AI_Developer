# What · Why · How — Deep Explainer + Q&A Bank

Presenter prep for the **Workspace** bootcamp. For every concept: **What** it is,
**Why** it exists (the pain it removes), **How** to use it, and **❓ the questions
your audience will actually ask** — with crisp answers.

> Use this alongside `FACILITATOR_GUIDE.md` (timing/run-of-show). This file is the
> "go deep / handle hard questions" reference.

---

## 0. The Workspace (the umbrella idea)

**What:** A normal project repo *plus* a committed configuration layer that teaches
Claude Code how the project works — `CLAUDE.md`, `.claude/` (agents, skills,
settings, commands), and `.mcp.json`.

**Why:** Without it, every session you re-explain the project: "build with X",
"our style is Y", "the auth code is in Z". That's slow, inconsistent, and dies when
you close the terminal. The workspace makes that knowledge **persistent, shared, and
version-controlled** — a teammate clones the repo and instantly gets a Claude that
already knows the project.

**How:** Add the files (this repo is the template). Commit `.claude/`; keep secrets
out. New repo? Run `/init` to auto-generate `CLAUDE.md`.

❓ **Q: Isn't this just a big system prompt?**
A: No. A system prompt is one blob you resend. A workspace is *structured* and
*file-based*: memory loads up front, skills load only when relevant, agents run in
isolation, settings enforce rules. It's modular and version-controlled.

❓ **Q: Does it work outside the terminal?**
A: Yes — the same `.claude/` works in the CLI, the desktop/web app, and IDE
extensions.

❓ **Q: Will this slow Claude down / cost more tokens?**
A: No — that's the point of *progressive disclosure* (see §6). Only small metadata
is always loaded; the rest loads on demand.

---

## 1. CLAUDE.md — project memory

**What:** A markdown file (repo root) that Claude reads at the **start of every
session**. Holds overview, architecture, build/test commands, conventions, and a
list of capabilities.

**Why:** It removes repetition. You write "run with `uvicorn backend.main:app`" and
"4-space indent, secrets in .env" *once*, and Claude respects it forever — no
re-explaining, fewer wrong assumptions, consistent output across the team.

**How:** Keep it **under ~200 lines** and high-level. Long step-by-step procedures
do **not** go here — they go in a Skill. Generate a first draft with `/init`.

❓ **Q: CLAUDE.md vs a Skill — what's the difference?**
A: CLAUDE.md = *always loaded*, short, "what the project is." A Skill = *loaded only
when relevant*, can be long, "how to do a specific task."

❓ **Q: Why under 200 lines?**
A: The longer it is, the less the model adheres to any single line. Lean memory =
sharper focus. Overflow → push detail into skills or `.claude/rules/`.

❓ **Q: Is it committed?**
A: Yes — the whole team shares one source of truth.

---

## 2. .claude/settings.json — governance

**What:** JSON config for **permissions** (what Claude may run without asking),
**env** vars, and **hooks**. Committed and shared.

**Why:** Two pains. (1) Without an allow-list, Claude asks permission for every
command — annoying. (2) Without a deny-list, a bad instruction could read secrets or
run something destructive. `settings.json` is the guardrail: allow safe commands,
**deny** reading `.env`. Everyone on the team gets the same safety net.

**How:** `permissions.allow` (e.g. `Bash(uvicorn:*)`), `permissions.deny` (e.g.
`Read(./.env)`), `env` (e.g. `PYTHONUNBUFFERED`). Personal tweaks go in
`settings.local.json` (gitignored).

❓ **Q: Where do MY personal settings go?**
A: `.claude/settings.local.json` (gitignored) or your global `~/.claude/`.

❓ **Q: Precedence if they conflict?**
A: `managed > local > project (.claude/) > user (~/.claude/)`.

❓ **Q: Is guidance in CLAUDE.md the same as a permission?**
A: No. CLAUDE.md is *advice* (Claude tries to follow). Permissions/hooks are
*enforced* — hard rules. Put "must never" things in settings, not memory.

---

## 3. .gitignore — share vs. secret

**What:** The rule for what git tracks. Here: **commit** `.claude/`, `CLAUDE.md`,
`.mcp.json`, `.env.example`; **ignore** `.env`, `*.local.json`, caches.

**Why:** Two opposite needs. You *want* to share agents/skills/settings (team
benefit) — so `.claude/` is committed. You *must not* share secrets or personal
overrides — so `.env` and `settings.local.json` are ignored. `!.env.example` is a
clever bit: commit the *template* (so people know which vars to set) but never the
real values.

**How:** See this repo's `.gitignore`. Golden rule: **commit `.claude/`, keep `.env`
& `*.local` out.**

❓ **Q: Wait — we commit the `.claude/` folder?? Isn't that config private?**
A: Yes, commit it — that's the whole value. It's team knowledge, not secrets. Only
`.env` and `*.local.json` are private.

❓ **Q: I committed my key by mistake — now what?**
A: Removing it from the next commit isn't enough — it's in git history. **Rotate the
key** (revoke + create new), then scrub history if it was pushed. Prevention: never
put keys anywhere except `.env`.

---

## 4. Agents — specialist subagents

**What:** A markdown file (`.claude/agents/x.md`) defining a specialist Claude with
its **own fresh context window, its own tools, and its own model**. Frontmatter:
`name`, `description`, optional `tools`, `model`.

**Why:** Two pains. (1) Heavy work (deep search, full code review) floods your main
conversation with noise — an agent keeps that **isolated**. (2) You want a *bounded*
role: a reviewer that can read but not rewrite, on a cheaper model. Listing `tools`
**sandboxes** it; setting `model` controls cost.

**How:** Drop a `.md` in `.claude/agents/`. The `description` tells the main Claude
*when* to delegate. Omit `tools` → inherits all; list them → restricted.

❓ **Q: What if I don't list `tools`?**
A: It inherits every tool. Listing them is how you sandbox an agent (e.g. read-only).

❓ **Q: Which model should an agent use?**
A: Cheapest that does the job. `sonnet`/`haiku` for bounded tasks; `inherit` for
general work.

❓ **Q: Agent vs Skill?**
A: Agent = *who* does the work (isolated worker). Skill = *how* the work is done
(a procedure). They compose: a skill can run inside an agent.

❓ **Q: Can agents run in parallel?**
A: Yes — independent slices of work can run at once.

---

## 5. Skills — reusable workflows

**What:** A **folder** with a `SKILL.md` (+ optional `scripts/`, `reference/`).
Packages a repeatable procedure — "how we add an endpoint", "how we deploy".

**Why:** You do the same multi-step task again and again (analyze → build → test →
document) and re-type the instructions each time. A Skill captures it **once** →
consistent, faster, less prompting. Bundled scripts/docs travel with it.

**How:** `mkdir .claude/skills/<name>/` + a `SKILL.md` with `name` + a sharp
`description` (the description is the *trigger*). No install, no restart — Claude
auto-discovers it; also runnable as `/<name>`.

❓ **Q: Skill vs slash command?**
A: Same machinery now. A skill auto-triggers by description AND runs as
`/skill-name`. `.claude/commands/*.md` is the older single-file form (like
`/ship-check`).

❓ **Q: Can a skill run a script?**
A: Yes — bundle it (e.g. `run-app/scripts/start.sh`) and reference it from
`SKILL.md`.

❓ **Q: How is the `description` used?**
A: It's how Claude decides whether the skill is relevant. Be specific — say *what it
does AND when to use it*.

---

## 6. Progressive disclosure — why skills scale ⭐

**What:** Skills load context in **three levels**:
1. **Metadata** (name + description) — *always* in context.
2. **Body** (full `SKILL.md`) — loads **when the skill triggers**.
3. **Bundled files** (`reference/…`, scripts) — load **only when Claude opens them**.

**Why:** Context windows are finite and tokens cost money/speed. If every skill's
full text were always loaded, 50 skills would bury the model. Progressive disclosure
means you can ship **hundreds** of skills and huge reference docs while Claude pays
only for what it actually opens.

**How:** Write a tight `description` (always-on), keep the body focused, and push
long detail into `reference/` files you link from `SKILL.md`.

❓ **Q: So a 500-line reference doc costs nothing until used?**
A: Right — it's read with a file tool only when Claude needs it. Until then it's just
sitting on disk.

❓ **Q: This is the single most important idea — why?**
A: It's what makes the whole system *scale*. Memory + skills + tools could bloat
context; progressive disclosure keeps the always-loaded part tiny.

---

## 7. .mcp.json — connecting external tools (MCP)

**What:** Model Context Protocol config (repo root). Declares **MCP servers** —
standardized connectors to the outside world: filesystem, web fetch, a database,
GitHub, a browser.

**Why:** By itself Claude only sees the conversation. MCP is the **bridge** to live
systems — query a DB, fetch a URL, open a PR — through one standard protocol, so any
tool that implements MCP just plugs in. Committed in `.mcp.json` → the team shares
the same tools.

**How:** `claude mcp add fetch -s project -- uvx mcp-server-fetch` (or edit
`.mcp.json` by hand) → then `/mcp` to check status and authenticate. **Secrets go in
env vars — never commit tokens into `.mcp.json`.**

❓ **Q: Where do MCP credentials/tokens go?**
A: Env vars or your personal config — never in the committed `.mcp.json`.

❓ **Q: Project vs personal MCP servers?**
A: Project = `.mcp.json` (shared, committed). Personal = your `~/.claude.json`
(only you, all projects).

❓ **Q: How is MCP different from a tool the agent already has?**
A: Built-in tools (read/write/bash) act on your machine. MCP reaches *external*
systems through a standard protocol.

---

## 8. .env & the API key — app ↔ model link

**What:** `.env` holds secrets (chiefly `ANTHROPIC_API_KEY`) that the **app's
backend** uses to call the Claude API. Loaded by `python-dotenv`. Gitignored.

**Why:** Secrets must never be hardcoded in source or committed. `.env` keeps them on
your machine, out of git, and out of the codebase. `.env.example` is the committed
*template* (placeholders only) so others know which variables to set.

**How:** `cp .env.example .env` → put your **real** key in `.env` →
`uvicorn … --reload`. The SDK reads `ANTHROPIC_API_KEY` from the environment
automatically — you never pass it in code.

❓ **Q: Key in `.env.example` vs `.env`?**
A: `.env.example` = committed template, **placeholders only**. `.env` = your real
key, **gitignored**. Real key NEVER in `.env.example`.

❓ **Q: Is this the same key Claude Code uses?**
A: Separate concern. This key is for *the demo app* to call the API. Claude Code's
own auth is its login. Don't confuse the two.

❓ **Q: App runs without a key?**
A: Yes — this demo is placeholder-safe (demo mode). Real replies need the key + the
`anthropic` package.

---

## 9. Scopes & precedence (one slide of truth)

- **Project scope** = `.claude/` in the repo. Committed. The team shares it.
- **User scope** = `~/.claude/` in your home dir. Personal. Applies to all your
  projects.
- **Precedence on conflict:** `managed > CLI flags > project (.claude/) > user (~/.claude/)`.
  First match by name wins.

❓ **Q: I have a global agent AND a project agent with the same name — which runs?**
A: Project wins over user. (And managed/CLI win over project.)

---

## 10. The tough questions (be ready)

- **"Why not just use ChatGPT/Copilot?"** → Those work at the line/file level. A
  workspace gives Claude *project-level* awareness, scoped tools, and the ability to
  run commands — plus it's reproducible and shared via git.
- **"Is my code/data sent to Anthropic?"** → The model needs the context you give it
  to do the work; follow your org's data policy, use `permissions.deny` to keep
  sensitive paths out, and never put secrets in prompts. (Point to Anthropic's data
  usage terms for specifics.)
- **"What if Claude does something destructive?"** → Permissions + hooks gate risky
  actions; default mode asks before edits; you review diffs. That's what
  `settings.json` is for.
- **"Does any of this lock me in?"** → It's just markdown + JSON files in your repo.
  Delete `.claude/` and you have a plain project again.
- **"How do I keep CLAUDE.md from going stale?"** → Update it on big changes; record
  lessons learned; re-run `/init` after major refactors.
