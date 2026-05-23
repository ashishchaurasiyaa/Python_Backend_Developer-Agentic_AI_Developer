"""
02 — Strings — Theory
======================
Level: Basic → Intermediate
"""

# ════════════════════════════════════════════════════════════
# WHAT & WHY
# ════════════════════════════════════════════════════════════
"""
String = immutable sequence of characters in Python.
         Stored as array of Unicode code points.

WHY immutable? Thread-safe, hashable (can be dict key), interning optimization.
Consequence: every string operation (concat, replace) creates a NEW string.
"""

# ════════════════════════════════════════════════════════════
# COMPLEXITY
# ════════════════════════════════════════════════════════════
"""
Operation              Time       Note
─────────────────────────────────────────
s[i]                   O(1)       index
len(s)                 O(1)       cached
s + t                  O(n+m)     creates new string
s * n                  O(n·k)     creates new string
"".join(list)          O(n)       preferred for concat
s in t                 O(n·m)     naive; KMP = O(n+m)
s.find(t)              O(n·m)     naive substring search
s.replace(a, b)        O(n)
s.split(sep)           O(n)
s.strip()              O(n)
s[::-1]                O(n)       reverse
"""

# ════════════════════════════════════════════════════════════
# ESSENTIAL STRING METHODS
# ════════════════════════════════════════════════════════════

s = "  Hello, World!  "
print(s.strip())            # "Hello, World!"
print(s.lower())            # "  hello, world!  "
print(s.upper())            # "  HELLO, WORLD!  "
print(s.split(","))         # ["  Hello", " World!  "]
print("hello".capitalize()) # "Hello"
print("hello world".title()) # "Hello World"
print("abc".center(7, "-")) # "--abc--"
print("hello".replace("l","r")) # "herro"
print("hello".startswith("he")) # True
print("hello".endswith("lo"))   # True
print("hello world".find("world"))  # 6 (index)
print("hello world".count("l"))     # 3

# String building — ALWAYS use join, not +=
words = ["Hello", "World", "Python"]
bad   = ""
for w in words:
    bad += w + " "          # O(n²) — creates new string each time!

good  = " ".join(words)     # O(n) — single allocation

# ════════════════════════════════════════════════════════════
# CHARACTER OPERATIONS
# ════════════════════════════════════════════════════════════

print(ord('A'))     # 65  — char to ASCII
print(chr(65))      # 'A' — ASCII to char
print(ord('a') - ord('A'))  # 32 — case difference

# All alphabets
import string
print(string.ascii_lowercase)  # abcdefghijklmnopqrstuvwxyz
print(string.ascii_uppercase)  # ABCDEFGHIJKLMNOPQRSTUVWXYZ
print(string.digits)           # 0123456789

# Character checks
print('A'.isalpha())     # True
print('3'.isdigit())     # True
print('A3'.isalnum())    # True
print(' '.isspace())     # True
print('Hello'.isupper()) # False
print('hello'.islower()) # True

# ════════════════════════════════════════════════════════════
# KEY PATTERNS
# ════════════════════════════════════════════════════════════

# PATTERN 1: Two Pointers (palindrome, reverse)
def is_palindrome(s: str) -> bool:
    left, right = 0, len(s) - 1
    while left < right:
        if s[left] != s[right]:
            return False
        left  += 1
        right -= 1
    return True

# PATTERN 2: Sliding Window (substring problems)
def longest_unique_substring(s: str) -> int:
    """Max length substring without repeating characters."""
    char_idx = {}
    left = max_len = 0
    for right, c in enumerate(s):
        if c in char_idx and char_idx[c] >= left:
            left = char_idx[c] + 1
        char_idx[c] = right
        max_len = max(max_len, right - left + 1)
    return max_len

# PATTERN 3: Character frequency (anagram, permutation)
from collections import Counter

def is_anagram(s, t):
    return Counter(s) == Counter(t)

# PATTERN 4: KMP (Knuth-Morris-Pratt) — efficient substring search O(n+m)
def kmp_search(text: str, pattern: str) -> list[int]:
    """Return all start indices of pattern in text."""
    if not pattern: return []

    # Build failure function
    m   = len(pattern)
    lps = [0] * m
    j   = 0
    for i in range(1, m):
        while j > 0 and pattern[i] != pattern[j]:
            j = lps[j - 1]
        if pattern[i] == pattern[j]:
            j += 1
        lps[i] = j

    # Search
    result, j = [], 0
    for i, c in enumerate(text):
        while j > 0 and c != pattern[j]:
            j = lps[j - 1]
        if c == pattern[j]:
            j += 1
        if j == m:
            result.append(i - m + 1)
            j = lps[j - 1]
    return result

print(kmp_search("AABAACAADAABAABA", "AABA"))  # [0, 9, 12]

# PATTERN 5: String hashing / Rabin-Karp (rolling hash)
def rabin_karp(text: str, pattern: str) -> list[int]:
    """O(n+m) average substring search using rolling hash."""
    n, m = len(text), len(pattern)
    if m > n: return []

    BASE, MOD = 31, 10**9 + 9

    def char_val(c): return ord(c) - ord('a') + 1

    pattern_hash = 0
    window_hash  = 0
    power = 1

    for i in range(m):
        pattern_hash = (pattern_hash + char_val(pattern[i]) * power) % MOD
        window_hash  = (window_hash  + char_val(text[i])    * power) % MOD
        if i < m - 1:
            power = (power * BASE) % MOD

    result = []
    for i in range(n - m + 1):
        if window_hash == pattern_hash and text[i:i+m] == pattern:
            result.append(i)
        if i < n - m:
            window_hash = (window_hash - char_val(text[i]) + MOD) % MOD
            window_hash = (window_hash * pow(BASE, MOD - 2, MOD)) % MOD
            window_hash = (window_hash + char_val(text[i+m]) * power) % MOD
    return result

# ════════════════════════════════════════════════════════════
# INTERVIEW Q&A
# ════════════════════════════════════════════════════════════
"""
Q: Why is string concatenation with += O(n²)?
A: Each += creates a new string object copying all previous chars.
   For n concatenations of 1-char strings: 1+2+3+...+n = O(n²).
   Fix: collect in list, join at end.

Q: How to reverse a string in Python?
A: s[::-1]  — slicing with step -1. O(n).

Q: Difference between s.find() and s.index()?
A: find() returns -1 if not found. index() raises ValueError.

Q: What is string interning?
A: Python caches small strings (identifiers, short strings) in memory.
   s1 = "hello"; s2 = "hello" → (s1 is s2) may be True (same object).
   Not guaranteed for all strings.

Q: How to check if string has only digits?
A: s.isdigit()  or  s.isnumeric()  or  bool(re.fullmatch(r'\d+', s))
"""
