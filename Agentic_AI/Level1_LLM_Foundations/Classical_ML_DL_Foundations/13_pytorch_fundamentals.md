# Classical ML/DL Foundations — Doc 13: PyTorch Fundamentals (Tensors, Autograd, nn.Module, Training Loop)

> **Why this doc exists:** Doc 4 solved XOR with hand-derived backprop in pure numpy so you'd SEE the chain rule work, not just call a library. That was deliberate — but nobody writes production networks that way. **PyTorch is the tool version of doc 4**: same math (tensors, forward pass, backward pass, gradient descent), except autograd computes the derivatives for you and `nn.Module` organizes the layers. Every framework you already use — HuggingFace `transformers`, `peft` (LoRA/QLoRA in `Level8_Production_LLMOps/06_llm_finetuning.md`), the training loop sketched in `Deep_Architecture/09_training_briefly.md` — is written in this exact vocabulary. This doc is the missing link between "I derived backprop by hand" and "I can read/write a real training script."

---

## 1. Tensor = numpy array + two extra powers

A PyTorch `Tensor` behaves like a numpy array (same indexing, broadcasting, matmul), but adds two things numpy doesn't have:

1. **Runs on GPU** — move it with `.to("cuda")` and every operation happens on the GPU instead of CPU.
2. **Tracks its own gradient history** — if `requires_grad=True`, PyTorch silently builds a graph of every operation applied to it, so it can later compute `d(something)/d(this tensor)` automatically.

```python
import torch
import numpy as np

# numpy world (doc 1-12)
x_np = np.array([1.0, 2.0, 3.0])

# torch world — looks identical...
x = torch.tensor([1.0, 2.0, 3.0])
print(x + 1, x * 2, x @ x)          # same ops, same broadcasting rules

# ...but this is the part numpy CANNOT do:
w = torch.tensor([2.0], requires_grad=True)   # "track gradients for this"
y = w * 3
y.backward()                                   # compute dy/dw
print(w.grad)                                  # tensor([3.]) — correct: dy/dw = 3
```

`requires_grad=True` is the single flag that turns a plain array into something autograd will differentiate through. Everything below builds on this one idea.

---

## 2. Autograd = doc 4's chain rule, done automatically

Doc 4 manually wrote six backward-pass steps (`d_z2`, `d_W2`, `d_h`, `d_z1`, `d_W1`, ...) by hand-deriving the chain rule. Autograd builds the exact same computation graph during the forward pass, then walks it backward for you.

```python
# ===== The doc-4 forward pass, in torch =====
W1 = torch.randn(2, 4, requires_grad=True)
b1 = torch.zeros(1, 4, requires_grad=True)
W2 = torch.randn(4, 1, requires_grad=True)
b2 = torch.zeros(1, 1, requires_grad=True)

X = torch.tensor([[0., 0.], [0., 1.], [1., 0.], [1., 1.]])
Y = torch.tensor([[0.], [1.], [1.], [0.]])

z1 = X @ W1 + b1
h  = torch.relu(z1)
z2 = h @ W2 + b2
y_pred = torch.sigmoid(z2)

loss = torch.nn.functional.binary_cross_entropy(y_pred, Y)

# ===== The doc-4 backward pass — ALL SIX MANUAL STEPS COLLAPSE TO ONE CALL =====
loss.backward()

print(W1.grad)   # exactly what doc 4's `d_W1` computed by hand — autograd derived it
print(W2.grad)   # exactly what doc 4's `d_W2` computed by hand
```

**What autograd actually does under the hood:** every tensor op (`@`, `+`, `relu`, `sigmoid`, the loss function) is secretly a node in a directed graph, remembering both its inputs and how to compute its own local derivative. `loss.backward()` walks that graph from the loss back to every leaf tensor with `requires_grad=True`, multiplying local derivatives along the way — this **is** the chain rule, applied automatically instead of by hand. Doc 4 built one tiny version of this graph on paper; autograd builds it for arbitrarily deep networks (GPT has 96+ layers — nobody hand-derives that).

**One gotcha every beginner hits:** gradients **accumulate** by default — a second `.backward()` call adds to the existing `.grad`, it doesn't replace it. This is why every training loop calls `optimizer.zero_grad()` before the forward pass (Section 5).

---

## 3. `nn.Module` — the layer/weight bookkeeping doc 4 did manually

In doc 4, `W1, b1, W2, b2` were plain numpy arrays you tracked yourself. `nn.Module` is PyTorch's way of grouping weights into reusable, composable layers.

```python
import torch.nn as nn

class TwoLayerMLP(nn.Module):
    def __init__(self, input_dim=2, hidden_dim=4, output_dim=1):
        super().__init__()
        self.layer1 = nn.Linear(input_dim, hidden_dim)   # owns W1, b1 internally
        self.layer2 = nn.Linear(hidden_dim, output_dim)  # owns W2, b2 internally

    def forward(self, x):
        h = torch.relu(self.layer1(x))
        return torch.sigmoid(self.layer2(h))

model = TwoLayerMLP()
y_pred = model(X)                        # calls .forward() — same architecture as doc 4

for name, param in model.named_parameters():
    print(name, param.shape)             # layer1.weight, layer1.bias, layer2.weight, layer2.bias
```

`nn.Linear(in, out)` is doing exactly `x @ W + b` (doc 1's insight that a single neuron IS a linear layer) — it just initializes `W` and `b` for you and registers them so `model.parameters()` can find every weight in the network, no matter how many layers deep.

**Composing real architectures** is just stacking these blocks — `nn.Sequential`, or writing your own `forward()` calling submodules in order. A transformer block (`Deep_Architecture/05_transformer_block.md`) is `nn.Module`s calling `nn.Module`s: attention layer → feedforward layer → layer norm, wired together in exactly this pattern.

---

## 4. Loss functions & optimizers — turning "the math" into "the update rule"

Doc 4 wrote gradient descent by hand: `W -= lr * grad`. PyTorch's `optim` package does this, plus smarter variants (momentum, adaptive learning rates).

```python
import torch.optim as optim

criterion = nn.BCELoss()                                   # binary cross-entropy (doc 3's loss function)
optimizer = optim.Adam(model.parameters(), lr=0.01)         # Adam > plain SGD for most tasks

# Common losses, matched to task (doc 3's territory):
# nn.MSELoss()          → regression (doc 1)
# nn.BCELoss()          → binary classification
# nn.CrossEntropyLoss() → multi-class classification (expects raw logits, not softmax!)
```

**Why Adam instead of plain gradient descent?** Plain SGD uses ONE learning rate for every weight, always. Adam keeps a running estimate of each weight's gradient mean AND variance, and adapts the effective step size per-weight — weights with noisy/sparse gradients get smaller, more cautious updates; weights with consistent gradients move faster. This is why virtually every deep learning training run (including LLM pre-training, `Deep_Architecture/09_training_briefly.md`) uses Adam or its variant AdamW, not vanilla SGD.

---

## 5. The Training Loop — the exact loop from `Deep_Architecture/09_training_briefly.md`, explained line by line

You've already seen this loop, unexplained, in the LLM training doc:

```python
for batch in dataset:
    logits = model(input_tokens)
    loss = cross_entropy(logits, target_tokens)
    loss.backward()
    optimizer.step()
    optimizer.zero_grad()
```

Here is every line, why it exists, and why the order matters:

```python
for epoch in range(num_epochs):
    for x_batch, y_batch in dataloader:

        optimizer.zero_grad()          # 1. Clear old gradients (they ACCUMULATE otherwise — Section 2's gotcha)

        y_pred = model(x_batch)        # 2. Forward pass — builds the autograd graph as it runs

        loss = criterion(y_pred, y_batch)   # 3. How wrong were we? (doc 3's loss functions)

        loss.backward()                # 4. Backward pass — autograd fills every param's .grad

        optimizer.step()               # 5. Gradient descent update: param -= lr * param.grad (Adam's smarter version)
```

**If you swap step 1 and step 4's order** (`zero_grad()` after `backward()` instead of before), you'd still work for a single batch — but on batch 2, the old batch's gradients are still sitting in `.grad`, and get ADDED to the new batch's gradients, silently corrupting training. This is the single most common PyTorch bug beginners hit, and now you know exactly why the fix is "call `zero_grad()` first."

---

## 6. Dataset & DataLoader — feeding data in batches

Doc 4 trained on all 4 XOR examples at once ("full-batch" gradient descent). Real datasets don't fit in memory / a single GPU pass, so PyTorch splits them into mini-batches.

```python
from torch.utils.data import Dataset, DataLoader

class XORDataset(Dataset):
    def __init__(self, X, Y):
        self.X, self.Y = X, Y
    def __len__(self):
        return len(self.X)
    def __getitem__(self, idx):
        return self.X[idx], self.Y[idx]

dataset = XORDataset(X, Y)
dataloader = DataLoader(dataset, batch_size=2, shuffle=True)

for x_batch, y_batch in dataloader:     # each iteration = one "mini-batch"
    ...
```

- **`batch_size`** — bigger batches = more stable gradient estimate, more GPU memory needed, fewer updates per epoch.
- **`shuffle=True`** — reshuffles the dataset every epoch so the model doesn't learn the ORDER of examples, only the pattern.
- This is exactly what "batch" means in `Deep_Architecture/09_training_briefly.md`'s training loop — a chunk of the 10-15 trillion pre-training tokens, not the whole corpus at once.

---

## 7. Device management — CPU vs GPU (vs Apple Silicon MPS)

```python
device = torch.device("cuda" if torch.cuda.is_available()
                       else "mps" if torch.backends.mps.is_available()   # Apple Silicon
                       else "cpu")

model = model.to(device)              # move ALL weights to the device
x_batch = x_batch.to(device)          # move THIS batch to the same device

# RULE: model and data must be on the SAME device, or you get a RuntimeError
```

Training a 7B-parameter model on CPU is theoretically possible and practically useless (weeks per epoch) — GPUs parallelize the matrix multiplications (`@` in every `nn.Linear`) across thousands of cores. This is the hardware reality behind `Deep_Architecture/09_training_briefly.md`'s "10,000+ H100 GPUs running for months."

---

## 8. Saving & Loading — checkpoints, and why LoRA only saves a *few MB*

```python
# Save just the weights (recommended — smaller, more portable than pickling the whole object)
torch.save(model.state_dict(), "model_checkpoint.pt")

# Load into a freshly-constructed model with the SAME architecture
model = TwoLayerMLP()
model.load_state_dict(torch.load("model_checkpoint.pt"))
model.eval()             # switches off dropout/batchnorm training-mode behavior (doc 5)
```

`state_dict()` is just a Python dict mapping `"layer1.weight" -> tensor`, `"layer1.bias" -> tensor`, etc. — every weight `nn.Module` tracked, nothing more. This directly explains **why LoRA checkpoints are tiny** (`09_transfer_learning.md`, `Level8_Production_LLMOps/06_llm_finetuning.md`): a LoRA adapter is a `state_dict` containing only the small injected adapter matrices, not the full frozen base model — the same `state_dict` mechanism, just with fewer entries in the dict.

---

## 9. Solving XOR — Doc 4's 27 manual lines vs PyTorch's ~10

```python
model = TwoLayerMLP()
optimizer = optim.Adam(model.parameters(), lr=0.05)
criterion = nn.BCELoss()

for epoch in range(3000):
    optimizer.zero_grad()
    y_pred = model(X)
    loss = criterion(y_pred, Y)
    loss.backward()
    optimizer.step()

print(model(X))   # same near-perfect XOR predictions as doc 4's hand-rolled version
```

Same problem, same underlying math (doc 4 proved this by hand), same result — autograd + `nn.Module` + `optim` just remove the bookkeeping. The practical for this doc runs BOTH side by side and confirms the gradients match.

---

## 10. Where This Shows Up In Your Real Work

| Concept here | Where you already use it (without the vocabulary) |
|---|---|
| `Tensor` + `requires_grad` | Every HuggingFace `transformers`/`peft` model — weights are `nn.Parameter` tensors under the hood |
| `nn.Module` composition | A transformer block (`Deep_Architecture/05_transformer_block.md`) is `nn.Module`s wrapping `nn.Module`s |
| `loss.backward()` | The single line doing everything doc 4 derived across 6 manual steps |
| `optimizer.zero_grad()` → `step()` | The exact loop shown unexplained in `Deep_Architecture/09_training_briefly.md` |
| `state_dict()` | Why `Level8_Production_LLMOps/06_llm_finetuning.md`'s LoRA adapters are a few MB, not the full model |
| `DataLoader` batching | "Batch" in every training-loop code snippet you've read across this repo |
| `.to(device)` | Why fine-tuning needs a GPU and why `10_gans_diffusion_image_gen.md` / vision models need CUDA |

**This doc doesn't teach a new concept** — every idea (forward pass, backprop, gradient descent, batching) was already covered in docs 1-9. It teaches the **tool vocabulary** so that reading a real `transformers`/`peft`/`trl` training script, or a PyTorch error message, is no longer opaque.

---

## 11. Interview-Ready Questions

1. What does `requires_grad=True` actually do, mechanically?
2. Why does PyTorch require `optimizer.zero_grad()` before every backward pass?
3. What's the relationship between `nn.Linear` and doc 1's "logistic regression IS a 1-neuron network"?
4. Why does `nn.CrossEntropyLoss` expect raw logits instead of softmax probabilities? *(it applies softmax internally — feeding it already-softmaxed values double-applies softmax and breaks training)*
5. Why is Adam preferred over plain SGD for most deep learning?
6. What's actually inside a `state_dict()`, and why does that explain LoRA's tiny checkpoint size?
7. What happens if model and input tensor are on different devices?
8. Trace `loss.backward()` back to doc 4's six manual backprop steps — what's the correspondence?

---

## 12. Quick Recap

| Concept | One-liner |
|---|---|
| `Tensor` | numpy array + GPU support + optional gradient tracking |
| `requires_grad=True` | "Track every operation on this tensor so autograd can differentiate through it later" |
| Autograd | Builds a computation graph during forward pass, walks it backward on `.backward()` — automates doc 4's chain rule |
| `nn.Module` | Groups weights into reusable layers; `nn.Linear` = doc 1's `x @ W + b`, generalized |
| `optim.Adam`/`SGD` | Turns `.grad` into a weight update — Adam adapts the learning rate per-weight |
| Training loop | `zero_grad() → forward → loss → backward() → step()` — order matters because grads accumulate |
| `DataLoader` | Splits a dataset into shuffled mini-batches |
| `.to(device)` | Moves tensors/model to CPU/GPU/MPS — model and data must match |
| `state_dict()` | A plain dict of every tracked weight — the save/load unit, and why LoRA checkpoints are small |

**Folder complete.** You've gone from a single neuron (doc 1) through backprop-by-hand (doc 4), CNNs, RNNs, the bridge to Transformers (doc 8), transfer learning (doc 9), classical ML/NLP breadth (docs 11-12), to the actual tool (doc 13) every framework in this repo is built on.
