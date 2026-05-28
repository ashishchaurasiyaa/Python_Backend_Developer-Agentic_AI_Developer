"""
============================================================
SAGA PATTERN — Working Implementation
============================================================
Saga = long-running distributed transaction broken into local steps,
each with a COMPENSATING action for rollback.

Two flavors:
  1. ORCHESTRATION  — central coordinator drives the saga
  2. CHOREOGRAPHY   — services emit/react to events, no coordinator

This file implements BOTH for an e-commerce order flow:
  Steps: ReserveInventory → ChargePayment → ScheduleShipping → SendEmail
  Compensations (reverse order):
    Refund ← Release Inventory ← Cancel Shipment

Run: python saga.py
"""
from __future__ import annotations
import time
import random
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
from typing import Callable, Any


# ============================================================
# COMMON: Services with simulated failure
# ============================================================
class ServiceError(Exception):
    pass


class InventoryService:
    def __init__(self, fail_rate=0.0):
        self.fail_rate = fail_rate
        self.reserved = {}

    def reserve(self, order_id, items) -> str:
        if random.random() < self.fail_rate:
            raise ServiceError("Inventory reservation failed")
        ticket = f"inv-{order_id}"
        self.reserved[ticket] = items
        print(f"  [Inventory] Reserved {items} → ticket={ticket}")
        return ticket

    def release(self, ticket):
        if ticket in self.reserved:
            del self.reserved[ticket]
            print(f"  [Inventory] Released {ticket}")


class PaymentService:
    def __init__(self, fail_rate=0.0):
        self.fail_rate = fail_rate
        self.charges = {}

    def charge(self, order_id, amount) -> str:
        if random.random() < self.fail_rate:
            raise ServiceError("Payment declined")
        txn = f"pay-{order_id}"
        self.charges[txn] = amount
        print(f"  [Payment] Charged ₹{amount} → txn={txn}")
        return txn

    def refund(self, txn):
        if txn in self.charges:
            amt = self.charges[txn]
            del self.charges[txn]
            print(f"  [Payment] Refunded ₹{amt} for {txn}")


class ShippingService:
    def __init__(self, fail_rate=0.0):
        self.fail_rate = fail_rate
        self.shipments = {}

    def schedule(self, order_id, address) -> str:
        if random.random() < self.fail_rate:
            raise ServiceError("Shipping unavailable")
        ship = f"ship-{order_id}"
        self.shipments[ship] = address
        print(f"  [Shipping] Scheduled to {address} → {ship}")
        return ship

    def cancel(self, ship):
        if ship in self.shipments:
            del self.shipments[ship]
            print(f"  [Shipping] Cancelled {ship}")


class EmailService:
    def send(self, to, subject):
        print(f"  [Email] To {to}: {subject}")


# ============================================================
# ORCHESTRATION SAGA — central coordinator
# ============================================================
class SagaStatus(Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    COMPENSATING = "COMPENSATING"
    FAILED = "FAILED"


@dataclass
class SagaStep:
    name: str
    action: Callable
    compensation: Callable
    result: Any = None
    completed: bool = False


@dataclass
class SagaLog:
    """Persistent log of saga state — recover from crashes."""
    saga_id: str
    status: SagaStatus
    completed_steps: list[str] = field(default_factory=list)
    failed_step: str | None = None
    payload: dict = field(default_factory=dict)


class SagaOrchestrator:
    """Centralized saga — knows the full flow."""

    def __init__(self, saga_id: str):
        self.saga_id = saga_id
        self.steps: list[SagaStep] = []
        self.log = SagaLog(saga_id=saga_id, status=SagaStatus.PENDING)

    def add_step(self, name, action, compensation):
        self.steps.append(SagaStep(name, action, compensation))
        return self

    def execute(self) -> SagaLog:
        self.log.status = SagaStatus.IN_PROGRESS
        executed: list[SagaStep] = []

        for step in self.steps:
            try:
                print(f"  → Step: {step.name}")
                step.result = step.action()
                step.completed = True
                executed.append(step)
                self.log.completed_steps.append(step.name)
                self.log.payload[step.name] = step.result
            except Exception as e:
                print(f"  ❌ Step '{step.name}' failed: {e}")
                self.log.failed_step = step.name
                self.log.status = SagaStatus.COMPENSATING
                self._compensate(executed)
                self.log.status = SagaStatus.FAILED
                return self.log

        self.log.status = SagaStatus.COMPLETED
        return self.log

    def _compensate(self, executed: list[SagaStep]):
        print("  ⚠️  Running compensations (reverse order):")
        for step in reversed(executed):
            try:
                step.compensation(step.result)
            except Exception as e:
                # Log but continue — compensations should be idempotent
                print(f"    [WARN] Compensation for {step.name} failed: {e}")


# ============================================================
# CHOREOGRAPHY SAGA — event-driven, no central coordinator
# ============================================================
class EventBus:
    def __init__(self):
        self._subs: dict[str, list[Callable]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: Callable):
        self._subs[event_type].append(handler)

    def publish(self, event_type: str, payload: dict):
        print(f"  📡 EVENT: {event_type} {payload}")
        for h in self._subs[event_type]:
            h(payload)


class ChoreographedInventory:
    def __init__(self, bus: EventBus, svc: InventoryService):
        self.bus = bus
        self.svc = svc
        bus.subscribe("OrderPlaced", self.on_order_placed)
        bus.subscribe("PaymentFailed", self.on_payment_failed)

    def on_order_placed(self, evt):
        try:
            ticket = self.svc.reserve(evt["order_id"], evt["items"])
            self.bus.publish("InventoryReserved", {**evt, "inv_ticket": ticket})
        except ServiceError as e:
            self.bus.publish("InventoryFailed", {**evt, "reason": str(e)})

    def on_payment_failed(self, evt):
        self.svc.release(evt["inv_ticket"])
        self.bus.publish("InventoryReleased", evt)


class ChoreographedPayment:
    def __init__(self, bus: EventBus, svc: PaymentService):
        self.bus = bus
        self.svc = svc
        bus.subscribe("InventoryReserved", self.on_inventory_reserved)
        bus.subscribe("ShippingFailed", self.on_shipping_failed)

    def on_inventory_reserved(self, evt):
        try:
            txn = self.svc.charge(evt["order_id"], evt["amount"])
            self.bus.publish("PaymentCharged", {**evt, "txn": txn})
        except ServiceError as e:
            self.bus.publish("PaymentFailed", {**evt, "reason": str(e)})

    def on_shipping_failed(self, evt):
        self.svc.refund(evt["txn"])
        self.bus.publish("PaymentRefunded", evt)


class ChoreographedShipping:
    def __init__(self, bus: EventBus, svc: ShippingService):
        self.bus = bus
        self.svc = svc
        bus.subscribe("PaymentCharged", self.on_payment_charged)

    def on_payment_charged(self, evt):
        try:
            ship = self.svc.schedule(evt["order_id"], evt["address"])
            self.bus.publish("OrderCompleted", {**evt, "shipment": ship})
        except ServiceError as e:
            self.bus.publish("ShippingFailed", {**evt, "reason": str(e)})


# ============================================================
# DEMO 1: Orchestration happy path
# ============================================================
def demo_orchestration_happy():
    print("=" * 60)
    print("DEMO 1: Orchestration — Happy Path")
    print("=" * 60)
    random.seed(0)
    inv = InventoryService()
    pay = PaymentService()
    ship = ShippingService()
    email = EmailService()

    order_id = f"ord-{uuid.uuid4().hex[:6]}"
    items = ["sku-1", "sku-2"]
    amount = 1500
    address = "Bengaluru"

    saga = SagaOrchestrator(order_id)
    saga.add_step(
        "ReserveInventory",
        lambda: inv.reserve(order_id, items),
        lambda ticket: inv.release(ticket),
    )
    saga.add_step(
        "ChargePayment",
        lambda: pay.charge(order_id, amount),
        lambda txn: pay.refund(txn),
    )
    saga.add_step(
        "ScheduleShipping",
        lambda: ship.schedule(order_id, address),
        lambda s: ship.cancel(s),
    )
    saga.add_step(
        "SendEmail",
        lambda: email.send("user@x.com", f"Order {order_id} placed!") or "sent",
        lambda r: None,   # no compensation needed
    )

    result = saga.execute()
    print(f"\n  Final status: {result.status.value}")
    print(f"  Completed steps: {result.completed_steps}")


# ============================================================
# DEMO 2: Orchestration with shipping failure → compensation
# ============================================================
def demo_orchestration_failure():
    print("\n" + "=" * 60)
    print("DEMO 2: Orchestration — Shipping fails, compensate")
    print("=" * 60)
    random.seed(1)
    inv = InventoryService()
    pay = PaymentService()
    ship = ShippingService(fail_rate=1.0)   # ALWAYS fail

    order_id = f"ord-{uuid.uuid4().hex[:6]}"
    saga = SagaOrchestrator(order_id)
    saga.add_step("ReserveInventory",
                  lambda: inv.reserve(order_id, ["sku-1"]),
                  lambda t: inv.release(t))
    saga.add_step("ChargePayment",
                  lambda: pay.charge(order_id, 999),
                  lambda x: pay.refund(x))
    saga.add_step("ScheduleShipping",
                  lambda: ship.schedule(order_id, "X"),
                  lambda s: ship.cancel(s))

    result = saga.execute()
    print(f"\n  Final status   : {result.status.value}")
    print(f"  Failed at step : {result.failed_step}")
    print(f"  Completed steps: {result.completed_steps}")


# ============================================================
# DEMO 3: Choreography happy path
# ============================================================
def demo_choreography_happy():
    print("\n" + "=" * 60)
    print("DEMO 3: Choreography — Happy Path")
    print("=" * 60)
    random.seed(0)
    bus = EventBus()
    ChoreographedInventory(bus, InventoryService())
    ChoreographedPayment(bus, PaymentService())
    ChoreographedShipping(bus, ShippingService())

    bus.publish("OrderPlaced", {
        "order_id": "ord-A",
        "items": ["sku-1"],
        "amount": 500,
        "address": "Mumbai",
    })


# ============================================================
# DEMO 4: Choreography failure cascade
# ============================================================
def demo_choreography_failure():
    print("\n" + "=" * 60)
    print("DEMO 4: Choreography — Shipping fails, cascade rollback")
    print("=" * 60)
    random.seed(0)
    bus = EventBus()
    ChoreographedInventory(bus, InventoryService())
    ChoreographedPayment(bus, PaymentService())
    ChoreographedShipping(bus, ShippingService(fail_rate=1.0))

    bus.publish("OrderPlaced", {
        "order_id": "ord-B",
        "items": ["sku-2"],
        "amount": 800,
        "address": "Delhi",
    })


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    demo_orchestration_happy()
    demo_orchestration_failure()
    demo_choreography_happy()
    demo_choreography_failure()

    print("\n" + "=" * 60)
    print("ORCHESTRATION vs CHOREOGRAPHY")
    print("=" * 60)
    print("""
| Aspect              | Orchestration         | Choreography          |
|---------------------|-----------------------|-----------------------|
| Coordination        | Central orchestrator  | Event-driven, no boss |
| Visibility          | Easy to trace         | Distributed — hard    |
| Coupling            | Coordinator knows all | Services loosely coup |
| Failure handling    | Central rollback      | Cascading rollback    |
| Adding steps        | Modify orchestrator   | Subscribe new service |
| Production use      | Temporal, AWS Step    | Kafka, RabbitMQ + ES  |

WHEN TO USE WHICH:
- Orchestration: complex flows, need observability, ordered logic
- Choreography: simple flows, loose coupling, scalability priority

PRODUCTION TOOLS:
- Temporal / Cadence: orchestrated sagas with durability
- AWS Step Functions: state-machine orchestration
- Camunda: BPMN workflow orchestration
- Kafka + microservices: choreography

KEY PRACTICES:
1. Compensations must be IDEMPOTENT (may run multiple times)
2. Persist saga state — survive crashes
3. Timeouts on each step — don't wait forever
4. Monitor saga completion rate + failure causes
5. Test failure scenarios — happy path is easy
""")
