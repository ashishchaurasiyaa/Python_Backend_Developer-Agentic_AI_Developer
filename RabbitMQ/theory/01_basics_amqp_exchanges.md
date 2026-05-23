# RabbitMQ — Basics, AMQP Protocol & Exchanges
**Basic to Advanced | Theory + Interview Q&A**

---

## Quick Concepts
- **RabbitMQ** = Message Broker — Producer aur Consumer ke beech middleman
- **AMQP** = Advanced Message Queuing Protocol — RabbitMQ ka underlying protocol
- **Producer** = Message bhejta hai → Exchange ko
- **Exchange** = Message receive karta hai → Rules ke basis pe Queue mein route karta hai
- **Queue** = Messages store karta hai → Consumer ke liye
- **Consumer** = Queue se message leke process karta hai
- **Binding** = Exchange aur Queue ko connect karta hai (routing rule)
- **Routing Key** = Producer ka label — Exchange decide karta hai kahan bhejein
- **Virtual Host (vhost)** = Logical isolation — alag environments ke liye

---

## Core Architecture — Flow

```
Producer
   │
   │  publish(exchange, routing_key, message)
   ▼
Exchange  ──── Binding (routing_key) ────► Queue A  ──► Consumer 1
              ──── Binding (routing_key) ────► Queue B  ──► Consumer 2
              ──── Binding (routing_key) ────► Queue C  ──► Consumer 3
```

---

## Interview Questions & Answers

---

### Q1: RabbitMQ kya hai? Kyu use karte hain?

**Answer:**
RabbitMQ ek **message broker** hai jo services ke beech **asynchronous communication** enable karta hai.

**Kyu use karte hain:**
```
Problem without RabbitMQ:
  OrderService → directly calls → PaymentService
  Agar PaymentService down hai → Order fail ho jaata hai
  Tight coupling → ek fail = dono fail

Solution with RabbitMQ:
  OrderService → Queue mein dalta hai → PaymentService ready hone pe process karta hai
  Loose coupling → services independently scale + fail ho sakti hain
```

**Use cases:**
```python
# 1. Order processing — ek order → multiple services notify karo
order_created → [payment_queue, inventory_queue, email_queue]

# 2. Background jobs — heavy task async mein karo
user_signup → [send_welcome_email, create_profile, send_analytics]

# 3. Rate limiting — queue buffer karo bursts ke liye
1000 requests/sec → queue → 100 requests/sec process karo

# 4. Microservices communication — services decouple karo
user-service → rabbitmq → notification-service
```

---

### Q2: AMQP Protocol kya hai? RabbitMQ mein kaise kaam karta hai?

**Answer:**
**AMQP = Advanced Message Queuing Protocol**
Binary protocol — HTTP se efficient — TCP pe chalta hai

```
AMQP ke 4 main entities:
┌─────────────────────────────────────────────────┐
│  Connection  (TCP connection to broker)          │
│    └── Channel  (lightweight virtual connection) │
│          └── Exchange  (message router)          │
│                └── Queue  (message buffer)        │
└─────────────────────────────────────────────────┘

Connection vs Channel:
  Connection = Heavy — TCP handshake — expensive to create
  Channel    = Lightweight — Connection ke andar — ek app mein multiple channels
  
  Rule: 1 Connection per app, multiple Channels per thread/coroutine
```

```python
import pika

# Connection = TCP connection to RabbitMQ
connection = pika.BlockingConnection(
    pika.ConnectionParameters(
        host='localhost',
        port=5672,          # AMQP default port
        virtual_host='/',   # default vhost
        credentials=pika.PlainCredentials('guest', 'guest'),
        heartbeat=600,      # connection alive check — 600 seconds
        blocked_connection_timeout=300
    )
)

# Channel = lightweight virtual connection
channel = connection.channel()
# Ek connection pe multiple channels — thread safety ke liye
channel2 = connection.channel()
```

**Interview one-liner:**
> "Connection is the TCP socket; Channel is a logical multiplex inside that connection. Use one connection per process, one channel per thread."

---

### Q3: Exchange Types kya hain? Kab kaunsa use karo?

**Answer: 4 types hain — har ek alag routing logic**

```
┌──────────────────────────────────────────────────────────────┐
│ Exchange Type │ Routing Logic          │ Use Case            │
├──────────────────────────────────────────────────────────────┤
│ Direct        │ Exact routing_key match│ Task queues         │
│ Fanout        │ Broadcast to ALL queues│ Notifications       │
│ Topic         │ Wildcard pattern match │ Logs, events        │
│ Headers       │ Header attributes      │ Complex routing     │
└──────────────────────────────────────────────────────────────┘
```

---

### Q4: Direct Exchange kya hai? Kaise kaam karta hai?

**Answer:**
Routing key **exactly match** hone pe message us queue mein jaata hai.

```
Producer → routing_key="payment"
    │
Exchange (direct)
    ├── Binding key="payment"  → payment_queue  ✅ message delivered
    ├── Binding key="email"    → email_queue    ❌ skipped
    └── Binding key="sms"      → sms_queue      ❌ skipped
```

```python
import pika

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()

# Step 1: Exchange declare karo
channel.exchange_declare(
    exchange='order_exchange',
    exchange_type='direct',
    durable=True   # RabbitMQ restart pe survive kare
)

# Step 2: Queues declare karo
channel.queue_declare(queue='payment_queue', durable=True)
channel.queue_declare(queue='email_queue', durable=True)
channel.queue_declare(queue='sms_queue', durable=True)

# Step 3: Bindings — Exchange se Queue ko connect karo
channel.queue_bind(
    exchange='order_exchange',
    queue='payment_queue',
    routing_key='payment'   # exact match
)
channel.queue_bind(
    exchange='order_exchange',
    queue='email_queue',
    routing_key='email'
)

# Step 4: Message publish karo
channel.basic_publish(
    exchange='order_exchange',
    routing_key='payment',   # payment_queue ko jaayega
    body='{"order_id": 123, "amount": 999}',
    properties=pika.BasicProperties(
        delivery_mode=pika.DeliveryMode.Persistent  # disk pe save karo
    )
)
print("Payment message sent!")

channel.basic_publish(
    exchange='order_exchange',
    routing_key='email',     # email_queue ko jaayega
    body='{"order_id": 123, "email": "user@test.com"}',
    properties=pika.BasicProperties(delivery_mode=pika.DeliveryMode.Persistent)
)
print("Email message sent!")

connection.close()
```

**Consumer (Direct Exchange):**
```python
def payment_callback(ch, method, properties, body):
    import json
    data = json.loads(body)
    print(f"Processing payment for order: {data['order_id']}, amount: {data['amount']}")
    ch.basic_ack(delivery_tag=method.delivery_tag)  # manual ack — processed

channel.basic_qos(prefetch_count=1)  # ek baar mein 1 message
channel.basic_consume(
    queue='payment_queue',
    on_message_callback=payment_callback,
    auto_ack=False   # ALWAYS False in production
)
channel.start_consuming()
```

---

### Q5: Fanout Exchange kya hai? Broadcast kaise karta hai?

**Answer:**
Routing key **ignore** karta hai — message **SABHI** bound queues ko jaata hai.

```
Producer → routing_key="" (ignored)
    │
Exchange (fanout)
    ├── email_queue    ✅ message milega
    ├── sms_queue      ✅ message milega
    └── push_queue     ✅ message milega
```

**Real use case:** User signup → email + SMS + push notification — teeno ko ek saath

```python
import pika, json

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()

# Fanout exchange
channel.exchange_declare(
    exchange='notification_exchange',
    exchange_type='fanout',
    durable=True
)

# Queues — sabhi bound hain
channel.queue_declare(queue='email_notifications', durable=True)
channel.queue_declare(queue='sms_notifications', durable=True)
channel.queue_declare(queue='push_notifications', durable=True)

# Bind sab queues — routing_key='' (ignored in fanout)
channel.queue_bind(exchange='notification_exchange', queue='email_notifications')
channel.queue_bind(exchange='notification_exchange', queue='sms_notifications')
channel.queue_bind(exchange='notification_exchange', queue='push_notifications')

# Publish karo — teeno queues ko jaayega automatically
event = {"user_id": 42, "event": "user_signup", "name": "Alice"}
channel.basic_publish(
    exchange='notification_exchange',
    routing_key='',        # fanout mein ignored hai
    body=json.dumps(event),
    properties=pika.BasicProperties(delivery_mode=pika.DeliveryMode.Persistent)
)
print(f"Notification broadcast to all 3 queues: {event}")
connection.close()
```

**Fanout Consumer (Email Service):**
```python
def email_callback(ch, method, properties, body):
    data = json.loads(body)
    print(f"Sending welcome email to user {data['user_id']}: {data['name']}")
    # send_email(data['name'])
    ch.basic_ack(delivery_tag=method.delivery_tag)

channel.basic_qos(prefetch_count=1)
channel.basic_consume(queue='email_notifications', on_message_callback=email_callback, auto_ack=False)
channel.start_consuming()
```

---

### Q6: Topic Exchange kya hai? Wildcard routing kaise kaam karta hai?

**Answer:**
Routing key mein **wildcard pattern** use karta hai.

```
Wildcards:
  *  = exactly ONE word
  #  = zero or more words

Routing key format: word1.word2.word3

Examples:
  "order.placed.india"   → *.placed.* aur order.# dono match honge
  "payment.failed.usa"   → *.failed.* match hoga
  "user.login"           → user.# match hoga
```

```python
channel.exchange_declare(
    exchange='app_events',
    exchange_type='topic',
    durable=True
)

# Different queues different patterns sun rahi hain
channel.queue_declare(queue='all_order_events', durable=True)
channel.queue_declare(queue='failed_events', durable=True)
channel.queue_declare(queue='india_events', durable=True)
channel.queue_declare(queue='all_events', durable=True)

# Bindings with patterns
channel.queue_bind(
    exchange='app_events',
    queue='all_order_events',
    routing_key='order.#'       # order se start hone wale sab
)
channel.queue_bind(
    exchange='app_events',
    queue='failed_events',
    routing_key='*.failed.*'    # beech mein failed wale sab
)
channel.queue_bind(
    exchange='app_events',
    queue='india_events',
    routing_key='#.india'       # india se end hone wale sab
)
channel.queue_bind(
    exchange='app_events',
    queue='all_events',
    routing_key='#'             # SAB events
)

# Test publishes
events = [
    ('order.placed.india',   'Order placed from India'),
    ('order.failed.usa',     'Order failed in USA'),
    ('payment.failed.india', 'Payment failed in India'),
    ('user.login.india',     'User login from India'),
]

for routing_key, message in events:
    channel.basic_publish(
        exchange='app_events',
        routing_key=routing_key,
        body=message.encode()
    )
    print(f"Published: [{routing_key}] {message}")

# Expected routing:
# order.placed.india  → all_order_events ✅, india_events ✅, all_events ✅
# order.failed.usa    → all_order_events ✅, failed_events ✅, all_events ✅
# payment.failed.india→ failed_events ✅, india_events ✅, all_events ✅
# user.login.india    → india_events ✅, all_events ✅
```

---

### Q7: Headers Exchange kya hai? Kab use karo?

**Answer:**
Routing key **bilkul ignore** karta hai. Message headers ke basis pe route karta hai.
`x-match: all` = saare headers match hone chahiye
`x-match: any` = koi bhi ek header match ho

```python
channel.exchange_declare(
    exchange='report_exchange',
    exchange_type='headers',
    durable=True
)

channel.queue_declare(queue='pdf_reports', durable=True)
channel.queue_declare(queue='excel_reports', durable=True)
channel.queue_declare(queue='urgent_reports', durable=True)

# Binding with header arguments
channel.queue_bind(
    exchange='report_exchange',
    queue='pdf_reports',
    routing_key='',   # ignored
    arguments={
        'x-match': 'all',    # sab match hone chahiye
        'format': 'pdf',
        'type': 'report'
    }
)
channel.queue_bind(
    exchange='report_exchange',
    queue='urgent_reports',
    routing_key='',
    arguments={
        'x-match': 'any',    # koi bhi ek match ho
        'priority': 'urgent'
    }
)

# Publish with headers
channel.basic_publish(
    exchange='report_exchange',
    routing_key='',    # ignored
    body='Report data here',
    properties=pika.BasicProperties(
        headers={
            'format': 'pdf',
            'type': 'report',
            'priority': 'normal'
        }
    )
)
# → pdf_reports queue mein jaayega (format=pdf AND type=report match)
```

---

### Q8: Default Exchange kya hai?

**Answer:**
Har queue ka naam hi uska routing key hota hai. Exchange ka naam `""` (empty string).

```python
# Direct queue mein bhejne ka shortcut — exchange name="" 
channel.queue_declare(queue='my_queue', durable=True)

# Default exchange use — routing_key = queue ka naam
channel.basic_publish(
    exchange='',         # Default exchange
    routing_key='my_queue',   # Queue ka naam hi routing key
    body='Hello!'
)
# Seedha my_queue mein jaayega — no exchange setup needed
# Yahi tumhare old send.py + receive.py mein use tha!
```

---

### Q9: auto_ack=True vs False — kya fark hai? Production mein kaunsa?

**Answer:**
```
auto_ack=True  → Message deliver hote hi delete ho jaata hai
               → Consumer crash ho → message LOST forever ❌
               → NEVER use in production

auto_ack=False → Consumer ko explicitly ack karna padta hai
               → basic_ack() call ke baad hi delete hota hai
               → Consumer crash → message requeue hota hai ✅
               → ALWAYS use in production
```

```python
def callback(ch, method, properties, body):
    try:
        process_message(body)
        ch.basic_ack(delivery_tag=method.delivery_tag)   # success → delete
    except Exception as e:
        print(f"Processing failed: {e}")
        ch.basic_nack(
            delivery_tag=method.delivery_tag,
            requeue=True    # True = queue mein wapas, False = discard/DLQ
        )

channel.basic_consume(queue='my_queue', on_message_callback=callback, auto_ack=False)
```

---

### Q10: durable=True vs False kya hai?

**Answer:**
```
Queue durable=False → RabbitMQ restart pe queue DELETE ho jaata hai
Queue durable=True  → RabbitMQ restart ke baad bhi queue survive karta hai

Message delivery_mode=Persistent → Disk pe save hota hai (RabbitMQ restart safe)
Message delivery_mode=Transient  → Sirf memory mein — restart pe LOST

Production rule:
  durable=True + delivery_mode=Persistent = Crash-safe setup
```

---

## Summary Table

```
┌─────────────────────────────────────────────────────────────────┐
│ Exchange  │ Routing Logic    │ routing_key   │ Use Case         │
├─────────────────────────────────────────────────────────────────┤
│ Default   │ queue name match │ queue name    │ Simple queuing   │
│ Direct    │ exact match      │ any string    │ Task routing     │
│ Fanout    │ all queues       │ ignored       │ Broadcast/notify │
│ Topic     │ wildcard (* #)   │ word.word     │ Pub/sub, logs    │
│ Headers   │ header attrs     │ ignored       │ Complex routing  │
└─────────────────────────────────────────────────────────────────┘
```
