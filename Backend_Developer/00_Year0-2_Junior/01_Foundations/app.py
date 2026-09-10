"""
app.py
============================================================

Operating System Concepts for Backend Developers
Python practical demonstration

Topics covered:
    1. Process
    2. Thread
    3. GIL
    4. Multiprocessing
    5. File Descriptors
    6. File I/O
    7. mmap
    8. Signals
    9. Socket
    10. asyncio
    11. /proc
    12. CPU / Memory information
    13. fork() / Copy-on-Write
    14. OS-level debugging

Run:
    python app.py

Recommended Linux/macOS:
    Python 3.10+
"""

import asyncio
import mmap
import os
import signal
import socket
import sys
import threading
import time
from concurrent.futures import ProcessPoolExecutor


# ============================================================
# 1. PROCESS
# ============================================================

def show_process_info():
    """
    Demonstrate basic process information.
    """

    print("\n" + "=" * 60)
    print("1. PROCESS")
    print("=" * 60)

    print(f"Process ID (PID): {os.getpid()}")
    print(f"Parent Process ID (PPID): {os.getppid()}")
    print(f"Python Version: {sys.version}")
    print(f"Platform: {sys.platform}")

    print("\nCurrent Process:")
    print("PID =", os.getpid())


# ============================================================
# 2. THREAD
# ============================================================

def worker_thread(name: str):
    """
    Function executed by a thread.
    """

    print(
        f"[Thread] name={name}, "
        f"PID={os.getpid()}, "
        f"TID={threading.get_ident()}"
    )

    time.sleep(1)

    print(f"[Thread] {name} finished")


def demonstrate_threads():
    """
    Demonstrate multiple threads inside one process.
    """

    print("\n" + "=" * 60)
    print("2. THREADS")
    print("=" * 60)

    print(f"Main PID: {os.getpid()}")

    threads = []

    for i in range(3):
        thread = threading.Thread(
            target=worker_thread,
            args=(f"worker-{i}",),
        )

        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    print("\nAll threads completed.")

    print(
        "\nImportant:"
        "\n- Threads belong to the same process."
        "\n- Threads share process memory."
        "\n- Python threads are useful for I/O-bound work."
    )


# ============================================================
# 3. GIL DEMONSTRATION
# ============================================================

def cpu_heavy_task(n: int):
    """
    CPU-heavy Python operation.

    This is intentionally simple so that we can compare
    threading vs multiprocessing.
    """

    total = 0

    for i in range(n):
        total += i * i

    return total


def demonstrate_gil():
    """
    Demonstrate CPU-bound work with threads.

    Note:
        This does NOT prove every Python implementation behaves
        identically. It demonstrates the CPython GIL limitation
        discussed in the notes.
    """

    print("\n" + "=" * 60)
    print("3. GIL / CPU-BOUND THREADING")
    print("=" * 60)

    n = 5_000_000

    start = time.perf_counter()

    thread1 = threading.Thread(
        target=cpu_heavy_task,
        args=(n,),
    )

    thread2 = threading.Thread(
        target=cpu_heavy_task,
        args=(n,),
    )

    thread1.start()
    thread2.start()

    thread1.join()
    thread2.join()

    elapsed = time.perf_counter() - start

    print(f"CPU-bound threaded execution: {elapsed:.2f}s")

    print(
        "\nGIL concept:"
        "\nCPython's GIL serializes execution of Python bytecode "
        "between threads."
    )


# ============================================================
# 4. MULTIPROCESSING
# ============================================================

def demonstrate_multiprocessing():
    """
    Demonstrate CPU-bound work using multiple processes.
    """

    print("\n" + "=" * 60)
    print("4. MULTIPROCESSING")
    print("=" * 60)

    n = 5_000_000

    start = time.perf_counter()

    with ProcessPoolExecutor(max_workers=2) as executor:

        futures = [
            executor.submit(cpu_heavy_task, n),
            executor.submit(cpu_heavy_task, n),
        ]

        results = [future.result() for future in futures]

    elapsed = time.perf_counter() - start

    print(f"Results calculated: {len(results)}")
    print(f"Multiprocessing execution: {elapsed:.2f}s")

    print(
        "\nConcept:"
        "\nProcesses have separate memory spaces."
        "\nMultiprocessing can provide true CPU parallelism."
    )


# ============================================================
# 5. FILE DESCRIPTORS
# ============================================================

def demonstrate_file_descriptor():
    """
    Demonstrate file descriptor creation.
    """

    print("\n" + "=" * 60)
    print("5. FILE DESCRIPTOR")
    print("=" * 60)

    file_name = "os_demo.txt"

    file = open(file_name, "w")

    print(f"File opened: {file_name}")
    print(f"File descriptor: {file.fileno()}")

    file.write("Hello from OS demonstration.\n")
    file.write("This file has an associated file descriptor.\n")

    file.close()

    print("File closed.")

    print(
        "\nStandard file descriptors:"
        "\n0 = stdin"
        "\n1 = stdout"
        "\n2 = stderr"
    )


# ============================================================
# 6. FILE I/O
# ============================================================

def demonstrate_file_io():
    """
    Demonstrate basic file read/write.
    """

    print("\n" + "=" * 60)
    print("6. FILE I/O")
    print("=" * 60)

    file_name = "io_demo.txt"

    with open(file_name, "w") as file:
        file.write("Line 1\n")
        file.write("Line 2\n")
        file.write("Line 3\n")

    with open(file_name, "r") as file:
        content = file.read()

    print("File content:")
    print(content)

    print(
        "\nBehind the scenes, file operations eventually "
        "involve OS-level system calls."
    )


# ============================================================
# 7. MMAP
# ============================================================

def demonstrate_mmap():
    """
    Demonstrate memory mapping.

    mmap allows a file to be mapped into memory.
    """

    print("\n" + "=" * 60)
    print("7. MMAP")
    print("=" * 60)

    file_name = "mmap_demo.txt"

    with open(file_name, "wb") as file:
        file.write(b"Hello from mmap!")

    with open(file_name, "r+b") as file:

        mapped = mmap.mmap(
            file.fileno(),
            0,
        )

        print("Mapped content:")
        print(mapped[:].decode())

        mapped.close()

    print(
        "\nConcept:"
        "\nmmap() maps file/anonymous memory into a process address space."
    )


# ============================================================
# 8. SIGNALS
# ============================================================

shutdown_requested = False


def signal_handler(signum, frame):
    """
    Handle SIGTERM / SIGINT.
    """

    global shutdown_requested

    print(
        f"\nSignal received: {signal.Signals(signum).name}"
    )

    shutdown_requested = True


def demonstrate_signals():
    """
    Demonstrate graceful signal handling.
    """

    print("\n" + "=" * 60)
    print("8. SIGNALS")
    print("=" * 60)

    signal.signal(
        signal.SIGINT,
        signal_handler,
    )

    if hasattr(signal, "SIGTERM"):
        signal.signal(
            signal.SIGTERM,
            signal_handler,
        )

    print(f"Current PID: {os.getpid()}")

    print(
        "\nTry from another terminal:"
        f"\nkill -TERM {os.getpid()}"
    )

    print("Waiting for signal...")

    for _ in range(5):

        if shutdown_requested:
            break

        time.sleep(1)

    print("Signal demo finished.")


# ============================================================
# 9. SOCKET
# ============================================================

def demonstrate_socket():
    """
    Demonstrate a local TCP socket.
    """

    print("\n" + "=" * 60)
    print("9. SOCKET")
    print("=" * 60)

    server = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM,
    )

    server.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_REUSEADDR,
        1,
    )

    server.bind(
        ("127.0.0.1", 0)
    )

    server.listen(1)

    host, port = server.getsockname()

    print(f"Server listening on {host}:{port}")

    def client():

        time.sleep(0.2)

        client_socket = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM,
        )

        client_socket.connect(
            (host, port)
        )

        client_socket.sendall(
            b"Hello server"
        )

        client_socket.close()

    client_thread = threading.Thread(
        target=client
    )

    client_thread.start()

    connection, address = server.accept()

    print(f"Client connected from {address}")

    data = connection.recv(1024)

    print(f"Received: {data.decode()}")

    connection.close()
    server.close()

    client_thread.join()

    print(
        "\nImportant:"
        "\nA socket is represented by a file descriptor."
    )


# ============================================================
# 10. ASYNCIO
# ============================================================

async def async_worker(name: str, delay: float):
    """
    Simulate an I/O-bound operation.
    """

    print(f"[async] {name} started")

    await asyncio.sleep(delay)

    print(f"[async] {name} finished")

    return name


async def demonstrate_asyncio():
    """
    Demonstrate asynchronous concurrency.
    """

    print("\n" + "=" * 60)
    print("10. ASYNCIO")
    print("=" * 60)

    start = time.perf_counter()

    results = await asyncio.gather(
        async_worker("request-1", 1),
        async_worker("request-2", 1),
        async_worker("request-3", 1),
    )

    elapsed = time.perf_counter() - start

    print(f"Results: {results}")
    print(f"Elapsed time: {elapsed:.2f}s")

    print(
        "\nConcept:"
        "\nMultiple I/O operations can be managed by an event loop "
        "without creating one OS thread per operation."
    )


# ============================================================
# 11. /PROC INFORMATION
# ============================================================

def demonstrate_proc():
    """
    Demonstrate Linux /proc information.

    This section requires Linux.
    """

    print("\n" + "=" * 60)
    print("11. /PROC")
    print("=" * 60)

    pid = os.getpid()

    proc_status = f"/proc/{pid}/status"

    if not os.path.exists(proc_status):

        print(
            "/proc is not available on this system."
        )

        return

    print(f"Reading: {proc_status}")

    with open(proc_status, "r") as file:

        for line in file:

            if (
                    line.startswith("Name:")
                    or line.startswith("Pid:")
                    or line.startswith("PPid:")
                    or line.startswith("VmRSS:")
                    or line.startswith("VmSize:")
            ):
                print(line.strip())


# ============================================================
# 12. MEMORY INFORMATION
# ============================================================

def demonstrate_memory():
    """
    Demonstrate basic process memory information on Linux.
    """

    print("\n" + "=" * 60)
    print("12. MEMORY")
    print("=" * 60)

    pid = os.getpid()

    status_file = f"/proc/{pid}/status"

    if not os.path.exists(status_file):

        print(
            "Linux /proc memory information unavailable."
        )

        return

    with open(status_file, "r") as file:

        for line in file:

            if (
                    line.startswith("VmRSS:")
                    or line.startswith("VmSize:")
                    or line.startswith("VmPeak:")
            ):
                print(line.strip())


# ============================================================
# 13. FORK / COPY-ON-WRITE
# ============================================================

def demonstrate_fork():
    """
    Demonstrate fork() concept.

    IMPORTANT:
        os.fork() is Unix-specific.
        It is not available on standard Windows Python.
    """

    print("\n" + "=" * 60)
    print("13. FORK / COPY-ON-WRITE")
    print("=" * 60)

    if not hasattr(os, "fork"):

        print(
            "os.fork() is not available on this operating system."
        )

        return

    print(f"Parent PID before fork: {os.getpid()}")

    pid = os.fork()

    if pid == 0:

        print(
            f"Child process created. "
            f"Child PID={os.getpid()}, "
            f"Parent PID={os.getppid()}"
        )

        time.sleep(1)

        print("Child exiting.")

        os._exit(0)

    else:

        print(
            f"Parent created child with PID={pid}"
        )

        os.waitpid(pid, 0)

        print("Child process finished.")

    print(
        "\nConcept:"
        "\nfork() creates a child process."
        "\nInitially memory pages can be shared."
        "\nWhen a process writes to a shared page, "
        "Copy-on-Write can create a private copy."
    )


# ============================================================
# 14. SYSTEM INFORMATION
# ============================================================

def demonstrate_system_info():
    """
    Display basic OS information.
    """

    print("\n" + "=" * 60)
    print("14. SYSTEM INFORMATION")
    print("=" * 60)

    print(f"Operating system: {os.name}")
    print(f"CPU count: {os.cpu_count()}")
    print(f"Current working directory: {os.getcwd()}")

    print("\nEnvironment variables:")
    print(f"PATH exists: {'PATH' in os.environ}")


# ============================================================
# 15. MAIN
# ============================================================

def main():
    """
    Run all demonstrations.
    """

    print("\n")
    print("=" * 70)
    print(" OPERATING SYSTEM CONCEPTS — PYTHON DEMO")
    print("=" * 70)

    show_process_info()

    demonstrate_threads()

    demonstrate_gil()

    demonstrate_multiprocessing()

    demonstrate_file_descriptor()

    demonstrate_file_io()

    demonstrate_mmap()

    demonstrate_socket()

    demonstrate_system_info()

    demonstrate_proc()

    demonstrate_memory()

    demonstrate_fork()

    print("\nRunning asyncio demonstration...")

    asyncio.run(
        demonstrate_asyncio()
    )

    print("\n" + "=" * 70)
    print(" ALL DEMOS COMPLETED")
    print("=" * 70)


if __name__ == "__main__":
    main()