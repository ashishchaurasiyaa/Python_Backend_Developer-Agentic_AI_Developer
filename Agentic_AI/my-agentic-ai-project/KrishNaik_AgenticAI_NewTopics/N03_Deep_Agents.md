# Deep Agents

> **Source:** Krish Naik — "Complete Agentic AI Course In 10 Hours" · 08:02:11 · notebook: deepagents (Google Drive)

---

## TL;DR

`deepagents` ek Python library hai jo tujhe **production-grade autonomous agents** banana deti hai — sirf ek function call se. Yeh LangGraph ke upar build hui hai, aur automatically 4 kaam karti hai: (1) **plan** banata hai (todo list tool se), (2) **context ko files mein store** karta hai (virtual filesystem), (3) **sub-agents spawn** karta hai complex subtasks ke liye, aur (4) ek **Claude Code-inspired detailed system prompt** use karta hai jo in sabko orchestrate karta hai. Agar tune ALEX jaisa multi-agent system haath se banaya hai — yeh library woh sab cheez ek `create_deep_agent()` call mein deti hai, lekin with batteries included.

---

## Hinglish Explanation

### Problem: Complex Tasks ke liye normal agents kyun fail karte hain?

Teri normal `create_agent()` pattern mein — ek model, kuch tools, aur ek loop — yeh chhoti tasks ke liye kaafi hai. Lekin jab task complex ho jaye — "Research karo aur ek detailed report likho" — tab problems aati hain:

1. **Context window exhaust** ho jaata hai — saare search results ek hi conversation mein daal do, model confuse ho jaata hai
2. **No planning** — agent seedha action mein kood jaata hai bina soch ke ki pehle kya karna hai, baad mein kya
3. **Specialization nahi** — ek hi agent sab kuch kar raha hai, chahe uske liye optimize na ho
4. **Memory nahi** — conversation khatam, sab bhool gaya

`deepagents` yeh sab solve karta hai ek structured pattern se.

---

### Pillar 1: Planning Tool — "Pehle Soch, Phir Karo"

Deep agent ke paas ek built-in **`write_todos` tool** hota hai. Jab agent koi complex task receive karta hai, woh pehle apna **plan likha hai ek structured todo list ke roop mein**. Yeh sirf ek gimmick nahi hai — yeh LLM ko force karta hai ki task ke "shape" ke baare mein soche pehle action lene se.

Real example: agar tune agent ko bola "What is deepagent?" — toh agent ne automatically:
- Task ko sub-problems mein todha
- Har sub-problem ke liye steps likhe
- Phir systematically execute kiya

Yeh wahi pattern hai jo Claude Code follow karta hai — seedha code likhne ki jagah pehle ek plan/approach think karta hai. Humans bhi yahi karte hain — senior engineer seedha code nahi likhta, pehle design karta hai.

---

### Pillar 2: Virtual Filesystem — "Context Ka Hard Drive"

LLM ka context window finite hai. Jab tu web search karta hai toh results bohot bade hote hain. Sab kuch context mein rakh do toh model slow ho jaata hai, expensive ho jaata hai, aur quality girti hai.

**Solution:** Deep agent ke paas built-in file system tools hain:

- **`write_file(path, content)`** — search results ya intermediate work ko virtual files mein save karo
- **`read_file(path)`** — jab zaroorat ho tab file wapas padho
- **`list_files()`** — dekho ki kya kya save hai

Yeh **scratch memory / working memory** ki tarah kaam karta hai. Agent apni findings ko files mein dump karta rahe, aur sirf relevant cheez context mein rakhe synthesis ke liye.

Invoke ke baad result mein ek `files` key bhi hoti hai — tu dekh sakta hai agent ne kya kya files banaye:

```python
result = deepagent.invoke({"messages": [{"role": "user", "content": "What is deepagent?"}]})

# Agent ka final response
print(result["messages"][-1].content)

# Agent ne kya kya files banaye dekhna hai
print(result['files'])
```

---

### Pillar 3: Sub-Agents — "Kaam Ka Delegation"

Complex tasks ke liye deep agent **child agents spawn** kar sakta hai. Yeh context isolation ke liye hai:

- Main agent ka context clean rahta hai high-level orchestration ke liye
- Each sub-agent apna specific subtask independently complete karta hai
- Sub-agent ki findings main agent ko return ho jaati hain

Yeh pattern Claude Code (file editing + bash execution alag tools), Deep Research (parallel search agents), aur Manus (multi-modal parallel agents) se inspired hai.

---

### Pillar 4: Detailed System Prompt — "Claude Code Jaisa Brain"

Deep agent ek **built-in, Claude Code-inspired system prompt** ke saath aata hai. Yeh prompt bahut detailed hota hai — isme instructions hain ki:
- Planning tool kab aur kaise use karna hai
- Filesystem tools kab use karni hain
- Sub-agents kab spawn karne hain
- Task completion ke baad report kaise synthesize karni hai

Iske upar tu apna **custom system prompt** add kar sakta hai jo use-case specific instructions deta hai. Built-in prompt ka kaam underlying mechanics handle karna hai, tera prompt domain-specific expertise deta hai:

```python
research_instructions = """\
You are an expert researcher. Your job is to conduct \
thorough research, and then write a polished report. \
"""

agent = create_deep_agent(
    model=model,
    system_prompt=research_instructions,
)
```

---

### `create_deep_agent()` — Full Usage

**Step 1: Setup**

```python
import os
from dotenv import load_dotenv
load_dotenv()

os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
os.environ["GROQ_API_KEY"] = os.getenv("GROQ_API_KEY")
os.environ["TAVILY_API_KEY"] = os.getenv("TAVILY_API_KEY")
```

**Step 2: Model init — LangChain ke zariye**

```python
from langchain.chat_models import init_chat_model

model = init_chat_model("groq:qwen/qwen3-32b")
# ya GPT ke liye:
# model = init_chat_model(model="gpt-5")
```

**Step 3: Custom tool define karo**

```python
from tavily import TavilyClient
from typing import Literal

tavily_client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])

def internet_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
    include_raw_content: bool = False,
):
    """Run a web search"""
    return tavily_client.search(
        query,
        max_results=max_results,
        include_raw_content=include_raw_content,
        topic=topic,
    )
```

**Step 4: Deep agent create karo**

```python
from deepagents import create_deep_agent

# Minimal version
deepagent = create_deep_agent(
    model=model,
    tools=[internet_search],
    system_prompt="Act as a researcher"
)

# Full production version with custom instructions
research_instructions = """\
You are an expert researcher. Your job is to conduct \
thorough research, and then write a polished report. \
"""

deepagent = create_deep_agent(
    model=model,
    tools=[internet_search],
    system_prompt=research_instructions,
)
```

**Step 5: Invoke — standard LangGraph interface**

```python
result = deepagent.invoke({
    "messages": [{"role": "user", "content": "What is deepagent in Agentic AI?"}]
})

# Final answer
print(result["messages"][-1].content)

# Filesystem check — agent ne kya notes rakhe
print(result['files'])
```

**Under the hood kya hua (automatic):**

1. `write_todos` tool call — task breakdown
2. `internet_search` tool call (tera custom tool) — web se data fetch
3. `write_file` tool calls — results filesystem mein save
4. (Optional) sub-agent spawn — complex subtasks ke liye
5. `read_file` tool calls — relevant files padho
6. Final synthesis — polished report generate karo

---

### Comparison: Simple Agent vs Deep Agent

```python
# Simple agent — seedha tools call karta hai, no planning
from langchain.agents import create_agent

simple_agent = create_agent(
    model=model,
    tools=[web_search]
)

# Deep agent — plan + filesystem + sub-agents + detailed prompt
from deepagents import create_deep_agent

deep_agent = create_deep_agent(
    model=model,
    tools=[internet_search],
    system_prompt="Act as a researcher"
)
```

Simple agent ek junior developer jaisa hai — task do, direct karo execute karna shuru. Deep agent ek senior engineer jaisa hai — task do, woh khud plan banata hai, kaam delegate karta hai, notes rakhta hai, aur ek comprehensive output deta hai.

---

## Aapke Existing Knowledge Se Connect

### LangGraph Se Connection — "Yeh LangGraph Par Hi Hai"

Tu LangGraph ka 23-lecture course kar chuka hai. `deepagents` ko samajhna tera kaam easy ho jaata hai:

| LangGraph Concept | deepagents Equivalent |
|---|---|
| `StateGraph` nodes | Internal nodes for planning, tool execution, synthesis |
| `ToolNode` | Built-in nodes for `write_todos`, `write_file`, `read_file` |
| `MessagesState` | Standard messages + extra `files` key in state |
| `checkpointer` | Built-in thread/memory persistence |
| Custom nodes for routing | Built-in supervisor that decides plan/execute/sub-agent/synthesize |
| Human-in-the-loop interrupt | Available via standard LangGraph interrupt mechanism |

**Simple terms mein:** `create_deep_agent()` ek pre-built `StateGraph` return karta hai. Teri invoke syntax wahi hai jo LangGraph mein hoti hai — `{"messages": [...]}`. Result bhi ek State dict hai jisme `messages` aur `files` keys hain.

Tu `deepagent` object ke upar saari LangGraph operations kar sakta hai — streaming, async invoke, thread management, breakpoints — kyunki internally yeh ek compiled LangGraph graph hai.

```python
# LangGraph style streaming — same as teri LangGraph knowledge
async for chunk in deepagent.astream({"messages": [...]}):
    print(chunk)
```

---

### Tera ALEX System Se Contrast — "Haath Se Banaya vs Pre-built"

Tu ne ALEX banaya — Orchestrator + Planner + Analyst + Risk Analyst + Synthesizer. Sochte hain kaise compare hota hai:

**ALEX (Haath se banaya):**
- 5 alag agents, explicitly defined
- Orchestrator manually routing decisions karta hai
- Har agent ka context tumhare haath mein hai
- Tool assignment explicit hai — kaun sa agent kaun sa tool use karta hai
- Inter-agent communication tere graph edges define karte hain
- Debugging easy hai kyunki sab visible hai

**deepagents approach:**
- Ek single `create_deep_agent()` call
- Planning tool automatically todo list banata hai (ALEX ke Planner jaisa)
- Sub-agents on-demand spawn hote hain (ALEX ke Analyst/Risk/Synthesizer jaisa)
- Filesystem context management hai (ALEX mein yeh manually handle karna padta)
- LangGraph graph internally hai, but hidden hai

**Kab ALEX jaisa hand-built system better hai:**
- Jab tujhe exact control chahiye ki kaun sa agent kab chalega
- Jab fixed workflow hai — e.g., "Pehle plan, phir risk assessment, phir synthesis" — yeh order kabhi nahi badlega
- Jab explainability/auditability critical ho (compliance, finance, healthcare)
- Jab har agent ke liye alag memory store chahiye

**Kab deepagents better hai:**
- Rapid prototyping — "prove karo ki yeh kaam karta hai" in hours not days
- Research/information-gathering tasks jahan workflow dynamic ho
- Jab task structure apfront unknown ho — agent khud decide kare
- Internal tools, demos, one-off automation

**Sab se important insight:** ALEX banake tune yeh samajh liya ki deepagents ke andar kya ho raha hai. Production mein ek senior dev dono ke tradeoffs jaanta hai aur situation ke hisaab se choose karta hai. deepagents = good starting point / prototype tool. ALEX-style = production-grade custom orchestration.

---

## Key Concepts

| Concept | Matlab |
|---|---|
| `deepagents` library | LangGraph-based library for autonomous agents with planning + filesystem + sub-agents |
| `create_deep_agent()` | Main factory function — returns a compiled LangGraph graph |
| `write_todos` tool | Built-in planning tool — agent apna todo list banata hai |
| `write_file` / `read_file` | Built-in virtual filesystem tools — context management ke liye |
| Sub-agents | Spawned on-demand for context isolation and specialization |
| Detailed system prompt | Claude Code-inspired built-in prompt + tera custom domain prompt |
| `result['files']` | Agent ke virtual filesystem ka snapshot — state mein extra key |
| Context isolation | Sub-agent ko fresh context milti hai — main agent ka window pollute nahi hota |
| `init_chat_model()` | LangChain helper — model string se model object banao ("groq:qwen3-32b") |
| Manus / Deep Research | Production agents jinse deepagents inspired hai — same architectural pattern |

---

## Backend Dev Ke Liye Note

1. **Library install:** `pip install deepagents` — yeh actively developed hai, LangGraph version compatibility check karna important hai. Internally LangGraph ka latest compile pattern use karta hai.

2. **API Key management:** Teri `.env` pattern wahi hai. Lekin production mein `os.getenv()` ke jagah proper secrets management use karo (AWS Secrets Manager, GCP Secret Manager, etc.).

3. **Filesystem tool state:** `result['files']` dictionary hai — keys file paths, values content. Yeh in-memory hai, persistent nahi by default. Agar teri production use-case mein files persist karni hain (across sessions), toh custom filesystem tool banana padega jo actual S3/GCS/DB pe likhta ho.

4. **Model flexibility:** `init_chat_model("groq:qwen/qwen3-32b")` — yeh LangChain ka universal interface hai. String format: `"provider:model_id"`. Swap karna easy hai — "openai:gpt-4o", "anthropic:claude-opus-4-5" — bina code change ke.

5. **Sub-agent spawning depth:** Deep agents mein sub-agents recursive bhi ho sakte hain — sub-agent bhi sub-agents spawn kar sakta hai. Production mein recursion depth cap karna best practice hai — infinite loop aur cost overrun se bachne ke liye.

6. **LangSmith integration:** Kyunki internally LangGraph hai, LangSmith tracing automatically kaam karta hai. `LANGCHAIN_API_KEY` aur `LANGCHAIN_TRACING_V2=true` set karo aur poori agent execution trace mein dikh jaayegi — har tool call, har sub-agent invocation sab visible.

7. **Streaming ke liye:** `deepagent.astream()` use karo FastAPI endpoints ke liye — real-time intermediate steps stream karna users ko much better experience deta hai long-running research tasks pe.

---

## Takeaway

- `deepagents` ek **high-level abstraction** hai LangGraph ke upar — woh sab kuch jo tu ALEX mein manually bana chuka hai (planning, orchestration, memory), yeh library wo sab built-in deti hai
- **4 pillars:** planning tool (write_todos) + virtual filesystem (write_file/read_file) + sub-agents (context isolation) + detailed system prompt (Claude Code-inspired) — yeh cheeze milke agent ko genuinely autonomous banati hain
- **`create_deep_agent(model, tools, system_prompt)`** — bas itna kaafi hai ek capable agent ke liye; result standard LangGraph state dict hai jisme extra `files` key hai
- **ALEX vs deepagents:** ALEX = explicit control, production-grade, auditable; deepagents = rapid prototyping, dynamic workflows, minimal boilerplate — dono ka apna place hai
- **Production mindset:** deepagents ek great starting point hai, lekin real-world use cases mein tu iske components ko individual LangGraph nodes mein extract kar sakta hai jab custom control chahiye — yeh knowledge teri LangGraph background se direct aati hai

---

## Source & Code

- **Video:** [Krish Naik — Complete Agentic AI Course In 10 Hours](https://www.youtube.com/watch?v=rV3HJ4LEZ7k) — Chapter at 08:02:11
- **Notebook source:** `/Users/youngmanindia/Documents/PythonRevision/Agentic_AI/my-agentic-ai-project/KrishNaik_AgenticAI_NewTopics/_sources/deep_agents.txt`
- **Library:** `pip install deepagents` — built on LangGraph, inspired by Claude Code / Manus / Deep Research patterns
- **Key import:** `from deepagents import create_deep_agent`
