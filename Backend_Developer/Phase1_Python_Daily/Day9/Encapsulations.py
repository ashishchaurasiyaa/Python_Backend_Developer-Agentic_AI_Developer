# Encapsulation = data hide karo, controlled access do
# Why Encapsulation?
# ✅ Data protection — bahar se directly change nahi kar sakte
# ✅ Validation — deposit mein negative amount nahi
# ✅ Flexibility — andar ka code change karo, bahar affect nahi
# ✅ Security — sensitive data hide karo
# Q: Encapsulation ka real use?
# A: BankAccount — balance private, deposit/withdraw se access
#
# Q: Polymorphism types?
# A: Overriding, Duck Typing, Operator Overloading
#
# Q: Abstract class vs Normal class?
# A: Abstract mein @abstractmethod — child MUST implement
#
# Q: __str__ vs __repr__?
# A: str = user friendly, repr = developer/debug friendly
#
# Q: Why use abstraction?
# A: Interface define karo, implementation hide karo

class BankAccount:
    def __init__(self, owner, balance):
        self.owner = owner
        self.balance = balance
        self.__pin = 201303


    def deposit(self, amount):
        if amount >= 0:
            self.balance += amount

    def get_balance(self):
        return self.balance

    def set_pin(self, old, new):
        if old == self.__pin:
            self.__pin = new
            print(f"Pin changed successfully")
        else:
            print("Wrong pin")

acc = BankAccount("Ashish", 1000)
print(f"Account owner: {acc.owner}")
print(f"Account balance: {acc.get_balance()}")
print(f"Bank Account Pincode : {acc._BankAccount__pin}")

acc.set_pin(201303, 201213)