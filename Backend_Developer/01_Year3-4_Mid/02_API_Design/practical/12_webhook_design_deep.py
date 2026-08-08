"""
Webhook System — Production Patterns

Both receiver and sender sides.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import random
import time
import uuid
from datetime import datetime, timedelta
from typing import Any

import httpx
import redis.asyncio as aioredis
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel


app = FastAPI()
r = aioredis.from_url('redis://localhost:6379/0', decode_responses=True)
log = logging.getLogger(__name__)


# ==========================================================================
# 1. SIGNING (sender side)
# ==========================================================================

def sign_payload(body: bytes, timestamp: int, secret: str) -> str:
    """Generate HMAC-SHA256 signature."""
    signed_payload = f'{timestamp}.'.encode() + body
    return hmac.new(
        secret.encode(),
        signed_payload,
        hashlib.sha256,
    ).hexdigest()


def make_webhook_headers(body: bytes, secret: str, event_id: str = None) -> dict:
    timestamp = int(time.time())
    return {
        'Content-Type': 'application/json',
        'X-Webhook-Timestamp': str(timestamp),
        'X-Webhook-Signature': f'sha256={sign_payload(body, timestamp, secret)}',
        'X-Webhook-Event-Id': event_id or str(uuid.uuid4()),
        'User-Agent': 'MyApp-Webhooks/1.0',
    }


# ==========================================================================
# 2. VERIFICATION (receiver side)
# ==========================================================================

TIMESTAMP_TOLERANCE = 300   # 5 min replay window


def verify_signature(
    body: bytes,
    signature: str,
    timestamp: int,
    secret: str,
    tolerance: int = TIMESTAMP_TOLERANCE,
) -> bool:
    """Verify HMAC + replay window. Constant-time compare."""

    if abs(time.time() - timestamp) > tolerance:
        return False

    received = signature.removeprefix('sha256=')
    expected = sign_payload(body, timestamp, secret)

    # Constant-time compare prevents timing attacks
    return hmac.compare_digest(expected, received)


def verify_multi_secret(body, signature, timestamp, secrets: list[str]) -> bool:
    """Try multiple secrets — useful during secret rotation."""
    return any(
        verify_signature(body, signature, timestamp, s)
        for s in secrets
    )


# ==========================================================================
# 3. RECEIVER ENDPOINT (full pattern)
# ==========================================================================

WEBHOOK_SECRETS = [
    'whsec_current_secret',
    'whsec_old_secret_during_rotation',
]


@app.post('/webhooks/incoming')
async def receive_webhook(
    request: Request,
    background: BackgroundTasks,
    x_signature: str = Header(..., alias='X-Webhook-Signature'),
    x_timestamp: int = Header(..., alias='X-Webhook-Timestamp'),
    x_event_id: str = Header(..., alias='X-Webhook-Event-Id'),
):
    # 1. Read raw bytes (don't parse yet)
    body = await request.body()

    # 2. Verify signature
    if not verify_multi_secret(body, x_signature, x_timestamp, WEBHOOK_SECRETS):
        log.warning(f'Invalid signature from {request.client.host}')
        raise HTTPException(401, 'Invalid signature')

    # 3. Idempotency check (SETNX with TTL)
    idempotency_key = f'webhook:processed:{x_event_id}'
    acquired = await r.set(idempotency_key, '1', ex=86400 * 7, nx=True)

    if not acquired:
        # Already processed — return 200 (don't make sender retry)
        log.info(f'Duplicate webhook event {x_event_id}')
        return {'status': 'duplicate', 'event_id': x_event_id}

    # 4. Parse + validate
    try:
        event = json.loads(body)
    except json.JSONDecodeError:
        await r.delete(idempotency_key)
        raise HTTPException(400, 'Invalid JSON')

    # 5. Queue for async processing
    background.add_task(process_event_async, event, x_event_id)

    # 6. Acknowledge IMMEDIATELY (< 5s SLA)
    return {'status': 'received', 'event_id': x_event_id}


async def process_event_async(event: dict, event_id: str):
    """Background processing — release idempotency lock on failure."""
    try:
        event_type = event.get('type', '')
        handler = EVENT_HANDLERS.get(event_type)
        if handler:
            await handler(event['data'])
        else:
            log.warning(f'No handler for event type: {event_type}')
    except Exception as e:
        log.exception(f'Failed to process event {event_id}: {e}')
        # Release lock so retry from sender can re-process
        await r.delete(f'webhook:processed:{event_id}')


# Event handlers registry
async def handle_payment_succeeded(data):
    # ... business logic
    pass


async def handle_payment_failed(data):
    pass


async def handle_subscription_created(data):
    pass


EVENT_HANDLERS = {
    'payment.succeeded': handle_payment_succeeded,
    'payment.failed': handle_payment_failed,
    'subscription.created': handle_subscription_created,
}


# ==========================================================================
# 4. STRIPE-STYLE SIGNATURE (multi-version)
# ==========================================================================

def parse_stripe_signature(header: str) -> dict[str, list[str]]:
    parts: dict[str, list[str]] = {}
    for chunk in header.split(','):
        k, _, v = chunk.partition('=')
        if k and v:
            parts.setdefault(k.strip(), []).append(v.strip())
    return parts


def verify_stripe_webhook(body: bytes, header: str, secrets: list[bytes]) -> bool:
    parsed = parse_stripe_signature(header)

    timestamps = parsed.get('t', [])
    if not timestamps:
        return False

    try:
        timestamp = int(timestamps[0])
    except ValueError:
        return False

    if abs(time.time() - timestamp) > TIMESTAMP_TOLERANCE:
        return False

    v1_sigs = parsed.get('v1', [])
    if not v1_sigs:
        return False

    payload = f'{timestamp}.'.encode() + body

    for secret in secrets:
        expected = hmac.new(secret, payload, hashlib.sha256).hexdigest()
        if any(hmac.compare_digest(expected, sig) for sig in v1_sigs):
            return True

    return False


# ==========================================================================
# 5. SENDER — DELIVERY WITH RETRY
# ==========================================================================

class WebhookDeliveryError(Exception):
    pass


def should_retry(status_code: int | None) -> bool:
    """4xx (except 408, 429) = permanent; 5xx/timeout = retry."""
    if status_code is None:
        return True   # network error
    if 200 <= status_code < 300:
        return False
    if 400 <= status_code < 500 and status_code not in {408, 429}:
        return False
    return True


def compute_retry_delay(attempt: int) -> float:
    """Exponential backoff with jitter, capped at 1 hour."""
    base = 2 ** attempt
    delay = min(base, 3600)
    jitter = random.uniform(0, 0.3 * delay)
    return delay + jitter


async def deliver_webhook(
    url: str,
    payload: dict,
    secret: str,
    timeout: float = 10.0,
) -> tuple[int | None, str]:
    """Single delivery attempt. Returns (status_code, response_or_error)."""

    body = json.dumps(payload).encode()
    event_id = payload.get('id', str(uuid.uuid4()))
    headers = make_webhook_headers(body, secret, event_id)

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.post(url, content=body, headers=headers)
            return resp.status_code, resp.text[:1000]
        except httpx.RequestError as e:
            return None, str(e)


# ==========================================================================
# 6. PERSISTENT DELIVERY MODEL + WORKER
# ==========================================================================

"""
# models.py

from django.db import models


class WebhookSubscription(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    customer_id = models.IntegerField()
    url = models.URLField()
    secret = models.CharField(max_length=64)
    secret_previous = models.CharField(max_length=64, blank=True)  # for rotation
    events = models.JSONField(default=list)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


class WebhookDelivery(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    subscription = models.ForeignKey(WebhookSubscription, on_delete=models.CASCADE)
    event_id = models.UUIDField(unique=True, db_index=True)
    event_type = models.CharField(max_length=100)
    payload = models.JSONField()

    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('sent', 'Sent'),
            ('failed', 'Failed'),
            ('dead', 'Dead'),
        ],
        default='pending',
    )
    attempts = models.IntegerField(default=0)
    next_retry_at = models.DateTimeField(db_index=True)
    last_attempt_at = models.DateTimeField(null=True)
    last_response_status = models.IntegerField(null=True)
    last_error = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['status', 'next_retry_at']),
            models.Index(fields=['subscription', '-created_at']),
        ]
"""


# ==========================================================================
# 7. PUBLISHING AN EVENT
# ==========================================================================

async def publish_event(event_type: str, data: dict):
    """Fan out event to all subscribed customer webhooks."""

    event = {
        'id': str(uuid.uuid4()),
        'type': event_type,
        'created_at': datetime.utcnow().isoformat(),
        'data': data,
    }

    # subscriptions = WebhookSubscription.objects.filter(
    #     events__contains=event_type,
    #     active=True,
    # )

    # Mock subscriptions
    subscriptions = [
        {'id': 'sub1', 'url': 'https://customer1.example.com/webhook', 'secret': 'whsec_1'},
        {'id': 'sub2', 'url': 'https://customer2.example.com/webhook', 'secret': 'whsec_2'},
    ]

    for sub in subscriptions:
        # Create delivery record
        delivery = {
            'id': uuid.uuid4().hex,
            'subscription_id': sub['id'],
            'event_id': event['id'],
            'event_type': event_type,
            'payload': event,
            'status': 'pending',
            'attempts': 0,
            'next_retry_at': datetime.utcnow(),
        }
        # WebhookDelivery.objects.create(**delivery)

        # Try immediate delivery
        # await attempt_delivery(delivery, sub)


async def attempt_delivery(delivery: dict, subscription: dict):
    """Single attempt; update delivery record."""

    status, response = await deliver_webhook(
        subscription['url'],
        delivery['payload'],
        subscription['secret'],
    )

    delivery['last_attempt_at'] = datetime.utcnow()
    delivery['last_response_status'] = status
    delivery['attempts'] += 1

    if not should_retry(status):
        if status and 200 <= status < 300:
            delivery['status'] = 'sent'
        else:
            delivery['status'] = 'dead'
            delivery['last_error'] = response
            # notify_customer(subscription, delivery)
    else:
        # Schedule next retry
        delay = compute_retry_delay(delivery['attempts'])
        delivery['next_retry_at'] = datetime.utcnow() + timedelta(seconds=delay)
        delivery['last_error'] = response
        if delivery['attempts'] >= 15:
            delivery['status'] = 'dead'
            # notify_customer(subscription, delivery)
        else:
            delivery['status'] = 'failed'

    # WebhookDelivery.objects.filter(pk=delivery['id']).update(**delivery)


# ==========================================================================
# 8. RETRY WORKER (Celery task)
# ==========================================================================

"""
@shared_task
def retry_failed_webhooks():
    \"\"\"Run every minute. Pick up pending/failed deliveries that are due.\"\"\"

    now = timezone.now()
    deliveries = (
        WebhookDelivery.objects
        .select_related('subscription')
        .filter(
            status__in=['pending', 'failed'],
            next_retry_at__lte=now,
            attempts__lt=15,
        )
        .order_by('next_retry_at')[:1000]
    )

    for delivery in deliveries:
        try:
            attempt_delivery(delivery)
        except Exception as e:
            log.exception(f'Worker error on delivery {delivery.id}: {e}')


# Celery beat schedule
CELERY_BEAT_SCHEDULE = {
    'retry-webhooks': {
        'task': 'webhooks.tasks.retry_failed_webhooks',
        'schedule': 60.0,   # every 60s
    },
}
"""


# ==========================================================================
# 9. CUSTOMER DASHBOARD ENDPOINTS
# ==========================================================================

@app.get('/webhook-subscriptions/{sub_id}/deliveries')
async def list_deliveries(sub_id: str, status: str = None, limit: int = 100):
    """Customer can view delivery history + status."""
    # qs = WebhookDelivery.objects.filter(subscription_id=sub_id)
    # if status:
    #     qs = qs.filter(status=status)
    # deliveries = qs.order_by('-created_at')[:limit]
    return {'deliveries': []}


@app.post('/webhook-deliveries/{delivery_id}/replay')
async def replay_delivery(delivery_id: str):
    """Customer triggers manual replay."""
    # delivery = WebhookDelivery.objects.get(pk=delivery_id)
    # delivery.status = 'pending'
    # delivery.attempts = 0
    # delivery.next_retry_at = timezone.now()
    # delivery.save()
    return {'replayed': True}


@app.post('/webhook-subscriptions/{sub_id}/secret/rotate')
async def rotate_secret(sub_id: str):
    """Generate new secret. Both old and new accepted for 7 days."""
    # sub = WebhookSubscription.objects.get(pk=sub_id)
    # sub.secret_previous = sub.secret
    # sub.secret = f'whsec_{secrets.token_urlsafe(32)}'
    # sub.save()
    # schedule_old_secret_purge.apply_async(args=[sub_id], countdown=86400 * 7)
    return {'new_secret': 'whsec_xyz123...'}


# ==========================================================================
# 10. WEBHOOK TEST SEND
# ==========================================================================

@app.post('/webhook-subscriptions/{sub_id}/test')
async def test_webhook(sub_id: str):
    """Send sample event to verify subscription works."""
    test_event = {
        'id': f'evt_test_{uuid.uuid4().hex[:8]}',
        'type': 'test.ping',
        'created_at': datetime.utcnow().isoformat(),
        'data': {'message': 'This is a test webhook'},
    }

    # sub = WebhookSubscription.objects.get(pk=sub_id)
    # status, response = await deliver_webhook(sub.url, test_event, sub.secret)
    status, response = 200, '{"received": true}'

    return {
        'status_code': status,
        'response_preview': response[:500],
    }


# ==========================================================================
# 11. WEBHOOK CHALLENGE (for subscription verification)
# ==========================================================================

@app.post('/webhooks/verify')
async def webhook_verify(request: Request):
    """
    Some platforms (Slack, Discord) require challenge-response to verify endpoint.
    Receiver echoes back challenge token to prove ownership.
    """
    body = await request.json()
    if body.get('type') == 'url_verification':
        return {'challenge': body.get('challenge')}
    return {'ok': True}


# ==========================================================================
# 12. NGROK / STRIPE CLI for LOCAL TESTING
# ==========================================================================

LOCAL_TESTING_GUIDE = """
# ngrok — expose localhost via HTTPS
npm install -g ngrok
ngrok http 8000

# → https://abc123.ngrok-free.app forwarding to http://localhost:8000


# Stripe CLI
stripe listen --forward-to localhost:8000/webhooks/stripe
stripe trigger payment_intent.succeeded


# GitHub: use smee.io
npx smee -u https://smee.io/abc -t http://localhost:8000/webhooks/github


# Save sample payloads for replay
curl -X POST http://localhost:8000/webhooks/test \\
    -H 'Content-Type: application/json' \\
    -H 'X-Webhook-Signature: sha256=...' \\
    -d @sample-event.json
"""


# ==========================================================================
# 13. MONITORING & METRICS
# ==========================================================================

WEBHOOK_METRICS = """
from prometheus_client import Counter, Histogram


WEBHOOK_DELIVERIES = Counter(
    'webhook_deliveries_total',
    'Webhook delivery attempts',
    ['event_type', 'status']
)

WEBHOOK_DURATION = Histogram(
    'webhook_delivery_duration_seconds',
    'Webhook delivery duration',
    ['event_type']
)

WEBHOOK_QUEUE_DEPTH = Gauge(
    'webhook_queue_depth',
    'Pending webhook deliveries'
)


# Alerts:
# - Delivery success rate < 95% (broad issue)
# - Per-customer success rate < 80% (customer endpoint down)
# - Queue depth > 10000 (worker behind)
# - Dead deliveries > N per hour (alert ops + customer)
"""


# ==========================================================================
# 14. PROD CHECKLIST
# ==========================================================================

PROD_CHECKLIST = """
Sender side:
[ ] HTTPS-only delivery URLs
[ ] HMAC SHA256 signing (sender + receiver have shared secret)
[ ] Timestamp in signed payload (replay protection)
[ ] Event ID for idempotency (unique per event)
[ ] User-Agent identifying your service
[ ] 10s timeout per attempt
[ ] Exponential backoff with jitter
[ ] Max attempts (10-15)
[ ] Persist deliveries in DB (DLQ for failures)
[ ] Secret rotation support (sender sends multiple sigs)
[ ] Customer dashboard: logs, replay, test, pause
[ ] Metrics + alerts

Receiver side:
[ ] Read raw bytes BEFORE parsing
[ ] Verify HMAC with constant-time compare
[ ] Validate timestamp window (5 min)
[ ] Idempotency check via Redis SETNX
[ ] Respond < 5 seconds (queue for async processing)
[ ] Return 2xx for success/duplicate (200)
[ ] Return 4xx for permanent errors (signature, parse)
[ ] Return 5xx for temporary (will retry)
[ ] Log all received events (audit trail)
[ ] Handle unknown event types gracefully (return 200, log)
"""


# ==========================================================================
# RUNNABLE LAB — Sign + Verify, Tamper-Detection Proof (Docker-free)
# ==========================================================================
"""
LAB OBJECTIVE: Section 1 (sign_payload) and Section 2 (verify_signature)
above are the reference implementation. This lab has you write both again
from scratch — the point isn't to duplicate code, it's to prove you
understand WHY signing works: a signature is a promise about the EXACT
bytes that were signed. Flip one bit after signing and verification must
fail, or the entire scheme is worthless.

TASK:
  1. TODO: `_sign()` (sender) and `_verify()` (receiver) — implement for
     real (Section 1/2 above show the reference, but write it yourself).
  2. Run: python3 12_webhook_design_deep.py
"""


def _sign(body: bytes, timestamp: int, secret: str) -> str:
    """Sender side: HMAC-SHA256 over f'{timestamp}.{body}'."""
    # ─────────────────────────────────────────────────────
    # TODO: same construction as Section 1's sign_payload():
    #   signed_payload = f'{timestamp}.'.encode() + body
    #   return hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    #
    signed_payload = f'{timestamp}.'.encode() + body
    return hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    # ─────────────────────────────────────────────────────


def _verify(body: bytes, signature: str, timestamp: int, secret: str) -> bool:
    """Receiver side: recompute + constant-time compare."""
    # ─────────────────────────────────────────────────────
    # TODO: same construction as Section 2's verify_signature():
    #   expected = _sign(body, timestamp, secret)
    #   return hmac.compare_digest(expected, signature)
    #   (NOTE: use compare_digest, not `==` — plain `==` short-circuits on
    #   the first mismatched byte, leaking timing info an attacker can use
    #   to guess the signature byte-by-byte.)
    #
    expected = _sign(body, timestamp, secret)
    return hmac.compare_digest(expected, signature)
    # ─────────────────────────────────────────────────────


def main() -> None:
    secret = "whsec_test_secret"
    timestamp = int(time.time())
    payload = {"id": "evt_1", "type": "payment.succeeded", "data": {"amount": 4999}}
    body = json.dumps(payload).encode()

    print("\n[1] correctly-signed payload")
    signature = _sign(body, timestamp, secret)
    valid = _verify(body, signature, timestamp, secret)
    print(f"  signature: {signature[:24]}...")
    print(f"  verify(untampered) → {valid}")

    print("\n[2] tampered payload (flip a bit AFTER signing, signature unchanged)")
    tampered = bytearray(body)
    mid = len(tampered) // 2
    tampered[mid] ^= 0xFF
    tampered = bytes(tampered)
    tampered_valid = _verify(tampered, signature, timestamp, secret)
    print(f"  tampered body differs at byte {mid}: {body[max(0, mid - 5):mid + 5]!r} → "
          f"{tampered[max(0, mid - 5):mid + 5]!r}")
    print(f"  verify(tampered)   → {tampered_valid}")

    print("\n" + "─" * 55)
    if valid and not tampered_valid:
        print("✅ PASS — untampered payload accepted, tampered payload REJECTED")
        print("   (this IS the entire point of webhook signing — payload integrity)")
    elif tampered_valid:
        print("❌ FAIL — tampered payload was ACCEPTED. This is a security hole:")
        print("   _verify() is either always returning True, or not actually comparing")
        print("   the recomputed HMAC against the given signature. Fix the TODO.")
    else:
        print("❌ FAIL — even the UNTAMPERED payload failed verification.")
        print("   _sign()/_verify() don't agree — check both TODOs use the same")
        print("   f'{timestamp}.' + body construction as Section 1/2 above.")

    print("""
SOCH:
  1. hmac.compare_digest() kyu, == kyu nahi? (constant-time — timing attack se bachta hai)
  2. Signature payload me timestamp bhi included hai (f'{timestamp}.{body}') —
     agar sirf body sign karte to replay attack me kya farak padta?
  3. Section 3 (receive_webhook) me signature check ke BAAD hi JSON parse
     hota hai. Pehle parse karke fir verify karte to kya risk hota?
  4. Secret rotation (Section 4: verify_multi_secret) — dono purane/naye
     secret try karte hain. Yeh zero-downtime rotation kaise enable karta hai?
""")


if __name__ == "__main__":
    main()
