"""
Level 6.9 — Human-in-the-Loop (HITL) PRACTICAL
===============================================
KYA SEEKHENGE (What we will learn):
  1. Approval Gate — agent ruka, human ne haan/naa boli, phir action hua
  2. Confidence-Based Escalation — high confidence auto-handle, low confidence human ke paas
  3. Async HITL — approval request submit karo, baad mein decide karo
  4. Active Learning Feedback Loop — human corrections se agent seekhta hai
  5. Supervised Chat Session — bot chal raha hai, human kabhi bhi override kar sakta hai
  6. Audit Trail — har decision log hota hai compliance ke liye
  7. HITL Metrics — escalation rate, rejection rate track karna

KAISE CHALANA (How to run):
  uv run --project /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/my-agentic-ai-project \\
      python /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/Level6_Agent_Patterns/09_human_in_loop_practical.py

  No key chahiye — sab kuch offline demo chalega aur EXIT 0 hoga.
  GROQ_API_KEY set karo live LLM demo ke liye (optional).

THEORY LINK: Level6_Agent_Patterns/09_human_in_loop.md
"""

import os
import json
import uuid
import random
import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Callable


# ─────────────────────────────────────────────────────────────────────────────
# LLM CLIENT SETUP — Groq free tier default, crashes safely with no key
# ─────────────────────────────────────────────────────────────────────────────

def get_client():
    """
    Groq client banata hai. Agar key nahi hai toh placeholder use karo —
    OpenAI() constructor None key pe crash karta hai, isliye yahan
    api_key="placeholder" safely pass hota hai; actual call pe error aayega
    jo hum try/except mein pakad lete hain.
    """
    from openai import OpenAI
    return OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=os.getenv("GROQ_API_KEY") or "placeholder",
    )


GROQ_KEY_HAI = bool(os.getenv("GROQ_API_KEY"))
LIVE_MODE = GROQ_KEY_HAI  # sirf key hone pe live calls


def llm_call(prompt: str, system: str = "You are a helpful assistant.",
             model: str = "llama3-8b-8192", max_tokens: int = 200) -> str:
    """
    LLM ko call karo. Agar key nahi ya error aaya toh fake response return karo.
    Graceful degradation — key nahi hai toh bhi program chalta hai.
    """
    if not LIVE_MODE:
        # Offline mode — fake response
        return f"[OFFLINE MOCK] Query processed: {prompt[:60]}..."

    try:
        client = get_client()
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
            temperature=0.3,
        )
        return resp.choices[0].message.content or "[empty response]"
    except Exception as e:
        return f"[LLM Error — offline fallback] {str(e)[:80]}"


# ─────────────────────────────────────────────────────────────────────────────
# ENUMS & DATACLASSES — Theory se directly liye gaye structures
# ─────────────────────────────────────────────────────────────────────────────

class ActionStatus(Enum):
    """
    Theory Pattern 1 se: action ka status track karna.
    PENDING = ruka hua, APPROVED = human ne haan bola, REJECTED = human ne naa bola.
    """
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class Action:
    """
    Ek agent action represent karta hai — kya karna chahta hai agent?
    Theory se: approval gate, confidence, high-stakes fields.
    """
    type: str                   # jaise "send_money", "delete_user", "send_email"
    payload: dict               # action ke details
    confidence: float = 1.0     # agent kitna confident hai (0.0 to 1.0)
    amount: float = 0.0         # agar money involved hai
    tenant_id: str = "default"  # multi-tenant rules ke liye
    action_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    status: ActionStatus = ActionStatus.PENDING_APPROVAL


@dataclass
class AuditEvent:
    """
    Theory se: compliance ke liye har decision log karo.
    Finance, healthcare mein yeh mandatory hota hai.
    """
    timestamp: str
    action_type: str
    confidence: float
    human_required: bool
    human_decision: Optional[str]
    human_id: Optional[str]
    final_outcome: str
    action_id: str

    def to_log_entry(self) -> dict:
        """Audit log mein convert karo — tamper-evident format."""
        return {
            "ts": self.timestamp,
            "actor": self.human_id or "agent_autonomous",
            "action_type": self.action_type,
            "confidence": self.confidence,
            "approved_by_human": self.human_required,
            "human_decision": self.human_decision,
            "outcome": self.final_outcome,
            "action_id": self.action_id,
        }


# Global audit log — production mein DB mein jayega
AUDIT_LOG: List[AuditEvent] = []

def record_audit(action: Action, human_required: bool,
                 human_decision: Optional[str], outcome: str,
                 human_id: Optional[str] = None):
    """Har HITL decision ko audit log mein daal do."""
    event = AuditEvent(
        timestamp=datetime.utcnow().isoformat(),
        action_type=action.type,
        confidence=action.confidence,
        human_required=human_required,
        human_decision=human_decision,
        human_id=human_id,
        final_outcome=outcome,
        action_id=action.action_id,
    )
    AUDIT_LOG.append(event)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: HITL DECISION LOGIC
# Theory: hitl_decision() function — kab human ko loop mein laana hai
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 65)
print("SECTION 1: HITL Decision Logic — Kab Human Ko Bulana Hai?")
print("=" * 65)

# Theory se directly: HIGH_STAKES_ACTIONS always need approval
HIGH_STAKES_ACTIONS = {"delete_user", "send_money", "publish_content", "deploy_prod"}

# Kuch tenants pe special rules hain
REQUIRE_APPROVAL_TENANTS = {"enterprise_client_A", "regulated_bank_B"}


def hitl_decision(action: Action, agent_confidence: float) -> bool:
    """
    Theory Pattern: Kab human ko loop mein lana chahiye?

    Rules in order:
    1. Irreversible / high-stakes actions — HAMESHA human
    2. Zyada paisa — human
    3. Kam confidence — human
    4. Special tenants — human
    5. Random QA sampling (5%) — human
    6. Baaki sab — auto-handle
    """

    # Rule 1: High-stakes action — bilkul nahi autonomous
    if action.type in HIGH_STAKES_ACTIONS:
        return True

    # Rule 2: Amount threshold — 10,000 se zyada toh ruko
    if action.amount > 10_000:
        return True

    # Rule 3: Confidence threshold — 70% se kam matlab uncertain
    if agent_confidence < 0.7:
        return True

    # Rule 4: Tenant-specific rules
    if action.tenant_id in REQUIRE_APPROVAL_TENANTS:
        return True

    # Rule 5: Random QA sampling — 5% high-confidence actions bhi check karo
    if random.random() < 0.05 and agent_confidence < 0.95:
        return True

    # Sab rules pass — autonomous chal sakta hai
    return False


# --- Demo: alag-alag actions test karo ---
test_actions = [
    Action(type="send_email",   payload={"to": "user@example.com"}, confidence=0.95, amount=0),
    Action(type="send_money",   payload={"to": "vendor", "amount": 500}, confidence=0.90, amount=500),
    Action(type="send_money",   payload={"to": "contractor"}, confidence=0.88, amount=50_000),
    Action(type="delete_user",  payload={"user_id": "u42"}, confidence=0.99, amount=0),
    Action(type="update_profile", payload={"field": "email"}, confidence=0.55, amount=0),
    Action(type="send_report",  payload={}, confidence=0.92, amount=0, tenant_id="regulated_bank_B"),
]

print("\nHITL Decision Table:")
print(f"  {'Action':<20} {'Confidence':>11} {'Amount':>10} {'Human Needed?':>15}")
print("  " + "-" * 60)
for act in test_actions:
    needs_human = hitl_decision(act, act.confidence)
    marker = "YES — Human!" if needs_human else "auto"
    print(f"  {act.type:<20} {act.confidence:>11.0%} {act.amount:>10,.0f} {marker:>15}")

print("\nInterview insight: Confidence + stakes-based routing — human sirf zaroorat pe aata hai.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: APPROVAL GATE (SYNC HITL) — Pattern 1
# Theory: Agent ruka, human ne approve/reject kiya, phir action hua
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 2: Approval Gate (Sync HITL) — Agent Ruka, Human Ne Decide Kiya")
print("=" * 65)


def mock_human_approval_callback(action: Action, reviewer_id: str = "reviewer_01") -> tuple[bool, str]:
    """
    Real system mein: Slack message, email, ya UI se approval aata.
    Yahan hum simulate kar rahe hain — production code ke baad comments mein
    Slack SDK example bhi hai.

    Returns: (approved: bool, notes: str)
    """
    # Simulation: action type pe based auto-decision (in real app: human input)
    if action.type == "delete_user":
        # Delete operations pe zyada scrutiny — 30% chance reject
        approved = random.random() > 0.3
        notes = "Approved: user consent verified." if approved else "Rejected: missing consent form."
    elif action.amount > 10_000:
        # Bade transactions pe 80% approval rate
        approved = random.random() > 0.2
        notes = "Approved: budget allocated." if approved else "Rejected: exceeds quarterly limit."
    else:
        # Default: 90% approval
        approved = random.random() > 0.1
        notes = "Approved." if approved else "Rejected: policy violation."

    print(f"    [Human '{reviewer_id}'] Decision: {'APPROVED' if approved else 'REJECTED'} — {notes}")
    return approved, notes


class HITLAgent:
    """
    Theory Pattern 1: Approval Gate.
    Agent har action se pehle check karta hai: kya human approval chahiye?
    Agar haan, toh ruko — callback se pata karo.
    """

    def __init__(self, approval_callback: Callable):
        self.approval_callback = approval_callback
        self.actions_taken: List[dict] = []

    def _needs_approval(self, action: Action) -> bool:
        """Delegate to central HITL decision function."""
        return hitl_decision(action, action.confidence)

    def execute(self, action: Action) -> dict:
        """
        Action execute karo — approval gate ke saath.
        High-stakes actions pe ruko, low-stakes pe seedha chalo.
        """
        needs_human = self._needs_approval(action)

        if needs_human:
            print(f"  [Agent] Action '{action.type}' needs human approval (confidence={action.confidence:.0%})")
            approved, notes = self.approval_callback(action)

            if not approved:
                record_audit(action, human_required=True,
                             human_decision="rejected", outcome="action_cancelled")
                return {
                    "status": "rejected",
                    "action_id": action.action_id,
                    "reason": notes,
                }
            record_audit(action, human_required=True,
                         human_decision="approved", outcome="action_executed")
        else:
            # Auto-handle — no human in loop
            print(f"  [Agent] Auto-handling '{action.type}' (confidence={action.confidence:.0%}, no approval needed)")
            record_audit(action, human_required=False,
                         human_decision=None, outcome="auto_executed")

        # Action execute karo (yahan business logic hogi)
        result = self._do_action(action)
        self.actions_taken.append({
            "action_id": action.action_id,
            "type": action.type,
            "human_reviewed": needs_human,
        })
        return {"status": "completed", "result": result, "action_id": action.action_id}

    def _do_action(self, action: Action) -> str:
        """Actual action execution — yahan real API calls honge."""
        return f"Executed: {action.type} with payload {list(action.payload.keys())}"


# --- Demo ---
random.seed(42)  # reproducible output ke liye
agent = HITLAgent(approval_callback=mock_human_approval_callback)

demo_actions = [
    Action(type="send_email",  payload={"to": "alice@co.com", "subject": "invoice"}, confidence=0.97),
    Action(type="send_money",  payload={"to": "vendor_X", "desc": "payment"}, confidence=0.89, amount=75_000),
    Action(type="delete_user", payload={"user_id": "u99"}, confidence=0.95),
    Action(type="update_tag",  payload={"tag": "premium"}, confidence=0.80),
]

print("\nApproval Gate Demo:")
for act in demo_actions:
    print(f"\n  Queuing action: '{act.type}' (amount={act.amount:,.0f})")
    result = agent.execute(act)
    print(f"  Result: status={result['status']}")

print("\nInterview: Approval gate = agent pauses, human approves/rejects, then resume.")

# Slack approval code pattern (comment mein — library optional)
print("""
  Slack Approval Pattern (production mein):
    # await slack.chat_postMessage(
    #     channel="#agent-approvals",
    #     blocks=[approve_button, reject_button]
    # )
    # decision = await wait_for_slack_decision(msg_ts, timeout=600)
    # return decision == "approve"
""")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: CONFIDENCE-BASED ESCALATION — Pattern 2
# Theory: High confidence = auto-handle, medium = disclaimer, low = escalate
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 65)
print("SECTION 3: Confidence-Based Escalation — Theory Pattern 2")
print("=" * 65)


def create_human_ticket(query: str, history: List[dict], agent_response: str) -> str:
    """
    Low confidence pe human ticket create karo.
    Production mein: Zendesk/Jira API call hogi.
    """
    ticket_id = f"TICKET-{random.randint(1000, 9999)}"
    print(f"    [Ticket System] Created {ticket_id} for query: '{query[:40]}...'")
    return ticket_id


def handle_with_escalation(query: str, conversation_history: List[dict]) -> dict:
    """
    Theory Pattern 2: Confidence threshold pe routing.
    > 0.85 = agent handle karta hai (confident)
    0.5-0.85 = agent handle karta hai lekin disclaimer ke saath
    < 0.50 = human ko escalate karo
    """
    # LLM se response + confidence simulate karo
    if LIVE_MODE:
        raw = llm_call(
            prompt=f"Answer this customer query: {query}\n\nAlso estimate your confidence (0-1) in the last line as 'CONFIDENCE: X.XX'",
            system="You are a customer support agent. Always end with CONFIDENCE: X.XX",
            max_tokens=150,
        )
        # Parse confidence
        confidence = 0.75  # fallback
        for line in raw.split("\n"):
            if "CONFIDENCE:" in line:
                try:
                    confidence = float(line.split(":")[-1].strip())
                except ValueError:
                    pass
        response = raw
    else:
        # Offline mode — simulate alag queries ke liye alag confidence
        mock_responses = {
            "refund policy": (0.92, "Hum 30-day refund policy follow karte hain."),
            "transfer money": (0.45, "Main is transaction ke baare mein sure nahi hoon."),
            "order status": (0.78, "Aapka order processing mein hai, estimated delivery 3 din."),
        }
        key = next((k for k in mock_responses if k in query.lower()), None)
        if key:
            confidence, response = mock_responses[key]
        else:
            confidence = random.uniform(0.4, 0.95)
            response = f"Query '{query[:30]}' ke baare mein: [mock agent response]"

    # Confidence-based routing
    if confidence > 0.85:
        return {
            "source": "agent_confident",
            "response": response,
            "confidence": confidence,
            "show_disclaimer": False,
        }
    elif confidence > 0.5:
        return {
            "source": "agent_uncertain",
            "response": response,
            "confidence": confidence,
            "show_disclaimer": True,
            "disclaimer": "Yeh response approximate hai — ek specialist se verify karo.",
        }
    else:
        ticket_id = create_human_ticket(query, conversation_history, response)
        return {
            "source": "escalated_to_human",
            "response": "Aapko ek specialist se connect kar rahe hain. 1 ghante mein reply milega.",
            "ticket_id": ticket_id,
            "confidence": confidence,
        }


# --- Demo ---
test_queries = [
    "What is your refund policy?",
    "What is my order status for order #5678?",
    "I want to transfer money to an international account, is it safe?",
]

print("\nConfidence-Based Escalation Demo:")
history: List[dict] = []
for q in test_queries:
    print(f"\n  User: {q}")
    result = handle_with_escalation(q, history)
    src = result["source"]
    conf = result["confidence"]
    print(f"  Source: {src} (confidence={conf:.0%})")
    print(f"  Response: {result['response'][:100]}")
    if result.get("show_disclaimer"):
        print(f"  Disclaimer: {result['disclaimer']}")
    if result.get("ticket_id"):
        print(f"  Ticket: {result['ticket_id']}")

print("\nInterview: Confidence routing = human sirf tab aata hai jab agent unsure ho.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: ASYNC HITL — Pattern 3
# Theory: Agent approval request submit karta hai, immediately return karta hai
# Human baad mein decide karta hai — durable workflow ke liye perfect
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 4: Async HITL — Submit Karo, Baad Mein Decide Karo")
print("=" * 65)


@dataclass
class PendingApproval:
    """
    Theory Pattern 3: Pending approval record.
    In-memory dict yahan hai, production mein DB hoga (PostgreSQL, etc.)
    """
    approval_id: str
    action: Action
    status: str = "pending"     # pending / approved / rejected
    requested_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    decided_at: Optional[str] = None
    decided_by: Optional[str] = None
    notes: Optional[str] = None


# In-memory "database" — production mein real DB use karo
PENDING_APPROVALS: dict[str, PendingApproval] = {}


def request_approval_async(action: Action) -> str:
    """
    Theory se: Async HITL — request submit karo aur immediately return karo.
    Agent blocked nahi hota — resources free rehte hain.
    """
    pending = PendingApproval(
        approval_id=str(uuid.uuid4())[:12],
        action=action,
    )
    PENDING_APPROVALS[pending.approval_id] = pending

    # Production mein: await notify_approvers(pending) — email, Slack, etc.
    print(f"    [Async HITL] Approval {pending.approval_id} submitted for '{action.type}'")
    print(f"    [Async HITL] Approvers notified via email/Slack — agent continues other work")

    return pending.approval_id


def human_decide(approval_id: str, decision: str,
                 decided_by: str, notes: str = "") -> dict:
    """
    Human ka decision record karo — webhook ya UI callback se aata hai.
    Theory se: POST /approvals/{action_id}/decide endpoint.
    """
    if approval_id not in PENDING_APPROVALS:
        return {"error": "Approval ID not found"}

    pending = PENDING_APPROVALS[approval_id]
    pending.status = decision
    pending.decided_at = datetime.utcnow().isoformat()
    pending.decided_by = decided_by
    pending.notes = notes

    if decision == "approved":
        # Workflow resume karo — Temporal signal ya DB update
        print(f"    [System] Action '{pending.action.type}' approved by {decided_by} — resuming workflow")
        record_audit(pending.action, human_required=True,
                     human_decision="approved", outcome="workflow_resumed",
                     human_id=decided_by)
    else:
        print(f"    [System] Action '{pending.action.type}' rejected by {decided_by} — cancelled")
        record_audit(pending.action, human_required=True,
                     human_decision="rejected", outcome="workflow_cancelled",
                     human_id=decided_by)

    return {"ok": True, "approval_id": approval_id, "status": decision}


# --- Demo ---
print("\nAsync HITL Demo:")

# Agent submits requests and moves on
async_actions = [
    Action(type="send_money", payload={"to": "vendor_Y", "amount": 25000}, confidence=0.85, amount=25000),
    Action(type="publish_content", payload={"title": "Q4 Report", "channel": "public"}, confidence=0.88),
]

approval_ids = []
for act in async_actions:
    print(f"\n  Agent: Submitting async approval for '{act.type}'")
    aid = request_approval_async(act)
    approval_ids.append(aid)
    print(f"  Agent: Continuing other work... (not blocked!)")

print(f"\n  [Later — Human reviews queue]")
# Human comes online and makes decisions
human_decide(approval_ids[0], "approved", "manager_ravi", "Budget pre-approved for Q4")
human_decide(approval_ids[1], "rejected", "manager_priya", "Needs legal review first")

print(f"\n  Pending approvals status:")
for aid, pending in PENDING_APPROVALS.items():
    print(f"    {aid}: {pending.action.type} -> {pending.status} (by {pending.decided_by or 'pending'})")

print("\nInterview: Async HITL = agent resources free rehte hain, human apne time pe decide karta hai.")
print("Temporal / Durable workflows = workflow weeks-long delay bhi survive karta hai.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: ACTIVE LEARNING FEEDBACK LOOP — Pattern 5
# Theory: Human corrections capture karo, agent ko improve karo
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 5: Active Learning — Human Corrections Se Agent Seekhta Hai")
print("=" * 65)


@dataclass
class FeedbackEvent:
    """
    Theory Pattern 5: Human correction ka record.
    Yeh future fine-tuning ya few-shot examples ke liye use hoga.
    """
    query: str
    agent_response: str
    user_rating: int            # 1-5 scale
    user_correction: Optional[str]  # Human ne kya change kiya
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    feedback_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])


# Feedback database — production mein DB mein store hoga
FEEDBACK_DB: List[FeedbackEvent] = []


def handle_with_learning(query: str) -> dict:
    """
    Theory Pattern 5: Agent respond karta hai, human feedback deta hai,
    feedback store hota hai — future mein agent improve hota hai.
    """
    # Step 1: Agent ka initial response
    agent_response = llm_call(
        prompt=query,
        system="You are a customer support agent. Be concise.",
        max_tokens=100,
    )

    # Step 2: Simulated user feedback (real mein UI se aata hai)
    mock_feedbacks = [
        (5, None),                    # Perfect response
        (3, "Discount 10% nahi, 15% hona chahiye tha"),  # Minor correction
        (2, "Bilkul galat — humari policy 30 din nahi, 14 din ki hai"),  # Major correction
        (4, None),
    ]
    rating, correction = random.choice(mock_feedbacks)

    # Step 3: Feedback store karo
    event = FeedbackEvent(
        query=query,
        agent_response=agent_response,
        user_rating=rating,
        user_correction=correction,
    )
    FEEDBACK_DB.append(event)

    print(f"    [Feedback] Rating: {rating}/5")
    if correction:
        print(f"    [Feedback] Correction: {correction}")
        print(f"    [Learning] Storing correction for fine-tuning / few-shot examples")

    # Step 4: Agar correction hai toh use hi return karo
    final_response = correction if correction else agent_response
    return {
        "response": final_response,
        "rating": rating,
        "corrected": correction is not None,
        "feedback_id": event.feedback_id,
    }


def analyze_feedback_for_improvement():
    """
    Theory: Low-rated responses aggregate karo — weak spots identify karo.
    Phir fine-tuning data ya few-shot examples banao.
    """
    if not FEEDBACK_DB:
        return

    low_rated = [f for f in FEEDBACK_DB if f.user_rating <= 3]
    corrected = [f for f in FEEDBACK_DB if f.user_correction]
    avg_rating = sum(f.user_rating for f in FEEDBACK_DB) / len(FEEDBACK_DB)

    print(f"\n  Feedback Analysis:")
    print(f"    Total interactions: {len(FEEDBACK_DB)}")
    print(f"    Average rating: {avg_rating:.1f}/5")
    print(f"    Low-rated (<=3): {len(low_rated)} ({len(low_rated)/len(FEEDBACK_DB):.0%})")
    print(f"    Human corrections: {len(corrected)}")
    if corrected:
        print(f"    Example correction pairs (for fine-tuning):")
        for f in corrected[:2]:
            print(f"      Query: '{f.query[:40]}'")
            print(f"      Agent said: '{f.agent_response[:50]}'")
            print(f"      Correct: '{f.user_correction[:50]}'")


# --- Demo ---
random.seed(123)
print("\nActive Learning Demo:")
learning_queries = [
    "What is your return policy?",
    "How much discount do loyal customers get?",
    "What are your business hours?",
]

for q in learning_queries:
    print(f"\n  Query: '{q}'")
    result = handle_with_learning(q)
    print(f"  Final Response: {result['response'][:80]}")

analyze_feedback_for_improvement()
print("\nInterview: Active learning = (agent_response, human_correction) pairs store karo,")
print("fine-tuning ya few-shot examples mein use karo. Escalation rate time ke saath ghatna chahiye.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: SUPERVISED CHAT SESSION — Pattern 6
# Theory: Bot chal raha hai, human agent observe kar sakta hai aur takeover bhi
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 6: Supervised Chat — Human Bot Ko Override Kar Sakta Hai")
print("=" * 65)


class ChatMode(Enum):
    """Theory Pattern 6: Chat session ke modes."""
    BOT = "bot"                     # Pure bot
    AGENT_OBSERVING = "observing"   # Human dekh raha hai, approve/modify karta hai
    HUMAN = "human"                 # Human ne takeover kar liya


class SupervisedChatSession:
    """
    Theory Pattern 6: Supervised Chat.
    Bot user se baat karta hai, human supervisor kabhi bhi:
    - Approve kare (bot response seedha bhejo)
    - Modify kare (apna text bhejo)
    - Takeover kare (bot band, sirf human)
    """

    def __init__(self, session_id: str, mode: ChatMode = ChatMode.BOT):
        self.session_id = session_id
        self.mode = mode
        self.messages: List[dict] = []
        self.assigned_human: Optional[str] = None

    def handle_message(self, user_message: str) -> Optional[str]:
        """User message process karo — mode ke hisaab se."""

        if self.mode == ChatMode.HUMAN:
            # Human ne takeover kar liya — bot kuch nahi karega
            print(f"    [Session {self.session_id}] Human mode — forwarding to {self.assigned_human}")
            return None  # Human agent seedha respond karega

        # Bot response generate karo
        bot_reply = llm_call(
            prompt=user_message,
            system="You are a customer support chatbot. Be helpful and concise.",
            max_tokens=80,
        )

        if self.mode == ChatMode.AGENT_OBSERVING:
            # Human supervisor decide karta hai
            decision = self._ask_human_supervisor(user_message, bot_reply)

            if decision["action"] == "approve":
                final_reply = bot_reply
                print(f"    [Supervisor] Bot reply approved")
            elif decision["action"] == "modify":
                final_reply = decision["text"]
                print(f"    [Supervisor] Bot reply modified: '{final_reply[:50]}'")
            elif decision["action"] == "take_over":
                self.mode = ChatMode.HUMAN
                self.assigned_human = decision.get("agent_id", "human_support_01")
                final_reply = f"Ek moment — aapko ek specialist se connect kar rahe hain."
                print(f"    [Supervisor] Takeover by {self.assigned_human}")
            else:
                final_reply = bot_reply
        else:
            # Pure bot mode — seedha reply
            final_reply = bot_reply

        self.messages.append({"role": "user", "content": user_message})
        self.messages.append({"role": "assistant", "content": final_reply})
        return final_reply

    def _ask_human_supervisor(self, user_msg: str, bot_reply: str) -> dict:
        """
        Human supervisor se decision lena — production mein real-time UI hogi.
        Yahan simulate kar rahe hain.
        """
        # Simulate supervisor decisions
        decisions = [
            {"action": "approve"},
            {"action": "modify", "text": "Hum aapki madad karne ke liye tayar hain. Kripya order number batayein."},
            {"action": "take_over", "agent_id": "support_agent_02"},
        ]
        choice = random.choice(decisions[:2])  # mostly approve/modify
        return choice


# --- Demo ---
random.seed(456)
print("\nSupervised Chat Demo:")

# Session 1: Pure bot mode
session1 = SupervisedChatSession("sess_001", ChatMode.BOT)
print(f"\n  [Session 1 — Pure Bot Mode]")
customer_msgs = ["I want to return my order", "Order was delivered damaged"]
for msg in customer_msgs:
    print(f"  Customer: {msg}")
    reply = session1.handle_message(msg)
    print(f"  Bot: {(reply or '[human handling]')[:90]}")

# Session 2: Supervised mode — human is watching
session2 = SupervisedChatSession("sess_002", ChatMode.AGENT_OBSERVING)
print(f"\n  [Session 2 — Human Supervisor Observing]")
sensitive_msgs = ["I want a refund of 5000 rupees", "Your product gave me food poisoning"]
for msg in sensitive_msgs:
    print(f"  Customer: {msg}")
    reply = session2.handle_message(msg)
    if reply:
        print(f"  Final Reply: {reply[:90]}")

print("\nInterview: Supervised chat = progressive automation.")
print("Start with human oversight, gradually move to autonomous as confidence grows.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: HITL METRICS — Theory se
# Track karo: escalation rate, rejection rate, response time
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 7: HITL Metrics — Kaise Measure Karte Hain Effectiveness?")
print("=" * 65)


@dataclass
class HITLMetrics:
    """
    Theory se: Key metrics track karo.
    Goal: Escalation rate time ke saath GHATNA chahiye — agent seekh raha hai.
    """
    total_actions: int = 0
    auto_handled: int = 0
    human_approved: int = 0
    human_rejected: int = 0
    response_times: List[float] = field(default_factory=list)

    @property
    def escalation_rate(self) -> float:
        """% actions jahan human involved tha."""
        human_total = self.human_approved + self.human_rejected
        if self.total_actions == 0:
            return 0.0
        return human_total / self.total_actions

    @property
    def rejection_rate(self) -> float:
        """% human decisions jahan human ne naa bola."""
        human_total = self.human_approved + self.human_rejected
        if human_total == 0:
            return 0.0
        return self.human_rejected / human_total

    @property
    def automation_rate(self) -> float:
        """% actions jahan human ki zaroorat nahi padi."""
        if self.total_actions == 0:
            return 0.0
        return self.auto_handled / self.total_actions

    @property
    def p50_response_time(self) -> float:
        """Median human response time (seconds)."""
        if not self.response_times:
            return 0.0
        sorted_times = sorted(self.response_times)
        return sorted_times[len(sorted_times) // 2]

    @property
    def p99_response_time(self) -> float:
        """P99 human response time — worst case."""
        if not self.response_times:
            return 0.0
        sorted_times = sorted(self.response_times)
        idx = int(len(sorted_times) * 0.99)
        return sorted_times[min(idx, len(sorted_times) - 1)]

    def daily_summary(self) -> dict:
        return {
            "total_actions": self.total_actions,
            "auto_handled": self.auto_handled,
            "human_approved": self.human_approved,
            "human_rejected": self.human_rejected,
            "escalation_rate": f"{self.escalation_rate:.1%}",
            "rejection_rate": f"{self.rejection_rate:.1%}",
            "automation_rate": f"{self.automation_rate:.1%}",
            "human_response_time_p50": f"{self.p50_response_time:.0f}s",
            "human_response_time_p99": f"{self.p99_response_time:.0f}s",
        }


# Audit log se metrics compute karo
def compute_metrics_from_audit() -> HITLMetrics:
    """Audit trail se real metrics nikalo."""
    metrics = HITLMetrics()
    metrics.total_actions = len(AUDIT_LOG)
    for event in AUDIT_LOG:
        if event.human_required:
            if event.human_decision == "approved":
                metrics.human_approved += 1
            elif event.human_decision == "rejected":
                metrics.human_rejected += 1
        else:
            metrics.auto_handled += 1
    # Simulate response times (production mein actual timestamps se calculate hoga)
    metrics.response_times = [random.uniform(30, 3600) for _ in range(metrics.human_approved + metrics.human_rejected)]
    return metrics


print("\nAudit Trail (last 5 events):")
print(f"  {'Action':<20} {'Human?':>8} {'Decision':>10} {'Outcome':>18}")
print("  " + "-" * 60)
for event in AUDIT_LOG[-5:]:
    hr = "Yes" if event.human_required else "No"
    dec = event.human_decision or "auto"
    print(f"  {event.action_type:<20} {hr:>8} {dec:>10} {event.final_outcome:>18}")

metrics = compute_metrics_from_audit()
summary = metrics.daily_summary()

print("\nHITL Daily Metrics Summary:")
for k, v in summary.items():
    print(f"  {k:<35}: {v}")

print("\nInterview: Goal = escalation rate ko time ke saath reduce karo.")
print("Agar rejection rate zyada hai = agent ki training weak hai ya rules wrong hain.")
print("P99 response time zyada = approvers overwhelmed ya escalation chain weak hai.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8: COMMON PITFALLS — Theory se
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 8: Common Pitfalls — Galtiyan Jo Avoid Karni Hain")
print("=" * 65)

PITFALLS = [
    ("Har action pe approval", "Human overwhelm ho jaata hai — rubber stamping shuru",
     "Confidence-based routing — only low-confidence / high-stakes escalate karo"),
    ("Indefinite timeout", "User ghanton intezaar karta hai",
     "Backup approvers + escalation chain + default 'reject' on timeout"),
    ("Agent indefinitely wait karta hai", "Resources tied up",
     "Async HITL ya Temporal durable workflows use karo"),
    ("No audit trail", "Compliance fail, legal issues",
     "Har action, decision, human_id log karo — tamper-evident"),
    ("Human ko agent reasoning nahi dikhti", "Bad approvals, rubber stamping",
     "Show: agent plan + confidence + reasoning + risk assessment"),
    ("Rejection UI mushkil hai", "Humans sab approve kar dete hain",
     "Rejection ko approval se asaan banao — default 'reject' option"),
    ("Human corrections wasted", "Same galtiyan baar baar",
     "Active learning loop — corrections ko fine-tuning data mein convert karo"),
    ("Sync + Async mix, unclear to users", "Confusing UX",
     "Explicit messaging: 'Specialist 1 ghante mein reply karega' vs real-time"),
]

for i, (pitfall, consequence, fix) in enumerate(PITFALLS, 1):
    print(f"\n  {i}. Galti: {pitfall}")
    print(f"     Consequence: {consequence}")
    print(f"     Fix: {fix}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 9: INTERVIEW Q&A — Theory ke key questions
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 9: Interview Q&A — Yeh Questions Pooche Jaate Hain")
print("=" * 65)

QA = [
    (
        "Q1: Agent kab autonomous nahi hona chahiye?",
        "Irreversible actions (delete, financial). High-stakes amounts. Low confidence. "
        "Regulatory requirement (finance, healthcare mein human accountability mandatory). "
        "Edge cases jo training mein nahi the.",
    ),
    (
        "Q2: Human ko approval requests se overwhelm hone se kaise bachao?",
        "Confidence-based routing (only < 0.7 confidence escalate). Random sampling (5% QA). "
        "Batch approvals (similar decisions group karo). "
        "Async patterns (human apne time pe approve kare).",
    ),
    (
        "Q3: Human corrections se 'feedback loop' kaise banate hain?",
        "Har (agent_response, human_correction) pair log karo. "
        "Use: (a) few-shot examples in future prompts, (b) fine-tuning data, "
        "(c) weak topics identify karo, (d) agent improvement measure karo.",
    ),
    (
        "Q4: Agar human approval time pe nahi aaya toh kya karo?",
        "Timeout -> safe default (usually 'reject'). "
        "Escalation chain -> backup approvers. "
        "Auto-cancel + user ko notify. "
        "Temporal workflows: workflow survive karta hai jab tak human respond kare.",
    ),
    (
        "Q5: Sync HITL aur Async HITL mein kya fark hai?",
        "Sync: agent blocks, human real-time decide karta hai. "
        "Good UX but resources tied during wait. "
        "Async: agent request submit karta hai, turant return karta hai, "
        "human baad mein decide karta hai. "
        "Better for long delays + scale. Production ke liye prefer karo.",
    ),
]

for q, a in QA:
    print(f"\n  {q}")
    # Wrap answer lines nicely
    words = a.split()
    line = "    "
    for word in words:
        if len(line) + len(word) > 70:
            print(line)
            line = "    " + word + " "
        else:
            line += word + " "
    if line.strip():
        print(line)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 10: LIVE LLM DEMO — Groq key hone pe chalega
# Confidence-based escalation with actual LLM
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("SECTION 10: Live LLM Demo (GROQ_API_KEY hone pe)")
print("=" * 65)

if LIVE_MODE:
    print("\nGroq key mili! Live demo chal raha hai...\n")
    live_queries = [
        "What is 2 + 2?",
        "Should I take aspirin for severe chest pain?",  # Medical = low confidence expected
    ]
    for lq in live_queries:
        print(f"  Query: {lq}")
        result = handle_with_escalation(lq, [])
        print(f"  Source: {result['source']} | Confidence: {result['confidence']:.0%}")
        print(f"  Response: {result['response'][:100]}")
        print()
else:
    print("\nGROQ_API_KEY set nahi hai — offline demo chal raha hai (yeh expected hai).")
    print("Live demo ke liye: export GROQ_API_KEY=gsk_... phir dobara chalao.")
    print("Sab sections offline bhi fully execute hue hain — EXIT 0.")


# ─────────────────────────────────────────────────────────────────────────────
# EXERCISES
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("EXERCISES — Practice Karo")
print("=" * 65)
print("""
EASY:
  1. hitl_decision() mein ek naya rule add karo:
     "weekend pe sab send_money actions approval chahiye"
  2. AuditEvent mein request IP address bhi store karo.

MEDIUM:
  3. Escalation chain: agar primary approver 5 min mein respond nahi karta
     toh secondary approver ko notify karo.
  4. SupervisedChatSession mein sentiment detect karo —
     agar customer frustrated lag raha hai toh auto-escalate.

HARD:
  5. LangGraph interrupt pattern implement karo:
     - StateGraph banao with 'plan' -> 'review' -> 'execute' nodes
     - interrupt_before=["review"] se human review simulate karo
     - State resume karo
  6. HITL metrics ka time-series graph banao (matplotlib se):
     - x-axis: week number
     - y-axis: escalation rate
     - Goal: declining trend dikhao as agent learns
""")

print("=" * 65)
print("HITL Senior Mantras:")
MANTRAS = [
    "HITL = safety + compliance, 'agent bad at job' nahi.",
    "Intelligently escalate — confidence + stakes based.",
    "Audit everything. Future-you will thank you.",
    "Async HITL > sync for non-urgent actions.",
    "Rejection ko approval se asaan banao — rubber stamping rokne ke liye.",
    "Escalation rate time ke saath GHATNI chahiye — active learning.",
    "Human ko agent reasoning dikhao — better decisions aate hain.",
    "Kuch actions HAMESHA human chahte hain. Sab automation good nahi.",
]
for i, m in enumerate(MANTRAS, 1):
    print(f"  {i}. {m}")
print("=" * 65)
print("Lab complete! EXIT 0.")
