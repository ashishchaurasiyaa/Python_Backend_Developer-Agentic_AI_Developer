"""
╔══════════════════════════════════════════════════════════════════╗
║              TREES — 15 LeetCode-Style Problems                  ║
╚══════════════════════════════════════════════════════════════════╝
"""

from typing import List, Optional
from collections import deque

class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right

def build_tree_bfs(values: list) -> Optional[TreeNode]:
    if not values or values[0] is None:
        return None
    root = TreeNode(values[0])
    queue = deque([root])
    i = 1
    while queue and i < len(values):
        node = queue.popleft()
        if i < len(values) and values[i] is not None:
            node.left = TreeNode(values[i]); queue.append(node.left)
        i += 1
        if i < len(values) and values[i] is not None:
            node.right = TreeNode(values[i]); queue.append(node.right)
        i += 1
    return root

def tree_to_list(root: Optional[TreeNode]) -> list:
    if not root: return []
    result, queue = [], deque([root])
    while queue:
        node = queue.popleft()
        if node:
            result.append(node.val)
            queue.append(node.left)
            queue.append(node.right)
        else:
            result.append(None)
    while result and result[-1] is None:
        result.pop()
    return result

# ══════════════════════════════════════════════════════════════════
# Problem 1: Invert Binary Tree (LC 226)
# ══════════════════════════════════════════════════════════════════
def invertTree(root: Optional[TreeNode]) -> Optional[TreeNode]:
    """
    Invert (mirror) a binary tree.

    Approach: Swap left and right children at every node recursively.

    Example: [4,2,7,1,3,6,9] → [4,7,2,9,6,3,1]
    """
    if not root:
        return None
    root.left, root.right = invertTree(root.right), invertTree(root.left)
    return root

print("=== Invert Binary Tree ===")
root = build_tree_bfs([4,2,7,1,3,6,9])
print(tree_to_list(invertTree(root)))  # [4,7,2,9,6,3,1]
# Time: O(n) | Space: O(h)

# ══════════════════════════════════════════════════════════════════
# Problem 2: Maximum Depth of Binary Tree (LC 104)
# ══════════════════════════════════════════════════════════════════
def maxDepth(root: Optional[TreeNode]) -> int:
    """
    Find the maximum depth (number of nodes on the longest root-to-leaf path).

    Example: [3,9,20,None,None,15,7] → 3
    """
    if not root:
        return 0
    return 1 + max(maxDepth(root.left), maxDepth(root.right))

print("\n=== Maximum Depth of Binary Tree ===")
root = build_tree_bfs([3,9,20,None,None,15,7])
print(maxDepth(root))  # 3
# Time: O(n) | Space: O(h)

# ══════════════════════════════════════════════════════════════════
# Problem 3: Diameter of Binary Tree (LC 543)
# ══════════════════════════════════════════════════════════════════
def diameterOfBinaryTree(root: Optional[TreeNode]) -> int:
    """
    Find the length of the longest path between any two nodes.
    (doesn't have to pass through root)

    Approach: At each node, diameter through it = left_height + right_height.
    Track global max.

    Example: [1,2,3,4,5] → 3 (path: 4-2-1-3 or 5-2-1-3)
    """
    self_max = [0]
    def dfs(node):
        if not node: return 0
        left = dfs(node.left)
        right = dfs(node.right)
        self_max[0] = max(self_max[0], left + right)
        return 1 + max(left, right)
    dfs(root)
    return self_max[0]

print("\n=== Diameter of Binary Tree ===")
root = build_tree_bfs([1,2,3,4,5])
print(diameterOfBinaryTree(root))  # 3
# Time: O(n) | Space: O(h)

# ══════════════════════════════════════════════════════════════════
# Problem 4: Balanced Binary Tree (LC 110)
# ══════════════════════════════════════════════════════════════════
def isBalanced(root: Optional[TreeNode]) -> bool:
    """
    Determine if tree is height-balanced (every node's left and right
    subtrees differ in height by at most 1).

    Approach: Return -1 as sentinel for "unbalanced". If either subtree
    returns -1, propagate up.

    Example: [3,9,20,None,None,15,7] → True
             [1,2,2,3,3,None,None,4,4] → False
    """
    def check(node):
        if not node: return 0
        left = check(node.left)
        if left == -1: return -1
        right = check(node.right)
        if right == -1: return -1
        if abs(left - right) > 1: return -1
        return 1 + max(left, right)
    return check(root) != -1

print("\n=== Balanced Binary Tree ===")
print(isBalanced(build_tree_bfs([3,9,20,None,None,15,7])))  # True
print(isBalanced(build_tree_bfs([1,2,2,3,3,None,None,4,4])))  # False
# Time: O(n) | Space: O(h)

# ══════════════════════════════════════════════════════════════════
# Problem 5: Same Tree (LC 100)
# ══════════════════════════════════════════════════════════════════
def isSameTree(p: Optional[TreeNode], q: Optional[TreeNode]) -> bool:
    """
    Check if two binary trees are identical (same structure and values).

    Example: [1,2,3] vs [1,2,3] → True
             [1,2] vs [1,None,2] → False
    """
    if not p and not q: return True
    if not p or not q: return False
    if p.val != q.val: return False
    return isSameTree(p.left, q.left) and isSameTree(p.right, q.right)

print("\n=== Same Tree ===")
p = build_tree_bfs([1,2,3]); q = build_tree_bfs([1,2,3])
print(isSameTree(p, q))  # True
p = build_tree_bfs([1,2]); q = build_tree_bfs([1,None,2])
print(isSameTree(p, q))  # False
# Time: O(n) | Space: O(h)

# ══════════════════════════════════════════════════════════════════
# Problem 6: Subtree of Another Tree (LC 572)
# ══════════════════════════════════════════════════════════════════
def isSubtree(root: Optional[TreeNode], subRoot: Optional[TreeNode]) -> bool:
    """
    Check if subRoot is a subtree of root (same structure and values).

    Approach: At each node of root, check if same tree as subRoot.

    Example: root=[3,4,5,1,2], subRoot=[4,1,2] → True
             root=[3,4,5,1,2,None,None,None,None,0], subRoot=[4,1,2] → False
    """
    if not root: return False
    if isSameTree(root, subRoot): return True
    return isSubtree(root.left, subRoot) or isSubtree(root.right, subRoot)

print("\n=== Subtree of Another Tree ===")
root = build_tree_bfs([3,4,5,1,2])
sub = build_tree_bfs([4,1,2])
print(isSubtree(root, sub))  # True
# Time: O(m*n) | Space: O(h)

# ══════════════════════════════════════════════════════════════════
# Problem 7: Lowest Common Ancestor of BST (LC 235)
# ══════════════════════════════════════════════════════════════════
def lowestCommonAncestorBST(root: TreeNode, p: TreeNode, q: TreeNode) -> TreeNode:
    """
    Find the LCA of nodes p and q in a BST.

    Approach: Use BST property.
    - If both p,q < root → LCA in left subtree
    - If both p,q > root → LCA in right subtree
    - Otherwise → root is LCA

    Example: root=[6,2,8,0,4,7,9,None,None,3,5], p=2, q=8 → 6
             p=2, q=4 → 2
    """
    while root:
        if p.val < root.val and q.val < root.val:
            root = root.left
        elif p.val > root.val and q.val > root.val:
            root = root.right
        else:
            return root
    return root

print("\n=== Lowest Common Ancestor of BST ===")
root = build_tree_bfs([6,2,8,0,4,7,9,None,None,3,5])
p = TreeNode(2); q = TreeNode(8)
print(lowestCommonAncestorBST(root, p, q).val)  # 6
p = TreeNode(2); q = TreeNode(4)
print(lowestCommonAncestorBST(root, p, q).val)  # 2
# Time: O(h) | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 8: Binary Tree Level Order Traversal (LC 102)
# ══════════════════════════════════════════════════════════════════
def levelOrder(root: Optional[TreeNode]) -> List[List[int]]:
    """
    Return level-order traversal as list of lists.

    Approach: BFS with deque. Process one level at a time.

    Example: [3,9,20,None,None,15,7] → [[3],[9,20],[15,7]]
    """
    if not root: return []
    result = []
    queue = deque([root])
    while queue:
        level = []
        for _ in range(len(queue)):
            node = queue.popleft()
            level.append(node.val)
            if node.left: queue.append(node.left)
            if node.right: queue.append(node.right)
        result.append(level)
    return result

print("\n=== Level Order Traversal ===")
root = build_tree_bfs([3,9,20,None,None,15,7])
print(levelOrder(root))  # [[3],[9,20],[15,7]]
# Time: O(n) | Space: O(w)

# ══════════════════════════════════════════════════════════════════
# Problem 9: Binary Tree Right Side View (LC 199)
# ══════════════════════════════════════════════════════════════════
def rightSideView(root: Optional[TreeNode]) -> List[int]:
    """
    Return the values visible from the right side of the tree.
    = last node of each level.

    Example: [1,2,3,None,5,None,4] → [1,3,4]
    """
    if not root: return []
    result = []
    queue = deque([root])
    while queue:
        for i in range(len(queue)):
            node = queue.popleft()
            if i == len(queue):  # last of this level (after popleft, queue shrunk)
                result.append(node.val)
            if node.left: queue.append(node.left)
            if node.right: queue.append(node.right)
        result.append(node.val)  # node is last in level after the loop
    # Fix: re-implement cleanly
    return result

def rightSideViewClean(root: Optional[TreeNode]) -> List[int]:
    """Clean version: just take the last element of each BFS level."""
    if not root: return []
    result = []
    queue = deque([root])
    while queue:
        level_size = len(queue)
        for i in range(level_size):
            node = queue.popleft()
            if i == level_size - 1:
                result.append(node.val)
            if node.left: queue.append(node.left)
            if node.right: queue.append(node.right)
    return result

print("\n=== Binary Tree Right Side View ===")
root = build_tree_bfs([1,2,3,None,5,None,4])
print(rightSideViewClean(root))  # [1,3,4]
# Time: O(n) | Space: O(w)

# ══════════════════════════════════════════════════════════════════
# Problem 10: Validate BST (LC 98)
# ══════════════════════════════════════════════════════════════════
def isValidBST(root: Optional[TreeNode]) -> bool:
    """
    Validate that a binary tree is a valid BST.

    Approach: Pass down min and max bounds. Each node must be
    strictly within (min, max).

    Example: [2,1,3] → True
             [5,1,4,None,None,3,6] → False (root 5 > right child 4)
    """
    def validate(node, lo, hi):
        if not node: return True
        if not (lo < node.val < hi): return False
        return validate(node.left, lo, node.val) and validate(node.right, node.val, hi)
    return validate(root, float('-inf'), float('inf'))

print("\n=== Validate BST ===")
print(isValidBST(build_tree_bfs([2,1,3])))          # True
print(isValidBST(build_tree_bfs([5,1,4,None,None,3,6])))  # False
# Time: O(n) | Space: O(h)

# ══════════════════════════════════════════════════════════════════
# Problem 11: Kth Smallest Element in BST (LC 230)
# ══════════════════════════════════════════════════════════════════
def kthSmallest(root: Optional[TreeNode], k: int) -> int:
    """
    Find the kth smallest element in a BST.

    Approach: In-order traversal gives sorted order. Stop at kth element.
    Use iterative for early stopping.

    Example: [3,1,4,None,2], k=1 → 1
             [5,3,6,2,4,None,None,1], k=3 → 3
    """
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
    return -1

print("\n=== Kth Smallest in BST ===")
root = build_tree_bfs([3,1,4,None,2])
print(kthSmallest(root, 1))  # 1
root = build_tree_bfs([5,3,6,2,4,None,None,1])
print(kthSmallest(root, 3))  # 3
# Time: O(h+k) | Space: O(h)

# ══════════════════════════════════════════════════════════════════
# Problem 12: Construct Tree from Preorder + Inorder (LC 105)
# ══════════════════════════════════════════════════════════════════
def buildTreeFromTraversals(preorder: List[int], inorder: List[int]) -> Optional[TreeNode]:
    """
    Reconstruct binary tree from preorder and inorder traversals.

    Approach: preorder[0] is always the root.
    Find root in inorder → elements to its left are in left subtree.
    Recurse on left and right halves.

    Example: preorder=[3,9,20,15,7], inorder=[9,3,15,20,7] → [3,9,20,None,None,15,7]
    """
    if not preorder or not inorder:
        return None
    root_val = preorder[0]
    root = TreeNode(root_val)
    mid = inorder.index(root_val)  # O(n) lookup; use hashmap for O(1)
    root.left = buildTreeFromTraversals(preorder[1:mid+1], inorder[:mid])
    root.right = buildTreeFromTraversals(preorder[mid+1:], inorder[mid+1:])
    return root

print("\n=== Construct Tree from Preorder + Inorder ===")
root = buildTreeFromTraversals([3,9,20,15,7], [9,3,15,20,7])
print(tree_to_list(root))  # [3,9,20,None,None,15,7]
# Time: O(n²) naive; O(n) with hashmap | Space: O(n)

# ══════════════════════════════════════════════════════════════════
# Problem 13: Binary Tree Maximum Path Sum (LC 124)
# ══════════════════════════════════════════════════════════════════
def maxPathSum(root: Optional[TreeNode]) -> int:
    """
    Find the maximum path sum in a binary tree. Path can start and end
    at any node. Path does not need to go through root.

    Approach: At each node, max gain = max(0, left_gain, right_gain) + node.val.
    Update global max with left_gain + right_gain + node.val.

    Example: [-10,9,20,None,None,15,7] → 42 (path: 15→20→7)
             [1,2,3] → 6
    """
    max_sum = [float('-inf')]
    def dfs(node):
        if not node: return 0
        left = max(dfs(node.left), 0)   # ignore negative paths
        right = max(dfs(node.right), 0)
        max_sum[0] = max(max_sum[0], left + right + node.val)
        return node.val + max(left, right)  # can only choose one direction to extend
    dfs(root)
    return max_sum[0]

print("\n=== Binary Tree Maximum Path Sum ===")
root = build_tree_bfs([-10,9,20,None,None,15,7])
print(maxPathSum(root))  # 42
root = build_tree_bfs([1,2,3])
print(maxPathSum(root))  # 6
# Time: O(n) | Space: O(h)

# ══════════════════════════════════════════════════════════════════
# Problem 14: Serialize and Deserialize Binary Tree (LC 297)
# ══════════════════════════════════════════════════════════════════
class Codec:
    """
    Serialize a binary tree to a string and deserialize back.

    Approach: Pre-order DFS. Use 'N' for null nodes.
    Serialize: preorder, join with ','.
    Deserialize: split by ',', use index pointer to reconstruct.

    Example: [1,2,3,None,None,4,5] → "1,2,N,N,3,4,N,N,5,N,N" → tree
    """
    def serialize(self, root: Optional[TreeNode]) -> str:
        result = []
        def dfs(node):
            if not node:
                result.append('N')
                return
            result.append(str(node.val))
            dfs(node.left)
            dfs(node.right)
        dfs(root)
        return ','.join(result)

    def deserialize(self, data: str) -> Optional[TreeNode]:
        vals = iter(data.split(','))
        def dfs():
            val = next(vals)
            if val == 'N':
                return None
            node = TreeNode(int(val))
            node.left = dfs()
            node.right = dfs()
            return node
        return dfs()

print("\n=== Serialize and Deserialize Binary Tree ===")
codec = Codec()
root = build_tree_bfs([1,2,3,None,None,4,5])
s = codec.serialize(root)
print(f"Serialized: {s}")
root2 = codec.deserialize(s)
print(f"Deserialized: {tree_to_list(root2)}")  # [1,2,3,None,None,4,5]
# Time: O(n) | Space: O(n)

# ══════════════════════════════════════════════════════════════════
# Problem 15: Count Good Nodes in Binary Tree (LC 1448)
# ══════════════════════════════════════════════════════════════════
def goodNodes(root: TreeNode) -> int:
    """
    A node X is "good" if in the path from root to X there are no nodes
    with a greater value than X.

    Approach: DFS tracking the max value seen on the path so far.
    If current node >= max_so_far, it's good.

    Example: [3,1,4,3,None,1,5] → 4
             [3,3,None,4,2] → 3
    """
    def dfs(node, max_so_far):
        if not node: return 0
        is_good = 1 if node.val >= max_so_far else 0
        new_max = max(max_so_far, node.val)
        return is_good + dfs(node.left, new_max) + dfs(node.right, new_max)
    return dfs(root, float('-inf'))

print("\n=== Count Good Nodes in Binary Tree ===")
root = build_tree_bfs([3,1,4,3,None,1,5])
print(goodNodes(root))  # 4
root = build_tree_bfs([3,3,None,4,2])
print(goodNodes(root))  # 3
# Time: O(n) | Space: O(h)

print("\n✓ All 15 Tree problems solved!")
