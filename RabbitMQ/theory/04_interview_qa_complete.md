# RabbitMQ — Complete Interview Q&A
**All Levels | Senior Python Backend + Agentic AI**

---

## Quick Revision — 60 Second Summary

```
RabbitMQ = Message Broker
  Producer → Exchange → (Binding/Routing) → Queue → Consumer

Exchange Types:
  Direct  = exact routing_key match       → task routing
  Fanout  = broadcast ALL queues          → notifications
  Topic   = wildcard (* one word, # many) → logs, events
  Headers = header attributes match       → complex routing

Must Know:
  auto_ack=False → always production mein
  durable=True   → queue restart survive kare
  Persistent     → message restart survive kare
  DLX            → failed message → dead letter queue
  aio-pika       → FastAPI ke saath (async)
  prefetch_count → fair dispatch (1 = ek baar mein 1 message)
```

---

## Interview Questions & Answers

---

### Q1: RabbitMQ aur Kafka mein kya fark hai? Kab kya choose karo?

**Answer:**
```
┌────────────────────────────────────────────────────────────────┐
│ Feature          │ RabbitMQ              │ Kafka               │
├────────────────────────────────────────────────────────────────┤
│ Type             │ Message Broker        │ Event Streaming     │
│ Message Routing  │ Exchanges + Bindings  │ Topic Partitions    │
│ Message Deleted  │ Consume ke baad       │ Retain karta hai    │
│ Throughput       │ ~50k/sec              │ ~1M+/sec            │
│ Ordering         │ Queue level           │ Partition level     │
│ Replay           │ No (consumed = gone)  │ Yes (offset replay) │
│ Complexity       │ Medium                │ Higher              │
│ Use Case         │ Task queues, RPC      │ Event sourcing, logs│
└────────────────────────────────────────────────────────────────┘

Choose RabbitMQ when:
  ✅ Complex routing (Direct/Fanout/Topic exchanges)
  ✅ DLQ, Priority, TTL needed
  ✅ RPC pattern (request-reply)
  ✅ Per-message ACK/NACK control
  ✅ Microservices task distribution

Choose Kafka when:
  ✅ Event streaming + replay
  ✅ 1M+ messages/sec throughput
  ✅ Multiple consumers same event chahiye (consumer groups)
  ✅ Audit log, time-series events
  ✅ Event sourcing architecture
```

---

### Q2: Message kaise guarantee karo ki lost na ho?

**Answer:** 3 levels pe guarantee chahiye:

```python
# Level 1: Producer side — Publisher Confirms
channel.confirm_delivery()
# Broker se ACK aane ke baad hi "sent" maano

# Level 2: Queue side — Durable queue
channel.queue_declare(queue='important', durable=True)
# RabbitMQ restart pe queue survive kare

# Level 3: Message side — Persistent delivery
channel.basic_publish(
    ...,
    properties=pika.BasicProperties(
        delivery_mode=pika.DeliveryMode.Persistent  # disk pe save
    )
)

# Level 4: Consumer side — Manual ACK
def callback(ch, method, properties, body):
    try:
        process(body)
        ch.basic_ack(delivery_tag=method.delivery_tag)   # success
    except:
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)  # retry

channel.basic_consume(..., auto_ack=False)  # NEVER auto_ack=True in production
```

---

### Q3: basic_qos prefetch_count kya karta hai? Kyu zaruri hai?

**Answer:**
```
prefetch_count=0 (default):
  Worker ko unlimited messages ek saath de do
  Fast worker + slow worker = fast ko 1000 messages, slow ko 0
  Unbalanced ❌

prefetch_count=1:
  Worker ko ek baar mein sirf 1 message
  ACK karne ke baad hi next message milega
  Fair dispatch ✅ — har worker equally loaded

prefetch_count=10:
  Worker 10 messages buffer karta hai
  Better throughput — less broker round-trips
  Production: 5-20 recommended

Rule: 
  CPU-bound work → prefetch_count=1
  I/O-bound work → prefetch_count=5-20
```

```python
channel.basic_qos(prefetch_count=1)  # fair dispatch
```

---

### Q4: Dead Letter Queue kab use karo? Pattern explain karo?

**Answer:**
```
DLQ = 3 use cases:
  1. Consumer ne reject kiya (nack requeue=False)
  2. Message TTL expire ho gayi
  3. Queue overflow (x-max-length reached)

Pattern:
  main_queue (x-dead-letter-exchange=dlx)
      → fail → dlx → dead_letter_queue
                          → monitor/alert/retry/log

Real scenarios:
  ✅ Payment fail → DLQ → manual review + refund
  ✅ Email bounce → DLQ → mark user email invalid
  ✅ Invalid message → DLQ → developer alert
  ✅ Retry exhausted → DLQ → escalate to human
```

---

### Q5: RabbitMQ mein message ordering guarantee hai kya?

**Answer:**
```
Single Queue + Single Consumer = FIFO guaranteed ✅
Single Queue + Multiple Consumers = NOT guaranteed ❌
  → Worker 1 message 1 le gaya, Worker 2 message 2 le gaya
  → Worker 2 pehle finish kare → out of order

Strict ordering chahiye toh:
  Option 1: Single consumer only
  Option 2: Consistent Hash Exchange (same key → same queue/worker)
  Option 3: Application level ordering (sequence number)
  
Real world: Most cases ordering matter nahi karta
  (payment, email, notification — order se independent)
```

---

### Q6: aio-pika mein connection_robust kyun use karo?

**Answer:**
```python
# connect() — basic connection
connection = await aio_pika.connect("amqp://localhost/")
# Network drop → ConnectionError → crash ❌

# connect_robust() — auto-reconnect with backoff
connection = await aio_pika.connect_robust(
    "amqp://localhost/",
    reconnect_interval=5,    # 5 seconds retry
    heartbeat=60
)
# Network drop → internally retry → messages continue ✅
# Production ALWAYS use connect_robust
```

---

### Q7: RabbitMQ mein idempotency kaise handle karo?

**Answer:**
```
Problem: Network issue → producer same message 2 baar bhejta hai
         Consumer 2 baar process karta hai → duplicate order!

Solutions:

1. message_id + Database check
```
```python
def callback(ch, method, properties, body):
    message_id = properties.message_id
    
    # Already processed? Skip karo
    if redis.exists(f"processed:{message_id}"):
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return
    
    # Process karo
    process(body)
    
    # Mark as processed (TTL=24h)
    redis.setex(f"processed:{message_id}", 86400, "1")
    ch.basic_ack(delivery_tag=method.delivery_tag)
```

```
2. Database unique constraint
   → order_id UNIQUE → duplicate insert → IntegrityError → ack safely
```

---

### Q8: Topic Exchange mein * aur # kya hai? Example do?

**Answer:**
```
* = exactly ONE word replace karta hai
# = zero ya more words replace karta hai

Example routing keys: "service.action.region"

Pattern "order.*"       → order.placed ✅, order.failed ✅, order.placed.india ❌
Pattern "order.#"       → order.placed ✅, order.placed.india ✅, order ✅
Pattern "*.error"       → payment.error ✅, order.error ✅, system.critical.error ❌
Pattern "*.*.india"     → order.placed.india ✅, user.login.india ✅
Pattern "#.india"       → order.placed.india ✅, india ✅
Pattern "#"             → EVERYTHING ✅

Interview trick: * = one word ka placeholder, # = any words ka placeholder
```

---

### Q9: Production pe RabbitMQ kaise monitor karo?

**Answer:**
```
1. Management UI — http://localhost:15672
   → Queue lengths, message rates, consumers
   → Alerts set karo agar queue > 10000 messages

2. Prometheus + Grafana
   → rabbitmq_exporter → Prometheus → Grafana dashboard
   → Metrics: queue_messages, consumer_count, publish_rate

3. Health check endpoint
   → GET /api/healthchecks/node (Management API)
   → FastAPI health endpoint mein check karo

4. Key metrics to watch:
   → messages_ready       — queue mein waiting messages
   → messages_unacked     — consumer ne liya but ack nahi
   → consumer_utilisation — workers kitna busy hain
   → publish_rate         — messages per second
   → deliver_rate         — delivery rate

5. Alerts:
   → Queue depth > threshold → worker scale karo
   → DLQ messages > 0 → investigate
   → Consumer count = 0 → worker down alert
```

---

### Q10: FastAPI mein RabbitMQ correctly kaise integrate karo?

**Answer:**
```python
# CORRECT Pattern:
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: connect karo
    app.state.rabbitmq = await aio_pika.connect_robust("amqp://localhost/")
    app.state.channel  = await app.state.rabbitmq.channel()
    yield
    # Shutdown: close karo
    await app.state.channel.close()
    await app.state.rabbitmq.close()

app = FastAPI(lifespan=lifespan)

# Dependency injection se channel lo
async def get_channel(request: Request) -> aio_pika.Channel:
    return request.app.state.channel

@app.post("/orders")
async def create_order(order: OrderRequest, channel = Depends(get_channel)):
    await channel.default_exchange.publish(...)
    return {"status": "queued"}

# WRONG — har request pe new connection:
@app.post("/orders_bad")
async def bad_example(order: OrderRequest):
    conn = await aio_pika.connect(...)   # ❌ expensive! har request pe
    channel = await conn.channel()
    ...
```

---

## Complete Topics Checklist

```
✅ AMQP Protocol — Connection vs Channel
✅ Default Exchange
✅ Direct Exchange — exact routing
✅ Fanout Exchange — broadcast
✅ Topic Exchange — wildcard routing
✅ Headers Exchange — attribute routing
✅ Queue properties — durable, exclusive, auto-delete
✅ Message properties — delivery_mode, ttl, priority
✅ Manual ACK/NACK
✅ basic_qos prefetch_count
✅ Dead Letter Exchange (DLX) + DLQ
✅ Message TTL + Queue TTL
✅ Priority Queues
✅ Publisher Confirms
✅ Competing Consumers
✅ Retry with Exponential Backoff
✅ aio-pika (async)
✅ FastAPI integration (lifespan)
✅ RPC pattern (request-reply)
✅ RabbitMQ vs Kafka — when to use
✅ Idempotency handling
✅ Production monitoring
```
