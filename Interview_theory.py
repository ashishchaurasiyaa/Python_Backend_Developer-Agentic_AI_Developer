# Define OOPS
# What is Class? What is Object? What is Inheritance? What is Polymorphism? What is Encapsulation?
# What is Abstraction? What is Method Overriding? What is Method Overloading? What is Operator Overloading?
# What is Decorator? What is Getter and Setter? What is Private Attribute? What is Protected Attribute?
# What is  static method? What is class method? What is instance method? What is self? What is __init__?
# What is the difference between @staticmethod, @classmethod, and an instance method?
# How can you implement multiple inheritance in Python?
# What is super() in Python?
# What is the difference between class and instance variables?
# What is a Python decorator, and how is it used?
# Explain the concept of generators and yield.
# Explain Python's Global Interpreter Lock (GIL).
# How does Python manage memory?
# What are Python's mutable and immutable data types?
# What is the difference between deepcopy and shallow copy?
# What is the difference between lists and tuples?
# What is the difference between kwargs and args?
# What is  Lambda function? What is map, filter, and reduce?
# What is a Python iterator?
# What is a Python generator?
# What is List Comprehension?
# What is Dictionary Comprehension?
# What is a Python closure?
# What is Pickling and Unpickling?


# Django

# What is the difference between Django, Flask, and FastAPI?
# What is Django?
# What is Django ORM?
# What is Django Template?
# What is Django Model?
# Define Django Architecture.
# What is Django Middleware?
# What is Django QuerySet?
# What is ASGI and WSGI and how are they different and used in Django?
# What is Django Rest Framework?
# What is Serializer in Django Rest Framework?
# What is the difference between render(), HttpResponse(), and redirect() in Django?
# What are ForeignKey, ManyToManyField, and OneToOneField in Django models? Provide examples.
# What is the difference between HTTP methods (GET, POST, PUT, PATCH, DELETE)?
# What are RESTful APIs? Explain their key principles.
# What are the differences between authentication and authorization in REST APIs?
# Explain the concept of status codes in REST APIs. Provide examples of commonly used status codes.
# What is the use of select_related() and prefetch_related()?
# What is Django's cache framework?
# What are Django signals?
# What is Django's context processors?
# Explain Q objects in Django ORM.
# What are Django Exceptions?
# What is Django's class-based views and function-based views?
# What is Mixins in Django?
# How to configure Django settings for multiple environments?
# How to configure static files in Django?
# What is Django's CSRF protection?
# How to pass Context in Django Class-Based Views and Function-Based Views?
#  Explain the caching strategies in the Django?
# What is Django's session framework?
# Define Custom Middleware in Django?


# AWS
# What is EC2?
# What is S3?
# What is RDS?
# How to Deploy Django Application on AWS?

# Answers

# Define OOPS : Object-oriented programming (OOP) is a programming paradigm that uses objects and classes in programming. It aims to implement real-world entities like inheritance, polymorphism, encapsulation, and abstraction.
# What is Class? What is Object? What is Inheritance? What is Polymorphism? What is Encapsulation?
# Class: A class is a blueprint for creating objects (a particular data structure), providing initial values for state (member variables or attributes), and implementations of behavior (member functions or methods).
# Object: An object is an instance of a class. When a class is defined, no memory is allocated but when it is instantiated (i.e. an object is created) memory is allocated.
# Inheritance: Inheritance is the mechanism by which one class acquires the properties and behavior of another class. It supports the concept of hierarchical classification.
# Polymorphism: Polymorphism is the ability of a programming language to present the same interface for several different underlying data types.
# Encapsulation: Encapsulation is used to protect the data stored in an object from system-wide access. Encapsulation is implemented using private attributes and methods.
# What is Abstraction? What is Method Overriding? What is Method Overloading? What is Operator Overloading?
# Abstraction: Abstraction is the concept of hiding the complex implementation details and showing only the necessary features of an object.
# Method Overriding: Method overriding is a feature that allows a subclass to provide a specific implementation of a method that is already provided by its superclass.
# Method Overloading: Method overloading is the ability to define multiple methods with the same name but with different parameters.
# Operator Overloading: Operator overloading is the ability to define custom behavior for operators in a class.
# What is Decorator? What is Getter and Setter? What is Private Attribute? What is Protected Attribute?
# Decorator: A decorator is a design pattern in Python that allows a user to add new functionality to an object without modifying its structure.
# Decorators are very powerful and useful tool in Python since it allows programmers to modify the behavior of function or class.
# Getter and Setter: Getter and setter methods are used to access and modify the private attributes of a class respectively.
# They provide controlled access to the private attributes of a class.
# Private Attribute: Private attributes are attributes that are not accessible outside the class. They are defined using double underscores (__).
# Protected Attribute: Protected attributes are attributes that are accessible within the class and its subclasses. They are defined using a single underscore (_).
# What is  static method? What is class method? What is instance method? What is self? What is __init__?
# Static Method: A static method is a method that does not receive an implicit first argument (self, cls). It is defined using the @staticmethod decorator.
# Class Method: A class method is a method that receives the class itself as the first argument (cls). It is defined using the @classmethod decorator.
# Instance Method: An instance method is a method that receives the instance itself as the first argument (self). It is the most common type of method in Python classes.
# Self: Self is a reference to the current instance of the class. It is used to access the attributes and methods of the class within the class definition.
# __init__: __init__ is a special method in Python classes that is called when a new instance of the class is created. It is used to initialize the attributes of the class.
# What is the difference between @staticmethod, @classmethod, and an instance method?
# @staticmethod: A static method is a method that does not receive an implicit first argument (self, cls). It is defined using the @staticmethod decorator.
# @classmethod: A class method is a method that receives the class itself as the first argument (cls). It is defined using the @classmethod decorator.
# Instance Method: An instance method is a method that receives the instance itself as the first argument (self). It is the most common type of method in Python classes.
# How can you implement multiple inheritance in Python?
# Multiple inheritance in Python is implemented by defining a class that inherits from multiple parent classes.
# class ChildClass(ParentClass1, ParentClass2):
#     def __init__(self):
#         super().__init__()
# What is super() in Python? super() is a built-in function in Python that is used to call the superclass (parent) methods. It returns a temporary object of the superclass that allows you to call its methods.
# What is the difference between class and instance variables?
# Class variables are shared among all instances of a class, while instance variables are unique to each instance of a class.
# What is a Python decorator, and how is it used?
# A decorator is a design pattern in Python that allows a user to add new functionality to an object without modifying its structure.
# Decorators are very powerful and useful tool in Python since it allows programmers to modify the behavior of function or class.
# Explain the concept of generators and yield.
# Generators are functions that return an iterator object. They generate values one at a time and only when needed.
# The yield statement is used to return a value from a generator function.
# Explain Python's Global Interpreter Lock (GIL).
# The Global Interpreter Lock (GIL) is a mutex that protects access to Python objects, preventing multiple threads from executing Python bytecodes at once.
# How does Python manage memory?
# Python uses a private heap to manage memory. The Python memory manager allocates and deallocates memory as needed.
# What are Python's mutable and immutable data types?
# Mutable data types can be changed after they are created, while immutable data types cannot be changed after they are created.
# What is the difference between deepcopy and shallow copy?
# Deepcopy creates a new object and recursively copies the objects found in the original object. Shallow copy creates a new object and copies the references to the objects found in the original object.
# What is the difference between lists and tuples?
# Lists are mutable, while tuples are immutable. Lists use square brackets [], while tuples use parentheses ().
# What is the difference between kwargs and args?
# Args is used to pass a variable number of non-keyword arguments to a function, while kwargs is used to pass a variable number of keyword arguments to a function.
# What is  Lambda function? What is map, filter, and reduce?
# Lambda function is an anonymous function in Python that can have any number of arguments, but can only have one expression.
# Map, filter, and reduce are built-in functions in Python.
# Map: Applies a function to all the items in an input list.
# Filter: Filters out items based on a condition.
# Reduce: Applies a rolling computation to sequential pairs of values in a list.
# What is a Python iterator?
# An iterator is an object that enables a programmer to traverse a container, particularly lists. An iterator is an object that can be iterated upon, meaning that you can traverse through all the values.
# What is a Python generator?
# A generator is a function that returns an iterator object. It generates values one at a time and only when needed. Generators are used to create iterators.
# What is List Comprehension?
# List comprehension is a concise way to create lists in Python. It consists of brackets containing an expression followed by a for clause, then zero or more for or if clauses.
# What is Dictionary Comprehension?
# Dictionary comprehension is a concise way to create dictionaries in Python. It consists of curly braces containing key-value pairs followed by a for clause, then zero or more for or if clauses.
# What is a Python closure?
# A closure is a function object that has access to variables in its enclosing scope even after the scope has finished executing.
# What is Pickling and Unpickling?
# Pickling is the process of converting a Python object into a byte stream, and unpickling is the process of converting a byte stream back into a Python object.

# Django

# What is the difference between Django, Flask, and FastAPI?
# Django is a high-level Python web framework that encourages rapid development and clean, pragmatic design.
# Flask is a micro web framework for Python based on Werkzeug, Jinja 2, and good intentions.
# FastAPI is a modern, fast (high-performance), web framework for building APIs with Python 3.6+ based on standard Python type hints.
# What is Django?
# Django is a high-level Python web framework that encourages rapid development and clean, pragmatic design.
# It follows the Model-View-Template (MVT) architecture.
# What is Django ORM?
# Django ORM (Object-Relational Mapping) is a tool that allows developers to interact with the database using Python objects.
# It abstracts the database structure and provides a high-level API for database operations.
# What is Django Template?
# Django Template is a text file that defines the structure of the output of a web application.
# It uses Django's template language to define the HTML structure of a web page.

# What is Django Model?
# Django Model is a Python class that represents the structure of a database table. It is used to interact with the database and perform CRUD operations.
# Define Django Architecture.
# Django follows the Model-View-Template (MVT) architecture.
# Model: Represents the structure of the database table and interacts with the database.
# View: Handles the business logic and user interaction.
# Template: Defines the structure of the output of a web application.
# What is Django Middleware?
# Django Middleware is a framework of hooks into Django's request/response processing.
# It is a lightweight plugin system that processes requests and responses before and after they reach the view.
# What is Django QuerySet?
# Django QuerySet is a collection of database queries that can be executed against a database.
# It allows developers to retrieve, filter, and manipulate data from the database using Python.

# What is ASGI and WSGI and how are they different and used in Django?
# ASGI (Asynchronous Server Gateway Interface) and WSGI (Web Server Gateway Interface) are specifications for how a web server communicates with web applications.
# WSGI is synchronous and used for traditional synchronous web applications, while ASGI is asynchronous and used for asynchronous web applications.

# What is Django Rest Framework?
# Django Rest Framework is a powerful and flexible toolkit for building Web APIs in Django.
# It provides a set of tools and libraries for building RESTful APIs in Django. It is used to serialize and deserialize data.

# What is Serializer in Django Rest Framework?
# Serializer in Django Rest Framework is a class that converts complex data types (such as querysets and model instances) into
# native Python data types that can be easily rendered into JSON, XML, or other content types.

# What is the difference between render(), HttpResponse(), and redirect() in Django?
# render(): Renders a given template with a given context dictionary and returns an HttpResponse object. It is used to render HTML templates.
# HttpResponse(): Returns an HTTP response with the given content and content type. It is used to return simple text or HTML content.
# redirect(): Redirects to a specified URL. It can be a view name, URL, or the result of a view function.

# What are ForeignKey, ManyToManyField, and OneToOneField in Django models? Provide examples.
# ForeignKey: Represents a many-to-one relationship between two models. It is used to define a foreign key relationship.
# ManyToManyField: Represents a many-to-many relationship between two models. It is used to define a many-to-many relationship.
# OneToOneField: Represents a one-to-one relationship between two models. It is used to define a one-to-one relationship.

# What is the difference between HTTP methods (GET, POST, PUT, PATCH, DELETE)?
# GET: Requests data from a specified resource.
# POST: Submits data to be processed to a specified resource.
# PUT: Updates a specified resource with new data.
# PATCH: Updates a specified resource with partial data.
# DELETE: Deletes a specified resource.

# What are RESTful APIs? Explain their key principles.
# RESTful APIs are APIs that adhere to the principles of Representational State Transfer (REST).
# Key principles of RESTful APIs include stateless communication, uniform interface, resource-based architecture, and client-server architecture.

# What are the differences between authentication and authorization in REST APIs?
# Authentication is the process of verifying the identity of a user, while authorization is the process of determining what a user is allowed to do after they have been authenticated.

# Explain the concept of status codes in REST APIs. Provide examples of commonly used status codes.
# Status codes are standardized codes that indicate the result of an HTTP request. Examples of commonly used status codes include:
# 200 OK: The request was successful.
# 201 Created: The request has been fulfilled and a new resource has been created.
# 202 Accepted: The request has been accepted for processing.
# 301 Moved Permanently: The requested resource has been permanently moved to a new location.
# 400 Bad Request: The request could not be understood by the server.
# 404 Not Found: The requested resource could not be found.
# 401 Unauthorized: The request requires user authentication.
# 500 Internal Server Error: The server encountered an unexpected condition.

# What is the use of select_related() and prefetch_related()?
# select_related() and prefetch_related() are used to reduce the number of database queries when accessing related objects in Django.
# select_related() performs a single SQL query to retrieve related objects, while prefetch_related() performs two queries to retrieve related objects.

