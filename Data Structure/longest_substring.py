# Problem: Find the length of the longest substring without repeating characters.

def longest_substring(s):
    longest = 0
    seen = {}
    start = 0
    for i in range(len(s)):
        if s[i] in seen:
            start = max(start, seen[s[i]] + 1)
        seen[s[i]] = i
        longest = max(longest, i - start + 1)
    return longest
s = "abcabcbb"
print(longest_substring(s))

# don't use max and min

def longest_substring(s):
    longest = 0
    seen = {}
    start = 0
    for i in range(len(s)):
        if s[i] in seen:
            start = seen[s[i]] + 1 if seen[s[i]] + 1 > start else start
        seen[s[i]] = i
        longest = i - start + 1 if i - start + 1 > longest else longest
    return longest
s = "abcabcbb"
print(longest_substring(s))