"""
class Stack:
    # push(item)   → top pe add
    # pop()        → top se remove + return
    # peek()       → top dekho, remove mat karo
    # is_empty()   → True/False
    # size()       → kitne items
"""

class Stack:
    def __init__(self):
        self.items = []

    def push(self, item):
        self.items.append(item)

    def pop(self):
        return self.items.pop()

    def peek(self):
        return self.items[-1]

    def is_empty(self):
        return self.items == []

    def size(self):
        return len(self.items)

s = Stack()
s.push(1)
s.push(2)
s.push(3)
print(s.peek())
s.pop()
print(s.peek())
print(s.is_empty())
print(s.size())
print(s.items)