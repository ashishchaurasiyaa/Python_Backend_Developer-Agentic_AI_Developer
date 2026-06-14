"""
Level5_RAG — Doc 4: Chunking Strategies Practical
====================================================
KYA SEEKHENGE (What we will learn):
  1. Fixed-Size Chunking  — sabse simple, char-count ke basis pe
  2. Sentence-Based       — sentence boundaries respect karta hai
  3. Recursive Character  — LangChain ka default, production-ready
  4. Semantic Chunking    — embedding similarity se topic shift detect
  5. Hierarchical         — sections → paragraphs → sentences
  6. Document-Type Tricks — Markdown headers, code AST, Q&A pairs
  7. Overlap demo         — boundary info kaise protect hota hai
  8. Metadata in Chunks   — source, page, section track karna
  9. Live LLM call        — groq se chunk quality check (optional)

KAISE CHALANA (How to run):
  uv run --project /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/my-agentic-ai-project \\
      python "/Users/youngmanindia/Documents/PythonRevision/Agentic_AI/Level5_RAG_Vector_Databases/04_chunking_strategies_practical.py"

  Keys ke bina bhi chalega (offline mode — graceful degradation).
  GROQ_API_KEY set karo live LLM demo ke liye.
"""

# ---------------------------------------------------------------------------
# Standard library imports — heavy optional libraries baad mein lazy import
# ---------------------------------------------------------------------------
import os
import re
import ast
import math
import json
import textwrap
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# GROQ_API_KEY check — crash avoid karne ke liye placeholder pattern use karo
# OpenAI() constructor None key pe crash karta hai, isliye "placeholder" default
# ---------------------------------------------------------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY") or "placeholder"
MOCK_MODE = GROQ_API_KEY == "placeholder"


def get_client():
    """
    LLM client factory — groq free tier default.
    Key nahi hai to None return karo, caller gracefully skip karega.
    """
    if MOCK_MODE:
        return None
    try:
        # langchain-groq already installed in project (pyproject.toml mein hai)
        from langchain_groq import ChatGroq  # type: ignore
        return ChatGroq(api_key=GROQ_API_KEY, model="llama3-8b-8192", temperature=0)
    except Exception as exc:
        print(f"  [WARN] Client init fail hua: {exc}")
        return None


# ---------------------------------------------------------------------------
# Header print — ek baar top pe
# ---------------------------------------------------------------------------
print("=" * 65)
print("CHUNKING STRATEGIES — RAG Quality ka #1 lever")
print("=" * 65)

if MOCK_MODE:
    print("  [OFFLINE MODE] GROQ_API_KEY nahi mila — live calls skip honge.\n")
else:
    print("  [LIVE MODE] GROQ_API_KEY mila — live LLM call karega.\n")

# Concept overview — theory doc se match karta hai
CHUNKING_CONCEPTS = {
    "Fixed-Size":          "Char count se tukde. Simple, fast. Semantic boundary nahi.",
    "Sentence-Based":      "Sentence end pe split. Better than fixed.",
    "Recursive Char":      "Hierarchy: para → line → sentence → word. LangChain default.",
    "Semantic":            "Embedding cosine sim se topic shift detect karo. Best quality.",
    "Hierarchical":        "Section → para → sentence. Retrieve small, expand big.",
    "Markdown Header":     "Har header ek chunk. Metadata se section track karo.",
    "Code AST":            "Function/Class node se split. Syntax-aware.",
    "Q&A Pair":            "Ek Q+A = ek chunk. QA-based RAG ke liye perfect.",
    "Overlap":             "10-20% overlap — boundary info protect karta hai.",
    "Metadata":            "source, page, section track karo retrieval filter ke liye.",
}
for k, v in CHUNKING_CONCEPTS.items():
    print(f"  {k:<20}: {v}")


# ---------------------------------------------------------------------------
# SAMPLE TEXT — sabhi demos ke liye ek hi text use karenge (RAG ke baare mein)
# ---------------------------------------------------------------------------
SAMPLE_TEXT = (
    "RAG, ya Retrieval-Augmented Generation, ek powerful technique hai. "
    "Isme documents ko vector store mein store karte hain. "
    "Query aane pe relevant chunks retrieve karte hain. "
    "Phir LLM ko un chunks ke saath prompt karte hain.\n\n"
    "Chunking is process ka pehla aur sabse important step hai. "
    "Agar chunks bahut chhote hain to context kho jaata hai. "
    "Agar chunks bahut bade hain to noise badh jaata hai aur cost zyada hoti hai. "
    "Isliye sahi chunk size chunna bahut zaroori hai.\n\n"
    "Overlap ek aur important concept hai. "
    "Boundary pe important information split nahi ho, isliye 10-20% overlap rakhte hain. "
    "For example, 500 char chunks mein 100 char ka overlap rakhte hain. "
    "Isse boundary pe koi bhi fact miss nahi hota. "
    "Production mein 500-1000 token chunks with 10-20% overlap standard practice hai.\n\n"
    "Semantic chunking sabse advance method hai. "
    "Isme har sentence ka embedding nikaalte hain. "
    "Phir adjacent sentences ki cosine similarity check karte hain. "
    "Agar similarity 0.5 se kam hai, matlab topic shift ho gaya. "
    "Wahan pe chunk boundary daalo. "
    "Yeh method costly hai lekin best RAG quality deta hai."
)


# =========================================================================
# SECTION 1: Fixed-Size Chunking
# Theory doc: Section 2A — Simple, fast, no semantic boundary
# =========================================================================
print("\n" + "=" * 65)
print("SECTION 1: Fixed-Size Chunking")
print("=" * 65)

FIXED_CODE = '''\
# Theory doc Section 2A — har method ka direct implementation
def fixed_chunks(text, size=500, overlap=50):
    """
    Text ko fixed size ke tukdon mein baanto.
    Overlap ka matlab hai adjacent chunks mein kuch common text hoga.
    """
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start:start + size])
        start += size - overlap  # overlap subtract karo next start se
    return chunks
'''
print(FIXED_CODE)


def fixed_chunks(text: str, size: int = 200, overlap: int = 40) -> List[str]:
    """
    Theory doc Section 2A ka direct implementation.
    size aur overlap chars mein hain (tokens nahi) — demo ke liye.
    """
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        chunks.append(text[start:end])
        # Overlap ke liye next start ko overlap amount peeche rakhte hain
        start += size - overlap
        if start >= len(text):
            break
    return chunks


fixed_result = fixed_chunks(SAMPLE_TEXT, size=200, overlap=40)
print(f"  Fixed chunks count: {len(fixed_result)}")
for i, ch in enumerate(fixed_result[:3]):
    print(f"  Chunk {i+1} ({len(ch)} chars): {ch[:80].strip()!r}...")
print(f"\n  [NOTE] Simple aur fast hai lekin sentence ke beech mein cut ho sakta hai.")
print(f"  Use case: Quick prototype ke liye theek hai.")


# =========================================================================
# SECTION 2: Sentence-Based Chunking
# Theory doc: Section 2B — sentence boundaries respect karo
# =========================================================================
print("\n" + "=" * 65)
print("SECTION 2: Sentence-Based Chunking")
print("=" * 65)

SENTENCE_CODE = '''\
# Theory doc Section 2B — sentence tokenizer ke saath splitting
# NLTK use karo real project mein; yahan hum regex se simulate karenge

import re

def sentence_chunks(text, max_size=500):
    # Sentences ko period, exclamation, question mark pe split karo
    sentences = re.split(r"(?<=[.!?]) +", text)
    chunks = []
    current = ""
    for s in sentences:
        if len(current) + len(s) > max_size:
            if current:
                chunks.append(current.strip())
            current = s
        else:
            current = current + " " + s if current else s
    if current:
        chunks.append(current.strip())
    return chunks
'''
print(SENTENCE_CODE)


def sentence_chunks(text: str, max_size: int = 300) -> List[str]:
    """
    Theory doc Section 2B implementation.
    NLTK ki jagah regex use kar rahe hain — offline demo ke liye enough.
    Real production mein: nltk.sent_tokenize() ya spacy use karo.
    """
    # Sentence boundary: period/!/? ke baad space
    sentences = re.split(r"(?<=[.!?]) +", text.replace("\n\n", " "))
    chunks: List[str] = []
    current = ""
    for s in sentences:
        if len(current) + len(s) > max_size and current:
            chunks.append(current.strip())
            current = s
        else:
            current = (current + " " + s).strip() if current else s
    if current:
        chunks.append(current.strip())
    return chunks


sent_result = sentence_chunks(SAMPLE_TEXT, max_size=300)
print(f"  Sentence chunks count: {len(sent_result)}")
for i, ch in enumerate(sent_result[:3]):
    print(f"  Chunk {i+1} ({len(ch)} chars): {ch[:90].strip()!r}...")
print(f"\n  [NOTE] Sentence boundary respect karta hai.")
print(f"  Fixed chunking se better — sentences intact rehte hain.")


# =========================================================================
# SECTION 3: Recursive Character Splitting
# Theory doc: Section 2C + Section 7 — LangChain default, production-ready
# =========================================================================
print("\n" + "=" * 65)
print("SECTION 3: Recursive Character Splitting (LangChain Default)")
print("=" * 65)

RECURSIVE_CODE = '''\
# Theory doc Section 2C — hierarchy mein split karo
# LangChain ka RecursiveCharacterTextSplitter yehi karta hai internally

separators = ["\\n\\n", "\\n", ". ", " ", ""]
# Try karo paragraph split pehle
# Agar chunk still too big → line split try karo
# Still too big → sentence split
# Still too big → word split
# Last resort → character split

# Production code (theory doc Section 7):
from langchain_text_splitters import RecursiveCharacterTextSplitter
splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=100,
    separators=["\\n\\n", "\\n", ". ", " "],
)
chunks = splitter.split_text(document)
'''
print(RECURSIVE_CODE)


def recursive_char_split(
    text: str,
    chunk_size: int = 300,
    overlap: int = 50,
    separators: Optional[List[str]] = None,
) -> List[str]:
    """
    Theory doc Section 2C ka pure-Python implementation.
    Hierarchy: para > line > sentence > word > char.
    LangChain internally bhi yehi logic follow karta hai.
    """
    if separators is None:
        separators = ["\n\n", "\n", ". ", " ", ""]

    def _split(text: str, seps: List[str]) -> List[str]:
        if not seps or len(text) <= chunk_size:
            return [text] if text.strip() else []
        sep, rest = seps[0], seps[1:]
        parts = text.split(sep)
        chunks: List[str] = []
        current = ""
        for p in parts:
            candidate = (current + sep + p).strip() if current else p.strip()
            if len(candidate) <= chunk_size:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                if len(p) > chunk_size:
                    # Recursively split further
                    chunks.extend(_split(p, rest))
                    current = ""
                else:
                    current = p.strip()
        if current:
            chunks.append(current)
        return chunks

    raw_chunks = _split(text, separators)

    # Overlap apply karo — adjacent chunks ke beech shared suffix/prefix
    if overlap <= 0 or len(raw_chunks) <= 1:
        return raw_chunks
    overlapped: List[str] = [raw_chunks[0]]
    for i in range(1, len(raw_chunks)):
        prev_tail = overlapped[-1][-overlap:] if len(overlapped[-1]) > overlap else overlapped[-1]
        merged = (prev_tail + " " + raw_chunks[i]).strip()
        overlapped.append(merged)
    return overlapped


rec_result = recursive_char_split(SAMPLE_TEXT, chunk_size=300, overlap=50)
print(f"  Recursive chunks count: {len(rec_result)}")
for i, ch in enumerate(rec_result[:3]):
    print(f"  Chunk {i+1} ({len(ch)} chars): {ch[:90].strip()!r}...")
print(f"\n  [NOTE] Production mein yahi use karo — most robust strategy.")
print(f"  LangChain: RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)")

# LangChain import (optional) — lazy, with fallback
print("\n  --- LangChain RecursiveCharacterTextSplitter (if installed) ---")
try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter  # type: ignore
    lc_splitter = RecursiveCharacterTextSplitter(
        chunk_size=300, chunk_overlap=50, separators=["\n\n", "\n", ". ", " "]
    )
    lc_chunks = lc_splitter.split_text(SAMPLE_TEXT)
    print(f"  LangChain chunks: {len(lc_chunks)}")
    for i, ch in enumerate(lc_chunks[:2]):
        print(f"  LC Chunk {i+1}: {ch[:80]!r}...")
except ImportError:
    print("  [SKIP] langchain-text-splitters not installed — pure-Python version already shown above.")


# =========================================================================
# SECTION 4: Semantic Chunking
# Theory doc: Section 2D — embedding similarity se topic shift detect
# =========================================================================
print("\n" + "=" * 65)
print("SECTION 4: Semantic Chunking")
print("=" * 65)

SEMANTIC_CODE = '''\
# Theory doc Section 2D — topic shift detect karo embedding se
def semantic_chunks(text, threshold=0.5):
    sentences = sent_tokenize(text)
    embeddings = [embed_model.encode(s) for s in sentences]

    chunks = []
    current = [sentences[0]]
    for i in range(1, len(sentences)):
        sim = cosine_similarity(embeddings[i-1], embeddings[i])
        if sim < threshold:   # Topic shift! Nayi chunk shuru karo
            chunks.append(" ".join(current))
            current = []
        current.append(sentences[i])
    if current:
        chunks.append(" ".join(current))
    return chunks

# sentence-transformers zaroorat hai real use ke liye:
# pip install sentence-transformers
'''
print(SEMANTIC_CODE)


def _mock_embedding(text: str) -> List[float]:
    """
    Fake embedding — sentence-transformers nahi hai to simulate karo.
    Real version: embed_model.encode(text)
    Returns a simple bag-of-words inspired vector (dim=10).
    """
    vocab = ["rag", "chunk", "overlap", "semantic", "embedding",
             "retrieval", "vector", "llm", "topic", "boundary"]
    t = text.lower()
    vec = [t.count(w) / max(len(t.split()), 1) for w in vocab]
    # L2 normalize
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def _cosine_sim(a: List[float], b: List[float]) -> float:
    """Cosine similarity — theory doc mein formula."""
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1e-9
    nb = math.sqrt(sum(x * x for x in b)) or 1e-9
    return dot / (na * nb)


def semantic_chunks(
    text: str,
    threshold: float = 0.3,
    embed_fn=_mock_embedding,
) -> List[str]:
    """
    Theory doc Section 2D implementation.
    embed_fn ko real model se replace karo production mein.
    """
    # Sentence split — period ke baad newline ya space
    sentences = re.split(r"(?<=[.!?]) +|\n", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    if len(sentences) < 2:
        return [text]

    embeddings = [embed_fn(s) for s in sentences]

    chunks: List[str] = []
    current: List[str] = [sentences[0]]

    for i in range(1, len(sentences)):
        sim = _cosine_sim(embeddings[i - 1], embeddings[i])
        # sim < threshold = topic shift = naya chunk
        if sim < threshold:
            chunks.append(" ".join(current))
            current = []
        current.append(sentences[i])

    if current:
        chunks.append(" ".join(current))
    return chunks


sem_result = semantic_chunks(SAMPLE_TEXT, threshold=0.3)
print(f"  Semantic chunks count: {len(sem_result)}  (mock embeddings, real model se better results)")
for i, ch in enumerate(sem_result[:3]):
    print(f"  Chunk {i+1} ({len(ch)} chars): {ch[:90]!r}...")
print(f"\n  [NOTE] Best quality lekin costly (embedding model chahiye).")
print(f"  Real production: sentence-transformers ya OpenAI embeddings use karo.")

# Optional: real sentence-transformers
print("\n  --- sentence-transformers (if installed) ---")
try:
    from sentence_transformers import SentenceTransformer, util  # type: ignore
    st_model = SentenceTransformer("all-MiniLM-L6-v2")
    sentences_demo = [s.strip() for s in re.split(r"(?<=[.!?]) +", SAMPLE_TEXT) if s.strip()][:6]
    st_embs = st_model.encode(sentences_demo)
    for i in range(len(sentences_demo) - 1):
        sim = util.cos_sim(st_embs[i], st_embs[i + 1]).item()
        print(f"  Sim[{i}→{i+1}]: {sim:.3f}  | {sentences_demo[i][:50]!r}")
    print("  [sentence-transformers available — semantic chunking with real embeddings possible]")
except ImportError:
    print("  [SKIP] sentence-transformers not installed — mock embedding used above.")
except Exception as e:
    print(f"  [SKIP] sentence-transformers error: {e}")


# =========================================================================
# SECTION 5: Hierarchical Chunking
# Theory doc: Section 2E — sections > paragraphs > sentences
# =========================================================================
print("\n" + "=" * 65)
print("SECTION 5: Hierarchical Chunking")
print("=" * 65)

HIER_CODE = '''\
# Theory doc Section 2E — multi-level chunking
# Level 1 (coarse):  Full sections/paragraphs — retrieval ka context
# Level 2 (medium):  Paragraphs — medium granularity
# Level 3 (fine):    Sentences — precise match

# Retrieve fine-grained chunks, expand to parent for context.
# ParentDocumentRetriever (LangChain) yahi karta hai.
'''
print(HIER_CODE)


@dataclass
class HierChunk:
    """Ek chunk jo apna level aur parent ID jaanta hai."""
    id: str
    text: str
    level: int  # 1=section, 2=paragraph, 3=sentence
    parent_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


def hierarchical_chunks(text: str) -> List[HierChunk]:
    """
    3-level hierarchy banao.
    Level 1 = double-newline se split (paragraphs/sections).
    Level 2 = single-newline se split.
    Level 3 = sentence se split.
    """
    all_chunks: List[HierChunk] = []

    # Level 1 — sections (double newline)
    sections = [s.strip() for s in text.split("\n\n") if s.strip()]
    for sec_i, sec in enumerate(sections):
        sec_id = f"sec_{sec_i}"
        all_chunks.append(HierChunk(
            id=sec_id, text=sec, level=1,
            metadata={"section_index": sec_i},
        ))

        # Level 2 — paragraphs (single newline ya long lines)
        paras = [p.strip() for p in sec.split("\n") if p.strip()] or [sec]
        for par_i, para in enumerate(paras):
            par_id = f"sec_{sec_i}_par_{par_i}"
            all_chunks.append(HierChunk(
                id=par_id, text=para, level=2, parent_id=sec_id,
                metadata={"section_index": sec_i, "para_index": par_i},
            ))

            # Level 3 — sentences
            sents = re.split(r"(?<=[.!?]) +", para)
            for s_i, sent in enumerate(sents):
                if sent.strip():
                    all_chunks.append(HierChunk(
                        id=f"{par_id}_s{s_i}", text=sent.strip(), level=3,
                        parent_id=par_id,
                        metadata={"section_index": sec_i, "para_index": par_i, "sent_index": s_i},
                    ))

    return all_chunks


hier_result = hierarchical_chunks(SAMPLE_TEXT)
level_counts = {1: 0, 2: 0, 3: 0}
for ch in hier_result:
    level_counts[ch.level] += 1

print(f"  Hierarchical chunks:")
print(f"    Level 1 (sections):   {level_counts[1]}")
print(f"    Level 2 (paragraphs): {level_counts[2]}")
print(f"    Level 3 (sentences):  {level_counts[3]}")
print(f"\n  Sample L3 chunk: {hier_result[-1].text[:80]!r}")
print(f"  Parent L2 ID:    {hier_result[-1].parent_id}")
print(f"\n  [NOTE] Small chunks se retrieve karo, phir parent expand karo context ke liye.")
print(f"  LangChain: ParentDocumentRetriever yahi karta hai automatically.")


# =========================================================================
# SECTION 6: Document-Type Specific Strategies
# Theory doc: Section 3 — Markdown, Code AST, Q&A pairs
# =========================================================================
print("\n" + "=" * 65)
print("SECTION 6: Document-Type Specific Strategies")
print("=" * 65)

# --- 6A: Markdown Header Splitting ---
print("\n  --- 6A: Markdown Header Splitting ---")
MD_CODE = '''\
# Theory doc Section 3 (Markdown) + Section 7 (MarkdownHeaderTextSplitter)
import re
# Har header ek chunk ka start hai
chunks = re.split(r"\\n#{1,6} ", markdown_text)

# LangChain version (header info as metadata):
from langchain_text_splitters import MarkdownHeaderTextSplitter
headers = [("#", "h1"), ("##", "h2"), ("###", "h3")]
splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers)
chunks = splitter.split_text(markdown_doc)
# Har chunk mein metadata["h1"], metadata["h2"] available hoga
'''
print(MD_CODE)

SAMPLE_MARKDOWN = """# Python aur RAG
## Introduction
RAG ek important technique hai modern AI mein.
Isse LLM ko fresh knowledge de sakte hain.

## Chunking
Chunking sabse important step hai.
Sahi chunk size select karna bahut zaroori hai.

### Fixed Chunking
Sabse simple method. Char count se split karo.

### Semantic Chunking
Expensive lekin best quality deta hai.

## Conclusion
RAG + good chunking = high quality answers.
"""


def markdown_header_chunks(md: str) -> List[Dict[str, Any]]:
    """Theory doc Section 3 — header pe split, header info metadata mein rakho."""
    pattern = re.compile(r"^(#{1,6})\s+(.+)", re.MULTILINE)
    headers = list(pattern.finditer(md))
    chunks = []
    for idx, match in enumerate(headers):
        start = match.end()
        end = headers[idx + 1].start() if idx + 1 < len(headers) else len(md)
        content = md[start:end].strip()
        if content:
            level = len(match.group(1))
            chunks.append({
                "text": content,
                "metadata": {
                    "header": match.group(2),
                    "level": level,
                    "header_path": match.group(1) + " " + match.group(2),
                }
            })
    return chunks


md_chunks = markdown_header_chunks(SAMPLE_MARKDOWN)
print(f"  Markdown chunks: {len(md_chunks)}")
for ch in md_chunks[:4]:
    print(f"  Header: {ch['metadata']['header_path']!r} | text: {ch['text'][:60]!r}...")

# --- 6B: Code AST Splitting ---
print("\n  --- 6B: Code AST Splitting ---")
CODE_SAMPLE = '''\
def greet(name):
    """User ko greet karo."""
    return f"Hello, {name}!"

class Calculator:
    """Simple calculator class."""
    def add(self, a, b):
        return a + b

    def subtract(self, a, b):
        return a - b

def farewell(name):
    return f"Goodbye, {name}!"
'''

AST_CODE = '''\
# Theory doc Section 3 (Code) — AST se function/class boundaries
import ast
tree = ast.parse(code)
chunks = [
    ast.unparse(node)
    for node in tree.body
    if isinstance(node, (ast.FunctionDef, ast.ClassDef))
]
'''
print(AST_CODE)


def code_ast_chunks(source: str) -> List[Dict[str, Any]]:
    """Theory doc Section 3 — AST se top-level function/class extract karo."""
    try:
        tree = ast.parse(source)
        chunks = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                chunks.append({
                    "text": ast.unparse(node),
                    "metadata": {
                        "type": type(node).__name__,
                        "name": node.name,
                        "lineno": node.lineno,
                    }
                })
        return chunks
    except SyntaxError as e:
        return [{"text": source, "metadata": {"error": str(e)}}]


ast_chunks = code_ast_chunks(CODE_SAMPLE)
print(f"  AST chunks: {len(ast_chunks)}")
for ch in ast_chunks:
    print(f"  {ch['metadata']['type']} '{ch['metadata']['name']}' | lines: {ch['text'].count(chr(10))+1}")

# --- 6C: Q&A Pair Chunking ---
print("\n  --- 6C: Q&A Pair Chunking ---")
QA_SAMPLE = [
    ("RAG kya hai?", "RAG = Retrieval-Augmented Generation. Documents retrieve karo, phir LLM se answer generate karo."),
    ("Chunking kyun zaroori hai?", "Chunking RAG quality ka #1 factor hai. Sahi size aur overlap = relevant retrieval."),
    ("Overlap kya hota hai?", "Adjacent chunks mein shared text. 10-20% overlap boundary pe information protect karta hai."),
]


def qa_pair_chunks(qa_list: List[Tuple[str, str]]) -> List[Dict[str, Any]]:
    """
    Theory doc Section 3 (Q&A) — ek Q+A pair = ek chunk.
    Retrieval ke liye ideal kyunki query usually question jaisi hoti hai.
    """
    return [
        {
            "text": f"Q: {q}\nA: {a}",
            "metadata": {"question": q, "chunk_type": "qa_pair", "index": i},
        }
        for i, (q, a) in enumerate(qa_list)
    ]


qa_chunks = qa_pair_chunks(QA_SAMPLE)
print(f"  Q&A chunks: {len(qa_chunks)}")
for ch in qa_chunks:
    print(f"  {ch['text'][:80]!r}...")


# =========================================================================
# SECTION 7: Overlap Demo
# Theory doc: Section 5 — boundary info protect karna
# =========================================================================
print("\n" + "=" * 65)
print("SECTION 7: Overlap — Boundary Info Protect Karna")
print("=" * 65)

OVERLAP_CODE = '''\
# Theory doc Section 5 — overlap ka visual demo
chunks_no_overlap = [text[0:200], text[200:400], text[400:600]]
chunks_with_overlap = [text[0:200], text[160:360], text[320:520]]
#                              ^^^^ 40 char overlap ^^^^
# Boundary pe jo sentence hai woh dono adjacent chunks mein hogi.
# Retrieval mein koi important fact miss nahi hoga.
'''
print(OVERLAP_CODE)

# Demo: boundary word overlap vs no-overlap
demo_text = "AAAA " * 20 + "IMPORTANT BOUNDARY INFO " + "BBBB " * 20
size = 50
overlap = 20

no_ov = fixed_chunks(demo_text, size=size, overlap=0)
with_ov = fixed_chunks(demo_text, size=size, overlap=overlap)

# Kaunse chunk mein "IMPORTANT" hai?
def find_important(chunks: List[str], keyword: str = "IMPORTANT") -> List[int]:
    return [i for i, ch in enumerate(chunks) if keyword in ch]

no_ov_found = find_important(no_ov)
with_ov_found = find_important(with_ov)

print(f"  Boundary keyword 'IMPORTANT' chunks:")
print(f"    Without overlap ({len(no_ov)} chunks): found in chunks {no_ov_found}")
print(f"    With overlap    ({len(with_ov)} chunks): found in chunks {with_ov_found}")
print(f"\n  Overlap {overlap}/{size} = {overlap/size:.0%} — theory doc recommends 10-20%.")
print(f"  More chunks mein keyword milna = better retrieval coverage.")


# =========================================================================
# SECTION 8: Metadata in Chunks
# Theory doc: Section 6 — source, page, section track karo
# =========================================================================
print("\n" + "=" * 65)
print("SECTION 8: Metadata in Chunks")
print("=" * 65)

META_CODE = '''\
# Theory doc Section 6 — metadata chunk ke saath rakho
chunk = {
    "text": "Python uses indentation...",
    "metadata": {
        "source": "tutorial.pdf",
        "page": 5,
        "section": "Python Basics",
        "chunk_index": 12,
        "char_start": 4200,
        "char_end": 4700,
    }
}
# Retrieval ke time filter kar sako:
# vectorstore.as_retriever(search_kwargs={"filter": {"source": "tutorial.pdf"}})
'''
print(META_CODE)


def chunks_with_metadata(
    text: str,
    source: str = "demo_doc.txt",
    section: str = "Main Section",
    chunk_fn=sentence_chunks,
    **kwargs,
) -> List[Dict[str, Any]]:
    """
    Theory doc Section 6 — har chunk ke saath metadata attach karo.
    source, page, section, char positions — sab track karo.
    """
    raw_chunks = chunk_fn(text, **kwargs)
    result = []
    char_pos = 0
    for i, ch in enumerate(raw_chunks):
        # Approximate char start position dhundho
        idx = text.find(ch[:30], char_pos)
        if idx == -1:
            idx = char_pos
        char_end = idx + len(ch)
        result.append({
            "text": ch,
            "metadata": {
                "source": source,
                "section": section,
                "chunk_index": i,
                "total_chunks": len(raw_chunks),
                "char_start": idx,
                "char_end": char_end,
                "char_length": len(ch),
            }
        })
        char_pos = max(char_pos, char_end - 50)  # small backtrack for overlap
    return result


meta_chunks = chunks_with_metadata(
    SAMPLE_TEXT, source="rag_tutorial.txt", section="RAG Basics",
    chunk_fn=sentence_chunks, max_size=300
)
print(f"  Chunks with metadata: {len(meta_chunks)}")
for ch in meta_chunks[:2]:
    print(f"  Text: {ch['text'][:60]!r}...")
    print(f"  Meta: {json.dumps(ch['metadata'], indent=4)}")


# =========================================================================
# SECTION 9: Chunk Size Trade-offs Summary
# Theory doc: Section 4 — table se values
# =========================================================================
print("\n" + "=" * 65)
print("SECTION 9: Chunk Size Trade-offs (Theory Table)")
print("=" * 65)

# Theory doc Section 4 table ka direct representation
TRADEOFFS = [
    ("100 tokens",  "Precise retrieval",       "Lost context",          "Q&A specific facts"),
    ("500 tokens",  "Sweet spot",               "—",                     "General RAG"),
    ("1000+ tokens","Full context",             "More noise, expensive", "Long-form analysis"),
]
print(f"  {'Size':<14} {'Pros':<28} {'Cons':<26} {'Use Case'}")
print(f"  {'-'*14} {'-'*28} {'-'*26} {'-'*24}")
for size, pros, cons, use in TRADEOFFS:
    print(f"  {size:<14} {pros:<28} {cons:<26} {use}")

print(f"\n  Default recommendation (theory doc Section 4):")
print(f"  500-1000 tokens with 10-20% overlap.")

# Demonstrate token vs char count difference
SAMPLE_SHORT = "RAG matlab Retrieval-Augmented Generation. Ye ek powerful AI technique hai."
char_count = len(SAMPLE_SHORT)
# Rough token estimate: ~0.75 tokens per word (GPT tokenizer approximation)
word_count = len(SAMPLE_SHORT.split())
est_tokens = int(word_count * 0.75)
print(f"\n  Token vs Char demo:")
print(f"  Text:     {SAMPLE_SHORT!r}")
print(f"  Chars:    {char_count}")
print(f"  Words:    {word_count}")
print(f"  Est. tokens (approx): {est_tokens}  (1 token ~ 4 chars or ~0.75 words)")
print(f"  Production mein tiktoken use karo exact token count ke liye.")


# =========================================================================
# SECTION 10: Strategy Comparison
# Theory doc: Section 8 (Testing) + Section 9 (Key Takeaways)
# =========================================================================
print("\n" + "=" * 65)
print("SECTION 10: Strategy Comparison (Mini Benchmark)")
print("=" * 65)


def benchmark_strategies(text: str) -> List[Dict[str, Any]]:
    """
    Sabhi strategies ek saath compare karo.
    Theory doc Section 8 — evaluate_chunking concept.
    """
    strategies = [
        ("Fixed-Size",    lambda t: fixed_chunks(t, size=200, overlap=40)),
        ("Sentence",      lambda t: sentence_chunks(t, max_size=300)),
        ("Recursive",     lambda t: recursive_char_split(t, chunk_size=300, overlap=50)),
        ("Semantic",      lambda t: semantic_chunks(t, threshold=0.3)),
        ("Hierarchical-L3", lambda t: [
            ch.text for ch in hierarchical_chunks(t) if ch.level == 3
        ]),
    ]
    results = []
    for name, fn in strategies:
        try:
            chunks = fn(text)
            chunks = [c for c in chunks if c.strip()]
            lengths = [len(c) for c in chunks]
            avg_len = sum(lengths) / len(lengths) if lengths else 0
            results.append({
                "strategy": name,
                "count": len(chunks),
                "avg_len": round(avg_len, 1),
                "min_len": min(lengths) if lengths else 0,
                "max_len": max(lengths) if lengths else 0,
            })
        except Exception as e:
            results.append({"strategy": name, "error": str(e)})
    return results


bench = benchmark_strategies(SAMPLE_TEXT)
print(f"  {'Strategy':<22} {'Count':>6} {'Avg Len':>9} {'Min':>6} {'Max':>6}")
print(f"  {'-'*22} {'-'*6} {'-'*9} {'-'*6} {'-'*6}")
for r in bench:
    if "error" in r:
        print(f"  {r['strategy']:<22} ERROR: {r['error']}")
    else:
        print(f"  {r['strategy']:<22} {r['count']:>6} {r['avg_len']:>9.1f} {r['min_len']:>6} {r['max_len']:>6}")

print(f"\n  [KEY INSIGHT] Koi ek 'best' strategy nahi hai.")
print(f"  Document type aur use case ke hisaab se choose karo.")
print(f"  Theory doc Section 8: multiple strategies test karo, recall measure karo.")


# =========================================================================
# SECTION 11: Live LLM Call — Groq se chunk quality check
# Theory doc: Section 8 — testing chunking concept
# =========================================================================
print("\n" + "=" * 65)
print("SECTION 11: Live LLM Call — Chunk Quality Check (Groq)")
print("=" * 65)

if MOCK_MODE:
    print("  [SKIP] GROQ_API_KEY nahi hai — live call skip kar rahe hain.")
    print("  GROQ_API_KEY set karo aur dobara chalao live demo ke liye.")
    print("  Mock response: 'Chunking strategy evaluation skipped in offline mode.'")
else:
    llm = get_client()
    if llm is None:
        print("  [SKIP] LLM client init fail hua — live call skip.")
    else:
        try:
            # Recursive chunks lenge aur LLM se quality check karenge
            test_chunks = recursive_char_split(SAMPLE_TEXT, chunk_size=300, overlap=50)
            sample_chunk = test_chunks[0] if test_chunks else SAMPLE_TEXT[:200]

            prompt = (
                f"Evaluate this RAG chunk for quality (1-10 scale):\n\n"
                f"CHUNK: {sample_chunk}\n\n"
                f"Rate: [1] Completeness [2] Coherence [3] Context.\n"
                f"One line response only."
            )
            print(f"  Sending chunk to Groq (llama3-8b-8192)...")
            response = llm.invoke(prompt)
            resp_text = response.content if hasattr(response, "content") else str(response)
            print(f"  LLM Quality Check: {resp_text.strip()}")
        except Exception as exc:
            print(f"  [WARN] Live call fail hua: {exc}")
            print(f"  [DEGRADED] Offline mode pe fall back — EXIT 0 guarantee.")


# =========================================================================
# SECTION 12: ChromaDB Integration (Optional — lazy import)
# Production mein chunks vector store mein jaate hain
# =========================================================================
print("\n" + "=" * 65)
print("SECTION 12: ChromaDB Integration (Optional)")
print("=" * 65)

print("  ChromaDB mein chunks store karna (if available)...")
# NOTE: chromadb.Client() ke saath query_texts use karne se ONNX model download hota hai.
# Offline demo ke liye hum get() use karte hain (no embedding needed).
try:
    import chromadb  # type: ignore
    # EphemeralClient = in-memory, no disk writes
    client_chroma = chromadb.EphemeralClient()
    # embedding_function=None — hum manually embeddings nahi de rahe,
    # sirf documents store aur id-based retrieve karenge (offline-safe)
    collection = client_chroma.get_or_create_collection(
        "chunking_demo",
        # Default embedding function network download karti hai — skip karo
        metadata={"hnsw:space": "cosine"},
    )
    demo_chunks = sentence_chunks(SAMPLE_TEXT, max_size=300)
    # Add with dummy embeddings (dim=3) — avoids network download for ONNX model
    import random as _random
    _random.seed(42)
    fake_embs = [[_random.random() for _ in range(3)] for _ in demo_chunks]
    collection.add(
        documents=demo_chunks,
        ids=[f"chunk_{i}" for i in range(len(demo_chunks))],
        embeddings=fake_embs,
        metadatas=[{"source": "demo", "index": i} for i in range(len(demo_chunks))],
    )
    print(f"  ChromaDB EphemeralClient mein {len(demo_chunks)} chunks store kiye.")
    # ID-based get (no query embedding needed — offline safe)
    stored = collection.get(ids=[f"chunk_{i}" for i in range(min(2, len(demo_chunks)))])
    print(f"  Stored chunk count: {collection.count()}")
    for doc in stored["documents"][:2]:
        print(f"  Sample stored doc: {doc[:70]!r}...")
    print(f"  [NOTE] Production mein real embeddings pass karo ya default embed fn use karo.")
except ImportError:
    print("  [SKIP] chromadb not installed.")
    print("  Install: pip install chromadb")
    print("  Fallback: In-memory dict se simulate kar sakte hain.")

    # Simple in-memory fallback — chromadb ke bina
    class SimpleVectorStore:
        """Bhot simple keyword-based retrieval — chromadb nahi hai to."""
        def __init__(self):
            self.docs: List[Dict[str, Any]] = []

        def add(self, chunks: List[str], metadatas: Optional[List[Dict]] = None):
            for i, ch in enumerate(chunks):
                self.docs.append({
                    "text": ch,
                    "meta": (metadatas or [{}] * len(chunks))[i],
                })

        def query(self, q: str, k: int = 2) -> List[str]:
            words = set(q.lower().split())
            scored = [
                (sum(1 for w in words if w in d["text"].lower()), d["text"])
                for d in self.docs
            ]
            scored.sort(key=lambda x: -x[0])
            return [text for _, text in scored[:k]]

    store = SimpleVectorStore()
    store.add(sentence_chunks(SAMPLE_TEXT, max_size=300), metadatas=[{"source": "demo"}])
    top = store.query("chunking size overlap", k=2)
    print(f"\n  In-memory fallback store — top-2 results:")
    for i, t in enumerate(top):
        print(f"  [{i+1}] {t[:80]!r}...")
except Exception as e:
    print(f"  [WARN] ChromaDB error: {e} — skipping.")


# =========================================================================
# FINAL SUMMARY — theory doc Section 9 ke Key Takeaways
# =========================================================================
print("\n" + "=" * 65)
print("CHUNKING STRATEGIES — KEY TAKEAWAYS (Theory Doc Section 9)")
print("=" * 65)

TAKEAWAYS = [
    "Chunking RAG quality ka #1 lever hai — iska sahi hona bahut zaroori.",
    "Recursive Character Splitter = solid default for most use cases.",
    "Semantic chunking = best quality, lekin embedding model chahiye.",
    "500-1000 token chunks with 10-20% overlap = standard production.",
    "Har chunk ke saath metadata raho — source, page, section.",
    "Document type ke hisaab se strategy adapt karo (Markdown, Code, Q&A).",
    "Multiple strategies test karo, retrieval recall measure karo.",
    "Overlap = boundary pe important info ko protect karna.",
    "Hierarchical chunking: small chunks retrieve, parent expand for context.",
]
for i, t in enumerate(TAKEAWAYS, 1):
    print(f"  {i}. {t}")

print("\n" + "=" * 65)
print("PRACTICE COMPLETE — Ab 05_embedding_models.md padho!")
print("=" * 65)
