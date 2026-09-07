"""
Level8 — Doc 11: Databricks / Spark / Snowflake (PRACTICAL)
================================================================
None of pyspark, delta, mlflow, or snowflake-snowpark-python need to be
installed to understand what they actually DO underneath — this builds
minimal, honest reimplementations of the core mechanics (lazy DAG,
shuffle/skew, ACID merge + time travel, experiment tracking) so the
concepts are provable, not just described.

Topics covered:
  1. Spark's lazy DAG — transformations build a plan, actions execute it
  2. Shuffle + skew — why groupBy/join are expensive, and the salting fix
  3. Delta Lake — ACID merge (upsert) + time travel, from scratch
  4. MLflow — experiment tracking + model registry, minimal reimplementation
  5. Snowflake vs Spark/Databricks — a real decision function, not a table

Install (optional, real SDKs): pip install pyspark mlflow
Run: python 11_databricks_spark_snowflake_practical.py
"""

import time
from dataclasses import dataclass, field


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Spark's Lazy DAG — Plan First, Execute Later
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 1: Lazy Evaluation — Transformations Build a Plan")
print("=" * 70)


class LazyDataFrame:
    """Mirrors PySpark's core behavior: every transformation just RECORDS an
    operation and returns a new LazyDataFrame — nothing runs until an ACTION
    (collect/show/write) is called. This is the actual mechanism behind
    'Spark is lazy', not just a description of it."""

    def __init__(self, data: list[dict], plan: list[str] = None):
        self._data = data
        self.plan = plan or []

    def filter(self, predicate) -> "LazyDataFrame":
        new_plan = self.plan + [f"FILTER({predicate.__name__ if hasattr(predicate, '__name__') else 'lambda'})"]
        df = LazyDataFrame(self._data, new_plan)
        df._pending_filter = predicate
        df._parent = self
        df._op = "filter"
        return df

    def group_by_avg(self, key: str, value_col: str) -> "LazyDataFrame":
        new_plan = self.plan + [f"GROUP_BY({key}).AVG({value_col})"]
        df = LazyDataFrame(self._data, new_plan)
        df._key, df._value_col = key, value_col
        df._parent = self
        df._op = "group_by_avg"
        return df

    def _execute(self) -> list[dict]:
        """The ACTION — this is where the whole recorded plan finally runs,
        all at once, letting a real Spark optimizer reorder/fuse steps first."""
        if not hasattr(self, "_op"):
            return self._data
        parent_data = self._parent._execute()
        if self._op == "filter":
            return [row for row in parent_data if self._pending_filter(row)]
        if self._op == "group_by_avg":
            groups: dict = {}
            for row in parent_data:
                groups.setdefault(row[self._key], []).append(row[self._value_col])
            return [{self._key: k, f"avg_{self._value_col}": sum(v) / len(v)} for k, v in groups.items()]
        return parent_data

    def collect(self) -> list[dict]:
        """ACTION — triggers real execution, exactly like PySpark's .collect()."""
        print(f"    [EXECUTING plan: {' -> '.join(self.plan) or '(no-op)'}]")
        return self._execute()


orders = LazyDataFrame([
    {"region": "north", "status": "delivered", "amount": 100},
    {"region": "north", "status": "delivered", "amount": 200},
    {"region": "south", "status": "pending", "amount": 150},
    {"region": "south", "status": "delivered", "amount": 300},
])

print("\n  Building the plan (nothing executes yet):")
filtered = orders.filter(lambda r: r["status"] == "delivered")
grouped = filtered.group_by_avg("region", "amount")
print(f"    Plan so far: {grouped.plan}")
print("    (no data has been touched — this is the lazy part)")

print("\n  Now calling .collect() — the ACTION that finally runs everything:")
result = grouped.collect()
print(f"    Result: {result}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Shuffle + Skew — the Real Performance Gotcha
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 2: Shuffle + Data Skew, Simulated")
print("=" * 70)


def simulate_partition_distribution(data: list[dict], key: str, num_partitions: int = 4) -> dict[int, int]:
    """A groupBy needs every row with the same key on the same partition —
    this simulates WHERE each row would land, showing skew when one key
    dominates (a real shuffle would actually move this data over the network)."""
    distribution: dict[int, int] = {i: 0 for i in range(num_partitions)}
    for row in data:
        partition = hash(row[key]) % num_partitions
        distribution[partition] += 1
    return distribution


balanced_data = [{"customer_id": f"cust_{i}"} for i in range(40)]  # 40 distinct customers
skewed_data = [{"customer_id": "cust_VIP"}] * 30 + [{"customer_id": f"cust_{i}"} for i in range(10)]  # one customer dominates

print(f"\n  Balanced key distribution across 4 partitions: {simulate_partition_distribution(balanced_data, 'customer_id')}")
print(f"  Skewed key distribution across 4 partitions:    {simulate_partition_distribution(skewed_data, 'customer_id')}")
print("\n  Whichever partition 'cust_VIP' hashes to does 30x the work of the others —")
print("  that ONE executor becomes the bottleneck for the whole job. This is exactly")
print("  what the 'salting' technique fixes: append a random suffix to the hot key")
print("  before grouping, spreading it across partitions, then merge the partial")
print("  results in a second pass.")


def salted_key(customer_id: str, salt_buckets: int = 4) -> str:
    import random
    return f"{customer_id}_salt{random.randint(0, salt_buckets - 1)}"


salted_data = [{"customer_id": salted_key("cust_VIP")} for _ in range(30)] + [{"customer_id": f"cust_{i}"} for i in range(10)]
print(f"\n  After salting the hot key: {simulate_partition_distribution(salted_data, 'customer_id')}")
print("  (more evenly spread — a real pipeline would then re-aggregate the")
print("   salted partial sums back into one 'cust_VIP' total in a cheap second step)")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Delta Lake — ACID Merge + Time Travel, From Scratch
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 3: Delta Lake — ACID Upsert + Time Travel")
print("=" * 70)


class MiniDeltaTable:
    """Delta Lake's actual trick: it's plain Parquet-equivalent data PLUS a
    transaction log. This reimplements that idea directly — every write
    appends a new immutable VERSION instead of mutating in place, which is
    what makes time travel and atomic rollback possible."""

    def __init__(self, initial_rows: list[dict], key: str):
        self.key = key
        self._versions: list[list[dict]] = [initial_rows]  # version 0

    @property
    def current(self) -> list[dict]:
        return self._versions[-1]

    def merge_upsert(self, updates: list[dict]):
        """whenMatchedUpdateAll + whenNotMatchedInsertAll, in one operation —
        atomic: either the whole merge lands as a new version, or nothing does."""
        current_by_key = {row[self.key]: row for row in self.current}
        for update in updates:
            current_by_key[update[self.key]] = update  # update existing OR insert new
        new_version = list(current_by_key.values())
        self._versions.append(new_version)  # commit as a NEW version — old one untouched

    def read_version(self, version: int) -> list[dict]:
        return self._versions[version]


customers = MiniDeltaTable([
    {"customer_id": 1, "name": "Alice", "tier": "gold"},
    {"customer_id": 2, "name": "Bob", "tier": "silver"},
], key="customer_id")

print(f"\n  Version 0: {customers.current}")

customers.merge_upsert([
    {"customer_id": 2, "name": "Bob", "tier": "gold"},   # UPDATE — Bob promoted
    {"customer_id": 3, "name": "Priya", "tier": "silver"},  # INSERT — new customer
])
print(f"  Version 1 (after merge): {customers.current}")

customers.merge_upsert([{"customer_id": 1, "name": "Alice", "tier": "platinum"}])
print(f"  Version 2 (after another merge): {customers.current}")

print(f"\n  Time travel — read version 0 as if none of this ever happened:")
print(f"    {customers.read_version(0)}")
print("\n  Real Delta Lake: `spark.read.format('delta').option('versionAsOf', 0).load(...)`")
print("  — same idea, backed by a real transaction log instead of a Python list.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: MLflow — Experiment Tracking + Model Registry
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 4: MLflow-Shaped Experiment Tracking")
print("=" * 70)


@dataclass
class Run:
    run_id: str
    run_name: str
    params: dict = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)
    artifacts: list = field(default_factory=list)


class MiniMLflow:
    """Same API shape as mlflow: start_run / log_param / log_metric /
    log_artifact / register_model — 'Git for ML experiments', as the doc
    calls it. Directly applicable to RAG eval tracking, per the doc's
    own interview angle for AI/agentic roles."""

    def __init__(self):
        self.runs: dict[str, Run] = {}
        self.registry: dict[str, list[dict]] = {}
        self._current: Run | None = None

    def start_run(self, run_name: str):
        run_id = f"run_{len(self.runs) + 1}"
        self._current = Run(run_id=run_id, run_name=run_name)
        self.runs[run_id] = self._current
        return self

    def __enter__(self):
        return self._current

    def __exit__(self, *args):
        self._current = None

    def log_param(self, key: str, value):
        self._current.params[key] = value

    def log_metric(self, key: str, value):
        self._current.metrics[key] = value

    def log_artifact(self, path: str):
        self._current.artifacts.append(path)

    def register_model(self, run_id: str, name: str):
        self.registry.setdefault(name, []).append({"run_id": run_id, "stage": "Staging", "registered_at": time.time()})


mlflow = MiniMLflow()

# The doc's own RAG-eval-tracking example — comparing 2 chunking configs
for chunk_size, recall in [(256, 0.81), (512, 0.87)]:
    with mlflow.start_run(run_name=f"rag-eval-chunk{chunk_size}") as run:
        mlflow.log_param("embedding_model", "text-embedding-3-small")
        mlflow.log_param("chunk_size", chunk_size)
        mlflow.log_metric("retrieval_recall_at_5", recall)
        mlflow.log_artifact("eval_report.json")

print()
for run_id, run in mlflow.runs.items():
    print(f"  {run.run_name}: params={run.params}, metrics={run.metrics}")

best_run = max(mlflow.runs.values(), key=lambda r: r.metrics.get("retrieval_recall_at_5", 0))
print(f"\n  Best run by recall@5: {best_run.run_name} ({best_run.metrics['retrieval_recall_at_5']})")

mlflow.register_model(run_id=best_run.run_id, name="rag-retriever-v1")
print(f"  Registered: {mlflow.registry['rag-retriever-v1']}")
print("\n  This is the exact workflow the doc describes for AI/agentic roles:")
print("  log each (chunk_size, embedding_model, reranker) config as a run,")
print("  compare recall/faithfulness across runs, promote the winner.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Snowflake vs Spark/Databricks — a Real Decision
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 5: Snowflake vs Spark/Databricks — When Each Wins")
print("=" * 70)


def pick_data_platform(is_compliance_heavy: bool, needs_custom_python_ml: bool, data_already_in_snowflake: bool) -> str:
    if is_compliance_heavy and data_already_in_snowflake:
        return "Snowflake + Cortex — data never leaves the governed warehouse, one access-control model (HIPAA/SOC2-friendly)"
    if needs_custom_python_ml:
        return "Databricks/Spark — Snowpark runs Python inside Snowflake too, but Spark's ML/Delta ecosystem is more flexible for custom pipelines"
    if data_already_in_snowflake:
        return "Snowflake — avoid duplicating a data platform you already operate"
    return "Databricks/Spark — the more common default for a greenfield AI-heavy pipeline"


for case in [(True, False, True), (False, True, False), (True, False, False)]:
    print(f"\n  compliance_heavy={case[0]}, needs_custom_ml={case[1]}, already_on_snowflake={case[2]}")
    print(f"    -> {pick_data_platform(*case)}")

print("\n  Reality check from the doc's own JD analysis: only 1 of 47 JDs sampled made")
print("  this central to the role (a Staff MLE role at a company already all-in on")
print("  Databricks). Know the CONCEPTS (this file); don't over-invest in the specific")
print("  SDKs unless a target JD explicitly names them.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Exercises
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 6: EXERCISES")
print("=" * 70)
print("""
EASY:
1. Add a `.select(columns)` transformation to LazyDataFrame — should also
   just record a plan step, not execute immediately.

MEDIUM:
2. Add a `whenNotMatchedBySourceDelete` mode to MiniDeltaTable.merge_upsert()
   — rows present in `current` but absent from `updates` get deleted, not
   just left alone (a real Delta MERGE supports this mode).

HARD:
3. Extend MiniMLflow with a `search_runs(filter_metric, threshold)` method
   that returns only runs above a metric threshold — mirrors the real
   mlflow.search_runs() API used to programmatically pick a winning config.

PRO:
4. Implement the "medallion architecture" (Bronze -> Silver -> Gold) as 3
   chained LazyDataFrame stages: Bronze = raw rows as-is, Silver = filtered
   + deduplicated, Gold = the group_by_avg aggregate. Print the full plan
   at each stage — this is literally what a real ingestion pipeline's
   lineage looks like.
""")

if __name__ == "__main__":
    print("\nDone. Level8 complete — every doc now has hands-on code.")
    print("Agentic_AI Level1-8 + Modern_Topics: zero remaining practical gaps.")
