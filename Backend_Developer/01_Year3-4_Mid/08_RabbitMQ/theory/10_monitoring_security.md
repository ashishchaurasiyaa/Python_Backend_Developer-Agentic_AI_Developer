# RabbitMQ — Monitoring & Security

## Part 1: Monitoring

---

## 1. Management UI (Built-in)

```
http://localhost:15672   (default: guest/guest)

Key tabs:
  Overview    → broker-wide message rates, node health
  Connections → active TCP connections + client info
  Channels    → per-channel publish/deliver rates, unacked count
  Exchanges   → exchange-level traffic
  Queues      → per-queue depth, consumers, message rates ← most used
  Admin       → users, vhosts, permissions
```

---

## 2. Key Metrics to Monitor (⭐⭐⭐⭐⭐)

| Metric | Healthy | Alert When |
|--------|---------|-----------|
| Queue depth (`messages`) | Near zero or stable | Growing continuously |
| Unacked messages | Low | High = slow/crashed consumers |
| Publish rate | Matches expected | Sudden drop = producer issue |
| Deliver rate | Matches publish rate | Lower = consumers lagging |
| Consumer count | > 0 | 0 = all consumers down |
| Memory used | < 70% of watermark | > 80% → alarm imminent |
| Disk free | > 2GB | < 2GB → disk alarm |
| Connection count | Expected | Sudden spike = connection leak |

---

## 3. Management HTTP API

```bash
# Overview — broker health
curl -u guest:guest http://localhost:15672/api/overview

# All queues + stats
curl -u guest:guest http://localhost:15672/api/queues

# Specific queue
curl -u guest:guest http://localhost:15672/api/queues/%2f/payment_queue

# Key fields in queue response:
# {
#   "name": "payment_queue",
#   "messages": 0,            ← queue depth
#   "messages_unacknowledged": 3,
#   "consumers": 2,           ← active consumers
#   "durable": true,
#   "message_stats": {
#     "publish_details": {"rate": 45.2},
#     "deliver_details": {"rate": 44.8},
#     "ack_details":     {"rate": 44.8}
#   }
# }
```

```python
import urllib.request, json, base64

def get_queue_depth(queue: str, vhost: str = "%2f") -> dict:
    auth = base64.b64encode(b"guest:guest").decode()
    req  = urllib.request.Request(
        f"http://localhost:15672/api/queues/{vhost}/{queue}",
        headers={"Authorization": f"Basic {auth}"},
    )
    with urllib.request.urlopen(req, timeout=5) as r:
        data = json.load(r)
        return {
            "depth":    data["messages"],
            "unacked":  data["messages_unacknowledged"],
            "consumers": data["consumers"],
        }
```

---

## 4. Prometheus + Grafana Integration

```bash
# RabbitMQ 3.8+ has built-in Prometheus endpoint
# Enable prometheus plugin:
rabbitmq-plugins enable rabbitmq_prometheus

# Scrape endpoint:
# http://localhost:15692/metrics

# Key Prometheus metrics:
# rabbitmq_queue_messages_total            ← queue depth per queue
# rabbitmq_queue_messages_unacked_total    ← unacked messages
# rabbitmq_queue_consumers                 ← consumer count
# rabbitmq_channel_messages_published_total ← publish rate
# rabbitmq_channel_messages_delivered_ack_total ← deliver rate
# rabbitmq_node_mem_used_bytes             ← broker memory
# rabbitmq_node_disk_free_bytes            ← disk space
```

```yaml
# prometheus.yml scrape config
scrape_configs:
  - job_name: "rabbitmq"
    static_configs:
      - targets: ["rabbitmq:15692"]
```

```
# Grafana Alerts (examples):
# Alert 1: queue depth
rabbitmq_queue_messages_total{queue="payment_queue"} > 1000

# Alert 2: no consumers
rabbitmq_queue_consumers{queue="payment_queue"} == 0

# Alert 3: high unacked (consumers stuck)
rabbitmq_queue_messages_unacked_total{queue="payment_queue"} > 500

# Alert 4: memory alarm
rabbitmq_node_mem_alarm == 1
```

---

## 5. CLI Commands

```bash
# Overall broker status
rabbitmqctl status

# List queues with depth
rabbitmqctl list_queues name messages consumers

# List connections (detect leaks)
rabbitmqctl list_connections name peer_host peer_port state

# List consumers
rabbitmqctl list_consumers

# List exchanges
rabbitmqctl list_exchanges name type durable

# Check cluster status (for multi-node)
rabbitmqctl cluster_status

# Purge a stuck queue (DESTRUCTIVE)
rabbitmqctl purge_queue payment_queue

# Close a misbehaving connection
rabbitmqctl close_connection "<conn-id>" "manual close"
```

---

## Part 2: Security

---

## 6. Authentication — Users

```bash
# Delete default guest user in production (it has full access, no network restrictions)
rabbitmqctl delete_user guest

# Create application-specific users
rabbitmqctl add_user app_user "strong_password_here"
rabbitmqctl set_user_tags app_user management    # management UI access

# Create separate monitoring user
rabbitmqctl add_user monitor_user "monitor_pass"
rabbitmqctl set_user_tags monitor_user monitoring  # read-only UI
```

---

## 7. Authorization — Permissions

```
Permission format: (configure, write, read)
configure: create/delete queues/exchanges
write:     publish messages
read:      consume messages

Principle of least privilege:
  Producer:  write only (no read, no configure)
  Consumer:  read only (no write, no configure)
  App setup: configure (for initial queue/exchange creation only)
```

```bash
# Give app_user write permission on /production vhost (producer)
rabbitmqctl set_permissions -p /production app_producer "^$" ".*" "^$"
#                                                configure  write  read

# Give consumer read permission
rabbitmqctl set_permissions -p /production app_consumer "^$" "^$" ".*"

# Give admin full access
rabbitmqctl set_permissions -p /production app_admin ".*" ".*" ".*"

# Verify
rabbitmqctl list_user_permissions app_producer
```

---

## 8. Virtual Hosts (Isolation)

```
RabbitMQ instance
  ├── /production    ← production exchanges/queues
  ├── /staging       ← staging exchanges/queues (same names, isolated)
  └── /development   ← dev environment

Benefits:
  - Complete namespace isolation (same queue name in different vhosts = different queues)
  - Separate user permissions per vhost
  - Independent resource management
```

```bash
# Create vhosts
rabbitmqctl add_vhost /production
rabbitmqctl add_vhost /staging

# Grant user access to specific vhost only
rabbitmqctl set_permissions -p /production app_user ".*" ".*" ".*"
rabbitmqctl set_permissions -p /staging    app_user ".*" ".*" ".*"
# app_user has NO access to /development by default
```

```python
# Connect to specific vhost
connection = pika.BlockingConnection(
    pika.ConnectionParameters(
        host="rabbitmq.internal",
        virtual_host="/production",
        credentials=pika.PlainCredentials("app_user", "strong_password"),
    )
)
```

---

## 9. TLS / SSL

```bash
# rabbitmq.conf
listeners.ssl.default = 5671      # TLS port (5672 = plaintext)

ssl_options.cacertfile   = /etc/rabbitmq/ca_certificate.pem
ssl_options.certfile     = /etc/rabbitmq/server_certificate.pem
ssl_options.keyfile      = /etc/rabbitmq/server_key.pem
ssl_options.verify       = verify_peer        # verify client cert
ssl_options.fail_if_no_peer_cert = true       # require mutual TLS
```

```python
import ssl, pika

ssl_context = ssl.create_default_context(cafile="/path/to/ca_certificate.pem")
ssl_context.load_cert_chain("/path/to/client_cert.pem", "/path/to/client_key.pem")

connection = pika.BlockingConnection(
    pika.ConnectionParameters(
        host="rabbitmq.internal",
        port=5671,
        ssl_options=pika.SSLOptions(ssl_context, "rabbitmq.internal"),
        credentials=pika.PlainCredentials("app_user", "password"),
    )
)
```

---

## 10. Credential Management

```python
# ❌ WRONG: hardcoded credentials
RABBITMQ_URL = "amqp://admin:password123@rabbitmq.internal/production"

# ✅ CORRECT: environment variables
import os
RABBITMQ_URL = os.environ["RABBITMQ_URL"]   # injected at deploy time

# ✅ BEST: secrets management (AWS Secrets Manager / Vault)
import boto3
secrets = boto3.client("secretsmanager").get_secret_value(SecretId="rabbitmq/prod")
creds = json.loads(secrets["SecretString"])
# { "username": "app_user", "password": "...", "host": "..." }
```

---

## 11. Security Checklist

```
□ Delete default 'guest' user before production
□ Create per-service users with least-privilege permissions
□ Use virtual hosts to isolate environments
□ Enable TLS (port 5671) for all connections in production
□ Management UI (15672) not exposed to internet — internal only
□ Rotate credentials regularly
□ Use secrets manager (not .env files) for credentials
□ AMQP plaintext port (5672) blocked at firewall for external traffic
□ Audit user permissions periodically (rabbitmqctl list_user_permissions)
□ Log failed auth attempts (rabbitmq_auth_backend_ldap / logs)
```

---

## 12. Interview Questions

**Q: RabbitMQ monitoring mein sabse important metric kaunsa hai?**
Queue depth + consumer count. Queue depth continuously badh rahi hai + consumer count 0 = critical alert. Publish rate vs deliver rate ka ratio dikhata hai ki consumers lag kar rahe hain ya nahi.

**Q: Production mein guest user kyun delete karte hain?**
Default guest user sirf localhost se connect kar sakta hai lekin credentials public knowledge hain. Production mein delete karo → per-service users banao with least privilege (producer: write only, consumer: read only).

**Q: Virtual host ka purpose kya hai?**
Environment isolation. `/production`, `/staging`, `/development` alag vhosts — same queue name dono mein exist kar sakta hai, completely isolated. Per-vhost permissions se service A production data access nahi kar sakti accidentally.

**Q: Prometheus + Grafana ke liye RabbitMQ kaise configure karein?**
`rabbitmq_prometheus` plugin enable karo → port 15692 pe `/metrics` endpoint available hota hai. Grafana alert: `rabbitmq_queue_messages_total > 1000` for queue depth, `rabbitmq_queue_consumers == 0` for dead consumers.
