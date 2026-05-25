# What is class?
# Class is BluePrint
# Real world → Code, # Car      → class Car, # Ashish   → class Person, # Account  → class BankAccount

#Self is reference of current object.
class Dog:
    # class variable share every objects
    species = "Canis familiaris"

    # Constructor -> It is called when an object is created
    def __init__(self, name, age):
        # Instance variable -> It is unique to every object
        self.name = name
        self.age = age

    #Instance method -> It is unique to every object
    def bark(self):
        print(f"{self.name} is barking!")

    def info(self):
        print(f"This is {self.name} and he is {self.age} years old")


#Create Object
dog1 = Dog("Rex", 5)
dog2 = Dog("Bella", 3)

dog1.bark()
dog2.bark()
dog1.info()
dog2.info()

print(Dog.species)
print(dog1.species)

dog1.bark()
Dog.bark(dog1)