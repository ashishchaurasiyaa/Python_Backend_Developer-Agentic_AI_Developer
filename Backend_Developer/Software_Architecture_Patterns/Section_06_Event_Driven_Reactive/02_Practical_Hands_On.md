# Lecture 2 — Practical Hands-On: Event Sourcing & CQRS

> **Theory file:** [02_Event_Sourcing_CQRS.md](02_Event_Sourcing_CQRS.md)

---

## 🎯 Is Practical Mein Kya Banayenge?

Full Event Sourcing + CQRS system:

1. ✅ **Event Store** in PostgreSQL with optimistic concurrency
2. ✅ **Aggregate** pattern with event replay
3. ✅ **Command handlers** (write side)
4. ✅ **Projections** (read side)
5. ✅ **Multiple read models** from same events
6. ✅ **Snapshots** for performance
7. ✅ **Up-casters** for event versioning
8. ✅ **Eventual consistency** demo
9. ✅ **Replayable projections** to rebuild views
10. ✅ **Banking account** example end-to-end

By end: aap **production-ready ES + CQRS** system bana sakte ho.

---

## 1. Project Structure

```
es_cqrs_demo/
├── docker-compose.yml
├── README.md
│
├── domain/
│   ├── events.py           # Domain events
│   ├── commands.py         # Commands
│   ├── aggregates.py       # Aggregates (Account, Order)
│   └── exceptions.py
│
├── event_store/
│   ├── postgres_store.py
│   ├── snapshots.py
│   └── upcaster.py
│
├── write_side/
│   ├── command_handler.py
│   └── repository.py
│
├── read_side/
│   ├── projections/
│   │   ├── account_balance.py
│   │   ├── transaction_history.py
│   │   ├── monthly_report.py
│   │   └── fraud_detector.py
│   └── query_handler.py
│
├── api/
│   ├── commands_api.py
│   └── queries_api.py
│
└── tests/
    ├── test_aggregates.py
    └── test_projections.py
```

---

## 2. Setup

```bash
pip install fastapi uvicorn
pip install asyncpg
pip install pydantic
pip install python-dateutil
```

### `docker-compose.yml`

```yaml
version: '3.8'
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app
      POSTGRES_DB: es_cqrs
    ports: ["5432:5432"]
    volumes:
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
```

### `init.sql` — Database Schema

```sql
-- ─────────────────────────────────────────────────────────────
-- EVENT STORE (append-only)
-- ─────────────────────────────────────────────────────────────
CREATE SCHEMA event_store;

CREATE TABLE event_store.events (
    sequence_number BIGSERIAL PRIMARY KEY,
    stream_id VARCHAR NOT NULL,
    stream_version INTEGER NOT NULL,
    event_type VARCHAR NOT NULL,
    event_data JSONB NOT NULL,
    metadata JSONB,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Optimistic concurrency control
    UNIQUE (stream_id, stream_version)
);

CREATE INDEX idx_stream ON event_store.events (stream_id, stream_version);
CREATE INDEX idx_event_type ON event_store.events (event_type, timestamp);

-- ─────────────────────────────────────────────────────────────
-- SNAPSHOTS (for performance)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE event_store.snapshots (
    stream_id VARCHAR PRIMARY KEY,
    version INTEGER NOT NULL,
    state JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────
-- READ MODELS (separate schema for clear separation)
-- ─────────────────────────────────────────────────────────────
CREATE SCHEMA read_models;

CREATE TABLE read_models.account_balances (
    account_id VARCHAR PRIMARY KEY,
    owner_name VARCHAR NOT NULL,
    balance NUMERIC(20, 4) NOT NULL,
    status VARCHAR NOT NULL,
    last_updated TIMESTAMPTZ NOT NULL
);

CREATE TABLE read_models.transaction_history (
    id BIGSERIAL PRIMARY KEY,
    account_id VARCHAR NOT NULL,
    transaction_id VARCHAR NOT NULL,
    type VARCHAR NOT NULL,
    amount NUMERIC(20, 4) NOT NULL,
    balance_after NUMERIC(20, 4),
    timestamp TIMESTAMPTZ NOT NULL,
    
    UNIQUE (transaction_id)
);

CREATE INDEX idx_account_txn ON read_models.transaction_history (account_id, timestamp DESC);

CREATE TABLE read_models.monthly_summary (
    account_id VARCHAR NOT NULL,
    year_month VARCHAR NOT NULL,
    total_deposits NUMERIC(20, 4) NOT NULL DEFAULT 0,
    total_withdrawals NUMERIC(20, 4) NOT NULL DEFAULT 0,
    transaction_count INTEGER NOT NULL DEFAULT 0,
    
    PRIMARY KEY (account_id, year_month)
);

-- ─────────────────────────────────────────────────────────────
-- PROJECTION CHECKPOINTS (track replay position)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE event_store.projection_checkpoints (
    projection_name VARCHAR PRIMARY KEY,
    last_sequence INTEGER NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## 3. 📜 Domain Events

### `domain/events.py`

```python
"""
Banking domain events.
Past tense, immutable, descriptive.
"""
from pydantic import BaseModel
from datetime import datetime
from typing import Literal
import uuid

class BaseEvent(BaseModel):
    event_id: str = uuid.uuid4().hex
    event_type: str
    version: str = "v1"
    timestamp: datetime = datetime.utcnow()
    
    class Config:
        frozen = True  # Immutable!

class AccountOpenedEvent(BaseEvent):
    event_type: Literal["AccountOpened"] = "AccountOpened"
    
    account_id: str
    owner_name: str
    initial_deposit: float

class MoneyDepositedEvent(BaseEvent):
    event_type: Literal["MoneyDeposited"] = "MoneyDeposited"
    
    account_id: str
    transaction_id: str
    amount: float
    source: str  # "ATM", "BANK_TRANSFER", etc.

class MoneyWithdrawnEvent(BaseEvent):
    event_type: Literal["MoneyWithdrawn"] = "MoneyWithdrawn"
    
    account_id: str
    transaction_id: str
    amount: float
    destination: str

class AccountFrozenEvent(BaseEvent):
    event_type: Literal["AccountFrozen"] = "AccountFrozen"
    
    account_id: str
    reason: str
    frozen_by: str

class AccountClosedEvent(BaseEvent):
    event_type: Literal["AccountClosed"] = "AccountClosed"
    
    account_id: str
    closing_balance: float
    closed_by: str
```

---

## 4. 🏗 Aggregate (Write Side)

### `domain/aggregates.py`

```python
"""
Account aggregate - the heart of the write side.
"""
from typing import List
from datetime import datetime
import uuid
from .events import (
    BaseEvent,
    AccountOpenedEvent,
    MoneyDepositedEvent,
    MoneyWithdrawnEvent,
    AccountFrozenEvent,
    AccountClosedEvent,
)

class AccountAggregate:
    """
    Account business logic + state.
    State is derived from events.
    """
    
    def __init__(self):
        # State (initially empty)
        self.id: str = None
        self.owner_name: str = None
        self.balance: float = 0
        self.status: str = None
        self.version: int = 0
        
        # New events to be persisted
        self._uncommitted_events: List[BaseEvent] = []
    
    # ─────────────────────────────────────────────────────────
    # COMMAND METHODS (the "do something" actions)
    # ─────────────────────────────────────────────────────────
    def open_account(self, owner_name: str, initial_deposit: float = 0):
        """Open a new account"""
        if self.status is not None:
            raise ValueError("Account already exists")
        
        if initial_deposit < 0:
            raise ValueError("Initial deposit cannot be negative")
        
        # Emit event (don't update state directly!)
        self._apply(AccountOpenedEvent(
            account_id=str(uuid.uuid4()),
            owner_name=owner_name,
            initial_deposit=initial_deposit,
        ))
    
    def deposit(self, amount: float, source: str):
        """Deposit money"""
        self._ensure_active()
        
        if amount <= 0:
            raise ValueError("Deposit amount must be positive")
        
        self._apply(MoneyDepositedEvent(
            account_id=self.id,
            transaction_id=str(uuid.uuid4()),
            amount=amount,
            source=source,
        ))
    
    def withdraw(self, amount: float, destination: str):
        """Withdraw money"""
        self._ensure_active()
        
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        if self.balance < amount:
            raise ValueError(f"Insufficient balance. Available: {self.balance}, requested: {amount}")
        
        self._apply(MoneyWithdrawnEvent(
            account_id=self.id,
            transaction_id=str(uuid.uuid4()),
            amount=amount,
            destination=destination,
        ))
    
    def freeze(self, reason: str, frozen_by: str):
        """Freeze account (anti-fraud)"""
        self._ensure_active()
        
        self._apply(AccountFrozenEvent(
            account_id=self.id,
            reason=reason,
            frozen_by=frozen_by,
        ))
    
    def close(self, closed_by: str):
        """Close account"""
        if self.status == "CLOSED":
            raise ValueError("Already closed")
        
        if self.balance != 0:
            raise ValueError(f"Cannot close with non-zero balance: {self.balance}")
        
        self._apply(AccountClosedEvent(
            account_id=self.id,
            closing_balance=self.balance,
            closed_by=closed_by,
        ))
    
    # ─────────────────────────────────────────────────────────
    # EVENT APPLICATION (updates state)
    # ─────────────────────────────────────────────────────────
    def _apply(self, event: BaseEvent):
        """Apply event to state + track for persistence"""
        self._mutate(event)
        self._uncommitted_events.append(event)
        self.version += 1
    
    def _mutate(self, event: BaseEvent):
        """State machine - update state based on event type"""
        if isinstance(event, AccountOpenedEvent):
            self.id = event.account_id
            self.owner_name = event.owner_name
            self.balance = event.initial_deposit
            self.status = "ACTIVE"
        
        elif isinstance(event, MoneyDepositedEvent):
            self.balance += event.amount
        
        elif isinstance(event, MoneyWithdrawnEvent):
            self.balance -= event.amount
        
        elif isinstance(event, AccountFrozenEvent):
            self.status = "FROZEN"
        
        elif isinstance(event, AccountClosedEvent):
            self.status = "CLOSED"
    
    # ─────────────────────────────────────────────────────────
    # REHYDRATION (rebuild from events)
    # ─────────────────────────────────────────────────────────
    @classmethod
    def from_events(cls, events: List[BaseEvent]) -> "AccountAggregate":
        """Rebuild aggregate from event history"""
        account = cls()
        for event in events:
            account._mutate(event)
            account.version += 1
        return account
    
    # ─────────────────────────────────────────────────────────
    # UTILITIES
    # ─────────────────────────────────────────────────────────
    def _ensure_active(self):
        if self.status is None:
            raise ValueError("Account doesn't exist")
        if self.status == "FROZEN":
            raise ValueError("Account is frozen")
        if self.status == "CLOSED":
            raise ValueError("Account is closed")
    
    def get_uncommitted_events(self) -> List[BaseEvent]:
        """Get new events to persist"""
        return self._uncommitted_events.copy()
    
    def mark_committed(self):
        """Clear uncommitted events after persistence"""
        self._uncommitted_events.clear()
```

---

## 5. 💾 Event Store

### `event_store/postgres_store.py`

```python
"""
PostgreSQL-based event store with optimistic concurrency.
"""
import asyncpg
import json
from typing import List, Optional
from domain.events import BaseEvent
import importlib

class PostgresEventStore:
    """
    Event store with:
    - Append-only writes
    - Optimistic concurrency control
    - Stream-based reads
    - Real-time subscriptions
    """
    
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool
    
    async def append(
        self,
        stream_id: str,
        events: List[BaseEvent],
        expected_version: int,
    ) -> int:
        """
        Append events to stream.
        Raises ConcurrencyError if version mismatch.
        """
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Check current version (optimistic concurrency)
                row = await conn.fetchrow("""
                    SELECT COALESCE(MAX(stream_version), 0) as version
                    FROM event_store.events
                    WHERE stream_id = $1
                """, stream_id)
                
                current_version = row["version"]
                
                if current_version != expected_version:
                    raise ConcurrencyError(
                        f"Stream version mismatch. Expected: {expected_version}, "
                        f"Actual: {current_version}"
                    )
                
                # Insert events
                for i, event in enumerate(events):
                    new_version = expected_version + i + 1
                    await conn.execute("""
                        INSERT INTO event_store.events
                            (stream_id, stream_version, event_type, event_data, timestamp)
                        VALUES ($1, $2, $3, $4, $5)
                    """,
                        stream_id,
                        new_version,
                        event.event_type,
                        json.dumps(event.dict(), default=str),
                        event.timestamp,
                    )
                
                # Notify subscribers (LISTEN/NOTIFY)
                await conn.execute(
                    f"NOTIFY events_channel, '{stream_id}'"
                )
                
                return expected_version + len(events)
    
    async def load_stream(self, stream_id: str) -> List[BaseEvent]:
        """Load all events for a stream"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT event_type, event_data
                FROM event_store.events
                WHERE stream_id = $1
                ORDER BY stream_version ASC
            """, stream_id)
            
            return [self._deserialize(row) for row in rows]
    
    async def load_from_sequence(
        self,
        from_sequence: int,
        limit: int = 1000,
    ) -> List[tuple]:
        """Load events globally from a sequence number (for projections)"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT sequence_number, stream_id, event_type, event_data, timestamp
                FROM event_store.events
                WHERE sequence_number > $1
                ORDER BY sequence_number ASC
                LIMIT $2
            """, from_sequence, limit)
            
            return [
                (
                    row["sequence_number"],
                    row["stream_id"],
                    self._deserialize(row),
                )
                for row in rows
            ]
    
    def _deserialize(self, row) -> BaseEvent:
        """Reconstruct event object from DB row"""
        event_data = json.loads(row["event_data"]) if isinstance(row["event_data"], str) else row["event_data"]
        event_type = row["event_type"]
        
        # Map event type to class
        from domain import events as events_module
        event_class = getattr(events_module, f"{event_type}Event", None)
        if not event_class:
            raise ValueError(f"Unknown event type: {event_type}")
        
        return event_class(**event_data)

class ConcurrencyError(Exception):
    pass
```

---

## 6. 📷 Snapshots (Performance Optimization)

### `event_store/snapshots.py`

```python
"""
Snapshots for fast aggregate reconstruction.
"""
import json
import asyncpg
from typing import Optional

class SnapshotStore:
    """
    Stores periodic snapshots of aggregate state.
    Avoids replaying 1000s of events.
    """
    
    SNAPSHOT_EVERY_N = 50  # Take snapshot every 50 events
    
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool
    
    async def save_snapshot(
        self,
        stream_id: str,
        version: int,
        state: dict,
    ):
        """Save snapshot of current state"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO event_store.snapshots (stream_id, version, state)
                VALUES ($1, $2, $3)
                ON CONFLICT (stream_id) DO UPDATE
                SET version = EXCLUDED.version,
                    state = EXCLUDED.state,
                    created_at = NOW()
            """, stream_id, version, json.dumps(state, default=str))
    
    async def load_snapshot(self, stream_id: str) -> Optional[dict]:
        """Load most recent snapshot"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT version, state
                FROM event_store.snapshots
                WHERE stream_id = $1
            """, stream_id)
            
            if not row:
                return None
            
            return {
                "version": row["version"],
                "state": json.loads(row["state"]) if isinstance(row["state"], str) else row["state"],
            }
```

### Repository Using Snapshots

```python
"""
Repository combining snapshots + event store.
"""
from domain.aggregates import AccountAggregate

class AccountRepository:
    """Loads + saves aggregates with snapshot optimization"""
    
    def __init__(self, event_store, snapshot_store):
        self.event_store = event_store
        self.snapshot_store = snapshot_store
    
    async def load(self, account_id: str) -> AccountAggregate:
        """Load aggregate (snapshot + events since)"""
        stream_id = f"account-{account_id}"
        
        # Try snapshot first
        snapshot = await self.snapshot_store.load_snapshot(stream_id)
        
        account = AccountAggregate()
        from_version = 0
        
        if snapshot:
            # Restore from snapshot
            state = snapshot["state"]
            account.id = state.get("id")
            account.owner_name = state.get("owner_name")
            account.balance = state.get("balance", 0)
            account.status = state.get("status")
            account.version = snapshot["version"]
            from_version = snapshot["version"]
        
        # Replay events since snapshot
        all_events = await self.event_store.load_stream(stream_id)
        events_since = all_events[from_version:]
        
        for event in events_since:
            account._mutate(event)
            account.version += 1
        
        return account
    
    async def save(self, account: AccountAggregate):
        """Save uncommitted events + maybe snapshot"""
        stream_id = f"account-{account.id}"
        new_events = account.get_uncommitted_events()
        
        if not new_events:
            return
        
        # Append events
        new_version = await self.event_store.append(
            stream_id=stream_id,
            events=new_events,
            expected_version=account.version - len(new_events),
        )
        
        account.mark_committed()
        
        # Maybe save snapshot
        if new_version % SnapshotStore.SNAPSHOT_EVERY_N == 0:
            await self.snapshot_store.save_snapshot(
                stream_id=stream_id,
                version=new_version,
                state={
                    "id": account.id,
                    "owner_name": account.owner_name,
                    "balance": account.balance,
                    "status": account.status,
                }
            )
```

---

## 7. 📤 Command Handlers (Write Side)

### `write_side/command_handler.py`

```python
"""
Command handlers - the API into the write side.
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Banking - Write Side")

# Initialize dependencies
event_store = PostgresEventStore(pool)
snapshot_store = SnapshotStore(pool)
repository = AccountRepository(event_store, snapshot_store)

# ─────────────────────────────────────────────────────────────
# COMMAND MODELS
# ─────────────────────────────────────────────────────────────
class OpenAccountCommand(BaseModel):
    owner_name: str
    initial_deposit: float = 0

class DepositCommand(BaseModel):
    amount: float
    source: str

class WithdrawCommand(BaseModel):
    amount: float
    destination: str

# ─────────────────────────────────────────────────────────────
# HANDLERS
# ─────────────────────────────────────────────────────────────
@app.post("/accounts")
async def open_account(cmd: OpenAccountCommand):
    """Open a new account"""
    try:
        # Create fresh aggregate
        account = AccountAggregate()
        
        # Execute command
        account.open_account(cmd.owner_name, cmd.initial_deposit)
        
        # Persist events
        await repository.save(account)
        
        return {"account_id": account.id}
    
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.post("/accounts/{account_id}/deposit")
async def deposit(account_id: str, cmd: DepositCommand):
    """Deposit money"""
    try:
        # Load aggregate from events
        account = await repository.load(account_id)
        
        # Execute command
        account.deposit(cmd.amount, cmd.source)
        
        # Persist
        await repository.save(account)
        
        return {"new_balance": account.balance}
    
    except (ValueError, ConcurrencyError) as e:
        raise HTTPException(400, str(e))

@app.post("/accounts/{account_id}/withdraw")
async def withdraw(account_id: str, cmd: WithdrawCommand):
    """Withdraw money"""
    try:
        account = await repository.load(account_id)
        account.withdraw(cmd.amount, cmd.destination)
        await repository.save(account)
        return {"new_balance": account.balance}
    
    except ValueError as e:
        raise HTTPException(400, str(e))
```

---

## 8. 📊 Projections (Read Side)

### `read_side/projections/account_balance.py`

```python
"""
Projection: current account balances.
"""
import asyncpg

class AccountBalanceProjection:
    """
    Maintains current balance for fast queries.
    Updated from events.
    """
    
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool
    
    async def handle(self, event):
        async with self.pool.acquire() as conn:
            if event.event_type == "AccountOpened":
                await conn.execute("""
                    INSERT INTO read_models.account_balances
                        (account_id, owner_name, balance, status, last_updated)
                    VALUES ($1, $2, $3, 'ACTIVE', $4)
                """, event.account_id, event.owner_name, event.initial_deposit, event.timestamp)
            
            elif event.event_type == "MoneyDeposited":
                await conn.execute("""
                    UPDATE read_models.account_balances
                    SET balance = balance + $1, last_updated = $2
                    WHERE account_id = $3
                """, event.amount, event.timestamp, event.account_id)
            
            elif event.event_type == "MoneyWithdrawn":
                await conn.execute("""
                    UPDATE read_models.account_balances
                    SET balance = balance - $1, last_updated = $2
                    WHERE account_id = $3
                """, event.amount, event.timestamp, event.account_id)
            
            elif event.event_type == "AccountFrozen":
                await conn.execute("""
                    UPDATE read_models.account_balances
                    SET status = 'FROZEN', last_updated = $1
                    WHERE account_id = $2
                """, event.timestamp, event.account_id)
            
            elif event.event_type == "AccountClosed":
                await conn.execute("""
                    UPDATE read_models.account_balances
                    SET status = 'CLOSED', last_updated = $1
                    WHERE account_id = $2
                """, event.timestamp, event.account_id)
```

### `read_side/projections/transaction_history.py`

```python
"""
Projection: detailed transaction history.
"""
class TransactionHistoryProjection:
    """Track every transaction with running balance"""
    
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool
    
    async def handle(self, event):
        async with self.pool.acquire() as conn:
            if event.event_type == "AccountOpened":
                if event.initial_deposit > 0:
                    await conn.execute("""
                        INSERT INTO read_models.transaction_history
                            (account_id, transaction_id, type, amount, balance_after, timestamp)
                        VALUES ($1, $2, 'INITIAL_DEPOSIT', $3, $3, $4)
                        ON CONFLICT (transaction_id) DO NOTHING
                    """,
                        event.account_id,
                        f"INIT-{event.account_id}",
                        event.initial_deposit,
                        event.timestamp,
                    )
            
            elif event.event_type == "MoneyDeposited":
                # Get current balance
                balance = await conn.fetchval("""
                    SELECT balance FROM read_models.account_balances 
                    WHERE account_id = $1
                """, event.account_id)
                
                await conn.execute("""
                    INSERT INTO read_models.transaction_history
                        (account_id, transaction_id, type, amount, balance_after, timestamp)
                    VALUES ($1, $2, 'DEPOSIT', $3, $4, $5)
                    ON CONFLICT (transaction_id) DO NOTHING
                """,
                    event.account_id,
                    event.transaction_id,
                    event.amount,
                    balance + event.amount,
                    event.timestamp,
                )
            
            elif event.event_type == "MoneyWithdrawn":
                balance = await conn.fetchval("""
                    SELECT balance FROM read_models.account_balances 
                    WHERE account_id = $1
                """, event.account_id)
                
                await conn.execute("""
                    INSERT INTO read_models.transaction_history
                        (account_id, transaction_id, type, amount, balance_after, timestamp)
                    VALUES ($1, $2, 'WITHDRAWAL', $3, $4, $5)
                    ON CONFLICT (transaction_id) DO NOTHING
                """,
                    event.account_id,
                    event.transaction_id,
                    event.amount,
                    balance - event.amount,
                    event.timestamp,
                )
```

### `read_side/projections/monthly_report.py`

```python
"""
Projection: monthly aggregated summary.
Notice - same events but DIFFERENT view!
"""
class MonthlySummaryProjection:
    """Aggregate by month for reporting"""
    
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool
    
    async def handle(self, event):
        if event.event_type not in ["MoneyDeposited", "MoneyWithdrawn"]:
            return
        
        async with self.pool.acquire() as conn:
            year_month = event.timestamp.strftime("%Y-%m")
            
            if event.event_type == "MoneyDeposited":
                await conn.execute("""
                    INSERT INTO read_models.monthly_summary
                        (account_id, year_month, total_deposits, transaction_count)
                    VALUES ($1, $2, $3, 1)
                    ON CONFLICT (account_id, year_month)
                    DO UPDATE SET
                        total_deposits = read_models.monthly_summary.total_deposits + EXCLUDED.total_deposits,
                        transaction_count = read_models.monthly_summary.transaction_count + 1
                """, event.account_id, year_month, event.amount)
            
            elif event.event_type == "MoneyWithdrawn":
                await conn.execute("""
                    INSERT INTO read_models.monthly_summary
                        (account_id, year_month, total_withdrawals, transaction_count)
                    VALUES ($1, $2, $3, 1)
                    ON CONFLICT (account_id, year_month)
                    DO UPDATE SET
                        total_withdrawals = read_models.monthly_summary.total_withdrawals + EXCLUDED.total_withdrawals,
                        transaction_count = read_models.monthly_summary.transaction_count + 1
                """, event.account_id, year_month, event.amount)
```

---

## 9. 🏃 Projection Runner

### Background Process Replaying Events

```python
"""
Run all projections - keeps read models up to date.
"""
import asyncio
import asyncpg

class ProjectionRunner:
    def __init__(self, pool, projections: list):
        self.pool = pool
        self.projections = projections
    
    async def run(self):
        """Run forever, processing new events"""
        while True:
            try:
                processed = await self._process_batch()
                if processed == 0:
                    # No new events - wait
                    await asyncio.sleep(1)
            except Exception as e:
                print(f"Projection error: {e}")
                await asyncio.sleep(5)
    
    async def _process_batch(self) -> int:
        """Process one batch of events for each projection"""
        total_processed = 0
        
        for projection in self.projections:
            projection_name = projection.__class__.__name__
            
            async with self.pool.acquire() as conn:
                # Get last processed sequence
                last_seq = await conn.fetchval("""
                    SELECT last_sequence FROM event_store.projection_checkpoints
                    WHERE projection_name = $1
                """, projection_name) or 0
                
                # Fetch new events
                rows = await conn.fetch("""
                    SELECT sequence_number, event_type, event_data
                    FROM event_store.events
                    WHERE sequence_number > $1
                    ORDER BY sequence_number ASC
                    LIMIT 100
                """, last_seq)
                
                if not rows:
                    continue
                
                # Process each event
                for row in rows:
                    event = self._deserialize(row)
                    await projection.handle(event)
                    
                    # Update checkpoint
                    await conn.execute("""
                        INSERT INTO event_store.projection_checkpoints
                            (projection_name, last_sequence)
                        VALUES ($1, $2)
                        ON CONFLICT (projection_name)
                        DO UPDATE SET last_sequence = EXCLUDED.last_sequence,
                                     updated_at = NOW()
                    """, projection_name, row["sequence_number"])
                
                total_processed += len(rows)
        
        return total_processed
    
    def _deserialize(self, row):
        # Same as event store deserialize
        ...

# ─────────────────────────────────────────────────────────────
# RUN ALL PROJECTIONS
# ─────────────────────────────────────────────────────────────
async def main():
    pool = await asyncpg.create_pool("postgresql://app:app@localhost/es_cqrs")
    
    projections = [
        AccountBalanceProjection(pool),
        TransactionHistoryProjection(pool),
        MonthlySummaryProjection(pool),
    ]
    
    runner = ProjectionRunner(pool, projections)
    await runner.run()  # Forever

asyncio.run(main())
```

---

## 10. 📥 Query API (Read Side)

```python
"""
Read-side API - queries the projections.
"""
from fastapi import FastAPI, HTTPException

app = FastAPI(title="Banking - Read Side")

@app.get("/accounts/{account_id}/balance")
async def get_balance(account_id: str):
    """Fast - reads from materialized view"""
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT account_id, owner_name, balance, status
            FROM read_models.account_balances
            WHERE account_id = $1
        """, account_id)
    
    if not row:
        raise HTTPException(404, "Account not found")
    
    return dict(row)

@app.get("/accounts/{account_id}/transactions")
async def get_transactions(account_id: str, limit: int = 50):
    """Recent transactions - indexed for speed"""
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT transaction_id, type, amount, balance_after, timestamp
            FROM read_models.transaction_history
            WHERE account_id = $1
            ORDER BY timestamp DESC
            LIMIT $2
        """, account_id, limit)
    
    return [dict(row) for row in rows]

@app.get("/accounts/{account_id}/monthly-summary")
async def get_monthly_summary(account_id: str):
    """Monthly aggregated view"""
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT year_month, total_deposits, total_withdrawals, transaction_count
            FROM read_models.monthly_summary
            WHERE account_id = $1
            ORDER BY year_month DESC
        """, account_id)
    
    return [dict(row) for row in rows]
```

---

## 11. 🔄 Replayable Projections

### Rebuild Read Models from Events

```python
"""
Reset and rebuild a projection.
Useful when:
- Projection had a bug
- New projection added
- Schema changed
"""
async def rebuild_projection(projection_name: str, pool):
    print(f"Rebuilding {projection_name}...")
    
    async with pool.acquire() as conn:
        # 1. Truncate read model
        if projection_name == "AccountBalanceProjection":
            await conn.execute("TRUNCATE read_models.account_balances")
        elif projection_name == "TransactionHistoryProjection":
            await conn.execute("TRUNCATE read_models.transaction_history")
        # ... etc
        
        # 2. Reset checkpoint
        await conn.execute("""
            DELETE FROM event_store.projection_checkpoints
            WHERE projection_name = $1
        """, projection_name)
    
    print("Truncated. Restart projection runner - it will replay events.")
    # Projection runner picks up from sequence 0 → rebuilds entire view
```

---

## 12. 🧪 Testing Aggregates

```python
"""
Aggregate tests - test business rules in isolation.
"""
import pytest
from domain.aggregates import AccountAggregate

def test_open_account():
    account = AccountAggregate()
    account.open_account("Ashish", initial_deposit=1000)
    
    assert account.balance == 1000
    assert account.status == "ACTIVE"
    assert len(account.get_uncommitted_events()) == 1
    assert account.version == 1

def test_deposit():
    account = AccountAggregate()
    account.open_account("Ashish", 1000)
    
    account.deposit(500, "ATM")
    
    assert account.balance == 1500
    assert len(account.get_uncommitted_events()) == 2

def test_cant_withdraw_more_than_balance():
    account = AccountAggregate()
    account.open_account("Ashish", 1000)
    
    with pytest.raises(ValueError, match="Insufficient"):
        account.withdraw(2000, "ATM")

def test_cant_use_frozen_account():
    account = AccountAggregate()
    account.open_account("Ashish", 1000)
    account.freeze("Suspected fraud", "admin")
    
    with pytest.raises(ValueError, match="frozen"):
        account.deposit(100, "ATM")

def test_rebuild_from_events():
    """Verify replay produces same state"""
    # Original
    account1 = AccountAggregate()
    account1.open_account("Ashish", 1000)
    account1.deposit(500, "ATM")
    account1.withdraw(200, "Shopping")
    
    events = account1.get_uncommitted_events()
    
    # Rebuild from events
    account2 = AccountAggregate.from_events(events)
    
    assert account2.balance == account1.balance == 1300
    assert account2.status == account1.status
    assert account2.owner_name == account1.owner_name
```

---

## 13. 🎯 End-to-End Demo

```bash
# 1. Start infrastructure
$ docker-compose up -d postgres

# 2. Run database migrations
$ psql -U app -d es_cqrs < init.sql

# 3. Start write side
$ uvicorn write_side.command_handler:app --port 8001

# 4. Start projection runner
$ python -m read_side.projection_runner

# 5. Start read side
$ uvicorn read_side.query_handler:app --port 8002

# 6. Test full flow
# Open account
$ curl -X POST http://localhost:8001/accounts \
    -d '{"owner_name": "Ashish", "initial_deposit": 1000}'
# {"account_id": "abc-123"}

# Deposit
$ curl -X POST http://localhost:8001/accounts/abc-123/deposit \
    -d '{"amount": 500, "source": "ATM"}'

# Withdraw
$ curl -X POST http://localhost:8001/accounts/abc-123/withdraw \
    -d '{"amount": 200, "destination": "Shopping"}'

# Query balance (FAST - reads from projection)
$ curl http://localhost:8002/accounts/abc-123/balance
# {"balance": 1300, ...}

# Query transactions
$ curl http://localhost:8002/accounts/abc-123/transactions

# Query monthly summary
$ curl http://localhost:8002/accounts/abc-123/monthly-summary
```

---

## 14. Key Learnings Summary

```
✅ Event store: append-only PostgreSQL table
✅ Optimistic concurrency control with stream version
✅ Aggregate pattern: state derived from events
✅ Snapshots: skip 1000s of events
✅ Multiple projections from same events
✅ Replayable projections (rebuild from scratch)
✅ Eventual consistency (~ms latency)
✅ Different DBs for different read models
✅ Time-travel debugging via event log
✅ Full audit trail built-in

🎯 Production ES+CQRS stack:
   PostgreSQL/EventStoreDB → projections → read DBs
   Write API (commands) + Read API (queries)
   Snapshots + replay + monitoring
```

---

## 🎬 What's Next?

In **Lecture 3**, we'll explore **Reactive Principles** — responsive, resilient, elastic, message-driven systems.

> **Next lecture:** [03_Reactive_Principles.md](03_Reactive_Principles.md)

---

## 📚 Try It Yourself

1. Add **OrderAggregate** with full e-commerce events
2. Implement **multiple read models** (admin panel, mobile, search)
3. Build **time-travel debugger** UI
4. Add **event up-caster** for schema evolution
5. Implement **CDC** to stream events to Kafka
