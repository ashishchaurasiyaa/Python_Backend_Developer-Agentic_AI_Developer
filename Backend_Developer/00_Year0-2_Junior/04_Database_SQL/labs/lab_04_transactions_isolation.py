"""
Lab 04 — Transactions, ACID & Isolation Levels
════════════════════════════════════════════════════════════════════════════════

ARCHITECTURE — Transaction guarantees:

    ACID:
    ┌─────────────────────────────────────────────────────────────────┐
    │ A — Atomicity:    All-or-nothing. Partial failure = full ROLLBACK│
    │ C — Consistency:  Constraints never violated (FK, UNIQUE, CHECK) │
    │ I — Isolation:    Concurrent transactions don't see each other's │
    │                   uncommitted changes (at default level)         │
    │ D — Durability:   Committed data survives crash (WAL / fsync)   │
    └─────────────────────────────────────────────────────────────────┘

ISOLATION LEVELS (least → most strict):
  READ UNCOMMITTED  — can see uncommitted changes (dirty reads) — rarely used
  READ COMMITTED    — sees only committed rows — PostgreSQL DEFAULT
  REPEATABLE READ   — same query returns same rows within tx (no phantom in PG)
  SERIALIZABLE      — transactions appear to run one-at-a-time

ANOMALIES:
  Dirty Read          — read uncommitted data that later rolls back (READ UNCOMMITTED)
  Non-repeatable Read — same SELECT returns different data within same tx (READ COMMITTED allows)
  Phantom Read        — range query returns different rows within same tx (REPEATABLE READ allows in MySQL)
  Lost Update         — two concurrent updates overwrite each other

SAVEPOINTS:
  Allow partial rollback within a transaction:
    SAVEPOINT sp1;
    ... some work ...
    ROLLBACK TO SAVEPOINT sp1;   ← undo since sp1, tx still active
    ... more work ...
    COMMIT;

INTERVIEW ANSWER:
  "Atomicity matlab ek transaction mein saare operations succeed hone chahiye,
   warna sab rollback. Isolation ka matlab hai concurrent transactions ek
   dusre ke uncommitted changes nahi dekhte — isolation level decide karta hai
   kitni isolation chahiye. Serializable strictest hai lekin slowest."

TASK:
  1. TODO 1: atomicity_demo() — insert two rows in one transaction, force failure mid-way,
             prove both rows are absent after rollback
  2. TODO 2: savepoint_demo() — insert 3 rows, savepoint after row 2, rollback to savepoint,
             prove only rows 1+2 visible
  3. TODO 3: isolation_committed_reads() — show that READ COMMITTED doesn't see
             uncommitted changes from another connection
  4. TODO 4: lost_update_demo() — simulate lost update without proper transaction;
             then fix it with a read-modify-write in a single UPDATE

RUN: python lab_04_transactions_isolation.py

Prereq: none — uses Python's built-in sqlite3
Note: SQLite isolation model differs from PostgreSQL but core concepts are identical.
     Real PostgreSQL isolation: SET TRANSACTION ISOLATION LEVEL REPEATABLE READ;
"""

import sqlite3
import threading

# ════════════════════════════════════════════════════════════════════════════
# SCHEMA + SETUP
# ════════════════════════════════════════════════════════════════════════════

def make_conn(isolation_level=None) -> sqlite3.Connection:
    """
    isolation_level=None → autocommit (each statement auto-commits).
    isolation_level=''   → deferred transactions (sqlite3 default).
    """
    conn = sqlite3.connect(":memory:", isolation_level=isolation_level)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE accounts (
            id      INTEGER PRIMARY KEY,
            owner   TEXT NOT NULL,
            balance REAL NOT NULL DEFAULT 0
        )
    """)
    conn.commit()
    return conn


def seed_accounts(conn: sqlite3.Connection):
    conn.execute("DELETE FROM accounts")
    conn.executemany(
        "INSERT INTO accounts(id, owner, balance) VALUES (?,?,?)",
        [(1,'Alice',1000.0),(2,'Bob',500.0),(3,'Carol',250.0)]
    )
    conn.commit()


# ════════════════════════════════════════════════════════════════════════════
# TODO 1 — Atomicity: all-or-nothing
# ════════════════════════════════════════════════════════════════════════════
"""
Demonstrate atomicity: if ANY statement fails inside a transaction,
ALL prior changes in that transaction must be rolled back.

Implement atomicity_demo(conn) -> dict:
  1. BEGIN (sqlite3 in Python: use conn.execute("BEGIN"))
  2. INSERT INTO accounts(id,owner,balance) VALUES (10,'Dave',800)
  3. INSERT INTO accounts(id,owner,balance) VALUES (11,'Eve',600)
  4. Force a failure: INSERT a row with id=10 again → UNIQUE violation
  5. ROLLBACK (in except block)
  6. Return count of rows where id IN (10,11)

Expected: count = 0 (both rows rolled back — partial insert must not survive)

Hint:
  conn.execute("BEGIN")
  try:
      conn.execute("INSERT INTO accounts VALUES (10,'Dave',800)")
      conn.execute("INSERT INTO accounts VALUES (11,'Eve',600)")
      conn.execute("INSERT INTO accounts VALUES (10,'DUPLICATE',0)")  # fails
      conn.execute("COMMIT")
  except sqlite3.IntegrityError:
      conn.execute("ROLLBACK")

  count = conn.execute("SELECT COUNT(*) FROM accounts WHERE id IN (10,11)").fetchone()[0]
  return {"dave_eve_count": count}
"""

def atomicity_demo(conn: sqlite3.Connection) -> dict:
    raise NotImplementedError(
        "TODO 1: BEGIN, insert 2 rows, force UNIQUE error, ROLLBACK, return count"
    )


# ════════════════════════════════════════════════════════════════════════════
# TODO 2 — Savepoints: partial rollback
# ════════════════════════════════════════════════════════════════════════════
"""
Demonstrate SAVEPOINT: roll back only part of a transaction.

Implement savepoint_demo(conn) -> dict:
  1. seed_accounts(conn) first
  2. BEGIN
  3. UPDATE accounts SET balance = 9999 WHERE id = 1     ← Alice
  4. SAVEPOINT sp1
  5. UPDATE accounts SET balance = 9999 WHERE id = 2     ← Bob
  6. ROLLBACK TO SAVEPOINT sp1                           ← undo Bob's update only
  7. COMMIT
  8. Return {"alice_balance": ..., "bob_balance": ...}

Expected:
  Alice balance = 9999 (her update was BEFORE the savepoint — kept)
  Bob balance = 500  (his update was AFTER savepoint — rolled back)

Hint:
  conn.execute("BEGIN")
  conn.execute("UPDATE accounts SET balance = 9999 WHERE id = 1")
  conn.execute("SAVEPOINT sp1")
  conn.execute("UPDATE accounts SET balance = 9999 WHERE id = 2")
  conn.execute("ROLLBACK TO SAVEPOINT sp1")
  conn.execute("COMMIT")
"""

def savepoint_demo(conn: sqlite3.Connection) -> dict:
    raise NotImplementedError(
        "TODO 2: BEGIN, UPDATE Alice, SAVEPOINT, UPDATE Bob, ROLLBACK TO SAVEPOINT, COMMIT"
    )


# ════════════════════════════════════════════════════════════════════════════
# TODO 3 — Read isolation: uncommitted changes not visible to other connections
# ════════════════════════════════════════════════════════════════════════════
"""
Demonstrate that connection B cannot see connection A's uncommitted change.

Implement isolation_committed_reads() -> dict:
  1. Create conn_a and conn_b (two separate connections to :memory: won't share data —
     use a FILE-BASED db for this test, then clean up)
     For simplicity: simulate with a shared list and two threads.

  Instead of two real connections (hard with :memory:), simulate the concept:
  Show that:
    - conn_a begins a transaction, updates Alice's balance to 5000, does NOT commit
    - conn_a reads Alice's balance WITHIN its transaction → sees 5000
    - conn_b reads Alice's balance → sees 1000 (original, committed value)
    - conn_a commits
    - conn_b reads again → now sees 5000

  Use a temporary file database:
    import tempfile, os
    db_file = tempfile.mktemp(suffix='.db')

  Return:
    {
      "conn_b_before_commit": <balance conn_b sees before conn_a commits>,
      "conn_b_after_commit":  <balance conn_b sees after conn_a commits>
    }

Hint:
  import tempfile, os
  db_file = tempfile.mktemp(suffix='.db')

  conn_a = sqlite3.connect(db_file)
  conn_b = sqlite3.connect(db_file)
  conn_a.row_factory = sqlite3.Row
  conn_b.row_factory = sqlite3.Row

  # Setup
  conn_a.execute("CREATE TABLE accounts (...)")
  conn_a.execute("INSERT INTO accounts VALUES (1,'Alice',1000)")
  conn_a.commit()

  # conn_a begins tx, updates, does NOT commit
  conn_a.execute("BEGIN")
  conn_a.execute("UPDATE accounts SET balance=5000 WHERE id=1")

  # conn_b reads — should see 1000 (conn_a uncommitted)
  before = conn_b.execute("SELECT balance FROM accounts WHERE id=1").fetchone()[0]

  # conn_a commits
  conn_a.commit()

  # conn_b reads again — should see 5000
  after = conn_b.execute("SELECT balance FROM accounts WHERE id=1").fetchone()[0]

  conn_a.close(); conn_b.close(); os.unlink(db_file)
  return {"conn_b_before_commit": before, "conn_b_after_commit": after}
"""

def isolation_committed_reads() -> dict:
    raise NotImplementedError(
        "TODO 3: Two connections, one updates without commit, other reads before+after commit"
    )


# ════════════════════════════════════════════════════════════════════════════
# TODO 4 — Lost Update: the problem + the fix
# ════════════════════════════════════════════════════════════════════════════
"""
Lost update: two transactions read the same value, both modify it,
one overwrites the other's change.

BROKEN PATTERN (simulated):
  t1_balance = read(alice)      # reads 1000
  t2_balance = read(alice)      # reads 1000
  write(alice, t1_balance - 200)  # writes 800
  write(alice, t2_balance - 300)  # writes 700  ← OVERWRITES t1's 200 debit!
  # Expected: 1000 - 200 - 300 = 500
  # Actual:   700 (t1's debit lost)

FIXED PATTERN:
  Use atomic SQL: UPDATE accounts SET balance = balance - 200 WHERE id = 1
  The DB reads + writes in one atomic operation — no race condition possible.

Implement:
  lost_update_broken(conn) -> float:
    Simulate the broken pattern: two read-modify-write pairs that race.
    Return final Alice balance.

  lost_update_fixed(conn) -> float:
    Use atomic UPDATE: balance = balance - 200 then balance = balance - 300
    Return final Alice balance.

Hint for broken:
  # Read
  bal = conn.execute("SELECT balance FROM accounts WHERE id=1").fetchone()[0]
  # Simulate "another transaction" running between read and write
  t2_bal = conn.execute("SELECT balance FROM accounts WHERE id=1").fetchone()[0]
  # First write
  conn.execute("UPDATE accounts SET balance=? WHERE id=1", (bal - 200,))
  conn.commit()
  # Second write overwrites first (lost update)
  conn.execute("UPDATE accounts SET balance=? WHERE id=1", (t2_bal - 300,))
  conn.commit()
  return conn.execute("SELECT balance FROM accounts WHERE id=1").fetchone()[0]

Hint for fixed:
  conn.execute("UPDATE accounts SET balance = balance - 200 WHERE id=1")
  conn.commit()
  conn.execute("UPDATE accounts SET balance = balance - 300 WHERE id=1")
  conn.commit()
  return conn.execute("SELECT balance FROM accounts WHERE id=1").fetchone()[0]
"""

def lost_update_broken(conn: sqlite3.Connection) -> float:
    raise NotImplementedError(
        "TODO 4a: read-modify-write twice — second write overwrites first (lost update)"
    )

def lost_update_fixed(conn: sqlite3.Connection) -> float:
    raise NotImplementedError(
        "TODO 4b: atomic UPDATE balance = balance - N (no separate read)"
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

    # ── TODO 1: Atomicity ────────────────────────────────────────────────────
    print("\n── TODO 1: Atomicity — rollback on failure ──")
    conn1 = make_conn()
    result = atomicity_demo(conn1)
    check("1a. dave_eve_count = 0 (both rows rolled back)",
          result.get("dave_eve_count") == 0,
          f"Expected 0. Got {result.get('dave_eve_count')}. "
          f"Both rows should be rolled back — atomicity violated if count > 0")
    conn1.close()

    # ── TODO 2: Savepoints ───────────────────────────────────────────────────
    print("\n── TODO 2: Savepoints — partial rollback ──")
    conn2 = make_conn()
    seed_accounts(conn2)
    result = savepoint_demo(conn2)
    check("2a. Alice balance = 9999 (before savepoint — kept)",
          abs(result.get("alice_balance", 0) - 9999) < 0.01,
          f"Alice={result.get('alice_balance')} — update before SAVEPOINT should persist")
    check("2b. Bob balance = 500 (after savepoint — rolled back)",
          abs(result.get("bob_balance", 0) - 500) < 0.01,
          f"Bob={result.get('bob_balance')} — update after SAVEPOINT should be rolled back")
    conn2.close()

    # ── TODO 3: Isolation ────────────────────────────────────────────────────
    print("\n── TODO 3: Read isolation — uncommitted not visible ──")
    result = isolation_committed_reads()
    check("3a. Before commit: conn_b sees original balance (1000)",
          abs(result.get("conn_b_before_commit", -1) - 1000) < 0.01,
          f"Expected 1000. Got {result.get('conn_b_before_commit')}. "
          f"Uncommitted change should NOT be visible to other connection")
    check("3b. After commit: conn_b sees updated balance (5000)",
          abs(result.get("conn_b_after_commit", -1) - 5000) < 0.01,
          f"Expected 5000. Got {result.get('conn_b_after_commit')}. "
          f"After conn_a commits, conn_b should see the new value")

    # ── TODO 4: Lost Update ──────────────────────────────────────────────────
    print("\n── TODO 4: Lost Update ──")

    conn4a = make_conn()
    seed_accounts(conn4a)
    broken_bal = lost_update_broken(conn4a)
    check("4a. Broken: lost update (t1's debit overwritten by t2)",
          abs(broken_bal - 700) < 0.01,
          f"Expected 700 (lost update — t1 deducted 200 but t2 overwrote with 1000-300=700). "
          f"Got {broken_bal}. Are you actually simulating the race condition?")
    conn4a.close()

    conn4b = make_conn()
    seed_accounts(conn4b)
    fixed_bal = lost_update_fixed(conn4b)
    check("4b. Fixed: atomic update (both debits applied correctly)",
          abs(fixed_bal - 500) < 0.01,
          f"Expected 500 (1000 - 200 - 300). Got {fixed_bal}. "
          f"Use atomic: UPDATE balance = balance - N")
    conn4b.close()

    print(f"\n{'═'*50}")
    print(f"  {passed} passed  |  {failed} failed")
    if failed == 0:
        print("  ✅ ALL PASS — Lab 04 complete!")
    else:
        print("  ❌ Fix the failing TODOs above and rerun.")
    print('═'*50)


# ════════════════════════════════════════════════════════════════════════════
# SOCH (Answer ALOUD)
# ════════════════════════════════════════════════════════════════════════════
"""
Q1: ACID mein "Consistency" ka kya matlab hai?
    (Database constraints — FK, UNIQUE, CHECK — never violated even during tx)

Q2: SAVEPOINT aur nested transaction mein kya fark hai?
    ROLLBACK TO SAVEPOINT ke baad outer transaction kya state mein hoti hai?

Q3: Dirty Read, Non-repeatable Read, Phantom Read explain karo with examples.

Q4: PostgreSQL ka default isolation level kya hai?
    MySQL (InnoDB) ka kya hai? Kya difference padta hai?
    (PG: READ COMMITTED; MySQL: REPEATABLE READ)

Q5: Lost update ko SELECT FOR UPDATE se kaise prevent karte hain?
    Kya koi case hai jahan atomic UPDATE bhi kaam na kare?
    (Yes: conditional updates — e.g., only deduct if balance >= amount — need FOR UPDATE)
"""

if __name__ == "__main__":
    run_tests()
