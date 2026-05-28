# Webhook Design Deep

## Why It Matters

Webhooks = how systems notify each other asynchronously. Used by Stripe, GitHub, Slack, Shopify. Senior API design includes:
- **HMAC signing** — prove authenticity
- **Retry policy** — handle failures
- **Replay protection** — prevent attacks
- **Idempotency** — survive retries
- **Dead letter queue** — handle permanent failures
- **Versioning** — evolve schema

Senior interview: "Design webhook system for payment events."

---

## Webhook Lifecycle

```
Event Source (Stripe/GitHub/Your API)
  ↓ HTTP POST with signed payload
Customer Webhook Endpoint
  ↓ HTTP 2xx response
[Acknowledged]


On failure (timeout, 5xx, network):
  → Retry with exponential backoff
  → After max attempts → dead letter
```

---

## Signing (HMAC-SHA256)

### Sender Side

```python
import hmac
import hashlib
import time
import json


def sign_webhook(payload: dict, secret: str) -> dict:
    timestamp = int(time.time())
    body = json.dumps(payload, sort_keys=True)
    signed_payload = f'{timestamp}.{body}'

    signature = hmac.new(
        secret.encode(),
        signed_payload.encode(),
        hashlib.sha256,
    ).hexdigest()

    return {
        'X-Webhook-Timestamp': str(timestamp),
        'X-Webhook-Signature': f'sha256={signature}',
        'X-Webhook-Event-Id': str(uuid.uuid4()),
    }
```

### Receiver Side

```python
def verify_webhook(body: bytes, timestamp: int, signature: str, secret: str, tolerance: int = 300):
    # Replay protection — reject old requests
    if abs(time.time() - timestamp) > tolerance:
        return False

    signed_payload = f'{timestamp}.'.encode() + body
    expected = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    received = signature.removeprefix('sha256=')

    # Constant-time compare — prevent timing attacks
    return hmac.compare_digest(expected, received)
```

### Stripe-Style (Multiple Signatures)

```
Stripe-Signature: t=1709125200,v1=abc...,v1=def...
```

`t` = timestamp, `v1` = current scheme, multiple `v1` for secret rotation.

```python
def parse_stripe_signature(header: str) -> dict:
    parts = {}
    for chunk in header.split(','):
        k, _, v = chunk.partition('=')
        parts.setdefault(k, []).append(v)
    return parts
```

---

## Retry Policy

### Exponential Backoff

```python
def compute_retry_delay(attempt: int, base: float = 1.0, max_delay: float = 3600) -> float:
    delay = min(base * (2 ** attempt), max_delay)
    jitter = random.uniform(0, 0.5 * delay)
    return delay + jitter


# Attempt 0: ~1s
# Attempt 1: ~2s
# Attempt 2: ~4s
# Attempt 5: ~32s
# Attempt 10: ~1024s → capped at 3600
```

### Retry Schedule (Stripe Example)

```
1st attempt: immediately
2nd attempt: 5 minutes later
3rd attempt: 30 minutes later
4th attempt: 2 hours later
5th attempt: 5 hours later
6th attempt: 11 hours later
7th attempt: 17 hours later
8th attempt: 23 hours later
... up to 3 days total
```

After 3 days: webhook marked dead, customer notified.

### When NOT to Retry

```python
def should_retry(response_status: int) -> bool:
    # 2xx: success
    if 200 <= response_status < 300:
        return False
    # 4xx (except 408, 429): permanent client error
    if 400 <= response_status < 500 and response_status not in {408, 429}:
        return False
    # 5xx, timeouts, network: retry
    return True
```

---

## Idempotency (Receiver Side)

Same event delivered multiple times → must produce same result:

```python
@app.post('/webhooks/payment')
async def handle_payment_webhook(request: Request, ...):
    event_id = request.headers.get('X-Webhook-Event-Id')

    # SETNX with TTL — atomic check + lock
    acquired = await r.set(f'webhook:event:{event_id}', '1', ex=86400 * 7, nx=True)

    if not acquired:
        # Already processed — return 200 (don't make sender retry)
        return {'status': 'duplicate', 'event_id': event_id}

    try:
        await process_event(event)
    except Exception:
        # Release lock so retry can re-process
        await r.delete(f'webhook:event:{event_id}')
        raise

    return {'status': 'processed'}
```

---

## Schema Evolution / Versioning

```http
POST /webhook
X-Webhook-Version: 2.0

{
    "id": "evt_abc",
    "type": "payment.succeeded",
    "schema_version": "2.0",
    "data": {...}
}
```

**Strategies:**
- **Versioned URLs** — `/webhook/v1`, `/webhook/v2`
- **Header-based** — `X-Webhook-Version`
- **Schema in payload** — `schema_version` field
- **Stripe pattern** — customer fixed on API version at signup

**Compatibility:**
- Additive changes (new fields) — non-breaking, no version bump
- Breaking changes — new version, sunset old after 6-12 months

---

## Dead Letter Queue (DLQ)

```python
class WebhookDelivery(models.Model):
    id = models.UUIDField(primary_key=True)
    subscription = models.ForeignKey(WebhookSubscription, on_delete=models.CASCADE)
    event_id = models.UUIDField(unique=True, db_index=True)
    payload = models.JSONField()
    status = models.CharField(max_length=20)  # pending, sent, failed, dead
    attempts = models.IntegerField(default=0)
    next_retry_at = models.DateTimeField(db_index=True)
    last_error = models.TextField(blank=True)
    last_response_status = models.IntegerField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)


# Worker periodically picks up
@shared_task
def retry_failed_webhooks():
    now = timezone.now()
    pending = WebhookDelivery.objects.filter(
        status__in=['pending', 'failed'],
        next_retry_at__lte=now,
        attempts__lt=10,
    )[:100]

    for delivery in pending:
        try:
            deliver(delivery)
            delivery.status = 'sent'
        except Exception as e:
            delivery.attempts += 1
            delivery.last_error = str(e)[:1000]
            if delivery.attempts >= 10:
                delivery.status = 'dead'
                notify_customer(delivery.subscription)
            else:
                delivery.next_retry_at = now + timedelta(
                    seconds=compute_retry_delay(delivery.attempts)
                )
        delivery.save()
```

---

## Receiver Best Practices

### 1. Respond Fast (< 5s)

```python
@app.post('/webhooks/stripe')
async def webhook(request: Request, background: BackgroundTasks):
    body = await request.body()

    # Verify quickly
    if not verify(body, ...):
        raise HTTPException(401)

    # Queue for background processing
    background.add_task(process_event_async, body)

    # Respond immediately
    return {'received': True}
```

### 2. Acknowledge Receipt Before Processing

Sender's job done at 2xx. If you fail during processing, lookup events from your DLQ later or use sender's UI to replay.

### 3. Handle All Event Types

```python
EVENT_HANDLERS = {
    'payment.succeeded': handle_payment_succeeded,
    'payment.failed': handle_payment_failed,
    'subscription.created': handle_subscription_created,
    # ...
}


async def process_event(event):
    handler = EVENT_HANDLERS.get(event['type'])
    if not handler:
        log.warning(f'Unknown event type: {event["type"]}')
        # Still return 200 — don't fail just because we don't know
        return
    await handler(event['data'])
```

### 4. Test Webhook Locally

```bash
# ngrok for tunneling
ngrok http 8000

# Stripe CLI
stripe listen --forward-to localhost:8000/webhooks/stripe

# Use ngrok URL in Stripe Dashboard webhook config
```

---

## Sender (Your API Exposing Webhooks)

### Customer Subscription

```http
POST /webhook-subscriptions

{
    "url": "https://customer.com/webhook",
    "events": ["payment.succeeded", "order.created"],
    "active": true
}
```

Returns subscription with secret:

```json
{
    "id": "sub_abc",
    "secret": "whsec_xyz...",
    "url": "...",
    "events": [...]
}
```

Customer stores secret; uses for verification.

### Delivery

```python
async def deliver_event(subscription, event):
    body = json.dumps(event).encode()
    timestamp = int(time.time())
    signature = sign(body, subscription.secret, timestamp)

    headers = {
        'Content-Type': 'application/json',
        'X-Webhook-Signature': f'sha256={signature}',
        'X-Webhook-Timestamp': str(timestamp),
        'X-Webhook-Event-Id': event['id'],
        'User-Agent': 'MyApp-Webhooks/1.0',
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(subscription.url, content=body, headers=headers)
            return resp.status_code, resp.text[:1000]
        except httpx.RequestError as e:
            return None, str(e)
```

### Customer Dashboard Features

- **Replay** — manually trigger redelivery for failed events
- **Logs** — see all attempts with response codes
- **Test** — send sample event
- **Pause/Resume** — disable temporarily without losing config
- **Secret rotation** — generate new secret, support both for grace period

---

## Common Pitfalls

### 1. Slow Receiver

Receiver takes 30s → sender times out → retry → cascade. Respond fast, process async.

### 2. No HMAC Verification

Receiver doesn't verify → attacker can forge events.

### 3. Signing Parsed Body

```python
event = json.loads(body)
verify(json.dumps(event), ...)   # different bytes → fail
```

Always sign raw bytes.

### 4. No Idempotency on Receiver

Retry → duplicate processing → double-charge customer.

### 5. Retry Forever

Permanent failure (4xx) being retried forever wastes resources.

### 6. No Timestamp Validation

Captured request replayed days later — accepted. Window of 5 min standard.

### 7. Webhook in Frontend / Client

Webhooks server-to-server. Don't expose webhook endpoint to browsers (CORS, abuse).

### 8. Forgetting Secret Rotation Plan

Compromise → no way to rotate without breaking customers. Support old + new for grace period.

---

## Interview Q&A

**Q1:** Webhook security design?
**A:** HMAC-SHA256 of (timestamp + body) with shared secret. Constant-time compare on receiver. Timestamp validation (5min window) prevents replay. Event ID for idempotency. HTTPS only. Secret rotation support (sender sends multiple sigs during transition).

**Q2:** Retry policy?
**A:** Exponential backoff with jitter. 2xx = success (stop). 4xx (except 408, 429) = permanent (stop, alert customer). 5xx/timeout/network = retry. Max attempts (10-20), max duration (24-72 hours). Persist in DB; periodic worker retries.

**Q3:** Idempotency on receiver?
**A:** Sender includes unique event_id. Receiver checks Redis SETNX with TTL = retention period. If lock acquired → process. If exists → return 200 (don't make sender retry). On processing exception → release lock so next retry attempts again.

**Q4:** Webhook receiver pattern?
**A:** (1) Verify signature quickly. (2) Idempotency check via event_id. (3) Persist event to local queue/DB. (4) Return 2xx immediately. (5) Process async via worker. Avoids timeout cascades; allows reliable processing.

**Q5:** Schema evolution?
**A:** Additive (new field, new event type) = non-breaking, send to all. Breaking changes require versioning: customer fixed on API version at signup OR header-based version. Sunset old after 6-12 months with deprecation emails.

**Q6:** Dead letter queue?
**A:** After max retries, mark delivery 'dead'. Customer dashboard shows failed events. Support manual replay (re-queue). Alert customer via email when X% of webhooks failing. Eventually disable subscription if dead too long.

**Q7:** Secret rotation?
**A:** Customer requests new secret. Sender sends BOTH old and new signatures for grace period (24h-7d). After grace, only new. Receiver verifies against both during transition, only new after.

**Q8:** Testing webhooks locally?
**A:** ngrok for HTTPS tunnel to localhost. Stripe CLI `stripe listen --forward-to localhost:8000/webhook`. svix.com playground. Or self-built: log all incoming webhook payloads to file for replay.

---

## Real-World Examples

### Stripe Webhooks

- Versioned by API version (customer-fixed)
- HMAC SHA256 with versioned signatures
- Retry with exponential backoff over 3 days
- Customer dashboard for logs + replay
- Signature header: `Stripe-Signature: t=...,v1=...`

### GitHub Webhooks

- HMAC SHA256: `X-Hub-Signature-256: sha256=...`
- Delivery ID for idempotency: `X-GitHub-Delivery`
- Event type in header: `X-GitHub-Event`
- Up to 10 redelivery attempts in 8 hours
- Webhook secret per repository

### Slack Events API

- Signed request signature
- Replay protection via timestamp
- `challenge` request to verify ownership on subscription
- Acknowledge within 3 seconds

---

## References

- [Stripe webhook signatures](https://stripe.com/docs/webhooks/signatures)
- [GitHub webhook delivery](https://docs.github.com/en/webhooks/using-webhooks/handling-webhook-deliveries)
- [Standard Webhooks specification](https://www.standardwebhooks.com/)
- [Svix](https://svix.com/) — webhooks-as-a-service
- [ngrok](https://ngrok.com/) — local tunneling for testing
