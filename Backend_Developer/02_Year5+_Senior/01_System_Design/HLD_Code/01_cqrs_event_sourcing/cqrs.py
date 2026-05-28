"""
============================================================
CQRS + EVENT SOURCING — Working Implementation
============================================================
CQRS  = Command Query Responsibility Segregation
        Separate WRITE model from READ model.

Event Sourcing = Store events (facts), derive state by replay.

Combined:
  Commands → Events → Event Store → Projections (Read Models)

This file demonstrates a bank account domain:
  Commands: OpenAccount, Deposit, Withdraw, TransferOut
  Events  : AccountOpened, MoneyDeposited, MoneyWithdrawn, TransferRequested
  Queries : GetBalance, GetStatement (different read model)

Run:  python cqrs.py
"""
from __future__ import annotations
import json
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from collections import defaultdict
from typing import Any


# ============================================================
# 1. EVENTS — immutable facts about what happened
# ============================================================
@dataclass(frozen=True)
class Event:
    event_id: str
    aggregate_id: str
    event_type: str
    payload: dict
    version: int               # version of aggregate AFTER this event
    timestamp: float

    def to_dict(self):
        d = asdict(self)
        return d


def new_event(aggregate_id, event_type, payload, version) -> Event:
    return Event(
        event_id=str(uuid.uuid4()),
        aggregate_id=aggregate_id,
        event_type=event_type,
        payload=payload,
        version=version,
        timestamp=time.time(),
    )


# ============================================================
# 2. EVENT STORE — append-only log
# ============================================================
class EventStore:
    """In-memory event store. In prod: PostgreSQL, EventStoreDB, Kafka."""
    def __init__(self):
        self._events: list[Event] = []
        self._subscribers: list = []

    def append(self, events: list[Event], expected_version: int | None = None):
        """Append events with optimistic concurrency check."""
        if events and expected_version is not None:
            current = self.last_version(events[0].aggregate_id)
            if current != expected_version:
                raise ConcurrencyError(
                    f"Expected version {expected_version}, got {current}"
                )
        for e in events:
            self._events.append(e)
            for sub in self._subscribers:
                sub(e)

    def load(self, aggregate_id: str) -> list[Event]:
        return [e for e in self._events if e.aggregate_id == aggregate_id]

    def last_version(self, aggregate_id: str) -> int:
        events = self.load(aggregate_id)
        return events[-1].version if events else 0

    def all_events(self) -> list[Event]:
        return list(self._events)

    def subscribe(self, callback):
        self._subscribers.append(callback)


class ConcurrencyError(Exception):
    pass


# ============================================================
# 3. AGGREGATE — encapsulates business rules
# ============================================================
@dataclass
class Account:
    """Write-side aggregate. Reconstructed from events."""
    account_id: str
    owner: str = ""
    balance: float = 0.0
    is_open: bool = False
    version: int = 0

    @classmethod
    def from_events(cls, events: list[Event]) -> "Account":
        acc = cls(account_id=events[0].aggregate_id) if events else cls("")
        for e in events:
            acc._apply(e)
        return acc

    def _apply(self, event: Event):
        if event.event_type == "AccountOpened":
            self.owner = event.payload["owner"]
            self.is_open = True
        elif event.event_type == "MoneyDeposited":
            self.balance += event.payload["amount"]
        elif event.event_type == "MoneyWithdrawn":
            self.balance -= event.payload["amount"]
        elif event.event_type == "TransferRequested":
            self.balance -= event.payload["amount"]
        elif event.event_type == "AccountClosed":
            self.is_open = False
        self.version = event.version


# ============================================================
# 4. COMMAND HANDLERS — business logic + event emission
# ============================================================
class AccountCommandHandler:
    def __init__(self, store: EventStore):
        self.store = store

    def open_account(self, account_id: str, owner: str) -> list[Event]:
        events = self.store.load(account_id)
        if events:
            raise ValueError("Account already exists")
        e = new_event(account_id, "AccountOpened", {"owner": owner}, version=1)
        self.store.append([e], expected_version=0)
        return [e]

    def deposit(self, account_id: str, amount: float) -> list[Event]:
        if amount <= 0:
            raise ValueError("Amount must be positive")
        events = self.store.load(account_id)
        if not events:
            raise ValueError("Account not found")
        acc = Account.from_events(events)
        if not acc.is_open:
            raise ValueError("Account closed")
        e = new_event(account_id, "MoneyDeposited", {"amount": amount}, acc.version + 1)
        self.store.append([e], expected_version=acc.version)
        return [e]

    def withdraw(self, account_id: str, amount: float) -> list[Event]:
        if amount <= 0:
            raise ValueError("Amount must be positive")
        events = self.store.load(account_id)
        acc = Account.from_events(events)
        if not acc.is_open:
            raise ValueError("Account closed")
        if acc.balance < amount:
            raise ValueError(f"Insufficient funds: {acc.balance} < {amount}")
        e = new_event(account_id, "MoneyWithdrawn", {"amount": amount}, acc.version + 1)
        self.store.append([e], expected_version=acc.version)
        return [e]

    def close_account(self, account_id: str) -> list[Event]:
        events = self.store.load(account_id)
        acc = Account.from_events(events)
        if not acc.is_open:
            raise ValueError("Already closed")
        if acc.balance != 0:
            raise ValueError("Must zero balance before closing")
        e = new_event(account_id, "AccountClosed", {}, acc.version + 1)
        self.store.append([e], expected_version=acc.version)
        return [e]


# ============================================================
# 5. READ MODELS / PROJECTIONS — different views from same events
# ============================================================
class BalanceProjection:
    """Fast lookup of current balance by account ID."""
    def __init__(self):
        self._balances: dict[str, float] = defaultdict(float)
        self._owners: dict[str, str] = {}

    def handle(self, event: Event):
        if event.event_type == "AccountOpened":
            self._owners[event.aggregate_id] = event.payload["owner"]
        elif event.event_type == "MoneyDeposited":
            self._balances[event.aggregate_id] += event.payload["amount"]
        elif event.event_type == "MoneyWithdrawn":
            self._balances[event.aggregate_id] -= event.payload["amount"]

    def get_balance(self, account_id: str) -> float:
        return self._balances[account_id]

    def get_owner(self, account_id: str) -> str:
        return self._owners.get(account_id, "")


class StatementProjection:
    """Per-account transaction history for statement generation."""
    def __init__(self):
        self._statements: dict[str, list[dict]] = defaultdict(list)

    def handle(self, event: Event):
        if event.event_type in ("MoneyDeposited", "MoneyWithdrawn"):
            sign = 1 if event.event_type == "MoneyDeposited" else -1
            self._statements[event.aggregate_id].append({
                "type": event.event_type,
                "amount": sign * event.payload["amount"],
                "timestamp": event.timestamp,
            })

    def get_statement(self, account_id: str) -> list[dict]:
        return self._statements[account_id]


class TopAccountsProjection:
    """Analytics view — top accounts by balance."""
    def __init__(self):
        self._balances: dict[str, float] = defaultdict(float)

    def handle(self, event: Event):
        if event.event_type == "MoneyDeposited":
            self._balances[event.aggregate_id] += event.payload["amount"]
        elif event.event_type == "MoneyWithdrawn":
            self._balances[event.aggregate_id] -= event.payload["amount"]

    def top(self, n=3) -> list[tuple[str, float]]:
        return sorted(self._balances.items(), key=lambda x: -x[1])[:n]


# ============================================================
# 6. QUERY HANDLERS — read-only, hit projections
# ============================================================
class AccountQueryHandler:
    def __init__(self, balance: BalanceProjection, statement: StatementProjection):
        self.balance = balance
        self.statement = statement

    def get_balance(self, account_id: str) -> dict:
        return {
            "account_id": account_id,
            "owner": self.balance.get_owner(account_id),
            "balance": self.balance.get_balance(account_id),
        }

    def get_statement(self, account_id: str) -> dict:
        return {
            "account_id": account_id,
            "transactions": self.statement.get_statement(account_id),
        }


# ============================================================
# 7. WIRE EVERYTHING TOGETHER
# ============================================================
def build_system():
    store = EventStore()
    balance_proj = BalanceProjection()
    statement_proj = StatementProjection()
    top_proj = TopAccountsProjection()

    # Subscribe projections to event stream
    store.subscribe(balance_proj.handle)
    store.subscribe(statement_proj.handle)
    store.subscribe(top_proj.handle)

    commands = AccountCommandHandler(store)
    queries = AccountQueryHandler(balance_proj, statement_proj)

    return store, commands, queries, top_proj


# ============================================================
# DEMO
# ============================================================
def demo():
    print("=" * 60)
    print("CQRS + EVENT SOURCING DEMO")
    print("=" * 60)

    store, cmd, qry, top_proj = build_system()

    print("\n--- COMMANDS ---")
    cmd.open_account("acc-1", "Ashish")
    cmd.deposit("acc-1", 5000)
    cmd.deposit("acc-1", 2000)
    cmd.withdraw("acc-1", 1000)

    cmd.open_account("acc-2", "Bob")
    cmd.deposit("acc-2", 10000)
    cmd.deposit("acc-2", 25000)

    cmd.open_account("acc-3", "Carol")
    cmd.deposit("acc-3", 500)

    print(f"  Total events in store: {len(store.all_events())}")

    print("\n--- QUERIES (read from projections) ---")
    print(f"  Balance acc-1: {qry.get_balance('acc-1')}")
    print(f"  Balance acc-2: {qry.get_balance('acc-2')}")

    print("\n--- STATEMENT (different read model from SAME events) ---")
    stmt = qry.get_statement("acc-1")
    for txn in stmt["transactions"]:
        print(f"  {txn['type']:20s} {txn['amount']:+.2f}")

    print("\n--- TOP ACCOUNTS (analytics view) ---")
    for acc, bal in top_proj.top(3):
        print(f"  {acc}: ₹{bal}")

    print("\n--- TIME TRAVEL: Rebuild aggregate from events ---")
    events = store.load("acc-1")
    acc = Account.from_events(events)
    print(f"  Rebuilt acc-1: owner={acc.owner}, balance={acc.balance}, version={acc.version}")

    print("\n--- OPTIMISTIC CONCURRENCY ---")
    try:
        # Manually create event with wrong version
        bad = new_event("acc-1", "MoneyDeposited", {"amount": 1}, version=99)
        store.append([bad], expected_version=99)
    except ConcurrencyError as e:
        print(f"  Concurrency caught: {e}")

    print("\n--- INSUFFICIENT FUNDS ---")
    try:
        cmd.withdraw("acc-3", 999999)
    except ValueError as e:
        print(f"  Business rule enforced: {e}")

    print("\n--- EVENT LOG SAMPLE ---")
    for e in store.all_events()[:5]:
        print(f"  v{e.version} {e.event_type}({e.aggregate_id}): {e.payload}")


# ============================================================
# SNAPSHOTS (Optimization for long event streams)
# ============================================================
@dataclass
class Snapshot:
    aggregate_id: str
    state: dict
    version: int


class SnapshotStore:
    """Optimization: store periodic snapshots so we don't replay 100k events."""
    def __init__(self, every_n=100):
        self.every_n = every_n
        self._snapshots: dict[str, Snapshot] = {}

    def save(self, snapshot: Snapshot):
        self._snapshots[snapshot.aggregate_id] = snapshot

    def latest(self, aggregate_id: str) -> Snapshot | None:
        return self._snapshots.get(aggregate_id)


def load_with_snapshot(store: EventStore, snapshots: SnapshotStore, account_id: str) -> Account:
    snap = snapshots.latest(account_id)
    all_events = store.load(account_id)
    if snap:
        acc = Account(account_id=account_id, **snap.state)
        acc.version = snap.version
        remaining = [e for e in all_events if e.version > snap.version]
    else:
        acc = Account.from_events(all_events)
        return acc
    for e in remaining:
        acc._apply(e)
    return acc


if __name__ == "__main__":
    demo()
    print("\n" + "=" * 60)
    print("KEY TAKEAWAYS")
    print("=" * 60)
    print("""
1. Events = immutable facts. Append-only log.
2. Aggregate = reconstructed by replaying events.
3. Multiple PROJECTIONS = different read models from same events.
4. Commands → Events → Store → Pub/Sub → Projections.
5. Optimistic concurrency via expected_version check.
6. Snapshots periodically to avoid replaying huge streams.
7. Time travel: rebuild state at any point in history.
8. Production: use Kafka / EventStoreDB / Postgres LISTEN/NOTIFY.

ADVANTAGES:
- Full audit log (compliance!)
- Time travel debugging
- Multiple read models tuned per use case
- Easy to add new projections

DRAWBACKS:
- Eventual consistency (projections lag write)
- More moving parts
- Schema evolution of events is tricky
- Replay can be slow without snapshots
""")
