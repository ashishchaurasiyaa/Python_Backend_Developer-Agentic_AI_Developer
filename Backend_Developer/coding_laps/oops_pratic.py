from os import name


class Student:
    name = ""
    age = ""
    gender = ""

    def set_name(self):
        self.name = input("Enter name: ")
        self.age = int(input("Enter age: "))
        self.gender = input("Enter gender: ")

    def display(self):
        print(f"My Name is {self.name} and I am {self.age} years old.")


student = Student()
student.set_name()
student.display()
