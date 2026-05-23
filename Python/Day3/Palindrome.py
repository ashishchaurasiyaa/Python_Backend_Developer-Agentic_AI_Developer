"""
Palindrome check karo WITHOUT slicing
# "madam" → Palindrome ✅
"""

words = input("Enter a string check palindrome:")
word = words.lower()
reverse_words = ""

for char in word:
    reverse_words = char + reverse_words
if word == reverse_words:
    print("Palindrome")
else:
    print("Not Palindrome")


