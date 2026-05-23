# Strategy Pattern
> **Category:** Behavioral | **Difficulty:** Easy-Medium | **Interview Frequency:** ★★★★★

---

## Quick Reference Card
```
Kya karta hai : Algorithm/behavior ko runtime pe swap karo — context class change kiye bina
Kab use karo  : Multiple payment methods, sorting algorithms, pricing strategies, discount rules
Key mechanism : Context class mein strategy inject karo — method call delegate karo
Real project  : Niroskos → PaymentMethod strategy | Youngman → DiscountStrategy
Pattern type  : Behavioral
```

---

## PART 1: HINGLISH — Samjhne ke liye

### 1.1 Kya hai?

Strategy pattern mein **algorithm ko alag class mein rakhte ho** — aur runtime pe swap kar sakte ho.

Context class ko nahi pata kaunsa algorithm use ho raha hai — woh sirf interface call karta hai.

**Simple analogy:**
```
Maps app — navigation strategy:
  Driving     → highways, speed
  Walking     → footpaths, shortcuts
  Cycling     → bike lanes, avoid highways
  Public Bus  → bus routes only

Same destination — alag alag strategy.
Maps app ka core nahi badla — sirf strategy swap hua.

Context = Maps App
Strategy = Driving / Walking / Cycling
```

---

### 1.2 Kab use karo?

```
✅ Multiple ways se ek kaam karna ho
✅ Runtime pe algorithm change karna ho (user ne payment method change kiya)
✅ if-elif ki badi chain hai behavior decide karne ke liye → Strategy mein shift karo
✅ Alag alag algorithms independently test karne ho
✅ Open/Closed Principle chahiye — naya algorithm add karo, context mat badlo
```

---

### 1.3 Kab mat use karo?

```
❌ Sirf ek hi algorithm use hoga — unnecessary abstraction
❌ Algorithms bahut similar hain — ek class mein parameter se handle ho sakta hai
❌ Strategy objects state rakhte hain — thread safety issue ho sakta hai
```

---

### 1.4 Code — Hinglish Comments ke saath

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


# ─── Abstract Strategy ───
class PaymentStrategy(ABC):
    """
    Har payment method ka alag algorithm hoga.
    Yeh common interface hai — context sirf isse jaanta hai.
    """
    @abstractmethod
    def initiate(self, amount: float, currency: str) -> dict:
        pass

    @abstractmethod
    def verify(self, event_id: str) -> bool:
        pass

    @abstractmethod
    def refund(self, txn_id: str, amount: float) -> dict:
        pass

    @property
    @abstractmethod
    def method_name(self) -> str:
        pass


# ─── Concrete Strategies — har ek ka alag algorithm ───

class CardPaymentStrategy(PaymentStrategy):
    """Stripe/Razorpay card — synchronous"""

    @property
    def method_name(self): return "card"

    def initiate(self, amount, currency):
        print(f"[CARD] Stripe PaymentIntent: {amount} {currency}")
        return {
            "status":        "pending",
            "client_secret": "pi_secret_xyz",
            "method":        self.method_name
        }

    def verify(self, event_id):
        print(f"[CARD] Stripe webhook verify: {event_id}")
        return True  # Synchronous — turant confirm

    def refund(self, txn_id, amount):
        print(f"[CARD] Stripe refund {amount} for {txn_id}")
        return {"status": "refunded", "refund_id": "re_xyz"}


class CryptoPaymentStrategy(PaymentStrategy):
    """Ethereum/USDT — blockchain scan karna padta hai"""

    @property
    def method_name(self): return "crypto"

    def initiate(self, amount, currency):
        print(f"[CRYPTO] USDT deposit address generate: {amount}")
        return {
            "status":          "pending_blockchain",
            "deposit_address": "0x742d35Cc...",
            "network":         "ERC20",
            "expires_in":      3600,
            "method":          self.method_name
        }

    def verify(self, event_id):
        # Blockchain scan — async Celery task se confirm hota hai
        print(f"[CRYPTO] Blockchain scan check: {event_id}")
        return True

    def refund(self, txn_id, amount):
        # Crypto refund manual hai — approval chahiye
        return {"status": "pending_approval", "requires_manual": True}


class MPesaPaymentStrategy(PaymentStrategy):
    """M-Pesa — Africa mobile money"""

    @property
    def method_name(self): return "mpesa"

    def initiate(self, amount, currency):
        print(f"[MPESA] STK push: {amount} KES")
        return {
            "status":       "stk_push_sent",
            "checkout_id":  "ws_CO_123456",
            "method":       self.method_name
        }

    def verify(self, event_id):
        print(f"[MPESA] M-Pesa confirmation: {event_id}")
        return True

    def refund(self, txn_id, amount):
        print(f"[MPESA] Reversal initiated: {amount}")
        return {"status": "reversal_initiated"}


class BankTransferStrategy(PaymentStrategy):
    """Manual bank transfer"""

    @property
    def method_name(self): return "bank_transfer"

    def initiate(self, amount, currency):
        return {
            "status":  "pending",
            "account": "HDFC-IFSC-001",
            "ref":     "TXN-REF-001",
            "method":  self.method_name
        }

    def verify(self, event_id):
        # Bank transfer manual verify hoti hai
        return True

    def refund(self, txn_id, amount):
        return {"status": "manual_bank_refund_initiated"}


# ─── Context — Strategy use karta hai ───
class PaymentContext:
    """
    Context ko nahi pata kaunsa strategy hai.
    Sirf PaymentStrategy interface call karta hai.
    Runtime pe strategy change kar sakte ho.
    """

    def __init__(self, strategy: PaymentStrategy):
        self._strategy = strategy  # Current strategy

    def set_strategy(self, strategy: PaymentStrategy):
        """Runtime pe change karo — user ne method badla"""
        self._strategy = strategy

    def process_payment(self, amount: float, currency: str) -> dict:
        # Strategy ko delegate karo — andar kya hoga pata nahi
        return self._strategy.initiate(amount, currency)

    def handle_webhook(self, event_id: str) -> bool:
        return self._strategy.verify(event_id)

    def process_refund(self, txn_id: str, amount: float) -> dict:
        result = self._strategy.refund(txn_id, amount)
        # Crypto manual refund ke liye special handling
        if result.get("requires_manual"):
            print("Manual refund approval queue mein add kiya")
        return result


# ─── Strategy Registry — Factory + Strategy combo ───
class PaymentStrategyFactory:
    """
    String se strategy object banao — OCP follow karo.
    Naya method? Sirf register karo — context nahi badlega.
    """
    _strategies = {
        'card':          CardPaymentStrategy,
        'crypto':        CryptoPaymentStrategy,
        'mpesa':         MPesaPaymentStrategy,
        'bank_transfer': BankTransferStrategy,
    }

    @classmethod
    def get(cls, method: str) -> PaymentStrategy:
        strategy_class = cls._strategies.get(method)
        if not strategy_class:
            raise ValueError(f"Unknown method: {method}. Available: {list(cls._strategies)}")
        return strategy_class()


# ─── Usage ───
# User ne card select kiya
context = PaymentContext(PaymentStrategyFactory.get('card'))
context.process_payment(10000, 'INR')

# User ne crypto switch kiya — runtime strategy change
context.set_strategy(PaymentStrategyFactory.get('crypto'))
context.process_payment(10000, 'USD')

# M-Pesa — Africa ke liye
context.set_strategy(PaymentStrategyFactory.get('mpesa'))
context.process_payment(5000, 'KES')


# ─── Real Example 2: Pricing Strategy (Youngman + Niroskos) ───
class PricingStrategy(ABC):
    @abstractmethod
    def calculate(self, base_price: float, guests: int) -> float:
        pass

    @abstractmethod
    def description(self) -> str:
        pass

class StandardPricing(PricingStrategy):
    def calculate(self, base_price, guests):
        return base_price * guests

    def description(self): return "Standard rate"

class GroupDiscountPricing(PricingStrategy):
    GROUP_DISCOUNT = 0.10  # 10% off

    def calculate(self, base_price, guests):
        total    = base_price * guests
        discount = total * self.GROUP_DISCOUNT
        return total - discount

    def description(self): return "Group discount (10% off)"

class SeasonalPricing(PricingStrategy):
    def __init__(self, multiplier: float):
        self._multiplier = multiplier

    def calculate(self, base_price, guests):
        return base_price * guests * self._multiplier

    def description(self): return f"Seasonal rate ({self._multiplier}x)"

class EarlyBirdPricing(PricingStrategy):
    DISCOUNT = 0.15  # 15% early bird

    def calculate(self, base_price, guests):
        total    = base_price * guests
        discount = total * self.DISCOUNT
        return total - discount

    def description(self): return "Early bird (15% off)"


class BookingPricingContext:
    def __init__(self, strategy: PricingStrategy):
        self._strategy = strategy

    def calculate_price(self, base_price: float, guests: int) -> dict:
        total = self._strategy.calculate(base_price, guests)
        return {
            "base_price":  base_price,
            "guests":      guests,
            "total":       total,
            "strategy":    self._strategy.description()
        }


# Usage
safari_price = 50000  # Per person

standard = BookingPricingContext(StandardPricing())
print(standard.calculate_price(safari_price, 2))   # 100000

group = BookingPricingContext(GroupDiscountPricing())
print(group.calculate_price(safari_price, 10))     # 450000 (10% off)

peak = BookingPricingContext(SeasonalPricing(1.5))
print(peak.calculate_price(safari_price, 2))       # 150000 (peak season)
```

---

### 1.5 Tumhara Real Project Mein Kahan Use Hua

```
Project 1 — Niroskos Safari Platform:
  → PaymentMethod Strategy
    Card (Stripe sync) vs Crypto (blockchain async) vs MPesa — teeno alag
    PaymentService context tha — strategy inject hoti thi
    Booking price calculation — Standard, Group, Seasonal strategies

Project 2 — Youngman (Existing Code):
  → DiscountStrategy (Open_Closed_Principle.py)
    PercentageDiscount vs FixedDiscount
    PriceCalculator context — strategy calculate() call karta tha

Project 3 — Sorting Strategies (tumhara code):
  → SortContext + QuickSort, MergeSort, BubbleSort
    Runtime pe sort strategy change karo
    SortContext.sort_data() delegate karta tha

Project 4 — Robot Architecture (tumhara code):
  → Talkable, Walkable, Flyable strategies
    Robot mein compose kiya — runtime pe behavior swap
```

---

## PART 2: ENGLISH — Interviewer ko bolne ke liye

### 2.1 Definition

> **Strategy is a behavioral pattern that defines a family of algorithms, encapsulates each one, and makes them interchangeable. The pattern lets the algorithm vary independently from the clients that use it.**

---

### 2.2 Problem It Solves

```python
# WITHOUT Strategy — if-elif chains, OCP violation
class PaymentService:
    def process(self, method: str, amount: float):
        if method == 'card':
            # 50 lines of card logic
        elif method == 'crypto':
            # 80 lines of crypto logic
        elif method == 'mpesa':
            # 40 lines of M-Pesa logic
        # Every new method → modify this class

# WITH Strategy — clean, extensible
class PaymentService:
    def __init__(self, strategy: PaymentStrategy):
        self._strategy = strategy

    def process(self, amount: float):
        return self._strategy.initiate(amount, 'USD')
    # New method → new class, zero change here
```

---

### 2.3 Key Components

| Component | Role | Example |
|-----------|------|---------|
| **Strategy** (Interface) | Common algorithm interface | `PaymentStrategy(ABC)` |
| **Concrete Strategies** | Algorithm implementations | `CardPaymentStrategy`, `CryptoPaymentStrategy` |
| **Context** | Uses strategy, delegates work | `PaymentContext` |
| **Client** | Creates and injects strategy | `PaymentContext(CardPaymentStrategy())` |

---

### 2.4 Clean Code Example

```python
from abc import ABC, abstractmethod

class SortStrategy(ABC):
    @abstractmethod
    def sort(self, data: list) -> list: pass

class QuickSort(SortStrategy):
    def sort(self, data):
        if len(data) <= 1: return data
        pivot  = data[len(data) // 2]
        left   = [x for x in data if x < pivot]
        middle = [x for x in data if x == pivot]
        right  = [x for x in data if x > pivot]
        return self.sort(left) + middle + self.sort(right)

class MergeSort(SortStrategy):
    def sort(self, data):
        if len(data) <= 1: return data
        mid   = len(data) // 2
        left  = self.sort(data[:mid])
        right = self.sort(data[mid:])
        return self._merge(left, right)

    def _merge(self, left, right):
        result = []
        i = j = 0
        while i < len(left) and j < len(right):
            if left[i] <= right[j]:
                result.append(left[i]); i += 1
            else:
                result.append(right[j]); j += 1
        return result + left[i:] + right[j:]

class Sorter:
    def __init__(self, strategy: SortStrategy):
        self._strategy = strategy

    def set_strategy(self, strategy: SortStrategy):
        self._strategy = strategy

    def sort(self, data: list) -> list:
        return self._strategy.sort(data)

data   = [64, 34, 25, 12, 22, 11, 90]
sorter = Sorter(QuickSort())
print(sorter.sort(data))   # QuickSort

sorter.set_strategy(MergeSort())
print(sorter.sort(data))   # MergeSort — same sorter, new algorithm
```

---

### 2.5 Real Project Answer

**"Tell me about Strategy pattern in your work"**

> "Strategy pattern is the backbone of Niroskos's payment system. We support four payment methods — Card via Stripe, Crypto (USDT/ETH via Web3), M-Pesa for Africa, and Bank Transfer. Each has a completely different flow: Card is synchronous with webhooks, Crypto requires blockchain scanning with a Celery task that reschedules itself every 10 seconds, M-Pesa sends an STK push, and Bank Transfer is manual.
>
> I defined a `PaymentStrategy` abstract class with `initiate()`, `verify()`, and `refund()` methods. Each payment method is a concrete strategy. The `PaymentService` (context) takes the strategy via constructor injection. Adding a new payment method — say Apple Pay — means writing one new class that implements `PaymentStrategy`. Zero changes to `PaymentService`.
>
> I also used a Strategy Registry (dict-based factory) so methods could be looked up by string key from the database, keeping configuration-driven behavior."

---

### 2.6 Follow-up Q&A

**Q: "Strategy vs State pattern — difference?"**
> "Both use similar structure but different intent. Strategy is about choosing an algorithm — the context doesn't change based on strategy (PaymentService always processes payments, just differently). State is about object lifecycle — the object's behavior changes as its internal state changes (Booking behaves differently when CONFIRMED vs PAID vs CANCELLED). Strategy strategies are usually interchangeable; State transitions are driven by the object's own logic."

**Q: "How is Strategy different from simple if-elif?"**
> "If-elif violates OCP — every new case requires modifying existing code. Strategy isolates each algorithm in its own class — independently testable, independently deployable. In a team, multiple developers can work on different strategies simultaneously without conflicts. Also, strategies can be stored in a database/config and loaded dynamically."

**Q: "Can Strategy maintain state?"**
> "Yes — Stateful strategies are valid. For example, `RateLimitStrategy` keeps call timestamps. But shared state in strategies needs thread safety. Stateless strategies are simpler and safer for concurrent systems — I used stateless strategies in the payment system since each request is independent."

---

## Strategy vs State vs Template Method

| | Strategy | State | Template Method |
|---|---------|-------|----------------|
| **Changes** | Algorithm | Object behavior by state | Step implementations |
| **Who decides** | Client/external | Object itself | Subclass |
| **Intent** | Interchangeable algorithms | State-driven behavior | Skeleton with variable steps |
| **Example** | Payment method | Booking status | EwayBillBuilder.build() |

---

*Last Updated: April 2026 | SDE-2 Interview Prep*
