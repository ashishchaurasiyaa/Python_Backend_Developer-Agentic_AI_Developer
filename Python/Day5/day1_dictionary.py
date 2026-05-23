# fruits = ["apple", "banana", "cherry","grapes","mango","orange","pineapple","strawberry","watermelon","avocado"]
# print(fruits[0])

students = {
    "name":"Ashish Kumar Chaurasiya",
    "age":28,
    "skills":["Python", "Php","JavaScript"],
    "profession":"Senior Software Engineer",
    "company":"Y Equipment Services Pvt Ltd"
}
# print(students["profession"])
# print(students.get("profession"))
# print(students["skills"][1])
# print(students.get("skills")[1])



# Method 2: dict() constructor
person  = dict(name="Ashish Kumar Chaurasiya", age=28, skills=["Python", "Php","JavaScript"], profession="Senior Software Engineer", company="Y Equipment Services Pvt Ltd")
print(person["profession"])

# # Method 3: Empty dictionary
empty = {}
empty = dict()
print(empty)

# Method 4: fromkeys()
keys = ["name", "age", "skills", "profession", "company"]
d = dict.fromkeys(keys, 0)
print(d)

# # Nested Dictionary
company = {
    "name": "Google",
    "employees": {"dev": 1000, "design": 200},
    "locations": ["USA", "India", "UK"]
}

print(company["employees"]["dev"])
print(company["locations"][1])

# Access Karna
student = {"name": "Ashish", "age": 28, "city": "Noida"}
# Method 1: [] - KeyError deta hai agar key nahi hai
print(student["name"])
print(student["age"])

# # Method 2: .get() - Safe access
print(student.get("name"))
print(student.get("salary"))
print(student.get("salary", 0))

# Nested access
company = {"name": "Google", "employees": {"dev": 1000, "design": 200}, "locations": ["USA", "India", "UK"]}
print(company["employees"]["dev"])
print(company["locations"][1])
print(company.get("emp", {}).get("dev", 0))

"""
🔑 Golden Rule: [] vs .get()

student["salary"]           → KeyError! Program crash ho jaata hai
student.get("salary")       → None return karta hai (safe)
student.get("salary", 0)    → 0 return karta hai (default)

Interview mein: get() use karo — crash nahi hoga!
"""

# 4. Add / Update / Delete
student = {"name": "Ashish", "age": 28, "city": "Noida"}
# ADD — naya key-value
student["city"] = "Noida"
student["skills"] = ["Python", "Django", "Django Rest Framework", "Fast API"]

print(student)

# Update multiple at once
student.update({"age":30, "city":"Kanpur","state":"Uttar Pradesh","country":"India"})
print(student)

# delete
# del student["age"]
# print(student)
# val = student.pop("age")
# print(val)

last = student.popitem()         # last item delete + return
print(last)

student.clear()                  # sab clear karo

# 5. Saare Methods
print(student.keys())
print(student.values())
print(student.items())
print(student.get("skills"))
print(student.get("state", "Not Found"))
print(student.update({"state":"U.P."}))
print(student.copy())
print(student.fromkeys(["name", "age", "city"], 0))
print(student.setdefault("x", 0))
"name" in student
len(student)
# 6. Dictionary Loop Karna

students = {"name": "Ashish", "age": 28, "city": "Noida"}
for key, value in students.items():
    print(f"{key} = {value}")

for key in students:
    print(key)

for value in students.values():
    print(value)

# 7. Dictionary Comprehension
squres = {}
for n in range(1, 11):
    squres[n] = n**2
print(squres)

squres = {n: n**2 for n in range(1, 11)}
print(squres)

# with condition
even = {n: n**2 for n in range(1, 11) if n % 2 == 0}
print(even)

# string frequency
word = "hello"
freq = {char: word.count(char) for char in word}
print(freq)

# Bina Built-in Methods — Interview Techniques
word = "programming"
freq = {}
for char in word:
    if char in freq:
        freq[char] += 1
    else:
        freq[char] = 1
print(freq)

# Two_sum_has_map

def two_sum_hash_map(nums, target):
    nums_dict ={}
    for i, num in enumerate(nums):
        complement = target - num
        if complement in nums_dict:
            return [nums_dict[complement], i]
        nums_dict[num] = i
    return []
nums = [2, 7, 11, 15, 1, 3, 4,9]
print(two_sum_hash_map(nums, 10))

# Group Anagrams

def group_anagrams(strs):
    groups = {}
    for word in strs:
        key = "".join(sorted(word))
        if key not in groups:
            groups[key] = []
        groups[key].append(word)
    return list(groups.values())
print(group_anagrams(["eat", "tea", "tan", "ate", "nat", "bat"]))

# First Non-Repeating Character

def first_unique(s):
    freq = {}
    for char in s:
        freq[char] = freq.get(char, 0) + 1
    for char, count in freq.items():
        if count == 1:
            return char
    return -1
print(first_unique("leetcode"))
print(first_unique("aabb"))

# Anagram

def isAnagram(s1, s2):
    return sorted(s1) == sorted(s2)
print(isAnagram("anagram", "nagaram"))

def valid_Anagram(s1, s2):
    if len(s1) != len(s2):
        return False
    freq1 = {}
    freq2 = {}
    for char in s1:
        freq1[char] = freq1.get(char, 0) + 1
    for char in s2:
        freq2[char] = freq2.get(char, 0) + 1
    return freq1 == freq2
print(valid_Anagram("anagram", "nagaram"))