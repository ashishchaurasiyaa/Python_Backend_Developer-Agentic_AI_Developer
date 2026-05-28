# 51 — Idempotency Tokens

> The mechanism that makes "click pay twice" not charge twice. Critical for payments, orders, and any operation where retries are inevitable.

---

## The Problem

```
Client: POST /pay (charge $100)
        ↓ (network fail)
Server: processed, charged $100
        ↓ response lost
Client: timeout → retries → POST /pay
Server: processes AGAIN → $200 charged.
```

User wanted $100, got charged $200. Trust destroyed.

---

## Idempotency Defined

**Idempotent operation:** same operation applied N times has same effect as applying it once.

```
GET /user/123        — idempotent (no side effects)
PUT /user/123        — idempotent (sets to specific value)
DELETE /user/123     — idempotent (delete twice = same as once)
POST /pay            — NOT idempotent by default
POST /pay (with key) — idempotent (handled correctly)
```

---

## Idempotency Key Pattern

Client generates a unique key per logical operation, sends it in header:

```http
POST /pay HTTP/1.1
Idempotency-Key: 8f1a2b3c-4d5e-6f7a-8b9c-0d1e2f3a4b5c
Content-Type: application/json

{"amount": 100, "to": "alice"}
```

Server:
1. Check if key seen.
2. If yes: return saved response (no re-execution).
3. If no: execute, save response, mark key as processed.

---

## Implementation

### Naive (broken under concurrency)

```python
async def pay(req, idem_key: str = Header(...)):
    cached = await redis.get(f"idem:{idem_key}")
    if cached:
        return json.loads(cached)
    result = await process_payment(req)
    await redis.set(f"idem:{idem_key}", json.dumps(result), ex=86400)
    return result
```

**Race condition:** Two simultaneous requests with same key. Both check cache → both miss → both process → both charge.

### Correct (with lock + dedup)

```python
async def pay(req, idem_key: str = Header(...)):
    # 1. Check cache
    cached = await redis.get(f"idem:{idem_key}")
    if cached:
        return json.loads(cached)

    # 2. Try to acquire lock for this key
    lock = await redis.set(f"idem_lock:{idem_key}", "1", nx=True, ex=30)
    if not lock:
        # Another request is in flight with same key
        # Option A: return 409 Conflict
        raise HTTPException(409, "Idempotent request in progress")
        # Option B: wait briefly and retry cache check
        for _ in range(30):
            await asyncio.sleep(0.1)
            cached = await redis.get(f"idem:{idem_key}")
            if cached: return json.loads(cached)
        raise HTTPException(504, "Timeout waiting for idempotent operation")

    try:
        # 3. Compute body hash to detect mismatched retries
        body_hash = hashlib.sha256(json.dumps(req, sort_keys=True).encode()).hexdigest()

        # 4. Process the payment
        result = await process_payment(req)

        # 5. Save response with hash for validation
        await redis.set(
            f"idem:{idem_key}",
            json.dumps({"hash": body_hash, "result": result, "status": 200}),
            ex=86400
        )
        return result
    finally:
        await redis.delete(f"idem_lock:{idem_key}")
```

### Validate body matches

If client reuses key with different body, that's a client bug. Server should reject:

```python
cached = json.loads(cached)
if cached["hash"] != body_hash:
    raise HTTPException(422, "Idempotency-Key reused with different request body")
return cached["result"]
```

---

## DB-Based Idempotency (More Robust)

Redis can lose data on restart (unless persisted). For mission-critical (payments), use DB.

```sql
CREATE TABLE idempotency_keys (
    key            TEXT PRIMARY KEY,
    request_hash   TEXT NOT NULL,
    response       JSONB,
    status_code    INT,
    created_at     TIMESTAMPTZ DEFAULT now(),
    expires_at     TIMESTAMPTZ
);
CREATE INDEX ON idempotency_keys(expires_at);
```

### Flow

```python
async def pay(req, idem_key):
    body_hash = compute_hash(req)

    async with db.transaction():
        # Atomically: insert (key, hash, in_progress) or fail
        try:
            await db.execute(
                "INSERT INTO idempotency_keys (key, request_hash, status_code) "
                "VALUES ($1, $2, 0)",
                idem_key, body_hash
            )
        except UniqueViolationError:
            # Key exists → fetch
            row = await db.fetchrow(
                "SELECT request_hash, response, status_code FROM idempotency_keys WHERE key = $1",
                idem_key
            )
            if row.status_code == 0:
                raise HTTPException(409, "Request in flight")
            if row.request_hash != body_hash:
                raise HTTPException(422, "Body mismatch")
            return JSONResponse(row.response, status_code=row.status_code)

    # Process
    try:
        result = await process_payment(req)
        await db.execute(
            "UPDATE idempotency_keys SET response = $1, status_code = 200 "
            "WHERE key = $2",
            json.dumps(result), idem_key
        )
        return result
    except Exception as e:
        await db.execute(
            "UPDATE idempotency_keys SET response = $1, status_code = 500 WHERE key = $2",
            json.dumps({"error": str(e)}), idem_key
        )
        raise
```

**Key insight:** Unique constraint on `key` is the race-condition-killer.

---

## Storing Errors Idempotently

If a request fails (5xx), should retries succeed or fail?

### Conservative: replay error
- Failure was "real" (insufficient funds).
- Retrying won't help.
- Return cached error.

### Aggressive: allow retry
- Failure was infra (timeout, DB down).
- Retry might succeed.
- Don't cache 5xx.

**Pattern:** Cache 4xx + 200; treat 5xx as "try again" by not storing.

```python
if 200 <= status_code < 500 and status_code != 408 and status_code != 425:
    # Cache 2xx, 3xx, 4xx (except timeout codes)
    await cache_response(key, response)
```

---

## Idempotency Key Lifetime

How long to keep keys?

| Lifetime | Trade-off |
|---|---|
| 5 min | Covers immediate retries; saves storage |
| 24 hours | Stripe's default; covers most real-world scenarios |
| 7 days | For idempotent batch operations |
| Forever | Big storage cost; only for high-stakes |

**Stripe:** 24 hours.
**AWS APIs:** varies; typically 1-7 days.
**Square:** 60 minutes default.

---

## What Operations Need Idempotency?

### Always
- Payment, transfers, charges.
- Order placement.
- Account credits/debits.
- Sending notifications/emails (don't spam user).
- Stock reservation.

### Usually
- Resource creation (avoid duplicates).
- Event publishing.

### Rarely
- Read-only queries (idempotent by design).
- Logging.

---

## Client Responsibility

Client must:
1. **Generate UUID for each logical operation** (not per HTTP attempt).
2. **Reuse same key on retry** — that's the whole point.
3. **Don't reuse keys for different operations** — server treats different-body-same-key as error.

```javascript
const idempotencyKey = uuid.v4();  // generate ONCE per user action

for (let attempt = 0; attempt < 3; attempt++) {
    try {
        return await fetch('/pay', {
            headers: {'Idempotency-Key': idempotencyKey},
            body: JSON.stringify({amount: 100})
        });
    } catch (err) {
        if (attempt === 2) throw err;
        await sleep(2 ** attempt * 1000);  // exponential backoff
    }
}
```

---

## Server-Side Alternatives

### Natural idempotency via unique constraints

If the operation has a natural unique key:

```sql
CREATE TABLE payments (
    id            UUID PRIMARY KEY,
    user_id       UUID,
    amount        NUMERIC,
    request_id    TEXT UNIQUE,    -- client-provided
    created_at    TIMESTAMPTZ
);

INSERT INTO payments (id, user_id, amount, request_id)
VALUES ($1, $2, $3, $4);
-- If duplicate request_id → UniqueViolationError → return existing payment
```

Simpler than full idempotency key infra.

### Use of unique ID in resource creation

```http
POST /orders
{"id": "ord_abc123", "items": [...]}
```

Server uses provided ID. Conflict → "already exists" → return existing order.

---

## Idempotency in Distributed Workflows

For multi-step business processes (Saga pattern):

```
Step 1: Reserve inventory
Step 2: Charge card
Step 3: Ship order

Each step independently idempotent → retry safe at any point.
```

Generate step-specific idempotency keys:
```
order_abc_step_reserve
order_abc_step_charge
order_abc_step_ship
```

If workflow restarts after step 2 succeeded but state lost:
- Re-running step 2 with same key → no double charge.
- Re-running step 3 → no double ship.

---

## At-Least-Once Delivery + Idempotency

Distributed message systems (Kafka, SQS) guarantee at-least-once delivery → duplicates inevitable.

**Pattern:** Producer assigns unique ID to each message. Consumer dedups via idempotency key.

```python
async def consume(msg):
    msg_id = msg.headers["msg_id"]
    if await redis.exists(f"processed:{msg_id}"):
        return  # already done
    await process(msg)
    await redis.set(f"processed:{msg_id}", "1", ex=86400)
```

This is how exactly-once is achieved in practice — at-least-once + idempotent consumer = effectively-once.

---

## Stripe's Implementation Notes

Stripe's idempotency is the gold standard:
- Key in `Idempotency-Key` header.
- 24-hour retention.
- 255-char limit on key.
- Hash check on body.
- Returns full original response (status code + body + headers).
- Errors with "Idempotency-Key already used" if body differs.
- 409 if request in progress.

[https://stripe.com/docs/api/idempotent_requests](https://stripe.com/docs/api/idempotent_requests)

---

## Common Mistakes

### 1. Client generates new key on each retry
Defeats the purpose. Server sees new key each time → re-processes.

### 2. Server doesn't store the response
Replay returns "200 OK" but no actual data. Caller doesn't know if the operation completed.

### 3. Don't validate body hash
Different body with same key should be a 422 error, not silent override.

### 4. Mixing idempotent and non-idempotent state
If step 1 mutates external state non-idempotently, retry breaks.

### 5. Caching errors permanently
"User had insufficient funds at 9am" cached forever → retry at noon when balance restored fails forever.

### 6. Forgetting expiry
Idempotency table grows unboundedly. Add cleanup job.

---

## Testing Idempotency

```python
@pytest.mark.asyncio
async def test_idempotent_pay():
    key = str(uuid.uuid4())
    # First request
    r1 = await client.post("/pay", json={"amount": 100}, headers={"Idempotency-Key": key})
    assert r1.status_code == 200

    # Second request (retry)
    r2 = await client.post("/pay", json={"amount": 100}, headers={"Idempotency-Key": key})
    assert r2.status_code == 200
    assert r1.json() == r2.json()

    # Verify only one charge in DB
    charges = await db.fetch("SELECT * FROM charges WHERE idem_key = $1", key)
    assert len(charges) == 1

@pytest.mark.asyncio
async def test_idempotency_concurrent():
    key = str(uuid.uuid4())
    responses = await asyncio.gather(*[
        client.post("/pay", json={"amount": 100}, headers={"Idempotency-Key": key})
        for _ in range(10)
    ])
    success = [r for r in responses if r.status_code == 200]
    # Either 1 success + 9 conflicts (strict), or 10 successes returning same response
    assert all(r.json() == success[0].json() for r in success)
```

---

## Idempotency for State Machines

For order status transitions:

```
PENDING → PAID → SHIPPED → DELIVERED
```

Each transition idempotent if you check current state:

```python
async def mark_paid(order_id):
    result = await db.execute(
        "UPDATE orders SET status = 'paid' WHERE id = $1 AND status = 'pending' "
        "RETURNING *",
        order_id
    )
    if not result:
        # Either already paid or never existed
        order = await db.fetchrow("SELECT * FROM orders WHERE id = $1", order_id)
        if order and order.status == 'paid':
            return order   # idempotent success
        raise InvalidStateTransition()
    return result
```

---

## Idempotency Key Format

| Format | Pros | Cons |
|---|---|---|
| UUID v4 | Random, no collisions, easy to generate | No info embedded |
| UUID v7 | Time-ordered, useful in DB indexes | Same as v4 properties |
| Snowflake | Time-ordered, compact | Needs central generator |
| Hash of body | Deterministic | Different body = different key (loses retry semantics) |
| Custom (`{user_id}-{operation}-{timestamp}`) | Debuggable | Risk of collisions |

**Recommend:** UUID v7 generated client-side, sent in header.

---

## TL;DR

- Idempotency = same op, same result.
- Use `Idempotency-Key` header.
- Server: dedupe via Redis or DB unique constraint.
- Store full response, return on replay.
- Validate body matches (else 422).
- 24-hour retention typical.
- Handle concurrency: lock or unique-constraint.
- Test with concurrent + retry scenarios.

**Essential for:** payments, orders, message processing. Non-negotiable for senior backend roles.
