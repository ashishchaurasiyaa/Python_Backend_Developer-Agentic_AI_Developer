class BaseClass:
    num_base_calls = 0


    def call_me(self) -> None:
        print("Calling method on Base Class")
        self.num_base_calls += 1

class LeftSubClass(BaseClass):
    num_left_calls = 0

    def call_me(self) -> None:
        super().call_me()
        print("Calling method on Left Sub Class")
        self.num_left_calls += 1

class RightSubClass(BaseClass):
    num_right_calls = 0

    def call_me(self) -> None:
        super().call_me()
        print("Calling method on Right Sub Class")
        self.num_right_calls += 1

class SubClass(LeftSubClass, RightSubClass):
    num_sub_calls = 0

    def call_me(self) -> None:
        super().call_me()
        print("Calling method on Sub Class")
        self.num_sub_calls += 1

obj = SubClass()
obj.call_me()

print(SubClass.__mro__)

