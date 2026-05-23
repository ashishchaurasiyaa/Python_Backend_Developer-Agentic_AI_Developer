"""
# Vehicle hierarchy
class Vehicle:      # brand, speed
class Car(Vehicle): # doors
class Bike(Vehicle):# type (sport/normal)
class Truck(Vehicle): # capacity (tons)
# Sab ka describe() method

# Expected output:
# Toyota Car - Speed: 120 kmph, Doors: 4
# Royal Enfield Bike - Speed: 100 kmph, Type: Sport
# Tata Truck - Speed: 80 kmph, Capacity: 10 tons
"""
class Vehicle:
    def __init__(self, brand, speed):
        self.brand = brand
        self.speed = speed

    def describe(self):
        print(f"{self.brand} {self.__class__.__name__} - Speed: {self.speed} kmph")


class Car(Vehicle):
    def __init__(self, brand, speed, doors):
        super().__init__(brand, speed)
        self.doors = doors

    def describe(self):
        print(f"{self.brand} {self.__class__.__name__} - Speed: {self.speed} kmph, Doors: {self.doors}")


class Bike(Vehicle):
    def __init__(self, brand, speed, type):
        super().__init__(brand, speed)
        self.type = type

    def describe(self):
        print(f"{self.brand} {self.__class__.__name__} - Speed: {self.speed} kmph, Type: {self.type}")


class Truck(Vehicle):
    def __init__(self, brand, speed, capacity):
        super().__init__(brand, speed)
        self.capacity = capacity

    def describe(self):
        print(f"{self.brand} {self.__class__.__name__} - Speed: {self.speed} kmph, Capacity: {self.capacity} tons")



c = Car("Toyota", 120, 4)
b = Bike("Royal Enfield", 100, "Sport")
t = Truck("Tata", 80, 10)

c.describe()
b.describe()
t.describe()


