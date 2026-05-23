# Note -> The Strategy Design Pattern is a behavioral design pattern that allows you to define a family of algorithms
# (strategies), encapsulate each one in a separate class, and make them interchangeable at runtime.
#It decouples the logic that uses the algorithms (the context) from the specific algorithm implementations.

# Why Use the Strategy Design Pattern?
# Flexibility: It allows you to select and change algorithms dynamically at runtime.
# Separation of Concerns: Each algorithm is encapsulated in its own class, which makes the code easier to understand and maintain.
# Scalability: Adding a new strategy doesn't require modifying existing code, adhering to the Open/Closed Principle.
# Readability: It improves code readability by clearly defining where each algorithm is implemented and how it is used.

# What is the Strategy Design Pattern?
# The Strategy Design Pattern defines three key components ->
# Context: Maintains a reference to a strategy and provides a way to interact with it.
# Strategy Interface: Declares the methods that all concrete strategies must implement.
# Concrete Strategies: Implement the interface and provide specific algorithm implementations.

# How Does It Work?
# The Strategy Pattern works by having the client code interact with the context, which delegates the work to
# the selected strategy. This way, the context remains agnostic of the specific algorithm details.


from abc import ABC, abstractmethod

# Define the Strategy Interface
class PaymentStrategy(ABC):
    @abstractmethod
    def pay(self, amount):
        pass

# Implement Concrete Strategies
class CreditCardPayment(PaymentStrategy):
    def pay(self, amount):
        print(f"Paid {amount} Credit Card Payment")


class PayPalPayment(PaymentStrategy):
    def pay(self, amount):
        print(f"Paid {amount} PayPal Payment")

class BankTransferPayment(PaymentStrategy):
    def pay(self, amount):
        print(f"Paid {amount} Bank Transfer Payment")


# Create the Context Class

class PaymentContext:
    def __init__(self, payment_strategy):
        self.payment_strategy = payment_strategy

    def set_payment_strategy(self, payment_strategy):
        self.payment_strategy = payment_strategy

    def make_payment(self, amount):
        self.payment_strategy.pay(amount)

# Use the Strategy Pattern

if __name__ == "__main__":
    credit_card = CreditCardPayment()
    paypal = PayPalPayment()
    bank_transfer = BankTransferPayment()

    payment_context = PaymentContext(credit_card)
    payment_context.make_payment(300)
    payment_context.set_payment_strategy(paypal)
    payment_context.make_payment(300)
    payment_context.set_payment_strategy(bank_transfer)
    payment_context.make_payment(300)
