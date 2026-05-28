# Bulk Operations API Design

## Why It Matters

Single requests = slow for batch needs:
- Import 10K records → 10K HTTP requests = OUCH
- Delete 1M old logs → infinite scroll deletions
- Update prices on 500 products

Bulk APIs solve this. But design choices matter: atomic vs best-effort, response shape, error handling, idempotency.

Senior interview: "Design API for importing 100K records efficiently."

---

## Bulk Patterns

### 1. Bulk Create (Idempotent)

```http
POST /v1/products/bulk
Content-Type: application/json
Idempotency-Key: import-2026-01-15-abc123

{
    "items": [
        {"sku": "A001", "name": "Widget", "price": 9.99},
        {"sku": "A002", "name": "Gadget", "price": 19.99}
    ]
}
```

```http
HTTP/1.1 200 OK

{
    "created": 2,
    "failed": 0,
    "items": [
        {"sku": "A001", "id": 1234, "status": "created"},
        {"sku": "A002", "id": 1235, "status": "created"}
    ]
}
```

### 2. Bulk with Partial Success (Best-Effort)

```http
POST /v1/users/bulk
{
    "items": [
        {"email": "a@example.com", "name": "Alice"},
        {"email": "INVALID", "name": "Bob"},
        {"email": "c@example.com", "name": "Carol"}
    ]
}
```

```http
HTTP/1.1 207 Multi-Status

{
    "summary": {"total": 3, "succeeded": 2, "failed": 1},
    "items": [
        {"index": 0, "status": 201, "id": 1, "email": "a@example.com"},
        {"index": 1, "status": 422, "error": "Invalid email format"},
        {"index": 2, "status": 201, "id": 2, "email": "c@example.com"}
    ]
}
```

`207 Multi-Status` (RFC 4918) signals mixed results.

### 3. Bulk Atomic (All-or-Nothing)

```http
POST /v1/orders/bulk?mode=atomic
{
    "items": [...]
}
```

If any item fails, entire batch rolled back. Returns 422 with first error.

### 4. Bulk Update

```http
PATCH /v1/products/bulk
{
    "items": [
        {"id": 1, "price": 9.99},
        {"id": 2, "price": 19.99}
    ]
}
```

Each item has identifier + patch fields.

### 5. Bulk Delete

```http
DELETE /v1/messages/bulk
{
    "ids": [1, 2, 3, 4, 5]
}
```

Or via query:

```http
DELETE /v1/messages?ids=1,2,3,4,5
```

Or filter-based:

```http
DELETE /v1/messages?older_than=2026-01-01&status=spam
```

Filter-based dangerous (mass delete bug) — require explicit confirmation.

### 6. Async Bulk Operation

For huge batches (>1000 items):

```http
POST /v1/import-jobs
{
    "type": "products",
    "file_url": "https://uploads/import.csv"
}


HTTP/1.1 202 Accepted

{
    "job_id": "job_abc123",
    "status": "queued",
    "status_url": "/v1/import-jobs/job_abc123"
}
```

Client polls or webhook:

```http
GET /v1/import-jobs/job_abc123

{
    "job_id": "job_abc123",
    "status": "processing",
    "progress": {
        "total": 50000,
        "processed": 12000,
        "succeeded": 11500,
        "failed": 500
    },
    "errors": [
        {"line": 142, "error": "Duplicate SKU"}
    ]
}
```

---

## Size Limits

### Hard Limits

```python
MAX_BULK_ITEMS = 1000      # per request
MAX_PAYLOAD_SIZE = 10 * 1024 * 1024   # 10 MB
```

Reject larger requests at edge (nginx) + app.

### Pagination of Bulk

For very large batches, paginate or chunk:

```http
# Client side
items = [...]
for chunk in chunks(items, 100):
    api.post('/bulk', {'items': chunk})
```

Or server-side via file upload + async job.

---

## Idempotency

```http
POST /v1/products/bulk
Idempotency-Key: import-batch-2026-01-15-abc
```

Server stores key → result mapping for 24h. Duplicate request → return cached response.

```python
@app.post('/products/bulk')
def bulk_create(payload, idempotency_key: str = Header(...)):
    cached = redis.get(f'idempotency:{idempotency_key}')
    if cached:
        return json.loads(cached)

    # Process
    result = do_bulk_create(payload)

    # Cache for 24h
    redis.set(
        f'idempotency:{idempotency_key}',
        json.dumps(result),
        ex=86400,
    )
    return result
```

---

## Error Handling Strategies

### Strategy 1: Fail-Fast (Atomic)

First error → abort entire batch.

```python
@transaction.atomic
def bulk_create_atomic(items):
    created = []
    for i, item in enumerate(items):
        try:
            created.append(Model.objects.create(**item))
        except Exception as e:
            raise BulkError(index=i, error=str(e))
    return created
```

Pros: simple, all-or-nothing semantics.
Cons: one bad item blocks 999 good ones.

### Strategy 2: Best-Effort (Partial)

Continue on individual errors.

```python
def bulk_create_partial(items):
    results = []
    for i, item in enumerate(items):
        try:
            obj = Model.objects.create(**item)
            results.append({'index': i, 'status': 201, 'id': obj.id})
        except Exception as e:
            results.append({'index': i, 'status': 400, 'error': str(e)})
    return results
```

Pros: import maximum data despite errors.
Cons: harder to reason about partial state.

### Strategy 3: Validate-First

```python
def bulk_create_validated(items):
    # Phase 1: validate ALL
    errors = []
    for i, item in enumerate(items):
        try:
            Schema.model_validate(item)
        except ValidationError as e:
            errors.append({'index': i, 'error': str(e)})

    if errors:
        return {'errors': errors}

    # Phase 2: create (atomic)
    with transaction.atomic():
        created = Model.objects.bulk_create([Model(**item) for item in items])
    return {'created': len(created)}
```

Best for: structured data where validation cheap, create expensive.

---

## Implementation (FastAPI)

```python
from pydantic import BaseModel
from typing import Literal


class BulkItem(BaseModel):
    sku: str
    name: str
    price: float


class BulkRequest(BaseModel):
    items: list[BulkItem]
    mode: Literal['atomic', 'partial'] = 'partial'


class BulkResultItem(BaseModel):
    index: int
    status: int
    id: int | None = None
    error: str | None = None


class BulkResponse(BaseModel):
    summary: dict
    items: list[BulkResultItem]


@app.post(
    '/products/bulk',
    response_model=BulkResponse,
    status_code=207,
)
async def bulk_create(
    payload: BulkRequest,
    idempotency_key: str = Header(...),
    user: CurrentUser = Depends(get_current_user),
):
    # Idempotency
    cached = redis_client.get(f'idem:{idempotency_key}')
    if cached:
        return json.loads(cached)

    # Validate batch size
    if len(payload.items) > 1000:
        raise HTTPException(400, 'Max 1000 items per batch')

    if payload.mode == 'atomic':
        result = await bulk_atomic(payload.items, user)
    else:
        result = await bulk_partial(payload.items, user)

    # Cache result
    redis_client.set(f'idem:{idempotency_key}', json.dumps(result), ex=86400)
    return result
```

---

## Async Bulk (Large Batches)

```python
@app.post('/import-jobs', status_code=202)
async def create_import_job(
    file_url: str,
    user: CurrentUser = Depends(get_current_user),
):
    # Validate URL (SSRF safe)
    validate_url(file_url)

    job = ImportJob.objects.create(
        user_id=user.id,
        file_url=file_url,
        status='queued',
    )

    # Async processing
    process_import_job.delay(job.id)

    return {
        'job_id': job.id,
        'status': 'queued',
        'status_url': f'/import-jobs/{job.id}',
    }


@app.get('/import-jobs/{job_id}')
async def get_job_status(job_id, user: CurrentUser = Depends(get_current_user)):
    job = ImportJob.objects.get(id=job_id, user_id=user.id)
    return {
        'job_id': job.id,
        'status': job.status,
        'progress': {
            'total': job.total,
            'processed': job.processed,
            'succeeded': job.succeeded,
            'failed': job.failed,
        },
        'errors': job.errors[:100],   # truncate huge error lists
    }
```

---

## Common Pitfalls

### 1. No Size Limit

```python
# Client sends 1M items → server OOM
```

Always set `MAX_BULK_ITEMS`.

### 2. Loop with N Queries

```python
for item in items:
    Model.objects.create(**item)   # 1000 queries
```

Use `bulk_create`:

```python
Model.objects.bulk_create([Model(**item) for item in items])   # 1 query
```

### 3. No Idempotency

Network glitch → client retries → duplicate import → corrupt data.

### 4. Atomic Mode for Huge Batches

10K items in single transaction → lock everything for minutes. Chunk into 100s.

### 5. Returning Huge Response

```python
{
    'items': [...10K result objects with full data...]
}
```

Return summary + sample errors. Full results via separate paginated endpoint.

### 6. No Progress for Async Jobs

User waits unknown duration. Provide progress updates via polling or webhook.

### 7. Mixing Bulk + Pagination Confusingly

`/items/bulk?page=2` — weird. Bulk = one-shot. Use file upload for huge data + paginated polling for results.

---

## Interview Q&A

**Q1:** Bulk endpoint design choices?
**A:** (1) Atomic vs partial — atomic for financial; partial for import-friendly. (2) Size limit (typically 100-1000 items). (3) Idempotency key for safe retries. (4) Response shape — summary + per-item status. (5) 207 Multi-Status for partial. (6) Async via job for huge batches.

**Q2:** Atomic vs partial mode trade-off?
**A:** Atomic: all-or-nothing, simple semantics, but one bad row blocks all. Partial: best-effort, max throughput, but complex error handling. Default partial for imports; atomic for transactional ops (orders, transfers).

**Q3:** Idempotency in bulk APIs?
**A:** `Idempotency-Key` header. Server stores key → result in Redis (24h TTL). Duplicate request returns cached response. Critical: same key with different payload should be rejected (409) — prevents accidental misuse.

**Q4:** 100K items batch — sync or async?
**A:** Async via job. POST returns 202 + job_id. Client polls GET /jobs/{id} for status. Process in background (Celery). Includes progress (succeeded/failed/total). Result available via separate endpoint or webhook.

**Q5:** Error response for partial bulk?
**A:** 207 Multi-Status with per-item status:
```json
{
    "summary": {"total": 100, "succeeded": 95, "failed": 5},
    "items": [
        {"index": 0, "status": 201, "id": ...},
        {"index": 42, "status": 422, "error": "..."}
    ]
}
```

**Q6:** Bulk update vs PATCH on each?
**A:** Bulk: 1 request, N rows updated. PATCH per item: N requests. Bulk preferred for large N. But: bulk needs careful design (which fields updateable, validation per item). For 5-10 items, individual PATCHes simpler.

**Q7:** Race conditions in bulk?
**A:** Two concurrent bulk requests with overlapping items → undefined result. Solutions: (1) Idempotency keys force serialization. (2) `SELECT FOR UPDATE` locking on identifying fields. (3) Optimistic locking via version column. (4) Queue serialization (single worker per resource).

**Q8:** Bulk operations limits?
**A:** Hard cap: 1000 items per request (memory, lock time). Payload size: 10 MB. Rate limit: bulk endpoints lower than single (e.g., 10/min vs 1000/min). Per-account quota: max active jobs at once.

---

## Real-World Use Cases

### 1. Stripe Bulk Charge

Actually doesn't support bulk in API — but recommends client-side concurrency with idempotency keys. Trade-off: client complexity vs server features.

### 2. SendGrid Bulk Send

```json
POST /v3/mail/send

{
    "personalizations": [
        {"to": [{"email": "user1@example.com"}], "subject": "Hi"},
        {"to": [{"email": "user2@example.com"}], "subject": "Hi"}
    ],
    "from": {"email": "sender@example.com"},
    "content": [{"type": "text/plain", "value": "Body"}]
}
```

1 API call → N personalized emails sent.

### 3. Shopify Bulk Operations

Async job model. GraphQL `bulkOperationRunQuery` mutation. Returns operation ID. Client polls for completion → downloads result file.

---

## References

- [RFC 4918 — Multi-Status (207)](https://datatracker.ietf.org/doc/html/rfc4918#section-13)
- [Stripe Idempotency](https://stripe.com/docs/api/idempotent_requests)
- [Shopify Bulk Operations](https://shopify.dev/docs/apps/tools/graphql/bulk-operations)
- [Microsoft API guidelines — Bulk](https://github.com/microsoft/api-guidelines)
