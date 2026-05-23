"""
Microservices Advanced Patterns — Practical Demo
=================================================
Patterns covered:
  - Outbox Pattern (dual-write problem solution)
  - Idempotency (safe retries with deduplication)
  - Saga Orchestration (distributed transactions with compensation)
  - Strangler Fig (monolith migration strategy)

Run:
  python 04_outbox_idempotency.py outbox
  python 04_outbox_idempotency.py idempotency
  python 04_outbox_idempotency.py saga
  python 04_outbox_idempotency.py strangler
  python 04_outbox_idempotency.py all

Requirements:
  pip install sqlalchemy aiosqlite

No external services needed — SQLite in-memory + asyncio
"""

import asyncio
import json
import random
import sys
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Column, DateTime, Integer, JSON, Numeric, String, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase


# ──────────────────────────────────────────────────────────────
# DATABASE MODELS
# ──────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


class Order(Base):
    __tablename__ = "orders"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    user_id    = Column(Integer, nullable=False)
    product_id = Column(Integer, nullable=False)
    amount     = Column(Numeric(10, 2))
    status     = Column(String, default="placed")
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"Order(id={self.id}, user={self.user_id}, product={self.product_id}, amount={self.amount})"


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    event_type   = Column(String, nullable=False)       # e.g. "order.placed"
    aggregate_id = Column(String, nullable=False)       # e.g. "order:123"
    payload      = Column(JSON, nullable=False)
    status       = Column(String, default="pending")    # pending / published / failed
    created_at   = Column(DateTime, default=datetime.utcnow)
    published_at = Column(DateTime, nullable=True)
    retry_count  = Column(Integer, default=0)

    def __repr__(self):
        return f"OutboxEvent(id={self.id}, type={self.event_type}, status={self.status})"


# ──────────────────────────────────────────────────────────────
# OUTBOX PATTERN DEMO
# ──────────────────────────────────────────────────────────────

# In-memory SQLite engine — koi real DB nahi chahiye
_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
_session_factory = async_sessionmaker(_engine, expire_on_commit=False)


async def _setup_db():
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def create_order_with_outbox(
    user_id: int,
    product_id: int,
    amount: float,
) -> Order:
    """
    Order + OutboxEvent — SAME DB TRANSACTION.

    Either both save, or neither saves.
    Dual-write problem solved!
    """
    async with _session_factory() as session:
        async with session.begin():
            # Step 1: Order create karo
            order = Order(
                user_id=user_id,
                product_id=product_id,
                amount=amount,
            )
            session.add(order)
            await session.flush()   # Auto-generated ID chahiye

            # Step 2: Outbox event create karo (SAME transaction)
            event = OutboxEvent(
                event_type="order.placed",
                aggregate_id=f"order:{order.id}",
                payload={
                    "order_id":   order.id,
                    "user_id":    order.user_id,
                    "product_id": order.product_id,
                    "amount":     str(order.amount),
                    "timestamp":  datetime.utcnow().isoformat(),
                },
            )
            session.add(event)
            # Context manager exit pe commit — dono ya koi nahi

    return order


async def simulate_outbox_relay(
    fail_event_ids: list[int] | None = None,
    batch_size: int = 10,
) -> dict[str, int]:
    """
    Message Relay simulate karo.

    Real mein: outbox poll → RabbitMQ publish → mark published
    Demo mein:  outbox poll → print (simulate publish)  → mark published

    fail_event_ids: in event IDs ke liye publish fail simulate karo
    """
    fail_event_ids = fail_event_ids or []
    stats = {"published": 0, "failed": 0, "skipped": 0}

    async with _session_factory() as session:
        # Pending events fetch karo
        # with_for_update(skip_locked=True) → multiple relay instances safe
        # SQLite FOR UPDATE support nahi karta, toh simple select use karte hain demo mein
        result = await session.execute(
            select(OutboxEvent)
            .where(
                OutboxEvent.status == "pending",
                OutboxEvent.retry_count < 5,
            )
            .order_by(OutboxEvent.created_at)
            .limit(batch_size)
        )
        events = result.scalars().all()

        if not events:
            print("  [Relay] No pending events found.")
            return stats

        print(f"  [Relay] Found {len(events)} pending event(s) to publish...")

        for event in events:
            if event.id in fail_event_ids:
                # Publish fail simulate karo
                event.retry_count += 1
                if event.retry_count >= 5:
                    event.status = "failed"
                    print(f"  [Relay] PERMANENTLY FAILED (retry_count=5): {event.event_type} [{event.aggregate_id}]")
                    stats["failed"] += 1
                else:
                    print(
                        f"  [Relay] PUBLISH FAILED (retry {event.retry_count}/5): "
                        f"{event.event_type} [{event.aggregate_id}]"
                    )
                    stats["skipped"] += 1
            else:
                # Publish success simulate karo
                print(
                    f"  [Relay] --> RabbitMQ: routing_key={event.event_type} "
                    f"payload={json.dumps(event.payload)[:60]}..."
                )
                event.status = "published"
                event.published_at = datetime.utcnow()
                stats["published"] += 1

        await session.commit()

    return stats


async def check_outbox_state() -> dict[str, int]:
    """Current outbox table ki stats return karo."""
    async with _session_factory() as session:
        counts: dict[str, int] = {}
        for status in ("pending", "published", "failed"):
            result = await session.execute(
                select(OutboxEvent).where(OutboxEvent.status == status)
            )
            counts[status] = len(result.scalars().all())
    return counts


async def demo_outbox_pattern():
    print("=" * 60)
    print("DEMO 1: OUTBOX PATTERN")
    print("=" * 60)
    print()
    print("Problem: DB save + RabbitMQ publish — 2 separate operations")
    print("         Koi bhi fail ho sakta hai independently!")
    print("Solution: Dono ko same DB transaction mein karo")
    print()

    await _setup_db()

    # ── Step 1: 3 orders create karo ───────────────────────────
    print("[ Creating 3 orders (each with outbox event in same transaction) ]")
    orders = []
    for i in range(1, 4):
        order = await create_order_with_outbox(
            user_id=100 + i,
            product_id=i,
            amount=i * 1000.0,
        )
        orders.append(order)
        print(f"  Order {order.id} created — user={order.user_id}, amount={order.amount}")

    # ── Step 2: Outbox state check ──────────────────────────────
    print()
    state = await check_outbox_state()
    print(f"[ Outbox state before relay: {state} ]")
    assert state["pending"] == 3, "Expected 3 pending events"

    # ── Step 3: Relay run karo (all success) ───────────────────
    print()
    print("[ Running Outbox Relay — all events publish karein ]")
    stats = await simulate_outbox_relay()
    print(f"  Relay stats: {stats}")

    state = await check_outbox_state()
    print(f"[ Outbox state after relay: {state} ]")
    assert state["published"] == 3
    assert state["pending"] == 0

    # ── Step 4: Failure + retry simulation ────────────────────
    print()
    print("[ Simulating failure scenario — 2 more orders, 1 will fail ]")
    order4 = await create_order_with_outbox(user_id=200, product_id=10, amount=9999.0)
    order5 = await create_order_with_outbox(user_id=201, product_id=11, amount=500.0)
    print(f"  Order {order4.id} and Order {order5.id} created")

    # Outbox IDs fetch karo
    async with _session_factory() as session:
        result = await session.execute(
            select(OutboxEvent).where(OutboxEvent.status == "pending")
        )
        pending_events = result.scalars().all()
        fail_id = pending_events[0].id  # Pehle event ko fail karein
        print(f"  Will simulate publish failure for outbox event id={fail_id}")

    print()
    print("[ Relay run #1 — one event fails ]")
    await simulate_outbox_relay(fail_event_ids=[fail_id])
    state = await check_outbox_state()
    print(f"  Outbox state: {state}")

    # Retry — 4 more times tak fail karo (max retry = 5)
    print()
    print("[ Relay run #2 to #5 — retrying failed event (will permanently fail at 5) ]")
    for attempt in range(2, 6):
        print(f"  -- Relay run #{attempt} --")
        await simulate_outbox_relay(fail_event_ids=[fail_id])

    state = await check_outbox_state()
    print(f"[ Final outbox state: {state} ]")
    print()
    print("  Notice: Permanently failed event → manual intervention / DLQ needed")
    print()
    print("OUTBOX PATTERN DEMO COMPLETE")
    print()


# ──────────────────────────────────────────────────────────────
# IDEMPOTENCY DEMO
# ──────────────────────────────────────────────────────────────

# In-memory dict as Redis substitute
_idempotency_store: dict[str, dict] = {}


async def create_order_idempotent(
    idempotency_key: str,
    order_data: dict,
) -> dict:
    """
    Idempotency key se duplicate order prevent karo.

    Same key pe dobara call karo → same response milega.
    Real application mein Redis use hoga (TTL ke saath).
    """
    if idempotency_key in _idempotency_store:
        print(
            f"  IDEMPOTENT HIT: Returning cached response "
            f"for key={idempotency_key[:12]}..."
        )
        return _idempotency_store[idempotency_key]

    # First time processing
    print(f"  FIRST TIME: Processing order for key={idempotency_key[:12]}...")
    await asyncio.sleep(0.05)   # Simulate async processing

    response = {
        "order_id": random.randint(10000, 99999),
        "status":   "created",
        **order_data,
        "created_at": datetime.utcnow().isoformat(),
    }

    # Cache the response
    _idempotency_store[idempotency_key] = response
    return response


async def demo_idempotency():
    print("=" * 60)
    print("DEMO 2: IDEMPOTENCY")
    print("=" * 60)
    print()
    print("Problem: Network timeout → client retries → duplicate order!")
    print("Solution: Idempotency key (UUID) — same key, same response")
    print()

    # ── Test 1: Same key 3 times → same order_id ──────────────
    print("[ Test 1: Same idempotency key called 3 times ]")
    key_1 = str(uuid.uuid4())
    print(f"  Idempotency key: {key_1}")
    results = []
    for i in range(1, 4):
        result = await create_order_idempotent(key_1, {"amount": 5000, "product_id": 42})
        results.append(result["order_id"])
        print(f"  Call {i}: order_id={result['order_id']}")

    all_same = len(set(results)) == 1
    print(f"  All calls returned same order_id: {all_same}")
    assert all_same, "Idempotency broken — different order_ids!"

    # ── Test 2: Different keys → different orders ──────────────
    print()
    print("[ Test 2: Different idempotency keys → different orders ]")
    key_2 = str(uuid.uuid4())
    key_3 = str(uuid.uuid4())

    result_a = await create_order_idempotent(key_2, {"amount": 1500})
    result_b = await create_order_idempotent(key_3, {"amount": 2500})

    print(f"  Key 2 order_id: {result_a['order_id']}")
    print(f"  Key 3 order_id: {result_b['order_id']}")
    assert result_a["order_id"] != result_b["order_id"], "Different keys gave same order!"
    print("  Confirmed: Different keys → different orders")

    # ── Test 3: Simulate concurrent duplicate requests ─────────
    print()
    print("[ Test 3: Concurrent requests with same key (race condition simulation) ]")
    key_4 = str(uuid.uuid4())

    async def _race_request(call_num: int):
        result = await create_order_idempotent(key_4, {"amount": 9000})
        return call_num, result["order_id"]

    race_results = await asyncio.gather(
        _race_request(1), _race_request(2), _race_request(3)
    )

    order_ids = [r[1] for r in race_results]
    print(f"  Concurrent results: {order_ids}")
    # Note: dict is not thread-safe, but asyncio single-threaded hai
    # In production: Redis SET NX (atomic) use karo
    print("  (In production: Redis SET NX ensures atomic check-and-set)")

    print()
    print("IDEMPOTENCY DEMO COMPLETE")
    print()


# ──────────────────────────────────────────────────────────────
# SAGA ORCHESTRATION DEMO
# ──────────────────────────────────────────────────────────────

class InventoryService:
    """Simulated inventory service."""

    def __init__(self, fail_at_call: int | None = None):
        self._call_count = 0
        self._fail_at = fail_at_call
        self._reservations: dict[str, dict] = {}

    async def reserve(self, product_id: int, quantity: int, saga_id: str) -> dict:
        self._call_count += 1
        await asyncio.sleep(0.05)

        if self._fail_at is not None and self._call_count == self._fail_at:
            raise RuntimeError(f"Inventory service DOWN (saga_id={saga_id[:8]}...)")

        reservation_id = f"rsv_{uuid.uuid4().hex[:8]}"
        self._reservations[reservation_id] = {
            "product_id": product_id,
            "quantity":   quantity,
            "saga_id":    saga_id,
        }
        return {"id": reservation_id, "product_id": product_id, "quantity": quantity}

    async def release(self, reservation_id: str, saga_id: str) -> dict:
        await asyncio.sleep(0.02)
        self._reservations.pop(reservation_id, None)
        return {"status": "released", "reservation_id": reservation_id}


class PaymentService:
    """Simulated payment service."""

    def __init__(self, fail_at_call: int | None = None):
        self._call_count = 0
        self._fail_at = fail_at_call
        self._charges: dict[str, dict] = {}

    async def charge(self, user_id: int, amount: float, saga_id: str) -> dict:
        self._call_count += 1
        await asyncio.sleep(0.05)

        if self._fail_at is not None and self._call_count == self._fail_at:
            raise RuntimeError(f"Payment service DECLINED (saga_id={saga_id[:8]}...)")

        payment_id = f"pay_{uuid.uuid4().hex[:8]}"
        self._charges[payment_id] = {
            "user_id": user_id,
            "amount":  amount,
            "saga_id": saga_id,
        }
        return {"id": payment_id, "user_id": user_id, "amount": amount}

    async def refund(self, payment_id: str, saga_id: str) -> dict:
        await asyncio.sleep(0.02)
        charge = self._charges.pop(payment_id, {})
        return {"status": "refunded", "payment_id": payment_id, "amount": charge.get("amount")}


class OrderRepository:
    """Simulated order repository."""

    def __init__(self, fail_at_call: int | None = None):
        self._call_count = 0
        self._fail_at = fail_at_call

    async def confirm(
        self,
        order_data: dict,
        reservation_id: str,
        payment_id: str,
    ) -> dict:
        self._call_count += 1
        await asyncio.sleep(0.05)

        if self._fail_at is not None and self._call_count == self._fail_at:
            raise RuntimeError("Order DB write FAILED")

        return {
            "id":             random.randint(10000, 99999),
            "reservation_id": reservation_id,
            "payment_id":     payment_id,
            **order_data,
        }


class OrderSagaOrchestrator:
    """
    Saga Orchestrator — Place Order

    Steps:
      1. Reserve inventory
      2. Process payment
      3. Confirm order in DB

    Compensation (on failure, reverse order):
      2. Refund payment (if charged)
      1. Release inventory (if reserved)
    """

    def __init__(
        self,
        inventory: InventoryService,
        payment: PaymentService,
        order_repo: OrderRepository,
    ):
        self.inventory  = inventory
        self.payment    = payment
        self.order_repo = order_repo

    async def execute(self, order_data: dict) -> dict:
        saga_id        = str(uuid.uuid4())
        completed_steps: list[tuple[str, Any]] = []

        print(f"  Starting saga [{saga_id[:8]}...] for user={order_data['user_id']}")

        try:
            # ── Step 1: Reserve inventory ──────────────────────
            print(f"    Step 1: Reserving inventory (product={order_data['product_id']})...")
            reservation = await self.inventory.reserve(
                product_id=order_data["product_id"],
                quantity=order_data.get("quantity", 1),
                saga_id=saga_id,
            )
            completed_steps.append(("inventory_reserved", reservation))
            print(f"    Step 1 SUCCESS: reservation_id={reservation['id']}")

            # ── Step 2: Process payment ────────────────────────
            print(f"    Step 2: Processing payment (amount={order_data['amount']})...")
            payment = await self.payment.charge(
                user_id=order_data["user_id"],
                amount=order_data["amount"],
                saga_id=saga_id,
            )
            completed_steps.append(("payment_processed", payment))
            print(f"    Step 2 SUCCESS: payment_id={payment['id']}")

            # ── Step 3: Confirm order ──────────────────────────
            print("    Step 3: Confirming order in DB...")
            order = await self.order_repo.confirm(
                order_data=order_data,
                reservation_id=reservation["id"],
                payment_id=payment["id"],
            )
            print(f"    Step 3 SUCCESS: order_id={order['id']}")

            return {"status": "success", "order_id": order["id"], "saga_id": saga_id}

        except Exception as exc:
            print(f"    SAGA FAILED at step {len(completed_steps) + 1}: {exc}")
            print("    Starting compensation (rollback)...")
            await self._compensate(completed_steps, saga_id)
            return {"status": "failed", "reason": str(exc), "saga_id": saga_id}

    async def _compensate(
        self,
        completed_steps: list[tuple[str, Any]],
        saga_id: str,
    ) -> None:
        """Completed steps ko REVERSE order mein undo karo."""
        for step_name, step_data in reversed(completed_steps):
            try:
                if step_name == "payment_processed":
                    refund = await self.payment.refund(step_data["id"], saga_id=saga_id)
                    print(
                        f"    COMPENSATED payment_processed — "
                        f"refunded {refund['amount']} (payment_id={step_data['id']})"
                    )
                elif step_name == "inventory_reserved":
                    await self.inventory.release(step_data["id"], saga_id=saga_id)
                    print(
                        f"    COMPENSATED inventory_reserved — "
                        f"released reservation_id={step_data['id']}"
                    )
            except Exception as comp_exc:
                print(f"    COMPENSATION FAILED for {step_name}: {comp_exc}")
                print("    --> Send to Dead Letter Queue for manual intervention!")


async def demo_saga_orchestration():
    print("=" * 60)
    print("DEMO 3: SAGA ORCHESTRATION")
    print("=" * 60)
    print()
    print("Pattern: Central Orchestrator manages multi-step distributed transaction")
    print("         Steps: Reserve Inventory → Process Payment → Confirm Order")
    print("         Failure → Compensation in reverse order")
    print()

    order_data = {
        "user_id":    42,
        "product_id": 7,
        "quantity":   2,
        "amount":     2999.99,
    }

    # ── Scenario 1: Happy path ─────────────────────────────────
    print("[ Scenario 1: Happy Path — all steps succeed ]")
    saga = OrderSagaOrchestrator(
        inventory=InventoryService(),
        payment=PaymentService(),
        order_repo=OrderRepository(),
    )
    result = await saga.execute(order_data.copy())
    print(f"  Result: {result}")
    assert result["status"] == "success"
    print()

    # ── Scenario 2: Payment fails → inventory released ─────────
    print("[ Scenario 2: Payment fails at step 2 → inventory should be released ]")
    saga2 = OrderSagaOrchestrator(
        inventory=InventoryService(),
        payment=PaymentService(fail_at_call=1),   # First payment call fail
        order_repo=OrderRepository(),
    )
    result2 = await saga2.execute(order_data.copy())
    print(f"  Result: {result2}")
    assert result2["status"] == "failed"
    print()

    # ── Scenario 3: Order DB fails → payment refunded + inventory released
    print("[ Scenario 3: Order DB write fails at step 3 → full rollback ]")
    saga3 = OrderSagaOrchestrator(
        inventory=InventoryService(),
        payment=PaymentService(),
        order_repo=OrderRepository(fail_at_call=1),  # DB write fail
    )
    result3 = await saga3.execute(order_data.copy())
    print(f"  Result: {result3}")
    assert result3["status"] == "failed"
    print()

    # ── Scenario 4: Inventory fails first → no compensation needed
    print("[ Scenario 4: Inventory reserve fails at step 1 → nothing to compensate ]")
    saga4 = OrderSagaOrchestrator(
        inventory=InventoryService(fail_at_call=1),   # Inventory fail at step 1
        payment=PaymentService(),
        order_repo=OrderRepository(),
    )
    result4 = await saga4.execute(order_data.copy())
    print(f"  Result: {result4}")
    assert result4["status"] == "failed"
    print()

    print("SAGA ORCHESTRATION DEMO COMPLETE")
    print()


# ──────────────────────────────────────────────────────────────
# STRANGLER FIG DEMO
# ──────────────────────────────────────────────────────────────

def demo_strangler_fig():
    print("=" * 60)
    print("DEMO 4: STRANGLER FIG PATTERN")
    print("=" * 60)
    print()
    print("Pattern (Martin Fowler): Monolith ko safely replace karo")
    print("Strategy: Proxy layer add karo, gradually route traffic to new services")
    print()

    phases = [
        {
            "name": "Phase 1 — Proxy layer add karo (Monolith intact)",
            "description": (
                "Proxy/API Gateway ke through traffic route karo.\n"
                "Monolith untouched — zero risk, zero downtime."
            ),
            "nginx": """
# Phase 1 — All traffic still goes to monolith
upstream legacy_monolith { server monolith:8000; }

server {
    listen 80;

    location / {
        proxy_pass http://legacy_monolith;
    }
}
""",
        },
        {
            "name": "Phase 2 — User Service extract karo",
            "description": (
                "/api/users/* → New User Service (Python FastAPI)\n"
                "Everything else → Monolith (Ruby on Rails)\n"
                "Rollback = change one line in nginx config"
            ),
            "nginx": """
# Phase 2 — User service extracted
upstream user_service   { server user-service:8001; }
upstream legacy_monolith { server monolith:8000; }

server {
    listen 80;

    # Extracted: User Service (new microservice)
    location /api/users/ {
        proxy_pass http://user_service;
    }

    # Everything else → Monolith (unchanged)
    location / {
        proxy_pass http://legacy_monolith;
    }
}
""",
        },
        {
            "name": "Phase 3 — Products + Orders extracted (Monolith shrinking)",
            "description": (
                "/api/users/* → User Service\n"
                "/api/products/* → Product Service\n"
                "/api/orders/* → Order Service\n"
                "Monolith only has legacy features now"
            ),
            "nginx": """
# Phase 3 — 3 services extracted, monolith shrinking
upstream user_service    { server user-service:8001; }
upstream product_service { server product-service:8002; }
upstream order_service   { server order-service:8003; }
upstream legacy_monolith { server monolith:8000; }

server {
    listen 80;

    location /api/users/ {
        proxy_pass http://user_service;
    }

    location /api/products/ {
        proxy_pass http://product_service;
    }

    location /api/orders/ {
        proxy_pass http://order_service;
    }

    # Monolith handles remaining legacy routes
    location / {
        proxy_pass http://legacy_monolith;
    }
}
""",
        },
        {
            "name": "Phase 4 — Monolith fully strangled (migration complete!)",
            "description": (
                "Monolith retired!\n"
                "All traffic handled by microservices.\n"
                "The fig tree (monolith) has been strangled by the vines (microservices)."
            ),
            "nginx": """
# Phase 4 — Monolith is gone! All microservices.
upstream user_service     { server user-service:8001; }
upstream product_service  { server product-service:8002; }
upstream order_service    { server order-service:8003; }
upstream payment_service  { server payment-service:8004; }
upstream notification_svc { server notification-service:8005; }

server {
    listen 80;

    location /api/users/        { proxy_pass http://user_service; }
    location /api/products/     { proxy_pass http://product_service; }
    location /api/orders/       { proxy_pass http://order_service; }
    location /api/payments/     { proxy_pass http://payment_service; }
    location /api/notifications/ { proxy_pass http://notification_svc; }

    # Health check endpoint
    location /health {
        return 200 'OK';
        add_header Content-Type text/plain;
    }
}
""",
        },
    ]

    for i, phase in enumerate(phases, 1):
        print(f"{'─' * 50}")
        print(f"  {phase['name']}")
        print(f"{'─' * 50}")
        print(f"  {phase['description']}")
        print(f"  Nginx config:")
        for line in phase["nginx"].strip().splitlines():
            print(f"    {line}")
        print()

    # Rollback strategy
    print("─" * 50)
    print("  ROLLBACK STRATEGY")
    print("─" * 50)
    rollback_example = """
# Agar User Service fail ho raha hai — instant rollback:

# BEFORE (user service routing):
location /api/users/ {
    proxy_pass http://user_service;
}

# AFTER (rollback to monolith — seconds mein):
location /api/users/ {
    proxy_pass http://legacy_monolith;   # one line change!
}

# Reload nginx — zero downtime:
# nginx -s reload
"""
    for line in rollback_example.strip().splitlines():
        print(f"    {line}")

    print()
    print("  Canary deployment with Strangler Fig:")
    canary_example = """
# Gradual traffic shift (10% → 25% → 50% → 100%)
upstream user_service_canary {
    server user-service:8001  weight=10;   # 10% new service
    server monolith:8000      weight=90;   # 90% monolith
}

# Agar metrics okay hain → weight adjust karo gradually
# Error rate badhe → weight=0 on new service (instant rollback)
"""
    for line in canary_example.strip().splitlines():
        print(f"    {line}")

    print()
    print("STRANGLER FIG DEMO COMPLETE")
    print()


# ──────────────────────────────────────────────────────────────
# MAIN DISPATCHER
# ──────────────────────────────────────────────────────────────

DEMOS = {
    "outbox":    demo_outbox_pattern,
    "idempotency": demo_idempotency,
    "saga":      demo_saga_orchestration,
    "strangler": demo_strangler_fig,       # sync function, special case below
}


async def run_all():
    await demo_outbox_pattern()
    await demo_idempotency()
    await demo_saga_orchestration()
    demo_strangler_fig()   # sync
    print("=" * 60)
    print("ALL DEMOS COMPLETE")
    print("=" * 60)


def main():
    usage = (
        "Usage: python 04_outbox_idempotency.py [outbox|idempotency|saga|strangler|all]\n"
        "\n"
        "  outbox       — Outbox Pattern: dual-write problem + relay + retry\n"
        "  idempotency  — Idempotency Key: duplicate request deduplication\n"
        "  saga         — Saga Orchestration: distributed tx + compensation\n"
        "  strangler    — Strangler Fig: monolith → microservices migration\n"
        "  all          — Run all demos sequentially\n"
    )

    arg = sys.argv[1].lower() if len(sys.argv) > 1 else "all"

    if arg == "all":
        asyncio.run(run_all())
    elif arg == "strangler":
        demo_strangler_fig()   # sync function
    elif arg in DEMOS:
        asyncio.run(DEMOS[arg]())
    else:
        print(f"Unknown demo: '{arg}'\n")
        print(usage)
        sys.exit(1)


if __name__ == "__main__":
    main()
