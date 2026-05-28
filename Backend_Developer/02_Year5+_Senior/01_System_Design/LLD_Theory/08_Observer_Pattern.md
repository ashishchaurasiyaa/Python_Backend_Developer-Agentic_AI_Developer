# Observer Pattern
> **Category:** Behavioral | **Difficulty:** Easy-Medium | **Interview Frequency:** ★★★★★

---

## Quick Reference Card
```
Kya karta hai : Ek object ka state change hone pe automatically sabko notify karo
Kab use karo  : Event systems, notifications, cache invalidation, UI updates
Key mechanism : Subject observers list rakhta hai — state change pe sabko update() call
Real project  : Niroskos → Django Signals (PaymentAllocation → Booking cache) | Laravel → Events
Pattern type  : Behavioral
```

---

## PART 1: HINGLISH — Samjhne ke liye

### 1.1 Kya hai?

Observer pattern mein **ek object (subject) apne "subscribers" (observers) ko automatically batata hai jab uska state change hota hai**.

Observers ko polling nahi karni — woh subscribe karte hain, aur automatically notification milti hai.

**Simple analogy:**
```
YouTube channel subscribe karna:
  Channel = Subject
  Subscribers = Observers
  Video upload = State change
  Notification = update() call

Tum baar baar YouTube nahi check karte — notification aati hai.
Channel ko pata nahi kitne subscribers hain — woh sab ko broadcast karta hai.
```

---

### 1.2 Kab use karo?

```
✅ Ek object ka change → multiple objects ko affect kare
✅ Event-driven architecture — loose coupling chahiye
✅ Cache invalidation — data change → cache clear karo
✅ Real-time notifications — payment complete → user ko email/SMS
✅ Audit logging — koi bhi change → log record
✅ UI reactive updates — model change → view update
✅ Django Signals → post_save, post_delete ya custom signals
```

---

### 1.3 Kab mat use karo?

```
❌ Observers ki chain bahut lambi ho — debugging nightmare
❌ Order of notification matter karta hai — Observer mein guarantee nahi
❌ Memory leaks — observers unsubscribe nahi kiye (weak references use karo)
❌ Synchronous processing mein bottleneck ho sakta hai
```

---

### 1.4 Code — Hinglish Comments ke saath

```python
from abc import ABC, abstractmethod
from typing import List


# ─── Observer Interface ───
class Observer(ABC):
    @abstractmethod
    def update(self, event_type: str, data: dict) -> None:
        pass


# ─── Subject (Observable) ───
class Subject:
    def __init__(self):
        self._observers: List[Observer] = []  # Subscribers ki list

    def subscribe(self, observer: Observer):
        if observer not in self._observers:
            self._observers.append(observer)
            print(f"[SUBJECT] {observer.__class__.__name__} subscribed")

    def unsubscribe(self, observer: Observer):
        if observer in self._observers:
            self._observers.remove(observer)

    def notify(self, event_type: str, data: dict):
        # Sab observers ko notify karo
        for observer in self._observers:
            observer.update(event_type, data)


# ─── Concrete Observers — booking complete hone pe kya karna hai ───

class EmailNotificationObserver(Observer):
    """Booking complete → customer ko email"""
    def update(self, event_type, data):
        if event_type == 'BOOKING_CONFIRMED':
            print(f"[EMAIL] Confirmation to {data['email']}: Booking {data['ref_code']}")
        elif event_type == 'PAYMENT_COMPLETED':
            print(f"[EMAIL] Receipt to {data['email']}: Rs {data['amount']}")

class SMSNotificationObserver(Observer):
    """Payment complete → SMS"""
    def update(self, event_type, data):
        if event_type == 'PAYMENT_COMPLETED':
            print(f"[SMS] to {data['phone']}: Payment of Rs {data['amount']} received")

class AuditLogObserver(Observer):
    """Sab events ko audit trail mein log karo"""
    def update(self, event_type, data):
        print(f"[AUDIT] {event_type}: {data}")
        # DB mein save karo
        # AuditLog.objects.create(event=event_type, data=data)

class BookingCacheObserver(Observer):
    """Payment complete → booking ka cached amount refresh karo"""
    def update(self, event_type, data):
        if event_type in ('PAYMENT_COMPLETED', 'REFUND_PROCESSED'):
            booking_id = data.get('booking_id')
            if booking_id:
                # Booking ka cached amount_paid, balance_due refresh karo
                print(f"[CACHE] Booking {booking_id} payment cache refresh")
                # booking.refresh_payment_cache()

class SlackAlertObserver(Observer):
    """High-value bookings pe team ko Slack notification"""
    def update(self, event_type, data):
        if event_type == 'BOOKING_CONFIRMED' and data.get('amount', 0) > 100000:
            print(f"[SLACK] #bookings: High-value booking! Rs {data['amount']}")


# ─── Event-driven Booking Service ───
class BookingService(Subject):
    """
    BookingService = Subject
    State change hone pe automatically sab observers notify ho jaate hain
    Service ko nahi pata kaun subscribe hai — decoupled!
    """

    def confirm_booking(self, booking) -> bool:
        booking['status'] = 'CONFIRMED'

        # Ek line — sab observers automatically notify
        self.notify('BOOKING_CONFIRMED', {
            'ref_code': booking['ref_code'],
            'email':    booking['email'],
            'phone':    booking['phone'],
            'amount':   booking['amount'],
        })
        return True

    def complete_payment(self, booking, amount: float) -> bool:
        # Observers ko notify karo — yeh log directly nahi lete
        self.notify('PAYMENT_COMPLETED', {
            'booking_id': booking['id'],
            'ref_code':   booking['ref_code'],
            'email':      booking['email'],
            'phone':      booking['phone'],
            'amount':     amount,
        })
        return True

    def process_refund(self, booking, amount: float) -> bool:
        self.notify('REFUND_PROCESSED', {
            'booking_id': booking['id'],
            'amount':     amount,
        })
        return True


# ─── Setup — observers wire karo ───
service = BookingService()

# Observers subscribe karein
service.subscribe(EmailNotificationObserver())
service.subscribe(SMSNotificationObserver())
service.subscribe(AuditLogObserver())
service.subscribe(BookingCacheObserver())
service.subscribe(SlackAlertObserver())

booking = {
    'id': 123, 'ref_code': 'BKG-001',
    'email': 'rahul@gmail.com', 'phone': '+919876543210',
    'amount': 150000, 'status': 'PENDING'
}

# Ek call → sab observers trigger
service.confirm_booking(booking)
service.complete_payment(booking, 150000)
# Email, SMS, Audit, Cache, Slack — sab automatically fire!


# ─── Django Signals — Python ka built-in Observer ───
"""
Django mein Observer pattern BUILT-IN hai — Signals ke roop mein.
Tumhara actual Niroskos code:
"""

# Niroskos ka actual signal (apps/payments/signals.py):
from django.db.models.signals import post_save
from django.dispatch import receiver

# @receiver(post_save, sender=PaymentAllocation)
# def update_booking_cache_on_allocation(sender, instance, created, **kwargs):
#     """
#     PaymentAllocation save hone pe → Booking cache refresh karo
#
#     Subject: PaymentAllocation (Django model)
#     Observer: yeh function
#     Signal: post_save
#     """
#     booking = instance.order_item.content_object
#     if isinstance(booking, Booking):
#         booking.refresh_payment_cache()
#         # amount_paid aur balance_due update ho jaate hain
#         # Booking list pe N+1 queries avoid hoti hain


# Django Signal vs Manual Observer:
# Django Signal = built-in Observer mechanism
# Subject = any Model (post_save, post_delete, pre_save)
# Observer = @receiver decorated function
# Notify = Django automatically call karta hai signal ke baad


# ─── Custom Django Signal ───
from django.dispatch import Signal

# Custom signal define karo
booking_confirmed  = Signal()
payment_completed  = Signal()

# Observers — koi bhi file mein likhein, decoupled
# @receiver(booking_confirmed)
# def send_confirmation_email(sender, booking, **kwargs):
#     EmailNotificationService().send_booking_confirmation(booking)
#
# @receiver(booking_confirmed)
# def log_booking_event(sender, booking, **kwargs):
#     AuditLog.objects.create(event='BOOKING_CONFIRMED', ...)
#
# @receiver(payment_completed)
# def refresh_booking_cache(sender, booking, payment, **kwargs):
#     booking.refresh_payment_cache()

# Sender — signal fire karo
# booking_confirmed.send(sender=Booking, booking=booking_obj)
# payment_completed.send(sender=Payment, booking=booking_obj, payment=payment_obj)
```

---

### 1.5 Tumhara Real Project Mein Kahan Use Hua

```
Project 1 — Niroskos (Django Signals):
  Signal: post_save on PaymentAllocation
  Observer: update_booking_cache_on_allocation()
  Kya hua: Payment allocate hone pe booking ka amount_paid, balance_due
           automatically refresh ho jaata tha
  Benefit: N+1 queries avoid — booking list fast thi

  Signal: m2m_changed on StaffProfile.extra_groups
  Observer: sync_staff_extra_groups()
  Kya hua: Staff ke extra groups change hone pe user.groups
           automatically sync ho jaate the

Project 2 — Youngman Laravel (Events/Listeners):
  Subject: Challan delivery pipeline
  Events:  VehicleLoaded, VehicleOutForDelivery,
           MaterialDeliveredAndInstalled, PickupDone
  Observers: ListnVehicleLoaded (notification), ListnPickupDone (invoice trigger)
  Benefit: Challan stage change → notification alag service mein — decoupled

Project 3 — Youngman Django:
  Odoo webhook = Observer pattern
  Subject: Odoo (external system)
  Observer: OdooWebhookMixin.odoo_sync() endpoint
  Kya hua: Odoo mein customer update → webhook → local DB sync
```

---

## PART 2: ENGLISH — Interviewer ko bolne ke liye

### 2.1 Definition

> **Observer is a behavioral pattern that defines a one-to-many dependency between objects. When one object (Subject) changes state, all its dependents (Observers) are notified and updated automatically. It implements the publish-subscribe mechanism.**

---

### 2.2 Problem It Solves

```
Without Observer — tight coupling:
  class PaymentService:
      def complete_payment(self, payment):
          # Business logic
          payment.status = 'COMPLETED'

          # Directly calling other services — tightly coupled!
          EmailService().send_receipt(payment)    # What if email fails?
          SMSService().send_sms(payment)          # Adding WhatsApp? Modify this class
          BookingService().refresh_cache(payment) # More coupling
          AuditLogger().log(payment)              # Grows forever

With Observer — loose coupling:
  class PaymentService(Subject):
      def complete_payment(self, payment):
          payment.status = 'COMPLETED'
          self.notify('PAYMENT_COMPLETED', payment_data)
          # Done. Observers handle the rest. Payment service knows nothing.
```

---

### 2.3 Key Components

| Component | Role | Example |
|-----------|------|---------|
| **Subject** | Maintains observers list, fires events | `BookingService(Subject)` |
| **Observer** (Interface) | Defines update() contract | `Observer(ABC)` |
| **Concrete Observers** | Handle specific events | `EmailNotificationObserver` |
| **Event/Data** | What changed and relevant data | `{'event': 'PAYMENT_COMPLETED', 'amount': 10000}` |

---

### 2.4 Clean Code Example

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any

class Observer(ABC):
    @abstractmethod
    def update(self, event: str, data: Dict[str, Any]) -> None: pass

class Subject:
    def __init__(self):
        self._observers: List[Observer] = []

    def subscribe(self, observer: Observer) -> None:
        self._observers.append(observer)

    def unsubscribe(self, observer: Observer) -> None:
        self._observers.remove(observer)

    def notify(self, event: str, data: Dict[str, Any]) -> None:
        for observer in self._observers:
            observer.update(event, data)

class EmailObserver(Observer):
    def update(self, event, data):
        if event == 'PAYMENT_COMPLETED':
            print(f"Email receipt sent to {data['email']}")

class CacheObserver(Observer):
    def update(self, event, data):
        if event in ('PAYMENT_COMPLETED', 'REFUND_PROCESSED'):
            print(f"Cache invalidated for booking {data['booking_id']}")

class OrderService(Subject):
    def complete_payment(self, order_id: int, amount: float, email: str):
        # Business logic
        print(f"Payment {amount} processed for order {order_id}")
        # Notify all observers
        self.notify('PAYMENT_COMPLETED', {
            'booking_id': order_id,
            'amount': amount,
            'email': email
        })

service = OrderService()
service.subscribe(EmailObserver())
service.subscribe(CacheObserver())
service.complete_payment(123, 10000, "user@example.com")
# Both email and cache update fire automatically
```

---

### 2.5 Real Project Answer

**"Explain Observer pattern from your project"**

> "I used Observer pattern in two distinct ways in production:
>
> **Django Signals in Niroskos** — When a `PaymentAllocation` was saved (money allocated to a booking item), a `post_save` signal fired. The signal handler `update_booking_cache_on_allocation` refreshed the booking's cached `amount_paid` and `balance_due` fields. The payment system had zero knowledge of the booking cache — completely decoupled. This prevented N+1 queries on booking list views where we needed payment totals.
>
> The second signal was on `StaffProfile.extra_groups` (M2M field). When staff permissions changed, an `m2m_changed` signal kept Django's `user.groups` in sync automatically.
>
> **Laravel Events in Youngman ERP** — The challan delivery pipeline had 8 stages. Each stage transition fired an event — `VehicleLoaded`, `MaterialDeliveredAndInstalled`, `PickupDone`. Listeners handled notifications and triggered downstream processes like invoice generation. The ChallanStage model didn't know about notifications — it just fired events."

---

### 2.6 Follow-up Q&A

**Q: "Observer vs Pub-Sub — difference?"**
> "Observer: Subject directly knows its observers, calls them synchronously. Tight coupling between subject and observer (both in same process). Pub-Sub: Publisher and Subscriber don't know each other — message broker (Redis, RabbitMQ) sits between. Asynchronous, decoupled across services. Django Signals = Observer. Celery with Redis = Pub-Sub."

**Q: "What are the risks of Observer pattern?"**
> "Three main risks: (1) Memory leaks — if observers don't unsubscribe, subject holds references. Fix: weak references. (2) Unexpected cascades — one update triggers another observer which triggers another. (3) Order dependency — if observers must execute in sequence, plain Observer doesn't guarantee order. Solution: priority queue or explicit ordering."

**Q: "How does Django Signal differ from regular Observer?"**
> "Django Signal is Python's implementation of Observer with extras: `sender` parameter lets observers filter by which model fired (not just event type), `dispatch_uid` prevents duplicate signal connections, and `@receiver` is syntactic sugar for `signal.connect()`. The mechanism is identical — Signal object maintains handlers list, `send()` calls all handlers."

---

## Observer vs Pub-Sub

| | Observer | Pub-Sub |
|---|---------|---------|
| **Coupling** | Subject knows observers | Publisher and Subscriber decoupled |
| **Communication** | Direct method call | Via message broker |
| **Sync/Async** | Usually synchronous | Usually asynchronous |
| **Scope** | Same process/application | Across services/systems |
| **Example** | Django Signals | Celery + Redis/RabbitMQ |
| **Real use** | PaymentAllocation → Booking cache | Invoice created → SAP sync task |

---

*Last Updated: April 2026 | SDE-2 Interview Prep*
