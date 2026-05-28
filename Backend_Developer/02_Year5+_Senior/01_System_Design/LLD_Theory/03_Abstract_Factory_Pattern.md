# Abstract Factory Pattern
> **Category:** Creational | **Difficulty:** Medium | **Interview Frequency:** ★★★★☆

---

## Quick Reference Card
```
Kya karta hai : Related objects ki FAMILY banata hai — sab compatible hote hain
Kab use karo  : Cross-platform UI, multi-region notifications, themed components
Key mechanism : Factory of factories — ek factory object jo multiple related objects banata hai
Real project  : Niroskos → Multi-channel notification suite per tenant
Pattern type  : Creational
```

---

## PART 1: HINGLISH — Samjhne ke liye

### 1.1 Kya hai?

Abstract Factory mein **ek factory object milta hai jo ek poori family of related objects banata hai**.

Factory Pattern: "Mujhe ek payment processor do" → ek object milta hai
Abstract Factory: "Mujhe India ke liye poora notification suite do" → email + SMS + WhatsApp — sab India ke compatible

**Simple analogy:**
```
Socho tum ghar furnish kar rahe ho.
Option A: IKEA style → IKEA sofa + IKEA table + IKEA lamp (sab match karte hain)
Option B: Premium style → Premium sofa + Premium table + Premium lamp

Tum Factory se ek sofa nahi maangoge.
Tum Abstract Factory se bologe "IKEA suite do" → sab saman compatible milega.

Factory    = "Ek sofa do"
Abstract Factory = "Poora IKEA living room do"
```

---

### 1.2 Kab use karo?

```
✅ Cross-platform UI        → Windows buttons + checkboxes, Mac buttons + checkboxes
✅ Multi-region systems     → India notifications (SMS=Twilio) vs Africa (SMS=Africas Talking)
✅ Themed components        → Dark theme buttons + Dark inputs vs Light theme
✅ Database drivers         → MySQL family (connection + cursor + transaction)
✅ Cloud providers          → AWS family (S3 + EC2 + RDS) vs GCP (Storage + Compute + SQL)
✅ Jab family of objects ka compatibility ensure karna ho
```

---

### 1.3 Kab mat use karo?

```
❌ Sirf ek type ka object chahiye — simple Factory enough hai
❌ Objects alag alag independent hain — family nahi hain
❌ Zyada complexity add ho rahi hai without benefit
```

---

### 1.4 Code — Hinglish Comments ke saath

```python
from abc import ABC, abstractmethod

# ─── Abstract Products — do related cheezein ───
class EmailProvider(ABC):
    @abstractmethod
    def send_email(self, to: str, subject: str, body: str) -> bool:
        pass

class SMSProvider(ABC):
    @abstractmethod
    def send_sms(self, phone: str, message: str) -> bool:
        pass

class PushProvider(ABC):
    @abstractmethod
    def send_push(self, device_token: str, message: str) -> bool:
        pass


# ─── Concrete Products — India family ───
class PostmarkEmailProvider(EmailProvider):
    # India ke liye Postmark email use karo
    def send_email(self, to, subject, body):
        print(f"[POSTMARK-IN] Email → {to}: {subject}")
        return True

class TwilioIndiaSMSProvider(SMSProvider):
    # India ke liye Twilio SMS (Indian DLT compliance)
    def send_sms(self, phone, message):
        print(f"[TWILIO-IN] SMS → {phone}: {message}")
        return True

class FirebasePushProvider(PushProvider):
    # Firebase push — India mein Android users zyada
    def send_push(self, device_token, message):
        print(f"[FIREBASE] Push → {device_token}: {message}")
        return True


# ─── Concrete Products — Africa family ───
class MailgunAfricaEmailProvider(EmailProvider):
    # Africa ke liye Mailgun
    def send_email(self, to, subject, body):
        print(f"[MAILGUN-AF] Email → {to}: {subject}")
        return True

class AfricasTalkingSMSProvider(SMSProvider):
    # Africa ke liye Africa's Talking (local SMS provider)
    def send_sms(self, phone, message):
        print(f"[AFRICAS-TALKING] SMS → {phone}: {message}")
        return True

class APNSPushProvider(PushProvider):
    # Africa mein iPhone users zyada — APNS use karo
    def send_push(self, device_token, message):
        print(f"[APNS] Push → {device_token}: {message}")
        return True


# ─── Abstract Factory — interface ───
class NotificationFactory(ABC):
    """
    Ek factory jo ek poori notification suite banata hai.
    Email + SMS + Push — sab ek region ke compatible.
    """

    @abstractmethod
    def create_email_provider(self) -> EmailProvider:
        pass

    @abstractmethod
    def create_sms_provider(self) -> SMSProvider:
        pass

    @abstractmethod
    def create_push_provider(self) -> PushProvider:
        pass


# ─── Concrete Factories — region specific ───
class IndiaNotificationFactory(NotificationFactory):
    # India ke liye poora suite — sab India-compatible
    def create_email_provider(self):
        return PostmarkEmailProvider()

    def create_sms_provider(self):
        return TwilioIndiaSMSProvider()

    def create_push_provider(self):
        return FirebasePushProvider()


class AfricaNotificationFactory(NotificationFactory):
    # Africa ke liye poora suite — sab Africa-compatible
    def create_email_provider(self):
        return MailgunAfricaEmailProvider()

    def create_sms_provider(self):
        return AfricasTalkingSMSProvider()

    def create_push_provider(self):
        return APNSPushProvider()


# ─── Client — factory inject karo, details nahi pata ───
class BookingNotificationService:
    """
    Service ko nahi pata India ka factory hai ya Africa ka.
    Woh sirf NotificationFactory interface se kaam karta hai.
    """

    def __init__(self, factory: NotificationFactory):
        # Dependency Injection + Abstract Factory — dono ek saath
        self.email = factory.create_email_provider()
        self.sms   = factory.create_sms_provider()
        self.push  = factory.create_push_provider()

    def send_booking_confirmation(self, booking):
        self.email.send_email(
            to      = booking.user.email,
            subject = f"Booking Confirmed: {booking.ref_code}",
            body    = f"Your safari on {booking.travel_date} is confirmed!"
        )
        self.sms.send_sms(
            phone   = booking.user.phone,
            message = f"Booking {booking.ref_code} confirmed!"
        )
        self.push.send_push(
            device_token = booking.user.device_token,
            message      = "Your safari booking is confirmed 🦁"
        )


# ─── Usage ───
# India region ke liye booking service
india_service = BookingNotificationService(
    factory=IndiaNotificationFactory()   # India suite inject karo
)

# Africa region ke liye booking service
africa_service = BookingNotificationService(
    factory=AfricaNotificationFactory()  # Africa suite inject karo
)

# Code same hai — factory alag hai!
# india_service  → Postmark + Twilio India + Firebase
# africa_service → Mailgun + Africa's Talking + APNS
```

---

### 1.5 Tumhara Real Project Mein Kahan Use Hua

```
Project 1 — Niroskos Safari Platform:
  → Multi-tenant notification system
    Alag alag subsidiaries ke liye alag alag providers
    SubsidiaryNotificationFactory: ek factory jo email + SMS + push
    sab ek subsidiary ke compatible de

Project 2 — Existing Code (Pizza.py):
  → IndianPizzaFactory → IndianVegPizza + IndianNonVegPizza (family)
  → USPizzaFactory     → AmericanVegPizza + AmericanNonVegPizza (family)
  → Factory ensure karta tha ki Indian factory se American pizza na nikle

Project 3 — Existing Code (Abstract_Factory.py):
  → WindowsFactory → WindowsButton + WindowsCheckbox (sab Windows style)
  → MacFactory     → MacButton + MacCheckbox (sab Mac style)
```

---

## PART 2: ENGLISH — Interviewer ko bolne ke liye

### 2.1 Definition

> **Abstract Factory is a creational pattern that provides an interface for creating families of related or dependent objects without specifying their concrete classes. It guarantees that the products created are compatible with each other.**

---

### 2.2 Problem It Solves

```
Problem: You need multiple related objects that must be compatible.
         Creating them independently risks incompatibility.

Example: India notification → Twilio SMS + Postmark Email (both India-compliant)
         If you create SMS independently → might get Africa's Talking (wrong!)

Abstract Factory guarantees:
  IndiaFactory.create_sms()   → always India-compatible SMS
  IndiaFactory.create_email() → always India-compatible email
  They're designed to work together.
```

---

### 2.3 Key Components

| Component | Role | Example |
|-----------|------|---------|
| **Abstract Product** | Interface for each product type | `EmailProvider(ABC)`, `SMSProvider(ABC)` |
| **Concrete Products** | Region-specific implementations | `PostmarkEmailProvider`, `TwilioIndiaSMSProvider` |
| **Abstract Factory** | Interface to create product family | `NotificationFactory(ABC)` |
| **Concrete Factory** | Creates compatible product family | `IndiaNotificationFactory` |
| **Client** | Uses factory — doesn't know region | `BookingNotificationService` |

---

### 2.4 Clean Code Example

```python
from abc import ABC, abstractmethod

# Abstract Products
class EmailProvider(ABC):
    @abstractmethod
    def send(self, to: str, body: str) -> bool: pass

class SMSProvider(ABC):
    @abstractmethod
    def send(self, phone: str, msg: str) -> bool: pass

# India Family
class PostmarkEmail(EmailProvider):
    def send(self, to, body):
        return True  # Postmark API

class TwilioSMS(SMSProvider):
    def send(self, phone, msg):
        return True  # Twilio API

# Africa Family
class MailgunEmail(EmailProvider):
    def send(self, to, body):
        return True  # Mailgun API

class AfricasTalkingSMS(SMSProvider):
    def send(self, phone, msg):
        return True  # Africa's Talking API

# Abstract Factory
class NotificationFactory(ABC):
    @abstractmethod
    def email(self) -> EmailProvider: pass

    @abstractmethod
    def sms(self) -> SMSProvider: pass

# Concrete Factories
class IndiaFactory(NotificationFactory):
    def email(self): return PostmarkEmail()
    def sms(self):   return TwilioSMS()

class AfricaFactory(NotificationFactory):
    def email(self): return MailgunEmail()
    def sms(self):   return AfricasTalkingSMS()

# Client — factory agnostic
class NotificationService:
    def __init__(self, factory: NotificationFactory):
        self._email = factory.email()
        self._sms   = factory.sms()

    def notify(self, user, message: str):
        self._email.send(user.email, message)
        self._sms.send(user.phone, message)

# Switch region by swapping factory
india_svc  = NotificationService(IndiaFactory())
africa_svc = NotificationService(AfricaFactory())
```

---

### 2.5 Real Project Answer

**"Explain Abstract Factory with a real example"**

> "In Niroskos, which is a multi-tenant safari booking platform, different subsidiaries operate in different regions — India and Africa. Each region needs Email + SMS + Push notifications, but the providers differ: India uses Postmark + Twilio, Africa uses Mailgun + Africa's Talking.
>
> I used Abstract Factory where `IndiaNotificationFactory` creates the complete India-compatible suite and `AfricaNotificationFactory` creates the Africa-compatible suite. The `BookingNotificationService` takes a factory via constructor injection and doesn't know which region it's serving. When a booking is confirmed, it calls `email.send()`, `sms.send()` — the right provider executes automatically.
>
> The key benefit was compatibility guarantee — I could never accidentally mix India's SMS provider with Africa's email provider, because both come from the same factory."

---

### 2.6 Follow-up Q&A

**Q: "Factory vs Abstract Factory — when to choose which?"**
> "Choose Factory when you need one type of object with variants — `create('card')` returns a payment processor. Choose Abstract Factory when you need multiple related objects that must work together — `IndiaFactory` gives you email + SMS + push that are all India-compliant. If you find yourself calling multiple factories together and worrying about compatibility — that's Abstract Factory territory."

**Q: "How do you add a new region in Abstract Factory?"**
> "Create a new Concrete Factory class — `EuropeNotificationFactory` implementing `NotificationFactory`. Create its product classes — `SendgridEmail`, `VonageSMS`. Register it. Zero modification to existing factories or the client `NotificationService`. Open/Closed Principle maintained."

**Q: "Abstract Factory vs Builder?"**
> "Abstract Factory creates a family of DIFFERENT product types — email, SMS, push. Builder creates ONE complex product step by step — BookingDraft with package, date, guests, pricing, pickup. Abstract Factory is about compatibility across types; Builder is about constructing a single complex object."

---

## Comparison: Factory vs Abstract Factory vs Builder

| | Factory | Abstract Factory | Builder |
|---|---------|-----------------|---------|
| **Creates** | 1 object type, multiple variants | Family of related objects | 1 complex object |
| **How** | `factory.create('type')` | `factory.email()`, `factory.sms()` | `builder.set_x().set_y().build()` |
| **Guarantees** | Correct variant | Product compatibility | Complete construction |
| **Add new** | New class + register | New factory + product classes | New builder subclass |
| **Real example** | `PaymentProcessorFactory` | `IndiaNotificationFactory` | `EwayBillBuilder` |

---

*Last Updated: April 2026 | SDE-2 Interview Prep*
