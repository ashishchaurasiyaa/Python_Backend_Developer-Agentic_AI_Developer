"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FILE I/O — Reading, Writing, CSV, JSON
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ARCHITECTURE UNDERSTANDING:
  open(file, mode) → file object → read/write → close
  'r'  = read       (default)
  'w'  = write      (overwrites existing)
  'a'  = append     (adds to existing)
  'rb' = read binary (images, PDFs)
  'wb' = write binary

  WHY with statement?
  → __enter__ opens file, __exit__ closes it even on exception
  → No manual .close() needed — no resource leak

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import csv
import json
import pathlib

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. BASIC FILE READ / WRITE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

# Write a file
with open("sample.txt", "w") as f:
    f.write("Line 1: Python is great\n")
    f.write("Line 2: File I/O is important\n")
    f.write("Line 3: Always use with statement\n")

# Read entire file
with open("sample.txt", "r") as f:
    content = f.read()          # entire string
print(content)

# Read line by line (memory efficient for large files)
with open("sample.txt", "r") as f:
    for line in f:              # file is iterable — lazy read
        print(line.strip())

# Read all lines as list
with open("sample.txt", "r") as f:
    lines = f.readlines()       # ['Line 1...\n', 'Line 2...\n']

# Append to existing file
with open("sample.txt", "a") as f:
    f.write("Line 4: Appended line\n")

# Read with seek (random access)
with open("sample.txt", "r") as f:
    f.seek(0)                   # go to start
    first_line = f.readline()   # read one line
    position = f.tell()         # current byte position
    print(f"Position after first line: {position}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. PATHLIB (modern approach — use this, not os.path)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
INTERVIEW Q: os.path vs pathlib?
A: pathlib is OOP, cleaner, cross-platform. os.path is old string-based API.
   Always prefer pathlib in modern Python (3.4+).
"""

path = pathlib.Path("sample.txt")

# Check existence
print(path.exists())            # True
print(path.is_file())           # True
print(path.suffix)              # '.txt'
print(path.stem)                # 'sample'
print(path.parent)              # current directory

# Read / write with pathlib
content = path.read_text(encoding="utf-8")
path.write_text("New content", encoding="utf-8")

# Directory operations
current_dir = pathlib.Path(".")
for file in current_dir.glob("*.py"):   # find all .py files
    print(file.name)

for file in current_dir.rglob("*.py"): # recursive search
    print(file)

# Create directory
logs_dir = pathlib.Path("logs")
logs_dir.mkdir(parents=True, exist_ok=True)  # no error if exists

# Join paths (cross-platform — no "/" hardcoding)
config_file = pathlib.Path("config") / "settings.json"
print(config_file)  # config/settings.json

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. CSV FILES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
INTERVIEW Q: When to use csv module vs pandas?
A: csv module — simple, no dependency, small files
   pandas    — analysis, large files, transformations needed
"""

# Write CSV
employees = [
    {"name": "Ashish", "age": 28, "role": "Backend Dev"},
    {"name": "Priya",  "age": 25, "role": "Data Engineer"},
    {"name": "Rahul",  "age": 30, "role": "DevOps"},
]

with open("employees.csv", "w", newline="", encoding="utf-8") as f:
    fieldnames = ["name", "age", "role"]
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(employees)

# Read CSV as dict (most common pattern)
with open("employees.csv", "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        print(f"{row['name']} → {row['role']}")

# Read CSV as list of lists
with open("employees.csv", "r", encoding="utf-8") as f:
    reader = csv.reader(f)
    next(reader)            # skip header
    for row in reader:
        print(row)          # ['Ashish', '28', 'Backend Dev']

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. JSON FILES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
INTERVIEW Q: json.dumps vs json.dump?
A: dumps → string output (serialize to string)
   dump  → file output  (serialize to file)
Same for loads (string) vs load (file)
"""

config = {
    "database": {
        "host": "localhost",
        "port": 5432,
        "name": "myapp_db"
    },
    "redis_url": "redis://localhost:6379",
    "debug": True,
    "allowed_origins": ["http://localhost:3000"],
}

# Write JSON to file
with open("config.json", "w") as f:
    json.dump(config, f, indent=2)     # indent=2 for pretty print

# Read JSON from file
with open("config.json", "r") as f:
    loaded_config = json.load(f)
print(loaded_config["database"]["port"])   # 5432

# JSON string serialization (for APIs, Redis storage)
json_string = json.dumps(config, indent=2)
back_to_dict = json.loads(json_string)

# Custom JSON serialization (for datetime, custom objects)
from datetime import datetime

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()          # "2025-05-19T10:30:00"
        return super().default(obj)

data_with_date = {"created_at": datetime.now(), "name": "Ashish"}
json_str = json.dumps(data_with_date, cls=DateTimeEncoder)
print(json_str)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. REAL-WORLD PATTERN: Config Loader
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

class ConfigLoader:
    """
    Load JSON config with fallback defaults.
    Architecture pattern: separate config from code.
    """
    def __init__(self, config_path: str, defaults: dict | None = None):
        self._path = pathlib.Path(config_path)
        self._defaults = defaults or {}
        self._config = self._load()

    def _load(self) -> dict:
        if not self._path.exists():
            return self._defaults.copy()
        with self._path.open() as f:
            data = json.load(f)
        return {**self._defaults, **data}   # defaults + file (file wins)

    def get(self, key: str, default=None):
        return self._config.get(key, default)

    def save(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("w") as f:
            json.dump(self._config, f, indent=2)


loader = ConfigLoader("config.json", defaults={"debug": False, "port": 8000})
print(loader.get("debug"))          # True (from file)
print(loader.get("missing_key", "default_val"))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# CLEANUP
# ━━━━━━━━━━━━━━━━━━━━━━━━━━
for f in ["sample.txt", "employees.csv", "config.json"]:
    pathlib.Path(f).unlink(missing_ok=True)

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INTERVIEW Q&A:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q: Why use 'with' for files?
A: Context manager — guarantees file.close() even if exception occurs.
   Without it: file stays open → memory leak, file lock issues.

Q: 'r' vs 'rb' mode?
A: 'r' = text mode — handles line endings (\r\n → \n on Windows)
   'rb' = binary mode — exact bytes, use for images/PDFs/zip files

Q: How to read large file without loading all in memory?
A: Iterate line by line:
   with open(file) as f:
       for line in f:   ← reads one line at a time, O(1) memory
           process(line)

Q: json.dumps() when to use?
A: When you need string — storing in Redis, sending in HTTP response
   json.dump() when you need file — saving config, caching to disk
"""
