# for i in range(1, 101):
#     if i % 2 == 0:
#         continue
#     print(i)
#

total = 0
while True:
    num = int(input("Enter a number: "))
    if num == 0:
        break
    total += num
print(f"Total = {total}")
