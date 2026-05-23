sentence = "the cat sat on the mat the cat"
# Expected: {'the': 3, 'cat': 2, 'sat': 1, 'on': 1, 'mat': 1}

freq = {}
for word in sentence.split():
    freq[word] = freq.get(word, 0) + 1
print(freq)

# # ✅ Problem 2 — Two lists se dict banao
keys = ["name","age","city"]
values = ["Ashish",29,"Kanpur"]

dictionary = dict(zip(keys,values))
print(dictionary)

# # ✅ Problem 3 — Dict invert karo
d = {"a": 1, "b": 2, "c": 3}
# Expected: {1: 'a', 2: 'b', 3: 'c'}
inverted = {v:k for k,v in d.items()}
print(inverted)

# ✅ Problem 4 — Common elements (sets use karo)
list1 = [1, 2, 3, 4, 5]
list2 = [3, 4, 5, 6, 7]
print(set(list1) & set(list2))

# # ✅ Problem 5 — Student topper find karo
students = {"Rahul": 85, "Priya": 92, "Amit": 78}
topper = max(students, key=students.get)
print(topper)

# ✅ Problem 6 — Group anagrams
words = ["eat", "tea", "tan", "ate", "nat", "bat"]
from collections import defaultdict
word = ["eat", "tea","tan","ate","nat","bat"]
groups = defaultdict(list)
for word in words:
    key = "".join(sorted(word))
    groups[key].append(word)
print(list(groups.values()))

# ✅ Problem 7 — Phone book (dict)
phone_book = {}
def add_contact(name, number): phone_book[name] = number
def get_number(name): return phone_book.get(name, "Not found")
def delete_contact(name): phone_book.pop(name, None)

# # ✅ Problem 8 — Remove duplicates using set (order preserve karo)
arr = [3, 1, 4, 1, 5, 9, 2, 6, 5, 3]
seen = set()
result = []
for x in arr:
    if x not in seen:
        seen.add(x)
        result.append(x)
print(result)



# # ✅ Problem 9 — Symmetric difference
a = {1, 2, 3, 4}
b = {3, 4, 5, 6}
print(a ^ b)

# # ✅ Problem 10 — Nested dict — marks by subject

students = {
    "Rahul": {"math": 90, "science": 85, "english": 78},
    "Priya": {"math": 80, "science": 95, "english": 60},
    "Amit": {"math": 70, "science": 65, "english": 90}
}

subjects = ["math", "science", "english"]
for sub in subjects:
    avg = sum(s[sub] for s in students.values()) / len(students)
    print(f"Average {sub} marks: {avg:.1f}")

# # Q1 — Dict mein sirf even values rakhho

d = {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5}
even_values = {}
for key, value in d.items():
    if value %2 == 0:
        even_values[key] = value
print(even_values)

# # Q2 — List of dicts ko sort karo age ke hisaab se

people = [
    {"name": "Rahul", "age": 25},
    {"name": "Priya", "age": 22},
    {"name": "Amit",  "age": 28}
]
# # Expected: Priya(22) → Rahul(25) → Amit(28)
people.sort(key=lambda x: x["age"])
for person in people:
    print(person["name"], person["age"])


# # Q3 — Tuple list ko 2nd element se sort karo
data = [(1, 5), (3, 2), (2, 8), (4, 1)]
data.sort(key=lambda x: x[1])
print(data)

# # Q4 — Two dicts merge karo

d1 = {"a": 10, "b": 20, "c": 30}
d2 = {"b": 50, "c": 60, "d": 70}

merged = {}
for key in set(d1) | set(d2):
    merged[key] = d1.get(key, 0) + d2.get(key, 0)
print(merged)

# # Q5 — Character frequency (only repeating chars dikhao)

s = "abracadabra"
freq = {}
for char in s:
    freq[char] = freq.get(char, 0) + 1
print(freq)

repeating = {k: v for k, v in freq.items() if v > 1}
print(repeating)

# # Q6 — First non-repeating character
s = "aabbcddeff"

def first_unique(s):
    freq = {}
    for char in s:
        freq[char] = freq.get(char, 0) + 1
    for char, count in freq.items():
        if count == 1:
            return char
    return -1
print(first_unique(s))

# # Q7 — Subarray jo set mein hai uske elements nikalo
arr    = [1, 2, 3, 4, 5, 6, 7]
banned = {2, 4, 6}
result = [x for x in arr if x not in banned]
print(result)

# Q8 — Dict ka dict — best subject per student
students = {
    "Rahul": {"math": 90, "science": 85, "english": 78},
    "Priya": {"math": 78, "science": 92, "english": 88},
}
# Expected: {"Rahul": "math", "Priya": "science"}

best_subjects = {}
for student, scores in students.items():
    best_subject = max(scores, key=scores.get)
    best_subjects[student] = best_subject
print(best_subjects)