# Lecture 5 — Practical Hands-On: Real-World Patterns

> **Theory file:** [05_Real_World_Use_Cases.md](05_Real_World_Use_Cases.md)

---

## 🎯 Is Practical Mein Kya Banayenge?

Real-world distributed system patterns:

1. ✅ **SaaS multi-tenant** architecture (schema-per-tenant)
2. ✅ **Public API platform** patterns (idempotency, versioning)
3. ✅ **Fintech Saga** with compensations
4. ✅ **E-commerce inventory** with race condition handling
5. ✅ **Social feed** generation (hybrid push/pull)
6. ✅ **Outbox pattern** for reliable events
7. ✅ **CQRS** with read/write separation
8. ✅ **BFF pattern** for different clients
9. ✅ **Production-ready** code samples

By end: aap **real-world distributed patterns** ko code mein implement kar sakte ho.

---

## 1. 🏢 SaaS Multi-Tenant Architecture

### Schema-Per-Tenant Pattern

```python
"""
Multi-tenant SaaS with schema-per-tenant isolation.
Each tenant gets their own PostgreSQL schema.
"""
from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker
from contextvars import ContextVar
from fastapi import FastAPI, Header, Depends, HTTPException

app = FastAPI()

# Context variable to track current tenant
current_tenant: ContextVar[str] = ContextVar("current_tenant")

DATABASE_URL = "postgresql://user:pass@localhost/saas_db"
engine = create_engine(DATABASE_URL)

# ─────────────────────────────────────────────────────────────
# TENANT MIDDLEWARE
# ─────────────────────────────────────────────────────────────
def get_tenant_id(x_tenant_id: str = Header(...)) -> str:
    """Extract tenant ID from header"""
    if not x_tenant_id:
        raise HTTPException(401, "Missing tenant ID")
    
    # Validate tenant exists & user has access
    # In production: JWT decode + tenant access check
    return x_tenant_id

def get_db(tenant_id: str = Depends(get_tenant_id)):
    """Get DB session for specific tenant"""
    current_tenant.set(tenant_id)
    
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    try:
        # Set search_path to tenant's schema
        session.execute(f"SET search_path TO tenant_{tenant_id}, public")
        yield session
    finally:
        session.close()

# ─────────────────────────────────────────────────────────────
# TENANT PROVISIONING
# ─────────────────────────────────────────────────────────────
def provision_tenant(tenant_id: str):
    """Create new tenant's schema with tables"""
    with engine.connect() as conn:
        # Create schema
        conn.execute(f"CREATE SCHEMA tenant_{tenant_id}")
        
        # Create tenant-specific tables
        conn.execute(f"""
            CREATE TABLE tenant_{tenant_id}.users (
                id SERIAL PRIMARY KEY,
                email VARCHAR UNIQUE NOT NULL,
                name VARCHAR NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            
            CREATE TABLE tenant_{tenant_id}.documents (
                id SERIAL PRIMARY KEY,
                title VARCHAR NOT NULL,
                content TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)

# ─────────────────────────────────────────────────────────────
# API ENDPOINTS
# ─────────────────────────────────────────────────────────────
@app.get("/users")
def list_users(db = Depends(get_db)):
    """Each tenant sees ONLY their data"""
    result = db.execute("SELECT * FROM users").fetchall()
    return [dict(r) for r in result]

@app.post("/tenants")
def create_tenant(tenant_id: str):
    """Onboard new tenant"""
    provision_tenant(tenant_id)
    return {"status": "provisioned", "tenant_id": tenant_id}
```

### Comparison: Multi-Tenancy Strategies

```python
# Strategy 1: Shared DB, Shared Tables (tenant_id column)
class Document(Base):
    id = Column(Integer, primary_key=True)
    tenant_id = Column(String, index=True)  # ← MUST be in every query!
    title = Column(String)

# Strategy 2: Shared DB, Separate Schemas (recommended)
# See implementation above

# Strategy 3: Separate Databases per Tenant
def get_db_for_tenant(tenant_id):
    return create_engine(f"postgresql://...{tenant_id}_db")
```

---

## 2. 💳 Public API Platform Patterns

### Idempotency Keys (Stripe-Style)

```python
"""
Idempotency for payment APIs.
Same request with same idempotency key = same response.
"""
from fastapi import FastAPI, Header, HTTPException
from typing import Optional
import redis.asyncio as redis
import hashlib
import json
from datetime import timedelta

app = FastAPI()
redis_client = redis.from_url("redis://localhost")

async def with_idempotency(
    idempotency_key: Optional[str],
    handler,
    request_body: dict,
    ttl_hours: int = 24,
):
    """
    Wrap any handler with idempotency.
    
    Behavior:
    - First call: Execute handler, cache response
    - Subsequent calls (same key, same body): Return cached
    - Subsequent calls (same key, DIFFERENT body): Reject (conflict)
    """
    if not idempotency_key:
        return await handler()
    
    # Hash of request body (to detect replay vs. conflict)
    body_hash = hashlib.sha256(
        json.dumps(request_body, sort_keys=True).encode()
    ).hexdigest()
    
    cache_key = f"idempotency:{idempotency_key}"
    cached = await redis_client.get(cache_key)
    
    if cached:
        cached_data = json.loads(cached)
        
        if cached_data["body_hash"] != body_hash:
            raise HTTPException(
                409,
                "Idempotency-Key conflict: different request body"
            )
        
        # Return cached response
        return cached_data["response"]
    
    # Execute and cache
    response = await handler()
    
    await redis_client.setex(
        cache_key,
        timedelta(hours=ttl_hours),
        json.dumps({
            "body_hash": body_hash,
            "response": response,
        })
    )
    
    return response

# ─────────────────────────────────────────────────────────────
# USAGE
# ─────────────────────────────────────────────────────────────
@app.post("/v1/charges")
async def create_charge(
    request_data: dict,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    async def _process():
        # Actual charge logic
        return {
            "id": "ch_abc123",
            "amount": request_data["amount"],
            "status": "succeeded"
        }
    
    return await with_idempotency(
        idempotency_key=idempotency_key,
        handler=_process,
        request_body=request_data,
    )
```

### API Versioning

```python
"""
Date-based API versioning (Stripe pattern).
Each customer pins to a version.
"""
from fastapi import FastAPI, Header, Request
from typing import Optional

app = FastAPI()

API_VERSIONS = ["2024-04-15", "2024-03-01", "2024-01-15"]
DEFAULT_VERSION = "2024-04-15"

class VersionedAPI:
    """Route requests based on version header"""
    
    def __init__(self):
        self.handlers = {}  # version → handler function
    
    def add_version(self, version: str, handler):
        self.handlers[version] = handler
    
    def get_handler(self, version: Optional[str]):
        version = version or DEFAULT_VERSION
        if version not in API_VERSIONS:
            raise HTTPException(400, f"Unsupported version: {version}")
        
        # Find handler for this or older version (forward compat)
        for v in API_VERSIONS:
            if v <= version and v in self.handlers:
                return self.handlers[v]
        
        raise HTTPException(400, "No handler available")

# ─────────────────────────────────────────────────────────────
# USAGE: Same endpoint, different versions
# ─────────────────────────────────────────────────────────────
charge_api = VersionedAPI()

@charge_api.add_version("2024-01-15")
async def create_charge_v1(data):
    return {"id": "ch_001", "amount": data["amount"]}

@charge_api.add_version("2024-04-15")
async def create_charge_v2(data):
    # New version adds "currency" field, supports new payment methods
    return {
        "id": "ch_001",
        "amount": data["amount"],
        "currency": data.get("currency", "usd"),
        "payment_method_types": ["card", "wallet"],
    }

@app.post("/v1/charges")
async def create_charge(
    data: dict,
    stripe_version: Optional[str] = Header(None, alias="Stripe-Version")
):
    handler = charge_api.get_handler(stripe_version)
    return await handler(data)
```

### Rate Limiting Per Customer

```python
"""
Per-customer rate limiting using Redis token bucket.
"""
import time

class TokenBucketRateLimiter:
    """
    Token bucket: 
    - Bucket holds N tokens
    - Refills at R tokens/sec
    - Each request consumes 1 token
    - When empty: rate limited
    """
    
    def __init__(self, redis_client, capacity: int, refill_rate: float):
        self.redis = redis_client
        self.capacity = capacity
        self.refill_rate = refill_rate
    
    async def allow_request(self, key: str) -> tuple[bool, dict]:
        """Returns (allowed, headers)"""
        now = time.time()
        
        # Lua script for atomic operations
        lua = """
        local key = KEYS[1]
        local capacity = tonumber(ARGV[1])
        local rate = tonumber(ARGV[2])
        local now = tonumber(ARGV[3])
        
        local data = redis.call('HMGET', key, 'tokens', 'last_refill')
        local tokens = tonumber(data[1]) or capacity
        local last = tonumber(data[2]) or now
        
        -- Refill tokens
        local elapsed = now - last
        tokens = math.min(capacity, tokens + elapsed * rate)
        
        if tokens >= 1 then
            tokens = tokens - 1
            redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
            redis.call('EXPIRE', key, 3600)
            return {1, tokens}
        else
            return {0, tokens}
        end
        """
        
        result = await self.redis.eval(
            lua, 1, key, self.capacity, self.refill_rate, now
        )
        allowed = bool(result[0])
        remaining = int(result[1])
        
        return allowed, {
            "X-RateLimit-Limit": str(self.capacity),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(int(now + (1 / self.refill_rate))),
        }

# Usage
limiter = TokenBucketRateLimiter(
    redis_client,
    capacity=100,        # 100 tokens max
    refill_rate=10/60,   # 10 requests per minute
)

@app.middleware("http")
async def rate_limit(request, call_next):
    customer_id = request.headers.get("X-Customer-Id")
    if customer_id:
        allowed, headers = await limiter.allow_request(f"rate:{customer_id}")
        if not allowed:
            return JSONResponse(
                {"error": "Rate limit exceeded"},
                status_code=429,
                headers=headers
            )
    
    response = await call_next(request)
    for k, v in headers.items():
        response.headers[k] = v
    return response
```

---

## 3. 🏦 Fintech Saga with Compensations

### Production Saga Implementation

```python
"""
Saga orchestrator for distributed financial transactions.
Each step has a compensating action.
"""
import asyncio
import logging
from typing import Callable, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

class StepStatus(Enum):
    PENDING = "pending"
    EXECUTING = "executing"
    SUCCESS = "success"
    FAILED = "failed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"

@dataclass
class SagaStep:
    name: str
    action: Callable
    compensation: Optional[Callable] = None
    status: StepStatus = StepStatus.PENDING
    result: Any = None
    error: Optional[str] = None

class FinancialSaga:
    """
    Saga for financial transactions.
    
    Features:
    - Sequential steps
    - Automatic compensation on failure
    - Persistence to DB (for crash recovery)
    - Audit logging
    """
    
    def __init__(self, saga_id: str, name: str, audit_logger):
        self.saga_id = saga_id
        self.name = name
        self.steps: List[SagaStep] = []
        self.audit = audit_logger
    
    def add_step(self, name: str, action: Callable, compensation: Callable = None):
        self.steps.append(SagaStep(name=name, action=action, compensation=compensation))
        return self
    
    async def execute(self) -> dict:
        """Execute all steps, compensating on failure"""
        await self.audit.log(self.saga_id, "saga.started", {"name": self.name})
        
        executed = []
        
        try:
            for step in self.steps:
                await self._execute_step(step)
                executed.append(step)
            
            await self.audit.log(self.saga_id, "saga.completed", {"name": self.name})
            return {"status": "SUCCESS", "results": [s.result for s in executed]}
        
        except Exception as e:
            await self.audit.log(self.saga_id, "saga.failed", {
                "name": self.name,
                "failed_step": step.name,
                "error": str(e),
            })
            
            await self._compensate(executed)
            return {"status": "FAILED", "error": str(e), "failed_step": step.name}
    
    async def _execute_step(self, step: SagaStep):
        step.status = StepStatus.EXECUTING
        await self.audit.log(self.saga_id, "step.started", {"step": step.name})
        
        try:
            step.result = await step.action()
            step.status = StepStatus.SUCCESS
            await self.audit.log(self.saga_id, "step.completed", {
                "step": step.name,
                "result": str(step.result)[:200],
            })
        except Exception as e:
            step.status = StepStatus.FAILED
            step.error = str(e)
            raise
    
    async def _compensate(self, executed_steps: List[SagaStep]):
        """Run compensations in REVERSE order"""
        for step in reversed(executed_steps):
            if step.compensation:
                step.status = StepStatus.COMPENSATING
                await self.audit.log(self.saga_id, "step.compensating", {
                    "step": step.name
                })
                
                try:
                    await step.compensation(step.result)
                    step.status = StepStatus.COMPENSATED
                except Exception as e:
                    # Critical: compensation failed
                    logger.error(f"COMPENSATION FAILED for {step.name}: {e}")
                    await self.audit.log(self.saga_id, "step.compensation_failed", {
                        "step": step.name,
                        "error": str(e),
                    })

# ─────────────────────────────────────────────────────────────
# REAL EXAMPLE: Payment Flow
# ─────────────────────────────────────────────────────────────
async def process_payment(order_id, user_id, amount):
    saga = FinancialSaga(
        saga_id=f"saga-{order_id}",
        name="payment_processing",
        audit_logger=audit_logger,
    )
    
    # Step 1: Reserve funds in wallet
    saga.add_step(
        name="reserve_funds",
        action=lambda: wallet_service.reserve(user_id, amount),
        compensation=lambda r: wallet_service.cancel_reservation(r["reservation_id"])
    )
    
    # Step 2: Fraud check
    saga.add_step(
        name="fraud_check",
        action=lambda: fraud_service.evaluate(user_id, amount),
        # No compensation - it's just a check
    )
    
    # Step 3: Charge external gateway
    saga.add_step(
        name="external_charge",
        action=lambda: gateway.charge(amount),
        compensation=lambda r: gateway.refund(r["charge_id"])
    )
    
    # Step 4: Record in immutable ledger
    saga.add_step(
        name="ledger_entry",
        action=lambda: ledger_service.record({
            "order_id": order_id,
            "user_id": user_id,
            "amount": amount,
            "type": "DEBIT",
        }),
        compensation=lambda r: ledger_service.record({
            "order_id": order_id,
            "user_id": user_id,
            "amount": amount,
            "type": "REVERSAL",
            "reversal_of": r["entry_id"],
        })
    )
    
    # Step 5: Update wallet balance
    saga.add_step(
        name="finalize_wallet",
        action=lambda: wallet_service.deduct(user_id, amount),
        # No compensation - this is last step
    )
    
    return await saga.execute()
```

---

## 4. 🛒 E-Commerce Inventory with Race Conditions

### Optimistic Locking Pattern

```python
"""
Inventory with race condition handling.
Multiple users trying to buy the LAST iPhone.
"""
import asyncpg
import asyncio
from typing import Optional

class InventoryRepository:
    """Inventory with concurrency control"""
    
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool
    
    async def reserve_item(
        self, 
        sku: str, 
        quantity: int,
        reservation_id: str,
        ttl_seconds: int = 900,  # 15 minutes
    ) -> bool:
        """
        Atomically reserve stock using conditional update.
        
        Returns True if reserved, False if insufficient stock.
        """
        async with self.pool.acquire() as conn:
            # ATOMIC: update only if stock available
            result = await conn.fetchval("""
                UPDATE products
                SET 
                    available_stock = available_stock - $1,
                    reserved_stock = reserved_stock + $1
                WHERE sku = $2 
                  AND available_stock >= $1  -- KEY: check before update
                RETURNING id
            """, quantity, sku)
            
            if not result:
                return False  # Insufficient stock
            
            # Record the reservation with expiry
            await conn.execute("""
                INSERT INTO reservations 
                    (id, sku, quantity, expires_at)
                VALUES 
                    ($1, $2, $3, NOW() + INTERVAL '1 second' * $4)
            """, reservation_id, sku, quantity, ttl_seconds)
            
            return True
    
    async def confirm_reservation(self, reservation_id: str) -> bool:
        """Confirm reservation - move from reserved to sold"""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Get reservation
                res = await conn.fetchrow("""
                    SELECT sku, quantity FROM reservations 
                    WHERE id = $1 AND expires_at > NOW()
                """, reservation_id)
                
                if not res:
                    return False  # Expired or not found
                
                # Move from reserved to sold
                await conn.execute("""
                    UPDATE products
                    SET reserved_stock = reserved_stock - $1
                    WHERE sku = $2
                """, res["quantity"], res["sku"])
                
                # Delete reservation
                await conn.execute(
                    "DELETE FROM reservations WHERE id = $1",
                    reservation_id
                )
                
                return True
    
    async def release_reservation(self, reservation_id: str):
        """Release reservation - return to available"""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                res = await conn.fetchrow("""
                    SELECT sku, quantity FROM reservations 
                    WHERE id = $1
                """, reservation_id)
                
                if res:
                    # Return to available
                    await conn.execute("""
                        UPDATE products
                        SET 
                            available_stock = available_stock + $1,
                            reserved_stock = reserved_stock - $1
                        WHERE sku = $2
                    """, res["quantity"], res["sku"])
                    
                    await conn.execute(
                        "DELETE FROM reservations WHERE id = $1",
                        reservation_id
                    )

# ─────────────────────────────────────────────────────────────
# BACKGROUND JOB: Release expired reservations
# ─────────────────────────────────────────────────────────────
async def release_expired_reservations(repo: InventoryRepository):
    """Run periodically to clean up expired reservations"""
    async with repo.pool.acquire() as conn:
        expired = await conn.fetch("""
            DELETE FROM reservations 
            WHERE expires_at < NOW()
            RETURNING id, sku, quantity
        """)
        
        for r in expired:
            await conn.execute("""
                UPDATE products
                SET 
                    available_stock = available_stock + $1,
                    reserved_stock = reserved_stock - $1
                WHERE sku = $2
            """, r["quantity"], r["sku"])

# ─────────────────────────────────────────────────────────────
# TEST: 100 users buying the last iPhone
# ─────────────────────────────────────────────────────────────
async def test_race_condition():
    repo = InventoryRepository(pool)
    
    # Set stock to 1
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE products SET available_stock = 1 WHERE sku = 'iPhone-15'
        """)
    
    # 100 concurrent purchase attempts
    async def try_purchase(user_id):
        success = await repo.reserve_item(
            sku="iPhone-15",
            quantity=1,
            reservation_id=f"res-{user_id}",
        )
        return success
    
    results = await asyncio.gather(*[try_purchase(i) for i in range(100)])
    
    successes = sum(results)
    print(f"Successful purchases: {successes}")  # Will be 1 - only one wins!
```

---

## 5. 📱 Social Feed - Hybrid Push/Pull

### Implementation

```python
"""
Twitter/Instagram-style feed with hybrid push/pull model.
"""
import redis.asyncio as redis
import json
from typing import List

CELEBRITY_THRESHOLD = 10000  # Users with > 10k followers

class FeedService:
    def __init__(self, redis_client, graph_service, post_service):
        self.redis = redis_client
        self.graph = graph_service
        self.posts = post_service
    
    # ─────────────────────────────────────────────────────────
    # WRITE PATH: User posts something
    # ─────────────────────────────────────────────────────────
    async def on_post_created(self, post: dict):
        """
        When a user posts:
        - Regular user → PUSH to all followers' feeds (fan-out write)
        - Celebrity → don't push (followers pull at read time)
        """
        user_id = post["user_id"]
        post_id = post["id"]
        
        follower_count = await self.graph.get_follower_count(user_id)
        
        if follower_count < CELEBRITY_THRESHOLD:
            # PUSH MODEL: write to all followers' feeds
            followers = await self.graph.get_followers(user_id)
            
            # Use Redis pipeline for batch
            async with self.redis.pipeline() as pipe:
                for follower_id in followers:
                    pipe.lpush(f"feed:{follower_id}", post_id)
                    pipe.ltrim(f"feed:{follower_id}", 0, 1000)  # Keep top 1000
                await pipe.execute()
            
            print(f"[FEED] Pushed post {post_id} to {len(followers)} followers")
        
        else:
            # PULL MODEL: don't push. Track this celebrity's recent posts.
            await self.redis.lpush(f"celebrity_posts:{user_id}", post_id)
            await self.redis.ltrim(f"celebrity_posts:{user_id}", 0, 100)
            print(f"[FEED] Celebrity post {post_id} stored for pull")
    
    # ─────────────────────────────────────────────────────────
    # READ PATH: User opens app
    # ─────────────────────────────────────────────────────────
    async def get_feed(self, user_id: int, limit: int = 50) -> List[dict]:
        """
        Get user's feed:
        1. Get pre-computed feed (from push)
        2. Add celebrity posts (pull at read-time)
        3. Merge and rank
        """
        # Step 1: Get pushed posts
        pushed_post_ids = await self.redis.lrange(f"feed:{user_id}", 0, limit)
        pushed_post_ids = [pid.decode() for pid in pushed_post_ids]
        
        # Step 2: Get celebrities user follows
        celebrities = await self.graph.get_celebrity_following(user_id)
        
        # Step 3: Get recent posts from each celebrity
        celebrity_post_ids = []
        for celeb_id in celebrities:
            recent = await self.redis.lrange(f"celebrity_posts:{celeb_id}", 0, 5)
            celebrity_post_ids.extend([pid.decode() for pid in recent])
        
        # Step 4: Fetch full post data (batch)
        all_post_ids = list(set(pushed_post_ids + celebrity_post_ids))
        posts = await self.posts.batch_get(all_post_ids)
        
        # Step 5: Rank with ML (or chronological for simplicity)
        ranked_posts = sorted(posts, key=lambda p: p["created_at"], reverse=True)
        
        return ranked_posts[:limit]
```

---

## 6. 📦 Outbox Pattern (Reliable Events)

### Implementation

```python
"""
Outbox pattern: Atomic DB writes + reliable event publishing.

Problem: How to ensure events are published when DB writes succeed?
   - If you commit DB then publish: crash between → lost event
   - If you publish then commit DB: failure → ghost event
   
Solution: Write event to outbox table in SAME transaction.
         Separate publisher polls outbox.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import asyncio
import json
from aiokafka import AIOKafkaProducer

class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    
    id = Column(Integer, primary_key=True)
    aggregate_type = Column(String, nullable=False)
    aggregate_id = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    published_at = Column(DateTime, nullable=True)

# ─────────────────────────────────────────────────────────────
# WRITE: Atomic DB + Outbox
# ─────────────────────────────────────────────────────────────
async def create_order_with_event(session: AsyncSession, user_id, items):
    """Create order AND outbox event in same transaction"""
    
    async with session.begin():
        # 1. Create order
        order = Order(
            user_id=user_id,
            items=items,
            status="CREATED",
        )
        session.add(order)
        await session.flush()  # Get the ID
        
        # 2. Create outbox event in SAME transaction
        event = OutboxEvent(
            aggregate_type="order",
            aggregate_id=str(order.id),
            event_type="order.created",
            payload={
                "order_id": order.id,
                "user_id": user_id,
                "items": items,
            }
        )
        session.add(event)
        
        # Both commit together
        # If anything fails: BOTH roll back
    
    return order

# ─────────────────────────────────────────────────────────────
# PUBLISHER: Reads outbox, sends to Kafka
# ─────────────────────────────────────────────────────────────
class OutboxPublisher:
    """
    Background process that:
    1. Polls outbox for unpublished events
    2. Sends to Kafka
    3. Marks as published
    """
    
    def __init__(self, session_factory, kafka_producer):
        self.session_factory = session_factory
        self.producer = kafka_producer
    
    async def run(self):
        """Run forever, polling outbox"""
        while True:
            try:
                published = await self._publish_batch()
                if published == 0:
                    await asyncio.sleep(1)  # No events, sleep
            except Exception as e:
                logger.error(f"Outbox publisher error: {e}")
                await asyncio.sleep(5)
    
    async def _publish_batch(self) -> int:
        """Publish up to 100 unpublished events"""
        async with self.session_factory() as session:
            # Lock rows so concurrent publishers don't double-publish
            result = await session.execute(
                select(OutboxEvent)
                .where(OutboxEvent.published_at == None)
                .order_by(OutboxEvent.id)
                .limit(100)
                .with_for_update(skip_locked=True)  # KEY: skip locked rows
            )
            events = result.scalars().all()
            
            if not events:
                return 0
            
            # Send all to Kafka
            for event in events:
                topic = event.event_type  # e.g., "order.created"
                await self.producer.send_and_wait(
                    topic,
                    json.dumps(event.payload).encode(),
                    key=event.aggregate_id.encode(),
                )
                event.published_at = datetime.utcnow()
            
            await session.commit()
            
            return len(events)
```

---

## 7. 📊 CQRS Pattern

### Implementation

```python
"""
CQRS: Separate read and write models.

Write side: Normalized DB (PostgreSQL)
Read side: Denormalized (Elasticsearch, Redis)

Synced via events.
"""

# ─────────────────────────────────────────────────────────────
# WRITE MODEL
# ─────────────────────────────────────────────────────────────
class OrderWriteModel:
    """Write model: normalized, optimized for ACID"""
    
    async def create_order(self, user_id, items):
        async with self.session() as session:
            # Insert order
            order = await session.execute("""
                INSERT INTO orders (user_id, status, total)
                VALUES ($1, 'PENDING', $2)
                RETURNING id
            """, user_id, sum(i.price for i in items))
            
            # Insert order items
            for item in items:
                await session.execute("""
                    INSERT INTO order_items (order_id, product_id, qty, price)
                    VALUES ($1, $2, $3, $4)
                """, order.id, item.product_id, item.quantity, item.price)
            
            # Publish event for read model update
            await event_bus.publish("order.created", {
                "order_id": order.id,
                "user_id": user_id,
                "items": [{"product_id": i.product_id, "name": i.name} for i in items],
            })

# ─────────────────────────────────────────────────────────────
# READ MODEL
# ─────────────────────────────────────────────────────────────
class OrderReadModel:
    """Read model: denormalized, optimized for queries"""
    
    def __init__(self, elasticsearch_client):
        self.es = elasticsearch_client
    
    async def get_user_orders(self, user_id):
        """Get all orders for a user - one query, denormalized data"""
        result = await self.es.search(
            index="orders_read_model",
            body={
                "query": {"match": {"user_id": user_id}},
                "sort": [{"created_at": "desc"}],
            }
        )
        return [hit["_source"] for hit in result["hits"]["hits"]]
    
    async def get_orders_by_product(self, product_id):
        """Get all orders containing a product"""
        return await self.es.search(
            index="orders_read_model",
            body={
                "query": {"match": {"items.product_id": product_id}}
            }
        )

# ─────────────────────────────────────────────────────────────
# PROJECTION: Build read model from events
# ─────────────────────────────────────────────────────────────
async def on_order_created(payload, read_model: OrderReadModel):
    """Project event into read model"""
    await read_model.es.index(
        index="orders_read_model",
        id=payload["order_id"],
        body={
            "order_id": payload["order_id"],
            "user_id": payload["user_id"],
            "items": payload["items"],  # Denormalized!
            "created_at": datetime.utcnow().isoformat(),
        }
    )

event_bus.subscribe("order.created", on_order_created)
```

---

## 8. 🎯 BFF (Backend for Frontend) Pattern

### Mobile vs Web BFFs

```python
"""
Different clients need different data shapes.
BFFs tailor responses for each client.
"""
from fastapi import FastAPI
import httpx
import asyncio

# ─────────────────────────────────────────────────────────────
# WEB BFF (Rich UI, lots of data)
# ─────────────────────────────────────────────────────────────
web_app = FastAPI(title="Web BFF")

@web_app.get("/dashboard")
async def web_dashboard(user_id: int):
    """Web sees comprehensive data"""
    async with httpx.AsyncClient() as client:
        # Parallel fetches
        user_task = client.get(f"http://user-svc/users/{user_id}")
        orders_task = client.get(f"http://order-svc/users/{user_id}/orders?limit=20")
        recs_task = client.get(f"http://rec-svc/recommendations/{user_id}?count=10")
        notifs_task = client.get(f"http://notif-svc/users/{user_id}")
        
        user, orders, recs, notifs = await asyncio.gather(
            user_task, orders_task, recs_task, notifs_task
        )
        
        return {
            "user": user.json(),
            "recent_orders": orders.json(),
            "recommendations": recs.json(),
            "notifications": notifs.json(),
            "analytics": await get_user_analytics(user_id),  # extra for web
        }

# ─────────────────────────────────────────────────────────────
# MOBILE BFF (Minimal data, save bandwidth)
# ─────────────────────────────────────────────────────────────
mobile_app = FastAPI(title="Mobile BFF")

@mobile_app.get("/dashboard")
async def mobile_dashboard(user_id: int):
    """Mobile sees minimal data, optimized for bandwidth"""
    async with httpx.AsyncClient() as client:
        user_task = client.get(f"http://user-svc/users/{user_id}")
        orders_task = client.get(f"http://order-svc/users/{user_id}/orders?limit=3")
        
        user, orders = await asyncio.gather(user_task, orders_task)
        user_data = user.json()
        
        # Return minimal data
        return {
            "name": user_data["name"],
            "avatar": user_data["avatar_url"],
            "unread_notifications": user_data["notif_count"],
            "recent_orders": [
                # Only essential fields for mobile
                {"id": o["id"], "status": o["status"], "total": o["total"]}
                for o in orders.json()
            ],
        }
```

---

## 9. 🔬 Putting It All Together: Complete System

### End-to-End Order Flow

```python
"""
Complete production-grade order flow using multiple patterns:
- Saga for distributed transaction
- Outbox for reliable events
- Idempotency for safe retries
- Optimistic locking for inventory
- CQRS for read optimization
"""
from fastapi import FastAPI, Header
import uuid

app = FastAPI()

@app.post("/orders")
async def create_order(
    request: dict,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    return await with_idempotency(
        idempotency_key=idempotency_key,
        handler=lambda: _create_order_impl(request),
        request_body=request,
    )

async def _create_order_impl(request):
    order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
    
    # Use Saga for distributed transaction
    saga = FinancialSaga(
        saga_id=order_id,
        name="create_order",
        audit_logger=audit_logger,
    )
    
    saga.add_step(
        name="reserve_inventory",
        action=lambda: inventory_service.reserve(
            sku=request["sku"],
            quantity=request["quantity"],
            reservation_id=order_id,
        ),
        compensation=lambda r: inventory_service.release(order_id)
    )
    
    saga.add_step(
        name="process_payment",
        action=lambda: payment_service.charge(
            user_id=request["user_id"],
            amount=request["amount"],
            order_id=order_id,  # idempotency key
        ),
        compensation=lambda r: payment_service.refund(r["transaction_id"])
    )
    
    saga.add_step(
        name="confirm_inventory",
        action=lambda: inventory_service.confirm_reservation(order_id),
        compensation=lambda r: inventory_service.release(order_id)
    )
    
    saga.add_step(
        name="create_order_record",
        action=lambda: order_repository.create_with_outbox({
            "id": order_id,
            "user_id": request["user_id"],
            "items": request["items"],
            "total": request["amount"],
            "status": "CONFIRMED",
        }),
        # No compensation - last step
    )
    
    result = await saga.execute()
    
    if result["status"] == "FAILED":
        raise HTTPException(400, f"Order failed: {result['error']}")
    
    return {
        "order_id": order_id,
        "status": "CONFIRMED",
    }
```

---

## 10. Key Learnings Summary

```
✅ Multi-tenancy: schema-per-tenant for SaaS isolation
✅ Idempotency: prevent double-charges in public APIs
✅ Versioning: date-based versions for backward compat
✅ Saga: distributed transactions with compensations
✅ Optimistic locking: solve race conditions
✅ Hybrid push/pull: scale social feeds
✅ Outbox pattern: reliable event publishing
✅ CQRS: separate reads from writes
✅ BFF: tailor responses per client

🎯 The real-world systems use COMBINATIONS of these patterns.
   Master them individually, then mix and match.
```

---

## 🎬 Section Complete!

You've completed **Section 3: Distributed Systems & Service Architectures**!

### Files Created

```
Section_03_Distributed_Systems/
├── 01_Service_Oriented_Architecture.md       (theory)
├── 01_Practical_Hands_On.md                  (practical)
├── 02_Microservices_Architecture.md           (theory)
├── 02_Practical_Hands_On.md                  (practical)
├── 03_Modular_Monoliths_Migration.md         (theory)
├── 03_Practical_Hands_On.md                  (practical)
├── 04_Micro_Frontends_UI_Composition.md      (theory)
├── 04_Practical_Hands_On.md                  (practical)
├── 05_Real_World_Use_Cases.md                (theory)
└── 05_Practical_Hands_On.md                  (practical)  ← you are here
```

### What You Can Now Build

```
✓ SOA system with ESB
✓ Microservices with FastAPI + Kafka + tracing
✓ Modular monolith with enforced boundaries
✓ Micro-frontends with Module Federation
✓ Real-world production patterns:
   - Multi-tenant SaaS
   - Public API platforms
   - Fintech with Sagas
   - E-commerce with race-condition handling
   - Social feeds with hybrid models
```

---

## 📚 Try These Projects

1. **Build a SaaS starter** with multi-tenancy + billing
2. **Create a payment platform** with full Saga + compensation
3. **Implement Twitter clone** with feed generation
4. **Build an e-commerce checkout** with idempotency
5. **Set up complete observability** stack (Jaeger + Prometheus + Grafana)

---

## 🚀 Next Steps

Continue your learning with:
- **Section 4**: Integration Patterns (APIs, messaging, events)
- **Section 5**: Data Management & Persistence
- **Section 6**: Security Patterns
- **Section 7**: Performance & Scalability

Good luck on your software architecture journey! 🎓
