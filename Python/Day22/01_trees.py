"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DSA — Trees: BFS, DFS, Binary Search Trees, Classic Problems
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from collections import deque, defaultdict, OrderedDict
import heapq


# ═══════════════════════════════════════════════════════════════
# SECTION 1: TREENODE CLASS AND HELPERS
# ═══════════════════════════════════════════════════════════════

class TreeNode:
    """Standard binary tree node used in all LeetCode tree problems."""
    def __init__(self, val: int = 0, left: 'TreeNode' = None, right: 'TreeNode' = None):
        self.val = val
        self.left = left
        self.right = right

    def __repr__(self):
        return f"TreeNode({self.val})"


def build_tree_from_list(values: list) -> TreeNode:
    """
    Build a binary tree from a level-order list (BFS order).
    None represents a missing node.

    Example: [3, 9, 20, None, None, 15, 7]
           3
          / \\
         9  20
           /  \\
          15   7
    """
    if not values or values[0] is None:
        return None

    root = TreeNode(values[0])
    queue = deque([root])
    i = 1

    while queue and i < len(values):
        node = queue.popleft()
        # Left child
        if i < len(values) and values[i] is not None:
            node.left = TreeNode(values[i])
            queue.append(node.left)
        i += 1
        # Right child
        if i < len(values) and values[i] is not None:
            node.right = TreeNode(values[i])
            queue.append(node.right)
        i += 1

    return root


def tree_to_list(root: TreeNode) -> list:
    """Serialize tree to level-order list (BFS), including None for missing nodes."""
    if not root:
        return []
    result = []
    queue = deque([root])
    while queue:
        node = queue.popleft()
        if node:
            result.append(node.val)
            queue.append(node.left)
            queue.append(node.right)
        else:
            result.append(None)
    # Trim trailing Nones
    while result and result[-1] is None:
        result.pop()
    return result


# ═══════════════════════════════════════════════════════════════
# SECTION 2: BFS — LEVEL ORDER TRAVERSAL
# ═══════════════════════════════════════════════════════════════
"""
CONCEPT:
  Use a deque/queue. Process level by level.
  To track levels: snapshot queue size at start of each level.

WHEN TO USE:
  - Level-by-level processing
  - Shortest path in unweighted tree
  - Right/left side view
  - Zigzag traversal
  - Finding nodes at depth k

TEMPLATE:
    from collections import deque
    queue = deque([root])
    while queue:
        level_size = len(queue)
        for _ in range(level_size):
            node = queue.popleft()
            # process node
            if node.left:  queue.append(node.left)
            if node.right: queue.append(node.right)
"""

def level_order_traversal(root: TreeNode) -> list[list[int]]:
    """
    LeetCode 102: Return nodes grouped by level.
    [[3], [9, 20], [15, 7]]
    """
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
            if node.left:
                queue.append(node.left)
            if node.right:
                queue.append(node.right)
        result.append(level)

    return result
# Time: O(n) | Space: O(n) — at most n/2 nodes in queue at leaf level


# ═══════════════════════════════════════════════════════════════
# SECTION 3: DFS — PREORDER / INORDER / POSTORDER
# ═══════════════════════════════════════════════════════════════
"""
TRAVERSAL ORDER:
  Preorder  (Root-Left-Right):  useful for copying/serializing tree
  Inorder   (Left-Root-Right):  gives sorted order for BST
  Postorder (Left-Right-Root):  useful for deletion, bottom-up computation

RECURSIVE TEMPLATE:
    def dfs(node):
        if not node: return
        # preorder: process(node) here
        dfs(node.left)
        # inorder: process(node) here
        dfs(node.right)
        # postorder: process(node) here
"""

# ─── Recursive ────────────────────────────────────────────────
def preorder_recursive(root: TreeNode) -> list[int]:
    result = []
    def dfs(node):
        if not node:
            return
        result.append(node.val)   # Root
        dfs(node.left)             # Left
        dfs(node.right)            # Right
    dfs(root)
    return result

def inorder_recursive(root: TreeNode) -> list[int]:
    result = []
    def dfs(node):
        if not node:
            return
        dfs(node.left)             # Left
        result.append(node.val)   # Root
        dfs(node.right)            # Right
    dfs(root)
    return result

def postorder_recursive(root: TreeNode) -> list[int]:
    result = []
    def dfs(node):
        if not node:
            return
        dfs(node.left)             # Left
        dfs(node.right)            # Right
        result.append(node.val)   # Root
    dfs(root)
    return result
# Time: O(n) | Space: O(h) where h = tree height (O(log n) balanced, O(n) skewed)


# ─── Iterative (using explicit stack) ─────────────────────────
def preorder_iterative(root: TreeNode) -> list[int]:
    if not root:
        return []
    result = []
    stack = [root]
    while stack:
        node = stack.pop()
        result.append(node.val)
        # Push right first so left is processed first
        if node.right:
            stack.append(node.right)
        if node.left:
            stack.append(node.left)
    return result

def inorder_iterative(root: TreeNode) -> list[int]:
    """
    Simulate call stack: go left as far as possible,
    then process node, then go right.
    """
    result = []
    stack = []
    curr = root
    while curr or stack:
        # Go left as far as possible
        while curr:
            stack.append(curr)
            curr = curr.left
        # Process
        curr = stack.pop()
        result.append(curr.val)
        # Move to right subtree
        curr = curr.right
    return result

def postorder_iterative(root: TreeNode) -> list[int]:
    """
    Trick: postorder = reverse of (root, right, left) preorder.
    """
    if not root:
        return []
    result = []
    stack = [root]
    while stack:
        node = stack.pop()
        result.append(node.val)
        if node.left:
            stack.append(node.left)   # push left first (processed after right)
        if node.right:
            stack.append(node.right)
    return result[::-1]  # reverse gives left-right-root
# Time: O(n) | Space: O(h)

# Interview note: Interviewers frequently ask iterative inorder — memorize it.
# It's used in BST problems where you process nodes in sorted order without recursion.


# ═══════════════════════════════════════════════════════════════
# SECTION 4: MAXIMUM DEPTH OF BINARY TREE (LeetCode 104)
# ═══════════════════════════════════════════════════════════════
"""
PROBLEM:
  Return the maximum depth (number of nodes on longest root-to-leaf path).

APPROACHES:
  1. Recursive DFS: depth = 1 + max(left_depth, right_depth)
  2. BFS: count levels
  3. Iterative DFS with stack: track (node, depth) pairs
"""

def max_depth_recursive(root: TreeNode) -> int:
    if not root:
        return 0
    return 1 + max(max_depth_recursive(root.left), max_depth_recursive(root.right))
# Time: O(n) | Space: O(h)

def max_depth_bfs(root: TreeNode) -> int:
    if not root:
        return 0
    depth = 0
    queue = deque([root])
    while queue:
        depth += 1
        for _ in range(len(queue)):
            node = queue.popleft()
            if node.left:
                queue.append(node.left)
            if node.right:
                queue.append(node.right)
    return depth
# Time: O(n) | Space: O(n)


# ═══════════════════════════════════════════════════════════════
# SECTION 5: VALIDATE BINARY SEARCH TREE (LeetCode 98)
# ═══════════════════════════════════════════════════════════════
"""
PROBLEM:
  Determine if a binary tree is a valid BST.
  BST property: left subtree < node < right subtree (all descendants, not just children).

APPROACH 1 — Range validation (recommended):
  Pass valid range [min_val, max_val] down. Node must be strictly within range.

APPROACH 2 — Inorder traversal:
  Inorder of valid BST is strictly increasing. Check prev < current.

COMMON MISTAKE:
  Only checking parent-child relationship is WRONG.
  E.g., [5,4,6,None,None,3,7] — node 3 is in right subtree of 5 but < 5.
"""

def is_valid_bst(root: TreeNode) -> bool:
    """Range validation approach."""
    def validate(node, min_val, max_val):
        if not node:
            return True
        if not (min_val < node.val < max_val):
            return False
        return (validate(node.left, min_val, node.val) and
                validate(node.right, node.val, max_val))

    return validate(root, float('-inf'), float('inf'))
# Time: O(n) | Space: O(h)

def is_valid_bst_inorder(root: TreeNode) -> bool:
    """Inorder traversal — values must be strictly increasing."""
    prev = [float('-inf')]  # use list to allow mutation in nested function

    def inorder(node):
        if not node:
            return True
        if not inorder(node.left):
            return False
        if node.val <= prev[0]:
            return False
        prev[0] = node.val
        return inorder(node.right)

    return inorder(root)
# Time: O(n) | Space: O(h)


# ═══════════════════════════════════════════════════════════════
# SECTION 6: LOWEST COMMON ANCESTOR (LeetCode 236 / 235)
# ═══════════════════════════════════════════════════════════════
"""
PROBLEM (LeetCode 236 — General Binary Tree):
  Given root and two nodes p and q, find their lowest common ancestor.
  LCA is the deepest node that has both p and q as descendants.
  A node is a descendant of itself.

APPROACH:
  Recursive DFS. At each node:
  - If node is None, p, or q: return node
  - Recurse left and right
  - If both sides return non-None: current node is LCA
  - If only one side: that side contains both p and q (one is ancestor of other)
"""

def lowest_common_ancestor(root: TreeNode, p: TreeNode, q: TreeNode) -> TreeNode:
    if not root or root is p or root is q:
        return root

    left = lowest_common_ancestor(root.left, p, q)
    right = lowest_common_ancestor(root.right, p, q)

    if left and right:
        return root   # p and q are in different subtrees
    return left if left else right  # both in same subtree
# Time: O(n) | Space: O(h)

# LCA in BST (LeetCode 235) — can use BST property for O(h) with O(1) extra space:
def lca_bst(root: TreeNode, p: TreeNode, q: TreeNode) -> TreeNode:
    """For BST: navigate toward p and q based on value comparisons."""
    curr = root
    while curr:
        if p.val < curr.val and q.val < curr.val:
            curr = curr.left   # both in left subtree
        elif p.val > curr.val and q.val > curr.val:
            curr = curr.right  # both in right subtree
        else:
            return curr        # split point is LCA
    return None
# Time: O(h) | Space: O(1)


# ═══════════════════════════════════════════════════════════════
# SECTION 7: BINARY TREE RIGHT SIDE VIEW (LeetCode 199)
# ═══════════════════════════════════════════════════════════════
"""
PROBLEM:
  Return values of nodes visible when looking at the tree from the right side.
  (Rightmost node at each level.)

APPROACH 1 — BFS: last node at each level.
APPROACH 2 — DFS: track depth, record first node visited at each new depth
             using right-first DFS (root, right, left).
"""

def right_side_view(root: TreeNode) -> list[int]:
    """BFS approach — last node at each level."""
    if not root:
        return []
    result = []
    queue = deque([root])
    while queue:
        level_size = len(queue)
        for i in range(level_size):
            node = queue.popleft()
            if i == level_size - 1:
                result.append(node.val)  # rightmost node at this level
            if node.left:
                queue.append(node.left)
            if node.right:
                queue.append(node.right)
    return result
# Time: O(n) | Space: O(n)

def right_side_view_dfs(root: TreeNode) -> list[int]:
    """DFS approach — traverse right subtree first."""
    result = []
    def dfs(node, depth):
        if not node:
            return
        if depth == len(result):
            result.append(node.val)   # first node at this depth (rightmost)
        dfs(node.right, depth + 1)    # right first
        dfs(node.left, depth + 1)
    dfs(root, 0)
    return result
# Time: O(n) | Space: O(h)


# ═══════════════════════════════════════════════════════════════
# SECTION 8: SERIALIZE / DESERIALIZE BINARY TREE (LeetCode 297)
# ═══════════════════════════════════════════════════════════════
"""
PROBLEM:
  Implement serialization (tree → string) and deserialization (string → tree).
  No constraints on format — design your own.

APPROACH — Preorder DFS with None markers:
  Serialize: preorder traversal, "null" for None nodes, comma separator.
  Deserialize: reconstruct using a queue of tokens, recursively rebuild.

WHY PREORDER?
  Root value comes first — we know what the root is immediately on deserialization.
  Inorder alone is ambiguous without structure markers.
"""

class Codec:
    def serialize(self, root: TreeNode) -> str:
        """Encode tree as comma-separated preorder string."""
        tokens = []

        def dfs(node):
            if not node:
                tokens.append("null")
                return
            tokens.append(str(node.val))
            dfs(node.left)
            dfs(node.right)

        dfs(root)
        return ",".join(tokens)

    def deserialize(self, data: str) -> TreeNode:
        """Decode preorder string back to tree."""
        tokens = deque(data.split(","))

        def build():
            token = tokens.popleft()
            if token == "null":
                return None
            node = TreeNode(int(token))
            node.left = build()
            node.right = build()
            return node

        return build()
# serialize: O(n) | deserialize: O(n) | Space: O(n)

# Interview note: BFS-based serialization (like LeetCode's own format) is also valid.
# Preorder DFS is cleaner to implement in an interview.


# ═══════════════════════════════════════════════════════════════
# SECTION 9: KTH SMALLEST ELEMENT IN BST (LeetCode 230)
# ═══════════════════════════════════════════════════════════════
"""
PROBLEM:
  Given the root of a BST and integer k, return the kth smallest value.

APPROACH 1 — Inorder traversal (sorted order): stop at kth element.
APPROACH 2 — Augmented BST: store subtree sizes (optimal for repeated queries).

KEY INSIGHT:
  Inorder traversal of BST yields values in ascending sorted order.
  The kth element visited is the kth smallest.
"""

def kth_smallest(root: TreeNode, k: int) -> int:
    """Iterative inorder traversal — stop early at kth element."""
    stack = []
    curr = root
    count = 0

    while curr or stack:
        while curr:
            stack.append(curr)
            curr = curr.left
        curr = stack.pop()
        count += 1
        if count == k:
            return curr.val
        curr = curr.right

    return -1  # k > number of nodes (invalid input)
# Time: O(h + k) | Space: O(h)

def kth_smallest_recursive(root: TreeNode, k: int) -> int:
    """Recursive inorder with early termination."""
    result = [None]
    count = [0]

    def inorder(node):
        if not node or result[0] is not None:
            return
        inorder(node.left)
        count[0] += 1
        if count[0] == k:
            result[0] = node.val
            return
        inorder(node.right)

    inorder(root)
    return result[0]
# Time: O(h + k) | Space: O(h)


# ═══════════════════════════════════════════════════════════════
# SECTION 10: PATH SUM II (LeetCode 113)
# ═══════════════════════════════════════════════════════════════
"""
PROBLEM:
  Find all root-to-leaf paths where the path sum equals targetSum.
  Return a list of all such paths (each path is a list of node values).

APPROACH:
  DFS with backtracking. Track current path and remaining sum.
  When leaf reached and remaining == 0, add copy of current path to result.
  Backtrack by removing last element after returning from recursion.
"""

def path_sum(root: TreeNode, target_sum: int) -> list[list[int]]:
    result = []

    def dfs(node, remaining, path):
        if not node:
            return
        path.append(node.val)
        remaining -= node.val

        # Leaf node check
        if not node.left and not node.right and remaining == 0:
            result.append(list(path))  # copy current path

        dfs(node.left, remaining, path)
        dfs(node.right, remaining, path)
        path.pop()  # backtrack

    dfs(root, target_sum, [])
    return result
# Time: O(n²) worst case — O(n) nodes, O(n) to copy path at each leaf
# Space: O(h) for recursion stack + O(n) for result

# Variation — Path Sum I (just check if any path exists):
def has_path_sum(root: TreeNode, target_sum: int) -> bool:
    if not root:
        return False
    if not root.left and not root.right:
        return root.val == target_sum
    return (has_path_sum(root.left, target_sum - root.val) or
            has_path_sum(root.right, target_sum - root.val))
# Time: O(n) | Space: O(h)

# Variation — Path Sum III (any path, not just root-to-leaf, using prefix sums):
def path_sum_iii(root: TreeNode, target_sum: int) -> int:
    """Count paths (any start/end) summing to targetSum. LeetCode 437."""
    prefix_count = defaultdict(int)
    prefix_count[0] = 1

    def dfs(node, curr_sum):
        if not node:
            return 0
        curr_sum += node.val
        count = prefix_count[curr_sum - target_sum]
        prefix_count[curr_sum] += 1
        count += dfs(node.left, curr_sum)
        count += dfs(node.right, curr_sum)
        prefix_count[curr_sum] -= 1  # backtrack
        return count

    return dfs(root, 0)
# Time: O(n) | Space: O(n)


# ═══════════════════════════════════════════════════════════════
# QUICK REFERENCE SUMMARY
# ═══════════════════════════════════════════════════════════════
"""
TRAVERSAL         | ORDER          | KEY USE CASE
──────────────────┼────────────────┼──────────────────────────────
BFS (level order) | Level by level | Shortest path, right-side view
Preorder (DFS)    | Root-L-R       | Serialization, copy tree
Inorder (DFS)     | L-Root-R       | BST sorted order, kth smallest
Postorder (DFS)   | L-R-Root       | Deletion, height computation

PROBLEM                  | TECHNIQUE                    | TIME    | SPACE
─────────────────────────┼──────────────────────────────┼─────────┼──────
Max Depth                | Recursive DFS / BFS          | O(n)    | O(h)
Validate BST             | Range validation / inorder   | O(n)    | O(h)
Lowest Common Ancestor   | Recursive DFS                | O(n)    | O(h)
Level Order Traversal    | BFS with deque               | O(n)    | O(n)
Right Side View          | BFS last-in-level / DFS      | O(n)    | O(n)
Serialize/Deserialize    | Preorder DFS + null markers  | O(n)    | O(n)
Kth Smallest in BST      | Iterative inorder            | O(h+k)  | O(h)
Path Sum II              | DFS + backtracking           | O(n²)   | O(h)

KEY BST PROPERTIES:
  - Inorder gives sorted sequence
  - Search/insert/delete: O(log n) balanced, O(n) skewed
  - LCA can use value comparisons (O(h) vs O(n) for general tree)
"""


# ═══════════════════════════════════════════════════════════════
# TESTS — run this file to verify all solutions
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    # ── Build tree helper ──
    root = build_tree_from_list([3, 9, 20, None, None, 15, 7])
    assert tree_to_list(root) == [3, 9, 20, None, None, 15, 7]
    print("build_tree_from_list: OK")

    # ── Level Order Traversal ──
    assert level_order_traversal(root) == [[3], [9, 20], [15, 7]]
    assert level_order_traversal(None) == []
    assert level_order_traversal(build_tree_from_list([1])) == [[1]]
    print("level_order_traversal: OK")

    # ── DFS Traversals ──
    t = build_tree_from_list([1, 2, 3, 4, 5])
    # Tree:     1
    #          / \
    #         2   3
    #        / \
    #       4   5
    assert preorder_recursive(t) == [1, 2, 4, 5, 3]
    assert inorder_recursive(t) == [4, 2, 5, 1, 3]
    assert postorder_recursive(t) == [4, 5, 2, 3, 1]
    assert preorder_iterative(t) == [1, 2, 4, 5, 3]
    assert inorder_iterative(t) == [4, 2, 5, 1, 3]
    assert postorder_iterative(t) == [4, 5, 2, 3, 1]
    print("DFS traversals (recursive + iterative): OK")

    # ── Max Depth ──
    assert max_depth_recursive(root) == 3
    assert max_depth_recursive(None) == 0
    assert max_depth_bfs(root) == 3
    assert max_depth_bfs(build_tree_from_list([1, 2])) == 2
    print("max_depth: OK")

    # ── Validate BST ──
    valid_bst = build_tree_from_list([5, 3, 7, 2, 4, 6, 8])
    invalid_bst = build_tree_from_list([5, 1, 4, None, None, 3, 6])
    edge_case = build_tree_from_list([5, 4, 6, None, None, 3, 7])  # tricky!
    assert is_valid_bst(valid_bst) == True
    assert is_valid_bst(invalid_bst) == False
    assert is_valid_bst(edge_case) == False  # 3 is in right subtree but < 5
    assert is_valid_bst_inorder(valid_bst) == True
    assert is_valid_bst_inorder(invalid_bst) == False
    print("is_valid_bst: OK")

    # ── Lowest Common Ancestor ──
    lca_tree = build_tree_from_list([3, 5, 1, 6, 2, 0, 8, None, None, 7, 4])
    # Find nodes by value for testing
    def find_node(root, val):
        if not root:
            return None
        if root.val == val:
            return root
        return find_node(root.left, val) or find_node(root.right, val)

    p = find_node(lca_tree, 5)
    q = find_node(lca_tree, 1)
    assert lowest_common_ancestor(lca_tree, p, q).val == 3

    p = find_node(lca_tree, 5)
    q = find_node(lca_tree, 4)
    assert lowest_common_ancestor(lca_tree, p, q).val == 5
    print("lowest_common_ancestor: OK")

    # ── Right Side View ──
    rsv_tree = build_tree_from_list([1, 2, 3, None, 5, None, 4])
    assert right_side_view(rsv_tree) == [1, 3, 4]
    assert right_side_view_dfs(rsv_tree) == [1, 3, 4]
    assert right_side_view(None) == []
    print("right_side_view: OK")

    # ── Serialize / Deserialize ──
    codec = Codec()
    original = build_tree_from_list([1, 2, 3, None, None, 4, 5])
    serialized = codec.serialize(original)
    deserialized = codec.deserialize(serialized)
    assert codec.serialize(deserialized) == serialized
    assert codec.serialize(codec.deserialize("null")) == "null"
    print("serialize/deserialize: OK")

    # ── Kth Smallest in BST ──
    bst = build_tree_from_list([5, 3, 7, 2, 4, 6, 8])
    # Inorder: [2, 3, 4, 5, 6, 7, 8]
    assert kth_smallest(bst, 1) == 2
    assert kth_smallest(bst, 3) == 4
    assert kth_smallest(bst, 7) == 8
    assert kth_smallest_recursive(bst, 3) == 4
    print("kth_smallest: OK")

    # ── Path Sum II ──
    ps_tree = build_tree_from_list([5, 4, 8, 11, None, 13, 4, 7, 2, None, None, 5, 1])
    paths = path_sum(ps_tree, 22)
    assert sorted(paths) == sorted([[5, 4, 11, 2], [5, 8, 4, 5]])
    assert path_sum(None, 0) == []
    print("path_sum: OK")

    # ── Path Sum III ──
    ps3_tree = build_tree_from_list([10, 5, -3, 3, 2, None, 11, 3, -2, None, 1])
    assert path_sum_iii(ps3_tree, 8) == 3
    print("path_sum_iii: OK")

    print("\nAll tests passed!")
