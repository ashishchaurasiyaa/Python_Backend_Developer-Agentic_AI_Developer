"""
02 — Strings — Problems
========================
Problems: 12  |  Level: Easy → Medium
"""
from collections import Counter, defaultdict
from typing import List

# ─────────────────────────────────────────────
# P01. Valid Palindrome  [Easy] [LC 125]
# ─────────────────────────────────────────────
"""Only alphanumeric chars, case-insensitive."""
def isPalindrome(s: str) -> bool:
    cleaned = [c.lower() for c in s if c.isalnum()]
    return cleaned == cleaned[::-1]

# Two-pointer (no extra space)
def isPalindrome_v2(s: str) -> bool:
    l, r = 0, len(s) - 1
    while l < r:
        while l < r and not s[l].isalnum(): l += 1
        while l < r and not s[r].isalnum(): r -= 1
        if s[l].lower() != s[r].lower(): return False
        l += 1; r -= 1
    return True

print("P01:", isPalindrome("A man, a plan, a canal: Panama"))  # True


# ─────────────────────────────────────────────
# P02. Longest Substring Without Repeating  [Medium] [LC 3]
# ─────────────────────────────────────────────
def lengthOfLongestSubstring(s: str) -> int:
    char_idx = {}
    left = result = 0
    for right, c in enumerate(s):
        if c in char_idx and char_idx[c] >= left:
            left = char_idx[c] + 1
        char_idx[c] = right
        result = max(result, right - left + 1)
    return result

print("P02:", lengthOfLongestSubstring("abcabcbb"))  # 3


# ─────────────────────────────────────────────
# P03. Longest Repeating Character Replacement  [Medium] [LC 424]
# ─────────────────────────────────────────────
"""
Replace at most k chars → find longest substring with same char.
Input: s="AABABBA", k=1  Output: 4
"""
def characterReplacement(s: str, k: int) -> int:
    count = defaultdict(int)
    left = max_count = result = 0
    for right, c in enumerate(s):
        count[c]  += 1
        max_count  = max(max_count, count[c])
        # window size - most frequent char > k → shrink
        if (right - left + 1) - max_count > k:
            count[s[left]] -= 1
            left += 1
        result = max(result, right - left + 1)
    return result

print("P03:", characterReplacement("AABABBA", 1))  # 4


# ─────────────────────────────────────────────
# P04. Minimum Window Substring  [Hard] [LC 76]
# ─────────────────────────────────────────────
"""
Smallest window in s that contains all chars of t.
Input: s="ADOBECODEBANC", t="ABC"  Output: "BANC"
"""
def minWindow(s: str, t: str) -> str:
    if not t or not s: return ""
    need   = Counter(t)
    window = defaultdict(int)
    have, total = 0, len(need)
    left = 0
    best = (float('inf'), 0, 0)

    for right, c in enumerate(s):
        window[c] += 1
        if c in need and window[c] == need[c]:
            have += 1
        while have == total:
            if right - left + 1 < best[0]:
                best = (right - left + 1, left, right)
            window[s[left]] -= 1
            if s[left] in need and window[s[left]] < need[s[left]]:
                have -= 1
            left += 1
    return s[best[1]:best[2]+1] if best[0] != float('inf') else ""

print("P04:", minWindow("ADOBECODEBANC", "ABC"))  # "BANC"


# ─────────────────────────────────────────────
# P05. Longest Palindromic Substring  [Medium] [LC 5]
# ─────────────────────────────────────────────
"""Expand around center approach: O(n²) time, O(1) space."""
def longestPalindrome(s: str) -> str:
    start = length = 0

    def expand(l, r):
        while l >= 0 and r < len(s) and s[l] == s[r]:
            l -= 1; r += 1
        return l + 1, r - l - 1   # start, length

    for i in range(len(s)):
        for l, r in [(i, i), (i, i+1)]:   # odd and even centers
            st, ln = expand(l, r)
            if ln > length:
                start, length = st, ln

    return s[start:start+length]

print("P05:", longestPalindrome("babad"))  # "bab"


# ─────────────────────────────────────────────
# P06. Palindromic Substrings Count  [Medium] [LC 647]
# ─────────────────────────────────────────────
"""Count all palindromic substrings."""
def countSubstrings(s: str) -> int:
    count = 0
    for i in range(len(s)):
        for l, r in [(i, i), (i, i+1)]:
            while l >= 0 and r < len(s) and s[l] == s[r]:
                count += 1
                l -= 1; r += 1
    return count

print("P06:", countSubstrings("aaa"))  # 6


# ─────────────────────────────────────────────
# P07. String to Integer (atoi)  [Medium] [LC 8]
# ─────────────────────────────────────────────
def myAtoi(s: str) -> int:
    s   = s.lstrip()
    if not s: return 0
    sign  = -1 if s[0] == '-' else 1
    s     = s[1:] if s[0] in '+-' else s
    num   = 0
    for c in s:
        if not c.isdigit(): break
        num = num * 10 + int(c)
    num *= sign
    INT_MIN, INT_MAX = -2**31, 2**31 - 1
    return max(INT_MIN, min(INT_MAX, num))

print("P07:", myAtoi("   -42"))  # -42


# ─────────────────────────────────────────────
# P08. Count and Say  [Medium] [LC 38]
# ─────────────────────────────────────────────
"""
1 → "1"
2 → "11"  (one 1)
3 → "21"  (two 1s)
4 → "1211" (one 2, one 1)
"""
def countAndSay(n: int) -> str:
    s = "1"
    for _ in range(n - 1):
        result = []
        i = 0
        while i < len(s):
            count = 1
            while i + count < len(s) and s[i+count] == s[i]:
                count += 1
            result.append(f"{count}{s[i]}")
            i += count
        s = "".join(result)
    return s

print("P08:", countAndSay(4))  # "1211"


# ─────────────────────────────────────────────
# P09. Reverse Words in String  [Medium] [LC 151]
# ─────────────────────────────────────────────
def reverseWords(s: str) -> str:
    return " ".join(reversed(s.split()))

print("P09:", reverseWords("  the sky   is blue  "))  # "blue is sky the"


# ─────────────────────────────────────────────
# P10. Find All Anagrams  [Medium] [LC 438]
# ─────────────────────────────────────────────
"""Return start indices of all anagrams of p in s."""
def findAnagrams(s: str, p: str) -> List[int]:
    need   = Counter(p)
    window = Counter(s[:len(p)])
    result = [0] if window == need else []

    for i in range(len(p), len(s)):
        window[s[i]] += 1
        left = s[i - len(p)]
        window[left] -= 1
        if window[left] == 0:
            del window[left]
        if window == need:
            result.append(i - len(p) + 1)
    return result

print("P10:", findAnagrams("cbaebabacd", "abc"))  # [0, 6]


# ─────────────────────────────────────────────
# P11. Zigzag Conversion  [Medium] [LC 6]
# ─────────────────────────────────────────────
"""
"PAYPALISHIRING" with numRows=3:
P   A   H   N
A P L S I I G
Y   I   R
→ "PAHNAPLSIIGYIR"
"""
def convert(s: str, numRows: int) -> str:
    if numRows == 1 or numRows >= len(s): return s
    rows = [""] * numRows
    row, direction = 0, 1
    for c in s:
        rows[row] += c
        if row == 0: direction = 1
        elif row == numRows - 1: direction = -1
        row += direction
    return "".join(rows)

print("P11:", convert("PAYPALISHIRING", 3))  # "PAHNAPLSIIGYIR"


# ─────────────────────────────────────────────
# P12. Roman to Integer  [Easy] [LC 13]
# ─────────────────────────────────────────────
def romanToInt(s: str) -> int:
    values = {'I':1,'V':5,'X':10,'L':50,'C':100,'D':500,'M':1000}
    total  = 0
    for i in range(len(s)):
        if i + 1 < len(s) and values[s[i]] < values[s[i+1]]:
            total -= values[s[i]]
        else:
            total += values[s[i]]
    return total

print("P12:", romanToInt("MCMXCIV"))  # 1994


# ─────────────────────────────────────────────
# COMPLEXITY SUMMARY
# ─────────────────────────────────────────────
"""
Problem                            Time      Space   Pattern
────────────────────────────────────────────────────────────
Valid Palindrome                   O(n)      O(1)    Two pointers
Longest Substring No Repeat        O(n)      O(1)    Sliding window
Longest Repeating Replacement      O(n)      O(1)    Sliding window
Minimum Window Substring           O(n+m)    O(m)    Sliding window
Longest Palindromic Substring      O(n²)     O(1)    Expand center
Count Palindromic Substrings       O(n²)     O(1)    Expand center
String to Integer                  O(n)      O(1)    Parsing
Reverse Words                      O(n)      O(n)    Split + reverse
Find All Anagrams                  O(n)      O(1)    Fixed window
Zigzag Conversion                  O(n)      O(n)    Simulation
Roman to Integer                   O(n)      O(1)    Hash map
"""
