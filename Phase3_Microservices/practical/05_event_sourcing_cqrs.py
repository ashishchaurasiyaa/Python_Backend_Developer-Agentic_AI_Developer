"""
Event Sourcing + CQRS — Python Backend Developer Interview Prep (40 LPA Series)
SQLite only — zero external dependencies.

CLI: python 05_event_sourcing_cqrs.py [basic|snapshot|cqrs|rebuild|concurrency|all]
"""

import sqlite3
import json
import uuid
import sys
import time
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional, Any
from abc import ABC, abstractmethod


# ─────────────────────────────────────────────────────────────
# DOMAIN EVENTS
# ─────────────────────────────────────────────────────────────

@dataclass
class DomainEvent:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = ""
    aggregate_id: str = ""
    aggregate_type: str = "Order"
    version: int = 0
    payload: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class OrderCreated(DomainEvent):
    def __post_init__(self):
        self.event_type = "OrderCreated"


@dataclass
class ItemAdded(DomainEvent):
    def __post_init__(self):
        self.event_type = "ItemAdded"


@dataclass
class ItemRemoved(DomainEvent):
    def __post_init__(self):
        self.event_type = "ItemRemoved"


@dataclass
class OrderConfirmed(DomainEvent):
    def __post_init__(self):
        self.event_type = "OrderConfirmed"


@dataclass
class OrderShipped(DomainEvent):
    def __post_init__(self):
        self.event_type = "OrderShipped"


@dataclass
class OrderCancelled(DomainEvent):
    def __post_init__(self):
        self.event_type = "OrderCancelled"


@dataclass
class PaymentProcessed(DomainEvent):
    def __post_init__(self):
        self.event_type = "PaymentProcessed"


EVENT_CLASS_MAP = {
    "OrderCreated": OrderCreated,
    "ItemAdded": ItemAdded,
    "ItemRemoved": ItemRemoved,
    "OrderConfirmed": OrderConfirmed,
    "OrderShipped": OrderShipped,
    "OrderCancelled": OrderCancelled,
    "PaymentProcessed": PaymentProcessed,
}


def _deserialize_event(row: tuple) -> DomainEvent:
    event_id, event_type, aggregate_id, aggregate_type, version, payload_json, timestamp = row
    payload = json.loads(payload_json)
    cls = EVENT_CLASS_MAP.get(event_type, DomainEvent)
    return cls(
        event_id=event_id,
        event_type=event_type,
        aggregate_id=aggregate_id,
        aggregate_type=aggregate_type,
        version=version,
        payload=payload,
        timestamp=timestamp,
    )


# ─────────────────────────────────────────────────────────────
# EXCEPTIONS
# ─────────────────────────────────────────────────────────────

class ConcurrencyError(Exception):
    pass


class InvalidStateError(Exception):
    pass


# ─────────────────────────────────────────────────────────────
# ORDER AGGREGATE
# ─────────────────────────────────────────────────────────────

class Order:
    def __init__(self, order_id: str):
        self.order_id = order_id
        self.status = "draft"
        self.items: list = []
        self.total = 0.0
        self.customer_id: Optional[str] = None
        self.version = 0
        self._uncommitted_events: list = []

    # ── Commands ──────────────────────────────────────────────

    def create(self, customer_id: str):
        if self.version != 0:
            raise InvalidStateError("Order already created")
        self._emit(OrderCreated(
            aggregate_id=self.order_id,
            payload={"customer_id": customer_id},
        ))

    def add_item(self, product_id: str, name: str, price: float, qty: int):
        if self.status not in ("draft",):
            raise InvalidStateError(f"Cannot add item to order in status '{self.status}'")
        self._emit(ItemAdded(
            aggregate_id=self.order_id,
            payload={"product_id": product_id, "name": name, "price": price, "qty": qty},
        ))

    def remove_item(self, product_id: str):
        if self.status != "draft":
            raise InvalidStateError("Can only remove items from draft orders")
        if not any(i["product_id"] == product_id for i in self.items):
            raise InvalidStateError(f"Item {product_id} not in order")
        self._emit(ItemRemoved(
            aggregate_id=self.order_id,
            payload={"product_id": product_id},
        ))

    def confirm(self):
        if self.status != "draft":
            raise InvalidStateError(f"Cannot confirm order in status '{self.status}'")
        if not self.items:
            raise InvalidStateError("Cannot confirm empty order")
        self._emit(OrderConfirmed(
            aggregate_id=self.order_id,
            payload={"total": self.total},
        ))

    def ship(self, tracking_number: str):
        if self.status != "confirmed":
            raise InvalidStateError(f"Cannot ship order in status '{self.status}'")
        self._emit(OrderShipped(
            aggregate_id=self.order_id,
            payload={"tracking_number": tracking_number},
        ))

    def cancel(self, reason: str):
        if self.status in ("shipped", "cancelled"):
            raise InvalidStateError(f"Cannot cancel order in status '{self.status}'")
        self._emit(OrderCancelled(
            aggregate_id=self.order_id,
            payload={"reason": reason},
        ))

    # ── Event application (state mutation) ────────────────────

    def _emit(self, event: DomainEvent):
        self.version += 1
        event.version = self.version
        event.aggregate_id = self.order_id
        self._apply(event)
        self._uncommitted_events.append(event)

    def _apply(self, event: DomainEvent):
        t = event.event_type
        p = event.payload
        if t == "OrderCreated":
            self.customer_id = p["customer_id"]
            self.status = "draft"
        elif t == "ItemAdded":
            existing = next((i for i in self.items if i["product_id"] == p["product_id"]), None)
            if existing:
                existing["qty"] += p["qty"]
                existing["subtotal"] = existing["price"] * existing["qty"]
            else:
                self.items.append({
                    "product_id": p["product_id"],
                    "name": p["name"],
                    "price": p["price"],
                    "qty": p["qty"],
                    "subtotal": p["price"] * p["qty"],
                })
            self.total = sum(i["subtotal"] for i in self.items)
        elif t == "ItemRemoved":
            self.items = [i for i in self.items if i["product_id"] != p["product_id"]]
            self.total = sum(i["subtotal"] for i in self.items)
        elif t == "OrderConfirmed":
            self.status = "confirmed"
        elif t == "OrderShipped":
            self.status = "shipped"
        elif t == "OrderCancelled":
            self.status = "cancelled"
        elif t == "PaymentProcessed":
            pass  # payment info stored separately
        self.version = event.version

    @classmethod
    def from_events(cls, order_id: str, events: list) -> "Order":
        order = cls(order_id)
        for event in events:
            order._apply(event)
        return order

    @classmethod
    def _from_snapshot(cls, order_id: str, state: dict) -> "Order":
        order = cls(order_id)
        order.status = state["status"]
        order.items = state["items"]
        order.total = state["total"]
        order.customer_id = state["customer_id"]
        order.version = state["version"]
        return order

    def _to_snapshot_state(self) -> dict:
        return {
            "status": self.status,
            "items": self.items,
            "total": self.total,
            "customer_id": self.customer_id,
            "version": self.version,
        }

    def get_uncommitted_events(self) -> list:
        return list(self._uncommitted_events)

    def mark_committed(self):
        self._uncommitted_events.clear()


# ─────────────────────────────────────────────────────────────
# EVENT STORE
# ─────────────────────────────────────────────────────────────

class EventStore:
    def __init__(self, db_path: str = ":memory:"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._setup_schema()

    def _setup_schema(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                event_id      TEXT PRIMARY KEY,
                event_type    TEXT NOT NULL,
                aggregate_id  TEXT NOT NULL,
                aggregate_type TEXT NOT NULL,
                version       INTEGER NOT NULL,
                payload       TEXT NOT NULL,
                timestamp     TEXT NOT NULL,
                UNIQUE (aggregate_id, version)
            )
        """)
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_aggregate_id ON events (aggregate_id)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_type ON events (event_type)"
        )
        self.conn.commit()

    def append(self, events: list):
        if not events:
            return
        rows = [
            (
                e.event_id,
                e.event_type,
                e.aggregate_id,
                e.aggregate_type,
                e.version,
                json.dumps(e.payload),
                e.timestamp,
            )
            for e in events
        ]
        try:
            self.conn.executemany(
                "INSERT INTO events VALUES (?,?,?,?,?,?,?)", rows
            )
            self.conn.commit()
        except sqlite3.IntegrityError as exc:
            self.conn.rollback()
            raise ConcurrencyError(
                f"Version conflict while appending events: {exc}"
            ) from exc

    def load(self, aggregate_id: str, from_version: int = 0) -> list:
        cursor = self.conn.execute(
            "SELECT event_id, event_type, aggregate_id, aggregate_type, version, payload, timestamp "
            "FROM events WHERE aggregate_id=? AND version>? ORDER BY version ASC",
            (aggregate_id, from_version),
        )
        return [_deserialize_event(row) for row in cursor.fetchall()]

    def load_all(self, aggregate_type: str = None) -> list:
        if aggregate_type:
            cursor = self.conn.execute(
                "SELECT event_id, event_type, aggregate_id, aggregate_type, version, payload, timestamp "
                "FROM events WHERE aggregate_type=? ORDER BY rowid ASC",
                (aggregate_type,),
            )
        else:
            cursor = self.conn.execute(
                "SELECT event_id, event_type, aggregate_id, aggregate_type, version, payload, timestamp "
                "FROM events ORDER BY rowid ASC"
            )
        return [_deserialize_event(row) for row in cursor.fetchall()]

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]

    def stats(self) -> dict:
        rows = self.conn.execute(
            "SELECT event_type, COUNT(*) FROM events GROUP BY event_type"
        ).fetchall()
        total = self.conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        agg_count = self.conn.execute(
            "SELECT COUNT(DISTINCT aggregate_id) FROM events"
        ).fetchone()[0]
        return {
            "total_events": total,
            "aggregates": agg_count,
            "by_type": {r[0]: r[1] for r in rows},
        }


# ─────────────────────────────────────────────────────────────
# SNAPSHOT STORE
# ─────────────────────────────────────────────────────────────

class SnapshotStore:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._setup_schema()

    def _setup_schema(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                aggregate_id TEXT PRIMARY KEY,
                state        TEXT NOT NULL,
                version      INTEGER NOT NULL,
                timestamp    TEXT NOT NULL
            )
        """)
        self.conn.commit()

    def save(self, aggregate_id: str, state: dict, version: int):
        self.conn.execute(
            "INSERT OR REPLACE INTO snapshots VALUES (?,?,?,?)",
            (aggregate_id, json.dumps(state), version, datetime.utcnow().isoformat()),
        )
        self.conn.commit()

    def load(self, aggregate_id: str) -> Optional[tuple]:
        row = self.conn.execute(
            "SELECT state, version FROM snapshots WHERE aggregate_id=?",
            (aggregate_id,),
        ).fetchone()
        if row:
            return json.loads(row[0]), row[1]
        return None


# ─────────────────────────────────────────────────────────────
# ORDER REPOSITORY
# ─────────────────────────────────────────────────────────────

class OrderRepository:
    SNAPSHOT_EVERY = 5

    def __init__(self, event_store: EventStore, snapshot_store: SnapshotStore):
        self.event_store = event_store
        self.snapshot_store = snapshot_store

    def save(self, order: Order):
        events = order.get_uncommitted_events()
        if not events:
            return
        self.event_store.append(events)
        order.mark_committed()
        if order.version % self.SNAPSHOT_EVERY == 0:
            self._save_snapshot(order)

    def _save_snapshot(self, order: Order):
        self.snapshot_store.save(order.order_id, order._to_snapshot_state(), order.version)

    def load(self, order_id: str) -> Order:
        snapshot = self.snapshot_store.load(order_id)
        if snapshot:
            state, snap_version = snapshot
            order = Order._from_snapshot(order_id, state)
            events = self.event_store.load(order_id, from_version=snap_version)
            for e in events:
                order._apply(e)
            return order
        events = self.event_store.load(order_id)
        if not events:
            raise ValueError(f"Order {order_id} not found")
        return Order.from_events(order_id, events)


# ─────────────────────────────────────────────────────────────
# PROJECTIONS (CQRS READ MODELS)
# ─────────────────────────────────────────────────────────────

class OrderSummaryProjection:
    """Read model: flat denormalized table for fast queries."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._setup_schema()

    def _setup_schema(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS order_summary (
                order_id    TEXT PRIMARY KEY,
                customer_id TEXT,
                status      TEXT,
                total       REAL DEFAULT 0,
                items_count INTEGER DEFAULT 0,
                created_at  TEXT,
                updated_at  TEXT
            )
        """)
        self.conn.commit()

    def handle(self, event: DomainEvent):
        handlers = {
            "OrderCreated": self._on_created,
            "ItemAdded": self._on_item_added,
            "ItemRemoved": self._on_item_removed,
            "OrderConfirmed": self._on_confirmed,
            "OrderShipped": self._on_shipped,
            "OrderCancelled": self._on_cancelled,
        }
        handler = handlers.get(event.event_type)
        if handler:
            handler(event)

    def _on_created(self, event: DomainEvent):
        self.conn.execute(
            "INSERT OR IGNORE INTO order_summary (order_id, customer_id, status, total, items_count, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (event.aggregate_id, event.payload["customer_id"], "draft", 0.0, 0, event.timestamp, event.timestamp),
        )
        self.conn.commit()

    def _on_item_added(self, event: DomainEvent):
        p = event.payload
        subtotal = p["price"] * p["qty"]
        self.conn.execute(
            "UPDATE order_summary SET total=total+?, items_count=items_count+1, updated_at=? WHERE order_id=?",
            (subtotal, event.timestamp, event.aggregate_id),
        )
        self.conn.commit()

    def _on_item_removed(self, event: DomainEvent):
        # We don't store line items in the read model, so recalculate from events is needed.
        # For simplicity: decrement items_count and trust the write-side total is consistent.
        self.conn.execute(
            "UPDATE order_summary SET items_count=MAX(0, items_count-1), updated_at=? WHERE order_id=?",
            (event.timestamp, event.aggregate_id),
        )
        self.conn.commit()

    def _on_confirmed(self, event: DomainEvent):
        self.conn.execute(
            "UPDATE order_summary SET status='confirmed', updated_at=? WHERE order_id=?",
            (event.timestamp, event.aggregate_id),
        )
        self.conn.commit()

    def _on_shipped(self, event: DomainEvent):
        self.conn.execute(
            "UPDATE order_summary SET status='shipped', updated_at=? WHERE order_id=?",
            (event.timestamp, event.aggregate_id),
        )
        self.conn.commit()

    def _on_cancelled(self, event: DomainEvent):
        self.conn.execute(
            "UPDATE order_summary SET status='cancelled', updated_at=? WHERE order_id=?",
            (event.timestamp, event.aggregate_id),
        )
        self.conn.commit()

    def rebuild(self, all_events: list):
        self.conn.execute("DELETE FROM order_summary")
        self.conn.commit()
        type_counts: dict = {}
        for event in all_events:
            type_counts[event.event_type] = type_counts.get(event.event_type, 0) + 1
            self.handle(event)
        return type_counts

    def get_by_id(self, order_id: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT order_id, customer_id, status, total, items_count, created_at, updated_at "
            "FROM order_summary WHERE order_id=?",
            (order_id,),
        ).fetchone()
        if row:
            return dict(zip(["order_id", "customer_id", "status", "total", "items_count", "created_at", "updated_at"], row))
        return None

    def get_by_customer(self, customer_id: str) -> list:
        rows = self.conn.execute(
            "SELECT order_id, customer_id, status, total, items_count, created_at, updated_at "
            "FROM order_summary WHERE customer_id=? ORDER BY created_at",
            (customer_id,),
        ).fetchall()
        cols = ["order_id", "customer_id", "status", "total", "items_count", "created_at", "updated_at"]
        return [dict(zip(cols, r)) for r in rows]

    def get_by_status(self, status: str) -> list:
        rows = self.conn.execute(
            "SELECT order_id, customer_id, status, total, items_count, created_at, updated_at "
            "FROM order_summary WHERE status=? ORDER BY created_at",
            (status,),
        ).fetchall()
        cols = ["order_id", "customer_id", "status", "total", "items_count", "created_at", "updated_at"]
        return [dict(zip(cols, r)) for r in rows]

    def get_statistics(self) -> dict:
        total_row = self.conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(total),0) FROM order_summary"
        ).fetchone()
        status_rows = self.conn.execute(
            "SELECT status, COUNT(*) FROM order_summary GROUP BY status"
        ).fetchall()
        return {
            "total_orders": total_row[0],
            "total_revenue": total_row[1],
            "by_status": {r[0]: r[1] for r in status_rows},
        }

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM order_summary").fetchone()[0]


class CustomerSpendProjection:
    """Read model: customer → total spend analytics."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._setup_schema()

    def _setup_schema(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS customer_spend (
                customer_id  TEXT PRIMARY KEY,
                total_spend  REAL DEFAULT 0,
                order_count  INTEGER DEFAULT 0,
                last_order   TEXT
            )
        """)
        self.conn.commit()

    def handle(self, event: DomainEvent):
        if event.event_type == "OrderCreated":
            cid = event.payload["customer_id"]
            self.conn.execute(
                "INSERT OR IGNORE INTO customer_spend (customer_id, total_spend, order_count, last_order) "
                "VALUES (?,0,0,?)",
                (cid, event.timestamp),
            )
            self.conn.execute(
                "UPDATE customer_spend SET order_count=order_count+1, last_order=? WHERE customer_id=?",
                (event.timestamp, cid),
            )
            self.conn.commit()
        elif event.event_type == "ItemAdded":
            p = event.payload
            # We need to look up customer_id from the order_summary projection
            row = self.conn.execute(
                "SELECT customer_id FROM order_summary WHERE order_id=?",
                (event.aggregate_id,),
            ).fetchone()
            if row:
                subtotal = p["price"] * p["qty"]
                self.conn.execute(
                    "UPDATE customer_spend SET total_spend=total_spend+? WHERE customer_id=?",
                    (subtotal, row[0]),
                )
                self.conn.commit()
        elif event.event_type == "ItemRemoved":
            row = self.conn.execute(
                "SELECT customer_id FROM order_summary WHERE order_id=?",
                (event.aggregate_id,),
            ).fetchone()
            if row:
                # Recalc from order_summary total; for simplicity track nothing here
                pass

    def rebuild(self, all_events: list):
        self.conn.execute("DELETE FROM customer_spend")
        self.conn.commit()
        for event in all_events:
            self.handle(event)

    def get_top_customers(self, limit: int = 5) -> list:
        rows = self.conn.execute(
            "SELECT customer_id, total_spend, order_count FROM customer_spend "
            "ORDER BY total_spend DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [{"customer_id": r[0], "total_spend": r[1], "order_count": r[2]} for r in rows]


# ─────────────────────────────────────────────────────────────
# COMMANDS & COMMAND HANDLER
# ─────────────────────────────────────────────────────────────

@dataclass
class CreateOrderCmd:
    customer_id: str


@dataclass
class AddItemCmd:
    order_id: str
    product_id: str
    name: str
    price: float
    qty: int


@dataclass
class RemoveItemCmd:
    order_id: str
    product_id: str


@dataclass
class ConfirmOrderCmd:
    order_id: str


@dataclass
class ShipOrderCmd:
    order_id: str
    tracking_number: str


@dataclass
class CancelOrderCmd:
    order_id: str
    reason: str


class OrderCommandHandler:
    def __init__(self, repo: OrderRepository, *projections):
        self._repo = repo
        self._projections = projections

    def handle(self, cmd) -> Any:
        if isinstance(cmd, CreateOrderCmd):
            return self._create_order(cmd)
        elif isinstance(cmd, AddItemCmd):
            return self._add_item(cmd)
        elif isinstance(cmd, RemoveItemCmd):
            return self._remove_item(cmd)
        elif isinstance(cmd, ConfirmOrderCmd):
            return self._confirm_order(cmd)
        elif isinstance(cmd, ShipOrderCmd):
            return self._ship_order(cmd)
        elif isinstance(cmd, CancelOrderCmd):
            return self._cancel_order(cmd)
        else:
            raise ValueError(f"Unknown command: {type(cmd)}")

    def _fan_out(self, order_id: str, new_events: list):
        for event in new_events:
            for proj in self._projections:
                proj.handle(event)

    def _create_order(self, cmd: CreateOrderCmd) -> str:
        order_id = str(uuid.uuid4())[:8]
        order = Order(order_id)
        order.create(cmd.customer_id)
        events = order.get_uncommitted_events()
        self._repo.save(order)
        self._fan_out(order_id, events)
        return order_id

    def _add_item(self, cmd: AddItemCmd) -> Order:
        order = self._repo.load(cmd.order_id)
        order.add_item(cmd.product_id, cmd.name, cmd.price, cmd.qty)
        events = order.get_uncommitted_events()
        self._repo.save(order)
        self._fan_out(cmd.order_id, events)
        return order

    def _remove_item(self, cmd: RemoveItemCmd) -> Order:
        order = self._repo.load(cmd.order_id)
        order.remove_item(cmd.product_id)
        events = order.get_uncommitted_events()
        self._repo.save(order)
        self._fan_out(cmd.order_id, events)
        return order

    def _confirm_order(self, cmd: ConfirmOrderCmd) -> Order:
        order = self._repo.load(cmd.order_id)
        order.confirm()
        events = order.get_uncommitted_events()
        self._repo.save(order)
        self._fan_out(cmd.order_id, events)
        return order

    def _ship_order(self, cmd: ShipOrderCmd) -> Order:
        order = self._repo.load(cmd.order_id)
        order.ship(cmd.tracking_number)
        events = order.get_uncommitted_events()
        self._repo.save(order)
        self._fan_out(cmd.order_id, events)
        return order

    def _cancel_order(self, cmd: CancelOrderCmd) -> Order:
        order = self._repo.load(cmd.order_id)
        order.cancel(cmd.reason)
        events = order.get_uncommitted_events()
        self._repo.save(order)
        self._fan_out(cmd.order_id, events)
        return order


# ─────────────────────────────────────────────────────────────
# QUERY HANDLER
# ─────────────────────────────────────────────────────────────

class OrderQueryHandler:
    def __init__(self, summary_proj: OrderSummaryProjection, spend_proj: CustomerSpendProjection):
        self._summary = summary_proj
        self._spend = spend_proj

    def get_order(self, order_id: str) -> Optional[dict]:
        return self._summary.get_by_id(order_id)

    def get_customer_orders(self, customer_id: str) -> list:
        return self._summary.get_by_customer(customer_id)

    def get_stats(self) -> dict:
        return self._summary.get_statistics()

    def get_top_customers(self) -> list:
        return self._spend.get_top_customers()


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def _make_store(shared_conn: bool = True):
    """Create a fresh in-memory EventStore + SnapshotStore sharing the same connection."""
    event_store = EventStore(":memory:")
    snapshot_store = SnapshotStore(event_store.conn)
    return event_store, snapshot_store


def _rupees(amount: float) -> str:
    return f"₹{amount:,.2f}"


# ─────────────────────────────────────────────────────────────
# DEMO 1: BASIC EVENT SOURCING
# ─────────────────────────────────────────────────────────────

def demo_basic_event_sourcing():
    print("\n" + "=" * 60)
    print("  Demo 1: Basic Event Sourcing")
    print("=" * 60)

    event_store, snapshot_store = _make_store()

    order_id = "ORD-001"
    order = Order(order_id)

    print(f"\nCreating order {order_id} for customer CUST-001...")
    order.create("CUST-001")
    print(f"  → Event: OrderCreated v{order.version}")

    items = [
        ("P-001", "Laptop",   85000.0, 1),
        ("P-002", "Mouse",     1500.0, 2),
        ("P-003", "Keyboard",  3000.0, 1),
    ]
    print("Adding 3 items...")
    for pid, name, price, qty in items:
        order.add_item(pid, name, price, qty)
        print(f"  → Event: ItemAdded v{order.version} ({name}, {_rupees(price)}, qty:{qty})")

    order.confirm()
    print(f"Confirming order...\n  → Event: OrderConfirmed v{order.version}")

    order.ship("TRACK-XYZ-999")
    print(f"Shipping order...\n  → Event: OrderShipped v{order.version}")

    event_store.append(order.get_uncommitted_events())
    order.mark_committed()

    events = event_store.load(order_id)
    print(f"\nEvent Store contents ({len(events)} events):")
    for e in events:
        print(f"  v{e.version:<3} {e.event_type:<18} {e.timestamp[:19]}")

    rebuilt = Order.from_events(order_id, events)
    print(f"\nRebuilding state from events...")
    print(f"  Order {order_id}: status={rebuilt.status}, items={len(rebuilt.items)}, total={_rupees(rebuilt.total)}")

    print("\nTime Travel:")
    for v in (2, 4, 5):
        partial = Order.from_events(order_id, [e for e in events if e.version <= v])
        print(f"  At v{v}: status={partial.status}, items={len(partial.items)}, total={_rupees(partial.total)}")


# ─────────────────────────────────────────────────────────────
# DEMO 2: SNAPSHOTS PERFORMANCE
# ─────────────────────────────────────────────────────────────

def demo_snapshots():
    print("\n" + "=" * 60)
    print("  Demo 2: Snapshot Performance")
    print("=" * 60)

    event_store, snapshot_store = _make_store()
    repo = OrderRepository(event_store, snapshot_store)

    order_id = "ORD-SNAP"
    order = Order(order_id)
    order.create("CUST-SNAP")
    repo.save(order)

    print(f"\nCreating order with 15 items (triggers snapshots at v5, v10, v15)...")
    for i in range(1, 16):
        order = repo.load(order_id)
        order.add_item(f"P-{i:03}", f"Product-{i}", float(100 * i), 1)
        repo.save(order)
        if order.version % 5 == 0:
            print(f"  Snapshot saved at v{order.version}")

    # Without snapshot — measure loading all events
    t0 = time.perf_counter()
    events = event_store.load(order_id)
    o1 = Order.from_events(order_id, events)
    t1 = time.perf_counter()
    no_snap_ms = (t1 - t0) * 1000

    # With snapshot — load from snap at v15 (only delta events, which is 0 here)
    # Manually place a snapshot at v10 and measure
    snap10_state = None
    partial = Order.from_events(order_id, [e for e in events if e.version <= 10])
    snap10_state = partial._to_snapshot_state()

    t0 = time.perf_counter()
    o2 = Order._from_snapshot(order_id, snap10_state)
    delta_events = event_store.load(order_id, from_version=10)
    for e in delta_events:
        o2._apply(e)
    t1 = time.perf_counter()
    snap_ms = (t1 - t0) * 1000

    pct = (1 - snap_ms / no_snap_ms) * 100 if no_snap_ms > 0 else 0

    print(f"\nWithout snapshot : loading {len(events)} events ... {no_snap_ms:.3f}ms")
    print(f"With snapshot@v10: loading {len(delta_events)} events ... {snap_ms:.3f}ms ({pct:.0f}% faster)")

    match = o1.total == o2.total and o1.status == o2.status and len(o1.items) == len(o2.items)
    print(f"\nVerifying state matches: {'✓ (both methods give same result)' if match else '✗ MISMATCH'}")


# ─────────────────────────────────────────────────────────────
# DEMO 3: CQRS WRITE → READ
# ─────────────────────────────────────────────────────────────

def demo_cqrs():
    print("\n" + "=" * 60)
    print("  Demo 3: CQRS Pattern")
    print("=" * 60)

    event_store, snapshot_store = _make_store()
    repo = OrderRepository(event_store, snapshot_store)
    summary_proj = OrderSummaryProjection(event_store.conn)
    spend_proj = CustomerSpendProjection(event_store.conn)
    cmd_handler = OrderCommandHandler(repo, summary_proj, spend_proj)
    qry_handler = OrderQueryHandler(summary_proj, spend_proj)

    print("\n--- WRITE SIDE (Commands) ---")

    # Alice: 2 items
    oid1 = cmd_handler.handle(CreateOrderCmd("Alice"))
    print(f"CMD: CreateOrder(customer=Alice)    → order_id: {oid1}")

    cmd_handler.handle(AddItemCmd(oid1, "P-001", "Laptop", 85000.0, 1))
    o = qry_handler.get_order(oid1)
    print(f"CMD: AddItem(Laptop, {_rupees(85000)})        → items={o['items_count']}, total={_rupees(o['total'])}")

    cmd_handler.handle(AddItemCmd(oid1, "P-002", "Mouse", 1500.0, 2))
    o = qry_handler.get_order(oid1)
    print(f"CMD: AddItem(Mouse, {_rupees(1500)} x2)       → items={o['items_count']}, total={_rupees(o['total'])}")

    cmd_handler.handle(ConfirmOrderCmd(oid1))
    o = qry_handler.get_order(oid1)
    print(f"CMD: ConfirmOrder()                 → status={o['status']}")

    # Alice: 2nd order (shipped)
    oid2 = cmd_handler.handle(CreateOrderCmd("Alice"))
    cmd_handler.handle(AddItemCmd(oid2, "P-003", "Monitor", 25000.0, 1))
    cmd_handler.handle(ConfirmOrderCmd(oid2))
    cmd_handler.handle(ShipOrderCmd(oid2, "TRACK-001"))

    # Alice: 3rd order (draft)
    oid3 = cmd_handler.handle(CreateOrderCmd("Alice"))
    cmd_handler.handle(AddItemCmd(oid3, "P-004", "Headphones", 4500.0, 1))

    # Bob: a few orders for stats
    for name, prod, price in [("Bob", "Tablet", 35000.0), ("Bob", "Case", 500.0)]:
        ox = cmd_handler.handle(CreateOrderCmd(name))
        cmd_handler.handle(AddItemCmd(ox, "P-X", prod, price, 1))
        cmd_handler.handle(ConfirmOrderCmd(ox))

    oc = cmd_handler.handle(CreateOrderCmd("Charlie"))
    cmd_handler.handle(AddItemCmd(oc, "P-Y", "Charger", 2000.0, 1))
    cmd_handler.handle(CancelOrderCmd(oc, "Changed mind"))

    print("\nEvents → Projection updated automatically")

    print("\n--- READ SIDE (Queries) ---")
    order_data = qry_handler.get_order(oid1)
    print(f"GET order {oid1}:")
    print(f"  {order_data}")

    alice_orders = qry_handler.get_customer_orders("Alice")
    alice_total = sum(o["total"] for o in alice_orders)
    print(f"\nGET Alice's orders: {len(alice_orders)} orders, total spend {_rupees(alice_total)}")

    stats = qry_handler.get_stats()
    print(f"\nGET statistics:")
    print(f"  Total orders  : {stats['total_orders']}")
    print(f"  Total revenue : {_rupees(stats['total_revenue'])}")
    print(f"  By status     : {stats['by_status']}")

    top = qry_handler.get_top_customers()
    print(f"\nTop customers by spend:")
    for i, c in enumerate(top, 1):
        print(f"  {i}. {c['customer_id']} — {_rupees(c['total_spend'])} across {c['order_count']} order(s)")


# ─────────────────────────────────────────────────────────────
# DEMO 4: PROJECTION REBUILD
# ─────────────────────────────────────────────────────────────

def demo_projection_rebuild():
    print("\n" + "=" * 60)
    print("  Demo 4: Projection Rebuild")
    print("=" * 60)

    event_store, snapshot_store = _make_store()
    repo = OrderRepository(event_store, snapshot_store)
    summary_proj = OrderSummaryProjection(event_store.conn)
    spend_proj = CustomerSpendProjection(event_store.conn)
    cmd_handler = OrderCommandHandler(repo, summary_proj, spend_proj)

    customers = ["Alice", "Bob", "Charlie", "Diana", "Eve"]
    products = [
        ("P-001", "Laptop",    85000.0),
        ("P-002", "Mouse",      1500.0),
        ("P-003", "Monitor",   25000.0),
        ("P-004", "Keyboard",   3000.0),
        ("P-005", "Webcam",     4500.0),
    ]

    order_ids = []
    for i, cust in enumerate(customers):
        oid = cmd_handler.handle(CreateOrderCmd(cust))
        order_ids.append(oid)
        for j in range(i % 3 + 1):
            prod = products[(i + j) % len(products)]
            cmd_handler.handle(AddItemCmd(oid, prod[0], prod[1], prod[2], 1))
        # Confirm all except the last one (which will be cancelled)
        if i != 4:
            cmd_handler.handle(ConfirmOrderCmd(oid))
        if i == 1:
            cmd_handler.handle(ShipOrderCmd(oid, f"TRACK-{i:03}"))
        if i == 4:
            cmd_handler.handle(CancelOrderCmd(oid, "Out of budget"))

    total_events = event_store.count()
    print(f"\nEvent store has {total_events} events across {len(order_ids)} orders")

    print("Corrupted projection (clearing read model)...")
    event_store.conn.execute("DELETE FROM order_summary")
    event_store.conn.execute("DELETE FROM customer_spend")
    event_store.conn.commit()

    all_events = event_store.load_all()
    print(f"Rebuilding from {len(all_events)} events...")

    t0 = time.perf_counter()
    type_counts = summary_proj.rebuild(all_events)
    spend_proj.rebuild(all_events)
    elapsed = (time.perf_counter() - t0) * 1000

    for etype, cnt in sorted(type_counts.items()):
        print(f"  Processing {etype} x{cnt}...")

    order_count = summary_proj.count()
    print(f"\nRebuild complete in {elapsed:.2f}ms")
    print(f"Orders in projection: {order_count} {'✓' if order_count == len(order_ids) else '✗'}")


# ─────────────────────────────────────────────────────────────
# DEMO 5: OPTIMISTIC CONCURRENCY
# ─────────────────────────────────────────────────────────────

def demo_optimistic_concurrency():
    print("\n" + "=" * 60)
    print("  Demo 5: Optimistic Concurrency")
    print("=" * 60)

    event_store, snapshot_store = _make_store()
    repo = OrderRepository(event_store, snapshot_store)
    summary_proj = OrderSummaryProjection(event_store.conn)
    cmd_handler = OrderCommandHandler(repo, summary_proj)

    # Seed an order with 3 events so version=3
    oid = cmd_handler.handle(CreateOrderCmd("CUST-CONC"))
    cmd_handler.handle(AddItemCmd(oid, "P-001", "Widget", 500.0, 1))
    cmd_handler.handle(AddItemCmd(oid, "P-002", "Gadget", 750.0, 1))

    order_a = repo.load(oid)
    order_b = repo.load(oid)

    print(f"\nOrder {oid} loaded by Session-A (version={order_a.version})")
    print(f"Order {oid} loaded by Session-B (version={order_b.version})")

    # Session A commits first
    order_a.add_item("P-003", "ItemA", 100.0, 1)
    event_store.append(order_a.get_uncommitted_events())
    order_a.mark_committed()
    print(f"\nSession-A adds item → saves at v{order_a.version} ✓")

    # Session B tries to commit on stale version
    order_b.add_item("P-004", "ItemB", 200.0, 1)
    print(f"Session-B adds item → tries to save at v{order_b.version}...")
    try:
        event_store.append(order_b.get_uncommitted_events())
        order_b.mark_committed()
        print("  (unexpected success)")
    except ConcurrencyError:
        print("  ✗ ConcurrencyError: Version conflict!")
        print("  → Session-B must reload and retry")

        # Retry: reload and re-apply the intended command
        order_b_retry = repo.load(oid)
        print(f"Session-B reloads (version={order_b_retry.version}), adds item → ", end="")
        order_b_retry.add_item("P-004", "ItemB", 200.0, 1)
        event_store.append(order_b_retry.get_uncommitted_events())
        order_b_retry.mark_committed()
        print(f"saves at v{order_b_retry.version} ✓")

        final = repo.load(oid)
        print(f"\nFinal state: version={final.version}, items={len(final.items)} ✓")


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def run_all():
    print("\n" + "=" * 60)
    print("  EVENT SOURCING + CQRS COMPLETE DEMO")
    print("=" * 60)
    demo_basic_event_sourcing()
    demo_snapshots()
    demo_cqrs()
    demo_projection_rebuild()
    demo_optimistic_concurrency()
    print("\n✅ All demos completed!")


if __name__ == "__main__":
    demos = {
        "basic":       demo_basic_event_sourcing,
        "snapshot":    demo_snapshots,
        "cqrs":        demo_cqrs,
        "rebuild":     demo_projection_rebuild,
        "concurrency": demo_optimistic_concurrency,
        "all":         run_all,
    }
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    fn = demos.get(cmd)
    if fn is None:
        print(f"Unknown demo '{cmd}'. Choose from: {', '.join(demos)}")
        sys.exit(1)
    fn()
