# Level 5 — Doc 4: Chunking Strategies (Deep Dive)

> **Goal:** Documents ko kaise tukde karein for RAG. Chunking strategy = RAG quality determine karta hai.

---

## 1. Why Chunking Matters

RAG = retrieve relevant chunks → feed to LLM.

If chunks are bad:
- Too small → context lost
- Too big → too much noise, costs more
- Wrong split → important info split across chunks

**Chunking is THE #1 lever for RAG quality.**

---

## 2. Chunking Strategies (5 Types)

### A. Fixed-Size Chunking
```python
def fixed_chunks(text, size=500, overlap=50):
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start:start + size])
        start += size - overlap
    return chunks
```
- Simple, fast
- Doesn't respect semantic boundaries
- **Use when:** Quick prototype

### B. Sentence-Based
```python
import nltk
sentences = nltk.sent_tokenize(text)
chunks = []
current = ""
for s in sentences:
    if len(current) + len(s) > 500:
        chunks.append(current)
        current = s
    else:
        current += " " + s
```
- Respects sentence boundaries
- Better than fixed

### C. Recursive Character Splitting (LangChain Default)
Split on hierarchical separators:
```python
separators = ["\n\n", "\n", ". ", " ", ""]
# Try splitting on paragraphs first
# If chunks still too big, split on lines
# If still too big, sentences, then words, then chars
```
**Most popular in production.**

### D. Semantic Chunking
Use embeddings to detect topic shifts:
```python
def semantic_chunks(text):
    sentences = sent_tokenize(text)
    embeddings = [embed(s) for s in sentences]
    
    chunks = []
    current = [sentences[0]]
    for i in range(1, len(sentences)):
        # Check similarity with previous sentence
        sim = cosine_sim(embeddings[i-1], embeddings[i])
        if sim < 0.5:  # Topic shift
            chunks.append(" ".join(current))
            current = []
        current.append(sentences[i])
    if current:                       # IMPORTANT: loop ke baad bacha hua chunk flush karo
        chunks.append(" ".join(current))  # warna LAST chunk silently drop ho jata hai
    return chunks
```

### E. Hierarchical Chunking
For long docs:
- Level 1: Sections (large chunks)
- Level 2: Paragraphs (medium)
- Level 3: Sentences (small)

Retrieve at small level, expand to relevant section.

---

## 3. Document-Type-Specific Strategies

### Markdown / Docs
Split on headers:
```python
chunks = re.split(r"\n#{1,6} ", markdown_text)
# Each section becomes a chunk
```

### Code
Split on functions/classes:
```python
import ast
tree = ast.parse(code)
chunks = [ast.unparse(node) for node in tree.body 
          if isinstance(node, (ast.FunctionDef, ast.ClassDef))]
```

### PDFs
- Page-based (simple but often wrong)
- Layout-aware (better — uses structure)
- Use `pdfplumber`, `unstructured.io` for structure

### Tables
Don't split tables. Keep as single chunk OR convert to markdown.

### Q&A Format
Each Q&A pair = one chunk.

---

## 4. Chunk Size Trade-offs

| Size | Pros | Cons | Use Case |
|---|---|---|---|
| 100 tokens | Precise retrieval | Lost context | Q&A on specific facts |
| 500 tokens | Sweet spot | — | General RAG |
| 1000+ tokens | Full context | More noise, expensive | Long-form analysis |

**Default:** 500-1000 tokens with 10-20% overlap.

---

## 5. Overlap

```python
chunks_with_overlap = [
    text[0:500],
    text[400:900],   # Overlap = 100
    text[800:1300],
    ...
]
```

**Why?** Important info at chunk boundaries doesn't get split.

**Overlap %:** 10-20% typical.

---

## 6. Metadata in Chunks

Don't lose context:
```python
chunk = {
    "text": "Python uses indentation...",
    "metadata": {
        "source": "tutorial.pdf",
        "page": 5,
        "section": "Python Basics",
        "chunk_index": 12
    }
}
```

Later when retrieving, you can filter by metadata.

---

## 7. Production Code

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=100,
    separators=["\n\n", "\n", ". ", " "],
    length_function=lambda x: len(tiktoken.encode(x))  # Count tokens, not chars
)

chunks = splitter.split_text(document)
```

For metadata:
```python
from langchain_text_splitters import MarkdownHeaderTextSplitter

headers = [("#", "h1"), ("##", "h2"), ("###", "h3")]
splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers)
chunks = splitter.split_text(markdown_doc)
# Each chunk includes header info as metadata
```

---

## 8. Testing Chunking

```python
def evaluate_chunking(chunks, queries_and_expected):
    """For each query, check if the relevant chunk is in top-K retrieval."""
    correct = 0
    for q, expected_chunk_id in queries_and_expected:
        top_k = retrieve(q, chunks, k=3)
        if expected_chunk_id in [c.id for c in top_k]:
            correct += 1
    return correct / len(queries_and_expected)
```

Try multiple strategies. Pick one with best recall.

---

## 9. Key Takeaways

✅ Chunking determines RAG quality
✅ Recursive character splitter is solid default
✅ Semantic chunking is best when affordable
✅ 500-1000 token chunks with 10-20% overlap
✅ Always include metadata (source, page, section)
✅ Adapt strategy to document type
✅ Test multiple strategies — measure retrieval recall

**Next:** [05_embedding_models.md](05_embedding_models.md) — Choosing embeddings
