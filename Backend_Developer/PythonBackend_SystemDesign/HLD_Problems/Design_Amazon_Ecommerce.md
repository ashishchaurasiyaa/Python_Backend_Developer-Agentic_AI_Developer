# Design Amazon / E-commerce Platform

---

## 1. Requirements

### Functional
- Product catalog (search, browse, filter)
- Product detail page (price, stock, seller, reviews)
- Shopping cart (add/remove/update)
- Checkout (address, payment, order placement)
- Order management (track, cancel, return)
- Flash sale / deals (limited time, high concurrency)
- Inventory management
- Seller dashboard

### Non-Functional
- 500M products, 1B users
- Peak: 100K orders/sec (Prime Day)
- Product search < 100ms
- Cart operations < 50ms
- Order placement < 2s (payment included)
- 99.999% for checkout (highest priority)

---

## 2. Scale Estimation

| Metric | Calculation | Result |
|--------|-------------|--------|
| Product catalog size | 500M products × 10KB | ~5 TB |
| Search QPS (normal) | 1B users × 10 searches/day ÷ 86400 | ~115K QPS |
| Orders (normal) | 30M orders/day ÷ 86400 | ~350 QPS |
| Orders (Prime Day) | 300M orders × 12h ÷ 43200s | ~7K QPS |
| Flash sale peak | 1M users hit same product at t=0 | ~100K QPS |

---

## 3. Architecture

```
Users → CloudFront CDN → API Gateway → Services
                                          │
         ┌────────────────────────────────┤
         │                                │
    ┌────▼────┐  ┌──────────┐  ┌──────────▼──┐  ┌──────────┐
    │Product  │  │  Cart    │  │  Order      │  │ Payment  │
    │Service  │  │ Service  │  │  Service    │  │ Service  │
    └────┬────┘  └────┬─────┘  └──────┬──────┘  └──────────┘
         │            │               │
    Elasticsearch  Redis          PostgreSQL
    (search)    (cart, stock)    (orders, ACID)
         │
    DynamoDB / Aurora
    (product catalog)
                    ┌──────────────────────────────┐
                    │         Kafka                 │
                    │  order_placed, inventory_     │
                    │  updated, payment_completed   │
                    └──────────────────────────────┘
```

---

## 4. Product Catalog Service

```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Product:
    product_id: str
    title: str
    description: str
    price: float
    seller_id: str
    category: str
    attributes: dict          # color, size, material, etc.
    images: list[str]         # S3 URLs
    stock: int
    rating: float = 0.0
    review_count: int = 0

# DynamoDB: primary key = product_id (single-digit ms reads)
# Elasticsearch: full-text search on title, description, attributes

class ProductService:
    async def get_product(self, product_id: str) -> Product:
        # Cache-aside: Redis → DynamoDB
        cached = await self.redis.get(f"product:{product_id}")
        if cached:
            return Product(**json.loads(cached))
        product = await self.dynamo.get_item(product_id)
        await self.redis.setex(f"product:{product_id}", 300, json.dumps(product.__dict__))
        return product

    async def search_products(self, query: str, filters: dict,
                               page: int = 0, size: int = 20) -> list[Product]:
        """Elasticsearch full-text search with filters."""
        es_query = {
            "query": {
                "bool": {
                    "must": {"multi_match": {
                        "query": query,
                        "fields": ["title^3", "description", "category^2"]
                    }},
                    "filter": [{"term": {k: v}} for k, v in filters.items()
                               if k != "price_range"] +
                              ([{"range": {"price": {"gte": filters["price_range"][0],
                                                     "lte": filters["price_range"][1]}}}]
                               if "price_range" in filters else [])
                }
            },
            "sort": [{"_score": "desc"}, {"rating": "desc"}],
            "from": page * size, "size": size
        }
        resp = await self.es.search(index="products", body=es_query)
        return [Product(**hit["_source"]) for hit in resp["hits"]["hits"]]
```

---

## 5. Cart Service

```python
import json
import time

class CartService:
    """
    Cart stored in Redis (fast, ephemeral).
    Persisted to DynamoDB on checkout / session end.
    TTL: 30 days (auto-expire abandoned carts).
    """
    CART_TTL = 30 * 86400   # 30 days

    def __init__(self, redis_client):
        self.redis = redis_client

    def _cart_key(self, user_id: str) -> str:
        return f"cart:{user_id}"

    async def add_item(self, user_id: str, product_id: str,
                        quantity: int, price: float) -> dict:
        key = self._cart_key(user_id)
        cart_item = json.dumps({
            "product_id": product_id,
            "quantity": quantity,
            "price": price,
            "added_at": time.time()
        })
        await self.redis.hset(key, product_id, cart_item)
        await self.redis.expire(key, self.CART_TTL)
        return await self.get_cart(user_id)

    async def update_quantity(self, user_id: str, product_id: str,
                               quantity: int) -> dict:
        key = self._cart_key(user_id)
        if quantity <= 0:
            await self.redis.hdel(key, product_id)
        else:
            item = json.loads(await self.redis.hget(key, product_id))
            item["quantity"] = quantity
            await self.redis.hset(key, product_id, json.dumps(item))
        return await self.get_cart(user_id)

    async def get_cart(self, user_id: str) -> dict:
        key = self._cart_key(user_id)
        raw_items = await self.redis.hgetall(key)
        items = [json.loads(v) for v in raw_items.values()]
        subtotal = sum(i["price"] * i["quantity"] for i in items)
        return {"items": items, "subtotal": round(subtotal, 2), "item_count": len(items)}

    async def clear_cart(self, user_id: str):
        await self.redis.delete(self._cart_key(user_id))
```

---

## 6. Inventory & Stock Management

```python
class InventoryService:
    """
    Critical: prevent overselling.
    Use Redis atomic operations for stock reservation.
    PostgreSQL for authoritative stock record.
    """

    async def check_and_reserve_stock(self, product_id: str,
                                       quantity: int,
                                       order_id: str) -> bool:
        """
        Atomically decrement stock. Returns False if insufficient.
        Uses Lua script for atomicity (no race conditions).
        """
        lua_script = """
        local stock = redis.call('GET', KEYS[1])
        if stock == false or tonumber(stock) < tonumber(ARGV[1]) then
            return 0
        end
        redis.call('DECRBY', KEYS[1], ARGV[1])
        -- Reserve for order (set expiry for unpaid reservations)
        redis.call('SETEX', 'reserve:'..KEYS[1]..':'..ARGV[2], 600, ARGV[1])
        return 1
        """
        result = await self.redis.eval(lua_script, 1,
                                        f"stock:{product_id}",
                                        quantity, order_id)
        return bool(result)

    async def release_reservation(self, product_id: str, order_id: str):
        """Release reserved stock if payment fails or order cancelled."""
        reserve_key = f"reserve:stock:{product_id}:{order_id}"
        quantity = await self.redis.get(reserve_key)
        if quantity:
            await self.redis.incrby(f"stock:{product_id}", int(quantity))
            await self.redis.delete(reserve_key)
```

---

## 7. Order Service & Checkout Flow

```python
from enum import Enum
from decimal import Decimal

class OrderStatus(Enum):
    PENDING   = "pending"
    CONFIRMED = "confirmed"
    SHIPPED   = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    RETURNED  = "returned"

class CheckoutService:
    """
    Checkout = multi-step saga with compensation on failure.

    Steps:
    1. Validate cart items still exist + prices current
    2. Reserve inventory (Redis atomic)
    3. Calculate final price (discounts, tax, shipping)
    4. Create order record (PostgreSQL)
    5. Charge payment
    6. Confirm inventory deduction (PostgreSQL)
    7. Emit order_placed event (Kafka)
    8. Clear cart
    """
    async def checkout(self, user_id: str, cart: dict,
                        payment_token: str, address_id: str) -> dict:
        order_id = generate_order_id()

        # Step 1: Validate items
        validated = await self._validate_cart_items(cart["items"])
        if not validated["valid"]:
            return {"error": f"Item unavailable: {validated['reason']}"}

        # Step 2: Reserve inventory (all or nothing)
        reserved = []
        for item in cart["items"]:
            ok = await self.inventory.check_and_reserve_stock(
                item["product_id"], item["quantity"], order_id
            )
            if not ok:
                # COMPENSATE: release already-reserved items
                for r in reserved:
                    await self.inventory.release_reservation(r["product_id"], order_id)
                return {"error": f"Insufficient stock: {item['product_id']}"}
            reserved.append(item)

        # Step 3: Calculate total
        subtotal = Decimal(str(cart["subtotal"]))
        tax      = subtotal * Decimal("0.08")
        shipping = await self.shipping.calculate(address_id, cart["items"])
        total    = subtotal + tax + Decimal(str(shipping))

        # Step 4: Create order (PostgreSQL, ACID)
        order = await self.db.create_order({
            "order_id":  order_id,
            "user_id":   user_id,
            "items":     cart["items"],
            "total":     float(total),
            "status":    OrderStatus.PENDING.value,
            "address_id": address_id
        })

        # Step 5: Charge payment
        try:
            payment = await self.payment.charge(
                user_id=user_id,
                amount=float(total),
                token=payment_token,
                idempotency_key=f"order:{order_id}"   # prevent double charge
            )
        except PaymentError as e:
            # COMPENSATE: cancel order + release inventory
            await self.db.update_order_status(order_id, OrderStatus.CANCELLED)
            for item in cart["items"]:
                await self.inventory.release_reservation(item["product_id"], order_id)
            return {"error": f"Payment failed: {e}"}

        # Step 6: Confirm order
        await self.db.update_order_status(order_id, OrderStatus.CONFIRMED)

        # Step 7: Emit event → triggers fulfillment, email, analytics
        await self.kafka.send("order_placed", {
            "order_id": order_id, "user_id": user_id,
            "total": float(total), "items": cart["items"]
        })

        # Step 8: Clear cart
        await self.cart_service.clear_cart(user_id)

        return {"order_id": order_id, "status": "confirmed", "total": float(total)}
```

---

## 8. Flash Sale System

```python
"""
Flash Sale Challenge: 1M users hit BUY at exactly t=0 for 100 items.
Must: prevent overselling, be fair, stay fast.
"""

class FlashSaleService:
    """
    Strategy:
    1. Pre-load stock into Redis before sale starts
    2. Use DECR + check (Lua script) for atomic stock decrement
    3. Rate limit per user (1 purchase per user per sale)
    4. Queue overflow requests (first-come-first-served)
    5. Process queue async → send order confirmation email
    """
    async def setup_sale(self, sale_id: str, product_id: str, stock: int, start_time: float):
        await self.redis.set(f"flash:stock:{sale_id}", stock)
        await self.redis.set(f"flash:start:{sale_id}", start_time)

    async def attempt_purchase(self, user_id: str, sale_id: str) -> dict:
        now = time.time()
        start = float(await self.redis.get(f"flash:start:{sale_id}") or 0)
        if now < start:
            return {"error": "Sale not started yet"}

        # Check if user already purchased
        if await self.redis.sismember(f"flash:buyers:{sale_id}", user_id):
            return {"error": "Already purchased"}

        # Atomic: decrement stock + add user to buyers set
        lua = """
        local stock = redis.call('GET', KEYS[1])
        if not stock or tonumber(stock) <= 0 then return 0 end
        redis.call('DECRBY', KEYS[1], 1)
        redis.call('SADD', KEYS[2], ARGV[1])
        redis.call('RPUSH', KEYS[3], ARGV[1])  -- add to purchase queue
        return 1
        """
        result = await self.redis.eval(
            lua, 3,
            f"flash:stock:{sale_id}",
            f"flash:buyers:{sale_id}",
            f"flash:queue:{sale_id}",
            user_id
        )

        if result:
            # Place order async
            await self.kafka.send("flash_purchase", {"user_id": user_id, "sale_id": sale_id})
            return {"status": "success", "message": "Order being processed"}
        return {"error": "Sold out"}
```

---

## 9. Pricing Service

```python
class PricingService:
    """Dynamic pricing: base price + seller markup + promotions + demand."""

    async def get_final_price(self, product_id: str, user_id: str,
                               quantity: int) -> dict:
        base_price = await self.get_base_price(product_id)

        # Apply promotions (coupon, Prime discount, bundle deal)
        promotions = await self.get_applicable_promotions(user_id, product_id)
        discount = sum(p.calculate_discount(base_price * quantity) for p in promotions)

        # Tax based on delivery address
        # Shipping cost
        return {
            "base_price": base_price,
            "quantity": quantity,
            "subtotal": base_price * quantity,
            "discount": discount,
            "final_price": base_price * quantity - discount
        }
```

---

## 10. Failure Scenarios

| Scenario | Solution |
|----------|----------|
| Overselling on flash sale | Redis Lua script atomic decrement — guaranteed no race |
| Payment timeout | Idempotency key — safe to retry, never double charge |
| Inventory service down | Fallback: allow purchase, reconcile async (oversell risk accepted for UX) |
| Cart lost (Redis crash) | Persist cart to DynamoDB on every mutation. Restore on Redis miss. |
| Order placed but payment system down | Saga compensation: auto-cancel order + release inventory after 10min |
| Search service slow | Circuit breaker → fallback to category browse (no search) |

---

## 11. Interview Questions

**Q1: How do you prevent overselling during flash sales?**
> Use Redis Lua script for atomic: check stock > 0 → decrement → add user to purchased set. Lua scripts are atomic in Redis (single-threaded execution). No two requests can simultaneously see stock > 0 and both decrement. Pre-load stock into Redis before sale starts.

**Q2: How does the cart service handle concurrent updates?**
> Redis HSET is atomic per key. Each product_id is a separate hash field — concurrent updates to different products don't conflict. For quantity update of same product: use Redis WATCH + MULTI/EXEC (optimistic locking) or serialization per user cart (message queue per user).

**Q3: Why PostgreSQL for orders but Redis for cart and DynamoDB for catalog?**
> Cart: ephemeral, fast reads/writes, no complex queries — Redis perfect. Catalog: massive scale, simple key lookups, global distribution — DynamoDB perfect. Orders: ACID required (money!), complex relationships (user, items, payment, shipping), ad-hoc queries — PostgreSQL. Right tool for right job.

**Q4: How does checkout handle partial failures (e.g., payment fails after stock reserved)?**
> SAGA pattern with compensating transactions. If payment fails: (1) cancel order record, (2) release inventory reservation, (3) refund if partially charged. All compensation steps are idempotent. Kafka events track saga state — if service crashes, replay events to resume from last successful step.

**Q5: How to implement "price drop notification"?**
> User subscribes: store (product_id, user_id, target_price) in PostgreSQL. Price change event → Kafka → notification service consumer. Consumer queries: SELECT users WHERE product_id=X AND target_price >= new_price. Send push notification / email. For scale: partition by product_id, shard notifications.

**Q6: How to design product search with millions of products?**
> Elasticsearch cluster with product index. Index fields: title (text, analyzed), category (keyword), price (float, range queries), rating (float), attributes (keyword map). Shard by category for query isolation. Sync: product updates → Kafka → ES consumer (near-real-time). Cache popular searches in Redis (30-min TTL).

**Q7: How to handle product returns and refunds?**
> Return request → create return order (linked to original). State machine: REQUESTED → APPROVED → SHIPPED_BACK → RECEIVED → REFUNDED. Refund via Payment Service (same idempotency key as original + ":refund"). Inventory updated on received. Fraud detection: flag excessive returners.

**Q8: How does recommendation work for "Customers also bought"?**
> Offline: frequent itemset mining (FP-Growth) on order history. item2vec: embed products in vector space, find nearest neighbors. Collaborative filtering: users who bought A also bought B. Store results in Redis: `also_bought:{product_id}` → sorted list of product_ids. Refresh daily. Real-time: session-based collaborative filtering for current browsing context.
