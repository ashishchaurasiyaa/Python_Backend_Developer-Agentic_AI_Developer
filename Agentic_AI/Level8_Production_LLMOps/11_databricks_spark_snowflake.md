# Databricks / Spark / Snowflake — Big-Data Platforms Behind Enterprise AI

## Quick Concepts
- **Why this matters for an AI/backend engineer**: at enterprise scale, RAG pipelines, embeddings, and ML features don't come from a random Postgres table — they come off a governed big-data platform. JDs from HPE, Warner Bros Discovery, Mastercard, The Hartford, and ZF all pair "build agentic/RAG systems" with "on Databricks" or "on Snowflake." You don't need to be a data engineer — you need to recognize the vocabulary and not freeze when it comes up.
- **Apache Spark** = distributed data-processing engine. Core abstraction: DataFrame (like Pandas, but partitioned across a cluster). Lazy evaluation — transformations (`.filter`, `.select`) build a plan; actions (`.collect`, `.show`, `.write`) trigger execution.
- **Databricks** = a managed platform *on top of* Spark, adding: **Delta Lake** (ACID transactions + versioning on top of cloud storage/Parquet), **Unity Catalog** (governance/access control/lineage), **MLflow** (experiment tracking + model registry), **Workflows/Delta Live Tables** (pipeline orchestration), **Genie** (natural-language-to-SQL assistant over governed data).
- **Snowflake** = a cloud data warehouse with storage/compute fully separated (scale each independently via "virtual warehouses"). **Snowpark** = run Python/Java/Scala code inside Snowflake instead of exporting data out. **Cortex** = Snowflake's built-in LLM layer (`Cortex.Complete`, `Cortex Search` for RAG, `Cortex Analyst` for NL-to-SQL) — this is the piece that shows up directly in agentic JDs.
- **Medallion architecture** (Bronze → Silver → Gold) = the standard layering pattern on both platforms: raw ingested data → cleaned/conformed → business-ready aggregates. Comes up in almost every Databricks-flavored JD (e.g. HPE's).
- **Key insight**: for your target roles (Python backend + agentic AI, not data engineering), the interview bar is usually *"can you have an intelligent conversation about this"*, not *"can you tune a Spark job."* Depth here is optional; fluency is not.

---

## Interview Questions & Answers

### Q1: PySpark — DataFrame API basics?
**Answer:**
```python
# pip install pyspark

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, avg, count

spark = SparkSession.builder.appName("example").getOrCreate()

df = spark.read.csv("orders.csv", header=True, inferSchema=True)

# ===== TRANSFORMATIONS (lazy — build a plan, don't execute yet) =====
filtered = df.filter(col("status") == "delivered")
grouped = filtered.groupBy("region").agg(
    avg("amount").alias("avg_order_value"),
    count("*").alias("order_count"),
)

# ===== ACTIONS (trigger actual execution across the cluster) =====
grouped.show()                 # action
result = grouped.collect()     # action — pulls data to driver, careful with size
grouped.write.parquet("output/regional_summary")  # action

# INTERVIEW: "Why is Spark lazy?" —
# Lazy evaluation lets Spark's Catalyst optimizer see the WHOLE plan before running
# anything, so it can reorder filters, push down predicates, and minimize shuffles —
# instead of executing each line eagerly like Pandas does.

# ===== SQL INTERFACE (same engine, SQL syntax) =====
df.createOrReplaceTempView("orders")
spark.sql("""
    SELECT region, AVG(amount) as avg_value
    FROM orders
    WHERE status = 'delivered'
    GROUP BY region
""").show()
```

---

### Q2: Shuffle aur partitioning — performance ka sabse bada gotcha?
**Answer:**
```python
"""
INTERVIEW: "What's the most common Spark performance problem you'd watch for?"
Answer: shuffles.

Shuffle = data ko cluster ke nodes ke beech redistribute karna — expensive because it
means disk I/O + network transfer. Triggers: groupBy, join, distinct, repartition,
orderBy (anything that needs same key on the same node).

  df.groupBy("customer_id").count()   # shuffle — same customer_id sab ek node pe aana chahiye
  df1.join(df2, "order_id")           # shuffle — dono sides same order_id pe align honi chahiye

Mitigations (interview-worthy):
  1. Broadcast join — chhoti table (fits in memory) ko sab executors pe copy kar do,
     shuffle avoid ho jata hai:
"""
from pyspark.sql.functions import broadcast

large_orders_df.join(broadcast(small_lookup_df), "product_id")

"""
  2. Partition pruning — data ko partition column (jaise date) se already organized
     rakho, taaki query sirf relevant partitions padhe, poora table scan na ho.
  3. repartition() vs coalesce() — repartition = full shuffle (more partitions ya
     better balance chahiye), coalesce = shuffle-free (sirf partitions kam karni hain).
  4. Skew — agar ek key (jaise ek hi customer_id) mein data ka bahut zyada % ho jaaye,
     ek executor overloaded ho jata hai. Salting technique se fix karte hain
     (key ke saath random suffix add karo, phir aggregate karke merge karo).
"""
```

---

### Q3: Databricks — Delta Lake kya problem solve karta hai?
**Answer:**
```python
"""
INTERVIEW: "What does Delta Lake add over plain Parquet files on S3/ADLS?"

Plain Parquet on cloud storage:
  - No transactions — agar write beech mein fail ho jaaye, corrupt/partial data reh jaata hai
  - No schema enforcement — koi bhi column type mismatch silently likh sakta hai
  - No "time travel" — purani state dekhna mushkil hai

Delta Lake adds (on top of the same Parquet files):
  - ACID transactions      — writes atomic hain, partial writes rollback ho jaate hain
  - Schema enforcement     — mismatched writes reject ho jaate hain (schema evolution bhi supported)
  - Time travel            — SELECT * FROM table VERSION AS OF 5 — purani version query kar sakte ho
  - MERGE / UPSERT support — jo plain Parquet mein possible hi nahi tha
"""

# ===== PySpark + Delta example =====
from delta.tables import DeltaTable

# Upsert (merge) — common pattern for incremental loads
target = DeltaTable.forPath(spark, "/mnt/delta/customers")

target.alias("t").merge(
    updates_df.alias("s"),
    "t.customer_id = s.customer_id"
).whenMatchedUpdateAll() \
 .whenNotMatchedInsertAll() \
 .execute()

# Time travel
spark.read.format("delta").option("versionAsOf", 5).load("/mnt/delta/customers")

"""
Medallion architecture (comes up constantly in JDs like HPE's):
  Bronze  → raw data, as-ingested, minimal transformation
  Silver  → cleaned, deduplicated, conformed schema
  Gold    → business-level aggregates, ready for BI / ML / RAG consumption

For an AI engineer: your RAG ingestion pipeline usually reads from Gold (or a
purpose-built "AI-ready" layer) — clean text + metadata, not raw scraped documents.
"""
```

---

### Q4: MLflow — experiment tracking aur model registry?
**Answer:**
```python
import mlflow

# ===== EXPERIMENT TRACKING =====
# INTERVIEW: MLflow = "Git for ML experiments" — tracks params, metrics, artifacts per run

with mlflow.start_run(run_name="rag-embedding-eval"):
    mlflow.log_param("embedding_model", "text-embedding-3-small")
    mlflow.log_param("chunk_size", 512)
    mlflow.log_metric("retrieval_recall_at_5", 0.87)
    mlflow.log_artifact("eval_report.json")

# ===== MODEL REGISTRY =====
# Central place to version models, promote through stages (Staging → Production)
mlflow.register_model(
    model_uri="runs:/abc123/model",
    name="customer-intent-classifier",
)

"""
INTERVIEW angle for AI/agentic roles specifically:
  MLflow isn't just for classical ML — Databricks JDs increasingly use it for
  LLMOps too: logging prompt versions, RAG eval metrics (recall, faithfulness),
  and agent run traces, same idea as LangSmith/Langfuse but inside the Databricks
  ecosystem. If asked "how would you track RAG experiment quality on Databricks?" —
  answer: log each config (chunk size, embedding model, reranker) as an MLflow run,
  compare metrics across runs in the MLflow UI.
"""
```

---

### Q5: Snowflake — architecture aur Snowpark?
**Answer:**
```python
"""
INTERVIEW: "How is Snowflake's architecture different from a traditional data warehouse?"

Traditional (on-prem) warehouse: storage + compute tightly coupled — scale one,
you pay for both.

Snowflake: storage and compute are SEPARATE.
  - Storage: single copy of data, cheap, in Snowflake's managed cloud storage
  - Compute: "virtual warehouses" — independent clusters you spin up/resize/pause,
    each billed separately. Multiple teams can query the SAME data with their OWN
    warehouse, no resource contention.

Snowpark = run Python (or Java/Scala) code INSIDE Snowflake's compute, instead of
pulling data out to a separate Spark/pandas environment:
"""

# pip install snowflake-snowpark-python
from snowflake.snowpark import Session
from snowflake.snowpark.functions import col

session = Session.builder.configs({
    "account": "...", "user": "...", "password": "...",
    "warehouse": "COMPUTE_WH", "database": "SALES_DB", "schema": "PUBLIC",
}).create()

df = session.table("orders").filter(col("status") == "delivered")
df.group_by("region").agg({"amount": "avg"}).show()

# INTERVIEW: why does this matter vs. just using pandas/Spark?
# Data never leaves Snowflake's governed environment — important for compliance-heavy
# JDs (healthcare, finance) that showed up repeatedly in your JD sample.
```

---

### Q6: Snowflake Cortex — yeh directly agentic AI JDs mein kyun aata hai?
**Answer:**
```sql
-- INTERVIEW: Cortex = Snowflake's built-in LLM layer — SQL se hi LLM call kar sakte ho,
-- data ko warehouse se bahar nikale bina. Warner Bros Discovery JD mein explicitly
-- named: "Cortex Analyst / Copilot", "Cortex Search for RAG", "Cortex Fine-Tuning".

-- Cortex.Complete — direct LLM call from SQL
SELECT SNOWFLAKE.CORTEX.COMPLETE(
    'llama3.1-70b',
    'Summarize this customer feedback: ' || feedback_text
) AS summary
FROM customer_feedback;

-- Cortex Search — managed RAG retrieval, no separate vector DB needed
-- (you define a "search service" over a table; querying it does embedding +
--  retrieval internally, governed by the same Snowflake access controls)

-- Cortex Analyst — natural language to SQL, for self-serve business queries
```

```
INTERVIEW ANGLE — why enterprises want this over LangChain + external vector DB:
  1. Data never leaves the governed warehouse (compliance: HIPAA/SOC2/etc.)
  2. One access-control model (Snowflake roles) instead of managing a separate
     vector DB's auth
  3. Less infra to run — no separate embedding pipeline / vector store to operate

Trade-off (worth naming in an interview): less flexibility than a custom
LangChain/LangGraph + Pinecone/pgvector stack — you're inside Snowflake's opinionated
tooling. Enterprises with existing Snowflake investment (Warner Bros Discovery,
Mastercard) pick this to avoid duplicating a data platform; startups building
AI-first products typically don't.
```

---

### Q7: Yeh sab tumhare interview ke liye kitna zaroori hai?
**Answer:**
```
Reality check (per JD_ANALYSIS_TOP50.md):
  - 5 of 47 JDs named Databricks/Spark/Snowflake explicitly, and only 1 (Warner Bros
    Discovery, Staff MLE) made it central to the role.
  - Your target roles (per ROADMAP.md / INTERVIEW_PREP_COMPANIES.md) are Python
    Backend + Agentic AI at 3-5 yrs — not Data Engineer / Staff MLE.

What's worth knowing (this file's ceiling):
  - Vocabulary fluency: Delta Lake, Medallion architecture, Unity Catalog, Snowpark,
    Cortex — so a mention in a JD or interview doesn't blindside you
  - The ONE thing that connects to your actual RAG/agentic work: enterprise AI
    pipelines pull governed data from Bronze/Silver/Gold (Databricks) or query via
    Cortex (Snowflake) rather than an ad-hoc script — name-drop this if asked
    "how would this look different at enterprise scale?"

What's NOT worth deep hands-on time right now:
  - Writing/tuning actual Spark jobs, Databricks cluster config, Snowflake
    performance tuning — that's a distinct specialization, not a blocker for the
    roles you're targeting.
```

---

## Core Summary

```
Big-Data Platform Landscape:

  Apache Spark (engine)
    └── Databricks (managed platform on Spark)
          ├── Delta Lake       → ACID + time travel + schema enforcement on Parquet
          ├── Unity Catalog    → governance, access control, lineage
          ├── MLflow           → experiment tracking + model registry (+ LLMOps use)
          ├── Workflows/DLT    → pipeline orchestration
          └── Genie            → NL-to-SQL / data assistant

  Snowflake (separate lineage — cloud data warehouse)
    ├── Storage/Compute separation → virtual warehouses, independent scaling
    ├── Snowpark                   → Python/Java/Scala inside Snowflake
    └── Cortex                     → built-in LLM layer (Complete, Search=RAG, Analyst=NL2SQL)

Where this connects to your Agentic AI prep:
  Same RAG concepts you already know (Level5_RAG_Vector_Databases) — these platforms
  are just where enterprise-scale data governance happens before/instead of a
  standalone vector DB. Don't relearn RAG; learn the vocabulary shift.
```
