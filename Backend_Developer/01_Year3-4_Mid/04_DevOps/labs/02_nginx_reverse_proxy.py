"""
DevOps Lab 02 — Nginx Reverse Proxy
=====================================
OBJECTIVE: nginx ko ek real backend ke aage proxy banao, aur PROVE karo ki
response nginx ka apna default page nahi — asli backend se aaya, aur client
ka forwarded-IP header sahi backend tak pahuncha.

TASK:
  1. `configs/nginx.conf` kholo — 3 TODO bharo (upstream, proxy_pass, header).
  2. Run: python3 02_nginx_reverse_proxy.py

Prereq: docker compose up -d nginx backend   (yeh script khud bhi chala dega)
"""

import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

LABS_DIR = Path(__file__).resolve().parent
NGINX_CONF = LABS_DIR / "configs" / "nginx.conf"
NGINX_URL = "http://localhost:18010/"
TEST_FORWARDED_IP = "203.0.113.99"     # RFC 5737 test-net address, deterministic marker


def check_todos_filled() -> bool:
    content = NGINX_CONF.read_text()
    missing = [m for m in ("___TODO_1___", "___TODO_2___", "___TODO_3___") if m in content]
    if missing:
        print(f"❌ TODO abhi baaki hai in configs/nginx.conf: {', '.join(missing)}")
        print("   1 = upstream block, 2 = proxy_pass, 3 = X-Forwarded-For header")
        return False
    return True


def compose(*args) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "compose", "-f", str(LABS_DIR / "docker-compose.yml"), *args],
        cwd=LABS_DIR, capture_output=True, text=True,
    )


def wait_for_http(url: str, headers: dict, timeout_s: int = 25):
    deadline = time.time() + timeout_s
    last_err = None
    while time.time() < deadline:
        try:
            req = urllib.request.Request(url, headers=headers)
            return urllib.request.urlopen(req, timeout=2)
        except (urllib.error.URLError, ConnectionError) as e:
            last_err = e
            time.sleep(1)
    print(f"  (last connection error: {last_err})")
    return None


def get_backend_hostname() -> str:
    result = subprocess.run(
        ["docker", "inspect", "--format={{.Config.Hostname}}", "devops-lab-backend"],
        capture_output=True, text=True,
    )
    return result.stdout.strip()


def cleanup() -> None:
    compose("stop", "nginx", "backend")
    compose("rm", "-f", "nginx", "backend")


def main() -> None:
    if not check_todos_filled():
        return

    print("\n[1] Bringing up nginx + backend...")
    up = compose("up", "-d", "nginx", "backend")
    if up.returncode != 0:
        print("❌ FAIL — docker compose up nahi hua")
        print(up.stderr[-2000:])
        return

    try:
        print(f"\n[2] Requesting {NGINX_URL} through nginx (with X-Forwarded-For: {TEST_FORWARDED_IP})...")
        resp = wait_for_http(NGINX_URL, headers={"X-Forwarded-For": TEST_FORWARDED_IP})

        ok_from_backend = False
        ok_forwarded = False
        body = {}
        if resp is not None:
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read().decode()
            print(f"  ← status={resp.status} content-type={content_type}")
            try:
                body = json.loads(raw)
            except json.JSONDecodeError:
                body = {}

            # nginx's own default page is HTML ("Welcome to nginx") — our
            # backend always answers JSON with source=backend. Real proof
            # the request reached the backend, not nginx's own static page.
            ok_from_backend = body.get("source") == "backend" and "hostname" in body

            fwd = body.get("forwarded_for", "")
            # nginx appends its own perceived client IP after our marker via
            # $proxy_add_x_forwarded_for — so we expect "TEST_IP, <something>"
            ok_forwarded = fwd.startswith(TEST_FORWARDED_IP)
            print(f"  ← body: {body}")

        expected_hostname = get_backend_hostname()
        hostname_ok = bool(expected_hostname) and body.get("hostname") == expected_hostname

        print("\n" + "─" * 55)
        if ok_from_backend and ok_forwarded and hostname_ok:
            print("✅ PASS — response backend se aaya (nginx default page nahi), "
                  "hostname match hua, aur X-Forwarded-For sahi forward hua")
        else:
            print("❌ FAIL")
            if not ok_from_backend:
                print("   Response backend jaisa nahi laga — TODO 1/2 (upstream +")
                print("   proxy_pass) check karo. `docker compose logs nginx` dekho.")
            if not hostname_ok:
                print(f"   hostname mismatch: body={body.get('hostname')!r} vs "
                      f"container={expected_hostname!r}")
            if not ok_forwarded:
                print("   X-Forwarded-For backend tak nahi pahuncha ya khaali tha —")
                print("   TODO 3 (proxy_set_header X-Forwarded-For ...) check karo.")

        print("""
SOCH (bolke jawab do):
  1. `proxy_pass` ke bina agar sirf `location /` khaali chhod do to
     nginx kya serve karega? (Hint: apna default page)
  2. `$proxy_add_x_forwarded_for` aur sirf `$remote_addr` me kya farak
     hai jab request pehle se ek proxy se ho ke aayi ho (proxy chain)?
  3. Docker compose network me service naam DNS ki tarah kaam karta hai —
     `upstream backend_pool { server backend:8000; }` me "backend" kahan
     se resolve hua?
  4. Production me nginx ke peeche 3 backend replicas hote to upstream
     block me kya badalta?
""")
    finally:
        cleanup()


if __name__ == "__main__":
    main()
