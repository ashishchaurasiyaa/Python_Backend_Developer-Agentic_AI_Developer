"""First Unique Character in a String"""
def firstUniqChar(s):
    freq = {}
    for char in s:
        freq[char] = freq.get(char, 0) + 1
    for i, char in enumerate(s):
        if freq[char] == 1:
            return i
    return -1
s = "leetcode"
print(firstUniqChar(s))
print(firstUniqChar("loveleetcode"))
print(firstUniqChar("aabb"))
