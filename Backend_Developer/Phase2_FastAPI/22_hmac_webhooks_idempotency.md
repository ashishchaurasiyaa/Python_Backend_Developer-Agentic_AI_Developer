# HMAC Webhooks + Idempotency — Secure Async Communication

## Why It Matters (Senior 5 YOE Context)

Webhooks = how external systems (Stripe, GitHub, Twilio) notify your app. Critical security + reliability concerns:

- **HMAC signature** → prove webhook is genuine, not forged
- **Replay protection** → attacker can't re-send old webhooks
- **Idempotency** → duplicate delivery doesn't double-charge
- **Retry semantics** → temporary failures retry without state corruption
- **Out-of-order delivery** → handle reordering

Senior interview: "Stripe sends `payment_succeeded` webhook. How do you ensure exactly-once processing?" → HMAC verify + idempotency key + DB-tracked processed events.

---

## Core Concepts

### HMAC Signature Verification

Webhook sender signs payload with shared secret:

```
sig = HMAC-SHA256(secret, body_bytes).hex()
```

Sent as header:

```
X-Hub-Signature-256: sha256=abc123...
```

Receiver verifies:

```python
import hmac
import hashlib


WEBHOOK_SECRET = b"shared-secret"


def verify_signature(body: bytes, signature_header: str) -> bool:
    if not signature_header.startswith('sha256='):
        return False
    received_sig = signature_header[7:]  # strip 'sha256='

    expected = hmac.new(WEBHOOK_SECRET, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, received_sig)
```

**Why `hmac.compare_digest`:** constant-time comparison prevents timing attacks. `==` is vulnerable.

### Replay Protection — Timestamp Window

Without timestamp, attacker captures + replays later:

```python
import time


# Sender includes timestamp in header + signs (timestamp + body)
TIMESTAMP_TOLERANCE_SEC = 300  # 5 min


def verify_with_timestamp(body: bytes, signature: str, timestamp: int) -> bool:
    # Reject old requests
    if abs(time.time() - timestamp) > TIMESTAMP_TOLERANCE_SEC:
        return False

    # Sign timestamp + body
    payload = f'{timestamp}.{body.decode()}'.encode()
    expected = hmac.new(WEBHOOK_SECRET, payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
```

### Stripe-Style Signature

```
Stripe-Signature: t=1614556800,v1=abc123...,v0=def456...
```

Versioned. `t` = timestamp, `v1` = current HMAC. Allows secret rotation.

```python
def parse_stripe_signature(header: str) -> dict:
    parts = {}
    for chunk in header.split(','):
        k, _, v = chunk.partition('=')
        parts.setdefault(k, []).append(v)
    return parts


def verify_stripe_webhook(body: bytes, signature_header: str, secret: bytes) -> bool:
    parsed = parse_stripe_signature(signature_header)
    timestamp = parsed.get('t', [None])[0]
    v1_sigs = parsed.get('v1', [])

    if not timestamp or not v1_sigs:
        return False

    # Replay window
    if abs(time.time() - int(timestamp)) > 300:
        return False

    payload = f'{timestamp}.{body.decode()}'.encode()
    expected = hmac.new(secret, payload, hashlib.sha256).hexdigest()

    return any(hmac.compare_digest(expected, sig) for sig in v1_sigs)
```

### Idempotency Pattern

Webhooks can deliver duplicates (network retry). Track processed event IDs:

```python
# Sender includes unique ID (e.g., event_id)
# Receiver tracks → ignore duplicates

from fastapi import FastAPI, Request, Header, HTTPException
import redis


app = FastAPI()
r = redis.Redis()


@app.post("/webhook/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(...),
):
    body = await request.body()

    # 1. Verify signature
    if not verify_stripe_webhook(body, stripe_signature, STRIPE_SECRET):
        raise HTTPException(401, "Invalid signature")

    event = json.loads(body)
    event_id = event['id']  # e.g., 'evt_1234'

    # 2. Idempotency check (SETNX with TTL)
    key = f'webhook:stripe:{event_id}'
    if not r.set(key, '1', ex=86400 * 7, nx=True):
        # Already processed
        return {'status': 'duplicate'}

    # 3. Process the event
    try:
        await process_event(event)
    except Exception:
        # Failed — remove idempotency lock so retry works
        r.delete(key)
        raise

    return {'status': 'ok'}
```

### Idempotency Key in Requests (Opposite Direction)

When YOUR app calls external APIs with side effects:

```python
import uuid


async def charge_customer(amount: float):
    idempotency_key = str(uuid.uuid4())

    async with httpx.AsyncClient() as client:
        # First attempt
        resp = await client.post(
            'https://api.stripe.com/v1/charges',
            data={'amount': amount},
            headers={
                'Authorization': 'Bearer sk_xxx',
                'Idempotency-Key': idempotency_key,
            },
        )
    # If we retry with SAME key, Stripe returns cached result, no double charge
    return resp.json()
```

Store idempotency_key with request, retry on transient failures using same key.

### Sender-Side: Webhook Delivery with Retries

```python
import httpx
import asyncio


async def deliver_webhook(url: str, payload: dict, secret: bytes, max_retries: int = 5):
    import json
    body = json.dumps(payload).encode()
    timestamp = int(time.time())

    # Sign
    sig_payload = f'{timestamp}.{body.decode()}'.encode()
    signature = hmac.new(secret, sig_payload, hashlib.sha256).hexdigest()

    headers = {
        'Content-Type': 'application/json',
        'X-Webhook-Signature': f'sha256={signature}',
        'X-Webhook-Timestamp': str(timestamp),
        'X-Webhook-Event-Id': payload.get('id', str(uuid.uuid4())),
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        for attempt in range(max_retries):
            try:
                resp = await client.post(url, content=body, headers=headers)
                if 200 <= resp.status_code < 300:
                    return  # success
                # 4xx → don't retry (client bug)
                if 400 <= resp.status_code < 500:
                    raise WebhookDeliveryError(f'4xx: {resp.status_code}')
                # 5xx → retry
            except httpx.RequestError:
                pass

            # Exponential backoff with jitter
            delay = (2 ** attempt) + random.uniform(0, 1)
            await asyncio.sleep(delay)

        raise WebhookDeliveryError('Max retries exceeded')
```

### Dead Letter Queue (DLQ) for Failed Webhooks

```python
class WebhookDelivery(Base):
    __tablename__ = 'webhook_deliveries'

    id = Column(Integer, primary_key=True)
    event_id = Column(String, unique=True, index=True)
    url = Column(String)
    payload = Column(JSON)
    status = Column(String, default='pending')  # pending, sent, failed
    attempts = Column(Integer, default=0)
    next_retry_at = Column(DateTime)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())


# Periodic worker
async def retry_failed_webhooks():
    pending = await db.fetch_pending_webhooks()
    for w in pending:
        try:
            await deliver_webhook(w.url, w.payload, SECRET)
            w.status = 'sent'
        except WebhookDeliveryError as e:
            w.attempts += 1
            w.last_error = str(e)
            if w.attempts >= MAX_ATTEMPTS:
                w.status = 'dead'
            else:
                w.next_retry_at = backoff_time(w.attempts)
        await db.save(w)
```

---

## How It Works Internally

### Why HMAC vs Plain Signature?

- **HMAC**: symmetric (shared secret), prevents length-extension attacks vs naive `hash(secret + body)`
- **Plain hash + secret**: vulnerable to length-extension (SHA1, SHA256 raw)
- **Asymmetric (RSA/ECDSA)**: heavier, used when sender shouldn't know verifying key

### `hmac.compare_digest` — Timing Attack Prevention

```python
# VULNERABLE
def compare(a, b):
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if x != y:
            return False
    return True   # exits early on first mismatch → timing leak


# SAFE (constant time)
hmac.compare_digest(a, b)
```

### Idempotency via Redis SETNX

```
SET webhook:stripe:evt_1234 "1" EX 604800 NX
```

`NX` = only if not exists. `EX 604800` = expire after 7 days. Atomic operation.

### Idempotency vs Deduplication Window

Tradeoff: how long to remember? Stripe keeps 24 hours. Bank: 7 days. Forever (DB unique constraint): safest but storage cost.

---

## Common Pitfalls

### 1. Using `==` for Signature

```python
if expected == received:  # timing leak
```

Use `hmac.compare_digest`.

### 2. Verifying After Parsing Body

```python
# WRONG — body already parsed → tampered if attacker manipulates parser
body = await request.json()
verify(json.dumps(body), signature)  # different bytes than original

# RIGHT — use raw bytes
body = await request.body()
verify(body, signature)
event = json.loads(body)
```

### 3. No Timestamp Tolerance

No window = clock skew breaks legitimate webhooks. Too wide = replay window. 5-minute tolerance is industry standard.

### 4. Idempotency Lock Without Release on Failure

```python
r.set(key, '1', nx=True)
# If process_event() raises and we don't release, retry blocked forever
process_event(event)
```

Either: release lock on exception, OR set TTL short enough that natural expiry retries.

### 5. Returning 5xx on Application Errors

Receiver: webhook arrived but processing failed → return 5xx → sender retries → good.

But: if 5xx but already processed (lock taken), retries blocked. Use idempotent processing.

### 6. Synchronous Heavy Work in Webhook Handler

```python
@app.post("/webhook")
async def webhook(request: Request):
    # ... long processing ...  # ← sender times out
```

**Fix:** Verify + ack quickly, dispatch to background:

```python
@app.post("/webhook")
async def webhook(request: Request, background: BackgroundTasks):
    body = await request.body()
    if not verify_signature(body, ...):
        raise HTTPException(401)
    background.add_task(process_webhook_async, body)
    return {'status': 'received'}
```

### 7. Trusting Webhook Source IP

Stripe documents IP ranges, but they change. Use signature verification, not IP allowlist.

### 8. Secret Rotation Without Versioning

Switching secret without overlap → in-flight webhooks fail. Versioned signatures:

```
X-Webhook-Signature: sha256=abc...; key_id=v2
```

Receiver tries both v1 and v2 during rotation window.

---

## Interview Q&A

**Q1:** Webhook signature verification kaise karte ho?
**A:** HMAC-SHA256 of raw body (not parsed JSON) with shared secret. Compare with header value using `hmac.compare_digest` (constant-time, no timing leak). Reject mismatch with 401. Use raw `request.body()` bytes — never re-serialize.

**Q2:** Replay attack se webhook kaise protect karoge?
**A:** Include timestamp in signed payload. Receiver checks `|now - timestamp| < window` (typically 5 min). Combined with event_id idempotency: even if replay within window, second processing skipped via DB/Redis check.

**Q3:** Idempotency exact details?
**A:** Sender includes unique event_id. Receiver: (1) SETNX in Redis with TTL = retention period. (2) If lock acquired, process. (3) If failed, release lock so retry can proceed. (4) DB unique constraint on event_id as defense-in-depth.

**Q4:** Stripe webhook handle karne ka full pattern?
**A:** (1) `stripe.Webhook.construct_event(body, sig_header, secret)` for verification. (2) Idempotent check via event['id']. (3) Quick 200 response. (4) Background task processes event. (5) On unrecoverable error, log + DLQ. (6) Stripe retries on 5xx; on 2xx considers delivered.

**Q5:** Outgoing webhook retry strategy?
**A:** Exponential backoff with jitter: `delay = 2^attempt + random(0,1)`. Max 5-10 attempts. Cap delay (e.g., 1 hour). 4xx → no retry (client bug). 5xx/network error → retry. Dead-letter after max attempts for manual investigation.

**Q6:** Idempotency-Key header outgoing kab use karoge?
**A:** When calling external APIs with side effects (charge, send SMS). Generate UUID per logical operation, use SAME key on retries. External API caches result by key, returns same response on duplicate. Prevents double-charging on network blip + retry.

**Q7:** Webhook listener latency budget?
**A:** Sender typically times out at 10-30 seconds. Strategy: verify sig (fast), persist event to queue/DB, return 200. Process async. If process fails async, retry from DB later. Never block the HTTP response.

**Q8:** Secret rotation pattern?
**A:** Versioned signatures. Sender includes `key_id`. Receiver supports old + new during rotation window. Stripe pattern: `Stripe-Signature: v1=..., v0=...` — multiple sigs per request, accept any valid. After grace period, drop old secret.

---

## Real-World Use Cases

### 1. Stripe Webhook Receiver

```python
import stripe


@app.post("/webhook/stripe")
async def stripe_webhook(request: Request, stripe_signature: str = Header(...)):
    body = await request.body()
    try:
        event = stripe.Webhook.construct_event(
            payload=body,
            sig_header=stripe_signature,
            secret=STRIPE_WEBHOOK_SECRET,
        )
    except (stripe.error.SignatureVerificationError, ValueError):
        raise HTTPException(401)

    # Idempotency
    if r.exists(f'stripe:event:{event.id}'):
        return {'status': 'duplicate'}
    r.set(f'stripe:event:{event.id}', '1', ex=86400 * 7)

    # Dispatch
    if event.type == 'payment_intent.succeeded':
        await handle_payment_succeeded(event.data.object)

    return {'status': 'ok'}
```

### 2. GitHub Webhook (X-Hub-Signature-256)

```python
@app.post("/webhook/github")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str = Header(...),
):
    body = await request.body()
    if not verify_github_signature(body, x_hub_signature_256, GITHUB_SECRET):
        raise HTTPException(401)

    event = json.loads(body)
    # ... handle pull_request, push, etc
```

### 3. Outgoing Webhook from Your App

Customer subscribes to events → save (url, secret, events[]) → on event, deliver with HMAC + retry.

---

## References

- [Stripe webhook signatures](https://stripe.com/docs/webhooks/signatures)
- [GitHub webhook security](https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries)
- [Standard webhook spec](https://www.standardwebhooks.com/)
- RFC 8915 — Network Time Security (for clock sync)
