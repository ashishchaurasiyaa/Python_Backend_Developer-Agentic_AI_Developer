# Top Interview Questions — 90 Curated Problems

> Source: Top Interview 150 + Blind 75 + Grind 75 overlap
> Organized by topic → approach → difficulty
> Each topic maps to the folder in this directory

---

## Study Order (Recommended)

| Week | Topics |
|------|--------|
| 1–2  | Arrays & Hashing, Two Pointers, Sliding Window |
| 3–4  | Stack, Binary Search, Linked List |
| 5–6  | Trees, Graphs |
| 7–8  | Dynamic Programming, Backtracking |
| 9+   | Heap, Trie, Intervals, Bit Manipulation |

---

## 01. Arrays & Hashing → `01_Arrays_Hashing/`
**Approach:** HashMap / HashSet / Counting / Prefix-Suffix

| # | Problem | Difficulty | Pattern |
|---|---------|------------|---------|
| LC 217 | Contains Duplicate | Easy | HashSet |
| LC 242 | Valid Anagram | Easy | Counting |
| LC 1   | Two Sum | Easy | HashMap |
| LC 49  | Group Anagrams | Medium | HashMap |
| LC 347 | Top K Frequent Elements | Medium | Bucket Sort |
| LC 238 | Product of Array Except Self | Medium | Prefix/Suffix |
| LC 128 | Longest Consecutive Sequence | Medium | HashSet |

---

## 02. Two Pointers → `06_Two_Pointers_Sliding_Window/`
**Approach:** L/R pointers shrinking toward each other

| # | Problem | Difficulty | Pattern |
|---|---------|------------|---------|
| LC 125 | Valid Palindrome | Easy | 2ptr |
| LC 167 | Two Sum II (sorted input) | Medium | 2ptr |
| LC 15  | 3Sum | Medium | Sort + 2ptr |
| LC 11  | Container With Most Water | Medium | Greedy 2ptr |
| LC 42  | Trapping Rain Water | Hard | 2ptr / Mono Stack |

---

## 03. Sliding Window → `06_Two_Pointers_Sliding_Window/`
**Approach:** Expand right pointer, shrink left when condition breaks

| # | Problem | Difficulty | Pattern |
|---|---------|------------|---------|
| LC 121 | Best Time to Buy & Sell Stock | Easy | Sliding Window |
| LC 3   | Longest Substring Without Repeating | Medium | Variable Window |
| LC 424 | Longest Repeating Char Replacement | Medium | Variable Window |
| LC 567 | Permutation in String | Medium | Fixed Window |
| LC 76  | Minimum Window Substring | Hard | Variable Window |

---

## 04. Stack → `04_Stack_Queue/`
**Approach:** Monotonic stack for next-greater problems; stack for bracket matching

| # | Problem | Difficulty | Pattern |
|---|---------|------------|---------|
| LC 20  | Valid Parentheses | Easy | Stack |
| LC 155 | Min Stack | Medium | Aux Stack |
| LC 150 | Evaluate Reverse Polish Notation | Medium | Stack |
| LC 739 | Daily Temperatures | Medium | Mono Stack |
| LC 853 | Car Fleet | Medium | Mono Stack |
| LC 84  | Largest Rectangle in Histogram | Hard | Mono Stack |

---

## 05. Binary Search → `05_Binary_Search/`
**Approach:** Left/right boundary; search on answer space

| # | Problem | Difficulty | Pattern |
|---|---------|------------|---------|
| LC 704 | Binary Search | Easy | Classic |
| LC 74  | Search a 2D Matrix | Medium | Flatten to 1D |
| LC 875 | Koko Eating Bananas | Medium | Search on Answer |
| LC 153 | Find Min in Rotated Sorted Array | Medium | Rotated |
| LC 33  | Search in Rotated Sorted Array | Medium | Rotated |
| LC 4   | Median of Two Sorted Arrays | Hard | Partition |

---

## 06. Linked List → `03_Linked_List/`
**Approach:** Dummy node; fast/slow pointers; find-mid then reverse

| # | Problem | Difficulty | Pattern |
|---|---------|------------|---------|
| LC 206 | Reverse Linked List | Easy | Iterative / Recursive |
| LC 21  | Merge Two Sorted Lists | Easy | Dummy node |
| LC 141 | Linked List Cycle | Easy | Fast/Slow |
| LC 19  | Remove Nth Node From End | Medium | Two pointers |
| LC 143 | Reorder List | Medium | Mid + Reverse + Merge |
| LC 23  | Merge K Sorted Lists | Hard | Heap / Divide & Conquer |

---

## 07. Trees → `09_Trees/`
**Approach:** DFS (pre/in/post-order); BFS level-order; BST properties

| # | Problem | Difficulty | Pattern |
|---|---------|------------|---------|
| LC 226 | Invert Binary Tree | Easy | DFS |
| LC 104 | Max Depth of Binary Tree | Easy | DFS |
| LC 100 | Same Tree | Easy | DFS |
| LC 572 | Subtree of Another Tree | Easy | DFS |
| LC 235 | LCA of BST | Medium | BST property |
| LC 102 | Binary Tree Level Order Traversal | Medium | BFS |
| LC 105 | Construct from Preorder + Inorder | Medium | Recursion |
| LC 98  | Validate BST | Medium | DFS with bounds |
| LC 230 | Kth Smallest in BST | Medium | Inorder |
| LC 124 | Binary Tree Max Path Sum | Hard | DFS + global max |
| LC 297 | Serialize / Deserialize Binary Tree | Hard | BFS or DFS |

---

## 08. Graphs → `11_Graphs_BFS_DFS/`
**Approach:** BFS / DFS; Union-Find; Topological Sort (Kahn's or DFS)

| # | Problem | Difficulty | Pattern |
|---|---------|------------|---------|
| LC 200 | Number of Islands | Medium | DFS/BFS |
| LC 133 | Clone Graph | Medium | DFS + HashMap |
| LC 695 | Max Area of Island | Medium | DFS |
| LC 417 | Pacific Atlantic Water Flow | Medium | Reverse BFS |
| LC 130 | Surrounded Regions | Medium | BFS from border |
| LC 207 | Course Schedule | Medium | Topo Sort (cycle detect) |
| LC 210 | Course Schedule II | Medium | Topo Sort (Kahn's) |
| LC 684 | Redundant Connection | Medium | Union-Find |
| LC 127 | Word Ladder | Hard | BFS |
| LC 269 | Alien Dictionary | Hard | Topo Sort |

---

## 09. Dynamic Programming → `12_Dynamic_Programming/`
**Approach:** 1D DP → 2D DP → Interval DP → Knapsack variants

| # | Problem | Difficulty | Pattern |
|---|---------|------------|---------|
| LC 70  | Climbing Stairs | Easy | 1D DP (Fib) |
| LC 198 | House Robber | Medium | 1D DP |
| LC 213 | House Robber II | Medium | 1D DP (circular) |
| LC 5   | Longest Palindromic Substring | Medium | Expand around center |
| LC 322 | Coin Change | Medium | Unbounded Knapsack |
| LC 139 | Word Break | Medium | 1D DP |
| LC 300 | Longest Increasing Subsequence | Medium | DP / Patience Sort |
| LC 416 | Partition Equal Subset Sum | Medium | 0/1 Knapsack |
| LC 1143| Longest Common Subsequence | Medium | 2D DP |
| LC 72  | Edit Distance | Medium | 2D DP |
| LC 152 | Maximum Product Subarray | Medium | DP (min/max) |
| LC 91  | Decode Ways | Medium | 1D DP |
| LC 312 | Burst Balloons | Hard | Interval DP |

---

## 10. Heap / Priority Queue → `10_Heaps_Priority_Queue/`
**Approach:** Min-heap for top-K; two heaps for median

| # | Problem | Difficulty | Pattern |
|---|---------|------------|---------|
| LC 703 | Kth Largest in Stream | Easy | Min-Heap |
| LC 215 | Kth Largest Element in Array | Medium | Min-Heap |
| LC 621 | Task Scheduler | Medium | Max-Heap / Greedy |
| LC 355 | Design Twitter | Medium | Heap + HashMap |
| LC 295 | Find Median from Data Stream | Hard | Two Heaps |

---

## 11. Tries → `14_Trie/`
**Approach:** Build prefix tree; DFS for wildcard search

| # | Problem | Difficulty | Pattern |
|---|---------|------------|---------|
| LC 208 | Implement Trie | Medium | Trie build |
| LC 211 | Design Add and Search Words | Medium | Trie + DFS wildcard |
| LC 212 | Word Search II | Hard | Trie + Backtracking |

---

## 12. Backtracking → `07_Recursion_Backtracking/`
**Approach:** Choose → Explore → Unchoose (state tree pruning)

| # | Problem | Difficulty | Pattern |
|---|---------|------------|---------|
| LC 78  | Subsets | Medium | Backtrack |
| LC 90  | Subsets II (with duplicates) | Medium | Backtrack + skip |
| LC 46  | Permutations | Medium | Backtrack |
| LC 39  | Combination Sum | Medium | Backtrack |
| LC 40  | Combination Sum II | Medium | Backtrack + skip |
| LC 131 | Palindrome Partitioning | Medium | Backtrack |
| LC 79  | Word Search | Medium | DFS + Backtrack |
| LC 51  | N-Queens | Hard | Backtrack |

---

## 13. Intervals → `17_Intervals/`
**Approach:** Sort by start time; sweep line; greedy

| # | Problem | Difficulty | Pattern |
|---|---------|------------|---------|
| LC 252 | Meeting Rooms | Easy | Sort |
| LC 57  | Insert Interval | Medium | Scan + Merge |
| LC 56  | Merge Intervals | Medium | Sort + Merge |
| LC 435 | Non-Overlapping Intervals | Medium | Greedy |
| LC 253 | Meeting Rooms II | Medium | Min-Heap / Sweep |

---

## 14. Bit Manipulation → `16_Bit_Manipulation/`
**Approach:** XOR tricks; bit masking; Brian Kernighan's algorithm

| # | Problem | Difficulty | Pattern |
|---|---------|------------|---------|
| LC 136 | Single Number | Easy | XOR |
| LC 191 | Number of 1 Bits | Easy | Bit mask |
| LC 190 | Reverse Bits | Easy | Bit shift |
| LC 268 | Missing Number | Easy | XOR / Gauss sum |
| LC 338 | Counting Bits | Easy | DP + bits |
| LC 371 | Sum of Two Integers (no + op) | Medium | Bit addition |

---

## Summary

| Topic | Easy | Medium | Hard | Total |
|-------|------|--------|------|-------|
| Arrays & Hashing | 3 | 4 | 0 | 7 |
| Two Pointers | 1 | 3 | 1 | 5 |
| Sliding Window | 1 | 3 | 1 | 5 |
| Stack | 1 | 4 | 1 | 6 |
| Binary Search | 1 | 4 | 1 | 6 |
| Linked List | 3 | 2 | 1 | 6 |
| Trees | 3 | 6 | 2 | 11 |
| Graphs | 0 | 8 | 2 | 10 |
| Dynamic Programming | 1 | 11 | 1 | 13 |
| Heap | 1 | 3 | 1 | 5 |
| Tries | 0 | 2 | 1 | 3 |
| Backtracking | 0 | 7 | 1 | 8 |
| Intervals | 1 | 4 | 0 | 5 |
| Bit Manipulation | 4 | 2 | 0 | 6 |
| **Total** | **20** | **63** | **12** | **95** |

---

## Sufficiency Verdict

These 95 questions cover every pattern that appears in real interviews.
Doing them well (not just getting AC) is enough for any product company interview.

> Rule: One question solved 3 different ways > 3 questions solved once.
