# name = input("Enter your name:")
# parts = name.split(" ")
# print(f"first part is {parts[0]}")
# print(f"middle part is {parts[1]}")
# print(f"last part is {parts[-1]}")



"""
# "@" aur "." dono check karo
# valid: ashish@gmail.com
# invalid: ashishgmail.com ya ashish@gmailcom
"""
# email = input("Enter your email:")
# if "@" in email and "." in email:
#     print(f"Valid Email {email}")
# else:
#     print(f"Invalid Email {email}")

"""
# Problem 3:
# User se sentence lo
# Count karo:
# 1. Total words kitne hain
# 2. Total characters kitne hain (spaces ke bina)
# 3. Sentence ko reverse karo
"""
# Problem3
input_user = input("Enter single line of sentence:")
count = 0
for char in input_user:
    if char not in " ":
        count = count + 1
print(count)

# without space count
input_user = input("Enter single line of sentence:")
count = 0
for char in input_user:
    if char == " ":
        count = count + 1

words = count + 1
print(words)

# Sentence ko reverse karo

input_sentence = input("Enter single line of sentence:")
print(input_sentence[::-1])


# using loop reverse

input_sentence_reverse = input("Enter single line of sentence:")
result = " "
for char in input_sentence_reverse:
    result = result + char
print(result)

print("".join(reversed(input_sentence)))


