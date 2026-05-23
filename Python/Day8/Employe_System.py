"""
# Q3 — Employee system
class Employee:     # name, salary, department
class Manager(Employee):   # team_size extra
class Developer(Employee): # language extra
# Manager: give_raise(percent)
# Developer: code(task)
# Dono: show_info()
"""

class Employee:
    def __init__(self, name, salary, department):
        self.name = name
        self.salary = salary
        self.department = department

    def show_info(self):
        print(f"Name : {self.name} Salary : {self.salary} Department : {self.department}")


class Manager(Employee):
    def __init__(self, name, salary, department, team_size):
        super().__init__(name, salary,department)
        self.team_size = team_size

    def give_raise(self, percent):
        self.salary += self.salary * percent / 100
        print(f"{self.name} received a raise of {percent}%")

    def show_info(self):
        super().show_info()
        print(f"Manager of {self.team_size} employees")


class Developer(Employee):
    def __init__(self, name, salary, department, language="Python"):
        super().__init__(name, salary,department)
        self.lang = language

    def code(self, task):
        print(f"{self.name} is coding {task} in {self.lang}")
        self.salary += 100
        print(f"{self.name} earns {self.salary} now")

    def show_info(self):
        super().show_info()
        print(f"Role : {self.lang} Developer")

print("=" * 30)
print("MANAGER:")
print("=" * 30)
m = Manager("Rahul", 80000, "Engineering", 8)
m.show_info()
m.give_raise(10)

print()
print("=" * 30)
print("DEVELOPER:")
print("=" * 30)
d = Developer("Ashish", 60000, "IT", "Python")
d.show_info()
d.code("Build REST API")
d.show_info()