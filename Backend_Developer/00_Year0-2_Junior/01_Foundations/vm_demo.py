"""
Virtual Memory -- verified practical demo.
Three real proofs: (1) VSZ vs RSS diverge as memory is touched, not just
allocated, (2) mmap() maps a file into address space without loading it
into a Python list, (3) invalid memory access is caught by the OS as a
real SIGSEGV, isolated in a subprocess so it can't take down this script.
"""

import mmap
import os
import subprocess
import sys
import time


def get_vsz_rss(pid: int) -> tuple[int, int]:
    """VSZ/RSS in KB, via ps (portable to macOS/Linux, unlike /proc)."""
    out = subprocess.check_output(
        ["ps", "-o", "vsz,rss", "-p", str(pid)], text=True
    ).splitlines()[1]
    vsz, rss = out.split()
    return int(vsz), int(rss)


def demo_vsz_vs_rss() -> None:
    print("=== Proof 1: VSZ (address space reserved) vs RSS (physical RAM actually touched) ===")
    pid = os.getpid()

    vsz0, rss0 = get_vsz_rss(pid)
    print(f"  Baseline:            VSZ={vsz0:>9} KB   RSS={rss0:>9} KB")

    # Reserve a big virtual range without touching most of it.
    big = bytearray(500 * 1024 * 1024)  # 500 MB, zero-initialized
    vsz1, rss1 = get_vsz_rss(pid)
    print(f"  After allocating 500MB bytearray:  VSZ={vsz1:>9} KB   RSS={rss1:>9} KB")
    print(f"    VSZ grew by ~{(vsz1 - vsz0) // 1024} MB, RSS grew by ~{(rss1 - rss0) // 1024} MB")

    # Now actually WRITE to every page -- forces the kernel to back each
    # page with real physical RAM (this is what "touching" a page means).
    for i in range(0, len(big), 4096):
        big[i] = 1
    vsz2, rss2 = get_vsz_rss(pid)
    print(f"  After writing to every page (forces real allocation): VSZ={vsz2:>9} KB   RSS={rss2:>9} KB")
    print(f"    RSS grew by ~{(rss2 - rss1) // 1024} MB now that pages are actually resident")
    print("  (VSZ barely changed between steps 2 and 3 -- the address space was")
    print("   already reserved; RSS is what actually costs physical RAM)\n")

    del big


def demo_mmap() -> None:
    print("=== Proof 2: mmap() maps a file into virtual address space, no full read into a list ===")
    path = "/tmp/vm_demo_mmap_file.bin"
    size = 10 * 1024 * 1024  # 10 MB
    with open(path, "wb") as f:
        f.write(b"\x00" * size)

    with open(path, "r+b") as f:
        mm = mmap.mmap(f.fileno(), 0)  # maps the WHOLE file into this process's address space
        mm[0:5] = b"HELLO"
        mm[size - 5:size] = b"WORLD"
        mm.flush()
        print(f"  Mapped a {size // 1024 // 1024}MB file via mmap() -- wrote at start and end")
        print(f"  mm[0:5]  = {bytes(mm[0:5])!r}")
        print(f"  mm[-5:]  = {bytes(mm[size-5:size])!r}")
        mm.close()

    # Prove the write actually landed on DISK (via the page cache), not
    # just in this process's private memory -- reopen fresh and re-read.
    with open(path, "rb") as f:
        f.seek(0)
        start = f.read(5)
        f.seek(size - 5)
        end = f.read(5)
    print(f"  Re-opened file fresh (not mmap'd): start={start!r}, end={end!r}")
    print("  (mmap() writes are backed by the same page-table machinery as")
    print("   regular memory -- the kernel handles when/how they hit disk)\n")

    os.remove(path)


def demo_segfault_protection() -> None:
    print("=== Proof 3: invalid memory access -> real SIGSEGV, caught safely in a subprocess ===")
    # Deliberately dereference an invalid pointer via ctypes. Isolated in
    # a subprocess -- a real SIGSEGV would otherwise kill this interpreter.
    code = (
        "import ctypes\n"
        "ctypes.cast(1, ctypes.POINTER(ctypes.c_int))[0] = 42\n"
    )
    result = subprocess.run([sys.executable, "-c", code])
    print(f"  Child process exit code: {result.returncode}")
    if result.returncode < 0:
        import signal as sig
        print(f"  Killed by signal: {sig.Signals(-result.returncode).name}")
    print("  (the page table has NO valid mapping for that address -> MMU traps")
    print("   into the kernel -> kernel sends SIGSEGV -> process dies. This is")
    print("   the OS-level memory-protection guarantee Python normally shields")
    print("   you from -- ctypes is one of the few ways to actually trigger it.)")


if __name__ == "__main__":
    demo_vsz_vs_rss()
    demo_mmap()
    demo_segfault_protection()
