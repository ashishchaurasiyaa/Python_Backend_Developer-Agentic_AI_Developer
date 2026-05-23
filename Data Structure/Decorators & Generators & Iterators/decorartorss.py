# What is Python Decorators & Generators & Iterators?
"""
A decorator is a functional that modifies the behavior of another function or method without changing its behavior.
It is widely used for logging, authentication, caching, and performance measurement in Python applications, including Django, Flask, and Celery

Key Points:
Decorators & Generators & Iterators are higher-order function.
They use the @decorator_name syntax.
They are used for code reuse.
"""

# Basic Decorators & Generators & Iterators

def my_decorator(func):
    def wrapper(*args, **kwargs):
        print("Something before the function is called")
        func(*args, **kwargs)
        print("Something after the function is called")
    return wrapper

@my_decorator
def say_hello():
    print("Hello World")
say_hello()

# Example 2: Decorator with Arguments

def repeat(n):
    def decorator(func):
        def wrapper(*args, **kwargs):
            for _ in range(n):
                func(*args, **kwargs)
        return wrapper
    return decorator

@repeat(4)
def greet(name):
    print(f"Hello, {name}")

greet("Ashish Chaurasiya")


# Example 3: Real-World Use Case – Logging Decorator

import time

def log_execution_time(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        print(f"Execution time: {end_time - start_time}")
        return result
    return wrapper

@log_execution_time
def process_data():
    time.sleep(2)
    print("Processing data.....")

process_data()


# You can apply multiple decorators to a single function

def uppercase_decorators(func):
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        return result
    return wrapper

def execution_decorators(func):
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        return result + "!"
    return wrapper
@execution_decorators
@uppercase_decorators
def greet_decorator(name):
    return f"Hello, {name}"
greet_decorator(name="Ashish Chaurasiya")


