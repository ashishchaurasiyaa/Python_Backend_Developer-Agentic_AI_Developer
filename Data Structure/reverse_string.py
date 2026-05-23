# Problem: Write a function to reverse a string without using built-in methods

def reverse_string(s):
    return s[::-1]
s = "Ashish"
print(reverse_string(s))

# Using loop

def reverse_string(s):
    reversed = ""
    for i in range(len(s)-1,-1,-1):
        reversed += s[i]
    return reversed
s = "Ashish"
print(reverse_string(s))

# Using recursion

def reverse_string(s):
    if len(s) == 0:
        return s
    else:
        return reverse_string(s[1:]) + s[0]

s = "Ashish"
print(reverse_string(s))

# Using stack

def reverse_string(s):
    stack = []
    for i in range(len(s)):
        stack.append(s[i])
    reversed = ""
    while len(stack) > 0:
        reversed += stack.pop()
    return reversed
s = "Ashish"
print(reverse_string(s))