"""
21 — String DP — Theory
=========================
Level: Intermediate → Advanced
"""
from __future__ import annotations
from typing import List
from functools import lru_cache

# ════════════════════════════════════════════════════════════
# WHAT & WHY
# ════════════════════════════════════════════════════════════
"""
String DP = Dynamic Programming on one or two strings.
Most problems ask: transform, match, find common/diff structure.

KEY INSIGHT: Most string DP has a 2D table dp[i][j] where:
  i = index into string s1 (or length of prefix)
  j = index into string s2 (or length of prefix)
  dp[i][j] = answer for s1[:i] and s2[:j]

COMMON PROBLEMS:
  Edit Distance (Levenshtein) — transform s1 into s2
  LCS — Longest Common Subsequence
  LIS — Longest Increasing Subsequence
  Palindrome DP — longest palindromic subsequence/substring
  Regex / Wildcard Matching
  Word Break / Concatenation
"""

# ════════════════════════════════════════════════════════════
# COMPLEXITY
# ════════════════════════════════════════════════════════════
"""
Problem                        Time      Space
──────────────────────────────────────────────
Edit Distance                  O(m×n)    O(m×n) → O(n) optimized
LCS                            O(m×n)    O(m×n) → O(n) optimized
Palindromic Subsequence        O(n²)     O(n²)
Palindromic Substring (DP)     O(n²)     O(n²)
Regex Matching                 O(m×n)    O(m×n)
Word Break                     O(n²×k)   O(n)
Distinct Subsequences          O(m×n)    O(m×n)
"""

# ════════════════════════════════════════════════════════════
# PATTERN 1: Edit Distance (Levenshtein)
# ════════════════════════════════════════════════════════════

def edit_distance(word1: str, word2: str) -> int:
    """
    Minimum operations (insert, delete, replace) to convert word1 → word2.

    dp[i][j] = edit distance of word1[:i] and word2[:j]

    if word1[i-1] == word2[j-1]:  dp[i][j] = dp[i-1][j-1]  (no op needed)
    else:
      replace: dp[i-1][j-1] + 1
      delete:  dp[i-1][j] + 1   (delete from word1)
      insert:  dp[i][j-1] + 1   (insert into word1)
      dp[i][j] = 1 + min(replace, delete, insert)
    """
    m, n = len(word1), len(word2)
    # Space-optimized: only need previous row
    dp = list(range(n + 1))   # dp[j] = edit_dist("", word2[:j])

    for i in range(1, m + 1):
        prev = dp[0]           # dp[i-1][j-1]
        dp[0] = i              # edit_dist(word1[:i], "") = i deletions
        for j in range(1, n + 1):
            temp = dp[j]
            if word1[i-1] == word2[j-1]:
                dp[j] = prev
            else:
                dp[j] = 1 + min(prev, dp[j], dp[j-1])
            prev = temp
    return dp[n]

print("Edit Distance 'horse'→'ros':", edit_distance("horse", "ros"))   # 3
print("Edit Distance 'intention'→'execution':", edit_distance("intention","execution"))  # 5


# ════════════════════════════════════════════════════════════
# PATTERN 2: Longest Common Subsequence (LCS)
# ════════════════════════════════════════════════════════════

def lcs(s1: str, s2: str) -> int:
    """
    Length of longest common subsequence (not necessarily contiguous).

    dp[i][j] = LCS of s1[:i] and s2[:j]
    if s1[i-1]==s2[j-1]: dp[i][j] = dp[i-1][j-1] + 1
    else:                 dp[i][j] = max(dp[i-1][j], dp[i][j-1])
    """
    m, n = len(s1), len(s2)
    dp = [[0]*(n+1) for _ in range(m+1)]
    for i in range(1, m+1):
        for j in range(1, n+1):
            if s1[i-1] == s2[j-1]:
                dp[i][j] = dp[i-1][j-1] + 1
            else:
                dp[i][j] = max(dp[i-1][j], dp[i][j-1])
    return dp[m][n]

def lcs_string(s1: str, s2: str) -> str:
    """Reconstruct the actual LCS string."""
    m, n = len(s1), len(s2)
    dp = [[0]*(n+1) for _ in range(m+1)]
    for i in range(1,m+1):
        for j in range(1,n+1):
            if s1[i-1]==s2[j-1]: dp[i][j]=dp[i-1][j-1]+1
            else: dp[i][j]=max(dp[i-1][j],dp[i][j-1])
    result = []
    i, j = m, n
    while i > 0 and j > 0:
        if s1[i-1]==s2[j-1]: result.append(s1[i-1]); i-=1; j-=1
        elif dp[i-1][j]>dp[i][j-1]: i-=1
        else: j-=1
    return "".join(reversed(result))

print("LCS('abcde','ace'):", lcs("abcde","ace"))     # 3
print("LCS string:", lcs_string("abcde","ace"))       # "ace"


# ════════════════════════════════════════════════════════════
# PATTERN 3: Longest Palindromic Subsequence
# ════════════════════════════════════════════════════════════

def longest_palindrome_subseq(s: str) -> int:
    """
    Longest subsequence of s that is a palindrome.
    KEY INSIGHT: LPS(s) = LCS(s, reverse(s))

    OR: dp[i][j] = LPS of s[i..j]
    if s[i]==s[j]: dp[i][j] = dp[i+1][j-1] + 2
    else:          dp[i][j] = max(dp[i+1][j], dp[i][j-1])
    """
    n = len(s)
    dp = [[0]*n for _ in range(n)]
    for i in range(n): dp[i][i] = 1   # single char

    for length in range(2, n+1):
        for i in range(n - length + 1):
            j = i + length - 1
            if s[i] == s[j]:
                dp[i][j] = dp[i+1][j-1] + 2 if length > 2 else 2
            else:
                dp[i][j] = max(dp[i+1][j], dp[i][j-1])
    return dp[0][n-1]

print("Longest palindrome subseq 'bbbab':", longest_palindrome_subseq("bbbab"))  # 4 (bbbb)


# ════════════════════════════════════════════════════════════
# PATTERN 4: Minimum Insertions to Make Palindrome
# ════════════════════════════════════════════════════════════

def min_insertions_palindrome(s: str) -> int:
    """
    Min insertions to make s a palindrome.
    = len(s) - LPS(s)
    Because non-palindrome chars need one mirror char inserted.
    """
    return len(s) - longest_palindrome_subseq(s)

print("Min insertions 'mbadm':", min_insertions_palindrome("mbadm"))  # 2


# ════════════════════════════════════════════════════════════
# PATTERN 5: Distinct Subsequences
# ════════════════════════════════════════════════════════════

def num_distinct(s: str, t: str) -> int:
    """
    Count distinct subsequences of s that equal t. (LC 115)

    dp[i][j] = # ways to form t[:j] from s[:i]
    if s[i-1]==t[j-1]: dp[i][j] = dp[i-1][j-1] + dp[i-1][j]
                        (use this match OR skip s[i-1])
    else:               dp[i][j] = dp[i-1][j]  (skip s[i-1])
    """
    m, n = len(s), len(t)
    dp = [[0]*(n+1) for _ in range(m+1)]
    for i in range(m+1): dp[i][0] = 1   # empty t always matches

    for i in range(1, m+1):
        for j in range(1, n+1):
            dp[i][j] = dp[i-1][j]
            if s[i-1] == t[j-1]:
                dp[i][j] += dp[i-1][j-1]
    return dp[m][n]

print("Distinct subseq 'rabbbit','rabbit':", num_distinct("rabbbit","rabbit"))  # 3


# ════════════════════════════════════════════════════════════
# PATTERN 6: Word Break
# ════════════════════════════════════════════════════════════

def word_break(s: str, wordDict: List[str]) -> bool:
    """
    Can s be segmented into dictionary words?
    dp[i] = True if s[:i] can be segmented.
    O(n² × k) where k = avg word length.
    """
    word_set = set(wordDict)
    n = len(s)
    dp = [False] * (n+1)
    dp[0] = True   # empty string

    for i in range(1, n+1):
        for j in range(i):
            if dp[j] and s[j:i] in word_set:
                dp[i] = True
                break
    return dp[n]

print("Word break 'leetcode':", word_break("leetcode", ["leet","code"]))    # True
print("Word break 'catsandog':", word_break("catsandog", ["cats","dog","sand","and","cat"]))  # False


# ════════════════════════════════════════════════════════════
# PATTERN 7: Regex / Wildcard Matching
# ════════════════════════════════════════════════════════════

def is_match_regex(s: str, p: str) -> bool:
    """
    LC 10: Regex matching. '.' matches any char. '*' matches 0+ of preceding.

    dp[i][j] = does s[:i] match p[:j]?
    if p[j-1]=='*':
      zero occurrences: dp[i][j-2]
      one+ occurrences: dp[i-1][j] if s[i-1] matches p[j-2]
    elif p[j-1]=='.' or p[j-1]==s[i-1]:
      dp[i][j] = dp[i-1][j-1]
    """
    m, n = len(s), len(p)
    dp = [[False]*(n+1) for _ in range(m+1)]
    dp[0][0] = True

    for j in range(1, n+1):
        if p[j-1] == '*' and j >= 2:
            dp[0][j] = dp[0][j-2]   # zero occurrences of preceding

    for i in range(1, m+1):
        for j in range(1, n+1):
            if p[j-1] == '*':
                dp[i][j] = dp[i][j-2]   # zero occurrences
                if p[j-2] == '.' or p[j-2] == s[i-1]:
                    dp[i][j] |= dp[i-1][j]  # one+ occurrences
            elif p[j-1] == '.' or p[j-1] == s[i-1]:
                dp[i][j] = dp[i-1][j-1]
    return dp[m][n]

print("Regex 'aa','a*':", is_match_regex("aa","a*"))       # True
print("Regex 'aab','c*a*b':", is_match_regex("aab","c*a*b"))  # True


# ════════════════════════════════════════════════════════════
# PATTERN 8: Shortest Common Supersequence
# ════════════════════════════════════════════════════════════

def shortest_common_superseq(s1: str, s2: str) -> str:
    """
    Shortest string containing both s1 and s2 as subsequences.
    Length = len(s1) + len(s2) - LCS(s1, s2)
    Reconstruct using LCS table.
    """
    m, n = len(s1), len(s2)
    dp = [[0]*(n+1) for _ in range(m+1)]
    for i in range(1,m+1):
        for j in range(1,n+1):
            if s1[i-1]==s2[j-1]: dp[i][j]=dp[i-1][j-1]+1
            else: dp[i][j]=max(dp[i-1][j],dp[i][j-1])

    result = []
    i, j = m, n
    while i > 0 and j > 0:
        if s1[i-1]==s2[j-1]: result.append(s1[i-1]); i-=1; j-=1
        elif dp[i-1][j]>dp[i][j-1]: result.append(s1[i-1]); i-=1
        else: result.append(s2[j-1]); j-=1
    while i>0: result.append(s1[i-1]); i-=1
    while j>0: result.append(s2[j-1]); j-=1
    return "".join(reversed(result))

print("SCS('abac','cab'):", shortest_common_superseq("abac","cab"))  # "cabac"


# ════════════════════════════════════════════════════════════
# INTERVIEW Q&A
# ════════════════════════════════════════════════════════════
"""
Q1: What is the base case for edit distance?
A: dp[i][0] = i (delete all i chars from s1 to get empty string).
   dp[0][j] = j (insert j chars into empty string to get s2[:j]).

Q2: How does LCS relate to Edit Distance?
A: Edit Distance = len(s1) + len(s2) - 2*LCS when only insertions/deletions allowed.
   With replacements: Edit Distance uses different recurrence.

Q3: What is the relation between LPS and LCS?
A: LPS(s) = LCS(s, reverse(s)).
   Because reversing s keeps all palindromic subsequences intact.

Q4: Why is Word Break O(n²×k) and how to optimize?
A: For each position i, we check all j<i if s[j:i] is in dict — O(n²).
   s[j:i] check is O(k) for string comparison.
   Optimize: use Trie to check suffixes in O(k) total. Or limit j to max_word_len.

Q5: How to handle the '*' in regex DP?
A: '*' means "zero or more of preceding element".
   Zero occurrences: dp[i][j] = dp[i][j-2] (skip pattern p[j-2] and '*').
   One+ occurrence: dp[i][j] = dp[i-1][j] if s[i-1] matches p[j-2].
   (dp[i-1][j] not dp[i-1][j-2] because '*' can match multiple chars).

Q6: Space optimization for 2D string DP?
A: Most string DP only needs previous row (dp[i-1]).
   Use 1D array and update in correct direction.
   Edit distance: O(n) space instead of O(m×n).

Q7: What is the palindrome partition problem?
A: Minimum cuts to partition s into all-palindrome substrings.
   dp[i] = min cuts for s[:i].
   Precompute isPalin[i][j] using expand-around-center or DP.

Q8: How to count palindromic substrings using DP?
A: dp[i][j] = True if s[i..j] is palindrome.
   Base: dp[i][i]=True, dp[i][i+1] = s[i]==s[i+1].
   Transition: dp[i][j] = dp[i+1][j-1] and s[i]==s[j].
   Fill diagonally (by length). Count all True cells.

Q9: Memoization vs tabulation for string DP?
A: Memoization (top-down): natural recursive formulation, only computes needed states.
   Tabulation (bottom-up): no recursion overhead, better cache performance, easier space opt.
   For string DP, tabulation is usually preferred.

Q10: What is the Interleaving String problem?
A: dp[i][j] = can s1[:i] and s2[:j] interleave to form s3[:i+j]?
   if s1[i-1]==s3[i+j-1]: dp[i][j] |= dp[i-1][j]
   if s2[j-1]==s3[i+j-1]: dp[i][j] |= dp[i][j-1]
"""
