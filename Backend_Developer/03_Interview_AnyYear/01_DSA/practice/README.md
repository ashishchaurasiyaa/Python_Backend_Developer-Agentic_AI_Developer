# DSA Practice Harness — "padha" se "kiya" tak

> 28 topic folders me **reference solutions** hain (`NN_Topic/problems.py`). Wo padhne ke liye hain. Yeh folder **likhne** ke liye hai — apna solution likho, harness turant batayega sahi hai ya nahi, aur kaunsa case fail hua.

## Quick start

```bash
cd Backend_Developer/03_Interview_AnyYear/01_DSA/practice
python harness.py              # pehli baar: attempts.py auto-ban jaata hai
# attempts.py kholo, kisi ek function ka `pass` hatao, solution likho
python harness.py two_sum      # sirf wahi problem test karo
python harness.py              # sab attempted problems
python harness.py --list       # 28 problems, topic-wise
```

`attempts.py` gitignored hai — tumhari personal working file hai, commit nahi hoti.

## Kya cover hota hai

28 canonical problems, har major pattern se kam se kam ek:

| Pattern | Problems |
|---|---|
| Hashing / Prefix | two_sum, group_anagrams, max_subarray (Kadane) |
| Sliding Window / Two Pointers | longest_unique_substring, container_with_most_water, trapping_rain_water |
| Heap / Top-K | top_k_frequent |
| Binary Search (modified) | search_rotated, find_min_rotated |
| Stack / Monotonic Stack | valid_parentheses, daily_temperatures |
| Intervals | merge_intervals, min_meeting_rooms |
| Linked List | reverse_list_values, has_cycle_at (Floyd) |
| Trees | max_depth, is_valid_bst |
| Graphs | num_islands, can_finish_courses (topo sort) |
| DP | climb_stairs, coin_change, house_robber, longest_common_subsequence |
| Backtracking | subsets, permutations |
| Greedy / Bit | jump_game, single_number, count_bits |

Linked-list aur tree problems me nodes banane ke helpers (`build_list`, `build_tree`) template me pehle se hain — tum sirf algorithm likhte ho, boilerplate nahi.

## The protocol (yehi asli value hai)

```
1. TIMER LAGAO — 20 minutes, ek problem.
2. Pehle approach BOLO (ya likho): "yeh sliding window hai kyunki..."
   Interview me pehle 2 min yehi hote hain. Silent coding = red flag.
3. Code likho. Compile-level galtiyan chalti hain — logic pe focus.
4. `python harness.py <name>` chalao.
   ✅ PASS → complexity comment likho (O(?) time, O(?) space). Agla problem.
   ❌ FAIL → harness exact failing case deta hai. Debug karo, 10 min aur.
5. 30 min total ho gaye aur stuck ho → tab reference kholo:
   ../NN_Topic/problems.py
   Padh ke SAMAJHO, phir file band karo, aur BLANK se dobara likho.
   Jab tak blank se nahi likh sakte, wo problem "done" nahi hai.
6. 3 din baad wahi problem dobara — spaced repetition. Yaad rehna chahiye
   pattern, solution nahi.
```

## Progress tracking

```bash
python harness.py     # niche summary aati hai:
# Attempted 12/28   ✅ 10   ❌ 2   ⬜ not-started 16
```

**Target ladder:**
- **Week 1:** 28/28 attempted (chahe kuch fail ho) — coverage pehle
- **Week 2:** 28/28 passing — correctness
- **Week 3:** har problem blank file se 20 min ke andar — recall
- **Week 4:** [TOP_INTERVIEW_QUESTIONS.md](../TOP_INTERVIEW_QUESTIONS.md) + company-tagged list se aage badho

## Yeh harness kya NAHI hai

Yeh LeetCode ka replacement nahi hai — 28 problems interview ke liye kaafi nahi (~150 chahiye). Yeh **pattern-coverage smoke test** hai: har pattern ka ek representative problem, tez feedback loop ke saath. Patterns solid hone ke baad volume LeetCode/company-tagged list se karo — [2_Month_DSA_5_Problems_Per_Day_WITH_LINKS_AND_COMPANY_TAGS.docx](../2_Month_DSA_5_Problems_Per_Day_WITH_LINKS_AND_COMPANY_TAGS.docx) wahi plan hai.

## Naya problem add karna

`harness.py` me `PROBLEMS` dict me entry daalo:

```python
"my_problem": ("09_Trees", [
    ((arg1, arg2), expected),      # har case: (args_tuple, expected)
    ((other_args,), other_expected),
], None),                          # comparator: None | sorted | _sorted_nested
```

`attempts.py` delete karke dobara `python harness.py` chalao — naya stub aa jayega (purana kaam bach jaye isliye pehle copy rakh lo).

---

**Related:** [Coding Patterns Index](../00_Coding_Patterns_Index.md) · [Top Interview Questions](../TOP_INTERVIEW_QUESTIONS.md) · [System Design drills](../../../02_Year5+_Senior/01_System_Design/PRACTICE_DRILLS.md)
