from abc import ABC, abstractmethod

class Payment(ABC):
    @abstractmethod
    def pay(self, amount):
        pass

class CreditCard(Payment):
    def pay(self, amount):
        print(f"Processing payment of {amount} using credit card")


class DebitCard(Payment):
    def pay(self, amount):
        print(f"Processing payment of {amount} using debit card")

class UPI(Payment):
    def pay(self, amount):
        print(f"Processing payment of {amount} using UPI")

payments = [CreditCard(), DebitCard(), UPI()]
for p in payments:
    print(p.pay(100))

