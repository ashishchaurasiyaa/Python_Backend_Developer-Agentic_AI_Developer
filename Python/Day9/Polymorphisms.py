# Polymorphism = same method, different behavior

"""
┌─────────────────────────────────────────────┐
│  ENCAPSULATION                               │
│  Data hide karo + controlled access do       │
│  Tools: private __, @property                │
│  Example: BankAccount.__balance              │
├─────────────────────────────────────────────┤
│  INHERITANCE                                 │
│  Parent ke properties reuse karo             │
│  Tools: class Child(Parent), super()         │
│  Example: Dog(Animal)                        │
├─────────────────────────────────────────────┤
│  POLYMORPHISM                                │
│  Same interface, different behavior          │
│  Tools: Override, Duck Typing, Dunder        │
│  Example: shape.area() for all shapes        │
├─────────────────────────────────────────────┤
│  ABSTRACTION                                 │
│  Complexity hide karo                        │
│  Tools: ABC, @abstractmethod                 │
│  Example: Vehicle.start() — car/bike alag    │
"""

# ── TYPE 1: Method Overriding ──

class Animal:
    def speak(self):
        return "some sound"

class Dog(Animal):
    def speak(self):
        return "bark"

class Cat(Animal):
    def speak(self):
        return "meow"

class Duck(Animal):
    def speak(self):
        return "quack"

animals = [Dog(), Cat(), Duck()]
for animal in animals:
    print(animal.speak())


# # ── TYPE 2: Duck Typing ──
# # "If it walks like a duck, quacks like a duck — it's a duck!"
# # Type check nahi karte — behavior check karte hain

class Printer:
    def print_doc(self):
        print("Printing a document...")


class Scanner:
    def print_doc(self):
        print("Scanning a document...")

class FaxMachine:
    def print_doc(self):
        print("Faxing a document...")

machine = [Printer(), Scanner(), FaxMachine()]
for m in machine:
    m.print_doc()

# Type 1 — Method Overriding:

class Shape:
    def area(self):
        return 0

class Circle(Shape):
    def __init__(self, radius):
        self.radius = radius

    def area(self):
        return 3.14 * self.radius ** 2

class Rectangle(Shape):
    def __init__(self, length, width):
        self.length = length
        self.width = width
    def area(self):
        return self.length * self.width

shapes = [Circle(5), Rectangle(4, 6)]
for shape in shapes:
    print(f"{shape.__class__.__name__}: {shape.area()}")


# Type 3 — Operator Overloading:
class Money:
    def __init__(self, amount,currency="INR"):
        self.amount = amount
        self.currency = currency

    def __add__(self, other):
        return Money(self.amount + other.amoun)

    def __sub__(self, other):
        return Money(self.amount - other.amount)

    def __get__(self, other):
        return self.amount > other.amount

    def __str__(self):
        return f"{self.amount} {self.currency}"


m1 = Money(500)
m2 = Money(300)

print(m1 + m2)    # ₹800
print(m1 - m2)    # ₹200
print(m1 > m2)

