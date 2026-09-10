import os
import sys
import time

print(f"=== BEFORE fork() ===")
print(f"Single process PID: {os.getpid()}, PPID = {os.getppid()}")

shared_looking_variable = "I exist before the fork"
counter = 0
pid = os.fork()

if pid == 0:
    #This block is executed only in the child process
    counter += 100
    print(f"\n[CHILD] my PID = {os.getpid()}, my PPID = {os.getppid()}")
    print("f[CHILD] fork() returned 0 to me")
    print(f"[CHILD] counter after += 100: {counter}")
    print(f"[CHILD] I have mu OWN copy of  'shared_looking_variable': {shared_looking_variable!r}")
    time.sleep(1)
    sys.exit(42)
else:
    #This block is executed only in the parent process
    counter += 1
    print(f"\n[PARENT] my PID = {os.getpid()}, my PPID = {os.getppid()}")
    print(f"[PARENT] fork() returned {pid} to me")
    print(f"[PARENT] counter after += 1: {counter}")
    print(f"[PARENT] I have mu OWN copy of  'shared_looking_variable': {shared_looking_variable!r}")
    # Without this wait(), the child becomes a ZOMBIE after it exits
    # (terminated, but its exit status sits unclaimed in the process table
    # until the parent reaps it) -- try commenting this out and running
    # `ps` quickly after to see STAT column show 'Z' briefly.
    child_pid, status = os.waitpid(pid, 0)
    exit_code = os.WEXITSTATUS(status)
    print(f"[PARENT] reaped child {child_pid} with exit code {exit_code!r} and status {status:08x}")

"""
1. print() call hua "BEFORE fork()" ke liye
2. Terminal se pipe/redirect ho raha tha (Bash tool ke through) →
   Python stdout ko FULLY BUFFER karta hai (line-buffer nahi, jaisa
   real terminal me hota), matlab print() turant likha NAHI gaya —
   memory buffer me pending raha
3. fork() chala — is buffer ka bhi COPY child ko mil gaya
   (kyunki fork() poora process memory copy karta hai, buffer sahit)
4. Dono processes (parent + child) apna-apna buffer independently
   flush karte hain exit pe → line 2 baar print ho gayi
   
   
Note:
Real production lesson: agar aap logging/print ke turant baad fork()/multiprocessing use karte ho,
aur output buffered hai (file ya pipe me redirect), duplicate log lines aa sakti hain. Fix: sys.stdout.flush() fork se pehle, ya print(..., flush=True), ya buffering disable karo.
"""
