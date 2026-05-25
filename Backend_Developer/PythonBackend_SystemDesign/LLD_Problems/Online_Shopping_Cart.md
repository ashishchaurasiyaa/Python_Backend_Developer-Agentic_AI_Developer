# Design Online Shopping Cart — LLD

## Requirements

### Functional
- Users can browse products (with price, stock, categories)
- Add/remove items from cart
- Update quantity in cart
- Apply discount coupons / promo codes
- Calculate total with tax
- Checkout: validate stock → place order
- Cart persists across sessions (even if user closes browser)
- Guest cart → merge on login

### Non-Functional
- Cart operations < 50ms (Redis-backed)
- Support 100k concurrent shopping sessions
- No overselling (stock check before confirm)
- SOLID, extensible pricing engine

---

## Class Design

```python
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime
from enum import StrEnum, auto
from typing import Optional
from abc import ABC, abstractmethod
import uuid

# ── Domain Models ──────────────────────────────────────────────────────────

class ProductStatus(StrEnum):
    ACTIVE   = auto()
    INACTIVE = auto()
    DELETED  = auto()

class DiscountType(StrEnum):
    PERCENTAGE = "percentage"
    FLAT       = "flat"
    FREE_ITEM  = "free_item"

@dataclass
class Product:
    id:          str
    name:        str
    price:       Decimal
    stock:       int
    category:    str
    tax_rate:    Decimal = Decimal("0.18")   # 18% GST default
    status:      ProductStatus = ProductStatus.ACTIVE

    def is_available(self, quantity: int = 1) -> bool:
        return self.status == ProductStatus.ACTIVE and self.stock >= quantity

    def reserve(self, quantity: int) -> None:
        if not self.is_available(quantity):
            raise ValueError(f"Insufficient stock: {self.name} "
                             f"(requested={quantity}, available={self.stock})")
        self.stock -= quantity


@dataclass
class CartItem:
    product:    Product
    quantity:   int
    added_at:   datetime = field(default_factory=datetime.now)

    @property
    def subtotal(self) -> Decimal:
        return self.product.price * self.quantity

    @property
    def tax(self) -> Decimal:
        return self.subtotal * self.product.tax_rate

    @property
    def total(self) -> Decimal:
        return self.subtotal + self.tax

    def update_quantity(self, new_qty: int) -> None:
        if new_qty <= 0:
            raise ValueError("Quantity must be positive")
        if not self.product.is_available(new_qty):
            raise ValueError(f"Only {self.product.stock} available")
        self.quantity = new_qty


@dataclass
class Coupon:
    code:            str
    discount_type:   DiscountType
    discount_value:  Decimal       # % or flat amount
    min_order_value: Decimal = Decimal("0")
    max_discount:    Optional[Decimal] = None   # cap for % discounts
    expiry:          Optional[datetime] = None
    is_active:       bool = True

    def is_valid(self, order_total: Decimal) -> bool:
        if not self.is_active:
            return False
        if self.expiry and datetime.now() > self.expiry:
            return False
        if order_total < self.min_order_value:
            return False
        return True

    def calculate_discount(self, order_total: Decimal) -> Decimal:
        if not self.is_valid(order_total):
            return Decimal("0")
        if self.discount_type == DiscountType.FLAT:
            return min(self.discount_value, order_total)
        elif self.discount_type == DiscountType.PERCENTAGE:
            discount = order_total * (self.discount_value / 100)
            if self.max_discount:
                discount = min(discount, self.max_discount)
            return discount
        return Decimal("0")


# ── Cart ──────────────────────────────────────────────────────────────────

class Cart:
    """Shopping cart — can be guest or user-owned."""

    def __init__(self, cart_id: str, user_id: Optional[str] = None):
        self.cart_id  = cart_id
        self.user_id  = user_id
        self._items:  dict[str, CartItem] = {}  # product_id → CartItem
        self._coupon: Optional[Coupon] = None
        self.updated_at = datetime.now()

    # ── Item Management ───────────────────────────────────────────────────

    def add_item(self, product: Product, quantity: int = 1) -> CartItem:
        if not product.is_available(quantity):
            raise ValueError(f"'{product.name}' is out of stock or unavailable")

        if product.id in self._items:
            # Increase quantity
            existing = self._items[product.id]
            new_qty  = existing.quantity + quantity
            if not product.is_available(new_qty):
                raise ValueError(f"Only {product.stock} of '{product.name}' available")
            existing.update_quantity(new_qty)
        else:
            self._items[product.id] = CartItem(product=product, quantity=quantity)

        self.updated_at = datetime.now()
        return self._items[product.id]

    def remove_item(self, product_id: str) -> None:
        if product_id not in self._items:
            raise KeyError(f"Product {product_id} not in cart")
        del self._items[product_id]
        self.updated_at = datetime.now()

    def update_quantity(self, product_id: str, quantity: int) -> None:
        if product_id not in self._items:
            raise KeyError(f"Product {product_id} not in cart")
        if quantity <= 0:
            self.remove_item(product_id)
        else:
            self._items[product_id].update_quantity(quantity)
        self.updated_at = datetime.now()

    def clear(self) -> None:
        self._items.clear()
        self._coupon = None
        self.updated_at = datetime.now()

    # ── Coupon ────────────────────────────────────────────────────────────

    def apply_coupon(self, coupon: Coupon) -> None:
        if not coupon.is_valid(self.subtotal):
            raise ValueError(f"Coupon '{coupon.code}' is not valid "
                             f"for this order (min: ₹{coupon.min_order_value})")
        self._coupon = coupon

    def remove_coupon(self) -> None:
        self._coupon = None

    # ── Pricing ───────────────────────────────────────────────────────────

    @property
    def items(self) -> list[CartItem]:
        return list(self._items.values())

    @property
    def item_count(self) -> int:
        return sum(item.quantity for item in self._items.values())

    @property
    def subtotal(self) -> Decimal:
        """Price before tax and discounts."""
        return sum(item.subtotal for item in self._items.values())

    @property
    def tax_total(self) -> Decimal:
        return sum(item.tax for item in self._items.values())

    @property
    def discount(self) -> Decimal:
        if not self._coupon:
            return Decimal("0")
        return self._coupon.calculate_discount(self.subtotal + self.tax_total)

    @property
    def total(self) -> Decimal:
        return max(Decimal("0"), self.subtotal + self.tax_total - self.discount)

    def summary(self) -> dict:
        return {
            "cart_id":  self.cart_id,
            "items":    len(self._items),
            "subtotal": float(self.subtotal),
            "tax":      float(self.tax_total),
            "discount": float(self.discount),
            "coupon":   self._coupon.code if self._coupon else None,
            "total":    float(self.total),
        }


# ── Order ─────────────────────────────────────────────────────────────────

@dataclass
class OrderItem:
    product_id:   str
    product_name: str
    unit_price:   Decimal
    quantity:     int
    tax_rate:     Decimal

    @property
    def line_total(self) -> Decimal:
        return self.unit_price * self.quantity * (1 + self.tax_rate)

@dataclass
class Order:
    id:           str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id:      str = ""
    items:        list[OrderItem] = field(default_factory=list)
    discount:     Decimal = Decimal("0")
    coupon_code:  Optional[str] = None
    status:       str = "pending"
    created_at:   datetime = field(default_factory=datetime.now)

    @property
    def total(self) -> Decimal:
        return max(Decimal("0"),
                   sum(i.line_total for i in self.items) - self.discount)


# ── Checkout Service ───────────────────────────────────────────────────────

class CheckoutService:
    """Converts cart to order — validates stock, charges payment."""

    def __init__(self,
                 product_repo: "ProductRepository",
                 order_repo:   "OrderRepository",
                 payment_gw:   "PaymentGateway"):
        self._products = product_repo
        self._orders   = order_repo
        self._payment  = payment_gw

    def checkout(self, cart: Cart, user_id: str,
                 payment_method: str) -> Order:
        if not cart.items:
            raise ValueError("Cart is empty")

        # 1. Validate stock (pessimistic — reserve from DB)
        for item in cart.items:
            product = self._products.get_by_id(item.product.id)
            if not product or not product.is_available(item.quantity):
                raise ValueError(f"'{item.product.name}' is out of stock. "
                                 f"Available: {product.stock if product else 0}")

        # 2. Create order record
        order = Order(
            user_id     = user_id,
            discount    = cart.discount,
            coupon_code = cart._coupon.code if cart._coupon else None,
            items       = [
                OrderItem(
                    product_id   = ci.product.id,
                    product_name = ci.product.name,
                    unit_price   = ci.product.price,
                    quantity     = ci.quantity,
                    tax_rate     = ci.product.tax_rate,
                )
                for ci in cart.items
            ],
        )

        # 3. Process payment
        payment_result = self._payment.charge(
            amount  = float(cart.total),
            method  = payment_method,
            order_id = order.id,
        )
        if not payment_result["success"]:
            raise RuntimeError(f"Payment failed: {payment_result['error']}")

        # 4. Deduct stock (atomic in real system)
        for item in cart.items:
            self._products.deduct_stock(item.product.id, item.quantity)

        # 5. Save order
        order.status = "confirmed"
        self._orders.save(order)

        # 6. Clear cart
        cart.clear()

        return order


# ── Strategy Pattern for pricing ──────────────────────────────────────────

class PricingStrategy(ABC):
    @abstractmethod
    def calculate(self, cart: Cart) -> Decimal: ...

class StandardPricing(PricingStrategy):
    def calculate(self, cart: Cart) -> Decimal:
        return cart.total

class MemberPricing(PricingStrategy):
    """Members get 5% extra discount on top."""
    def calculate(self, cart: Cart) -> Decimal:
        return cart.total * Decimal("0.95")

class BulkPricing(PricingStrategy):
    """10% off if order > ₹5000."""
    def calculate(self, cart: Cart) -> Decimal:
        total = cart.total
        return total * Decimal("0.90") if total > 5000 else total
```

---

## Tests

```python
def test_cart_operations():
    p1 = Product("p1", "Python Book", Decimal("500"), stock=10, category="Books")
    p2 = Product("p2", "PyCharm IDE", Decimal("2000"), stock=5, category="Software",
                 tax_rate=Decimal("0.18"))
    
    cart = Cart("cart-001", user_id="user-123")

    # Add items
    cart.add_item(p1, 2)
    cart.add_item(p2, 1)
    assert cart.item_count == 3

    # Subtotal = 500×2 + 2000 = 3000
    assert cart.subtotal == Decimal("3000")

    # Apply 10% coupon (min order ₹1000)
    coupon = Coupon("SAVE10", DiscountType.PERCENTAGE, Decimal("10"), min_order_value=Decimal("1000"))
    cart.apply_coupon(coupon)
    
    # Total = (3000 + tax) - 10%
    print(f"Cart summary: {cart.summary()}")
    assert cart.discount > 0

    # Remove item
    cart.remove_item("p2")
    assert cart.item_count == 2

    # Update quantity
    cart.update_quantity("p1", 3)
    assert cart._items["p1"].quantity == 3

    print("Shopping Cart tests passed ✓")

test_cart_operations()
```

---

## Key Design Decisions

| Decision | Choice | Reason |
|---|---|---|
| Cart storage | Redis (real) / dict (in-process) | Fast reads, TTL expiry for guest carts |
| Price calculation | Decimal not float | Avoid floating-point rounding errors in money |
| Stock validation | Pessimistic locking (DB) | Prevent overselling |
| Coupon discount | Applied on total (after tax) | Common e-commerce standard |
| Guest cart | cart_id without user_id | Merge on login |
| State machine | Order status transitions | Clear lifecycle |

---

## Interview Q&A

**Q: How do you prevent overselling?**
A: (1) DB-level: `UPDATE products SET stock = stock - qty WHERE id = ? AND stock >= qty` — atomic. (2) Pessimistic lock: `SELECT FOR UPDATE`. (3) Optimistic lock: version column — retry on conflict.

**Q: How do you handle guest cart merging on login?**
A: Store guest cart in Redis with cart_id (in cookie). On login, fetch guest cart → merge items with user's existing cart → delete guest cart → associate with user_id.

**Q: How do you implement price locking (cart price doesn't change during checkout)?**
A: Store `unit_price` in CartItem when added (snapshot). Even if Product price changes, cart shows original price. Display warning if price changed.
