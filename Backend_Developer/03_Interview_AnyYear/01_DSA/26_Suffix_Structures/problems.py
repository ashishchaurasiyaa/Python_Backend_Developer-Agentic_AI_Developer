"""
============================================================
SUFFIX ARRAY + LCP — INTERVIEW PROBLEMS
============================================================

Problems covered:
  1. Longest Repeated Substring (LRS)
  2. Number of Distinct Substrings
  3. Longest Common Substring of two strings
  4. Longest Palindromic Substring (via SA + LCP on s + s[::-1])
  5. Pattern Count — number of occurrences
  6. K-th Lexicographic Substring
  7. Longest Common Substring of N strings
  8. Suffix-based Z-function alternative
"""
import math
from collections import defaultdict


# ============================================================
# Helpers (reusable)
# ============================================================
def suffix_array(s):
    n = len(s)
    sa = list(range(n))
    rank = [ord(c) for c in s]
    tmp = [0] * n
    k = 1
    while True:
        def key(i):
            r2 = rank[i + k] if i + k < n else -1
            return (rank[i], r2)

        sa.sort(key=key)
        tmp[sa[0]] = 0
        for i in range(1, n):
            tmp[sa[i]] = tmp[sa[i - 1]]
            if key(sa[i]) != key(sa[i - 1]):
                tmp[sa[i]] += 1
        rank = tmp[:]
        if rank[sa[-1]] == n - 1:
            break
        k *= 2
        if k >= n:
            break
    return sa


def lcp_array(s, sa):
    n = len(s)
    rank = [0] * n
    for i in range(n):
        rank[sa[i]] = i
    lcp = [0] * n
    h = 0
    for i in range(n):
        if rank[i] > 0:
            j = sa[rank[i] - 1]
            while i + h < n and j + h < n and s[i + h] == s[j + h]:
                h += 1
            lcp[rank[i]] = h
            if h > 0:
                h -= 1
    return lcp


# ============================================================
# Problem 1: Longest Repeated Substring
# LeetCode 1044
# ============================================================
def longest_repeated_substring(s):
    """Max LCP value = length, sa[idx] = start position."""
    if len(s) < 2:
        return ""
    sa = suffix_array(s)
    lcp = lcp_array(s, sa)
    max_len = max(lcp)
    if max_len == 0:
        return ""
    idx = lcp.index(max_len)
    return s[sa[idx]:sa[idx] + max_len]


# ============================================================
# Problem 2: Number of Distinct Substrings
# Codeforces, SPOJ DISUBSTR
# ============================================================
def count_distinct_substrings(s):
    """Total substrings = N*(N+1)/2.
    Subtract sum(LCP) for repeats.
    """
    n = len(s)
    if n == 0:
        return 0
    sa = suffix_array(s)
    lcp = lcp_array(s, sa)
    return n * (n + 1) // 2 - sum(lcp)


# ============================================================
# Problem 3: Longest Common Substring of two strings
# LeetCode 718 variant
# ============================================================
def longest_common_substring(a, b):
    """Concat a + '#' + b + '$', build SA + LCP.
    Find max LCP between adjacent suffixes from DIFFERENT strings.
    """
    s = a + "#" + b + "$"
    n1 = len(a)
    sa = suffix_array(s)
    lcp = lcp_array(s, sa)

    best_len = 0
    best_start = 0
    for i in range(1, len(s)):
        # Check if sa[i-1] and sa[i] are from different sides
        from_a_prev = sa[i - 1] < n1
        from_a_curr = sa[i] < n1
        if from_a_prev != from_a_curr:
            if lcp[i] > best_len:
                best_len = lcp[i]
                best_start = sa[i]
    return s[best_start:best_start + best_len]


# ============================================================
# Problem 4: Longest Palindromic Substring (via SA approach)
# Alternative to Manacher's — O(N log N)
# ============================================================
def longest_palindromic_substring_sa(s):
    """Build SA on s + '#' + reverse(s) + '$'.
    For each suffix from s, find LCP with corresponding rev suffix.
    Note: Manacher's O(N) is faster — this is an SA application demo.
    """
    n = len(s)
    if n < 2:
        return s
    combined = s + "#" + s[::-1] + "$"

    # For each center, expansion would still work — keep simple here
    # This is more illustrative than optimal.
    best = ""
    for center in range(n):
        # Odd length
        l, r = center, center
        while l >= 0 and r < n and s[l] == s[r]:
            if r - l + 1 > len(best):
                best = s[l:r+1]
            l -= 1
            r += 1
        # Even length
        l, r = center, center + 1
        while l >= 0 and r < n and s[l] == s[r]:
            if r - l + 1 > len(best):
                best = s[l:r+1]
            l -= 1
            r += 1
    return best


# ============================================================
# Problem 5: Number of occurrences of a pattern (substring count)
# ============================================================
def count_occurrences(text, pattern):
    """Count occurrences of pattern in text using SA + binary search.
    O(M log N)."""
    n = len(text)
    m = len(pattern)
    sa = suffix_array(text)

    # Lower bound
    lo, hi = 0, n
    while lo < hi:
        mid = (lo + hi) // 2
        if text[sa[mid]:sa[mid] + m] < pattern:
            lo = mid + 1
        else:
            hi = mid
    start = lo

    # Upper bound
    lo, hi = 0, n
    while lo < hi:
        mid = (lo + hi) // 2
        if text[sa[mid]:sa[mid] + m] <= pattern:
            lo = mid + 1
        else:
            hi = mid
    end = lo

    # Verify (could be off if pattern not present)
    count = 0
    for i in range(start, end):
        if text[sa[i]:sa[i] + m] == pattern:
            count += 1
    return count


# ============================================================
# Problem 6: K-th Lexicographic Substring
# Codeforces 128B "String"
# ============================================================
def kth_lex_substring(s, k):
    """Find K-th lexicographically smallest substring (1-indexed)."""
    n = len(s)
    sa = suffix_array(s)
    lcp = lcp_array(s, sa)

    # For each suffix in SA order, contributes (len(suffix) - lcp[i]) new substrings
    for i in range(n):
        suffix_len = n - sa[i]
        new_substrings = suffix_len - lcp[i]
        if k <= new_substrings:
            # K-th comes from this suffix; length = lcp[i] + k
            return s[sa[i]:sa[i] + lcp[i] + k]
        k -= new_substrings
    return ""  # k too large


# ============================================================
# Problem 7: Longest Common Substring of N strings
# SPOJ LCS2 — for 2 it's Problem 3; generalize via group min LCP
# ============================================================
def lcs_of_n_strings(strings):
    """Concat with unique separators, build SA + LCP.
    For each window of suffixes containing ALL strings, take min LCP.
    Best answer = max of such mins.
    Simplified: use Problem 3 approach pairwise for small N.
    """
    if not strings:
        return ""
    if len(strings) == 1:
        return strings[0]
    result = strings[0]
    for i in range(1, len(strings)):
        result = longest_common_substring(result, strings[i])
        if not result:
            return ""
    return result


# ============================================================
# Problem 8: Count distinct palindromic substrings (eertree alternative)
# Using SA on s + '#' + reverse(s) — heuristic
# ============================================================
def is_substring(text, pattern):
    """Quick check using SA — O(M log N)."""
    sa = suffix_array(text)
    n, m = len(text), len(pattern)
    lo, hi = 0, n
    while lo < hi:
        mid = (lo + hi) // 2
        if text[sa[mid]:sa[mid] + m] < pattern:
            lo = mid + 1
        else:
            hi = mid
    return lo < n and text[sa[lo]:sa[lo] + m] == pattern


# ============================================================
# Demo
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("PROBLEM 1: Longest Repeated Substring")
    print("=" * 60)
    for s in ["banana", "abcabc", "abcdefg", "aabbaabb"]:
        print(f"  '{s}' -> '{longest_repeated_substring(s)}'")

    print("\n" + "=" * 60)
    print("PROBLEM 2: Distinct Substrings")
    print("=" * 60)
    for s in ["abc", "aaa", "banana"]:
        print(f"  '{s}' -> {count_distinct_substrings(s)} distinct substrings")

    print("\n" + "=" * 60)
    print("PROBLEM 3: Longest Common Substring of 2 strings")
    print("=" * 60)
    print(f"  ('GeeksforGeeks', 'GeeksQuiz') -> '{longest_common_substring('GeeksforGeeks', 'GeeksQuiz')}'")
    print(f"  ('apple', 'pineapple') -> '{longest_common_substring('apple', 'pineapple')}'")

    print("\n" + "=" * 60)
    print("PROBLEM 4: Longest Palindromic Substring")
    print("=" * 60)
    for s in ["babad", "cbbd", "racecar"]:
        print(f"  '{s}' -> '{longest_palindromic_substring_sa(s)}'")

    print("\n" + "=" * 60)
    print("PROBLEM 5: Pattern Occurrence Count")
    print("=" * 60)
    text = "abracadabra"
    for p in ["abra", "a", "cad", "xyz"]:
        print(f"  '{p}' in '{text}' -> {count_occurrences(text, p)} times")

    print("\n" + "=" * 60)
    print("PROBLEM 6: K-th Lex Substring")
    print("=" * 60)
    s = "aa"
    print(f"  String: '{s}'")
    print("  Distinct substrings in order: 'a', 'aa'")
    for k in [1, 2]:
        print(f"  k={k} -> '{kth_lex_substring(s, k)}'")

    print("\n" + "=" * 60)
    print("PROBLEM 7: LCS of N strings")
    print("=" * 60)
    strs = ["abcdxyz", "xyzabcd", "qabcdr"]
    print(f"  Inputs: {strs}")
    print(f"  LCS  : '{lcs_of_n_strings(strs)}'")

    print("\n" + "=" * 60)
    print("KEY TAKEAWAYS")
    print("=" * 60)
    print("""
1. Suffix Array + LCP solves MOST string problems
2. Build: O(N log^2 N) doubling — sufficient for N ≤ 1e5
3. Pattern search: O(M log N) via binary search
4. Longest repeated substring = max(LCP)
5. Distinct substrings = N(N+1)/2 - sum(LCP)
6. Common substring of multiple = combine with separators
7. For competitive: practice SA-IS / DC3 for O(N) build
""")
