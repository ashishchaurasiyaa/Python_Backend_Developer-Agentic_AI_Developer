"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  DAY 42 — enum + datetime + os/sys + logging (COMPLETE)                      ║
║  Level: Basic → Advanced → Production Patterns                               ║
╚══════════════════════════════════════════════════════════════════════════════╝

TOPICS:
  Part A: enum module — Enum, StrEnum, IntEnum, Flag, auto()
  Part B: datetime module — dates, times, timedelta, timezone
  Part C: os + sys module — environment, paths, system info
  Part D: logging module — complete production logging
  Part E: subprocess — run system commands safely
  Part F: Interview Q&A
"""

from enum import Enum, StrEnum, IntEnum, Flag, auto, unique
from datetime import datetime, timedelta, date, timezone
import os
import sys
import logging
import subprocess
from typing import Optional


# ══════════════════════════════════════════════════════════════════════════════
# PART A: enum MODULE
# ══════════════════════════════════════════════════════════════════════════════
"""
WHY ENUM?
  String constants are DANGEROUS:
    role = "ADMIN"     # typo → "ADIMN" — no error at runtime!
    if role == "admn": # bug — no warning

  Enum catches errors at DEFINITION TIME:
    class Role(Enum):
        ADMIN = "admin"
    Role.ADIMN   # AttributeError immediately!

ENUM TYPES:
  Enum     → base, any value
  StrEnum  → subclass of str — can be used WHERE str is expected (Python 3.11+)
  IntEnum  → subclass of int — can be compared to int
  Flag     → bit flags — combine with | & ~
  auto()   → auto-assign values

ENUM FEATURES:
  .name     → "ADMIN"    (the Python attribute name)
  .value    → "admin"    (the assigned value)
  list(MyEnum)           → all members
  MyEnum["ADMIN"]        → get by name
  MyEnum("admin")        → get by value
  for member in MyEnum:  → iterate
"""

print("=" * 60)
print("PART A: enum Module")
print("=" * 60)


# ── 1. Basic Enum ──
class AgentStatus(Enum):
    IDLE      = "idle"
    RUNNING   = "running"
    PAUSED    = "paused"
    COMPLETED = "completed"
    FAILED    = "failed"

    def is_active(self) -> bool:
        return self in (AgentStatus.RUNNING, AgentStatus.PAUSED)

    def is_terminal(self) -> bool:
        return self in (AgentStatus.COMPLETED, AgentStatus.FAILED)


# Usage
status = AgentStatus.RUNNING
print(f"status.name:  {status.name}")    # RUNNING
print(f"status.value: {status.value}")   # running
print(f"is_active:    {status.is_active()}")     # True
print(f"is_terminal:  {status.is_terminal()}")   # False

# Get by name (string → Enum)
s = AgentStatus["FAILED"]
print(f"By name 'FAILED': {s}")

# Get by value (value → Enum)
s2 = AgentStatus("idle")
print(f"By value 'idle': {s2}")

# Iterate all members
print(f"All statuses: {[s.value for s in AgentStatus]}")

# Comparison
print(f"Status == RUNNING: {status == AgentStatus.RUNNING}")  # True
print(f"Status is RUNNING: {status is AgentStatus.RUNNING}")  # True (singletons!)

# Use in match-case (Python 3.10+)
def handle_status(s: AgentStatus) -> str:
    match s:
        case AgentStatus.IDLE:      return "Waiting for task..."
        case AgentStatus.RUNNING:   return "Task in progress"
        case AgentStatus.PAUSED:    return "Paused — resume when ready"
        case AgentStatus.COMPLETED: return "✅ Task completed"
        case AgentStatus.FAILED:    return "❌ Task failed — retry?"

print(f"\nmatch-case with enum:")
for s in AgentStatus:
    print(f"  {handle_status(s)}")


# ── 2. StrEnum — usable directly as string ──
class Role(StrEnum):
    """StrEnum values ARE strings — no need for .value"""
    SYSTEM    = "system"
    USER      = "user"
    ASSISTANT = "assistant"
    TOOL      = "tool"


print(f"\nStrEnum:")
role = Role.USER
print(f"role == 'user': {role == 'user'}")     # True! StrEnum is a str
print(f"isinstance str: {isinstance(role, str)}")  # True
print(f"f-string: {role}")                     # "user" (no .value needed!)

# Works directly in dict
message = {"role": Role.USER, "content": "Hello"}  # role IS a string
print(f"Message role type: {type(message['role'])}")  # <enum 'Role'>
print(f"Message role value: {message['role']}")       # user (prints as string)

# Validate from API input
def parse_role(raw: str) -> Role:
    try:
        return Role(raw.lower())
    except ValueError:
        raise ValueError(f"Invalid role {raw!r}. Valid: {[r.value for r in Role]}")

print(f"parse_role('USER'): {parse_role('USER')}")


# ── 3. IntEnum — comparable to integers ──
class Priority(IntEnum):
    LOW      = 1
    MEDIUM   = 2
    HIGH     = 3
    CRITICAL = 4


print(f"\nIntEnum:")
p = Priority.HIGH
print(f"Priority.HIGH == 3: {p == 3}")      # True
print(f"Priority.HIGH > Priority.LOW: {p > Priority.LOW}")  # True
print(f"sorted: {sorted([Priority.CRITICAL, Priority.LOW, Priority.HIGH])}")


# ── 4. auto() — auto-assign values ──
class ModelTier(Enum):
    BASIC    = auto()   # 1
    STANDARD = auto()   # 2
    PREMIUM  = auto()   # 3
    ELITE    = auto()   # 4

print(f"\nauto() values: {[(t.name, t.value) for t in ModelTier]}")


# ── 5. @unique — prevent duplicate values ──
@unique
class HttpMethod(StrEnum):
    GET    = "GET"
    POST   = "POST"
    PUT    = "PUT"
    PATCH  = "PATCH"
    DELETE = "DELETE"

# This would raise ValueError at CLASS DEFINITION:
# @unique
# class Bad(Enum):
#     A = 1
#     B = 1   # duplicate! → ValueError


# ── 6. Flag — bitwise combination ──
class Permission(Flag):
    READ    = auto()   # 1
    WRITE   = auto()   # 2
    EXECUTE = auto()   # 4
    DELETE  = auto()   # 8

    # Combination shortcuts
    READ_WRITE = READ | WRITE
    ALL = READ | WRITE | EXECUTE | DELETE


print(f"\nFlag (bitwise permissions):")
user_perms = Permission.READ | Permission.WRITE
print(f"User permissions: {user_perms}")
print(f"Can READ:    {Permission.READ in user_perms}")    # True
print(f"Can EXECUTE: {Permission.EXECUTE in user_perms}") # False
print(f"Can DELETE:  {Permission.DELETE in user_perms}")  # False

admin_perms = Permission.ALL
print(f"Admin: {admin_perms}")


# ══════════════════════════════════════════════════════════════════════════════
# PART B: datetime MODULE
# ══════════════════════════════════════════════════════════════════════════════
"""
TYPES:
  date:      year, month, day (no time)
  time:      hour, minute, second, microsecond (no date)
  datetime:  date + time combined (most used)
  timedelta: duration / difference between datetimes
  timezone:  UTC offset

KEY METHODS:
  datetime.now()          → current local datetime (naive)
  datetime.now(tz=UTC)    → current UTC datetime (aware)
  datetime.utcnow()       → deprecated, use datetime.now(timezone.utc)
  datetime.fromisoformat() → parse ISO format string
  dt.strftime(format)     → datetime → string
  datetime.strptime(str, fmt) → string → datetime

FORMAT CODES:
  %Y  year  (2024)    %m  month (01-12)    %d  day (01-31)
  %H  hour  (00-23)   %M  minute (00-59)   %S  second (00-59)
  %f  microsecond     %z  UTC offset       %Z  timezone name
  %a  weekday abbrev  %A  weekday full     %b  month abbrev
"""

print("\n" + "=" * 60)
print("PART B: datetime Module")
print("=" * 60)

# Current datetime
now = datetime.now()
utc_now = datetime.now(timezone.utc)

print(f"Local now:   {now}")
print(f"UTC now:     {utc_now}")
print(f"ISO format:  {now.isoformat()}")

# strftime — format datetime as string
print(f"\nFormatting:")
print(f"  {now.strftime('%Y-%m-%d')}")            # 2024-01-15
print(f"  {now.strftime('%d/%m/%Y %H:%M:%S')}")   # 15/01/2024 14:30:22
print(f"  {now.strftime('%A, %B %d, %Y')}")        # Monday, January 15, 2024
print(f"  {now.strftime('%Y-%m-%dT%H:%M:%SZ')}")   # ISO with Z (UTC marker)

# strptime — parse string to datetime
date_str = "2024-01-15 14:30:22"
parsed = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
print(f"\nParsed: {parsed} (type: {type(parsed).__name__})")

# fromisoformat — parse ISO 8601 strings
iso_str = "2024-01-15T14:30:22.123456"
dt = datetime.fromisoformat(iso_str)
print(f"From ISO: {dt}")

# timedelta — date arithmetic
delta_1_day = timedelta(days=1)
delta_1_hour = timedelta(hours=1)
delta_90_days = timedelta(days=90)

tomorrow = now + timedelta(days=1)
yesterday = now - timedelta(days=1)
next_quarter = now + timedelta(days=90)

print(f"\nDate arithmetic:")
print(f"  Tomorrow:     {tomorrow.date()}")
print(f"  Yesterday:    {yesterday.date()}")
print(f"  +90 days:     {next_quarter.date()}")

# Difference between datetimes
start = datetime(2024, 1, 1, 0, 0, 0)
end   = datetime(2024, 3, 15, 12, 30, 0)
diff  = end - start

print(f"\nDifference:")
print(f"  {diff.days} days, {diff.seconds // 3600} hours")
print(f"  Total seconds: {diff.total_seconds():,.0f}")

# Timezone-aware (production — always use UTC internally)
from datetime import timezone as tz

utc = timezone.utc
aware_now = datetime.now(tz=utc)
print(f"\nTimezone-aware (UTC): {aware_now.isoformat()}")

# Convert to different timezone (using zoneinfo — Python 3.9+)
try:
    from zoneinfo import ZoneInfo
    ist = ZoneInfo("Asia/Kolkata")
    ist_now = aware_now.astimezone(ist)
    print(f"IST (India):          {ist_now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
except (ImportError, Exception):
    print("  (zoneinfo not available — install tzdata)")


# Production patterns
def age_in_days(created_at: datetime) -> int:
    """How many days since created_at?"""
    return (datetime.now() - created_at).days


def is_expired(created_at: datetime, ttl_hours: int = 24) -> bool:
    """Check if a session/token has expired."""
    return datetime.now() - created_at > timedelta(hours=ttl_hours)


def format_relative(dt: datetime) -> str:
    """Human-readable: '2 hours ago', 'in 3 days'"""
    diff = datetime.now() - dt
    seconds = int(diff.total_seconds())
    if seconds < 0:
        seconds = -seconds
        prefix, suffix = "in ", ""
    else:
        prefix, suffix = "", " ago"

    if seconds < 60:    return f"{prefix}{seconds}s{suffix}"
    if seconds < 3600:  return f"{prefix}{seconds//60}m{suffix}"
    if seconds < 86400: return f"{prefix}{seconds//3600}h{suffix}"
    return f"{prefix}{seconds//86400}d{suffix}"


session_created = datetime.now() - timedelta(hours=2, minutes=15)
print(f"\nSession age: {format_relative(session_created)}")
print(f"Expired (24h TTL): {is_expired(session_created, ttl_hours=24)}")


# ══════════════════════════════════════════════════════════════════════════════
# PART C: os + sys MODULE
# ══════════════════════════════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("PART C: os + sys Module")
print("=" * 60)

# ── os.environ — environment variables ──
print("Environment Variables:")
home_dir = os.environ.get("HOME", "not set")
path_var  = os.environ.get("PATH", "")[:60]
api_key   = os.environ.get("OPENAI_API_KEY", "not configured")

print(f"  HOME: {home_dir}")
print(f"  PATH: {path_var}...")
print(f"  OPENAI_API_KEY: {'*' * len(api_key) if api_key != 'not configured' else api_key}")

# Set environment variable (only for current process)
os.environ["MY_APP_ENV"] = "development"
os.environ["LOG_LEVEL"]  = "DEBUG"
print(f"  MY_APP_ENV: {os.environ['MY_APP_ENV']}")

# Check if key exists
print(f"  OPENAI_API_KEY set: {'OPENAI_API_KEY' in os.environ}")


# ── os.path — path operations (use pathlib in new code) ──
print("\nos.path operations:")
filepath = "/Users/user/projects/myapp/config/settings.py"
print(f"  dirname:  {os.path.dirname(filepath)}")
print(f"  basename: {os.path.basename(filepath)}")
print(f"  splitext: {os.path.splitext(filepath)}")
print(f"  exists:   {os.path.exists(filepath)}")
print(f"  join:     {os.path.join('/tmp', 'data', 'file.json')}")
print(f"  abspath:  {os.path.abspath('.')}")


# ── os file/dir operations ──
import tempfile
print("\nFile/Directory operations:")
with tempfile.TemporaryDirectory() as tmpdir:
    # Create directory
    new_dir = os.path.join(tmpdir, "data", "outputs")
    os.makedirs(new_dir, exist_ok=True)
    print(f"  Created: {new_dir}")
    print(f"  isdir:   {os.path.isdir(new_dir)}")

    # List directory
    parent = os.path.join(tmpdir, "data")
    print(f"  listdir: {os.listdir(parent)}")

    # os.walk — recursive directory listing
    for root, dirs, files in os.walk(tmpdir):
        level = root.replace(tmpdir, "").count(os.sep)
        indent = "  " * level
        print(f"  {indent}{os.path.basename(root)}/")

    # Remove directory
    os.rmdir(new_dir)
    print(f"  After rmdir: {os.listdir(parent)}")


# ── os system info ──
print("\nSystem Info (os):")
print(f"  Platform:   {sys.platform}")
print(f"  Python:     {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
print(f"  CWD:        {os.getcwd()}")
print(f"  PID:        {os.getpid()}")
print(f"  CPU count:  {os.cpu_count()}")


# ── sys module ──
print("\nsys module:")
print(f"  sys.argv:        {sys.argv[:3]}")          # command line args
print(f"  sys.version:     {sys.version[:30]}")
print(f"  sys.path[:2]:    {sys.path[:2]}")           # module search path
print(f"  sys.executable:  {sys.executable}")          # python interpreter path
print(f"  sys.maxsize:     {sys.maxsize:,}")           # max int for platform
print(f"  sys.getdefaultencoding(): {sys.getdefaultencoding()}")

# sys.exit — controlled exit
def safe_exit(code: int = 0) -> None:
    """Use sys.exit() instead of exit() in scripts."""
    # sys.exit(code)  # 0 = success, non-zero = error
    print(f"  Would exit with code {code}")

safe_exit(0)


# ── Production: Settings class using os.environ ──
class Settings:
    """Centralized settings from environment variables."""

    # Required — will raise if not set
    OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")

    # Optional with defaults
    LLM_MODEL:       str   = os.environ.get("LLM_MODEL", "gpt-4")
    MAX_TOKENS:      int   = int(os.environ.get("MAX_TOKENS", "4096"))
    TEMPERATURE:     float = float(os.environ.get("TEMPERATURE", "0.7"))
    LOG_LEVEL:       str   = os.environ.get("LOG_LEVEL", "INFO")
    DEBUG:           bool  = os.environ.get("DEBUG", "false").lower() == "true"
    MAX_RETRIES:     int   = int(os.environ.get("MAX_RETRIES", "3"))
    RATE_LIMIT_RPM:  int   = int(os.environ.get("RATE_LIMIT_RPM", "60"))

    @classmethod
    def validate(cls) -> None:
        """Validate required settings on startup."""
        if not cls.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY environment variable is not set!")
        if cls.TEMPERATURE < 0 or cls.TEMPERATURE > 2:
            raise ValueError(f"TEMPERATURE must be 0-2, got {cls.TEMPERATURE}")

    @classmethod
    def show(cls) -> None:
        print(f"\n  Settings:")
        print(f"    LLM_MODEL:   {cls.LLM_MODEL}")
        print(f"    MAX_TOKENS:  {cls.MAX_TOKENS}")
        print(f"    TEMPERATURE: {cls.TEMPERATURE}")
        print(f"    LOG_LEVEL:   {cls.LOG_LEVEL}")
        print(f"    DEBUG:       {cls.DEBUG}")


Settings.show()


# ══════════════════════════════════════════════════════════════════════════════
# PART D: logging MODULE (PRODUCTION COMPLETE)
# ══════════════════════════════════════════════════════════════════════════════
"""
WHY logging OVER print?
  print: goes to stdout, no levels, can't filter, no timestamps, no context
  logging: levels (DEBUG/INFO/WARNING/ERROR/CRITICAL), handlers (file, stream),
           formatters, filtering, structured output (JSON)

LEVELS (in order):
  DEBUG    (10) → detailed debugging info
  INFO     (20) → general information
  WARNING  (30) → something unexpected, but OK
  ERROR    (40) → error, function failed
  CRITICAL (50) → serious error, may crash

COMPONENTS:
  Logger:   what you use (logging.getLogger("myapp"))
  Handler:  where logs go (StreamHandler=console, FileHandler=file)
  Formatter:how logs look ("[%(levelname)s] %(name)s: %(message)s")
  Filter:   which messages pass through

HIERARCHY:
  root logger → app logger → module logger
  If module logger has no handler: propagates UP to parent
"""

print("\n" + "=" * 60)
print("PART D: logging Module")
print("=" * 60)

# ── 1. Basic logging ──
# Don't use root logger in production (use named loggers)
logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")

# ── 2. Named logger (production pattern) ──
logger = logging.getLogger("myapp.agent")
logger.setLevel(logging.DEBUG)

# Remove any handlers (clean slate for demo)
logger.handlers.clear()
logger.propagate = False

# StreamHandler with custom format
handler = logging.StreamHandler()
formatter = logging.Formatter(
    fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
handler.setFormatter(formatter)
logger.addHandler(handler)

print("\nLogging levels:")
logger.debug("Agent initialized with model=gpt-4")
logger.info("Starting task: research Python async patterns")
logger.warning("Token usage at 85% of limit (6970/8192)")
logger.error("Tool call failed: web_search timeout after 30s")
# logger.critical("Database connection lost!")

# ── 3. Logging with context (extra dict) ──
class ContextLogger:
    """Logger with automatic context injection."""

    def __init__(self, name: str, context: dict):
        self._logger = logging.getLogger(name)
        self._context = context

    def _format(self, msg: str) -> str:
        ctx = " ".join(f"{k}={v!r}" for k, v in self._context.items())
        return f"{msg} | {ctx}"

    def info(self, msg: str, **extra) -> None:
        self._logger.info(self._format(msg), extra=extra)

    def error(self, msg: str, exc_info: bool = False, **extra) -> None:
        self._logger.error(self._format(msg), exc_info=exc_info, extra=extra)

    def warning(self, msg: str, **extra) -> None:
        self._logger.warning(self._format(msg), extra=extra)


agent_log = ContextLogger("agent", {"agent_id": "agent_001", "model": "gpt-4"})
agent_log.info("Task started", task="research")
agent_log.warning("Rate limit approaching")
agent_log.error("Tool execution failed")

# ── 4. JSON Logging (for log aggregation — ELK, CloudWatch) ──
import json as _json

class JSONFormatter(logging.Formatter):
    """Format logs as JSON for structured log aggregation."""

    def format(self, record: logging.LogRecord) -> str:
        data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
        }
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)
        # Add extra fields
        for key in ("agent_id", "model", "task", "tokens"):
            if hasattr(record, key):
                data[key] = getattr(record, key)
        return _json.dumps(data)


json_logger = logging.getLogger("myapp.json")
json_logger.handlers.clear()
json_logger.propagate = False
json_logger.setLevel(logging.DEBUG)
json_handler = logging.StreamHandler()
json_handler.setFormatter(JSONFormatter())
json_logger.addHandler(json_handler)

print("\nJSON logging:")
json_logger.info("Agent completed task")
json_logger.error("API rate limit exceeded")

# ── 5. File handler + rotation ──
print("\nFile logging (rotating):")
from logging.handlers import RotatingFileHandler
import tempfile, os

log_dir = tempfile.mkdtemp()
log_file = os.path.join(log_dir, "agent.log")

file_logger = logging.getLogger("myapp.file")
file_logger.handlers.clear()
file_logger.propagate = False
file_logger.setLevel(logging.DEBUG)

# Rotating: max 5MB per file, keep 3 backup files
rot_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3)
rot_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
file_logger.addHandler(rot_handler)

file_logger.info("Logging to rotating file")
file_logger.error("Example error entry")
print(f"  Log file: {log_file}")
print(f"  File exists: {os.path.exists(log_file)}")


# ══════════════════════════════════════════════════════════════════════════════
# PART E: subprocess — RUN SYSTEM COMMANDS
# ══════════════════════════════════════════════════════════════════════════════
"""
WHY subprocess?
  - Run shell commands from Python (git, docker, pip, custom scripts)
  - Capture command output and errors
  - AI code runner tools — execute user-submitted code safely

FUNCTIONS:
  subprocess.run()        → run command, wait for it to finish (recommended)
  subprocess.Popen()      → run + stream output in real-time
  subprocess.check_output() → shortcut: run and get output (raises on error)

subprocess.run() ARGUMENTS:
  args:          command as list [cmd, arg1, arg2] or string
  capture_output=True   → capture stdout + stderr
  text=True             → return strings (not bytes)
  timeout=N             → raise TimeoutExpired after N seconds
  check=True            → raise CalledProcessError if return code != 0
  cwd="path"            → set working directory
  env=dict              → set environment variables

SECURITY: NEVER use shell=True with user input!
  shell=True + user input = command injection vulnerability
  Always use list form: ["python", user_script]
"""

print("\n" + "=" * 60)
print("PART E: subprocess")
print("=" * 60)

# ── 1. Basic command ──
result = subprocess.run(
    ["python", "--version"],
    capture_output=True,
    text=True,
    timeout=10,
)
print(f"Python version: {result.stdout.strip()}")
print(f"Return code: {result.returncode}")

# ── 2. Command that fails ──
result = subprocess.run(
    ["ls", "/nonexistent/path"],
    capture_output=True,
    text=True,
)
print(f"\nFailed command (returncode={result.returncode}):")
print(f"  stderr: {result.stderr.strip()}")

# ── 3. check=True — raise on failure ──
try:
    subprocess.run(["ls", "/nonexistent"], check=True, capture_output=True)
except subprocess.CalledProcessError as e:
        print(f"\nCalledProcessError caught: returncode={e.returncode}")

# ── 4. Capture and process output ──
result = subprocess.run(
    ["python", "-c", "print('Hello from subprocess!')"],
    capture_output=True,
    text=True,
)
output = result.stdout.strip()
print(f"\nCapture output: {output!r}")

# ── 5. AI Code Runner — safe execution ──
def run_python_code(code: str, timeout: int = 10) -> dict:
    """
    Safely execute Python code in a subprocess.
    Used in AI coding assistants and REPL tools.
    """
    import tempfile, os

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        script_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, script_path],  # use SAME Python as current process
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
        return {"success": False, "error": f"Timeout after {timeout}s", "stdout": "", "stderr": ""}
    finally:
        os.unlink(script_path)  # cleanup


print("\nAI Code Runner:")
code_samples = [
    "print('Hello World!')",
    "x = [i**2 for i in range(5)]\nprint(x)",
    "raise ValueError('intentional error')",
]

for code in code_samples:
    result = run_python_code(code)
    icon = "✅" if result["success"] else "❌"
    output = result["stdout"].strip() or result["stderr"].strip() or result.get("error", "")
    print(f"  {icon} `{code[:40].strip()}` → {output[:60]}")


# ── 6. Popen — streaming real-time output ──
print("\nPopen streaming output:")
process = subprocess.Popen(
    ["python", "-c", "import time\nfor i in range(3):\n  print(f'Line {i}')\n  import sys; sys.stdout.flush()"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)

for line in process.stdout:
    print(f"  Stream: {line.rstrip()}")

process.wait()
print(f"  Exit code: {process.returncode}")


# ══════════════════════════════════════════════════════════════════════════════
# PART F: INTERVIEW Q&A
# ══════════════════════════════════════════════════════════════════════════════
"""
Q1: Why use Enum over string constants?
A:  String constants: typos give no error at all — silent bugs.
    Enum: typos cause AttributeError immediately (fail fast).
    Enum: completion in IDEs, exhaustive match-case checking, clear intent.
    Also: Enum members are SINGLETONS (identity comparison with `is` works).

Q2: What is the difference between Enum and StrEnum?
A:  Enum: members are Enum objects — need .value to get the string
          "user" == Role.USER → False (different types)
    StrEnum: members ARE strings — can be used directly as strings
             "user" == Role.USER → True

Q3: What is the difference between naive and aware datetime?
A:  Naive: no timezone info (datetime.now())
           Dangerous in global apps — 5PM could mean any timezone!
    Aware: has timezone info (datetime.now(timezone.utc))
           Always know exactly which moment it represents

    Production rule: ALWAYS store UTC internally, convert to local for display.

Q4: What is the difference between os.environ.get() and os.getenv()?
A:  They are functionally identical — both return None (or default) for missing keys.
    os.environ.get("KEY", "default")  ← dict method
    os.getenv("KEY", "default")       ← convenience function
    Both are fine; os.environ.get() is more explicit about what it's doing.

Q5: When is shell=True dangerous in subprocess?
A:  With shell=True: the command is passed to the shell — shell metacharacters are interpreted.
    If user input is part of the command:
      user_input = "file.py; rm -rf /"    # malicious input
      subprocess.run(f"python {user_input}", shell=True)  → DELETES EVERYTHING!

    Safe alternative: always use list form:
      subprocess.run(["python", user_script_path])  # shell metacharacters not interpreted

Q6: What is the difference between logging.warning() and logger.warning()?
A:  logging.warning(): uses the ROOT logger (affects entire application)
    logger.warning():  uses YOUR named logger (scoped to your module)
    Always use named loggers in production:
    logger = logging.getLogger(__name__)  # __name__ = "mypackage.mymodule"
    logger.warning("...")

Q7: What is RotatingFileHandler and why use it?
A:  RotatingFileHandler: automatically creates new log files when size limit reached.
    Keeps backupCount old files. Prevents log files from growing infinitely.
    Alternative: TimedRotatingFileHandler — rotates at midnight, weekly, etc.
    In production: logs sent to CloudWatch/ELK/Datadog instead of local files.
"""

print("\n✅ Day42 — enum + datetime + os + sys + logging + subprocess COMPLETE")
