# RabbitMQ — DLX, TTL, Priority Queues & Publisher Confirms
**Intermediate Level | Theory + Interview Q&A**

---

## Quick Concepts
- **DLX (Dead Letter Exchange)** = Failed/rejected/expired messages kahan jaate hain
- **DLQ (Dead Letter Queue)** = DLX se connected queue — failed messages yahan aate hain
- **TTL (Time To Live)** = Message ya Queue ka expiry time
- **Priority Queue** = Higher priority messages pehle process hote hain (0-255)
- **Publisher Confirms** = Broker ne message receive kiya — guarantee
- **Nack** = Negative Acknowledgment — message reject karna
- **Requeue** = Rejected message wapas queue mein daalna

---

## Interview Questions & Answers

---

### Q1: Dead Letter Exchange (DLX) kya hai? Kab message dead letter hota hai?

**Answer:**
Message **3 cases** mein dead letter hota hai:
```
1. basic_nack(requeue=False) — Consumer ne reject kiya
2. Message TTL expire ho gayi — queue mein bahut der se pada hai
3. Queue full ho gayi — x-max-length limit reach ho gayi
```

```
Normal Flow:
Producer → Exchange → work_queue → Consumer (process karta hai)
                                        ↓ fail ho gaata hai
Dead Letter Flow:
Consumer nack karta hai (requeue=False)
          ↓
work_queue → DLX (dead_letter_exchange) → dead_letter_queue
                                                ↓
                                    Monitoring / Retry / Alert
```

**Setup:**
```python
import pika, json, time

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()

# Step 1: DLX aur DLQ pehle banao
channel.exchange_declare(
    exchange='dlx_exchange',
    exchange_type='direct',
    durable=True
)
channel.queue_declare(queue='dead_letter_queue', durable=True)
channel.queue_bind(
    exchange='dlx_exchange',
    queue='dead_letter_queue',
    routing_key='dead'
)

# Step 2: Main queue banao — DLX attach karo
channel.queue_declare(
    queue='order_processing_queue',
    durable=True,
    arguments={
        'x-dead-letter-exchange': 'dlx_exchange',   # fail → yahaan jaao
        'x-dead-letter-routing-key': 'dead',          # DLQ ka routing key
        'x-message-ttl': 60000,                        # 60 sec mein expire
        'x-max-length': 1000                           # max 1000 messages
    }
)

# Step 3: Message publish karo
order = {"order_id": 101, "item": "Laptop", "price": 75000}
channel.basic_publish(
    exchange='',
    routing_key='order_processing_queue',
    body=json.dumps(order),
    properties=pika.BasicProperties(delivery_mode=pika.DeliveryMode.Persistent)
)
print("Order message sent!")
connection.close()
```

**Consumer with intentional failure (DLQ trigger):**
```python
def order_callback(ch, method, properties, body):
    data = json.loads(body)
    print(f"Processing order: {data['order_id']}")

    try:
        if data['price'] > 50000:   # simulate validation failure
            raise ValueError(f"Price too high: {data['price']}")
        print(f"Order {data['order_id']} processed successfully!")
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        print(f"Order failed: {e} → Sending to DLQ")
        ch.basic_nack(
            delivery_tag=method.delivery_tag,
            requeue=False   # False = DLX ko bhejo, True = wapas queue mein
        )

channel.basic_qos(prefetch_count=1)
channel.basic_consume(
    queue='order_processing_queue',
    on_message_callback=order_callback,
    auto_ack=False
)
channel.start_consuming()
```

**DLQ Consumer (monitoring/alerting):**
```python
def dlq_callback(ch, method, properties, body):
    data = json.loads(body)
    print(f"⚠️  DEAD LETTER RECEIVED: {data}")
    # Alert bhejo — Slack/Email/PagerDuty
    # Database mein log karo
    # Manual review ke liye store karo
    ch.basic_ack(delivery_tag=method.delivery_tag)

channel.basic_consume(
    queue='dead_letter_queue',
    on_message_callback=dlq_callback,
    auto_ack=False
)
channel.start_consuming()
```

---

### Q2: Message Retry with Exponential Backoff — DLX pattern kaise karo?

**Answer:**
**Pattern:** Failed message → wait queue (TTL) → original queue → retry

```
attempt 1 fail → wait 5 sec → retry
attempt 2 fail → wait 10 sec → retry
attempt 3 fail → wait 20 sec → retry
attempt 4 fail → permanent DLQ (give up)
```

```python
import pika, json, time

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()

# 1. Final DLQ — permanent failures
channel.exchange_declare(exchange='final_dlx', exchange_type='direct', durable=True)
channel.queue_declare(queue='permanent_failures', durable=True)
channel.queue_bind(exchange='final_dlx', queue='permanent_failures', routing_key='failed')

# 2. Main work queue
channel.exchange_declare(exchange='work_exchange', exchange_type='direct', durable=True)
channel.queue_declare(
    queue='email_queue',
    durable=True,
    arguments={
        'x-dead-letter-exchange': 'retry_exchange',  # fail → retry exchange
    }
)
channel.queue_bind(exchange='work_exchange', queue='email_queue', routing_key='email')

# 3. Retry queue (with TTL — wait karo phir wapas original queue)
channel.exchange_declare(exchange='retry_exchange', exchange_type='direct', durable=True)
channel.queue_declare(
    queue='email_retry_queue',
    durable=True,
    arguments={
        'x-dead-letter-exchange': 'work_exchange',  # TTL expire → wapas original
        'x-dead-letter-routing-key': 'email',
        'x-message-ttl': 5000,   # 5 second wait (exponential increase karo)
    }
)
channel.queue_bind(exchange='retry_exchange', queue='email_retry_queue', routing_key='email')

# Producer
def send_email_task(to_email: str, subject: str, retry_count: int = 0):
    message = {
        'to': to_email,
        'subject': subject,
        'retry_count': retry_count
    }
    channel.basic_publish(
        exchange='work_exchange',
        routing_key='email',
        body=json.dumps(message),
        properties=pika.BasicProperties(delivery_mode=pika.DeliveryMode.Persistent)
    )
    print(f"Email task queued (attempt {retry_count + 1}): {to_email}")

send_email_task('user@test.com', 'Welcome!')

# Consumer with retry logic
MAX_RETRIES = 3

def email_callback(ch, method, properties, body):
    data = json.loads(body)
    retry_count = data.get('retry_count', 0)

    print(f"Processing email (attempt {retry_count + 1}): {data['to']}")

    try:
        # Simulate failure
        if retry_count < MAX_RETRIES:
            raise ConnectionError("Email server not responding")
        print(f"Email sent to {data['to']}!")
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        if retry_count >= MAX_RETRIES:
            print(f"Max retries reached — sending to permanent DLQ")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        else:
            print(f"Attempt {retry_count + 1} failed — retry after delay")
            data['retry_count'] = retry_count + 1
            # Updated retry count ke saath naya message bhejo
            ch.basic_publish(
                exchange='retry_exchange',
                routing_key='email',
                body=json.dumps(data),
                properties=pika.BasicProperties(delivery_mode=pika.DeliveryMode.Persistent)
            )
            ch.basic_ack(delivery_tag=method.delivery_tag)  # original ack karo

channel.basic_qos(prefetch_count=1)
channel.basic_consume(queue='email_queue', on_message_callback=email_callback, auto_ack=False)
channel.start_consuming()
```

---

### Q3: Message TTL aur Queue TTL kya hai?

**Answer:**
```
Message TTL = specific message kitni der tak queue mein rehe
              → per-message ya queue level pe set kar sakte hain

Queue TTL   = queue mein koi consumer nahi → kitni der baad delete ho
              → Temporary queues ke liye (RPC, temporary subscriptions)
```

```python
# Method 1: Queue level TTL — saare messages pe apply hota hai
channel.queue_declare(
    queue='limited_offers',
    durable=True,
    arguments={
        'x-message-ttl': 3600000,  # 1 hour = 3600000 milliseconds
    }
)

# Method 2: Per-message TTL — specific message pe apply karo
channel.basic_publish(
    exchange='',
    routing_key='limited_offers',
    body='Flash sale 50% off!',
    properties=pika.BasicProperties(
        expiration='1800000',   # 30 minutes in milliseconds — STRING format
        delivery_mode=pika.DeliveryMode.Persistent
    )
)

# Queue auto-delete TTL (koi consumer nahi toh delete karo)
channel.queue_declare(
    queue='temp_rpc_queue',
    durable=False,
    arguments={
        'x-expires': 300000,   # 5 minutes baad delete (if unused)
    }
)

# Interview Note:
# Agar dono set hain — jo PEHLE expire ho — wahi apply hoga
# Message TTL=60000, Queue TTL=3600000 → message 60 sec mein expire
```

---

### Q4: Priority Queue kya hai? Kaise setup karo?

**Answer:**
High priority tasks pehle process hote hain — priority 0 se 255 tak (higher = pehle)

```
Without Priority:
  Queue: [task1(p:0), task2(p:0), urgent_task(p:10), task3(p:0)]
  Processing: task1 → task2 → urgent_task → task3  ❌ urgent wait karta hai

With Priority:
  Queue internally sort karta hai:
  Processing: urgent_task(p:10) → task1(p:0) → task2(p:0) → task3(p:0) ✅
```

```python
import pika, json

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()

# Priority queue — max priority 10 set karo
channel.queue_declare(
    queue='task_queue_priority',
    durable=True,
    arguments={
        'x-max-priority': 10   # 0 to 10 — higher = pehle process
    }
)

# Normal task (priority 1)
def send_task(task_name: str, priority: int = 1):
    channel.basic_publish(
        exchange='',
        routing_key='task_queue_priority',
        body=json.dumps({'task': task_name, 'priority': priority}),
        properties=pika.BasicProperties(
            delivery_mode=pika.DeliveryMode.Persistent,
            priority=priority   # message priority set karo
        )
    )
    print(f"Task queued: {task_name} (priority: {priority})")

# Messages bhejo
send_task('Generate monthly report', priority=1)   # low
send_task('Process payment', priority=8)           # high
send_task('Send newsletter', priority=2)           # low-medium
send_task('URGENT: Fraud alert', priority=10)      # highest
send_task('Update user cache', priority=3)         # medium

# Consumer
def task_callback(ch, method, properties, body):
    data = json.loads(body)
    print(f"Processing: {data['task']} (priority: {data['priority']})")
    time.sleep(0.5)  # simulate work
    ch.basic_ack(delivery_tag=method.delivery_tag)

channel.basic_qos(prefetch_count=1)
channel.basic_consume(queue='task_queue_priority', on_message_callback=task_callback, auto_ack=False)
channel.start_consuming()
# Output order: URGENT fraud alert → Process payment → Update cache → newsletter → report
```

---

### Q5: Publisher Confirms kya hai? Message delivery guarantee kaise karte hain?

**Answer:**
```
Without Publisher Confirms:
  Producer publish karta hai → "hope karo broker ne receive kiya"
  Network fail → message LOST — koi pata nahi

With Publisher Confirms:
  Producer publish karta hai → Broker ack bhejta hai
  Confirmed = message queue mein safely tha ✅
  Nacked   = broker reject kiya (queue full, etc.) ❌
```

```python
import pika, json

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()

# Publisher Confirms enable karo
channel.confirm_delivery()   # yahi line enable karta hai

channel.queue_declare(queue='confirmed_queue', durable=True)

# Method 1: Simple — wait for confirm
try:
    channel.basic_publish(
        exchange='',
        routing_key='confirmed_queue',
        body='Important message',
        properties=pika.BasicProperties(delivery_mode=pika.DeliveryMode.Persistent),
        mandatory=True   # route nahi hua toh return karo
    )
    print("Message confirmed by broker!")
except pika.exceptions.UnroutableError:
    print("Message could not be routed — queue nahi mili!")

# Method 2: Callback with confirm/nack handling
def on_delivery_confirmation(method_frame):
    if method_frame.method.NAME == 'Basic.Ack':
        print(f"Message #{method_frame.method.delivery_tag} confirmed ✅")
    elif method_frame.method.NAME == 'Basic.Nack':
        print(f"Message #{method_frame.method.delivery_tag} nacked ❌ — retry karo")

channel.add_on_return_callback(on_delivery_confirmation)

# Method 3: Batch confirm (production ke liye efficient)
messages = [
    {'order_id': 1, 'amount': 500},
    {'order_id': 2, 'amount': 750},
    {'order_id': 3, 'amount': 1200},
]

for msg in messages:
    channel.basic_publish(
        exchange='',
        routing_key='confirmed_queue',
        body=json.dumps(msg),
        properties=pika.BasicProperties(delivery_mode=pika.DeliveryMode.Persistent)
    )

print(f"All {len(messages)} messages published with confirms enabled")
connection.close()
```

---

### Q6: Competing Consumers Pattern kya hai?

**Answer:**
Ek queue, multiple workers — load share hota hai — horizontal scaling.

```
Queue: [task1, task2, task3, task4, task5]
         │       │       │       │       │
      Worker1  Worker2  Worker1  Worker2  Worker1
      (koi bhi message le sakta hai)
```

```python
# Worker 1 aur Worker 2 — same queue pe basic_consume karo
# RabbitMQ round-robin distribute karta hai by default
# basic_qos(prefetch_count=1) = fair dispatch — busy worker ko zyada nahi milega

# Worker code (same code multiple instances run karo)
import pika, time, random

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()

channel.queue_declare(queue='work_queue', durable=True)
channel.basic_qos(prefetch_count=1)  # IMPORTANT — fair dispatch ke liye

def callback(ch, method, properties, body):
    task = body.decode()
    processing_time = random.uniform(0.5, 2.0)  # simulate variable work
    print(f"Worker processing: {task} (will take {processing_time:.1f}s)")
    time.sleep(processing_time)
    print(f"Done: {task}")
    ch.basic_ack(delivery_tag=method.delivery_tag)

channel.basic_consume(queue='work_queue', on_message_callback=callback, auto_ack=False)
print("Worker waiting for tasks...")
channel.start_consuming()

# Run 3 workers in separate terminals:
# python worker.py  (terminal 1)
# python worker.py  (terminal 2)
# python worker.py  (terminal 3)
# → Load automatically distribute hoga
```

---

## Summary Table

```
┌─────────────────────────────────────────────────────────────────────┐
│ Feature            │ Parameter               │ Kab Use karo         │
├─────────────────────────────────────────────────────────────────────┤
│ DLX                │ x-dead-letter-exchange  │ Failed msg handle    │
│ Message TTL        │ x-message-ttl (ms)      │ Expire old msgs      │
│ Queue Expires      │ x-expires (ms)          │ Temp queues          │
│ Priority Queue     │ x-max-priority (0-255)  │ Urgent tasks first   │
│ Publisher Confirms │ confirm_delivery()      │ Delivery guarantee   │
│ Max Length         │ x-max-length            │ Queue overflow ctrl  │
│ Competing Consumer │ prefetch_count=1        │ Multiple workers     │
└─────────────────────────────────────────────────────────────────────┘
```
