"""
DAY 37 — File I/O + subprocess
Architecture Level: Senior Python Backend + Agentic AI
"""

import subprocess
import json
import csv
import os
from pathlib import Path
import tempfile
import shutil


# ═══════════════════════════════════════════════════════
# PART A: File I/O — production patterns
# ═══════════════════════════════════════════════════════

# ─────────────────────────────────────────────
# 1. Basic file operations
# ─────────────────────────────────────────────

tmp_dir = Path(tempfile.mkdtemp())

# Text file — always specify encoding
text_file = tmp_dir / "notes.txt"
with open(text_file, "w", encoding="utf-8") as f:
    f.write("Line 1: Python backend\n")
    f.write("Line 2: Agentic AI\n")
    f.writelines(["Line 3\n", "Line 4\n"])

# Read modes:
# "r"  — read text (default)
# "w"  — write text (truncates)
# "a"  — append text
# "rb" — read binary
# "wb" — write binary
# "r+" — read + write

with open(text_file, "r", encoding="utf-8") as f:
    content = f.read()                    # entire file as string

with open(text_file, "r", encoding="utf-8") as f:
    lines = f.readlines()                 # list of lines (with \n)

with open(text_file, "r", encoding="utf-8") as f:
    for line in f:                        # lazy — one line at a time (best for large files)
        print(f"  Line: {line.rstrip()}")


# ─────────────────────────────────────────────
# 2. JSON — most common in backend/AI
# ─────────────────────────────────────────────

data = {
    "model": "gpt-4",
    "messages": [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi!"},
    ],
    "temperature": 0.7,
    "tokens": 150,
}

# Write JSON
json_file = tmp_dir / "conversation.json"
with open(json_file, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

# Read JSON
with open(json_file, "r", encoding="utf-8") as f:
    loaded = json.load(f)

print(f"JSON model: {loaded['model']}")

# json.dumps / json.loads — string versions
json_str = json.dumps(data, separators=(",", ":"))  # compact
parsed   = json.loads(json_str)


# Custom JSON encoder (for datetime, Decimal, dataclasses)
from datetime import datetime
from dataclasses import dataclass, asdict

@dataclass
class AgentLog:
    agent_id: str
    timestamp: datetime
    tokens: int

class AgentEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if hasattr(obj, "__dataclass_fields__"):  # dataclass
            return asdict(obj)
        return super().default(obj)

log = AgentLog("agent_1", datetime.utcnow(), 500)
print(json.dumps(log, cls=AgentEncoder))


# ─────────────────────────────────────────────
# 3. CSV — data pipeline pattern
# ─────────────────────────────────────────────

csv_file = tmp_dir / "results.csv"

# Write CSV
rows = [
    {"model": "gpt-4", "latency_ms": 450, "tokens": 500},
    {"model": "claude-3", "latency_ms": 380, "tokens": 420},
    {"model": "gemini", "latency_ms": 290, "tokens": 380},
]

with open(csv_file, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["model", "latency_ms", "tokens"])
    writer.writeheader()
    writer.writerows(rows)

# Read CSV
with open(csv_file, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        print(f"  {row['model']}: {row['latency_ms']}ms")


# ─────────────────────────────────────────────
# 4. PATTERN — Atomic file writes (prevent corruption)
# ─────────────────────────────────────────────

import os

def atomic_write(path: Path, content: str) -> None:
    """
    Write to a temp file then rename — prevents partial writes.
    If the process dies mid-write, original file is intact.
    Used in production for config files, agent state, etc.
    """
    tmp_path = path.with_suffix(".tmp")
    try:
        tmp_path.write_text(content, encoding="utf-8")
        tmp_path.replace(path)   # atomic on same filesystem
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


atomic_write(tmp_dir / "state.json", json.dumps({"agent": "running"}))
print("Atomic write successful")


# ═══════════════════════════════════════════════════════
# PART B: subprocess — run shell commands from Python
# ═══════════════════════════════════════════════════════

# ─────────────────────────────────────────────
# 1. subprocess.run — the standard way
# ─────────────────────────────────────────────

# Basic run
result = subprocess.run(
    ["python", "--version"],
    capture_output=True,    # capture stdout + stderr
    text=True,              # decode as string (not bytes)
    timeout=10,             # raise TimeoutExpired after 10s
)
print(f"\nPython version: {result.stdout.strip()}")
print(f"Return code: {result.returncode}")  # 0 = success

# Check=True raises CalledProcessError on non-zero exit
try:
    subprocess.run(
        ["ls", "/nonexistent"],
        check=True,
        capture_output=True,
        text=True,
    )
except subprocess.CalledProcessError as e:
    print(f"Command failed: {e.returncode}")
    print(f"stderr: {e.stderr.strip()}")


# ─────────────────────────────────────────────
# 2. Shell commands safely
# ─────────────────────────────────────────────

# NEVER use shell=True with user input — command injection risk!
# BAD:  subprocess.run(f"ls {user_input}", shell=True)
# GOOD: subprocess.run(["ls", user_input])

# When you NEED shell features (pipes, globs):
# Use shell=True only with hardcoded strings
result = subprocess.run(
    "echo 'Hello' | tr '[:lower:]' '[:upper:]'",
    shell=True,
    capture_output=True,
    text=True,
)
print(f"Shell result: {result.stdout.strip()}")


# ─────────────────────────────────────────────
# 3. AGENTIC AI — Code execution tool
# ─────────────────────────────────────────────

def run_python_code(code: str, timeout: int = 30) -> dict:
    """
    Execute Python code safely — used in AI agents.
    Production: use Docker sandbox, not direct subprocess.
    """
    code_file = tmp_dir / "agent_code.py"
    code_file.write_text(code, encoding="utf-8")

    try:
        result = subprocess.run(
            ["python", str(code_file)],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "timeout", "stdout": "", "stderr": ""}
    except Exception as e:
        return {"success": False, "error": str(e), "stdout": "", "stderr": ""}
    finally:
        code_file.unlink(missing_ok=True)


code_result = run_python_code("""
result = sum(range(1, 101))
print(f"Sum 1-100: {result}")
""")
print(f"\nCode result: {code_result['stdout'].strip()}")


# ─────────────────────────────────────────────
# 4. subprocess.Popen — streaming output
# ─────────────────────────────────────────────

def stream_command(command: list[str]):
    """Stream command output line by line — useful for long-running processes."""
    with subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,  # line-buffered
    ) as proc:
        for line in proc.stdout:  # type: ignore
            yield line.rstrip()
        proc.wait()
        return proc.returncode


print("\nStreamed output:")
for line in stream_command(["python", "-c", "for i in range(3): print(f'Line {i}')"]):
    print(f"  > {line}")


# Cleanup
shutil.rmtree(tmp_dir, ignore_errors=True)


# ─────────────────────────────────────────────
# INTERVIEW CHEAT SHEET
# ─────────────────────────────────────────────
# subprocess.run()     — standard, blocks until done
# subprocess.Popen()   — non-blocking, streaming, more control
# check=True           — raise on non-zero exit
# capture_output=True  — capture stdout+stderr
# text=True            — decode as string
# timeout=n            — raise TimeoutExpired after n seconds
# shell=True           — DANGEROUS with user input (injection risk)
#
# File I/O best practices:
# Always use 'with' — guarantees file close
# Always specify encoding="utf-8"
# Use pathlib.Path instead of os.path
# Use atomic writes for critical files
# Use json.dump/load for structured data
# Use csv.DictReader/Writer for tabular data
