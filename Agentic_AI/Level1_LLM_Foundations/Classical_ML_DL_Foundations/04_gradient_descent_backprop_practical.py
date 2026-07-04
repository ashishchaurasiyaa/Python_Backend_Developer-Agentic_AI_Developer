"""
Classical ML/DL Foundations — Doc 4: BACKPROPAGATION FROM SCRATCH (PRACTICAL)
=============================================================================
No PyTorch, no autograd. Every gradient below is hand-derived chain rule,
computed with pure numpy — so you SEE backprop, not just call .backward().

Solves XOR — the exact problem doc 2 showed a single perceptron CANNOT
solve. A 2-layer MLP trained with manual backprop solves it easily.

Run this to see:
  1. Manual forward pass (2-layer MLP: input -> hidden(ReLU) -> output(sigmoid))
  2. Manual backward pass (chain rule, step by step, matching the doc's derivation)
  3. Gradient descent updates over epochs
  4. Loss dropping to ~0 and XOR being solved perfectly
  5. A vanishing-gradient demo: same task with sigmoid hidden layer instead of ReLU

Install:
  pip install numpy

Run: python 04_gradient_descent_backprop_practical.py
"""

import numpy as np

np.random.seed(1)


def sigmoid(z):
    return 1 / (1 + np.exp(-z))


def relu(z):
    return np.maximum(0, z)


def relu_deriv(z):
    return (z > 0).astype(float)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: The XOR Dataset (unsolvable by 1 neuron, per doc 2)
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 1: XOR Dataset")
print("=" * 70)

X = np.array([[0, 0], [0, 1], [1, 0], [1, 1]], dtype=float)   # 4 examples, 2 features
Y = np.array([[0], [1], [1], [0]], dtype=float)                # XOR truth table

print("Inputs:\n", X)
print("XOR targets:\n", Y.ravel())
print()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Manual Forward + Backward Pass (2-layer MLP, ReLU hidden layer)
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 2: Training a 2-Layer MLP with Hand-Derived Backprop (ReLU)")
print("=" * 70)

input_dim, hidden_dim, output_dim = 2, 4, 1
lr = 0.5

# Small random init — zeros would make every hidden neuron identical (symmetry trap)
W1 = np.random.randn(input_dim, hidden_dim) * 0.5
b1 = np.zeros((1, hidden_dim))
W2 = np.random.randn(hidden_dim, output_dim) * 0.5
b2 = np.zeros((1, output_dim))

losses = []
for epoch in range(3000):
    # ---- FORWARD PASS ----
    z1 = X @ W1 + b1            # [4, hidden_dim]
    h = relu(z1)                 # [4, hidden_dim]
    z2 = h @ W2 + b2            # [4, 1]
    y_pred = sigmoid(z2)        # [4, 1]

    eps = 1e-9
    loss = -np.mean(Y * np.log(y_pred + eps) + (1 - Y) * np.log(1 - y_pred + eps))
    losses.append(loss)

    # ---- BACKWARD PASS (matches doc 4's Step 1-6 derivation exactly) ----
    n = X.shape[0]

    # Step 1+2 combined: for sigmoid + cross-entropy, d(loss)/d(z2) simplifies to (y_pred - y_true)
    d_z2 = (y_pred - Y) / n                          # [4, 1]

    # Step 3: gradient for W2, b2
    d_W2 = h.T @ d_z2                                 # [hidden_dim, 1]
    d_b2 = np.sum(d_z2, axis=0, keepdims=True)

    # Step 4: pass gradient back to hidden layer
    d_h = d_z2 @ W2.T                                 # [4, hidden_dim]

    # Step 5: chain through ReLU derivative
    d_z1 = d_h * relu_deriv(z1)                       # [4, hidden_dim]

    # Step 6: gradient for W1, b1
    d_W1 = X.T @ d_z1                                 # [input_dim, hidden_dim]
    d_b1 = np.sum(d_z1, axis=0, keepdims=True)

    # ---- GRADIENT DESCENT UPDATE ----
    W2 -= lr * d_W2
    b2 -= lr * d_b2
    W1 -= lr * d_W1
    b1 -= lr * d_b1

    if epoch % 500 == 0:
        print(f"  epoch {epoch:>4} | loss={loss:.5f}")

print(f"\nFinal loss: {losses[-1]:.6f}")
print("Predictions vs truth:")
final_pred = sigmoid(relu(X @ W1 + b1) @ W2 + b2)
for xi, pred, true in zip(X, final_pred.ravel(), Y.ravel()):
    print(f"  input={xi} → predicted={pred:.3f} (rounds to {round(pred)}) | true={true}")

print("\n→ A single perceptron CANNOT do this (doc 2). A 2-layer MLP CAN.")
print("  This is backprop + gradient descent, hand-derived, actually working.\n")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Vanishing Gradient Demo — Same Task, Sigmoid Hidden Layer Instead
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 3: Same Network, Sigmoid Hidden Layer — Watch Gradients Shrink")
print("=" * 70)

np.random.seed(1)
W1s = np.random.randn(input_dim, hidden_dim) * 0.5
b1s = np.zeros((1, hidden_dim))
W2s = np.random.randn(hidden_dim, output_dim) * 0.5
b2s = np.zeros((1, output_dim))

for epoch in range(3000):
    z1 = X @ W1s + b1s
    h = sigmoid(z1)                                    # sigmoid instead of relu
    z2 = h @ W2s + b2s
    y_pred = sigmoid(z2)

    n = X.shape[0]
    d_z2 = (y_pred - Y) / n
    d_W2 = h.T @ d_z2
    d_b2 = np.sum(d_z2, axis=0, keepdims=True)
    d_h = d_z2 @ W2s.T
    d_z1 = d_h * (h * (1 - h))                          # sigmoid derivative, max 0.25
    d_W1 = X.T @ d_z1
    d_b1 = np.sum(d_z1, axis=0, keepdims=True)

    if epoch == 0:
        print(f"  Gradient reaching W1 at epoch 0: mean |grad| = {np.mean(np.abs(d_W1)):.6f}")

    W2s -= lr * d_W2
    b2s -= lr * d_b2
    W1s -= lr * d_W1
    b1s -= lr * d_b1

eps = 1e-9
final_loss_sigmoid = -np.mean(Y * np.log(sigmoid(sigmoid(X @ W1s + b1s) @ W2s + b2s) + eps)
                               + (1 - Y) * np.log(1 - sigmoid(sigmoid(X @ W1s + b1s) @ W2s + b2s) + eps))

print(f"  Final loss with sigmoid hidden layer: {final_loss_sigmoid:.5f}")
print(f"  Final loss with ReLU hidden layer:    {losses[-1]:.6f}")
print("  → On this TINY 2-layer network the difference is small, but stack 10+")
print("    sigmoid layers and the gradient reaching W1 shrinks toward zero —")
print("    exactly the vanishing-gradient math shown in doc 3 and doc 4.")
print("=" * 70)
