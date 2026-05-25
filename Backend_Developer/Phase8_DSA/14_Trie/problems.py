"""
╔══════════════════════════════════════════════════════════════════╗
║                  TRIE — 8 LeetCode-Style Problems                ║
╚══════════════════════════════════════════════════════════════════╝
"""

from typing import List, Optional
from collections import defaultdict

# ─────────────────────────────────────────────
# Shared TrieNode class for all problems
# ─────────────────────────────────────────────
class TrieNode:
    def __init__(self):
        self.children = {}
        self.is_end = False
        self.count = 0    # used in some problems (Trie II)
        self.prefix_count = 0  # number of words passing through this node

# ══════════════════════════════════════════════════════════════════
# Problem 1: Implement Trie (Prefix Tree) (LC 208)
# ══════════════════════════════════════════════════════════════════
class Trie:
    """
    Implement a trie with insert, search, and startsWith.

    Example:
      insert("apple"), search("apple") → True
      search("app") → False
      startsWith("app") → True
    """
    def __init__(self):
        self.root = TrieNode()

    def insert(self, word: str) -> None:
        node = self.root
        for ch in word:
            if ch not in node.children:
                node.children[ch] = TrieNode()
            node = node.children[ch]
        node.is_end = True

    def search(self, word: str) -> bool:
        node = self.root
        for ch in word:
            if ch not in node.children:
                return False
            node = node.children[ch]
        return node.is_end

    def startsWith(self, prefix: str) -> bool:
        node = self.root
        for ch in prefix:
            if ch not in node.children:
                return False
            node = node.children[ch]
        return True

print("=== Implement Trie ===")
trie = Trie()
trie.insert("apple")
print(trie.search("apple"))    # True
print(trie.search("app"))      # False
print(trie.startsWith("app"))  # True
trie.insert("app")
print(trie.search("app"))      # True
# Time: O(m) per op | Space: O(n*m)

# ══════════════════════════════════════════════════════════════════
# Problem 2: Design Add and Search Words (LC 211)
# ══════════════════════════════════════════════════════════════════
class WordDictionary:
    """
    Supports addWord and search where '.' matches any single character.

    Approach: Trie with recursive DFS for '.' wildcards.

    Example:
      addWord("bad"), addWord("dad"), addWord("mad")
      search("pad") → False
      search("bad") → True
      search(".ad") → True
      search("b..") → True
    """
    def __init__(self):
        self.root = TrieNode()

    def addWord(self, word: str) -> None:
        node = self.root
        for ch in word:
            if ch not in node.children:
                node.children[ch] = TrieNode()
            node = node.children[ch]
        node.is_end = True

    def search(self, word: str) -> bool:
        def dfs(node, i):
            if i == len(word):
                return node.is_end
            ch = word[i]
            if ch == '.':
                return any(dfs(child, i+1) for child in node.children.values())
            if ch not in node.children:
                return False
            return dfs(node.children[ch], i+1)
        return dfs(self.root, 0)

print("\n=== Design Add and Search Words ===")
wd = WordDictionary()
wd.addWord("bad"); wd.addWord("dad"); wd.addWord("mad")
print(wd.search("pad"))  # False
print(wd.search("bad"))  # True
print(wd.search(".ad"))  # True
print(wd.search("b.."))  # True
# Time: O(m) add, O(m * 26^wildcards) search | Space: O(n*m)

# ══════════════════════════════════════════════════════════════════
# Problem 3: Word Search II (LC 212)
# ══════════════════════════════════════════════════════════════════
def findWords(board: List[List[str]], words: List[str]) -> List[str]:
    """
    Find all words from 'words' that exist in the board (word search).

    Approach: Build Trie from words. DFS on board; at each cell,
    traverse trie simultaneously. When is_end hit, record word.
    Prune trie nodes with no remaining words for speedup.

    Example:
      board=[["o","a","a","n"],["e","t","a","e"],["i","h","k","r"],["i","f","l","v"]]
      words=["oath","pea","eat","rain"] → ["eat","oath"]
    """
    # Build Trie
    root = TrieNode()
    for word in words:
        node = root
        for ch in word:
            if ch not in node.children:
                node.children[ch] = TrieNode()
            node = node.children[ch]
        node.is_end = True
        node.word = word  # store word at end node

    rows, cols = len(board), len(board[0])
    result = set()

    def dfs(r, c, node):
        ch = board[r][c]
        if ch not in node.children:
            return
        next_node = node.children[ch]
        if next_node.is_end:
            result.add(next_node.word)
            next_node.is_end = False  # avoid duplicates

        board[r][c] = '#'  # mark visited
        for dr, dc in [(0,1),(0,-1),(1,0),(-1,0)]:
            nr, nc = r+dr, c+dc
            if 0<=nr<rows and 0<=nc<cols and board[nr][nc] != '#':
                dfs(nr, nc, next_node)
        board[r][c] = ch  # restore

        # Prune empty trie node
        if not next_node.children:
            del node.children[ch]

    for r in range(rows):
        for c in range(cols):
            dfs(r, c, root)

    return list(result)

print("\n=== Word Search II ===")
board = [["o","a","a","n"],["e","t","a","e"],["i","h","k","r"],["i","f","l","v"]]
print(sorted(findWords(board, ["oath","pea","eat","rain"])))  # ['eat','oath']
# Time: O(M * 4 * 3^(L-1)) where M=cells, L=max word len | Space: O(n*L)

# ══════════════════════════════════════════════════════════════════
# Problem 4: Replace Words (LC 648)
# ══════════════════════════════════════════════════════════════════
def replaceWords(dictionary: List[str], sentence: str) -> str:
    """
    Replace each word in sentence with its shortest root from dictionary.
    If no root, keep the word.

    Approach: Build Trie from roots. For each word, traverse trie until
    we hit is_end (root found) or trie has no matching child (keep word).

    Example:
      dictionary=["cat","bat","rat"], sentence="the cattle was rattled by the battery"
      → "the cat was rat by the bat"
    """
    root = TrieNode()
    for word in dictionary:
        node = root
        for ch in word:
            if ch not in node.children:
                node.children[ch] = TrieNode()
            node = node.children[ch]
        node.is_end = True

    def find_root(word):
        node = root
        prefix = []
        for ch in word:
            if ch not in node.children:
                break
            node = node.children[ch]
            prefix.append(ch)
            if node.is_end:
                return ''.join(prefix)
        return word

    return ' '.join(find_root(w) for w in sentence.split())

print("\n=== Replace Words ===")
print(replaceWords(["cat","bat","rat"], "the cattle was rattled by the battery"))
# "the cat was rat by the bat"
# Time: O(n*m + |sentence|) | Space: O(n*m)

# ══════════════════════════════════════════════════════════════════
# Problem 5: Maximum XOR of Two Numbers (Binary Trie, LC 421)
# ══════════════════════════════════════════════════════════════════
def findMaximumXOR(nums: List[int]) -> int:
    """
    Find the maximum XOR of any two numbers in nums.

    Approach: Binary Trie. Insert all numbers bit by bit (MSB first).
    For each number, greedily traverse opposite bits to maximize XOR.

    Example:
      [3,10,5,25,2,8] → 28 (5 XOR 25 = 28)
    """
    BITS = 32
    root = {}

    # Build binary trie
    for num in nums:
        node = root
        for i in range(BITS - 1, -1, -1):
            bit = (num >> i) & 1
            if bit not in node:
                node[bit] = {}
            node = node[bit]

    max_xor = 0
    for num in nums:
        node = root
        curr_xor = 0
        for i in range(BITS - 1, -1, -1):
            bit = (num >> i) & 1
            want = 1 - bit  # try to get opposite bit for max XOR
            if want in node:
                curr_xor = (curr_xor << 1) | 1
                node = node[want]
            else:
                curr_xor = curr_xor << 1
                node = node[bit]
        max_xor = max(max_xor, curr_xor)

    return max_xor

print("\n=== Maximum XOR of Two Numbers ===")
print(findMaximumXOR([3,10,5,25,2,8]))  # 28
print(findMaximumXOR([14,70,53,83,49,91,36,80,92,51,66,70]))  # 127
# Time: O(n * BITS) | Space: O(n * BITS)

# ══════════════════════════════════════════════════════════════════
# Problem 6: Implement Trie II (LC 1804)
# ══════════════════════════════════════════════════════════════════
class Trie2:
    """
    Trie II supports:
    - insert(word): insert word
    - countWordsEqualTo(word): count exact occurrences
    - countWordsStartingWith(prefix): count words with this prefix
    - erase(word): remove one occurrence

    Track: count (exact) and prefix_count at each node.
    """
    def __init__(self):
        self.root = TrieNode()

    def insert(self, word: str) -> None:
        node = self.root
        for ch in word:
            if ch not in node.children:
                node.children[ch] = TrieNode()
            node = node.children[ch]
            node.prefix_count += 1
        node.count += 1

    def countWordsEqualTo(self, word: str) -> int:
        node = self.root
        for ch in word:
            if ch not in node.children:
                return 0
            node = node.children[ch]
        return node.count

    def countWordsStartingWith(self, prefix: str) -> int:
        node = self.root
        for ch in prefix:
            if ch not in node.children:
                return 0
            node = node.children[ch]
        return node.prefix_count

    def erase(self, word: str) -> None:
        node = self.root
        for ch in word:
            node = node.children[ch]
            node.prefix_count -= 1
        node.count -= 1

print("\n=== Implement Trie II ===")
t2 = Trie2()
t2.insert("apple"); t2.insert("apple"); t2.insert("app")
print(t2.countWordsEqualTo("apple"))        # 2
print(t2.countWordsStartingWith("app"))     # 3
t2.erase("apple")
print(t2.countWordsEqualTo("apple"))        # 1
print(t2.countWordsStartingWith("app"))     # 2
# Time: O(m) per op | Space: O(n*m)

# ══════════════════════════════════════════════════════════════════
# Problem 7: Longest Word in Dictionary (LC 720)
# ══════════════════════════════════════════════════════════════════
def longestWord(words: List[str]) -> str:
    """
    Find the longest word in words that can be built one character at a time
    (each prefix must also be in words). Return lexicographically smallest
    if there are ties.

    Approach: Build Trie. BFS/DFS only through nodes where is_end=True.
    (Every node on path must mark a valid word.)

    Example:
      ["w","wo","wor","word","world"] → "world"
      ["a","banana","app","appl","ap","apply","apple"] → "apple"
    """
    # Insert all words
    root = TrieNode()
    for word in words:
        node = root
        for ch in word:
            if ch not in node.children:
                node.children[ch] = TrieNode()
            node = node.children[ch]
        node.is_end = True
        node.word = word

    result = ""
    # BFS from root, only traversing through is_end nodes
    from collections import deque
    queue = deque([root])
    while queue:
        node = queue.popleft()
        for ch in sorted(node.children.keys(), reverse=True):  # reverse so best is explored last→remains in result
            child = node.children[ch]
            if child.is_end:
                if len(child.word) > len(result) or \
                   (len(child.word) == len(result) and child.word < result):
                    result = child.word
                queue.append(child)
    return result

print("\n=== Longest Word in Dictionary ===")
print(longestWord(["w","wo","wor","word","world"]))                           # "world"
print(longestWord(["a","banana","app","appl","ap","apply","apple"]))          # "apple"
# Time: O(n*m) | Space: O(n*m)

# ══════════════════════════════════════════════════════════════════
# Problem 8: Palindrome Pairs (LC 336)
# ══════════════════════════════════════════════════════════════════
def palindromePairs(words: List[str]) -> List[List[int]]:
    """
    Find all pairs (i, j) where words[i] + words[j] is a palindrome.

    Approach: For each word, check:
    1. Reverse of word exists in dict → pair
    2. Any prefix of word is palindrome AND reverse of suffix exists
    3. Any suffix of word is palindrome AND reverse of prefix exists

    Example:
      ["abcd","dcba","lls","s","sssll"] → [[0,1],[1,0],[3,2],[2,4]]
    """
    def is_palindrome(s, lo, hi):
        while lo < hi:
            if s[lo] != s[hi]: return False
            lo += 1; hi -= 1
        return True

    word_map = {w: i for i, w in enumerate(words)}
    result = []

    for i, word in enumerate(words):
        n = len(word)
        rev = word[::-1]

        # Case 1: reverse of the whole word exists (and it's different)
        if rev in word_map and word_map[rev] != i:
            result.append([i, word_map[rev]])

        # Case 2: prefix is palindrome, reverse of suffix exists
        for k in range(1, n):
            if is_palindrome(word, 0, k-1):
                suffix_rev = word[k:][::-1]
                if suffix_rev in word_map:
                    result.append([word_map[suffix_rev], i])

        # Case 3: suffix is palindrome, reverse of prefix exists
        for k in range(1, n):
            if is_palindrome(word, k, n-1):
                prefix_rev = word[:k][::-1]
                if prefix_rev in word_map:
                    result.append([i, word_map[prefix_rev]])

    return result

print("\n=== Palindrome Pairs ===")
print(sorted(palindromePairs(["abcd","dcba","lls","s","sssll"])))
# [[0,1],[1,0],[2,4],[3,2]]
print(sorted(palindromePairs(["bat","tab","cat"])))
# [[0,1],[1,0]]
# Time: O(n * m²) | Space: O(n * m)

print("\n✓ All 8 Trie problems solved!")
