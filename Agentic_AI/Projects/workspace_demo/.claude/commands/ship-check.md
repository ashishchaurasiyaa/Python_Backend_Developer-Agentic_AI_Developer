---
description: Pre-ship checklist — review the diff, run the API smoke test, and report go / no-go.
---

Run the pre-ship checklist for this project:

1. Show what changed: `git status` and `git diff`.
2. Delegate a review to the `code-reviewer` agent and summarize blockers.
3. Make sure the server runs, then delegate to the `api-tester` agent.
4. Confirm no secrets were added (grep the diff for `sk-ant`, keys, tokens).
5. Report a clear **GO** or **NO-GO** with the top reasons.

Stop after reporting — do not commit or push unless asked.
