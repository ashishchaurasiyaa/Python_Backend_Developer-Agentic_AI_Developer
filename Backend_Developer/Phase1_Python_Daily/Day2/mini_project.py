import random

def check_status(marks):
    return "Pass" if marks >= 40 else "Fail"

def get_marks(subject):
    while True:
        marks = int(input(f"Enter marks of {subject}: "))
        if marks >=0 and marks <= 100:
            return marks
        else:
            print("Invalid marks. Please enter marks between 0 and 100")

def check_overall_marks(marks_list):
    if min(marks_list) < 33:
        return "Fail"
    else:
        return "Pass"

while True:
    print("=" * 30)
    print(f"{'Main Menu':^30}")
    print("=" * 30)
    print("1. Grade Calculator")
    print("2. Number Guessing Game")
    print("3. Sum Calculator")
    print("4. Exit")
    print("=" * 30)

    choice = int(input("Enter your choice: "))

    if choice == 1:
        subjects = [ "Science", "Maths", "English", "Hindi", "Sanskrit", "History", "Geography"]
        marks_list = []
        for subject in subjects:
            marks = get_marks(subject)
            marks_list.append(marks)
            print(f"{subject:<15}: {marks} {check_status(marks)}")
        print(f"{'Grade Calculator':^30}")

        complete_marks = sum(marks_list)
        print(f"{'complete marks':<15}: {complete_marks}")
        marks = complete_marks/len(subjects)
        print(f"{'average marks':<15}: {marks:.2f}%")

        print("-"*30)
        overall = check_overall_marks(marks_list)
        if overall == "Pass":
            if marks >= 90:
                print("Grade A")
            elif marks >= 80:
                print("Grade B")
            elif marks >= 70:
                print("Grade C")
            elif marks >= 60:
                print("Grade D")
            elif marks >= 33:
                print("Grade E")
            print(f"Congratulations! You have passed the class with {marks:.2f}% marks")
        else:
            print("Failed! You have failed")
            for i in range(len(subjects)):
                if marks_list[i] < 33:
                    print(f"{subjects[i]}: {marks_list[i]}")

        print("-"*30)


    elif choice == 2:
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

    elif choice == 3:
        print("Sum Calculator")
        total = 0
        while True:
            num = int(input("Enter a number: "))
            if num == 0:
                break
            total += num
        print(f"Total = {total}")

    elif choice == 4:
        print("Exiting the program")
        break

    else:
        print("Invalid choice")

