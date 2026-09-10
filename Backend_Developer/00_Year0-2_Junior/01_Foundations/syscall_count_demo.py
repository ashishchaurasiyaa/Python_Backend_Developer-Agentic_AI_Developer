"""
Syscalls -- Part 7: does syscall COUNT actually matter?
Same total bytes written, but as many tiny syscalls vs few large ones.
"""

import os
import time


def demo_syscall_count_matters():
    print("=== Proof: many small write() syscalls vs few large ones (same total data) ===")
    total_bytes = 2_000_000  # 2 MB total, either way
    path_many = "/tmp/syscall_many_writes.bin"
    path_few = "/tmp/syscall_few_writes.bin"

    # Approach A: one syscall per byte -- 10,000,000 write() calls
    chunk = b"x"
    fd = os.open(path_many, os.O_WRONLY | os.O_CREAT | os.O_TRUNC)
    start = time.perf_counter()
    for _ in range(total_bytes):
        os.write(fd, chunk)
    time_many = time.perf_counter() - start
    os.close(fd)
    print(f"  {total_bytes:,} separate 1-byte write() syscalls: {time_many:.3f}s")

    # Approach B: one syscall per 64KB chunk -- ~153 write() calls for the same data
    chunk_size = 65536
    big_chunk = b"x" * chunk_size
    n_chunks = total_bytes // chunk_size
    fd = os.open(path_few, os.O_WRONLY | os.O_CREAT | os.O_TRUNC)
    start = time.perf_counter()
    for _ in range(n_chunks):
        os.write(fd, big_chunk)
    time_few = time.perf_counter() - start
    os.close(fd)
    print(f"  {n_chunks:,} batched 64KB write() syscalls (same {total_bytes:,} bytes): {time_few:.3f}s")

    print(f"\n  Same data, same disk in the end -- {time_many / time_few:.0f}x slower with")
    print(f"  one syscall per byte. This is EXACTLY why buffered I/O exists: Python's")
    print(f"  regular `open()`/`.write()` batches your writes into an internal buffer")
    print(f"  and only issues the real write() syscall periodically -- you get")
    print(f"  correctness (data does get written) without paying a kernel-crossing")
    print(f"  cost for every single byte.\n")

    os.remove(path_many)
    os.remove(path_few)


if __name__ == "__main__":
    demo_syscall_count_matters()
