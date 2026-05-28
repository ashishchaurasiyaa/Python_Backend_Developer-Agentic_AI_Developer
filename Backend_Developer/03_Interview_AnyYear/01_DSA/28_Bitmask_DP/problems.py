"""
============================================================
BITMASK DP — INTERVIEW PROBLEMS
============================================================

Problems covered:
  1. Traveling Salesman (TSP) — both min cost cycle and path
  2. Minimum Cost to Connect Two Groups (LC 1595)
  3. Maximum Score Words Formed by Letters (LC 1255)
  4. Smallest Sufficient Team (LC 1125)
  5. Find Maximum Compatibility Score Sum (LC 1947)
  6. Number of Ways to Reach a Position (LC variants)
  7. Distribute Repeating Integers (LC 1655)
  8. Maximum Students Taking Exam (LC 1349) — grid + bitmask
  9. Beautiful Arrangement (LC 526)
"""
from functools import lru_cache
from typing import List


# ============================================================
# Problem 1a: TSP Min Cost Cycle (Hamiltonian Cycle)
# ============================================================
def tsp_cycle(dist):
    n = len(dist)
    INF = float("inf")

    @lru_cache(maxsize=None)
    def dp(mask, last):
        if mask == (1 << n) - 1:
            return dist[last][0]   # return to start
        best = INF
        for nxt in range(n):
            if not (mask & (1 << nxt)):
                best = min(best, dist[last][nxt] + dp(mask | (1 << nxt), nxt))
        return best

    return dp(1, 0)   # start at city 0


# ============================================================
# Problem 1b: TSP Path (no return)
# ============================================================
def tsp_path(dist):
    n = len(dist)
    INF = float("inf")

    @lru_cache(maxsize=None)
    def dp(mask, last):
        if mask == (1 << n) - 1:
            return 0
        best = INF
        for nxt in range(n):
            if not (mask & (1 << nxt)):
                best = min(best, dist[last][nxt] + dp(mask | (1 << nxt), nxt))
        return best

    return min(dp(1 << start, start) for start in range(n))


# ============================================================
# Problem 2: Minimum Cost to Connect Two Groups (LC 1595)
# ============================================================
def connect_two_groups(cost: List[List[int]]) -> int:
    """size1 ≤ size2. Each point in group1 connects to ≥1 point in group2 (and vice versa).
    State: process points of group1 in order, mask = which group2 covered."""
    size1 = len(cost)
    size2 = len(cost[0])
    # Min cost per group2 point (precompute)
    min_g2 = [min(cost[i][j] for i in range(size1)) for j in range(size2)]

    @lru_cache(maxsize=None)
    def dp(i, mask):
        if i == size1:
            # Cover remaining uncovered group2 points
            total = 0
            for j in range(size2):
                if not (mask & (1 << j)):
                    total += min_g2[j]
            return total
        best = float("inf")
        for j in range(size2):
            best = min(best, cost[i][j] + dp(i + 1, mask | (1 << j)))
        return best

    return dp(0, 0)


# ============================================================
# Problem 3: Maximum Score Words Formed by Letters (LC 1255)
# ============================================================
def max_score_words(words, letters, scores):
    """Choose subset of words maximizing score, using each letter at most once."""
    from collections import Counter
    n = len(words)
    avail = Counter(letters)

    def word_score(word):
        return sum(scores[ord(c) - ord('a')] for c in word)

    def can_form(word, used):
        new_used = used.copy()
        for c in word:
            new_used[c] += 1
            if new_used[c] > avail[c]:
                return None
        return new_used

    # Try all subsets via bitmask
    best = 0
    for mask in range(1 << n):
        used = Counter()
        score = 0
        valid = True
        for i in range(n):
            if mask & (1 << i):
                new_used = can_form(words[i], used)
                if new_used is None:
                    valid = False
                    break
                used = new_used
                score += word_score(words[i])
        if valid:
            best = max(best, score)
    return best


# ============================================================
# Problem 4: Smallest Sufficient Team (LC 1125)
# ============================================================
def smallest_sufficient_team(req_skills, people):
    n_skills = len(req_skills)
    skill_idx = {s: i for i, s in enumerate(req_skills)}
    full = (1 << n_skills) - 1

    # Each person's skill bitmask
    person_mask = []
    for skills in people:
        m = 0
        for s in skills:
            if s in skill_idx:
                m |= (1 << skill_idx[s])
        person_mask.append(m)

    @lru_cache(maxsize=None)
    def dp(covered):
        if covered == full:
            return []
        best = None
        for i, pm in enumerate(person_mask):
            if pm & ~covered:  # adds new
                team = dp(covered | pm) + [i]
                if best is None or len(team) < len(best):
                    best = team
        return best

    return dp(0)


# ============================================================
# Problem 5: Find Maximum Compatibility Score Sum (LC 1947)
# Match students to mentors maximizing total compatibility
# ============================================================
def max_compatibility_sum(students, mentors):
    m = len(students)

    def score(s, ment):
        return sum(1 for a, b in zip(s, ment) if a == b)

    score_table = [[score(s, ment) for ment in mentors] for s in students]

    @lru_cache(maxsize=None)
    def dp(i, mask):
        if i == m:
            return 0
        best = 0
        for j in range(m):
            if not (mask & (1 << j)):
                best = max(best, score_table[i][j] + dp(i + 1, mask | (1 << j)))
        return best

    return dp(0, 0)


# ============================================================
# Problem 6: Beautiful Arrangement (LC 526)
# ============================================================
def count_beautiful_arrangements(n):
    """Permutations [1..n] where for each pos i, perm[i] % i == 0 OR i % perm[i] == 0."""

    @lru_cache(maxsize=None)
    def dp(pos, mask):
        if pos > n:
            return 1
        total = 0
        for num in range(1, n + 1):
            if mask & (1 << num):
                continue
            if num % pos == 0 or pos % num == 0:
                total += dp(pos + 1, mask | (1 << num))
        return total

    return dp(1, 0)


# ============================================================
# Problem 7: Distribute Repeating Integers (LC 1655)
# ============================================================
def can_distribute(nums, quantity):
    """Each customer needs `quantity[i]` of SAME value.
    Assign to all customers? nums has ≤ 50 elements, but values repeat.
    Customers ≤ 10 → bitmask DP on customers."""
    from collections import Counter
    counts = sorted(Counter(nums).values(), reverse=True)
    m = len(quantity)
    full = (1 << m) - 1

    # For each subset of customers, total quantity needed
    subset_sum = [0] * (1 << m)
    for mask in range(1 << m):
        for j in range(m):
            if mask & (1 << j):
                subset_sum[mask] += quantity[j]

    @lru_cache(maxsize=None)
    def dp(i, mask):
        if mask == full:
            return True
        if i == len(counts):
            return False
        # Try all subsets of UNCOVERED customers
        uncovered = full ^ mask
        sub = uncovered
        while sub > 0:
            if subset_sum[sub] <= counts[i]:
                if dp(i + 1, mask | sub):
                    return True
            sub = (sub - 1) & uncovered
        # Also can skip this count
        return dp(i + 1, mask)

    return dp(0, 0)


# ============================================================
# Problem 8: Maximum Students Taking Exam (LC 1349)
# ============================================================
def max_students(seats):
    """Grid m x n, '#' broken, '.' usable.
    Place max students so no one cheats from left, right, upper-left, upper-right.
    Row-by-row bitmask DP."""
    m = len(seats)
    n = len(seats[0])

    # Allowed mask per row (1 means seat usable)
    allowed = []
    for row in seats:
        mask = 0
        for j, c in enumerate(row):
            if c == '.':
                mask |= (1 << j)
        allowed.append(mask)

    def is_valid_row(mask, row_allowed):
        # No adjacent students + only on usable seats
        if mask & ~row_allowed:
            return False
        if mask & (mask >> 1):
            return False
        return True

    @lru_cache(maxsize=None)
    def dp(row, prev_mask):
        if row == m:
            return 0
        best = 0
        # Try all submasks of allowed[row]
        sub = allowed[row]
        while True:
            if is_valid_row(sub, allowed[row]):
                # Check no upper-left / upper-right cheating
                if not (sub & (prev_mask >> 1)) and not (sub & (prev_mask << 1)):
                    cnt = bin(sub).count('1')
                    best = max(best, cnt + dp(row + 1, sub))
            if sub == 0:
                break
            sub = (sub - 1) & allowed[row]
        return best

    return dp(0, 0)


# ============================================================
# Demo
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("PROBLEM 1a: TSP Cycle (4 cities)")
    print("=" * 60)
    dist = [
        [0, 10, 15, 20],
        [10, 0, 35, 25],
        [15, 35, 0, 30],
        [20, 25, 30, 0],
    ]
    print(f"  Min cycle cost: {tsp_cycle(tuple(map(tuple, dist)))}  (expected 80)")
    # Use tuples for hashability in lru_cache

    print("\n" + "=" * 60)
    print("PROBLEM 1b: TSP Path (4 cities)")
    print("=" * 60)
    print(f"  Min path cost: {tsp_path(tuple(map(tuple, dist)))}")

    print("\n" + "=" * 60)
    print("PROBLEM 4: Smallest Sufficient Team (LC 1125)")
    print("=" * 60)
    req = ["java", "nodejs", "reactjs"]
    people = [["java"], ["nodejs"], ["nodejs", "reactjs"]]
    print(f"  Team: {smallest_sufficient_team(tuple(req), tuple(map(tuple, people)))}")

    print("\n" + "=" * 60)
    print("PROBLEM 5: Max Compatibility (LC 1947)")
    print("=" * 60)
    students = [[1, 1, 0], [1, 0, 1], [0, 0, 1]]
    mentors = [[1, 0, 0], [0, 0, 1], [1, 1, 0]]
    print(f"  Max sum: {max_compatibility_sum(tuple(map(tuple, students)), tuple(map(tuple, mentors)))}")

    print("\n" + "=" * 60)
    print("PROBLEM 6: Beautiful Arrangement (LC 526)")
    print("=" * 60)
    for n in [1, 2, 3, 4, 5]:
        print(f"  n={n}: {count_beautiful_arrangements(n)}")

    print("\n" + "=" * 60)
    print("PROBLEM 8: Max Students Taking Exam (LC 1349)")
    print("=" * 60)
    seats = [
        list("#.#.#"),
        list("...#."),
        list("#.#.#"),
    ]
    print(f"  Max students: {max_students(tuple(map(tuple, seats)))}  (expected 4)")

    print("\n" + "=" * 60)
    print("PATTERN CHECKLIST")
    print("=" * 60)
    print("""
- N ≤ 20: bitmask covers all subsets
- Bitmask of M items where M ≤ ~10: track which items used
- Iterate over subsets via (sub - 1) & mask
- Use bin(mask).count('1') for popcount
- Combine with row-by-row state for grid problems
- Use @lru_cache with hashable args (tuples, not lists)
""")
