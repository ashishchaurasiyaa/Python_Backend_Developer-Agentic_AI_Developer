"""
Modern Topics — Doc 18: Model Training Internals (PRACTICAL)
================================================================
The actual math behind the doc's diagrams, implemented in numpy — small
enough to trace by hand, real enough that the numbers mean something.

Topics covered:
  1. DPO loss — computed for real chosen/rejected log-prob pairs
  2. GRPO advantage — the doc's own "17 x 23" example, computed exactly
  3. Validation loss / overfitting — a real train-vs-val divergence curve
  4. Distillation — soft-label vs hard-label training, made concrete

Install: pip install numpy
Run: python 18_model_training_internals_practical.py
"""

import numpy as np

np.random.seed(42)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: DPO Loss — Computed for Real Numbers
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 1: DPO Loss")
print("=" * 70)


def sigmoid(x):
    return 1 / (1 + np.exp(-x))


def dpo_loss(logp_chosen: float, logp_rejected: float, logp_chosen_ref: float, logp_rejected_ref: float, beta: float = 0.1) -> float:
    """DPO's actual loss: no reward model, no critic — just a log-ratio
    comparison between the policy and a frozen reference model, on a
    (chosen, rejected) preference pair."""
    policy_logratio = logp_chosen - logp_rejected
    ref_logratio = logp_chosen_ref - logp_rejected_ref
    logits = beta * (policy_logratio - ref_logratio)
    return -np.log(sigmoid(logits))


# Two scenarios: policy already prefers "chosen" more than the reference does
# (loss should be small), vs policy actually prefers "rejected" (loss should be large)
good_case = dpo_loss(logp_chosen=-2.0, logp_rejected=-5.0, logp_chosen_ref=-2.5, logp_rejected_ref=-4.0)
bad_case = dpo_loss(logp_chosen=-5.0, logp_rejected=-2.0, logp_chosen_ref=-2.5, logp_rejected_ref=-4.0)

print(f"\n  Policy strongly prefers chosen (good alignment): DPO loss = {good_case:.4f}")
print(f"  Policy actually prefers the rejected answer (bad): DPO loss = {bad_case:.4f}")
print(f"\n  Loss is {'lower' if good_case < bad_case else 'higher'} when the policy agrees with the")
print(f"  human preference more than the reference model did — this IS the training")
print(f"  signal, with no separate reward model anywhere in this computation.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: GRPO Advantage — the Doc's Own "17 x 23" Example
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 2: GRPO Group-Relative Advantage")
print("=" * 70)


def grpo_advantages(rewards: list[float]) -> list[float]:
    """No critic — the group's own mean + std IS the baseline. Exactly what
    the doc's ASCII diagram shows for 'solve 17 x 23'."""
    rewards = np.array(rewards, dtype=float)
    mean, std = rewards.mean(), rewards.std()
    if std == 0:
        return [0.0] * len(rewards)  # doc's key insight: no spread = no gradient
    return list((rewards - mean) / std)


scenarios = {
    "mixed (2 correct, 1 wrong) — the doc's example": [1, 1, 0, 1],
    "all correct — too easy, no signal": [1, 1, 1, 1],
    "all wrong — too hard, no signal": [0, 0, 0, 0],
}

for label, rewards in scenarios.items():
    adv = grpo_advantages(rewards)
    print(f"\n  {label}")
    print(f"    rewards: {rewards}")
    print(f"    advantages: {[round(float(a), 3) for a in adv]}")
    if all(a == 0 for a in adv):
        print(f"    -> mean={np.mean(rewards)}, std=0 -> NO gradient. GRPO auto-skips this prompt.")

print("\n  This is the doc's 'free curriculum' point, computed not just claimed:")
print("  training compute automatically concentrates on prompts with MIXED")
print("  results — the frontier of what the model can sometimes solve.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Validation Loss / Overfitting — a Real Divergence Curve
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 3: Overfitting, as an Actual Curve")
print("=" * 70)


def simulate_training_curve(epochs: int = 20) -> tuple[list[float], list[float]]:
    """Simplified but real dynamics: train loss monotonically decreases
    (model fits its own data better every epoch); val loss decreases then
    turns UP once the model starts memorizing training-set quirks instead
    of learning generalizable patterns."""
    train_loss = [2.0 * np.exp(-0.3 * e) + 0.1 for e in range(epochs)]
    val_loss = [2.0 * np.exp(-0.25 * e) + 0.15 + max(0, (e - 10) * 0.02) ** 1.5 for e in range(epochs)]
    return train_loss, val_loss


train_loss, val_loss = simulate_training_curve()
best_epoch = int(np.argmin(val_loss))

print(f"\n  {'Epoch':>6s} {'Train':>8s} {'Val':>8s}")
for e in range(0, 20, 2):
    marker = "  <- val minimum, early-stop here" if e == best_epoch else ""
    print(f"  {e:>6d} {train_loss[e]:>8.3f} {val_loss[e]:>8.3f}{marker}")

print(f"\n  Train loss keeps falling all the way to epoch 19 ({train_loss[-1]:.3f}) —")
print(f"  but val loss bottoms out at epoch {best_epoch} ({val_loss[best_epoch]:.3f}) and rises after.")
print(f"  Everything past epoch {best_epoch} is the model memorizing, not learning —")
print(f"  early stopping there is the fix the doc names.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Distillation — Soft Labels vs Hard Labels, Made Concrete
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 4: Distillation — What 'Soft Labels' Actually Means")
print("=" * 70)


def softmax(logits, temperature=1.0):
    scaled = np.array(logits) / temperature
    exp = np.exp(scaled - np.max(scaled))
    return exp / exp.sum()


# A teacher model's raw output for "classify this review: positive/negative/neutral"
teacher_logits = [4.2, 1.1, 2.8]  # positive, negative, neutral
classes = ["positive", "negative", "neutral"]

hard_label = classes[np.argmax(teacher_logits)]
soft_labels_normal = softmax(teacher_logits, temperature=1.0)
soft_labels_distilled = softmax(teacher_logits, temperature=3.0)  # "temperature" softens the distribution

print(f"\n  Teacher's raw logits: {dict(zip(classes, teacher_logits))}")
print(f"\n  HARD label (what training on final answers only gives you): '{hard_label}'")
print(f"  -> student only learns 'the answer is positive', nothing about HOW confident")
print(f"     or what the runner-up was.")

print(f"\n  SOFT labels, temperature=1.0: {dict(zip(classes, [float(x) for x in soft_labels_normal.round(3)]))}")
print(f"  SOFT labels, temperature=3.0 (typical distillation setting): {dict(zip(classes, [float(x) for x in soft_labels_distilled.round(3)]))}")
print(f"\n  Higher temperature flattens the distribution — the student sees that")
print(f"  'neutral' was a real runner-up, not just wrong. THIS extra signal (the")
print(f"  relative ordering/confidence across ALL classes, not just the top one)")
print(f"  is what the doc means by 'teacher's knowledge transfers via soft outputs'.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Exercises
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 5: EXERCISES")
print("=" * 70)
print("""
EASY:
1. Change good_case/bad_case's beta parameter to 0.5 — how much does the
   loss gap between the two scenarios change? What does beta control?

MEDIUM:
2. Add a 4th GRPO scenario: 3 correct out of 4, with the wrong one getting
   a PARTIAL reward (0.5) instead of 0 — recompute advantages.

HARD:
3. simulate_training_curve() uses fixed formulas — replace it with an
   actual tiny gradient-descent loop on a toy overfitting-prone model
   (e.g. a high-degree polynomial fit to noisy data) to get a REAL, not
   simulated, train/val divergence curve.

PRO:
4. Implement a minimal PPO-vs-GRPO memory comparison: given a policy model
   size, compute total parameter count in GPU memory for each algorithm
   (PPO: policy+ref+reward+critic, GRPO: policy+ref+reward) and the %
   memory savings GRPO gives — this is the doc's "why DeepSeek chose GRPO"
   reasoning, quantified for a specific model size you pick.
""")

if __name__ == "__main__":
    print("\nDone. Next: 23_claude_agent_sdk_skills_practical.py")
