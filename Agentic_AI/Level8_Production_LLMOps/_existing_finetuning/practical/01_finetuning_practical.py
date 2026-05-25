"""
Phase6_LLM_Finetuning — Complete Practical
===========================================
Topics:
  1. Fine-tuning vs RAG vs prompt engineering — when to use what
  2. Dataset format (JSONL for OpenAI, Alpaca, ShareGPT)
  3. OpenAI fine-tuning API
  4. LoRA / QLoRA (PEFT) concepts
  5. PEFT with Hugging Face
  6. Training loop patterns
  7. Evaluation metrics (perplexity, ROUGE, BERTScore)

Install: pip install openai datasets peft transformers
Run: python 01_finetuning_practical.py
"""

import os, json
from typing import List, Dict, Any

print("=" * 60)
print("LLM FINE-TUNING CONCEPTS")
print("=" * 60)

FINETUNING_CONCEPTS = {
    "Full fine-tuning":   "Update ALL weights. Best accuracy. Needs 8+ GPUs. $$$",
    "LoRA":               "Low-Rank Adaptation — train only small adapter matrices. 10-100× less params.",
    "QLoRA":              "LoRA + 4-bit quantization. Fits 70B model on single GPU!",
    "PEFT":               "Parameter-Efficient Fine-Tuning (HuggingFace library). LoRA, prefix, adapters.",
    "SFT":                "Supervised Fine-Tuning — learn from (input, output) pairs",
    "RLHF":               "RL from Human Feedback. PPO. Used for ChatGPT. Very complex.",
    "DPO":                "Direct Preference Optimization. Simpler than RLHF. Needs (good, bad) pairs.",
    "Catastrophic forgetting": "Model loses general knowledge when fine-tuned on narrow data. Use LoRA!",
}
for k, v in FINETUNING_CONCEPTS.items():
    print(f"  {k:<26}: {v}")

print("\n  Fine-tuning vs RAG vs Prompting:")
COMPARISON = {
    "Approach":        ["Prompting", "RAG", "Fine-tuning"],
    "Training cost":   ["$0",        "$0",  "$10-$10000"],
    "Latency":         ["Fastest",   "+50ms", "Fastest"],
    "Knowledge":       ["Training data", "Real-time", "Training data"],
    "Format control":  ["Good",      "Good",  "Best"],
    "Use when":        [
        "Simple tasks, GPT-4 is powerful enough",
        "Current info, private docs, citations",
        "Domain-specific style, consistency, smaller model"
    ],
}
rows = list(COMPARISON.keys())
for row in rows:
    vals = COMPARISON[row]
    print(f"  {row:<18}: {vals[0]:<20} {vals[1]:<20} {vals[2]}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Dataset Formats
# INTERVIEW: OpenAI uses JSONL with messages array
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 1: Dataset Formats")
print("=" * 60)

# OpenAI fine-tuning format (JSONL)
OPENAI_DATASET = [
    {
        "messages": [
            {"role": "system",    "content": "You are a Python code reviewer."},
            {"role": "user",      "content": "Review this code:\ndef add(a,b): return a+b"},
            {"role": "assistant", "content": "The function is correct but lacks type hints and a docstring. Improved version:\n\ndef add(a: int | float, b: int | float) -> int | float:\n    \"\"\"Add two numbers.\"\"\"\n    return a + b"},
        ]
    },
    {
        "messages": [
            {"role": "system",    "content": "You are a Python code reviewer."},
            {"role": "user",      "content": "Review: for i in range(len(my_list)): print(my_list[i])"},
            {"role": "assistant", "content": "Use direct iteration instead:\n\nfor item in my_list:\n    print(item)\n\nThis is more Pythonic and avoids index-based access."},
        ]
    },
]

# Alpaca format (popular for instruction tuning)
ALPACA_DATASET = [
    {
        "instruction": "Explain Python decorators",
        "input":       "",  # optional context
        "output":      "Decorators are functions that wrap other functions to add behavior...",
    },
    {
        "instruction": "Translate this Python code to TypeScript",
        "input":       "def greet(name: str) -> str:\n    return f'Hello, {name}'",
        "output":      "function greet(name: string): string {\n    return `Hello, ${name}`;\n}",
    },
]

# ShareGPT format (multi-turn, used by many open models)
SHAREGPT_DATASET = [
    {
        "conversations": [
            {"from": "human", "value": "What is the GIL?"},
            {"from": "gpt",   "value": "The GIL (Global Interpreter Lock) prevents multiple threads from executing Python bytecode simultaneously..."},
            {"from": "human", "value": "How do I work around it?"},
            {"from": "gpt",   "value": "Use multiprocessing for CPU-bound tasks, asyncio for I/O-bound tasks, or C extensions."},
        ]
    }
]

print("  OpenAI JSONL format (messages):")
print(json.dumps(OPENAI_DATASET[0], indent=2)[:400])

print("\n  Alpaca format:")
print(json.dumps(ALPACA_DATASET[0], indent=2)[:300])

print("\n  Dataset tips:")
print("  - Minimum: 10 examples. Recommended: 50-100+ for noticeable improvement")
print("  - Quality > quantity. Curate carefully.")
print("  - Validate JSONL: each line must be valid JSON")
print("  - Include variety: don't repeat same patterns")


def create_sample_dataset(examples: List[Dict], output_path: str = "/tmp/training.jsonl"):
    """Create JSONL training file."""
    with open(output_path, "w") as f:
        for ex in examples:
            f.write(json.dumps(ex) + "\n")
    print(f"\n  Created dataset: {output_path} ({len(examples)} examples)")

    # Validate
    errors = []
    for i, ex in enumerate(examples):
        if "messages" in ex:
            roles = [m["role"] for m in ex["messages"]]
            if "assistant" not in roles:
                errors.append(f"Example {i}: no assistant message")
    if errors:
        print(f"  Validation errors: {errors}")
    else:
        print(f"  Validation: ✓ All examples valid")

    return output_path


dataset_path = create_sample_dataset(OPENAI_DATASET)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: OpenAI Fine-tuning API
# INTERVIEW: Easiest fine-tuning — just upload JSONL and wait
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 2: OpenAI Fine-tuning API")
print("=" * 60)

OPENAI_FINETUNE_CODE = '''\
from openai import OpenAI
import time

client = OpenAI()

# ── Step 1: Upload training file ───────────────────────────────
with open("training.jsonl", "rb") as f:
    file_response = client.files.create(
        file    = f,
        purpose = "fine-tune",
    )
file_id = file_response.id
print(f"Uploaded file: {file_id}")

# Optional: upload validation file
with open("validation.jsonl", "rb") as f:
    val_file = client.files.create(file=f, purpose="fine-tune")

# ── Step 2: Create fine-tuning job ─────────────────────────────
# INTERVIEW: Supported base models: gpt-4o-mini, gpt-3.5-turbo
job = client.fine_tuning.jobs.create(
    training_file   = file_id,
    validation_file = val_file.id,      # optional
    model           = "gpt-4o-mini",    # base model
    hyperparameters = {
        "n_epochs":         3,          # default: auto
        "batch_size":       4,          # default: auto
        "learning_rate_multiplier": 2,  # default: auto
    },
    suffix = "code-reviewer",           # → model name: ft:gpt-4o-mini:org:code-reviewer:xxx
)
print(f"Job ID: {job.id}, Status: {job.status}")

# ── Step 3: Monitor job ────────────────────────────────────────
while True:
    job = client.fine_tuning.jobs.retrieve(job.id)
    print(f"Status: {job.status}")
    if job.status in ("succeeded", "failed", "cancelled"):
        break
    # List events for progress
    events = client.fine_tuning.jobs.list_events(fine_tuning_job_id=job.id)
    for event in events.data[:3]:
        print(f"  {event.created_at}: {event.message}")
    time.sleep(60)

# ── Step 4: Use fine-tuned model ───────────────────────────────
if job.status == "succeeded":
    model_id = job.fine_tuned_model
    # ft:gpt-4o-mini:org:code-reviewer:xxx

    response = client.chat.completions.create(
        model    = model_id,  # ← use fine-tuned model!
        messages = [
            {"role": "system", "content": "You are a Python code reviewer."},
            {"role": "user",   "content": "Review: x = lambda a,b: a+b"},
        ],
    )
    print(response.choices[0].message.content)

# ── Cost estimate ──────────────────────────────────────────────
# gpt-4o-mini: $0.003 per 1K training tokens
# 100 examples × 500 tokens × 3 epochs = 150K tokens = $0.45
'''
print(OPENAI_FINETUNE_CODE[:700])


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: LoRA / QLoRA Concepts
# INTERVIEW: Why LoRA works and when to use QLoRA
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 3: LoRA / QLoRA")
print("=" * 60)

LORA_EXPLANATION = """
LoRA (Low-Rank Adaptation) math:
  Original weight matrix W (d × k) — FROZEN during training
  LoRA adds: W' = W + BA
    where B is (d × r) and A is (r × k), r << min(d, k)
    e.g., W is 4096×4096 = 16M params
         BA with r=16: 4096×16 + 16×4096 = 131K params (100x less!)

  Only B and A are trained — W stays unchanged.

QLoRA adds:
  1. Load model in 4-bit (NF4 quantization) → 70B model fits in 48GB
  2. Apply LoRA adapters in fp16
  3. Use paged AdamW for memory spikes

Typical LoRA hyperparameters:
  r (rank):            4-64. Higher = more capacity but more params.
  alpha:               16-64. Usually 2×r. Scales learning rate.
  target_modules:      ["q_proj", "v_proj"] for attention layers
  lora_dropout:        0.0-0.1
  bias:                "none" (don't train biases)
"""
print(LORA_EXPLANATION)


PEFT_CODE = '''\
from peft import LoraConfig, get_peft_model, TaskType, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig,
    TrainingArguments, Trainer,
)
from datasets import Dataset
import torch

# ── Load model in 4-bit (QLoRA) ───────────────────────────────
bnb_config = BitsAndBytesConfig(
    load_in_4bit               = True,
    bnb_4bit_quant_type        = "nf4",     # NormalFloat4
    bnb_4bit_compute_dtype     = torch.float16,
    bnb_4bit_use_double_quant  = True,      # nested quantization
)
model = AutoModelForCausalLM.from_pretrained(
    "meta-llama/Meta-Llama-3.1-8B-Instruct",
    quantization_config = bnb_config,
    device_map          = "auto",
)
model = prepare_model_for_kbit_training(model)  # enable gradient checkpointing

# ── Apply LoRA ─────────────────────────────────────────────────
lora_config = LoraConfig(
    task_type   = TaskType.CAUSAL_LM,
    r           = 16,                 # rank
    lora_alpha  = 32,                 # scaling factor
    target_modules = [                # which layers to adapt
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj",
    ],
    lora_dropout = 0.05,
    bias         = "none",
)
model = get_peft_model(model, lora_config)
model.print_trainable_parameters()
# → trainable params: 6,815,744 || all params: 8,036,474,880 || 0.085%!

# ── Training with TRL (easiest) ────────────────────────────────
from trl import SFTTrainer

trainer = SFTTrainer(
    model           = model,
    tokenizer       = tokenizer,
    train_dataset   = train_dataset,
    peft_config     = lora_config,
    dataset_text_field = "text",
    max_seq_length  = 2048,
    args = TrainingArguments(
        output_dir          = "./results",
        num_train_epochs    = 3,
        per_device_train_batch_size = 4,
        gradient_accumulation_steps = 4,
        warmup_steps        = 10,
        learning_rate       = 2e-4,
        fp16                = True,
        logging_steps       = 10,
        optim               = "paged_adamw_32bit",
        save_strategy       = "epoch",
    ),
)
trainer.train()

# ── Save adapter ───────────────────────────────────────────────
model.save_pretrained("./lora_adapter")    # saves only LoRA weights (~10MB)

# ── Merge for deployment ───────────────────────────────────────
merged = model.merge_and_unload()          # bake LoRA into base weights
merged.save_pretrained("./merged_model")   # deploy as normal model
'''
print(PEFT_CODE[:700])


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Evaluation Metrics
# INTERVIEW: How to measure if fine-tuning improved the model
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 4: Evaluation Metrics")
print("=" * 60)

EVAL_METRICS = {
    "Perplexity":  "How 'surprised' the model is by test data. Lower = better. Use for language modeling.",
    "ROUGE-L":     "Longest common subsequence overlap. For summarization. 0-1 (higher=better).",
    "BLEU":        "N-gram precision. For translation. Controversial — doesn't capture semantics.",
    "BERTScore":   "Semantic similarity using BERT embeddings. Better than ROUGE for meaning.",
    "Exact Match": "% of outputs exactly matching expected. For classification/extraction.",
    "Win Rate":    "Human preference: finetuned vs base, A/B test. Gold standard.",
    "Task-specific": "Code: pass@k (tests pass). Q&A: F1/EM. Custom metrics for your use case.",
}
for m, d in EVAL_METRICS.items():
    print(f"  {m:<18}: {d}")

EVAL_CODE = '''\
from evaluate import load
import numpy as np

# ── ROUGE ─────────────────────────────────────────────────────
rouge = load("rouge")
results = rouge.compute(
    predictions = ["FastAPI is a modern Python web framework"],
    references  = ["FastAPI is a fast, modern web framework for Python"],
)
print(results["rougeL"])   # 0.76

# ── BERTScore ─────────────────────────────────────────────────
bertscore = load("bertscore")
results = bertscore.compute(
    predictions = ["FastAPI is fast"],
    references  = ["FastAPI has excellent performance"],
    lang        = "en",
)
print(results["f1"][0])    # 0.89 — semantic match!

# ── Perplexity ─────────────────────────────────────────────────
def calculate_perplexity(model, tokenizer, texts: list) -> float:
    """Lower perplexity = better language model."""
    import torch
    total_loss = 0
    for text in texts:
        inputs     = tokenizer(text, return_tensors="pt")
        with torch.no_grad():
            outputs = model(**inputs, labels=inputs["input_ids"])
        total_loss += outputs.loss.item()
    return math.exp(total_loss / len(texts))

# ── LLM-as-judge (best for instruction following) ─────────────
judge_prompt = """
Rate this response to the question on a scale of 1-10.
Question: {question}
Response: {response}
Reference: {reference}
Score (1-10) and brief reason:
"""
# Use GPT-4 or Claude to evaluate fine-tuned model outputs
# INTERVIEW: Correlates well with human eval, much cheaper
'''
print(EVAL_CODE[:500])


print("\n" + "=" * 60)
print("FINE-TUNING INTERVIEW SUMMARY:")
print("  Use fine-tuning: consistent style, domain vocab, complex formatting")
print("  Use RAG instead: current info, citations, knowledge retrieval")
print("  LoRA: train only low-rank adapters (~0.1% of params). r=16, alpha=32")
print("  QLoRA: 4-bit quantize base + LoRA adapters. 70B model on one GPU!")
print("  OpenAI API: upload JSONL → create job → wait → use ft:model-name")
print("  Dataset: min 50 high-quality examples, messages: system+user+assistant")
print("  Eval: perplexity (language), ROUGE (summarization), BERTScore (semantic)")
print("=" * 60)
