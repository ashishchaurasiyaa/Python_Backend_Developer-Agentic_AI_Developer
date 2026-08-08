"""
RabbitMQ Exercise 01 — Verify: fanout broadcasts to ALL subscribers
=======================================================================
Approach: subscriber.py aur publisher.py DONO separate processes hain
(real two-terminal pattern) — is liye yahan subprocess se 2 independent
subscribers background me chalate hain (har ek apni khud ki anonymous
queue banata hai), phir publisher.py chalate hain, aur check karte hain
ki DONO subscribers ko SAARE 4 messages mile — yehi fanout ka poora
point hai (ek subscriber crash bhi ho jaaye to doosre par asar nahi).

Run: python verify.py
"""
import os
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
NUM_SUBSCRIBERS = 2
EXPECTED_MESSAGES = {"Hello0", "Hello1", "Hello2", "Hello3"}


def start(script):
    return subprocess.Popen(
        [sys.executable, "-u", os.path.join(HERE, script)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )


def drain(proc, lines):
    for line in proc.stdout:
        lines.append(line.rstrip("\n"))


def main():
    print(f"[setup] starting {NUM_SUBSCRIBERS} subscribers in background...")
    procs, logs = [], []
    for _ in range(NUM_SUBSCRIBERS):
        p = start("subscriber.py")
        lines = []
        threading.Thread(target=drain, args=(p, lines), daemon=True).start()
        procs.append(p)
        logs.append(lines)

    time.sleep(2)  # let both bind + start consuming

    print("[publish] running publisher.py...")
    pub = subprocess.run(
        [sys.executable, "-u", os.path.join(HERE, "publisher.py")],
        capture_output=True, text=True, timeout=15,
    )
    print(pub.stdout, end="")
    if pub.returncode != 0:
        print("❌ publisher.py ka TODO abhi bharna hai / crash hua:")
        print(pub.stdout, pub.stderr)
        for p in procs:
            p.terminate()
        sys.exit(1)

    time.sleep(1.5)  # let delivery happen

    for p in procs:
        p.terminate()
    time.sleep(0.5)
    for p in procs:
        p.kill()

    print("-" * 55)
    received = []
    for i, lines in enumerate(logs):
        if any("❌ TODO" in l for l in lines):
            print(f"❌ subscriber #{i + 1} ka TODO abhi bharna hai:")
            print("\n".join(l for l in lines if l))
            sys.exit(1)
        got = {l.split("[x] ", 1)[1] for l in lines if l.startswith("[x] ")}
        # body messages print as b'Hello0' — normalize to plain text
        got = {g.strip("b'\"") for g in got}
        received.append(got)
        print(f"  subscriber #{i + 1} got {sorted(got)}")

    all_complete = all(r == EXPECTED_MESSAGES for r in received)

    print("-" * 55)
    if all_complete:
        print(f"✅ PASS — sabhi {NUM_SUBSCRIBERS} subscribers ko SAARE 4 messages mile "
              "(fanout broadcast confirmed)")
    else:
        print("❌ FAIL — expected har subscriber ko wahi 4 messages milte, alag-alag nahi.")
        print(f"   expected: {sorted(EXPECTED_MESSAGES)}")
        print("   Agar 0 mile: TODO 1/2 (EXCHANGE_TYPE/BINDING_KEY) check karo.")
        print("   Agar sirf ek subscriber ko mila: dono queue_declare(queue='') se")
        print("   apni-apni anonymous queue bana rahe the na, check karo.")
        sys.exit(1)

    print("""
SOCH (bolke jawab do):
  1. Fanout exchange me routing_key kyun ignore hota hai? Direct/topic se
     kya farak hai?
  2. Har subscriber ki queue exclusive hai (queue_declare(queue='',
     exclusive=True)) — agar subscriber crash ho jaaye, us queue ka
     kya hota hai? Doosre subscribers ko farak padta hai?
  3. Fanout ka real use-case socho — jaise "cache invalidate karo" event
     jo saare app instances ko ek saath bhejni hai.
""")


if __name__ == "__main__":
    main()
