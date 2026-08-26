# Flow Control & Backpressure — RabbitMQ

## 1. The Problem

```
Producer:   10,000 msg/sec → RabbitMQ broker
Consumer:    1,000 msg/sec ← RabbitMQ broker

Queue depth growing: +9,000 msg/sec
After 1 hour:        32,400,000 messages in queue

Consequences:
  → Broker RAM exhausted → memory alarm → publisher BLOCKED
  → Disk fills up (if persistent) → disk alarm → publisher BLOCKED
  → Latency for consumers spikes (messages waiting hours)
  → Eventual broker crash / OOM kill
```

---

## 2. RabbitMQ Memory Alarm

When broker hits `vm_memory_high_watermark` (default 40% of RAM):

```
Producer publishes → broker BLOCKS the connection (TCP backpressure)
Producer's channel.basic_publish() hangs (doesn't error, just blocks)
Consumer processing continues normally → queue drains
Once memory drops below watermark → producer UNBLOCKED automatically

# rabbitmq.conf
vm_memory_high_watermark.relative = 0.4     # block at 40% RAM
vm_memory_high_watermark.absolute = 6GB     # or absolute

# Check current status
rabbitmqctl status | grep memory
```

```python
# Producers must handle blocking — set a timeout or use async
connection = pika.BlockingConnection(
    pika.ConnectionParameters(
        host="localhost",
        blocked_connection_timeout=300,   # 5 min max block → ConnectionBlockedTimeout
    )
)
```

---

## 3. Disk Alarm

```
free_disk_space < disk_free_limit → all publishers blocked

# rabbitmq.conf
disk_free_limit.absolute = 2GB       # block when < 2GB free
disk_free_limit.relative = 1.0       # or 1× RAM free

# Monitor
rabbitmqctl status | grep disk
```

---

## 4. x-max-length (Queue Length Limit)

Cap the queue size. Old messages dropped (or dead-lettered) when limit exceeded.

```python
channel.queue_declare(
    queue="bounded_queue",
    arguments={
        "x-max-length":          10000,          # max 10k messages
        "x-overflow":            "drop-head",    # drop OLDEST when full
        # "x-overflow":          "reject-publish", # or reject new publishes
        "x-dead-letter-exchange": "overflow_dlx", # optional: route dropped msgs
    },
    durable=True,
)
```

| x-overflow | Behaviour |
|------------|-----------|
| `drop-head` (default) | Oldest message dropped when queue full |
| `reject-publish` | Publisher gets basic.return (if mandatory) or silent drop |
| `reject-publish-dlx` | Rejected message goes to DLX |

---

## 5. Consumer Prefetch — The Primary Knob

Prefetch = max unacked messages a consumer can hold at once.

```
prefetch_count=0 (unlimited):
  Consumer A grabs ALL 10,000 queued messages → RAM spike in consumer
  Consumer B, C, D → get nothing → idle

prefetch_count=1 (fair dispatch):
  Consumer A picks 1 → processes → ACKs → picks next
  Consumer B, C, D equally share remaining messages
  Throughput lower but fair

prefetch_count=10 (balanced):
  Each consumer holds up to 10 in-flight → better throughput than prefetch=1
  Still prevents one consumer hoarding all messages

Production rule: start with prefetch=10, tune based on consumer speed
```

```python
# Per-consumer prefetch (most common)
channel.basic_qos(prefetch_count=10, global_qos=False)

# Per-channel prefetch (total across all consumers on this channel)
channel.basic_qos(prefetch_count=100, global_qos=True)
```

---

## 6. Throttling the Producer

When consumers are slower than producers, slow down the producer.

### Option 1: Rate limiter on producer side

```python
import time

class RateLimitedPublisher:
    def __init__(self, channel, max_per_sec: int):
        self.channel     = channel
        self.interval    = 1.0 / max_per_sec
        self.last_publish = 0.0

    def publish(self, exchange, routing_key, body, properties=None):
        now     = time.monotonic()
        elapsed = now - self.last_publish
        if elapsed < self.interval:
            time.sleep(self.interval - elapsed)
        self.channel.basic_publish(
            exchange=exchange, routing_key=routing_key,
            body=body, properties=properties,
        )
        self.last_publish = time.monotonic()


publisher = RateLimitedPublisher(channel, max_per_sec=1000)
```

### Option 2: Check queue depth before publishing

```python
import urllib.request, base64, json

def queue_depth(queue_name: str) -> int:
    auth = base64.b64encode(b"guest:guest").decode()
    req  = urllib.request.Request(
        f"http://localhost:15672/api/queues/%2f/{queue_name}",
        headers={"Authorization": f"Basic {auth}"},
    )
    with urllib.request.urlopen(req, timeout=3) as r:
        return json.load(r)["messages"]

def publish_with_backpressure(channel, queue, body, max_depth=5000):
    while queue_depth(queue) > max_depth:
        print(f"Queue too deep — waiting... ({queue_depth(queue)} messages)")
        time.sleep(1)
    channel.basic_publish(exchange="", routing_key=queue, body=body)
```

### Option 3: Mandatory flag — detect if queue is full

```python
channel.confirm_delivery()
try:
    channel.basic_publish(
        exchange="main_exchange",
        routing_key="tasks",
        body=body,
        mandatory=True,     # raise UnroutableError if no queue bound
        properties=pika.BasicProperties(delivery_mode=2),
    )
except pika.exceptions.UnroutableError:
    # No queue bound or full → handle by queuing locally or discarding
    local_queue.append(body)
```

---

## 7. Scaling Consumers to Match Producer Rate

```
Producer: 10,000 msg/sec
Consumer: 1,000 msg/sec each

Required consumers: ceil(10,000 / 1,000) = 10

But: adding consumers has limits
  → DB connection pool exhaustion (10 consumers × 5 pool = 50 connections)
  → External API rate limits (10 consumers × 100 req/sec = 1000 req/sec > limit)

Scale computation:
  consumers_needed = producer_rate / (consumer_rate × efficiency)
  DB connections = consumers × db_pool_size ≤ postgres max_connections
```

```bash
# Scale consumers horizontally
# Each instance runs one consumer process
# Kubernetes HPA based on queue depth (KEDA):

apiVersion: keda.sh/v1alpha1
kind: ScaledObject
spec:
  triggers:
    - type: rabbitmq
      metadata:
        queueName: payment_queue
        queueLength: "50"   # scale up pod if queue > 50 messages per pod
```

---

## 8. Lazy Queues (Memory → Disk)

For queues that can grow large, use lazy mode to keep messages on disk instead of RAM.

```python
channel.queue_declare(
    queue="large_report_queue",
    arguments={"x-queue-mode": "lazy"},   # RabbitMQ 3.6+
    durable=True,
)
# Messages written to disk immediately instead of RAM
# Lower memory usage, slightly higher latency
# RabbitMQ 3.12+: all queues default to lazy behavior
```

---

## 9. Backpressure Architecture Pattern

```
              [Upstream Service]
                     │
                rate_limit(1000/sec)  ← Option 1: throttle producer
                     │
              [RabbitMQ Broker]
              x-max-length=50,000     ← Option 2: cap queue
              memory watermark=40%    ← Option 3: broker self-protects
                     │
              prefetch_count=10       ← Option 4: limit consumer in-flight
                     │
              [Consumer Workers × N]  ← Option 5: scale consumers
                     │
              [Downstream DB/API]
              connection pool limits  ← watch this when scaling consumers
```

---

## 10. Interview Questions

**Q: Producer 10,000 msg/sec, consumer 1,000 msg/sec — kya karoge?**
Primary: scale consumers to 10 (maar DB connections track karo). Secondary: `x-max-length` pe queue cap lagao overflow ke liye. Producer side mein rate limiter add karo. RabbitMQ memory alarm automatically block karega producers agar broker overloaded ho.

**Q: Memory alarm kya hai? Kab trigger hota hai?**
Broker ka RAM usage `vm_memory_high_watermark` (default 40%) cross kare toh ALL publishers block ho jaate hain (TCP level pe). Consumer processing continue karta hai. Queue drain hone pe unblock. Fix: `vm_memory_high_watermark` badao, ya lazy queues use karo (disk pe store).

**Q: prefetch=0 vs prefetch=1 — kya fark?**
prefetch=0 (unlimited): consumer saare messages grab kar leta hai — fair dispatch nahi, dusre consumers idle. prefetch=1: ek message at a time — perfectly fair but lower throughput. Production: prefetch=10-50 good balance hai.

**Q: Queue infinite grow ho rahi hai — kaise rokein?**
`x-max-length` + `x-overflow=reject-publish` → new publishes reject hone lagte hain jab queue full ho. Ya `drop-head` → purane messages drop. Long-term fix: consumer scaling.
