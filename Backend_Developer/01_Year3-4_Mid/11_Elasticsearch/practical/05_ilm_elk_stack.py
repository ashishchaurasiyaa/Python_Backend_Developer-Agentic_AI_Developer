"""
============================================================
ELASTICSEARCH ILM + ELK STACK — Practical
============================================================
Setup:
    docker run -d --name es -p 9200:9200 -p 9300:9300 \\
        -e "discovery.type=single-node" \\
        -e "xpack.security.enabled=false" \\
        elasticsearch:8.13.0

    docker run -d --name kibana -p 5601:5601 \\
        -e "ELASTICSEARCH_HOSTS=http://es:9200" \\
        --link es:es \\
        kibana:8.13.0

    pip install elasticsearch
"""


# ============================================================
# 1. CREATE ILM POLICY
# ============================================================
ILM_POLICY = """
PUT _ilm/policy/logs_policy
{
  "policy": {
    "phases": {
      "hot": {
        "min_age": "0ms",
        "actions": {
          "rollover": {
            "max_size": "50gb",
            "max_age": "1d",
            "max_docs": 100000000
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
            "include": { "data_tier": "data_warm" }
          }
        }
      },
      "cold": {
        "min_age": "30d",
        "actions": {
          "set_priority": { "priority": 0 },
          "allocate": {
            "number_of_replicas": 0,
            "include": { "data_tier": "data_cold" }
          },
          "freeze": {}
        }
      },
      "frozen": {
        "min_age": "90d",
        "actions": {
          "searchable_snapshot": {
            "snapshot_repository": "s3_backup"
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
"""


# ============================================================
# 2. CREATE INDEX TEMPLATE + DATA STREAM
# ============================================================
INDEX_TEMPLATE = """
PUT _index_template/logs_template
{
  "index_patterns": ["logs-*"],
  "data_stream": {},
  "template": {
    "settings": {
      "index.lifecycle.name": "logs_policy",
      "index.number_of_shards": 3,
      "index.number_of_replicas": 1,
      "index.codec": "best_compression",
      "index.refresh_interval": "5s"
    },
    "mappings": {
      "properties": {
        "@timestamp": { "type": "date" },
        "message":    { "type": "text" },
        "level":      { "type": "keyword" },
        "service":    { "type": "keyword" },
        "host":       { "type": "keyword" },
        "trace_id":   { "type": "keyword" },
        "span_id":    { "type": "keyword" },
        "duration_ms": { "type": "long" },
        "status_code": { "type": "short" }
      }
    }
  },
  "priority": 500
}

-- Create data stream (auto-rollover)
PUT _data_stream/logs-app
PUT _data_stream/logs-api
PUT _data_stream/logs-system

-- Insert (writes auto-route to current backing index)
POST logs-app/_doc
{
  "@timestamp": "2024-05-24T10:30:00Z",
  "message": "User logged in",
  "level": "INFO",
  "service": "auth-service",
  "user_id": 42
}
"""


# ============================================================
# 3. FILEBEAT CONFIG
# ============================================================
FILEBEAT_CONFIG = """
# /etc/filebeat/filebeat.yml

filebeat.inputs:
  - type: log
    enabled: true
    paths:
      - /var/log/app/*.log
    fields:
      service: my-app
      env: production
    fields_under_root: true
    json.keys_under_root: true       # if logs are JSON
    json.add_error_key: true
    multiline:
      pattern: '^\\d{4}-\\d{2}-\\d{2}'
      negate: true
      match: after

  - type: docker
    containers.ids: '*'

  - type: filestream
    paths:
      - /var/log/syslog

processors:
  - add_host_metadata:
      when.not.contains.tags: forwarded
  - add_docker_metadata: ~
  - add_kubernetes_metadata: ~
  - drop_event:
      when:
        regexp:
          message: '^DEBUG'

# Direct to ES (simpler)
output.elasticsearch:
  hosts: ["${ES_HOST}:9200"]
  username: "filebeat"
  password: "${ES_PASSWORD}"
  index: "logs-app-%{+yyyy.MM.dd}"

  # Or use data stream
  index: "logs-app-%{[agent.version]}"
  pipelines:
    - pipeline: "logs_enrichment"

# Or via Logstash
# output.logstash:
#   hosts: ["logstash:5044"]

# Monitoring
monitoring.enabled: true
monitoring.cluster_uuid: "${CLUSTER_UUID}"
"""


# ============================================================
# 4. LOGSTASH PIPELINE
# ============================================================
LOGSTASH_PIPELINE = '''
# /etc/logstash/pipeline.conf

input {
  beats {
    port => 5044
  }

  # Kafka source
  kafka {
    bootstrap_servers => "kafka:9092"
    topics => ["logs"]
    codec => json
  }
}

filter {
  # ===== PARSE JSON =====
  if [message] =~ /^\\{/ {
    json {
      source => "message"
      target => "parsed"
    }
  }

  # ===== PARSE COMMON LOG FORMAT =====
  grok {
    match => {
      "message" => "%{COMBINEDAPACHELOG}"
    }
    tag_on_failure => ["_grokparsefailure"]
  }

  # ===== DATE PARSING =====
  date {
    match => ["timestamp", "ISO8601", "yyyy-MM-dd HH:mm:ss"]
    target => "@timestamp"
  }

  # ===== ADD FIELDS =====
  mutate {
    add_field => {
      "environment" => "${ENV:dev}"
      "ingested_at" => "%{@timestamp}"
    }
    remove_field => ["host", "ecs", "agent"]
  }

  # ===== GEOIP LOOKUP =====
  if [clientip] {
    geoip {
      source => "clientip"
      target => "geo"
    }
  }

  # ===== USER AGENT =====
  if [agent] {
    useragent {
      source => "agent"
      target => "user_agent_info"
    }
  }

  # ===== DROP NOISY =====
  if [level] == "DEBUG" {
    drop {}
  }

  # ===== ROUTE BY SERVICE =====
  if [service] == "payment" {
    mutate { add_tag => ["critical"] }
  }
}

output {
  # ===== DEFAULT: ES =====
  elasticsearch {
    hosts => ["${ES_HOST}:9200"]
    index => "logs-%{[service]}-%{+YYYY.MM.dd}"
    user => "logstash"
    password => "${ES_PASSWORD}"
  }

  # ===== ERROR LOGS → SEPARATE INDEX =====
  if [level] == "ERROR" or "critical" in [tags] {
    elasticsearch {
      hosts => ["${ES_HOST}:9200"]
      index => "errors-%{+YYYY.MM.dd}"
    }
  }

  # ===== AUDIT LOGS → S3 (archive) =====
  if [type] == "audit" {
    s3 {
      bucket => "audit-logs"
      region => "us-east-1"
      time_file => 5
      codec => "json_lines"
    }
  }

  # ===== METRICS → KAFKA (for further processing) =====
  if [type] == "metric" {
    kafka {
      bootstrap_servers => "kafka:9092"
      topic_id => "metrics_processed"
    }
  }
}
'''


# ============================================================
# 5. PYTHON: INDEXING LOGS
# ============================================================
PYTHON_INDEXING = '''
from elasticsearch import AsyncElasticsearch, helpers
from datetime import datetime
import asyncio


client = AsyncElasticsearch(
    hosts=["http://es-cluster:9200"],
    basic_auth=("user", "password"),
)


# ===== SIMPLE INDEX =====
async def log_event(level: str, message: str, service: str, **extra):
    doc = {
        "@timestamp": datetime.utcnow().isoformat(),
        "level": level,
        "message": message,
        "service": service,
        **extra,
    }
    await client.index(index="logs-app", document=doc)


# ===== BULK INDEX (FAST) =====
async def bulk_log(events):
    actions = [
        {
            "_index": "logs-app",
            "_source": {
                "@timestamp": e.get("timestamp", datetime.utcnow().isoformat()),
                **e,
            }
        }
        for e in events
    ]
    success, failed = await helpers.async_bulk(client, actions)
    return success, failed


# ===== QUERY =====
async def search_errors(service: str, since_minutes: int = 60):
    query = {
        "query": {
            "bool": {
                "must": [
                    {"match": {"level": "ERROR"}},
                    {"match": {"service": service}},
                ],
                "filter": [
                    {"range": {
                        "@timestamp": {
                            "gte": f"now-{since_minutes}m",
                        }
                    }}
                ]
            }
        },
        "sort": [{"@timestamp": "desc"}],
        "size": 100,
    }
    result = await client.search(index="logs-*", body=query)
    return [hit["_source"] for hit in result["hits"]["hits"]]


# ===== AGGREGATION =====
async def errors_by_hour():
    query = {
        "query": {"match": {"level": "ERROR"}},
        "aggs": {
            "errors_over_time": {
                "date_histogram": {
                    "field": "@timestamp",
                    "fixed_interval": "1h",
                }
            },
            "by_service": {
                "terms": {"field": "service", "size": 10},
                "aggs": {
                    "by_hour": {
                        "date_histogram": {
                            "field": "@timestamp",
                            "fixed_interval": "1h",
                        }
                    }
                }
            }
        },
        "size": 0,
    }
    return await client.search(index="logs-*", body=query)
'''


# ============================================================
# 6. SNAPSHOT MANAGEMENT
# ============================================================
SNAPSHOT_MANAGEMENT = """
-- ===== REGISTER S3 REPOSITORY =====
PUT _snapshot/s3_backup
{
  "type": "s3",
  "settings": {
    "bucket": "es-snapshots",
    "region": "us-east-1",
    "base_path": "elasticsearch/cluster-1"
  }
}

-- ===== TAKE MANUAL SNAPSHOT =====
PUT _snapshot/s3_backup/snap_2024_05_24
{
  "indices": "logs-*",
  "include_global_state": false,
  "metadata": {
    "taken_by": "manual",
    "reason": "pre-upgrade"
  }
}

-- Check status
GET _snapshot/s3_backup/snap_2024_05_24

-- ===== AUTO SNAPSHOTS (SLM) =====
PUT _slm/policy/daily_logs_snapshot
{
  "schedule": "0 30 1 * * ?",   -- 01:30 daily
  "name": "<daily-logs-{now/d}>",
  "repository": "s3_backup",
  "config": {
    "indices": ["logs-*", "audit-*"],
    "include_global_state": false
  },
  "retention": {
    "expire_after": "30d",
    "min_count": 7,
    "max_count": 30
  }
}

-- Manual trigger
POST _slm/policy/daily_logs_snapshot/_execute

-- ===== RESTORE =====
POST _snapshot/s3_backup/snap_2024_05_24/_restore
{
  "indices": "logs-2024-05",
  "rename_pattern": "(.+)",
  "rename_replacement": "restored-$1",
  "include_global_state": false
}
"""


# ============================================================
# 7. KIBANA QUERIES (KQL)
# ============================================================
KIBANA_QUERIES = """
KIBANA KQL EXAMPLES:

# Basic filter
level: "ERROR" AND service: "payment"

# Multiple values
service: ("api" OR "auth" OR "payment")

# Range
status_code >= 500 AND duration_ms > 1000

# Wildcards
message: *timeout*

# Negation
NOT level: "DEBUG"

# Time range (relative)
@timestamp >= "now-1h"

# Field exists
trace_id: *

# Nested
geo.country_name: "India" AND geo.city_name: ("Mumbai" or "Bangalore")

# Combined
service: "api" AND level: "ERROR" AND NOT message: *retry* AND @timestamp >= now-15m
"""


# ============================================================
# 8. ALERTING (Kibana Watcher / Stack Alerts)
# ============================================================
ALERTING = """
-- ===== STACK ALERT: HIGH ERROR RATE =====
POST _watcher/watch/high_error_rate
{
  "trigger": {
    "schedule": { "interval": "5m" }
  },
  "input": {
    "search": {
      "request": {
        "indices": ["logs-*"],
        "body": {
          "query": {
            "bool": {
              "must": [
                { "match": { "level": "ERROR" } },
                { "range": { "@timestamp": { "gte": "now-5m" } } }
              ]
            }
          },
          "aggs": {
            "error_count": { "value_count": { "field": "level" } }
          }
        }
      }
    }
  },
  "condition": {
    "compare": {
      "ctx.payload.aggregations.error_count.value": { "gt": 100 }
    }
  },
  "actions": {
    "send_slack": {
      "webhook": {
        "method": "POST",
        "url": "https://hooks.slack.com/services/...",
        "body": "Error rate: {{ctx.payload.aggregations.error_count.value}} in last 5min"
      }
    },
    "send_pagerduty": {
      "webhook": {
        "method": "POST",
        "url": "https://events.pagerduty.com/v2/enqueue",
        "body": "{...}"
      }
    }
  }
}

-- ===== ANOMALY DETECTION (X-Pack ML) =====
PUT _ml/anomaly_detectors/api-latency-job
{
  "analysis_config": {
    "bucket_span": "5m",
    "detectors": [{
      "function": "high_mean",
      "field_name": "duration_ms",
      "by_field_name": "endpoint"
    }]
  },
  "data_description": {
    "time_field": "@timestamp"
  }
}
"""


# ============================================================
# 9. PERFORMANCE TUNING
# ============================================================
PERFORMANCE = """
-- ===== INDEXING SETTINGS =====
PUT logs-*/_settings
{
  "index.refresh_interval": "30s",          -- default 1s, less freq = faster ingest
  "index.translog.durability": "async",      -- not sync per request
  "index.translog.sync_interval": "30s"
}

-- ===== BULK SETTINGS (for ingestion) =====
PUT logs-bulk/_settings
{
  "index.number_of_replicas": 0,             -- during bulk load
  "index.refresh_interval": "-1"             -- no auto-refresh
}

-- After bulk:
PUT logs-bulk/_settings
{
  "index.number_of_replicas": 1,
  "index.refresh_interval": "5s"
}
POST logs-bulk/_refresh

-- ===== JVM HEAP =====
-- /etc/elasticsearch/jvm.options
-Xms16g
-Xmx16g
-- Always equal, max 32GB (compressed oops)

-- ===== DISK WATERMARKS =====
PUT _cluster/settings
{
  "transient": {
    "cluster.routing.allocation.disk.watermark.low": "80%",
    "cluster.routing.allocation.disk.watermark.high": "85%",
    "cluster.routing.allocation.disk.watermark.flood_stage": "90%"
  }
}

-- ===== CIRCUIT BREAKERS =====
GET _cluster/stats/breaker
PUT _cluster/settings
{
  "transient": {
    "indices.breaker.total.limit": "70%",
    "indices.breaker.request.limit": "60%"
  }
}
"""


# ============================================================
# 10. CLUSTER MONITORING
# ============================================================
CLUSTER_MONITORING = """
-- Cluster health (green/yellow/red)
GET _cluster/health?pretty

-- Cluster stats
GET _cluster/stats

-- Cluster state
GET _cluster/state/master_node,nodes,routing_nodes

-- ===== USEFUL _cat APIs =====
GET _cat/indices?v&s=store.size:desc        -- by size
GET _cat/shards?v&s=node                    -- shards per node
GET _cat/nodes?v&h=name,role,heap.percent,cpu,disk.used_percent
GET _cat/pending_tasks?v
GET _cat/recovery?v&active_only=true

-- ===== STUCK SHARDS =====
GET _cluster/allocation/explain
{
  "index": "logs-2024-05",
  "shard": 0,
  "primary": true
}

-- ===== HOT THREADS =====
GET _nodes/hot_threads

-- ===== SLOW LOG =====
PUT logs-*/_settings
{
  "index.indexing.slowlog.threshold.index.warn": "10s",
  "index.search.slowlog.threshold.query.warn": "10s"
}
"""


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("ELASTICSEARCH ILM + ELK STACK")
    print("=" * 60)

    print("\n--- ILM POLICY ---")
    print(ILM_POLICY)
    print("\n--- INDEX TEMPLATE + DATA STREAM ---")
    print(INDEX_TEMPLATE)
    print("\n--- FILEBEAT CONFIG ---")
    print(FILEBEAT_CONFIG)
    print("\n--- LOGSTASH PIPELINE ---")
    print(LOGSTASH_PIPELINE)
    print("\n--- PYTHON INDEXING ---")
    print(PYTHON_INDEXING)
    print("\n--- SNAPSHOT MANAGEMENT ---")
    print(SNAPSHOT_MANAGEMENT)
    print("\n--- KIBANA KQL ---")
    print(KIBANA_QUERIES)
    print("\n--- ALERTING ---")
    print(ALERTING)
    print("\n--- PERFORMANCE TUNING ---")
    print(PERFORMANCE)
    print("\n--- CLUSTER MONITORING ---")
    print(CLUSTER_MONITORING)
