# Classical ML/DL Foundations — Doc 6: CNNs for Computer Vision Applications

> **Goal:** Ek MLP image ko samajhne me bahut inefficient hai (har pixel ko har neuron se connect karna — millions of unnecessary weights, aur spatial structure ignore ho jaati hai). CNN ne yeh solve kiya: images ke liye ek specialized architecture jo local patterns detect karta hai aur spatial hierarchy samajhta hai.

---

## 1. Why Not Just Use an MLP on Images?

A 224×224 RGB image = 224 × 224 × 3 = **150,528 input values**. A fully-connected hidden layer with just 1,000 neurons would need 150 million weights in the FIRST layer alone.

Problems:
1. **Too many parameters** — massive overfitting risk, huge compute cost.
2. **Ignores spatial structure** — an MLP treats pixel (0,0) and pixel (223,223) as unrelated inputs; it has no built-in notion that nearby pixels are related (edges, textures, shapes are all *local* patterns).
3. **Not translation-invariant** — if a cat moves from the top-left to bottom-right of the image, an MLP has to re-learn "cat" as a totally different pattern of input neurons.

**CNN's fix:** instead of connecting every input to every neuron, use small, reusable filters that slide across the whole image, looking for the same local pattern everywhere.

---

## 2. The Convolution Operation

A **kernel** (a.k.a. filter) is a small matrix (e.g. 3×3) of learnable weights. It slides ("convolves") across the image, and at each position computes a weighted sum of the pixels under it.

```
Image patch (3x3):        Kernel (3x3):           Element-wise multiply, then sum:
 10  10  10                -1  0  1
 10  10  10        *        -1  0  1        =    (sum of all 9 products) = one output pixel
 10  10  10                -1  0  1
```

This single output value becomes one pixel of the **feature map** — the kernel's slide across the whole image produces a whole new (usually smaller) image, where each pixel says "how strongly did this pattern match, here?"

### 2.1 Concrete Example: An Edge-Detection Kernel

```python
edge_kernel = [
    [-1, 0, 1],
    [-1, 0, 1],
    [-1, 0, 1],
]
```

This kernel produces a **large output** when there's a strong left-to-right brightness change under it (a vertical edge), and near-zero output over a flat, uniform region. This is a *hand-designed* kernel (classic computer vision, pre-deep-learning) — CNNs LEARN kernels like this automatically via backpropagation, discovering whatever patterns are useful for the task, not just edges.

### 2.2 Key Convolution Parameters

| Parameter | Meaning |
|---|---|
| **Kernel size** | typically 3×3 or 5×5 — how big a local region each filter looks at |
| **Stride** | how many pixels the kernel moves per step (stride=1: dense overlap; stride=2: skips, shrinks output faster) |
| **Padding** | add zeros around the image border so the kernel can be centered on edge pixels too (keeps output size closer to input size) |
| **Number of filters** | a conv layer usually has MANY kernels (e.g. 64), each learning to detect a *different* pattern — one feature map per kernel |

---

## 3. Why Convolution Solves the MLP's Problems

1. **Parameter sharing:** the SAME 3×3 kernel (just 9 weights + bias) slides across the ENTIRE image. Whether the pattern appears top-left or bottom-right, the same weights detect it — this directly gives **translation invariance**, and it's why a 3×3 kernel has only ~10 weights instead of the millions an MLP would need.
2. **Local connectivity:** each output only depends on a small neighborhood of the input — matches the real structure of images (an edge is a local phenomenon, not a global one).
3. **Hierarchical composition:** stack conv layers — early layers' kernels learn simple patterns (edges, colors, gradients), middle layers combine those into textures/shapes, deep layers combine shapes into whole objects (faces, cars, cats). This is doc 5's "hierarchical features" idea, made concrete for images.

```
Layer 1 kernels detect:   edges, color blobs, simple gradients
Layer 2 kernels detect:   corners, textures, simple shapes (combinations of edges)
Layer 3 kernels detect:   object parts (eyes, wheels, wings)
Layer 4+ kernels detect:  whole objects (face, car, bird)
```

---

## 4. Pooling — Shrinking the Feature Map

After convolution, **pooling** layers downsample the feature map (usually 2×2 → keep only 1 value), most commonly **max pooling**: keep the maximum value in each 2×2 region.

```
Feature map (4x4):              Max pool 2x2, stride 2 → output (2x2):
 1  3  2  4                       3  4
 5  6  1  2          →            6  4
 3  1  4  9                       3  9
 0  2  8  1
```

Why pool:
- **Reduces computation** for later layers (smaller spatial size).
- **Adds a bit more translation invariance** — the exact pixel position of the strongest activation matters less; what matters is that the pattern was detected *somewhere* in that region.

---

## 5. A Typical CNN Architecture

```
Input Image
   ↓
[Conv → ReLU → Pool] × several blocks   (feature extraction — gets progressively "deeper but smaller")
   ↓
Flatten (turn final feature maps into one long vector)
   ↓
[Fully-Connected MLP layers]              (doc 2's MLP — classification "head")
   ↓
Softmax output (class probabilities)      (doc 3)
```

Notice: the END of a CNN is just an MLP (doc 2) with a softmax (doc 3) — CNNs don't replace MLPs, they add a specialized *feature-extraction* front-end before handing off to a standard MLP classifier.

---

## 6. Where CNNs Fit Alongside Transformers (Your Actual Domain)

- **Vision Transformers (ViT)** now compete with/replace CNNs for many vision tasks by treating an image as a sequence of patches and applying transformer attention instead of convolution — but CNNs remain dominant for efficiency-constrained vision (mobile, edge devices) and are still the backbone of many multimodal LLMs' vision encoders (e.g., CLIP-style encoders that feed into GPT-4V/Claude's vision capability use conv-based or hybrid backbones).
- **Diffusion models** (doc 10, DALL-E/Stable Diffusion) use a U-Net architecture that is fundamentally **convolutional** at its core, even though the overall diffusion *process* is a separate idea. Understanding CNNs is a prerequisite for understanding how image generation models actually process pixels.
- `Modern_Topics/05_multimodal.md` (in your repo) covers how vision inputs get tokenized/embedded for multimodal LLMs — CNNs (or ViT patch-embedding, a close cousin) are the layer doing that image → embedding conversion underneath.

---

## 7. Run the Practical

[`06_cnn_computer_vision_practical.py`](06_cnn_computer_vision_practical.py) implements **convolution and max-pooling from scratch with pure numpy** on a tiny synthetic image — no PyTorch, no downloaded dataset. You'll see a hand-designed edge kernel actually detect an edge, and max-pooling actually shrink a feature map, numerically.

---

## 8. Quick Recap

| Concept | One-liner |
|---|---|
| Convolution | Small learnable kernel slides across image, computing local weighted sums |
| Parameter sharing | Same kernel reused everywhere → far fewer weights than MLP, translation-invariant |
| Feature map | Output of one kernel sliding across the whole image |
| Pooling | Downsamples feature maps (usually max), adds mild translation invariance |
| CNN architecture | [Conv→ReLU→Pool] blocks (feature extraction) → MLP → Softmax (classification) |
| Modern successor | Vision Transformers (ViT) — patches + attention instead of convolution |

**Next:** [`07_rnn_lstm_sequential.md`](07_rnn_lstm_sequential.md) — the architecture family for *sequential* data (text, time series) that came before transformers: RNNs and LSTMs.
