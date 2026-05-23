"""
1. Card Insert
2. PIN verify
3. Options menu
   - Balance check
   - Withdraw
   - Deposit
4. Account type select
5. Amount input
6. Balance check
   - Enough → Transaction success
   - Less   → Insufficient balance
7. SMS notification
8. Receipt (Yes/No)
9. Card return

1. PIN verify       → Comparison operator
2. Balance check    → Comparison operator
3. Withdraw         → Assignment operator
4. Deposit          → Assignment operator
5. Receipt          → Ternary operator


"""

# ATM Machine
import time
print("=" * 30)
print(f"{'WELCOME TO ATM':^30}")
print("=" * 30)

balance = 10000
correct_pin = "1234"
pin = input("Enter PIN: ")
if pin == correct_pin:
    print("Access Granted")
else:
    print("Invalid PIN")
    exit()

# # Withdraw option
amount = int(input('Enter amount to withdraw:'))
if amount <= balance:
    balance -= amount
    print(f"Amount withdrawn: {amount}")
    print(f"Remaining balance: {balance}")
    print("Transaction successful")
    print("Thank you for using ATM")
else:
    print("Insufficient balance")
    exit()

receipt = input("Print Receipt? (y/n):")
message = "Receipt printed" if receipt == "y" else "Receipt not printed"
print(message)

phone = "XXXXXX" + correct_pin[-4:]
print(f"Sms sent: ₹{amount} debited balance: ₹{balance}")
print("\nPlease take your card...")
print("Thank you for banking with us!")
print("=" * 30)