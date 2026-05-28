lis = ["Ashish", "Rahul", "Ashish", "Priya", "Rahul"]
print(lis)
print(len(lis))
print(set(lis))

names = {"Ashish", "Rahul", "Ashish", "Priya"}
print(names)
print(len(names))

t1 = (1, 2, 3)
t2 = 1, 2, 3
t3 = (42,)
t4 = tuple([1, 2, 3])

wrong = (42)
print(type(wrong))

# Indexing + Slicing (list jaisa)

t = (10, 20, 30, 40, 50)
print(t[0])
print(t[-1])
print(t[1:3])
print(t[::-1])


# Unpacking (Most important)
t = (10, 20, 30)
a, b, c = t
print(a, b, c)

# star unpacking
first, *rest = (1, 2, 3, 4, 5)
print(first, rest)

# swap karna
x, y = 10, 20
x, y = y, x
print(x, y)

# Tuple methods (sirf 2 hain):
t = (1, 2, 3, 2, 4, 2)
print(t.count(2))
print(t.index(3))

# Tuple vs List — kab use karein?
# # 1. Data fix hai (coordinates, RGB colors)
point = (10, 20)
color = (255, 0, 128)

# # 2. Dictionary key banana ho
locations = {(28.6, 77.2): "Delhi", (19.0, 72.8): "Mumbai"}

#3. Function se multiple values return karo

def min_max(nums):
    return min(nums), max(nums)

low, high = min_max([1, 2, 3, 4, 5])
print(low, high)


s = {1, 2, 3, 3, 2, 1}
print(s)

# IMPORTANT: Empty set banana

empty = set()
wrong = {}

# Set Operations (yahi important hai):

a = {1, 2, 3, 4, 5}
b = {3, 4, 5, 6, 7}

#union - done ke sath
print(a | b)
print(a.union(b))

#intersection - done ke sath
print(a & b)
print(a.intersection(b))

# difference - a mein hai, b mein nahi
print(a -b)
print(a.difference(b))

#Symmetric Difference - dono mein se uncommon
print(a ^ b)
print(a.symmetric_difference(b))

# Set Methods

s = {1, 2, 3}
s.add(4)
s.update([5, 6])
s.remove(3)
s.discard(99)

print(3 in s)
print(len(s))

# Real use cases:
# # 1. Duplicates hatana — FASTEST way

arr = [1, 1, 2, 3, 3, 4]
unique = list(set(arr))
print(unique)

#2 Common friends dhundna

friends_A = {"Ram", "Shyam", "Mohan"}
friends_B = {"Ram", "Shyam", "Ashish", "Rahul", "Priya"}
common = friends_A & friends_B
print(common)

#3 Fast lookup - O(1)

vaild_users = {"alice", "bob", "charlie"}

user = "alice"
if user in vaild_users:
    print("Welcome back!")

