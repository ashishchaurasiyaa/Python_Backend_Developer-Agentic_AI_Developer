# Classical ML/DL Foundations — Doc 1: Linear & Logistic Regression

> **Goal:** In LLM/transformer sab kuch samajhne se pehle, samjho ki neural network ka sabse chhota version kya hai. Linear regression aur logistic regression = 1-layer, 0-hidden-layer neural networks. Yeh foundation hai — baaki sab (perceptron, MLP, backprop, transformers) isi ka extension hai.

---

## 1. Why Start Here (Even Though You Already Use LLMs)

Tum already RAG, agents, LangGraph bana chuke ho — to yeh "basics" kyun?

Kyunki interview me jab poochha jaata hai *"explain gradient descent"* ya *"why does the model overfit"*, log LLM-level jargon (attention, RLHF) bolte hain lekin **foundation** miss kar dete hain. Ek senior candidate ko yeh pata hona chahiye ki:

- Loss function kya hota hai aur kyun minimize karte hain
- Gradient descent literally kaise kaam karta hai (formula level, na ki sirf "it optimizes")
- Linear → Logistic → Perceptron → MLP → Transformer — yeh ek continuous chain hai, alag-alag cheezein nahi

**This doc + the next few = that missing chain.**

---

## 2. Linear Regression — The Simplest Model

**Problem:** Given input `x` (a number or vector), predict output `y` (a continuous number).

Example: predict house price from square footage.

```
y_pred = w * x + b
```

- `w` (weight) — kitna slope hai (per unit x, y kitna badhta hai)
- `b` (bias) — jab x=0 ho tab bhi y ka baseline value

**Goal:** find `w` and `b` that make `y_pred` as close as possible to the real `y` across all training examples.

### 2.1 Loss Function — "Kitna Galat Hoon Main?"

```python
# Mean Squared Error (MSE)
loss = mean((y_pred - y_true) ** 2)
```

Squaring karte hain taaki:
1. Negative errors cancel out na ho jaayein (+2 aur -2 ka average 0 nahi hona chahiye)
2. Bade errors ko zyada penalize kare (2 ka square 4, 10 ka square 100 — badi galti "zyada buri" lagti hai)

### 2.2 How Do We Find the Best `w`, `b`?

Yahi asli sawaal hai — aur iska jawaab hai **gradient descent** (detail next doc me), lekin intuition abhi samjho:

```
1. Random w, b se start karo
2. Prediction karo, loss measure karo
3. Loss ko kam karne ke liye w aur b ko thoda adjust karo
   (direction: jis taraf loss kam hoti hai us taraf jao)
4. Repeat until loss stops improving
```

Yeh "adjust in the direction that reduces loss" hi hai neural network training ka core loop — chahe wo linear regression ho ya GPT-4.

---

## 3. Logistic Regression — Classification, Not Prediction

Linear regression continuous number predict karta hai (price, temperature). Lekin agar tumhe **yes/no** answer chahiye (spam ya not-spam, fraud ya not-fraud) to?

**Problem:** `w*x + b` ka output kuch bhi ho sakta hai (-∞ se +∞). Lekin probability chahiye 0 aur 1 ke beech.

**Solution:** Sigmoid function laga do.

```python
import math

def sigmoid(z):
    return 1 / (1 + math.exp(-z))

z = w * x + b          # raw score, can be any number
probability = sigmoid(z)  # squashed into (0, 1)
```

Sigmoid curve:
```
1.0 |                    ______
    |                 __/
0.5 |             __/
    |         __/
0.0 |______/
    -∞      0            +∞
```

- `z` bahut negative → sigmoid ≈ 0 (confident "no")
- `z` bahut positive → sigmoid ≈ 1 (confident "yes")
- `z = 0` → sigmoid = 0.5 (unsure)

### 3.1 Loss for Classification: Binary Cross-Entropy

MSE classification ke liye achha nahi kaam karta (gradient bahut flat ho jaata hai jab prediction bahut galat ho). Instead:

```python
# Binary cross-entropy (log loss)
loss = -(y_true * log(y_pred) + (1 - y_true) * log(1 - y_pred))
```

Intuition: agar `y_true = 1` (real answer "yes") aur model ne `y_pred = 0.01` (confidently "no") bola, to `-log(0.01)` = **bahut bada number** → bahut bada punishment. Confidently galat hona MSE se zyada punish hota hai yahaan — yeh important hai kyunki classification me confident-wrong predictions dangerous hote hain (jaise scam detector confidently kehta hai "safe" jab wo scam hai).

**This exact same loss (cross-entropy) is what trains every LLM** — next-token prediction is literally logistic regression repeated over the whole vocabulary (softmax = multi-class version of sigmoid). Tumne already `Level1_LLM_Foundations/Deep_Architecture/06_layer_stacking_and_output.md` me softmax dekha hai — ab pata chalega uska "chhota version" yahaan se aaya.

---

## 4. Linear/Logistic Regression = A Neural Network With Zero Hidden Layers

```
Input(s) x ──[weights w, bias b]──> z ──[activation]──> output
```

- Linear regression: activation = identity (kuch nahi karo, seedha output)
- Logistic regression: activation = sigmoid

**Yeh hi ek single neuron hai.** Agla doc (`02_perceptron_mlp.md`) me hum ise "perceptron" bolenge aur inko layers me stack karenge — wahi se deep learning shuru hoti hai.

---

## 5. Where This Shows Up in Your Real Work

- **Backend/ML feature scoring:** fraud-risk score, churn probability — often literally logistic regression in production (interpretable, fast, cheap — before reaching for a neural net).
- **A/B test analysis:** linear regression coefficients = "how much does feature X affect the outcome."
- **Interview trap question:** *"Why not use linear regression for classification?"* → answer: unbounded output range + MSE loss gives bad gradients near decision boundary; sigmoid + cross-entropy fixes both.
- **Your scam-detection project (from the syllabus)** — before reaching for an LLM classifier, a logistic regression baseline on TF-IDF features is the "boring but correct" first model interviewers respect.

---

## 6. Quick Recap

| Concept | Linear Regression | Logistic Regression |
|---|---|---|
| Output | continuous number | probability (0-1) |
| Activation | none (identity) | sigmoid |
| Loss | MSE | binary cross-entropy |
| Use case | price, temperature, score | yes/no, spam/not-spam, fraud/not-fraud |
| Neural net view | 1 neuron, no hidden layers | 1 neuron, no hidden layers |

**Next:** [`02_perceptron_mlp.md`](02_perceptron_mlp.md) — stack these neurons into layers → perceptron → MLP.
