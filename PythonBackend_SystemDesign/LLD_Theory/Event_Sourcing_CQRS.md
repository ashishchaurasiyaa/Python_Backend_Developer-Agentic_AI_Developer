# Event Sourcing & CQRS

---

## What & Why

### Event Sourcing
**Traditional:** Store current state only.
```sql
UPDATE accounts SET balance=500 WHERE id=1;  -- history LOST
```

**Event Sourcing:** Store sequence of events. Current state = replay of events.
```python
events = [
    {"type": "AccountOpened",   "amount": 1000},
    {"type": "MoneyDeposited",  "amount": 500},
    {"type": "MoneyWithdrawn",  "amount": 200},
]
# Current balance = 1000 + 500 - 200 = 1300
```

**Benefits:**
- Complete audit trail (every change is recorded)
- Time travel (replay events to any point in time)
- Event-driven architecture (events can trigger downstream)
- Debugging (exact sequence of what happened)

**Drawbacks:**
- Query complexity (must replay events or build projections)
- Event schema evolution (old events must still be playable)
- Storage grows indefinitely (mitigated by snapshots)

---

### CQRS (Command Query Responsibility Segregation)
Separate READ and WRITE models.

```
Command side (Write):           Query side (Read):
  POST /transfer                  GET /account/balance
  → validate                      → Read projection
  → publish event                   (pre-computed view)
  → update event store              updated via events
```

**Why separate?**
- Write model needs strong consistency, validation, business rules
- Read model needs denormalized, fast queries, possibly eventual consistency
- Scale independently (usually many more reads than writes)

---

## 1. Event Store

```python
from dataclasses import dataclass, field
from typing import Any
import json
import time
import uuid

@dataclass
class DomainEvent:
    """Base class for all domain events."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = ""
    aggregate_id: str = ""
    aggregate_type: str = ""
    sequence_number: int = 0    # monotonically increasing per aggregate
    timestamp: float = field(default_factory=time.time)
    data: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)   # user_id, correlation_id, etc.

    def to_dict(self) -> dict:
        return {
            "event_id":       self.event_id,
            "event_type":     self.event_type,
            "aggregate_id":   self.aggregate_id,
            "aggregate_type": self.aggregate_type,
            "sequence_number": self.sequence_number,
            "timestamp":      self.timestamp,
            "data":           self.data,
            "metadata":       self.metadata
        }


# Concrete events
@dataclass
class AccountOpened(DomainEvent):
    event_type: str = "AccountOpened"

@dataclass
class MoneyDeposited(DomainEvent):
    event_type: str = "MoneyDeposited"

@dataclass
class MoneyWithdrawn(DomainEvent):
    event_type: str = "MoneyWithdrawn"

@dataclass
class MoneyTransferred(DomainEvent):
    event_type: str = "MoneyTransferred"


class EventStore:
    """
    Append-only store for domain events.
    Primary key: (aggregate_id, sequence_number).
    Optimistic concurrency: reject if expected_version doesn't match.

    Schema:
      events(
        event_id        UUID PK,
        aggregate_id    TEXT,
        aggregate_type  TEXT,
        sequence_number INT,
        event_type      TEXT,
        data            JSONB,
        metadata        JSONB,
        created_at      TIMESTAMPTZ,
        UNIQUE(aggregate_id, sequence_number)
      )
    """

    async def append(self, aggregate_id: str,
                      events: list[DomainEvent],
                      expected_version: int) -> int:
        """
        Append events to aggregate's stream.
        expected_version: version before append (for optimistic locking).
        Returns new version.

        Raises ConcurrencyException if another write happened.
        """
        async with self.db.transaction():
            # Optimistic lock: check current version
            current = await self.db.query_one(
                "SELECT COALESCE(MAX(sequence_number), -1) as version "
                "FROM events WHERE aggregate_id=$1",
                aggregate_id
            )
            current_version = current["version"]

            if current_version != expected_version:
                raise ConcurrencyException(
                    f"Optimistic lock: expected version {expected_version}, "
                    f"got {current_version}"
                )

            # Assign sequence numbers
            for i, event in enumerate(events):
                event.sequence_number = expected_version + 1 + i

            # Bulk insert events
            rows = [event.to_dict() for event in events]
            await self.db.execute_many(
                "INSERT INTO events(event_id, aggregate_id, aggregate_type, "
                "sequence_number, event_type, data, metadata, created_at) "
                "VALUES($1,$2,$3,$4,$5,$6,$7,NOW())",
                [(r["event_id"], r["aggregate_id"], r["aggregate_type"],
                  r["sequence_number"], r["event_type"],
                  json.dumps(r["data"]), json.dumps(r["metadata"]))
                 for r in rows]
            )

            new_version = expected_version + len(events)

            # Publish events to Kafka for downstream projections
            for event in events:
                await self.kafka.send("domain_events", event.to_dict(),
                                       key=aggregate_id)

            return new_version

    async def load(self, aggregate_id: str,
                    from_version: int = 0) -> list[DomainEvent]:
        """Load all events for an aggregate from a given version."""
        rows = await self.db.query_many(
            "SELECT * FROM events WHERE aggregate_id=$1 "
            "AND sequence_number >= $2 ORDER BY sequence_number",
            aggregate_id, from_version
        )
        return [self._deserialize(row) for row in rows]

    async def load_by_type(self, aggregate_type: str,
                            after_timestamp: float = 0) -> list[DomainEvent]:
        """Load all events for an aggregate type (for rebuilding projections)."""
        rows = await self.db.query_many(
            "SELECT * FROM events WHERE aggregate_type=$1 AND created_at > $2 "
            "ORDER BY created_at",
            aggregate_type, after_timestamp
        )
        return [self._deserialize(row) for row in rows]

    def _deserialize(self, row: dict) -> DomainEvent:
        event_classes = {
            "AccountOpened":    AccountOpened,
            "MoneyDeposited":   MoneyDeposited,
            "MoneyWithdrawn":   MoneyWithdrawn,
            "MoneyTransferred": MoneyTransferred,
        }
        cls = event_classes.get(row["event_type"], DomainEvent)
        return cls(
            event_id=row["event_id"],
            event_type=row["event_type"],
            aggregate_id=row["aggregate_id"],
            aggregate_type=row["aggregate_type"],
            sequence_number=row["sequence_number"],
            timestamp=row["created_at"],
            data=json.loads(row["data"]),
            metadata=json.loads(row["metadata"])
        )


class ConcurrencyException(Exception):
    pass
```

---

## 2. Aggregate (Write Model)

```python
"""
Aggregate: domain object that:
1. Validates commands (business rules)
2. Emits events (state changes)
3. Applies events to update internal state

Key: aggregate only stores UNCOMMITTED events until persisted.
"""

from decimal import Decimal
from enum import Enum

class AccountStatus(Enum):
    OPEN   = "open"
    FROZEN = "frozen"
    CLOSED = "closed"

class BankAccount:
    """
    Aggregate root: bank account.
    All state changes go through events.
    """

    def __init__(self, account_id: str):
        self.account_id  = account_id
        self.balance     = Decimal("0")
        self.status      = None
        self.owner_id    = None
        self.version     = -1          # current version in event store
        self._uncommitted: list[DomainEvent] = []   # pending events

    # ── Commands (validate + emit events) ──────────────────────────

    def open(self, owner_id: str, initial_deposit: Decimal):
        """Command: open account."""
        if self.status is not None:
            raise ValueError("Account already exists")
        if initial_deposit < 0:
            raise ValueError("Initial deposit cannot be negative")

        self._emit(AccountOpened(
            aggregate_id=self.account_id,
            aggregate_type="BankAccount",
            data={"owner_id": owner_id, "initial_deposit": str(initial_deposit)}
        ))

    def deposit(self, amount: Decimal):
        """Command: deposit money."""
        if self.status != AccountStatus.OPEN:
            raise ValueError("Account is not open")
        if amount <= 0:
            raise ValueError("Deposit amount must be positive")

        self._emit(MoneyDeposited(
            aggregate_id=self.account_id,
            aggregate_type="BankAccount",
            data={"amount": str(amount)}
        ))

    def withdraw(self, amount: Decimal):
        """Command: withdraw money."""
        if self.status != AccountStatus.OPEN:
            raise ValueError("Account is not open")
        if amount <= 0:
            raise ValueError("Withdrawal amount must be positive")
        if self.balance < amount:
            raise ValueError(f"Insufficient funds: balance={self.balance}, requested={amount}")

        self._emit(MoneyWithdrawn(
            aggregate_id=self.account_id,
            aggregate_type="BankAccount",
            data={"amount": str(amount)}
        ))

    def transfer(self, to_account_id: str, amount: Decimal):
        """Command: transfer money to another account."""
        if self.status != AccountStatus.OPEN:
            raise ValueError("Account is not open")
        if self.balance < amount:
            raise ValueError("Insufficient funds for transfer")

        self._emit(MoneyTransferred(
            aggregate_id=self.account_id,
            aggregate_type="BankAccount",
            data={"to_account_id": to_account_id, "amount": str(amount)}
        ))

    # ── Apply events (update state) ──────────────────────────────

    def apply(self, event: DomainEvent):
        """Apply a single event to update aggregate state."""
        handler = {
            "AccountOpened":    self._apply_opened,
            "MoneyDeposited":   self._apply_deposited,
            "MoneyWithdrawn":   self._apply_withdrawn,
            "MoneyTransferred": self._apply_transferred,
        }.get(event.event_type)

        if handler:
            handler(event)
        self.version = event.sequence_number

    def _apply_opened(self, event: DomainEvent):
        self.owner_id = event.data["owner_id"]
        self.balance  = Decimal(event.data["initial_deposit"])
        self.status   = AccountStatus.OPEN

    def _apply_deposited(self, event: DomainEvent):
        self.balance += Decimal(event.data["amount"])

    def _apply_withdrawn(self, event: DomainEvent):
        self.balance -= Decimal(event.data["amount"])

    def _apply_transferred(self, event: DomainEvent):
        self.balance -= Decimal(event.data["amount"])

    # ── Infrastructure helpers ────────────────────────────────────

    def _emit(self, event: DomainEvent):
        """Apply event to self + add to uncommitted list."""
        self.apply(event)
        self._uncommitted.append(event)

    def get_uncommitted_events(self) -> list[DomainEvent]:
        return list(self._uncommitted)

    def mark_events_committed(self):
        self._uncommitted.clear()

    @classmethod
    def from_events(cls, account_id: str,
                     events: list[DomainEvent]) -> "BankAccount":
        """Reconstruct aggregate from event history."""
        account = cls(account_id)
        for event in events:
            account.apply(event)
        return account
```

---

## 3. Command Handler & Repository

```python
class AccountRepository:
    """Load and save aggregates via event store."""

    def __init__(self, event_store: EventStore):
        self.event_store = event_store
        self.snapshot_store = SnapshotStore()

    async def load(self, account_id: str) -> BankAccount:
        """Load aggregate, using snapshot if available for performance."""
        # Try snapshot first
        snapshot = await self.snapshot_store.get_latest(account_id)
        from_version = 0
        account = BankAccount(account_id)

        if snapshot:
            account = snapshot["state"]
            from_version = snapshot["version"] + 1

        # Load events since snapshot
        events = await self.event_store.load(account_id, from_version)
        for event in events:
            account.apply(event)

        return account

    async def save(self, account: BankAccount) -> int:
        """Persist uncommitted events to event store."""
        events = account.get_uncommitted_events()
        if not events:
            return account.version

        expected_version = account.version - len(events)
        new_version = await self.event_store.append(
            account.account_id, events, expected_version
        )
        account.mark_events_committed()

        # Create snapshot every 50 events
        if new_version % 50 == 0:
            await self.snapshot_store.save(account.account_id, new_version, account)

        return new_version


class AccountCommandHandler:
    """Handles commands: validate, load aggregate, execute, save."""

    def __init__(self, repository: AccountRepository):
        self.repo = repository

    async def handle_open_account(self, command: dict) -> str:
        account = BankAccount(command["account_id"])
        account.open(
            owner_id=command["owner_id"],
            initial_deposit=Decimal(str(command["initial_deposit"]))
        )
        await self.repo.save(account)
        return account.account_id

    async def handle_deposit(self, command: dict):
        account = await self.repo.load(command["account_id"])
        account.deposit(Decimal(str(command["amount"])))
        await self.repo.save(account)

    async def handle_withdraw(self, command: dict):
        account = await self.repo.load(command["account_id"])
        account.withdraw(Decimal(str(command["amount"])))
        await self.repo.save(account)

    async def handle_transfer(self, command: dict):
        """Transfer: update source account only. Target handled by event handler."""
        account = await self.repo.load(command["from_account_id"])
        account.transfer(
            to_account_id=command["to_account_id"],
            amount=Decimal(str(command["amount"]))
        )
        await self.repo.save(account)
```

---

## 4. Projections (Read Model)

```python
"""
Projection: event handler that builds read-optimized views.
Separate database/table from event store (CQRS read side).
Multiple projections can be built from the same events.
"""

class AccountBalanceProjection:
    """
    Read model: fast balance lookup.
    Updated by consuming domain_events Kafka topic.
    """

    async def handle(self, event: DomainEvent):
        """Route event to appropriate handler."""
        handlers = {
            "AccountOpened":    self._on_account_opened,
            "MoneyDeposited":   self._on_deposited,
            "MoneyWithdrawn":   self._on_withdrawn,
            "MoneyTransferred": self._on_transferred,
        }
        handler = handlers.get(event.event_type)
        if handler:
            await handler(event)

    async def _on_account_opened(self, event: DomainEvent):
        await self.read_db.execute(
            "INSERT INTO account_balances(account_id, owner_id, balance, status) "
            "VALUES($1,$2,$3,'open')",
            event.aggregate_id,
            event.data["owner_id"],
            event.data["initial_deposit"]
        )

    async def _on_deposited(self, event: DomainEvent):
        await self.read_db.execute(
            "UPDATE account_balances SET balance = balance + $2 WHERE account_id=$1",
            event.aggregate_id, event.data["amount"]
        )

    async def _on_withdrawn(self, event: DomainEvent):
        await self.read_db.execute(
            "UPDATE account_balances SET balance = balance - $2 WHERE account_id=$1",
            event.aggregate_id, event.data["amount"]
        )

    async def _on_transferred(self, event: DomainEvent):
        await self.read_db.execute(
            "UPDATE account_balances SET balance = balance - $2 WHERE account_id=$1",
            event.aggregate_id, event.data["amount"]
        )
        # Target account credited by a separate event consumer listening
        # for MoneyTransferred and applying to to_account_id

    async def query_balance(self, account_id: str) -> dict:
        """Fast balance query — no event replay needed."""
        return await self.read_db.query_one(
            "SELECT account_id, balance, status FROM account_balances WHERE account_id=$1",
            account_id
        )


class TransactionHistoryProjection:
    """
    Read model: transaction history for a user.
    Different read model from the same events.
    """

    async def handle(self, event: DomainEvent):
        if event.event_type in ("MoneyDeposited", "MoneyWithdrawn", "MoneyTransferred"):
            await self.read_db.execute(
                "INSERT INTO transaction_history(txn_id, account_id, event_type, "
                "amount, created_at) VALUES($1,$2,$3,$4,$5)",
                event.event_id, event.aggregate_id, event.event_type,
                event.data.get("amount"), event.timestamp
            )

    async def get_history(self, account_id: str, limit: int = 50) -> list[dict]:
        return await self.read_db.query_many(
            "SELECT * FROM transaction_history WHERE account_id=$1 "
            "ORDER BY created_at DESC LIMIT $2",
            account_id, limit
        )
```

---

## 5. Snapshots (Performance Optimization)

```python
"""
Problem: replaying 100,000 events to get current state is slow.
Solution: snapshot current state every N events.
Load: snapshot → apply only events after snapshot.
"""

import pickle

class SnapshotStore:
    """Stores aggregate state snapshots for fast loading."""

    SNAPSHOT_INTERVAL = 50   # create snapshot every 50 events

    async def save(self, aggregate_id: str, version: int,
                    aggregate: BankAccount):
        """Serialize and store aggregate state as snapshot."""
        state = {
            "account_id": aggregate.account_id,
            "balance":    str(aggregate.balance),
            "status":     aggregate.status.value if aggregate.status else None,
            "owner_id":   aggregate.owner_id,
        }
        await self.db.execute(
            "INSERT INTO snapshots(aggregate_id, version, state, created_at) "
            "VALUES($1,$2,$3,NOW()) "
            "ON CONFLICT(aggregate_id) DO UPDATE SET version=$2, state=$3, created_at=NOW()",
            aggregate_id, version, json.dumps(state)
        )

    async def get_latest(self, aggregate_id: str) -> dict | None:
        row = await self.db.query_one(
            "SELECT version, state FROM snapshots WHERE aggregate_id=$1",
            aggregate_id
        )
        if not row:
            return None

        state_data = json.loads(row["state"])
        account = BankAccount(aggregate_id)
        account.balance  = Decimal(state_data["balance"])
        account.status   = AccountStatus(state_data["status"]) if state_data["status"] else None
        account.owner_id = state_data["owner_id"]
        account.version  = row["version"]

        return {"state": account, "version": row["version"]}
```

---

## 6. Architecture Diagram

```
Write Side (Command):                Read Side (Query):
                                      
Client → POST /accounts/transfer      Client → GET /accounts/{id}/balance
    │                                     │
    ▼                                     ▼
CommandHandler                        QueryHandler
    │                                     │
    ▼                                     ▼
BankAccount (Aggregate)             AccountBalanceProjection
    │   validate + emit events           │   (pre-built read model)
    ▼                                     │
EventStore (PostgreSQL)              Read DB (PostgreSQL/Redis)
    │                                     ▲
    └──── Kafka ──────────────────────────┘
           domain_events topic
           (async, eventually consistent)
```

---

## 7. Interview Questions

**Q1: What is Event Sourcing and how is it different from traditional CRUD?**
> Traditional CRUD stores only current state (balance=500), losing history. Event Sourcing stores every change as an immutable event (AccountOpened, MoneyDeposited, MoneyWithdrawn). Current state = replay of all events. Benefits: complete audit trail, time travel (what was the balance 3 months ago?), easy event-driven integration, debuggability. Drawback: query complexity requires projections.

**Q2: What is CQRS and why combine it with Event Sourcing?**
> CQRS: separate read and write models. Write model: event-sourced aggregate handles commands, enforces business rules. Read model: denormalized projections optimized for specific queries. They complement each other: event sourcing makes it natural to derive multiple read models from the same events. Each read model can be rebuilt by replaying events. Scale independently — read models can use Redis, Elasticsearch, or any specialized store.

**Q3: How do you handle schema evolution (changing event structure)?**
> Strategies: (1) Additive changes: add optional fields — existing events still deserializable. (2) Version events: `MoneyDeposited_v2` with migration code for `MoneyDeposited_v1`. (3) Upcasting: when loading old events, transform to new format on the fly. (4) Never delete events — only append. Key: event schema is a public contract, treat like API versioning.

**Q4: What are projections and how are they rebuilt?**
> Projection: event handler that builds a read-optimized view by consuming domain events. Balance projection: listen for MoneyDeposited/Withdrawn events, maintain current balance. To rebuild: reset the read model (clear DB table), replay all events from Kafka/event store. During rebuild: serve old projection (stale), swap atomically when rebuild complete. Multiple projections from same events = different read models (balance, history, statements).

**Q5: How does optimistic concurrency work in an event store?**
> Each aggregate has a version (sequence number of last event). When writing: "I expect version N" → check current version is N → if not, another writer modified it → throw ConcurrencyException → caller retries. Similar to database optimistic locking with `WHERE version=$expected`. Prevents lost updates when two requests try to modify the same aggregate concurrently.

**Q6: What is the snapshot pattern and when should you use it?**
> After N events (e.g., 50), save the current aggregate state as a snapshot. On load: fetch latest snapshot + only events after snapshot's version. Without snapshots: 100,000 events = 100,000 DB rows loaded and replayed per request. With snapshots: load 1 snapshot row + last 50 events. Trade-off: snapshot storage overhead vs. load time. Use when: aggregate lives long and accumulates many events (bank account, customer record).
