from pandas._libs.tslibs import ccalendar

name = "Ashish Chaurasiya"
print(name)
print(name[0])
print(name[1])
print(name[-1])
print(name[-2])

"""
"Ashish Kumar Chaurasiya"
  A  s  h  i  s  h     C  h  a  u  r  a  s  i  y  a
  0  1  2  3  4  5  6  7  8  9  10 11 12 13 14 15 16
 -17-16-15-14-13-12-11-10 -9 -8 -7 -6 -5 -4 -3 -2 -1
"""
# print(name[1:5])

print(name[0:6])    # pehle 6 characters
print(name[7:])     # 7 se end tak
print(name[:6])     # start se 6 tak
print(name[::2])    # har doosra character
print(name[::-1])   # reverse!

#string method
print(name.split(" "))
print(name.find("kumar"))

name = "ashish kumar chaurasiya"

print(name.upper())          # UPPERCASE
print(name.lower())          # lowercase
print(name.title())          # Title Case
print(name.replace("ashish", "Rahul"))  # replace
print(name.split(" "))       # list mein tod do
print(len(name))             # length
print(name.count("a"))       # kitni baar "a" aaya
print(name.find("kumar"))    # index kahan hai
print(name.strip())          # spaces hatao
print(name.startswith("ash")) # True/False
print(name.endswith("iya"))   # True/False

# s = "A man, a plan, a canal: Panama"
# s = " "
s = "race a car"
print(s.split())

s = "0P"
clean = ""
for ch in s:
    if ('a' <= ch <= 'z') or ('A' <= ch <= 'Z') or ('0' <= ch <= '9'):
        clean += ch.lower()

left = 0
right = len(clean) -1
while left < right:
    if clean[left] != clean[right]:
        print(False)
        break
    left += 1
    right -= 1
else:
    print(True)
