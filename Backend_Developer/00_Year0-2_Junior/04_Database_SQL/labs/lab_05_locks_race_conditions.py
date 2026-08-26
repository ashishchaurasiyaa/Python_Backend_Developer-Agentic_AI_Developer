"""
Lab 05 — Locks & Race Conditions
════════════════════════════════════════════════════════════════════════════════

ARCHITECTURE — Pessimistic vs Optimistic Locking:

    PESSIMISTIC (SELECT FOR UPDATE):
    ┌─────────────────────────────────────────────────────────────┐
    │  T1: SELECT * FROM orders WHERE id=5 FOR UPDATE  ← lock    │
    │  T1: UPDATE orders SET status='shipped' WHERE id=5          │
    │  T1: COMMIT                                     ← unlock    │
    │                                                             │
    │  T2: SELECT * FROM orders WHERE id=5 FOR UPDATE  ← BLOCKS  │
    │  T2: (waits until T1 commits)                               │
    │  T2: proceeds with current data                             │
    └─────────────────────────────────────────────────────────────┘

    OPTIMISTIC (version column):
    ┌─────────────────────────────────────────────────────────────┐
    │  T1: SELECT id, balance, version FROM accounts WHERE id=1   │
    │  T1:  → balance=1000, version=5                             │
    │  T2: SELECT id, balance, version FROM accounts WHERE id=1   │
    │  T2:  → balance=1000, version=5                             │
    │                                                             │
    │  T1: UPDATE ... SET balance=800, version=6                  │
    │      WHERE id=1 AND version=5   ← 1 row updated ✅          │
    │                                                             │
    │  T2: UPDATE ... SET balance=700, version=6                  │
    │      WHERE id=1 AND version=5   ← 0 rows updated ❌ CONFLICT│
    │  T2: retry or raise ConflictError                           │
    └─────────────────────────────────────────────────────────────┘

WHEN TO USE WHICH:
  Pessimistic — high contention (many writes to same row); short transactions
  Optimistic  — low contention; long user-facing operations; distributed systems

SKIP LOCKED (queue pattern):
  SELECT * FROM jobs WHERE status='pending' FOR UPDATE SKIP LOCKED LIMIT 1
  Multiple workers each grab a different job — no deadlock, no waiting.

DEADLOCK:
  T1 locks row A, then tries to lock row B
  T2 locks row B, then tries to lock row A
  → circular wait → database kills one transaction
  Prevention: ALWAYS lock rows in the SAME ORDER (lower id first)

INTERVIEW ANSWER:
  "SELECT FOR UPDATE row-level lock leta hai — dusri transaction wait karti hai
   tab tak jab tak pehli commit/rollback na kare. Optimistic locking mein koi lock
   nahi, sirf version check: UPDATE WHERE version = old_version. Agar 0 rows update
   hue toh conflict — retry karo. Low-contention systems mein optimistic better
   hota hai kyunki no lock wait."

TASK:
  1. TODO 1: pessimistic_transfer() — simulate SELECT FOR UPDATE with serialized writes
  2. TODO 2: optimistic_update() — version-based CAS (compare-and-swap) update
  3. TODO 3: optimistic_with_retry() — retry on conflict
  4. TODO 4: stock_deduction_unsafe() — race condition demo (oversell)
  5. TODO 5: stock_deduction_safe() — fix with atomic UPDATE + constraint

RUN: python lab_05_locks_race_conditions.py

Prereq: none — uses Python's built-in sqlite3
Note: SQLite has file-level locking; PostgreSQL has true row-level locks.
     Concepts are identical; in production use PostgreSQL with FOR UPDATE.
"""

import sqlite3
import threading
import time

# ════════════════════════════════════════════════════════════════════════════
# SCHEMA + SETUP
# ════════════════════════════════════════════════════════════════════════════

def setup_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE accounts (
            id      INTEGER PRIMARY KEY,
            owner   TEXT NOT NULL,
            balance REAL NOT NULL,
            version INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE products (
            id    INTEGER PRIMARY KEY,
            name  TEXT NOT NULL,
            stock INTEGER NOT NULL CHECK(stock >= 0)   -- constraint prevents negative stock
        );

        INSERT INTO accounts VALUES (1,'Alice',1000,1),(2,'Bob',500,1);
        INSERT INTO products VALUES (1,'Widget',5);
    """)
    conn.commit()
    return conn


# ════════════════════════════════════════════════════════════════════════════
# TODO 1 — Pessimistic locking: serialized transfer
# ════════════════════════════════════════════════════════════════════════════
"""
Implement pessimistic_transfer(conn, from_id, to_id, amount) -> bool:

  In SQLite, true FOR UPDATE doesn't exist — simulate with IMMEDIATE transaction
  (acquires write lock immediately, blocking other writers):

    conn.execute("BEGIN IMMEDIATE")   ← SQLite write lock
    try:
        from_row = conn.execute(
            "SELECT balance FROM accounts WHERE id=?", (from_id,)
        ).fetchone()
        if from_row["balance"] < amount:
            conn.execute("ROLLBACK")
            return False
        conn.execute("UPDATE accounts SET balance = balance - ? WHERE id=?", (amount, from_id))
        conn.execute("UPDATE accounts SET balance = balance + ? WHERE id=?", (amount, to_id))
        conn.execute("COMMIT")
        return True
    except Exception:
        conn.execute("ROLLBACK")
        return False

  Note: In PostgreSQL, this would be:
    BEGIN;
    SELECT balance FROM accounts WHERE id=1 FOR UPDATE;  ← row-level lock
    UPDATE accounts SET balance = balance - 200 WHERE id=1;
    COMMIT;
"""

def pessimistic_transfer(conn: sqlite3.Connection, from_id: int, to_id: int, amount: float) -> bool:
    raise NotImplementedError(
        "TODO 1: BEGIN IMMEDIATE, check balance, UPDATE both accounts, COMMIT or ROLLBACK"
    )


# ════════════════════════════════════════════════════════════════════════════
# TODO 2 — Optimistic locking: version-based update
# ════════════════════════════════════════════════════════════════════════════
"""
Implement optimistic_update(conn, account_id, debit_amount) -> bool:

  1. Read current balance AND version
  2. Check balance >= debit_amount
  3. UPDATE WHERE id=? AND version=? (the old version)
     SET balance = balance - debit_amount, version = version + 1
  4. Check rowcount: if 0 → conflict (someone else updated) → return False
  5. COMMIT; return True on success

  Hint:
    row = conn.execute(
        "SELECT balance, version FROM accounts WHERE id=?", (account_id,)
    ).fetchone()
    old_version = row["version"]

    if row["balance"] < debit_amount:
        return False

    cur = conn.execute(
        "UPDATE accounts SET balance = balance - ?, version = version + 1 "
        "WHERE id = ? AND version = ?",
        (debit_amount, account_id, old_version)
    )
    conn.commit()
    return cur.rowcount == 1   # 0 = conflict (version changed by someone else)
"""

def optimistic_update(conn: sqlite3.Connection, account_id: int, debit_amount: float) -> bool:
    raise NotImplementedError(
        "TODO 2: read balance+version, UPDATE WHERE version=old_version, return rowcount==1"
    )


# ════════════════════════════════════════════════════════════════════════════
# TODO 3 — Optimistic with retry
# ════════════════════════════════════════════════════════════════════════════
"""
Implement optimistic_with_retry(conn, account_id, debit, max_retries=3) -> bool:

  Retry optimistic_update up to max_retries times if it returns False (conflict).
  If still failing after max_retries: return False.

  Hint:
    for attempt in range(max_retries):
        if optimistic_update(conn, account_id, debit):
            return True
        time.sleep(0.01)   # brief backoff before retry
    return False
"""

def optimistic_with_retry(conn: sqlite3.Connection, account_id: int, debit: float, max_retries: int = 3) -> bool:
    raise NotImplementedError(
        "TODO 3: retry optimistic_update up to max_retries times"
    )


# ════════════════════════════════════════════════════════════════════════════
# TODO 4 — Race condition: oversell demo (UNSAFE)
# ════════════════════════════════════════════════════════════════════════════
"""
Implement stock_deduction_unsafe(conn, product_id, qty) -> bool:

  The UNSAFE pattern (read-check-write):
    1. Read stock
    2. Check stock >= qty
    3. If yes: UPDATE stock = stock - qty
    4. Return True if deducted, False if insufficient stock

  This has a race condition: two concurrent requests can both read stock=1,
  both pass the check, and both deduct — resulting in stock=-1 (oversell).
  The CHECK constraint prevents the final write, raising IntegrityError.

  Hint:
    row = conn.execute("SELECT stock FROM products WHERE id=?", (product_id,)).fetchone()
    if row["stock"] < qty:
        return False
    conn.execute("UPDATE products SET stock = stock - ? WHERE id=?", (qty, product_id))
    conn.commit()
    return True
"""

def stock_deduction_unsafe(conn: sqlite3.Connection, product_id: int, qty: int) -> bool:
    raise NotImplementedError(
        "TODO 4: read stock, check qty, UPDATE (no lock — demonstrates oversell race)"
    )


# ════════════════════════════════════════════════════════════════════════════
# TODO 5 — Safe stock deduction: atomic UPDATE with constraint
# ════════════════════════════════════════════════════════════════════════════
"""
Implement stock_deduction_safe(conn, product_id, qty) -> bool:

  The SAFE pattern: single atomic UPDATE with WHERE stock >= qty check.
  No separate read step — the check and deduct happen in one SQL statement.

  If rowcount == 0: insufficient stock (or product not found) → return False
  If rowcount == 1: success → return True

  Hint:
    cur = conn.execute(
        "UPDATE products SET stock = stock - ? WHERE id = ? AND stock >= ?",
        (qty, product_id, qty)
    )
    conn.commit()
    return cur.rowcount == 1
"""

def stock_deduction_safe(conn: sqlite3.Connection, product_id: int, qty: int) -> bool:
    raise NotImplementedError(
        "TODO 5: UPDATE stock = stock - qty WHERE id=? AND stock >= qty; return rowcount==1"
    )


# ════════════════════════════════════════════════════════════════════════════
# TESTS
# ════════════════════════════════════════════════════════════════════════════

def run_tests():
    passed = 0
    failed = 0

    def check(label, condition, msg=""):
        nonlocal passed, failed
        if condition:
            print(f"✅ {label}")
            passed += 1
        else:
            print(f"❌ {label} — FAIL: {msg}")
            failed += 1

    def get_balance(conn, uid):
        return conn.execute("SELECT balance FROM accounts WHERE id=?", (uid,)).fetchone()[0]

    def get_version(conn, uid):
        return conn.execute("SELECT version FROM accounts WHERE id=?", (uid,)).fetchone()[0]

    def get_stock(conn, pid):
        return conn.execute("SELECT stock FROM products WHERE id=?", (pid,)).fetchone()[0]

    # ── TODO 1: Pessimistic Transfer ─────────────────────────────────────────
    print("\n── TODO 1: Pessimistic transfer (serialized) ──")
    conn1 = setup_db()

    ok = pessimistic_transfer(conn1, 1, 2, 200)
    check("1a. Transfer 200 Alice→Bob succeeds", ok, f"Expected True. Got {ok}")
    check("1b. Alice balance = 800",
          abs(get_balance(conn1, 1) - 800) < 0.01,
          f"Alice={get_balance(conn1,1)}")
    check("1c. Bob balance = 700",
          abs(get_balance(conn1, 2) - 700) < 0.01,
          f"Bob={get_balance(conn1,2)}")

    fail = pessimistic_transfer(conn1, 2, 1, 9999)
    check("1d. Transfer more than balance returns False",
          not fail, f"Expected False (insufficient funds). Got {fail}")
    check("1e. Balances unchanged after failed transfer",
          abs(get_balance(conn1, 2) - 700) < 0.01,
          f"Bob balance changed despite failed transfer: {get_balance(conn1,2)}")
    conn1.close()

    # ── TODO 2: Optimistic Update ────────────────────────────────────────────
    print("\n── TODO 2: Optimistic update (version check) ──")
    conn2 = setup_db()

    ok = optimistic_update(conn2, 1, 100)
    check("2a. First optimistic update succeeds", ok, f"Expected True. Got {ok}")
    check("2b. Alice balance = 900",
          abs(get_balance(conn2, 1) - 900) < 0.01, f"Got {get_balance(conn2,1)}")
    check("2c. Version incremented to 2",
          get_version(conn2, 1) == 2, f"Version={get_version(conn2,1)}")

    # Simulate conflict: manually advance version without going through optimistic_update
    conn2.execute("UPDATE accounts SET version = 99 WHERE id = 1")
    conn2.commit()
    # Now try optimistic_update — it will read version=99 but... actually it reads fresh
    # Better test: interfere between read and write. Simulate by corrupting version after read.
    # Simplest test: just verify the WHERE version=? clause works by checking rowcount=0
    # when we call with stale data manually
    cur = conn2.execute(
        "UPDATE accounts SET balance = balance - 50, version = version + 1 "
        "WHERE id = 1 AND version = 1"  # wrong version (current is 99)
    )
    conn2.commit()
    check("2d. Update with stale version returns 0 rows (conflict detected)",
          cur.rowcount == 0, f"rowcount={cur.rowcount} — version check not working")
    conn2.close()

    # ── TODO 3: Retry ────────────────────────────────────────────────────────
    print("\n── TODO 3: Optimistic retry ──")
    conn3 = setup_db()
    result = optimistic_with_retry(conn3, 1, 50)
    check("3a. Retry succeeds on clean update",
          result, "Expected True on first attempt (no conflict)")
    check("3b. Alice balance = 950",
          abs(get_balance(conn3, 1) - 950) < 0.01, f"Got {get_balance(conn3,1)}")

    result_fail = optimistic_with_retry(conn3, 1, 9999, max_retries=2)
    check("3c. Insufficient funds returns False even with retries",
          not result_fail, "Expected False — can't deduct 9999 from ~950")
    conn3.close()

    # ── TODO 4: Unsafe stock ─────────────────────────────────────────────────
    print("\n── TODO 4: Unsafe stock deduction (race condition demo) ──")
    conn4 = setup_db()

    ok1 = stock_deduction_unsafe(conn4, 1, 3)
    check("4a. Deduct 3 from stock=5 succeeds", ok1, f"Expected True. Got {ok1}")
    check("4b. Stock now = 2", get_stock(conn4, 1) == 2, f"Stock={get_stock(conn4,1)}")

    ok2 = stock_deduction_unsafe(conn4, 1, 2)
    check("4c. Deduct 2 from stock=2 succeeds", ok2, f"Expected True. Got {ok2}")
    check("4d. Stock now = 0", get_stock(conn4, 1) == 0, f"Stock={get_stock(conn4,1)}")

    fail = stock_deduction_unsafe(conn4, 1, 1)
    check("4e. Deduct from stock=0 returns False", not fail, f"Expected False. Got {fail}")
    conn4.close()

    # ── TODO 5: Safe atomic stock ────────────────────────────────────────────
    print("\n── TODO 5: Safe stock deduction (atomic UPDATE) ──")
    conn5 = setup_db()

    ok = stock_deduction_safe(conn5, 1, 4)
    check("5a. Atomic deduct 4 from stock=5 succeeds", ok, f"Expected True. Got {ok}")
    check("5b. Stock now = 1", get_stock(conn5, 1) == 1, f"Stock={get_stock(conn5,1)}")

    # Concurrent-safe: try to over-deduct
    fail = stock_deduction_safe(conn5, 1, 2)
    check("5c. Atomic deduct 2 from stock=1 returns False",
          not fail, f"Expected False (stock=1 < qty=2). Got {fail}")
    check("5d. Stock unchanged at 1 (no partial deduction)",
          get_stock(conn5, 1) == 1, f"Stock={get_stock(conn5,1)} — should be 1")
    conn5.close()

    print(f"\n{'═'*50}")
    print(f"  {passed} passed  |  {failed} failed")
    if failed == 0:
        print("  ✅ ALL PASS — Lab 05 complete!")
    else:
        print("  ❌ Fix the failing TODOs above and rerun.")
    print('═'*50)


# ════════════════════════════════════════════════════════════════════════════
# SOCH (Answer ALOUD)
# ════════════════════════════════════════════════════════════════════════════
"""
Q1: SELECT FOR UPDATE kya karta hai? Kab use karo?
    (Row-level lock — other transactions must wait to lock the same row.
     Use when: check-then-act patterns, financial transfers, inventory)

Q2: Pessimistic vs optimistic locking — kab kaunsa better hai?
    (Pessimistic: high contention, short tx; Optimistic: low contention, long user-facing flows)

Q3: Deadlock kab hota hai? Prevention strategy kya hai?
    (T1 locks A then B; T2 locks B then A → circular wait.
     Fix: ALWAYS lock rows in same order — e.g., lower id first)

Q4: "Oversell" problem kaise hota hai? stock_deduction_safe() kaise fix karta hai?
    (Read-check-write race. Atomic UPDATE WHERE stock >= qty eliminates separate read.)

Q5: SKIP LOCKED kya hai? Kahan use hota hai?
    (SELECT ... FOR UPDATE SKIP LOCKED — worker queue pattern.
     Multiple workers grab different rows; already-locked rows skipped.
     Prevents multiple workers processing the same job.)
"""

if __name__ == "__main__":
    run_tests()
