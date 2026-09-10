import os, resource, sys

SIZE = 50 * 1024 * 1024  # 50MB

def minor_faults():
    return resource.getrusage(resource.RUSAGE_SELF).ru_minflt

buf = bytearray(SIZE)
for i in range(0, SIZE, 4096):   # touch every page so it's fully resident in parent
    buf[i] = 1

faults_before_fork = minor_faults()

pid = os.fork()

if pid == 0:
    # CHILD: buf's pages are shared (COW) with parent right now, read-only
    faults_right_after_fork = minor_faults()

    for i in range(0, SIZE, 4096):   # now WRITE to every page -> triggers COW
        buf[i] = 2

    faults_after_write = minor_faults()

    print(f"[CHILD] minor faults right after fork (no write yet): {faults_right_after_fork}")
    print(f"[CHILD] minor faults AFTER writing to every page:      {faults_after_write}")
    print(f"[CHILD] extra faults caused by COW writes:             {faults_after_write - faults_right_after_fork}")
    print(f"[CHILD] pages touched (SIZE/4096):                     {SIZE // 4096}")
    sys.stdout.flush()
    os._exit(0)
else:
    os.waitpid(pid, 0)
    print(f"[PARENT] minor faults before fork: {faults_before_fork}")
    print("[PARENT] child finished — see [CHILD] lines above for the COW proof")
