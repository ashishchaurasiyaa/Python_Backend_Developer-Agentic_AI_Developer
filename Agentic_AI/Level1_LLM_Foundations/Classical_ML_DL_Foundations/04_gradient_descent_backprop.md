# Classical ML/DL Foundations — Doc 4: Gradient Descent & Backpropagation

> **Goal:** The single most important algorithm in all of deep learning. Har weight update — chahe 2-neuron toy network ho ya 1.7-trillion-parameter GPT-4 — isi algorithm se hota hai. Yeh doc chain rule se derive karke dikhayega, sirf naam nahi bolega.

---

## 1. Gradient Descent — The Optimization Loop

Recap from doc 1: gradient descent = "move weights in the direction that reduces loss, repeat."

```
w_new = w_old - learning_rate * gradient
```

- **Gradient** = derivative of loss with respect to that weight = "if I increase this weight slightly, does loss go up or down, and by how much?"
- We move **opposite** the gradient because gradient points in the direction of *steepest increase*; we want to decrease loss.
- **Learning rate** = step size. Too big → overshoots the minimum, loss oscillates/explodes. Too small → learning is painfully slow.

```
Loss landscape (1 weight, simplified to a curve):

  loss
   |     *  ← start here (random weight)
   |      \
   |       \___
   |           \___
   |               \___* ← minimum (best weight)
   +----------------------- weight

Gradient descent: at each point, compute slope, step downhill, repeat.
```

### 1.1 Three Flavors of Gradient Descent

| Variant | Gradient computed over | Trade-off |
|---|---|---|
| **Batch GD** | entire dataset, every step | accurate gradient, very slow per step, needs all data in memory |
| **Stochastic GD (SGD)** | 1 random example per step | fast, noisy gradient (bounces around) |
| **Mini-batch GD** | small batch (e.g. 32, 64, 256 examples) | the practical middle ground — what everyone actually uses |

Modern LLM training uses mini-batch GD with adaptive optimizers (**Adam**, **AdamW**) — these track a running average of past gradients (momentum) and per-parameter learning rates, so they converge faster and more stably than plain SGD. You've referenced Adam/AdamW implicitly in `Level8_Production_LLMOps/06_llm_finetuning.md` — this is the theory underneath "the optimizer."

---

## 2. The Problem: We Have Millions of Weights, Not Just One

A single-neuron model (doc 1) has 2 numbers to optimize (`w`, `b`). An MLP has thousands. A transformer has billions. We need the gradient of the loss **with respect to every single weight** — and we need to compute all of them efficiently.

**Naive approach:** nudge each weight slightly, re-run the whole network, see how loss changed. This is called numerical differentiation — and it's computationally insane at scale (for N weights, you'd need N forward passes just to get one gradient step).

**The real solution: Backpropagation** — compute all gradients in roughly the same time as ONE forward pass, using the chain rule.

---

## 3. Backpropagation — The Chain Rule, Applied Layer by Layer

### 3.1 Chain Rule Recap (Calculus)

If `y = f(g(x))`, then:
```
dy/dx = dy/dg * dg/dx
```
Derivatives of composed functions multiply together.

A neural network IS a composed function:
```
loss = L( output( hidden( input, W1 ), W2 ) )
```

To get `d(loss)/dW1` (how the *first* layer's weights affect the *final* loss, several layers away), we chain-multiply the derivatives backward through every layer in between.

### 3.2 Worked Example — 2-Layer Network

```
Forward pass:
  z1 = x @ W1 + b1
  h  = relu(z1)
  z2 = h @ W2 + b2
  y_pred = sigmoid(z2)
  loss = binary_cross_entropy(y_pred, y_true)
```

Backward pass (compute in REVERSE order — hence "back"-propagation):

```
Step 1: d(loss)/d(y_pred)              — how loss changes if prediction changes
Step 2: d(loss)/d(z2) = Step1 * d(y_pred)/d(z2)     — chain through sigmoid
Step 3: d(loss)/d(W2) = d(loss)/d(z2) * h            — gradient for W2 (what we update!)
Step 4: d(loss)/d(h)  = d(loss)/d(z2) * W2           — pass the "blame" back to hidden layer
Step 5: d(loss)/d(z1) = d(loss)/d(h) * d(h)/d(z1)    — chain through relu
Step 6: d(loss)/d(W1) = d(loss)/d(z1) * x            — gradient for W1 (what we update!)
```

Notice the pattern: **each layer's gradient depends on the gradient of the layer *after* it.** That's why we go backward — layer N's gradient needs layer N+1's gradient, which needs layer N+2's, and so on, all the way from the loss back to the input. Each layer is visited exactly once, reusing values computed during the forward pass (this is why frameworks cache activations — `h`, `z1`, `z2` — during the forward pass; you need them during backward).

**Computational cost:** roughly 2x the cost of one forward pass, REGARDLESS of how many weights there are. This is the breakthrough that made training large networks feasible — it doesn't matter if you have 1,000 or 1 trillion weights, backprop computes all their gradients in one backward pass.

### 3.3 Where "Vanishing Gradient" Comes From (Connecting to Doc 3)

Look at the chain again: gradients get **multiplied** together layer by layer, going backward. If each layer's local gradient is < 1 (e.g., sigmoid's max of 0.25), the product shrinks exponentially with depth:

```
10 layers of sigmoid: 0.25^10 ≈ 0.00000095   → early layers barely update
10 layers of ReLU (active neurons): 1^10 = 1  → gradient signal survives
```

This is precisely why doc 3's activation choice matters — it's not a style preference, it's whether backprop's chain of multiplications explodes, survives, or vanishes.

---

## 4. Gradient Descent + Backprop, Working Together

```
For each mini-batch of training data:
    1. FORWARD PASS: input → layers → prediction → loss (single number)
    2. BACKWARD PASS (backprop): loss → chain rule backward → gradient for every weight
    3. UPDATE: every weight -= learning_rate * its_gradient  (gradient descent)
    4. Repeat for next mini-batch, next epoch, ...
```

This 4-step loop, run billions of times, on billions of parameters, over trillions of tokens — **is literally how GPT-4/Claude/Llama were trained.** Nothing conceptually different happens at scale; it's this exact loop, parallelized across thousands of GPUs. You've read the "training briefly" overview in `Deep_Architecture/09_training_briefly.md` — this doc is the mechanical detail underneath that summary.

---

## 5. Run the Practical

[`04_gradient_descent_backprop_practical.py`](04_gradient_descent_backprop_practical.py) implements a 2-layer MLP **from scratch with pure numpy** — manual forward pass, manual backprop (no autograd, no PyTorch) — and trains it to solve **XOR**, the exact problem doc 2 showed a single perceptron cannot solve. Watching XOR's loss go to ~0 is the clearest possible proof that depth + backprop actually works.

---

## 6. Where This Shows Up in Your Real Work

- **Fine-tuning discussions** (`Level8_Production_LLMOps/06_llm_finetuning.md`, LoRA/QLoRA) — LoRA works by injecting small trainable matrices and running the *exact same* backprop loop, just on far fewer parameters. Understanding backprop is what makes "LoRA freezes the base weights and only backprops through the adapter" click.
- **Debugging "loss is NaN" in interviews** — usually: learning rate too high (gradient descent overshoots and diverges) or exploding gradients (opposite of vanishing — gradients multiply to huge numbers instead of tiny ones, common in deep RNNs, see doc 7).
- **Why training LLMs needs GPUs, not CPUs** — backprop's chain rule reduces to matrix multiplications at every layer; GPUs are matrix-multiplication machines.

---

## 7. Quick Recap

| Concept | One-liner |
|---|---|
| Gradient descent | Step weights opposite the gradient to reduce loss |
| Learning rate | Step size — too big overshoots, too small crawls |
| Backpropagation | Chain rule applied layer-by-layer, backward, to get every weight's gradient in one pass |
| Vanishing gradient | Gradients multiply across layers; <1 factors shrink to ~0 with depth |
| Adam/AdamW | Modern optimizer — momentum + adaptive per-parameter learning rates |

**Next:** [`05_deep_neural_networks_intro.md`](05_deep_neural_networks_intro.md) — what happens when you stack many more layers (true "deep" networks): overfitting, regularization, batch norm, dropout.
