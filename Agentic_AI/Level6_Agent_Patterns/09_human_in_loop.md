# Level 6.9 — Human-in-the-Loop (HITL)
**Phase: Agent Patterns | Production-Critical**

## Quick Concepts

- **HITL** = Human reviews / approves / corrects agent actions
- **Approval gate** = agent pauses, waits for human sign-off before acting
- **Active learning** = human corrections feed back to improve agent
- **Confidence-based escalation** = auto-handle high confidence, route low to human
- **Async HITL** = agent emits event → notification → human responds later
- **Sync HITL** = real-time chat with human takeover option
- **Auditable trail** = log all human interventions for compliance

---

## Why HITL Matters

```
Pure-autonomous agents fail when:
   ✗ Stakes are high (money, legal, safety)
   ✗ Edge cases not in training
   ✗ Compliance requires human accountability
   ✗ Domain-specific judgment needed

HITL benefits:
   ✓ Safety net for irreversible actions
   ✓ Human gets fewer queries (only hard ones)
   ✓ Better than full-manual (10x throughput)
   ✓ Builds training data for future autonomy
   ✓ Compliance + audit trails
```

### Common HITL Use Cases

```
✓ Approving refunds / discounts
✓ Customer support escalation
✓ Legal document review
✓ Medical diagnoses
✓ Code deployment approval
✓ Money movement (transfers, payouts)
✓ Content moderation
✓ Sales lead qualification
```

---

## Pattern 1: Approval Gate (Sync)

Agent pauses for human approval before acting:

```python
from enum import Enum


class ActionStatus(Enum):
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"


class HITLAgent:
    def __init__(self, approval_callback):
        self.approval_callback = approval_callback  # function: action → bool
    
    async def execute_with_approval(self, action: dict):
        # High-stakes action: needs approval
        if self._needs_approval(action):
            approved = await self.approval_callback(action)
            if not approved:
                return {"status": "rejected", "reason": "Human declined"}
        
        # Execute
        result = await self._do_action(action)
        return {"status": "completed", "result": result}
    
    def _needs_approval(self, action: dict) -> bool:
        """Define rules: which actions need approval."""
        if action["type"] == "send_money" and action["amount"] > 10000:
            return True
        if action["type"] == "delete_user":
            return True
        if action.get("confidence", 1.0) < 0.7:
            return True
        return False
```

### Slack Approval Callback Example

```python
import asyncio
from slack_sdk.web.async_client import AsyncWebClient


slack = AsyncWebClient(token="...")


async def slack_approval(action: dict) -> bool:
    """Send approval request to Slack, wait for response."""
    
    # Post message with approve/reject buttons
    msg = await slack.chat_postMessage(
        channel="#agent-approvals",
        text=f"Approval needed for {action['type']}",
        blocks=[
            {"type": "section", "text": {"type": "mrkdwn", "text": f"```{json.dumps(action, indent=2)}```"}},
            {
                "type": "actions",
                "elements": [
                    {"type": "button", "text": {"type": "plain_text", "text": "Approve"},
                     "value": "approve", "action_id": "approve"},
                    {"type": "button", "text": {"type": "plain_text", "text": "Reject"},
                     "value": "reject", "action_id": "reject", "style": "danger"},
                ],
            },
        ],
    )
    
    # Wait for response (interaction webhook)
    decision = await wait_for_slack_decision(msg["ts"], timeout=600)  # 10 min
    return decision == "approve"
```

---

## Pattern 2: Confidence-Based Escalation

```python
async def handle_with_escalation(query: str, conversation_history: list):
    """Agent handles or escalates based on confidence."""
    
    # Agent attempts to handle
    response, confidence = await agent.respond(query, history=conversation_history)
    
    if confidence > 0.85:
        # High confidence: return directly
        return {"source": "agent", "response": response, "confidence": confidence}
    
    elif confidence > 0.5:
        # Medium: show response but flag uncertain
        return {
            "source": "agent_uncertain",
            "response": response,
            "confidence": confidence,
            "show_disclaimer": True,
        }
    
    else:
        # Low: escalate to human
        ticket_id = await create_human_ticket(query, conversation_history, response)
        return {
            "source": "escalated",
            "response": "Let me connect you with a specialist. They'll respond within 1 hour.",
            "ticket_id": ticket_id,
        }
```

---

## Pattern 3: Async HITL (Long-Running Workflows)

For actions that don't need immediate response:

```python
# Database to track pending approvals
class PendingAction:
    id: str
    action: dict
    status: str  # pending / approved / rejected
    requested_at: datetime
    decided_at: datetime | None
    decided_by: str | None
    notes: str | None


async def request_approval_async(action: dict) -> str:
    """Submit approval request, return immediately."""
    pending = PendingAction(
        id=str(uuid.uuid4()),
        action=action,
        status="pending",
        requested_at=datetime.utcnow(),
    )
    await db.save(pending)
    
    # Notify approvers (email, Slack, etc.)
    await notify_approvers(pending)
    
    return pending.id


@app.post("/approvals/{action_id}/decide")
async def decide(action_id: str, decision: dict, current_user: User):
    pending = await db.get(action_id)
    pending.status = decision["status"]
    pending.decided_at = datetime.utcnow()
    pending.decided_by = current_user.email
    pending.notes = decision.get("notes")
    await db.save(pending)
    
    if pending.status == "approved":
        # Resume the workflow
        await execute_action(pending.action)
    
    return {"ok": True}
```

This decouples agent flow from human response time.

---

## Pattern 4: LangGraph Interrupt (Sync HITL)

LangGraph has built-in `interrupt` for HITL:

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver


def execute_action(state):
    # ... do work
    return state


def human_review_node(state):
    """Interrupt here, wait for human input."""
    # Returns state including action that needs approval
    return state


def should_review(state):
    if state.get("requires_approval"):
        return "review"
    return "execute"


graph = StateGraph(dict)
graph.add_node("plan", planner)
graph.add_node("review", human_review_node)
graph.add_node("execute", execute_action)

graph.add_conditional_edges("plan", should_review)
graph.add_edge("execute", END)

# Interrupt before review node — human can inspect state
compiled = graph.compile(
    checkpointer=MemorySaver(),
    interrupt_before=["review"],
)


# Run
config = {"configurable": {"thread_id": "1"}}
for event in compiled.stream({"query": "delete user 42"}, config):
    print(event)
# Stops at "review" — agent paused, state saved

# Human reviews state via UI
# To resume:
compiled.invoke(None, config)  # continues from where it stopped
```

---

## Pattern 5: Active Learning (Feedback Loop)

Capture human corrections to improve agent:

```python
async def handle_with_learning(query: str):
    # Agent response
    agent_response = await agent.respond(query)
    
    # Show to user (or human supervisor)
    user_feedback = await get_user_feedback(agent_response)
    
    # Store for learning
    feedback_event = {
        "query": query,
        "agent_response": agent_response,
        "user_rating": user_feedback.get("rating"),  # 1-5
        "user_correction": user_feedback.get("correction"),
        "timestamp": datetime.utcnow(),
    }
    await db.log_feedback(feedback_event)
    
    # If correction provided, use it
    if user_feedback.get("correction"):
        return user_feedback["correction"]
    return agent_response


# Periodically:
# 1. Aggregate low-rated responses
# 2. Use as fine-tuning data OR few-shot examples
# 3. Update agent prompts/configs
```

---

## Pattern 6: Supervised Chat (Real-Time Override)

Customer chats with bot, agent can take over:

```python
class SupervisedChatSession:
    def __init__(self, session_id):
        self.id = session_id
        self.mode = "bot"  # "bot" / "agent_observing" / "human"
        self.messages = []
        self.assigned_human = None
    
    async def handle_message(self, user_message: str):
        if self.mode == "human":
            # Just forward to human, don't bot-respond
            await self.notify_human(user_message)
            return None
        
        # Bot generates response
        bot_reply = await agent.respond(user_message, self.messages)
        
        # If human is observing, show before sending
        if self.mode == "agent_observing":
            human_decision = await self.ask_human_supervisor(
                {"user_msg": user_message, "bot_reply": bot_reply}
            )
            if human_decision["action"] == "approve":
                final_reply = bot_reply
            elif human_decision["action"] == "modify":
                final_reply = human_decision["text"]
            elif human_decision["action"] == "take_over":
                self.mode = "human"
                self.assigned_human = human_decision["agent_id"]
                final_reply = await self.wait_for_human()
        else:
            final_reply = bot_reply
        
        self.messages.append({"role": "user", "content": user_message})
        self.messages.append({"role": "assistant", "content": final_reply})
        return final_reply
```

---

## UI Patterns for HITL

### Inline Confidence Indicators

```
┌────────────────────────────────────────────────────┐
│  💬 You: What's my refund policy?                 │
│                                                    │
│  🤖 Bot (confident): We offer 30-day refunds.     │
│                                                    │
│  💬 You: I want a $500 refund                     │
│                                                    │
│  🤖 Bot (uncertain — sent to specialist):         │
│      A team member will review and respond within  │
│      1 hour. Ticket #1234                          │
└────────────────────────────────────────────────────┘
```

### Action Preview + Confirm

```
┌────────────────────────────────────────────────────┐
│  Agent wants to:                                   │
│                                                    │
│  📤 Send refund of $500 to john@example.com       │
│                                                    │
│  Reason: User reports product defect               │
│  Confidence: 75%                                   │
│                                                    │
│  [Approve]  [Reject]  [Modify]                     │
└────────────────────────────────────────────────────┘
```

### Side-by-Side Edit

```
Agent's draft:                | Your edit:
─────────────────────────────|──────────────────────
"We can offer you 20% off    | "We can offer you 15% off
your next order as           | your next order plus
compensation."               | free shipping."
                             |
[Send Draft]                 | [Send Edited]
```

---

## HITL with FastAPI + Background Workflow

```python
from fastapi import FastAPI, BackgroundTasks
from temporalio.client import Client

app = FastAPI()


@app.post("/agent/task")
async def start_agent_task(task: dict):
    """Start agent workflow, may pause for human."""
    client = await Client.connect("localhost:7233")
    handle = await client.start_workflow(
        AgentWorkflow.run,
        args=[task],
        id=f"agent-{task['id']}",
        task_queue="agents",
    )
    return {"workflow_id": handle.id}


@app.post("/approvals/{workflow_id}/decide")
async def approve_action(workflow_id: str, decision: dict):
    """Human approval callback."""
    client = await Client.connect("localhost:7233")
    handle = client.get_workflow_handle(workflow_id)
    # Send signal to workflow
    await handle.signal(AgentWorkflow.human_decision, decision)
    return {"ok": True}


# Workflow side (Temporal)
@workflow.defn
class AgentWorkflow:
    def __init__(self):
        self.decision = None
    
    @workflow.signal
    def human_decision(self, decision: dict):
        self.decision = decision
    
    @workflow.run
    async def run(self, task: dict):
        # Agent decides on action
        action = await workflow.execute_activity(agent_decide, task)
        
        if action["needs_approval"]:
            # Notify human
            await workflow.execute_activity(notify_approvers, action)
            
            # Wait for human signal
            await workflow.wait_condition(
                lambda: self.decision is not None,
                timeout=timedelta(hours=24),
            )
            
            if self.decision["status"] != "approved":
                return {"status": "rejected"}
        
        # Execute
        return await workflow.execute_activity(execute_action, action)
```

→ Workflow survives weeks-long human delays without holding resources.

---

## Choosing When to Loop in Humans

```python
def hitl_decision(action: dict, agent_confidence: float) -> bool:
    """Return True if human should review."""
    
    # ALWAYS for irreversible / high-stakes
    if action["type"] in ("delete_user", "send_money", "publish_content"):
        return True
    
    # Amount thresholds
    if action.get("amount", 0) > 10000:
        return True
    
    # Confidence threshold
    if agent_confidence < 0.7:
        return True
    
    # Tenant-specific rules (some tenants require approval for everything)
    if action["tenant_id"] in REQUIRE_APPROVAL_TENANTS:
        return True
    
    # Random sampling for QA (5% of high-confidence actions)
    if random.random() < 0.05 and agent_confidence < 0.95:
        return True
    
    return False
```

---

## Metrics to Track

```python
class HITLMetrics:
    """Track HITL effectiveness."""
    
    def daily_summary(self, date):
        return {
            "total_actions": ...,
            "auto_handled": ...,
            "human_approved": ...,
            "human_rejected": ...,
            "escalation_rate": ...,  # % needing human
            "human_response_time_p50": ...,
            "human_response_time_p99": ...,
            "rejection_rate": ...,  # % humans say "no" to agent
            "false_positives": ...,  # human approved, was actually wrong
            "false_negatives": ...,  # auto-handled, should've escalated
        }
```

Key insight: aim to **reduce escalation rate over time** as agent learns.

---

## Common Pitfalls

```
1. ✗ Every action needs approval → human overwhelmed
   ✓ Auto-handle high confidence

2. ✗ Long timeouts without escalation
   → User waits hours
   ✓ Backup approvers, escalation chains

3. ✗ Agent waits indefinitely for human
   → Tied-up resources
   ✓ Use durable workflows (Temporal) or async patterns

4. ✗ No audit trail
   ✓ Log every action, decision, human

5. ✗ Human can't see agent's reasoning
   → Bad approvals
   ✓ Show agent's plan + confidence + reasoning

6. ✗ Approval UI hard to use
   → Humans skip / approve everything
   ✓ Make rejection easy + faster than approval

7. ✗ Not using human feedback to improve agent
   → Same questions asked over and over
   ✓ Active learning loop

8. ✗ Mixing sync + async without clarity
   → Confusing UX
   ✓ Be explicit: "Specialist will reply within X"
```

---

## Compliance + Audit

```python
@dataclass
class AuditEvent:
    timestamp: datetime
    action: dict
    agent_decision: str
    confidence: float
    human_required: bool
    human_decision: str | None
    human_id: str | None
    final_outcome: dict
    
    def to_log_entry(self):
        return {
            "ts": self.timestamp.isoformat(),
            "actor": self.human_id or "agent",
            "action_type": self.action["type"],
            "approved_by_human": self.human_required,
            "outcome": self.final_outcome,
            ...
        }
```

For regulated industries (finance, healthcare):
- Store every human decision permanently
- Include agent reasoning at time of decision
- Sign / timestamp records (tamper-evident)
- Support legal review queries

---

## Interview Questions

### Q1: When should an agent NOT make decisions autonomously?

(1) Irreversible actions (deletes, financial transactions). (2) High-stakes amounts above threshold. (3) Low confidence on critical paths. (4) Regulatory requirements (some actions require human accountability). (5) Edge cases not seen in training.

### Q2: How do you avoid overwhelming humans with approval requests?

Confidence-based routing — only escalate low-confidence or high-stakes. Random sampling — 5% of high-confidence for QA. Batch approvals — group similar decisions. Async patterns — humans approve when they have time, not real-time blocking.

### Q3: How do you build a "feedback loop" from human corrections?

Log every (agent_response, human_correction) pair. Use for: (a) few-shot examples in future prompts, (b) fine-tuning data, (c) flagging weak topics for prompt engineering, (d) measuring agent improvement over time.

### Q4: How do you handle a human approval that doesn't come in time?

Strategies: (1) Timeout → safe default (usually "reject"). (2) Escalation chain → backup approvers. (3) Auto-cancel + notify user. (4) For Temporal-style workflows: workflow survives indefinitely, picks up whenever human responds.

### Q5: Difference between sync and async HITL?

**Sync**: agent blocks waiting for human (interactive chat, real-time approval UI). Good UX but ties up resources during wait. **Async**: agent submits request and returns; human responds later via webhook/UI; workflow resumes. Better for long delays + scale.

---

## Senior Mantras

```
1. HITL = safety + compliance, not "agent is bad at job".

2. Escalate intelligently — confidence + stakes-based.

3. Audit everything. Future-you will thank you.

4. Async HITL > sync for non-urgent actions.

5. Make rejection as easy as approval. Reduce rubber-stamping.

6. Use durable workflows for long-running HITL.

7. Track escalation rate — should decrease over time.

8. Active learning: feed human corrections back to agent.

9. Show agent reasoning to humans. Better decisions.

10. Some actions ALWAYS need humans. Not all automation is good.
```

---

## Related

- [04_react_pattern.md](04_react_pattern.md) — ReAct + approval gate
- [07_multi_agent_supervisor.md](07_multi_agent_supervisor.md) — supervisor escalation
- [10_agent_evaluation.md](10_agent_evaluation.md) — measuring HITL quality
- [../Level8_Production_LLMOps/09_guardrails.md](../Level8_Production_LLMOps/09_guardrails.md) — safety + guardrails
- [../../Backend_Developer/Phase3_Microservices/15_temporal_durable_workflows.md](../../Backend_Developer/Phase3_Microservices/15_temporal_durable_workflows.md) — durable workflows for HITL
