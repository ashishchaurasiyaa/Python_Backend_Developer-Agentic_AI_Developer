"""
HMAC Webhooks + Idempotency — Production Patterns
"""

import hmac
import hashlib
import json
import time
import random
import uuid
import asyncio
from typing import Any

import httpx
import redis.asyncio as redis
from fastapi import FastAPI, Request, Header, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse


app = FastAPI()
r = redis.Redis()


WEBHOOK_SECRET = b"shared-secret-from-env"
TIMESTAMP_TOLERANCE_SEC = 300
IDEMPOTENCY_TTL = 86400 * 7  # 7 days


# ==========================================================================
# 1. SIGNATURE VERIFICATION
# ==========================================================================

def compute_signature(body: bytes, timestamp: int, secret: bytes = WEBHOOK_SECRET) -> str:
    """HMAC-SHA256 over timestamp + body."""
    payload = f'{timestamp}.'.encode() + body
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()


def verify_signature(
    body: bytes,
    signature: str,
    timestamp: int,
    secret: bytes = WEBHOOK_SECRET,
) -> bool:
    """Verify with constant-time compare + timestamp window."""
    # Replay protection
    if abs(time.time() - timestamp) > TIMESTAMP_TOLERANCE_SEC:
        return False

    expected = compute_signature(body, timestamp, secret)
    return hmac.compare_digest(expected, signature)


# ==========================================================================
# 2. STRIPE-STYLE MULTI-VERSION SIGNATURE
# ==========================================================================

def parse_stripe_signature(header: str) -> dict[str, list[str]]:
    parts: dict[str, list[str]] = {}
    for chunk in header.split(','):
        k, _, v = chunk.partition('=')
        k, v = k.strip(), v.strip()
        if k and v:
            parts.setdefault(k, []).append(v)
    return parts


def verify_stripe_webhook(
    body: bytes,
    signature_header: str,
    secrets: list[bytes],
) -> bool:
    """Supports key rotation — try multiple secrets."""
    parsed = parse_stripe_signature(signature_header)
    timestamps = parsed.get('t', [])
    v1_sigs = parsed.get('v1', [])

    if not timestamps or not v1_sigs:
        return False

    try:
        timestamp = int(timestamps[0])
    except ValueError:
        return False

    if abs(time.time() - timestamp) > TIMESTAMP_TOLERANCE_SEC:
        return False

    payload = f'{timestamp}.'.encode() + body
    for secret in secrets:
        expected = hmac.new(secret, payload, hashlib.sha256).hexdigest()
        if any(hmac.compare_digest(expected, sig) for sig in v1_sigs):
            return True
    return False


# ==========================================================================
# 3. GITHUB-STYLE SIGNATURE
# ==========================================================================

def verify_github_signature(body: bytes, signature_header: str, secret: bytes) -> bool:
    """GitHub uses 'X-Hub-Signature-256: sha256=<hex>'."""
    if not signature_header.startswith('sha256='):
        return False
    received = signature_header[7:]
    expected = hmac.new(secret, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, received)


# ==========================================================================
# 4. WEBHOOK RECEIVER (full pattern)
# ==========================================================================

@app.post("/webhook/payment")
async def payment_webhook(
    request: Request,
    background: BackgroundTasks,
    x_signature: str = Header(..., alias="X-Webhook-Signature"),
    x_timestamp: int = Header(..., alias="X-Webhook-Timestamp"),
    x_event_id: str = Header(..., alias="X-Webhook-Event-Id"),
):
    body = await request.body()

    # Step 1: Signature verification
    sig = x_signature.removeprefix('sha256=')
    if not verify_signature(body, sig, x_timestamp):
        raise HTTPException(401, "Invalid signature")

    # Step 2: Idempotency (SETNX with TTL)
    key = f'webhook:payment:{x_event_id}'
    acquired = await r.set(key, '1', ex=IDEMPOTENCY_TTL, nx=True)

    if not acquired:
        return {'status': 'duplicate'}

    # Step 3: Parse + queue for async processing
    try:
        event = json.loads(body)
    except json.JSONDecodeError:
        await r.delete(key)
        raise HTTPException(400, "Invalid JSON")

    # Step 4: Background process
    background.add_task(process_payment_event, event, x_event_id)

    return {'status': 'received', 'event_id': x_event_id}


async def process_payment_event(event: dict[str, Any], event_id: str):
    """Heavy work — runs after response sent."""
    try:
        # ... business logic
        await asyncio.sleep(0.1)  # placeholder
    except Exception as e:
        # Release lock so retry can process
        await r.delete(f'webhook:payment:{event_id}')
        import logging
        logging.error(f"Failed to process event {event_id}: {e}", exc_info=True)


# ==========================================================================
# 5. STRIPE WEBHOOK
# ==========================================================================

STRIPE_SECRETS = [b"whsec_current", b"whsec_old_during_rotation"]


@app.post("/webhook/stripe")
async def stripe_webhook(
    request: Request,
    background: BackgroundTasks,
    stripe_signature: str = Header(..., alias="Stripe-Signature"),
):
    body = await request.body()

    if not verify_stripe_webhook(body, stripe_signature, STRIPE_SECRETS):
        raise HTTPException(401, "Invalid signature")

    event = json.loads(body)
    event_id = event.get('id', '')

    key = f'webhook:stripe:{event_id}'
    if not await r.set(key, '1', ex=IDEMPOTENCY_TTL, nx=True):
        return {'status': 'duplicate'}

    background.add_task(process_stripe_event, event)
    return {'status': 'ok'}


async def process_stripe_event(event: dict[str, Any]):
    event_type = event.get('type', '')
    obj = event.get('data', {}).get('object', {})

    if event_type == 'payment_intent.succeeded':
        # ... handle payment
        pass
    elif event_type == 'charge.refunded':
        # ... handle refund
        pass


# ==========================================================================
# 6. GITHUB WEBHOOK
# ==========================================================================

GITHUB_SECRET = b"github-webhook-secret"


@app.post("/webhook/github")
async def github_webhook(
    request: Request,
    background: BackgroundTasks,
    x_hub_signature_256: str = Header(..., alias="X-Hub-Signature-256"),
    x_github_event: str = Header(..., alias="X-GitHub-Event"),
    x_github_delivery: str = Header(..., alias="X-GitHub-Delivery"),
):
    body = await request.body()

    if not verify_github_signature(body, x_hub_signature_256, GITHUB_SECRET):
        raise HTTPException(401, "Invalid signature")

    # GitHub uses Delivery ID for idempotency
    key = f'webhook:github:{x_github_delivery}'
    if not await r.set(key, '1', ex=IDEMPOTENCY_TTL, nx=True):
        return {'status': 'duplicate'}

    event = json.loads(body)
    background.add_task(process_github_event, x_github_event, event)
    return {'status': 'ok'}


async def process_github_event(event_type: str, event: dict[str, Any]):
    if event_type == 'pull_request':
        action = event.get('action')
        # ... handle PR opened/closed/merged
        pass


# ==========================================================================
# 7. OUTGOING WEBHOOK DELIVERY WITH RETRIES
# ==========================================================================

class WebhookDeliveryError(Exception):
    pass


async def deliver_webhook(
    url: str,
    payload: dict[str, Any],
    secret: bytes,
    max_attempts: int = 5,
    base_delay: float = 1.0,
    timeout: float = 10.0,
):
    """Outgoing webhook with HMAC sig + exponential backoff."""

    body = json.dumps(payload).encode()
    timestamp = int(time.time())
    signature = compute_signature(body, timestamp, secret)
    event_id = payload.get('id', str(uuid.uuid4()))

    headers = {
        'Content-Type': 'application/json',
        'X-Webhook-Signature': f'sha256={signature}',
        'X-Webhook-Timestamp': str(timestamp),
        'X-Webhook-Event-Id': event_id,
    }

    last_error = None
    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(max_attempts):
            try:
                resp = await client.post(url, content=body, headers=headers)
                if 200 <= resp.status_code < 300:
                    return  # success
                # 4xx — client bug, don't retry
                if 400 <= resp.status_code < 500 and resp.status_code != 408:
                    raise WebhookDeliveryError(f'Non-retriable: {resp.status_code}')
                last_error = f'HTTP {resp.status_code}'
            except httpx.RequestError as e:
                last_error = str(e)
                # network error — retriable

            # Exponential backoff with jitter
            if attempt < max_attempts - 1:
                delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                await asyncio.sleep(min(delay, 3600))  # cap 1h

    raise WebhookDeliveryError(f'Max attempts; last error: {last_error}')


# ==========================================================================
# 8. IDEMPOTENCY-KEY (outgoing requests)
# ==========================================================================

async def charge_customer(amount_cents: int, customer_id: str, retry_count: int = 3):
    """Charge with Idempotency-Key — safe retries."""

    idempotency_key = str(uuid.uuid4())  # stable across retries

    async with httpx.AsyncClient(timeout=30.0) as client:
        for attempt in range(retry_count):
            try:
                resp = await client.post(
                    'https://api.stripe.com/v1/charges',
                    data={
                        'amount': amount_cents,
                        'currency': 'usd',
                        'customer': customer_id,
                    },
                    headers={
                        'Authorization': 'Bearer sk_test_xxx',
                        'Idempotency-Key': idempotency_key,
                    },
                )
                if resp.status_code == 200:
                    return resp.json()
                if 400 <= resp.status_code < 500:
                    # Don't retry client errors
                    raise Exception(f'Client error: {resp.text}')
                # 5xx → retry
            except httpx.RequestError:
                pass

            if attempt < retry_count - 1:
                await asyncio.sleep(2 ** attempt)

    raise Exception('Charge failed after retries')


# ==========================================================================
# 9. WEBHOOK SUBSCRIBER MODEL (multi-tenant)
# ==========================================================================

# from sqlalchemy import Column, Integer, String, JSON, DateTime, Boolean
# from sqlalchemy.ext.declarative import declarative_base
# from sqlalchemy.sql import func
#
# Base = declarative_base()
#
#
# class WebhookSubscription(Base):
#     __tablename__ = 'webhook_subscriptions'
#
#     id = Column(Integer, primary_key=True)
#     tenant_id = Column(Integer, nullable=False, index=True)
#     url = Column(String, nullable=False)
#     secret = Column(String, nullable=False)
#     events = Column(JSON, default=list)  # ['payment.succeeded', 'order.created']
#     active = Column(Boolean, default=True)
#     created_at = Column(DateTime, default=func.now())
#
#
# class WebhookDelivery(Base):
#     __tablename__ = 'webhook_deliveries'
#
#     id = Column(Integer, primary_key=True)
#     subscription_id = Column(Integer, nullable=False, index=True)
#     event_id = Column(String, unique=True, index=True)
#     event_type = Column(String, nullable=False)
#     payload = Column(JSON, nullable=False)
#     status = Column(String, default='pending')  # pending, sent, failed, dead
#     attempts = Column(Integer, default=0)
#     last_attempt_at = Column(DateTime)
#     next_retry_at = Column(DateTime)
#     last_error = Column(String, nullable=True)


# ==========================================================================
# 10. BACKGROUND RETRY WORKER
# ==========================================================================

async def webhook_retry_worker():
    """Periodic worker — picks up failed deliveries from DB and retries."""

    while True:
        try:
            # pending = await db.fetch_pending_webhooks(limit=100)
            pending = []  # placeholder
            for delivery in pending:
                try:
                    await deliver_webhook(
                        delivery.url,
                        delivery.payload,
                        delivery.secret,
                        max_attempts=1,  # single try, worker schedules next
                    )
                    delivery.status = 'sent'
                except WebhookDeliveryError as e:
                    delivery.attempts += 1
                    delivery.last_error = str(e)
                    if delivery.attempts >= 10:
                        delivery.status = 'dead'
                    else:
                        # Schedule next attempt
                        backoff_min = 2 ** delivery.attempts
                        # delivery.next_retry_at = now + backoff_min minutes
                # await db.save(delivery)
        except Exception:
            import logging
            logging.exception("Retry worker iteration failed")

        await asyncio.sleep(30)  # poll every 30s
