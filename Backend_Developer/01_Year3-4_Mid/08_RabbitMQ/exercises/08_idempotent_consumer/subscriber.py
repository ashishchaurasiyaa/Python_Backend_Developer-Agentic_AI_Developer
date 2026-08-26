"""
RabbitMQ Exercise 08 — Idempotent Consumer
==========================================
TASK:
  1. TODO 1: SQLite mein check karo — payment_id already processed?
             Yes → ACK + return (skip, don't charge again)
  2. TODO 2: Process karo + DB mein insert karo
  3. TODO 3: basic_ack karo after successful processing + DB write

Subscriber exits after 3 messages (all 3 deliveries of same payment).

Run: python subscriber.py
Prereq: publisher.py already run (3 deliveries queued)
"""

import json
import os
import sqlite3
import pika

QUEUE   = "payment_queue_demo"
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "payments.db")
MSG_MAX = 3
received_count = [0]

# ── SQLite setup (in-process, no extra install) ───────────────────────────
def init_db(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS processed_payments (
            payment_id   TEXT    PRIMARY KEY,
            amount       REAL    NOT NULL,
            processed_at TEXT    DEFAULT (datetime('now'))
        )
    """)
    conn.commit()

db_conn = sqlite3.connect(DB_PATH)
init_db(db_conn)


def charge_customer(payment_id: str, amount: float):
    """Simulate calling external payment gateway."""
    print(f"  💳 CHARGING customer: {payment_id} = ₹{amount}")
    # In real code: stripe.PaymentIntent.create(amount=amount, ...)


# ── Message handler ───────────────────────────────────────────────────────
connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
channel    = connection.channel()
channel.basic_qos(prefetch_count=1)


def on_message(ch, method, properties, body):
    received_count[0] += 1
    data       = json.loads(body)
    payment_id = properties.message_id or data["payment_id"]
    amount     = data["amount"]
    attempt    = data.get("delivery_attempt", "?")

    print(f"\n[←] Delivery attempt {attempt} | payment_id={payment_id}")

    # ──────────────────────────────────────────────────────────────────
    # TODO 1: DB mein check karo — payment_id already process hua?
    #   Agar haan → print "duplicate skipped" + basic_ack + return
    #   Hint:
    #     row = db_conn.execute(
    #         "SELECT payment_id FROM processed_payments WHERE payment_id=?",
    #         (payment_id,)
    #     ).fetchone()
    #     if row:
    #         print(f"  ⏭️  DUPLICATE — {payment_id} already processed, skipping")
    #         ch.basic_ack(delivery_tag=method.delivery_tag)
    #         ...
    row = None   # ← TODO 1: isse badlo
    if row:
        pass     # ← reach nahi hoga tab tak jab tak TODO 1 nahi bhara
    # ──────────────────────────────────────────────────────────────────

    print(f"  🆕 First time processing {payment_id}")

    # ──────────────────────────────────────────────────────────────────
    # TODO 2: Payment process karo + DB mein insert karo.
    #   IMPORTANT: INSERT karo aur commit karo BEFORE ACK.
    #   Agar charge karo, ACK karo, fir DB crash → next delivery pe
    #   payment_id DB mein nahi hoga → double charge!
    #   Hint:
    #     charge_customer(payment_id, amount)
    #     db_conn.execute(
    #         "INSERT INTO processed_payments (payment_id, amount) VALUES (?, ?)",
    #         (payment_id, amount)
    #     )
    #     db_conn.commit()
    print("  ⚠️  TODO 2 nahi bhara — payment skipped")
    # ──────────────────────────────────────────────────────────────────

    # ──────────────────────────────────────────────────────────────────
    # TODO 3: ACK karo — message queue se permanently remove karo.
    #   ACK DB write ke BAAD hona chahiye (TODO 2 ke baad).
    #   Hint: ch.basic_ack(delivery_tag=method.delivery_tag)
    ch.basic_ack(delivery_tag=method.delivery_tag)   # ← move this after TODO 2
    # ──────────────────────────────────────────────────────────────────

    if received_count[0] >= MSG_MAX:
        ch.stop_consuming()


channel.basic_consume(queue=QUEUE, on_message_callback=on_message)

if __name__ == "__main__":
    print(f"[*] Waiting for {MSG_MAX} deliveries of same payment...")
    channel.start_consuming()
    print(f"\n[*] Done. Total deliveries received: {received_count[0]}")

    # Show DB state
    rows = db_conn.execute("SELECT payment_id, amount, processed_at FROM processed_payments").fetchall()
    print(f"\n[DB] Processed payments table ({len(rows)} rows):")
    for r in rows:
        print(f"  {r}")
    db_conn.close()
    connection.close()
