class Student:
    #class variable
    school = "S.C.D. Inter College Tangapur Unnao"
    total_students = 0

    def __init__(self, name, marks):
        self.name = name #instance variable
        self.marks = marks
        Student.total_students += 1 #class variable update

    #Instance method = self leta hai
    def get_grade(self):
        if self.marks >= 90: return "A"
        elif self.marks >= 80: return "B"
        elif self.marks >= 70: return "C"
        else:                  return "D"

    def show(self):
        print(f"{self.name}: {self.marks} ({self.get_grade()})")

    #class methiod -> cls leta hai
    @classmethod
    def get_total(cls):
        return cls.total_students

    @classmethod
    def from_string(cls, data):
        name, marks = data.split(":")
        return cls(name, int(marks))

    #static method -> it is not bound to any object
    @staticmethod
    def is_passing(marks):
        return marks >= 40


s1 = Student("Ravi", 90)
s2 = Student("Ashish", 80)
s3 = Student("Simran", 70)
s4 = Student("Rahul", 50)
s1.show()
s2.show()
s3.show()
s4.show()
print(Student.get_total())
print(Student.is_passing(50))
print(Student.is_passing(30))