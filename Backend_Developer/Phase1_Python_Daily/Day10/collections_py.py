"""
# Q4 — collections use karo
# Ek paragraph text do
# Top 5 most frequent words nikalo
# Word length distribution nikalo (defaultdict)
# Last 5 words deque mein rakhho
"""

import collections

s = ("Iterable vs Iterator vs Generator:\n\nIterable: An object that can be looped over."
     "It has an __iter__() method that returns an iterator. Examples include list, tuple, string, set, and dictionary."
     "Iterator: An object that returns one item at a time using next(). It has both __iter__() and __next__() methods."
     "When elements are exhausted, it raises StopIteration.\n\nGenerator: A special type of iterator created using the yield keyword."
     "It provides lazy evaluation and is memory efficient because it generates values on the fly instead of storing them."
     "Key Rules: Every generator is an iterator, but not every iterator is a generator."
     "Generator vs Iterator: Iterator requires manual class implementation and state management,"
     "while a generator automatically manages state using yield and requires less code."
     "Generator Pipeline: This demonstrates lazy evaluation where each transformation is applied step-by-step without storing intermediate results,"
     "making it memory efficient.\n\nReal-world analogy: Iterable = Warehouse (full data stored), Iterator = Worker (fetches one item at a time), "
     "Generator = Machine (produces items on demand)."
     "Important: Generators are single-use iterators. Once consumed, they cannot be reused because they don’t store data — they generate it on the fly."
     "To reuse a generator, it must be recreated.")

words = s.split()
word_count = collections.Counter(words)
print(word_count.most_common(5))
word_length_dist = collections.defaultdict(int)
for word in words:
    word_length_dist[len(word)] += 1
print(word_length_dist)
last_five = collections.deque(words, maxlen=5)
print(last_five)
