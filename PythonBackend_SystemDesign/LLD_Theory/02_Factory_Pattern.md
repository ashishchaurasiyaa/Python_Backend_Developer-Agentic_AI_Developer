# Factory Pattern
> **Category:** Creational | **Difficulty:** Easy-Medium | **Interview Frequency:** ★★★★★

---

## Quick Reference Card
```
Kya karta hai : Object creation logic ek jagah — caller ko nahi pata kaunsa class ban raha hai
Kab use karo  : Payment gateways, File parsers, Logger types, E-way bill types
Key mechanism : Static/class method jo string input lekar correct object return kare
Real project  : Niroskos → PaymentMethodFactory | Youngman → EwayBillFactory
Pattern type  : Creational
```

---

## PART 1: HINGLISH — Samjhne ke liye

### 1.1 Kya hai?

Factory pattern mein **ek class hoti hai jiska kaam sirf objects banana hota hai**.

Caller ko nahi pata ki andar kaunsa class use ho raha hai — woh sirf bolta hai "mujhe yeh type chahiye" aur Factory correct object de deti hai.

**Simple analogy:**
```
Tum restaurant mein jaate ho aur bolte ho "Dosa do".
Tum nahi jaante kitchen mein kaunsa chef banayega, kaunsa pan use hoga.
Tum sirf order dete ho → sahi cheez milti hai.

Factory = Restaurant counter
Object  = Dosa / Idli / Vada (jo manga woh mila)
```

---

### 1.2 Kab use karo?

```
✅ Payment gateways     → "card" bolo → CardPayment mile, "crypto" bolo → CryptoPayment
✅ File parsers         → ".csv" → CSVParser, ".json" → JSONParser, ".xml" → XMLParser
✅ Logger types         → "file" → FileLogger, "console" → ConsoleLogger
✅ E-way bill           → "Delivery" → DeliveryBuilder, "Pickup" → PickupBuilder
✅ Notification channel → "email" → EmailChannel, "sms" → SMSChannel
✅ Jab if-elif ki chain ho object banane ke liye → Factory mein shift karo
```

---

### 1.3 Kab mat use karo?

```
❌ Sirf ek hi type ka object hai — unnecessary complexity
❌ Object creation simple hai — direct instantiation theek hai
❌ Related objects ka family banana hai — Abstract Factory use karo
```

---

### 1.4 Code — Hinglish Comments ke saath

```python
from abc import ABC, abstractmethod

# ─── Abstract Product — common interface ───
class PaymentProcessor(ABC):
    @abstractmethod
    def process(self, amount: float) -> dict:
        pass

    @abstractmethod
    def refund(self, transaction_id: str) -> dict:
        pass


# ─── Concrete Products — actual implementations ───

class CardPaymentProcessor(PaymentProcessor):
    # Card payment — Stripe/Razorpay use karta hai
    def process(self, amount):
        print(f"[CARD] Stripe se {amount} charge ho raha hai")
        return {"status": "success", "method": "card", "txn_id": "txn_card_001"}

    def refund(self, transaction_id):
        print(f"[CARD] Stripe refund: {transaction_id}")
        return {"status": "refunded"}


class CryptoPaymentProcessor(PaymentProcessor):
    # Crypto payment — blockchain deposit address generate karta hai
    def process(self, amount):
        print(f"[CRYPTO] USDT deposit address generate ho raha hai: {amount}")
        return {
            "status":          "pending",
            "method":          "crypto",
            "deposit_address": "0x742d35Cc...",
            "network":         "ERC20"
        }

    def refund(self, transaction_id):
        # Crypto refund manual hota hai — automatic nahi
        return {"status": "manual_approval_required"}


class MPesaPaymentProcessor(PaymentProcessor):
    # M-Pesa — Africa ke liye mobile money
    def process(self, amount):
        print(f"[MPESA] STK push ja raha hai: {amount} KES")
        return {"status": "stk_sent", "method": "mpesa", "checkout_id": "ws_CO_123"}

    def refund(self, transaction_id):
        return {"status": "reversal_initiated"}


class BankTransferProcessor(PaymentProcessor):
    def process(self, amount):
        print(f"[BANK] Bank transfer details: {amount}")
        return {"status": "pending", "method": "bank", "account": "HDFC-001"}

    def refund(self, transaction_id):
        return {"status": "manual_bank_refund"}


# ─── Factory — yahi magic karta hai ───
class PaymentProcessorFactory:
    """
    Caller ko sirf payment type batana hai.
    Factory andar se sahi class bana ke deta hai.
    Naya payment method aaya → sirf yahan add karo — baaki kuch nahi badlega.
    """

    # Registry pattern — dict mein sab mapping
    _processors = {
        'card':          CardPaymentProcessor,
        'crypto':        CryptoPaymentProcessor,
        'mpesa':         MPesaPaymentProcessor,
        'bank_transfer': BankTransferProcessor,
    }

    @classmethod
    def create(cls, payment_type: str) -> PaymentProcessor:
        processor_class = cls._processors.get(payment_type.lower())

        if processor_class is None:
            available = ', '.join(cls._processors.keys())
            raise ValueError(
                f"Unknown payment type: '{payment_type}'. "
                f"Available: {available}"
            )

        return processor_class()  # Object banao aur return karo

    @classmethod
    def register(cls, payment_type: str, processor_class):
        """
        Naya payment method add karna ho → bas yahan register karo
        Factory class modify nahi karni padegi — OCP ✅
        """
        cls._processors[payment_type] = processor_class


# ─── Usage — caller itna simple hai ───
factory = PaymentProcessorFactory()

# String se object ban jaata hai — caller ko class import nahi karni
card   = PaymentProcessorFactory.create('card')
crypto = PaymentProcessorFactory.create('crypto')
mpesa  = PaymentProcessorFactory.create('mpesa')

card.process(10000)    # [CARD] Stripe se 10000 charge...
crypto.process(50000)  # [CRYPTO] USDT deposit address...
mpesa.process(5000)    # [MPESA] STK push ja raha hai...


# ─── Real Project Example — EwayBill Factory (Youngman) ───
class EwayBillFactory:
    """
    Challan type ke basis par sahi builder return karo.
    'Delivery' → DeliveryBuilder (Company → Customer)
    'Pickup'   → PickupBuilder   (Customer → Company)
    """

    _builders = {
        'Delivery': 'DeliveryEwayBillBuilder',
        'Pickup':   'PickupEwayBillBuilder',
    }

    @classmethod
    def create_builder(cls, challan, params):
        builder_name = cls._builders.get(challan.challan_type)

        if builder_name is None:
            raise ValueError(f"Unsupported challan type: {challan.challan_type}")

        # Dynamic import — OCP ke liye
        # Naya challan type → sirf dict mein add karo
        return builder_name(challan=challan, params=params)
```

---

### 1.5 Tumhara Real Project Mein Kahan Use Hua

```
Project 1 — Niroskos Safari Platform:
  → PaymentProcessorFactory — 'card', 'crypto', 'mpesa', 'bank'
    PaymentService ko nahi pata kaunsa processor hai
    factory.create(payment.method) se object milta tha

Project 2 — Youngman Django Backend:
  → EwayBillFactory — 'Delivery' ya 'Pickup' challan type
    challan.challan_type string se sahi Builder class return hoti thi
    View ko DeliveryBuilder ya PickupBuilder directly import nahi karna pada

Project 3 — Youngman Laravel (Existing code):
  → PaymentGatewayFactory — PayPal, Stripe, Razorpay
    Factory.create_payment_gateway('paypal', client_id, secret)
```

---

## PART 2: ENGLISH — Interviewer ko bolne ke liye

### 2.1 Definition

> **Factory Method is a creational pattern that provides an interface for creating objects, but lets subclasses or a factory class decide which class to instantiate. It decouples object creation from object usage.**

---

### 2.2 Problem It Solves

```python
# Without Factory — tightly coupled, hard to extend
class PaymentService:
    def process(self, payment_type, amount):
        if payment_type == 'card':
            processor = CardPaymentProcessor()   # Direct dependency
        elif payment_type == 'crypto':
            processor = CryptoPaymentProcessor() # Direct dependency
        # Every new type → modify this class (OCP violation)
        processor.process(amount)

# With Factory — loosely coupled, easy to extend
class PaymentService:
    def process(self, payment_type, amount):
        processor = PaymentProcessorFactory.create(payment_type)  # Factory
        processor.process(amount)
        # New payment type → only add to factory, nothing else changes
```

---

### 2.3 Key Components

| Component | Role | Example |
|-----------|------|---------|
| **Product** (Abstract) | Common interface for all objects | `PaymentProcessor(ABC)` |
| **Concrete Products** | Actual implementations | `CardPaymentProcessor`, `CryptoPaymentProcessor` |
| **Factory** | Creates and returns correct product | `PaymentProcessorFactory.create('card')` |
| **Client** | Uses factory — doesn't know concrete class | `PaymentService` |

---

### 2.4 Clean Code Example

```python
from abc import ABC, abstractmethod
from typing import Type

class PaymentProcessor(ABC):
    @abstractmethod
    def process(self, amount: float) -> dict: pass

    @abstractmethod
    def refund(self, txn_id: str) -> dict: pass


class CardPaymentProcessor(PaymentProcessor):
    def process(self, amount):
        return {"method": "card", "status": "completed", "amount": amount}

    def refund(self, txn_id):
        return {"status": "refunded", "txn_id": txn_id}


class CryptoPaymentProcessor(PaymentProcessor):
    def process(self, amount):
        return {"method": "crypto", "status": "pending_confirmation", "amount": amount}

    def refund(self, txn_id):
        return {"status": "manual_approval_required"}


class PaymentProcessorFactory:
    _registry: dict[str, Type[PaymentProcessor]] = {
        'card':   CardPaymentProcessor,
        'crypto': CryptoPaymentProcessor,
    }

    @classmethod
    def create(cls, payment_type: str) -> PaymentProcessor:
        klass = cls._registry.get(payment_type)
        if not klass:
            raise ValueError(f"Unsupported payment type: {payment_type}")
        return klass()

    @classmethod
    def register(cls, name: str, klass: Type[PaymentProcessor]) -> None:
        cls._registry[name] = klass


# New payment type — zero change to existing code (OCP ✅)
class MPesaPaymentProcessor(PaymentProcessor):
    def process(self, amount):
        return {"method": "mpesa", "status": "stk_push_sent"}

    def refund(self, txn_id):
        return {"status": "reversal_initiated"}

PaymentProcessorFactory.register('mpesa', MPesaPaymentProcessor)

# Usage
processor = PaymentProcessorFactory.create('mpesa')
print(processor.process(5000))
```

---

### 2.5 Real Project Answer

**"Where did you use the Factory pattern?"**

> "In two projects:
>
> **Niroskos** — The payment system supports Card, Crypto (Web3/USDT), M-Pesa, and Bank Transfer. Instead of if-elif chains in `PaymentService`, I used a `PaymentProcessorFactory` with a registry dict. The service calls `factory.create(payment.method)` and gets the correct processor. When we added Bank Transfer, I just registered a new class — `PaymentService` was untouched. This is Open/Closed Principle in action.
>
> **Youngman Django Backend** — The E-way bill system handles two challan types: Delivery (Company → Customer) and Pickup (Customer → Company). The `EwayBillFactory` takes `challan.challan_type` string and returns the correct builder — `DeliveryEwayBillBuilder` or `PickupEwayBillBuilder`. The view only called `factory.create_builder(challan, params).build()` — completely decoupled from builder implementation details."

---

### 2.6 Follow-up Q&A

**Q: "Factory vs Abstract Factory — difference?"**
> "Factory creates ONE type of product — you pass a string, get back an object. Abstract Factory creates a FAMILY of related products — you get a factory object that can create multiple related types. Example: Factory gives you a `PaymentProcessor`. Abstract Factory gives you a `PaymentFactory` which creates both `PaymentProcessor` AND `RefundProcessor` that are guaranteed to be compatible."

**Q: "What's the Registry pattern in Factory?"**
> "Instead of if-elif, I use a dict mapping strings to classes: `_registry = {'card': CardPayment, 'crypto': CryptoPayment}`. To add new types: `register('mpesa', MPesaPayment)`. This is cleaner, follows OCP, and allows dynamic registration at runtime — like plugin systems."

**Q: "How is Factory different from just calling a constructor?"**
> "Direct constructor couples the caller to the concrete class — if you change the class name, all callers break. Factory provides an abstraction layer — caller only knows the interface, not the implementation. It also centralizes creation logic — if construction needs parameters, validation, or caching, it's all in one place."

---

## Factory vs Abstract Factory vs Builder

| Aspect | Factory | Abstract Factory | Builder |
|--------|---------|-----------------|---------|
| Creates | Single object | Family of related objects | One complex object step-by-step |
| Input | Type string | Factory object | Builder method calls |
| Example | `create('card')` → processor | `get_factory('India')` → Indian notification suite | `builder.set_from().set_to().build()` |
| Use when | Multiple variants of one type | Multiple related types must be compatible | Object has many optional parts |

---

*Last Updated: April 2026 | SDE-2 Interview Prep*
