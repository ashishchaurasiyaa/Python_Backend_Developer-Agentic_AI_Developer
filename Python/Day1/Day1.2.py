# name = input("Enter your name: ")
# print(f"Hello My Name is {name}")
# age= int(input("Enter your age: "))
# print(f"I am {age} years old")
# print(type(age))
# print(type(name))

# age = input("Enter your age: ")
# print(age + 5)
# Hint: input() hamesha str deta hai — toh str ko int mein kaise badloge?
# TypeError: can only concatenate str (not "int") to str
# "Bhai! String ke saath int add nahi kar sakte!"

# age = int(input("Age batao: "))
# print(age + 5)
#
# user1 = int(input("entr the number"))
# user2 = int(input("enter the number"))
# print(type(user1))
# print(type(user2))
# print(user1 + user2)

"""
1 Burger = ₹150
User ne 3 burgers order kiye
Delivery charge = ₹30
GST = 5%

Total bill calculate karo — user se quantity lo input mein!
"""

# Burger_Price = 150
# Quantity = int(input("Enter the quantity: "))
# Delivery_Charge = 30
# GST = 5/100
#
# burger_quantity = Quantity * Burger_Price
# gst_amount = burger_quantity * GST
# total_bill = burger_quantity + gst_amount + Delivery_Charge
# print(f"User Completed Order. Total Bill is {total_bill}")


# Ab ek last challenge — poora bill receipt banao jaise real Swiggy receipt hoti hai:
"""
===================================
         SWIGGY BILL
===================================
Item     : Burger
Quantity : 3
Price    : ₹150 each
─────────────────────────────────
Subtotal : ₹450
GST 5%   : ₹22.5
Delivery : ₹30
─────────────────────────────────
Total    : ₹502.5
===================================
"""


print("=" * 30)
print(f"{'Swiggy Bill':^30}")
print("=" * 30)

item = "Burger"
quantity = int(input("Enter the quantity: "))
price = float(input("Enter the price: "))
print(f"{'Item':<20}:{item}")
print(f"{'Quantity':<20}:{quantity}")
print(f"{'Price':<20}:₹{price} each")
GST_RATE = 5 /100

print("-" * 30)
sub_total = (quantity * price)
print(f"{'Subtotal':<20}:{sub_total}")
gst = sub_total * GST_RATE
print(f"{'GST 5%':<20}:{gst}")
delivery_charge = 30
print(f"{'Delivery':<20}: {delivery_charge}")

print("-" * 30)
print(f"{'Total':<20}: {sub_total + gst + delivery_charge:.2f}")
print("=" * 30)
