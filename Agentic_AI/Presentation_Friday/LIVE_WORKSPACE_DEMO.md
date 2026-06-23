# 🟢 Live Workspace Demo — "karke dikhana"

Agar team/manager bole *"actually chala ke dikhao"*, ye 3 options hain. **Option A bulletproof hai** — no key, no internet, ek command. Usi ko default rakho.

---

## ⭐ Option A — Runnable mini-workspace (recommended)

**Ek hi file mein Agent + Tools + Skills + RAG live chalte hain** — workspace ek real task pe kaam karke citation ke saath jawab deta hai.

```bash
cd /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/Presentation_Friday
python demo_workspace.py
```

**Screen pe ye dikhega (har task pe):**
`💬 Task → 🤔 Thought → 🔧 Action → 👁 Observe → ✅ Answer (with source)`

**Bolne ka script (~2 min):**
1. *"Ye ek chhota AI workspace hai — Agent, kuch tools/skills, aur company docs ka RAG, sab ek saath."*
2. Pehla task (refund) chalte waqt: *"Dekho — pehle ye **docs search** karta hai (RAG), phir purchase date pe **days_between tool** chalata hai (skill), phir dono ko jod ke jawab deta hai. Yeh **multi-step** kaam hai, single answer nahi."* → **10 days left** + **citation DOC-101**.
3. Teesra/unknown task: *"Aur jo docs mein nahi hai, ye **bana ke nahi bolta** — 'couldn't find' kehta hai. Yahi grounding + no-hallucination ka faayda hai."*

**Apna sawaal live poochna ho:**
```bash
python demo_workspace.py "What are the support hours?"
```

**Kya highlight karna hai (4 pillars, point karke):**
- **Agent** — Thought/Action/Observe loop
- **MCP** — tools MCP-style schema (name/description/params) mein defined
- **Skills** — `search_docs`, `days_between`, `create_ticket` registry mein
- **RAG** — `KNOWLEDGE_BASE` ke 4 docs pe real retrieval + citations

**No key chahiye** — MOCK MODE deterministic hai (kabhi fail nahi). Key set ho to top pe `[agent mode: LLM]` dikhega.
Customize: file ke top pe `KNOWLEDGE_BASE` mein apni team ke 2-3 real policy lines daal do → demo aur relatable.

---

## Option B — Repo ke 2 ready demos (agar "real code" dikhana ho)

```bash
cd /Users/youngmanindia/Documents/PythonRevision/Agentic_AI
python Level6_Agent_Patterns/04_react_pattern_practical.py            # Agent + tools (ReAct from scratch)
python Projects/project3_multiagent_code_review_starter/main.py      # multi-agent workspace (architecture + cost)
```
Dono no-key safe. Detail `DEMO_CHEATSHEET.md` mein.

---

## Option C — Claude Code / Desktop ko hi workspace ki tarah dikhao

Agar **real product** dikhana ho (sabse impressive, par network/accounts pe depend):
- **MCP connectors** — host ka config kholo, ek connected MCP server dikhao, ek tool live call karwao.
- **Skills** — ek skill invoke karke dikhao (instructions + script on-demand load hote hain).
- **Agent + your data** — apne repo pe ek multi-step task do (e.g. "is folder ke X find karke summarize karo") aur use tools chalata hua dikhao.

**Risk-control:** pehle se ek baar rehearse karo, ek **safe/non-sensitive** repo ya folder use karo, aur koi bhi external link **bina verify** mat khulwao. Network gir jaaye to turant **Option A** pe switch.

---

## 🚑 Golden rule
Live kuch bhi atke → seedha **Option A** chalao (`python demo_workspace.py`). Wo hamesha chalega aur teeno pillars ek saath dikha deta hai.
