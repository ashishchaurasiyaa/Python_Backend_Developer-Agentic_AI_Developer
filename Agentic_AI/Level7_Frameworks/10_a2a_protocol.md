# A2A (Agent2Agent Protocol) — Agent Interoperability Across Vendors/Frameworks

## Quick Concepts
- **A2A** = Google-led open protocol (donated to Linux Foundation) letting AI agents built on DIFFERENT frameworks/vendors discover and collaborate with each other
- **Agent Card** = a JSON metadata document an agent publishes describing its capabilities, skills, and how to reach it — the A2A equivalent of an OpenAPI spec, but for agents
- **Task** = the unit of work one agent delegates to another over A2A — has a lifecycle (submitted → working → completed/failed)
- **MCP vs A2A — the distinction interviewers check for:** MCP connects an agent to TOOLS/DATA (agent-to-resource). A2A connects an agent to ANOTHER AGENT (agent-to-agent) — different layer of the stack entirely, complementary not competing

---

## Why It Matters

You already have deep MCP coverage (`04_mcp_complete.md`) — MCP solves "how
does my agent call a tool or read a resource." A2A solves a DIFFERENT
problem that MCP was never designed for: "how does MY agent (built on
LangGraph, say) hand off a task to a DIFFERENT company's agent (built on a
completely different stack) without either side needing custom integration
code per agent." This is an increasingly asked distinction in 2025-26 agentic
interviews as multi-agent systems cross organizational boundaries.

Senior interview: "You're building an agent that needs to delegate a
sub-task to a partner company's agent, and you have no idea what framework
they built it on. How?" → A2A protocol, not a custom API integration per partner.

---

## The Core Architecture

```
Your Agent (LangGraph)                    Partner's Agent (CrewAI, or
                                            any other framework)
        │                                          │
        │  1. Discover: GET partner's Agent Card    │
        │ ─────────────────────────────────────────►│
        │  ◄───── Agent Card (capabilities JSON) ────│
        │                                          │
        │  2. Send Task (via A2A JSON-RPC/HTTP)     │
        │ ─────────────────────────────────────────►│
        │                                          │  (partner agent
        │                                          │   does its work)
        │  3. Receive Task result / status updates  │
        │ ◄─────────────────────────────────────────│
```

Neither side needs to know the other's internal framework, prompting
strategy, or model choice — A2A standardizes only the OUTER communication
contract (discovery format + task lifecycle), leaving each agent free to be
built however its owner wants internally.

---

## Agent Card — the discovery mechanism

```json
{
  "name": "InvoiceProcessingAgent",
  "description": "Extracts and validates invoice data from documents",
  "url": "https://partner.example.com/a2a",
  "capabilities": {
    "streaming": true,
    "pushNotifications": true
  },
  "skills": [
    {
      "id": "extract-invoice-data",
      "name": "Extract Invoice Data",
      "description": "Parses an invoice document and returns structured fields",
      "inputModes": ["application/pdf", "image/png"],
      "outputModes": ["application/json"]
    }
  ]
}
```

This is conceptually the A2A equivalent of an OpenAPI/Swagger spec — any
client (human-written or another agent) can fetch this and programmatically
learn what the agent can do and how to invoke it, without prior
documentation or custom integration work.

---

## Sending a Task (simplified A2A client)

```python
import httpx

async def delegate_task(agent_url: str, task_input: dict) -> dict:
    # 1. Discover capabilities
    card = await httpx.AsyncClient().get(f"{agent_url}/.well-known/agent.json")
    agent_card = card.json()

    # 2. Submit a task, following A2A's JSON-RPC-based task protocol
    response = await httpx.AsyncClient().post(
        agent_url,
        json={
            "jsonrpc": "2.0",
            "method": "tasks/send",
            "params": {
                "id": "task-001",
                "message": {
                    "role": "user",
                    "parts": [{"type": "data", "data": task_input}],
                },
            },
        },
    )
    return response.json()

# Task lifecycle states the caller polls/subscribes to:
# submitted → working → input-required (if the agent needs clarification)
#           → completed | failed | canceled
```

**Streaming/push notifications:** A2A supports Server-Sent Events for
long-running tasks (an agent that takes minutes to finish can stream
intermediate status), or webhook-style push notifications instead of
polling — relevant given your existing SSE coverage in
`13_WebSocket_SSE/02_sse_server_sent_events.md`.

---

## A2A vs MCP — the table interviewers actually want

| | **MCP** | **A2A** |
|---|---|---|
| Connects | Agent ↔ Tool/Data source | Agent ↔ Agent |
| Analogy | Function calling, but standardized across servers | Microservice-to-microservice API, but for agents |
| Who defines the capability | The MCP server (tool provider) | The remote agent itself (via Agent Card) |
| Typical use | Your agent reads a database, calls a search API, runs a calculator | Your agent delegates "book this trip" to a specialized travel-booking agent built by someone else |
| Do you use both together? | Yes — routinely. An agent uses MCP to call ITS OWN tools, and A2A to delegate to OTHER agents when a task is outside its own scope | |

**The one-line answer to memorize:** "MCP is how an agent uses tools. A2A is
how an agent uses OTHER agents. They operate at different layers and are
designed to be used together, not as alternatives to each other."

---

## Interview Q&A

**Q: Why do we need A2A if MCP already lets agents call external functionality?**
A: MCP's model is a tool/resource with a fixed, well-defined interface (a
function signature, effectively) — it's not designed for delegating an
open-ended TASK to another autonomous agent that itself might reason, plan,
and take multiple steps before responding. A2A's task lifecycle
(submitted/working/input-required/completed) fits agent-to-agent delegation,
which is a fundamentally different interaction shape than a tool call.

**Q: How does an agent discover what another agent can do, without prior integration?**
A: It fetches the other agent's Agent Card (a well-known JSON endpoint,
similar in spirit to `/.well-known/` conventions or an OpenAPI spec) —
describing its skills, supported input/output formats, and how to reach it.

**Q: Is A2A vendor-specific to Google, or a true open standard?**
A: It was Google-led originally but was donated to the Linux Foundation as
an open, vendor-neutral protocol specifically so agents built by different
companies on different frameworks can interoperate — the same motivation
that led Anthropic to open MCP rather than keep it proprietary.

---

Related: `04_mcp_complete.md` (agent-to-tool, the complementary protocol),
`Level6_Agent_Patterns/07_multi_agent_supervisor.md` (multi-agent
orchestration WITHIN one framework — A2A extends this concept ACROSS
framework/vendor boundaries).
