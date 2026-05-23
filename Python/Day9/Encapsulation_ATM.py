class ATM:
    def __init__(self, balance, pin):
        self.__balance = balance
        self.__pin = pin

    def deposit(self, amount):
        if amount > 0:
            self.__balance += amount
            return f"Deposited: {amount}"
        return "Invalid amount"

    def withdraw(self, amount, pin):
        if pin != self.__pin:
            return "Invalid PIN"
        if amount > self.__balance:
            return "Insufficient balance"

        self.__balance -= amount
        return f"Withdrew: {amount}"

    def check_balance(self, pin):
        if pin != self.__pin:
            return "Invalid PIN"
        return f"Balance: {self.__balance}"

    def change_pin(self, old_pin, new_pin):
        if old_pin != self.__pin:
            return "Invalid PIN"
        self.__pin = new_pin
        return "PIN changes successfully"


atm = ATM(1000, 1234)
print(atm.withdraw(500, 1234))
print(atm.check_balance(1234))
print(atm.change_pin(1234, 4321))

