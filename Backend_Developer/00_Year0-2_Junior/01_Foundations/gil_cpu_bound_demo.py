import time
import threading
import multiprocessing

def cpu_bound_work(n):
    x = 0
    for i in range(n):
        x += i * i
    return x

N = 20_000_000

def main():
    start = time.perf_counter()
    cpu_bound_work(N)
    cpu_bound_work(N)
    single_thread_time = time.perf_counter() - start

    start = time.perf_counter()
    t1 = threading.Thread(target=cpu_bound_work, args=(N,))
    t2 = threading.Thread(target=cpu_bound_work, args=(N,))
    t1.start(); t2.start()
    t1.join(); t2.join()
    threaded_time = time.perf_counter() - start

    start = time.perf_counter()
    p1 = multiprocessing.Process(target=cpu_bound_work, args=(N,))
    p2 = multiprocessing.Process(target=cpu_bound_work, args=(N,))
    p1.start(); p2.start()
    p1.join(); p2.join()
    process_time = time.perf_counter() - start

    print(f"Sequential (1 thread, 2x work): {single_thread_time:.2f}s")
    print(f"Threading  (2 threads, GIL):    {threaded_time:.2f}s   <- expect ~same or worse than sequential")
    print(f"Multiproc  (2 processes):        {process_time:.2f}s   <- expect ~half of sequential")

if __name__ == "__main__":
    main()
