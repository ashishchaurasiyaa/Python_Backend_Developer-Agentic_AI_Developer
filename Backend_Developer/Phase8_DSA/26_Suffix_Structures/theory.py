"""
============================================================
SUFFIX ARRAY + SUFFIX TREE (+ LCP Array)
============================================================

WHAT IS A SUFFIX?
-----------------
For string "banana":
  index 0: "banana"
  index 1: "anana"
  index 2: "nana"
  index 3: "ana"
  index 4: "na"
  index 5: "a"

Total N suffixes for string of length N.

WHAT IS A SUFFIX ARRAY?
-----------------------
Sorted indices of all suffixes (lexicographic order).

For "banana":
  Sorted suffixes:
    a      (index 5)
    ana    (index 3)
    anana  (index 1)
    banana (index 0)
    na     (index 4)
    nana   (index 2)

Suffix Array = [5, 3, 1, 0, 4, 2]

USE CASES
---------
1. Pattern matching (substring search) — binary search on suffix array
2. Longest Common Substring of multiple strings
3. Longest Repeated Substring
4. Number of distinct substrings
5. Bioinformatics — DNA sequence alignment
6. Search engines — full-text indexing
7. Compression algorithms — BWT (Burrows-Wheeler Transform)

SUFFIX ARRAY vs SUFFIX TREE
----------------------------
| Aspect       | Suffix Array        | Suffix Tree           |
|--------------|---------------------|-----------------------|
| Space        | O(N) integers       | O(N) nodes/edges      |
| Memory       | ~4-8 bytes per char | ~20+ bytes per char   |
| Build        | O(N log N) basic    | O(N) Ukkonen's algo   |
|              | O(N) DC3/SA-IS      |                       |
| Implementation | Simple            | Complex (Ukkonen)     |
| Pattern match | O(M log N) binsearch| O(M) walk             |
| Modern use   | Preferred (compact) | Educational           |

PYTHON: Suffix Array is the practical choice.

LCP ARRAY (Longest Common Prefix)
----------------------------------
lcp[i] = longest common prefix of suffix at SA[i] and SA[i-1].

Powerful augmentation — answers many string queries.
Build: Kasai's algorithm in O(N) after suffix array.

PROBLEMS SUFFIX ARRAY SOLVES (with LCP)
---------------------------------------
- Substring search: O(M log N)
- Longest repeated substring: max(LCP)
- Distinct substrings: N*(N+1)/2 - sum(LCP)
- Longest common substring of K strings: clever LCP + sliding window

============================================================
"""

# ============================================================
# SUFFIX ARRAY — O(N^2 log N) simple version
# ============================================================
def suffix_array_naive(s):
    """Simple O(N^2 log N) — just sort the suffixes.
    Fine for N ≤ 1000."""
    n = len(s)
    suffixes = [(s[i:], i) for i in range(n)]
    suffixes.sort()
    return [suf[1] for suf in suffixes]


# ============================================================
# SUFFIX ARRAY — O(N log^2 N) using rank doubling
# ============================================================
def suffix_array_nlogn(s):
    """O(N log^2 N) — standard for competitive programming.
    Uses doubling: sort by first 1 char, then 2, 4, 8, ...
    """
    n = len(s)
    sa = list(range(n))
    rank = [ord(c) for c in s]
    tmp = [0] * n
    k = 1
    while True:
        def cmp_key(i):
            r1 = rank[i]
            r2 = rank[i + k] if i + k < n else -1
            return (r1, r2)

        sa.sort(key=cmp_key)
        tmp[sa[0]] = 0
        for i in range(1, n):
            tmp[sa[i]] = tmp[sa[i - 1]]
            if cmp_key(sa[i]) != cmp_key(sa[i - 1]):
                tmp[sa[i]] += 1
        rank = tmp[:]
        if rank[sa[n - 1]] == n - 1:
            break
        k *= 2
        if k >= n:
            break
    return sa


# ============================================================
# LCP ARRAY using Kasai's Algorithm — O(N)
# ============================================================
def lcp_kasai(s, sa):
    """Compute LCP array given suffix array.
    lcp[i] = LCP(suffix(sa[i]), suffix(sa[i-1])) for i ≥ 1.
    lcp[0] = 0 by convention.
    """
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
# PATTERN SEARCH using Suffix Array — O(M log N)
# ============================================================
def find_pattern(text, pattern, sa=None):
    """Find pattern in text using suffix array binary search.
    Returns list of starting indices."""
    if sa is None:
        sa = suffix_array_nlogn(text)
    n, m = len(text), len(pattern)

    # Lower bound — first SA index where text[sa[i]:] >= pattern
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

    return sorted([sa[i] for i in range(start, end) if text[sa[i]:sa[i] + m] == pattern])


# ============================================================
# SUFFIX TREE — Trie of Suffixes (simple version, O(N^2) build)
# ============================================================
class SuffixTrieNode:
    def __init__(self):
        self.children = {}
        self.indices = []   # starting indices of suffixes through this node


class SuffixTrie:
    """Simplified suffix tree — actually a suffix TRIE.
    Real suffix tree (Ukkonen) compresses paths. This is for understanding."""

    def __init__(self, text):
        self.root = SuffixTrieNode()
        self.text = text
        for i in range(len(text)):
            self._insert(text[i:] + "$", i)

    def _insert(self, suffix, start_idx):
        node = self.root
        for ch in suffix:
            if ch not in node.children:
                node.children[ch] = SuffixTrieNode()
            node = node.children[ch]
            node.indices.append(start_idx)

    def search(self, pattern):
        """Returns starting indices of pattern."""
        node = self.root
        for ch in pattern:
            if ch not in node.children:
                return []
            node = node.children[ch]
        return sorted(node.indices)


# ============================================================
# Demo
# ============================================================
if __name__ == "__main__":
    s = "banana"
    print("=" * 60)
    print(f"String: {s}")
    print("=" * 60)

    sa = suffix_array_nlogn(s)
    print(f"\nSuffix Array : {sa}")
    print("Sorted suffixes:")
    for i, idx in enumerate(sa):
        print(f"  [{i}] idx={idx}: {s[idx:]}")

    lcp = lcp_kasai(s, sa)
    print(f"\nLCP Array    : {lcp}")
    print("LCP between adjacent sorted suffixes:")
    for i in range(1, len(sa)):
        print(f"  LCP({s[sa[i-1]:]!r}, {s[sa[i]:]!r}) = {lcp[i]}")

    print("\n--- Pattern Search ---")
    for pat in ["ana", "ban", "na", "xyz"]:
        positions = find_pattern(s, pat, sa)
        print(f"  '{pat}' found at: {positions}")

    print("\n--- Suffix Trie ---")
    trie = SuffixTrie(s)
    for pat in ["ana", "an", "na"]:
        print(f"  '{pat}' -> indices {trie.search(pat)}")

    print("\n" + "=" * 60)
    print("APPLICATIONS — solve with suffix array + LCP")
    print("=" * 60)

    # Longest repeated substring
    s2 = "banana"
    sa2 = suffix_array_nlogn(s2)
    lcp2 = lcp_kasai(s2, sa2)
    max_lcp = max(lcp2)
    idx = lcp2.index(max_lcp)
    lrs = s2[sa2[idx]:sa2[idx] + max_lcp]
    print(f"Longest repeated substring of '{s2}': '{lrs}' (length {max_lcp})")

    # Number of distinct substrings
    n = len(s2)
    distinct = n * (n + 1) // 2 - sum(lcp2)
    print(f"Distinct substrings of '{s2}': {distinct}")

    print("\n" + "=" * 60)
    print("INTERVIEW Q&A")
    print("=" * 60)
    print("""
Q: Suffix Array vs Suffix Tree?
A: SA — compact (4N bytes), simple build, slightly slower queries.
   ST — verbose (20N+ bytes), O(N) Ukkonen build complex.
   Modern code prefers SA + LCP.

Q: Build complexity?
A: Naive: O(N^2 log N), Doubling: O(N log^2 N),
   Best: O(N) via SA-IS or DC3.

Q: Real-world uses?
A: Search engines (ES indexing), bioinformatics (genome assembly),
   data compression (BWT in bzip2), plagiarism detection.

Q: LCP array kya solve karta?
A: Longest repeated substring (max LCP), distinct substring count,
   longest common substring of multiple strings.

Q: Pattern search complexity?
A: O(M log N) using binary search on SA. With LCP enhancements,
   O(M + log N). Suffix tree gives O(M) but uses much more memory.
""")
