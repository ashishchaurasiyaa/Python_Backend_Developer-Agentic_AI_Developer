"""
# Q1 — BankAccount class
# __init__(owner, balance=0)
# deposit(amount)
# withdraw(amount) → insufficient funds check
# get_balance()
# __str__ → "Account[Ashish]: ₹5000"
"""

class BankAccount:
    def __init__(self, owner, balance=0):
        self.owner = owner
        self.balance = balance


    def deposit(self, amount):
        if amount >= 0:
            print(f"Depositing {amount} to {self.owner}'s account")
            return
        self.balance += amount
        print(f"!₹{amount} deposited to {self.owner}'s account")

    def withdraw(self, amount):
        if amount <= 0:
            print(f"Amount must be positive")
            return
        if amount > self.balance:
            print(f"Insufficient funds! Balance: ₹{self.balance}")
            return
        self.balance -= amount
        print(f"₹{amount} withdrawn from {self.owner}'s account")

    def get_balance(self):
        return self.balance

    def __str__(self):
        return f"Account[{self.owner}]: ₹{self.balance}"

account = BankAccount("Ashish")
print(account)
account.deposit(5000)
print(account)
account.withdraw(1000)
print(account)
account.withdraw(99999)
print(account)

account.deposit(-100)