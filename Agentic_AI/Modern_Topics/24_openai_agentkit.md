# Modern Topics — Doc 24: OpenAI AgentKit ⭐

> **Goal:** AgentKit = OpenAI ka **agent-building product suite** (DevDay Oct 2025 launch) — visual Agent Builder, embeddable ChatKit UI, Connector Registry, aur agent-focused Evals. Yeh Agents SDK (code framework) ka *product layer* hai, replacement nahi. Interview me "OpenAI stack me production agent kaise ship karoge" ka 2026 answer AgentKit + Agents SDK + Responses API combo hai.

---

## 1. OpenAI ka agent stack — layers samjho

Confusion bahut hoti hai kyunki OpenAI ke paas 4 overlapping cheezein hain:

| Layer | Kya hai | Form |
|---|---|---|
| **Responses API** | Base API — stateful, hosted tools (web_search, file_search, code_interpreter, computer_use), built-in agent loop | API endpoint |
| **Agents SDK** | Code framework — agents, handoffs, guardrails, sessions, tracing (Swarm ka production successor) | Python/JS library |
| **AgentKit** | Product suite us sab ke upar — visual builder, chat UI components, connectors, evals | Platform/products |
| **ChatGPT Apps SDK** | ChatGPT ke andar apps banane ka (alag use case) | SDK |

**AgentKit ke 4 components:**

1. **Agent Builder** — visual canvas (drag-drop nodes) multi-agent workflows design karne ka. Nodes: agent, guardrail, MCP tool, if/else logic, human approval, transform. Versioning + preview runs built-in. Non-engineers bhi workflow bana sakte hain; export karke Agents SDK code bhi milta hai.
2. **ChatKit** — embeddable chat UI toolkit — apne app/website me agent chat interface daalne ka ready-made component (streaming, threads, attachments, widgets). Frontend chat UI khud banana skip.
3. **Connector Registry** — org-level central place jahan admins data sources/tools (Drive, SharePoint, Slack, MCP servers) register + govern karte hain. Compliance/admin story.
4. **Evals for agents** — datasets, **trace grading** (poore agent run ka step-by-step assessment), automated prompt optimization, third-party model support bhi.

---

## 2. Agent Builder — kaise sochta hai

Workflow = graph of nodes (LangGraph jaisa concept, par hosted + visual):

```
User input
   │
   ▼
[Guardrail node]  ── fail ──▶ [Refusal response]
   │ pass
   ▼
[Classifier agent]  "sales" / "support" branch
   │
   ├─ sales ──▶ [Sales agent + CRM MCP tool]
   └─ support ─▶ [Support agent + KB file_search]
                      │
                      ▼
              [Human approval node]   (sensitive actions gate)
                      │
                      ▼
                  Final response
```

Har agent node ke paas: model choice, instructions, tools (hosted + MCP), output schema. Publish karne pe workflow ID milta hai jo ChatKit ya Responses API se invoke hota hai.

## 3. Agents SDK connection (code side)

Agent Builder ke workflows Agents SDK primitives pe hi map hote hain — SDK yaad karo to Builder free me samajh aata hai:

```python
# pip install openai-agents
from agents import Agent, Runner, handoff

support = Agent(name="Support", instructions="Handle support queries via KB.")
sales = Agent(name="Sales", instructions="Handle pricing/demo queries.")

triage = Agent(
    name="Triage",
    instructions="Route the user to the right team.",
    handoffs=[handoff(support), handoff(sales)],   # AgentKit "branch" = SDK handoff
)

result = Runner.run_sync(triage, "Mujhe enterprise pricing chahiye")
print(result.final_output)
```

- **Handoff** = control transfer between agents (Swarm pattern — dekho [11_swarm_agents.md](../Level6_Agent_Patterns/11_swarm_agents.md))
- **Guardrails** = parallel-run validators (input/output) jo trip hone pe run rok dete hain
- **Sessions** = automatic conversation history
- **Tracing** = har run ka step-level trace (Evals isi pe grade karta hai)

## 4. Claude Agent SDK vs OpenAI AgentKit (interview comparison)

| | Claude Agent SDK | OpenAI AgentKit |
|---|---|---|
| Core idea | Claude Code harness as library — ek **capable single agent** (files, bash, code) | Product suite — **multi-agent workflows** visually + UI components |
| Orchestration | Model khud decide karta hai (agentic loop) | Tum explicitly graph design karte ho (Builder) ya handoffs (SDK) |
| Built-in tools | Read/Write/Edit/Bash/Glob/Grep/WebSearch | Hosted: web_search, file_search, code_interpreter, computer_use |
| UI story | Nahi (terminal/headless) | ChatKit embeddable UI |
| Hosting | Tumhara infra | Workflows OpenAI-hosted (Builder) ya self-hosted (SDK) |
| Sweet spot | Coding/filesystem/ops agents | Customer-facing chat agents, business workflows |

## 5. Kab kya

- **Business workflow + non-eng stakeholders + chat UI chahiye** → AgentKit (Builder + ChatKit)
- **Code-first multi-agent, full control, self-host** → OpenAI Agents SDK ya LangGraph
- **Coding/filesystem agent** → Claude Agent SDK ([23_claude_agent_sdk_skills.md](23_claude_agent_sdk_skills.md))
- **Vendor-neutral graph orchestration** → LangGraph

## 6. Interview Angle

**Q: AgentKit aur Agents SDK me kya relation hai?**
AgentKit product layer hai, Agents SDK code framework. Agent Builder visually jo workflow banata hai wo Agents SDK ke primitives (agents, handoffs, guardrails) pe hi chalta hai — Builder se SDK code export bhi hota hai. SDK akela use kar sakte ho; AgentKit us pe UI, governance (Connector Registry), aur evals add karta hai.

**Q: Trace grading kya hai aur normal eval se alag kaise?**
Normal eval = final answer grade karo. Trace grading = poore agent run ka har step assess karo — kya sahi tool chuna, kya handoff sahi tha, kahan waste hua. Multi-step agents me final answer sahi ho sakta hai galat (expensive/fragile) path se — trace grading wahi pakadta hai.

**Q: Guardrail node ko system prompt instruction se behtar kyun mante ho?**
Guardrail separate validator hai jo main model ke *bahar* chalta hai — prompt injection se main agent compromise ho bhi jaye to guardrail independently trip karta hai. System prompt instruction usi context me hai jo attacker manipulate kar raha hai. (Same logic Claude side pe hooks ka — dekho doc 23 §5.)

---

## Related
- Responses API (AgentKit ka base API) → [12_openai_responses_api.md](12_openai_responses_api.md)
- Swarm/handoff pattern → [../Level6_Agent_Patterns/11_swarm_agents.md](../Level6_Agent_Patterns/11_swarm_agents.md)
- Claude equivalent → [23_claude_agent_sdk_skills.md](23_claude_agent_sdk_skills.md)
- Agent evaluation (RAGAS, OpenAI Evals) → [../Level6_Agent_Patterns/10_agent_evaluation.md](../Level6_Agent_Patterns/10_agent_evaluation.md)
