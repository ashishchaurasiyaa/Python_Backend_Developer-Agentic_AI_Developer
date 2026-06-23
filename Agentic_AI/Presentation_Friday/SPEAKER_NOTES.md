# 🎤 Speaker Run-Sheet — "From Prompt to Production: The End-to-End AI Workflow"

**Audience:** technical team · **Length:** 20–30 min · **Deck:** `AI_Workflow_Presentation.pptx` (16 slides)
**2 live demos** from this repo. Full commands + fallbacks below.

> Talking points English mein hain (taaki seedha bol sako). Jahan helpful hai, **🗣 cue** mein Hinglish delivery hint di hai. Har slide ~1–1.5 min — demos ke saath total ~25 min.

---

## ⏱ Timing at a glance

| Block | Slides | Time |
|---|---|---|
| Hook + the map | 1–3 | 4 min |
| The stack, layer by layer | 4–8 | 7 min |
| Workflows vs Agents + ReAct | 9–10 | 3 min |
| **Demo 1 — ReAct from scratch** | 11 | 4 min |
| Frameworks + Production | 12–13 | 3 min |
| Reference architecture | 14 | 2 min |
| **Demo 2 — Multi-agent review** | 15 | 3 min |
| Close + Q&A | 16 | 3 min |

If running short: trim slides 12–13 to 1 line each, and keep Demo 1 only.

---

## ✅ Pre-flight checklist (do this 10 min before)

```bash
cd /Users/youngmanindia/Documents/PythonRevision/Agentic_AI
source ../.venv/bin/activate          # repo venv is at the project root
python -c "import openai, dotenv; print('deps ok')"
echo $OPENAI_API_KEY | head -c 6      # should print 'sk-...' if a live demo is planned
```

- [ ] Terminal font size **18pt+** (back row must read it).
- [ ] Dark terminal theme (matches the deck).
- [ ] Decide: **live with API key**, or **dry-run (no key)**. Both work — see each demo.
- [ ] Open the two demo files in your editor as backup: `04_react_pattern_practical.py`, `project3.../main.py`.
- [ ] Slides 11 & 15 are the demo anchors — keep them on screen while you switch to the terminal.

---

## Slide-by-slide

### 1 — Title
**Say:** "Today isn't about one clever prompt. It's about the *workflow* around the model — how a request goes from a single LLM call all the way to an autonomous, multi-agent system. We'll climb that stack and run two of the layers live."
**🗣 cue:** Loop chip (Thought → Action → Observation) pe haath rakh ke bolo — "yeh chhota sa loop hi har agent ka dil hai, isko hum live banayenge."

### 2 — A chatbot answers. An agent acts.
**Say:** "Two years ago an LLM was a text box: one prompt, one answer, no memory, can't touch the world. Today the same model sits inside a loop — it reasons over multiple steps, retrieves your data, calls tools and other agents, and it's observable and guardrailed. The model barely changed. What changed is everything *around* it."
**🗣 cue:** Left card = "pehle", right card = "ab". Emphasis: "skill ab prompt likhna nahi, system design karna hai."

### 3 — The workflow, in 8 layers
**Say:** "Here's the whole talk on one slide. Eight layers. 1–3 are the foundation — the model, how you prompt it, how you call it like any API. 4 and 6 (amber) are the agentic core — tools and agent patterns — and that's what we'll demo. 5 is RAG. 7–8 are frameworks and production. We climb bottom to top."
**🗣 cue:** Amber waale do (Tool Use, Agent Patterns) pe ungli rakho — "yeh do = agentic heart, baaki sab inko support karta hai."

### 4 — The model + how you talk to it (Layers 1–2)
**Say:** "Layer 1: an LLM is a next-token predictor. Not a database, not a reasoner — a very good autocomplete. It's stochastic, it has no memory between calls, and it will be confidently wrong. So engineer it like an unreliable function. Layer 2 is how you constrain it: a system prompt is role + rules + an output *contract*. Force structured output and validate it — don't hope, parse."
**🗣 cue:** Code chip dikhao — "`temperature=0` + a typed response = same shape har baar."

### 5 — Same model, real engineering (Layer 3)
**Say:** "The model is the easy part. Shipping it is a distributed-systems problem: stream tokens so it feels instant, fan out calls async for throughput, retry with backoff because rate limits *will* hit, and meter cost per request — tokens are money. A demo ignores all four. Production lives or dies on them."

### 6 — Tool use: the LLM acts (Layer 4)
**Say:** "This is where 'agentic' begins. You give the model a menu of functions — name, schema, when-to-use. It picks one and fills the arguments; *you* run the code and feed the result back; it decides the next step. That loop on the right — decide, execute, observe, repeat — is the seed of every agent we'll build."
**🗣 cue:** "Tool description ki quality = agent ki reliability. Inhe documentation ki tarah likho."

### 7 — RAG: ground the model in truth (Layer 5)
**Say:** "The model doesn't know your docs or last week's release. RAG fixes that: chunk your data, embed it to vectors, retrieve the relevant bits with hybrid search, rerank for precision, then generate with citations. The quality levers are all in retrieval — and you *measure* it with RAGAS, not vibes."

### 8 — Agent design patterns (Layer 6)
**Say:** "Six reusable shapes. ReAct — reason/act/observe in a loop, the default. Plan-and-Execute — plan first, then run. Reflection — critique and revise. Multi-agent — a supervisor delegates to specialists. Routing — classify, then branch. Human-in-the-loop — pause for approval. Real systems mix two or three. The two marked DEMO are what we'll run."

### 9 — Workflows vs. Agents
**Say:** "The single most useful design decision, framed by Anthropic. A *workflow* is LLM steps wired by predefined code — chaining, routing, parallelization. Predictable, cheap, debuggable. An *agent* lets the LLM direct its own path — open-ended, loops until done, handles ambiguity, but costs more and is harder to predict. Golden rule: use the simplest thing that works. Reach for an agent only when you genuinely can't hard-code the path."
**🗣 cue:** Yeh slide pe thoda ruko — interviewers/seniors ko yahi distinction impress karta hai.

### 10 — ReAct: the loop we'll build live
**Say:** "Zoom into ReAct because we're about to build it. The model writes a Thought, names an Action and its input, we run the tool, feed back the Observation — and it repeats until it can give a Final Answer. No framework: it's literally a prompt, a parser, and a while-loop. The stop sequence on 'Observation:' is the trick — it hands control back to our code so *we* run the tool. Production just adds max-iterations, a timeout, a dollar budget, and stuck-detection."
**🗣 cue:** Transcript padh ke dikhao — "yeh exactly aise hi terminal mein aayega."

### 11 — 🔴 DEMO 1 → switch to terminal (see Demo 1 below)

### 12 — Frameworks: when to reach for them (Layer 7)
**Say:** "Build the loop by hand once — then you understand what frameworks hide, and you graduate. LangGraph for stateful, durable, multi-step graphs. MCP — think USB-C for tools — so a tool works across apps and models. CrewAI for fast role-based multi-agent prototypes. LangChain / LlamaIndex / Pydantic-AI as building blocks. Don't *start* with a framework; adopt one when you need state and standard integrations."

### 13 — Production: demos vs. systems (Layer 8)
**Say:** "The last mile, and none of it is the model. Observability — trace every step, token and dollar. Guardrails — block prompt injection, PII leaks, unsafe output. Evaluation — golden sets plus LLM-as-judge, run in CI to catch regressions. Cost optimization — cache, route to cheaper models, trim context. Plus human gates and reliability. This is what makes a team *trust* the thing."

### 14 — One end-to-end reference architecture
**Say:** "Everything on one diagram. A request comes in through a gateway, hits the orchestrator — that's the agent loop, often LangGraph — which fans out to the LLM, your tools (via MCP), and RAG, then returns an answer with citations. Two things wrap *every* hop: guardrails on input and output, and observability across the whole run. That's the shape of a real production AI system."
**🗣 cue:** "Slides 4–13 ke saare boxes yahan ek jagah baith jaate hain."

### 15 — 🔴 DEMO 2 → switch to terminal (see Demo 2 below)

### 16 — When to use what + takeaways
**Say:** "Pick the lowest rung that solves your problem: single call, then structured output, then tools, then RAG, then an agent loop, then multi-agent. Each rung adds power *and* cost — most problems stop at rung 3 or 4. Five things to take home:" *(read the right column).* "The model is one layer; the workflow around it is the real work. Thank you — questions?"

---

## 🔴 DEMO 1 — ReAct agent from scratch (slide 11)

**Goal:** show the Thought → Action → Observation loop running in pure Python — *no framework*.

**Run:**
```bash
cd /Users/youngmanindia/Documents/PythonRevision/Agentic_AI
source ../.venv/bin/activate
python Level6_Agent_Patterns/04_react_pattern_practical.py
```

**Walk through, top to bottom:**
1. **Section 3 — Basic agent.** Point at the printed `--- Iteration N ---` blocks: "Watch it think, pick a tool, read the result, then go again." It answers *"weather in Mumbai AND 25×8"* by chaining **two** tools.
2. **Section 4 — Production agent.** Point at the per-question summary: **Status · Cost · Iterations · Tools used.** "Same loop, but now with a dollar budget, a timeout, and stuck-detection — the difference between a toy and something you'd ship."
3. **Section 5 — Streaming events.** "These callbacks (`on_thought`, `on_action`, `on_observation`) are exactly what a chat UI consumes to render the agent live."

**🗣 cue:** Jab tool chain hota dikhe — "dekho, humne ise nahi bola kaunsa tool; *usne* khud decide kiya." Yahi agentic behaviour hai.

**No API key? (totally fine — fully rehearsable):**
- The file runs end-to-end without a key. Section 3 prints `[NO_API_KEY]`; Section 4 prints `Status: no_api_key` for each question (no crash — verified).
- In that case, **don't** rely on live output — instead walk the **slide-10 transcript** line by line and say "with a key set, this is exactly what streams out." Then show the *code* (the prompt template + the while-loop in `run()`) to prove there's no magic.
- To go live later: `export OPENAI_API_KEY=sk-...` then re-run.

**If it errors live:** stay calm, switch to slide 10, narrate the transcript, show the `build_prompt()` + `run()` methods in the editor. The story doesn't depend on the network.

---

## 🔴 DEMO 2 — Multi-agent code review (slide 15)

**Goal:** show the *whole stack* in one system — multi-agent supervisor, routing, human-in-loop, cost-aware model tiering, an MCP tool.

**Run:**
```bash
cd /Users/youngmanindia/Documents/PythonRevision/Agentic_AI
python Projects/project3_multiagent_code_review_starter/main.py
```

**This one is bullet-proof — it runs in placeholder mode with no key** and prints the architecture + cost breakdown. Narrate the printed output:
- "A GitHub PR comes in → three specialists run **in parallel**: Security on **Opus** (don't miss a CVE), Performance on **Sonnet**, Style on **Haiku** (cheapest)."
- "They're synthesized; if there's a CRITICAL issue it routes to **human review**, else it posts inline comments — and fires a **Slack alert via an MCP tool**."
- **Punchline:** "Total ≈ **$0.10 per PR**. Tiering the models — Opus only where it matters — is ~80× cheaper than running everything on Opus. That's a production cost decision, live."

**🗣 cue:** "Yeh ek file mein slide 8 ke aadhe patterns + slide 13 ki cost optimization ek saath dikhata hai." Connect it back to the reference architecture (slide 14).

**Going deeper (optional):** open `main.py` in the editor — the milestones (1–8) are commented out as a build roadmap. Good place to say "yeh skeleton hai, production mein LangGraph supervisor + Instructor + GitHub webhook isi pe banta hai."

---

## ❓ Likely questions (have an answer ready)

- **"Workflow vs agent — practically, kab kya?"** → If you can draw the flowchart, it's a workflow; if the steps depend on what the model discovers at runtime, it's an agent. Start with the workflow.
- **"ReAct vs native function-calling?"** → Function-calling is the same loop with the provider parsing tool calls for you (structured, fewer parse bugs). ReAct-from-scratch is the teaching version and works on any model. Production: prefer native tool-calling.
- **"How do you stop an agent looping forever / burning money?"** → Exactly the Section-4 guards: max-iterations, timeout, a hard dollar budget, and stuck-detection (same action repeated → bail).
- **"RAG vs fine-tuning?"** → RAG for *knowledge* that changes (docs, tickets); fine-tuning for *behaviour/format/style*. Most teams need RAG first.
- **"How do you evaluate any of this?"** → Golden test set + LLM-as-judge in CI (slide 13). For RAG specifically, RAGAS (faithfulness, answer relevance).
- **"Which model?"** → Tier it. Cheapest model that passes your eval; escalate (Haiku → Sonnet → Opus) only where quality demands it — Demo 2 is exactly this.
```
