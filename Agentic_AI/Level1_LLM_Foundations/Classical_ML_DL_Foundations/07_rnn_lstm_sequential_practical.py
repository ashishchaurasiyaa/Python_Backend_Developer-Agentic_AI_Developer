"""
Classical ML/DL Foundations — Doc 7: VANILLA RNN + BPTT (PRACTICAL)
=============================================================================
From-scratch, numpy-only. No PyTorch. Implements a vanilla RNN forward pass
and Backpropagation Through Time (BPTT) by hand, then directly MEASURES the
vanishing-gradient-over-time effect the doc describes.

Task: "sum parity" — given a sequence of 0/1 bits, predict whether the
count of 1s is even or odd. Requires remembering information across the
WHOLE sequence, so it's a good demo for how gradient signal decays with
sequence length.

Run this to see:
  1. A vanilla RNN forward pass, step by step
  2. BPTT computing the gradient at EVERY time step
  3. The gradient magnitude reaching early time steps SHRINKING as the
     sequence gets longer (the vanishing gradient problem, measured directly)
  4. Training the RNN on short sequences (where it CAN learn) vs long
     sequences (where plain RNN struggles)

Install:
  pip install numpy

Run: python 07_rnn_lstm_sequential_practical.py
"""

import numpy as np

np.random.seed(0)


def sigmoid(z):
    return 1 / (1 + np.exp(-z))


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Vanilla RNN Forward Pass
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 1: Vanilla RNN Forward Pass on a Toy Sequence")
print("=" * 70)

hidden_dim = 4
Wx = np.random.randn(1, hidden_dim) * 0.5     # input -> hidden
Wh = np.random.randn(hidden_dim, hidden_dim) * 0.5   # hidden -> hidden (the "recurrent" weight)
bh = np.zeros((1, hidden_dim))
Wy = np.random.randn(hidden_dim, 1) * 0.5     # hidden -> output
by = np.zeros((1, 1))


def rnn_forward(sequence):
    """sequence: list of scalars (0.0/1.0 bits). Returns hidden states + final prediction."""
    h = np.zeros((1, hidden_dim))
    hidden_states = [h]
    for x in sequence:
        x_arr = np.array([[x]])
        h = np.tanh(x_arr @ Wx + h @ Wh + bh)
        hidden_states.append(h)
    y_pred = sigmoid(h @ Wy + by)
    return hidden_states, y_pred


seq = [1.0, 0.0, 1.0, 1.0]
hidden_states, y_pred = rnn_forward(seq)
print(f"Input sequence: {seq}  (parity: {'odd' if sum(seq) % 2 else 'even'} number of 1s)")
print(f"Number of hidden states produced: {len(hidden_states)} (initial h0 + one per input)")
print(f"Final prediction (probability of 'odd'): {y_pred.item():.4f}\n")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: BPTT — Backprop Through Time, Measuring Gradient at Each Step
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 2: BPTT — Gradient Magnitude Reaching Each Time Step")
print("=" * 70)


def rnn_bptt_gradient_trace(sequence, y_true):
    """Runs forward + BPTT, returns the gradient magnitude reaching h_t at each step."""
    h = np.zeros((1, hidden_dim))
    hidden_states = [h]
    raw_pre_activations = []
    for x in sequence:
        x_arr = np.array([[x]])
        z = x_arr @ Wx + h @ Wh + bh
        h = np.tanh(z)
        raw_pre_activations.append(z)
        hidden_states.append(h)

    y_pred = sigmoid(h @ Wy + by)
    eps = 1e-9
    loss = -(y_true * np.log(y_pred + eps) + (1 - y_true) * np.log(1 - y_pred + eps))

    # Backward pass through time
    d_y = y_pred - y_true                          # d(loss)/d(pre-sigmoid output)
    d_h = d_y @ Wy.T                                 # gradient flowing INTO the last hidden state

    grad_magnitudes = []  # magnitude of gradient reaching each h_t, walking backward
    T = len(sequence)
    for t in reversed(range(T)):
        grad_magnitudes.append((t, float(np.linalg.norm(d_h))))
        z = raw_pre_activations[t]
        d_z = d_h * (1 - np.tanh(z) ** 2)            # chain through tanh derivative
        d_h = d_z @ Wh.T                             # propagate to the PREVIOUS time step

    grad_magnitudes.reverse()   # now in chronological (t=0 ... t=T-1) order
    return loss.item(), grad_magnitudes


for length in [4, 10, 20, 40]:
    seq_test = list(np.random.randint(0, 2, size=length).astype(float))
    y_true = float(sum(seq_test) % 2 == 1)
    loss, grads = rnn_bptt_gradient_trace(seq_test, y_true)
    first_step_grad = grads[0][1]
    last_step_grad = grads[-1][1]
    print(f"  seq_len={length:>3} | grad at t=0 (earliest): {first_step_grad:.6f} "
          f"| grad at t={length-1} (latest): {last_step_grad:.6f} "
          f"| ratio (early/late): {first_step_grad / max(last_step_grad, 1e-12):.6f}")

print("\n→ As sequence length grows, the gradient reaching the EARLIEST time step")
print("  shrinks toward zero relative to the latest step — the RNN is progressively")
print("  less able to learn from information far back in a long sequence.")
print("  This is the exact vanishing-gradient-over-time problem doc 7 describes,")
print("  and precisely why LSTMs (additive cell state) and eventually attention")
print("  (direct token-to-token connections, no multiplicative chain) replaced it.\n")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Training on Short vs Long Sequences
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 3: RNN Trains Fine on Short Sequences, Struggles on Long Ones")
print("=" * 70)


def train_parity_rnn(seq_length, n_examples=200, epochs=300, lr=0.1):
    global Wx, Wh, bh, Wy, by
    Wx = np.random.randn(1, hidden_dim) * 0.5
    Wh = np.random.randn(hidden_dim, hidden_dim) * 0.5
    bh = np.zeros((1, hidden_dim))
    Wy = np.random.randn(hidden_dim, 1) * 0.5
    by = np.zeros((1, 1))

    sequences = [list(np.random.randint(0, 2, size=seq_length).astype(float)) for _ in range(n_examples)]
    labels = [float(sum(s) % 2 == 1) for s in sequences]

    for epoch in range(epochs):
        for seq_i, y_true in zip(sequences, labels):
            h = np.zeros((1, hidden_dim))
            hs, zs = [h], []
            for x in seq_i:
                x_arr = np.array([[x]])
                z = x_arr @ Wx + h @ Wh + bh
                h = np.tanh(z)
                zs.append(z)
                hs.append(h)
            y_pred = sigmoid(h @ Wy + by)

            d_y = y_pred - y_true
            d_Wy = hs[-1].T @ d_y
            d_by = d_y
            d_h = d_y @ Wy.T

            d_Wx = np.zeros_like(Wx)
            d_Wh = np.zeros_like(Wh)
            d_bh = np.zeros_like(bh)
            for t in reversed(range(len(seq_i))):
                d_z = d_h * (1 - np.tanh(zs[t]) ** 2)
                x_arr = np.array([[seq_i[t]]])
                d_Wx += x_arr.T @ d_z
                d_Wh += hs[t].T @ d_z
                d_bh += d_z
                d_h = d_z @ Wh.T

            Wy -= lr * d_Wy
            by -= lr * d_by
            Wx -= lr * d_Wx
            Wh -= lr * d_Wh
            bh -= lr * d_bh

    # Evaluate
    correct = 0
    for seq_i, y_true in zip(sequences, labels):
        _, y_pred = rnn_forward(seq_i)
        correct += int((y_pred.item() > 0.5) == bool(y_true))
    return correct / n_examples


for length in [3, 8, 15]:
    acc = train_parity_rnn(seq_length=length, epochs=150)
    print(f"  seq_length={length:>2} → training accuracy after 150 epochs: {acc:.1%}")

print("\n→ Accuracy typically drops as sequence length grows — the parity task")
print("  needs the network to remember EVERY bit across the whole sequence, and")
print("  a plain RNN's vanishing gradient makes that progressively harder to learn.")
print("=" * 70)
