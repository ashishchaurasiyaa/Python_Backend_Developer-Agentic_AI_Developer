"""
# Q1 — Custom Exception chain
# InvalidAgeError, InvalidEmailError banao
# validate_user(name, age, email) function
# Sab validations check karo
"""

class UserValidationError(Exception):
    pass

class InvalidAgeError(UserValidationError):
    def __init__(self, age):
        self.age = age
        super().__init__(f"Age {age} is invalid. User must be at least 18 years old. {self.age}")
class InvalidEmailError(UserValidationError):
    def __init__(self, email):
        self.email = email
        super().__init__(f"Email {email} is invalid. Invalid email format. {self.email}")


class InvalidUserError(UserValidationError):
    def __init__(self, name):
        self.name = name
        super().__init__(f"User {name} is invalid. User must have a name. {self.name}")



def validate_user(name, age, email):
    if not name or not name.strip():
        raise InvalidUserError(name)

    if not isinstance(age,int) or age < 18:
        raise InvalidAgeError(age)

    if '@' not in email or "." not in email:
        raise InvalidEmailError(email)

    return "User is valid"

try:
    result = validate_user("Ashish", 20, 'ashishkumar.mailto@gmail.com')
    print(result)
except InvalidUserError as e:
    print(f"Validation Error: {e}")