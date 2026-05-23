import random

secret =  random.randint(1,100)
attempts = 0

print("=" * 35)
print(f"{'Guess the number':^35}")
print("=" * 35)
print(f"I'm thinking of a number between 1 and 100")

while True:
    guess = int(input("Enter your guess: "))
    attempts +=1
    if guess < secret:
        print("Too low")
    elif guess > secret:
        print("Too high")
    else:
        print(f"You guessed it in {attempts} attempts")
        break

