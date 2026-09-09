"""
FD Soft vs Hard limits -- verified practical: real limits on this machine
via the resource module (Python's interface to getrlimit/setrlimit), plus
actually raising the soft limit and proving it with a real open-files count.
"""

import resource
import socket

if __name__ == "__main__":
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    print(f"Current FD limits -- soft: {soft}, hard: {hard}")

    new_soft = min(hard, soft * 2)
    resource.setrlimit(resource.RLIMIT_NOFILE, (new_soft, hard))
    soft2, hard2 = resource.getrlimit(resource.RLIMIT_NOFILE)
    print(f"After raising soft toward hard limit -- soft: {soft2}, hard: {hard2}")

    print(f"\nOpening real sockets up to a small sample to prove FDs are consumed one-by-one...")
    sockets = []
    try:
        for i in range(10):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sockets.append(s)
        print(f"Opened {len(sockets)} sockets. Sample FD numbers: {[s.fileno() for s in sockets[:5]]}...")
    finally:
        for s in sockets:
            s.close()

    print("\nTrying to raise the hard limit itself (should fail without root --")
    print("hard limit can only be raised by a privileged process, e.g. via sudo):")
    try:
        resource.setrlimit(resource.RLIMIT_NOFILE, (soft2, hard2 + 1000))
        print("  Unexpectedly succeeded")
    except (ValueError, PermissionError, OverflowError) as e:
        print(f"  Failed as expected: {type(e).__name__}: {e}")
        if isinstance(e, OverflowError):
            print(f"  (this machine's hard limit is already RLIM_INFINITY = {hard2},")
            print("   a sentinel 'unlimited' value -- adding to it overflows a C long.")
            print("   On typical Linux production servers the hard limit is a real finite")
            print("   number like 4096 or 65536, not infinity -- macOS defaults differ here,")
            print("   worth knowing before assuming 'ulimit -n' behaves identically everywhere.)")
