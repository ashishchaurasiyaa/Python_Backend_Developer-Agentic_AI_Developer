# Design Distributed Logging System

---

## 1. Requirements

### Functional
- Collect logs from 1000s of services across many regions.
- Centralized search across all logs (Kibana-like UI).
- Real-time tail (live log streaming).
- Filter by service, host, severity, timestamp, free text.
- Structured log support (JSON).
- Retention: hot 7 days, warm 30 days, cold 1 year.
- Alerting on log patterns (e.g., "5 ERRORs in 1 min").
- Trace correlation (link logs by trace_id).
- Export/download for offline analysis.

### Non-Functional
- 10M events/sec ingest at peak.
- 1 PB/day of logs.
- Search p99 < 5s for last 7 days, < 30s for older.
- No log loss after producer ack.
- Multi-tenant (workspaces/teams).
- 99.9% availability.

---

## 2. Scale Estimation

| Metric | Calc | Number |
|---|---|---|
| Events/sec | 10M peak | |
| Daily volume | 10M × 86400 × 500 bytes | ~430 TB/day raw |
| With compression (5x) | | ~85 TB/day stored |
| Hot tier (7d) | 85 × 7 | 600 TB |
| Warm tier (30d) | 85 × 30 | 2.5 PB |
| Cold tier (1yr) | 85 × 365 | 30 PB |
| Search queries/sec | 1K |
| Active dashboards | 10K |

---

## 3. High-Level Architecture

```
   ┌──────────────────────────┐
   │ Apps (1000s of services) │
   └────────┬─────────────────┘
            │
   ┌────────▼─────────┐
   │  Log Agent       │ (Fluent Bit / Vector — on each host)
   │  (parse + batch) │
   └────────┬─────────┘
            │
   ┌────────▼──────────────────┐
   │     Ingest Pipeline        │
   │  (Kafka / Kinesis Firehose)│
   └────────┬──────────────────┘
            │
   ┌────────┼─────────┬──────────┬───────────┐
   │        │         │          │           │
┌──▼──┐  ┌──▼───┐  ┌──▼─────┐ ┌──▼─────┐  ┌──▼──────┐
│Parse│  │Index │  │Archival│ │Alert    │  │Trace     │
│Norm.│  │Worker│  │Worker  │ │Worker   │  │Correlator│
└──┬──┘  └──┬───┘  └────┬───┘ └─────────┘  └──────────┘
   │        │            │
   │   ┌────▼────┐  ┌────▼────────┐
   │   │ Hot ES /│  │ S3 (Parquet)│
   │   │ Loki    │  │ Cold        │
   │   └─────────┘  └─────────────┘
   │
   └─→ Stream to Kibana / Grafana / Custom UI
```

---

## 4. Log Agent (Edge Collection)

Runs on every host as DaemonSet in K8s, or system service on bare metal.

### Responsibilities
- Tail log files / stdout streams.
- Parse (JSON, syslog, custom regex).
- Add metadata (hostname, k8s pod, region).
- Batch + compress.
- Send to ingest pipeline.
- Handle backpressure (local buffer if upstream slow).

### Sample: Fluent Bit config

```ini
[INPUT]
    Name              tail
    Path              /var/log/containers/*.log
    Parser            docker
    Tag               kube.*
    Buffer_Chunk_Size 1MB
    Buffer_Max_Size   100MB

[FILTER]
    Name              kubernetes
    Match             kube.*
    K8S-Logging.Parser On

[OUTPUT]
    Name              kafka
    Match             *
    Brokers           kafka.internal:9092
    Topics            logs.${KUBE_NAMESPACE}
    Compression       gzip
```

### Backpressure handling
- Local disk buffer up to N GB.
- Drop oldest if buffer full → loss visible in metrics.
- Or apply sampling under pressure (drop INFO, keep ERROR).

---

## 5. Ingest Pipeline (Kafka)

Kafka chosen for:
- Replay-ability (re-index if pipeline bug).
- Decoupling producers from consumers.
- High throughput (millions of msg/sec/topic).
- Partitioning by service/host.

### Topic strategy
- `logs.{tenant}` — one topic per tenant (multi-tenancy isolation).
- Partition by `service_name` → ordering within service preserved.
- Replication factor = 3.
- Retention: 7 days (acts as buffer + short-term archive).

### Sample message format
```json
{
  "ts": "2024-01-01T12:00:00.123Z",
  "level": "ERROR",
  "service": "payments-api",
  "host": "pod-abc123",
  "region": "us-east-1",
  "trace_id": "abc...",
  "span_id": "def...",
  "msg": "Payment failed",
  "error_code": "INSUFFICIENT_FUNDS",
  "amount": 100,
  "user_id": 42,
  "raw": "ERROR Payment failed for user 42 amount 100"
}
```

---

## 6. Parse + Normalize Worker

Consume Kafka, transform to canonical schema, write to next stage.

```python
async def parse_worker(consumer, producer):
    async for batch in consumer:
        normalized = []
        for msg in batch:
            try:
                doc = json.loads(msg.value)
            except json.JSONDecodeError:
                doc = parse_unstructured(msg.value)

            # Add derived fields
            doc["@timestamp"] = parse_ts(doc.get("ts"))
            doc["level_num"] = LEVEL_MAP[doc.get("level", "INFO")]
            doc["service"] = msg.headers.get("service") or doc.get("service")

            normalized.append(doc)
        await producer.send_batch("logs.parsed", normalized)
```

---

## 7. Hot Storage: Elasticsearch / Loki

### Option A: Elasticsearch (heavy indexing, complex queries)
- Indexes every field for fast filter + search.
- Expensive: ~3x raw data size.
- Time-based indices: `logs-{tenant}-{YYYY.MM.DD}`.
- ILM (Index Lifecycle Management): hot → warm → delete.

```json
PUT _ilm/policy/logs-policy
{
  "policy": {
    "phases": {
      "hot":  { "actions": { "rollover": { "max_size": "50GB", "max_age": "1d" } } },
      "warm": { "min_age": "7d",  "actions": { "shrink": { "number_of_shards": 1 }, "forcemerge": {} } },
      "cold": { "min_age": "30d", "actions": { "freeze": {} } },
      "delete": { "min_age": "365d", "actions": { "delete": {} } }
    }
  }
}
```

### Option B: Loki (Grafana's, cheaper)
- Indexes only labels (service, host, level) — not full text.
- Stores raw chunks compressed in S3.
- Search = label filter + grep over raw chunks.
- Much cheaper, but full-text search is slower.

**Pick Loki** for cost-sensitive workloads. **Pick ES** when complex search is critical.

### Sharding strategy (ES)
- One index per day per tenant per region.
- Shard count: tune for ~30GB per shard.
- For 100 TB / day / tenant → ~3000 shards/day → manageable.

---

## 8. Cold Storage (S3 + Parquet)

After 30 days, move to S3 in columnar format.

### Why Parquet
- Column-oriented (filter without reading all data).
- 10x better compression than JSON.
- Queryable via Athena/BigQuery/Trino.

### Pipeline
```
Daily batch job:
  Read ES indices > 30 days old
  Convert to Parquet (partitioned by date + service)
  Upload to S3
  Delete from ES
```

```python
import pandas as pd
df = pd.DataFrame(records)
df.to_parquet(
    f"s3://logs-cold/year=2024/month=01/day=15/service=payments-api/data.parquet",
    compression="zstd"
)
```

### Query cold data
Use Athena / Trino / Presto with SQL:
```sql
SELECT * FROM logs_cold
WHERE year = 2024 AND service = 'payments-api'
  AND level = 'ERROR' AND ts > '2024-01-15T00:00:00Z'
LIMIT 100;
```

Slower (~10-60s) but cheap.

---

## 9. Search UI

### Architecture
```
User (Kibana/Custom UI) → Search API → Decide tier (hot/cold) → ES or Athena
                                ↓
                          Aggregate + return
```

### Query routing
```python
async def search(query, time_range):
    if time_range.duration > 30_days:
        # Use cold path
        return await athena_search(query, time_range)
    else:
        return await es_search(query, time_range)
```

### Common queries
- "All ERROR logs for service X in last 1h"
- "Count of 5xx errors per minute"
- "Logs containing user_id=42"
- "All logs with trace_id=abc123"

---

## 10. Real-Time Tail / Live Logs

### Implementation
- Consumer reads from Kafka topic (newest offset).
- WS pushes filtered events to subscribed clients.
- Backpressure: rate limit per client (1000 msg/sec).

```python
@app.websocket("/ws/tail/{service}")
async def tail(ws: WebSocket, service: str, level: str = "INFO"):
    consumer = KafkaConsumer("logs.parsed", auto_offset_reset="latest")
    consumer.subscribe([f"logs.parsed.{service}"])

    try:
        for msg in consumer:
            log = json.loads(msg.value)
            if log["level"] >= level:
                await ws.send_json(log)
    finally:
        consumer.close()
```

---

## 11. Alerting on Log Patterns

### Rule definition
```yaml
- name: high_error_rate
  query: 'service:payments-api AND level:ERROR'
  window: 1m
  threshold: 5
  notify: ["slack:#oncall", "pagerduty:payments"]
```

### Evaluation
Continuous worker:
- Every 30s, run query for last 1m window.
- If hit threshold, send alert (deduped within cool-off period).

### Anomaly detection
ML-based: train on historical baseline, alert on > 3 σ deviation.

---

## 12. Trace Correlation

Logs include `trace_id` from distributed tracer (OTel).

### Query path
- User clicks log → "view trace".
- Lookup trace in Jaeger/Tempo using trace_id.
- Tempo also pulls related logs (logs-to-traces).

```python
# Standard OTel log attribute
log = {
    "trace_id": "abc",
    "span_id": "def",
    ...
}
```

---

## 13. Sampling

At 10M events/sec, even storing 1% is 100K events/sec.

### Sampling strategies
- **Head-based**: decide at log time (random N%).
- **Tail-based**: keep all error logs, sample INFO.
- **Adaptive**: more samples during high traffic, fewer during low.

### Sample at agent level
```python
def should_sample(log, traffic_rate):
    if log.level >= "WARN": return True
    if traffic_rate > THRESHOLD:
        return random.random() < 0.01
    return True
```

---

## 14. Multi-Tenancy

### Tenant isolation
- Separate Kafka topic per tenant (or partition key).
- Separate ES index per tenant.
- IAM at search API: query injected with tenant filter.
- S3 prefix per tenant.

### Tenant quotas
- Bytes/day limit.
- Query rate limit per tenant.
- Storage quota → alerts, then throttling.

---

## 15. Compression

- Agent: gzip on send.
- Kafka: lz4 compression on topic.
- ES: ZSTD or LZ4.
- S3 Parquet: ZSTD or Snappy.

Typical: 5-10x compression ratio for structured logs, 3-5x for free text.

---

## 16. Schema Evolution

Logs are heterogeneous. Schema not enforced at ingest, but normalized.

### Strategy
- Required fields: ts, service, level (drop log if missing — or assign defaults).
- All other fields: optional, dynamic mapping in ES.
- Use ECS (Elastic Common Schema) for cross-service consistency:
```
@timestamp, log.level, log.logger, service.name, host.name, error.message, error.stack_trace
```

---

## 17. Operational Concerns

### Backfill
Old logs from S3 can be re-indexed into ES on demand for forensic investigation.

### Reprocessing
Bug in parser → re-process Kafka topic with fixed parser. Kafka retention covers 7 days.

### Disaster recovery
- ES snapshots to S3 daily.
- Multi-region replication for tenants who need it.
- Restore time: 6-12h for full re-index.

---

## 18. APIs

```
POST /ingest                       # agent endpoint
GET  /search?q=...&from=...&to=... # ad-hoc query
GET  /tail?service=...&level=...   # WebSocket
POST /alerts                       # rule creation
GET  /alerts/triggered            # history
POST /export?range=...             # async export to S3
```

---

## 19. Trade-offs

| Decision | Trade-off |
|---|---|
| Kafka in middle | Adds latency, gives durability + replay |
| ES for hot | Fast search, expensive storage |
| Loki for cheap | Limited search, much cheaper |
| Parquet cold | Cheap, slow ad-hoc query |
| Agent-level sampling | Less data, harder to investigate edge cases |
| Per-tenant indices | Isolation, more shards to manage |

---

## 20. Follow-up Questions

- **"Difference between logging, metrics, tracing?"** → Logs: detailed events. Metrics: aggregated numbers. Traces: causal chain of operations across services. Three pillars of observability.
- **"How to deduplicate logs?"** → Hash log content; reject duplicates within 1m window per source. Or accept and dedup at query time.
- **"What about secret leaks in logs?"** → Scrub at agent: regex-based PII/secret detection, mask before send.
- **"How to handle a flooded log topic?"** → Backpressure → agent buffer fills → agent drops oldest → metric/alert fires. Operator can throttle / sample upstream.
- **"GDPR-comply with logs?"** → User-id field tagged. On deletion request, sweep all logs in retention window, delete or anonymize.
- **"Loki vs ES vs Splunk vs Datadog?"** → Loki cheapest, ES open-source workhorse, Splunk enterprise, Datadog managed (most expensive but best UX).
