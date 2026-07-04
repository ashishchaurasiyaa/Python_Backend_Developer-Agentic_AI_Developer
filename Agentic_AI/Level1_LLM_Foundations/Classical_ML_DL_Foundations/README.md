# 🧠 Classical ML/DL Foundations — Before the Transformer

> **Why this folder exists:** `Level1_LLM_Foundations` and `Deep_Architecture/` start at the transformer/attention level. This folder fills the layer BEFORE that — classical machine learning and deep learning (linear regression → perceptron → MLP → CNN → RNN/LSTM), ending with an explicit bridge into the Transformer you already know, plus transfer learning and GANs/diffusion. Gap identified 2026-07-04 while cross-checking the repo against an external Agentic AI bootcamp syllabus's "Foundations of Neural Networks and Transformers" module.

---

## 📖 Reading Order

| # | Doc | What You'll Learn | Practical |
|---|---|---|---|
| 1 | [01_ml_foundations_regression.md](01_ml_foundations_regression.md) | Linear & logistic regression — the 1-neuron neural network | [✅ practical.py](01_ml_foundations_regression_practical.py) |
| 2 | [02_perceptron_mlp.md](02_perceptron_mlp.md) | Perceptron, XOR problem, multi-layer perceptrons | (concepts) |
| 3 | [03_loss_activation_functions.md](03_loss_activation_functions.md) | Sigmoid/tanh/ReLU/GELU/softmax + MSE/cross-entropy | (concepts) |
| 4 | [04_gradient_descent_backprop.md](04_gradient_descent_backprop.md) ⭐ | **The core algorithm** — chain rule, backprop, gradient descent | [✅ practical.py](04_gradient_descent_backprop_practical.py) — solves XOR from scratch |
| 5 | [05_deep_neural_networks_intro.md](05_deep_neural_networks_intro.md) | Overfitting, regularization, dropout, batch norm, residual connections | (concepts) |
| 6 | [06_cnn_computer_vision.md](06_cnn_computer_vision.md) | Convolution, pooling, CNN architecture | [✅ practical.py](06_cnn_computer_vision_practical.py) — edge detection from scratch |
| 7 | [07_rnn_lstm_sequential.md](07_rnn_lstm_sequential.md) | RNN, BPTT, vanishing gradients over time, LSTM gates | [✅ practical.py](07_rnn_lstm_sequential_practical.py) — measures gradient decay directly |
| 8 | [08_rnn_limits_transformer_rise.md](08_rnn_limits_transformer_rise.md) ⭐ | **The bridge** — RNN's 2 limitations → Transformer's 2 fixes | (links to existing Deep_Architecture series) |
| 9 | [09_transfer_learning.md](09_transfer_learning.md) | Feature extraction vs fine-tuning — maps directly to RAG vs LoRA vs full fine-tune | (concepts) |
| 10 | [10_gans_diffusion_image_gen.md](10_gans_diffusion_image_gen.md) | GANs, diffusion models, DALL-E/Stable Diffusion/Midjourney foundations | (concepts) |

---

## ⏱️ Time to Complete

- **Quick skim:** 2 hours (read 01, 04, 08 — the load-bearing docs)
- **Full read + run practicals:** 6-8 hours

---

## 🎯 What You'll Know After This

✅ Why linear/logistic regression IS a neural network (1 neuron, 0 hidden layers)
✅ Why XOR needs 2 layers, not 1 (and can prove it — practical solves XOR from scratch)
✅ Why cross-entropy beats MSE for classification (gradient math, not convention)
✅ Backpropagation derived via chain rule, implemented with zero autograd
✅ Why sigmoid causes vanishing gradients and ReLU/GELU don't
✅ Why residual connections ("Add & Norm" in every transformer block) exist — they solved this exact problem in CNNs first
✅ How convolution + pooling work, numerically, on a real array
✅ Why RNNs vanish over long sequences — measured directly, not just asserted
✅ The exact 2 things Transformers fixed that RNNs couldn't (distance + parallelization)
✅ Why LoRA works: it's classical "feature extraction" transfer learning, applied to LLMs
✅ How Stable Diffusion actually turns noise + a text prompt into an image

---

## 🎤 Interview-Ready Questions

1. Why is logistic regression considered a neural network?
2. Why can't a single perceptron solve XOR? What's the minimum fix?
3. Derive why cross-entropy is preferred over MSE for classification.
4. Explain backpropagation using the chain rule — walk through 2 layers.
5. Why does depth cause vanishing/exploding gradients, and how do ReLU + residual connections address it?
6. Explain convolution and pooling — why do they beat a plain MLP on images?
7. Why do RNNs struggle with long sequences? What does BPTT even mean?
8. What are LSTM gates, and why does the cell state avoid vanishing gradients?
9. What TWO specific problems did the Transformer solve that RNNs couldn't?
10. Why is LoRA so parameter-efficient — connect it to transfer learning theory.
11. How does a diffusion model generate an image from a text prompt?

---

## 🔧 How This Connects to the Rest of Your Repo

```
THIS FOLDER (classical foundations)
        ↓
Level1_LLM_Foundations/04_attention_transformers.md  (doc 8 bridges here)
        ↓
Deep_Architecture/ (full transformer internals — attention, layers, sampling, inference)
        ↓
Level8_Production_LLMOps/06_llm_finetuning.md  (doc 9 bridges here — LoRA/QLoRA = transfer learning)
        ↓
Level5_RAG_Vector_Databases/  (doc 1's cross-entropy/embeddings connect here)
```

This folder is the prerequisite layer — read it BEFORE or interleaved with Level1, not after. If you already know transformers well, docs 4 and 8 are the two highest-value reads (backprop mechanics + the explicit RNN→Transformer bridge).

---

## 🚀 Start Here

→ **[01_ml_foundations_regression.md](01_ml_foundations_regression.md)** — start with the single neuron, build up from there.

**Most important docs (if short on time):**
- ⭐ [04_gradient_descent_backprop.md](04_gradient_descent_backprop.md) — the algorithm underneath everything
- ⭐ [08_rnn_limits_transformer_rise.md](08_rnn_limits_transformer_rise.md) — the explicit "why transformers won" bridge
