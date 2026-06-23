# ⚡ Demo Cheat-Sheet — keep this open in a terminal tab

## Setup (once, before the talk)
```bash
cd /Users/youngmanindia/Documents/PythonRevision/Agentic_AI
source ../.venv/bin/activate
# Optional, for LIVE output (else dry-run still works):
export OPENAI_API_KEY=sk-...
```

---

## ▶︎ DEMO 1 — ReAct from scratch  (slide 11)
```bash
python Level6_Agent_Patterns/04_react_pattern_practical.py
```
**Watch:** Iteration blocks → Thought/Action/Observation → 2 tools chained → Section 4 prints **Status · Cost · Iterations · Tools used**.
**One line:** *"We never told it which tool — it decided."*
**No key:** runs anyway → prints `[NO_API_KEY]` / `Status: no_api_key`; walk the slide-10 transcript + show `run()` in the editor.

---

## ▶︎ DEMO 2 — Multi-agent code review  (slide 15)
```bash
python Projects/project3_multiagent_code_review_starter/main.py
```
**Always works (no key needed)** — prints the multi-agent flow + cost.
**Watch:** Security=Opus, Perf=Sonnet, Style=Haiku run in parallel → synthesize → critical? human → post + Slack(MCP).
**Punchline:** *"≈ $0.10 / PR — tiering models is ~80× cheaper than all-Opus."*

---

## 🚑 If a demo breaks live
1. Don't debug on stage.
2. Flip back to the demo's slide (11 or 15).
3. Narrate the diagram / transcript, then show the source file in the editor.
4. Move on — the talk never depends on the network.
