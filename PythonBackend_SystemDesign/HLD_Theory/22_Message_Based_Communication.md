# Message-Based Communication — Queues, Pub-Sub, Kafka, RabbitMQ

## Quick Reference Card
```
Message Queue → Point-to-point — 1 producer, 1 consumer (FIFO tasks)
Pub-Sub       → 1 publisher, N subscribers — broadcast events
Kafka         → Distributed log — high throughput, replay, partitioned
RabbitMQ      → AMQP broker — routing, priority, dead letter queues
Celery        → Python task queue using RabbitMQ/Redis as broker
Interview hook → "Youngman: Celery+RabbitMQ for SAP sync | Niroskos: Redis Streams for booking events"
```

---

## PART 1: HINGLISH — Samjhne ke liye

### 1.1 Message-Based Communication Kya Hai?

**Analogy: Post office**

- **Message Queue**: Tum letter box mein letter daalte ho (enqueue). Ek postman (consumer) uthata hai, deliver karta hai. Done.
- **Pub-Sub**: Newspaper subscription — ek publisher prints, sabhi subscribers ko mile (broadcast). Publisher ko subscribers ki count nahi maloom.
- **Kafka**: Super post office — every letter archived 7 din tak. Koi bhi consumer purana letter dobara padh sakta hai. Letters sorted by geography (partitions).

```
MESSAGE QUEUE (Point-to-Point):
  Producer → [Queue: Task1, Task2, Task3] → Consumer 1 (takes Task1)
                                          → Consumer 2 (takes Task2)
                                          → Consumer 1 (takes Task3)
  
  Each message → consumed by EXACTLY ONE consumer
  Use: Task distribution, work queue

PUB-SUB (Broadcast):
  Publisher → [Topic: "booking_created"] → Subscriber 1 (Email service)
                                         → Subscriber 2 (SMS service)
                                         → Subscriber 3 (Analytics service)
  
  Each message → consumed by ALL subscribers
  Use: Event broadcasting, microservices events

KAFKA (Distributed Log):
  Producers → [Partition 0: msg1, msg4, msg7]  → Consumer Group A
           → [Partition 1: msg2, msg5, msg8]  → Consumer Group B (reread!)
           → [Partition 2: msg3, msg6, msg9]  
  
  Messages retained for 7 days (default)
  Multiple consumer groups read independently
  Use: High-throughput event streaming, replayable
```

---

### 1.2 Message Queue — Deep Dive

```
WHY MESSAGE QUEUE?

Without queue:
  User creates booking → API calls Email Service → Email Service DOWN!
  Booking fails because email fails — WRONG! Unrelated services fail together!

With queue:
  User creates booking → API enqueues "send email" → 200 OK immediately
  Email Service processes message when it comes back online
  Booking and email are DECOUPLED!

PROPERTIES:
  1. Durability: Message persists even if consumer crashes
  2. Reliability: At-least-once delivery (can set exactly-once)
  3. Load leveling: Queue absorbs spikes → consumer processes steadily
  4. Decoupling: Producer and consumer don't need to be running simultaneously
  5. Priority: High-priority messages processed first

QUEUE TYPES:
  Standard: No ordering guarantee (higher throughput)
  FIFO: First-In-First-Out (lower throughput, ordered)
  Priority Queue: Higher priority dequeued first
  Dead Letter Queue (DLQ): Failed messages sent here for inspection

CELERY QUEUE EXAMPLE:
  CELERY_TASK_ROUTES = {
      'tasks.push_to_sap': {'queue': 'sap'},         # SAP integration queue
      'tasks.send_email': {'queue': 'notifications'}, # Email/SMS queue
      'tasks.generate_pdf': {'queue': 'heavy'},       # Heavy tasks queue
  }
  
  # Start workers for specific queues:
  # celery worker -Q sap --concurrency 3      # 3 workers for SAP
  # celery worker -Q notifications --concurrency 5  # 5 for notifications
  # celery worker -Q heavy --concurrency 1    # 1 for heavy tasks (resource limit)
```

---

### 1.3 Pub-Sub Pattern

```
PUB-SUB:
  Publisher: "booking_created" event published
  
  Subscribers (all receive same event):
  1. Email Service: Send confirmation email
  2. SMS Service: Send booking SMS
  3. Analytics: Record booking stats
  4. Inventory Service: Reduce available seats
  5. SAP Service: Create SAP booking entry
  
  Publisher knows NOTHING about subscribers
  Subscribers register their interest in topic

  ┌─────────────────────────────────────────────────────────────┐
  │                      Message Broker                          │
  │  Topic: "booking_created"                                   │
  │  ├── Queue A → Email Service worker                         │
  │  ├── Queue B → SMS Service worker                           │
  │  ├── Queue C → Analytics worker                             │
  │  └── Queue D → SAP Service worker                           │
  └─────────────────────────────────────────────────────────────┘
                    ↑
               Publisher (Booking API)

DJANGO SIGNALS = Pub-Sub (in-process):
  @receiver(post_save, sender=Booking)
  def on_booking_created(sender, instance, created, **kwargs):
      if created:
          # These are "subscribers" to booking creation event
          send_confirmation_email.delay(instance.id)  # Subscriber 1
          send_sms_confirmation.delay(instance.id)    # Subscriber 2
          update_analytics.delay(instance.id)         # Subscriber 3
  
  # Limitation: Signal subscribers run in-process — don't span microservices
  # For microservices: Use Kafka/RabbitMQ topic

REDIS PUB-SUB (simple, no persistence):
  # Publisher:
  redis.publish('booking_events', json.dumps({'booking_id': 123, 'event': 'created'}))
  
  # Subscriber:
  pubsub = redis.pubsub()
  pubsub.subscribe('booking_events')
  for message in pubsub.listen():
      handle_booking_event(message['data'])
  
  WARNING: Redis pub-sub = fire and forget
  If subscriber is down when message published → MESSAGE LOST!
  Use Redis Streams for persistence
```

---

### 1.4 Apache Kafka

```
KAFKA CONCEPTS:

  Broker:    Kafka server (usually 3+ in cluster)
  Topic:     Named log (like a category/channel)
  Partition: Topic split into N partitions (parallelism)
  Offset:    Position of message in partition (0, 1, 2...)
  Producer:  Writes messages to topic
  Consumer:  Reads messages from topic
  Consumer Group: Group of consumers sharing a topic's load
  
  ┌─────────────────────────────────────────────────────────────┐
  │                     Topic: "bookings"                        │
  │  Partition 0: [msg0][msg3][msg6][msg9]  offset → 0,3,6,9  │
  │  Partition 1: [msg1][msg4][msg7]        offset → 1,4,7      │
  │  Partition 2: [msg2][msg5][msg8]        offset → 2,5,8      │
  └─────────────────────────────────────────────────────────────┘
         ↑                                           ↓
    Producer writes                        Consumer reads
    
  Consumer Group A: Each partition → 1 consumer
    → Consumer 1: Reads Partition 0
    → Consumer 2: Reads Partition 1
    → Consumer 3: Reads Partition 2
  
  Consumer Group B: Independently reads same partitions
    → Same messages, different offsets tracked separately

KEY FEATURES:
  1. Message Retention: Default 7 days — messages stay regardless of consumption
  2. Replayability: Consumer can reset offset → re-read old messages
  3. High Throughput: 1M+ messages/second per broker
  4. Ordering: Guaranteed within a partition (not across partitions)
  5. Exactly-once semantics: With transactions
  6. Log compaction: Keep latest value per key indefinitely

PARTITION KEY:
  How to decide which partition?
  producer.send(topic, key=user_id, value=event_data)
  → hash(key) % num_partitions = partition number
  → Same user_id → always same partition → ORDER GUARANTEED per user

USE CASES:
  ✓ Event streaming (user activity, clickstream)
  ✓ Log aggregation (centralized logging)
  ✓ Real-time analytics pipelines
  ✓ Change Data Capture (DB changes → Kafka)
  ✓ Microservices event bus
  ✓ Stream processing (Kafka Streams, Flink)
```

---

### 1.5 RabbitMQ

```
RABBITMQ CONCEPTS:
  Producer: Sends messages
  Exchange: Routes messages to queues based on rules
  Queue: Stores messages
  Consumer: Reads from queue
  Binding: Connection between exchange and queue with routing key
  
  ┌──────────┐  message   ┌──────────┐  routing   ┌──────────┐
  │ Producer │ ─────────► │ Exchange │ ─────────► │  Queue   │ → Consumer
  └──────────┘            └──────────┘            └──────────┘

EXCHANGE TYPES:
  Direct:  routing_key = queue_binding_key
           "sap.invoice" → SAP Queue
           "email.invoice" → Email Queue
  
  Topic:   Pattern matching (* = 1 word, # = multiple words)
           "booking.*.created" → matches "booking.tour.created"
           "booking.#" → matches all booking events
  
  Fanout:  Broadcast to ALL bound queues
           Used for pub-sub
  
  Headers: Route by message header values

DEAD LETTER EXCHANGE (DLX):
  Message rejected 3 times → routed to Dead Letter Queue
  Ops team inspects failed messages
  Can replay from DLQ after fixing issue
  
  # In RabbitMQ setup via Celery:
  CELERY_TASK_QUEUES = (
      Queue('default', 
            Exchange('default'), 
            routing_key='default',
            queue_arguments={
                'x-dead-letter-exchange': 'dead_letters',
                'x-message-ttl': 86400000  # 24hr message TTL
            }),
  )

ACKNOWLEDGMENTS:
  auto-ack: Message deleted from queue when delivered to consumer
            (risky: consumer crashes before processing → message lost)
  
  manual-ack: Consumer explicitly ACKs after processing
              (Celery default: CELERY_TASK_ACKS_LATE = True)
              If consumer crashes → message requeued → another consumer picks it up!
```

---

### 1.6 Kafka vs RabbitMQ vs Redis Queue

```
                    KAFKA           RABBITMQ        REDIS (as queue)
                    ─────────────────────────────────────────────────
Model               Distributed log  Message broker  In-memory queue
Message retention   Days/weeks       Until consumed   Until consumed
                                     (or TTL)         (or TTL)
Throughput          Millions/sec     ~100K/sec        ~1M/sec (simple)
Ordering            Per partition    Per queue        List order
Replay messages     Yes (offset)     No               No
Consumer groups     Yes              No (competing    No
                                     consumers)
Delivery guarantee  At-least-once    At-least-once    At-most-once
                    Exactly-once     (with acks)      (fire-forget)
                    (with txns)
Use case            Event streaming  Task queue       Simple queue,
                    High throughput  Complex routing  small scale
                    Real-time pipel  Microservices    Celery broker
Persistence         Yes (disk)       Yes (disk)       Configurable
                                                      (AOF/RDB)
Best for            LinkedIn scale   Enterprise apps  Startups,
                    CDC, logs        Complex routing  Celery, cache

Celery + RabbitMQ:  Production standard for Python task queues
Celery + Redis:     Simpler setup, good for small-medium scale
Kafka:              When you need replay, high throughput, event streaming
```

---

### 1.7 Exactly-Once vs At-Least-Once vs At-Most-Once

```
AT-MOST-ONCE (fire and forget):
  Message sent, not confirmed
  If network fails → message lost
  Use: Logging, metrics (losing a few is ok)
  Redis pub-sub default behavior

AT-LEAST-ONCE (with ACK):
  Consumer processes, sends ACK
  If ACK lost → broker resends → consumer processes AGAIN
  Duplicate processing possible → need idempotent consumer
  Use: Most task queues (Celery with acks_late)
  
  Idempotent consumer:
  @shared_task
  def process_payment(payment_id):
      # Check if already processed (deduplication)
      if Payment.objects.filter(id=payment_id, processed=True).exists():
          return  # Already done — safe to skip duplicate
      
      # Process...
      Payment.objects.filter(id=payment_id).update(processed=True)

EXACTLY-ONCE:
  Each message processed exactly once
  Achieved via: distributed transactions, idempotent consumers + dedup
  Kafka supports exactly-once with transactions (complex)
  Use: Financial transactions, inventory updates
  
  Most production systems use: AT-LEAST-ONCE + IDEMPOTENCY
  (Simpler than exactly-once, same effective result)
```

---

### 1.8 Ashish ke projects mein

```python
# Youngman — Celery + RabbitMQ (or Redis)

QUEUES:
  'sap': SAP HANA integration tasks
    - push_invoice_to_sap
    - push_customer_to_sap
    - sync_payments_from_sap
  
  'notifications': Email + SMS tasks
    - send_invoice_email
    - send_payment_reminder
  
  'reports': Heavy computation
    - generate_monthly_report
    - reconcile_payments
  
  'default': Everything else

# Celery Beat (scheduled tasks — like cron):
CELERY_BEAT_SCHEDULE = {
    'sap-morning-sync': {
        'task': 'tasks.bulk_sap_sync',
        'schedule': crontab(hour=6, minute=0),  # 6 AM daily
    },
    'check-overdue-invoices': {
        'task': 'tasks.check_overdue',
        'schedule': crontab(hour='*/6'),  # Every 6 hours
    },
}

# Monitoring: Celery Flower
# Access: http://flower.youngman.internal:5555
# Shows: Queue depth, task success/failure, worker status

# Niroskos — Redis Streams for booking events (lightweight Kafka)
# Redis Streams = persistent pub-sub (messages don't disappear)

import redis

def publish_booking_event(booking_id, event_type, data):
    r = redis.Redis()
    r.xadd(
        'booking_events',
        {
            'booking_id': str(booking_id),
            'event_type': event_type,
            'data': json.dumps(data),
            'timestamp': str(timezone.now())
        }
    )

# Consumer:
def consume_booking_events():
    r = redis.Redis()
    last_id = '0'  # Start from beginning (or store in Redis for resuming)
    
    while True:
        messages = r.xread({'booking_events': last_id}, block=5000)  # Block 5sec
        for stream, msgs in messages:
            for msg_id, data in msgs:
                process_booking_event(data)
                last_id = msg_id  # Track progress
```

---

## PART 2: ENGLISH — Interviewer ko bolne ke liye

### 2.1 Definitions

> **Message Queue**: An asynchronous communication pattern where producers enqueue messages and consumers dequeue and process them. Messages are consumed by exactly one consumer. Provides decoupling, load leveling, and reliability.

> **Pub-Sub (Publish-Subscribe)**: A messaging pattern where publishers broadcast messages to a topic, and all subscribers receive them. Publishers and subscribers are decoupled — neither knows about the other.

> **Apache Kafka**: A distributed event streaming platform built as an immutable append-only log. Messages are retained for configurable duration, allowing replay. Supports multiple consumer groups independently reading the same stream.

---

### 2.2 Message Queue vs Pub-Sub vs Stream

| Feature | Message Queue | Pub-Sub | Kafka Streams |
|---------|--------------|---------|---------------|
| Delivery | One consumer | All subscribers | Per consumer group |
| Persistence | Until consumed | No (or short) | Configurable (days) |
| Replay | No | No | Yes (by offset) |
| Ordering | FIFO (same queue) | No guarantee | Per partition |
| Scale | Per queue | Per topic | Partition-level |
| Example | Celery, SQS | Redis pub-sub, SNS | Apache Kafka |
| Best for | Task distribution | Event fanout | Event sourcing, CDC |

---

### 2.3 Real Project Answer

> "In Youngman, we use Celery with RabbitMQ (or Redis) as our task queue. The pattern is: Django view creates the DB record synchronously, then fires Celery tasks for everything slow: SAP push, PDF generation, email sending. We have separate Celery queues for different task types — SAP integration, notifications, heavy computation — allowing us to scale workers independently. Tasks that fail retry up to 3 times with exponential backoff; after exhausting retries, they go to a dead letter queue that our ops team monitors. Celery Beat handles scheduled tasks — daily SAP sync, overdue invoice checks every 6 hours. For Niroskos, Django signals act as an in-process pub-sub — booking creation signals trigger tasks for email, SMS, search index update, and SAP sync."

---

### 2.4 Common Follow-up Q&A

**Q1: What is the difference between Kafka and RabbitMQ?**
> "Fundamentally different mental models. RabbitMQ is a message broker: it routes messages from producers to consumers, consumers acknowledge receipt, and messages are typically deleted after consumption. It's designed for task distribution and complex routing. Kafka is a distributed log: messages are appended to partitions and retained for days. Multiple consumer groups independently read the same messages. Kafka excels at high-throughput event streaming, replaying history, and powering analytics pipelines. For Celery-style task queues: RabbitMQ or Redis. For event streaming, CDC, or when replay matters: Kafka."

**Q2: How do you handle message ordering in distributed systems?**
> "Strict global ordering across all producers and consumers is very hard and expensive. Practical approach: ordering per entity, not globally. In Kafka, same partition key (e.g., user_id or booking_id) always routes to same partition. Within a partition, messages are strictly ordered. A consumer for partition 0 processes all messages for user group 0 in order. This gives you per-entity ordering at scale — booking events for booking#123 are always processed in order, even if booking#456's events interleave. For RabbitMQ: single queue + single consumer = FIFO. Multiple consumers = no ordering guarantee."

**Q3: What is backpressure in message queues?**
> "Backpressure is when consumers can't keep up with producers — the queue grows unboundedly. Left unchecked: memory exhaustion, disk fill, system crash. Solutions: (1) Rate limiting producers — throttle message production when queue depth exceeds threshold. (2) Add more consumers — horizontal scale consumer workers. (3) Consumer timeout / circuit breaker — if a downstream service is slow, stop accepting work rather than queuing indefinitely. Kafka handles this naturally — producers block if the broker's buffer is full. In Celery, monitor queue depth via Flower — when queue grows rapidly, add workers. Alert threshold: queue depth > 10x average processing rate × average task duration."

---

## Interview Cheat Sheet

```
Message Queue (Point-to-Point):
  1 producer → queue → 1 consumer
  Each message consumed once
  Use: Task distribution (Celery)

Pub-Sub:
  1 publisher → topic → N subscribers (all get it)
  Use: Event broadcasting, microservices events
  Django Signals = in-process pub-sub

Kafka:
  Distributed persistent log
  Key features: retention, replay, partitions, consumer groups
  Partition key → same key → same partition → ordered per key
  Use: High throughput, event streaming, CDC, analytics

RabbitMQ:
  AMQP broker with routing (Direct, Topic, Fanout, Headers)
  Dead Letter Exchange for failed messages
  Manual ACK for reliability
  Use: Celery broker, complex routing, enterprise

Delivery guarantees:
  At-most-once: Fire and forget (Redis pub-sub)
  At-least-once: ACK + retry (Celery default)
  Exactly-once: Deduplication + idempotency

Idempotency pattern:
  Check if already processed before processing
  if already_done: return early

My setup:
  Celery + RabbitMQ: SAP push, PDF gen, emails
  Queues: sap, notifications, reports, default
  Dead Letter Queue: Failed tasks after 3 retries
  Celery Beat: Scheduled jobs (daily SAP sync, overdue checks)
  Django Signals: In-process pub-sub for model events
```
