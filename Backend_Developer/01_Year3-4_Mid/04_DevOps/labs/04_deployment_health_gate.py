"""
DevOps Lab 04 — Deployment Health Gate
=========================================
OBJECTIVE: ek lightweight, REAL health-gate decision logic likho — jo
production deploy me "naya version chalu karo, health check karo, N baar
consecutive healthy mile to hi purana retire karo, warna rollback karo"
wala core pattern hai. Yeh GitHub Actions rolling-update ya Kubernetes ka
poora replacement nahi hai (wahan replica sets, readiness probes, traffic
shifting waghera zyada complex hote hain) — par DECISION LOGIC yahan genuinely
proven hoti hai: dono paths (promote / rollback) real containers ke saath.

TASK:
  1. TODO 1: `compute_streak()` — healthy check pe streak+1, unhealthy pe
     streak reset to 0.
  2. TODO 2: `should_promote()` — streak threshold tak pahuncha ya nahi.
  3. Run: python3 04_deployment_health_gate.py

Prereq: Docker daemon chalu hona chahiye.

NOTE: Yeh script apne khud ke containers subprocess se manage karta hai
(Lab 2/3 ke docker-compose.yml se alag), kyunki yahan hum khud DEPLOYMENT
GATE ka process test kar rahe hain, koi static stack nahi.
"""

import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

LABS_DIR = Path(__file__).resolve().parent
HEALTH_APP = LABS_DIR / "app" / "health_app.py"

OLD_NAME = "devops-lab04-old"
NEW_NAME = "devops-lab04-new"
OLD_PORT = 18041
NEW_PORT = 18042
CONSECUTIVE_REQUIRED = 3
POLL_INTERVAL_S = 1
POLL_TIMEOUT_S = 8


# ── TODO 1 ───────────────────────────────────────────────────────────────
def compute_streak(previous_streak: int, healthy: bool) -> int:
    """Healthy poll pe streak +1, unhealthy pe streak reset to 0.
    (Ek healthy check kaafi nahi hai — flaky/slow-starting service se
    false-positive promote ho sakta hai, isliye CONSECUTIVE checks chahiye.)
    """
    # ─────────────────────────────────────────────────────────────
    # TODO 1: Hint —
    #   return previous_streak + 1 if healthy else 0
    raise NotImplementedError("TODO 1: compute_streak() abhi implement nahi hui")
    # ─────────────────────────────────────────────────────────────


# ── TODO 2 ───────────────────────────────────────────────────────────────
def should_promote(streak: int, required: int) -> bool:
    """Streak required threshold tak pahuncha to True (promote), nahi to False (rollback)."""
    # ─────────────────────────────────────────────────────────────
    # TODO 2: Hint —
    #   return streak >= required
    raise NotImplementedError("TODO 2: should_promote() abhi implement nahi hui")
    # ─────────────────────────────────────────────────────────────


def check_todos_filled() -> bool:
    try:
        ok1 = (compute_streak(0, True) == 1
               and compute_streak(5, False) == 0
               and compute_streak(2, True) == 3)
    except NotImplementedError as e:
        print(f"❌ {e}")
        return False
    if not ok1:
        print("❌ TODO 1 (compute_streak) galat logic — healthy=+1, unhealthy=reset-to-0 hona chahiye")
        return False

    try:
        ok2 = should_promote(3, 3) is True and should_promote(2, 3) is False
    except NotImplementedError as e:
        print(f"❌ {e}")
        return False
    if not ok2:
        print("❌ TODO 2 (should_promote) galat logic — streak >= required par True hona chahiye")
        return False

    return True


# ── Infra plumbing (already written — not the exercise) ─────────────────
def run(cmd: list, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)


def start_container(name: str, host_port: int, broken: bool) -> bool:
    run(["docker", "rm", "-f", name])
    result = run([
        "docker", "run", "-d", "--name", name,
        "-p", f"{host_port}:8000",
        "-e", f"LAB_BROKEN_HEALTH={'1' if broken else '0'}",
        "-v", f"{HEALTH_APP}:/app/health_app.py:ro",
        "-w", "/app",
        "python:3.12-slim",
        "python", "health_app.py",
    ])
    return result.returncode == 0


def is_healthy(host_port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://localhost:{host_port}/health", timeout=2) as resp:
            return resp.status == 200
    except urllib.error.HTTPError:
        return False              # 500 etc — valid response, just unhealthy
    except (urllib.error.URLError, ConnectionError):
        return False              # not up yet


def stop_container(name: str) -> None:
    run(["docker", "stop", name])


def container_running(name: str) -> bool:
    result = run(["docker", "inspect", "--format={{.State.Running}}", name])
    return result.stdout.strip() == "true"


def deploy_with_health_gate(broken: bool) -> bool:
    """Starts NEW candidate, health-gates it, promotes or rolls back.
    Returns True if promoted. Real side effect: exactly OLD xor NEW is
    left running — that's what main() asserts.
    """
    print(f"  starting NEW candidate (broken={broken}) on port {NEW_PORT}...")
    if not start_container(NEW_NAME, NEW_PORT, broken=broken):
        print("  infra error starting NEW container (not a gate-logic issue)")
        return False

    streak = 0
    deadline = time.time() + POLL_TIMEOUT_S
    while time.time() < deadline:
        healthy = is_healthy(NEW_PORT)
        streak = compute_streak(streak, healthy)
        print(f"    poll: healthy={healthy} streak={streak}/{CONSECUTIVE_REQUIRED}")
        if should_promote(streak, CONSECUTIVE_REQUIRED):
            break
        time.sleep(POLL_INTERVAL_S)

    promote = should_promote(streak, CONSECUTIVE_REQUIRED)
    if promote:
        print("  → PROMOTE: naya version healthy raha, purana version retire kar rahe hain")
        stop_container(OLD_NAME)
    else:
        print("  → ROLLBACK: naya version healthy nahi hua, purana version rakh rahe hain")
        stop_container(NEW_NAME)
    return promote


def cleanup() -> None:
    run(["docker", "rm", "-f", OLD_NAME, NEW_NAME])


def main() -> None:
    if not check_todos_filled():
        return

    try:
        print("\n=== Scenario A: healthy new version → should PROMOTE ===")
        cleanup()
        start_container(OLD_NAME, OLD_PORT, broken=False)
        time.sleep(2)  # OLD ko boot hone do
        promoted_a = deploy_with_health_gate(broken=False)
        old_running_a = container_running(OLD_NAME)
        new_running_a = container_running(NEW_NAME)
        a_ok = promoted_a and not old_running_a and new_running_a
        print(f"  → promoted={promoted_a} old_running={old_running_a} "
              f"new_running={new_running_a}  {'✓' if a_ok else '✗'}")

        print("\n=== Scenario B: broken new version (500 on /health) → should ROLLBACK ===")
        cleanup()
        start_container(OLD_NAME, OLD_PORT, broken=False)
        time.sleep(2)
        promoted_b = deploy_with_health_gate(broken=True)
        old_running_b = container_running(OLD_NAME)
        new_running_b = container_running(NEW_NAME)
        b_ok = (not promoted_b) and old_running_b and (not new_running_b)
        print(f"  → promoted={promoted_b} old_running={old_running_b} "
              f"new_running={new_running_b}  {'✓' if b_ok else '✗'}")

        print("\n" + "─" * 55)
        if a_ok and b_ok:
            print("✅ PASS — healthy → promote (old retired) AND broken → rollback "
                  "(old survives) — dono paths concretely proven")
        else:
            print("❌ FAIL")
            if not a_ok:
                print("   Scenario A: healthy version promote nahi hua sahi se.")
                print("   compute_streak/should_promote check karo (TODO 1/2).")
            if not b_ok:
                print("   Scenario B: broken version ne rollback trigger nahi kiya,")
                print("   ya OLD container survive nahi hua. TODO 1/2 ya")
                print("   health_app.py ka LAB_BROKEN_HEALTH env var check karo.")

        print("""
SOCH (bolke jawab do):
  1. Sirf EK healthy check kaafi kyun nahi? Konsi real-world situation
     (slow cold-start, transient network blip) false-positive de sakti hai?
  2. Yeh gate "all or nothing" hai — halfway rollback (kuch traffic naye
     pe, kuch purane pe) real K8s rolling update me kaise hota hai?
  3. Agar OLD container khud crash ho jaaye rollback ke baad, tumhara
     system kya karega? Is lab me is case ko handle kiya gaya hai?
  4. `should_promote` aur `compute_streak` ko pure functions (no docker
     calls) rakha gaya — testing ke liye yeh design choice kyun important hai?
""")
    finally:
        cleanup()


if __name__ == "__main__":
    main()
