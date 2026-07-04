"""
Classical ML/DL Foundations — Doc 1: LINEAR & LOGISTIC REGRESSION (PRACTICAL)
=============================================================================
From-scratch, numpy-only. No sklearn, no torch — so you SEE every gradient
update happen, not hide it behind .fit().

Run this to see:
  1. Linear regression via gradient descent (predict a continuous value)
  2. Logistic regression via gradient descent (binary classification)
  3. Loss curve going down — proof that gradient descent is actually learning
  4. Why MSE is a bad loss for classification (flat gradient demo)

Install:
  pip install numpy

Run: python 01_ml_foundations_regression_practical.py
"""

import numpy as np

np.random.seed(42)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Linear Regression from Scratch
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 1: Linear Regression — Predict a Continuous Value")
print("=" * 70)

# Fake data: y = 3x + 7 + noise (so we KNOW the right answer: w=3, b=7)
x = np.linspace(0, 10, 50)
y_true = 3 * x + 7 + np.random.normal(0, 1, size=x.shape)

w, b = 0.0, 0.0          # start at zero — model knows nothing
lr = 0.01                # learning rate — how big a step each update takes

for epoch in range(200):
    y_pred = w * x + b
    error = y_pred - y_true

    loss = np.mean(error ** 2)                # MSE

    # Gradients (calculus: d(loss)/dw and d(loss)/db)
    grad_w = np.mean(2 * error * x)
    grad_b = np.mean(2 * error)

    # Gradient descent update: move OPPOSITE the gradient (downhill)
    w -= lr * grad_w
    b -= lr * grad_b

    if epoch % 40 == 0:
        print(f"  epoch {epoch:>3} | loss={loss:6.3f} | w={w:.3f} | b={b:.3f}")

print(f"\nLearned: w={w:.3f}, b={b:.3f}  (true answer: w=3.000, b=7.000)")
print("Notice: gradient descent found it WITHOUT us telling it the formula.\n")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Logistic Regression from Scratch
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 2: Logistic Regression — Binary Classification")
print("=" * 70)


def sigmoid(z):
    return 1 / (1 + np.exp(-z))


# Fake data: 2 clusters (class 0 and class 1), 1 feature
x0 = np.random.normal(-2, 1, size=50)   # class 0 cluster
x1 = np.random.normal(2, 1, size=50)    # class 1 cluster
x_clf = np.concatenate([x0, x1])
y_clf = np.concatenate([np.zeros(50), np.ones(50)])

w, b = 0.0, 0.0
lr = 0.1

for epoch in range(300):
    z = w * x_clf + b
    y_pred = sigmoid(z)

    eps = 1e-9  # avoid log(0)
    loss = -np.mean(y_clf * np.log(y_pred + eps) + (1 - y_clf) * np.log(1 - y_pred + eps))

    error = y_pred - y_clf
    grad_w = np.mean(error * x_clf)
    grad_b = np.mean(error)

    w -= lr * grad_w
    b -= lr * grad_b

    if epoch % 60 == 0:
        acc = np.mean((y_pred > 0.5) == y_clf)
        print(f"  epoch {epoch:>3} | loss={loss:.4f} | accuracy={acc:.2%}")

final_acc = np.mean((sigmoid(w * x_clf + b) > 0.5) == y_clf)
print(f"\nFinal accuracy: {final_acc:.2%}  (decision boundary learned at x ≈ {-b/w:.2f})\n")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Why MSE Is a Bad Loss for Classification (the "flat gradient" trap)
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 3: MSE vs Cross-Entropy Gradient — Why Classification Needs CE")
print("=" * 70)

# Take a badly-wrong, confident prediction: true=1, predicted=0.01
y_true_bad, y_pred_bad = 1.0, 0.01

mse_grad = 2 * (y_pred_bad - y_true_bad)                       # d(MSE)/d(y_pred)
ce_grad = -(y_true_bad / y_pred_bad) + (1 - y_true_bad) / (1 - y_pred_bad)  # d(CE)/d(y_pred)

print(f"  True label: {y_true_bad}, Confidently-wrong prediction: {y_pred_bad}")
print(f"  MSE gradient magnitude:            {abs(mse_grad):.3f}")
print(f"  Cross-Entropy gradient magnitude:  {abs(ce_grad):.3f}")
print("  → Cross-entropy pushes MUCH harder to correct confident mistakes.")
print("  → This is why every classifier (and every LLM's next-token loss) uses")
print("    cross-entropy, never MSE, for anything with a probability output.\n")

print("=" * 70)
print("DONE — you just trained 2 models with pure numpy + calculus.")
print("Everything from here (perceptron → MLP → transformer) is this")
print("SAME loop (predict → measure loss → gradient → update) at bigger scale.")
print("=" * 70)
