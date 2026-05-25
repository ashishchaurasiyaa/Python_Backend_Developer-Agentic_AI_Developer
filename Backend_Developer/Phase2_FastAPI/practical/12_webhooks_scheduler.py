"""
PHASE 2 FastAPI — Practical 12: Webhooks + APScheduler
Run: uvicorn 12_webhooks_scheduler:app --reload
Docs: http://127.0.0.1:8000/docs

Install: pip install apscheduler fastapi uvicorn

Topics:
  - Webhook endpoint — HMAC-SHA256 signature verification
  - GitHub-style webhook (X-Hub-Signature-256)
  - Stripe-style webhook (Stripe-Signature)
  - Webhook retry handling + idempotency
  - Outgoing webhooks — notify external systems
  - APScheduler — periodic background jobs within FastAPI
  - Cron jobs, interval jobs, one-time jobs
  - Job management — add/remove/list jobs at runtime
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import APIRouter, BackgroundTasks, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, HttpUrl


# ═══════════════════════════════════════════════════════
# SECTION 1: Webhook Secrets Config
# ═══════════════════════════════════════════════════════

GITHUB_WEBHOOK_SECRET  = "github-secret-for-learning"
STRIPE_WEBHOOK_SECRET  = "stripe-secret-for-learning"
GENERIC_WEBHOOK_SECRET = "generic-secret-for-learning"

# In-memory stores (use DB in production)
WEBHOOK_EVENTS:   list[dict] = []
PROCESSED_IDS:    set[str]   = set()   # idempotency — no duplicate processing
SCHEDULER_JOBS:   dict[str, dict] = {}


# ═══════════════════════════════════════════════════════
# SECTION 2: HMAC Signature Verification Helpers
# ═══════════════════════════════════════════════════════

def verify_hmac_sha256(payload: bytes, signature: str, secret: str) -> bool:
    """
    Verify HMAC-SHA256 webhook signature.
    Used by: GitHub, Linear, many others.

    signature format: "sha256=<hex_digest>"
    """
    expected = hmac.new(
        key=secret.encode(),
        msg=payload,
        digestmod=hashlib.sha256,
    ).hexdigest()

    expected_header = f"sha256={expected}"

    # Use hmac.compare_digest to prevent timing attacks
    return hmac.compare_digest(expected_header, signature)


def verify_stripe_signature(payload: bytes, sig_header: str, secret: str, tolerance: int = 300) -> bool:
    """
    Verify Stripe webhook signature.
    Stripe header format: "t=<timestamp>,v1=<signature>"

    tolerance: max age in seconds (default 5 minutes)
    """
    try:
        parts = dict(part.split("=", 1) for part in sig_header.split(","))
        timestamp = int(parts["t"])
        signature = parts["v1"]
    except (KeyError, ValueError):
        return False

    # Check timestamp to prevent replay attacks
    if abs(time.time() - timestamp) > tolerance:
        return False

    # Compute expected signature
    signed_payload = f"{timestamp}.{payload.decode()}"
    expected = hmac.new(
        key=secret.encode(),
        msg=signed_payload.encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


def generate_webhook_signature(payload: bytes, secret: str) -> str:
    """Generate HMAC-SHA256 signature for outgoing webhooks."""
    digest = hmac.new(
        key=secret.encode(),
        msg=payload,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return f"sha256={digest}"


# ═══════════════════════════════════════════════════════
# SECTION 3: Incoming Webhook Endpoints
# ═══════════════════════════════════════════════════════

webhook_router = APIRouter(prefix="/webhooks", tags=["Webhooks — Incoming"])


@webhook_router.post("/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: Optional[str] = Header(None),
    x_github_event: Optional[str] = Header(None),
    x_github_delivery: Optional[str] = Header(None),
):
    """
    GitHub webhook receiver.
    Setup: GitHub repo → Settings → Webhooks → add URL + secret.

    Test with curl:
    SECRET="github-secret-for-learning"
    PAYLOAD='{"action":"push","repository":{"name":"myrepo"}}'
    SIG=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$SECRET" | awk '{print "sha256="$2}')
    curl -X POST http://localhost:8000/webhooks/github \\
      -H "Content-Type: application/json" \\
      -H "X-Hub-Signature-256: $SIG" \\
      -H "X-GitHub-Event: push" \\
      -H "X-GitHub-Delivery: test-delivery-id" \\
      -d "$PAYLOAD"
    """
    payload_bytes = await request.body()

    # 1. Verify signature
    if not x_hub_signature_256:
        raise HTTPException(status_code=400, detail="Missing X-Hub-Signature-256 header")

    if not verify_hmac_sha256(payload_bytes, x_hub_signature_256, GITHUB_WEBHOOK_SECRET):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    # 2. Idempotency — skip if already processed
    delivery_id = x_github_delivery or str(uuid.uuid4())
    if delivery_id in PROCESSED_IDS:
        return {"status": "already_processed", "delivery_id": delivery_id}
    PROCESSED_IDS.add(delivery_id)

    # 3. Parse payload
    try:
        payload = json.loads(payload_bytes)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # 4. Process in background — respond immediately (GitHub expects <10s)
    background_tasks.add_task(process_github_event, x_github_event or "unknown", payload, delivery_id)

    return {"status": "accepted", "delivery_id": delivery_id, "event": x_github_event}


@webhook_router.post("/stripe")
async def stripe_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    stripe_signature: Optional[str] = Header(None, alias="Stripe-Signature"),
):
    """
    Stripe webhook receiver.
    Stripe sends: Stripe-Signature: t=<timestamp>,v1=<signature>

    Test: use Stripe CLI → stripe trigger payment_intent.succeeded
    """
    payload_bytes = await request.body()

    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")

    if not verify_stripe_signature(payload_bytes, stripe_signature, STRIPE_WEBHOOK_SECRET):
        raise HTTPException(status_code=401, detail="Invalid Stripe signature or expired timestamp")

    try:
        event = json.loads(payload_bytes)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Idempotency using Stripe event ID
    event_id = event.get("id", str(uuid.uuid4()))
    if event_id in PROCESSED_IDS:
        return {"status": "already_processed"}
    PROCESSED_IDS.add(event_id)

    background_tasks.add_task(process_stripe_event, event)

    # IMPORTANT: Stripe requires 200 response FAST — processing is async
    return {"status": "received"}


@webhook_router.post("/generic")
async def generic_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_signature: Optional[str] = Header(None, alias="X-Signature"),
    x_event_id:  Optional[str] = Header(None, alias="X-Event-ID"),
):
    """Generic HMAC-verified webhook — your own services can use this."""
    payload_bytes = await request.body()

    if x_signature and not verify_hmac_sha256(payload_bytes, x_signature, GENERIC_WEBHOOK_SECRET):
        raise HTTPException(status_code=401, detail="Invalid signature")

    event_id = x_event_id or str(uuid.uuid4())
    if event_id in PROCESSED_IDS:
        return {"status": "duplicate", "event_id": event_id}
    PROCESSED_IDS.add(event_id)

    payload = json.loads(payload_bytes)
    WEBHOOK_EVENTS.append({
        "event_id": event_id,
        "payload": payload,
        "received_at": datetime.now(timezone.utc).isoformat(),
    })

    return {"status": "accepted", "event_id": event_id}


# ═══════════════════════════════════════════════════════
# SECTION 4: Background Event Processors
# ═══════════════════════════════════════════════════════

async def process_github_event(event_type: str, payload: dict, delivery_id: str):
    """Handle GitHub webhook events."""
    print(f"\n[GITHUB] event={event_type} delivery={delivery_id}")

    if event_type == "push":
        repo = payload.get("repository", {}).get("name", "unknown")
        commits = payload.get("commits", [])
        print(f"  Push to {repo}: {len(commits)} commits")
        # Trigger CI/CD, notify Slack, etc.

    elif event_type == "pull_request":
        action = payload.get("action")
        pr_title = payload.get("pull_request", {}).get("title", "")
        print(f"  PR {action}: {pr_title}")

    elif event_type == "issues":
        action = payload.get("action")
        issue_title = payload.get("issue", {}).get("title", "")
        print(f"  Issue {action}: {issue_title}")

    WEBHOOK_EVENTS.append({
        "source": "github",
        "event": event_type,
        "delivery_id": delivery_id,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    })


async def process_stripe_event(event: dict):
    """Handle Stripe payment events."""
    event_type = event.get("type", "")
    print(f"\n[STRIPE] event={event_type}")

    if event_type == "payment_intent.succeeded":
        amount = event.get("data", {}).get("object", {}).get("amount", 0)
        currency = event.get("data", {}).get("object", {}).get("currency", "usd")
        print(f"  Payment succeeded: {amount/100:.2f} {currency.upper()}")
        # Update order status, send receipt email, etc.

    elif event_type == "customer.subscription.deleted":
        customer_id = event.get("data", {}).get("object", {}).get("customer")
        print(f"  Subscription cancelled for customer: {customer_id}")
        # Downgrade user, send cancellation email, etc.

    WEBHOOK_EVENTS.append({
        "source": "stripe",
        "event": event_type,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    })


# ═══════════════════════════════════════════════════════
# SECTION 5: Outgoing Webhooks (notify other systems)
# ═══════════════════════════════════════════════════════

class WebhookSubscription(BaseModel):
    url: str
    events: list[str] = ["*"]
    secret: str = ""


SUBSCRIPTIONS: dict[str, dict] = {}


async def send_outgoing_webhook(url: str, event_type: str, payload: dict, secret: str = ""):
    """Send webhook to subscriber — with signature + retry."""
    body = json.dumps({"event": event_type, "data": payload, "timestamp": time.time()}).encode()
    headers = {
        "Content-Type": "application/json",
        "X-Event-Type": event_type,
        "X-Delivery-ID": str(uuid.uuid4()),
    }

    if secret:
        headers["X-Signature"] = generate_webhook_signature(body, secret)

    # Retry up to 3 times with exponential backoff
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, content=body, headers=headers)
                if resp.status_code < 300:
                    print(f"[WEBHOOK OUT] Delivered to {url} — status {resp.status_code}")
                    return True
        except Exception as e:
            print(f"[WEBHOOK OUT] Attempt {attempt+1} failed: {e}")
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)  # 1s, 2s, 4s

    print(f"[WEBHOOK OUT] Failed after 3 attempts: {url}")
    return False


webhook_out_router = APIRouter(prefix="/webhook-subscriptions", tags=["Webhooks — Outgoing"])


@webhook_out_router.post("/")
async def subscribe(sub: WebhookSubscription):
    """Register a webhook subscriber."""
    sub_id = str(uuid.uuid4())[:8]
    SUBSCRIPTIONS[sub_id] = sub.model_dump()
    return {"subscription_id": sub_id, **sub.model_dump()}


@webhook_out_router.post("/trigger/{event_type}")
async def trigger_event(event_type: str, payload: dict, background_tasks: BackgroundTasks):
    """Trigger event → notify all subscribed URLs."""
    notified = 0
    for sub_id, sub in SUBSCRIPTIONS.items():
        if "*" in sub["events"] or event_type in sub["events"]:
            background_tasks.add_task(send_outgoing_webhook, sub["url"], event_type, payload, sub["secret"])
            notified += 1
    return {"event": event_type, "notified_subscribers": notified}


# ═══════════════════════════════════════════════════════
# SECTION 6: APScheduler — Periodic Jobs
# ═══════════════════════════════════════════════════════

scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")

JOB_RESULTS: list[dict] = []


# ─── Job functions ───
async def cleanup_old_events():
    """Runs every 5 minutes: remove events older than 1 hour."""
    cutoff = time.time() - 3600
    before = len(WEBHOOK_EVENTS)
    WEBHOOK_EVENTS[:] = [
        e for e in WEBHOOK_EVENTS
        if e.get("received_at", "") > datetime.fromtimestamp(cutoff, timezone.utc).isoformat()
    ]
    removed = before - len(WEBHOOK_EVENTS)
    result = {"job": "cleanup_old_events", "removed": removed, "ran_at": datetime.now(timezone.utc).isoformat()}
    JOB_RESULTS.append(result)
    print(f"[SCHEDULER] cleanup_old_events: removed {removed} events")


async def send_daily_digest():
    """Runs daily at 9 AM IST: send summary email."""
    total_events = len(WEBHOOK_EVENTS)
    print(f"[SCHEDULER] daily_digest: {total_events} events in last 24h")
    JOB_RESULTS.append({
        "job": "daily_digest",
        "events_count": total_events,
        "ran_at": datetime.now(timezone.utc).isoformat(),
    })


async def health_check_job():
    """Runs every 30 seconds: check external services."""
    print(f"[SCHEDULER] health_check: {datetime.now(timezone.utc).strftime('%H:%M:%S')}")
    JOB_RESULTS.append({
        "job": "health_check",
        "status": "ok",
        "ran_at": datetime.now(timezone.utc).isoformat(),
    })


async def process_retry_queue():
    """Runs every minute: retry failed webhook deliveries."""
    print(f"[SCHEDULER] retry_queue: checking failed deliveries...")
    JOB_RESULTS.append({
        "job": "retry_queue",
        "ran_at": datetime.now(timezone.utc).isoformat(),
    })


# ─── Scheduler management API ───
scheduler_router = APIRouter(prefix="/scheduler", tags=["APScheduler"])


@scheduler_router.get("/jobs")
async def list_jobs():
    """List all scheduled jobs."""
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "trigger": str(job.trigger),
            "next_run": str(job.next_run_time),
        })
    return {"jobs": jobs, "count": len(jobs)}


@scheduler_router.post("/jobs/pause/{job_id}")
async def pause_job(job_id: str):
    """Pause a scheduled job."""
    job = scheduler.get_job(job_id)
    if not job:
        raise HTTPException(404, f"Job '{job_id}' not found")
    job.pause()
    return {"paused": job_id}


@scheduler_router.post("/jobs/resume/{job_id}")
async def resume_job(job_id: str):
    """Resume a paused job."""
    job = scheduler.get_job(job_id)
    if not job:
        raise HTTPException(404, f"Job '{job_id}' not found")
    job.resume()
    return {"resumed": job_id}


@scheduler_router.post("/jobs/run-now/{job_id}")
async def run_job_now(job_id: str):
    """Trigger a job to run immediately."""
    job = scheduler.get_job(job_id)
    if not job:
        raise HTTPException(404, f"Job '{job_id}' not found")
    # Run in background
    asyncio.create_task(job.func())
    return {"triggered": job_id}


@scheduler_router.post("/jobs/add-interval")
async def add_interval_job(name: str, seconds: int):
    """Dynamically add a new interval job."""
    job_id = f"dynamic_{name}_{uuid.uuid4().hex[:4]}"

    async def dynamic_job():
        print(f"[DYNAMIC JOB] {name} ran at {datetime.now(timezone.utc)}")
        JOB_RESULTS.append({"job": name, "ran_at": datetime.now(timezone.utc).isoformat()})

    scheduler.add_job(
        dynamic_job,
        trigger=IntervalTrigger(seconds=seconds),
        id=job_id,
        name=name,
        replace_existing=True,
    )
    return {"added": job_id, "runs_every": f"{seconds}s"}


@scheduler_router.delete("/jobs/{job_id}")
async def remove_job(job_id: str):
    """Remove a scheduled job."""
    job = scheduler.get_job(job_id)
    if not job:
        raise HTTPException(404, f"Job '{job_id}' not found")
    scheduler.remove_job(job_id)
    return {"removed": job_id}


@scheduler_router.get("/results")
async def job_results(limit: int = 20):
    """See job execution history."""
    return {"results": JOB_RESULTS[-limit:][::-1]}


# ═══════════════════════════════════════════════════════
# SECTION 7: App Setup
# ═══════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── STARTUP: Register jobs ──
    scheduler.add_job(
        health_check_job,
        trigger=IntervalTrigger(seconds=30),
        id="health_check",
        name="Health Check",
        replace_existing=True,
    )
    scheduler.add_job(
        cleanup_old_events,
        trigger=IntervalTrigger(minutes=5),
        id="cleanup_events",
        name="Cleanup Old Events",
        replace_existing=True,
    )
    scheduler.add_job(
        send_daily_digest,
        trigger=CronTrigger(hour=9, minute=0, timezone="Asia/Kolkata"),
        id="daily_digest",
        name="Daily Digest Email",
        replace_existing=True,
    )
    scheduler.add_job(
        process_retry_queue,
        trigger=IntervalTrigger(minutes=1),
        id="retry_queue",
        name="Retry Failed Webhooks",
        replace_existing=True,
    )

    scheduler.start()
    print(f"✅ Scheduler started with {len(scheduler.get_jobs())} jobs")

    yield

    # ── SHUTDOWN: Stop scheduler ──
    scheduler.shutdown(wait=False)
    print("🛑 Scheduler stopped")


app = FastAPI(
    title="Webhooks + APScheduler Practical",
    description="HMAC signature verification + APScheduler periodic jobs",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(webhook_router)
app.include_router(webhook_out_router)
app.include_router(scheduler_router)


@app.get("/webhook-events", tags=["Webhooks — Incoming"])
async def get_events(limit: int = 20):
    """See all received webhook events."""
    return {"events": WEBHOOK_EVENTS[-limit:][::-1], "total": len(WEBHOOK_EVENTS)}


@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "Webhooks + APScheduler Practical",
        "test": {
            "github_webhook":  "POST /webhooks/github",
            "stripe_webhook":  "POST /webhooks/stripe",
            "generic_webhook": "POST /webhooks/generic",
            "scheduler_jobs":  "GET /scheduler/jobs",
            "job_results":     "GET /scheduler/results",
            "webhook_events":  "GET /webhook-events",
        },
        "tip": "Run app and watch terminal for scheduled job logs every 30s!",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("12_webhooks_scheduler:app", host="0.0.0.0", port=8011, reload=True)
