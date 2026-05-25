# Async API Patterns

## Why It Matters

Many operations exceed HTTP request timeout (PDF generation, AI inference, large export). Async patterns let clients trigger work and check results.

Senior interview: "30-second report generation API design?" → async job + polling/webhook/SSE.

---

## Long-Running Operation Patterns

### 1. Polling (Simplest)

```
Client → POST /jobs           → 202 Accepted + Location: /jobs/123
Client → GET /jobs/123        → 200 {status: 'queued'}
Client → GET /jobs/123        → 200 {status: 'processing', progress: 50}
Client → GET /jobs/123        → 200 {status: 'completed', result: {...}}
```

**Pros:** Simple, works everywhere, no special infra
**Cons:** Wasted polls (battery, bandwidth), latency until next poll

### 2. Long-Polling

```
Client → GET /jobs/123/wait?timeout=30
Server holds request open until status changes (or 30s)
Server → 200 {status: 'completed', result: {...}}
```

**Pros:** Lower latency than polling
**Cons:** Server resources held, complex timeout handling

### 3. Server-Sent Events (SSE)

```
Client → GET /jobs/123/events
Server → text/event-stream

event: progress
data: {"progress": 25}

event: progress
data: {"progress": 75}

event: complete
data: {"result": {...}}
```

**Pros:** Push-based, HTTP-native, browser support
**Cons:** Server holds connection, unidirectional only

### 4. WebSocket

```
Client opens WS connection
Server pushes events bidirectionally
```

**Pros:** Bidirectional, low latency
**Cons:** More complex, firewall issues sometimes

### 5. Webhook Callback

```
Client → POST /jobs {callback_url: 'https://client/notify'}
        → 202 + job_id
Server processes job
Server → POST https://client/notify (with HMAC signature)
```

**Pros:** No polling, scales well
**Cons:** Client needs publicly accessible endpoint, retry complexity

### 6. Hybrid (Polling + Webhook)

Client uses polling, optionally provides webhook URL. Server notifies via webhook AND keeps state available for polling.

---

## RFC 7240 — Asynchronous Pattern

```http
POST /jobs
Prefer: respond-async, return=representation

HTTP/1.1 202 Accepted
Location: /jobs/123
Preference-Applied: respond-async
Retry-After: 5

{
    "id": "123",
    "status": "queued"
}
```

`Prefer: respond-async` tells server to do work asynchronously.
`Retry-After` hints when to poll.

---

## Standard Status Endpoint

```http
GET /jobs/123

{
    "id": "123",
    "status": "processing",
    "created_at": "2026-01-15T10:00:00Z",
    "started_at": "2026-01-15T10:00:01Z",
    "updated_at": "2026-01-15T10:00:30Z",
    "progress": {
        "current": 250,
        "total": 1000,
        "percentage": 25
    },
    "result_url": null,
    "error": null
}
```

When complete:
```json
{
    "id": "123",
    "status": "completed",
    "completed_at": "2026-01-15T10:05:00Z",
    "result_url": "/jobs/123/result"
}
```

---

## Implementation (FastAPI + Celery + Redis)

### Job Endpoint

```python
from fastapi import FastAPI, BackgroundTasks
from celery import Celery


app = FastAPI()
celery = Celery('myapp', broker='redis://localhost:6379/1')


@celery.task(bind=True)
def generate_report(self, user_id: int, params: dict):
    total = 1000
    for i in range(total):
        # Update progress
        self.update_state(
            state='PROGRESS',
            meta={'current': i, 'total': total},
        )
        process_item(i)

    # Final result
    return {'report_url': f's3://bucket/reports/{self.request.id}.pdf'}


@app.post('/jobs', status_code=202)
async def create_job(user_id: int, params: dict):
    task = generate_report.delay(user_id, params)
    return {
        'job_id': task.id,
        'status': 'queued',
        'status_url': f'/jobs/{task.id}',
    }


@app.get('/jobs/{job_id}')
async def get_job_status(job_id: str):
    from celery.result import AsyncResult

    result = AsyncResult(job_id, app=celery)

    response = {
        'id': job_id,
        'status': result.state.lower(),
    }

    if result.state == 'PROGRESS':
        response['progress'] = result.info
    elif result.state == 'SUCCESS':
        response['result'] = result.result
    elif result.state == 'FAILURE':
        response['error'] = str(result.info)

    return response
```

### SSE Streaming

```python
from sse_starlette.sse import EventSourceResponse


@app.get('/jobs/{job_id}/events')
async def job_events(job_id: str, request: Request):
    async def gen():
        last_state = None
        while True:
            if await request.is_disconnected():
                break

            result = AsyncResult(job_id, app=celery)
            current_state = (result.state, str(result.info))

            if current_state != last_state:
                yield {
                    'event': result.state.lower(),
                    'data': json.dumps({
                        'state': result.state,
                        'info': result.info if isinstance(result.info, dict) else str(result.info),
                    }),
                }
                last_state = current_state

            if result.state in {'SUCCESS', 'FAILURE'}:
                break

            await asyncio.sleep(2)

    return EventSourceResponse(gen(), ping=15)
```

### Webhook Callback

```python
@app.post('/jobs/with-webhook')
async def create_job_with_webhook(user_id: int, params: dict, callback_url: str):
    # Validate URL (SSRF safe)
    validate_url(callback_url)

    task = generate_report.apply_async(
        args=[user_id, params],
        link=notify_webhook.s(callback_url),  # call on success
        link_error=notify_webhook.s(callback_url, error=True),
    )
    return {'job_id': task.id}


@celery.task
def notify_webhook(result, callback_url, error=False):
    payload = {
        'status': 'failed' if error else 'completed',
        'result': result,
    }
    # Sign payload
    body = json.dumps(payload).encode()
    sig = sign_payload(body, WEBHOOK_SECRET)

    requests.post(
        callback_url,
        json=payload,
        headers={'X-Webhook-Signature': f'sha256={sig}'},
        timeout=10,
    )
```

---

## Idempotency

Async APIs MUST support idempotency:

```python
@app.post('/jobs')
async def create_job(
    params: dict,
    idempotency_key: str = Header(...),
):
    # Check if job already exists for this key
    existing = await redis.get(f'idem:{idempotency_key}')
    if existing:
        return json.loads(existing)

    task = generate_report.delay(params)
    response = {
        'job_id': task.id,
        'status': 'queued',
    }
    await redis.set(f'idem:{idempotency_key}', json.dumps(response), ex=86400)
    return response
```

---

## Cancellation

```python
@app.post('/jobs/{job_id}/cancel')
async def cancel_job(job_id: str):
    result = AsyncResult(job_id, app=celery)

    if result.state in {'SUCCESS', 'FAILURE'}:
        raise HTTPException(409, 'Cannot cancel completed job')

    result.revoke(terminate=True)
    return {'status': 'cancelled'}


# In task, check cancellation
@celery.task(bind=True)
def long_task(self):
    for i in range(1000):
        if self.is_revoked():
            return {'status': 'cancelled', 'completed': i}
        process(i)
```

---

## Result Storage

Where to store result?

| Storage | Use Case |
|---|---|
| Celery result backend (Redis) | Small results, short TTL |
| Database | Auditable, queryable |
| S3 + signed URL | Large results (files, exports) |
| Cache (Redis) | Fast access, ephemeral |

For large results, return URL to fetch:

```python
{
    "status": "completed",
    "result_url": "/jobs/123/download",
    "expires_at": "2026-01-15T11:00:00Z"
}
```

---

## TTL / Retention

Jobs should expire. Storage cost + DB bloat otherwise.

```python
# Celery
CELERY_RESULT_EXPIRES = 3600   # 1 hour for default backend


# Job records
class JobRecord(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)


# Cleanup task
@celery.task
def cleanup_old_jobs():
    cutoff = timezone.now() - timedelta(days=30)
    JobRecord.objects.filter(created_at__lt=cutoff).delete()


CELERY_BEAT_SCHEDULE = {
    'cleanup-jobs': {'task': 'tasks.cleanup_old_jobs', 'schedule': crontab(hour=3)},
}
```

---

## Common Pitfalls

### 1. Synchronous in Async Endpoint

```python
@app.post('/jobs')
async def create_job():
    result = generate_report.delay(...).get()   # BLOCKS — kills async benefit
```

Don't `.get()` — return task_id, let client poll.

### 2. No Idempotency

Client retries on network blip → duplicate job → double charges or data corruption.

### 3. Polling Without Backoff

Client polls every 100ms forever → DoS. Server should hint via `Retry-After` header.

### 4. No TTL on Job Records

Jobs accumulate forever → DB bloat. Set retention (30-90 days typical).

### 5. Large Result in Response

Returning 100MB result inline → response timeout. Use S3 + signed URL.

### 6. No Cancellation

Long-running stuck jobs hold workers. Provide cancel endpoint + check periodically.

### 7. Sync Webhook Notification

Webhook call inside Celery task blocks task. Use dedicated task for webhook with retries.

### 8. No Progress Granularity

Client sees "processing..." for 5 min, then "complete". Update progress every X seconds.

---

## Interview Q&A

**Q1:** Long-running API design?
**A:** Async job pattern. POST returns 202 + job_id. Client polls GET /jobs/{id} until complete. Progress updates via SSE or polling. Result via separate endpoint or signed URL. Idempotency-Key for retry safety. TTL on records (cleanup).

**Q2:** Polling vs SSE vs WebSocket vs webhook?
**A:** Polling: simple, works everywhere, wasteful. SSE: server-push, browser-friendly, unidirectional. WebSocket: bidirectional, complex. Webhook: scales best, requires public client endpoint. Choose: polling for simple/cron clients; SSE for browsers; webhook for production server-to-server.

**Q3:** Job result storage?
**A:** Small results (< 1MB): Celery backend (Redis) or DB. Large results (files, exports): S3 + signed URL in response. Reasoning: response should be small + cacheable; large data via separate fetch.

**Q4:** Cancellation in async APIs?
**A:** POST /jobs/{id}/cancel. Server marks task as revoked. Task code checks `self.is_revoked()` periodically and exits gracefully. Idempotent: canceling completed job returns 409 or no-op.

**Q5:** Status response design?
**A:** Include: state (queued/processing/completed/failed), timestamps (created/started/updated/completed), progress {current, total, percentage}, error (if failed), result_url (if completed + large). Consistent across all endpoints. Stable JSON shape.

**Q6:** Idempotency for async?
**A:** Idempotency-Key header. Server checks Redis SETNX before creating job. If exists, return same job_id (don't create duplicate). Cached for retention period (24h-7d). Critical when network blips cause client retries.

**Q7:** Polling rate guidance?
**A:** `Retry-After` header in 202 response. Adaptive: increase interval as job progresses (1s → 5s → 30s). Cap maximum interval (e.g., 60s). Client backs off if 429 returned.

**Q8:** Webhook vs polling for completion?
**A:** Webhook: client has public endpoint, server pushes on completion. Less wasted requests. Polling: simpler, no client infra. Hybrid: client provides optional webhook URL; falls back to polling if URL unreachable.

---

## Real-World Examples

### Stripe Async Processing

POST /charges returns 200 immediately with status. Webhooks notify on state changes (charge.succeeded, charge.failed). Customer can poll OR rely on webhook.

### AWS Long-Running Operations

S3 multipart upload, ECS task creation, etc. — return ID immediately. Subsequent calls to describe operation status. Standard pattern across AWS services.

### Anthropic Claude Batch API

POST /v1/messages/batches with up to 10K requests. Returns batch ID. Poll status. When complete, download results file.

---

## References

- [RFC 7240 Prefer: respond-async](https://datatracker.ietf.org/doc/html/rfc7240#section-4.1)
- [AWS Operation Pattern](https://aws.amazon.com/blogs/architecture/)
- [Stripe API design](https://stripe.com/docs/api/idempotent_requests)
- [Async API specification](https://www.asyncapi.com/)
