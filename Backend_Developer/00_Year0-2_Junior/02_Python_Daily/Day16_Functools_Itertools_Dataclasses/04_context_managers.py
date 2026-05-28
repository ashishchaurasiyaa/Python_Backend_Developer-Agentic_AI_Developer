"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTEXT MANAGERS — __enter__, __exit__, contextlib
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ARCHITECTURE UNDERSTANDING:
  Context Manager = object that manages setup and teardown.

  Protocol:
  __enter__(self)                → called when entering 'with' block
                                   return value goes to 'as' variable
  __exit__(self, exc_type, exc_val, tb)
                                → called when leaving 'with' block
                                   even if exception occurred
                                   return True → suppress exception
                                   return False/None → re-raise exception

  WHY IT MATTERS:
  → Guarantees cleanup code runs (file close, DB connection release, lock release)
  → Used in: file I/O, DB sessions, threading.Lock, test setup, timing

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import time
import contextlib
import threading
import sqlite3
from typing import Generator

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. CLASS-BASED CONTEXT MANAGER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

class Timer:
    """Measure code execution time."""

    def __enter__(self):
        self.start = time.perf_counter()
        return self                          # accessible as 'timer' in: with Timer() as timer

    def __exit__(self, exc_type, exc_val, tb):
        self.elapsed = time.perf_counter() - self.start
        print(f"Elapsed: {self.elapsed:.4f}s")
        return False                         # don't suppress exceptions

with Timer() as t:
    time.sleep(0.1)
    result = sum(range(1_000_000))

print(f"Result: {result}")
print(f"Time stored: {t.elapsed:.4f}s")     # access elapsed after block

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. DATABASE CONNECTION MANAGER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

class DatabaseConnection:
    """Manages DB connection lifecycle — auto-commit or rollback."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = None
        self.cursor = None

    def __enter__(self):
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        print("DB connected")
        return self.cursor                  # caller gets cursor

    def __exit__(self, exc_type, exc_val, tb):
        if exc_type is None:
            self.conn.commit()              # success → commit
            print("Transaction committed")
        else:
            self.conn.rollback()            # error → rollback
            print(f"Transaction rolled back due to: {exc_val}")
        self.cursor.close()
        self.conn.close()
        print("DB disconnected")
        return False                        # don't suppress the exception


with DatabaseConnection(":memory:") as cursor:
    cursor.execute("CREATE TABLE users (id INTEGER, name TEXT)")
    cursor.execute("INSERT INTO users VALUES (1, 'Ashish')")
    # auto-commits when block exits normally

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. EXCEPTION SUPPRESSION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

class SuppressException:
    """Suppress specific exception types."""

    def __init__(self, *exceptions):
        self.exceptions = exceptions

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, tb):
        if exc_type and issubclass(exc_type, self.exceptions):
            print(f"Suppressed: {exc_val}")
            return True     # suppress — don't re-raise
        return False        # re-raise any other exception

with SuppressException(FileNotFoundError, KeyError):
    raise FileNotFoundError("File not found")   # suppressed!
    print("This won't run")

print("Execution continues here")

# Python has this built-in: contextlib.suppress
with contextlib.suppress(FileNotFoundError):
    open("nonexistent.txt")

print("File not found, but we moved on")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. GENERATOR-BASED (@contextmanager) — SIMPLER SYNTAX
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
@contextmanager:
  Code BEFORE yield → __enter__
  yield value       → the 'as' value
  Code AFTER yield  → __exit__
  try/finally ensures cleanup runs even on exception
"""

@contextlib.contextmanager
def timer_cm():
    """Simple timing context manager."""
    start = time.perf_counter()
    try:
        yield                               # code in with block runs here
    finally:
        elapsed = time.perf_counter() - start
        print(f"Took {elapsed:.4f}s")

with timer_cm():
    time.sleep(0.05)


@contextlib.contextmanager
def managed_db(db_path: str):
    """SQLite connection with auto commit/rollback."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        yield cursor                        # give cursor to user
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

with managed_db(":memory:") as cur:
    cur.execute("CREATE TABLE t (v INTEGER)")
    cur.execute("INSERT INTO t VALUES (42)")


@contextlib.contextmanager
def temp_directory():
    """Create temp dir, yield it, clean up after."""
    import tempfile, shutil, pathlib
    tmpdir = pathlib.Path(tempfile.mkdtemp())
    try:
        yield tmpdir
    finally:
        shutil.rmtree(tmpdir)

with temp_directory() as tmpdir:
    (tmpdir / "test.txt").write_text("hello")
    print(list(tmpdir.iterdir()))
# tmpdir is deleted after block

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. REAL-WORLD: THREADING LOCK
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
threading.Lock() is a context manager — always use with 'with'.
"""

lock = threading.Lock()
shared_counter = 0

def safe_increment():
    global shared_counter
    with lock:                  # acquires lock, releases even on exception
        shared_counter += 1

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 6. NESTED CONTEXT MANAGERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

# Multiple context managers in one line
with open("a.txt", "w") as f1, open("b.txt", "w") as f2:
    f1.write("File A")
    f2.write("File B")

# contextlib.ExitStack — dynamic number of context managers
def process_files(file_paths: list[str]):
    with contextlib.ExitStack() as stack:
        files = [stack.enter_context(open(p)) for p in file_paths]
        for f in files:
            print(f.read())

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 7. REAL-WORLD: FASTAPI LIFESPAN PATTERN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

# This is exactly how FastAPI lifespan works!
@contextlib.asynccontextmanager
async def lifespan(app):
    # Startup code (before yield)
    print("Starting up: connecting to DB, loading models...")
    db_pool = "fake_pool"           # await create_pool(...)
    app.state.db = db_pool

    yield                           # app runs here

    # Shutdown code (after yield)
    print("Shutting down: closing DB pool...")
    # await db_pool.close()

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INTERVIEW Q&A:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q: __exit__ mein return True ka matlab?
A: Exception suppress karo — outside code ko pata nahi chalega.
   return False / None → exception normal tarah propagate hoga.

Q: @contextmanager mein yield ke baad exception aaye to?
A: try/finally use karo in generator:
   try: yield
   finally: cleanup()  ← runs even on exception

Q: Class-based vs @contextmanager — kab kya?
A: @contextmanager → simple, one-off, generator style preferred
   Class-based      → reusable, needs __repr__, multiple methods,
                      need to inherit from it

Q: ExitStack kab use karte hain?
A: Jab number of context managers runtime pe decide ho
   (like opening N files from a list).
   Dynamic alternative to nested with statements.
"""

import pathlib
pathlib.Path("a.txt").unlink(missing_ok=True)
pathlib.Path("b.txt").unlink(missing_ok=True)
