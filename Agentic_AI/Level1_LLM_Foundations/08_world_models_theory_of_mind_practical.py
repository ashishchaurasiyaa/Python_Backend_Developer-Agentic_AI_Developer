"""
Level 1 — Doc 8: LLM World Models & Theory of Mind (PRACTICAL)
================================================================
Reproduces the actual evidence-for / evidence-against arguments from the
doc as real probes against a real model, instead of just reading the claim.

Topics covered:
  1. State tracking across a story (evidence FOR an implicit world model)
  2. A known failure mode — counting/spatial reasoning (evidence AGAINST)
  3. The Sally-Anne false-belief test (Theory of Mind)
  4. A novel-phrasing variant of Sally-Anne (tests genuine reasoning vs
     pattern-matching a familiar training-data scenario)

Install:
  pip install openai python-dotenv

Run: python 08_world_models_theory_of_mind_practical.py
"""

import os
from dotenv import load_dotenv

load_dotenv()
HAS_KEY = bool(os.getenv("OPENAI_API_KEY"))


def call(prompt: str, system: str = "Answer precisely and briefly.", max_tokens: int = 150) -> str:
    if not HAS_KEY:
        return "[NO_API_KEY — set OPENAI_API_KEY in .env to run these probes live]"
    from openai import OpenAI
    client = OpenAI()
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Evidence FOR — State Tracking Across a Story
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 1: Evidence FOR — Implicit State Tracking")
print("=" * 70)

story_prompt = """
Track the state carefully as this story unfolds, then answer the question.

Room A has a red box and a blue box. The red box is empty. The blue box
has a key inside it. Priya takes the key out of the blue box and puts it
in her pocket. Priya then walks to Room B, taking the key with her. She
places the key on a table in Room B.

Question: Where is the key now, and is the blue box empty or full?
"""
output = call(story_prompt, max_tokens=80)
print(f"\n  {output}")
print("\n  Getting this right requires tracking an object's location as it moves")
print("  across multiple sentences — something a pure 'predict the next word'")
print("  process shouldn't obviously be able to do unless it built SOME internal")
print("  representation of world state while reading. This is the strongest")
print("  evidence-for argument in the doc.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Evidence AGAINST — a Known Failure Mode
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 2: Evidence AGAINST — Spatial/Counting Failure")
print("=" * 70)

spatial_prompt = """
A 5x5 grid of empty cells. I place a token at position (2,2) — using
(row, column), 0-indexed from the top-left. I then move it: 2 cells right,
then 3 cells down, then 1 cell left, then 2 cells up.

What is the final (row, column) position of the token?
"""
output = call(spatial_prompt, max_tokens=100)
print(f"\n  {output}")
print("\n  Correct answer: start (2,2) -> right 2 = (2,4) -> down 3 = (5,4) [off-grid on a")
print("  5x5 0-indexed board, max row=4] -> this is DELIBERATELY slightly malformed to")
print("  see whether the model catches the boundary issue or confidently gives an")
print("  in-bounds answer anyway. Multi-step spatial tracking without a real coordinate")
print("  system to fall back on is exactly where 'world model' claims get shakiest.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Theory of Mind — Sally-Anne False Belief Test
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 3: Theory of Mind — Classic Sally-Anne Test")
print("=" * 70)

sally_anne_prompt = """
Sally has a basket and Anne has a box. Sally puts a marble in her basket,
then leaves the room to go for a walk. While Sally is out, Anne takes the
marble out of the basket and puts it in her own box instead. Sally comes
back into the room.

Question: Where will Sally look for the marble first? Explain your reasoning.
"""
output = call(sally_anne_prompt, max_tokens=120)
print(f"\n  {output}")
print("\n  Correct answer: the basket — Sally didn't see the swap, so she acts on")
print("  her OWN (now false) belief, not on the real (ground-truth) location.")
print("  Getting this right requires modeling SALLY's mental state as distinct")
print("  from reality — that's Theory of Mind, a step beyond just tracking state.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Novel-Phrasing Variant — Ruling Out Memorization
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 4: Novel Variant — Is It Reasoning, or a Memorized Pattern?")
print("=" * 70)

novel_variant_prompt = """
Kabir stores his motorcycle keys in a drawer in the hallway every evening.
Tonight, while Kabir is asleep, his roommate Dev borrows the keys from the
drawer to move the motorcycle for street cleaning, then puts the keys back
in a different drawer in the kitchen instead of the hallway one, and never
mentions this to Kabir. In the morning, Kabir wants his keys.

Question: Which drawer will Kabir check first, and why? Then, separately,
state where the keys ACTUALLY are.
"""
output = call(novel_variant_prompt, max_tokens=150)
print(f"\n  {output}")
print("\n  Same underlying structure as Sally-Anne (an agent acts on an outdated")
print("  belief because they weren't present for a change), but unfamiliar")
print("  surface details (keys/drawers/roommate instead of the classic marble/")
print("  basket/box). If the model still separates 'where Kabir will look' from")
print("  'where the keys actually are,' that's better evidence of genuine")
print("  reasoning rather than having memorized the classic Sally-Anne wording.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Exercises
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 5: EXERCISES")
print("=" * 70)
print("""
EASY:
1. Run Section 1's story again but add a THIRD location change. Does
   tracking degrade with more hops?

MEDIUM:
2. Write your own novel-phrasing false-belief scenario (Section 4 style)
   from a completely different domain (e.g. a warehouse inventory system,
   a git branch someone force-pushed while you were offline).

HARD:
3. Section 4's prompt asks for BOTH the false belief and the ground truth
   in one call. Split it into two separate calls asking only "where will
   Kabir look" — does isolating the question change the answer quality?

PRO:
4. Build a tiny "multi-agent ToM checker": simulate a supervisor delegating
   a task to a sub-agent, where the sub-agent is missing context the
   supervisor has. Ask the model (playing supervisor) to predict what the
   sub-agent will get wrong BEFORE it acts — this is the exact skill
   Level 6's multi-agent harness design exists to work around.
""")

if __name__ == "__main__":
    print("\nDone. Level 1 complete — every doc now has hands-on code, not just theory.")
    print("Next: Level 2 (Prompt Engineering)")
