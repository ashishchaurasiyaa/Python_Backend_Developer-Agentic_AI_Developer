"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
*ARGS AND **KWARGS — Variadic Arguments
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ARCHITECTURE UNDERSTANDING:
  *args   = variable positional arguments → tuple inside function
  **kwargs = variable keyword arguments  → dict inside function

  * and ** are UNPACKING operators — they work in two directions:
  1. In function DEFINITION: pack multiple args into tuple/dict
  2. In function CALL:       unpack tuple/dict into individual args

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. *ARGS — VARIABLE POSITIONAL ARGS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

def add(*numbers):
    """*args packs all positional args into a tuple."""
    print(type(numbers))    # <class 'tuple'>
    return sum(numbers)

print(add(1, 2))            # 3
print(add(1, 2, 3, 4, 5))  # 15

# Mixed: normal + *args
def greet(greeting, *names):
    for name in names:
        print(f"{greeting}, {name}!")

greet("Hello", "Alice", "Bob", "Charlie")
# Hello, Alice!
# Hello, Bob!
# Hello, Charlie!

# *args in middle is NOT allowed: def f(a, *b, c) ← c must be keyword-only

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. **KWARGS — VARIABLE KEYWORD ARGS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

def create_user(**info):
    """**kwargs packs all keyword args into a dict."""
    print(type(info))       # <class 'dict'>
    for key, value in info.items():
        print(f"  {key}: {value}")

create_user(name="Ashish", age=28, city="Delhi", role="Backend Dev")

# Real use: flexible config function
def connect_db(host, port, **options):
    """Options can be any extra DB settings."""
    config = {"host": host, "port": port}
    config.update(options)   # merge extra kwargs
    return config

conn = connect_db("localhost", 5432,
                  dbname="myapp",
                  user="postgres",
                  password="secret",
                  pool_size=10)
print(conn)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. CORRECT ARGUMENT ORDER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
INTERVIEW Q: What is the correct order of parameters?
A: def func(positional, *args, keyword_only, **kwargs)
   1. Regular positional args
   2. *args
   3. Keyword-only args (after *)
   4. **kwargs
"""

def full_example(a, b, *args, keyword_only=10, **kwargs):
    print(f"a={a}, b={b}")
    print(f"args={args}")
    print(f"keyword_only={keyword_only}")
    print(f"kwargs={kwargs}")

full_example(1, 2, 3, 4, 5, keyword_only=99, x="hello", y="world")
# a=1, b=2
# args=(3, 4, 5)
# keyword_only=99
# kwargs={'x': 'hello', 'y': 'world'}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. UNPACKING OPERATOR (*, **) IN CALLS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
* and ** also UNPACK when calling a function.
"""

def add(a, b, c):
    return a + b + c

numbers = [1, 2, 3]
print(add(*numbers))        # same as add(1, 2, 3) → 6

coords = {"a": 10, "b": 20, "c": 30}
print(add(**coords))        # same as add(a=10, b=20, c=30) → 60

# Merge dicts (Python 3.9+: {**d1, **d2})
defaults = {"color": "blue", "size": 10, "font": "Arial"}
overrides = {"color": "red", "size": 14}
merged = {**defaults, **overrides}   # override wins
print(merged)   # {'color': 'red', 'size': 14, 'font': 'Arial'}

# Merge lists
list1 = [1, 2, 3]
list2 = [4, 5, 6]
merged_list = [*list1, *list2]       # [1, 2, 3, 4, 5, 6]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. REAL-WORLD PATTERNS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

# Pattern 1: Wrapper / Decorator using *args, **kwargs
import functools
import time

def timer(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):        # accepts ANY function signature
        start = time.time()
        result = func(*args, **kwargs)   # passes through all args unchanged
        elapsed = time.time() - start
        print(f"{func.__name__} took {elapsed:.3f}s")
        return result
    return wrapper

@timer
def fetch_data(url, timeout=30, retries=3):
    time.sleep(0.1)
    return f"Data from {url}"

fetch_data("https://api.example.com", timeout=10)

# Pattern 2: Logging wrapper
def log_calls(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        print(f"CALL: {func.__name__}({args}, {kwargs})")
        try:
            result = func(*args, **kwargs)
            print(f"RETURN: {result}")
            return result
        except Exception as e:
            print(f"ERROR: {e}")
            raise
    return wrapper

# Pattern 3: Flask/FastAPI style route decorator
routes = {}

def route(path, methods=("GET",)):
    def decorator(func):
        routes[path] = {"handler": func, "methods": methods}
        return func
    return decorator

@route("/users", methods=("GET", "POST"))
def users_handler(*args, **kwargs):
    pass

# Pattern 4: Pass-through constructor
class APIClient:
    def __init__(self, base_url, **session_kwargs):
        """session_kwargs go directly to requests.Session"""
        self.base_url = base_url
        self.timeout = session_kwargs.pop("timeout", 30)
        self.headers = session_kwargs.pop("headers", {})
        # Extra kwargs can go to underlying library

client = APIClient(
    "https://api.example.com",
    timeout=10,
    headers={"Authorization": "Bearer token123"},
)

# Pattern 5: Keyword-only enforcement (Python 3+)
def create_order(*, product_id, quantity, discount=0.0):
    """
    * forces ALL args to be keyword-only.
    Prevents: create_order(123, 2) — position mistake
    Requires: create_order(product_id=123, quantity=2)
    """
    return {"product_id": product_id, "quantity": quantity, "discount": discount}

order = create_order(product_id=42, quantity=3, discount=0.1)
print(order)

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INTERVIEW Q&A:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q: *args vs **kwargs — when to use which?
A: *args  → when number of POSITIONAL args is unknown (sum of N numbers)
   **kwargs → when number of NAMED options is unknown (config params)
   Both together → wrapper functions that need to forward all args

Q: Why do decorators always use *args, **kwargs?
A: Decorator wraps ANY function — it doesn't know the wrapped
   function's signature. Using *args/**kwargs makes it universal.

Q: What does ** do when merging dicts?
A: Unpacks dict into keyword arguments.
   {**d1, **d2} creates new dict with all keys from both.
   If same key exists, rightmost dict wins.

Q: Keyword-only arguments kya hain?
A: def f(a, *, b): ← b can only be passed as keyword, not positional
   Use when: arg order matters and you want to force clarity.
   Example: sorted(items, key=func, reverse=True) ← key/reverse are keyword-only
"""
