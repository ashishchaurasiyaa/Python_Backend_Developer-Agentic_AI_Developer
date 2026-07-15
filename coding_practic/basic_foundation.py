import sys
x = [1,2,3]
print(sys.getrefcount(x))
y = x
print(sys.getrefcount(y))
z = y
print(sys.getrefcount(z))

del y

print(sys.getrefcount(x))

a = [1,2,3]
b = a
print(id(a))
print(id(b))