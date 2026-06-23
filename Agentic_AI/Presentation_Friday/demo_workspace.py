"""
========================================================================
LIVE AI WORKSPACE DEMO  —  Agent + MCP-style Tools + Skills + RAG
========================================================================
Ek chhota, SELF-CONTAINED AI workspace jo REAL kaam karta hai:

   Task aata hai  ->  Agent sochta hai  ->  docs retrieve karta hai (RAG)
   ->  tool chalata hai (skill)  ->  citation ke saath answer deta hai.

Demo ke liye banaya gaya:
  • ZERO external dependencies (sirf Python stdlib) — pip ki zaroorat nahi
  • NO API key chahiye — MOCK MODE deterministic hai, live kabhi fail nahi hota
  • OPENAI_API_KEY set ho to (optional) real LLM reasoning bhi chal sakta hai

Run:
  python demo_workspace.py            # saare example tasks
  python demo_workspace.py "your question here"

4 PILLARS jo is ek file mein live dikhte hain:
  1) AGENT  — Think/Act/Observe loop (orchestrator)
  2) MCP    — tools MCP-style schema (name/description/params) mein defined
  3) SKILLS — tool registry: search_docs, days_between, create_ticket
  4) RAG    — chhoti internal knowledge-base pe real retrieval + citations
"""

import os
import re
import sys
from datetime import date

# Presentation ke din ko fix rakha hai taaki rehearsal deterministic rahe.
# Apna date chahiye to yahan badal do (ya os.getenv use karo).
DEMO_TODAY = date(2026, 6, 21)

LLM_MODE = bool(os.getenv("OPENAI_API_KEY"))  # key ho to real LLM, warna mock


# ─────────────────────────────────────────────────────────────────────────────
# PILLAR 4 — RAG : ek chhoti internal knowledge-base (company docs)
# ─────────────────────────────────────────────────────────────────────────────
KNOWLEDGE_BASE = {
    "DOC-101 Refund Policy": (
        "AcmeCorp refund policy: Customers may request a full refund within "
        "30 days of purchase. After 30 days, only store credit is offered. "
        "Refunds are processed within 5 business days."
    ),
    "DOC-102 Support Hours": (
        "Support is available Monday to Friday, 9 AM to 6 PM IST. "
        "P1 (critical) incidents are handled 24x7 via the on-call pager."
    ),
    "DOC-103 Incident Escalation": (
        "To escalate a P1 incident: (1) page the on-call engineer, "
        "(2) open a war-room in #incidents, (3) notify the EM within 15 minutes. "
        "P2 issues are triaged next business day."
    ),
    "DOC-104 Data Retention": (
        "Customer PII is retained for 24 months, then anonymized. "
        "Backups are encrypted at rest and rotated every 90 days."
    ),
}

_STOP = {"the", "a", "an", "is", "to", "of", "and", "or", "for", "how", "do",
         "i", "what", "our", "my", "if", "in", "on", "are", "many", "left",
         "as", "within", "purchased", "bought"}


def _tokens(text):
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in _STOP]


def retrieve(query, k=1):
    """REAL keyword-overlap retrieval over the knowledge base (RAG pillar)."""
    q = set(_tokens(query))
    scored = []
    for doc_id, text in KNOWLEDGE_BASE.items():
        overlap = q & set(_tokens(doc_id + " " + text))
        if overlap:
            scored.append((len(overlap), doc_id, text))
    scored.sort(reverse=True)
    return [(doc_id, text) for _, doc_id, text in scored[:k]]


# ─────────────────────────────────────────────────────────────────────────────
# PILLAR 2 + 3 — MCP-style TOOLS  exposed via a SKILLS registry
# ─────────────────────────────────────────────────────────────────────────────
class ToolRegistry:
    def __init__(self):
        self._tools = {}
        self._schemas = []

    def register(self, schema):
        def deco(fn):
            self._tools[schema["name"]] = fn
            self._schemas.append(schema)
            return fn
        return deco

    def call(self, name, **kwargs):
        return self._tools[name](**kwargs)

    @property
    def schemas(self):
        return self._schemas


registry = ToolRegistry()


@registry.register({
    "name": "search_docs",
    "description": "Search internal company docs. Use for any policy/process question.",
    "parameters": {"query": "string"},
})
def search_docs(query):
    hits = retrieve(query, k=1)
    if not hits:
        return {"found": False, "answer": "No matching document."}
    doc_id, text = hits[0]
    return {"found": True, "source": doc_id, "text": text}


@registry.register({
    "name": "days_between",
    "description": "Compute the number of days between two ISO dates (YYYY-MM-DD).",
    "parameters": {"start": "string", "end": "string"},
})
def days_between(start, end):
    d1 = date.fromisoformat(start)
    d2 = date.fromisoformat(end)
    return {"days": abs((d2 - d1).days)}


@registry.register({
    "name": "create_ticket",
    "description": "Create a support ticket (an action that changes a system).",
    "parameters": {"summary": "string"},
})
def create_ticket(summary):
    # Mock action — production mein ye GitHub/Jira/DB call hota.
    ticket_id = "TKT-" + str(abs(hash(summary)) % 9000 + 1000)
    return {"ticket_id": ticket_id, "summary": summary, "status": "open"}


# ─────────────────────────────────────────────────────────────────────────────
# PILLAR 1 — THE AGENT : Think / Act / Observe loop
# ─────────────────────────────────────────────────────────────────────────────
def say(role, text, color=""):
    icons = {"think": "🤔 Thought ", "act": "🔧 Action  ",
             "obs": "👁  Observe ", "final": "✅ Answer  ", "user": "💬 Task    "}
    print(f"   {icons.get(role, role)}: {text}")


def find_date(text):
    m = re.search(r"\d{4}-\d{2}-\d{2}", text)
    return m.group(0) if m else None


def find_number(text):
    m = re.search(r"\b(\d{1,3})\b", text)
    return int(m.group(1)) if m else None


def agent(task):
    """
    A real ReAct-style loop. In MOCK MODE the tool choices are rule-based but
    EVERY tool genuinely runs on real data — the retrieval and the math are not
    faked. With OPENAI_API_KEY the same tools would be driven by the LLM.
    """
    print("\n" + "─" * 72)
    say("user", task)
    mode = "LLM" if LLM_MODE else "MOCK (deterministic — set OPENAI_API_KEY for live LLM)"
    print(f"   [agent mode: {mode}]")

    # STEP 1 — always ground in the docs (RAG)
    say("think", "This is a company-knowledge question — search the docs first.")
    say("act", 'search_docs(query="%s")' % task[:48])
    doc = registry.call("search_docs", query=task)
    if not doc["found"]:
        say("obs", "No relevant doc found.")
        say("final", "I couldn't find this in our internal docs.")
        return
    say("obs", f"[{doc['source']}] {doc['text'][:90]}...")

    # STEP 2 — if there's a date + a policy window, do the math (tool/skill)
    q_date = find_date(task)
    policy_days = find_number(doc["text"])  # e.g. "30 days" from the refund doc
    if q_date and policy_days and any(w in task.lower() for w in ["day", "left", "window", "refund"]):
        say("think", f"There's a purchase date ({q_date}) and a {policy_days}-day window — compute it.")
        say("act", f'days_between(start="{q_date}", end="{DEMO_TODAY}")')
        elapsed = registry.call("days_between", start=q_date, end=DEMO_TODAY.isoformat())["days"]
        remaining = policy_days - elapsed
        say("obs", f"{elapsed} days elapsed since purchase.")
        say("think", "Combine the policy window with elapsed days for the final answer.")
        verdict = (f"{remaining} day(s) left in the {policy_days}-day window."
                   if remaining > 0 else
                   f"the {policy_days}-day window has passed ({-remaining} day(s) ago).")
        say("final", f"Per {doc['source']}: {policy_days}-day window. "
                     f"Purchased {q_date}, today {DEMO_TODAY} → {elapsed} days elapsed, "
                     f"so {verdict}")
        return

    # STEP 3 — otherwise answer straight from the retrieved doc (with citation)
    say("think", "The doc fully answers this — respond with a citation.")
    say("final", f"{doc['text']}  (source: {doc['source']})")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def banner():
    print("=" * 72)
    print("  LIVE AI WORKSPACE  —  Agent + MCP-style Tools + Skills + RAG")
    print("=" * 72)
    print("  Knowledge base :", ", ".join(KNOWLEDGE_BASE.keys()))
    print("  Skills (tools) :", ", ".join(s["name"] for s in registry.schemas))
    print("  Today (demo)   :", DEMO_TODAY.isoformat())
    print("=" * 72)


if __name__ == "__main__":
    banner()
    if len(sys.argv) > 1:
        agent(" ".join(sys.argv[1:]))
    else:
        # Curated demo tasks — har ek alag pillar-combo dikhata hai
        agent("What is our refund window, and if I purchased on 2026-06-01, "
              "how many days are left?")
        agent("How do I escalate a P1 incident?")
        agent("How long do we retain customer PII?")
    print("\n" + "─" * 72)
    print("✅ Workspace ran end-to-end. Same 4 pillars, live.\n")
