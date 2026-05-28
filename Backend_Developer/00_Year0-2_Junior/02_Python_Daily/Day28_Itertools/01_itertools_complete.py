"""
DAY 28 — itertools: Complete Senior-Level Guide
Architecture Level: Senior Python Backend + Agentic AI

itertools produces LAZY iterators — they don't compute all values upfront.
Critical for: large datasets, streaming AI responses, infinite sequences.
"""

import itertools
from typing import Iterator, Iterable, TypeVar

T = TypeVar("T")


# ═══════════════════════════════════════════════════════
# PART A: INFINITE ITERATORS
# ═══════════════════════════════════════════════════════

# count — infinite counter
counter = itertools.count(start=1, step=2)
print("count:", [next(counter) for _ in range(5)])   # [1, 3, 5, 7, 9]

# cycle — infinite loop through iterable
models = itertools.cycle(["gpt-4", "claude-3", "gemini"])
print("cycle:", [next(models) for _ in range(5)])   # round-robin

# repeat — repeat N times or infinitely
print("repeat:", list(itertools.repeat(0, 5)))       # [0,0,0,0,0]


# ═══════════════════════════════════════════════════════
# PART B: COMBINING ITERATORS
# ═══════════════════════════════════════════════════════

# chain — flatten iterables
api_keys = list(itertools.chain(
    ["key_prod_1", "key_prod_2"],
    ["key_dev_1"],
    ["key_staging_1", "key_staging_2"],
))
print("\nchain:", api_keys)

# chain.from_iterable — flattens one level
nested = [["tool_1", "tool_2"], ["tool_3"], ["tool_4", "tool_5"]]
flat = list(itertools.chain.from_iterable(nested))
print("chain.from_iterable:", flat)

# zip_longest — zip with fill value for unequal lengths
questions = ["What is Python?", "Explain asyncio", "What is LangChain?"]
answers   = ["A language", "Async I/O"]   # shorter list
pairs = list(itertools.zip_longest(questions, answers, fillvalue="[No answer yet]"))
print("\nzip_longest:", pairs)


# ═══════════════════════════════════════════════════════
# PART C: SLICING AND FILTERING
# ═══════════════════════════════════════════════════════

# islice — lazy slice without creating full list (critical for large streams)
def infinite_log_stream() -> Iterator[str]:
    """Simulate infinite stream of logs."""
    i = 0
    while True:
        yield f"LOG_{i:05d}"
        i += 1

# Take first 5 logs from infinite stream — no memory explosion
first_5 = list(itertools.islice(infinite_log_stream(), 5))
print("\nislice:", first_5)

# islice with start, stop, step
items = list(range(100))
every_10th = list(itertools.islice(items, 0, 100, 10))
print("every_10th:", every_10th)

# takewhile / dropwhile
scores = [45, 78, 92, 55, 88, 91, 34]
above_50 = list(itertools.takewhile(lambda x: x > 40, scores))
print("\ntakewhile:", above_50)  # stops at first False

after_threshold = list(itertools.dropwhile(lambda x: x < 90, scores))
print("dropwhile:", after_threshold)  # drops until condition is False

# compress — filter by boolean mask
tools = ["web_search", "calculator", "code_runner", "file_reader"]
available = [True, False, True, True]
active_tools = list(itertools.compress(tools, available))
print("compress:", active_tools)  # ['web_search', 'code_runner', 'file_reader']


# ═══════════════════════════════════════════════════════
# PART D: COMBINATORICS (Interview Favorites)
# ═══════════════════════════════════════════════════════

# product — cartesian product (nested for loops)
models = ["gpt-4", "claude-3"]
temps  = [0.1, 0.5, 0.9]
grid = list(itertools.product(models, temps))
print("\nproduct (model × temperature):")
for model, temp in grid:
    print(f"  {model} @ temp={temp}")

# combinations — choose r items, order doesn't matter
agents = ["researcher", "coder", "reviewer", "tester"]
teams_of_2 = list(itertools.combinations(agents, 2))
print(f"\nPossible 2-agent teams: {len(teams_of_2)}")
print(teams_of_2[:3])

# combinations_with_replacement — can repeat
print("with_replacement:", list(itertools.combinations_with_replacement("ABC", 2)))

# permutations — order matters
tasks = ["fetch", "process", "save"]
orderings = list(itertools.permutations(tasks))
print(f"\nTask orderings: {len(orderings)}")


# ═══════════════════════════════════════════════════════
# PART E: GROUPBY — CRITICAL for data pipelines
# ═══════════════════════════════════════════════════════

# IMPORTANT: groupby only groups CONSECUTIVE equal keys
# You MUST sort first if you want all items of same key together

api_logs = [
    {"endpoint": "/users", "status": 200},
    {"endpoint": "/users", "status": 404},
    {"endpoint": "/orders", "status": 200},
    {"endpoint": "/orders", "status": 500},
    {"endpoint": "/ai", "status": 200},
    {"endpoint": "/ai", "status": 200},
]

# Sort by endpoint first, then group
sorted_logs = sorted(api_logs, key=lambda x: x["endpoint"])
grouped = {
    endpoint: list(group)
    for endpoint, group in itertools.groupby(sorted_logs, key=lambda x: x["endpoint"])
}
print("\ngroupby endpoints:")
for endpoint, logs in grouped.items():
    statuses = [l["status"] for l in logs]
    print(f"  {endpoint}: {statuses}")


# ═══════════════════════════════════════════════════════
# PART F: REAL-WORLD PATTERNS
# ═══════════════════════════════════════════════════════

# PATTERN 1: Batch processing (chunking)
def chunk(iterable: Iterable[T], size: int) -> Iterator[list[T]]:
    """Split an iterable into chunks of given size. Critical for batch API calls."""
    it = iter(iterable)
    while True:
        batch = list(itertools.islice(it, size))
        if not batch:
            break
        yield batch


documents = [f"doc_{i}" for i in range(17)]
print("\nBatch processing (size=5):")
for i, batch in enumerate(chunk(documents, 5)):
    print(f"  Batch {i+1}: {batch}")


# PATTERN 2: Round-robin load balancing
def round_robin_balancer(servers: list[str]) -> Iterator[str]:
    """Infinite round-robin iterator for load balancing."""
    return itertools.cycle(servers)


balancer = round_robin_balancer(["server_1", "server_2", "server_3"])
requests = [f"req_{i}" for i in range(7)]
print("\nRound-robin load balancing:")
for req in requests:
    print(f"  {req} → {next(balancer)}")


# PATTERN 3: Accumulate for running totals
daily_costs = [0.50, 1.20, 0.80, 2.10, 0.90]
running_total = list(itertools.accumulate(daily_costs))
print(f"\nRunning AI costs: {[round(c, 2) for c in running_total]}")

# Max so far (not sum)
running_max = list(itertools.accumulate(daily_costs, max))
print(f"Running max cost: {running_max}")


# ─────────────────────────────────────────────
# INTERVIEW — Key facts to remember
# ─────────────────────────────────────────────
# 1. All itertools return LAZY iterators — wrap in list() to materialize
# 2. groupby requires sorted input
# 3. islice is O(n) not O(1) — it still iterates to position
# 4. product is equivalent to nested for loops
# 5. combinations: n!/(r!(n-r)!) | permutations: n!/(n-r)!
