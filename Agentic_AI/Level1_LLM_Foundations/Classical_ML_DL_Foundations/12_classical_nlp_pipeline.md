# Classical ML/DL Foundations — Doc 12: Classical NLP Pipeline & Text Vectorization

> **Goal:** Tumhare notes modern embeddings (`Level5_RAG_Vector_Databases/05_embedding_models.md`) se shuru hote hain — lekin *usse pehle* ka classical NLP missing tha. Yeh doc wahi bharaa: text cleaning → tokenization → Bag-of-Words → TF-IDF → N-grams → Word2Vec. Yeh **exactly wo evolution hai jo aaj ke transformer embeddings tak pahunchi** — aur interview me "how does an embedding actually work" ka sahi jawaab yahin se aata hai.

> **Gap source:** Tutedude "90-Day GenAI" Module 13 (NLP, 15h) condensed. Hands-on code (TF-IDF classifier + Word2Vec): [`12_classical_nlp_pipeline_practical.py`](12_classical_nlp_pipeline_practical.py).

---

## 1. Why Classical NLP Still Matters (You Use LLMs, So What?)

- **Embeddings ka foundation:** OpenAI/Cohere embedding = Word2Vec/GloVe ka evolved version. "Dense vector jisme meaning encode hai" — yeh idea yahin se aaya. Interviewer poochhega "why is cosine similarity used for embeddings?" — jawaab classical vector space model se hai.
- **Cheap baselines:** har text task LLM nahi maangta. Spam filter, intent classifier, dedup — TF-IDF + logistic regression milliseconds me chalta hai, $0 cost, no hallucination.
- **RAG internals:** BM25 (jo tumhare `06_hybrid_search.md` me hai) = TF-IDF ka production cousin. Hybrid search samajhne ke liye classical term-weighting samajhna zaroori.

---

## 2. The Classical NLP Pipeline

```
Raw text
  → Text cleaning        (lowercase, punctuation, noise hatao)
  → Tokenization         (sentence/word tokens me todo)
  → Normalization        (stopwords, stemming/lemmatization)
  → Vectorization        (text → numbers: BoW / TF-IDF / Word2Vec)
  → Model                (classifier / similarity / clustering)
```

Model numbers khaata hai — **vectorization hi asli "NLP" step hai** jo text ko usable banata hai.

---

## 3. Text Cleaning & Normalization

| Step | Kya | Kyun / Gotcha |
|---|---|---|
| **Lowercase** | "Apple"→"apple" | vocab chhota; par "Apple" (company) vs "apple" (fruit) info gum ho sakti |
| **Remove punctuation/HTML/URLs** | noise hatao | par emoji/`!` sentiment me matter kar sakte |
| **Tokenization** | text → tokens | "don't" → ["do","n't"]? language-aware karo |
| **Stopword removal** | "the/is/a" hatao | BoW/TF-IDF me useful; par "to be or not to be" sab stopwords — kabhi meaning maar deta hai |
| **Stemming** | "running/runs"→"run" (rule-chop) | fast, par kabhi non-word ("studies"→"studi") |
| **Lemmatization** | "better"→"good" (dictionary) | accurate, dheema; POS chahiye |

**Stemming vs Lemmatization interview line:** "Stemming rule-based chopping hai (fast, sloppy — 'studies'→'studi'); lemmatization dictionary+grammar se real base word deta hai ('better'→'good') — accurate par slow."

> **Note:** Transformers ke saath yeh heavy cleaning **ulta bhi ho sakti hai** — subword tokenizers (BPE) casing/morphology se seekhte hain. Classical (BoW/TF-IDF) me cleaning zaroori; LLM embeddings me minimal cleaning. Yeh distinction senior signal hai.

---

## 4. Vectorization — Text ko Numbers Banana

### 4.1 One-Hot / Bag-of-Words (BoW)

Har document ko vocabulary-size vector se represent karo, jisme har position ek word ka **count** hai.

```
Vocab: [ai, is, fun, hard]
"ai is fun"      → [1, 1, 1, 0]
"ai is hard"     → [1, 1, 0, 1]
```

- ✅ Simple, fast, interpretable, strong baseline (BoW + NB spam pe classic).
- ❌ **Word order gum** ("dog bites man" == "man bites dog"). **Sparse & huge** (vocab=50k → 50k-dim). **No meaning** ("good"/"great" utne hi door jitne "good"/"car").

### 4.2 TF-IDF — Har Word Barabar Nahi Hota

BoW me "the" 100 baar aata hai par bekaar. TF-IDF common words ko down-weight, rare-but-informative words ko up-weight karta hai.

```
TF   = term ka count us doc me (kitni baar aaya)
IDF  = log(total docs / docs containing term)   ← rare word = high IDF
TF-IDF = TF × IDF
```

Intuition: "the" har doc me → IDF≈0 → weight≈0. "quantum" sirf kuch docs me → high IDF → high weight. **Rare, document-defining words ko spotlight.**

- ✅ Better baseline, still interpretable, search/ranking ka backbone (**BM25 = TF-IDF ka tuned production version**, tumhare hybrid-search me).
- ❌ Abhi bhi order-blind aur meaning-blind ("king"/"queen" ka koi relation nahi).

### 4.3 N-Grams — Thoda Context Wapas

Single words ke bajaye consecutive word-groups:
- unigram: `["new","york","city"]`
- bigram: `["new york","york city"]`
- trigram: `["new york city"]`

"new york" ek unit ban jaata hai. Local order/phrases capture hota hai — cost: vocabulary explode. (BoW/TF-IDF ke saath combine karte hain.)

---

## 5. Word Embeddings — Word2Vec (The Leap to Meaning)

BoW/TF-IDF ka core problem: **"good" aur "great" ek dusre se utne hi anjaan jitne "good" aur "car".** Word2Vec ne isko toda — har word ko ek **dense vector** (e.g. 300 numbers) do jahaan **similar-meaning words paas** hon.

### 5.1 The Idea: "You shall know a word by the company it keeps"
Distributional hypothesis — jo words similar contexts me aate hain, unka matlab similar hai. Word2Vec ek chhoti neural net ko yeh predict karne pe train karta hai, aur **hidden layer ke weights hi embeddings ban jaate hain**.

**Do flavours:**
- **CBOW** — surrounding context se center word predict karo (fast, common words pe achha)
- **Skip-gram** — center word se context predict karo (rare words pe behtar, slow)

### 5.2 The Magic: Vector Arithmetic
```
vec("king") − vec("man") + vec("woman") ≈ vec("queen")
```
Meaning geometry ban gayi — direction "royalty", direction "gender". Yahi wo "semantic space" hai jise aaj cosine similarity se search karte ho.

### 5.3 Word2Vec → Modern Embeddings (the bridge)
| | Word2Vec (2013) | Modern (OpenAI/BERT) |
|---|---|---|
| Vector per word | **fixed** ("bank" ka ek hi vector) | **contextual** ("river bank" vs "money bank" alag) |
| Model | shallow net | deep transformer |
| Sentence-level | average words (crude) | native sentence embedding |

**Word2Vec ki limitation** (ek word = ek vector, context ignore) = **exactly** wo problem jo transformers ke contextual embeddings ne solve kiya. Yeh seedha connect karta hai `Deep_Architecture/03_embeddings_and_position.md` se. Tum classical → modern ka poora arc ab bol sakte ho.

---

## 6. Similarity — Cosine, Not Distance

Dense vectors ko compare karne ke liye **cosine similarity** (angle, magnitude nahi):
```
cos(θ) = (A · B) / (|A| × |B|)     range: −1 … 1  (1 = same direction = same meaning)
```
Magnitude (word frequency/length) ignore, **direction (meaning)** matter — isiliye embeddings/RAG me cosine default hai. Yeh direct link hai tumhare vector DB retrieval se.

---

## 7. Putting It Together — Recommendation / Classifier Mini-Project

Classical NLP ka canonical project (Tutedude bhi yahi karwaata hai):
1. Text clean + tokenize
2. TF-IDF vectorize (ya Word2Vec average)
3. Cosine similarity (recommendation) **ya** Logistic Regression / Naive Bayes (classification)
4. Deploy as Streamlit/FastAPI

Yeh "content-based recommender" ya "spam classifier" hai — practical file me end-to-end hai. Concept: **text → vector → similarity/model** — bilkul wahi shape jo RAG retrieval ka hai, bas embeddings modern ho jaate hain.

---

## 8. Interview-Ready Questions

1. BoW ki 2 badi limitations kya hain? TF-IDF kaunsi fix karta hai, kaunsi nahi?
2. TF-IDF me IDF ka kaam kya hai — intuition do.
3. Stemming vs lemmatization — tradeoff?
4. Word2Vec BoW/TF-IDF se fundamentally alag kaise? "king − man + woman" kya dikhata hai?
5. CBOW vs Skip-gram?
6. Word2Vec embeddings BERT/OpenAI embeddings se kaise alag (static vs contextual)?
7. Similarity ke liye cosine kyun, euclidean kyun nahi?
8. Transformers ke saath heavy text-cleaning kab *nahi* karni chahiye?
9. BM25 aur TF-IDF ka rishta? (hybrid search se connect)
10. Sentiment ke liye LLM ke bajaye TF-IDF + logistic regression kab chunoge?

---

## 9. Recap — The Evolution in One Table

| Method | Captures order? | Captures meaning? | Dim | Legacy today |
|---|---|---|---|---|
| **One-Hot / BoW** | ❌ | ❌ | huge, sparse | quick baseline |
| **TF-IDF** | ❌ | ❌ (weights terms) | huge, sparse | **BM25 / search / hybrid retrieval** |
| **N-grams** | 🟡 local | ❌ | bigger | phrase features |
| **Word2Vec/GloVe** | ❌ | ✅ static | dense (~300) | pre-transformer embeddings |
| **Transformer (BERT/OpenAI)** | ✅ | ✅ contextual | dense (768+) | **your RAG embeddings** |

**The one-line arc:** *count words → weight rare words → embed meaning statically → embed meaning in context.* Har step ne pichhle ki ek limitation todi — aur aakhri step tumhare Deep_Architecture notes hain.

**Next:** wapas modern stack — [`../../Level5_RAG_Vector_Databases/05_embedding_models.md`](../../Level5_RAG_Vector_Databases/05_embedding_models.md) (ab pata hai embeddings *kahaan se* aaye) aur [`../../Level5_RAG_Vector_Databases/06_hybrid_search.md`](../../Level5_RAG_Vector_Databases/06_hybrid_search.md) (BM25 = yeh TF-IDF).
