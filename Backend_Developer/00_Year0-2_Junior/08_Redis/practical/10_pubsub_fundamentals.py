"""
Redis Practical 10 — Pub/Sub Fundamentals
Run: python 10_pubsub_fundamentals.py [basic|pattern|failover|vsstreams|all]

Prerequisites:
  pip install "redis[hiredis]>=5.0"
  docker run -d --name redis -p 6379:6379 redis:7-alpine
"""

import sys
import time
import threading
import redis

r = redis.Redis(host='localhost', port=6379, decode_responses=True)


# ════════════════════════════════════════════
# SECTION 1: BASIC PUBLISH / SUBSCRIBE
# ════════════════════════════════════════════
def demo_basic():
    print("\n" + "=" * 50)
    print("  SECTION 1: BASIC PUB/SUB")
    print("=" * 50)

    received = []

    def listener():
        sub = redis.Redis(decode_responses=True)
        p = sub.pubsub()
        p.subscribe("notifications")
        for msg in p.listen():
            if msg["type"] == "message":
                received.append(msg["data"])
                break                      # demo: ek message ke baad exit

    t = threading.Thread(target=listener, daemon=True)
    t.start()
    time.sleep(0.3)                        # listener SUBSCRIBE ho jaye pehle

    n = r.publish("notifications", "New order #123 created")
    print(f"📤 PUBLISH → {n} subscriber(s) ko delivered")
    t.join(timeout=2)

    if received:
        print(f"✅ Subscriber received: {received[0]}")
    else:
        print("⚠️ Kuch nahi mila — listener subscribe hone se pehle publish ho gaya")

    # ─── GOTCHA: agar koi subscribe nahi tha, message GONE FOREVER ───
    n = r.publish("nobody_listening", "this message has no audience")
    print(f"📤 PUBLISH to empty channel → {n} subscribers (0 = message lost forever)")


# ════════════════════════════════════════════
# SECTION 2: PATTERN SUBSCRIPTIONS — PSUBSCRIBE
# ════════════════════════════════════════════
def demo_pattern():
    print("\n" + "=" * 50)
    print("  SECTION 2: PSUBSCRIBE — PATTERN MATCHING")
    print("=" * 50)

    received = []

    def listener():
        sub = redis.Redis(decode_responses=True)
        p = sub.pubsub()
        p.psubscribe("user.*.notifications")
        for msg in p.listen():
            if msg["type"] == "pmessage":
                received.append((msg["channel"], msg["data"]))
                if len(received) == 2:
                    break

    t = threading.Thread(target=listener, daemon=True)
    t.start()
    time.sleep(0.3)

    r.publish("user.123.notifications", "order shipped")
    r.publish("user.456.notifications", "payment received")
    t.join(timeout=2)

    print("✅ Ek PSUBSCRIBE se multiple users ke channels cover ho gaye:")
    for channel, data in received:
        user_id = channel.split(".")[1]
        print(f"   user_id={user_id} → {data}")
    print("   Fayda: N users ke liye N SUBSCRIBE calls nahi karne padte")


# ════════════════════════════════════════════
# SECTION 3: FAILOVER GOTCHA — subscription is NOT durable
# ════════════════════════════════════════════
def demo_failover():
    print("\n" + "=" * 50)
    print("  SECTION 3: RECONNECT GOTCHA")
    print("=" * 50)

    sub = redis.Redis(decode_responses=True)
    p = sub.pubsub()
    p.subscribe("alerts")
    print("✅ Subscribed to 'alerts'")

    # ─── Connection drop simulate karo (jaisa Sentinel failover me hota hai) ───
    p.connection.disconnect()
    print("💥 Connection forcibly dropped (simulates master failover)")

    r.publish("alerts", "disk almost full")   # koi is waqt nahi sun raha
    time.sleep(0.2)
    msg = p.get_message(timeout=1)
    print(f"📥 get_message() after disconnect: {msg}")
    print("   GOTCHA: Redis client library reconnect kar sakti hai, lekin")
    print("   subscription state Redis-side replicate/failover NAHI hoti —")
    print("   app ko disconnect detect karke SUBSCRIBE dobara issue karna hoga.")
    p.close()


# ════════════════════════════════════════════
# SECTION 4: PUB/SUB vs STREAMS — delivery guarantee difference
# ════════════════════════════════════════════
def demo_vsstreams():
    print("\n" + "=" * 50)
    print("  SECTION 4: PUB/SUB vs STREAMS — same event, two mechanisms")
    print("=" * 50)

    stream_key = "demo:stream:orders"
    r.delete(stream_key)

    # ─── Pub/Sub: agar koi subscribe nahi hai, event lost ───
    n = r.publish("orders_channel", "order#1")
    print(f"📤 Pub/Sub publish, 0 subscribers → delivered to {n} clients (LOST)")

    # ─── Stream: XADD persist karta hai, chahe koi consumer ho ya na ho ───
    msg_id = r.xadd(stream_key, {"order": "1"})
    print(f"📤 Stream XADD → stored as {msg_id} (persists, replayable)")

    # ─── Baad me aane wala consumer bhi Stream se purana data padh sakta hai ───
    entries = r.xrange(stream_key, min="-", max="+")
    print(f"✅ Late consumer XRANGE reads {len(entries)} entr(y/ies) it missed nothing for")
    print("   → yahi wajah hai Streams task-queues/event-sourcing ke liye,")
    print("     Pub/Sub sirf ephemeral broadcast (WebSocket fan-out, cache invalidation) ke liye")

    r.delete(stream_key)


if __name__ == "__main__":
    sections = {
        "basic": demo_basic,
        "pattern": demo_pattern,
        "failover": demo_failover,
        "vsstreams": demo_vsstreams,
    }
    choice = sys.argv[1] if len(sys.argv) > 1 else "all"
    if choice == "all":
        for fn in sections.values():
            fn()
    elif choice in sections:
        sections[choice]()
    else:
        print(f"Usage: python 10_pubsub_fundamentals.py [{'|'.join(sections)}|all]")
