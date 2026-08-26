"""
Celery Lab 06 — DB Transaction + Celery (NO WORKER NEEDED)
============================================================
OBJECTIVE: classic production bug samjho — Celery task dispatch BEFORE DB commit.

SCENARIO:
  Django view mein order create karo aur task dispatch karo.
  Agar task dispatch COMMIT se pehle hota hai:
    → task runs, DB se order read karta hai → ORDER NOT FOUND (not committed yet)
    → ya phir transaction rollback hoti hai → task chal chuka tha for non-existent order

NO WORKER NEEDED — task_always_eager=True mode: .delay() call same process mein
task immediately execute karta hai. Isse timing clearly dikhti hai.

TASK:
  1. TODO 1: bad_dispatch() mein task commit se PEHLE dispatch karo
  2. TODO 2: good_dispatch() mein task commit ke BAAD dispatch karo
  3. TODO 3: on_commit_dispatch() mein Django-style callback implement karo

Run: python 06_django_transaction_on_commit.py   (no docker needed!)
"""

import sqlite3
import tempfile
import os
from celery import Celery

# ── In-process Celery (no real broker needed) ─────────────────────────────
sim_app = Celery("lab06", broker="memory://", backend="cache+memory://")
sim_app.conf.task_always_eager = True        # .delay() runs synchronously, in-process
sim_app.conf.task_always_eager_propagates = True

# ── Shared temp DB (real SQLite file so two connections see same data) ─────
_db_fd, DB_PATH = tempfile.mkstemp(suffix=".db")
os.close(_db_fd)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id       INTEGER PRIMARY KEY,
            status   TEXT    NOT NULL,
            amount   REAL    NOT NULL
        )
    """)
    conn.commit()
    conn.close()


@sim_app.task
def process_order(order_id: int) -> dict:
    """
    Simulates what a Celery WORKER would do: open a FRESH DB connection and
    read the order. With task_always_eager, this runs inline when .delay() is called.
    A fresh connection honours SQLite's isolation — uncommitted rows are invisible.
    """
    worker_conn = sqlite3.connect(DB_PATH)    # fresh connection = what real worker gets
    row = worker_conn.execute(
        "SELECT id, status, amount FROM orders WHERE id=?", (order_id,)
    ).fetchone()
    worker_conn.close()

    if row is None:
        return {"found": False, "order_id": order_id,
                "error": "Order NOT FOUND — not committed yet!"}
    return {"found": True, "id": row[0], "status": row[1], "amount": row[2]}


# ─────────────────────────────────────────────────────────────
# BAD PATTERN — dispatch INSIDE transaction (before commit)
# ─────────────────────────────────────────────────────────────
def bad_dispatch(order_id: int, amount: float) -> dict:
    """
    ❌ BAD: task dispatch before commit.
    Real world: Django view calls .delay() inside transaction.atomic() block.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.execute("BEGIN")
    conn.execute("INSERT INTO orders VALUES (?, 'pending', ?)", (order_id, amount))

    # ── TODO 1: yahan task dispatch karo (COMMIT se pehle) ───────────────
    # process_order.delay(order_id)
    task_result = None   # ← isse badlo
    # ─────────────────────────────────────────────────────────────────────

    conn.execute("COMMIT")
    conn.close()
    return task_result.get() if task_result else {"error": "TODO 1 nahi bhara"}


# ─────────────────────────────────────────────────────────────
# GOOD PATTERN — dispatch AFTER commit
# ─────────────────────────────────────────────────────────────
def good_dispatch(order_id: int, amount: float) -> dict:
    """
    ✅ GOOD: commit first, then dispatch.
    Simple fix — explicit commit ke baad task dispatch karo.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.execute("BEGIN")
    conn.execute("INSERT INTO orders VALUES (?, 'pending', ?)", (order_id, amount))

    # ── TODO 2: pehle COMMIT karo, phir task dispatch karo ───────────────
    # conn.execute("COMMIT")
    # conn.close()
    # task_result = process_order.delay(order_id)
    conn.close()         # ← isse badlo: commit + close + delay
    task_result = None   # ← isse badlo
    # ─────────────────────────────────────────────────────────────────────

    return task_result.get() if task_result else {"error": "TODO 2 nahi bhara"}


# ─────────────────────────────────────────────────────────────
# BEST PATTERN — on_commit callback (Django-style)
# ─────────────────────────────────────────────────────────────
class AtomicContext:
    """
    Django transaction.atomic() ka simulation.
    on_commit() callbacks sirf tab chalte hain jab COMMIT succeed kare.
    """
    def __init__(self, conn):
        self.conn = conn
        self._callbacks = []

    def on_commit(self, fn):
        """Register a callback to run AFTER commit."""
        self._callbacks.append(fn)

    def __enter__(self):
        self.conn.execute("BEGIN")
        return self

    def __exit__(self, exc_type, *_):
        if exc_type:
            self.conn.execute("ROLLBACK")
            self._callbacks.clear()          # on_commit callbacks NAHI chalte on rollback
        else:
            self.conn.execute("COMMIT")
            for cb in self._callbacks:
                cb()                         # callbacks run AFTER commit


def on_commit_dispatch(order_id: int, amount: float) -> dict:
    """
    ✅ BEST: on_commit callback pattern — Django equivalent.
    Task dispatch is registered as a callback, runs only when commit succeeds.
    """
    conn = sqlite3.connect(DB_PATH)

    # ── TODO 3: on_commit callback se task dispatch karo ─────────────────
    # with AtomicContext(conn) as txn:
    #     conn.execute("INSERT INTO orders VALUES (?, 'pending', ?)", (order_id, amount))
    #     txn.on_commit(lambda: process_order.delay(order_id))
    # Hint: task_result = ??? (on_commit callbacks ka return value nahi milta directly)
    task_result = None   # ← TODO 3: implement karo aur result capture karo
    conn.close()
    # ─────────────────────────────────────────────────────────────────────

    if task_result is None:
        # Manual approach for TODO 3 — just verify DB has the row
        verify_conn = sqlite3.connect(DB_PATH)
        row = verify_conn.execute(
            "SELECT id, status, amount FROM orders WHERE id=?", (order_id,)
        ).fetchone()
        verify_conn.close()
        if row:
            return {"found": True, "id": row[0], "note": "TODO 3 ke liye direct .delay() call karo"}
        return {"error": "TODO 3 nahi bhara"}
    return task_result.get()


# ─────────────────────────────────────────────────────────────
# ROLLBACK SCENARIO — task dispatched but transaction rolls back
# ─────────────────────────────────────────────────────────────
def rollback_scenario(order_id: int, amount: float) -> dict:
    """
    Yeh scenario dikhata hai: task dispatched + commit se PEHLE exception.
    Task chal chuka → transaction rollback → order KABHI exist nahi kiya.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.execute("BEGIN")
    conn.execute("INSERT INTO orders VALUES (?, 'pending', ?)", (order_id, amount))

    # Task dispatched inside transaction (bad pattern)
    r = process_order.delay(order_id)       # runs immediately (eager mode)
    task_read = r.get()                     # task ne kya dekha?

    # Simulate unexpected exception → ROLLBACK
    conn.execute("ROLLBACK")
    conn.close()

    # Verify: order DB mein exist karta hai?
    verify_conn = sqlite3.connect(DB_PATH)
    final = verify_conn.execute(
        "SELECT id FROM orders WHERE id=?", (order_id,)
    ).fetchone()
    verify_conn.close()

    return {
        "task_saw": task_read,
        "db_has_order_after_rollback": final is not None,
    }


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
def main():
    init_db()

    print("\n[SCENARIO 1] BAD — task dispatch BEFORE commit")
    res = bad_dispatch(order_id=1, amount=999.0)
    print(f"  Task result: {res}")
    if not res.get("found"):
        print("  ❌ Task ne order nahi dekha — commit nahi hua tha tab")
    else:
        print("  ✅ TODO 1 bhara")

    print("\n[SCENARIO 2] GOOD — dispatch AFTER commit")
    res2 = good_dispatch(order_id=2, amount=1500.0)
    print(f"  Task result: {res2}")
    if res2.get("found"):
        print("  ✅ Task ne order dekha — commit ho chuka tha")
    else:
        print("  ❌ TODO 2 bharo: pehle COMMIT karo, phir .delay()")

    print("\n[SCENARIO 3] BEST — on_commit callback")
    res3 = on_commit_dispatch(order_id=3, amount=2000.0)
    print(f"  Task result: {res3}")
    if res3.get("found"):
        print("  ✅ on_commit pattern kaam kar raha hai")
    else:
        print("  ⚠️  TODO 3 implement karo (AtomicContext.on_commit)")

    print("\n[SCENARIO 4] ROLLBACK — task chal gaya but order never committed")
    res4 = rollback_scenario(order_id=4, amount=500.0)
    print(f"  Task saw order: {res4['task_saw']}")
    print(f"  Order in DB after rollback: {res4['db_has_order_after_rollback']}")
    if not res4["db_has_order_after_rollback"]:
        print("  ⚠️  DANGER: task chal chuka, order rollback ho gaya — orphan task!")
        print("  Fix: on_commit callback pattern use karo (Scenario 3)")

    print("\n" + "─" * 55)
    print("SOCH QUESTIONS:")
    print("  1. Django transaction.on_commit() kab callbacks chalata hai?")
    print("  2. FastAPI + SQLAlchemy mein on_commit equivalent kya hai?")
    print("  3. Transactional Outbox pattern kya hai? Kab use karo?")
    print("  4. Task payload mein object pass karo ya sirf ID?")

    # Cleanup
    os.unlink(DB_PATH)


if __name__ == "__main__":
    main()
