"""
╔══════════════════════════════════════════════════════════════════╗
║                 TREES — Complete Theory Guide                    ║
╚══════════════════════════════════════════════════════════════════╝

WHAT IS A BINARY TREE?
───────────────────────
A tree where each node has at most two children: left and right.

Key Properties:
  - Root: top node (no parent)
  - Leaf: node with no children
  - Height: longest path from root to leaf
  - Depth: distance from root to node
  - For n nodes: height is O(log n) balanced, O(n) skewed

WHAT IS A BST?
───────────────
Binary Search Tree: for every node,
  - All values in LEFT subtree < node.val
  - All values in RIGHT subtree > node.val

BST enables O(log n) search, insert, delete (balanced).

COMPLEXITY TABLE
─────────────────────────────────────────────────────────────────
Operation        BST Avg     BST Worst   Array
─────────────────────────────────────────────────────────────────
Search           O(log n)    O(n)        O(n)
Insert           O(log n)    O(n)        O(1)/O(n)
Delete           O(log n)    O(n)        O(n)
Min/Max          O(log n)    O(n)        O(n)
In-order         O(n)        O(n)        —
─────────────────────────────────────────────────────────────────
"""

from typing import List, Optional, Deque
from collections import deque

class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right
    def __repr__(self):
        return f"TreeNode({self.val})"

# Build helper
def build_tree(values: list) -> Optional[TreeNode]:
    """Build tree from level-order list (None = missing node)."""
    if not values or values[0] is None:
        return None
    root = TreeNode(values[0])
    queue = deque([root])
    i = 1
    while queue and i < len(values):
        node = queue.popleft()
        if i < len(values) and values[i] is not None:
            node.left = TreeNode(values[i])
            queue.append(node.left)
        i += 1
        if i < len(values) and values[i] is not None:
            node.right = TreeNode(values[i])
            queue.append(node.right)
        i += 1
    return root

# ─────────────────────────────────────────────
# 1. TREE TRAVERSALS
# ─────────────────────────────────────────────
print("=" * 60)
print("1. TREE TRAVERSALS")
print("=" * 60)

"""
TRAVERSAL ORDER:
  In-order   (Left → Root → Right): gives SORTED output for BST
  Pre-order  (Root → Left → Right): used for tree serialization, cloning
  Post-order (Left → Right → Root): used for deletion, calculating sizes
  Level-order (BFS, level by level): shortest path, find closest nodes
"""

root = build_tree([1, 2, 3, 4, 5, 6, 7])

# ── Recursive Traversals ─────────────────────
def inorder_recursive(root: Optional[TreeNode]) -> List[int]:
    """Left → Root → Right."""
    if not root:
        return []
    return inorder_recursive(root.left) + [root.val] + inorder_recursive(root.right)

def preorder_recursive(root: Optional[TreeNode]) -> List[int]:
    """Root → Left → Right."""
    if not root:
        return []
    return [root.val] + preorder_recursive(root.left) + preorder_recursive(root.right)

def postorder_recursive(root: Optional[TreeNode]) -> List[int]:
    """Left → Right → Root."""
    if not root:
        return []
    return postorder_recursive(root.left) + postorder_recursive(root.right) + [root.val]

print(f"In-order:   {inorder_recursive(root)}")    # [4,2,5,1,6,3,7]
print(f"Pre-order:  {preorder_recursive(root)}")   # [1,2,4,5,3,6,7]
print(f"Post-order: {postorder_recursive(root)}")  # [4,5,2,6,7,3,1]

# ── Iterative Traversals ──────────────────────
print("\n--- Iterative Traversals ---")

def inorder_iterative(root: Optional[TreeNode]) -> List[int]:
    """Stack-based in-order traversal."""
    result = []
    stack = []
    curr = root
    while curr or stack:
        while curr:
            stack.append(curr)
            curr = curr.left   # go as far left as possible
        curr = stack.pop()
        result.append(curr.val)
        curr = curr.right      # then go right
    return result

def preorder_iterative(root: Optional[TreeNode]) -> List[int]:
    """Stack-based pre-order traversal."""
    if not root:
        return []
    result = []
    stack = [root]
    while stack:
        node = stack.pop()
        result.append(node.val)
        if node.right: stack.append(node.right)  # right first (LIFO)
        if node.left: stack.append(node.left)
    return result

def postorder_iterative(root: Optional[TreeNode]) -> List[int]:
    """Stack-based post-order traversal (reverse of modified pre-order)."""
    if not root:
        return []
    result = []
    stack = [root]
    while stack:
        node = stack.pop()
        result.append(node.val)
        if node.left: stack.append(node.left)
        if node.right: stack.append(node.right)
    return result[::-1]  # reverse gives post-order

print(f"In-order (iter):   {inorder_iterative(root)}")
print(f"Pre-order (iter):  {preorder_iterative(root)}")
print(f"Post-order (iter): {postorder_iterative(root)}")

# ── Level-Order (BFS) ─────────────────────────
print("\n--- Level-Order Traversal ---")

def level_order(root: Optional[TreeNode]) -> List[List[int]]:
    """BFS using deque. Returns list of levels."""
    if not root:
        return []
    result = []
    queue = deque([root])
    while queue:
        level_size = len(queue)
        level = []
        for _ in range(level_size):
            node = queue.popleft()
            level.append(node.val)
            if node.left: queue.append(node.left)
            if node.right: queue.append(node.right)
        result.append(level)
    return result

print(f"Level-order: {level_order(root)}")  # [[1],[2,3],[4,5,6,7]]

# ─────────────────────────────────────────────
# 2. TREE HEIGHT AND DIAMETER
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("2. HEIGHT AND DIAMETER")
print("=" * 60)

def height(root: Optional[TreeNode]) -> int:
    """Max depth = number of nodes on longest root-to-leaf path."""
    if not root:
        return 0
    return 1 + max(height(root.left), height(root.right))

def diameter(root: Optional[TreeNode]) -> int:
    """
    Diameter = longest path between any two nodes (may not pass through root).
    At each node: left_height + right_height = path through that node.
    Track global maximum.
    """
    max_diameter = [0]
    def dfs(node):
        if not node:
            return 0
        left = dfs(node.left)
        right = dfs(node.right)
        max_diameter[0] = max(max_diameter[0], left + right)
        return 1 + max(left, right)
    dfs(root)
    return max_diameter[0]

print(f"Height of tree: {height(root)}")    # 3
print(f"Diameter of tree: {diameter(root)}") # 4 (longest path 4→2→1→3→7 or similar)

# ─────────────────────────────────────────────
# 3. BST OPERATIONS
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("3. BST OPERATIONS")
print("=" * 60)

def bst_search(root: Optional[TreeNode], target: int) -> Optional[TreeNode]:
    """Search BST in O(log n) avg."""
    if not root or root.val == target:
        return root
    if target < root.val:
        return bst_search(root.left, target)
    return bst_search(root.right, target)

def bst_insert(root: Optional[TreeNode], val: int) -> TreeNode:
    """Insert into BST maintaining BST property."""
    if not root:
        return TreeNode(val)
    if val < root.val:
        root.left = bst_insert(root.left, val)
    elif val > root.val:
        root.right = bst_insert(root.right, val)
    return root  # duplicate — do nothing

def bst_delete(root: Optional[TreeNode], key: int) -> Optional[TreeNode]:
    """
    Delete node from BST. Three cases:
    1. Node has no children: just remove it.
    2. Node has one child: replace with child.
    3. Node has two children: replace with in-order successor (min of right subtree).
    """
    if not root:
        return None
    if key < root.val:
        root.left = bst_delete(root.left, key)
    elif key > root.val:
        root.right = bst_delete(root.right, key)
    else:  # found the node
        if not root.left: return root.right   # case 1 or 2
        if not root.right: return root.left   # case 2
        # case 3: find in-order successor (min of right subtree)
        successor = root.right
        while successor.left:
            successor = successor.left
        root.val = successor.val              # copy successor's value
        root.right = bst_delete(root.right, successor.val)  # delete successor
    return root

# Demo BST operations
bst_root = None
for v in [5, 3, 7, 1, 4, 6, 8]:
    bst_root = bst_insert(bst_root, v)
print(f"BST in-order: {inorder_recursive(bst_root)}")   # [1,3,4,5,6,7,8]
print(f"Search 4: {bst_search(bst_root, 4)}")          # TreeNode(4)
bst_root = bst_delete(bst_root, 3)
print(f"After delete 3: {inorder_recursive(bst_root)}") # [1,4,5,6,7,8]

# ─────────────────────────────────────────────
# 4. DFS vs BFS ON TREES
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("4. DFS vs BFS DECISION GUIDE")
print("=" * 60)

guide = """
USE DFS WHEN:
  ✓ Find a PATH in the tree (root-to-leaf, any path)
  ✓ Problems about depth/height
  ✓ Tree serialization/reconstruction
  ✓ Most tree recursion problems

USE BFS WHEN:
  ✓ Find SHORTEST path
  ✓ Level-order operations (right side view, zigzag, by level)
  ✓ Find closest ancestor
  ✓ Problems mentioning "level" or "distance"

MEMORY:
  DFS: O(h) stack space (h = height)
  BFS: O(w) queue space (w = max width)
  Balanced tree: h ≈ log n, w ≈ n/2 → DFS wins on space!
  Skewed tree: h = n → BFS wins on space
"""
print(guide)

# ─────────────────────────────────────────────
# 5. AVL TREE CONCEPT (Self-Balancing BST)
# ─────────────────────────────────────────────
print("=" * 60)
print("5. AVL TREE — Self-Balancing BST Concept")
print("=" * 60)

avl_explanation = """
AVL Tree properties:
  - BST property maintained
  - Balance factor = height(left) - height(right) ∈ {-1, 0, 1}
  - Re-balancing via rotations after insert/delete

Rotations:
  Left Rotation (RR case): z → y → x becomes y with z-left, x-right
  Right Rotation (LL case): opposite
  Left-Right (LR): left rotate child, then right rotate root
  Right-Left (RL): right rotate child, then left rotate root

Guarantees O(log n) for all operations.

Python doesn't have a built-in AVL tree.
Use sortedcontainers.SortedList for O(log n) operations.
  pip install sortedcontainers
  from sortedcontainers import SortedList
  sl = SortedList([3, 1, 4, 1, 5])
  sl.add(2)      # O(log n)
  sl.discard(3)  # O(log n)
  sl[0]          # O(1) access by index
"""
print(avl_explanation)

# ─────────────────────────────────────────────
# 6. INTERVIEW Q&A
# ─────────────────────────────────────────────
print("=" * 60)
print("INTERVIEW Q&A")
print("=" * 60)

qa = """
Q1: What is the difference between a binary tree and a BST?
A1: Binary tree: at most 2 children, no ordering constraint.
    BST: binary tree WITH ordering (left < root < right).
    Not all binary trees are BSTs. BST enables O(log n) search.

Q2: When does in-order traversal produce sorted output?
A2: Only for a valid BST. In-order (left→root→right) visits nodes
    in ascending key order because of the BST property.

Q3: Why do tree problems often use recursion?
A3: Trees have natural recursive structure — a tree is a root node
    plus two subtrees, each of which is also a tree. Recursive
    solutions directly mirror this self-similar structure.

Q4: How do you find the height of a binary tree?
A4: height(root) = 1 + max(height(left), height(right)), base: height(None) = 0.
    This is O(n) — must visit all nodes.

Q5: What is the difference between height and depth?
A5: Height = distance from node to deepest descendant (measured bottom-up).
    Depth = distance from root to node (measured top-down).
    root.height = tree height. root.depth = 0.

Q6: How do you check if a tree is balanced?
A6: For each node, |height(left) - height(right)| <= 1.
    Must be true for ALL nodes, not just the root.

Q7: What is an in-order successor in a BST?
A7: The next node in sorted order. For node with right subtree:
    leftmost node of right subtree. Without right subtree: walk up
    until you take a left turn (nearest ancestor where you're in left subtree).

Q8: How does LCA (Lowest Common Ancestor) work?
A8: For BST: use values — if both nodes are less than root, go left;
    if both greater, go right; otherwise root is LCA.
    For general binary tree: DFS returning whether each subtree contains
    each target node. LCA is the first node where both targets are found.
"""
print(qa)
