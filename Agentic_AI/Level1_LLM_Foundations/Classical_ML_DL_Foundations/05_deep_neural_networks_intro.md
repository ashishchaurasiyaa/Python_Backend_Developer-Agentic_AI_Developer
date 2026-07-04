# Classical ML/DL Foundations — Doc 5: Introduction to Deep Neural Networks

> **Goal:** Ab tak humne 1-2 layer networks dekhe. "Deep" learning ka matlab hai many layers (10s to 100s). Zyada layers naya power dete hain, lekin naye problems bhi — overfitting, exploding/vanishing gradients, training instability. Yeh doc un problems aur unke standard fixes (regularization, dropout, batch norm, residual connections) ko cover karta hai — sab kuch jo aage transformers me already use ho raha hai.

---

## 1. What Changes When You Go From "Shallow" to "Deep"

```
Shallow (1-2 hidden layers):        Deep (10-100+ layers):
input → hidden → output              input → h1 → h2 → h3 → ... → h50 → output
```

More layers = more capacity to learn hierarchical features (doc 2's point: edges → shapes → objects, or in language: characters → words → phrases → meaning). But more layers also mean:

1. **Harder to train** — vanishing/exploding gradients compound with depth (doc 4).
2. **Easier to overfit** — more parameters can memorize training data instead of learning general patterns.
3. **Slower to train** — more sequential computation, though this parallelizes well on GPUs.

---

## 2. Overfitting — The Core Deep Learning Problem

**Overfitting** = model performs great on training data, badly on new/unseen data. It memorized instead of generalized.

```
Training loss:    ↓↓↓↓↓↓↓↓↓↓↓↓  (keeps dropping)
Validation loss:  ↓↓↓___↑↑↑↑↑    (drops, then starts RISING — this is overfitting starting)
                        ^
                        stop training here (early stopping)
```

**Why deep networks overfit more easily:** millions/billions of parameters give the network enough "room" to literally memorize training examples (including their noise) rather than learn the underlying pattern.

### 2.1 Fixes for Overfitting

**Regularization (L1/L2 weight penalty):** add a penalty term to the loss based on weight magnitude, discouraging any single weight from growing huge.
```python
loss_with_l2 = loss + lambda_ * sum(w ** 2 for w in all_weights)
```
Large weights often mean the model is fitting noise very precisely; penalizing them nudges toward simpler, smoother functions.

**Dropout:** during training, randomly "turn off" (zero out) a fraction of neurons on each forward pass (commonly 20-50%).
```python
# During training only:
mask = (np.random.rand(*h.shape) > dropout_rate).astype(float)
h = h * mask / (1 - dropout_rate)   # scale to keep expected value the same
```
Forces the network to not rely on any single neuron too heavily — it has to build redundant, robust representations because it never knows which neurons will be "on." At inference time, dropout is turned off (use the full network).

**Early stopping:** monitor validation loss during training, stop when it starts rising even if training loss keeps dropping. Simple and almost always used in practice.

**More data / data augmentation:** the most direct fix — a model can't memorize what it hasn't seen enough times. (In vision: random crops/flips/rotations. In NLP/LLMs: this is why pretraining corpora are trillions of tokens — enough scale that memorization becomes statistically difficult for any single example.)

---

## 3. Batch Normalization — Stabilizing Deep Training

As data flows through many layers, the distribution of activations at each layer can shift and become unstable during training (called "internal covariate shift"). **Batch normalization** normalizes each layer's output (per mini-batch) to have mean ≈0, std ≈1, then lets the network learn a scale/shift on top:

```python
z_norm = (z - batch_mean) / sqrt(batch_var + eps)
z_out = gamma * z_norm + beta     # gamma, beta are learned parameters
```

Effects: allows higher learning rates, less sensitive to weight initialization, acts as mild regularization too. Very standard in CNNs (doc 6). Transformers use a close relative called **LayerNorm** (normalizes across features for one example, not across the batch) — you've already seen this in `Deep_Architecture/05_transformer_block.md` ("Add & Norm" step) — same underlying motivation, different axis of normalization.

---

## 4. Residual Connections ("Skip Connections") — Enabling Real Depth

Before 2015, networks deeper than ~20 layers actually got *worse* — not from overfitting, but because gradients (and even the forward signal) degraded across so many layers ("degradation problem"). The fix, from the ResNet paper (2015):

```python
# Normal layer:
output = layer(x)

# Residual layer:
output = layer(x) + x        # add the ORIGINAL input back
```

Why this helps: it gives the gradient a direct, unimpeded path backward (the `+ x` term has a derivative of exactly 1, so at minimum the gradient always has one "unblocked lane" back to earlier layers, no matter how deep). This single idea is what made networks with 100+ layers (and eventually transformers with 96+ layers) trainable at all.

**You already know this from transformers** — every "Add & Norm" step in `Deep_Architecture/05_transformer_block.md` and `06_layer_stacking_and_output.md` IS a residual connection. GPT-4's 96 layers only work because of this exact trick, invented for CNNs a decade earlier and inherited wholesale by transformers.

---

## 5. Putting It Together — What a "Modern Deep Layer" Actually Looks Like

```
x_out = x_in + Dropout( Layer( LayerNorm(x_in) ) )
        ^^^^^^        ^^^^^^^   ^^^^^^^^^^^^^^^^
        residual      regularize  normalize first (stabilize)
        connection
```

This exact pattern (Norm → Layer → Dropout → residual add) is the template used inside every transformer block. Nothing here is transformer-specific invention — it's the accumulated toolkit of "how to make very deep networks trainable," built up through the 2010s on CNNs and RNNs, then inherited by transformers in 2017.

---

## 6. Where This Shows Up in Your Real Work

- **"Why do LLMs need residual connections?"** — classic interview question; answer: without them, 96-layer networks wouldn't train at all (gradient degradation), not just "would overfit."
- **Fine-tuning stability** (`Level8_Production_LLMOps/06_llm_finetuning.md`) — dropout and weight decay (L2 regularization) are exactly the levers you tune when a fine-tune overfits on a small custom dataset.
- **"Model does great on my test prompts but breaks in production"** — classic overfitting-to-your-eval-set pattern; the fix vocabulary (more diverse eval data, don't over-tune to a fixed prompt set) mirrors doc's "more data" fix directly.

---

## 7. Quick Recap

| Problem | Fix | Where you've seen it already |
|---|---|---|
| Overfitting | L1/L2 regularization, dropout, early stopping | fine-tuning small datasets |
| Unstable training | Batch norm / Layer norm | transformer "Add & Norm" |
| Degrading gradients at depth | Residual (skip) connections | every transformer block |
| Not enough data | Data augmentation / more data | trillion-token pretraining corpora |

**Next:** [`06_cnn_computer_vision.md`](06_cnn_computer_vision.md) — the architecture family that popularized dropout, batch norm, and residual connections in the first place: Convolutional Neural Networks.
