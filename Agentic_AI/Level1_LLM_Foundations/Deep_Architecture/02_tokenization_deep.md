# Deep Architecture — Doc 2: Tokenization Deep Dive

> **Goal:** Text → tokens → IDs. BPE algorithm, vocabulary, why tokenization matters for cost + multilingual.

---

## 1. The Problem

Computers don't understand text. They need numbers.

Naive approach: every word = unique number.
```
"hello" → 1
"world" → 2
"the" → 3
```

**Problems:**
- Millions of unique words (vocab huge)
- Misspellings break everything
- Compound words explode vocab
- Different languages = different vocabs

Solution: **Subword tokenization** — break words into smaller pieces.

---

## 2. Subword Tokenization Intuition

Instead of whole words, learn common **subwords**:

```
"unbelievable" → ["un", "believ", "able"]
"hello" → ["hello"]      # Common word, stays whole
"prepostroposing" → ["pre", "post", "ro", "posing"]  # Made-up word
```

**Benefits:**
- Vocab small (50K-200K, not millions)
- Handle new words (decompose into known parts)
- Cross-lingual (share subwords like "tion", "ing")

---

## 3. Byte-Pair Encoding (BPE)

The algorithm OpenAI uses (and most modern LLMs).

### Training the tokenizer:

**Step 1:** Start with all characters as tokens.
```
Vocab: ['a', 'b', 'c', ..., 'z', '0'..'9', ' ', '!', ...]
Size: ~256 (all bytes)
```

**Step 2:** Tokenize a huge corpus of text.
```
"the cat sat" → ['t','h','e',' ','c','a','t',' ','s','a','t']
```

**Step 3:** Find most common adjacent pair.
```
Counts:
('t','h'): 100
('h','e'): 100
('e',' '): 100
(' ','c'): 50
...
```

**Step 4:** Merge that pair into a single new token.
```
Add 't_h' to vocab.
Re-tokenize: ['th','e',' ','c','a','t',' ','s','a','t']
```

**Step 5:** Repeat 30,000-200,000 times.
```
After training:
- Common letters merged: 'th', 'he', 'ing', 'ed', ...
- Common subwords: ' the', ' and', ' for', ...
- Whole words: ' Python', ' AI', ' programming', ...
- Code patterns: 'def ', 'return ', '== '
```

### Final vocabulary contains:
- Original 256 bytes (handle any text)
- ~50,000-200,000 learned tokens
- Special tokens: `<|im_start|>`, `<|endoftext|>`, etc.

---

## 4. tiktoken — OpenAI's Tokenizer

```python
import tiktoken

# Get tokenizer for specific model
enc = tiktoken.encoding_for_model("gpt-4o")

# Encode text → token IDs
tokens = enc.encode("Hello world!")
# [13225, 1879, 0]

# Each ID maps to a subword
for tok_id in tokens:
    print(f"{tok_id} = {repr(enc.decode([tok_id]))}")
# 13225 = 'Hello'
# 1879  = ' world'
# 0     = '!'

# Decode back
text = enc.decode(tokens)  # "Hello world!"
```

### Key insight:
- ` world` (with leading space) is ONE token, ID 1879
- `world` (no space) might be a DIFFERENT token, ID 14957
- The tokenizer learned that spaces are part of words

---

## 5. Vocabulary Stats — Real Models

| Model | Vocab Size | Notes |
|---|---|---|
| GPT-3.5 (cl100k_base) | 100,256 | OpenAI |
| GPT-4o (o200k_base) | 200,019 | Larger, more efficient |
| Claude 3.5 | ~100,000 | Anthropic-specific |
| Llama 3 | 128,000 | Bigger than Llama 2 (32K) |
| Gemini | 256,000 | Largest |

**Bigger vocab = fewer tokens per text** → cheaper, faster, longer context fits.

---

## 6. Why Hindi/Chinese Cost More

```python
# English
"Hello, how are you?"
# Tokens: ['Hello',',', ' how', ' are', ' you','?']
# 6 tokens for 21 characters → ~3.5 chars/token

# Hindi
"नमस्ते, आप कैसे हैं?"
# Tokens: ['नम','स्','ते',',',' आप',' कै','से',' हैं','?']
# 9 tokens for 22 characters → ~2.4 chars/token

# Chinese
"你好，你怎么样？"
# Tokens: ['你','好','，','你','怎','么','样','？']
# 8 tokens for 8 characters → 1 char/token
```

**Why?** Tokenizer trained mostly on English text — English has many learned merges.

**Cost impact:**
- Same paragraph in English: 100 tokens, $0.000015
- Same paragraph in Hindi: 200-300 tokens, $0.000030-45
- Same paragraph in Chinese: 400+ tokens, even more

This is **tokenization unfairness**. New models (like Gemini, GPT-4o) have larger vocabs that include more non-English merges, reducing this gap.

---

## 7. Special Tokens

Each model has special tokens with specific purposes:

```python
# OpenAI
<|endoftext|>       # End of document
<|im_start|>system  # Start of system message  
<|im_end|>          # End of message

# Anthropic Claude
Human:              # User turn
Assistant:          # Assistant turn

# Llama 3
<|begin_of_text|>
<|start_header_id|>user<|end_header_id|>
<|eot_id|>          # End of turn

# Code
<|fim_prefix|>      # Fill-in-middle prefix (for code completion)
<|fim_suffix|>
```

These don't appear in normal text — they're reserved IDs to mark structure.

---

## 8. Chat Templates — Adding Special Tokens

When you call:
```python
messages = [
    {"role": "system", "content": "You are helpful."},
    {"role": "user", "content": "Hi"}
]
```

Server-side converts to text with special tokens:
```
<|im_start|>system
You are helpful.<|im_end|>
<|im_start|>user
Hi<|im_end|>
<|im_start|>assistant
```

Now tokenize this whole string. The special tokens get their reserved IDs.

**Important:** Different models have DIFFERENT chat templates. If you use Llama's template with GPT-4, model won't understand.

---

## 9. Tokenization Edge Cases

### Edge Case 1: Whitespace Matters
```python
" Python"  # 1 token: ' Python' (with leading space)
"Python"   # 1 token: 'Python' (different ID!)
"python"   # 1 or 2 tokens (lowercase, different)
```

### Edge Case 2: Numbers
```python
"123"       # 1 token usually
"12345"     # 1-2 tokens
"1234567890" # Multiple tokens (long number)
```

### Edge Case 3: Code
```python
"def fibonacci(n):"
# Tokens: ['def', ' fibonacci', '(', 'n', '):']
# Code tokenizes efficiently — patterns learned during training
```

### Edge Case 4: Emojis
```python
"😀"  # Single emoji = 1-2 tokens (varies)
"🇮🇳"  # Flag = often 3-5 tokens (composed of multiple unicode chars)
```

### Edge Case 5: Repeated characters
```python
"aaaaaaa"   # Might be 1 token or several
"AAAAAA"    # Different from lowercase
```

---

## 10. Counting Tokens — Practical Tips

```python
import tiktoken

def estimate_tokens(text: str, model: str = "gpt-4o-mini") -> int:
    """Quick token count."""
    enc = tiktoken.encoding_for_model("gpt-4o")
    return len(enc.encode(text))

def estimate_cost(text: str, model: str) -> float:
    tokens = estimate_tokens(text, model)
    prices = {
        "gpt-4o-mini": 0.15,    # per 1M input
        "gpt-4o": 2.50,
        "claude-3-5-sonnet": 3.00,
    }
    return tokens * prices.get(model, 1.0) / 1_000_000

# Examples
print(estimate_tokens("Hello world!"))  # 3
print(estimate_tokens("The quick brown fox..."))  # ~6
```

---

## 11. Token IDs Across Models — NOT INTERCHANGEABLE

```python
# OpenAI's "Hello" might be ID 13225
# Claude's "Hello" might be ID 8674
# Llama's "Hello" might be ID 31195
```

**This is why** you can't reuse cached embeddings across models. Different tokenizer = different IDs = different meaning.

---

## 12. Sentencepiece (Alternative to BPE)

Used by:
- Llama (until v3)
- T5
- Many Google models

**Difference from BPE:**
- BPE works on bytes/characters
- Sentencepiece treats whitespace as part of subwords differently
- Has `▁` (underscore) prefix for word boundaries

Functionally similar — both produce subword tokens.

---

## 13. WordPiece (BERT Era)

BERT used **WordPiece** tokenization:
- Similar to BPE
- Uses `##` prefix for continuation: "playing" → ["play", "##ing"]
- Less common in modern LLMs

---

## 14. Multimodal Tokenization

For models like GPT-4o / Gemini:

### Image tokenization
```
Image (224×224 pixels) → Vision encoder → 256 image tokens (vectors)
                                          ↓
                                       Concatenated with text tokens
                                       → fed to same transformer
```

Each image token represents a patch of the image (~14×14 pixels).

### Audio tokenization
```
Audio waveform → Encoder → Audio tokens
                ↓
              Combined with text
```

The transformer doesn't care — to it, everything is just tokens.

---

## 15. Why Tokenization is "the Original Sin"

Karpathy famously called it "the cause of many headaches":

### Problem 1: Inconsistent counting across languages
- English: ~3.5 chars/token
- Code: ~3 chars/token  
- Hindi: ~2 chars/token
- Chinese: ~1 char/token

### Problem 2: Numbers are awkward
- "1234" is usually 1-2 tokens
- "1+2=3" can be 3-5 tokens depending on spacing
- Math reasoning suffers because numbers break into weird subtokens

### Problem 3: Capitalization matters
- "PYTHON" vs "python" vs "Python" — all different tokens
- Model has to learn they're related

### Problem 4: Whitespace
- "Python " vs " Python" — different tokens
- Trailing/leading spaces affect output

### Problem 5: Some tokens are "weird"
- Some tokens learned during training are bizarre artifacts
- E.g., " SolidGoldMagikarp" (real example) — random Reddit username became a token, causes weird model behavior

---

## 16. Cost Optimization via Tokenization

To reduce cost:
1. **Use English when possible** (cheaper tokens)
2. **Avoid extreme whitespace** (multiple newlines = extra tokens)
3. **Compact prompts** — don't waste words
4. **Use newer models** with larger vocabs (more efficient)
5. **Reuse prompts** — cache via Anthropic's prompt caching

```python
# Wasteful
"Please, kindly, if you would be so kind, summarize the following document..."

# Efficient
"Summarize:"
```

---

## 17. Tokenizer Surgery — Future Direction

Newer research:
- **Byte-level models** (no tokenization) — treat each byte as token
- **Character-level** — every character is a token (slower but fairer)
- **Mamba, RWKV** — alternatives to transformer that don't need same tokenization

For now (2026), BPE-based tokenization dominates production LLMs.

---

## 18. Try It Yourself

OpenAI tokenizer playground:
- https://platform.openai.com/tokenizer
- Paste text → see tokens visualized

Anthropic doesn't have a public tokenizer (it's not open-source).

---

## 19. Common Interview Questions

1. **Q: Why subword tokenization over word tokenization?**
   - Smaller vocab, handles unknown words, cross-lingual

2. **Q: How does BPE work?**
   - Start with characters, iteratively merge most-frequent adjacent pairs

3. **Q: Why do non-English languages cost more?**
   - Tokenizer trained primarily on English; other languages get fewer merges

4. **Q: Are token IDs same across models?**
   - NO. Each tokenizer is independent.

5. **Q: Why is "hello" different from " hello"?**
   - Tokenizer learned them as separate subwords because they appear in different contexts

---

## 20. Key Takeaways

✅ Text → tokens via **subword tokenization** (BPE for OpenAI)
✅ Vocab: 50K-200K subwords learned from training data
✅ Tokens are NOT words — they're frequent character sequences
✅ Whitespace is part of tokens (` Python` vs `Python` differ)
✅ Non-English languages tokenize less efficiently (cost more)
✅ Special tokens mark structure (`<|im_start|>`, etc.)
✅ Chat templates add these special tokens before tokenization
✅ Token IDs NOT shared across models
✅ Tokenization is a known weak spot (numbers, edge cases)

**Next:** [03_embeddings_and_position.md](03_embeddings_and_position.md) — Token IDs → vectors with position info
