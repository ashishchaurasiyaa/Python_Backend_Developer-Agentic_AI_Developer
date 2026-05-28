# ── MULTI-LEVEL INHERITANCE ──
"""
Multi-Level Inheritance is a type of inheritance where a class is derived from another derived class.
Grandfather → Father → Son
How Python Handles It
Python uses Method Resolution Order (MRO).
"""
from Day8.inheritance_super import Animal


class Vechile:
    def __init__(self, brand):
        self.brand = brand

    def start(self):
        print(f"Starting {self.brand} vehicle")


class Car(Vechile):
    def __init__(self, brand, model):
        super().__init__(brand)
        self.model = model


    def drive(self):
        print(f"Driving {self.model} {self.brand} vehicle")


class ElectricCar(Car):
    def __init__(self, brand, model, battery):
        super().__init__(brand, model)
        self.battery = battery


    def charge(self):
        print(f"Charging {self.brand} Battery: {self.battery}")



tesla = ElectricCar("Tesla", "Model 3", 80)
tesla.start() # Vehicle ka method
tesla.drive() # Car ka method
tesla.charge() # ElectricCar ka method

# MRO = Method Resolution Order
print(ElectricCar.__mro__)

#--Multiple Inheritence--

class Flyable:
    def fly(self):
        print(f"{self.name} is flying")

class Swimable:
    def swim(self):
        print(f"{self.name} is swimming")

class Duck(Animal, Flyable, Swimable):
    def __init__(self, name):
        super().__init__(name,"Quack")

d = Duck("Donald")
d.speak()
d.fly()
d.swim()