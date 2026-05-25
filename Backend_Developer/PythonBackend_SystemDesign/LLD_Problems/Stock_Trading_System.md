# LLD: Stock Trading System (Order Book & Matching Engine)

---

## 1. Requirements

### Functional
- Place orders: market order, limit order, stop-limit order
- Order book: maintain bids (buy) and asks (sell) for each symbol
- Matching engine: match buy and sell orders (price-time priority)
- Order management: cancel, modify orders
- Trade execution: fill orders, generate trade records
- Real-time order book snapshots (top-of-book / depth)
- Portfolio management: track positions per user

### Non-Functional
- < 1ms order matching latency (co-located exchanges)
- ACID guarantees on trade execution (money movement)
- Order book must be thread-safe
- High throughput: 1M orders/sec (NASDAQ-scale)

---

## 2. Core Classes

```python
from dataclasses import dataclass, field
from enum import Enum
from decimal import Decimal
from typing import Optional
import heapq
import time
import uuid

class OrderSide(Enum):
    BUY  = "buy"
    SELL = "sell"

class OrderType(Enum):
    MARKET     = "market"       # execute immediately at best price
    LIMIT      = "limit"        # execute at specified price or better
    STOP_LIMIT = "stop_limit"   # activate when price hits stop, then limit order

class OrderStatus(Enum):
    PENDING   = "pending"
    OPEN      = "open"          # in order book, awaiting match
    PARTIALLY_FILLED = "partially_filled"
    FILLED    = "filled"        # fully executed
    CANCELLED = "cancelled"
    REJECTED  = "rejected"

class TimeInForce(Enum):
    GTC = "good_till_cancel"    # stay in book until filled or cancelled
    IOC = "immediate_or_cancel" # fill immediately, cancel remainder
    FOK = "fill_or_kill"        # fill entirely immediately or cancel all

@dataclass
class Order:
    order_id:     str
    user_id:      str
    symbol:       str
    side:         OrderSide
    order_type:   OrderType
    quantity:     Decimal       # total quantity requested
    price:        Optional[Decimal] = None    # None for market orders
    stop_price:   Optional[Decimal] = None    # for stop-limit
    time_in_force: TimeInForce = TimeInForce.GTC
    status:       OrderStatus = OrderStatus.PENDING
    filled_qty:   Decimal = Decimal("0")
    avg_fill_price: Decimal = Decimal("0")
    created_at:   float = field(default_factory=time.time)
    updated_at:   float = field(default_factory=time.time)

    @property
    def remaining_qty(self) -> Decimal:
        return self.quantity - self.filled_qty

    @property
    def is_fully_filled(self) -> bool:
        return self.filled_qty >= self.quantity

    def fill(self, qty: Decimal, price: Decimal):
        """Record a partial or full fill."""
        # Compute new average fill price
        total_value = self.avg_fill_price * self.filled_qty + price * qty
        self.filled_qty += qty
        self.avg_fill_price = total_value / self.filled_qty

        if self.is_fully_filled:
            self.status = OrderStatus.FILLED
        else:
            self.status = OrderStatus.PARTIALLY_FILLED
        self.updated_at = time.time()

    def cancel(self):
        if self.status in (OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED):
            self.status = OrderStatus.CANCELLED
            self.updated_at = time.time()

@dataclass
class Trade:
    """Represents a matched execution between buy and sell orders."""
    trade_id:     str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol:       str = ""
    buy_order_id: str = ""
    sell_order_id: str = ""
    buy_user_id:  str = ""
    sell_user_id: str = ""
    quantity:     Decimal = Decimal("0")
    price:        Decimal = Decimal("0")
    timestamp:    float = field(default_factory=time.time)

    @property
    def value(self) -> Decimal:
        return self.quantity * self.price
```

---

## 3. Order Book

```python
"""
Order Book: maintains sorted lists of buy (bid) and sell (ask) orders.

Bid side: highest price first (buyers want to pay least, so highest bidder matches first)
Ask side: lowest price first (sellers want highest price, so lowest asker matches first)

Price-time priority: at same price, earlier orders execute first.

Data structure:
  - Price levels: {price → list of orders} (sorted by price)
  - Priority queue for quick access to best bid/ask

For production: use sorted dict or skip list for O(log n) operations.
"""

import sortedcontainers   # pip install sortedcontainers

class PriceLevel:
    """All orders at the same price, ordered by time (FIFO)."""

    def __init__(self, price: Decimal):
        self.price  = price
        self.orders: list[Order] = []    # FIFO queue

    def add(self, order: Order):
        self.orders.append(order)

    def remove(self, order_id: str) -> Optional[Order]:
        for i, o in enumerate(self.orders):
            if o.order_id == order_id:
                return self.orders.pop(i)
        return None

    def peek(self) -> Optional[Order]:
        """Oldest order at this price (first to match)."""
        while self.orders and self.orders[0].status in (
            OrderStatus.CANCELLED, OrderStatus.FILLED
        ):
            self.orders.pop(0)   # remove stale orders
        return self.orders[0] if self.orders else None

    def is_empty(self) -> bool:
        return self.peek() is None

    @property
    def total_quantity(self) -> Decimal:
        return sum(o.remaining_qty for o in self.orders
                   if o.status in (OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED))


class OrderBook:
    """
    Maintains bid and ask price levels for one symbol.
    Thread-safe via locking in MatchingEngine.
    """

    def __init__(self, symbol: str):
        self.symbol = symbol
        # Bids: descending price (we want highest bid first)
        self.bids: sortedcontainers.SortedDict = sortedcontainers.SortedDict(lambda k: -k)
        # Asks: ascending price (we want lowest ask first)
        self.asks: sortedcontainers.SortedDict = sortedcontainers.SortedDict()
        # Order lookup: order_id → Order (for cancellation)
        self._orders: dict[str, Order] = {}

    def add_order(self, order: Order):
        """Add order to appropriate side of book."""
        assert order.price is not None, "Limit order must have price"
        self._orders[order.order_id] = order

        side = self.bids if order.side == OrderSide.BUY else self.asks
        if order.price not in side:
            side[order.price] = PriceLevel(order.price)
        side[order.price].add(order)

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order."""
        order = self._orders.get(order_id)
        if not order or order.status not in (OrderStatus.OPEN,
                                              OrderStatus.PARTIALLY_FILLED):
            return False
        order.cancel()
        return True

    def best_bid(self) -> Optional[Decimal]:
        """Highest buy price in book."""
        for price, level in self.bids.items():
            if not level.is_empty():
                return price
        return None

    def best_ask(self) -> Optional[Decimal]:
        """Lowest sell price in book."""
        for price, level in self.asks.items():
            if not level.is_empty():
                return price
        return None

    def spread(self) -> Optional[Decimal]:
        bid = self.best_bid()
        ask = self.best_ask()
        if bid and ask:
            return ask - bid
        return None

    def get_depth(self, levels: int = 5) -> dict:
        """Return top N price levels for market depth display."""
        bids = []
        for price, level in self.bids.items():
            if len(bids) >= levels: break
            qty = level.total_quantity
            if qty > 0:
                bids.append({"price": float(price), "quantity": float(qty)})

        asks = []
        for price, level in self.asks.items():
            if len(asks) >= levels: break
            qty = level.total_quantity
            if qty > 0:
                asks.append({"price": float(price), "quantity": float(qty)})

        return {
            "symbol": self.symbol,
            "bids":   bids,
            "asks":   asks,
            "spread": float(self.spread()) if self.spread() else None
        }

    def get_order(self, order_id: str) -> Optional[Order]:
        return self._orders.get(order_id)
```

---

## 4. Matching Engine

```python
import threading
from collections import defaultdict

class MatchingEngine:
    """
    Core matching logic: matches buy orders against sell orders.
    Price-time priority (FIFO within price level).

    Runs on a single thread per symbol for lock-free operation.
    Different symbols can run on different threads.
    """

    def __init__(self, trade_publisher):
        self.order_books: dict[str, OrderBook] = {}
        self.locks: dict[str, threading.Lock] = defaultdict(threading.Lock)
        self.publisher = trade_publisher   # publish trades to Kafka

    def get_or_create_book(self, symbol: str) -> OrderBook:
        if symbol not in self.order_books:
            self.order_books[symbol] = OrderBook(symbol)
        return self.order_books[symbol]

    def submit_order(self, order: Order) -> list[Trade]:
        """
        Process incoming order: match immediately, then add remainder to book.
        Returns list of trades generated.
        """
        with self.locks[order.symbol]:
            book = self.get_or_create_book(order.symbol)
            order.status = OrderStatus.OPEN

            if order.order_type == OrderType.MARKET:
                trades = self._match_market_order(order, book)
            elif order.order_type == OrderType.LIMIT:
                trades = self._match_limit_order(order, book)
            else:
                trades = []

            # Handle time-in-force
            if order.time_in_force == TimeInForce.IOC and not order.is_fully_filled:
                order.cancel()   # cancel remainder immediately
            elif order.time_in_force == TimeInForce.FOK:
                if not order.is_fully_filled:
                    # Must fill all or cancel all → reverse any partial fills
                    for trade in trades:
                        self._reverse_trade(trade, book)
                    order.cancel()
                    return []

            # Publish trades
            for trade in trades:
                self.publisher.publish(trade)

            return trades

    def _match_limit_order(self, order: Order, book: OrderBook) -> list[Trade]:
        """Match limit order against opposite side."""
        trades = []
        opposite = book.asks if order.side == OrderSide.BUY else book.bids

        for price, level in list(opposite.items()):
            if order.is_fully_filled:
                break

            # Price match check
            if order.side == OrderSide.BUY and price > order.price:
                break    # best ask too expensive for our bid
            if order.side == OrderSide.SELL and price < order.price:
                break    # best bid too cheap for our ask

            while not level.is_empty() and not order.is_fully_filled:
                resting = level.peek()
                if resting is None:
                    break

                # Determine trade quantity (min of remaining on both sides)
                trade_qty = min(order.remaining_qty, resting.remaining_qty)
                trade_price = price   # resting order sets the price

                trade = self._execute_fill(order, resting, trade_qty, trade_price)
                trades.append(trade)

                if resting.is_fully_filled:
                    level.orders.pop(0)

            if level.is_empty():
                del opposite[price]

        # Add unfilled remainder to book
        if not order.is_fully_filled and order.status != OrderStatus.CANCELLED:
            book.add_order(order)

        return trades

    def _match_market_order(self, order: Order, book: OrderBook) -> list[Trade]:
        """Market order: match at ANY available price."""
        trades = []
        opposite = book.asks if order.side == OrderSide.BUY else book.bids

        for price, level in list(opposite.items()):
            if order.is_fully_filled:
                break

            while not level.is_empty() and not order.is_fully_filled:
                resting = level.peek()
                if resting is None:
                    break

                trade_qty = min(order.remaining_qty, resting.remaining_qty)
                trade = self._execute_fill(order, resting, trade_qty, price)
                trades.append(trade)

                if resting.is_fully_filled:
                    level.orders.pop(0)

            if level.is_empty():
                del opposite[price]

        if not order.is_fully_filled:
            order.cancel()   # market orders can't rest in book

        return trades

    def _execute_fill(self, aggressor: Order, resting: Order,
                       qty: Decimal, price: Decimal) -> Trade:
        """Fill both sides and create trade record."""
        aggressor.fill(qty, price)
        resting.fill(qty, price)

        buy_order  = aggressor if aggressor.side == OrderSide.BUY else resting
        sell_order = resting if aggressor.side == OrderSide.BUY else aggressor

        return Trade(
            symbol=aggressor.symbol,
            buy_order_id=buy_order.order_id,
            sell_order_id=sell_order.order_id,
            buy_user_id=buy_order.user_id,
            sell_user_id=sell_order.user_id,
            quantity=qty,
            price=price
        )

    def cancel_order(self, symbol: str, order_id: str) -> bool:
        with self.locks[symbol]:
            book = self.get_or_create_book(symbol)
            return book.cancel_order(order_id)

    def get_order_book_snapshot(self, symbol: str, levels: int = 10) -> dict:
        with self.locks[symbol]:
            book = self.get_or_create_book(symbol)
            return book.get_depth(levels)

    def _reverse_trade(self, trade: Trade, book: OrderBook):
        """Reverse FOK trade (simplified — in production use SAGA)."""
        # Complex in practice: notify trade service to reverse
        pass
```

---

## 5. Portfolio & Risk Management

```python
class Position:
    """Tracks user's holdings for one symbol."""

    def __init__(self, user_id: str, symbol: str):
        self.user_id  = user_id
        self.symbol   = symbol
        self.quantity = Decimal("0")   # positive = long, negative = short
        self.avg_cost = Decimal("0")
        self.realized_pnl = Decimal("0")

    def on_buy(self, qty: Decimal, price: Decimal):
        """Update position on buy fill."""
        if self.quantity >= 0:
            # Adding to long or opening long position
            total_cost = self.avg_cost * self.quantity + price * qty
            self.quantity += qty
            self.avg_cost = total_cost / self.quantity if self.quantity > 0 else Decimal("0")
        else:
            # Covering short position
            closed_qty = min(qty, abs(self.quantity))
            self.realized_pnl += (self.avg_cost - price) * closed_qty
            self.quantity += qty
            if self.quantity > 0:
                self.avg_cost = price
            elif self.quantity == 0:
                self.avg_cost = Decimal("0")

    def on_sell(self, qty: Decimal, price: Decimal):
        """Update position on sell fill."""
        if self.quantity > 0:
            # Reducing/closing long position
            closed_qty = min(qty, self.quantity)
            self.realized_pnl += (price - self.avg_cost) * closed_qty
            self.quantity -= qty
            if self.quantity < 0:
                self.avg_cost = price   # opened short
        else:
            # Adding to short or opening short
            total_cost = self.avg_cost * abs(self.quantity) + price * qty
            self.quantity -= qty
            self.avg_cost = total_cost / abs(self.quantity) if self.quantity < 0 else Decimal("0")

    def unrealized_pnl(self, current_price: Decimal) -> Decimal:
        if self.quantity > 0:
            return (current_price - self.avg_cost) * self.quantity
        elif self.quantity < 0:
            return (self.avg_cost - current_price) * abs(self.quantity)
        return Decimal("0")


class RiskManager:
    """Pre-trade risk checks before order submission."""

    MAX_ORDER_VALUE = Decimal("1_000_000")
    MAX_POSITION_VALUE = Decimal("10_000_000")

    def __init__(self, portfolio_service):
        self.portfolio = portfolio_service

    async def check_order(self, order: Order) -> tuple[bool, str]:
        """Returns (approved, rejection_reason)."""

        # 1. Validate order fields
        if order.quantity <= 0:
            return False, "Quantity must be positive"

        if order.order_type == OrderType.LIMIT and (not order.price or order.price <= 0):
            return False, "Limit order requires positive price"

        # 2. Order value check
        if order.price:
            order_value = order.quantity * order.price
            if order_value > self.MAX_ORDER_VALUE:
                return False, f"Order value {order_value} exceeds limit {self.MAX_ORDER_VALUE}"

        # 3. Position limit check
        position = await self.portfolio.get_position(order.user_id, order.symbol)
        current_price = await self.portfolio.get_market_price(order.symbol)
        if current_price:
            new_qty = position.quantity + (
                order.quantity if order.side == OrderSide.BUY else -order.quantity
            )
            new_value = abs(new_qty) * current_price
            if new_value > self.MAX_POSITION_VALUE:
                return False, f"Position would exceed limit {self.MAX_POSITION_VALUE}"

        # 4. Buying power check (for buy orders)
        if order.side == OrderSide.BUY:
            available_cash = await self.portfolio.get_buying_power(order.user_id)
            required = order.quantity * (order.price or current_price or Decimal("0"))
            if required > available_cash:
                return False, f"Insufficient buying power: need {required}, have {available_cash}"

        return True, ""
```

---

## 6. Order Service (API Layer)

```python
class OrderService:
    """API layer: receive orders, run risk checks, submit to matching engine."""

    def __init__(self, engine: MatchingEngine, risk: RiskManager,
                  order_store, trade_store):
        self.engine      = engine
        self.risk        = risk
        self.order_store = order_store
        self.trade_store = trade_store

    async def place_order(self, user_id: str, symbol: str,
                           side: str, order_type: str,
                           quantity: float, price: float = None,
                           tif: str = "GTC") -> dict:
        """Place a new order. Returns order status."""
        order = Order(
            order_id=str(uuid.uuid4()),
            user_id=user_id,
            symbol=symbol.upper(),
            side=OrderSide(side),
            order_type=OrderType(order_type),
            quantity=Decimal(str(quantity)),
            price=Decimal(str(price)) if price else None,
            time_in_force=TimeInForce(tif)
        )

        # Pre-trade risk check
        approved, reason = await self.risk.check_order(order)
        if not approved:
            order.status = OrderStatus.REJECTED
            await self.order_store.save(order)
            return {"order_id": order.order_id, "status": "rejected", "reason": reason}

        # Persist order (before matching to prevent data loss)
        await self.order_store.save(order)

        # Submit to matching engine (synchronous, returns trades)
        trades = self.engine.submit_order(order)

        # Save trades
        for trade in trades:
            await self.trade_store.save(trade)

        # Update order status
        await self.order_store.update(order)

        return {
            "order_id":     order.order_id,
            "status":       order.status.value,
            "filled_qty":   float(order.filled_qty),
            "avg_price":    float(order.avg_fill_price),
            "trades":       len(trades)
        }

    async def cancel_order(self, user_id: str, order_id: str) -> dict:
        """Cancel an open order."""
        order = await self.order_store.get(order_id)
        if not order or order.user_id != user_id:
            return {"error": "Order not found or unauthorized"}

        success = self.engine.cancel_order(order.symbol, order_id)
        if success:
            await self.order_store.update(order)
            return {"order_id": order_id, "status": "cancelled"}
        return {"error": f"Cannot cancel order in status {order.status.value}"}

    async def get_order_book(self, symbol: str, levels: int = 10) -> dict:
        return self.engine.get_order_book_snapshot(symbol, levels)
```

---

## 7. Demo

```python
if __name__ == "__main__":
    class MockPublisher:
        def publish(self, trade: Trade):
            print(f"  TRADE: {trade.quantity} @ {trade.price} "
                  f"(buy:{trade.buy_order_id[:8]} sell:{trade.sell_order_id[:8]})")

    engine = MatchingEngine(MockPublisher())

    def make_order(uid, sym, side, otype, qty, price=None):
        return Order(
            order_id=str(uuid.uuid4()),
            user_id=uid, symbol=sym,
            side=OrderSide(side), order_type=OrderType(otype),
            quantity=Decimal(str(qty)),
            price=Decimal(str(price)) if price else None
        )

    # Add sell orders (asks)
    sell1 = make_order("seller1", "AAPL", "sell", "limit", 100, 150.00)
    sell2 = make_order("seller2", "AAPL", "sell", "limit",  50, 151.00)
    engine.submit_order(sell1)
    engine.submit_order(sell2)

    # Add buy order that matches sell1
    buy1 = make_order("buyer1", "AAPL", "buy", "limit", 60, 150.00)
    trades = engine.submit_order(buy1)
    print(f"Trades from buy1: {len(trades)}")

    # Check order book
    depth = engine.get_order_book_snapshot("AAPL")
    print(f"Bids: {depth['bids']}")
    print(f"Asks: {depth['asks']}")

    # Market order — takes best ask
    buy2 = make_order("buyer2", "AAPL", "buy", "market", 200)
    trades2 = engine.submit_order(buy2)
    print(f"Market order trades: {len(trades2)}")
```

---

## 8. Interview Questions

**Q1: What is price-time priority and how do you implement it?**
> Price-time priority: best price executes first; at same price, earliest order executes first (FIFO). Implementation: SortedDict of price levels. Each price level has a FIFO queue of orders. Matching engine iterates price levels in order (asks ascending, bids descending) and within each level processes orders in arrival order. This is standard exchange matching (used by NYSE, NASDAQ).

**Q2: How do you handle concurrency in the matching engine?**
> Per-symbol lock: each symbol has its own threading.Lock. Orders for different symbols process in parallel. Orders for same symbol serialize (one at a time). This is called "symbol partitioning." In ultra-low-latency systems: single-threaded per symbol, pin to CPU core, use lock-free queues (LMAX Disruptor pattern). Eliminates lock overhead entirely.

**Q3: What data structure is optimal for the order book?**
> Price levels stored in SortedDict (balanced BST, O(log n) insert/delete/min/max). Within each price level: deque for FIFO (O(1) add/remove front). Total complexity: O(log P) for price level access where P = distinct prices. Alternative: Red-Black tree (like TreeMap in Java). For cancellation: also maintain HashMap(order_id → Order) for O(1) lookup. In C++: std::map<Price, deque<Order>>.

**Q4: How does a market order differ from a limit order in matching?**
> Limit order: only matches at specified price or better. If no match, rests in order book until cancelled or filled. Market order: matches at ANY available price immediately. If book is empty or insufficient quantity, remaining is cancelled (can't rest in book — no price to place it at). Market orders guarantee execution, not price. Limit orders guarantee price, not execution.

**Q5: How do you implement stop-limit orders?**
> Stop-limit: two-phase order. Stop price: when market price hits this level, activate the order. Limit price: once activated, place as regular limit order at this price. Implementation: maintain a stop order list per symbol. On each trade, check if trade price triggered any stop orders. If triggered, convert stop-limit to limit order and submit to engine. Risk: stop orders may not fill if market gaps past limit price.

**Q6: How do you handle order book persistence (what if matching engine crashes)?**
> Event-sourced order book: every order placement, fill, cancellation is an event persisted to Kafka/DB before executing. On restart: replay events to rebuild exact order book state. Alternatively: write-ahead log (WAL) — persist to disk before processing. Order IDs must be idempotent to handle replay. Position state rebuilt from trade records. Critical: never acknowledge order to client before it's durably persisted.
