class Shape:
    def area(self):
        pass

class Circle(Shape):
    def __init__(self, radius):
        self.radius = radius        # super() zaruri nahi ab

    def area(self):
        return 3.14 * self.radius ** 2

class Rectangle(Shape):
    def __init__(self, length, width):
        self.length = length
        self.width  = width

    def area(self):
        return self.length * self.width

class Triangle(Shape):
    def __init__(self, base, height):
        self.base   = base
        self.height = height

    def area(self):
        return 0.5 * self.base * self.height


# Test
shapes = [Circle(5), Rectangle(4, 6), Triangle(3, 4)]

for shape in shapes:
    print(f"{shape.__class__.__name__} area: {shape.area()}")
