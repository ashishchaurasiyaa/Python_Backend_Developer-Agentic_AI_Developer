# Semantic Kernel — Microsoft's Agent Orchestration SDK

## Quick Concepts
- **Semantic Kernel (SK)** = Microsoft's open-source SDK (Python/.NET/Java) for wiring LLMs into apps — Azure-native equivalent of LangChain
- **Kernel** = the central object — holds registered AI services (chat completion, embeddings) and plugins, dependency-injection style
- **Plugin** = a group of functions the LLM can call — either **native functions** (plain Python, `@kernel_function`) or **prompt functions** (a templated prompt treated as a callable)
- **Automatic function calling** = SK inspects plugin function signatures/docstrings, builds the schema, and lets the model decide which to call — same idea as OpenAI function calling / LangChain tools
- **Planners** = older SK concept (sequential/stepwise planners) that auto-chained functions to reach a goal — **mostly superseded** by automatic function calling in current SK; interviewers who worked pre-2024 may still ask about it
- **Agent Framework** (newer SK) = `ChatCompletionAgent`, `AgentGroupChat` — SK's answer to CrewAI/AutoGen for multi-agent, converged with the (now-merged) AutoGen project
- **Key insight**: SK's real differentiator isn't the agent pattern (same ReAct/tool-calling ideas as everywhere else) — it's **first-class Azure/.NET enterprise integration** (Azure OpenAI, Azure AI Search, Semantic Kernel + Azure AI Foundry). JDs that name it (UnitedHealth Lead Architect, ZF, Dassault Systèmes) are Azure-heavy enterprise shops, not startups.

---

## Interview Questions & Answers

### Q1: Semantic Kernel kya hai aur LangChain se kaise alag hai?
**Answer:**
```python
"""
Semantic Kernel = Microsoft's SDK for LLM orchestration.

LangChain vs Semantic Kernel:
  LangChain → Python-first, huge community ecosystem, LCEL chains, LangGraph for agents
  Semantic Kernel → Enterprise/.NET-first (Python is a first-class but secondary SDK),
                     deep Azure integration, plugin model close to OpenAI function calling

Jab company Semantic Kernel maangti hai (usually):
  - Microsoft/Azure shop already using Azure OpenAI, Azure AI Foundry
  - .NET backend alongside Python AI layer
  - Enterprise governance/compliance heavy (SK plugins are easy to audit — plain functions)

Core building blocks:
  Kernel      → central registry: AI services + plugins
  Plugin      → group of functions (native or prompt-based)
  Function    → single callable the LLM can invoke
  Planner     → (legacy) auto-chains functions — replaced by auto function calling
  Agent       → ChatCompletionAgent / AgentGroupChat for multi-agent
"""

# pip install semantic-kernel

import asyncio
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion

kernel = Kernel()

# Register an AI service (OpenAI here; AzureChatCompletion for Azure OpenAI)
kernel.add_service(
    OpenAIChatCompletion(
        ai_model_id="gpt-4o-mini",
        api_key="sk-...",
        service_id="chat",
    )
)
```

---

### Q2: Native functions aur plugins — kaise register karte hain?
**Answer:**
```python
from semantic_kernel.functions import kernel_function
from typing import Annotated

# ===== NATIVE FUNCTION PLUGIN =====
# INTERVIEW: @kernel_function decorator = LangChain ke @tool jaisa hi kaam karta hai

class OrderPlugin:
    """Ek plugin = related functions ka group (jaise LangChain mein ek 'tool module')"""

    @kernel_function(
        name="get_order_status",
        description="Get the current status of an order by order ID",
    )
    def get_order_status(
        self,
        order_id: Annotated[str, "The order ID to look up"],
    ) -> str:
        # Real mein: DB lookup
        return f"Order {order_id} is out for delivery"

    @kernel_function(
        name="cancel_order",
        description="Cancel an order if it hasn't shipped yet",
    )
    def cancel_order(
        self,
        order_id: Annotated[str, "The order ID to cancel"],
    ) -> str:
        return f"Order {order_id} cancelled successfully"

# Plugin ko kernel mein register karo
kernel.add_plugin(OrderPlugin(), plugin_name="orders")

# INTERVIEW: docstring/description + type annotations se schema auto-generate hota hai
# — bilkul PydanticAI ke @agent.tool aur LangChain ke @tool jaisa concept
```

---

### Q3: Prompt functions — templated prompt ko callable banana?
**Answer:**
```python
from semantic_kernel.functions import KernelFunctionFromPrompt

# ===== PROMPT FUNCTION =====
# INTERVIEW: SK mein prompt bhi ek "function" hai — LangChain ke PromptTemplate | LLM chain jaisa

summarize_fn = KernelFunctionFromPrompt(
    function_name="summarize",
    plugin_name="text_utils",
    prompt="""
    Summarize the following text in {{$style}} style, in under 3 sentences:

    {{$input}}
    """,
)
kernel.add_function(plugin_name="text_utils", function=summarize_fn)

async def run_summary():
    result = await kernel.invoke(
        function_name="summarize",
        plugin_name="text_utils",
        input="Long article text here...",
        style="casual",
    )
    print(result)

asyncio.run(run_summary())

# {{$variable}} = SK's templating syntax (their own, not Jinja2)
# Prompt functions can call native functions inline too — {{orders.get_order_status $order_id}}
```

---

### Q4: Automatic function calling — LLM khud decide karta hai kaunsa function call kare?
**Answer:**
```python
from semantic_kernel.connectors.ai.open_ai import OpenAIChatPromptExecutionSettings
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior
from semantic_kernel.contents import ChatHistory

# ===== AUTO FUNCTION CALLING =====
# INTERVIEW: FunctionChoiceBehavior.Auto() = model ko saare registered plugins visible
# hote hain, wo khud decide karta hai kaunsa call karna hai — bilkul OpenAI tool_choice="auto"

settings = OpenAIChatPromptExecutionSettings(
    function_choice_behavior=FunctionChoiceBehavior.Auto(),
)

chat_history = ChatHistory()
chat_history.add_user_message("What's the status of order ORD-4521?")

async def run_agentic_call():
    chat_completion = kernel.get_service(service_id="chat")
    response = await chat_completion.get_chat_message_content(
        chat_history=chat_history,
        settings=settings,
        kernel=kernel,   # kernel pass karna zaroori hai — isse plugins accessible hote hain
    )
    print(response)  # model ne khud get_order_status() call kiya, phir jawab diya

asyncio.run(run_agentic_call())

# LangChain equivalent: bind_tools() + tool_choice="auto"
# PydanticAI equivalent: @agent.tool (automatic by default)
```

---

### Q5: Planners — legacy concept, ab kyun replace ho gaye?
**Answer:**
```python
"""
INTERVIEW TRAP: Purane SK docs/tutorials "Planners" (SequentialPlanner, ActionPlanner)
push karte the — ek natural-language goal se, LLM khud ek multi-step function-call
plan generate karta tha, phir wo plan execute hota tha.

Ab (2024+) yeh mostly deprecated hai kyunki:
  - Automatic function calling (Q4) same cheez achieve kar leta hai simpler tareeke se
  - Modern LLMs (GPT-4+) reliably multi-step tool calls khud kar lete hain bina
    separate "planning" phase ke
  - Planners debugging mushkil thi — generated plan opaque hota tha

Agar interviewer planners ke baare me poochhe:
  "Planners were SK's early approach to multi-step task decomposition — a planner LLM
   call would generate a sequence of function calls to execute. Modern SK (and the
   industry broadly — same shift happened with LangChain's deprecated `PlanAndExecute`)
   moved to native function calling, where the same model that's already in the loop
   decides tool sequence turn-by-turn, which is simpler and more reliable."

Yeh same pattern jo tumne LangGraph Plan-and-Execute pattern mein padha hai —
(Agentic_AI/Level6_Agent_Patterns/05_plan_and_execute.md) — wahi trade-off yahan bhi hai:
explicit upfront plan (fragile, opaque) vs step-by-step reactive tool calling (ReAct-style).
"""
```

---

### Q6: Multi-agent — AgentGroupChat kaise kaam karta hai?
**Answer:**
```python
from semantic_kernel.agents import ChatCompletionAgent, AgentGroupChat
from semantic_kernel.agents.strategies import TerminationStrategy

# ===== MULTI-AGENT WITH AgentGroupChat =====
# INTERVIEW: SK's Agent Framework absorbed AutoGen's ideas after the Microsoft merge —
# same "multiple role-based agents talk to each other" pattern as CrewAI/AutoGen

writer_agent = ChatCompletionAgent(
    kernel=kernel,
    name="Writer",
    instructions="You write concise marketing copy. Revise based on reviewer feedback.",
)

reviewer_agent = ChatCompletionAgent(
    kernel=kernel,
    name="Reviewer",
    instructions="You critique marketing copy for clarity and tone. Approve when good.",
)

class ApprovalTermination(TerminationStrategy):
    """Group chat rukta hai jab reviewer 'approved' bole"""
    async def should_agent_terminate(self, agent, history):
        return "approved" in history[-1].content.lower()

group_chat = AgentGroupChat(
    agents=[writer_agent, reviewer_agent],
    termination_strategy=ApprovalTermination(agents=[reviewer_agent], maximum_iterations=5),
)

async def run_group_chat():
    await group_chat.add_chat_message("Write a tagline for a running shoe brand.")
    async for message in group_chat.invoke():
        print(f"{message.name}: {message.content}")

asyncio.run(run_group_chat())

# COMPARISON:
# CrewAI    → role/task/crew abstraction, opinionated, easiest to start
# AutoGen   → conversational multi-agent, flexible, research-oriented (now merges into SK)
# SK Agents → same idea, but native to the Azure/enterprise stack you're already in
```

---

### Q7: SK kab choose karo — decision guide?
**Answer:**
```
Choose Semantic Kernel jab:
  - Company already Azure OpenAI / Azure AI Foundry pe invested hai
  - .NET/C# backend team ke saath Python AI layer integrate karna hai (SK has parity
    across languages — same plugin runs conceptually the same in Python and C#)
  - Enterprise governance chahiye — plugins are plain typed functions, easy to
    audit/unit-test compared to prompt-chain-heavy LangChain pipelines

Choose LangChain/LangGraph jab:
  - Python-only shop, need the biggest ecosystem of integrations
  - Complex cyclic multi-agent graphs with checkpointing (LangGraph's strength)

Interview one-liner:
  "Semantic Kernel and LangChain solve the same problem — tool-calling LLM orchestration.
   The real difference is ecosystem fit: SK is the natural choice in an Azure/.NET
   enterprise, LangChain/LangGraph in a Python-first, cloud-agnostic shop. I'd pick
   based on what the rest of the stack already is, not the framework's own merits."
```

---

## Core Architecture Summary

```
Semantic Kernel Architecture:

  Kernel
  ├── AI Services (registered)         ← OpenAIChatCompletion / AzureChatCompletion
  ├── Plugins (registered)
  │   ├── Native Functions             ← @kernel_function, plain Python
  │   └── Prompt Functions             ← KernelFunctionFromPrompt, {{$var}} templating
  │
  ├── FunctionChoiceBehavior.Auto()     ← model decides which function to call
  ├── (legacy) Planners                ← superseded by auto function calling
  │
  └── Agent Framework
      ├── ChatCompletionAgent          ← single role-based agent
      └── AgentGroupChat               ← multi-agent conversation + termination strategy

Where it fits in your prep:
  Same underlying concepts as LangChain tools (Level7_Frameworks/01) and CrewAI (05) —
  don't relearn agentic theory, just map SK's vocabulary onto what you already know.
  Only worth deep hands-on time if targeting an Azure-heavy enterprise (per
  JD_ANALYSIS_TOP50.md: UnitedHealth Lead Architect, ZF, Dassault Systèmes named it).
```
