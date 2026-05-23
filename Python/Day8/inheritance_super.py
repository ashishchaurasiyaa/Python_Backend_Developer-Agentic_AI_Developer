class Animal:
    def __init__(self, name, sound):
        self.name = name
        self.sound = sound

    def speak(self):
        print(f"{self.name} makes {self.sound}")


    def eat(self):
        print(f"{self.name} is eating")

# Child class

class Dog(Animal):
    def __init__(self, name, breed):
        super().__init__(name, "bark")
        self.breed = breed

    def fetch(self):
        print(f"{self.name} is fetching")

    #Method Override - Replace the parent method

    def speak(self):
        print(f"{self.name} ({self.breed}) barks: WOOF WOOF!")


class Cat(Animal):
    def __init__(self, name, indoor=True):
        super().__init__(name, "meow")
        self.indoor = indoor


    def speak(self):
        mood = "softly" if self.indoor else "loudly"
        print(f"{self.name} meows {mood}")


d = Dog("Tommy", "Labrador")
c = Cat("Whiskers", indoor=True)

d.speak()
d.eat()
d.fetch()

c.speak()   # Whiskers meows softly: Meow~

# ── ISINSTANCE CHECK ──
print(isinstance(d, Dog))     # True
print(isinstance(d, Animal))  # True — Dog IS-A Animal!
print(isinstance(c, Dog))     # False
