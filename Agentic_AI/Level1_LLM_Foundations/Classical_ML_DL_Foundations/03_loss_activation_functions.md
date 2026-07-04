# Classical ML/DL Foundations — Doc 3: Loss Functions & Activation Functions

> **Goal:** Two separate "which function do I use" decisions that every network needs — (1) what non-linearity goes between layers (activation), (2) what number tells the network "how wrong are you" (loss). Interviewers love asking "why ReLU over sigmoid" and "why cross-entropy over MSE" — this doc gives you both answers with the actual reasoning, not just the name.

---

## 1. Activation Functions — The Non-Linearity Between Layers

Recap from doc 2: without a non-linear activation, stacked layers collapse into one linear layer. Activation functions are what makes depth meaningful.

### 1.1 Sigmoid

```python
sigmoid(z) = 1 / (1 + exp(-z))     # output range: (0, 1)
```

- Good for: final layer of binary classifiers (output = probability)
- **Bad for hidden layers** in deep networks — here's why:

**Vanishing gradient problem:** sigmoid's derivative is `sigmoid(z) * (1 - sigmoid(z))`, whose maximum value is only **0.25** (at z=0), and it approaches **0** for large |z|.

```
sigmoid derivative:
0.25 |        __
     |      /    \
     |    /        \
0.00 |__/            \__
    -5    0    5
```

During backpropagation (next doc), gradients get **multiplied** together layer by layer (chain rule). If every layer's gradient is ≤0.25, after 10 layers: `0.25^10 ≈ 0.00000095` — the gradient signal essentially vanishes before it reaches early layers. Those layers stop learning. This is a real historical reason deep networks were hard to train before ReLU became standard (~2010s).

### 1.2 Tanh

```python
tanh(z) = (exp(z) - exp(-z)) / (exp(z) + exp(-z))     # output range: (-1, 1)
```

Same shape as sigmoid but centered at 0 (zero-centered outputs help gradient flow slightly), max derivative is 1.0 (vs sigmoid's 0.25) — better, but still vanishes for large |z|.

### 1.3 ReLU (Rectified Linear Unit) — The Modern Default

```python
relu(z) = max(0, z)
```

```
       |      /
       |    /
_______|__/________
       0
```

- Derivative is either **0** (z<0) or **1** (z>0) — no shrinking multiplication across layers for the "on" neurons. This is *the* reason ReLU enabled training much deeper networks (10s to 100s of layers).
- Extremely cheap to compute (just a max operation) — matters at GPU scale.
- **Downside — "dying ReLU":** if a neuron's weights push `z` permanently negative, its gradient is always 0 → it never updates again ("dead neuron"). Fixes: Leaky ReLU (`max(0.01z, z)`), GELU (smooth version, used in GPT/BERT).

### 1.4 GELU — What Transformers Actually Use

```
GELU(z) ≈ z * sigmoid(1.702 * z)
```

A smooth approximation of ReLU that doesn't have a hard cutoff at 0. GPT, BERT, and most modern transformer MLPs use GELU (or its variant SwiGLU in Llama/PaLM) instead of plain ReLU — smoother gradients, empirically better performance. You've seen this mentioned in `Deep_Architecture/06_layer_stacking_and_output.md`; this is the "why GELU not ReLU" answer.

### 1.5 Softmax — For Multi-Class Output

```python
def softmax(z):
    exp_z = [math.exp(zi) for zi in z]
    total = sum(exp_z)
    return [e / total for e in exp_z]
```

Converts a vector of raw scores into a probability distribution that **sums to 1**. This is exactly what an LLM does at the final layer — logits over the entire vocabulary (50k+ tokens) → softmax → probability of each next token. Sigmoid is the 2-class special case of softmax.

### 1.6 Activation Cheat Sheet

| Activation | Range | Used where | Key weakness |
|---|---|---|---|
| Sigmoid | (0,1) | binary output layer | vanishing gradient in hidden layers |
| Tanh | (-1,1) | older RNN hidden states | vanishing gradient (less severe) |
| ReLU | [0,∞) | CNN/MLP hidden layers | dying neurons |
| GELU | ≈(-0.17,∞) | transformer FFN layers | slightly more compute than ReLU |
| Softmax | (0,1), sums to 1 | multi-class output layer | none (it's the right tool for the job) |

---

## 2. Loss Functions — "How Wrong Are You, Numerically?"

A loss function converts (prediction, true answer) → a single number the network tries to minimize.

### 2.1 Mean Squared Error (MSE) — for Regression

```python
mse = mean((y_pred - y_true) ** 2)
```
Use when output is a continuous number (price, temperature, embedding similarity score).

### 2.2 Binary Cross-Entropy — for 2-Class Classification

```python
bce = -mean(y_true * log(y_pred) + (1 - y_true) * log(1 - y_pred))
```
Covered in doc 1 — punishes confident wrong answers far more than MSE does.

### 2.3 Categorical Cross-Entropy — for Multi-Class Classification

```python
# y_true is one-hot, e.g. [0, 0, 1, 0] for class 2 out of 4
cce = -sum(y_true[i] * log(y_pred[i]) for i in range(len(y_true)))
```

Since `y_true` is one-hot (only one entry is 1, rest are 0), this simplifies to `-log(y_pred[correct_class])` — you only care about the probability the model assigned to the *correct* answer.

**This is exactly the loss used to train every LLM.** Next-token prediction: `correct_class` = the actual next token, `y_pred` = softmax over the vocabulary. The training loss you'll see reported for GPT/Llama/Claude-style pretraining ("cross-entropy loss", "perplexity = exp(loss)") is this formula, applied per token, averaged over the whole dataset. Perplexity 10 roughly means "the model was as confused as if choosing uniformly among 10 tokens" — lower is better.

### 2.4 Why the Loss Function Choice Actually Matters (Not Just Convention)

The loss function determines the **shape of the gradient**, which determines *how* the network learns:
- MSE on a classification problem → flat gradients near confident-wrong predictions (see doc 1, Section 3) → slow/stuck learning.
- Cross-entropy's gradient, worked out via calculus, elegantly simplifies to just `(y_pred - y_true)` when paired with sigmoid/softmax — this clean form is *why* this pairing became the universal standard, not just tradition.

---

## 3. Where This Shows Up in Your Real Work

- **Choosing a model output layer:** binary fraud flag → sigmoid + BCE. Multi-class ticket routing (billing/technical/sales) → softmax + categorical cross-entropy.
- **Debugging a stuck-training model (interview scenario):** "loss isn't decreasing" → first two questions to ask: (1) is the activation causing vanishing gradients (sigmoid/tanh in deep hidden layers)? (2) is the loss function mismatched to the task (MSE on classification)?
- **RAGAS / LLM-judge scoring** (you've covered this in Level5) — under the hood, many of these are calibrated using cross-entropy-style scoring, not raw MSE, for the same reason above.

---

## 4. Quick Recap

| Question | Answer |
|---|---|
| Why not sigmoid in hidden layers of deep nets? | Vanishing gradient (max derivative 0.25) |
| Why ReLU became the default? | Derivative is 0 or 1 — no shrinking across layers |
| Why GELU in transformers specifically? | Smooth version of ReLU, better empirical performance |
| Why cross-entropy over MSE for classification? | Punishes confident-wrong harder, cleaner gradient |
| What is perplexity? | `exp(cross-entropy loss)` — LLM training's headline metric |

**Next:** [`04_gradient_descent_backprop.md`](04_gradient_descent_backprop.md) — the actual algorithm (chain rule + gradient descent) that uses these losses and activations to update every weight in the network.
