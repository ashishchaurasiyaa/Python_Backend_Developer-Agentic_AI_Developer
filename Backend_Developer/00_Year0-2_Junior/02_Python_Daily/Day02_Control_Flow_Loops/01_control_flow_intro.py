#Grade Calculator


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


subjects = [ "Science", "Maths", "English", "Hindi", "Sanskrit", "History", "Geography"]
marks_list = []
for subject in subjects:
    marks = get_marks(subject)
    marks_list.append(marks)
    print(f"{subject:<15}: {marks} {check_status(marks)}")
print("-"*30)

print(f"{'Grade Calculator':^30}")
print("-"*30)
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


