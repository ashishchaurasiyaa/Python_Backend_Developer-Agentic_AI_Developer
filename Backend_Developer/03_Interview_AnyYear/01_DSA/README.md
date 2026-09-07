# 01_DSA — Data Structures & Algorithms

28 topic folders, each with exactly two files:

- `theory.py` — annotated reference implementations, complexity analysis, pattern notes
- `problems.py` — curated problems with solutions and explanation comments

## Start here

| File | What it's for |
|---|---|
| [`00_Coding_Patterns_Index.md`](00_Coding_Patterns_Index.md) | **Read this first.** 33 patterns mapped to their topic folder, each with a "kab use karo" trigger, the trick, and a table of canonical LeetCode problems. |
| [`00_Approach_Flowcharts.md`](00_Approach_Flowcharts.md) | 12 decision trees (two pointers, sliding window, binary search, DP, backtracking, BFS/DFS, etc.) plus a master "which approach?" tree. |
| [`TOP_INTERVIEW_QUESTIONS.md`](TOP_INTERVIEW_QUESTIONS.md) | 90 curated problems (Blind 75 / Grind 75 / Top 150 overlap), topic → approach → difficulty. |
| [`practice/`](practice/) | 🔴 **The actual practice loop.** Write your own solution, `python harness.py <name>` verifies it against real test cases — no peeking at `problems.py` until you're stuck. 35 problems, one per major pattern. |

## Topic folders (01–28)

Arrays/Hashing → Strings → Linked List → Stack/Queue → Binary Search → Two Pointers/Sliding Window → Recursion/Backtracking → Sorting → Trees → Heaps → Graphs (BFS/DFS) → DP → Greedy → Trie → Advanced Graphs → Bit Manipulation → Intervals → Segment Tree/Fenwick → Math/Number Theory → Matrix/Grid → String DP → Monotonic Queue → Game Theory/Randomized → Concurrency → Sparse Table/RMQ → Suffix Structures → Digit DP → Bitmask DP.

Full description of each topic's core concepts: see the topic table in [`../README.md`](../README.md).

## Study order

1. **Week 1–2:** Topics 01–08 — patterns that show up in almost every screen.
2. **Week 3–6:** Topics 09–20 — trees, graphs, DP, greedy (bulk of medium/hard problems).
3. **Week 7–8:** Topics 21–28 — competitive-programming-level, valuable for senior/FAANG-track.
4. **Throughout:** run `practice/` alongside reading — coverage first (Week 1), then correctness, then recall from blank file.

> Not covered yet: LeetCode "Design" problems (LFU Cache, Design HashMap, Design Twitter). LRU currently lives inside `23_Game_Theory_Randomized/` rather than its own folder — worth a dedicated `29_Design_Data_Structures/` if you hit these in an interview loop.
