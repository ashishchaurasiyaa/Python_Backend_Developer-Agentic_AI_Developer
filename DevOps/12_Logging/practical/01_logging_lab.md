# Logging — Hands-On Lab
**DevOps Track · Phase 12 Practical**

## Prerequisites

- Docker + Docker Compose — the whole lab runs locally, zero cost
- **Resource note**: a full ELK stack (Elasticsearch + Logstash + Kibana) is genuinely heavy — Elasticsearch alone wants 2GB+ RAM minimum to start reliably. If your machine is resource-constrained, Labs 1 and 3 use Loki (lightweight, runs comfortably on a laptop); Lab 2 uses a standalone Logstash + Elasticsearch + Kibana stack specifically because grok/ELK parsing is the point of that lab — feel free to shut the ELK stack down (`docker compose down`) immediately after Lab 2 to reclaim resources
- A sample nginx access log file (or run real nginx locally from the Web Servers lab and use its actual `access.log`) — a handful of realistic lines is enough
- `curl` for querying Loki's API directly, and a browser for Kibana/Grafana Explore

---

## Lab 1: Stand Up Loki + Promtail + Grafana, View Logs

**Objective:** Get the lightweight, Kubernetes-native logging path working end to end — the stack the lesson file recommends for cost-sensitive, infra-log-heavy setups.

**Task:**
1. Write a `docker-compose.yml` with `loki`, `promtail`, and `grafana` services.
2. Configure `promtail-config.yml` to tail a local log directory (mount a `./logs` folder into the promtail container) and ship to Loki.
3. Generate some fake log lines into `./logs/app.log` — a mix of `INFO`, `WARN`, and `ERROR` lines, e.g. using a small shell loop.
4. In Grafana, add Loki as a data source (`http://loki:3100`) and open the **Explore** view.
5. Query `{job="app-logs"}` and confirm your fake log lines show up.
6. Filter to just errors: `{job="app-logs"} |= "ERROR"`.

<details>
<summary>Solution / walkthrough</summary>

```yaml
# docker-compose.yml
version: '3.8'
services:
  loki:
    image: grafana/loki:latest
    ports: ["3100:3100"]
    command: -config.file=/etc/loki/local-config.yaml

  promtail:
    image: grafana/promtail:latest
    volumes:
      - ./logs:/var/log/app
      - ./promtail-config.yml:/etc/promtail/config.yml
    command: -config.file=/etc/promtail/config.yml
    depends_on: [loki]

  grafana:
    image: grafana/grafana:latest
    ports: ["3000:3000"]
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
```

```yaml
# promtail-config.yml
server:
  http_listen_port: 9080

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: app-logs
    static_configs:
      - targets: [localhost]
        labels:
          job: app-logs
          __path__: /var/log/app/*.log
```

```bash
mkdir -p logs
for i in $(seq 1 20); do
  level=$([ $((RANDOM % 5)) -eq 0 ] && echo ERROR || echo INFO)
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $level request handled id=$i" >> logs/app.log
done

docker compose up -d
```

In Grafana Explore, select the Loki data source, then:
```logql
{job="app-logs"}
{job="app-logs"} |= "ERROR"
```

**Why labels matter here**: `job=app-logs` is the ONLY thing Loki indexes — everything else (the raw log text) is stored compressed and scanned at query time. This is the fundamental architectural difference from Elasticsearch you're about to feel directly in Lab 2 vs Lab 1's resource footprint.
</details>

---

## Lab 2: A Real Logstash Grok Filter — Parse an Nginx Access Log

**Objective:** Take the exact grok pattern from the lesson file and prove it actually turns unstructured text into structured, queryable fields — the core value proposition of the ELK ingest path.

**Task:**
1. Stand up a minimal Elasticsearch + Logstash + Kibana stack (heavier than Lab 1 — budget more RAM, and shut it down after this lab).
2. Create a realistic nginx `access.log` file with 10-15 lines in the combined log format (or copy real lines from the Web Servers lab's nginx container).
3. Write `logstash.conf`: a `file` input tailing your access log, a `grok` filter parsing it into fields (`client_ip`, `http_method`, `request`, `response_code`, `bytes_sent`, etc.), a `date` filter setting `@timestamp` from the log's own timestamp, and an `elasticsearch` output indexing into `logs-nginx-%{+YYYY.MM.dd}`.
4. Start Logstash pointed at this config and confirm it ships events.
5. In Kibana, create a Data View (`logs-nginx-*`) and use Discover to confirm `response_code` is a real, filterable NUMBER field (not a substring inside a text blob) — filter for `response_code >= 500` and confirm it works as a numeric comparison.
6. Deliberately feed it one malformed log line (missing a field) and check Kibana/Logstash for a `_grokparsefailure` tag — this is how you'd notice a parsing regression in production.

<details>
<summary>Solution / walkthrough</summary>

```yaml
# docker-compose.yml (ELK portion — separate from Lab 1's compose file, or merge if your machine can handle both)
version: '3.8'
services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.13.0
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
    ports: ["9200:9200"]

  kibana:
    image: docker.elastic.co/kibana/kibana:8.13.0
    ports: ["5601:5601"]
    environment:
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200
    depends_on: [elasticsearch]

  logstash:
    image: docker.elastic.co/logstash/logstash:8.13.0
    volumes:
      - ./logstash.conf:/usr/share/logstash/pipeline/logstash.conf
      - ./access.log:/usr/share/logstash/access.log
    depends_on: [elasticsearch]
```

```
# access.log — sample lines
203.0.113.5 - - [25/Jul/2026:14:32:01 +0000] "GET /api/orders HTTP/1.1" 200 1534 "-" "Mozilla/5.0"
198.51.100.9 - - [25/Jul/2026:14:32:03 +0000] "POST /api/checkout HTTP/1.1" 500 88 "-" "Mozilla/5.0"
203.0.113.5 - - [25/Jul/2026:14:32:05 +0000] "GET /api/orders/42 HTTP/1.1" 404 0 "-" "curl/8.0"
```

```ruby
# logstash.conf
input {
  file {
    path => "/usr/share/logstash/access.log"
    start_position => "beginning"
    sincedb_path => "/dev/null"    # re-read from the start every restart, for lab convenience only
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
    remove_field => ["timestamp"]
  }
}

output {
  elasticsearch {
    hosts => ["http://elasticsearch:9200"]
    index => "logs-nginx-%{+YYYY.MM.dd}"
  }
  stdout { codec => rubydebug }   # see parsed events in the container logs too, useful while debugging the pattern
}
```

```bash
docker compose up -d
docker compose logs -f logstash    # watch parsed events fly by via rubydebug
```

In Kibana: Stack Management → Data Views → Create data view → index pattern `logs-nginx-*`, time field `@timestamp`. Then Discover → filter `response_code >= 500` — this only works as a real numeric range filter because the `mutate { convert => {"response_code" => "integer"} }` step turned it from a string into a proper number field; skip that step and Kibana would only be able to do exact string matches, not `>=` comparisons.

**Malformed line test:**
```
this is not a valid nginx log line at all
```
Add it to `access.log`, restart Logstash, and check the `stdout` output or Kibana Discover for `tags: ["_grokparsefailure"]` — Logstash's grok filter doesn't crash on a non-matching line, it tags the event as a parse failure and passes it through anyway (with the raw `message` field intact), which is exactly the mechanism you'd alert on in production to catch a log-format change breaking your pipeline silently.
</details>

---

## Lab 3: LogQL — Metrics From Logs + a Fluent Bit DaemonSet Config

**Objective:** Practice Loki's query language for turning raw logs into rate/count metrics (the "correlate logs with your Prometheus dashboards in one Grafana UI" pattern), and write the Kubernetes-native log-shipping config from the lesson file.

**Task:**
1. Reusing Lab 1's Loki stack, generate a heavier burst of fake logs — at least 200 lines mixing `INFO`/`WARN`/`ERROR`, with timestamps spread over a few minutes (adjust your generator script's sleep/loop).
2. In Grafana Explore, write a LogQL query computing the rate of ERROR lines per second over a 5-minute window: `sum(rate({job="app-logs"} |= "ERROR" [5m]))`.
3. Write a second query counting log lines per some grouping label over the last hour (add a second label like `env=dev` to your promtail config first, then `sum by (env) (count_over_time({job="app-logs"}[1h]))`).
4. Switch the panel visualization from "Logs" to "Time series" in Grafana — confirm LogQL metric queries render as a graph just like PromQL, in the same UI, which is Loki's key selling point over separate Kibana/Grafana tools.
5. Write (you don't need a real cluster to do this — just write and validate the YAML) a Fluent Bit DaemonSet + ConfigMap that tails container logs and ships them to Loki with `namespace` and `job` labels, matching the pattern in the lesson file.
6. In the DaemonSet YAML, explain in a comment why it must be a DaemonSet and not a regular Deployment.

<details>
<summary>Solution / walkthrough</summary>

```logql
# Error rate per second, 5m window
sum(rate({job="app-logs"} |= "ERROR" [5m]))

# Line count per env over the last hour
sum by (env) (count_over_time({job="app-logs"}[1h]))

# Regex filter for either of two patterns
{job="app-logs"} |~ "ERROR|WARN"

# Parse JSON fields if your logs are structured, then filter numerically
{job="app-logs"} | json | status_code >= 500
```

Switching the Grafana panel type from "Logs" to "Time series" on the `rate(...)` query renders a proper line graph — this is the concrete version of the lesson file's claim "click a metric spike → jump to logs" without switching tools: the same Grafana instance, same Explore pane, handles both PromQL-against-Prometheus and LogQL-against-Loki.

```yaml
# fluent-bit-daemonset.yaml
apiVersion: apps/v1
kind: DaemonSet          # NOT a Deployment — a DaemonSet guarantees exactly one Fluent Bit
metadata:                # pod per node, which is required because container logs live on
  name: fluent-bit        # each node's local disk (/var/log/containers/*.log); a Deployment's
  namespace: logging       # replica count has no relationship to node count, so it could
spec:                       # easily miss nodes entirely or double-up on others
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

**Why `Labels` only carries `job` and `namespace`, not e.g. `pod_name`**: pod names are effectively unbounded cardinality in a cluster with frequent rollouts/autoscaling — putting them in a Loki label would explode stream count exactly like Lab 4 in the Monitoring lab explodes Prometheus series count. Pod-level detail belongs in the log body (searchable via `| json` at query time), not the label set used for stream routing.
</details>

---

## Lab 4: Troubleshooting — Diagnosing an Expensive Logging Setup

**Objective:** Reason through a realistic cost/design incident: "our logging bill tripled and nobody knows why" — practice the diagnostic questions from the lesson file's Senior Tips rather than just reading them.

**Task:**
1. Given this (deliberately bad) Fluent Bit output config, identify what's wrong and why it would explode Loki's cost model:
   ```ini
   [OUTPUT]
       Name              loki
       Match             *
       Host              loki.logging.svc.cluster.local
       Port              3100
       Labels            job=fluentbit, pod=$kubernetes['pod_name'], container_id=$kubernetes['container_id']
   ```
2. Fix the labels to only the bounded dimensions, and explain what you'd do INSTEAD to still be able to find "all logs from this specific pod" when debugging — hint: it's still possible, just via a different query mechanism, not a label.
3. Given this (deliberately bad) ELK setup — no ILM policy configured, indices never rotate or expire, `logs-nginx-*` has been growing since day one 8 months ago — explain the cost/operational consequence and design a fix (hot/warm/cold/delete tiers with concrete day thresholds).
4. A colleague says "we should just log everything at DEBUG level in production so we never miss anything during an incident." Explain, using concepts from this lab, why that's a bad default and what you'd propose instead.

<details>
<summary>Solution / walkthrough</summary>

**1. What's wrong with the Fluent Bit labels:**
`pod=$kubernetes['pod_name']` and `container_id=$kubernetes['container_id']` are both effectively unique per pod restart/deployment — in a cluster with autoscaling or frequent rolling deploys, this creates a NEW Loki stream (a new label-set combination) for every pod that has ever existed, not just every pod currently running. Loki has to track metadata for every distinct stream it has ever seen within the retention window — this is stream-count explosion, the direct Loki analog of Prometheus's series-count explosion covered in the Monitoring lab.

**2. Fix:**
```ini
[OUTPUT]
    Name              loki
    Match             *
    Host              loki.logging.svc.cluster.local
    Port              3100
    Labels            job=fluentbit, namespace=$kubernetes['namespace_name'], app=$kubernetes['labels']['app']
```
`namespace` and `app` (a stable deployment-level label, not a per-pod-instance one) are bounded — there are only ever a handful of distinct values. To still find "all logs from this specific pod" when debugging: keep `pod_name` in the log BODY (Fluent Bit's `kubernetes` filter with `Merge_Log On` already merges pod metadata into the log record itself), and filter for it at query time with `{namespace="prod", app="backend-api"} | json | pod_name="backend-api-7d9f-xk2p1"` — same end result, zero cost impact, because query-time filtering on body content doesn't create new streams.

**3. ELK without ILM:**
An index that's been growing unbounded for 8 months means Elasticsearch is holding the FULL inverted index (often several times the raw log size) for logs nobody has queried in months, on the same expensive "hot" storage tier as yesterday's logs — pure cost waste, and it also degrades query performance as shard count/size grows unbounded on nodes that were sized for a much smaller cluster.

Fix — an ILM policy with concrete tiers:
```
Hot   (0-7 days):    fast SSD-backed nodes, actively written and queried
Warm  (7-30 days):   cheaper nodes, read-only, still queryable but less often accessed
Cold  (30-90 days):  cheapest storage, rarely queried, higher query latency acceptable
Delete (90+ days):   removed entirely, unless a specific index (e.g. audit logs) has a
                      longer compliance-driven retention requirement
```
This mirrors the lesson file's explicit framing: "retention policy is a cost decision, not an afterthought" — define the tiers BEFORE the cost surprise, not after.

**4. DEBUG-everything-in-prod:**
This inflates both ingest volume (more log lines shipped, more Logstash/Fluent Bit throughput needed) and storage cost (more inverted-index terms in ELK, more compressed chunk volume in Loki) for the 99% of the time nothing is wrong, while providing no query-time benefit when it IS wrong — nobody's writing more effective incident queries at 3am because DEBUG lines exist somewhere in a 10x larger haystack. The better default: structured logging at INFO in production with request/trace IDs on every line (so you can reconstruct a request's full path across services without needing DEBUG-level noise), and a mechanism to dynamically raise log level for a specific service/pod temporarily during an active incident (a feature flag or env var toggle, reloaded without a redeploy) rather than paying the DEBUG cost 24/7 for the rare incident.
</details>

---

## Self-Check Checklist

- [ ] Can you explain the core architectural difference between Elasticsearch (full-text inverted index) and Loki (labels-only index, chunks scanned at query time)?
- [ ] Can you write a working grok pattern for a standard nginx/apache combined log line from memory (or closely enough to debug one against the actual format)?
- [ ] Can you explain why `mutate { convert => {"field" => "integer"} }` matters for a field like `response_code` beyond just "type correctness"?
- [ ] Can you write basic LogQL: a label selector, a text filter (`|=`), a regex filter (`|~`), and a `| json` parse-and-filter?
- [ ] Can you explain why Fluent Bit runs as a DaemonSet rather than a Deployment in Kubernetes?
- [ ] Can you name the label-cardinality trap in Loki, explain why it mirrors Prometheus's cardinality trap, and state the fix (bounded labels, IDs in body)?
- [ ] Can you design a basic hot/warm/cold/delete ILM retention policy and explain the cost reasoning behind each tier?
- [ ] Can you explain why structured (JSON) logging at the source reduces downstream parsing cost/complexity compared to unstructured text + grok?
- [ ] Can you explain, unprompted, when you'd genuinely still want ELK alongside Loki rather than picking one exclusively?
- [ ] Can you explain why a shared `request_id`/`trace_id` field logged on every line is what actually makes multi-service debugging tractable?
