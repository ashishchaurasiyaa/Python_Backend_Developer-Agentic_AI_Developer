# Facilitator Guide — Building a Claude Code Workspace

**Topic:** Workspace — structuring an end-to-end project (codebase + Agents + Skills + MCP)
**Length:** 40 min (fits a 30–45 min slot — trim points marked ✂️)
**Audience:** developers + bootcamp students (some technical, some learning)
**Format:** talk + live demo + one short hands-on lab
**Demo repo:** `workspace_demo/` (this project)

> This is your run-of-show. Each segment has: ⏱ time · 🎯 goal · 🗣 what to say
> · 🖥 what to show/do · ❓ likely questions. Slide numbers refer to the deck
> `bootcamp/Workspace_Bootcamp.pptx`.

---

## 0. Pre-flight checklist (do this 10 min BEFORE you start)

- [ ] Terminal open at `workspace_demo/`, font size bumped up (⌘+ a few times).
- [ ] `pip install -r requirements.txt` already run (so the live demo is instant).
- [ ] (Optional, for the "real" reply) `pip install anthropic` + `cp .env.example .env`
      and paste a key. If you skip this, the app runs in **demo mode** — that's fine
      and totally safe. Decide now so you can say the right thing on stage.
- [ ] Browser open to a blank tab (you'll point it at `localhost:8000`).
- [ ] Editor open with the folder tree visible in the sidebar.
- [ ] Slides open in presenter view. Cheat sheet (`CHEATSHEET.md`) printed/shared.
- [ ] Run the server once before the room fills, then Ctrl+C — confirms it boots.

**One-liner to have ready in your clipboard:**
```bash
uvicorn backend.main:app --reload
```

---

## 1. Welcome & the hook  ⏱ 3 min  · Slides 1–2

🎯 **Goal:** Get everyone on the same page about *what* a workspace is and *why* they should care.

🗣 **Say:**
> "Most people use Claude Code as a smart autocomplete. Today you'll learn to set
> it up as a *project teammate* — one that knows your conventions, has its own
> specialist agents, reusable skills, and connections to your tools. The secret
> isn't a prompt. It's how you structure the project. That structure is the
> **workspace**, and in 40 minutes you'll be able to build one."

> "Quick promise — by the end you'll know: the exact files, what to commit vs.
> keep secret, and how to add Skills and MCP servers. We'll build it on a real
> running app."

🖥 **Show:** Slide 2 (agenda). Read the 4 outcomes out loud.

❓ *"Do I need an API key?"* → "Not for today's demo — it runs in demo mode. You
only need a key when you want the app to actually call Claude."

---

## 2. The mental model: code + the `.claude/` layer  ⏱ 4 min  · Slide 3

🎯 **Goal:** The single most important idea — your code is untouched; the workspace is a thin config layer on top.

🗣 **Say:**
> "Here's the whole idea in one picture. Your codebase — `backend/`, `frontend/` —
> doesn't change. A workspace *adds a layer*: a `CLAUDE.md` memory file, a
> `.claude/` folder with agents and skills, and a `.mcp.json` for external tools.
> That layer is version-controlled and shared with your team. So when a new dev
> clones the repo, they don't just get the code — they get a Claude that already
> knows how the project works."

🖥 **Show:** Slide 3 — the stacked diagram (codebase at the bottom, config layers on top).

💡 **Analogy to drop:** "Think of `.claude/` as the onboarding handbook + the team
of specialists, checked into git right next to the code."

---

## 3. Meet the demo project  ⏱ 2 min  · Slide 4

🎯 **Goal:** Orient them to the app we'll use so the file tour has context.

🗣 **Say:**
> "We'll use a tiny but real app: an **AI chat assistant**. Python FastAPI backend,
> plain HTML/CSS/JS frontend — no framework, nothing fancy. The point isn't the
> app; it's how the workspace wraps around it."

🖥 **Show:** Slide 4, then briefly the editor sidebar — point at `backend/` and `frontend/`.

---

## 4. The folder map — live tour  ⏱ 5 min  · Slide 5

🎯 **Goal:** Give them the map. This is the spine of the whole talk.

🖥 **Show:** Slide 5 (full tree) → then the **real folder tree in the editor**.
Walk top to bottom, ~20 seconds each:

- `backend/`, `frontend/` — "the code."
- `CLAUDE.md` — "memory, loaded every session."
- `.claude/settings.json` — "permissions + env."
- `.claude/agents/` — "specialist subagents."
- `.claude/skills/` — "reusable workflows."
- `.claude/commands/` — "slash commands like `/ship-check`."
- `.mcp.json` — "external tool connections."
- `.gitignore`, `.env.example` — "what's shared vs. secret."

🗣 **Transition:** "Let's open the four files that actually wire this up to Claude."

✂️ **30-min trim:** Spend 3 min here, skip opening every file individually — just
point at them in the tree.

---

## 5. CLAUDE.md — project memory  ⏱ 3 min  · Slide 6

🎯 **Goal:** Understand the always-loaded instruction file.

🖥 **Show:** Open `CLAUDE.md` in the editor.

🗣 **Say:**
> "This is the project's memory. Claude reads it at the start of *every* session —
> you never have to re-explain the build command or your conventions. Notice the
> sections: Overview, Architecture, Commands, Conventions, Capabilities. Keep it
> **under 200 lines** — if it gets long, the model pays less attention to it.
> Long procedures don't go here; they go into a Skill."

> "Pro tip: you don't have to write this by hand. Run `/init` in Claude Code and
> it scans the repo and drafts a `CLAUDE.md` for you."

❓ *"Difference between CLAUDE.md and a skill?"* → "CLAUDE.md is always on, short,
high-level. A skill is loaded only when relevant, and can be long and detailed.
More on that in two minutes."

---

## 6. settings.json + .gitignore — governance & sharing  ⏱ 4 min  · Slide 7

🎯 **Goal:** What Claude is allowed to do, and what's committed vs. private.

🖥 **Show:** Open `.claude/settings.json`, then `.gitignore`.

🗣 **Say (settings.json):**
> "This is governance. `permissions.allow` lets Claude run `uvicorn`, `pip`, `curl`
> without asking each time. `permissions.deny` blocks reading `.env` — so even if
> you ask, it won't leak your key. `env` sets environment variables. This file is
> **committed** — the whole team gets the same guardrails."

🗣 **Say (.gitignore — the commit/secret split):**
> "Here's the rule everyone gets wrong: **`.claude/` IS committed.** You *want* the
> team to share agents, skills, and settings. The only things you keep out of git
> are: `.env` (your secret key), `settings.local.json` (your *personal* overrides),
> and caches. Notice `!.env.example` — we commit the *template* so people know
> which variables to set, just never the real values."

💡 **Whiteboard/point:** committed = `CLAUDE.md`, `settings.json`, `agents/`,
`skills/`, `.mcp.json`, `.env.example`. Ignored = `.env`, `settings.local.json`.

❓ *"Where do MY personal settings go?"* → "`settings.local.json` (gitignored), or
your global `~/.claude/`. Precedence: managed > local > project > user."

---

## 7. Agents — specialist subagents  ⏱ 3 min  · Slide 8

🎯 **Goal:** What a subagent is and why isolation matters.

🖥 **Show:** Open `.claude/agents/code-reviewer.md`.

🗣 **Say:**
> "An agent is a *specialist* Claude with its own fresh context, its own tools,
> and its own model. Look at the frontmatter: `name`, `description` — that
> description tells the main Claude *when* to hand work to this agent. `tools:
> Read, Grep, Glob, Bash` — we scoped it to read-only-ish tools, so a reviewer
> can't accidentally rewrite your files. `model: sonnet` — cheaper model for a
> bounded job. The body is the agent's system prompt."

> "We've got two: `code-reviewer` and `api-tester`. One file per agent. That's it."

❓ *"What if I don't list `tools`?"* → "It inherits all tools. Listing them is how
you sandbox an agent."

---

## 8. Skills + progressive disclosure  ⏱ 5 min  · Slide 9  ⭐ (most important segment)

🎯 **Goal:** Skills as reusable workflows + the load model that makes them scale.

🖥 **Show:** Open `.claude/skills/add-endpoint/SKILL.md`, then expand the folder to
show `reference/conventions.md` and the sibling `run-app/scripts/start.sh`.

🗣 **Say:**
> "A Skill is a **folder with a `SKILL.md`**. It packages a repeatable workflow —
> 'how we add an endpoint here', 'how we run the app' — so you define it once and
> reuse it forever. Frontmatter `name` + `description`; the description is the
> trigger. It can bundle scripts and reference docs."

> "Now the killer idea — **progressive disclosure**, three levels:
> 1. Only the `name` + `description` sit in context all the time.
> 2. The full `SKILL.md` body loads **when the skill triggers**.
> 3. Bundled files like `reference/conventions.md` load **only when Claude opens
>    them**.
> That's why you can ship a hundred skills and huge reference docs without
> bloating the context window. Claude pays only for what it actually opens."

🖥 **Optional show:** open `reference/conventions.md` and say "this isn't in context
right now — it loads only when the skill points Claude here."

❓ *"Skill vs. slash command?"* → "Same machinery now. A skill auto-triggers by
description AND can be run as `/skill-name`. Commands in `.claude/commands/` are
the older single-file form — like our `/ship-check`."

---

## 9. MCP — connecting external tools  ⏱ 3 min  · Slide 10

🎯 **Goal:** What MCP is and exactly how to add a server.

🖥 **Show:** Open `.mcp.json`.

🗣 **Say:**
> "MCP — Model Context Protocol — is how Claude reaches the *outside world*: a
> database, the web, GitHub, a browser. Project servers live in `.mcp.json` at the
> repo root, committed so the team shares them. We've wired two: `filesystem` and
> `fetch`."

> "Two ways to add one. Easiest is the CLI:
> `claude mcp add fetch -- uvx mcp-server-fetch` (add `-s project` to write it into
> this file for the team). Or edit `.mcp.json` by hand. Then run `/mcp` inside
> Claude Code to see status and authenticate. **Never** put tokens in this file —
> use env vars."

❓ *"Where do MCP secrets go?"* → "Env vars or your personal config — never
committed into `.mcp.json`."

---

## 10. LIVE DEMO — run the app  ⏱ 5 min  · Slide 12

🎯 **Goal:** Prove it's a real, running thing — and show Claude *using* the workspace.

🖥 **Do (narrate each step):**
```bash
uvicorn backend.main:app --reload
```
1. Open `http://127.0.0.1:8000` → the chat UI loads.
2. Point at the status pill — "demo mode" (or "live · claude-opus-4-8" if you set a key).
3. Type "hello" → show the reply.
4. (If time) flip to Claude Code and say: *"add a `/api/echo` endpoint"* — point out
   it would use the `add-endpoint` skill. Or just **invoke the `code-reviewer`
   agent** on the current diff to show an agent running.

🗣 **Say:**
> "Notice I didn't explain the project to Claude — `CLAUDE.md` already did. I didn't
> grant permissions one by one — `settings.json` did. That's the workspace paying
> off."

🧯 **If the demo breaks:**
- Port busy → `--port 8001` and open that.
- Module error → `pip install -r requirements.txt` (you did this pre-flight, right?).
- Worst case → you already have the curl output in `CHEATSHEET.md`; show that and move on. Never debug live for more than 30 seconds.

---

## 11. HANDS-ON — your turn: add a Skill  ⏱ 5 min  · Slide 13  (see LAB.md)

🎯 **Goal:** Everyone creates a working skill — the muscle memory that sticks.

🖥 **Do:** Walk them through **Lab 1** in `LAB.md` (create `.claude/skills/greet/SKILL.md`).
Give them 3 minutes heads-down, then do it on screen so stragglers catch up.

🗣 **Say:**
> "Make a folder `.claude/skills/greet/`, drop in a `SKILL.md` with a name and a
> one-line description. That's a working skill. No install, no restart. Go."

✂️ **30-min trim:** Skip the heads-down time — just demo Lab 1 on screen (2 min)
and point them to `LAB.md` to do later.

❓ *"Did it work?"* → "Run `/greet` in Claude Code, or just ask something that
matches the description. If Claude offers it, it registered."

---

## 12. Recap + Q&A  ⏱ 3 min  · Slides 14–15

🎯 **Goal:** Cement the takeaways and hand them the cheat sheet.

🗣 **Say (the 5 takeaways):**
> 1. A workspace = your code + a committed `.claude/` config layer.
> 2. `CLAUDE.md` is memory (always on, keep it lean).
> 3. **Agents** isolate; **Skills** package; **MCP** connects.
> 4. Progressive disclosure is why it scales — pay only for what's opened.
> 5. Commit `.claude/`; keep `.env` and `settings.local.json` out of git.

🖥 **Show:** Slide 14, then point to `CHEATSHEET.md` — "everything's on one page,
including how to add a skill and an MCP server."

**Q&A bank (have answers ready):**
- *"Project vs. user scope?"* → Project `.claude/` = team, committed. User `~/.claude/` = you, all projects. Project wins on conflict.
- *"Does this work outside the terminal?"* → Same `.claude/` works in the CLI, the desktop/web app, and IDE extensions.
- *"How is this different from a system prompt?"* → It's structured, file-based, version-controlled, and loads on demand — not one big blob.
- *"Can a skill run a script?"* → Yes — bundle it (like `run-app/scripts/start.sh`) and reference it from `SKILL.md`.
- *"What model should agents use?"* → Cheapest that does the job; `sonnet`/`haiku` for bounded tasks, inherit for general.

---

## Timing summary

| # | Segment | Min | Cumulative |
|---|---|---|---|
| 1 | Welcome & hook | 3 | 3 |
| 2 | Mental model | 4 | 7 |
| 3 | Meet the project | 2 | 9 |
| 4 | Folder map tour | 5 | 14 |
| 5 | CLAUDE.md | 3 | 17 |
| 6 | settings + gitignore | 4 | 21 |
| 7 | Agents | 3 | 24 |
| 8 | Skills + progressive disclosure ⭐ | 5 | 29 |
| 9 | MCP | 3 | 32 |
| 10 | Live demo | 5 | 37 |
| 11 | Hands-on lab | 5 | 42 |
| 12 | Recap + Q&A | 3 | 45 |

**Need 30 min?** Cut #11 (hands-on) to a 2-min screen demo and tighten #4 → ~32 min + Q&A.
