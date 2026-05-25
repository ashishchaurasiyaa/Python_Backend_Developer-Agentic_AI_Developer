# empty_list = []
# numbers = [1,2,3,4,5,6]
# mixed = [1, "Ashish", True, 3.14]
# nested = [[1,2], [3,4], [5,6]]
# print(numbers[0])
# print(numbers[-1])
# print(nested[0][1])
#
# # slicing
# print(numbers[1:4])
# print(numbers[::-1])
#
# fruits = ["apple", "banana", "mango"]
#
# # ADD
# fruits.append("grapes")
# print(fruits)# end mein add
# fruits.insert(1, "orange")
# print(fruits)
# # index 1 pe add
#
# # REMOVE
# fruits.remove("banana")        # value se remove
# print(fruits)
# popped = fruits.pop()          # last element remove + return
# print(popped)
# fruits.pop(0)                  # index se remove
# print(fruits)
#
# # INFO
# print(len(fruits))             # length
# print(fruits.index("mango"))   # index find karo
# print("apple" in fruits)       # True/False
#
# # SORT
# fruits.sort()                  # ascending
# print(fruits)
# fruits.sort(reverse=True)      # descending
# print(fruits)
# fruits.reverse()               # reverse
# print(fruits)

# original = [1, 2, 3]
# copy1 = original
# copy2 = original.copy()
#
# original[0] = 99      # ← original change kiya!
#
# print(original)
# print(copy1)
# print(copy2)
#
# print(id(original))
# print(id(copy1))
# print(id(copy2))

numbers = [1, 2, 3, 4, 5,6]

# Normal way — 3 lines
squares = []
for n in numbers:
    squares.append(n**2)

# List comprehension — 1 line!
squares = [n**2 for n in numbers]

print(squares)

even_squre = [n**2 for n in numbers if n %2 ==0]
print(even_squre)

odd = [n for n in numbers if n%2 != 0]
print(odd)

mulltiple_of_3 = [3*n for n in numbers]
print(mulltiple_of_3)

greater =[n for n in numbers if n > 5]
print(greater)