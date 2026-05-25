# Publisher Confirms & Competing Consumers

## Why It Matters

Default RabbitMQ = "fire and forget" from publisher. To guarantee delivery:
- **Publisher confirms** → broker acks each message
- **Mandatory flag** → detect unroutable messages
- **Competing consumers** → load distribution
- **Idempotency** → handle duplicates

Senior interview: "Publisher how do you guarantee message reached broker?" → confirms.

---

## Publisher Confirms

### Sync Confirms (Simple, Slow)

```python
import pika

connection = pika.BlockingConnection(...)
channel = connection.channel()
channel.confirm_delivery()

try:
    channel.basic_publish(
        exchange='orders',
        routing_key='new',
        body=b'...',
        properties=pika.BasicProperties(delivery_mode=2),
        mandatory=True,
    )
    # Returns successfully = confirmed
except pika.exceptions.UnroutableError:
    print("Message could not be routed (no binding)")
except pika.exceptions.NackError:
    print("Broker rejected (queue full, disk space, etc)")
```

Slow — one round-trip per message.

### Batch Confirms

```python
batch_size = 100
channel.confirm_delivery()

for i in range(1000):
    channel.basic_publish(...)
    if (i + 1) % batch_size == 0:
        channel.wait_for_confirms()
```

Faster than per-message confirms.

### Async Confirms (Fastest, Complex)

```python
import pika


def on_confirm(method_frame):
    delivery_tag = method_frame.method.delivery_tag
    if isinstance(method_frame.method, pika.spec.Basic.Ack):
        print(f"Confirmed up to {delivery_tag}")
    else:
        print(f"Nacked {delivery_tag}")


connection = pika.BlockingConnection(...)
channel = connection.channel()
channel.confirm_delivery(on_confirm)


# Publish without waiting
for i in range(1000):
    channel.basic_publish(
        exchange='x',
        routing_key='k',
        body=f'msg-{i}'.encode(),
        mandatory=True,
    )
    # delivery_tag auto-increments

# Process confirms while publishing
connection.process_data_events()
```

### Multiple Ack (Optimization)

Broker can ack multiple messages with single ACK frame (`multiple: true`). Client tracks pending tags, on ack removes everything up to delivery_tag.

```python
pending_tags = set()


def on_ack(delivery_tag, multiple):
    if multiple:
        to_remove = {t for t in pending_tags if t <= delivery_tag}
        pending_tags.difference_update(to_remove)
    else:
        pending_tags.discard(delivery_tag)
```

### Mandatory Flag

```python
channel.basic_publish(
    exchange='orders',
    routing_key='nonexistent',
    body=b'...',
    mandatory=True,
)
# If no queue bound to routing_key → basic.return fires
```

Without `mandatory=True`, unroutable messages silently discarded.

### Returns Handler

```python
def on_return(channel, method, props, body):
    print(f"Returned: {body} reply_code={method.reply_code}")


channel.add_on_return_callback(on_return)
```

## Competing Consumers (Load Distribution)

### Default — Round Robin

```python
# Multiple consumers on same queue
channel.basic_consume(queue='orders', on_message_callback=consume_a)
channel.basic_consume(queue='orders', on_message_callback=consume_b)
```

Broker rotates messages between consumers.

### Prefetch (Fair Dispatch)

```python
channel.basic_qos(prefetch_count=1)
```

Without prefetch: broker pre-sends N messages per consumer → slow consumer hogs messages → others idle.

With `prefetch_count=1`: broker only sends next message after previous acked. True fair dispatch.

### Tune Prefetch by Workload

- `prefetch=1` — strict fairness, slow throughput
- `prefetch=10-50` — balanced (typical)
- `prefetch=100-500` — high throughput, less fair

```python
# For fast handlers: higher prefetch
channel.basic_qos(prefetch_count=100)


# For slow handlers (DB writes, external API): lower
channel.basic_qos(prefetch_count=5)
```

### Per-Channel vs Per-Consumer Prefetch

```python
# Default: per-consumer
channel.basic_qos(prefetch_count=10)

# Per-channel: total across all consumers on channel
channel.basic_qos(prefetch_count=10, global_qos=True)
```

### Idempotent Consumer

```python
import redis


r = redis.Redis()


def handler(body, props):
    message_id = props.message_id    # set by publisher

    # Idempotency check
    if r.set(f'processed:{message_id}', '1', ex=86400, nx=True):
        # First time — process
        try:
            do_work(body)
        except Exception:
            # Failure — allow retry
            r.delete(f'processed:{message_id}')
            raise
    # else: already processed, ack and skip
```

Publisher must set unique `message_id`:

```python
channel.basic_publish(
    exchange='x',
    routing_key='k',
    body=b'...',
    properties=pika.BasicProperties(
        message_id=str(uuid.uuid4()),
        delivery_mode=2,
    ),
)
```

### Ack Strategies

```python
def callback(ch, method, props, body):
    try:
        process(body)
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except RetriableError:
        # Requeue for retry
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    except FatalError:
        # Send to DLQ (don't requeue)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
```

`basic.reject` for single message; `basic.nack` for batch with multiple.

### Connection vs Channel vs Consumer

```
Connection — TCP/TLS connection (heavy, slow to open)
  ├─ Channel — lightweight virtual connection (fast to open)
  │   ├─ Consumer — basic.consume subscription
  │   └─ Consumer
  └─ Channel
```

**Rules:**
- 1 connection per process (or per pool)
- N channels per connection (one per thread or task)
- Channels NOT thread-safe — use separate channel per thread

```python
# WRONG — channel shared across threads
channel = connection.channel()
threading.Thread(target=lambda: channel.basic_publish(...)).start()
threading.Thread(target=lambda: channel.basic_publish(...)).start()


# RIGHT — one channel per thread
def worker(connection):
    channel = connection.channel()
    channel.basic_publish(...)


threading.Thread(target=worker, args=(connection,)).start()
threading.Thread(target=worker, args=(connection,)).start()
```

### Graceful Consumer Shutdown

```python
import signal


shutdown_flag = False


def signal_handler(sig, frame):
    global shutdown_flag
    shutdown_flag = True


signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


def callback(ch, method, props, body):
    if shutdown_flag:
        # Don't ack — requeue for next consumer
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        return
    process(body)
    ch.basic_ack(delivery_tag=method.delivery_tag)


try:
    channel.basic_consume(queue='orders', on_message_callback=callback)
    channel.start_consuming()
except KeyboardInterrupt:
    pass
finally:
    channel.stop_consuming()
    connection.close()
```

---

## Common Pitfalls

### 1. No Publisher Confirms

Message published → broker crashes → silently lost. Always use confirms for critical data.

### 2. Sync Confirms (per-message)

```python
channel.basic_publish(...)
channel.wait_for_confirms()   # blocks 1 RTT per message
```

10000 RPS → can't sustain. Use async confirms or batches.

### 3. Forgetting Mandatory Flag

Unroutable message (no binding for routing key) silently dropped. Use `mandatory=True` + return handler.

### 4. Prefetch Too High

```python
channel.basic_qos(prefetch_count=10000)
```

One consumer grabs 10k, others starve. Also OOM risk. Tune for handler speed.

### 5. Sharing Channel Across Threads

Channel not thread-safe. Random errors. One channel per thread.

### 6. Auto-Ack with Important Messages

```python
channel.basic_consume(queue='X', auto_ack=True)
```

Consumer crashes before processing → message lost. Use manual ack.

### 7. Requeue Loop (Poison Pill)

```python
ch.basic_nack(..., requeue=True)   # always requeue
```

Bad message re-enters queue forever, blocking others. Use `x-delivery-limit` + DLQ.

### 8. No Heartbeat

```python
pika.ConnectionParameters(host='...', heartbeat=0)
```

Network blip = silent disconnect → publishes fail mysteriously. Use heartbeat 30-60s.

---

## Interview Q&A

**Q1:** Publisher confirms ka mechanism?
**A:** Channel enabled with `confirm_delivery()`. Each published message gets sequence number (delivery_tag). Broker sends `basic.ack` when message persisted (durable + queue). For ROW format, after written to disk. Async = pipelined, sync = wait per message. Use async + batch wait for throughput.

**Q2:** Mandatory flag aur returns?
**A:** `mandatory=True` tells broker: if message can't be routed to any queue (no binding matches), return to publisher via `basic.return`. Set `add_on_return_callback` to handle. Without mandatory, unroutable messages silently dropped — bad for critical data.

**Q3:** Prefetch tuning karne ka logic?
**A:** Trade-off: throughput vs fairness. High prefetch = consumer pulls many messages = if slow, others starve. Low (1) = strict fairness, RTT overhead. Calculate: `prefetch ≈ throughput * latency`. For 100 msg/s × 100ms = ~10. Start low, increase if throughput insufficient.

**Q4:** Idempotent consumer kaise design karoge?
**A:** Each message has unique `message_id` (publisher sets). Consumer maintains processed set (Redis SET with TTL or DB unique constraint). Before processing, check + atomically mark. If duplicate, just ack. On exception, release the mark to allow retry.

**Q5:** Connection vs Channel vs Consumer?
**A:** Connection: TCP socket (expensive, one per app). Channel: lightweight virtual connection within TCP (cheap, many per connection). Consumer: subscription on queue via basic.consume. Best practice: 1 connection per process, 1 channel per thread, N consumers per channel.

**Q6:** Competing consumers vs work stealing?
**A:** Competing consumers: multiple consumers on same queue, broker dispatches round-robin (with prefetch). Each message goes to ONE consumer. This is RabbitMQ's default. "Work stealing" usually means consumers actively pull from idle siblings — RabbitMQ doesn't do that.

**Q7:** Graceful shutdown pattern?
**A:** SIGTERM handler sets flag. In message callback, check flag — if set, nack(requeue=True), don't process new ones. After current in-flight done, close channel + connection. K8s grace period (terminationGracePeriodSeconds: 30) lets this finish.

**Q8:** Publisher confirm fail hua — kya karoge?
**A:** Nack = broker rejected (queue full, disk full, etc). Common: queue x-overflow=reject-publish-dlx. Retry policy: exponential backoff. If persistent, send to dead-letter or alert. For ack timeout (no response within N seconds): assume failed, retry. Idempotency at consumer side protects against double-publish.

---

## Real-World Use Cases

### 1. Payment Service (Async Confirms + DLQ)

Publisher uses async confirms with callback. On nack/timeout, retry with exponential backoff up to N. Final failure: send to DLQ for manual investigation.

### 2. High-Throughput Logs (Batch Confirms)

100k logs/sec. Publisher uses batches of 1000 + `wait_for_confirms_delivery()` per batch. Network overhead minimized.

### 3. Order Processing (Idempotent)

Stripe webhook → publish OrderEvent with `message_id=event_id`. Multiple consumers, but each event processed exactly once via Redis dedup.

---

## References

- [Publisher Confirms](https://www.rabbitmq.com/confirms.html)
- [Consumer Acknowledgements](https://www.rabbitmq.com/confirms.html#consumer-acknowledgements)
- [Reliability Guide](https://www.rabbitmq.com/reliability.html)
- [pika docs](https://pika.readthedocs.io/)
