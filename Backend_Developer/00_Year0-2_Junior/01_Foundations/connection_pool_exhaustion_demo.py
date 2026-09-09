"""
Connection Pool Exhaustion -- verified practical: a real bounded pool
(queue.Queue) with max=3 "connections", and a 4th concurrent request that
genuinely BLOCKS waiting for one to free up -- then times out if it waits
too long. Not simulated with sleeps standing in for the mechanism.
"""

import queue
import threading
import time

POOL_SIZE = 3


class ConnectionPool:
    def __init__(self, size):
        self.pool = queue.Queue(maxsize=size)
        for i in range(size):
            self.pool.put(f"conn-{i}")

    def borrow(self, timeout):
        return self.pool.get(timeout=timeout)

    def release(self, conn):
        self.pool.put(conn)


def worker(pool, worker_id, hold_seconds, results):
    t0 = time.perf_counter()
    try:
        conn = pool.borrow(timeout=2)
        waited = time.perf_counter() - t0
        print(f"  [worker {worker_id}] got {conn} after waiting {waited:.2f}s -- doing work for {hold_seconds}s")
        time.sleep(hold_seconds)
        pool.release(conn)
        print(f"  [worker {worker_id}] released {conn}")
        results[worker_id] = f"succeeded after {waited:.2f}s wait"
    except queue.Empty:
        waited = time.perf_counter() - t0
        print(f"  [worker {worker_id}] TIMED OUT after {waited:.2f}s -- pool exhausted (this is item 15's scenario)")
        results[worker_id] = f"pool timeout after {waited:.2f}s"


if __name__ == "__main__":
    pool = ConnectionPool(POOL_SIZE)
    print(f"Pool created with {POOL_SIZE} connections.\n")

    print(f"=== Launching {POOL_SIZE + 2} concurrent workers against a pool of {POOL_SIZE} ===\n")
    results = {}
    threads = []
    for i in range(POOL_SIZE + 2):
        t = threading.Thread(target=worker, args=(pool, i, 1.5, results))
        threads.append(t)
        t.start()
        time.sleep(0.05)

    for t in threads:
        t.join()

    print("\n=== Summary ===")
    for worker_id, outcome in results.items():
        print(f"  worker {worker_id}: {outcome}")
