# Friday Presentation — AI Workspace (+ AI Workflow alt)

Everything for the 20–30 min technical talk. **Primary topic: "Building an AI Workspace"** (Agents · MCP · Skills · RAG). A second deck on the broader "AI Workflow" stack is included as an alternative.

## ⭐ Primary deck — Building an AI Workspace
| File | Use |
|---|---|
| **`AI_Workspace_Presentation.pptx`** / **`.pdf`** | The deck — 16 slides. Agents + MCP + Skills + RAG, with hands-on code + 2 demos. |
| **`QA_PREP.md`** | **Question bank with answers** — manager (business) + team (technical "how to build": workspace, MCP, skills, RAG) questions, ready-to-speak, grounded in this repo. **Read this most.** |
| **`demo_workspace.py`** | **Runnable live mini-workspace** — Agent + Tools + Skills + RAG in one file. No key, no deps. `python demo_workspace.py`. |
| **`LIVE_WORKSPACE_DEMO.md`** | How to demo a workspace live ("karke dikhana") — 3 options + run-script + fallback. |
| **`DEMO_CHEATSHEET.md`** | One-page quick reference — keep open in a terminal tab during the talk. |
| `build/workspace_deck.js` | Source that generates the workspace .pptx (pptxgenjs). |

**Flow:** What is an AI Workspace → 4 pillars → environment setup → Agent (brain) → MCP (connectors) → MCP build → Skills/Tools → RAG → assembled architecture → 🔴 Demo 1 → 🔴 Demo 2 → guardrails/observability → build roadmap → right-size guide → takeaways.

## Alternative deck — The End-to-End AI Workflow
| File | Use |
|---|---|
| `AI_Workflow_Presentation.pptx` / `.pdf` | 16 slides — the broader 8-layer AI stack (LLM → Production). |
| `SPEAKER_NOTES.md` | Per-slide talking points + timing for the **AI Workflow** deck. |
| `build/deck.js` | Source for the workflow .pptx. |

> Note: `SPEAKER_NOTES.md` matches the **AI Workflow** deck’s slide order. `QA_PREP.md` and `DEMO_CHEATSHEET.md` apply to **both** decks.

## The two live demos (both from this repo, both QA’d)
1. **ReAct agent from scratch** — `../Level6_Agent_Patterns/04_react_pattern_practical.py` (Agent + Skills; runs with no key)
2. **Multi-agent code review** — `../Projects/project3_multiagent_code_review_starter/main.py` (all 4 pillars; runs with no key)

## Regenerate a deck after editing its `build/*.js`
```bash
cd build && node workspace_deck.js     # → ../AI_Workspace_Presentation.pptx
#        or  node deck.js               # → ../AI_Workflow_Presentation.pptx
# re-render to PDF + preview images:
cd .. && /Applications/LibreOffice.app/Contents/MacOS/soffice --headless --convert-to pdf AI_Workspace_Presentation.pptx
pdftoppm -jpeg -r 130 AI_Workspace_Presentation.pdf ws
```
