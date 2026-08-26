# LLM Fine-tuning — RAG vs Fine-tune, LoRA/QLoRA, OpenAI, HuggingFace PEFT

## Quick Concepts
- **Fine-tuning** = pre-trained model ko apne data par further train karo — style/behavior change
- **LoRA** = Low-Rank Adaptation — sirf small adapter weights train karo, base model freeze
- **QLoRA** = Quantized LoRA — 4-bit quantization se memory 4x reduce, consumer GPU pe possible
- **PEFT** = Parameter Efficient Fine-Tuning — HuggingFace library — LoRA, prefix tuning, etc.
- **RAG vs Fine-tune** = knowledge add karna hai → RAG; style/format change → fine-tune

---

## Andar kya hota hai — LoRA Ka Actual Math + QLoRA Memory Trick

### LoRA — poora weight matrix train NAHI karta, ek LOW-RANK decomposition add karta hai

```
Full fine-tuning: W (d×d matrix, HUGE — jaise 4096×4096) ko poora
  update karo — millions of trainable parameters, poora gradient +
  optimizer state (Adam ke 2 extra copies) store karna padta

LoRA: W ko FREEZE karo (touch hi nahi karte), iske bajaye:
  ΔW = B · A
  jahan B hai (d × r), A hai (r × d), aur r << d (jaise r=8, d=4096)

  Training sirf A aur B ke chhote matrices update karti hai —
  parameters count ~100-1000x kam training ke liye
```

Inference time pe do options: (1) `ΔW` ko `W` mein MERGE kar do (`W_new =
W + B·A`) — zero extra latency, ek hi normal forward pass; (2) ALAG rakho —
multiple LoRA adapters ek hi base model pe SWAP kar sakte ho runtime pe
(different task ke liye different adapter load karo, base model wahi rahe).

### QLoRA — 4-bit BASE model, higher-precision ADAPTER

```
Base model weights (W)     → 4-bit quantized (NF4 format), disk/memory
                              mein bahut kam jagah
LoRA adapters (A, B)        → higher precision (16-bit) rakhte hain

Forward/backward pass: 4-bit weights ko ON-THE-FLY dequantize karke
  compute karte hain, phir wapas discard — memory mein hamesha 4-bit hi
  rehta hai
```

Isiliye QLoRA se ek 70B model consumer GPU (24GB VRAM) pe FINE-TUNE ho
sakta hai — base weights 4-bit hone se memory drastically kam, par
adapter (jo actually training/learning kar raha hai) higher precision
mein rehne se training quality maintain hoti hai.

---

## Interview Questions & Answers

### Q1: RAG vs Fine-tuning — kab kya choose karte hain?
**Answer:**
```
RAG (Retrieval-Augmented Generation):
  ✓ Dynamic/changing knowledge (product catalog, docs)
  ✓ Need citations/sources
  ✓ Large knowledge base (10K+ documents)
  ✓ No training data required
  ✓ Quick to deploy
  ✓ Easy to update (just add documents)
  ✗ Retrieval can fail (wrong chunks)
  ✗ Latency overhead (retrieval step)
  ✗ Context window limits

Fine-tuning:
  ✓ Consistent style/format/tone (always JSON, always Hindi)
  ✓ Domain-specific language (medical terms, legal jargon)
  ✓ Behavior change (persona, refusal patterns)
  ✓ Compress knowledge into weights (smaller model, same quality)
  ✓ No retrieval latency
  ✗ Static knowledge (needs retraining to update)
  ✗ Requires labeled training data (100-10K examples)
  ✗ Expensive and time-consuming
  ✗ Can forget (catastrophic forgetting)

DECISION TABLE:
┌─────────────────────────────────────┬─────────┬──────────────┐
│ Use Case                            │ RAG     │ Fine-tuning  │
├─────────────────────────────────────┼─────────┼──────────────┤
│ Answer from company docs            │ ✓✓✓     │              │
│ Always respond in specific format   │         │ ✓✓✓          │
│ Customer support FAQ                │ ✓✓      │ ✓            │
│ Medical diagnosis from papers       │ ✓✓✓     │              │
│ Code generation in company style    │         │ ✓✓✓          │
│ Real-time price/inventory queries   │ ✓✓✓     │              │
│ Brand voice/persona                 │         │ ✓✓✓          │
│ Reasoning improvement               │ ✗       │ ~ (distill)  │
└─────────────────────────────────────┴─────────┴──────────────┘

> ⚠️ "neither" too strong: RAG se to nahi, par **fine-tuning/distillation** (reasoning traces pe
> RFT/SFT) target distribution pe reasoning IMPROVE kar sakta hai — aaj common practice hai.

REAL ANSWER IN INTERVIEWS:
"Usually RAG first. Fine-tune only when:
 1. RAG accuracy not meeting threshold after optimization
 2. Specific output format consistency needed
 3. Domain jargon model doesn't understand
 4. Cost reduction: fine-tuned small model > expensive large model"
```

---

### Q2: OpenAI Fine-tuning pipeline kaise karte hain?
**Answer:**
```python
import json
import openai
from pathlib import Path
import time

client = openai.OpenAI()

# ===== STEP 1: PREPARE TRAINING DATA =====
# JSONL format — each line = one training example

training_examples = [
    {
        "messages": [
            {"role": "system", "content": "You extract order info from customer emails as JSON."},
            {"role": "user", "content": "I want to order 3 blue shirts size L, total $89.97"},
            {"role": "assistant", "content": '{"items": [{"product": "blue shirt", "size": "L", "qty": 3}], "total": 89.97}'}
        ]
    },
    {
        "messages": [
            {"role": "system", "content": "You extract order info from customer emails as JSON."},
            {"role": "user", "content": "Please ship 1 red dress (XS) to Mumbai, cost 2500 INR"},
            {"role": "assistant", "content": '{"items": [{"product": "red dress", "size": "XS", "qty": 1}], "total": 2500, "currency": "INR", "shipping_city": "Mumbai"}'}
        ]
    },
    # Minimum 10 examples, recommended 50-100+ for good results
]

# Save as JSONL
def save_training_data(examples: list[dict], filepath: str):
    with open(filepath, "w") as f:
        for example in examples:
            f.write(json.dumps(example) + "\n")

save_training_data(training_examples, "training_data.jsonl")

# Validate before upload
def validate_training_data(filepath: str) -> dict:
    """Check format, token counts, estimate cost"""
    import tiktoken
    enc = tiktoken.encoding_for_model("gpt-4o-mini")
    
    errors = []
    total_tokens = 0
    examples = []
    
    with open(filepath) as f:
        for i, line in enumerate(f):
            try:
                example = json.loads(line)
                if "messages" not in example:
                    errors.append(f"Line {i}: Missing 'messages' key")
                    continue
                
                # Count tokens
                tokens = sum(len(enc.encode(m["content"])) for m in example["messages"])
                total_tokens += tokens
                examples.append(example)
                
            except json.JSONDecodeError:
                errors.append(f"Line {i}: Invalid JSON")
    
    # Cost estimate: $8 per 1M tokens (gpt-4o-mini fine-tuning)
    estimated_cost = (total_tokens * 3) * 8 / 1_000_000  # 3 epochs * cost
    
    return {
        "valid": len(errors) == 0,
        "examples": len(examples),
        "total_tokens": total_tokens,
        "errors": errors,
        "estimated_cost_usd": estimated_cost,
    }

# ===== STEP 2: UPLOAD FILE =====
def upload_training_file(filepath: str) -> str:
    with open(filepath, "rb") as f:
        file_response = client.files.create(
            file=f,
            purpose="fine-tune",
        )
    print(f"Uploaded: {file_response.id}")
    return file_response.id

# ===== STEP 3: CREATE FINE-TUNE JOB =====
def create_fine_tune_job(file_id: str) -> str:
    job = client.fine_tuning.jobs.create(
        training_file=file_id,
        model="gpt-4o-mini",           # cheapest to fine-tune
        hyperparameters={
            "n_epochs": 3,             # default 3-5
            "batch_size": "auto",      # auto based on dataset size
            "learning_rate_multiplier": "auto",  # auto tune
        },
        suffix="order-extractor",      # model name suffix
    )
    print(f"Job created: {job.id}")
    print(f"Status: {job.status}")
    return job.id

# ===== STEP 4: MONITOR PROGRESS =====
def monitor_job(job_id: str):
    while True:
        job = client.fine_tuning.jobs.retrieve(job_id)
        print(f"Status: {job.status}")
        
        if job.status == "succeeded":
            print(f"✓ Fine-tuned model: {job.fine_tuned_model}")
            return job.fine_tuned_model
        
        elif job.status == "failed":
            print(f"✗ Failed: {job.error}")
            return None
        
        # Check recent events
        events = client.fine_tuning.jobs.list_events(job_id, limit=5)
        for event in events.data:
            print(f"  [{event.created_at}] {event.message}")
        
        time.sleep(60)  # Check every minute

# ===== STEP 5: USE FINE-TUNED MODEL =====
def use_fine_tuned_model(model_id: str, user_input: str) -> str:
    """ft:gpt-4o-mini:myorg:order-extractor:abc123"""
    response = client.chat.completions.create(
        model=model_id,
        messages=[
            {"role": "system", "content": "You extract order info from customer emails as JSON."},
            {"role": "user", "content": user_input},
        ]
    )
    return response.choices[0].message.content

# Full pipeline
file_id = upload_training_file("training_data.jsonl")
job_id = create_fine_tune_job(file_id)
fine_tuned_model = monitor_job(job_id)

result = use_fine_tuned_model(fine_tuned_model, "2 green hoodies size M, $59.98")
print(result)  # {"items": [{"product": "green hoodie", "size": "M", "qty": 2}], "total": 59.98}
```

---

### Q3: LoRA/QLoRA — HuggingFace PEFT se kaise fine-tune karte hain?
**Answer:**
```python
# pip install transformers peft trl datasets bitsandbytes

from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    BitsAndBytesConfig,
)
from peft import LoraConfig, get_peft_model, TaskType, prepare_model_for_kbit_training
from trl import SFTTrainer
from datasets import load_dataset, Dataset
import torch

# ===== QLORA SETUP (4-bit quantization) =====

# Load model in 4-bit (QLoRA)
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",         # NF4 quantization (best for QLoRA)
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_use_double_quant=True,    # nested quantization
)

model_name = "meta-llama/Meta-Llama-3.1-8B-Instruct"  # 8B params

model = AutoModelForCausalLM.from_pretrained(
    model_name,
    quantization_config=bnb_config,
    device_map="auto",                 # auto GPU placement
    trust_remote_code=True,
)

tokenizer = AutoTokenizer.from_pretrained(model_name)
tokenizer.pad_token = tokenizer.eos_token

# Prepare for k-bit training
model = prepare_model_for_kbit_training(model)

# ===== LORA CONFIG =====
lora_config = LoraConfig(
    r=16,                              # rank — higher = more params, better quality
    lora_alpha=32,                     # scaling factor (alpha/r = effective learning rate)
    target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],  # attention layers
    lora_dropout=0.05,
    bias="none",
    task_type=TaskType.CAUSAL_LM,
)

model = get_peft_model(model, lora_config)
model.print_trainable_parameters()
# trainable params: 6,815,744 || all params: 8,036,474,880 || trainable%: 0.085%
# Only 0.085% of params are trained! Rest are frozen.

# ===== TRAINING DATA =====
def format_instruction(example: dict) -> str:
    """Format as instruction-following"""
    return f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>
You are a Python code reviewer.
<|eot_id|><|start_header_id|>user<|end_header_id|>
{example['instruction']}
<|eot_id|><|start_header_id|>assistant<|end_header_id|>
{example['output']}
<|eot_id|>"""

# Load dataset
dataset = load_dataset("json", data_files={"train": "train.jsonl", "test": "test.jsonl"})

# ===== TRAINING =====
training_args = TrainingArguments(
    output_dir="./lora-output",
    num_train_epochs=3,
    per_device_train_batch_size=4,
    gradient_accumulation_steps=4,    # effective batch = 4*4 = 16
    warmup_steps=100,
    learning_rate=2e-4,
    fp16=True,                         # mixed precision
    logging_steps=10,
    save_steps=100,
    evaluation_strategy="steps",
    eval_steps=100,
    load_best_model_at_end=True,
    report_to="none",                  # "wandb" ya "tensorboard" for tracking
)

trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset["train"],
    eval_dataset=dataset["test"],
    formatting_func=format_instruction,
    args=training_args,
    max_seq_length=2048,
    packing=False,
)

trainer.train()

# ===== SAVE ADAPTER WEIGHTS ONLY =====
model.save_pretrained("./lora-adapter")  # Saves only LoRA weights (~10MB vs 16GB!)
tokenizer.save_pretrained("./lora-adapter")

# ===== INFERENCE WITH LORA =====
from peft import PeftModel

# Load base model + adapter
base_model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype=torch.float16,
    device_map="auto",
)
model_with_lora = PeftModel.from_pretrained(base_model, "./lora-adapter")

# Merge adapter into base model (optional — faster inference)
merged_model = model_with_lora.merge_and_unload()
merged_model.save_pretrained("./merged-model")

# Inference
inputs = tokenizer("Review this code: def add(a,b): return a+b", return_tensors="pt")
outputs = merged_model.generate(**inputs, max_new_tokens=200)
print(tokenizer.decode(outputs[0], skip_special_tokens=True))
```

---

### Q4: Training data preparation — best practices?
**Answer:**
```python
import json
from pathlib import Path
import random

# ===== DATA QUALITY CHECKLIST =====
# 1. Minimum examples: 50-100 (ideally 500-1000)
# 2. Diverse examples — different phrasings, edge cases
# 3. Consistent format — same JSON schema, same tone
# 4. No contradictions — consistent answers
# 5. Train/val split — 90/10

def prepare_instruction_dataset(raw_data: list[dict]) -> dict:
    """
    raw_data format:
    [{"instruction": "...", "output": "..."}, ...]
    """
    
    # Deduplicate
    seen = set()
    unique_data = []
    for item in raw_data:
        key = item["instruction"][:100]
        if key not in seen:
            seen.add(key)
            unique_data.append(item)
    
    print(f"After dedup: {len(unique_data)} examples (was {len(raw_data)})")
    
    # Validate
    valid = []
    for item in unique_data:
        if len(item["instruction"]) < 10:
            continue
        if len(item["output"]) < 5:
            continue
        valid.append(item)
    
    # Shuffle
    random.shuffle(valid)
    
    # Split
    split_idx = int(len(valid) * 0.9)
    train_data = valid[:split_idx]
    val_data = valid[split_idx:]
    
    # Save
    def save_jsonl(data, path):
        with open(path, "w") as f:
            for item in data:
                f.write(json.dumps(item) + "\n")
    
    save_jsonl(train_data, "train.jsonl")
    save_jsonl(val_data, "val.jsonl")
    
    return {"train": len(train_data), "val": len(val_data)}

# ===== SYNTHETIC DATA GENERATION =====
async def generate_training_data(seed_examples: list[dict], target_count: int = 500) -> list[dict]:
    """Use Claude to generate synthetic training examples"""
    from anthropic import AsyncAnthropic
    import asyncio
    
    client = AsyncAnthropic()
    generated = []
    
    async def generate_batch(seed: dict) -> list[dict]:
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": f"""Generate 5 varied training examples similar to this:

Instruction: {seed['instruction']}
Output: {seed['output']}

Create 5 different examples with different wordings/scenarios.
Return as JSON array: [{{"instruction": "...", "output": "..."}}]"""
            }]
        )
        
        try:
            return json.loads(response.content[0].text)
        except:
            return []
    
    tasks = [generate_batch(ex) for ex in seed_examples[:10]]
    batches = await asyncio.gather(*tasks)
    
    for batch in batches:
        generated.extend(batch)
    
    return generated[:target_count]
```

---

### Q5: Fine-tuning cost aur comparison?
**Answer:**
```
FINE-TUNING COST COMPARISON (2025 approximate):

Provider       | Model          | Training Cost    | Inference Cost
───────────────┼────────────────┼──────────────────┼──────────────
OpenAI         | gpt-4o-mini    | $8/1M tokens     | 2x base price
OpenAI         | gpt-4o         | $25/1M tokens    | 2x base price
Anthropic      | claude-haiku   | Beta (limited)   | TBD
Together AI    | Llama-3.1-8B   | $1-3/1M tokens   | Cheap
Replicate      | Various        | Per compute hour | Per token
Self-hosted    | Any open model | AWS/GPU cost     | Self

LORA vs FULL FINE-TUNING:
┌────────────────────┬─────────────────┬──────────────────┐
│ Feature            │ Full Fine-tune  │ LoRA/QLoRA       │
├────────────────────┼─────────────────┼──────────────────┤
│ Parameters trained │ All (7B-70B)    │ 0.1-1% (6-70M)  │
│ GPU memory (7B)    │ 80GB+ (A100)    │ 16-24GB (RTX4090)│
│ Training time      │ Hours-days      │ 30min-3 hours    │
│ Quality            │ Best            │ Near-equal       │
│ Adapter size       │ 16GB            │ 10-100MB         │
│ Switch adapters    │ No              │ Yes (hot-swap)   │
└────────────────────┴─────────────────┴──────────────────┘

PRACTICAL RECOMMENDATION:
  Quick experiment        → OpenAI fine-tuning (easiest)
  Budget-conscious        → LoRA on Together AI / Replicate
  Full control, privacy   → QLoRA self-hosted (RunPod, Lambda Labs)
  Production, many users  → Fine-tune once → deploy on vLLM/TGI
```
