# Hour 1 — def, return, multiple return values

def greet(name):
    return f"Hello, {name}!"

print(greet("Ashish"))


# Multiple return values

def min_max(nums):
    return min(nums), max(nums)

low, high = min_max([3, 1, 4, 1, 5, 9])
print(low, high)

#Return Early

def is_even(n):
    if n % 2 == 0:
        return True
    return False
print(is_even(10))

#Short Form

def is_even(n):
    return n % 2 == 0
print(is_even(10))


# ⏰ Hour 2 — Default Args + *args + **kwargs

def greet(name, msg="Good Morning"):
    return f"{msg}, {name}!"
print(greet("Ashish"))

# # ── *args — multiple positional args ──

def total(*nums):
    return sum(nums)
print(total(1, 2, 3, 4, 5,10))

# # ── **kwargs — multiple keyword args ──

def profile(**info):
    print(info)
    for key, value in info.items():
        print(f"{key}: {value}")

profile(name="Ashish", age=28, city="Noida")

# # ── DONO SAATH ──
def show(*args, **kwargs):
    print("Args: ", args)
    print("Kwargs: ", kwargs)
show(1, 2, 3, name="Ashish", city="Noida")

# ⏰ Hour 3 — Lambda + map + filter
# ── LAMBDA — one line function ──

square = lambda x: x**2
print(square(5))

add = lambda x, y: x + y
print(add(5, 6))

sub = lambda x,y : x - y
print(sub(5, 6))

# ── MAP — har element pe function apply karo ──

nums = [1, 2, 3, 4, 5]
squares = list(map(lambda x: x**2, nums))
print(squares)

# ── FILTER — condition true wale rakhho ──

evens = list(filter(lambda x:x % 2 == 0, nums))
print(evens)

# ── SORTED with lambda ──

students = [("Rahul", 25), ("Priya", 22), ("Amit", 28)]
sorted_s = sorted(students, key=lambda x: x[1])
print(sorted_s)


# ⏰ Hour 4 — Scope

#local scope
def my_func():
    x = 10
    print(x)

my_func()

# ── GLOBAL SCOPE ──
name = "Ashish"
def show_name():
    print(name) #we can read global variable

show_name()

# # ── GLOBAL MODIFY karna ──
count = 0
def increment():
    global count
    count += 1

increment()
increment()
print(count)

# ── ENCLOSING SCOPE (nested functions) ──
def outer():
    msg = "Hello"
    def inner():
        print(msg)
    inner()
outer()