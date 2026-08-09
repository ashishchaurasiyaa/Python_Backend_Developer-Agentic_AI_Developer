# 🧩 Coding Patterns — Master Practice Index

> **Pattern-wise revision lens** over the 28 topic folders. Interview me topic se zyada **pattern pehchanna** matter karta hai — "yeh sliding window hai" ya "yeh top-K hai" — phir solution flow a`automatic aa jaata hai.
>
> **Yeh original compilation hai** — har pattern ke liye maine **standard canonical problems** (LeetCode #, jo har DSA resource me common hain) chune hain + apni 1-line technique. Kisi paid course ka content copy nahi.
>
> **Use kaise karo:** pattern padho → "Kab" + "Trick" ratto → us pattern ke 5-8 problems solve karo (easy→hard) → apne topic folder (`NN_.../problems.py`) me likho.

**Difficulty:** 🟢 Easy · 🟡 Medium · 🔴 Hard

---

## ⚡ Pattern → Topic Quick Map

| Pattern | Topic folder |
|---|---|
| Two Pointers · Sliding Window | `06_Two_Pointers_Sliding_Window` |
| Fast & Slow Pointers · In-place LL Reversal | `03_Linked_List` |
| Stack · Monotonic Stack | `04_Stack_Queue` |
| Monotonic Queue | `22_Monotonic_Queue` |
| Hashing · Prefix Sum · Counting | `01_Arrays_Hashing` |
| Merge Intervals | `17_Intervals` |
| Cyclic Sort · Linear Sorting | `08_Sorting_Algorithms` |
| Modified Binary Search | `05_Binary_Search` |
| Tree BFS/DFS · Level Order | `09_Trees` |
| Graphs · Island/Matrix | `11_Graphs_BFS_DFS` · `20_Matrix_Grid` |
| Two Heaps · Top-K · K-way Merge | `10_Heaps_Priority_Queue` |
| Subsets · Backtracking | `07_Recursion_Backtracking` |
| Bitwise XOR | `16_Bit_Manipulation` |
| Knapsack · Fibonacci DP | `12_Dynamic_Programming` |
| Palindromic / String DP | `21_String_DP` |
| Topological Sort · Union Find · Bridges | `15_Advanced_Graphs` |
| Trie | `14_Trie` |
| Segment Tree · Fenwick (BIT) · Ordered Set | `18_Segment_Tree_Fenwick` |
| Sparse Table / RMQ | `25_Sparse_Table_RMQ` |
| Multi-threaded | `24_Concurrency_Threading` |
| Math · Digit DP · Bitmask DP · Game Theory · Suffix | `19`,`27`,`28`,`23`,`26` |

---

# A. LINEAR — Arrays / Strings / Linked List

## 1. Two Pointers → `06`
**Kab:** sorted array, pair/triplet, palindrome, partition.
**Trick:** do pointers (ends se ya same direction), condition pe move karo — O(n²)→O(n).

| Problem | LC# | Diff |
|---|---|---|
| Two Sum II (sorted) | 167 | 🟢 |
| Valid Palindrome | 125 | 🟢 |
| 3Sum | 15 | 🟡 |
| Container With Most Water | 11 | 🟡 |
| Sort Colors (Dutch flag) | 75 | 🟡 |
| 4Sum | 18 | 🟡 |
| Trapping Rain Water | 42 | 🔴 |

## 2. Sliding Window → `06`
**Kab:** contiguous subarray/substring — "longest/shortest/max window with condition".
**Trick:** `right` se window badhao; condition toote toh `left` se shrink karo.

| Problem | LC# | Diff |
|---|---|---|
| Longest Substring Without Repeating | 3 | 🟡 |
| Max Sum Subarray of Size K (Kadane base) | 53 | 🟡 |
| Longest Substring with At Most K Distinct | 340 | 🟡 |
| Longest Repeating Char Replacement | 424 | 🟡 |
| Permutation in String | 567 | 🟡 |
| Subarray Product Less Than K | 713 | 🟡 |
| Minimum Window Substring | 76 | 🔴 |

## 3. Fast & Slow Pointers → `03`
**Kab:** cycle detect, middle node, "linked list / number sequence".
**Trick:** slow +1, fast +2 — milein toh cycle.

| Problem | LC# | Diff |
|---|---|---|
| Linked List Cycle | 141 | 🟢 |
| Middle of the Linked List | 876 | 🟢 |
| Happy Number | 202 | 🟢 |
| Linked List Cycle II (start) | 142 | 🟡 |
| Palindrome Linked List | 234 | 🟢 |
| Find the Duplicate Number | 287 | 🟡 |

## 4. In-place Reversal of Linked List → `03`
**Kab:** reverse whole/sub-list/k-group without extra space.
**Trick:** `prev, curr, next` teen pointers ghumao.

| Problem | LC# | Diff |
|---|---|---|
| Reverse Linked List | 206 | 🟢 |
| Swap Nodes in Pairs | 24 | 🟡 |
| Reverse Linked List II | 92 | 🟡 |
| Rotate List | 61 | 🟡 |
| Reverse Nodes in k-Group | 25 | 🔴 |

## 5. Hashing · Prefix Sum · Counting → `01`
**Kab:** O(1) lookup, "subarray sum = k", frequency.
**Trick:** prefix-sum + hashmap se subarray range O(n) me.

| Problem | LC# | Diff |
|---|---|---|
| Two Sum | 1 | 🟢 |
| Group Anagrams | 49 | 🟡 |
| Top K Frequent Elements | 347 | 🟡 |
| Product of Array Except Self | 238 | 🟡 |
| Subarray Sum Equals K | 560 | 🟡 |
| Contiguous Array | 525 | 🟡 |
| Longest Consecutive Sequence | 128 | 🟡 |

## 6. Merge Intervals → `17`
**Kab:** overlapping intervals, meetings, ranges.
**Trick:** start pe sort karo; phir overlap merge/count.

| Problem | LC# | Diff |
|---|---|---|
| Merge Intervals | 56 | 🟡 |
| Insert Interval | 57 | 🟡 |
| Interval List Intersections | 986 | 🟡 |
| Non-overlapping Intervals | 435 | 🟡 |
| Meeting Rooms II | 253 | 🟡 |
| Employee Free Time | 759 | 🔴 |

## 7. Cyclic Sort → `08`
**Kab:** array me 1..n range ke numbers, "missing/duplicate find".
**Trick:** har number ko apni index `nums[i]==i+1` pe swap karo.

| Problem | LC# | Diff | Code kahan hai |
|---|---|---|---|
| Missing Number | 268 | 🟢 | *(khud likho — 2 min ka hai: XOR ya sum-formula, ya cyclic sort)* |
| Find All Numbers Disappeared | 448 | 🟢 | `08_Sorting_Algorithms/problems.py` (P13) |
| Set Mismatch | 645 | 🟢 | `08_Sorting_Algorithms/problems.py` (P12) |
| Find All Duplicates | 442 | 🟡 | `01_Arrays_Hashing/problems.py` (P12 — index-sign trick) |
| First Missing Positive | 41 | 🔴 | `08_Sorting_Algorithms/problems.py` (P11) |

> 🧪 **Khud likh ke check karo:** `cd practice && python harness.py first_missing_positive`

## 8. Stack & Monotonic Stack → `04`
**Kab:** matching/nesting; "next greater/smaller element".
**Trick:** monotonic stack me element push karte hue chhote/bade pop karo → next-greater O(n).

| Problem | LC# | Diff |
|---|---|---|
| Valid Parentheses | 20 | 🟢 |
| Min Stack | 155 | 🟡 |
| Evaluate Reverse Polish Notation | 150 | 🟡 |
| Daily Temperatures | 739 | 🟡 |
| Next Greater Element II | 503 | 🟡 |
| Remove K Digits | 402 | 🟡 |
| Largest Rectangle in Histogram | 84 | 🔴 |

## 9. Monotonic Queue → `22`
**Kab:** sliding window me max/min, deque-based.
**Trick:** deque me decreasing rakho; front = window max.

| Problem | LC# | Diff |
|---|---|---|
| Sliding Window Maximum | 239 | 🔴 |
| Longest Subarray Abs Diff ≤ Limit | 1438 | 🟡 |
| Shortest Subarray with Sum ≥ K | 862 | 🔴 |
| Jump Game VI | 1696 | 🟡 |
| Constrained Subsequence Sum | 1425 | 🔴 |

---

# B. TREES & GRAPHS

## 10. Tree BFS / Level Order → `09`
**Kab:** level-by-level, "right view", "zigzag", min-depth.
**Trick:** queue; har level ka size pre-capture karo.

| Problem | LC# | Diff |
|---|---|---|
| Binary Tree Level Order Traversal | 102 | 🟡 |
| Zigzag Level Order | 103 | 🟡 |
| Binary Tree Right Side View | 199 | 🟡 |
| Average of Levels | 637 | 🟢 |
| Minimum Depth of Binary Tree | 111 | 🟢 |
| Populating Next Right Pointers | 116 | 🟡 |

## 11. Tree DFS → `09`
**Kab:** root-to-leaf paths, path-sum, diameter, LCA.
**Trick:** recursion; subtree result return karke combine karo.

| Problem | LC# | Diff |
|---|---|---|
| Path Sum | 112 | 🟢 |
| Path Sum II | 113 | 🟡 |
| Diameter of Binary Tree | 543 | 🟢 |
| Lowest Common Ancestor | 236 | 🟡 |
| Validate Binary Search Tree | 98 | 🟡 |
| Path Sum III | 437 | 🟡 |
| Binary Tree Maximum Path Sum | 124 | 🔴 |

## 12. Graphs (BFS/DFS) → `11`
**Kab:** connectivity, shortest unweighted path, cycle.
**Trick:** visited set; BFS = shortest hops, DFS = explore deep.

| Problem | LC# | Diff |
|---|---|---|
| Find if Path Exists in Graph | 1971 | 🟢 |
| Number of Provinces | 547 | 🟡 |
| Clone Graph | 133 | 🟡 |
| Rotting Oranges | 994 | 🟡 |
| Course Schedule | 207 | 🟡 |
| Word Ladder | 127 | 🔴 |

## 13. Island / Matrix Traversal → `20`
**Kab:** 2D grid, connected regions, flood fill.
**Trick:** har cell se DFS/BFS, visited mark; 4/8 directions.

| Problem | LC# | Diff |
|---|---|---|
| Flood Fill | 733 | 🟢 |
| Number of Islands | 200 | 🟡 |
| Max Area of Island | 695 | 🟡 |
| Surrounded Regions | 130 | 🟡 |
| Walls and Gates | 286 | 🟡 |
| Number of Closed Islands | 1254 | 🟡 |

## 14. Topological Sort → `15`
**Kab:** dependencies/ordering, DAG, "course schedule".
**Trick:** in-degree 0 wale queue me; Kahn's algorithm.

| Problem | LC# | Diff |
|---|---|---|
| Course Schedule | 207 | 🟡 |
| Course Schedule II | 210 | 🟡 |
| Minimum Height Trees | 310 | 🟡 |
| Alien Dictionary | 269 | 🔴 |
| Parallel Courses | 1136 | 🟡 |

## 15. Union Find (DSU) → `15`
**Kab:** dynamic connectivity, "groups merge", cycle in undirected.
**Trick:** parent[] + path compression + union by rank → ~O(α).

| Problem | LC# | Diff |
|---|---|---|
| Number of Provinces | 547 | 🟡 |
| Redundant Connection | 684 | 🟡 |
| Is Graph Bipartite? | 785 | 🟡 |
| Accounts Merge | 721 | 🟡 |
| Graph Valid Tree | 261 | 🟡 |
| Number of Islands II | 305 | 🔴 |

---

# C. HEAPS

## 16. Top 'K' Elements → `10`
**Kab:** "K largest/smallest/frequent".
**Trick:** size-K heap maintain karo → O(n log k).

| Problem | LC# | Diff |
|---|---|---|
| Kth Largest Element in Array | 215 | 🟡 |
| Top K Frequent Elements | 347 | 🟡 |
| K Closest Points to Origin | 973 | 🟡 |
| Sort Characters by Frequency | 451 | 🟡 |
| Task Scheduler | 621 | 🟡 |
| Reorganize String | 767 | 🟡 |

## 17. Two Heaps → `10`
**Kab:** running median, "balance two halves".
**Trick:** max-heap (lower half) + min-heap (upper half), balanced.

| Problem | LC# | Diff |
|---|---|---|
| Find Median from Data Stream | 295 | 🔴 |
| IPO (Maximize Capital) | 502 | 🔴 |
| Find Right Interval | 436 | 🟡 |
| Sliding Window Median | 480 | 🔴 |

## 18. K-way Merge → `10`
**Kab:** K sorted lists/arrays merge, "smallest range".
**Trick:** min-heap me har list ka head; pop+push.

| Problem | LC# | Diff |
|---|---|---|
| Merge k Sorted Lists | 23 | 🔴 |
| Kth Smallest in Sorted Matrix | 378 | 🟡 |
| Find K Pairs with Smallest Sums | 373 | 🟡 |
| Smallest Range Covering K Lists | 632 | 🔴 |

---

# D. RECURSION / SEARCH

## 19. Subsets (BFS combinatorics) → `07`
**Kab:** all subsets/permutations/combinations.
**Trick:** har element ke liye "include/exclude" → 2^n.

| Problem | LC# | Diff |
|---|---|---|
| Subsets | 78 | 🟡 |
| Subsets II (dups) | 90 | 🟡 |
| Permutations | 46 | 🟡 |
| Combinations | 77 | 🟡 |
| Letter Combinations of Phone | 17 | 🟡 |
| Generate Parentheses | 22 | 🟡 |

## 20. Backtracking → `07`
**Kab:** constraint satisfaction — "place/choose, fail → undo".
**Trick:** choose → recurse → un-choose (backtrack).

| Problem | LC# | Diff |
|---|---|---|
| Combination Sum | 39 | 🟡 |
| Word Search | 79 | 🟡 |
| Palindrome Partitioning | 131 | 🟡 |
| Restore IP Addresses | 93 | 🟡 |
| N-Queens | 51 | 🔴 |
| Sudoku Solver | 37 | 🔴 |

## 21. Modified Binary Search → `05`
**Kab:** sorted/rotated/answer-space — "find boundary/min/peak".
**Trick:** har step me aadha space kaato; condition se direction.

| Problem | LC# | Diff |
|---|---|---|
| Binary Search | 704 | 🟢 |
| Find First and Last Position | 34 | 🟡 |
| Search in Rotated Sorted Array | 33 | 🟡 |
| Find Minimum in Rotated Sorted | 153 | 🟡 |
| Find Peak Element | 162 | 🟡 |
| Koko Eating Bananas (answer BS) | 875 | 🟡 |

## 22. Bitwise XOR → `16`
**Kab:** "single number", toggling, sets via bits.
**Trick:** `a^a=0`, `a^0=a` → duplicates cancel.

| Problem | LC# | Diff |
|---|---|---|
| Single Number | 136 | 🟢 |
| Missing Number | 268 | 🟢 |
| Counting Bits | 338 | 🟢 |
| Single Number II | 137 | 🟡 |
| Single Number III | 260 | 🟡 |
| Maximum XOR of Two Numbers | 421 | 🟡 |

---

# E. DYNAMIC PROGRAMMING

## 23. 0/1 Knapsack → `12`
**Kab:** pick/skip with capacity, subset-sum family.
**Trick:** `dp[i][w]` = best using first i items, capacity w.

| Problem | LC# | Diff |
|---|---|---|
| Partition Equal Subset Sum | 416 | 🟡 |
| Target Sum | 494 | 🟡 |
| Coin Change | 322 | 🟡 |
| Coin Change II | 518 | 🟡 |
| Ones and Zeroes | 474 | 🟡 |
| Last Stone Weight II | 1049 | 🟡 |

## 24. Fibonacci / Linear DP → `12`
**Kab:** "har step pe choices", climbing, robber.
**Trick:** `dp[i]` = `dp[i-1]`/`dp[i-2]` ka combination.

| Problem | LC# | Diff |
|---|---|---|
| Climbing Stairs | 70 | 🟢 |
| House Robber | 198 | 🟡 |
| House Robber II | 213 | 🟡 |
| Decode Ways | 91 | 🟡 |
| Jump Game | 55 | 🟡 |
| Jump Game II | 45 | 🟡 |

## 25. Palindromic / String DP → `21`
**Kab:** two-string/substring DP — palindrome, LCS, edit distance.
**Trick:** `dp[i][j]` = i..j ya prefix-prefix relation.

| Problem | LC# | Diff |
|---|---|---|
| Longest Palindromic Substring | 5 | 🟡 |
| Longest Palindromic Subsequence | 516 | 🟡 |
| Palindromic Substrings | 647 | 🟡 |
| Longest Common Subsequence | 1143 | 🟡 |
| Edit Distance | 72 | 🔴 |
| Min Insertion Steps to Palindrome | 1312 | 🔴 |

## 26. Greedy → `13`
**Kab:** local-optimal → global-optimal provable.
**Trick:** sort/heap se sabse acchi choice pehle.

| Problem | LC# | Diff |
|---|---|---|
| Jump Game | 55 | 🟡 |
| Gas Station | 134 | 🟡 |
| Partition Labels | 763 | 🟡 |
| Hand of Straights | 846 | 🟡 |
| Valid Parenthesis String | 678 | 🟡 |
| Merge Triplets to Form Target | 1899 | 🟡 |

---

# F. ADVANCED STRUCTURES

## 27. Trie (Prefix Tree) → `14`
**Kab:** prefix search, autocomplete, word dictionary.
**Trick:** har node = 26 children + is_end flag.

| Problem | LC# | Diff |
|---|---|---|
| Implement Trie | 208 | 🟡 |
| Design Add and Search Words | 211 | 🟡 |
| Replace Words | 648 | 🟡 |
| Search Suggestions System | 1268 | 🟡 |
| Word Search II | 212 | 🔴 |

## 28. Segment Tree · Fenwick (BIT) · Ordered Set → `18`
**Kab:** range query + point/range update, "count smaller after self".
**Trick:** Segment tree = range agg; BIT = prefix sums with updates; Ordered set (SortedList) = log-n insert + rank.

| Problem | LC# | Diff |
|---|---|---|
| Range Sum Query - Mutable | 307 | 🟡 |
| My Calendar I (ordered set) | 729 | 🟡 |
| 132 Pattern (ordered set) | 456 | 🟡 |
| Count of Smaller Numbers After Self | 315 | 🔴 |
| Count of Range Sum | 327 | 🔴 |

## 29. Sparse Table / RMQ → `25`
**Kab:** **static** array, repeated range-min/max/GCD queries O(1).
**Trick:** precompute `2^j`-length blocks; overlap-friendly idempotent ops.

| Problem / Drill | Note |
|---|---|
| Range Minimum Query (static) | classic build O(n log n), query O(1) |
| LCA via Euler tour + RMQ | tree LCA reduction |
| Range GCD queries | idempotent → sparse table fits |

## 30. Multi-threaded → `24`
**Kab:** concurrency interview rounds (locks, semaphores, ordering).
**Trick:** condition variables / semaphores se ordering enforce.

| Problem | LC# | Diff |
|---|---|---|
| Print in Order | 1114 | 🟢 |
| Print FooBar Alternately | 1115 | 🟡 |
| Building H2O | 1117 | 🟡 |
| Fizz Buzz Multithreaded | 1195 | 🟡 |
| Web Crawler Multithreaded | 1242 | 🟡 |

---

# G. NICHE PATTERNS (Grokking me named, tere folders me subsumed)

## 31. Meet in the Middle → `28_Bitmask_DP`
**Kab:** N≈40 (2^N bahut bada, 2^(N/2) theek). Do halves ka result combine.

| Problem | LC# | Diff |
|---|---|---|
| Partition to K Equal Sum Subsets | 698 | 🟡 |
| Closest Subsequence Sum | 1755 | 🔴 |

## 32. Articulation Points & Bridges → `15_Advanced_Graphs`
**Kab:** critical nodes/edges jinke hatne se graph tut jaaye.
**Trick:** DFS discovery + low-link times (Tarjan).

| Problem | LC# | Diff |
|---|---|---|
| Critical Connections in a Network | 1192 | 🔴 |

## 33. Serialize / Deserialize · Clone → `09`/`11`
**Kab:** tree/graph ko string me <-> wapas; deep copy.

| Problem | LC# | Diff |
|---|---|---|
| Clone Graph | 133 | 🟡 |
| Copy List with Random Pointer | 138 | 🟡 |
| Encode and Decode Strings | 271 | 🟡 |
| Serialize and Deserialize Binary Tree | 297 | 🔴 |

---

# H. EXTRAS (tere folders me hai, Grokking me nahi)

| Topic | Folder | Sample problems (LC#) |
|---|---|---|
| Math / Number Theory | `19` | Pow(x,n) 50 · Sqrt 69 · Count Primes 204 · Happy Number 202 |
| Digit DP | `27` | Count Numbers Unique Digits 357 · Non-neg Ints w/o Consec Ones 600 · Numbers At Most N Given Digit Set 902 |
| Bitmask DP | `28` | Beautiful Arrangement 526 · Shortest Path Visiting All Nodes 847 · Partition to K Equal Sum 698 |
| Game Theory | `23` | Nim Game 292 · Stone Game 877 · Predict the Winner 486 · Can I Win 464 |
| Suffix Structures | `26` | Longest Duplicate Substring 1044 · Longest Common Prefix 14 |

---

## 🎯 Suggested order (interview prep)
1. **Week 1:** Patterns 1-9 (linear) — sabse zyada poocha jaata hai.
2. **Week 2:** 10-18 (trees, graphs, heaps).
3. **Week 3:** 19-26 (recursion, binary search, DP).
4. **Week 4:** 27-33 + extras (advanced + niche).

> Har pattern: pehle 1 easy solve karke template banao, phir medium/hard. Solution apne `NN_topic/problems.py` me likho — yeh index sirf **kya solve karna hai** batata hai, code tu khud likhega. 💪
