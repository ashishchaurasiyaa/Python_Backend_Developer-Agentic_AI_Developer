"""
Classical ML/DL Foundations — Doc 12: CLASSICAL NLP PIPELINE (PRACTICAL)
========================================================================
See the text->numbers evolution with your own eyes, on a tiny built-in corpus
(no downloads): Bag-of-Words -> TF-IDF -> a real TF-IDF spam classifier ->
a from-scratch mini "Word2Vec-style" co-occurrence embedding + cosine similarity.

Run this to see:
  1. BoW counts vs TF-IDF weights on the SAME sentences (why "the" gets crushed)
  2. N-grams turning "new york" into one feature
  3. A TF-IDF + LogisticRegression spam classifier (the cheap LLM-free baseline)
  4. Why BoW/TF-IDF are "meaning-blind" (good vs great look unrelated)
  5. A tiny co-occurrence embedding where similar words land close (Word2Vec idea)

Install:
  pip install scikit-learn numpy

Run: python 12_classical_nlp_pipeline_practical.py
"""

import numpy as np
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics.pairwise import cosine_similarity

np.set_printoptions(precision=2, suppress=True)


def line(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Bag-of-Words vs TF-IDF on the same sentences
# ─────────────────────────────────────────────────────────────────────────────
line("SECTION 1: BoW counts vs TF-IDF weights (watch 'the' get crushed)")

docs = [
    "the cat sat on the mat",
    "the dog sat on the log",
    "the quantum computer solved the problem",
]

bow = CountVectorizer()
bow_matrix = bow.fit_transform(docs).toarray()
print("Vocabulary:", bow.get_feature_names_out().tolist())
print("\nBoW (raw counts) — 'the' scores high everywhere but means nothing:")
for d, row in zip(docs, bow_matrix):
    print(f"  {row}   <- {d}")

tfidf = TfidfVectorizer()
tfidf.fit(docs)
vocab = list(tfidf.get_feature_names_out())
# The IDF component is the cleanest way to SEE term importance (TF-IDF = TF x IDF).
# It ignores how many times a word repeats and asks only: how rare is it?
print("\nIDF weights (higher = rarer = more informative):")
for w in ["the", "sat", "quantum", "mat"]:
    print(f"  idf('{w:<8}') = {tfidf.idf_[vocab.index(w)]:.2f}")
print("  -> 'the' (in every doc) = lowest; 'quantum'/'mat' (one doc) = highest.")
print("     TF-IDF then multiplies this by the count, so common words stay small.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: N-grams — give local order back
# ─────────────────────────────────────────────────────────────────────────────
line("SECTION 2: N-grams turn 'new york' into a single feature")

ng = CountVectorizer(ngram_range=(1, 2))   # unigrams + bigrams
ng.fit(["new york city is big", "york city map"])
feats = ng.get_feature_names_out().tolist()
print("unigram+bigram features:", feats)
print("Notice 'new york' and 'york city' — phrases BoW alone would have split.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: The cheap, LLM-free baseline — TF-IDF + Logistic Regression
# ─────────────────────────────────────────────────────────────────────────────
line("SECTION 3: TF-IDF + LogReg spam classifier (ms latency, $0, no hallucination)")

train_texts = [
    "win a free prize now click here",
    "claim your free gift card today",
    "urgent you won cash click link",
    "limited offer buy now discount",
    "hey are we still meeting for lunch",
    "can you review my pull request please",
    "the report is attached let me know",
    "lets catch up tomorrow afternoon",
]
train_labels = [1, 1, 1, 1, 0, 0, 0, 0]   # 1 = spam, 0 = ham

vec = TfidfVectorizer()
Xtr = vec.fit_transform(train_texts)
clf = LogisticRegression().fit(Xtr, train_labels)

tests = ["free cash prize click now", "can we reschedule the meeting"]
Xte = vec.transform(tests)
preds = clf.predict(Xte)
proba = clf.predict_proba(Xte)[:, 1]
for t, p, pr in zip(tests, preds, proba):
    print(f"  [{'SPAM' if p else 'HAM '}] p(spam)={pr:.2f}  <- {t}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Why TF-IDF is "meaning-blind"
# ─────────────────────────────────────────────────────────────────────────────
line("SECTION 4: TF-IDF has NO idea 'good' and 'great' are related")

pair_docs = ["good", "great", "car"]
m = TfidfVectorizer().fit_transform(pair_docs).toarray()
sim_good_great = cosine_similarity([m[0]], [m[1]])[0, 0]
sim_good_car = cosine_similarity([m[0]], [m[2]])[0, 0]
print(f"cosine('good','great') = {sim_good_great:.2f}")
print(f"cosine('good','car')   = {sim_good_car:.2f}")
print("Both 0.00 — to TF-IDF, distinct words are equally unrelated. This is the")
print("exact limitation Word2Vec/embeddings fix next.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Word2Vec idea in miniature — a co-occurrence embedding
# ─────────────────────────────────────────────────────────────────────────────
line("SECTION 5: 'A word is known by its company' — similar words land close")

# Tiny corpus where king/queen share royal context, cat/dog share pet context.
corpus = [
    "the king ruled the royal palace",
    "the queen ruled the royal palace",
    "the cat sat by the warm fire",
    "the dog sat by the warm fire",
]
tokens = [w for s in corpus for w in s.split()]
vocab5 = sorted(set(tokens))
idx = {w: i for i, w in enumerate(vocab5)}
V = len(vocab5)

# Build a co-occurrence matrix (window = neighbours in each sentence).
co = np.zeros((V, V))
for s in corpus:
    ws = s.split()
    for i, w in enumerate(ws):
        for j in range(max(0, i - 2), min(len(ws), i + 3)):
            if i != j:
                co[idx[w], idx[ws[j]]] += 1

# Each row = that word's context vector (the crude ancestor of a learned embedding).
def sim(a, b):
    return cosine_similarity([co[idx[a]]], [co[idx[b]]])[0, 0]

print("cosine('king','queen') =", round(sim("king", "queen"), 2), " (share royal context)")
print("cosine('cat','dog')    =", round(sim("cat", "dog"), 2), "  (share pet context)")
print("cosine('king','cat')   =", round(sim("king", "cat"), 2), "  (different contexts)")
print("\nSame principle as Word2Vec — just counted instead of learned. Modern")
print("embeddings replace this row with a trained, contextual vector.")

print("\n" + "=" * 70)
print("DONE. This is the ancestry of your RAG embeddings + BM25 hybrid search.")
print("=" * 70)
