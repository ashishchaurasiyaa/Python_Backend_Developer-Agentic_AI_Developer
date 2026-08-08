"""
DevOps Lab 01 — Multi-stage Docker Build
==========================================
OBJECTIVE: ek REAL multi-stage Dockerfile likho, build karo, container chalao,
aur PROVE karo ki (a) app kaam karta hai HTTP se, (b) image naive single-stage
se chhoti hai — yehi multi-stage ka pura point hai.

TASK:
  1. TODO 1: builder stage me requirements ko isolated prefix (/install) me
     install karo — taaki stage 2 sirf yeh folder copy kare.
  2. TODO 2: runtime stage me non-root user banao (security best practice).
  3. TODO 3: us non-root user pe switch karo (USER directive).
  4. Run: python3 01_docker_multistage_build.py

Prereq: Docker daemon chalu hona chahiye (`docker info` se check karo).
        Internet chahiye (`apt-get install gcc` builder stage me download karta hai).

NOTE: Yeh script apna khud ka build context bana ke docker CLI ko subprocess
se call karta hai — koi docker-compose nahi (Lab 2/3 se alag), kyunki yahan
hum khud BUILD process test kar rahe hain, ek static stack nahi.
"""

import json
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

HOST_PORT = 18001
CONTAINER_PORT = 8000
IMAGE_MULTISTAGE = "devops-lab01-multistage:test"
IMAGE_NAIVE = "devops-lab01-naive:test"
CONTAINER_NAME = "devops-lab01-container"

# ── The tiny app that goes inside the image ────────────────────────────
APP_PY = '''\
from http.server import HTTPServer, BaseHTTPRequestHandler
import json


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok", "from": "multistage-lab"}).encode())

    def log_message(self, format, *args):
        pass  # quiet server, hum apna khud ka print karte hain


if __name__ == "__main__":
    print("listening on 0.0.0.0:8000")
    HTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
'''

# requirements.txt — production app me yahan real deps hote (psycopg2, numpy...)
# jinke liye C compiler chahiye hota hai. Hum 'requests' use kar rahe hain aur
# ISSE COMPILE karne ke liye gcc install karte hain (real-world simulate karne ke
# liye) — asli point yeh hai ki builder stage me gcc rehta hai, runtime stage me nahi.
REQUIREMENTS_TXT = "requests==2.31.0\n"

# ── TODO: is Dockerfile ko complete karo ────────────────────────────────
DOCKERFILE_MULTISTAGE = """\
# ---- Stage 1: builder (heavy — gcc, pip cache, etc.) ----
FROM python:3.12-slim AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .

# ─────────────────────────────────────────────────────────────
# TODO 1: requirements.txt ko ISOLATED prefix me install karo,
#         taaki stage 2 sirf /install folder copy kare — gcc
#         final image me kabhi nahi jaayega.
#         Hint: RUN pip install --no-cache-dir --prefix=/install -r requirements.txt
___TODO_1___
# ─────────────────────────────────────────────────────────────

COPY app.py .

# ---- Stage 2: runtime (slim — no gcc, no build cache) ----
FROM python:3.12-slim
WORKDIR /app

# ─────────────────────────────────────────────────────────────
# TODO 2: non-root user banao. Root se container chalana risky
#         hai — agar attacker container break karta hai to root
#         mil jaata hai.
#         Hint: RUN addgroup --system app && adduser --system --ingroup app app
___TODO_2___
# ─────────────────────────────────────────────────────────────

COPY --from=builder /install /usr/local
COPY --from=builder /app/app.py .

# ─────────────────────────────────────────────────────────────
# TODO 3: USER directive laga ke TODO 2 wale user pe switch karo.
#         Hint: USER app
___TODO_3___
# ─────────────────────────────────────────────────────────────

EXPOSE 8000
CMD ["python", "app.py"]
"""

# Naive baseline — TODO nahi hai, yeh sirf COMPARISON ke liye hai (ek hi stage
# me sab kuch: gcc bhi final image me reh jaata hai).
DOCKERFILE_NAIVE = """\
FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
EXPOSE 8000
CMD ["python", "app.py"]
"""


def check_todos_filled() -> bool:
    missing = [m for m in ("___TODO_1___", "___TODO_2___", "___TODO_3___") if m in DOCKERFILE_MULTISTAGE]
    if missing:
        print(f"❌ TODO abhi baaki hai: {', '.join(missing)}")
        print("   DOCKERFILE_MULTISTAGE constant me in placeholders ko real")
        print("   Dockerfile instructions se replace karo (hints comments me hain).")
        return False
    return True


def run(cmd: list, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)


def build_image(build_dir: Path, dockerfile_name: str, tag: str) -> bool:
    print(f"  building {tag} ...")
    result = run(["docker", "build", "-f", str(build_dir / dockerfile_name), "-t", tag, str(build_dir)])
    if result.returncode != 0:
        print(f"❌ build FAILED for {tag}")
        print(result.stderr[-2000:])
        return False
    return True


def image_size_bytes(tag: str) -> int:
    result = run(["docker", "image", "inspect", tag, "--format={{.Size}}"])
    if result.returncode != 0 or not result.stdout.strip():
        return -1
    return int(result.stdout.strip())


def wait_for_http(url: str, timeout_s: int = 20) -> "urllib.response.addinfourl | None":
    deadline = time.time() + timeout_s
    last_err = None
    while time.time() < deadline:
        try:
            return urllib.request.urlopen(url, timeout=2)
        except (urllib.error.URLError, ConnectionError) as e:
            last_err = e
            time.sleep(1)
    print(f"  (last connection error: {last_err})")
    return None


def cleanup() -> None:
    run(["docker", "rm", "-f", CONTAINER_NAME])


def main() -> None:
    if not check_todos_filled():
        return

    build_dir = Path(tempfile.mkdtemp(prefix="devops-lab01-"))
    try:
        (build_dir / "app.py").write_text(APP_PY)
        (build_dir / "requirements.txt").write_text(REQUIREMENTS_TXT)
        (build_dir / "Dockerfile.multistage").write_text(DOCKERFILE_MULTISTAGE)
        (build_dir / "Dockerfile.naive").write_text(DOCKERFILE_NAIVE)

        print("\n[1] Building multi-stage image...")
        if not build_image(build_dir, "Dockerfile.multistage", IMAGE_MULTISTAGE):
            print("   Dockerfile syntax check karo — TODO 1/2/3 sahi Docker")
            print("   instructions hain? (pip install / addgroup+adduser / USER)")
            return

        print("\n[2] Building naive single-stage image (comparison baseline)...")
        if not build_image(build_dir, "Dockerfile.naive", IMAGE_NAIVE):
            print("   Naive build khud fail ho gaya — yeh script ka bug hai, lab ka nahi.")
            return

        print("\n[3] Running multi-stage container...")
        cleanup()  # purana container agar bacha ho
        result = run([
            "docker", "run", "-d", "--name", CONTAINER_NAME,
            "-p", f"{HOST_PORT}:{CONTAINER_PORT}", IMAGE_MULTISTAGE,
        ])
        if result.returncode != 0:
            print("❌ FAIL — container start nahi hua")
            print(result.stderr)
            return

        print(f"\n[4] HTTP request bhej rahe hain http://localhost:{HOST_PORT}/ ...")
        resp = wait_for_http(f"http://localhost:{HOST_PORT}/")
        http_ok = False
        body = {}
        if resp is not None:
            http_ok = resp.status == 200
            body = json.loads(resp.read().decode())
            print(f"  ← {resp.status} {body}")

        print("\n[5] Image sizes compare kar rahe hain...")
        size_multistage = image_size_bytes(IMAGE_MULTISTAGE)
        size_naive = image_size_bytes(IMAGE_NAIVE)
        mb = lambda b: b / (1024 * 1024)
        print(f"  multi-stage: {mb(size_multistage):.1f} MB")
        print(f"  naive:       {mb(size_naive):.1f} MB")
        size_ok = size_multistage > 0 and size_naive > 0 and size_multistage < size_naive

        print("\n" + "─" * 55)
        if http_ok and body.get("status") == "ok" and size_ok:
            saved_pct = (1 - size_multistage / size_naive) * 100
            print(f"✅ PASS — HTTP 200 mila, aur multi-stage naive se "
                  f"{saved_pct:.0f}% chhoti hai ({mb(size_naive - size_multistage):.1f} MB saved)")
        else:
            print("❌ FAIL")
            if not http_ok:
                print("   HTTP request fail hua — container logs check karo:")
                print(f"   docker logs {CONTAINER_NAME}")
            if not size_ok:
                print("   Multi-stage image naive se CHHOTI nahi hai — TODO 1")
                print("   (--prefix=/install) sahi se bhara hai? gcc final image")
                print("   me toh nahi reh gaya? `docker history` se dekho.")

        print("""
SOCH (bolke jawab do):
  1. Builder stage me gcc install hua tha — woh final image me kyun nahi hai?
     Docker layers ka concept isse kaise judता hai?
  2. `COPY --from=builder` exactly kya copy karta hai — poora filesystem
     ya sirf jo path diya?
  3. Non-root USER kyun important hai — agar tumhara container compromise
     ho jaaye to root vs non-root se kya farak padta hai?
  4. `docker build --target builder .` se kya hoga? Kab useful hai yeh?
""")
    finally:
        cleanup()


if __name__ == "__main__":
    main()
