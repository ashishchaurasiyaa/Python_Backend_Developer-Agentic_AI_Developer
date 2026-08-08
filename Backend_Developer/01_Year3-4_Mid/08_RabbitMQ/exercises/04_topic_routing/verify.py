"""
RabbitMQ Exercise 04 — Verify: topic exchange wildcard selectivity
=======================================================================
3 subscribers background me: errorhandlingsub (E.#), A3actiontaker
(#.A3.#), allwarningsfromC2 (W.#.C2). publisher.py 3 deterministic
routing keys bhejta hai jo single-match / multi-match / no-match teeno
scenarios cover karte hain — yehi topic wildcard ki real selectivity
prove karta hai (sirf "kuch mila" kaafi nahi, "sahi ko mila, galat ko
nahi mila" prove karna hai).

Run: python verify.py
"""
import os
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SUBSCRIBERS = ["errorhandlingsub.py", "A3actiontaker.py", "allwarningsfromC2.py"]

# routing_key -> {kaunse subscriber scripts ko yeh MILNA chahiye}
EXPECTED_MATCHES = {
    "E.H.A1.C1": {"errorhandlingsub.py"},
    "W.M.A3.C2": {"A3actiontaker.py", "allwarningsfromC2.py"},
    "I.L.A2.C3": set(),  # kisi ko nahi milna chahiye
}


def start(script):
    return subprocess.Popen(
        [sys.executable, "-u", os.path.join(HERE, script)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )


def drain(proc, lines):
    for line in proc.stdout:
        lines.append(line.rstrip("\n"))


def main():
    print("[setup] starting 3 subscribers (errorhandlingsub, A3actiontaker, allwarningsfromC2)...")
    procs, logs = {}, {}
    for script in SUBSCRIBERS:
        p = start(script)
        lines = []
        threading.Thread(target=drain, args=(p, lines), daemon=True).start()
        procs[script] = p
        logs[script] = lines

    time.sleep(2)

    print("[publish] running publisher.py (3 deterministic routing keys)...")
    pub = subprocess.run(
        [sys.executable, "-u", os.path.join(HERE, "publisher.py")],
        capture_output=True, text=True, timeout=15,
    )
    print(pub.stdout, end="")
    if pub.returncode != 0:
        print("❌ publisher.py ka TODO abhi bharna hai / crash hua:", pub.stderr)
        for p in procs.values():
            p.terminate()
        sys.exit(1)

    time.sleep(1.5)
    for p in procs.values():
        p.terminate()
    time.sleep(0.5)
    for p in procs.values():
        p.kill()

    for script in SUBSCRIBERS:
        if any("❌ TODO" in l for l in logs[script]):
            print(f"❌ {script} ka TODO abhi bharna hai:")
            print("\n".join(l for l in logs[script] if l))
            sys.exit(1)

    print("-" * 55)
    all_ok = True
    for rk, expected_subs in EXPECTED_MATCHES.items():
        for script in SUBSCRIBERS:
            got_it = any(rk in l for l in logs[script])
            should_get_it = script in expected_subs
            ok = got_it == should_get_it
            all_ok = all_ok and ok
            mark = "✅" if ok else "❌"
            verb = "mila" if got_it else "nahi mila"
            expect = "milna chahiye tha" if should_get_it else "NAHI milna chahiye tha"
            print(f"  {mark} {rk} -> {script}: {verb} ({expect})")

    print("-" * 55)
    if all_ok:
        print("✅ PASS — topic wildcards (*, #) ne sahi selectivity di")
    else:
        print("❌ FAIL — BINDING_PATTERN check karo har subscriber me.")
        sys.exit(1)

    print("""
SOCH (bolke jawab do):
  1. "I.L.A2.C3" kisi bhi subscriber ko nahi mila — kyun? Teeno
     patterns me se ek bhi match nahi karta, exactly kyun?
  2. "W.M.A3.C2" do subscribers ko mila — matlab kya broker message
     DUPLICATE karta hai, ya ek hi publish se dono queues ko independent
     copies milti hain?
  3. `*` aur `#` me farak kya hai? Agar allwarningsfromC2 "W.*.C2" bind
     karta (# ki jagah *), to kya "W.M.A3.C2" (2 words beech me) match
     karta? (Hint: * = EXACTLY ek word)
""")


if __name__ == "__main__":
    main()
