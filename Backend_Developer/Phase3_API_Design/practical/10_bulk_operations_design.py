"""
Bulk Operations API — Production Patterns
"""

import asyncio
import json
import uuid
from typing import Literal, Any

import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException, Header, Depends, BackgroundTasks, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError, field_validator


app = FastAPI()
r = aioredis.from_url('redis://localhost:6379/0', decode_responses=True)


# ==========================================================================
# 1. SCHEMAS
# ==========================================================================

class ProductItem(BaseModel):
    sku: str = Field(min_length=3, max_length=50, pattern=r'^[A-Z0-9-]+$')
    name: str = Field(min_length=1, max_length=200)
    price: float = Field(ge=0)
    stock: int = Field(default=0, ge=0)


class BulkCreateRequest(BaseModel):
    items: list[ProductItem] = Field(min_length=1, max_length=1000)
    mode: Literal['atomic', 'partial'] = 'partial'


class BulkResultItem(BaseModel):
    index: int
    status: int
    id: int | None = None
    sku: str | None = None
    error: str | None = None


class BulkResponse(BaseModel):
    summary: dict[str, int]
    items: list[BulkResultItem]


# ==========================================================================
# 2. PARTIAL MODE (best-effort)
# ==========================================================================

async def bulk_create_partial(items: list[ProductItem]) -> BulkResponse:
    """Continue on individual errors. Each item independent."""
    results = []
    succeeded = 0
    failed = 0

    for i, item in enumerate(items):
        try:
            # Check duplicate SKU
            # if await Product.objects.filter(sku=item.sku).aexists():
            #     raise ValueError('SKU already exists')

            # Create
            # obj = await Product.objects.acreate(**item.model_dump())
            obj_id = 1000 + i   # mock

            results.append(BulkResultItem(
                index=i,
                status=201,
                id=obj_id,
                sku=item.sku,
            ))
            succeeded += 1

        except Exception as e:
            results.append(BulkResultItem(
                index=i,
                status=400,
                sku=item.sku,
                error=str(e)[:200],
            ))
            failed += 1

    return BulkResponse(
        summary={'total': len(items), 'succeeded': succeeded, 'failed': failed},
        items=results,
    )


# ==========================================================================
# 3. ATOMIC MODE (all-or-nothing)
# ==========================================================================

async def bulk_create_atomic(items: list[ProductItem]) -> BulkResponse:
    """All succeed or none. Rollback on first error."""
    # Phase 1: validate all
    for i, item in enumerate(items):
        # Custom validation beyond Pydantic
        # if await Product.objects.filter(sku=item.sku).aexists():
        #     raise HTTPException(
        #         status_code=409,
        #         detail={'index': i, 'sku': item.sku, 'error': 'Duplicate SKU'},
        #     )
        pass

    # Phase 2: create all in transaction
    # async with transaction.atomic():
    #     objs = [Product(**item.model_dump()) for item in items]
    #     await Product.objects.abulk_create(objs, batch_size=100)

    # Mock
    results = [
        BulkResultItem(index=i, status=201, id=2000 + i, sku=item.sku)
        for i, item in enumerate(items)
    ]

    return BulkResponse(
        summary={'total': len(items), 'succeeded': len(items), 'failed': 0},
        items=results,
    )


# ==========================================================================
# 4. ENDPOINT WITH IDEMPOTENCY
# ==========================================================================

@app.post(
    '/products/bulk',
    status_code=207,
    response_model=BulkResponse,
)
async def bulk_create_products(
    payload: BulkCreateRequest,
    idempotency_key: str = Header(..., alias='Idempotency-Key'),
):
    # Validate idempotency key format
    if len(idempotency_key) < 8 or len(idempotency_key) > 128:
        raise HTTPException(400, 'Invalid Idempotency-Key format')

    cache_key = f'idem:bulk:products:{idempotency_key}'

    # Check cached result
    cached = await r.get(cache_key)
    if cached:
        return BulkResponse.model_validate_json(cached)

    # Process
    try:
        if payload.mode == 'atomic':
            result = await bulk_create_atomic(payload.items)
        else:
            result = await bulk_create_partial(payload.items)
    except HTTPException:
        # Cache errors too (so retry returns same error)
        raise

    # Cache result (24h)
    await r.set(cache_key, result.model_dump_json(), ex=86400)

    return result


# ==========================================================================
# 5. BULK UPDATE
# ==========================================================================

class BulkUpdateItem(BaseModel):
    id: int
    price: float | None = Field(None, ge=0)
    stock: int | None = Field(None, ge=0)
    name: str | None = Field(None, min_length=1, max_length=200)

    @field_validator('id')
    @classmethod
    def positive_id(cls, v):
        if v <= 0:
            raise ValueError('Invalid ID')
        return v


class BulkUpdateRequest(BaseModel):
    items: list[BulkUpdateItem] = Field(min_length=1, max_length=1000)


@app.patch('/products/bulk', status_code=207)
async def bulk_update_products(
    payload: BulkUpdateRequest,
    idempotency_key: str = Header(..., alias='Idempotency-Key'),
):
    results = []
    succeeded = failed = 0

    for i, item in enumerate(payload.items):
        try:
            # Build update dict — exclude None
            updates = item.model_dump(exclude={'id'}, exclude_unset=True)
            if not updates:
                results.append(BulkResultItem(index=i, status=400, id=item.id, error='No fields'))
                failed += 1
                continue

            # updated = await Product.objects.filter(pk=item.id).aupdate(**updates)
            updated = 1  # mock

            if updated == 0:
                results.append(BulkResultItem(index=i, status=404, id=item.id, error='Not found'))
                failed += 1
            else:
                results.append(BulkResultItem(index=i, status=200, id=item.id))
                succeeded += 1

        except Exception as e:
            results.append(BulkResultItem(index=i, status=400, id=item.id, error=str(e)[:200]))
            failed += 1

    return BulkResponse(
        summary={'total': len(payload.items), 'succeeded': succeeded, 'failed': failed},
        items=results,
    )


# ==========================================================================
# 6. BULK DELETE
# ==========================================================================

class BulkDeleteRequest(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=1000)
    soft_delete: bool = True   # default to soft delete


@app.delete('/products/bulk', status_code=207)
async def bulk_delete_products(payload: BulkDeleteRequest):
    if payload.soft_delete:
        # Bulk soft delete
        # deleted = await Product.objects.filter(pk__in=payload.ids).aupdate(
        #     deleted_at=timezone.now()
        # )
        deleted = len(payload.ids)  # mock
    else:
        # Hard delete (DANGER)
        # deleted, _ = await Product.objects.filter(pk__in=payload.ids).adelete()
        deleted = len(payload.ids)  # mock

    return {
        'summary': {
            'total': len(payload.ids),
            'deleted': deleted,
            'not_found': len(payload.ids) - deleted,
        },
    }


# ==========================================================================
# 7. ASYNC BULK JOB (large batches)
# ==========================================================================

class ImportJobRequest(BaseModel):
    type: Literal['products', 'users', 'orders']
    file_url: str
    notify_url: str | None = None    # webhook on completion


class ImportJobResponse(BaseModel):
    job_id: str
    status: str
    status_url: str


# Mock jobs DB
jobs_db: dict[str, dict] = {}


@app.post('/import-jobs', status_code=202)
async def create_import_job(
    payload: ImportJobRequest,
    background: BackgroundTasks,
):
    # Validate URL (SSRF prevention)
    # validate_url(payload.file_url)

    job_id = f'job_{uuid.uuid4().hex[:12]}'
    jobs_db[job_id] = {
        'id': job_id,
        'type': payload.type,
        'file_url': payload.file_url,
        'notify_url': payload.notify_url,
        'status': 'queued',
        'progress': {
            'total': 0,
            'processed': 0,
            'succeeded': 0,
            'failed': 0,
        },
        'errors': [],
        'created_at': uuid.uuid1().hex,   # mock timestamp
    }

    # Schedule async processing
    background.add_task(process_import_job, job_id)
    # In prod: from .tasks import process_import_job; process_import_job.delay(job_id)

    return ImportJobResponse(
        job_id=job_id,
        status='queued',
        status_url=f'/import-jobs/{job_id}',
    )


@app.get('/import-jobs/{job_id}')
async def get_job_status(job_id: str):
    job = jobs_db.get(job_id)
    if not job:
        raise HTTPException(404, 'Job not found')

    return {
        'job_id': job['id'],
        'type': job['type'],
        'status': job['status'],
        'progress': job['progress'],
        'errors': job['errors'][:100],    # truncate huge error lists
    }


@app.get('/import-jobs/{job_id}/errors')
async def get_job_errors(job_id: str, offset: int = 0, limit: int = 100):
    """Paginated full error list."""
    job = jobs_db.get(job_id)
    if not job:
        raise HTTPException(404)
    return {
        'total': len(job['errors']),
        'errors': job['errors'][offset:offset + limit],
    }


async def process_import_job(job_id: str):
    """Background worker — process import."""
    job = jobs_db.get(job_id)
    if not job:
        return

    job['status'] = 'processing'

    # Download file
    # async with httpx.AsyncClient() as c:
    #     resp = await c.get(job['file_url'])
    #     csv_content = resp.text

    # Process row by row
    total_rows = 50000   # mock
    job['progress']['total'] = total_rows

    for i in range(total_rows):
        try:
            # Process row
            await asyncio.sleep(0)   # placeholder
            job['progress']['processed'] += 1

            # Mock occasional error
            if i % 1000 == 999:
                raise ValueError(f'Mock error at row {i}')

            job['progress']['succeeded'] += 1

        except Exception as e:
            job['progress']['failed'] += 1
            if len(job['errors']) < 10000:
                job['errors'].append({'line': i, 'error': str(e)})

    job['status'] = 'completed'

    # Send webhook
    if job['notify_url']:
        # await notify_webhook(job['notify_url'], job)
        pass


# ==========================================================================
# 8. CHUNKED BULK CREATE (server-side chunking)
# ==========================================================================

async def chunked_bulk_create(items: list[dict], chunk_size: int = 100):
    """Process huge list in chunks to avoid huge transactions."""

    for chunk_idx in range(0, len(items), chunk_size):
        chunk = items[chunk_idx:chunk_idx + chunk_size]

        # async with transaction.atomic():
        #     await Product.objects.abulk_create(
        #         [Product(**item) for item in chunk]
        #     )
        await asyncio.sleep(0.01)   # mock

        # Optional: progress callback
        # await update_progress(processed=chunk_idx + len(chunk))


# ==========================================================================
# 9. PROGRESS TRACKING via WebSocket / SSE
# ==========================================================================

from fastapi import WebSocket, WebSocketDisconnect


@app.websocket('/import-jobs/{job_id}/ws')
async def job_progress_ws(websocket: WebSocket, job_id: str):
    await websocket.accept()

    try:
        while True:
            job = jobs_db.get(job_id)
            if not job:
                await websocket.send_json({'error': 'not_found'})
                await websocket.close()
                return

            await websocket.send_json({
                'status': job['status'],
                'progress': job['progress'],
            })

            if job['status'] in {'completed', 'failed', 'cancelled'}:
                await websocket.close()
                return

            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass


# ==========================================================================
# 10. CANCEL BULK JOB
# ==========================================================================

@app.post('/import-jobs/{job_id}/cancel')
async def cancel_job(job_id: str):
    job = jobs_db.get(job_id)
    if not job:
        raise HTTPException(404)

    if job['status'] not in {'queued', 'processing'}:
        raise HTTPException(409, f"Cannot cancel job in status {job['status']}")

    job['status'] = 'cancelled'

    # Signal worker to stop
    # await r.set(f'cancel:job:{job_id}', '1', ex=3600)

    return {'cancelled': True}


# ==========================================================================
# 11. CLIENT-SIDE BATCHING (sample)
# ==========================================================================

CLIENT_EXAMPLE = """
# Python client example

import httpx
import uuid


def bulk_import_chunked(items, chunk_size=100):
    results = []
    with httpx.Client() as client:
        for chunk_idx, chunk in enumerate(chunks(items, chunk_size)):
            idempotency_key = f'import-2026-01-15-{uuid.uuid4()}'

            response = client.post(
                'https://api.example.com/products/bulk',
                json={'items': chunk, 'mode': 'partial'},
                headers={'Idempotency-Key': idempotency_key},
                timeout=30,
            )

            if response.status_code == 207:
                results.extend(response.json()['items'])
            else:
                raise Exception(f'Bulk failed: {response.status_code}')

    return results


def chunks(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]
"""


# ==========================================================================
# 12. SIZE + RATE LIMITS
# ==========================================================================

LIMITS_CONFIG = """
# Bulk endpoints get stricter rate limits:
# - 100 single requests/min
# - 10 bulk requests/min
# - Bulk items: max 1000 per request
# - Payload size: max 10MB
# - Concurrent async jobs: max 3 per user
# - Job retention: 30 days

# Enforced at:
# 1. nginx: client_max_body_size 10M;
# 2. App middleware: payload size check
# 3. Endpoint validators: max_length=1000 on list
# 4. Per-user job quota in DB
"""
