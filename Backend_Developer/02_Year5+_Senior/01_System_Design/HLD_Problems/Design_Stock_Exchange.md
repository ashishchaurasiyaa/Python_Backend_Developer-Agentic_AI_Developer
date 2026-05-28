# Design Stock Exchange / Order Matching Engine

---

## 1. Requirements

### Functional
- Place orders (limit, market, stop, IOC, FOK).
- Cancel/modify orders.
- Match orders → produce trades.
- Order book per symbol (bids + asks).
- Market data feed (real-time quotes, trades, depth).
- Position tracking per user.
- Settlement (T+2 typical).
- Audit log of every event.

### Non-Functional
- **Latency**: matching engine < 100 μs per order.
- **Throughput**: 1M orders/sec at peak (cf. NASDAQ ~80K msg/sec).
- **Determinism**: same input → same output (replay for audit).
- **Fairness**: strict price-time priority.
- **No message loss**: every order acknowledged.
- **99.999% availability** during market hours.

---

## 2. Scale Estimation

| Metric | Number |
|---|---|
| Orders/day | 100M-1B |
| Peak orders/sec | 1M |
| Symbols traded | 5000-10000 |
| Active connections | 100K (brokers, market data subscribers) |
| Market data updates/sec | 10M (quote changes propagate) |
| Trade messages/sec | 100K |
| Settlement data | 10M trades/day × 500 bytes = 5 GB/day |

---

## 3. High-Level Architecture

```
   Brokers / Traders
        │
   ┌────▼──────┐
   │  FIX / TCP│  (low-latency direct connect, no LB)
   │  Gateway  │
   └────┬──────┘
        │
   ┌────▼──────────┐
   │ Pre-trade Risk│  (in-line checks: balance, limits)
   └────┬──────────┘
        │
   ┌────▼─────────┐
   │ Sequencer    │  (single thread per symbol, assigns seq#)
   └────┬─────────┘
        │
   ┌────▼─────────────────────────┐
   │  Matching Engine (per symbol)│   ← order book + match logic
   └────┬─────────────┬───────────┘
        │             │
   ┌────▼───┐    ┌────▼──────────┐
   │ Trade  │    │ Market Data    │
   │ Capture│    │ Publisher      │
   └────┬───┘    └────┬───────────┘
        │             │
   ┌────▼─────┐  ┌────▼──────────┐
   │ Clearing │  │ Multicast / WS │
   │ & Settle │  │  to subscribers│
   └──────────┘  └────────────────┘
```

---

## 4. Order Book Data Structure

The heart of the system.

### Structure
- **Bids**: sorted descending by price (best bid = highest).
- **Asks**: sorted ascending by price (best ask = lowest).
- **At each price level**: FIFO queue of orders (time priority).

```python
from sortedcontainers import SortedDict
from collections import deque

class PriceLevel:
    __slots__ = ('price', 'orders', 'total_qty')
    def __init__(self, price):
        self.price = price
        self.orders = deque()
        self.total_qty = 0

class OrderBook:
    def __init__(self, symbol):
        self.symbol = symbol
        self.bids = SortedDict(lambda p: -p)   # max-heap behavior
        self.asks = SortedDict()                # min-heap behavior

    def add_limit(self, order):
        side = self.bids if order.side == 'B' else self.asks
        if order.price not in side:
            side[order.price] = PriceLevel(order.price)
        level = side[order.price]
        level.orders.append(order)
        level.total_qty += order.qty
```

In production: tree (red-black) for log(N) insertion, or array for hot price levels.

**Why deque per level:** O(1) FIFO add/remove; preserves time priority.

---

## 5. Matching Algorithm

```python
def match_order(book: OrderBook, new_order: Order):
    """
    Try to match new_order against opposite side.
    Continues matching until: (a) new_order fully filled, or
    (b) no more orders on opposite side at acceptable price.
    """
    trades = []
    opposite = book.asks if new_order.side == 'B' else book.bids

    while new_order.qty > 0 and opposite:
        best_price = next(iter(opposite))   # SortedDict head

        # Price acceptable?
        if new_order.side == 'B' and best_price > new_order.price:
            break
        if new_order.side == 'S' and best_price < new_order.price:
            break

        level = opposite[best_price]
        while new_order.qty > 0 and level.orders:
            resting = level.orders[0]
            match_qty = min(new_order.qty, resting.qty)

            trade = Trade(
                buy_order=new_order.id if new_order.side == 'B' else resting.id,
                sell_order=resting.id if new_order.side == 'B' else new_order.id,
                price=best_price,    # resting price wins (price improvement)
                qty=match_qty,
                ts=time.time_ns()
            )
            trades.append(trade)

            new_order.qty -= match_qty
            resting.qty -= match_qty
            level.total_qty -= match_qty

            if resting.qty == 0:
                level.orders.popleft()

        if not level.orders:
            del opposite[best_price]

    # Remaining qty → add to book
    if new_order.qty > 0:
        book.add_limit(new_order)

    return trades
```

**Determinism rules:**
- Strict price-time priority.
- One thread per symbol — no cross-thread races.
- Wall-clock-independent — sequencer assigns logical order.

---

## 6. Single-Threaded Matching

**Counter-intuitive insight:** matching engines are single-threaded per symbol.

Why?
- Determinism: same input order → same output trades.
- No locks → no lock overhead, no deadlock.
- Cache-friendly: hot data stays in L1/L2.
- Low latency: single-thread on isolated CPU core.

Each symbol gets its own thread, pinned to a core (using `taskset` or `cpuset`).

```bash
taskset -c 5 ./matching_engine --symbol=AAPL
```

---

## 7. Sequencer

Single sequencer per symbol assigns monotonic `seq_no` to incoming orders.

```
Order arrives at gateway → sent to sequencer for symbol →
sequencer assigns seq=12345 → published to matching engine via lockless queue (LMAX Disruptor).
```

LMAX Disruptor pattern:
- Pre-allocated ring buffer.
- Single producer (sequencer), single consumer (matching engine).
- No GC pressure, no contention.

```python
# Conceptual — real impl in C++/Rust
ring_buffer = RingBuffer(size=1024*1024)

# Sequencer
def on_order(order):
    seq = ring_buffer.next()
    ring_buffer.set(seq, order)
    ring_buffer.publish(seq)

# Matching engine reads sequentially
while True:
    next_seq = ring_buffer.next_to_read()
    order = ring_buffer.get(next_seq)
    process(order)
```

---

## 8. Pre-Trade Risk Checks

Before matching, every order is risk-checked:

```python
def risk_check(order, account) -> RiskResult:
    # 1. Sufficient balance / margin
    if order.side == 'B' and order.qty * order.price > account.buying_power:
        return REJECT("insufficient buying power")

    # 2. Position limits
    if abs(account.position[order.symbol] + qty_delta) > position_limit:
        return REJECT("position limit exceeded")

    # 3. Fat-finger check (price way outside last trade)
    if abs(order.price - last_trade_price) / last_trade_price > 0.10:
        return REJECT("price outside collar")

    # 4. Order size sanity
    if order.qty > max_single_order_size:
        return REJECT("oversized order")

    return OK
```

These run on every order. Latency budget: ~20 μs.

In-memory account state, replicated for HA.

---

## 9. FIX Protocol (Industry Standard)

Brokers connect via FIX (Financial Information eXchange).

Sample FIX message:
```
8=FIX.4.4|9=140|35=D|34=4|49=BROKER|56=EXCHANGE|52=20240101-12:00:00.000|
11=ORDER001|55=AAPL|54=1|38=100|40=2|44=150.00|59=0|10=210|
```

Key tags:
- `35=D` → New Order Single
- `54=1` → Buy (2 = Sell)
- `55=AAPL` → Symbol
- `38=100` → Quantity
- `40=2` → Limit (1 = Market)
- `44=150.00` → Limit price
- `59=0` → Day order (3 = IOC, 4 = FOK)

Modern alternatives: FIXT, OUCH, ITCH (NASDAQ), Binary protocols for ultra-low latency.

---

## 10. Order Types

| Type | Behavior |
|---|---|
| Limit | Execute only at limit price or better; rest stays on book |
| Market | Execute at best available price; no resting |
| IOC (Immediate or Cancel) | Match what you can, cancel rest |
| FOK (Fill or Kill) | All-or-nothing; either full fill immediately or cancel |
| Stop | Triggers a market/limit order when price crosses stop level |
| Iceberg | Show only part of qty on book; replenish as filled |

```python
def handle_iceberg(order):
    visible = min(order.display_qty, order.qty)
    visible_order = order.clone(qty=visible)
    trades = match(visible_order)
    order.qty -= (visible - visible_order.qty)
    if order.qty > 0:
        # Reset visible chunk, re-add at end of queue (time priority lost)
        book.add(order.clone(qty=min(order.display_qty, order.qty)))
```

---

## 11. Market Data Dissemination

After each trade or book change, publish:

### Level 1 (Top of Book)
- Best bid, best ask, last trade price, last qty.

### Level 2 (Depth)
- Top N price levels on each side.

### Level 3 (Full Book)
- Every order detail (only paid subscribers / regulated venues).

### Distribution
- **Multicast UDP** (lowest latency, used by exchanges + brokers).
- **WebSocket** (consumer apps, brokers' retail interfaces).
- **Kafka** for downstream archival/analytics.

**Throughput:** 10M msgs/sec across all symbols. Each subscriber may filter to symbols they care about.

```python
def publish_book_update(symbol, side, price, total_qty):
    msg = {
        "type": "book_update",
        "symbol": symbol,
        "side": side,
        "price": price,
        "qty": total_qty,
        "ts": time.time_ns()
    }
    multicast.send(msg)
    kafka.produce("market_data", msg)
```

---

## 12. Trade Capture & Reporting

Every trade is:
1. Persisted to durable storage (Kafka + DB).
2. Sent to clearing house.
3. Sent to regulatory feed (Consolidated Tape in US, etc.).
4. Acknowledged to both parties.

```sql
CREATE TABLE trades (
    id           BIGSERIAL PRIMARY KEY,
    symbol       TEXT,
    price        NUMERIC(12,4),
    qty          BIGINT,
    buy_order    BIGINT,
    sell_order   BIGINT,
    buyer_id     UUID,
    seller_id    UUID,
    executed_at  TIMESTAMP,
    seq_no       BIGINT
);
CREATE INDEX ON trades(symbol, executed_at);
```

Partitioned by date (monthly), pruned to cold storage after 1 year.

---

## 13. Replay & Audit

**Critical for exchanges:** ability to replay every event exactly.

### Architecture
- All inputs (orders, cancels, modifies) sequenced in Kafka or equivalent durable log.
- Matching engine = pure function of (state, input).
- Replaying inputs → reproduces all state and outputs.

### When used
- Investigating disputes.
- Regulatory audits.
- Bug investigation (rebuild day's state).
- Cold start / disaster recovery.

```python
def replay(date):
    engine = MatchingEngine()
    for event in kafka.read(f"orders.{date}"):
        engine.process(event)
    return engine.state
```

---

## 14. High Availability

**Active-passive replication:**
- Primary matching engine + hot standby on different rack/AZ.
- Both consume from same input sequence.
- Standby maintains parallel state, ready to take over.
- Heartbeat-based failover (< 100 μs).

**Active-active:** not used. Determinism requires single source of truth per symbol.

### Crash recovery
- Periodic snapshot of state.
- On crash: load snapshot + replay events since.

---

## 15. Latency Optimizations

### Where the microseconds go
| Stage | Typical | With opt |
|---|---|---|
| Network ingress | 5 μs | 1 μs (kernel bypass: DPDK) |
| Parse FIX | 2 μs | 0.2 μs (binary protocol) |
| Risk check | 10 μs | 5 μs (in-mem, no malloc) |
| Sequencer queue | 1 μs | < 100 ns (Disruptor) |
| Matching | 5 μs | 1 μs (cache-friendly DS) |
| Market data send | 5 μs | 1 μs (multicast) |
| **Total** | **30 μs** | **8 μs** |

### Techniques
- **Kernel bypass**: DPDK, RDMA, custom NICs.
- **Co-location**: traders rack in same DC as exchange.
- **Pinned threads** on isolated cores.
- **Pre-allocated objects** (no GC, no malloc in hot path).
- **Lock-free data structures**.
- **Cache-line optimized** layouts.
- **Hardware timestamps** (PTP, GPS).

---

## 16. Architecture Decisions

| Component | Choice | Why |
|---|---|---|
| Language | C++ / Rust / Java (LMAX-style) | Predictable GC, low latency |
| Matching engine | Single-threaded per symbol | Determinism, no locks |
| Persistence | Append-only log (Kafka-like) | Replay-able |
| Risk | In-line, in-memory | Cannot block matching |
| Market data | Multicast UDP | Lowest latency to subscribers |
| Settlement | Async, T+2 batch | Not critical path |

---

## 17. Symbol Sharding

10,000 symbols × 1 thread each → too many threads.

**Sharding strategy:**
- Group symbols into ~50 shards.
- Each shard = 1 process, 1 thread, ~200 symbols.
- Shards on separate physical machines for fault isolation.

But: within a shard, sequencer handles inter-symbol ordering (e.g., if you process orders for AAPL and MSFT on same thread, sequence them deterministically).

---

## 18. Settlement & Clearing

Real exchanges hand off to clearing houses (DTCC in US).

```
T+0:  Trade executed
T+0:  Clearing house novates → becomes counterparty to both sides
T+1:  Margin calls based on net positions
T+2:  Cash and securities settled
```

Backend pipeline:
- Trades → clearing house API (overnight batch + intraday).
- Each broker's net position computed at end of day.
- Settlement instructions sent to custodians.

---

## 19. Trade-offs

| Decision | Trade-off |
|---|---|
| Single-threaded matching | Determinism + low latency; symbol throughput capped |
| Strict price-time priority | Fair; can be exploited (HFT advantage) |
| Pre-trade risk | Adds latency; required for safety |
| Multicast market data | Massive scale; some packet loss possible |
| Replay-able log | Storage cost; absolute requirement |
| Co-location | Fairness debates; revenue source |

---

## 20. Follow-up Questions

- **"How do you prevent runaway algorithms?"** → Order rate limits per broker, kill switch (auto-disable on threshold breaches).
- **"How is fairness enforced?"** → Strict price-time priority, single sequencer, no special priorities except regulatory carve-outs.
- **"What if matching engine crashes mid-trade?"** → Atomic event logging — either trade is in log or not. Replay reconstructs state.
- **"How are partial fills handled?"** → Order remains on book with remaining qty. Each match generates a trade message; broker reassembles.
- **"Circuit breakers / trading halts?"** → If symbol moves > X% in time window, all matching suspended for cool-off (5-15 min). Special exchange-wide halts for market crashes.
- **"Why not use ML/Python?"** → Latency. Python GC and interpreter unpredictable. ML may surface in pre-trade risk (fraud detection) but not matching path.
