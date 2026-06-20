# import sys
# import copy
# import time
# x = 42
# y = x
# print(f"x id: {id(x)}, y id: {id(y)}, same? {x is y}")
#
#
# #Mutable vs Immutable
#
# a = [1,2,3]
# b = a
# b.append(4)
# print(f"a = {a}")
#
# c = "hello"
# d = c
# d = d + " word"
# print(f"c = {c}")
#
# x = 256
# y = 256
# print(f"\nint caching: {x is y}")
# x = 257
# y = 257
# print(f"Large int: {x is y}")
#
# s1 = "hello"
# s2 = "hello"
# print(f"str interning: {s1 is s2}")
#
# print(f"bool is int: {isinstance(True, int)}")
# print(f"True + True = {True + True}")
# print(f"True * 5 = {True * 5}")
#
# falsy = [False, None, 0, 0.0, 0j, "", [], {}, set(), ()]
# print(f"\nFalsy values count: {len(falsy)}")
# print(f"All falsy: {all(not v for v in falsy)}")
#
# s = "hello"
# prompt = ""
# for part in s:
#     prompt += part
# print(f"Prompt: {prompt}")
#
#
# text ="  Hello,  World! Python AI Backend Developer   "
# processed = text.strip().lower()
# print(f"Processed: {processed}")
#
# parts = ["word"] * 10_000
# start = time.perf_counter()
# result = ""
# for p in parts:
#     result += p
# slow_time = time.perf_counter() - start
#
#
# start = time.perf_counter()
# result = "".join(parts)
# fast_time = time.perf_counter() - start
# print(f"\nString += (10k):  {slow_time*1000:.2f}ms")
# print(f"String join(10k): {fast_time*1000:.2f}ms")
# print(f"join is {slow_time/fast_time:.0f}x faster")
#
# # LIST - DYNAMIC ARRAY
# # List = ordered, mutable, dynamic array of object references.
# # can hold elements of ANY type (even mixed).
#
# # WHY:
# # Ordered data maintain karne ke liye
# # Elements add/remove karne ke liye dynamically
# # Sequential processing ke liye (for loops)
#
# # How (Inernal - Dynamic Array):
# # lst = [1,2,3]
# # ob_refcount = 1
# # ob_size = 3
# # allocated = 4
#
# # OVER-ALLOCATION: Python allocates extra space to avid  resizing on every append -> amortized o(1
# """
# BIG 0:
# append(x)  -> 0(1) amortized (over-allocation)
# insert(0, x) -> 0(n) - shift all elements right
# pop()  -> 0(1) - form end
# pop(0) -> 0(n) -shift all left
# x in list -> 0(n) -linear search
# list[i]   -> 0(1) - direct pointer access
#
#
# REAL LIFE ANAlOGY:
# List = numbered queue at bank.
# Add person at front (insert 0) -> everyone shuffles back.
# Find person by name -> check everyone one by one
# Find person by number -> direct.
#
# """
# """
# Production  Example:
# """
#
# # messages = [
# #     {"role": "system", "content": "You are helpful."},
# #     {"role": "user", "content": "Hello!"}messages = [
# # #     {"role": "system", "content": "You are helpful."},
# # #     {"role": "user", "content": "Hello!"},
# # #     {"role": "assistant", "content": "Hi! How can I assist you today?"}
# # # ]
# # #
# # # messages.append({"role": "user", "content": "Next question"})
# # #
# # # documents = ["doc1", "doc2","doc100"]
# # # for batch in chunks(documents, size=10):
# # #     embed_batch(batch),
# #     {"role": "assistant", "content": "Hi! How can I assist you today?"}
# # ]
# #
# # messages.append({"role": "user", "content": "Next question"})
# #
# # documents = ["doc1", "doc2","doc100"]
# # for batch in chunks(documents, size=10):
# #     embed_batch(batch)
#
#
# # shallow vs deep copy
#
# a = [[1, 2], [3, 4]]
# b = a.copy() # shallow copy - inner lists SHARED
# b[0][0] = 99
# b = copy.deepcopy(a)
# print(a, b)
#
#
# # slicing created a copy
# sliced = lst[1:4]
# sliced[0] = 99
# print(f"\nOriginal unchanged: {sliced}")
#
#
# numbers = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
# evern_squared = [x**2 for x in numbers if x % 2 == 0]
#
# print(f"\nEven squared: {evern_squared}")
#
# even_sq_gen = (x**2 for x in numbers if x % 2 == 0)
# print(f"\nEven squared (generator): {list(even_sq_gen)}")
#
# total = sum(x**2 for x in numbers if x % 2 == 0)
# print(f"\nTotal even squares: {total}")
#


x=y=z = [1,2,3]
print(x is y is z)
x.append(4)
print(z)
print(x is y is z)
print(id(x) is id(y) is id(z))
print(id(x) == id(y) == id(z))

print(id(x))
print(id(y))
print(id(z))