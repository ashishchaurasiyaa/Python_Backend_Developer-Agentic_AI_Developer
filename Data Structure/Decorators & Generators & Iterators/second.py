# 1. What is a decorator in Python? How does it work?

"""
decorator is a function that takes fucntion as an arugment, enhances or modifies its behavior, and returns the modified function.
It is often used with the @decorator.
"""

def my_decorators(func):
    def wrapper():
        print("Before function call")
        func()
        print("After function call")
    return wrapper

@my_decorators
def hello():
    print("Hello World")

hello()

# 2. How do you define and apply a custom decorator?
# A custom decorator is defined as a function that wraps another function.

def uppercase_decorator(func):
    def wrapper():
        return func().upper()
    return wrapper

@uppercase_decorator
def greet():
    print("Hello World")

print(greet())


"""
3. What are the differences between function decorators and class decorators?
Function Decorators: Modify the behavior of a function.Common use cases:
Logging
Authorization checks
Caching/memoization
Timing execution
"""
def my_decorator(func):
    def wrapper():
        print("Before function call")
        func()
        print("After function call")
    return wrapper
@my_decorator
def say_hello():
    print("Hello World")
say_hello()

"""
Class Decorators: Modify a class instead of a function.
It is often used for:
Adding or modifying class attributes
Automatically registering classes
Implementing singleton patterns
Enforcing constraints on class instances

"""

def class_decorator(cls):
    class NewClass(cls):
        def extra_method(self):
            return "This is an added method!"
    return NewClass

@class_decorator
class MyClass:
    def __init__(self, name):
        self.name = name

obj = MyClass('Ashish Chaurasiya')
print(obj.name)
print(obj.extra_method())
