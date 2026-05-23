name = "ada lovelace"
print(name.title())
print(name.upper())
print(name.lower())

first_name = "Ashish"
last_name = "Chaurasiya"

full_name = f"{first_name} {last_name}"
print(full_name)

print(f"Hello, {full_name.title()}")
print("\tPython")

favorite_language = 'Python '
print(favorite_language.rstrip())
print(favorite_language.lstrip())
print(favorite_language.strip())

nostarch_url = 'https://nostarch.com'
print(nostarch_url.removeprefix('https://'))

name = 'Eric'
print(f"Hello {name}")

print(name.lower())
print(name.upper())
print(name.title())

author = "Albert Einstein"
quote = "A person who never made a mistake never tried anything new."

print(f'{author} one said, "{quote}"')

filename = 'python_notes.txt'
print(filename.removesuffix('.txt'))


bicycles = ['trek', 'cannondale', 'redline', 'specialized']
print(bicycles)
print(bicycles[0].title())
print(bicycles[-1])

print(f"My First bicyle was a {bicycles[0].title()}")

motorcycles = ['honda', 'yamaha', 'suzuki']
print(motorcycles)
motorcycles[0] = 'ducati'
print(motorcycles)
motorcycles.append('honda')
print(motorcycles)

motorcycles.insert(0, 'ducati')
print(motorcycles)

# del motorcycles[0]

# Removing an Item Using the pop() Method
motorcycles = ['honda', 'yamaha', 'suzuki']
print(motorcycles)

popped_motorcycle = motorcycles.pop()
print(motorcycles)
print(popped_motorcycle)

# Popping Items from Any Position in a List
motorcycles = ['honda', 'yamaha', 'suzuki']
first_owned = motorcycles.pop(0)
print(f"The First motorcycle was {first_owned.title()}")

magicians = ['alice', 'david', 'carolina']
for magician in magicians:
    print(f"{magician.title()}, that was a great tick!")
    print(f"I can't wait to see your next trick, {magician.title()}.\n")

print("Thank you, everyone. That was a great magic show!")

pizzas = ["Pepperoni", "Margherita", "BBQ Chicken"]

for pizza in pizzas:
    print(pizza)
    print(f"I love pizza {pizza.title()}.\n")

animals = ["Dog", "Cat", "Rabbit"]
for animal in animals:
    print(animal)
    print(f"I like {animal.lower()} would make a great pet.\n")

# Range method

# for value in range(1,11):
#     print(value)

numbers = list(range(1, 11))
print(numbers)

even_numbsers = list(range(2,11,2))
print(even_numbsers)

squres = []
for value in range(2,11,2):
    value = value ** 2
    squres.append(value)
print(squres)


digits = [1, 2, 3, 4, 5, 6, 7, 8, 9, 0]

print(min(digits), max(digits), sum(digits))

squres=  [value ** 2 for value in range(1, 11)]
print(squres)

#  Counting to Twenty

for i in range(1, 21):
    print(i)

# One Million
# numbers = list(range(1, 1_000_001))
# for n in numbers:
#     print(n)

# Summing a Million

digits = [1, 2, 3, 4, 5, 6, 7, 8, 9, 0]

print(min(digits), max(digits), sum(digits))

#  Odd Numbers

odd_numbers = []
print(list(range(1, 11, 2)))

# Slicing a List

players = ['charles', 'martina', 'michael', 'florence', 'eli']
print(players[0:3])
print(players[1:5])
print(players[:4])
print(players[2:])
print(players[-3:])


for player in players[:3]:
    print(player.title())

my_foods = ['pizza', 'falafel', 'carrot cake']
friend_foods = my_foods[:]
print(friend_foods)

my_foods.append('cannoli')
print(my_foods)

cars = ['audi', 'bmw', 'subaru', 'toyota']
for car in cars:
    if car == 'audi':
        print(car.upper())
    else:
        print(car.title())

requested_topping = 'mushrooms'

if requested_topping != 'anchovies':
    print("Hold the anchovies!")

age = 19
if age >= 18:
    print("You are old enough to vote!")
    print("Have you registered to vote yet?")

fruitss = ["apple", "banana"]
fruitss.append('cherry')
print(fruitss)

# 2️⃣ insert(index, element) → Inserts an element at a specific index
fruits = ["apple", "banana"]
fruits.insert(2,'Banana')
print(fruits)

# 3️⃣ Using .extend(iterable) (Extends the list with another iterable)
fruits.extend(['Grapes','Apple','Mango','WaterMelon','Cherry'])
print(fruits)

a = ['Grapes', 'Apple', 'Mango', 'WaterMelon', 'Cherry']
b = ['apple', 'banana', 'cherry']

c = ['Grapes', 'Apple', ['apple', 'banana', 'cherry'], 'Mango', 'WaterMelon', 'Cherry']
d = ['apple', 'banana', 'cherry']

c.insert(2, d)
c[2].insert(2, ['apple', 'cherry', 'banana'])
print(c)

print(type('Hello World'))



