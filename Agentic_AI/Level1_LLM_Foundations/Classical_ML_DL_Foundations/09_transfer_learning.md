# Classical ML/DL Foundations — Doc 9: Transfer Learning Concepts & Applications

> **Goal:** Training a network from scratch needs huge data + compute. **Transfer learning** = reuse a model already trained on a big task, adapt it to your smaller/specific task. This is not a side topic for you — it's the concept underneath "why do we fine-tune GPT/Llama instead of training an LLM from zero," which you already do in practice (`Level8_Production_LLMOps/06_llm_finetuning.md`). This doc gives the general theory that fine-tuning is one specific case of.

---

## 1. The Core Idea

A network trained on a large, general dataset (e.g., ImageNet — millions of images, 1000 categories) learns **general-purpose features** in its early/middle layers (edges, textures, shapes — doc 6) before learning **task-specific** features in its final layers (this exact shape = "golden retriever").

**Transfer learning insight:** the general-purpose features (early/middle layers) are useful for almost ANY vision task, not just the original 1000 categories. So instead of training a new network from scratch for, say, "classify X-ray images as pneumonia/normal" (where you might only have 5,000 labeled images — not enough to learn good features from scratch), you:

1. Start with a network already trained on a big, general dataset (a "pretrained" model)
2. Keep its early/middle layers (general features) — they already work
3. Replace/retrain only the final layers for your specific task

```
Pretrained network (trained on huge general dataset):
[Conv layers: learned general edges/shapes/textures] → [Final classifier: 1000 general categories]
                    ↓ KEEP THESE (frozen or lightly adjusted)         ↓ REPLACE THIS
Your new network:
[Conv layers: reused from pretrained model] → [New final classifier: YOUR specific categories]
```

---

## 2. Two Main Strategies

### 2.1 Feature Extraction (Frozen Backbone)

**Freeze** all the pretrained layers (their weights don't update during your training — no gradient flows into them), and only train a new final layer (or small classifier head) on top.

```python
for param in pretrained_model.parameters():
    param.requires_grad = False        # freeze — no gradient, no update

new_head = Linear(pretrained_model.output_dim, num_your_classes)
# only new_head's weights get trained
```

- **When to use:** small dataset (few hundred to few thousand examples), your task is fairly similar to what the model was pretrained on.
- **Why it works:** you're only training a small number of new parameters, so you need far less data to avoid overfitting (doc 5).

### 2.2 Fine-Tuning (Unfrozen, Lower Learning Rate)

**Unfreeze** some or all of the pretrained layers, and continue training them (usually with a much smaller learning rate than you'd use from scratch) alongside the new final layer.

```python
for param in pretrained_model.parameters():
    param.requires_grad = True         # unfreeze

optimizer = Adam(model.parameters(), lr=1e-5)   # small LR — don't destroy pretrained knowledge
```

- **When to use:** more data available (thousands+), your task differs more from the original pretraining task, and you want to squeeze out more accuracy than frozen feature extraction gives.
- **Risk — "catastrophic forgetting":** if the learning rate is too high, fine-tuning can overwrite the useful general features the model already learned, making performance WORSE than just freezing. This is exactly why a much smaller learning rate is used than training-from-scratch would use — you want to nudge, not overwrite.

### 2.3 Which Layers to Unfreeze — the General Rule

```
Early layers  = most general (edges, basic syntax) → usually keep frozen
Later layers  = most task-specific                  → usually unfreeze first
```

A common practice: freeze early layers, unfreeze only the last few layers + the new head, train a bit, then optionally unfreeze more layers with an even smaller learning rate ("gradual unfreezing"/"discriminative fine-tuning").

---

## 3. Transfer Learning IS What LLM Fine-Tuning Is

This entire doc, translated to your actual daily-use vocabulary:

| Classical transfer learning term | LLM fine-tuning equivalent (`Level8_Production_LLMOps/06_llm_finetuning.md`) |
|---|---|
| Pretrained model (ImageNet-trained CNN) | Pretrained LLM (Llama/Mistral/GPT base model — trained on trillions of tokens) |
| "General features" in early layers | General language understanding, world knowledge, reasoning learned during pretraining |
| Feature extraction (frozen backbone) | **Prompt engineering / RAG / in-context learning** — using the model AS-IS, no weight changes at all |
| Fine-tuning (unfreeze + small LR) | **Full fine-tuning** — updating all model weights, small learning rate, small custom dataset |
| Freezing most layers, training only a small new head | **LoRA/QLoRA (PEFT)** — freeze the entire base model, train only small injected adapter matrices |
| Catastrophic forgetting risk | Same exact risk/term used for LLM fine-tuning — a badly fine-tuned model can lose general capability while gaining narrow task performance |

**This is the single biggest connection in this whole folder for your work:** LoRA is literally "feature extraction" (freeze the backbone, train a small new piece) applied to transformers instead of CNNs. The theoretical justification for why LoRA works (why you don't need to retrain billions of parameters to adapt a model to a new domain) is exactly the transfer-learning argument above — the base model already learned general-purpose representations; you only need to adjust a small amount to redirect it to your task.

---

## 4. Domain-Adaptive Pretraining (DAPT) — The Middle Ground

Sometimes your target domain (e.g., legal documents, medical text) is different enough from general pretraining data that neither "use as-is" nor "small fine-tune" is enough. **DAPT**: continue the ORIGINAL pretraining objective (next-token prediction) on a large corpus of your domain's text, BEFORE fine-tuning on your specific labeled task. This is exactly what your `Level7_Frameworks`/`Level8_Production_LLMOps` DAPT references point to — it's transfer learning with an extra intermediate step: pretrained → domain-adapted → task-fine-tuned.

---

## 5. Where This Shows Up in Your Real Work

- **Deciding RAG vs fine-tuning** (a question you already cover in Level5/Level8): this decision IS "feature extraction vs fine-tuning," reframed. RAG = don't touch the model at all, just feed it better context (frozen backbone + external retrieval instead of even a new head). Fine-tuning = actually adjust weights.
- **"Why does LoRA work so well with so few trainable parameters?"** — interview question whose real answer is this doc: the base model's general capability doesn't need to be relearned, only nudged.
- **Catastrophic forgetting in production** — if a fine-tuned support-bot model starts giving worse general answers after a narrow fine-tune, this is the classical transfer-learning failure mode, with a classical fix (lower learning rate, freeze more layers, or add general-capability examples back into the fine-tuning mix).

---

## 6. Quick Recap

| Concept | One-liner |
|---|---|
| Transfer learning | Reuse a pretrained model's general features instead of training from scratch |
| Feature extraction | Freeze pretrained layers, train only a new head — needs little data |
| Fine-tuning | Unfreeze (some/all) layers, small learning rate, more data needed |
| Catastrophic forgetting | Fine-tuning too aggressively erases general capability |
| DAPT | Continue pretraining on domain text before task-specific fine-tuning |
| LLM equivalent | RAG/prompting = feature extraction; LoRA = frozen backbone + small new adapter; full fine-tune = classical fine-tuning |

**Next:** [`10_gans_diffusion_image_gen.md`](10_gans_diffusion_image_gen.md) — a different generative paradigm entirely (not autoregressive like LLMs): GANs and diffusion models, the foundation of DALL-E/Stable Diffusion/Midjourney.
