"""
Level 7 — Doc 10: A2A Protocol (PRACTICAL)
=============================================
A2A has no widely-installed pip package to depend on yet, so this builds
the protocol's actual mechanics — Agent Card discovery + task lifecycle —
as a tiny in-process client/server pair. No network calls needed to see
the real shape of the protocol.

Topics covered:
  1. Agent Card — the discovery document (what MCP's tool schema is to a
     single tool, an Agent Card is to a whole remote agent)
  2. Task lifecycle state machine — submitted -> working -> completed/failed
  3. Sending a task, simplified A2A client/server round trip
  4. A2A vs MCP — made concrete with two runnable code paths side by side

Install: none required (uses only stdlib) — pip install httpx for the real
         HTTP version referenced in exercise 4
Run: python 10_a2a_protocol_practical.py
"""

import json
import uuid


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Agent Card — the Discovery Document
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 1: Agent Card (A2A's equivalent of an OpenAPI spec)")
print("=" * 70)

INVOICE_AGENT_CARD = {
    "name": "InvoiceProcessingAgent",
    "description": "Extracts and validates invoice data from documents",
    "url": "https://partner.example.com/a2a",
    "capabilities": {"streaming": True, "pushNotifications": True},
    "skills": [
        {
            "id": "extract-invoice-data",
            "name": "Extract Invoice Data",
            "description": "Parses an invoice document and returns structured fields",
            "inputModes": ["application/pdf", "image/png"],
            "outputModes": ["application/json"],
        }
    ],
}

print(f"\n{json.dumps(INVOICE_AGENT_CARD, indent=2)}")
print("\n  Any caller — human-written code OR another agent — can fetch this and")
print("  programmatically learn what the remote agent does, without prior")
print("  integration work or reading its source code.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Task Lifecycle State Machine
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 2: Task Lifecycle")
print("=" * 70)

VALID_TRANSITIONS = {
    "submitted": {"working", "canceled"},
    "working": {"completed", "failed", "input-required", "canceled"},
    "input-required": {"working", "canceled"},
    "completed": set(),   # terminal
    "failed": set(),      # terminal
    "canceled": set(),    # terminal
}


class TaskLifecycleError(Exception):
    pass


class A2ATask:
    def __init__(self, task_id: str):
        self.id = task_id
        self.state = "submitted"
        self.history = ["submitted"]

    def transition(self, new_state: str):
        if new_state not in VALID_TRANSITIONS[self.state]:
            raise TaskLifecycleError(f"Cannot go {self.state} -> {new_state}. Valid: {VALID_TRANSITIONS[self.state]}")
        self.state = new_state
        self.history.append(new_state)


task = A2ATask(task_id="task-001")
print(f"\n  Task {task.id} created, state={task.state}")
task.transition("working")
print(f"  -> {task.state}")
task.transition("input-required")   # agent needs clarification mid-task
print(f"  -> {task.state}")
task.transition("working")          # clarification received, resumes
print(f"  -> {task.state}")
task.transition("completed")
print(f"  -> {task.state}")
print(f"\n  Full history: {' -> '.join(task.history)}")

print("\n  Now try an invalid transition (completed is terminal):")
try:
    task.transition("working")
except TaskLifecycleError as e:
    print(f"    Correctly rejected: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Sending a Task — Simplified Client/Server Round Trip
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 3: Client Delegates a Task, Server Processes It")
print("=" * 70)


class MockA2AServer:
    """Stands in for httpx calls to a real partner agent — same JSON-RPC
    shape as the doc's real example, just in-process instead of over HTTP."""

    def __init__(self, agent_card: dict):
        self.agent_card = agent_card
        self.tasks: dict[str, A2ATask] = {}

    def get_agent_card(self) -> dict:
        return self.agent_card

    def send_task(self, task_input: dict) -> dict:
        task_id = str(uuid.uuid4())[:8]
        task = A2ATask(task_id)
        self.tasks[task_id] = task

        task.transition("working")
        # simulate the remote agent actually doing its work
        result = {"invoice_number": task_input.get("invoice_number", "unknown"), "amount": 4500.00, "status": "validated"}
        task.transition("completed")

        return {
            "jsonrpc": "2.0",
            "result": {"id": task_id, "state": task.state, "output": result},
        }


def delegate_task(server: MockA2AServer, task_input: dict) -> dict:
    """Same 2-step shape as the doc's real httpx client — discover, then send."""
    card = server.get_agent_card()                       # 1. discover
    print(f"  Discovered agent: {card['name']} ({card['skills'][0]['name']})")
    response = server.send_task(task_input)               # 2. submit
    return response


server = MockA2AServer(INVOICE_AGENT_CARD)
response = delegate_task(server, {"invoice_number": "INV-2026-0451"})
print(f"\n  Response: {json.dumps(response, indent=2)}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: A2A vs MCP — Made Concrete, Not Just a Table
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 4: A2A vs MCP — Two Different Code Paths, Same Agent")
print("=" * 70)


def mcp_style_call(tool_name: str, args: dict) -> str:
    """MCP: agent calls ITS OWN tool — deterministic, in-process, you own it."""
    if tool_name == "calculate_tax":
        return f"Tax on {args['amount']}: {args['amount'] * 0.18:.2f}"
    return "unknown tool"


def a2a_style_delegate(server: MockA2AServer, task_input: dict) -> dict:
    """A2A: agent delegates to ANOTHER agent — you don't own its internals,
    only its Agent Card contract."""
    return server.send_task(task_input)


print("\n  MCP call (own tool, own scope):")
print(f"    {mcp_style_call('calculate_tax', {'amount': 5000})}")

print("\n  A2A call (delegated to a whole other agent, different owner):")
a2a_result = a2a_style_delegate(server, {"invoice_number": "INV-2026-0452"})
print(f"    {a2a_result['result']['output']}")

print("\n  Same agent could use BOTH in one workflow: MCP to calculate tax itself,")
print("  A2A to delegate invoice extraction to a specialist agent it doesn't own.")
print("  One-line answer to memorize: 'MCP is how an agent uses tools. A2A is how")
print("  an agent uses OTHER agents.'")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Exercises
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 5: EXERCISES")
print("=" * 70)
print("""
EASY:
1. Add an "input-required" branch to MockA2AServer.send_task() — if
   task_input is missing "invoice_number", transition to input-required
   instead of completing.

MEDIUM:
2. Add a second Agent Card + MockA2AServer for a "TravelBookingAgent" with
   its own skill. Delegate a task to it and print its Agent Card first.

HARD:
3. Rewrite delegate_task() using real `httpx` against a `MockA2AServer`
   wrapped in a tiny FastAPI app (2 endpoints: GET /.well-known/agent.json,
   POST / for tasks/send) — the doc's exact shape, over real HTTP this time.

PRO:
4. Simulate a "failed" task: make send_task() raise partway through, catch
   it, and transition to "failed" instead of "completed" — then have the
   caller decide whether to retry the SAME agent or fall back to a different
   one whose Agent Card advertises the same skill.
""")

if __name__ == "__main__":
    print("\nDone. Next: 11_haystack_practical.py")
