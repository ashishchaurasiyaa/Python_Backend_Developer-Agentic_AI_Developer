"""
Classical ML/DL Foundations — Doc 6: CNN CONVOLUTION & POOLING (PRACTICAL)
=============================================================================
From-scratch, numpy-only. No PyTorch, no downloaded dataset — a small
synthetic image so you can see every convolution and pooling step happen.

Run this to see:
  1. A hand-drawn synthetic image with a vertical edge
  2. A vertical-edge-detection kernel actually detecting that edge (convolution)
  3. Max pooling shrinking the feature map while keeping the strongest signal
  4. Multiple kernels producing multiple feature maps (like a real conv layer)

Install:
  pip install numpy

Run: python 06_cnn_computer_vision_practical.py
"""

import numpy as np

np.set_printoptions(precision=1, suppress=True)


def conv2d(image, kernel, stride=1):
    """Valid (no padding) 2D convolution. Pure numpy, explicit loops for clarity."""
    ih, iw = image.shape
    kh, kw = kernel.shape
    oh = (ih - kh) // stride + 1
    ow = (iw - kw) // stride + 1
    output = np.zeros((oh, ow))
    for i in range(oh):
        for j in range(ow):
            region = image[i * stride:i * stride + kh, j * stride:j * stride + kw]
            output[i, j] = np.sum(region * kernel)
    return output


def max_pool(feature_map, pool_size=2, stride=2):
    h, w = feature_map.shape
    oh = (h - pool_size) // stride + 1
    ow = (w - pool_size) // stride + 1
    output = np.zeros((oh, ow))
    for i in range(oh):
        for j in range(ow):
            region = feature_map[i * stride:i * stride + pool_size, j * stride:j * stride + pool_size]
            output[i, j] = np.max(region)
    return output


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: A Synthetic Image with a Clear Vertical Edge
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 1: Synthetic 8x8 Image — Dark Left Half, Bright Right Half")
print("=" * 70)

image = np.array([
    [10, 10, 10, 10, 90, 90, 90, 90],
    [10, 10, 10, 10, 90, 90, 90, 90],
    [10, 10, 10, 10, 90, 90, 90, 90],
    [10, 10, 10, 10, 90, 90, 90, 90],
    [10, 10, 10, 10, 90, 90, 90, 90],
    [10, 10, 10, 10, 90, 90, 90, 90],
    [10, 10, 10, 10, 90, 90, 90, 90],
    [10, 10, 10, 10, 90, 90, 90, 90],
], dtype=float)

print(image)
print("(There's a clear vertical edge between column 3 and column 4)\n")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Convolve with a Vertical-Edge-Detection Kernel
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 2: Convolution with a Vertical-Edge Kernel")
print("=" * 70)

vertical_edge_kernel = np.array([
    [-1, 0, 1],
    [-1, 0, 1],
    [-1, 0, 1],
], dtype=float)

feature_map = conv2d(image, vertical_edge_kernel, stride=1)
print("Kernel:\n", vertical_edge_kernel)
print("\nResulting feature map (6x6, since 8-3+1=6):")
print(feature_map)
print("\n→ Notice the LARGE values (240) right where the edge is (middle columns")
print("  of the output), and near-ZERO everywhere else. The kernel found the edge.\n")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Max Pooling — Shrink the Feature Map, Keep the Strongest Signal
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 3: Max Pooling (2x2, stride 2)")
print("=" * 70)

pooled = max_pool(np.abs(feature_map), pool_size=2, stride=2)
print("Feature map (abs value) before pooling (6x6):")
print(np.abs(feature_map))
print("\nAfter 2x2 max pooling (3x3, since 6/2=3):")
print(pooled)
print("\n→ Half the spatial size, but the strongest edge signal (middle column)")
print("  is still clearly preserved — that's the point of pooling.\n")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Multiple Kernels = Multiple Feature Maps (a real conv LAYER)
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 4: A Conv Layer = Many Kernels, Each Detecting Something Different")
print("=" * 70)

horizontal_edge_kernel = np.array([
    [-1, -1, -1],
    [0, 0, 0],
    [1, 1, 1],
], dtype=float)

blur_kernel = np.ones((3, 3)) / 9.0   # simple averaging / smoothing kernel

kernels = {
    "vertical_edge": vertical_edge_kernel,
    "horizontal_edge": horizontal_edge_kernel,
    "blur": blur_kernel,
}

for name, k in kernels.items():
    fmap = conv2d(image, k)
    print(f"  Kernel '{name}': output range = [{fmap.min():.1f}, {fmap.max():.1f}], "
          f"mean |activation| = {np.mean(np.abs(fmap)):.2f}")

print("\n→ vertical_edge kernel has the strongest activation (this image has a")
print("  vertical edge, not horizontal) — a real CNN LEARNS which kernels are")
print("  useful via backprop (doc 4), instead of us hand-designing them.")
print("=" * 70)
