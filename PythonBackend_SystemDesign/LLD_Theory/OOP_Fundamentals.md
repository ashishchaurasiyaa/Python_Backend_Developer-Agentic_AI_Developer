# OOP Fundamentals — Interview Preparation
> **Target Role:** SDE-2 Python Backend | **Company:** Interview Kickstart
> **Real Examples From:** Niroskos Safaris, Youngman ERP, Youngman Django Backend

---

## Table of Contents
1. [What is OOP?](#1-what-is-oop)
2. [Class & Object](#2-class--object)
3. [Encapsulation](#3-encapsulation)
4. [Inheritance](#4-inheritance)
5. [Polymorphism](#5-polymorphism)
6. [Abstraction](#6-abstraction)
7. [How All 4 Pillars Work Together](#7-how-all-4-pillars-work-together)
8. [Interview Questions & Answers](#8-interview-questions--answers)

---

## 1. What is OOP?

**Definition:**
Object-Oriented Programming ek programming paradigm hai jisme hum **real-world entities ko objects ke roop mein model karte hain**. Har object ke paas apna data (attributes) aur behavior (methods) hota hai.

**4 Pillars:**
```
1. Encapsulation  → Data chhupao, sirf zaruri cheezein expose karo
2. Inheritance    → Parent se properties inherit karo, reuse karo
3. Polymorphism   → Ek hi interface, alag alag behavior
4. Abstraction    → Complex details chhupao, simple interface do
```

**Procedural vs OOP:**
```python
# ❌ Procedural — sab kuch global, koi structure nahi
invoice_status = "PENDING"
customer_name  = "Tata Steel"
invoice_amount = 50000

def update_invoice_status(status):
    global invoice_status
    invoice_status = status

# ✅ OOP — data aur behavior ek saath, structured
class Invoice:
    def __init__(self, customer_name, amount):
        self.customer_name = customer_name
        self.amount        = amount
        self.status        = "PENDING"

    def mark_paid(self):
        self.status = "PAID"

invoice = Invoice("Tata Steel", 50000)
invoice.mark_paid()
```

---

## 2. Class & Object

### Class — Blueprint hai
```python
class Payment:
    """
    Blueprint for payment — actual payment nahi hai yeh.
    Real-world entity: Niroskos platform ka Payment model
    """
    # Class variable — sab objects share karte hain
    VALID_METHODS = ['card', 'crypto', 'mpesa', 'bank']

    def __init__(self, order, method, amount):
        # Instance variables — har object ka apna hota hai
        self.order   = order
        self.method  = method
        self.amount  = amount
        self.status  = 'PENDING'

    def mark_completed(self):
        self.status = 'COMPLETED'
```

### Object — Class ka instance hai
```python
# payment1 aur payment2 — dono alag objects, same blueprint
payment1 = Payment(order=order_A, method='card',   amount=10000)
payment2 = Payment(order=order_B, method='crypto', amount=25000)

# Har object ka apna state
payment1.mark_completed()

print(payment1.status)  # COMPLETED
print(payment2.status)  # PENDING — payment2 affect nahi hua
```

### Real Project Example — Niroskos
```python
# apps/payments/models/payment.py
# Yahan har row ek Payment object hai database mein
# - PAY-20240413-A3F2B1 → object 1
# - PAY-20240413-B7C9D2 → object 2
# Dono alag objects, same Payment class

class Payment(TimeStampedModel):
    order           = ForeignKey(Order, on_delete=CASCADE)
    method          = CharField(choices=PaymentMethod.choices)
    amount          = DecimalField(max_digits=12, decimal_places=2)
    provider_fee    = DecimalField(max_digits=10, decimal_places=2)
    net_amount      = DecimalField(max_digits=12, decimal_places=2)
    status          = CharField(choices=PaymentStatus.choices)
```

---

## 3. Encapsulation

### Definition
> **Data aur methods ko ek unit (class) mein band karna, aur internal details ko bahar se chhupana.**

```
Public    → Koi bhi access kar sakta hai       → self.name
Protected → Sirf class aur subclass            → self._token
Private   → Sirf class ke andar               → self.__secret_key
```

### Python mein Encapsulation
```python
class SAPHANAConnector:
    """
    Real example: Youngman ERP mein SAP HANA integration
    4858+ lines ka connector — bahar walo ko details nahi chahiye
    """

    def __init__(self, base_url, username, password):
        self._base_url   = base_url       # protected
        self.__username  = username       # private
        self.__password  = password       # private
        self.__token     = None           # private
        self.__token_expiry = None        # private

    # ✅ Public interface — yahi expose karo
    def get_token(self) -> str:
        """Caller ko sirf token chahiye — kaise milta hai yeh mat batao"""
        if self.__is_token_valid():
            return self.__token
        return self.__fetch_new_token()

    def sync_invoice(self, invoice_data: dict) -> bool:
        """Invoice SAP mein push karo — internal logic hidden"""
        token = self.get_token()
        return self.__post_to_sap('/invoices', invoice_data, token)

    # ❌ Private methods — bahar se call nahi karna chahiye
    def __is_token_valid(self) -> bool:
        if not self.__token or not self.__token_expiry:
            return False
        from datetime import datetime
        return datetime.now() < self.__token_expiry

    def __fetch_new_token(self) -> str:
        import requests
        response = requests.post(
            f"{self._base_url}/auth",
            json={"username": self.__username, "password": self.__password}
        )
        self.__token = response.json()['token']
        from datetime import datetime, timedelta
        self.__token_expiry = datetime.now() + timedelta(minutes=5)
        return self.__token

    def __post_to_sap(self, endpoint, data, token) -> bool:
        import requests
        response = requests.post(
            f"{self._base_url}{endpoint}",
            json=data,
            headers={"Authorization": f"Bearer {token}"}
        )
        return response.status_code == 201


# Usage — caller ko andar ki complexity nahi dikhti
sap = SAPHANAConnector(
    base_url="https://sap.youngman.com",
    username="admin",
    password="secret"  # encapsulated — bahar nahi jaata
)

# Simple public API
sap.sync_invoice({"invoice_no": "INV-001", "amount": 50000})
# sap.__password  → AttributeError — protected hai!
```

### Why Encapsulation? — Interview Answer
```
1. Data Protection  → Password, token bahar nahi jaata
2. Flexibility      → Andar ka implementation badlo, API same rahe
3. Maintainability  → Ek jagah change karo, sab jagah reflect ho
4. Validation       → Data set hone se pehle validate kar sako
```

### Validation with Property (Advanced Encapsulation)
```python
class BookingDraft:
    def __init__(self):
        self._status = 'DRAFT'

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, new_status):
        VALID_TRANSITIONS = {
            'DRAFT':     ['CONFIRMED', 'EXPIRED', 'ABANDONED'],
            'CONFIRMED': ['EXPIRED'],
            'EXPIRED':   [],
            'ABANDONED': [],
        }
        if new_status not in VALID_TRANSITIONS[self._status]:
            raise ValueError(
                f"Invalid transition: {self._status} → {new_status}"
            )
        self._status = new_status

# Usage
draft = BookingDraft()
draft.status = 'CONFIRMED'   # ✅ OK
draft.status = 'DRAFT'       # ❌ ValueError — wapas nahi ja sakte
```

---

## 4. Inheritance

### Definition
> **Ek class doosri class ke properties aur methods inherit kare — code reuse aur hierarchy.**

### Types of Inheritance
```
1. Single        → Child inherits one Parent
2. Multi-level   → A → B → C (chain)
3. Multiple      → Child inherits multiple Parents (Python supports)
4. Hierarchical  → One Parent, many Children
```

### Single Inheritance — Real Example
```python
# Niroskos project ka actual pattern

class TimeStampedModel:
    """Base class — timestamps har jagah chahiye"""
    def __init__(self):
        from datetime import datetime
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

    def get_age(self) -> str:
        from datetime import datetime
        diff = datetime.now() - self.created_at
        if diff.days > 0:
            return f"{diff.days} days ago"
        hours = diff.seconds // 3600
        return f"{hours} hours ago"


class Payment(TimeStampedModel):
    """Payment ko timestamps chahiye — inherit karo"""
    def __init__(self, amount, method):
        super().__init__()          # Parent ka __init__ call karo
        self.amount = amount
        self.method = method
        self.status = 'PENDING'

    def mark_completed(self):
        self.status = 'COMPLETED'
        from datetime import datetime
        self.updated_at = datetime.now()  # parent ka field use kiya


payment = Payment(10000, 'card')
print(payment.created_at)    # Parent se mila
print(payment.get_age())     # Parent ka method — "0 hours ago"
print(payment.status)        # Apna field
```

### Multi-level Inheritance — Youngman Django Pattern
```python
# apps/core/models.py — ACTUAL PROJECT CODE PATTERN

class TimestampedModel:
    """Level 1 — Basic timestamps"""
    created_at = None  # auto_now_add
    updated_at = None  # auto_now


class AuditedModel(TimestampedModel):
    """Level 2 — Who created/updated"""
    created_by = None  # FK to User
    updated_by = None  # FK to User

    def save_with_user(self, user):
        if not self.created_by:
            self.created_by = user
        self.updated_by = user


class SoftDeleteModel(AuditedModel):
    """Level 3 — Logical deletion"""
    is_deleted = False
    deleted_at = None
    deleted_by = None

    def soft_delete(self, user):
        self.is_deleted = True
        self.deleted_by = user
        from datetime import datetime
        self.deleted_at = datetime.now()


class Invoice(SoftDeleteModel):
    """
    Invoice ko sab chahiye:
    - Timestamps (Level 1)
    - Audit trail (Level 2)
    - Soft delete (Level 3)
    """
    def __init__(self, invoice_number, amount):
        self.invoice_number = invoice_number
        self.amount         = amount
        self.status         = 'PENDING'

    def mark_paid(self):
        self.status = 'PAID'


# Invoice ko automatically milta hai:
invoice = Invoice("INV-001", 50000)
invoice.save_with_user(current_user)  # AuditedModel se
invoice.soft_delete(current_user)     # SoftDeleteModel se
print(invoice.created_at)             # TimestampedModel se
```

### Multiple Inheritance — Niroskos Booking Mixins
```python
# Niroskos ka actual booking.py pattern

class ContactInfoMixin:
    """Contact details — Booking aur Customer dono mein chahiye"""
    def __init__(self):
        self.first_name = ''
        self.last_name  = ''
        self.email      = ''
        self.phone      = ''

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"


class PricingMixin:
    """Pricing logic — Booking aur Quote dono mein chahiye"""
    def __init__(self):
        self.base_price      = 0
        self.discount_amount = 0

    def get_total(self):
        return self.base_price - self.discount_amount


class CancellationMixin:
    """Cancel logic — Booking specific"""
    def cancel(self, reason):
        self.status         = 'CANCELLED'
        self.cancel_reason  = reason
        self.cancelled_at   = __import__('datetime').datetime.now()


class Booking(ContactInfoMixin, PricingMixin, CancellationMixin):
    """
    Multiple inheritance — teen mixins se ek Booking
    MRO (Method Resolution Order): Booking → ContactInfo → Pricing → Cancellation
    """
    def __init__(self, package, travel_date):
        ContactInfoMixin.__init__(self)
        PricingMixin.__init__(self)
        self.package     = package
        self.travel_date = travel_date
        self.status      = 'CONFIRMED'


booking = Booking(package='Masai Mara Safari', travel_date='2024-06-15')
booking.first_name = 'Rahul'
booking.base_price = 150000
print(booking.get_full_name())  # ContactInfoMixin se
print(booking.get_total())      # PricingMixin se
booking.cancel("Budget issue")  # CancellationMixin se
```

### Method Resolution Order (MRO) — Important
```python
# Python MRO — C3 Linearization Algorithm
class A:
    def hello(self):
        return "A"

class B(A):
    def hello(self):
        return "B"

class C(A):
    def hello(self):
        return "C"

class D(B, C):  # Multiple inheritance
    pass

d = D()
print(d.hello())         # "B" — B pehle check hota hai
print(D.__mro__)         # (D, B, C, A, object) — MRO order

# super() MRO follow karta hai — yahi use karo always
class Payment(TimeStampedModel):
    def __init__(self, amount):
        super().__init__()   # MRO ke according next class call
        self.amount = amount
```

---

## 5. Polymorphism

### Definition
> **Ek hi interface, alag alag implementations. "Poly" = many, "morph" = forms.**

### 2 Types:
```
1. Compile-time (Method Overloading) → Python mein default parameter se
2. Runtime     (Method Overriding)   → Child class parent ka method override kare
```

### Runtime Polymorphism — Payment Strategy (Your Real Code)
```python
from abc import ABC, abstractmethod

# Abstract base — common interface define karo
class PaymentMethod(ABC):

    @abstractmethod
    def initiate(self, amount: float, currency: str) -> dict:
        pass

    @abstractmethod
    def verify(self, transaction_id: str) -> bool:
        pass

    @abstractmethod
    def refund(self, transaction_id: str, amount: float) -> bool:
        pass


# Concrete implementations — har ek alag behave karta hai

class CardPayment(PaymentMethod):
    """Stripe/Razorpay card payment"""

    def initiate(self, amount, currency):
        print(f"[CARD] Charging {amount} {currency} via Stripe")
        return {
            "payment_intent_id": "pi_3N2kJF",
            "client_secret": "pi_secret_xyz",
            "method": "card"
        }

    def verify(self, transaction_id):
        print(f"[CARD] Verifying {transaction_id} with Stripe webhook")
        return True

    def refund(self, transaction_id, amount):
        print(f"[CARD] Refunding {amount} via Stripe refund API")
        return True


class CryptoPayment(PaymentMethod):
    """Ethereum/USDT Web3 payment — Niroskos platform"""

    def initiate(self, amount, currency):
        print(f"[CRYPTO] Generating deposit address for {amount} USDT")
        return {
            "deposit_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f2bd48",
            "network":         "ERC20",
            "amount_token":    amount / 84.5,   # USD to USDT
            "expires_in":      3600
        }

    def verify(self, transaction_id):
        print(f"[CRYPTO] Scanning blockchain for tx: {transaction_id}")
        # Block scanner task check karo
        return True

    def refund(self, transaction_id, amount):
        print(f"[CRYPTO] Manual refund approval required for {amount}")
        # Crypto refund workflow — manual approval
        return False


class MPesaPayment(PaymentMethod):
    """M-Pesa mobile money — Africa market"""

    def initiate(self, amount, currency):
        print(f"[MPESA] Sending STK push for {amount} KES")
        return {
            "checkout_request_id": "ws_CO_123456",
            "response_code":       "0",
            "method":              "mpesa"
        }

    def verify(self, transaction_id):
        print(f"[MPESA] Checking M-Pesa confirmation: {transaction_id}")
        return True

    def refund(self, transaction_id, amount):
        print(f"[MPESA] Initiating M-Pesa reversal for {amount}")
        return True


# ✅ POLYMORPHISM — ek hi code, alag alag behavior
class PaymentService:
    """
    PaymentService ko nahi pata kon sa payment method hai
    Woh sirf PaymentMethod interface ke saath kaam karta hai
    """

    def process_payment(self, method: PaymentMethod, amount: float, currency: str):
        # Yahan 'method' Card, Crypto, MPesa — kuch bhi ho sakta hai
        result = method.initiate(amount, currency)   # Polymorphic call
        print(f"Payment initiated: {result}")
        return result

    def handle_refund(self, method: PaymentMethod, txn_id: str, amount: float):
        success = method.refund(txn_id, amount)   # Polymorphic call
        if success:
            print("Refund processed successfully")
        else:
            print("Manual refund intervention required")


# Usage — same service, alag alag payment methods
service = PaymentService()

card_method   = CardPayment()
crypto_method = CryptoPayment()
mpesa_method  = MPesaPayment()

# Ek hi process_payment() call — teen alag behaviors
service.process_payment(card_method,   10000, 'USD')
service.process_payment(crypto_method, 10000, 'USD')
service.process_payment(mpesa_method,  10000, 'KES')
```

### Duck Typing — Python ka Polymorphism
```python
# Python mein interface implement karna compulsory nahi
# Agar method hai → kaam karega

class EmailNotification:
    def send(self, message, recipient):
        print(f"[EMAIL] Sending to {recipient}: {message}")

class SMSNotification:
    def send(self, message, recipient):
        print(f"[SMS] Sending to {recipient}: {message}")

class SlackNotification:
    def send(self, message, recipient):
        print(f"[SLACK] Posting to #{recipient}: {message}")

# Polymorphism without inheritance!
def notify_user(notification_service, message, recipient):
    notification_service.send(message, recipient)  # Duck typing

# Same function, alag behavior
notify_user(EmailNotification(), "Booking confirmed!", "rahul@gmail.com")
notify_user(SMSNotification(),   "Booking confirmed!", "+919876543210")
notify_user(SlackNotification(), "New booking alert", "bookings-channel")
```

### Method Overriding — Serializer Strategy (Youngman Django)
```python
class BaseSerializer:
    def serialize(self, obj) -> dict:
        raise NotImplementedError

class CustomerListSerializer(BaseSerializer):
    """Lightweight — list view ke liye"""
    def serialize(self, customer) -> dict:
        return {
            "id":   customer.id,
            "name": customer.name,
            "gstn": customer.gstn,
        }

class CustomerDetailSerializer(BaseSerializer):
    """Full details — detail view ke liye"""
    def serialize(self, customer) -> dict:
        return {
            "id":              customer.id,
            "name":            customer.name,
            "gstn":            customer.gstn,
            "credit_limit":    customer.credit_limit,
            "credit_rating":   customer.credit_rating,
            "account_manager": customer.account_manager.name,
            "branches":        [b.gstn for b in customer.branches.all()],
            "contacts":        [c.name for c in customer.contacts.all()],
        }

class CustomerViewSet:
    def get_serializer(self, action):
        # Runtime mein decide hota hai — polymorphism!
        if action == 'list':
            return CustomerListSerializer()
        return CustomerDetailSerializer()
```

---

## 6. Abstraction

### Definition
> **Complex implementation details chhupao, sirf relevant interface expose karo.**
> "What it does" dikhao, "How it does" mat dikhao.

### Abstract Class vs Interface
```python
from abc import ABC, abstractmethod

# Abstract Class — kuch methods implemented, kuch abstract
class NotificationChannel(ABC):

    # Abstract — subclass MUST implement karna hoga
    @abstractmethod
    def send(self, recipient: str, message: str) -> bool:
        pass

    @abstractmethod
    def validate_recipient(self, recipient: str) -> bool:
        pass

    # Concrete — common logic already implemented
    def send_with_retry(self, recipient: str, message: str, max_retries=3) -> bool:
        """Retry logic common hai — har subclass ko repeat nahi karna"""
        for attempt in range(max_retries):
            try:
                if self.validate_recipient(recipient):
                    return self.send(recipient, message)
            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    raise
        return False


class PostmarkEmailChannel(NotificationChannel):
    """Abstract methods implement karo — details yahan hide hain"""

    def validate_recipient(self, recipient: str) -> bool:
        import re
        return bool(re.match(r'^[\w.-]+@[\w.-]+\.\w+$', recipient))

    def send(self, recipient: str, message: str) -> bool:
        print(f"[POSTMARK] Sending email to {recipient}")
        # Postmark API call — implementation detail
        # Caller ko nahi pata POST request kab gaya, headers kya the
        return True


class TwilioSMSChannel(NotificationChannel):
    """SMS specific implementation"""

    def validate_recipient(self, recipient: str) -> bool:
        return recipient.startswith('+') and len(recipient) >= 10

    def send(self, recipient: str, message: str) -> bool:
        print(f"[TWILIO] Sending SMS to {recipient}")
        # Twilio API call — implementation detail
        return True


# Caller ko sirf interface dikhta hai
def send_booking_confirmation(channel: NotificationChannel, user_contact: str):
    message = "Your safari booking is confirmed! 🦁"
    channel.send_with_retry(user_contact, message)   # Retry logic free milta hai

send_booking_confirmation(PostmarkEmailChannel(), "rahul@gmail.com")
send_booking_confirmation(TwilioSMSChannel(),     "+254712345678")
```

### Abstraction in Service Layer — Niroskos
```python
# PaymentService — abstraction ka best example
# Caller ko nahi pata:
# - Database mein kaise save hota hai
# - Transaction log kaise hota hai
# - Order status kaise update hota hai
# - Notification kaise jaati hai

class PaymentService:

    def initiate_payment(self, order_id: int, method: str, amount: float) -> dict:
        """
        Simple public interface — caller sirf yeh jaanta hai:
        - order_id do
        - method do
        - amount do
        → Payment initiate ho jaayega
        """
        # Internal complexity — caller ko nahi dikhta
        order   = self._get_order(order_id)             # hidden
        payment = self._create_payment(order, method, amount)  # hidden
        self._log_transaction(payment, 'INITIATED')     # hidden
        self._notify_team(payment)                      # hidden
        return {"payment_ref": payment.reference, "status": "PENDING"}

    # Private methods — implementation details
    def _get_order(self, order_id):
        pass  # DB query

    def _create_payment(self, order, method, amount):
        pass  # Payment object create

    def _log_transaction(self, payment, event_type):
        pass  # Audit log

    def _notify_team(self, payment):
        pass  # Slack/Email notification
```

---

## 7. How All 4 Pillars Work Together

### Real Example — Complete Booking System

```python
from abc import ABC, abstractmethod
from datetime import datetime, timedelta


# ─────────────────────────────────────────
# ABSTRACTION — Common interface define karo
# ─────────────────────────────────────────
class BaseBooking(ABC):

    @abstractmethod
    def confirm(self) -> bool:
        pass

    @abstractmethod
    def cancel(self, reason: str) -> bool:
        pass

    @abstractmethod
    def calculate_price(self) -> float:
        pass


# ─────────────────────────────────────────
# ENCAPSULATION — Data protect karo
# ─────────────────────────────────────────
class Package:
    def __init__(self, name: str, base_price: float, duration_days: int):
        self.name           = name
        self.__base_price   = base_price      # private
        self._duration_days = duration_days   # protected

    @property
    def price(self) -> float:
        return self.__base_price

    @price.setter
    def price(self, value: float):
        if value < 0:
            raise ValueError("Price cannot be negative")
        self.__base_price = value


# ─────────────────────────────────────────
# INHERITANCE — Reuse karo
# ─────────────────────────────────────────
class TimestampMixin:
    def __init__(self):
        self.created_at = datetime.now()
        self.updated_at = datetime.now()


class Booking(BaseBooking, TimestampMixin):
    """
    Abstraction: BaseBooking se interface
    Inheritance: TimestampMixin se timestamps
    """
    VALID_TRANSITIONS = {
        'CONFIRMED': ['PAID', 'CANCELLED'],
        'PAID':      ['CANCELLED', 'RESCHEDULED'],
        'CANCELLED': [],
        'RESCHEDULED': ['PAID']
    }

    def __init__(self, package: Package, travel_date: datetime, guests: int):
        TimestampMixin.__init__(self)
        self.package     = package
        self.travel_date = travel_date
        self.guests      = guests
        self.__status    = 'CONFIRMED'   # Encapsulated

        # Amendment deadline — business rule encapsulated
        days = 3 if package._duration_days >= 3 else 1
        self.__amendment_deadline = travel_date - timedelta(days=days)

    @property
    def status(self):
        return self.__status

    def _transition_to(self, new_status: str):
        if new_status not in self.VALID_TRANSITIONS[self.__status]:
            raise ValueError(
                f"Cannot transition from {self.__status} to {new_status}"
            )
        self.__status   = new_status
        self.updated_at = datetime.now()

    def is_locked(self) -> bool:
        return datetime.now() > self.__amendment_deadline

    # ─────────────────────────────────────
    # POLYMORPHISM — Override abstract methods
    # ─────────────────────────────────────
    def confirm(self) -> bool:
        print(f"Booking confirmed for {self.package.name}")
        return True

    def cancel(self, reason: str) -> bool:
        if self.is_locked():
            raise PermissionError("Cannot cancel — amendment deadline passed")
        self._transition_to('CANCELLED')
        print(f"Booking cancelled. Reason: {reason}")
        return True

    def calculate_price(self) -> float:
        return self.package.price * self.guests


class GroupBooking(Booking):
    """
    POLYMORPHISM — calculate_price override karo
    Group discount milti hai
    """
    GROUP_DISCOUNT = 0.10  # 10%

    def calculate_price(self) -> float:
        base_price = super().calculate_price()
        discount   = base_price * self.GROUP_DISCOUNT
        print(f"Group discount applied: -{discount}")
        return base_price - discount


# ─────────────────────────────────────────
# Main flow — Sab pillars ek saath
# ─────────────────────────────────────────
masai_mara = Package("Masai Mara Safari", base_price=50000, duration_days=5)

# Regular booking
solo_booking = Booking(
    package=masai_mara,
    travel_date=datetime(2024, 6, 15),
    guests=2
)
print(f"Price: {solo_booking.calculate_price()}")    # 100000
print(f"Status: {solo_booking.status}")              # CONFIRMED

# Group booking — POLYMORPHISM
group_booking = GroupBooking(
    package=masai_mara,
    travel_date=datetime(2024, 6, 15),
    guests=10
)
print(f"Group Price: {group_booking.calculate_price()}")  # 450000 (10% off)

# Encapsulation — private field protect
# solo_booking.__status = 'PAID'  → AttributeError!
solo_booking._transition_to('PAID')   # Proper way
print(f"Status after payment: {solo_booking.status}")   # PAID
```

---

## 8. Interview Questions & Answers

---

### Q1: "OOP kya hai? 4 pillars explain karo."

**Answer:**
> "OOP ek programming paradigm hai jisme real-world entities ko objects se model karte hain. 4 pillars hain —
>
> **Encapsulation** — Data aur methods ek class mein band karna. Maine SAP HANA connector mein use kiya — token, password sab private fields the, bahar sirf `get_token()` expose tha.
>
> **Inheritance** — Code reuse ke liye. Youngman Django backend mein `TimestampedModel → AuditedModel → SoftDeleteModel` chain banaya. 30+ models mein timestamps aur audit fields repeat nahi kiye.
>
> **Polymorphism** — Ek interface, alag behavior. Niroskos mein `PaymentMethod` abstract class banayi — `CardPayment`, `CryptoPayment`, `MPesaPayment` sab alag alag implement karte hain. `PaymentService` ko pata nahi kaunsa hai.
>
> **Abstraction** — Complex details chhupao. `PaymentService.initiate_payment()` mein caller ko nahi pata DB query, transaction log, notification sab internally ho raha hai."

---

### Q2: "Encapsulation vs Abstraction — difference kya hai?"

| | Encapsulation | Abstraction |
|---|---|---|
| **Kya karta hai** | Data hide karta hai | Complexity hide karta hai |
| **Focus** | Data protection | Implementation hiding |
| **Kaise** | Private/protected fields | Abstract class, interface |
| **Example** | `self.__password` | `PaymentMethod(ABC)` |
| **Real** | SAP token private field | PaymentService public API |

---

### Q3: "Multiple inheritance mein MRO kya hota hai?"

**Answer:**
> "MRO — Method Resolution Order. Jab multiple parents mein same method ho, Python C3 Linearization algorithm se decide karta hai kaunsa pehle call hoga. `D(B, C)` mein `D → B → C → A` order hoga. `super()` always MRO follow karta hai isliye main always `super()` use karta hun `ParentClass.__init__()` ke bajaye. Maine Niroskos mein `Booking(ContactInfoMixin, PricingMixin, CancellationMixin)` banaya — teeno ke `__init__` alag call kiye kyunki state initialize karna tha."

---

### Q4: "Abstract class vs Interface difference kya hai Python mein?"

**Answer:**
> "Python mein dedicated interface keyword nahi hai. Abstract class `ABC` se banate hain. Difference:
> - Abstract class mein kuch methods implemented ho sakte hain, kuch abstract
> - Pure interface mein sab abstract hote hain
>
> Maine Niroskos mein `NotificationChannel(ABC)` banaya — `send()` aur `validate_recipient()` abstract the, lekin `send_with_retry()` concretely implemented tha kyunki retry logic common tha sab channels mein."

---

### Q5: "Real project mein polymorphism kahan use kiya?"

**Answer:**
> "Niroskos platform mein payment system design kiya. `PaymentMethod` abstract class thi — `CardPayment`, `CryptoPayment`, `MPesaPayment` teeno implement karte the. `PaymentService.process_payment(method, amount)` ko nahi pata tha method kaunsa type hai. Jab naya payment method add karna ho — sirf naya class likho, `PaymentService` touch nahi karna. Yeh Open/Closed Principle bhi hai — extension ke liye open, modification ke liye closed."

---

### Q6: "Why is `super()` important?"

```python
class A:
    def __init__(self):
        print("A init")

class B(A):
    def __init__(self):
        super().__init__()   # ✅ MRO follow karta hai
        print("B init")

class C(A):
    def __init__(self):
        super().__init__()
        print("C init")

class D(B, C):
    def __init__(self):
        super().__init__()
        print("D init")

D()
# Output: A init → C init → B init → D init
# super() MRO (D→B→C→A) follow karta hai — A sirf ek baar call hua
```

---

### Q7: "Composition vs Inheritance — kab kya use karein?"

```
Inheritance → "IS-A" relationship
    GroupBooking IS-A Booking ✅

Composition → "HAS-A" relationship
    Booking HAS-A Package ✅
    Booking HAS-A Payment ✅
```

**Rule of thumb:**
> "Inheritance tab use karo jab child truly parent ka type ho. Baki cases mein composition prefer karo — zyada flexible hai, tightly coupled nahi hota. Maine Niroskos mein `Booking` ke andar `Package` object rakha — inherit nahi kiya — kyunki Booking, Package nahi hai, Package use karti hai."

---

### Quick Revision — 2 Minute Summary

```
ENCAPSULATION  → Data + Methods ek class mein | Private fields
                 Example: SAP token private, sirf get_token() expose

INHERITANCE    → Parent se properties lena | Code reuse
                 Example: TimestampedModel → AuditedModel → SoftDeleteModel

POLYMORPHISM   → Same interface, alag behavior | Override/Overload
                 Example: CardPayment, CryptoPayment, MPesaPayment — sab .initiate()

ABSTRACTION    → Complex chhupao, simple dikhao | ABC
                 Example: PaymentService — caller ko DB/log/notify ka pata nahi
```

---

*Last Updated: April 2026 | Prepared for SDE-2 Interview at Interview Kickstart*
