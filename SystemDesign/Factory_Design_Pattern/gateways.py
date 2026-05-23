# What id Factory_Design_Pattern
"""
The Factory Design Pattern is a creational Design Patterns that provides an interface for creating objects in a superclass but allows
subclass but allows subclasses to alter the type of objects that will be created.

Key Components:
1> Product(Interface or Abstract Class):-> Define the common behavior of all objects that can be created by the factory.
2-> Concreate Products:-> Implementation of the Product interface.
3-> Creator (Abstract Factory) -> Declares the factory method, which returns object of the product type
4-> Concreate Creators -> Override the factory method to return specific Product implementations.
5-> Clients -> Uses the factory to create objects without knowing their specific class.

Real-World Use Cases: Payment Gateways:Dynamically select between Stripe, PayPal, or Razorpay to process payments.
, Django ORM:
, File Parsers:,Dynamically load parsers for different file formats (CSV, JSON, XML).
 Logging: Create loggers dynamically for different output channels (FileLogger, ConsoleLogger, DatabaseLogger).
 , User Authentication: Generate authentication handlers dynamically (JWTAuthHandler, OAuthHandler).

Advantages of the Factory Method Pattern
Encapsulation: Hides the object creation process, reducing coupling between the client and the created objects.
Flexibility:Makes it easy to introduce new types of objects without modifying existing code.
Code Reusability:Centralizes object creation, which can be reused across the application.
Open-Closed Principle:You can add new products (concrete classes) without changing existing code.
Improves Testability:Easier to mock or replace factories in tests.
"""

from .gateway_interface import PaymentGateway

class PayPalPaymentGateway(PaymentGateway):
    """
    Concrete implementation of the PayPal payment gateway.
    """
    def __init__(self, client_id: str, secret: str):
        self.client_id = client_id
        self.secret = secret

    def authenticate(self) -> bool:
        """
        Simulate authentication with the PayPal API using client credentials.
        """
        print(f"Authenticating with PayPal using Client ID: {self.client_id}")
        # Simulate successful authentication
        return True

    def process_payment(self, amount: float) -> str:
        """
        Simulates processing a payment via PayPal.
        """
        if self.authenticate():
            return f"Payment of ${amount:.2f} processed successfully via PayPal."
        else:
            return "Authentication failed. Payment could not be processed."
