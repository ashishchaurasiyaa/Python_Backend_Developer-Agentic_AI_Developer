import time
import threading
import multiprocessing

def io_bound_work(seconds):
    # simulates waiting on network/DB/disk -> releases GIL during the wait
    time.sleep(seconds)

SLEEP = 1.5

def main():
    start = time.perf_counter()
    io_bound_work(SLEEP)
    io_bound_work(SLEEP)
    sequential_time = time.perf_counter() - start

    start = time.perf_counter()
    t1 = threading.Thread(target=io_bound_work, args=(SLEEP,))
    t2 = threading.Thread(target=io_bound_work, args=(SLEEP,))
    t1.start(); t2.start()
    t1.join(); t2.join()
    threaded_time = time.perf_counter() - start

    start = time.perf_counter()
    p1 = multiprocessing.Process(target=io_bound_work, args=(SLEEP,))
    p2 = multiprocessing.Process(target=io_bound_work, args=(SLEEP,))
    p1.start(); p2.start()
    p1.join(); p2.join()
    process_time = time.perf_counter() - start

    print(f"Sequential (2x {SLEEP}s wait, one after another): {sequential_time:.2f}s")
    print(f"Threading  (2 threads, I/O-bound):                {threaded_time:.2f}s   <- expect ~{SLEEP}s, GIL released during sleep")
    print(f"Multiproc  (2 processes, I/O-bound):               {process_time:.2f}s   <- also ~{SLEEP}s, but paid process-spawn overhead for no extra benefit")

if __name__ == "__main__":
    main()
