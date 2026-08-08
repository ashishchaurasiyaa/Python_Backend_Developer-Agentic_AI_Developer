"""
RabbitMQ Exercise 03 — Verify: direct exchange selective delivery
=====================================================================
3 subscribers ko background me chalate hain (alarmraiser: Error+Warning,
fiewriter: Warning only, screenprinter: Error+Warning+Info), phir
publisher.py chalate hain jo har severity pe EK deterministic message
bhejta hai. Phir check karte hain ki HAR subscriber ko SIRF apne bound
keys ke messages mile — baaki NAHI. Yehi direct exchange ka poora
point hai: selective delivery, na ki broadcast.

Run: python verify.py
"""
import os
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))

# script -> {routing keys ki messages jo isko milni CHAHIYE}
EXPECTED = {
    "alarmraiser.py": {"EMsg", "WMsg"},           # Error + Warning
    "fiewriter.py": {"WMsg"},                      # Warning only
    "screenprinter.py": {"EMsg", "WMsg", "IMsg"},  # Error + Warning + Info
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
    print("[setup] starting 3 subscribers (alarmraiser, fiewriter, screenprinter)...")
    procs, logs = {}, {}
    for script in EXPECTED:
        p = start(script)
        lines = []
        threading.Thread(target=drain, args=(p, lines), daemon=True).start()
        procs[script] = p
        logs[script] = lines

    time.sleep(2)

    print("[publish] running publisher.py (Error, Warning, Info, Other)...")
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

    print("-" * 55)
    all_ok = True
    for script, expected in EXPECTED.items():
        lines = logs[script]
        if any("❌ TODO" in l for l in lines):
            print(f"❌ {script} ka TODO abhi bharna hai:")
            print("\n".join(l for l in lines if l))
            all_ok = False
            continue

        got = set()
        for l in lines:
            for msg in ("EMsg", "WMsg", "IMsg", "OMsg"):
                if msg in l:
                    got.add(msg)

        ok = (got == expected)
        all_ok = all_ok and ok
        mark = "✅" if ok else "❌"
        print(f"  {mark} {script}: got {sorted(got)} (expected {sorted(expected)})")

    print("-" * 55)
    if all_ok:
        print("✅ PASS — direct exchange ne SIRF matching routing_key wali queues ko route kiya")
    else:
        print("❌ FAIL — kisi subscriber ko galat (ya missing) messages mile. BOUND_KEYS check karo.")
        sys.exit(1)

    print("""
SOCH (bolke jawab do):
  1. fiewriter ko sirf "WMsg" mila — "OMsg" (routing_key="Other") kyun
     nahi mila jabki publish hua tha? (Hint: koi bhi queue "Other" se
     bound nahi thi)
  2. Do queues (alarmraiser, screenprinter) dono "Warning" pe bound hain
     — jab Warning publish hota hai, kya dono ko independent copy
     milti hai ya sirf ek ko?
  3. Direct vs fanout — kis use-case me kaunsa exchange type sahi
     rahega? (Hint: "sabko batao" vs "sirf interested party ko batao")
""")


if __name__ == "__main__":
    main()
