"""
╔══════════════════════════════════════════════════════════════════╗
║                  TRIE — Complete Theory Guide                    ║
╚══════════════════════════════════════════════════════════════════╝

WHAT IS A TRIE?
────────────────
A Trie (Prefix Tree) is a tree-like data structure where each node
represents a character. Strings are stored by sharing common prefixes.

"trie" comes from re-TRIE-val.

STRUCTURE:
  - Root: empty node
  - Each path from root to a marked node = a stored word
  - Children are often stored in a dict (or array of 26 for lowercase alpha)
  - Nodes marked with is_end=True indicate a complete word

WHY TRIE?
──────────
Hash Map: stores exact strings, no prefix sharing, no ordering.
Trie: supports PREFIX operations efficiently.
  - Does "pre" start any stored word? → startsWith("pre")
  - Find all words with prefix "pre" → traverse subtree
  - Autocomplete, spell check, IP routing, pattern matching

COMPLEXITY TABLE
─────────────────────────────────────────────────────────────────
Operation          Time      Space   Note
─────────────────────────────────────────────────────────────────
insert(word)       O(m)      O(m)    m = word length
search(word)       O(m)      O(1)    exact search
startsWith(prefix) O(m)      O(1)    prefix search
delete(word)       O(m)      O(1)    marks is_end=False
Build trie (n words) O(n*m) O(n*m) total chars
─────────────────────────────────────────────────────────────────

APPLICATIONS:
  1. Autocomplete / Type-ahead search
  2. Spell checker
  3. IP routing (longest prefix match)
  4. Word games (Boggle, Scrabble)
  5. DNA sequence search
  6. Compiler lexical analysis
"""

from typing import Optional

# ─────────────────────────────────────────────
# 1. TRIE NODE AND TRIE CLASS
# ─────────────────────────────────────────────
print("=" * 60)
print("1. TRIE IMPLEMENTATION")
print("=" * 60)

class TrieNode:
    """A single node in the Trie."""
    def __init__(self):
        self.children = {}   # char → TrieNode
        self.is_end = False  # True if this node marks end of a word

class Trie:
    """
    Standard Trie supporting insert, search, startsWith.
    Space: O(alphabet_size × n × m) worst case.
    """
    def __init__(self):
        self.root = TrieNode()

    def insert(self, word: str) -> None:
        """Insert a word into the trie. O(m)."""
        node = self.root
        for ch in word:
            if ch not in node.children:
                node.children[ch] = TrieNode()
            node = node.children[ch]
        node.is_end = True

    def search(self, word: str) -> bool:
        """Search for exact word. Returns True if found. O(m)."""
        node = self.root
        for ch in word:
            if ch not in node.children:
                return False
            node = node.children[ch]
        return node.is_end

    def startsWith(self, prefix: str) -> bool:
        """Returns True if any word starts with prefix. O(m)."""
        node = self.root
        for ch in prefix:
            if ch not in node.children:
                return False
            node = node.children[ch]
        return True

    def get_prefix_node(self, prefix: str) -> Optional[TrieNode]:
        """Navigate to the node at end of prefix. Returns None if not found."""
        node = self.root
        for ch in prefix:
            if ch not in node.children:
                return None
            node = node.children[ch]
        return node

    def autocomplete(self, prefix: str):
        """Return all words with given prefix."""
        node = self.get_prefix_node(prefix)
        if not node:
            return []
        results = []
        def dfs(node, current):
            if node.is_end:
                results.append(prefix[:len(prefix)-len(current)] + current)
            for ch, child in node.children.items():
                dfs(child, current + ch)
        # Slight fix: build from node with prefix already consumed
        results_clean = []
        def dfs2(node, current):
            if node.is_end:
                results_clean.append(current)
            for ch, child in node.children.items():
                dfs2(child, current + ch)
        dfs2(node, prefix)
        return results_clean

# Demo
print("=== Basic Trie Operations ===")
trie = Trie()
words = ["apple", "app", "application", "apt", "bat", "ball"]
for w in words:
    trie.insert(w)

print(f"search('app'):     {trie.search('app')}")         # True
print(f"search('ap'):      {trie.search('ap')}")          # False
print(f"search('apple'):   {trie.search('apple')}")       # True
print(f"startsWith('ap'):  {trie.startsWith('ap')}")      # True
print(f"startsWith('cat'): {trie.startsWith('cat')}")     # False
print(f"autocomplete('ap'): {trie.autocomplete('ap')}")   # ['app', 'apple', 'application', 'apt']

# ─────────────────────────────────────────────
# 2. TRIE WITH WILDCARDS (LC 211)
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("2. TRIE WITH WILDCARDS ('.' matches any char)")
print("=" * 60)

class WordDictionary:
    """
    Design a data structure supporting:
    - addWord(word): add word
    - search(word): '.' matches any single character
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

wd = WordDictionary()
wd.addWord("bad"); wd.addWord("dad"); wd.addWord("mad")
print(f"search('pad'): {wd.search('pad')}")  # False
print(f"search('bad'): {wd.search('bad')}")  # True
print(f"search('.ad'): {wd.search('.ad')}")  # True
print(f"search('b..'): {wd.search('b..')}")  # True

# ─────────────────────────────────────────────
# 3. BINARY TRIE (for XOR problems)
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("3. BINARY TRIE — Maximum XOR")
print("=" * 60)

"""
A Binary Trie stores binary representations of numbers.
Each node has children '0' and '1'.
Used for: Maximum XOR of two numbers.

Approach for max XOR:
  Insert all numbers. For each number, greedily traverse opposite bit
  (1 if we have 0, 0 if we have 1) to maximize XOR.
"""

class BinaryTrieNode:
    def __init__(self):
        self.children = {}

class BinaryTrie:
    def __init__(self):
        self.root = BinaryTrieNode()

    def insert(self, num: int, bits: int = 32) -> None:
        node = self.root
        for i in range(bits - 1, -1, -1):
            bit = (num >> i) & 1
            if bit not in node.children:
                node.children[bit] = BinaryTrieNode()
            node = node.children[bit]

    def max_xor(self, num: int, bits: int = 32) -> int:
        """Find maximum XOR of num with any number in the trie."""
        node = self.root
        xor = 0
        for i in range(bits - 1, -1, -1):
            bit = (num >> i) & 1
            want = 1 - bit  # want opposite bit for max XOR
            if want in node.children:
                xor = (xor << 1) | 1
                node = node.children[want]
            else:
                xor = xor << 1
                node = node.children[bit]
        return xor

bt = BinaryTrie()
nums = [3, 10, 5, 25, 2, 8]
for n in nums:
    bt.insert(n)
print(f"Max XOR in {nums}: {max(bt.max_xor(n) for n in nums)}")  # 28 (5 XOR 25)

# ─────────────────────────────────────────────
# 4. TRIE vs HASH SET vs SORTED LIST
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("4. TRIE vs ALTERNATIVES")
print("=" * 60)

comparison = """
OPERATION              TRIE        HASH SET    SORTED LIST
─────────────────────────────────────────────────────────
Exact search           O(m)        O(m) avg    O(m log n)
Prefix check           O(m)        O(n*m)      O(m log n)
All words with prefix  O(m + k)    O(n)        O(m log n + k)
Count words with prefix O(m + k)   O(n)        O(m log n)
Ordered iteration      O(n*m)      N/A         O(n*m)
Space                  O(n*m)      O(n*m)      O(n*m)
─────────────────────────────────────────────────────────
m = avg word length, n = number of words, k = results

WHEN TO USE TRIE:
✓ Prefix operations needed (autocomplete, IP routing)
✓ Multiple prefix queries (amortize build cost O(n*m) over many queries)
✓ Words share many common prefixes (space efficient)

WHEN TO USE HASH SET:
✓ Only exact lookups (no prefix)
✓ Simpler code, similar time complexity

WHEN TO USE SORTED LIST (bisect):
✓ Prefix queries occasionally (don't need fast repeated prefix search)
✓ Also need sorted order for other reasons
"""
print(comparison)

# ─────────────────────────────────────────────
# 5. INTERVIEW Q&A
# ─────────────────────────────────────────────
print("=" * 60)
print("INTERVIEW Q&A")
print("=" * 60)

qa = """
Q1: When would you use a Trie over a hash map?
A1: When you need PREFIX operations: autocomplete, startsWith, longest
    common prefix. Hash maps only do exact matches.

Q2: What's the space complexity of a Trie?
A2: O(alphabet_size × n × m) worst case, where n = number of words and
    m = average word length. For lowercase English, 26 pointers per node.
    Using dict instead of array saves space for sparse alphabets.

Q3: How do you delete a word from a Trie?
A3: Mark is_end = False at the last character. Optionally, if a node has
    no children and is_end is False, prune it (recursively).

Q4: How would you find the longest common prefix of a set of strings?
A4: Insert all strings into a Trie. Traverse the root — follow any path
    where there's exactly one child and is_end is False. Stop when:
    - A node has multiple children (prefix forks), or
    - is_end is True (a word ends here), or
    - No more nodes.

Q5: How do you implement autocomplete with Trie?
A5: Build the Trie from all words. For a query prefix:
    1. Navigate to the prefix's last node.
    2. DFS from that node, collecting all words (paths to is_end nodes).
    Use BFS if you want results ordered by some priority.

Q6: What is a compressed Trie (Patricia Trie / Radix Tree)?
A6: Chains of single-child nodes are merged into one edge with a string label.
    Reduces space for sparse tries. Used in Linux kernel for routing tables.
    Standard Trie can use O(n*m) space; Patricia Trie uses O(n) nodes.

Q7: How does a Trie support sorting?
A7: DFS in alphabetical order (since children are typically stored sorted).
    DFS gives all words in lexicographic order in O(n*m) time.
"""
print(qa)
