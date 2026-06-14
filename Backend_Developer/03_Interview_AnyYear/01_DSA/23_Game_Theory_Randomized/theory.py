"""
23 — Game Theory & Randomized Algorithms — Theory
===================================================
Level: Intermediate
"""
from __future__ import annotations
from typing import List, Optional
import random
from functools import lru_cache

# ════════════════════════════════════════════════════════════
# PART A: GAME THEORY
# ════════════════════════════════════════════════════════════
"""
GAME THEORY in coding = two-player optimal strategy problems.
Both players play OPTIMALLY (best possible move).

KEY CONCEPTS:
  Minimax: minimize opponent's max gain / maximize your min gain
  Memoization: cache game states
  Nim theory: XOR trick for combinatorial games
  Sprague-Grundy theorem: every impartial game = Nim position
"""

# ────────────────────────────────────────────────────────────
# PATTERN 1: Predict the Winner (Minimax)
# ────────────────────────────────────────────────────────────

def predict_winner(nums: List[int]) -> bool:
    """
    LC 486: Two players alternately pick from ends of array.
    Return True if Player 1 can win (score >= Player 2).

    score(i,j) = max score DIFFERENCE Player1 can achieve on nums[i..j]
    If Player1 picks left:  nums[i] - score(i+1, j)   (opponent now maximizes on i+1..j)
    If Player1 picks right: nums[j] - score(i, j-1)

    score >= 0 means Player1 wins.
    """
    n = len(nums)

    @lru_cache(maxsize=None)
    def dp(i: int, j: int) -> int:
        if i == j: return nums[i]
        pick_left  = nums[i] - dp(i+1, j)
        pick_right = nums[j] - dp(i, j-1)
        return max(pick_left, pick_right)

    return dp(0, n-1) >= 0

print("Predict winner [1,5,2]:", predict_winner([1,5,2]))       # False
print("Predict winner [1,5,233,7]:", predict_winner([1,5,233,7]))  # True


# ────────────────────────────────────────────────────────────
# PATTERN 2: Stone Game Variants (Nim)
# ────────────────────────────────────────────────────────────

def stone_game(piles: List[int]) -> bool:
    """LC 877: Two players pick from either end. First player always wins with even piles."""
    # Mathematical insight: First player always wins!
    # Proof: First player can always choose all "odd-indexed" or all "even-indexed" piles
    return True   # First player always wins with even number of piles

def nim_winner(n: int) -> bool:
    """LC 292: Nim game — pick 1,2,3 stones. Lose if you take last stone."""
    # If n % 4 == 0, second player always wins. Otherwise first player wins.
    return n % 4 != 0

def can_win_nim(n: int) -> bool:
    """General Nim: player who takes last stone WINS."""
    return n % 4 != 0

print("Nim game n=4:", nim_winner(4))   # False (second player wins)
print("Nim game n=5:", nim_winner(5))   # True


# ────────────────────────────────────────────────────────────
# PATTERN 3: Minimax with Alpha-Beta (General)
# ────────────────────────────────────────────────────────────

def minimax(state, depth: int, is_maximizer: bool, alpha: float, beta: float) -> float:
    """
    General minimax with alpha-beta pruning.
    alpha = best score maximizer can guarantee so far
    beta  = best score minimizer can guarantee so far
    Prune when alpha >= beta (opponent won't allow this path).
    """
    if depth == 0 or is_terminal(state):
        return evaluate(state)

    if is_maximizer:
        max_eval = float('-inf')
        for child in get_children(state):
            eval_ = minimax(child, depth-1, False, alpha, beta)
            max_eval = max(max_eval, eval_)
            alpha = max(alpha, eval_)
            if beta <= alpha:
                break   # beta cutoff (minimizer won't allow this)
        return max_eval
    else:
        min_eval = float('inf')
        for child in get_children(state):
            eval_ = minimax(child, depth-1, True, alpha, beta)
            min_eval = min(min_eval, eval_)
            beta = min(beta, eval_)
            if beta <= alpha:
                break   # alpha cutoff (maximizer won't allow this)
        return min_eval

# ── Minimal Nim game for the minimax demo above ──────────────────────────────
# State: tuple (stones_remaining, maximizer_to_move).
#   stones_remaining — non-negative int.
#   maximizer_to_move — bool, True when it is the maximizer's turn.
# Each turn the current player takes 1, 2, or 3 stones.
# The player who takes the LAST stone WINS.
# A position with 0 stones is terminal: the player who just moved took the
# last stone and won.  So 0 stones means the player to move has LOST.
# evaluate() returns a score from the global maximizer's perspective:
#   +1  maximizer won, -1  minimizer won.

def is_terminal(state) -> bool:
    """No stones left: the player to move has no moves → terminal."""
    stones, _ = state
    return stones == 0

def evaluate(state) -> float:
    """
    Called only on terminal states (stones == 0).
    The player to move has lost because the opponent took the last stone.
    If it is the maximizer's turn to move, the maximizer loses → return -1.
    If it is the minimizer's turn to move, the minimizer loses → return +1.
    """
    _, maximizer_to_move = state
    return -1.0 if maximizer_to_move else +1.0

def get_children(state) -> list:
    """Take 1, 2, or 3 stones; propagate whose turn comes next."""
    stones, maximizer_to_move = state
    return [(stones - take, not maximizer_to_move)
            for take in range(1, min(4, stones + 1))]

# ── Demo: who wins from each starting position (1-7 stones)? ─────────────────
print("\n--- Minimax Nim demo (take 1-3 stones, last to take wins) ---")
for _stones in range(1, 8):
    _start = (_stones, True)   # maximizer moves first
    _result = minimax(_start, depth=_stones, is_maximizer=True,
                      alpha=float('-inf'), beta=float('inf'))
    _winner = "First player (maximizer)" if _result > 0 else "Second player (minimizer)"
    _xor    = "First"  if _stones % 4 != 0 else "Second"
    print(f"  {_stones} stone(s): minimax={_result:+.0f} → {_winner} wins"
          f"  (Nim theory: {_xor} player wins)")


# ════════════════════════════════════════════════════════════
# PART B: RANDOMIZED ALGORITHMS
# ════════════════════════════════════════════════════════════
"""
RANDOMIZED ALGORITHMS use randomness to achieve simplicity or efficiency.

TYPES:
  Las Vegas: always correct, runtime varies (e.g., QuickSelect, Randomized QuickSort)
  Monte Carlo: fixed runtime, small probability of error (e.g., primality test)

KEY CONCEPTS:
  Random shuffle (Fisher-Yates)
  Reservoir sampling
  Randomized QuickSelect (find kth element O(n) average)
  Random pick with weights
"""

# ────────────────────────────────────────────────────────────
# PATTERN 4: Fisher-Yates Shuffle
# ────────────────────────────────────────────────────────────

def shuffle(nums: List[int]) -> List[int]:
    """Unbiased shuffle in O(n). Each permutation equally likely."""
    nums = nums[:]
    n = len(nums)
    for i in range(n-1, 0, -1):
        j = random.randint(0, i)
        nums[i], nums[j] = nums[j], nums[i]
    return nums

print("Shuffle:", shuffle([1,2,3,4,5]))


# ────────────────────────────────────────────────────────────
# PATTERN 5: Reservoir Sampling (random from stream)
# ────────────────────────────────────────────────────────────

def reservoir_sample(stream, k: int) -> list:
    """
    Sample k items from a stream of unknown length uniformly at random.
    LC 382: Linked List Random Node (k=1).

    Algorithm:
    - Fill reservoir with first k items.
    - For item i (i > k): include with probability k/i.
      If included, replace random reservoir item.
    """
    reservoir = []
    for i, item in enumerate(stream):
        if i < k:
            reservoir.append(item)
        else:
            j = random.randint(0, i)
            if j < k:
                reservoir[j] = item
    return reservoir

# Demo
stream = range(100)
sample = reservoir_sample(stream, 5)
print("Reservoir sample (5 from 100):", sample)


# ────────────────────────────────────────────────────────────
# PATTERN 6: Randomized QuickSelect (Kth Largest)
# ────────────────────────────────────────────────────────────

def quickselect(nums: List[int], k: int) -> int:
    """
    Find kth largest element in O(n) average time.
    Worst case O(n²) with bad pivot, but randomization makes it O(n) expected.
    LC 215: Kth Largest Element in an Array.
    """
    def partition(lo, hi):
        # Random pivot to avoid worst case
        pivot_idx = random.randint(lo, hi)
        nums[pivot_idx], nums[hi] = nums[hi], nums[pivot_idx]
        pivot = nums[hi]
        i = lo
        for j in range(lo, hi):
            if nums[j] >= pivot:   # >= for kth LARGEST
                nums[i], nums[j] = nums[j], nums[i]
                i += 1
        nums[i], nums[hi] = nums[hi], nums[i]
        return i

    lo, hi = 0, len(nums) - 1
    target = k - 1   # 0-indexed target position
    while lo <= hi:
        pivot_pos = partition(lo, hi)
        if pivot_pos == target:   return nums[pivot_pos]
        elif pivot_pos < target:  lo = pivot_pos + 1
        else:                     hi = pivot_pos - 1
    return -1

nums = [3,2,1,5,6,4]
print("3rd largest:", quickselect(nums[:], 3))  # 4


# ────────────────────────────────────────────────────────────
# PATTERN 7: Random Pick with Weight (LC 528)
# ────────────────────────────────────────────────────────────

class WeightedRandom:
    """
    Pick index i with probability proportional to w[i].
    Build prefix sums. Random float in [0, total] → binary search.
    """
    def __init__(self, w: List[int]):
        self.prefix = []
        total = 0
        for weight in w:
            total += weight
            self.prefix.append(total)
        self.total = total

    def pick_index(self) -> int:
        target = random.random() * self.total
        lo, hi = 0, len(self.prefix) - 1
        while lo < hi:
            mid = (lo + hi) // 2
            if self.prefix[mid] < target:
                lo = mid + 1
            else:
                hi = mid
        return lo

wr = WeightedRandom([1, 3])
picks = [wr.pick_index() for _ in range(1000)]
print("Weight[1,3] → index 0 count:", picks.count(0), "index 1 count:", picks.count(1))
# Expect ~250 zeros, ~750 ones


# ────────────────────────────────────────────────────────────
# PATTERN 8: Random Pick in Rectangle (LC 497)
# ────────────────────────────────────────────────────────────

class SolutionRectangle:
    """Pick random integer point inside one of the given non-overlapping rectangles."""
    def __init__(self, rects):
        self.rects = rects
        self.areas = [((x2-x1+1)*(y2-y1+1)) for x1,y1,x2,y2 in rects]
        self.total = sum(self.areas)
        self.prefix = []
        s = 0
        for a in self.areas: s += a; self.prefix.append(s)

    def pick(self):
        target = random.randint(1, self.total)
        lo, hi = 0, len(self.prefix)-1
        while lo < hi:
            mid = (lo+hi)//2
            if self.prefix[mid] < target: lo = mid+1
            else: hi = mid
        x1,y1,x2,y2 = self.rects[lo]
        return [random.randint(x1,x2), random.randint(y1,y2)]


# ════════════════════════════════════════════════════════════
# INTERVIEW Q&A
# ════════════════════════════════════════════════════════════
"""
Q1: What is minimax and when do you use it?
A: Minimax is a decision-making algorithm for two-player zero-sum games.
   Maximizer tries to maximize score, Minimizer tries to minimize it.
   Use memoization (top-down DP) for overlapping subproblems.
   Alpha-beta pruning reduces search space from O(b^d) to O(b^(d/2)).

Q2: Why does Player 1 always win in LC 877 Stone Game?
A: With even number of piles, Player 1 can categorize all piles into
   odd-indexed and even-indexed. One group has more total. Player 1
   picks the category with more stones by choosing the first pile —
   they control which group the opponent gets.

Q3: What is the Nim game theory (XOR trick)?
A: In multi-pile Nim (take any stones from one pile, last to take wins):
   First player loses IFF XOR of all pile sizes = 0.
   If XOR ≠ 0, first player can always make a move to reach XOR = 0.
   Single pile (LC 292): n % 4 == 0 → second player wins.

Q4: What is Sprague-Grundy theorem?
A: Every impartial game (both players have same moves) is equivalent to
   a Nim heap of some size (its Grundy value / nimber).
   Sum of games: XOR their Grundy values. If XOR ≠ 0, first player wins.

Q5: Las Vegas vs Monte Carlo algorithms?
A: Las Vegas: always returns correct result, but running time is random.
   Example: Randomized QuickSort (O(n log n) expected, never wrong).
   Monte Carlo: fixed time, may return wrong result with small probability.
   Example: Miller-Rabin primality test (correct with prob ≥ 1 - 4^(-k)).

Q6: Why is reservoir sampling unbiased?
A: For item i (0-indexed): probability of being in reservoir at end =
   (1/i+1) × (i+1/i+2) × ... × (n-1/n) = 1/n. Each item has equal
   probability. Proof by induction on stream length.

Q7: QuickSelect average O(n) — why?
A: With random pivot: expected pivot position = middle. Recursion halves
   the problem on average. T(n) = T(n/2) + O(n) → O(n) by master theorem.
   Expected total comparisons ≈ 2n (with randomization).

Q8: How does weighted random pick work?
A: Build prefix sum array. Random uniform number in [0, total_weight].
   Binary search for first prefix sum ≥ random number = selected index.
   Probability of picking index i = w[i] / sum(w). O(log n) per pick.
"""
