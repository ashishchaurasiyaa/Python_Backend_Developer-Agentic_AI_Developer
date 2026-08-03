# Logging — ELK Stack, Loki, Fluentd/Fluent Bit
**DevOps Track · Phase 12: Logging**

> Complementary to Backend_Developer/01_Year3-4_Mid/04_DevOps/ (app-deployment angle) — this covers the fuller tool/architecture picture.

## Quick Concepts

- **ELK Stack** = Elasticsearch (storage + search) + Logstash (ingest/transform) + Kibana (visualize) — "Elastic Stack" once Beats are included
- **Inverted Index** = Elasticsearch's core data structure — maps each word/term to the list of documents containing it, making full-text search fast
- **Index / Document** = an Elasticsearch "index" is roughly a database/table; a "document" is roughly a row (a JSON object, e.g., one log line)
- **Logstash pipeline** = input → filter → output, config-driven log transformation
- **Grok** = Logstash's pattern-matching filter language for parsing unstructured text logs into structured fields
- **Filebeat** = a lightweight agent that tails log files and forwards them (to Logstash or directly to Elasticsearch) — handles rotation correctly, unlike a naive `tail -f`
- **ILM (Index Lifecycle Management)** = an Elasticsearch policy automating hot→warm→cold→delete transitions for aging indices
- **Loki** = Grafana's log aggregation system — indexes only labels (metadata), not full log text, making it far cheaper to run than Elasticsearch
- **LogQL** = Loki's query language, deliberately PromQL-like
- **Fluentd** = unified logging layer, collects/routes logs from many sources to many destinations via plugins
- **Fluent Bit** = Fluentd's lightweight C rewrite — smaller footprint, designed for edge/sidecar/DaemonSet deployment

---

## Why This Matters

```
"We use ELK" and "we use Loki" imply very different cost and
operational profiles. An interviewer asking "how would you design
logging for a 200-pod Kubernetes cluster" wants you to reason about:
   - full-text search need vs cost (ELK is expensive at scale)
   - label cardinality (Loki's Achilles heel if you get it wrong)
   - what actually ships logs off each pod (Fluent Bit as DaemonSet)
   - how a raw nginx log line becomes a structured, searchable field
     (grok, or Loki's parser stages)

This file builds that full mental model, not just "kubectl logs | grep".
```

---

## ELK Stack

### Elasticsearch — Inverted Index & Documents

Elasticsearch is a distributed document store built for search. Instead of a B-tree index per column (like a relational DB), it builds an **inverted index**: for every distinct term seen across all documents, it stores the list of document IDs containing that term.

```
Document 1: "ERROR database connection timeout"
Document 2: "INFO user login successful"
Document 3: "ERROR timeout on payment gateway"

Inverted index (simplified):
  "error"     -> [doc1, doc3]
  "timeout"   -> [doc1, doc3]
  "database"  -> [doc1]
  "login"     -> [doc2]
  "payment"   -> [doc3]

Query "error timeout" -> intersect [doc1,doc3] ∩ [doc1,doc3] -> doc1, doc3
```

This is why Elasticsearch full-text search is fast, and also why it's storage-heavy — the index itself, plus stored fields, plus replicas, can be several times the size of the raw log data.

**Index basics:**
```
Index    ≈ database/table   (e.g., logs-nginx-2026.07.25 — often date-suffixed)
Document ≈ row              (one JSON object — typically one log line/event)
Field    ≈ column           (message, timestamp, level, host, response_code...)
Shard    = a horizontal partition of an index, distributed across nodes
Replica  = a copy of a shard, for redundancy + read scaling
```

Daily/weekly index rotation (`logs-2026.07.25`) plus an **Index Lifecycle Management (ILM)** policy (hot → warm → cold → delete) is the standard way to keep Elasticsearch from growing unbounded — old indices get moved to cheaper storage tiers and eventually deleted.

```json
// ILM policy — PUT _ilm/policy/logs-policy
{
  "policy": {
    "phases": {
      "hot": {
        "min_age": "0ms",
        "actions": { "rollover": { "max_age": "1d", "max_size": "50gb" } }
      },
      "warm": {
        "min_age": "7d",
        "actions": { "shrink": { "number_of_shards": 1 }, "forcemerge": { "max_num_segments": 1 } }
      },
      "cold": {
        "min_age": "30d",
        "actions": { "searchable_snapshot": { "snapshot_repository": "s3-backup" } }
      },
      "delete": {
        "min_age": "90d",
        "actions": { "delete": {} }
      }
    }
  }
}
```

```
hot   → fast, expensive storage, actively being written to (today's logs)
warm  → shrink/forcemerge REDUCES the index's resource footprint —
         fewer shards, merged segments — for data still occasionally
         queried but no longer being written to
cold  → moved to cheap object storage (searchable_snapshot — S3-backed,
         still queryable, just slower) — same cost-tiering idea as
         S3 lifecycle policies (Phase 7) or the S3 log-lifecycle
         example already in this track, applied to Elasticsearch's own data
delete → gone — the retention boundary decided by compliance/cost, not
          an afterthought discovered during a disk-full incident
```

### Logstash — Input / Filter / Output Pipeline

Logstash reads raw logs, transforms them into structured events, and writes them somewhere (usually Elasticsearch).

```ruby
# logstash.conf
input {
  file {
    path => "/var/log/nginx/access.log"
    start_position => "beginning"
  }
}

filter {
  grok {
    match => {
      "message" => '%{IPORHOST:client_ip} - %{USER:ident} \[%{HTTPDATE:timestamp}\] "%{WORD:http_method} %{URIPATHPARAM:request} HTTP/%{NUMBER:http_version}" %{NUMBER:response_code} %{NUMBER:bytes_sent} "%{DATA:referrer}" "%{DATA:user_agent}"'
    }
  }

  date {
    match => ["timestamp", "dd/MMM/yyyy:HH:mm:ss Z"]
    target => "@timestamp"
  }

  mutate {
    convert => { "response_code" => "integer" }
    convert => { "bytes_sent" => "integer" }
    remove_field => ["timestamp", "message"]
  }

  geoip {
    source => "client_ip"
  }
}

output {
  elasticsearch {
    hosts => ["http://elasticsearch:9200"]
    index => "logs-nginx-%{+YYYY.MM.dd}"
  }
}
```

**What this grok filter does to a real nginx access log line:**

```
Raw:
203.0.113.5 - - [25/Jul/2026:14:32:01 +0000] "GET /api/orders HTTP/1.1" 200 1534 "-" "Mozilla/5.0"

Parsed into structured fields:
{
  "client_ip": "203.0.113.5",
  "http_method": "GET",
  "request": "/api/orders",
  "http_version": "1.1",
  "response_code": 200,
  "bytes_sent": 1534,
  "user_agent": "Mozilla/5.0",
  "@timestamp": "2026-07-25T14:32:01.000Z",
  "geoip": { "country_name": "...", "location": {...} }
}
```

Now `response_code >= 500` is a real queryable integer field, not a substring match inside a giant text blob — that's the entire point of the filter stage.

### Filebeat — The More Common Real Shipper

The example above has Logstash tailing the log file directly — workable, but Logstash is heavier (JVM-based) than something that should just be reading and forwarding files. In most real production setups, a lightweight **Filebeat** agent runs on each host/container and does the tailing/forwarding instead, with Logstash reserved for the heavier parsing/enrichment work.

```yaml
# filebeat.yml — runs on the host generating logs, forwards to Logstash
filebeat.inputs:
  - type: log
    paths:
      - /var/log/nginx/access.log
    fields:
      service: nginx
    fields_under_root: true

output.logstash:
  hosts: ["logstash:5044"]
```

```
Full real pipeline: nginx writes to disk → Filebeat tails the file,
handles log ROTATION correctly (it tracks file offsets so a rotated/
truncated log file doesn't cause duplicate or lost lines — something
a naive `tail -f` doesn't handle safely) and forwards each line → 
Logstash receives it (via a `beats` input, not a `file` input),
applies the grok/date/mutate filters shown above → Elasticsearch.

Filebeat's job is ONLY collection/forwarding — it has no filter stage
of its own for anything beyond very light processing. This is the
same division of labor as Fluent Bit (edge, lightweight, DaemonSet)
vs Fluentd (central, heavier processing) covered later in this file —
Filebeat and Logstash split the same way, just within the Elastic
ecosystem specifically.
```

### Kibana

- **Discover** — raw log search/browse, the "grep UI": filter by field, free-text search, time-range picker
- **Index Pattern** (now called "Data View") — tells Kibana which Elasticsearch indices to query (`logs-nginx-*`) and which field is the time field (`@timestamp`)
- **Visualizations** — bar/line/pie charts, data tables, built from aggregations over indexed fields (e.g., count of `response_code:500` over time)
- **Dashboards** — multiple visualizations combined, filterable together

### Querying Elasticsearch Directly — The API Beneath Kibana

Kibana's Discover tab is a UI over the same REST API you can hit directly — useful for scripting, automation, or debugging when you're not sure Kibana itself is showing what's actually in the index.

```bash
# Query DSL — the real search API Kibana translates your searches into
curl -X GET "elasticsearch:9200/logs-nginx-*/_search" -H 'Content-Type: application/json' -d '
{
  "query": {
    "bool": {
      "must": [
        { "match": { "response_code": 500 } }
      ],
      "filter": [
        { "range": { "@timestamp": { "gte": "now-1h" } } }
      ]
    }
  },
  "sort": [{ "@timestamp": "desc" }],
  "size": 20
}'
```

```
bool/must    → conditions that MUST match (like SQL's AND/WHERE)
range        → numeric/date range filter — "@timestamp": "now-1h" scopes
                the search to the last hour, avoiding a full-index scan
size         → cap how many documents come back — omitting this on a
                huge index is a real way to accidentally pull gigabytes
                of results into a script
```

### `_cat` APIs — Quick Operational Health Checks

```bash
curl "elasticsearch:9200/_cat/health?v"          # is the cluster green/yellow/red, right now
curl "elasticsearch:9200/_cat/indices?v&s=store.size:desc"   # every index, sorted by SIZE —
                                                                # the fastest way to spot which
                                                                # index is quietly eating disk
curl "elasticsearch:9200/_cat/nodes?v"             # per-node stats — heap usage, disk, CPU
curl "elasticsearch:9200/_cluster/health?pretty"     # JSON form — status, shard counts,
                                                        # unassigned shards (a RED cluster
                                                        # usually means unassigned primary shards)
```

```
Cluster status:
  green  → all primary AND replica shards allocated, fully healthy
  yellow → all primaries allocated, but some REPLICAS aren't — degraded
           redundancy, but the cluster is still fully functional and
           serving reads/writes (common right after a node restart)
  red    → some PRIMARY shard is unassigned — that index's data is
           partially or fully unavailable, the one status that means
           an actual active incident, not just "keep an eye on it"
```

---

## Loki

Loki takes a fundamentally different approach: it does **not** build a full-text inverted index over log content. It indexes only the **labels** (metadata like `app`, `namespace`, `pod`) and stores the raw log lines compressed in chunks, associated with that label set. Search within a label set is a grep-like scan over the compressed chunks at query time.

### ELK vs Loki — Indexing Model

| | Elasticsearch (ELK) | Loki |
|---|---|---|
| What's indexed | Every field/term in every log line (full-text) | Only labels (e.g., `app`, `env`, `pod`) |
| Storage cost | High — inverted index often bigger than raw logs | Low — mostly compressed raw log chunks (like S3-cheap) |
| Query speed for text search | Fast (index lookup) | Slower for broad searches (scans chunks matching labels) |
| Query language | Query DSL / Lucene syntax | LogQL (PromQL-like) |
| Best fit | Deep full-text search, ad-hoc investigation across arbitrary fields | Kubernetes-native log aggregation paired with Prometheus/Grafana, cost-sensitive at scale |
| Operational complexity | Higher (JVM heap tuning, shard management, ILM) | Lower (designed to run cheaply, especially with object storage backend) |

### LogQL Basics

```logql
# All logs from a label selector (like PromQL's {job="..."})
{app="backend-api", environment="production"}

# Text filter on top of the label selector
{app="backend-api"} |= "ERROR"

# Exclude a pattern
{app="backend-api"} != "healthcheck"

# Regex filter
{app="backend-api"} |~ "timeout|refused"

# Parse structured fields out of a JSON log line
{app="backend-api"} | json | status_code >= 500

# Rate of error lines per second — metrics FROM logs
sum(rate({app="backend-api"} |= "ERROR" [5m]))

# Count log lines per pod over 1h
sum by (pod) (count_over_time({app="backend-api"}[1h]))
```

The `| json` / `| logfmt` parser stages let LogQL extract fields from structured log lines on the fly at query time (rather than at ingest time like Logstash) — cheaper to ingest, costlier per-query, which fits Loki's overall "cheap storage, pay at query time" philosophy.

**Label cardinality warning**: never put high-cardinality values (user_id, request_id, raw timestamp) into Loki labels — that defeats the entire cost model by exploding the number of distinct streams Loki has to track, similar to the Prometheus cardinality trap. Keep labels to bounded dimensions: `app`, `env`, `namespace`, `pod`, `level`.

---

## Fluentd vs Fluent Bit

Both are log **shippers/routers** — they sit between "where logs are produced" and "where logs should end up" (Elasticsearch, Loki, S3, Kafka, etc.), and both use a plugin architecture (input → filter → output).

| | Fluentd | Fluent Bit |
|---|---|---|
| Language | Ruby (C core + Ruby plugins) | Pure C |
| Memory footprint | ~40MB+ typical | ~1-2MB typical |
| Plugin ecosystem | Very large (500+ plugins) | Smaller but covers the common cases |
| Typical role | Central log aggregator/router (receives from many Fluent Bit agents, does heavier processing) | Lightweight per-node/per-pod log shipper |
| Kubernetes pattern | Sometimes runs centrally as a "log router" deployment | Runs as a **DaemonSet** — one pod per node, tails container logs, forwards onward |

### Fluent Bit as a Kubernetes DaemonSet (Common Pattern)

```yaml
# fluent-bit DaemonSet reads every container's stdout/stderr log file
# on the node it's scheduled to, tags it with pod/namespace metadata,
# and forwards to a central destination.

apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: fluent-bit
  namespace: logging
spec:
  selector:
    matchLabels:
      app: fluent-bit
  template:
    metadata:
      labels:
        app: fluent-bit
    spec:
      containers:
        - name: fluent-bit
          image: fluent/fluent-bit:3.0
          volumeMounts:
            - name: varlog
              mountPath: /var/log
            - name: config
              mountPath: /fluent-bit/etc/
      volumes:
        - name: varlog
          hostPath:
            path: /var/log
        - name: config
          configMap:
            name: fluent-bit-config
```

```ini
# fluent-bit.conf (as a ConfigMap)
[INPUT]
    Name              tail
    Path              /var/log/containers/*.log
    Parser            docker
    Tag               kube.*

[FILTER]
    Name              kubernetes
    Match             kube.*
    Merge_Log         On
    Keep_Log          Off

[OUTPUT]
    Name              loki
    Match             *
    Host              loki.logging.svc.cluster.local
    Port              3100
    Labels            job=fluentbit, namespace=$kubernetes['namespace_name']
```

**Rule of thumb**: use Fluent Bit at the edge (DaemonSet, sidecar) wherever resource footprint matters — hundreds of nodes each running a 40MB Fluentd agent adds up. Use full Fluentd (or Logstash) where you need heavier processing/routing logic centrally and resource footprint per instance matters less.

---

## Comparison Table: ELK vs Loki

| | ELK Stack | Grafana Loki |
|---|---|---|
| Cost at scale | High (compute + storage for full-text index) | Low (compressed chunks, cheap object storage like S3) |
| Query model | Full-text search (Lucene), rich aggregations | Label-filtered grep + LogQL metric extraction |
| Best fit | Security/audit logs, deep ad-hoc investigation, compliance search across arbitrary fields | Kubernetes-native infra logs, correlating with Prometheus metrics/Grafana dashboards, cost-sensitive high-volume logging |
| Setup complexity | Higher (Elasticsearch cluster tuning, JVM heap, shard strategy) | Lower, especially with a managed/object-storage backend |
| Correlate with metrics | Separate tool (Kibana ≠ Grafana) unless bridged | Native — same Grafana UI as Prometheus dashboards, click a metric spike → jump to logs |

**In practice**: many teams run both — Loki for high-volume infra/app logs correlated with Grafana dashboards, and a smaller ELK (or OpenSearch) deployment for logs that genuinely need deep full-text/compliance search (audit trails, security logs).

---

## Senior Tip

```
1. Structured logging (JSON) at the SOURCE beats parsing unstructured
   text downstream. If your app logs `{"level":"error","msg":"...",
   "user_id":123}` directly, you skip grok entirely — Logstash/Fluent
   Bit just pass it through, Loki's `| json` parses it instantly.

2. Retention policy is a cost decision, not an afterthought. Hot logs
   (7 days, fast storage) -> warm (30 days) -> cold/archive (90+ days,
   cheap storage, rarely queried) -> delete. Define this before you
   have a cost surprise.

3. Never log secrets. A grok/JSON pipeline will happily index an
   API key sitting in a log line straight into a searchable store
   accessible to your whole team.

4. High-cardinality labels are the #1 way to blow up either system's
   cost model — Elasticsearch via mapping explosion, Loki via stream
   explosion. Keep IDs in the log body, not in labels/index fields
   used for routing.

5. Correlate logs with traces/metrics via a shared identifier
   (request_id / trace_id) logged on every line — that's what turns
   "here are 10,000 log lines" into "here's the exact request that
   failed and everything it touched."
```

## Interview Angle

**Q: "Why would you choose Loki over ELK for a Kubernetes cluster's logs?"**
Cost and operational simplicity at scale — Loki only indexes labels, not full text, so storage is a fraction of Elasticsearch's, and it lives natively in the same Grafana UI as your Prometheus metrics, so you can jump from a latency spike straight to the matching logs without switching tools. Trade-off: broad free-text search across unindexed content is slower than Elasticsearch's Lucene-backed search.

**Q: "Walk me through what happens to one nginx log line from disk to Kibana."**
nginx writes the line to `/var/log/nginx/access.log` → Logstash (or Filebeat feeding Logstash) tails the file → a grok filter parses it into structured fields (client_ip, response_code, etc.) → a date filter sets `@timestamp` → the event is shipped to Elasticsearch into a date-suffixed index → Kibana's Discover/Visualize queries that index via a configured data view.

**Q: "Why run Filebeat AND Logstash, instead of just having Logstash tail the log file directly?"**
Filebeat is a lightweight, purpose-built agent for exactly one job — tailing files and forwarding them, correctly handling log rotation (tracking file offsets so a rotated/truncated file doesn't cause duplicate or lost lines, which a naive `tail -f` doesn't handle safely). Logstash is JVM-based and heavier, better reserved for the actual parsing/enrichment work (grok, geoip, mutate). Running Filebeat on every host/container and centralizing the heavy processing in fewer Logstash instances is cheaper at scale than running full Logstash everywhere just to tail files.

**Q: "`_cat/health` shows your Elasticsearch cluster as yellow. Should you page someone?"**
Not urgently — yellow means every PRIMARY shard is allocated (the cluster is fully functional for reads/writes) but some REPLICA shards aren't yet, which commonly happens right after a node restart or a scale-down while the cluster rebalances. RED is the status that means an actual incident — some primary shard itself is unassigned, meaning that index's data is partially or fully unavailable right now.

---

## Related

- [`../05_Docker/04_storage_networking_registry.md`](../05_Docker/04_storage_networking_registry.md) — Docker's own logging drivers (`json-file`, `awslogs`, `fluentd`, `gelf`), the layer beneath everything in this file
- [`../11_Monitoring/01_prometheus_grafana_alertmanager.md`](../11_Monitoring/01_prometheus_grafana_alertmanager.md) — correlating logs with metrics via a shared `request_id`/`trace_id`
- [`../19_Observability/01_metrics_logs_traces_opentelemetry.md`](../19_Observability/01_metrics_logs_traces_opentelemetry.md) — logs as one of the three observability pillars, alongside metrics and traces
- [`../07_Cloud_AWS/02_storage_database.md`](../07_Cloud_AWS/02_storage_database.md) — S3 lifecycle tiering, the same hot/warm/cold pattern this file's ILM policy applies to Elasticsearch's own storage
