# Level 6 — Doc 12: Agent Harness Engineering ⭐

> **Goal:** The "harness" is everything AROUND the LLM that turns raw text-in/text-out into an agent — system prompt, tool loop, context management, sandboxing. This is the discipline behind Claude Code, Cursor, Devin — and increasingly its own job-description line item, distinct from prompt engineering.

---

## 1. What "Harness" Actually Means

```
LLM alone:  text in → text out. That's it. No memory, no tools, no loop.

Harness =  the ENGINEERING SCAFFOLD wrapped around the LLM that gives it:
           - A system prompt defining role/constraints/available actions
           - A tool-calling LOOP (call model → execute tool → feed result back → repeat)
           - Context management (what goes into the context window, what gets dropped)
           - Permission/sandboxing (what the agent is ALLOWED to do without asking)
           - State across turns (conversation history, task tracking)

The MODEL is a commodity increasingly (swap Claude for GPT for Gemini).
The HARNESS is where the actual product engineering happens.
```

**Why this is now its own discipline, not just "prompt engineering":** prompt
engineering optimizes what you SAY to the model, once. Harness engineering
designs the entire SYSTEM the model operates inside — including decisions
that have nothing to do with wording, like "when do we compact the
conversation history" or "which tools get loaded upfront vs. deferred."

Senior/staff interview: "You're building an AI coding assistant. What's
actually hard about it, beyond picking a good model?" → the harness: tool
design, context/token budget management, error recovery, permission model —
these dominate the actual engineering effort, not prompt wording.

---

## 2. The Core Loop (this is what "agent" means, mechanically)

```
1. Assemble context: system prompt + conversation history + relevant
   tool results + (sometimes) retrieved docs
2. Call the model
3. Model responds with EITHER:
   a) A final answer → done
   b) A tool call request → go to step 4
4. Execute the requested tool (real code runs here, not the LLM)
5. Feed the tool's result back into context
6. Loop to step 1

This is literally the ReAct pattern (04_react_pattern.md) — a harness
IS a ReAct loop, engineered for production robustness.
```

```python
# Minimal harness loop (the actual shape underneath every coding agent)
def agent_loop(user_message, tools, system_prompt, max_iterations=20):
    messages = [{"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}]

    for _ in range(max_iterations):   # hard cap — NEVER loop unbounded
        response = llm.call(messages, tools=tools)

        if response.stop_reason == "end_turn":
            return response.text   # model is done, no more tool calls

        for tool_call in response.tool_calls:
            result = execute_tool(tool_call)   # REAL side effects happen here
            messages.append({"role": "tool", "tool_call_id": tool_call.id,
                              "content": result})

        messages.append(response)   # model's own turn goes back into history

    return "Max iterations reached — task may be incomplete"
```

The `max_iterations` cap is not optional — a harness without one can spin
forever on a stuck task, burning tokens/cost with no human noticing until
the bill arrives.

---

## 3. System Prompt Design (harness-level, not just "good wording")

```
A harness's system prompt is an ENGINEERING ARTIFACT, not just instructions:
- Defines the agent's IDENTITY and scope ("You are a coding assistant
  operating in the user's repo")
- Lists AVAILABLE TOOLS and when to use each (often more effective than
  relying on tool descriptions alone)
- Encodes SAFETY RULES (never run destructive commands without confirmation)
- Sets OUTPUT FORMAT conventions (how to reference files, how to show diffs)
- Often INJECTS PROJECT-SPECIFIC CONTEXT (a CLAUDE.md/rules file, exactly
  like this repo's own CLAUDE.md — the harness reads it and folds it into
  the system prompt automatically, so YOU are already living inside an
  example of this pattern)
```

**Key harness-engineering tension:** longer, more detailed system prompts
improve reliability/safety but cost tokens on EVERY single call in the loop
— a system prompt is re-sent (or cached, see below) on every iteration, not
just once. This is a real budget decision, not just a prompt-quality one.

---

## 4. Context Window Management — the hardest harness problem

```
Problem: a long-running agent task (many tool calls, many turns) eventually
fills the context window. Options:

1. TRUNCATE oldest messages — simple, but loses early task context that
   might matter later (e.g., original user requirements)

2. SUMMARIZE/COMPACT — periodically ask the model to summarize the
   conversation so far, replace old messages with the summary. Preserves
   gist, loses precise detail. (This is literally what happens in THIS
   conversation when it gets long — the harness compacts prior turns.)

3. SELECTIVE RETENTION — keep system prompt + most recent N turns + any
   messages explicitly flagged as important (e.g., the original task
   description), drop routine tool-result noise from the middle

4. TOOL RESULT TRIMMING — a `read_file` tool result of a 2000-line file
   doesn't need to stay in full context forever; summarize or truncate
   PAST tool results more aggressively than the current turn's
```

```python
def manage_context(messages, max_tokens=100_000):
    current_tokens = count_tokens(messages)
    if current_tokens < max_tokens * 0.8:   # leave headroom, don't wait until full
        return messages

    system = messages[0]
    recent = messages[-10:]           # keep the most recent exchanges verbatim
    middle = messages[1:-10]

    summary = llm.call([
        {"role": "system", "content": "Summarize this conversation concisely, "
                                        "preserving key decisions and task state."},
        {"role": "user", "content": format_messages(middle)},
    ])
    return [system, {"role": "assistant", "content": f"[Earlier context summary: {summary}]"}] + recent
```

**Prompt caching** (Level3 coverage) is the OTHER half of this problem —
even when NOT compacting, re-sending the same system prompt + tool
definitions on every loop iteration is expensive; caching the static prefix
(system prompt, tool schemas) while only the growing conversation tail is
uncached is standard harness practice, not optional.

---

## 5. Permission Models & Sandboxing

```
A harness must decide, for EVERY tool call, one of three things:

1. AUTO-ALLOW  — safe, reversible, read-only actions (read a file, search)
2. ASK FIRST   — risky/irreversible actions (delete a file, run `rm -rf`,
                 push to git, send an email) — surface to a human, wait
3. NEVER ALLOW — hard-blocked regardless of what the model requests
                 (e.g., accessing credentials outside declared scope)
```

```python
RISK_TIERS = {
    "read_file": "auto_allow",
    "search_code": "auto_allow",
    "write_file": "ask_first",       # modifies state, but locally reversible via git
    "run_bash": "ask_first",         # depends on the specific command
    "git_push": "ask_first",
    "delete_production_db": "never_allow",   # not even a tool the model CAN call
}

def should_execute(tool_name, risk_tiers=RISK_TIERS):
    tier = risk_tiers.get(tool_name, "ask_first")   # unknown tool = ask, don't assume safe
    if tier == "never_allow":
        raise PermissionError(f"{tool_name} is hard-blocked")
    return tier == "auto_allow"   # if False, caller must get human confirmation
```

**Sandboxing** goes a level deeper — even an "allowed" tool call should run
in a constrained environment (a container, a restricted filesystem view, no
network access unless explicitly needed) so a MISTAKE (not malice) — the
model hallucinating a destructive command — can't cause unbounded damage.
This is why coding-agent harnesses run shell commands in sandboxes rather
than directly on the host, and why THIS system prompt you're reading right
now explicitly separates "reversible, low blast-radius" actions from ones
requiring explicit confirmation.

---

## 6. Sub-Agent Spawning (harness-level orchestration)

```
Complex tasks often get DELEGATED to a fresh sub-agent instance rather
than handled inline:

Main agent: "This requires searching 50 files for a pattern — that would
             blow my context budget if I read them all myself."
                    ↓
Spawns a SUB-AGENT with a narrow, self-contained task + its OWN fresh
context window
                    ↓
Sub-agent does the work, returns a SUMMARY (not its full trace) to the
main agent — keeping the main agent's context clean
```

This is a harness-level architectural decision — WHEN to delegate to a
sub-agent (context budget protection, parallelizing independent work,
isolating a risky exploratory task) versus handling everything in the main
loop. Directly extends the multi-agent-supervisor pattern
(`07_multi_agent_supervisor.md`) but the emphasis here is context/token
economics, not just task decomposition.

---

## 7. Evaluating a Harness (not just the model)

```
SWE-bench, Terminal-Bench, and similar benchmarks evaluate the FULL
harness+model combination, not the model in isolation — the same model
can score very differently depending on harness quality (tool design,
context management, error-recovery prompting).

This is why "which model is best at coding" is a less useful question
than "which harness+model combination performs best" — harness quality
is often a bigger lever than model choice alone.
```

Metrics that matter at the harness level specifically (beyond the general
agent evaluation metrics in `10_agent_evaluation.md`):
- **Tool-call success rate** — how often does the model call tools with
  valid arguments the harness can actually execute?
- **Recovery rate** — when a tool call fails/errors, does the agent
  recover gracefully or spiral?
- **Context efficiency** — tokens consumed per successfully completed task
  (a harness that compacts well costs less per task, same model)
- **Runaway rate** — how often does the loop hit `max_iterations` without
  completing (a harness/prompt-design failure, not necessarily a model failure)

---

## Interview Q&A

**Q: What's the difference between prompt engineering and harness engineering?**
A: Prompt engineering optimizes the WORDING of what you send the model.
Harness engineering designs the SYSTEM around the model — the tool-calling
loop, context/token budget management, permission model, sandboxing, and
sub-agent orchestration. A well-engineered harness with a mediocre prompt
often outperforms a great prompt in a poorly-engineered harness.

**Q: Why can't you just keep appending every tool result to the conversation forever?**
A: Context windows are finite, and even within budget, cost scales with
tokens sent per call (especially without caching). Harnesses must actively
manage context — truncation, summarization/compaction, or selective
retention — once the conversation approaches a token budget threshold.

**Q: How does a harness decide whether to ask for human confirmation before an action?**
A: A risk-tiered permission model — auto-allow reversible/read-only actions,
require explicit confirmation for irreversible or high-blast-radius actions
(deletions, pushes, external sends), and hard-block anything outside the
agent's declared scope regardless of what the model requests. This protects
against model MISTAKES, not just malicious intent.

**Q: Why would an agent spawn a sub-agent instead of just doing more tool calls itself?**
A: Context budget protection — reading dozens of files or exploring a
large search space inline would consume the main agent's context window
with intermediate noise. A sub-agent does that exploration in its OWN
context and returns only a distilled summary, keeping the main agent's
context focused on the task at hand.

---

Related: `04_react_pattern.md` (the loop this formalizes for production),
`07_multi_agent_supervisor.md` (sub-agent delegation, here viewed through a
context-economics lens), `10_agent_evaluation.md` (general eval — this file
adds harness-specific metrics), [../Level3_LLM_APIs_SDKs](../Level3_LLM_APIs_SDKs)
(prompt caching, essential for harness cost control), `Modern_Topics/07_ai_coding_tools.md`
(the coding-agent application of everything here — see the companion deep-dive).
