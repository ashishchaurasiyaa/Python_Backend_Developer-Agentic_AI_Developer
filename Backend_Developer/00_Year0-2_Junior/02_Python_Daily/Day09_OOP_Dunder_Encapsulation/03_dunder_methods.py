# Dunder Methods (Vector Class)
import math

from zeep.xsd import xsd_ns


class Vector:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __str__(self):
        return f"Vector({self.x}, {self.y})"

    def __add__(self, other):
        return Vector(self.x + other.x, self.y + other.y)

    def __sub__(self, other):
        return Vector(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar):
        return Vector(self.x * scalar, self.y * scalar)

    def __len__(self):
        return int(math.sqrt(self.x ** 2 + self.y ** 2))

    def __eq__(self, other):
        return self.x == other.x and self.y == other.y
    def __abs__(self):
        return math.sqrt(self.x ** 2 + self.y ** 2)


v1 = Vector(3, 4)
v2 = Vector(1, 2)

print(v1 + v2)     # Vector(4, 6)
print(len(v1))     # 5
print(abs(v1))     # 5.0