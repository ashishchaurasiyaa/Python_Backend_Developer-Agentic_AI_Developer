# Parent Class
class Vehicle:
    def __init__(self, color, max_speed):
        self.color = color
        self.max_speed = max_speed

    def start(self):
        print("Vehicle is starting.")

    def stop(self):
        print("Vehicle is stopping.")

# Child Class: Car
class Car(Vehicle):
    def __init__(self, color, max_speed, number_of_doors):
        super().__init__(color, max_speed)
        self.number_of_doors = number_of_doors

    def open_trunk(self):
        print("Car trunk is open.")

# Child Class: Bike
class Bike(Vehicle):
    def __init__(self, color, max_speed, type_of_handle):
        super().__init__(color, max_speed)
        self.type_of_handle = type_of_handle

    def wheelie(self):
        print("Bike is doing a wheelie!")

# Example Usage
car = Car("Red", 200, 4)
car.start()
print(f"Car Color: {car.color}, Max Speed: {car.max_speed}, Doors: {car.number_of_doors}")
car.open_trunk()
car.stop()

bike = Bike("Blue", 150, "Sports Handle")
bike.start()
print(f"Bike Color: {bike.color}, Max Speed: {bike.max_speed}, Handle Type: {bike.type_of_handle}")
bike.wheelie()
bike.stop()


# Code Reusability: Parent class functionality can be reused in child classes.
# Extensibility: Child classes can add or override methods without modifying the parent class.
# Logical Hierarchies: Makes programs more organized by defining generic properties and behaviors in a parent class and specific ones in child classes.