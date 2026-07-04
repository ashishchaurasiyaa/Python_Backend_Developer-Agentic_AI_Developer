# Hands-On Labs — Claude Code Workspace

Work on top of the `workspace_demo` project. Lab 1 fits the live session
(~5 min). Labs 2–4 are take-home extensions.

> **Setup (once):**
> ```bash
> cd workspace_demo
> pip install -r requirements.txt
> ```

---

## Lab 1 — Create your first Skill  ⭐ (do this in the session, ~5 min)

**Goal:** Add a working skill with zero install or restart.

1. Make the skill folder + file:
   ```bash
   mkdir -p .claude/skills/greet
   ```
2. Create `.claude/skills/greet/SKILL.md` with this content:
   ```markdown
   ---
   name: Greet the user
   description: Write a short, friendly welcome message for a new teammate joining this project. Use when asked to greet, welcome, or onboard someone.
   ---

   # Greet a new teammate

   1. Welcome them by name in one warm sentence.
   2. Point them to `README.md` for setup and `WORKSPACE_GUIDE.md` for the deep dive.
   3. Mention they can run the app with `uvicorn backend.main:app --reload`.
   Keep it to 3–4 sentences.
   ```
3. **Verify:** in Claude Code, run `/greet`, or ask *"welcome our new teammate Sara."*
   If Claude uses the skill, it registered.

✅ **You just shipped a skill.** No build step, no restart — Claude auto-discovers
the folder.

---

## Lab 2 — Add a bundled reference file (progressive disclosure)

**Goal:** See how a skill loads extra detail only when needed.

1. Add `.claude/skills/greet/reference/tone.md`:
   ```markdown
   # Tone guide (loaded on demand)
   - Warm but not cheesy. No exclamation overload.
   - Indian-English friendly; avoid slang.
   - Never promise features that don't exist.
   ```
2. In `SKILL.md`, add a line: `See reference/tone.md for the tone guide.`
3. **Observe:** `tone.md` is *not* in context until Claude opens it. That's
   progressive disclosure — the body loads on trigger, bundled files on demand.

---

## Lab 3 — Add an API endpoint using the project's own skill

**Goal:** Use the existing `add-endpoint` skill to extend the app.

1. In Claude Code, ask: *"Add a `/api/echo` endpoint that returns the message
   uppercased, following the add-endpoint skill."*
2. Confirm Claude:
   - added a Pydantic model + `@app.post("/api/echo")` **above** the `app.mount(...)` line,
   - kept logic typed and `async`.
3. **Test it:**
   ```bash
   curl -s -X POST localhost:8000/api/echo \
     -H 'Content-Type: application/json' -d '{"message":"hi"}'
   ```
4. Then run `/ship-check` (the slash command) to review the diff.

---

## Lab 4 — Add an MCP server

**Goal:** Connect an external tool.

1. Add a server (CLI way):
   ```bash
   claude mcp add fetch -s project -- uvx mcp-server-fetch
   ```
   …or add it by hand to `.mcp.json`.
2. Run `/mcp` in Claude Code to confirm it connects.
3. Ask Claude to fetch and summarize a public URL — it now has the `fetch` tool.

> **Rule:** never commit secrets/tokens into `.mcp.json`. Use env vars.

---

## Stretch goals

- Write a new **agent** (`.claude/agents/doc-writer.md`) scoped to `Read, Write`
  that keeps `README.md` in sync.
- Add a `permissions.deny` rule and watch Claude ask before a blocked action.
- Create a `settings.local.json` (gitignored) that overrides the model while you
  develop, and confirm it doesn't show in `git status`.
