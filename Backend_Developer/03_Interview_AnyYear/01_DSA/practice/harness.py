"""
DSA Practice Harness — apna solution likho, harness verify karega
==================================================================
Run: python harness.py              # saare attempted problems test karo
     python harness.py two_sum      # ek problem
     python harness.py --list       # kya-kya available hai
     python harness.py --stats      # progress

Kaise use karo:
  1. `attempts.py` kholo (pehli baar chalane pe auto-ban jaata hai)
  2. Ek function ka `pass` hatao aur apna solution likho
  3. `python harness.py` — PASS/FAIL + failing case turant dikhega
  4. Solution NAHI dekhna jab tak khud 20 min try na kar lo
     (reference solutions: ../NN_Topic/problems.py)

Design: har case = (args_tuple, expected). Comparison order-insensitive
hai jahan zaroori hai (subsets/permutations wale problems).
"""

import sys
import copy
import time
import importlib.util
from pathlib import Path

ATTEMPTS_FILE = Path(__file__).parent / "attempts.py"


# ════════════════════════════════════════════
# TEST CASES — pattern-wise canonical problems
# ════════════════════════════════════════════
# format: name: (topic_folder, [(args, expected), ...], comparator)

def _sorted_nested(x):
    """Order-insensitive compare for list-of-lists results."""
    return sorted(sorted(map(str, sub)) for sub in x)


PROBLEMS = {
    # ── Arrays & Hashing ──
    "two_sum": ("01_Arrays_Hashing", [
        (([2, 7, 11, 15], 9), [0, 1]),
        (([3, 2, 4], 6), [1, 2]),
        (([3, 3], 6), [0, 1]),
    ], None),
    "group_anagrams": ("01_Arrays_Hashing", [
        ((["eat", "tea", "tan", "ate", "nat", "bat"],),
         [["bat"], ["nat", "tan"], ["ate", "eat", "tea"]]),
        (([""],), [[""]]),
    ], _sorted_nested),
    "top_k_frequent": ("10_Heaps_Priority_Queue", [
        (([1, 1, 1, 2, 2, 3], 2), [1, 2]),
        (([1], 1), [1]),
    ], sorted),

    # ── Two Pointers / Sliding Window ──
    "max_subarray": ("01_Arrays_Hashing", [       # Kadane
        (([-2, 1, -3, 4, -1, 2, 1, -5, 4],), 6),
        (([1],), 1),
        (([5, 4, -1, 7, 8],), 23),
    ], None),
    "longest_unique_substring": ("06_Two_Pointers_Sliding_Window", [
        (("abcabcbb",), 3),
        (("bbbbb",), 1),
        (("pwwkew",), 3),
        (("",), 0),
    ], None),
    "container_with_most_water": ("06_Two_Pointers_Sliding_Window", [
        (([1, 8, 6, 2, 5, 4, 8, 3, 7],), 49),
        (([1, 1],), 1),
    ], None),
    "trapping_rain_water": ("06_Two_Pointers_Sliding_Window", [
        (([0, 1, 0, 2, 1, 0, 1, 3, 2, 1, 2, 1],), 6),
        (([4, 2, 0, 3, 2, 5],), 9),
    ], None),

    # ── Binary Search ──
    "search_rotated": ("05_Binary_Search", [
        (([4, 5, 6, 7, 0, 1, 2], 0), 4),
        (([4, 5, 6, 7, 0, 1, 2], 3), -1),
        (([1], 0), -1),
    ], None),
    "find_min_rotated": ("05_Binary_Search", [
        (([3, 4, 5, 1, 2],), 1),
        (([4, 5, 6, 7, 0, 1, 2],), 0),
        (([11, 13, 15, 17],), 11),
    ], None),

    # ── Stack ──
    "valid_parentheses": ("04_Stack_Queue", [
        (("()[]{}",), True),
        (("(]",), False),
        (("([)]",), False),
        (("{[]}",), True),
    ], None),
    "daily_temperatures": ("04_Stack_Queue", [    # monotonic stack
        (([73, 74, 75, 71, 69, 72, 76, 73],), [1, 1, 4, 2, 1, 1, 0, 0]),
        (([30, 40, 50, 60],), [1, 1, 1, 0]),
    ], None),

    # ── Intervals ──
    "merge_intervals": ("17_Intervals", [
        (([[1, 3], [2, 6], [8, 10], [15, 18]],), [[1, 6], [8, 10], [15, 18]]),
        (([[1, 4], [4, 5]],), [[1, 5]]),
    ], None),
    "min_meeting_rooms": ("17_Intervals", [
        (([[0, 30], [5, 10], [15, 20]],), 2),
        (([[7, 10], [2, 4]],), 1),
    ], None),

    # ── Linked List (list<->node helpers in attempts.py) ──
    "reverse_list_values": ("03_Linked_List", [   # values in, values out
        (([1, 2, 3, 4, 5],), [5, 4, 3, 2, 1]),
        (([],), []),
    ], None),
    "has_cycle_at": ("03_Linked_List", [          # (values, pos) -> bool
        (([3, 2, 0, -4], 1), True),
        (([1, 2], 0), True),
        (([1], -1), False),
    ], None),

    # ── Trees (level-order list representation) ──
    "max_depth": ("09_Trees", [
        (([3, 9, 20, None, None, 15, 7],), 3),
        (([1, None, 2],), 2),
        (([],), 0),
    ], None),
    "is_valid_bst": ("09_Trees", [
        (([2, 1, 3],), True),
        (([5, 1, 4, None, None, 3, 6],), False),
    ], None),

    # ── Graphs ──
    "num_islands": ("11_Graphs_BFS_DFS", [
        (([["1", "1", "0"], ["1", "0", "0"], ["0", "0", "1"]],), 2),
        (([["1", "1"], ["1", "1"]],), 1),
    ], None),
    "can_finish_courses": ("11_Graphs_BFS_DFS", [  # topological sort
        ((2, [[1, 0]]), True),
        ((2, [[1, 0], [0, 1]]), False),
    ], None),

    # ── Dynamic Programming ──
    "climb_stairs": ("12_Dynamic_Programming", [
        ((2,), 2), ((3,), 3), ((10,), 89),
    ], None),
    "coin_change": ("12_Dynamic_Programming", [
        (([1, 2, 5], 11), 3),
        (([2], 3), -1),
        (([1], 0), 0),
    ], None),
    "longest_common_subsequence": ("21_String_DP", [
        (("abcde", "ace"), 3),
        (("abc", "abc"), 3),
        (("abc", "def"), 0),
    ], None),
    "house_robber": ("12_Dynamic_Programming", [
        (([1, 2, 3, 1],), 4),
        (([2, 7, 9, 3, 1],), 12),
    ], None),

    # ── Backtracking ──
    "subsets": ("07_Recursion_Backtracking", [
        (([1, 2, 3],), [[], [1], [2], [1, 2], [3], [1, 3], [2, 3], [1, 2, 3]]),
    ], _sorted_nested),
    "permutations": ("07_Recursion_Backtracking", [
        (([1, 2, 3],), [[1, 2, 3], [1, 3, 2], [2, 1, 3],
                        [2, 3, 1], [3, 1, 2], [3, 2, 1]]),
    ], _sorted_nested),

    # ── Greedy / Bit / Math ──
    "jump_game": ("13_Greedy", [
        (([2, 3, 1, 1, 4],), True),
        (([3, 2, 1, 0, 4],), False),
    ], None),
    "single_number": ("16_Bit_Manipulation", [
        (([2, 2, 1],), 1),
        (([4, 1, 2, 1, 2],), 4),
    ], None),
    "count_bits": ("16_Bit_Manipulation", [
        ((5,), [0, 1, 1, 2, 1, 2]),
        ((2,), [0, 1, 1]),
    ], None),

    # ── Trie ──
    "implement_trie": ("14_Trie", [       # LC 208, design-problem as ops list
        (((["Trie", "insert", "search", "search", "startsWith", "insert", "search"],
           [[], ["apple"], ["apple"], ["app"], ["app"], ["app"], ["app"]])),
         [None, None, True, False, True, None, True]),
        (((["Trie", "startsWith", "insert", "search", "startsWith", "search"],
           [[], ["a"], ["ab"], ["a"], ["a"], ["ab"]])),
         [None, False, None, False, True, True]),
    ], None),

    # ── Union-Find ──
    "redundant_connection": ("15_Advanced_Graphs", [  # LC 684
        (([[1, 2], [1, 3], [2, 3]],), [2, 3]),
        (([[1, 2], [2, 3], [3, 4], [1, 4], [1, 5]],), [1, 4]),
        # ↓ DSU-forcing case. "pehla edge jiske dono ends pehle dekhe ja chuke hain"
        #   wala shortcut yahan [2,3] return karega — GALAT. [2,3] do alag
        #   components (1-2 aur 3-4) ko JODTA hai, cycle nahi banata.
        #   Sahi jawab [1,4] hai. Ye case sirf tab pass hoga jab tum actually
        #   union-find (ya DFS-per-edge) se connectivity track kar rahe ho.
        (([[1, 2], [3, 4], [2, 3], [1, 4]],), [1, 4]),
    ], None),

    # ── Dijkstra ──
    "network_delay_time": ("15_Advanced_Graphs", [    # LC 743
        (([[2, 1, 1], [2, 3, 1], [3, 4, 1]], 4, 2), 2),
        (([[1, 2, 1]], 2, 1), 1),
        (([[1, 2, 1]], 2, 2), -1),                    # node 1 unreachable
        # ↓ WEIGHT-forcing cases. Upar wale sab edges weight=1 hain, isliye
        #   plain BFS (hop count) bhi pass ho jata tha. Yahan weights alag hain:
        #   BFS bolega 1 hop, Dijkstra bolega 2 — sirf sahi answer pass hoga.
        (([[1, 2, 1], [2, 3, 1], [1, 3, 4]], 3, 1), 2),   # 1→2→3 (2) beats 1→3 (4)
        (([[1, 2, 10], [1, 3, 1], [3, 2, 1]], 3, 1), 2),  # detour sasta hai
    ], None),

    # ── Monotonic Queue ──
    "sliding_window_maximum": ("22_Monotonic_Queue", [  # LC 239
        (([1, 3, -1, -3, 5, 3, 6, 7], 3), [3, 3, 5, 5, 6, 7]),
        (([1], 1), [1]),
        (([9, 8, 7, 6, 5], 2), [9, 8, 7, 6]),           # strictly decreasing
    ], None),

    # ── Two Heaps ──
    "median_from_stream": ("10_Heaps_Priority_Queue", [  # LC 295, median after each add
        (([2, 3],), [2.0, 2.5]),
        (([1, 2, 3],), [1.0, 1.5, 2.0]),
        (([5, 1, 9, 2],), [5.0, 3.0, 5.0, 3.5]),
    ], None),

    # ── K-way Merge ──
    "merge_k_sorted_lists": ("10_Heaps_Priority_Queue", [  # LC 23, list-of-lists form
        (([[1, 4, 5], [1, 3, 4], [2, 6]],), [1, 1, 2, 3, 4, 4, 5, 6]),
        (([],), []),
        (([[], [1]],), [1]),
    ], None),

    # ── Cyclic Sort ──
    "first_missing_positive": ("08_Sorting_Algorithms", [  # LC 41
        (([1, 2, 0],), 3),
        (([3, 4, -1, 1],), 2),
        (([7, 8, 9, 11, 12],), 1),
        # ↓ DUPLICATE cases. Cyclic sort ka sabse common bug: swap loop me
        #   `nums[v-1] != v` guard bhool jana → duplicates pe INFINITE LOOP.
        #   Upar wale teeno cases me saare numbers distinct the, isliye bug
        #   pakda hi nahi jata tha. Ye teen use pakadte hain.
        (([1, 1],), 2),
        (([2, 2, 2, 2],), 1),
        (([1, 1, 2, 2],), 3),
    ], None),
}


TEMPLATE_HEADER = '''"""
DSA Attempts — apna solution yahan likho, phir `python harness.py` chalao.

Rules jo interview ke liye matter karte hain:
  - Pehle 20 min khud try karo. Stuck? Pattern hint dekho (00_Coding_Patterns_Index.md).
  - Reference solution SIRF attempt ke baad: ../NN_Topic/problems.py
  - Solve hone ke baad complexity comment me likho — interview me poocha jaata hai.

`pass` wale functions "not attempted" count hote hain — harness unhe skip karta hai.
"""

from typing import List, Optional


# ══════════════════════════════════════════════════
# Linked-list / tree helpers — inhe change mat karo
# ══════════════════════════════════════════════════
class ListNode:
    def __init__(self, val=0, next=None):
        self.val, self.next = val, next


class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val, self.left, self.right = val, left, right


def build_list(values: List[int]) -> Optional[ListNode]:
    head = None
    for v in reversed(values):
        head = ListNode(v, head)
    return head


def list_values(head: Optional[ListNode]) -> List[int]:
    out = []
    while head:
        out.append(head.val)
        head = head.next
    return out


def build_tree(level_order: list) -> Optional[TreeNode]:
    """[3,9,20,None,None,15,7] -> TreeNode tree (LeetCode format)."""
    if not level_order:
        return None
    root = TreeNode(level_order[0])
    queue, i = [root], 1
    while queue and i < len(level_order):
        node = queue.pop(0)
        if i < len(level_order) and level_order[i] is not None:
            node.left = TreeNode(level_order[i])
            queue.append(node.left)
        i += 1
        if i < len(level_order) and level_order[i] is not None:
            node.right = TreeNode(level_order[i])
            queue.append(node.right)
        i += 1
    return root


'''


def make_template() -> str:
    """attempts.py generate karo — har problem ka stub with signature hint."""
    sigs = {
        "two_sum": "nums: List[int], target: int) -> List[int]",
        "group_anagrams": "strs: List[str]) -> List[List[str]]",
        "top_k_frequent": "nums: List[int], k: int) -> List[int]",
        "max_subarray": "nums: List[int]) -> int",
        "longest_unique_substring": "s: str) -> int",
        "container_with_most_water": "height: List[int]) -> int",
        "trapping_rain_water": "height: List[int]) -> int",
        "search_rotated": "nums: List[int], target: int) -> int",
        "find_min_rotated": "nums: List[int]) -> int",
        "valid_parentheses": "s: str) -> bool",
        "daily_temperatures": "temps: List[int]) -> List[int]",
        "merge_intervals": "intervals: List[List[int]]) -> List[List[int]]",
        "min_meeting_rooms": "intervals: List[List[int]]) -> int",
        "reverse_list_values": "values: List[int]) -> List[int]",
        "has_cycle_at": "values: List[int], pos: int) -> bool",
        "max_depth": "level_order: list) -> int",
        "is_valid_bst": "level_order: list) -> bool",
        "num_islands": "grid: List[List[str]]) -> int",
        "can_finish_courses": "num_courses: int, prereqs: List[List[int]]) -> bool",
        "climb_stairs": "n: int) -> int",
        "coin_change": "coins: List[int], amount: int) -> int",
        "longest_common_subsequence": "a: str, b: str) -> int",
        "house_robber": "nums: List[int]) -> int",
        "subsets": "nums: List[int]) -> List[List[int]]",
        "permutations": "nums: List[int]) -> List[List[int]]",
        "jump_game": "nums: List[int]) -> bool",
        "single_number": "nums: List[int]) -> int",
        "count_bits": "n: int) -> List[int]",
        "implement_trie": "ops: List[str], args: List[List[str]]) -> List[Optional[bool]]",
        "redundant_connection": "edges: List[List[int]]) -> List[int]",
        "network_delay_time": "times: List[List[int]], n: int, k: int) -> int",
        "sliding_window_maximum": "nums: List[int], k: int) -> List[int]",
        "median_from_stream": "nums: List[int]) -> List[float]",
        "merge_k_sorted_lists": "lists: List[List[int]]) -> List[int]",
        "first_missing_positive": "nums: List[int]) -> int",
    }
    parts = [TEMPLATE_HEADER]
    current_topic = None
    for name, (topic, _, _) in PROBLEMS.items():
        if topic != current_topic:
            parts.append(f"\n# ─── {topic} " + "─" * max(0, 40 - len(topic)) + "\n")
            current_topic = topic
        hint = ""
        if name in ("reverse_list_values", "has_cycle_at"):
            hint = "    # Hint: build_list(values) se node banao, list_values() se wapas\n"
        elif name in ("max_depth", "is_valid_bst"):
            hint = "    # Hint: build_tree(level_order) se tree banao\n"
        elif name == "implement_trie":
            hint = (
                "    # Hint: LeetCode design format — ops[i] ko args[i] ke saath chalao,\n"
                "    #       har op ka result list me daalo (Trie/insert ka result None)\n"
            )
        elif name == "median_from_stream":
            hint = "    # Hint: two heaps — har number add hone ke BAAD current median append karo\n"
        elif name == "first_missing_positive":
            hint = "    # Hint: cyclic sort — value v ka ghar index v-1 hai (O(n)/O(1) required)\n"
        parts.append(
            f"def {name}({sigs[name]}:\n"
            f"    # TODO: Time O(?)  Space O(?)\n"
            f"{hint}    pass\n\n"
        )
    return "".join(parts)


def ensure_attempts_file() -> None:
    if not ATTEMPTS_FILE.exists():
        ATTEMPTS_FILE.write_text(make_template())
        print(f"✅ Created {ATTEMPTS_FILE.name} — ab usme solutions likho, phir dobara chalao.\n")


def load_attempts():
    spec = importlib.util.spec_from_file_location("attempts", ATTEMPTS_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(selected: str | None = None) -> None:
    ensure_attempts_file()
    mod = load_attempts()

    attempted = passed = failed = skipped = 0
    failures = []

    for name, (topic, cases, comparator) in PROBLEMS.items():
        if selected and name != selected:
            continue
        fn = getattr(mod, name, None)
        if fn is None:
            continue

        # "pass"-only body → not attempted.
        # deepcopy zaroori hai: in-place solutions (cyclic sort, sort colors)
        # warna PROBLEMS ka input mutate kar dete hain aur agla run galat hota hai.
        try:
            probe = fn(*copy.deepcopy(cases[0][0]))
        except NotImplementedError:
            probe = None
        except Exception as exc:                       # real attempt that crashed
            attempted += 1
            failed += 1
            failures.append((name, topic, f"raised {type(exc).__name__}: {exc}"))
            continue
        if probe is None and cases[0][1] is not None:
            skipped += 1
            continue

        attempted += 1
        ok, detail = True, ""
        start = time.perf_counter()
        for args, expected in cases:
            try:
                got = fn(*copy.deepcopy(args))   # har case fresh input pe chale
            except Exception as exc:
                ok, detail = False, f"{args} → raised {type(exc).__name__}: {exc}"
                break
            a, b = (comparator(got), comparator(expected)) if comparator else (got, expected)
            if a != b:
                ok, detail = False, f"{args} → got {got!r}, expected {expected!r}"
                break
        elapsed = (time.perf_counter() - start) * 1000

        if ok:
            passed += 1
            print(f"  ✅ {name:<32} {elapsed:6.2f}ms  ({topic})")
        else:
            failed += 1
            failures.append((name, topic, detail))
            print(f"  ❌ {name:<32} {detail}")

    total = len(PROBLEMS) if not selected else 1
    print(f"\n{'─' * 60}")
    print(f"  Attempted {attempted}/{total}   ✅ {passed}   ❌ {failed}   ⬜ not-started {total - attempted}")
    if failures:
        print("\n  Fix these (reference solution dekhne se pehle 20 min aur try karo):")
        for name, topic, detail in failures:
            print(f"    • {name} → ../{topic}/problems.py")
    elif attempted == total:
        print("  🎉 Sab pass! Ab timed mode: har problem 20 min me blank file se.")


def show_list() -> None:
    by_topic: dict[str, list[tuple[str, int]]] = {}
    for name, (topic, cases, _) in PROBLEMS.items():
        by_topic.setdefault(topic, []).append((name, len(cases)))
    for topic in sorted(by_topic):
        print(f"\n{topic}")
        for name, n in by_topic[topic]:
            print(f"  {name:<34} {n} cases")
    print(f"\nTotal: {len(PROBLEMS)} problems")


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    if arg == "--list":
        show_list()
    elif arg in ("--stats", "-s"):
        run()
    elif arg and arg.startswith("-"):
        print(__doc__)
    else:
        run(arg)
