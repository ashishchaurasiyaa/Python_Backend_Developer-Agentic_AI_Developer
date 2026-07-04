# Classical ML/DL Foundations — Doc 7: RNNs & LSTMs for Sequential Data

> **Goal:** CNNs (doc 6) handle spatial data (images). Text, speech, time-series are **sequential** — order matters, and length varies. RNNs were the first architecture built specifically for this, and understanding *why they eventually failed at long sequences* is exactly what motivates the Transformer (next doc, and what you already know from `04_attention_transformers.md`).

---

## 1. The Problem With Using an MLP or CNN on Sequences

An MLP needs a **fixed-size** input. A sentence can be 3 words or 300 words — you can't just "flatten it into an MLP" without either truncating/padding awkwardly or losing the notion that word order matters.

**RNN's idea:** process the sequence **one element at a time**, and maintain a running "memory" (hidden state) that gets updated at each step, carrying forward information from everything seen so far.

---

## 2. The Recurrent Neural Network (RNN)

```
        h0 ──┐
             ▼
   x1 ──►[RNN cell]──► h1 ──┐
                              ▼
   x2 ──────────────►[RNN cell]──► h2 ──┐
                                          ▼
   x3 ──────────────────────────►[RNN cell]──► h3 ──► output
```

At every time step `t`:
```python
h_t = tanh(x_t @ W_x + h_{t-1} @ W_h + b)
```

- `x_t`: input at this time step (e.g., embedding of the current word)
- `h_{t-1}`: hidden state carried over from the PREVIOUS step (the "memory")
- **Same weights `W_x`, `W_h`, `b` are reused at every time step** — this is the RNN's version of doc 6's "parameter sharing," except shared across *time* instead of *space*.

The final hidden state `h_n` (after processing the whole sequence) is a fixed-size vector summarizing the entire variable-length input — this can feed into a classifier (sentiment, spam/not-spam) or the RNN can produce an output at every step (next-word prediction, part-of-speech tagging).

---

## 3. Backpropagation Through Time (BPTT)

Training an RNN uses the exact same backpropagation (doc 4) — but now "layers" are actually **time steps**, since the same weights get applied at every step.

```
Loss at t=3 depends on h3, which depends on h2, which depends on h1, which depends on h0.
Gradient must flow ALL THE WAY BACK through every time step.
```

This is why it's called Backpropagation **Through Time**: unroll the RNN across all `T` time steps as if they were `T` separate layers, then apply standard backprop across that unrolled chain.

### 3.1 The Vanishing/Exploding Gradient Problem — Much Worse Here

Recall from doc 4: gradients multiply layer-by-layer. In an RNN, the "layers" are time steps, and there can be **hundreds** of them (a long document, a long conversation). The SAME weight matrix `W_h` gets multiplied into the gradient at EVERY step:

```
gradient at step 1 ≈ (local gradients) × W_h × W_h × W_h × ... (T times)
```

- If `W_h`'s effective magnitude < 1 → gradient **vanishes** exponentially with sequence length → the RNN "forgets" anything more than ~10-20 steps back. Classic symptom: a sentiment model can't connect "The movie, despite [200 words of plot summary], was..." back to the setup at the start.
- If `W_h`'s effective magnitude > 1 → gradient **explodes** → weights become NaN, training crashes. Common fix: **gradient clipping** (cap the gradient's magnitude before the update step).

This is a strictly worse version of the vanishing gradient problem from doc 4 — there, it was across ~10-100 network layers; here, it's across potentially thousands of time steps, with the SAME weight matrix repeated, making the exponential effect even more extreme and much harder to fix by just changing the activation function.

---

## 4. LSTM (Long Short-Term Memory) — The 1997 Fix

LSTM adds an explicit **cell state** (`C_t`) — a separate memory "conveyor belt" that information can flow along with minimal transformation, plus three **gates** that control what gets added, removed, or read:

```
Forget gate:  f_t = sigmoid(...)   → "what % of old memory to KEEP"
Input gate:   i_t = sigmoid(...)   → "what % of new info to ADD"
Output gate:  o_t = sigmoid(...)   → "what % of memory to EXPOSE as output"

Cell state update:  C_t = f_t * C_{t-1}  +  i_t * (candidate new memory)
Hidden state:        h_t = o_t * tanh(C_t)
```

**Why this fixes vanishing gradients:** the cell state update `C_t = f_t * C_{t-1} + i_t * (...)` is (mostly) an **addition**, not a repeated matrix multiplication through a squashing activation. When `f_t ≈ 1` (forget gate says "keep everything"), gradient flows backward through the cell state almost unchanged — this is conceptually the SAME trick as doc 5's residual connections (`x_out = x_in + f(x_in)`), applied across time instead of across layers. Both solve the exact same underlying vanishing-gradient math with the exact same idea: give the gradient an additive, unimpeded path.

**GRU (Gated Recurrent Unit)** — a simpler, faster variant of LSTM (combines forget+input into one "update gate," no separate cell state). Similar performance in practice, fewer parameters, faster to train — was popular right before transformers took over entirely (~2014-2017).

---

## 5. Where RNNs/LSTMs Were Used (Before Transformers)

- Machine translation (this is literally what motivated the original 2017 "Attention Is All You Need" paper — it was written to REPLACE the RNN encoder-decoder that was standard for translation at the time)
- Speech recognition, time-series forecasting, sentiment analysis
- Any sequence task before ~2018 — GPT-1/BERT (2018) is roughly when transformers fully displaced RNNs for NLP

---

## 6. Run the Practical

[`07_rnn_lstm_sequential_practical.py`](07_rnn_lstm_sequential_practical.py) implements a **vanilla RNN forward pass + BPTT from scratch with numpy**, and directly measures how the gradient magnitude reaching early time steps **shrinks** as sequence length grows — the exact vanishing-gradient-over-time phenomenon this doc describes, made numerically visible.

---

## 7. Where This Shows Up in Your Real Work

- **"Why did the field move from RNN to Transformer?"** — classic interview question. Correct answer has TWO parts, both matter: (1) vanishing gradients over long sequences (this doc), AND (2) RNNs are inherently **sequential** — you can't compute `h_5` before `h_4` is done, so RNNs can't parallelize across the sequence length on a GPU. Transformers process all positions simultaneously (attention is one big matrix multiply), which is why they train so much faster at scale. Doc 8 covers both in detail.
- **LSTM gating logic directly maps to the "gates" concept you'll see again** in agent frameworks (e.g., LangGraph's conditional edges deciding what state to carry forward) — same core idea of "should this information pass through or get blocked/updated," different domain.
- If you ever see legacy production code using `nn.LSTM` for text classification (some older enterprise systems still do, pre-2019 codebases) — you'll now know exactly why it was reasonable then and why it'd be replaced with a transformer/embedding-based approach today.

---

## 8. Quick Recap

| Concept | One-liner |
|---|---|
| RNN | Same weights applied at every time step, hidden state carries memory forward |
| BPTT | Backprop unrolled across time steps instead of layers |
| Vanishing gradient (RNN) | Same weight matrix multiplied repeatedly across many time steps → shrinks to ~0 |
| LSTM | Adds cell state + gates; additive cell update ≈ residual connection across time |
| GRU | Simplified, faster LSTM variant |
| Why transformers won | Solved vanishing gradient (attention, not recurrence) AND enabled full parallelization |

**Next:** [`08_rnn_limits_transformer_rise.md`](08_rnn_limits_transformer_rise.md) — connecting this directly to the Transformer architecture you already know.
