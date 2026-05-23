# 40 — Webhooks Design

---

## What & Why

**Webhook** = HTTP callback — your server sends an HTTP POST to a client-registered URL when an event occurs.

```
Traditional polling:              Webhook (event-driven):
Client: "Any updates?"            Server: "Event happened!" → POST /your-url
Server: "No"                      Client: receives and processes
Client: "Any updates?"  ← waste   (no polling overhead)
Server: "No"
Client: "Any updates?"
Server: "Yes! Here it is"
```

**Real-world examples:**
- Stripe → your server: "payment_intent.succeeded"
- GitHub → CI/CD: "push to main branch"
- Twilio → your server: "SMS received"
- Shopify → your app: "order.created"

---

## 1. Webhook Registration & Management

```python
from dataclasses import dataclass, field
from enum import Enum
import hmac
import hashlib
import uuid
import time

class WebhookEvent(str, Enum):
    PAYMENT_SUCCESS  = "payment.success"
    PAYMENT_FAILED   = "payment.failed"
    ORDER_CREATED    = "order.created"
    USER_REGISTERED  = "user.registered"
    SUBSCRIPTION_CANCELLED = "subscription.cancelled"

@dataclass
class Webhook:
    webhook_id: str
    owner_id: str          # the customer who registered this webhook
    url: str               # endpoint to deliver to
    events: list[str]      # which events to receive
    secret: str            # HMAC signing secret (customer keeps this)
    is_active: bool = True
    created_at: float = field(default_factory=time.time)
    retry_policy: dict = field(default_factory=lambda: {
        "max_retries": 5,
        "initial_delay_sec": 30,
        "backoff_multiplier": 2.0
    })


class WebhookRegistry:
    """CRUD for webhook registrations."""

    async def register(self, owner_id: str, url: str,
                        events: list[str]) -> Webhook:
        """Register a new webhook endpoint."""
        # Validate URL is reachable (optional warmup ping)
        await self._validate_url(url)

        webhook = Webhook(
            webhook_id=str(uuid.uuid4()),
            owner_id=owner_id,
            url=url,
            events=events,
            secret=self._generate_secret()
        )

        await self.db.execute(
            "INSERT INTO webhooks(webhook_id, owner_id, url, events, secret, is_active, created_at) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7)",
            webhook.webhook_id, webhook.owner_id, webhook.url,
            webhook.events, webhook.secret, webhook.is_active, webhook.created_at
        )

        return webhook

    async def list_webhooks(self, owner_id: str) -> list[Webhook]:
        rows = await self.db.query_many(
            "SELECT * FROM webhooks WHERE owner_id=$1 AND is_active=TRUE",
            owner_id
        )
        return [Webhook(**row) for row in rows]

    async def deactivate(self, webhook_id: str, owner_id: str) -> bool:
        await self.db.execute(
            "UPDATE webhooks SET is_active=FALSE WHERE webhook_id=$1 AND owner_id=$2",
            webhook_id, owner_id
        )
        return True

    async def get_webhooks_for_event(self, owner_id: str,
                                      event_type: str) -> list[Webhook]:
        """Get all active webhooks that subscribed to this event type."""
        rows = await self.db.query_many(
            "SELECT * FROM webhooks WHERE owner_id=$1 AND is_active=TRUE "
            "AND $2 = ANY(events)",
            owner_id, event_type
        )
        return [Webhook(**row) for row in rows]

    def _generate_secret(self) -> str:
        """HMAC secret: random 32-byte hex string."""
        import secrets
        return secrets.token_hex(32)

    async def _validate_url(self, url: str):
        """Send a test ping to the URL to verify it's reachable."""
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json={"type": "webhook.test"},
                                         timeout=aiohttp.ClientTimeout(total=5)) as r:
                    if r.status not in range(200, 300):
                        raise ValueError(f"URL returned {r.status}")
        except Exception as e:
            raise ValueError(f"URL validation failed: {e}")
```

---

## 2. Event Publishing & Payload Signing

```python
"""
Webhook security: HMAC-SHA256 signature.
Server signs payload with webhook secret.
Client verifies signature to confirm payload is authentic (not spoofed).

Stripe uses: X-Stripe-Signature: t=<timestamp>,v1=<sig>
GitHub uses: X-Hub-Signature-256: sha256=<sig>
"""

class WebhookPublisher:
    """
    Publish events to registered webhook endpoints.
    Puts delivery tasks on Kafka queue for async processing.
    """

    async def publish_event(self, owner_id: str, event_type: str,
                             payload: dict) -> int:
        """
        Find all webhooks for this event and queue delivery tasks.
        Returns number of webhooks notified.
        """
        webhooks = await self.registry.get_webhooks_for_event(owner_id, event_type)

        event_id = str(uuid.uuid4())
        event_ts = time.time()

        deliveries = 0
        for webhook in webhooks:
            # Create delivery task
            delivery_id = str(uuid.uuid4())

            # Sign the payload
            signed_payload = self._build_payload(
                event_id=event_id,
                event_type=event_type,
                payload=payload,
                timestamp=event_ts
            )
            signature = self._sign(signed_payload, webhook.secret, event_ts)

            # Queue delivery via Kafka (durable, retryable)
            await self.kafka.send("webhook_deliveries", {
                "delivery_id":  delivery_id,
                "webhook_id":   webhook.webhook_id,
                "url":          webhook.url,
                "event_id":     event_id,
                "event_type":   event_type,
                "payload":      signed_payload,
                "signature":    signature,
                "timestamp":    event_ts,
                "attempt":      0
            })

            # Record delivery attempt in DB (for customer visibility)
            await self.db.execute(
                "INSERT INTO webhook_deliveries(delivery_id, webhook_id, event_id, "
                "event_type, status, created_at) VALUES($1,$2,$3,$4,'pending',$5)",
                delivery_id, webhook.webhook_id, event_id, event_type, event_ts
            )
            deliveries += 1

        return deliveries

    def _build_payload(self, event_id: str, event_type: str,
                        payload: dict, timestamp: float) -> dict:
        """Standard webhook payload envelope."""
        return {
            "id":         event_id,
            "type":       event_type,
            "created_at": timestamp,
            "data":       payload
        }

    def _sign(self, payload: dict, secret: str, timestamp: float) -> str:
        """
        HMAC-SHA256 signature.
        Sign: timestamp + "." + JSON payload (prevents replay attacks).
        """
        import json
        payload_str = json.dumps(payload, sort_keys=True)
        signed_content = f"{int(timestamp)}.{payload_str}"
        signature = hmac.new(
            secret.encode("utf-8"),
            signed_content.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return f"t={int(timestamp)},v1={signature}"
```

---

## 3. Delivery Worker (Retry Logic)

```python
"""
Delivery worker: sends HTTP POST to webhook URL.
Retry policy: exponential backoff.
Track delivery status per webhook (customer dashboard).

Retry schedule (max 5 attempts):
  Attempt 1: immediately
  Attempt 2: after 30s
  Attempt 3: after 60s
  Attempt 4: after 120s
  Attempt 5: after 240s
  → Give up, mark as failed, alert customer
"""

import aiohttp
from enum import Enum

class DeliveryStatus(str, Enum):
    PENDING  = "pending"
    SUCCESS  = "success"
    FAILED   = "failed"
    RETRYING = "retrying"

class WebhookDeliveryWorker:
    """
    Consumes from Kafka webhook_deliveries topic.
    Attempts delivery with exponential backoff.
    """

    REQUEST_TIMEOUT_SEC = 30
    MAX_ATTEMPTS = 5
    INITIAL_DELAY_SEC = 30
    BACKOFF_MULTIPLIER = 2.0

    async def process_delivery(self, delivery_task: dict):
        """Process a single webhook delivery attempt."""
        attempt    = delivery_task["attempt"]
        webhook_id = delivery_task["webhook_id"]
        url        = delivery_task["url"]

        try:
            success, response_code = await self._deliver(
                url=url,
                payload=delivery_task["payload"],
                signature=delivery_task["signature"]
            )
        except Exception as e:
            success = False
            response_code = 0
            print(f"Delivery exception: {e}")

        # Update delivery record
        await self.db.execute(
            "INSERT INTO delivery_attempts(delivery_id, attempt, status, response_code, attempted_at) "
            "VALUES($1,$2,$3,$4,NOW())",
            delivery_task["delivery_id"],
            attempt + 1,
            DeliveryStatus.SUCCESS if success else DeliveryStatus.FAILED,
            response_code
        )

        if success:
            await self.db.execute(
                "UPDATE webhook_deliveries SET status='success', delivered_at=NOW() "
                "WHERE delivery_id=$1",
                delivery_task["delivery_id"]
            )
            return

        # Failed — schedule retry
        if attempt + 1 < self.MAX_ATTEMPTS:
            delay = self.INITIAL_DELAY_SEC * (self.BACKOFF_MULTIPLIER ** attempt)
            retry_at = time.time() + delay

            # Schedule retry via Kafka with delay (use Redis ZADD for delayed queue)
            await self.redis.zadd("webhook_retry_queue", {
                __import__("json").dumps({**delivery_task, "attempt": attempt + 1}): retry_at
            })

            await self.db.execute(
                "UPDATE webhook_deliveries SET status='retrying', next_retry_at=$2 "
                "WHERE delivery_id=$1",
                delivery_task["delivery_id"],
                retry_at
            )
        else:
            # Max retries exhausted — mark as permanently failed
            await self.db.execute(
                "UPDATE webhook_deliveries SET status='failed', failed_at=NOW() "
                "WHERE delivery_id=$1",
                delivery_task["delivery_id"]
            )
            # Notify customer (email / in-app alert)
            await self.kafka.send("webhook_alerts", {
                "type":       "delivery_failed",
                "webhook_id": webhook_id,
                "delivery_id": delivery_task["delivery_id"]
            })
            # Auto-disable webhook after too many consecutive failures
            await self._maybe_disable_webhook(webhook_id)

    async def _deliver(self, url: str, payload: dict,
                        signature: str) -> tuple[bool, int]:
        """
        Send HTTP POST to webhook URL.
        Success: 2xx response within timeout.
        Failure: non-2xx, timeout, connection error.
        """
        import json
        headers = {
            "Content-Type":  "application/json",
            "X-Webhook-Signature": signature,
            "X-Webhook-Timestamp": str(int(time.time())),
            "User-Agent": "MyApp-Webhooks/1.0"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    data=json.dumps(payload),
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self.REQUEST_TIMEOUT_SEC)
                ) as response:
                    success = 200 <= response.status < 300
                    return success, response.status
        except asyncio.TimeoutError:
            return False, 408
        except aiohttp.ClientConnectionError:
            return False, 0

    async def _maybe_disable_webhook(self, webhook_id: str,
                                      consecutive_threshold: int = 10):
        """Disable webhook if too many consecutive failures (likely bad URL)."""
        failed_count = await self.db.query_one(
            "SELECT COUNT(*) as cnt FROM webhook_deliveries "
            "WHERE webhook_id=$1 AND status='failed' "
            "AND created_at > NOW() - INTERVAL '24 hours'",
            webhook_id
        )
        if failed_count["cnt"] >= consecutive_threshold:
            await self.registry.deactivate(webhook_id, owner_id=None)
            await self.kafka.send("webhook_alerts", {
                "type": "webhook_auto_disabled",
                "webhook_id": webhook_id,
                "reason": f"{consecutive_threshold} failures in 24h"
            })
```

---

## 4. Delayed Retry Queue

```python
"""
Problem: need to delay retry by 30s, 60s, 120s...
Kafka doesn't natively support delayed messages.

Solution: Redis Sorted Set as delay queue.
Score = Unix timestamp of when to process.
Background poller: every second, fetch jobs with score <= now.
"""

class DelayedRetryPoller:
    """Polls Redis delay queue and republishes to Kafka when ready."""

    async def run(self):
        """Run as a dedicated background process."""
        while True:
            now = time.time()
            # Atomically fetch all jobs ready to process
            jobs = await self.redis.zrangebyscore(
                "webhook_retry_queue",
                min=0, max=now,
                start=0, num=100   # process 100 at a time
            )

            for job_json in jobs:
                # Remove from delay queue (atomic)
                removed = await self.redis.zrem("webhook_retry_queue", job_json)
                if removed:
                    import json
                    delivery_task = json.loads(job_json)
                    # Re-queue for immediate processing
                    await self.kafka.send("webhook_deliveries", delivery_task)

            await __import__("asyncio").sleep(1)
```

---

## 5. Idempotency & Ordering

```python
"""
Idempotency problem:
If our server retries a delivery (network timeout but receiver got it),
receiver may process the same event twice.

Solution: Include idempotency key in every delivery.
Receiver should deduplicate on event_id.

Ordering problem:
Events may arrive out of order (retry of event 1 arrives after event 2).
Solution: Include sequence number + timestamp. Let receiver decide.
"""

class ReceiverIdempotencyGuard:
    """
    Client-side: deduplicate webhook events using event_id.
    Stores processed event_ids in Redis.
    """

    EVENT_ID_TTL = 86400 * 7   # store for 7 days

    def __init__(self, redis_client):
        self.redis = redis_client

    async def is_duplicate(self, event_id: str) -> bool:
        return bool(await self.redis.get(f"processed_event:{event_id}"))

    async def mark_processed(self, event_id: str):
        await self.redis.setex(f"processed_event:{event_id}",
                                self.EVENT_ID_TTL, "1")

    def verify_signature(self, payload: str, signature_header: str,
                          secret: str, tolerance_sec: int = 300) -> bool:
        """
        Verify HMAC signature and check timestamp freshness.
        Prevents replay attacks (old signatures replayed).
        """
        # Parse: t=1234567890,v1=abc123def
        parts = dict(p.split("=", 1) for p in signature_header.split(","))
        timestamp = int(parts.get("t", 0))
        provided_sig = parts.get("v1", "")

        # Check timestamp freshness (within 5 minutes)
        if abs(time.time() - timestamp) > tolerance_sec:
            raise ValueError("Webhook timestamp too old — possible replay attack")

        # Recompute signature
        signed_content = f"{timestamp}.{payload}"
        expected_sig = hmac.new(
            secret.encode(),
            signed_content.encode(),
            hashlib.sha256
        ).hexdigest()

        # Constant-time comparison (prevent timing attacks)
        return hmac.compare_digest(expected_sig, provided_sig)


# Example FastAPI webhook receiver:
async def receive_payment_webhook(request, redis, secret: str):
    body = await request.body()
    sig  = request.headers.get("X-Webhook-Signature", "")

    guard = ReceiverIdempotencyGuard(redis)

    # 1. Verify signature
    if not guard.verify_signature(body.decode(), sig, secret):
        return {"error": "Invalid signature"}, 401

    import json
    event = json.loads(body)
    event_id = event["id"]

    # 2. Deduplicate
    if await guard.is_duplicate(event_id):
        return {"status": "already_processed"}   # 200 OK to stop retries!

    # 3. Process event
    await process_payment_event(event)
    await guard.mark_processed(event_id)

    return {"status": "ok"}
```

---

## 6. Delivery Guarantees

```
At-most-once:    Send once, no retry. Simplest. Risk: lost events.
At-least-once:   Retry on failure. Events may duplicate. Most webhook systems.
Exactly-once:    Retry + receiver deduplication on event_id. Best UX.

Our design: AT-LEAST-ONCE delivery + idempotency key for exactly-once semantics.
```

---

## 7. Customer Dashboard

```python
class WebhookDashboardService:
    """APIs for customer to view webhook delivery history."""

    async def get_delivery_history(self, webhook_id: str,
                                    limit: int = 50) -> list[dict]:
        return await self.db.query_many(
            """
            SELECT d.delivery_id, d.event_type, d.status, d.created_at,
                   d.delivered_at, d.failed_at,
                   json_agg(a ORDER BY a.attempt) as attempts
            FROM webhook_deliveries d
            LEFT JOIN delivery_attempts a USING(delivery_id)
            WHERE d.webhook_id=$1
            GROUP BY d.delivery_id
            ORDER BY d.created_at DESC
            LIMIT $2
            """,
            webhook_id, limit
        )

    async def retry_failed_delivery(self, delivery_id: str,
                                     owner_id: str) -> bool:
        """Allow customer to manually retry a failed delivery."""
        delivery = await self.db.query_one(
            "SELECT d.*, w.url, w.secret FROM webhook_deliveries d "
            "JOIN webhooks w USING(webhook_id) "
            "WHERE d.delivery_id=$1 AND w.owner_id=$2",
            delivery_id, owner_id
        )
        if not delivery or delivery["status"] != "failed":
            return False

        await self.kafka.send("webhook_deliveries", {
            **delivery,
            "attempt": 0,   # reset attempt counter for manual retry
            "delivery_id": str(uuid.uuid4()),   # new delivery ID
        })
        return True

    async def get_webhook_stats(self, webhook_id: str,
                                 days: int = 7) -> dict:
        stats = await self.db.query_one(
            """
            SELECT
              COUNT(*) as total,
              SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) as succeeded,
              SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as failed,
              AVG(EXTRACT(EPOCH FROM (delivered_at - created_at))) as avg_delivery_sec
            FROM webhook_deliveries
            WHERE webhook_id=$1
              AND created_at > NOW() - ($2 || ' days')::INTERVAL
            """,
            webhook_id, days
        )
        return {
            "total":            stats["total"],
            "succeeded":        stats["succeeded"],
            "failed":           stats["failed"],
            "success_rate":     stats["succeeded"] / max(stats["total"], 1),
            "avg_delivery_sec": stats["avg_delivery_sec"]
        }
```

---

## 8. Failure Scenarios

| Scenario | Solution |
|----------|----------|
| Receiver URL is down | Exponential backoff retry (5 attempts over 4 hours) |
| Network timeout (receiver got it, we didn't know) | Idempotency key — receiver deduplicates |
| Receiver returns 5xx | Treat as failure → retry |
| Replay attack | Timestamp in signature + 5-minute tolerance window |
| Spoofed webhook | HMAC-SHA256 verification required before processing |
| Out-of-order delivery | Include event timestamp + sequence. Receiver handles ordering |
| DB overload from delivery records | Partition delivery_attempts by date, archive old records |
| Webhook URL changes (customer moved service) | Customer updates webhook URL. Old deliveries retry to new URL after update |

---

## 9. Interview Questions

**Q1: How do you guarantee webhook delivery if the receiver is temporarily down?**
> At-least-once delivery with exponential backoff retry: attempt 1 immediately, then wait 30s, 60s, 120s, 240s (5 attempts over ~7 minutes). If all fail, mark as permanently failed and alert customer. Delivery state stored in DB with status (pending/retrying/success/failed). Customer can manually retry failed deliveries. Durable Kafka queue survives publisher crashes.

**Q2: How does webhook signature verification work?**
> Server computes HMAC-SHA256 of `{timestamp}.{payload_json}` using webhook's secret key. Result sent in `X-Signature` header. Receiver recomputes with the same secret and compares (constant-time comparison to prevent timing attacks). Timestamp check (within 5 minutes) prevents replay attacks where attacker captures and resends a valid old request.

**Q3: What is the idempotency problem in webhooks?**
> If our server retries a delivery (HTTP timeout, but receiver processed it), receiver gets the same event twice. Fix: include a unique `event_id` in every payload. Receiver stores processed event_ids in Redis (7-day TTL). Before processing, check if `event_id` was already handled. If yes, return 200 immediately (tells sender to stop retrying) without reprocessing.

**Q4: How to design the retry queue with delays?**
> Kafka doesn't support delayed messages natively. Solution: Redis Sorted Set as delay queue. Score = Unix timestamp when to process. On failure: `ZADD webhook_retry_queue <retry_at_timestamp> <delivery_json>`. Background poller every second: `ZRANGEBYSCORE 0 <now>` → fetch ready jobs → republish to Kafka → `ZREM`. This gives precise delay control without Kafka modifications.

**Q5: How to prevent a customer from registering a webhook to attack a third-party server?**
> (1) SSRF protection: block private IP ranges (10.x, 172.16.x, 192.168.x, localhost) in URL validation. (2) URL allowlist: only HTTPS. (3) Warmup ping: send test event on registration — if URL doesn't respond with 200, reject registration. (4) Rate limiting: max X deliveries/second to same domain. (5) User account verification before enabling webhooks.

**Q6: How do you handle ordering — events must be processed in order?**
> Webhooks are inherently unordered (retries can cause event 1 to arrive after event 2). Solutions: (1) Include sequence number and timestamp in payload, let receiver reorder. (2) Single delivery channel per resource (e.g., one queue per order_id) to preserve order for that resource. (3) For strict ordering: use message queue (SQS FIFO) between webhook sender and processor on receiver side. Generally, design event consumers to be commutative and idempotent.
