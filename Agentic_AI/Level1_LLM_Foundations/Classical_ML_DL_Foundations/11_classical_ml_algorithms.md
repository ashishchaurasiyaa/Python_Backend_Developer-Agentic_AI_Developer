# Classical ML/DL Foundations — Doc 11: Classical ML Algorithms & the DS Pipeline

> **Goal:** Docs 1–10 covered the *neural* line (regression → perceptron → MLP → CNN → RNN → transformer). Yeh doc us line ke **bagal wali branch** hai jo interviews aur DS roles me bahut poochhi jaati hai — classical supervised & unsupervised ML (SVM, KNN, Naive Bayes, Decision Trees, Random Forest, K-Means, DBSCAN) + poora **data science pipeline** (EDA → feature engineering → encoding → scaling → train/test → metrics). Yeh wo gap tha jo tumhare notes me missing tha (sirf regression + DL tha). Ab bharaa gaya.

> **Gap source:** Cross-checked against Tutedude "90-Day GenAI" Module 12 (Machine Learning, 30h). Wo module ka *content* yahaan condensed hai — theory + interview traps + kab kaunsa algo. Hands-on sklearn code: [`11_classical_ml_algorithms_practical.py`](11_classical_ml_algorithms_practical.py).

---

## 1. Why a Backend/Agentic Engineer Still Needs Classical ML

Tum LLMs/agents bana rahe ho, lekin:

- **Interviews me poochha jaata hai** "explain bias-variance", "precision vs recall", "when would you NOT use a neural net". Yeh classical ML se aate hain.
- **RAG/agents ke andar bhi** classical ML chhupa hai — embedding similarity = KNN, reranking = learned classifier, anomaly/spam filters = logistic/SVM baselines, clustering = deduping retrieved chunks.
- **"Boring but correct" baseline:** production me ek LLM classifier throw karne se pehle, logistic regression / random forest baseline lena — yeh senior judgment interviewers respect karte hain (cheaper, faster, interpretable, no hallucination).

---

## 2. The ML Development Lifecycle (The Real Job)

Algorithm choose karna kaam ka sirf **10%** hai. Baaki 90% pipeline hai:

```
1. Frame the problem      → business problem ko ML problem me convert karo (classification? regression? clustering?)
2. Gather data            → CSV / SQL / JSON / APIs
3. Clean data             → missing values, duplicates, outliers, wrong types
4. EDA                    → distributions, correlations, class balance samjho
5. Feature engineering    → naye useful columns banao, encode, scale
6. Split                  → train / validation / test
7. Train                  → fit the model
8. Evaluate               → RIGHT metric choose karo (accuracy alone = trap)
9. Tune                   → hyperparameters, cross-validation
10. Deploy + monitor      → drift, retraining
```

**Interview trap:** "Aapke model ka accuracy 95% hai" — senior answer: "95% accuracy meaningless hai agar dataset 95% ek class ka hai (imbalanced). Precision/recall/F1 dikhao." (Section 7)

---

## 3. Data Prep — Encoding & Scaling (the part everyone skips)

Models numbers samajhte hain, categories/strings nahi. Aur wo feature magnitudes ke prati sensitive hote hain.

### 3.1 Feature Encoding (categories → numbers)
| Technique | Kab use karo | Gotcha |
|---|---|---|
| **Label Encoding** | ordinal categories (low/med/high) | nominal pe mat lagao — model false order maan lega (red=0,green=1,blue=2 → "blue > red"?) |
| **One-Hot Encoding** | nominal categories (city, color) | high-cardinality (10k cities) → dimensionality explode; tab target/frequency encoding |
| **Ordinal Encoding** | explicit rank hai | order tumhe manually dena padta hai |

### 3.2 Feature Scaling (magnitudes ko barabar lao)
- **Standardization** (`z = (x − mean) / std`) → mean 0, std 1. Default choice. SVM, KNN, logistic, neural nets ke liye zaroori.
- **Normalization / Min-Max** (`x' = (x − min)/(max − min)`) → 0–1 range. Bounded input chahiye tab.
- **Kab zaroori:** distance/gradient based algos (KNN, SVM, K-Means, neural nets). **Kab nahi:** tree-based (Decision Tree, Random Forest) — split logic scale-invariant hai.

**Golden rule:** scaler ko **sirf train data pe `fit`** karo, phir train+test dono ko `transform`. Test pe fit karna = **data leakage** (classic interview kill-shot). Isliye sklearn `Pipeline` use karte hain — leakage automatically roka jaata hai.

---

## 4. Supervised Learning — Labeled Data se Seekhna

### 4.1 The Algorithm Cheat-Sheet

| Algorithm | Type | Core Idea | Strength | Weakness |
|---|---|---|---|---|
| **Linear Regression** | reg | best-fit line, MSE | interpretable, fast | only linear relations |
| **Logistic Regression** | clf | sigmoid → probability | interpretable baseline, calibrated probs | linear boundary only |
| **Naive Bayes** | clf | Bayes theorem + "features independent" assumption | text/spam pe great, tiny data pe works, super fast | independence assumption unrealistic |
| **KNN** | both | k nearest neighbours ka majority vote | no training, simple | slow at predict (lazy), curse of dimensionality, scaling zaroori |
| **SVM** | clf | max-margin hyperplane; kernel trick for non-linear | high-dim me strong, clear margins | large data pe slow, tuning tricky |
| **Decision Tree** | both | if/else splits (Gini/entropy) | interpretable, no scaling needed | overfits badly alone |
| **Random Forest** | both | many trees, **bagging**, vote | robust, strong default, low overfit | less interpretable, bigger |
| **Gradient Boosting** (XGBoost) | both | trees added sequentially, **boosting** errors | often best on tabular data | tuning/overfit care |

### 4.2 Concepts interviewers actually probe

**Naive Bayes — why "naive"?** Assumes har feature independent hai given the class. Real me galat (words correlate), phir bhi spam/text classification pe shockingly achha — kyunki decision boundary sahi jagah aa jaati hai bhale probabilities calibrated na ho.

**KNN — "lazy learner":** koi training nahi; predict ke time saare points se distance nikaalta hai. `k` chhota → noisy/overfit; `k` bada → oversmooth. Odd `k` lo taaki tie na ho. Scaling **must** (warna bada-magnitude feature dominate karega).

**Kernel trick (SVM):** data ko higher dimension me implicitly map karo jahaan wo linearly separable ho jaaye — bina actually compute kiye (RBF/polynomial kernel). Isi wajah se SVM non-linear boundaries bana leta hai.

---

## 5. Bagging vs Boosting (guaranteed interview question)

| | **Bagging** (Random Forest) | **Boosting** (XGBoost/AdaBoost) |
|---|---|---|
| Training | trees **parallel**, independent | trees **sequential**, each fixes previous errors |
| Data | random subsets (bootstrap) + random features | full data, misclassified points ka weight badhta hai |
| Goal | **variance** kam karo (overfit ko taming) | **bias** kam karo (weak → strong) |
| Risk | rarely overfits | overfit kar sakta hai agar zyada rounds |

One-liner: **Bagging = many independent opinions averaged (reduces variance). Boosting = each student learns from the last one's mistakes (reduces bias).**

---

## 6. Unsupervised Learning — No Labels

| Algorithm | Idea | Kab | Gotcha |
|---|---|---|---|
| **K-Means** | k centroids, points ko nearest centroid pe assign, repeat | customer segmentation, chunk dedup | `k` pehle dena padta hai (Elbow method); spherical clusters maanta hai; outlier-sensitive |
| **Hierarchical** | merge/split clusters into a tree (dendrogram) | `k` nahi pata, nested structure | O(n²), bade data pe slow |
| **DBSCAN** | density-based; dense regions = clusters | arbitrary shapes, outliers ignore karne ho | `eps`/`min_samples` tuning; varying density pe struggle |
| **Anomaly Detection** | normal se door = anomaly (Isolation Forest, One-Class SVM) | fraud, intrusion, defect | "normal" define karna hard |

**K-Means vs DBSCAN interview line:** "K-Means ko cluster count chahiye aur wo round clusters maanta hai; DBSCAN count nahi maangta, weird shapes handle karta hai, aur noise ko explicitly outlier mark karta hai — par uska density parameter tuning sensitive hai."

**Connect to your agentic work:** retrieved chunks ko dedup/cluster karne ke liye K-Means/DBSCAN on embeddings; anomaly detection = guardrail for weird agent inputs.

---

## 7. Metrics — The Part That Wins Interviews

### 7.1 Regression
- **MAE** — average absolute error (same units, outlier-robust)
- **MSE / RMSE** — squares errors (bade errors ko zyada punish; RMSE same units as target)
- **R²** — variance ka kitna % explain hua (1 = perfect, 0 = mean se better nahi)

### 7.2 Classification — the confusion matrix
```
                 Predicted +      Predicted −
Actual +          TP               FN   (missed)
Actual −          FP (false alarm) TN
```
- **Accuracy** = (TP+TN)/all → **imbalanced data pe jhoothi** (99% "not-fraud" bolke 99% accuracy)
- **Precision** = TP/(TP+FP) → "jab + bola, kitni baar sahi tha" → **FP mehnga ho tab** (spam filter: legit mail ko spam mat bolo)
- **Recall** = TP/(TP+FN) → "saare actual + me se kitne pakde" → **FN mehnga ho tab** (cancer/fraud detection: ek bhi miss na ho)
- **F1** = precision & recall ka harmonic mean → dono balance karne ho
- **ROC-AUC** = threshold ke across ranking quality (1 = perfect, 0.5 = random)

**The precision/recall tradeoff line:** "Threshold badhao → precision ↑ recall ↓; ghatao → recall ↑ precision ↓. Kaunsa chahiye wo *cost of error* decide karta hai — fraud me recall, spam me precision."

---

## 8. Bias, Variance, Overfitting (the mental model)

- **Underfitting (high bias):** model bahut simple, train aur test dono pe kharab. → bada model, zyada features.
- **Overfitting (high variance):** train pe perfect, test pe kharab (noise ratt liya). → regularization, more data, dropout, simpler model, cross-validation.
- **Sweet spot:** train aur validation error dono low aur close.

**Fixes for overfitting:** more data · regularization (L1/L2) · dropout (NN) · pruning (trees) · ensembling · early stopping · cross-validation.

**Cross-validation (k-fold):** data ko k parts me baanto, k-1 pe train 1 pe validate, rotate. Ek lucky/unlucky split pe bharosa nahi — har point ek baar validation banta hai. Robust estimate.

**Train / Validation / Test:** train = seekhna; validation = tuning/model-selection; test = **final unbiased** score (ek hi baar, end me chhuo).

---

## 9. Which Algorithm Do I Pick? (decision shortcut)

- **Tabular data, strong default:** Random Forest / XGBoost. (Neural net tabular pe aksar *behtar nahi*.)
- **Interpretability chahiye:** Logistic Regression / Decision Tree.
- **Text / spam, small data:** Naive Bayes.
- **High-dim, clear margin:** SVM.
- **Baseline pehle:** Logistic Regression — hamesha. Phir tree ensembles.
- **Labels nahi:** clustering (K-Means/DBSCAN).
- **Images / sequences / huge unstructured:** ab neural nets (docs 6–10).

---

## 10. Interview-Ready Questions

1. Accuracy kab misleading hai, aur uski jagah kya dekhoge?
2. Precision vs recall — ek fraud aur ek spam example do jahaan alag-alag matter karta hai.
3. Bagging vs boosting — kya reduce karte hain (variance vs bias)?
4. KNN "lazy learner" kyun hai, aur scaling kyun zaroori?
5. Naive Bayes "naive" kyun, phir bhi text pe achha kyun?
6. Kernel trick kya karta hai SVM me?
7. Data leakage kya hai, aur Pipeline usse kaise rokta hai?
8. K-Means vs DBSCAN — kab kaunsa?
9. Overfitting kaise detect aur fix karoge?
10. Tabular problem pe neural net ke bajaye Random Forest kab, aur kyun?

---

## 11. Recap

| Layer | Kya seekha |
|---|---|
| Pipeline | frame → gather → clean → EDA → feature eng → split → train → eval → tune |
| Prep | encoding (label/one-hot), scaling (standard/min-max), leakage se bacho |
| Supervised | LogReg, NB, KNN, SVM, Trees, RF, Boosting — kab kaunsa |
| Unsupervised | K-Means, Hierarchical, DBSCAN, anomaly |
| Metrics | reg: MAE/RMSE/R² · clf: precision/recall/F1/AUC |
| Model behavior | bias-variance, overfit fixes, cross-validation |

**Next:** [`12_classical_nlp_pipeline.md`](12_classical_nlp_pipeline.md) — text ko numbers me kaise badalte hain (BoW → TF-IDF → Word2Vec), jo modern embeddings ka dada-pardada hai.
