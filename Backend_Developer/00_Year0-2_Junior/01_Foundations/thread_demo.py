import os
import threading

# ─── Proof 1: same PID across all threads, but different TID ───

print("=== PID is SHARED across threads, TID is NOT ===")
print(f"Main thread: PID = {os.getpid()}, native TID = {threading.get_native_id()}")

def report_identity(label):
    print(f"{label}: PID = {os.getpid()}, native TID = {threading.get_native_id()}")

threads = [threading.Thread(target=report_identity, args=(f"Thread {i}",)) for i in range(3)]
for t in threads:
    t.start()
for t in threads:
    t.join()

print()
# ─── Proof 2: heap/global state IS shared (unlike fork(), which copies) ───

print("=== Global variable IS shared across threads (proves shared heap) ===")
shared_counter = 0
lock = threading.Lock()

def increment_shared(n):
    global shared_counter
    for _ in range(n):
        with lock:
            shared_counter += 1

t1 = threading.Thread(target=increment_shared, args=(10000000,))
t2 = threading.Thread(target=increment_shared, args=(10000000,))
t1.start(); t2.start()
t1.join(); t2.join()
print(f"Shared counter after 2 threads * 10,000,000 increments each = {shared_counter}")
print(f"(expected 20,000,000 -- BOTH threads mutated the SAME object, no fork()-style copy)")
print()

# ─── Proof 3: each thread's STACK (local variables) is private ───
print("=== STACK is private to each thread ===")
result = {}

def recurse_and_report(thread_name, depth, local_marker):
    # `local_marker` and `depth` live on THIS thread's own stack frame.
    # Two threads running this same function simultaneously do NOT see
    # or corrupt each other's local variables -- if the stack were shared,
    # this would be immediate chaos.
    if depth == 0:
        result[thread_name] = local_marker
        return
    local_marker = local_marker + f"->{depth}"
    recurse_and_report(thread_name, depth - 1, local_marker)

ta = threading.Thread(target=recurse_and_report, args=("A", 4, "start-A"))
tb = threading.Thread(target=recurse_and_report, args=("B", 4, "start-B"))
ta.start(); tb.start()
ta.join(); tb.join()

print(f"Result: {result}")
