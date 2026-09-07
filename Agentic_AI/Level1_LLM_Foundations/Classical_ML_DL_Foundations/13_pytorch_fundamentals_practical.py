"""
Classical ML/DL Foundations — Doc 13: PYTORCH FUNDAMENTALS (PRACTICAL)
=======================================================================
Doc 4 solved XOR with hand-derived backprop, pure numpy, zero autograd.
This practical solves the SAME problem with PyTorch, then proves the two
approaches compute the SAME gradients — so autograd isn't magic, it's the
exact chain rule from doc 4, automated.

Run this to see:
  1. Tensors + requires_grad + .backward() on a toy example
  2. Manual numpy gradient (doc 4's math) vs PyTorch autograd gradient —
     side by side, on the identical weights, proving they match
  3. nn.Module + optim.Adam solving XOR (doc 4's problem, PyTorch's tools)
  4. The training loop from Deep_Architecture/09_training_briefly.md, explained
  5. DataLoader batching over a synthetic dataset
  6. Device selection (CPU/CUDA/MPS)
  7. Save/load a state_dict checkpoint — and why LoRA checkpoints are tiny

Install:
  pip install torch numpy

Run: python 13_pytorch_fundamentals_practical.py
"""

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader

torch.manual_seed(1)
np.random.seed(1)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Tensors + requires_grad + .backward() — the one flag that matters
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 1: Tensor Basics — requires_grad + .backward()")
print("=" * 70)

w = torch.tensor([2.0], requires_grad=True)
y = w * 3
y.backward()
print(f"  w = 2.0, y = w * 3")
print(f"  dy/dw computed by autograd: {w.grad.item()}  (correct answer: 3.0)")

# Gradient accumulation gotcha (Section 2 of the doc)
y2 = w * 3
y2.backward()
print(f"  After a SECOND .backward() without zero_grad(): w.grad = {w.grad.item()}"
      f"  <- accumulated (3+3), NOT overwritten. This is why training loops call zero_grad().")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Manual numpy gradient (doc 4) vs PyTorch autograd — do they match?
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 2: Doc 4's Manual Backprop vs PyTorch Autograd (same weights)")
print("=" * 70)

X_np = np.array([[0, 0], [0, 1], [1, 0], [1, 1]], dtype=np.float64)
Y_np = np.array([[0], [1], [1], [0]], dtype=np.float64)

# Fixed weights so BOTH methods start identical (no randomness to explain away)
W1_init = np.array([[0.5, -0.3, 0.2, 0.8], [-0.4, 0.6, 0.1, -0.7]])
b1_init = np.zeros((1, 4))
W2_init = np.array([[0.3], [-0.5], [0.7], [0.2]])
b2_init = np.zeros((1, 1))


def relu(z):
    return np.maximum(0, z)


def relu_deriv(z):
    return (z > 0).astype(float)


def sigmoid(z):
    return 1 / (1 + np.exp(-z))


# ---- Manual numpy forward + backward (doc 4's exact steps) ----
z1 = X_np @ W1_init + b1_init
h = relu(z1)
z2 = h @ W2_init + b2_init
y_pred = sigmoid(z2)

n = X_np.shape[0]
d_z2 = (y_pred - Y_np) / n
d_W2_manual = h.T @ d_z2
d_h = d_z2 @ W2_init.T
d_z1 = d_h * relu_deriv(z1)
d_W1_manual = X_np.T @ d_z1

# ---- Same computation, PyTorch autograd ----
X_t = torch.tensor(X_np, dtype=torch.float64)
Y_t = torch.tensor(Y_np, dtype=torch.float64)
W1_t = torch.tensor(W1_init, dtype=torch.float64, requires_grad=True)
b1_t = torch.tensor(b1_init, dtype=torch.float64, requires_grad=True)
W2_t = torch.tensor(W2_init, dtype=torch.float64, requires_grad=True)
b2_t = torch.tensor(b2_init, dtype=torch.float64, requires_grad=True)

z1_t = X_t @ W1_t + b1_t
h_t = torch.relu(z1_t)
z2_t = h_t @ W2_t + b2_t
y_pred_t = torch.sigmoid(z2_t)

loss_t = torch.nn.functional.binary_cross_entropy(y_pred_t, Y_t)
loss_t.backward()   # <- this ONE line replaces doc 4's six manual backward steps

print(f"  Manual  d_W1 (doc 4's hand-derived chain rule):\n{d_W1_manual}")
print(f"\n  Autograd d_W1 (W1_t.grad, one .backward() call):\n{W1_t.grad.numpy()}")
print(f"\n  Max absolute difference: {np.abs(d_W1_manual - W1_t.grad.numpy()).max():.2e}")
print("  -> Effectively zero. Autograd computed the IDENTICAL gradient doc 4 derived by hand.")

print(f"\n  Manual  d_W2:\n{d_W2_manual.ravel()}")
print(f"  Autograd d_W2:\n{W2_t.grad.numpy().ravel()}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: nn.Module + optim.Adam solving XOR (doc 4's problem, real tools)
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 3: nn.Module + Adam Solving XOR")
print("=" * 70)


class TwoLayerMLP(nn.Module):
    def __init__(self, input_dim=2, hidden_dim=4, output_dim=1):
        super().__init__()
        self.layer1 = nn.Linear(input_dim, hidden_dim)
        self.layer2 = nn.Linear(hidden_dim, output_dim)

    def forward(self, x):
        h = torch.relu(self.layer1(x))
        return torch.sigmoid(self.layer2(h))


X = torch.tensor([[0., 0.], [0., 1.], [1., 0.], [1., 1.]])
Y = torch.tensor([[0.], [1.], [1.], [0.]])

model = TwoLayerMLP()
optimizer = optim.Adam(model.parameters(), lr=0.05)
criterion = nn.BCELoss()

print("\n  Model parameters (nn.Module tracks these automatically):")
for name, param in model.named_parameters():
    print(f"    {name:<16}: shape={tuple(param.shape)}")

losses = []
for epoch in range(2000):
    optimizer.zero_grad()          # 1. clear old gradients
    y_pred = model(X)              # 2. forward pass
    loss = criterion(y_pred, Y)    # 3. compute loss
    loss.backward()                # 4. backward pass (autograd)
    optimizer.step()               # 5. gradient descent update
    losses.append(loss.item())

    if epoch % 400 == 0:
        print(f"  epoch {epoch:>4} | loss={loss.item():.5f}")

print(f"\n  Final loss: {losses[-1]:.6f}")
print("  Predictions vs truth:")
with torch.no_grad():
    final_pred = model(X)
for xi, pred, true in zip(X, final_pred.ravel(), Y.ravel()):
    print(f"    input={xi.tolist()} -> predicted={pred.item():.3f} "
          f"(rounds to {round(pred.item())}) | true={int(true.item())}")

print("\n  -> Same XOR problem as doc 4, same result. nn.Module + optim.Adam")
print("     replaced the manual W1/b1/W2/b2 tracking and gradient descent loop.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: DataLoader — batching a synthetic dataset
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 4: Dataset + DataLoader Batching")
print("=" * 70)


class ToyDataset(Dataset):
    def __init__(self, n_samples=20):
        rng = np.random.RandomState(0)
        self.X = torch.tensor(rng.randn(n_samples, 2), dtype=torch.float32)
        self.Y = (self.X.sum(dim=1) > 0).float().unsqueeze(1)

    def __len__(self):
        return len(self.X)

    def __getitem__(self, idx):
        return self.X[idx], self.Y[idx]


dataset = ToyDataset(n_samples=20)
dataloader = DataLoader(dataset, batch_size=4, shuffle=True)

print(f"  Dataset size: {len(dataset)} examples, batch_size=4")
print(f"  Number of batches per epoch: {len(dataloader)}")
for i, (x_batch, y_batch) in enumerate(dataloader):
    print(f"    batch {i}: x_batch.shape={tuple(x_batch.shape)}, y_batch.shape={tuple(y_batch.shape)}")
    if i == 1:
        print("    ...")
        break


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Device selection — CPU / CUDA / MPS
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 5: Device Selection")
print("=" * 70)

device = torch.device(
    "cuda" if torch.cuda.is_available()
    else "mps" if torch.backends.mps.is_available()
    else "cpu"
)
print(f"  Selected device: {device}")
model_on_device = model.to(device)
sample_on_device = X.to(device)
with torch.no_grad():
    _ = model_on_device(sample_on_device)
print(f"  Model + a batch moved to '{device}' and ran forward pass successfully.")
print("  RULE: model and input tensors must be on the SAME device or you get a RuntimeError.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Save/Load state_dict — why LoRA checkpoints are tiny
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 6: state_dict Save/Load")
print("=" * 70)

state = model.state_dict()
print("  state_dict keys and shapes (this IS the entire checkpoint):")
total_params = 0
for k, v in state.items():
    print(f"    {k:<16}: shape={tuple(v.shape)}, params={v.numel()}")
    total_params += v.numel()
print(f"  Total trainable parameters in this tiny model: {total_params}")

import io
buffer = io.BytesIO()
torch.save(state, buffer)
checkpoint_bytes = len(buffer.getvalue())
print(f"  Serialized checkpoint size: {checkpoint_bytes} bytes")

reloaded_model = TwoLayerMLP()
buffer.seek(0)
reloaded_model.load_state_dict(torch.load(buffer, weights_only=True))
reloaded_model.eval()
with torch.no_grad():
    reloaded_pred = reloaded_model(X)
match = torch.allclose(final_pred, reloaded_pred)
print(f"  Reloaded model produces identical predictions: {match}")
print("\n  -> A LoRA adapter is this SAME mechanism, just with only the small adapter")
print("     matrices in the dict instead of a full model's weights — that's the")
print("     entire reason LoRA checkpoints are megabytes instead of gigabytes.")

print("\n" + "=" * 70)
print("PYTORCH FUNDAMENTALS SUMMARY:")
print("  Tensor = numpy array + GPU + optional gradient tracking (requires_grad)")
print("  Autograd = doc 4's manual chain rule, automated via .backward()")
print("  nn.Module = groups weights into layers (nn.Linear = doc 1's x @ W + b)")
print("  Training loop = zero_grad() -> forward -> loss -> backward() -> step()")
print("  DataLoader = mini-batches; .to(device) = CPU/GPU placement")
print("  state_dict() = the save/load unit; LoRA's small checkpoints = fewer keys")
print("=" * 70)
