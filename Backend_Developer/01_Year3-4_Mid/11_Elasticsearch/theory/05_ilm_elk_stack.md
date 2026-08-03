# Elasticsearch ILM + ELK Stack

> **Interview angle:** "Logs 100GB/day generate ho rahe. 1 year retain karna. Cost-effective Elasticsearch setup?"

---

## 1. The Problem: Endless Log Growth

```
Day 1:   100GB index
Day 30:  3TB
Day 365: 36TB+
```

Without management:
- Disk fills
- Queries slow
- Cluster unbalanced
- Cost explodes

**Solution:** Index Lifecycle Management (ILM).

---

## 2. ILM — Index Lifecycle Management

Defines automatic transitions through phases:

```
Hot       → Warm     → Cold       → Frozen     → Delete
(active)    (recent)   (rare)       (archive)    (gone)

SSD         HDD        Slow disk    Object       N/A
Many copies Fewer      1 copy       store        -
Frequent    Some       Rare         Search only  -
```

---

## 3. ILM Policy Example

```json
PUT _ilm/policy/logs_policy
{
  "policy": {
    "phases": {
      "hot": {
        "min_age": "0ms",
        "actions": {
          "rollover": {
            "max_size": "50gb",
            "max_age": "1d"
          },
          "set_priority": { "priority": 100 }
        }
      },
      "warm": {
        "min_age": "7d",
        "actions": {
          "shrink": { "number_of_shards": 1 },
          "forcemerge": { "max_num_segments": 1 },
          "set_priority": { "priority": 50 },
          "allocate": {
            "include": { "data_tier": "warm" }
          }
        }
      },
      "cold": {
        "min_age": "30d",
        "actions": {
          "set_priority": { "priority": 0 },
          "allocate": {
            "number_of_replicas": 0,
            "include": { "data_tier": "cold" }
          }
        }
      },
      "frozen": {
        "min_age": "90d",
        "actions": {
          "searchable_snapshot": {
            "snapshot_repository": "s3_repo"
          }
        }
      },
      "delete": {
        "min_age": "365d",
        "actions": {
          "delete": {}
        }
      }
    }
  }
}
```

---

## 4. Index Templates + Rollover

```json
PUT _index_template/logs_template
{
  "index_patterns": ["logs-*"],
  "data_stream": {},
  "template": {
    "settings": {
      "index.lifecycle.name": "logs_policy",
      "index.number_of_shards": 3,
      "index.number_of_replicas": 1
    },
    "mappings": {
      "properties": {
        "@timestamp": { "type": "date" },
        "message": { "type": "text" },
        "level": { "type": "keyword" },
        "service": { "type": "keyword" }
      }
    }
  }
}
```

### Data Stream (modern way)
```bash
# Create data stream — automatically rolls over backing indices
PUT _data_stream/logs-app

# Write goes to the active write index
POST logs-app/_doc
{
  "@timestamp": "2024-05-24T10:30:00",
  "message": "User logged in",
  "level": "INFO"
}
```

Old way: manual aliases + rollover. Data Streams handle this automatically.

---

## 5. Rollover Triggers

```json
"rollover": {
  "max_size": "50gb",      // rollover when index >= 50GB
  "max_age": "7d",         // OR when 7 days old
  "max_docs": 100000000    // OR 100M docs
}
```

Whichever fires first.

---

## 6. Shrink — Reduce Shards

After hot phase, "warm" data doesn't need 3 shards. Shrink to 1.

```json
"shrink": {
  "number_of_shards": 1
}
```

- Smaller indices = less overhead
- Faster recovery
- Less memory

---

## 7. ForceMerge — Compact Segments

Each ES index = collection of segments. New writes → new segments. Many small segments = slow searches.

```json
"forcemerge": {
  "max_num_segments": 1
}
```

After: single segment, optimal read performance. **NEVER do this on hot indices** (locks, slow).

---

## 8. Searchable Snapshots (Frozen Tier)

```json
"frozen": {
  "min_age": "90d",
  "actions": {
    "searchable_snapshot": {
      "snapshot_repository": "s3_repo"
    }
  }
}
```

- Data lives in S3/blob storage
- ~10x cheaper than disk
- Queryable but slower
- Indices removed from local disk
- ES fetches needed segments on demand

Massive cost savings for long retention.

---

## 9. ELK Stack Architecture

```
Apps → Beats / Logstash → Elasticsearch → Kibana
         (collection)      (storage +      (visualize)
                            search)
```

### Beats — lightweight shippers
- `Filebeat`: log files
- `Metricbeat`: system/service metrics
- `Packetbeat`: network
- `Heartbeat`: uptime
- `Auditbeat`: audit data

### Logstash — heavyweight pipeline
- Input → Filter → Output
- Parse, enrich, transform
- Use for complex transformations
- Heavier than Beats

### Modern alternative
- **Fluent Bit** — lighter than Logstash, written in C
- **OpenTelemetry Collector** — vendor-neutral

---

## 10. Filebeat Config

```yaml
# filebeat.yml
filebeat.inputs:
  - type: log
    paths:
      - /var/log/app/*.log
    fields:
      service: my-app
      env: production
    json.keys_under_root: true     # if logs are JSON

output.elasticsearch:
  hosts: ["es-cluster:9200"]
  username: "filebeat"
  password: "${ES_PASSWORD}"
  index: "logs-app-%{+yyyy.MM.dd}"

# OR via Logstash
output.logstash:
  hosts: ["logstash:5044"]

processors:
  - add_host_metadata: ~
  - add_docker_metadata: ~
  - drop_event:
      when:
        regexp:
          message: '^DEBUG'    # drop debug logs
```

---

## 11. Logstash Pipeline

```ruby
# logstash.conf

input {
  beats {
    port => 5044
  }
}

filter {
  # Parse JSON
  json {
    source => "message"
  }

  # Parse common log format with grok
  grok {
    match => {
      "message" => "%{COMBINEDAPACHELOG}"
    }
  }

  # Add fields
  mutate {
    add_field => {
      "environment" => "${ENV:dev}"
      "tenant_id" => "%{[fields][tenant]}"
    }
  }

  # Geo IP lookup
  geoip {
    source => "clientip"
  }

  # Drop noisy logs
  if [level] == "DEBUG" {
    drop {}
  }

  # User agent parsing
  useragent {
    source => "agent"
  }
}

output {
  elasticsearch {
    hosts => ["es:9200"]
    index => "logs-%{[fields][service]}-%{+YYYY.MM.dd}"
  }

  # Optional: also write to S3
  if [level] == "ERROR" {
    s3 {
      bucket => "error-logs"
      region => "us-east-1"
    }
  }
}
```

---

## 12. Kibana Features

- **Discover**: search + filter logs
- **Visualize**: charts, tables
- **Dashboard**: combine visualizations
- **Lens**: drag-drop chart builder
- **Maps**: geo visualization
- **Machine Learning**: anomaly detection
- **Alerts**: rule-based notifications
- **Observability**: logs + metrics + traces unified
- **SIEM**: security event correlation

### KQL (Kibana Query Language)
```
service: "api" AND level: "ERROR"
status_code >= 500 AND duration_ms > 1000
host.name: ("web-1" or "web-2")
@timestamp >= "2024-05-01" and @timestamp < "2024-06-01"
```

---

## 13. Index Aliases (legacy, now data streams)

```json
// Create alias for app reads
POST _aliases
{
  "actions": [
    { "add": { "index": "logs-2024-05", "alias": "logs-current" } },
    { "remove": { "index": "logs-2024-04", "alias": "logs-current" } }
  ]
}

// App always reads from "logs-current" — abstracts physical index
```

Data Streams replace this in modern ES.

---

## 14. Cluster Topology

```yaml
# 5-node production cluster
roles:
  - master eligible (3 nodes — odd number for quorum)
  - data (varies based on storage)
  - ingest (preprocess pipelines)
  - coordinating (query routing)

# Small cluster
node-1: master + data + ingest
node-2: master + data + ingest
node-3: master + data + ingest

# Large cluster (separate concerns)
master-1, 2, 3: dedicated master (low resource)
data-hot-1...5: SSD, high CPU
data-warm-1...3: HDD
data-cold-1...2: cheap HDD
coordinating-1, 2: routes queries
ingest-1: preprocess
```

---

## 15. Snapshot / Backup

```json
// Register S3 repository
PUT _snapshot/s3_backup
{
  "type": "s3",
  "settings": {
    "bucket": "es-backups",
    "region": "us-east-1"
  }
}

// Take snapshot
PUT _snapshot/s3_backup/snap_2024_05_24

// Auto-snapshot policy
PUT _slm/policy/daily_snapshots
{
  "schedule": "0 30 1 * * ?",      // 01:30 daily
  "name": "<daily-{now/d}>",
  "repository": "s3_backup",
  "config": {
    "indices": ["logs-*"]
  },
  "retention": {
    "expire_after": "30d",
    "min_count": 7,
    "max_count": 30
  }
}

// Restore
POST _snapshot/s3_backup/snap_2024_05_24/_restore
```

---

## 16. Performance Tuning

### Shard sizing
- **Optimal**: 20-50GB per shard
- < 10GB: too many shards = overhead
- > 50GB: slow recovery, large memory

### Heap
- 50% of RAM, but max **32GB** (JVM compression boundary)
- Set Xmx + Xms equal

### Refresh interval
```json
PUT logs-*/_settings
{
  "index.refresh_interval": "30s"   // default 1s
}
```
Higher = better indexing throughput, slower visibility.

### Disable replicas during bulk load
```json
PUT logs-*/_settings
{
  "index.number_of_replicas": 0
}

// ... bulk load ...

PUT logs-*/_settings
{
  "index.number_of_replicas": 1
}
```

---

## 17. Cost Optimization

| Strategy | Savings |
|---|---|
| ILM rollover | 50%+ |
| Hot → Warm tier | 60% storage cost |
| Cold tier (HDD) | 80% |
| Frozen tier (S3) | 95% |
| Delete old data | 100% (of that data) |
| Compression (best_compression) | 50% disk |
| Force merge old indices | 20-30% |

---

## 18. Cluster Health

```json
GET _cluster/health
// status: green / yellow / red
// green: all shards allocated
// yellow: primary OK, some replicas missing
// red: some primaries missing — data loss possible

GET _cat/indices?v
GET _cat/shards?v
GET _cat/nodes?v

GET _cluster/allocation/explain?pretty
{
  "index": "logs-2024-05",
  "shard": 0,
  "primary": true
}
```

---

## 19. Monitoring (Elastic Observability)

```yaml
# Elastic Stack Monitoring
xpack.monitoring.collection.enabled: true

# Or via Metricbeat
metricbeat.modules:
  - module: elasticsearch
    metricsets: ["node", "node_stats", "cluster_stats", "index"]
    period: 10s
    hosts: ["es:9200"]
```

Key metrics:
- JVM heap usage
- Cluster status
- Shard count per node
- Query latency p99
- Indexing rate
- Disk usage per tier

---

## 20. Interview Questions

**Q1: ILM kya hai?**
Automatic transitions: Hot → Warm → Cold → Frozen → Delete. Based on age, size, doc count.

**Q2: Hot vs Cold tier?**
Hot = SSD, frequent access, multiple replicas. Cold = cheap storage, rare reads, single copy.

**Q3: Searchable snapshot?**
Index data in S3, queryable but slower. Saves 95% cost vs hot storage.

**Q4: Rollover triggers?**
max_size (50GB typical), max_age (1d typical), max_docs.

**Q5: Data stream vs alias?**
Data stream = modern automated rollover + ILM. Alias = manual, legacy approach.

**Q6: Shard count sweet spot?**
20-50GB per shard. Too small = overhead, too large = slow recovery.

**Q7: ELK alternative for AI age?**
Loki (logs only), Grafana Mimir (metrics), Tempo (traces) — cheaper but ES has SIEM/ML.

---

## 21. Best Practices

1. **ILM policy on every index** (no exception)
2. **Data Streams** instead of aliases (modern)
3. **Shard size 20-50GB** target
4. **JVM heap = RAM/2, max 32GB**
5. **Snapshot daily** to S3
6. **Force merge in warm phase** (not hot)
7. **Hot/Warm/Cold tier separation** for cost
8. **Filebeat over Logstash** when no transformation needed
9. **KQL in Kibana** for log search
10. **Monitor cluster health** + disk usage

---

## 22. Ingest Pipelines & Runtime Fields (Logstash-ke-bina transforms)

### Ingest pipelines — transform at index time, inside ES

Logstash alag process hai; **ingest pipeline** ES ke andar hi processors chain karta hai — light transforms ke liye Logstash ki zaroorat khatam:

```json
PUT _ingest/pipeline/logs-pipeline
{
  "processors": [
    { "grok":   { "field": "message", "patterns": ["%{IP:client_ip} %{WORD:method} %{URIPATHPARAM:path}"] } },
    { "geoip":  { "field": "client_ip" } },
    { "date":   { "field": "ts", "formats": ["ISO8601"] } },
    { "remove": { "field": "message" } }
  ]
}

// Use: index request pe ?pipeline=logs-pipeline, ya index setting:
PUT logs-000001 { "settings": { "index.default_pipeline": "logs-pipeline" } }
```

Common processors: `grok`, `dissect`, `geoip`, `date`, `set/remove/rename`, `script` (Painless), `enrich` (lookup-join from another index). **Filebeat → ingest pipeline → ES** = Logstash-free ELK for most log cases (yehi modern default hai).

### Runtime fields — schema-on-read (query time)

Mapping me field nahi tha, ab chahiye — reindex mat karo:

```json
GET logs/_search
{
  "runtime_mappings": {
    "response_time_s": {
      "type": "double",
      "script": { "source": "emit(doc['response_time_ms'].value / 1000.0)" }
    }
  },
  "query": { "range": { "response_time_s": { "gte": 2.0 } } },
  "fields": ["response_time_s"]
}
```

**Trade-off (interview line):** *"Ingest pipeline = schema-on-write — pay at index time, fast queries. Runtime field = schema-on-read — zero reindex, per-query compute cost. Naya derived field pehle runtime field ke roop me try karta hoon; agar wo hot query ban jaye to ingest pipeline se materialize kar deta hoon."*

---

## Related
- [[01_basics_installation_crud]]
- [[02_search_queries]]
- [[03_aggregations_analyzers]]
- [[04_advanced_fastapi]]
