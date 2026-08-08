"""
RabbitMQ Exercise 02 — Verify: RPC correlation_id matching
=============================================================
Approach: server.py background subprocess me chalta hai (real
long-running worker). client.py ab `if __name__ == "__main__"` guard
ke peeche hai isliye yahan seedha import karke IN-PROCESS use karte
hain — ek hi command se poora round-trip test ho jaata hai.

  Test 1: normal call — fact(5) == 120 aana chahiye (TODO 1 sahi hai
          tabhi possible — warna reply kahin nahi jaata / hang ho jaata)
  Test 2: client ki apni reply-queue me ek "stray" (galat correlation_id)
          response manually inject karte hain — jaisे kisi doosre
          concurrent call ka jawab ho. Phir asli call karte hain.
          Agar TODO 2 (correlation match) missing/galat hai, client
          galat response (999) utha lega. Sahi implementation use
          IGNORE karke asli response (720) ka wait karega.

Run: python verify.py
"""
import os
import subprocess
import sys
import time

import pika

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def main():
    print("[setup] starting server.py in background...")
    server = subprocess.Popen(
        [sys.executable, "-u", os.path.join(HERE, "server.py")],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    time.sleep(1.5)  # let it declare queue + start consuming

    try:
        from client import FactRPCClient
    except SystemExit:
        print("❌ client.py ka TODO abhi bharna hai (import ke time hi crash hua)")
        server.terminate()
        sys.exit(1)

    client = FactRPCClient()

    print("[test 1] normal call — fact(5) chahiye 120")
    try:
        result = client.call(5)
    except SystemExit:
        print("❌ TODO abhi bharna hai (client.py ya server.py) — upar ka output dekho")
        server.terminate()
        sys.exit(1)
    test1_pass = (result == 120)
    print(f"  got {result} (expected 120) -> {'ok' if test1_pass else 'MISMATCH'}")

    print("[test 2] stray/wrong-correlation_id response inject kar rahe hain...")
    client.channel.basic_publish(
        exchange='',
        routing_key=client.queue_name,
        properties=pika.BasicProperties(correlation_id="not-my-call-xyz"),
        body="999",
    )
    time.sleep(0.3)

    try:
        result2 = client.call(6)  # fact(6) == 720
    except SystemExit:
        print("❌ TODO 2 abhi bharna hai (is_my_response) — upar ka output dekho")
        server.terminate()
        sys.exit(1)
    test2_pass = (result2 == 720)
    print(f"  got {result2} (expected 720, NOT 999) -> "
          f"{'ok' if test2_pass else 'MISMATCH — stray response leak ho gayi!'}")

    server.terminate()

    print("-" * 55)
    if test1_pass and test2_pass:
        print("✅ PASS — RPC correlation_id matching sahi kaam kar raha hai")
    else:
        print("❌ FAIL")
        if not test1_pass:
            print("   test 1 fail — reply_to/correlation_id (client TODO 1 / server TODO 1) check karo")
        if not test2_pass:
            print("   test 2 fail — is_my_response() (client TODO 2) galat response accept kar raha hai")
        sys.exit(1)

    print("""
SOCH (bolke jawab do):
  1. Agar correlation_id check hata do to kya bug aayega? (test 2 exactly
     yehi scenario simulate karta hai)
  2. RPC client ek EXCLUSIVE reply queue kyun banata hai — server ki
     bheji hui reply seedhe well-known queue pe kyun nahi bhej sakta?
  3. RPC pattern synchronous FEEL deta hai (`call()` block karta hai)
     par underlying transport async hai — `process_data_events()` loop
     kya kar raha hai internally?
""")


if __name__ == "__main__":
    main()
