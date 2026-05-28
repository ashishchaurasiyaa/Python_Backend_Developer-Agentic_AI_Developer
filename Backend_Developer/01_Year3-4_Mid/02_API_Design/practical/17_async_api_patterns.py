"""
Async API Patterns — Production Implementations
"""

import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Literal

import redis.asyncio as aioredis
from fastapi import FastAPI, Header, HTTPException, Request, Response, status, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


app = FastAPI()
r = aioredis.from_url('redis://localhost:6379/0', decode_responses=True)


# ==========================================================================
# 1. JOB MODEL
# ==========================================================================

class JobResponse(BaseModel):
    id: str
    status: Literal['queued', 'processing', 'completed', 'failed', 'cancelled']
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    progress: dict | None = None
    result_url: str | None = None
    error: str | None = None


# Mock job store (use DB or Celery in prod)
jobs_store: dict[str, dict] = {}


# ==========================================================================
# 2. CREATE JOB ENDPOINT (with idempotency)
# ==========================================================================

class ReportRequest(BaseModel):
    user_id: int
    report_type: str
    date_range: dict


@app.post('/jobs/reports', status_code=202, response_model=JobResponse)
async def create_report_job(
    payload: ReportRequest,
    response: Response,
    idempotency_key: str = Header(..., alias='Idempotency-Key'),
):
    # Idempotency check
    cached_id = await r.get(f'idem:job:{idempotency_key}')
    if cached_id:
        # Return existing job
        return await get_job_status(cached_id)

    # Create new job
    job_id = uuid.uuid4().hex
    now = datetime.utcnow().isoformat()

    job_data = {
        'id': job_id,
        'status': 'queued',
        'created_at': now,
        'started_at': None,
        'completed_at': None,
        'progress': None,
        'result_url': None,
        'error': None,
    }
    jobs_store[job_id] = job_data

    # Cache idempotency mapping (24h)
    await r.set(f'idem:job:{idempotency_key}', job_id, ex=86400)

    # Dispatch to worker
    # generate_report.delay(job_id, payload.model_dump())

    response.headers['Location'] = f'/jobs/{job_id}'
    response.headers['Retry-After'] = '5'

    return job_data


# ==========================================================================
# 3. GET STATUS (Polling)
# ==========================================================================

@app.get('/jobs/{job_id}', response_model=JobResponse)
async def get_job_status(job_id: str):
    job = jobs_store.get(job_id)
    if not job:
        raise HTTPException(404, 'Job not found')

    return job


# ==========================================================================
# 4. LONG-POLLING ENDPOINT
# ==========================================================================

@app.get('/jobs/{job_id}/wait')
async def wait_for_completion(
    job_id: str,
    timeout: int = 30,
):
    """Hold connection until job completes or timeout (max 60s)."""
    timeout = min(timeout, 60)

    start = time.time()
    while time.time() - start < timeout:
        job = jobs_store.get(job_id)
        if not job:
            raise HTTPException(404, 'Not found')

        if job['status'] in {'completed', 'failed', 'cancelled'}:
            return job

        await asyncio.sleep(2)

    # Timeout — return current state with retry header
    job = jobs_store.get(job_id)
    response = JSONResponse(content=job)
    response.headers['Retry-After'] = '5'
    return response


# ==========================================================================
# 5. SERVER-SENT EVENTS (SSE)
# ==========================================================================

from sse_starlette.sse import EventSourceResponse


@app.get('/jobs/{job_id}/events')
async def job_events(job_id: str, request: Request):
    """Stream job status changes via SSE."""

    async def gen():
        last_state = None
        last_progress_pct = -1

        while True:
            if await request.is_disconnected():
                break

            job = jobs_store.get(job_id)
            if not job:
                yield {'event': 'error', 'data': json.dumps({'error': 'not_found'})}
                break

            current_state = job['status']
            current_pct = (job.get('progress') or {}).get('percentage', 0)

            # Only emit on changes
            if current_state != last_state:
                yield {
                    'event': 'status',
                    'data': json.dumps({
                        'status': current_state,
                        'timestamp': datetime.utcnow().isoformat(),
                    }),
                }
                last_state = current_state

            if current_pct != last_progress_pct and job.get('progress'):
                yield {
                    'event': 'progress',
                    'data': json.dumps(job['progress']),
                }
                last_progress_pct = current_pct

            # Terminal states — close stream
            if current_state in {'completed', 'failed', 'cancelled'}:
                yield {
                    'event': 'final',
                    'data': json.dumps(job),
                }
                break

            await asyncio.sleep(2)

    return EventSourceResponse(gen(), ping=15)


# ==========================================================================
# 6. WEBSOCKET FOR REAL-TIME UPDATES
# ==========================================================================

from fastapi import WebSocket, WebSocketDisconnect


@app.websocket('/jobs/{job_id}/ws')
async def job_websocket(websocket: WebSocket, job_id: str):
    await websocket.accept()

    try:
        last_state = None
        while True:
            job = jobs_store.get(job_id)
            if not job:
                await websocket.send_json({'error': 'not_found'})
                await websocket.close()
                return

            if job != last_state:
                await websocket.send_json(job)
                last_state = dict(job)

            if job['status'] in {'completed', 'failed', 'cancelled'}:
                await websocket.close()
                return

            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass


# ==========================================================================
# 7. WEBHOOK CALLBACK PATTERN
# ==========================================================================

class WebhookJobRequest(BaseModel):
    user_id: int
    report_type: str
    callback_url: str
    callback_secret: str


@app.post('/jobs/with-webhook', status_code=202)
async def job_with_webhook(payload: WebhookJobRequest):
    # Validate URL (SSRF safe)
    # validate_url(payload.callback_url)

    job_id = uuid.uuid4().hex

    jobs_store[job_id] = {
        'id': job_id,
        'status': 'queued',
        'created_at': datetime.utcnow().isoformat(),
        'callback_url': payload.callback_url,
        'callback_secret': payload.callback_secret,
    }

    # Dispatch with webhook callback
    # generate_report.apply_async(
    #     args=[job_id, payload.model_dump()],
    #     link=notify_callback.s(payload.callback_url, payload.callback_secret),
    # )

    return {'job_id': job_id, 'status': 'queued'}


# Webhook notifier (after job completes)
async def notify_webhook_callback(job_id: str, callback_url: str, secret: str):
    import hmac
    import hashlib
    import httpx

    job = jobs_store[job_id]

    payload = {
        'job_id': job_id,
        'status': job['status'],
        'result_url': job.get('result_url'),
        'completed_at': job.get('completed_at'),
    }
    body = json.dumps(payload).encode()
    timestamp = int(time.time())
    sig = hmac.new(
        secret.encode(),
        f'{timestamp}.'.encode() + body,
        hashlib.sha256,
    ).hexdigest()

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            await client.post(
                callback_url,
                content=body,
                headers={
                    'Content-Type': 'application/json',
                    'X-Webhook-Timestamp': str(timestamp),
                    'X-Webhook-Signature': f'sha256={sig}',
                    'X-Job-Id': job_id,
                },
            )
        except Exception as e:
            # Log + retry via dedicated worker
            print(f'Webhook delivery failed: {e}')


# ==========================================================================
# 8. CANCELLATION
# ==========================================================================

@app.post('/jobs/{job_id}/cancel')
async def cancel_job(job_id: str):
    job = jobs_store.get(job_id)
    if not job:
        raise HTTPException(404)

    if job['status'] in {'completed', 'failed'}:
        raise HTTPException(409, f"Cannot cancel job in status {job['status']}")

    # Mark cancelled
    job['status'] = 'cancelled'
    job['completed_at'] = datetime.utcnow().isoformat()

    # Signal worker
    # task.revoke(terminate=True)
    # OR via Redis flag worker checks
    await r.set(f'cancel:job:{job_id}', '1', ex=3600)

    return {'status': 'cancelled'}


# In Celery task, check periodically:
"""
@celery.task(bind=True)
def long_task(self, job_id):
    for i in range(1000):
        if self.is_revoked():
            # OR check Redis flag
            return {'cancelled': True, 'completed': i}
        process_item(i)
"""


# ==========================================================================
# 9. RESULT DOWNLOAD (large results via signed URL)
# ==========================================================================

@app.get('/jobs/{job_id}/result')
async def get_job_result(job_id: str):
    job = jobs_store.get(job_id)
    if not job:
        raise HTTPException(404)

    if job['status'] != 'completed':
        raise HTTPException(409, f"Job not completed (status: {job['status']})")

    # For small results — inline
    if job.get('result_inline'):
        return job['result_inline']

    # For large — return signed URL
    if job.get('result_url'):
        return {
            'download_url': generate_signed_url(job['result_url'], ttl=600),
            'expires_in': 600,
        }

    raise HTTPException(404, 'No result available')


def generate_signed_url(url: str, ttl: int) -> str:
    # In real app: S3 presigned URL
    return f'{url}?signature=mock-sig&expires={int(time.time()) + ttl}'


# ==========================================================================
# 10. JOB LIST (paginated)
# ==========================================================================

@app.get('/jobs')
async def list_jobs(
    status: str | None = None,
    page: int = 1,
    limit: int = 50,
    user_id: int = 1,
):
    all_jobs = list(jobs_store.values())

    if status:
        all_jobs = [j for j in all_jobs if j['status'] == status]

    total = len(all_jobs)
    start = (page - 1) * limit
    page_jobs = all_jobs[start:start + limit]

    return {
        'items': page_jobs,
        'pagination': {
            'page': page,
            'limit': limit,
            'total': total,
            'has_more': start + limit < total,
        },
    }


# ==========================================================================
# 11. CELERY TASK WITH PROGRESS
# ==========================================================================

"""
from celery import shared_task


@shared_task(bind=True)
def generate_report(self, job_id, params):
    # Update store
    jobs_store[job_id]['status'] = 'processing'
    jobs_store[job_id]['started_at'] = datetime.utcnow().isoformat()

    total = 1000
    for i in range(total):
        # Check cancellation
        if self.is_revoked():
            jobs_store[job_id]['status'] = 'cancelled'
            return

        # Update progress (every 10 items)
        if i % 10 == 0:
            jobs_store[job_id]['progress'] = {
                'current': i,
                'total': total,
                'percentage': i * 100 // total,
            }
            # Also Celery state
            self.update_state(
                state='PROGRESS',
                meta={'current': i, 'total': total, 'percentage': i * 100 // total},
            )

        process_item(params, i)

    # Done
    result_url = upload_to_s3(generate_pdf(params))

    jobs_store[job_id].update({
        'status': 'completed',
        'completed_at': datetime.utcnow().isoformat(),
        'result_url': result_url,
        'progress': {'current': total, 'total': total, 'percentage': 100},
    })

    return {'result_url': result_url}


@shared_task
def cleanup_old_jobs():
    cutoff = datetime.utcnow() - timedelta(days=30)
    cutoff_str = cutoff.isoformat()
    expired = [jid for jid, j in jobs_store.items() if j['created_at'] < cutoff_str]
    for jid in expired:
        del jobs_store[jid]
"""


# ==========================================================================
# 12. POLLING CLIENT EXAMPLE
# ==========================================================================

CLIENT_POLLING = """
# Python client with adaptive polling

import httpx
import time


def poll_job(job_id, max_wait=600):
    base_interval = 1
    interval = base_interval
    deadline = time.time() + max_wait

    while time.time() < deadline:
        resp = httpx.get(f'https://api.example.com/jobs/{job_id}')
        data = resp.json()

        # Honor server Retry-After
        retry_after = resp.headers.get('Retry-After')
        if retry_after:
            interval = int(retry_after)

        status = data['status']
        if status == 'completed':
            return data
        elif status == 'failed':
            raise Exception(data.get('error', 'Job failed'))
        elif status == 'cancelled':
            raise Exception('Job cancelled')

        print(f'Status: {status}, progress: {data.get("progress")}')

        # Adaptive backoff (cap at 30s)
        time.sleep(interval)
        interval = min(interval * 1.5, 30)

    raise TimeoutError(f'Job not complete in {max_wait}s')


# Usage
result = poll_job('abc123', max_wait=300)
print('Done:', result)
"""


# ==========================================================================
# 13. SSE CLIENT (JavaScript)
# ==========================================================================

SSE_CLIENT_JS = """
const evt = new EventSource('/jobs/abc123/events');

evt.addEventListener('status', (e) => {
    const data = JSON.parse(e.data);
    console.log('Status:', data.status);
});

evt.addEventListener('progress', (e) => {
    const data = JSON.parse(e.data);
    document.getElementById('bar').style.width = `${data.percentage}%`;
});

evt.addEventListener('final', (e) => {
    const data = JSON.parse(e.data);
    if (data.status === 'completed') {
        window.location = data.result_url;
    } else {
        alert('Failed: ' + data.error);
    }
    evt.close();
});

evt.onerror = () => {
    console.log('SSE error, reconnecting...');
};
"""


# ==========================================================================
# 14. CIRCUIT BREAKER for downstream services
# ==========================================================================

"""
# If downstream API unreliable, don't queue more work that will fail

@app.post('/jobs')
async def create_job_with_circuit_check():
    if downstream_circuit.is_open():
        raise HTTPException(503, 'Downstream service unavailable')

    # ... create job
"""


# ==========================================================================
# 15. PROD CHECKLIST
# ==========================================================================

PROD_CHECKLIST = """
[ ] 202 Accepted on creation (not 200)
[ ] Location header with job_id URL
[ ] Retry-After header hinting poll interval
[ ] Idempotency-Key support for retry safety
[ ] Status endpoint with consistent shape
[ ] Progress updates (granularity matters — every 1-5s)
[ ] Cancellation endpoint + worker checks
[ ] Result via signed URL for large data
[ ] TTL on job records (cleanup task)
[ ] Webhook delivery with retries + HMAC signing
[ ] SSE / WebSocket for real-time UI
[ ] Adaptive polling backoff (1s → 30s cap)
[ ] Errors include detail + trace_id
[ ] Job list endpoint for client UIs
[ ] Per-user job quota (max N active)
[ ] Metrics: queue depth, processing time, failure rate
[ ] Alerts: jobs stuck > N minutes, failure rate > X%
"""
