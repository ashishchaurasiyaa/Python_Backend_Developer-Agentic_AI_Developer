"""
Modern Topics — Doc 2: Computer Use (PRACTICAL)
==================================================
Implements "the loop" mechanics with a MOCKED screen/executor — this
deliberately never touches a real desktop. The goal is understanding the
request/response shape and the action-execution loop safely, not driving
your actual machine from a study script.

Topics covered:
  1. The action vocabulary (screenshot, click, type, key, scroll)
  2. A mock screen you can "click" and "type" into, with real state
  3. The loop — model requests an action, you execute it, feed the result back
  4. Why sandboxing matters — the doc's own point, made concrete with a
     blocked-action example

Install: pip install anthropic python-dotenv  (only needed for a REAL loop —
         this practical runs the loop against a simulated model by default)
Run: python 02_computer_use_practical.py
"""

import os
from dotenv import load_dotenv

load_dotenv()
HAS_KEY = bool(os.getenv("ANTHROPIC_API_KEY"))

VALID_ACTIONS = {"screenshot", "left_click", "right_click", "double_click", "mouse_move", "type", "key", "scroll", "cursor_position"}


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: A Mock Screen With Real State
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 1: A Safe, In-Memory 'Screen' to Practice Against")
print("=" * 70)


class MockScreen:
    """Stands in for a real desktop — a tiny 'app' with buttons and a text
    field, entirely in memory. Real computer-use hits the actual OS; this
    hits a dict, on purpose."""

    def __init__(self):
        self.cursor = (0, 0)
        self.text_field = ""
        self.calculator_result = None
        # (x, y) -> what's there, so clicks can "do" something
        self.buttons = {(100, 100): "open_calculator", (200, 200): "compute"}
        self.calculator_open = False

    def screenshot(self) -> str:
        state = f"cursor={self.cursor}, calculator_open={self.calculator_open}, text_field='{self.text_field}'"
        if self.calculator_result is not None:
            state += f", result={self.calculator_result}"
        return f"[MOCK SCREENSHOT] {state}"

    def left_click(self, x: int, y: int) -> str:
        self.cursor = (x, y)
        action = self.buttons.get((x, y))
        if action == "open_calculator":
            self.calculator_open = True
            return f"Clicked ({x},{y}) — Calculator opened"
        if action == "compute" and self.calculator_open:
            try:
                self.calculator_result = eval(self.text_field, {"__builtins__": {}})
            except Exception:
                self.calculator_result = "error"
            return f"Clicked ({x},{y}) — computed: {self.calculator_result}"
        return f"Clicked ({x},{y}) — nothing there"

    def type_text(self, text: str) -> str:
        self.text_field += text
        return f"Typed '{text}' — field is now '{self.text_field}'"


screen = MockScreen()
print(f"\n  {screen.screenshot()}")
print(f"  {screen.left_click(100, 100)}")
print(f"  {screen.type_text('1234*567')}")
print(f"  {screen.left_click(200, 200)}")
print(f"  {screen.screenshot()}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: The Action Vocabulary
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 2: The Action Vocabulary")
print("=" * 70)
print(f"\n  Valid actions the model can request: {sorted(VALID_ACTIONS)}")


def execute_computer_action(action: dict, screen: MockScreen) -> str:
    """Same dispatch shape as the doc's execute_computer_action() — routes
    each action type to the right screen operation."""
    action_type = action.get("action")
    if action_type not in VALID_ACTIONS:
        return f"Error: unknown action '{action_type}'"
    if action_type == "screenshot":
        return screen.screenshot()
    if action_type == "left_click":
        return screen.left_click(action["x"], action["y"])
    if action_type == "type":
        return screen.type_text(action["text"])
    return f"[{action_type} not implemented in this mock — see exercises]"


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: The Loop — Model Requests, You Execute, You Feed Back
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 3: The Loop")
print("=" * 70)

# A SIMULATED model plan — same shape as what a real computer-use response's
# tool_use blocks would contain, so the loop mechanics are identical whether
# this list comes from a mock (below) or a real Anthropic beta response.
SIMULATED_PLAN = [
    {"action": "screenshot"},
    {"action": "left_click", "x": 100, "y": 100},
    {"action": "type", "text": "1234*567"},
    {"action": "left_click", "x": 200, "y": 200},
    {"action": "screenshot"},
]


def computer_use_loop(plan: list[dict], screen: MockScreen, max_actions: int = 20) -> list[str]:
    """Mirrors the doc's real loop shape: model requests an action -> execute
    it -> feed the result back as the next turn's tool_result -> repeat until
    stop_reason != 'tool_use'. Here, 'plan' stands in for the model's
    turn-by-turn decisions since there's no live model driving this."""
    results = []
    for i, action in enumerate(plan[:max_actions]):
        result = execute_computer_action(action, screen)
        results.append(result)
        print(f"  Step {i+1}: {action} -> {result}")
    return results


fresh_screen = MockScreen()
print()
computer_use_loop(SIMULATED_PLAN, fresh_screen)

if HAS_KEY:
    print("\n  ANTHROPIC_API_KEY is set — you could swap SIMULATED_PLAN for a real")
    print("  client.beta.messages.create(..., betas=['computer-use-2024-10-22'])")
    print("  call and parse response.content for tool_use blocks instead. Left as")
    print("  an exercise — this file deliberately doesn't drive a real desktop.")
else:
    print("\n  [NO_API_KEY — SIMULATED_PLAN stands in for what a real model would")
    print("   request turn by turn. The loop mechanics above are identical either way.]")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Why Sandboxing Matters
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 4: Sandboxing — a Blocked-Action Example")
print("=" * 70)

DANGEROUS_PATTERNS = ["rm -rf", "sudo", "format ", "del /f"]


def is_action_safe(action: dict) -> bool:
    if action.get("action") == "type":
        text = action.get("text", "")
        return not any(p in text for p in DANGEROUS_PATTERNS)
    return True


risky_action = {"action": "type", "text": "sudo rm -rf /important-data"}
print(f"\n  Requested action: {risky_action}")
print(f"  Safe to auto-execute? {is_action_safe(risky_action)}")
print("\n  A real computer-use harness needs exactly this kind of check BEFORE")
print("  execute_computer_action() runs — the model can be tricked (or just")
print("  wrong) into requesting something destructive, and unlike a text")
print("  response, a computer-use action has REAL side effects on a REAL machine.")
print("  This is the same permission-model idea as Level6 Doc 12's harness")
print("  engineering practical, applied to a much higher-blast-radius tool.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Exercises
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 5: EXERCISES")
print("=" * 70)
print("""
EASY:
1. Add a `right_click` and `key` implementation to execute_computer_action()
   and MockScreen, then add a step using each to SIMULATED_PLAN.

MEDIUM:
2. Add `scroll` support — MockScreen should track a `scroll_position` and
   the mock screenshot() should reflect it.

HARD:
3. Extend is_action_safe() to also check `left_click`/`key` actions for
   patterns that would trigger a destructive OS dialog (e.g. clicking a
   coordinate known to be a "Delete Account" button in a real app's UI map).

PRO:
4. If you have ANTHROPIC_API_KEY: replace SIMULATED_PLAN with a real
   `client.beta.messages.create(...)` call, parse `response.content` for
   `tool_use` blocks, and run them through execute_computer_action() against
   MockScreen instead of a real desktop — a genuinely safe way to test a real
   model's computer-use planning without touching your actual machine.
""")

if __name__ == "__main__":
    print("\nDone. Next: 03_local_serving_practical.py")
