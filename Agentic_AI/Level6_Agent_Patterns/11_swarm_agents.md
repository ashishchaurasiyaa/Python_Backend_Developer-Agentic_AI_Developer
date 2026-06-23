# Swarm Agents — Decentralized Multi-Agent Pattern

**Agentic AI · Level 6 — Agent Patterns | Senior AI Engineer**

---

## Quick Concepts

**WHAT:**
- **Swarm** = ek set of specialized agents jo peer-to-peer coordinate karte hain — koi central orchestrator nahi
- **Handoff** = ek agent apna control kisi doosre agent ko pass karta hai (baton-passing)
- OpenAI Swarm library ne yeh pattern popularize kiya (2024), ab Agents SDK me integrate hai

**Supervisor vs Swarm — KEY DIFFERENCE:**
```
Supervisor Pattern:
    Supervisor → Agent A
    Supervisor → Agent B     # Central controller decides sab kuch
    Supervisor → Agent C

Swarm Pattern:
    Agent A → handoff → Agent B → handoff → Agent C   # Agents khud decide karte hain
```

**WHEN TO USE SWARM:**
- Tasks me clear "departments" hain (support → billing → technical)
- Har agent ka domain clearly defined hai, overlap nahi
- Low-latency chahiye (supervisor roundtrip eliminate)
- Workflows jo mostly linear ya predictable hain

**WHEN NOT TO USE:**
- Complex coordination chahiye
- Agents ko ek doosre ka output simultaneously chahiye
- Dynamic task decomposition needed (LangGraph ya Supervisor better)

---

## Part 1: Core Mechanism — Handoff

```python
from swarm import Swarm, Agent

client = Swarm()

# Triage agent → billings ya technical ke paas bhejta hai
def transfer_to_billing():
    """User billing/payment queries ke liye."""
    return billing_agent

def transfer_to_technical():
    """User technical issues ke liye."""
    return technical_agent

triage_agent = Agent(
    name="Triage",
    instructions="""Tum customer queries route karte ho.
    - Billing/payment? → transfer_to_billing
    - Technical issue? → transfer_to_technical
    - General? Khud handle karo.""",
    functions=[transfer_to_billing, transfer_to_technical],
)

billing_agent = Agent(
    name="Billing",
    instructions="Tum billing aur payment queries handle karte ho. Refunds process kar sakte ho.",
    functions=[process_refund, check_invoice],
)

technical_agent = Agent(
    name="Technical Support",
    instructions="Tum technical issues debug karte ho. Escalate karo agar unsolvable.",
    functions=[check_system_status, reset_password, escalate_to_human],
)

# Run karo
response = client.run(
    agent=triage_agent,
    messages=[{"role": "user", "content": "Mujhe mera last invoice nahi mila"}]
)

print(f"Last agent: {response.agent.name}")  # "Billing"
print(response.messages[-1]["content"])
```

---

## Part 2: Context Variables (State across handoffs)

```python
from swarm import Swarm, Agent

client = Swarm()

def greet_user(context_variables: dict) -> str:
    """User ko greet karo."""
    name = context_variables.get("user_name", "Guest")
    return f"Namaste {name}! Aapki kaise madad kar sakta hoon?"

def lookup_order(order_id: str, context_variables: dict) -> str:
    """Order details fetch karo."""
    # Context update karo taki next agent use kar sake
    context_variables["last_order_id"] = order_id
    context_variables["order_status"] = "shipped"
    return f"Order {order_id}: Shipped on June 20, expected June 25."

def transfer_to_returns():
    return returns_agent

support_agent = Agent(
    name="Support",
    instructions="Helpful customer support agent.",
    functions=[greet_user, lookup_order, transfer_to_returns],
)

returns_agent = Agent(
    name="Returns",
    instructions="""Returns process karo.
    Context me last_order_id available hai use karo.""",
    functions=[process_return],
)

# Context initialize karo
context = {"user_name": "Rahul", "user_tier": "premium"}

response = client.run(
    agent=support_agent,
    messages=[{"role": "user", "content": "Order #1234 return karna hai"}],
    context_variables=context,
)

# Context updated values
print(context)  # {"user_name": "Rahul", "last_order_id": "1234", "order_status": "shipped", ...}
```

---

## Part 3: Swarm without OpenAI Swarm Library (Manual)

```python
from anthropic import Anthropic
import json

client = Anthropic()

class SwarmAgent:
    def __init__(self, name: str, system_prompt: str, tools: list, handoff_map: dict):
        self.name = name
        self.system_prompt = system_prompt
        self.tools = tools
        self.handoff_map = handoff_map  # {"transfer_to_billing": billing_agent}

class ManualSwarm:
    def __init__(self, entry_agent: SwarmAgent):
        self.entry_agent = entry_agent

    def run(self, user_message: str, context: dict) -> str:
        current_agent = self.entry_agent
        messages = [{"role": "user", "content": user_message}]
        iterations = 0
        max_iterations = 10

        while iterations < max_iterations:
            response = client.messages.create(
                model="claude-opus-4-8",
                max_tokens=1000,
                system=current_agent.system_prompt,
                tools=current_agent.tools,
                messages=messages,
            )

            # Handoff check
            for content in response.content:
                if content.type == "tool_use":
                    tool_name = content.name
                    if tool_name in current_agent.handoff_map:
                        # HANDOFF — agent switch karo
                        next_agent = current_agent.handoff_map[tool_name]
                        print(f"[Handoff: {current_agent.name} → {next_agent.name}]")
                        current_agent = next_agent
                        messages.append({"role": "assistant", "content": response.content})
                        messages.append({
                            "role": "user",
                            "content": [{"type": "tool_result", "tool_use_id": content.id,
                                         "content": f"Handoff to {next_agent.name}"}]
                        })
                        break

            if response.stop_reason == "end_turn":
                return response.content[0].text

            iterations += 1

        return "Max iterations reached."
```

---

## Part 4: Parallel Swarm (Multiple agents simultaneously)

```python
import asyncio
from anthropic import AsyncAnthropic

client = AsyncAnthropic()

async def parallel_analysis(document: str) -> dict:
    """
    Ek document ko parallel me multiple specialist agents analyze karte hain.
    Yeh Swarm nahi hai (handoff nahi hai), par related pattern hai.
    """
    async def legal_review():
        response = await client.messages.create(
            model="claude-opus-4-8",
            max_tokens=500,
            system="Tum legal expert ho. Sirf legal risks identify karo.",
            messages=[{"role": "user", "content": document}]
        )
        return {"legal": response.content[0].text}

    async def financial_review():
        response = await client.messages.create(
            model="claude-opus-4-8",
            max_tokens=500,
            system="Tum financial analyst ho. Sirf financial implications analyze karo.",
            messages=[{"role": "user", "content": document}]
        )
        return {"financial": response.content[0].text}

    async def technical_review():
        response = await client.messages.create(
            model="claude-opus-4-8",
            max_tokens=500,
            system="Tum tech expert ho. Sirf technical feasibility check karo.",
            messages=[{"role": "user", "content": document}]
        )
        return {"technical": response.content[0].text}

    # Parallel execution
    results = await asyncio.gather(legal_review(), financial_review(), technical_review())

    # Synthesis agent
    combined = "\n".join([str(r) for r in results])
    final = await client.messages.create(
        model="claude-opus-4-8",
        max_tokens=1000,
        system="Tum synthesis expert ho. Sab reviews ko ek coherent recommendation me combine karo.",
        messages=[{"role": "user", "content": combined}]
    )
    return final.content[0].text
```

---

## Part 5: Swarm vs Other Patterns

| Pattern          | Coordination | State | Best For |
|------------------|-------------|-------|----------|
| **Single Agent** | None        | Context window | Simple tasks |
| **Swarm**        | Handoffs    | context_variables | Domain routing |
| **Supervisor**   | Central LLM | Shared state | Complex decomposition |
| **Plan-Execute** | Sequential  | Plan object | Multi-step workflows |
| **Reflection**   | Self-loop   | Critique | Quality improvement |
| **LangGraph**    | Graph edges | State graph | Complex workflows |

### Real-world Swarm Use Cases
- **Customer Support**: Triage → Billing / Technical / Returns / Escalation
- **Code Review**: Orchestrator → Security Reviewer + Performance Reviewer + Style Checker
- **Content Pipeline**: Researcher → Writer → Editor → Publisher
- **Financial**: Data Collector → Analyst → Risk Assessor → Report Generator

---

## Part 6: Production Considerations

```python
# Swarm me guard rails
class ProductionSwarm:
    MAX_HANDOFFS = 5  # infinite loop prevent

    def run(self, ...) -> str:
        handoff_count = 0

        while True:
            if handoff_count > self.MAX_HANDOFFS:
                return "Too many handoffs — possible loop detected."

            response = self.call_agent(current_agent, messages)

            if self.is_handoff(response):
                handoff_count += 1
                # Audit log
                self.log_handoff(current_agent.name, next_agent.name, reason)
                current_agent = next_agent
            else:
                return response.final_text
```

### Monitoring
```python
# Har handoff ko trace karo
import time

class TracedSwarm:
    def log_handoff(self, from_agent: str, to_agent: str, reason: str):
        print(json.dumps({
            "event": "agent_handoff",
            "from": from_agent,
            "to": to_agent,
            "reason": reason,
            "timestamp": time.time(),
            "trace_id": self.trace_id,  # OTel trace se link
        }))
```

---

## Interview Q&A

**Q: Swarm aur Supervisor pattern me fundamental difference kya hai?**
A: Supervisor me ek central agent hota hai jo sab decisions leta hai — "kaunsa agent next?" Swarm me agents khud decide karte hain ki kis ko handoff karna hai — decentralized. Supervisor = more control + more latency (extra LLM call). Swarm = faster + simpler par harder to debug (non-linear flow).

**Q: Swarm me state management kaise hoti hai?**
A: `context_variables` dict se — yeh ek mutable dict hai jo sab agents ke beech share hoti hai. Koi bhi agent is dict ko update kar sakta hai aur next agent woh values read kar sakta hai. Limitation: sirf simple key-value state — complex state ke liye LangGraph ke State object better hain.

**Q: Swarm me infinite loop kaise rokein?**
A: Max handoffs counter + cycle detection (agent history track karo, agar same agent dubara aya to stop). OpenAI Swarm library me `max_turns` parameter hota hai. Production me timeout bhi add karo.

**Q: Kab Swarm choose karo, kab LangGraph?**
A: Domain routing clear hai aur linear? → Swarm. Complex branching, conditional logic, parallel paths, checkpointing chahiye? → LangGraph. Swarm simpler hai but less powerful. LangGraph zyada expressive hai but more setup.

---

## Related Topics
- `07_multi_agent_supervisor.md` — Supervisor pattern
- `05_plan_and_execute.md` — Planning pattern
- `03_agent_memory.md` — State management
- `09_human_in_loop.md` — Human confirmation in agentic flows
