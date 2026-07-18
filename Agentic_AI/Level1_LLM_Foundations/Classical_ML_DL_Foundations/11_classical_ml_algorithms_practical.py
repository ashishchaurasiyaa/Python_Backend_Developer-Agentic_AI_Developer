"""
Classical ML/DL Foundations — Doc 11: CLASSICAL ML ALGORITHMS (PRACTICAL)
=========================================================================
Unlike doc 1 (from-scratch numpy), this uses **scikit-learn** — because that
IS the real job: you rarely reimplement Random Forest, you compose a pipeline.

Run this to see, on synthetic data (no downloads):
  1. A leak-free Pipeline (encode + scale + model) — the correct pattern
  2. Supervised: LogReg, KNN, SVM, Naive Bayes, Decision Tree, Random Forest
     compared on the SAME split, with the RIGHT metrics
  3. Why accuracy lies on imbalanced data (precision/recall/F1 tell the truth)
  4. Cross-validation vs a single split
  5. Unsupervised: K-Means vs DBSCAN on the same points

Install:
  pip install scikit-learn numpy

Run: python 11_classical_ml_algorithms_practical.py
"""

import numpy as np
from sklearn.datasets import make_classification, make_moons
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import KNeighborsClassifier
from sklearn.svm import SVC
from sklearn.naive_bayes import GaussianNB
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.cluster import KMeans, DBSCAN
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, confusion_matrix,
)

np.random.seed(42)


def line(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: The correct pattern — a leak-free Pipeline
# ─────────────────────────────────────────────────────────────────────────────
line("SECTION 1: Pipeline = scale + model, fit ONLY on train (no leakage)")

X, y = make_classification(
    n_samples=2000, n_features=10, n_informative=6, n_redundant=2,
    weights=[0.9, 0.1], random_state=42,   # 90/10 imbalance on purpose
)
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.25, stratify=y, random_state=42
)

# The scaler is INSIDE the pipeline → it fits on train folds only. This is how
# you avoid the classic data-leakage interview trap automatically.
pipe = Pipeline([
    ("scaler", StandardScaler()),
    ("clf", LogisticRegression(max_iter=1000)),
])
pipe.fit(X_train, y_train)
print("Pipeline steps:", [name for name, _ in pipe.steps])
print("Test accuracy: %.3f" % pipe.score(X_test, y_test))


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2 + 3: Compare algorithms with the RIGHT metrics on imbalanced data
# ─────────────────────────────────────────────────────────────────────────────
line("SECTION 2+3: Same split, many models — accuracy vs precision/recall/F1")

models = {
    "LogReg":        LogisticRegression(max_iter=1000),
    "KNN":           KNeighborsClassifier(n_neighbors=7),
    "SVM (RBF)":     SVC(probability=True),
    "NaiveBayes":    GaussianNB(),
    "DecisionTree":  DecisionTreeClassifier(max_depth=6, random_state=42),
    "RandomForest":  RandomForestClassifier(n_estimators=200, random_state=42),
}

print(f"{'model':<14}{'acc':>7}{'prec':>7}{'recall':>8}{'f1':>7}{'auc':>7}")
print("-" * 50)
for name, clf in models.items():
    model = Pipeline([("scaler", StandardScaler()), ("clf", clf)])
    model.fit(X_train, y_train)
    pred = model.predict(X_test)
    # AUC needs scores; all these support predict_proba except tune-free SVC (we set probability=True)
    proba = model.predict_proba(X_test)[:, 1]
    print(f"{name:<14}"
          f"{accuracy_score(y_test, pred):>7.3f}"
          f"{precision_score(y_test, pred, zero_division=0):>7.3f}"
          f"{recall_score(y_test, pred):>8.3f}"
          f"{f1_score(y_test, pred):>7.3f}"
          f"{roc_auc_score(y_test, proba):>7.3f}")

print("\nLesson: high accuracy on 90/10 data is easy (predict 'majority' → 0.90).")
print("Recall/F1/AUC reveal whether the RARE (minority) class is actually caught.")

# Show a confusion matrix so TP/FP/FN/TN are concrete
best = Pipeline([("scaler", StandardScaler()),
                 ("clf", RandomForestClassifier(n_estimators=200, random_state=42))])
best.fit(X_train, y_train)
cm = confusion_matrix(y_test, best.predict(X_test))
print("\nRandomForest confusion matrix [rows=actual, cols=pred]:")
print("            pred_0  pred_1")
print(f"actual_0   {cm[0,0]:>6} {cm[0,1]:>7}")
print(f"actual_1   {cm[1,0]:>6} {cm[1,1]:>7}   <- minority class (fraud-like)")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Cross-validation vs a single split
# ─────────────────────────────────────────────────────────────────────────────
line("SECTION 4: One split can lie — cross-validation gives a stable estimate")

rf = Pipeline([("scaler", StandardScaler()),
               ("clf", RandomForestClassifier(n_estimators=200, random_state=42))])
scores = cross_val_score(rf, X, y, cv=5, scoring="f1")
print("5-fold F1 scores:", np.round(scores, 3))
print("mean = %.3f  std = %.3f  (std = how much a single split could fool you)"
      % (scores.mean(), scores.std()))


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Unsupervised — K-Means vs DBSCAN on non-spherical data
# ─────────────────────────────────────────────────────────────────────────────
line("SECTION 5: K-Means vs DBSCAN on two crescent 'moons'")

Xm, _ = make_moons(n_samples=400, noise=0.06, random_state=42)

km = KMeans(n_clusters=2, n_init=10, random_state=42).fit(Xm)
db = DBSCAN(eps=0.2, min_samples=5).fit(Xm)

n_db_clusters = len(set(db.labels_) - {-1})
n_noise = int((db.labels_ == -1).sum())
print("K-Means found 2 clusters (we HAD to tell it k=2), but it cuts the")
print("crescents straight through — it assumes round blobs.")
print(f"DBSCAN found {n_db_clusters} clusters on its own and flagged "
      f"{n_noise} points as noise/outliers (it follows density, any shape).")
print("\nTakeaway: shape + whether you know k decide K-Means vs DBSCAN.")

print("\n" + "=" * 70)
print("DONE. Re-read doc 11 sections 4-8 with these numbers in mind.")
print("=" * 70)
