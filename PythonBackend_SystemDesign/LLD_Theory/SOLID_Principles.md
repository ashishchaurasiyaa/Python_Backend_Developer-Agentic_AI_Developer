# SOLID Principles — Interview Preparation
> **Target Role:** SDE-2 Python Backend | **Company:** Interview Kickstart
> **Real Examples From:** Niroskos Safaris, Youngman ERP, Youngman Django Backend

---

## What is SOLID?

SOLID ek mnemonic hai — 5 design principles jo maintainable, scalable aur flexible code likhne mein help karte hain.

```
S → Single Responsibility Principle  (SRP)
O → Open / Closed Principle          (OCP)
L → Liskov Substitution Principle    (LSP)
I → Interface Segregation Principle  (ISP)
D → Dependency Inversion Principle   (DIP)
```

**Kyun zaroori hai?**
```
❌ SOLID ke bina:
   - Ek change → 10 jagah bugs
   - Test likhna mushkil
   - Naya developer samajh nahi paata
   - Feature add karne mein purana kaam toot jaata

✅ SOLID ke saath:
   - Ek class, ek kaam — change controlled
   - Easy to test, easy to extend
   - Naye payment method? Sirf ek class add karo
   - Production mein Rs 100 Crore+ safely process hota hai
```

---

## Table of Contents
1. [S — Single Responsibility Principle](#1-s--single-responsibility-principle)
2. [O — Open / Closed Principle](#2-o--open--closed-principle)
3. [L — Liskov Substitution Principle](#3-l--liskov-substitution-principle)
4. [I — Interface Segregation Principle](#4-i--interface-segregation-principle)
5. [D — Dependency Inversion Principle](#5-d--dependency-inversion-principle)
6. [All 5 Together — Real System Design](#6-all-5-together--real-system-design)
7. [Interview Questions & Answers](#7-interview-questions--answers)

---

## 1. S — Single Responsibility Principle

### Definition
> **"A class should have only one reason to change."**
> Ek class ka sirf ek kaam hona chahiye.

### Simple Analogy
```
Chef → Sirf khana banata hai
Waiter → Sirf serve karta hai
Cashier → Sirf payment leta hai

Agar Chef hi sab kuch kare → overwhelmed, errors, management nightmare
```

---

### ❌ BAD — SRP Violation

```python
# Yeh class bahut zyada kaam karti hai — WRONG
class Invoice:
    def __init__(self, customer, items):
        self.customer = customer
        self.items    = items

    # Kaam 1: Business logic
    def calculate_total(self):
        return sum(item.price * item.qty for item in self.items)

    def apply_gst(self, total):
        return total * 1.18

    # Kaam 2: Database
    def save_to_database(self):
        db.execute("INSERT INTO invoices ...")

    def fetch_from_database(self, invoice_id):
        return db.execute("SELECT * FROM invoices WHERE id = ?", invoice_id)

    # Kaam 3: Notification
    def send_email_to_customer(self):
        smtp.send(self.customer.email, "Your invoice is ready")

    # Kaam 4: PDF generation
    def generate_pdf(self):
        pdf = WeasyPrint()
        pdf.render(self.get_html_template())
        return pdf

    # Kaam 5: SAP sync
    def push_to_sap(self):
        sap_api.post('/invoices', self.to_sap_format())

# Problem:
# - Email logic change → Invoice class change
# - PDF library change → Invoice class change
# - Database change → Invoice class change
# Ek class mein 5 reasons to change = SRP violation
```

---

### ✅ GOOD — SRP Applied

```python
# Youngman Django Backend ka actual pattern

# ─── Class 1: Sirf business logic ───
class Invoice:
    def __init__(self, customer, items):
        self.customer = customer
        self.items    = items
        self.status   = 'PENDING'

    def calculate_total(self) -> float:
        return sum(item.price * item.qty for item in self.items)

    def apply_gst(self) -> float:
        return self.calculate_total() * 1.18

    def mark_paid(self):
        self.status = 'PAID'


# ─── Class 2: Sirf database operations ───
class InvoiceRepository:
    def save(self, invoice: Invoice) -> int:
        return db.execute(
            "INSERT INTO invoices (customer_id, total, status) VALUES (?, ?, ?)",
            invoice.customer.id, invoice.calculate_total(), invoice.status
        )

    def find_by_id(self, invoice_id: int) -> Invoice:
        row = db.execute("SELECT * FROM invoices WHERE id = ?", invoice_id)
        return self._map_to_invoice(row)

    def find_overdue(self) -> list:
        return db.execute("SELECT * FROM invoices WHERE status = 'OVERDUE'")


# ─── Class 3: Sirf notifications ───
class InvoiceNotificationService:
    def send_invoice_email(self, invoice: Invoice):
        subject = f"Invoice #{invoice.id} - Rs {invoice.calculate_total()}"
        body    = self._render_template(invoice)
        smtp.send(invoice.customer.email, subject, body)

    def send_overdue_reminder(self, invoice: Invoice):
        sms.send(invoice.customer.phone, f"Payment overdue: Rs {invoice.calculate_total()}")


# ─── Class 4: Sirf PDF ───
class InvoicePDFGenerator:
    def generate(self, invoice: Invoice) -> bytes:
        html = self._render_html_template(invoice)
        return WeasyPrint().write_pdf(html)

    def upload_to_s3(self, pdf: bytes, invoice_id: int) -> str:
        key = f"invoices/{invoice_id}.pdf"
        s3.put_object(Bucket='youngman-docs', Key=key, Body=pdf)
        return s3.generate_presigned_url(key)


# ─── Class 5: Sirf SAP sync ───
class SAPInvoiceSyncer:
    def push(self, invoice: Invoice) -> bool:
        payload = self._to_sap_format(invoice)
        response = sap_api.post('/invoices', payload)
        return response.status_code == 201
```

### Real Project Example — Niroskos PaymentService
```python
# apps/payments/services/payment_service.py
# Har service ka ek kaam:

class PaymentService:      # Sirf payment initiate/complete karo
    pass

class AllocationService:   # Sirf payment ko order items mein allocate karo
    pass

class OrderService:        # Sirf order totals aur status manage karo
    pass

class RefundService:       # Sirf refund process karo
    pass

# Agar Payment logic change ho → sirf PaymentService change
# Agar Allocation change ho → sirf AllocationService change
# Dono independent hain — SRP ✅
```

### SRP Violation Signs
```
🚨 Class mein "And" aa raha hai naam mein:
   "InvoiceGeneratorAndEmailSender" → BAD

🚨 1 class mein 500+ lines:
   Too many responsibilities

🚨 Ek change se unrelated tests fail:
   Email test fail hua toh Invoice calculation change kiya kya?

🚨 Class har jagah import hoti hai:
   Sab depend karte hain → tightly coupled
```

---

## 2. O — Open / Closed Principle

### Definition
> **"Software should be open for extension, but closed for modification."**
> Naya feature add karna ho → purana code mat chhedo, extend karo.

### Simple Analogy
```
USB port — Open for extension (nayi device lagao)
           Closed for modification (port ka design nahi badla)

Tum nayi pen drive lagaate ho → computer ka motherboard nahi badlata
```

---

### ❌ BAD — OCP Violation

```python
# Har naye payment method pe if-elif badha rahe ho — WRONG
class PaymentProcessor:
    def process(self, payment_type: str, amount: float):
        if payment_type == 'card':
            print(f"Processing card payment: {amount}")
            # Stripe API call...

        elif payment_type == 'paypal':
            print(f"Processing PayPal: {amount}")
            # PayPal API call...

        elif payment_type == 'crypto':
            print(f"Processing crypto: {amount}")
            # Web3 API call...

        elif payment_type == 'mpesa':            # Naya method aaya
            print(f"Processing M-Pesa: {amount}")  # Purana code modify kiya ❌

        # Problem: Har naye method pe yeh class modify karni padti hai
        # Test bhi dobara karo — purana code break ho sakta hai
```

---

### ✅ GOOD — OCP Applied

```python
# Niroskos ka actual Payment design
from abc import ABC, abstractmethod

# ─── Abstract Base — closed for modification ───
class PaymentMethod(ABC):
    @abstractmethod
    def initiate(self, amount: float, currency: str) -> dict:
        pass

    @abstractmethod
    def verify(self, provider_event_id: str) -> bool:
        pass

    @abstractmethod
    def refund(self, transaction_id: str, amount: float) -> dict:
        pass


# ─── Concrete implementations — open for extension ───
class CardPayment(PaymentMethod):
    """Stripe/Razorpay"""
    def initiate(self, amount, currency):
        return {"method": "card", "client_secret": "pi_secret_xyz"}

    def verify(self, provider_event_id):
        # Stripe webhook verify
        return True

    def refund(self, transaction_id, amount):
        # Stripe refund API
        return {"refund_id": "re_xyz", "status": "succeeded"}


class CryptoPayment(PaymentMethod):
    """Ethereum / USDT — Niroskos Web3"""
    def initiate(self, amount, currency):
        return {
            "method":          "crypto",
            "deposit_address": "0x742d35Cc...",
            "network":         "ERC20",
            "expires_in":      3600
        }

    def verify(self, provider_event_id):
        # Blockchain scan task check
        return True

    def refund(self, transaction_id, amount):
        # Manual approval required for crypto
        return {"status": "pending_approval"}


class MPesaPayment(PaymentMethod):
    """Africa market — M-Pesa mobile money"""
    def initiate(self, amount, currency):
        return {"method": "mpesa", "checkout_request_id": "ws_CO_123"}

    def verify(self, provider_event_id):
        return True

    def refund(self, transaction_id, amount):
        return {"status": "reversal_initiated"}


# ─── Processor — modification ke liye CLOSED ───
class PaymentService:
    def process(self, method: PaymentMethod, amount: float, currency: str):
        # Yeh kabhi nahi badlega — chahe 100 payment methods aayein
        result = method.initiate(amount, currency)
        self._log_transaction(result)
        return result

    def _log_transaction(self, result):
        print(f"Transaction logged: {result}")


# ─── Naya payment method? Sirf naya class likho ───
class BankTransferPayment(PaymentMethod):   # Purana kuch nahi badla ✅
    def initiate(self, amount, currency):
        return {"method": "bank_transfer", "account": "HDFC-123456"}

    def verify(self, provider_event_id):
        return True

    def refund(self, transaction_id, amount):
        return {"status": "manual_bank_transfer"}

# PaymentService modify nahi kiya → OCP ✅
service = PaymentService()
service.process(CardPayment(),        50000, 'INR')
service.process(CryptoPayment(),      50000, 'USD')
service.process(MPesaPayment(),       50000, 'KES')
service.process(BankTransferPayment(), 50000, 'INR')  # Naya — zero change
```

### Real Project — Youngman Laravel Discount Strategy
```python
# Existing code jo tumhara hai — Open_Closed_Principle.py
from abc import ABC, abstractmethod

class DiscountStrategy(ABC):
    @abstractmethod
    def calculate(self, price: float) -> float:
        pass

class PercentageDiscount(DiscountStrategy):
    def __init__(self, rate: float):
        self.rate = rate

    def calculate(self, price):
        return price * (1 - self.rate)   # 20% off

class FixedDiscount(DiscountStrategy):
    def __init__(self, amount: float):
        self.amount = amount

    def calculate(self, price):
        return price - self.amount       # Rs 500 off

# Naya type? Sirf class add karo
class SeasonalDiscount(DiscountStrategy):  # PriceCalculator nahi badla ✅
    def __init__(self, rate: float, valid_months: list):
        self.rate   = rate
        self.valid_months = valid_months

    def calculate(self, price):
        from datetime import datetime
        if datetime.now().month in self.valid_months:
            return price * (1 - self.rate)
        return price  # Off-season mein discount nahi

class PriceCalculator:
    def calculate(self, item, discount: DiscountStrategy) -> float:
        return discount.calculate(item.price)
```

---

## 3. L — Liskov Substitution Principle

### Definition
> **"Objects of a subclass should be replaceable with objects of the parent class without breaking the program."**
> Child class, parent ki jagah use ho sake — behavior same rahe.

### Simple Analogy
```
Agar recipe mein "Bird" use karo:
✅ Parrot (Bird) → works fine
✅ Eagle (Bird)  → works fine
❌ Penguin (Bird) → fly() call kiya → crash!

Penguin Bird hai but fly nahi kar sakta
→ LSP violation
```

---

### ❌ BAD — LSP Violation

```python
class Payment:
    def process(self, amount: float) -> dict:
        return {"status": "processed", "amount": amount}

    def refund(self, transaction_id: str) -> dict:
        return {"status": "refunded", "transaction_id": transaction_id}


class CryptoPayment(Payment):
    def process(self, amount):
        return {"status": "pending_blockchain", "amount": amount}

    def refund(self, transaction_id):
        # ❌ Crypto refund manual hai — exception throw kiya
        raise NotImplementedError("Crypto refunds require manual approval")
        # Ab jahan bhi Payment use ho, CryptoPayment tod dega!


# PROBLEM:
def handle_refund(payment: Payment, txn_id: str):
    return payment.refund(txn_id)   # CryptoPayment doge → crash!

card   = CreditCardPayment()
crypto = CryptoPayment()

handle_refund(card, "txn_001")    # ✅ Works
handle_refund(crypto, "txn_002")  # ❌ NotImplementedError → LSP violation
```

---

### ✅ GOOD — LSP Applied

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

@dataclass
class PaymentResult:
    success:        bool
    status:         str
    transaction_id: Optional[str] = None
    message:        Optional[str] = None

@dataclass
class RefundResult:
    initiated:    bool
    refund_type:  str          # 'automatic' | 'manual_approval'
    status:       str
    message:      Optional[str] = None


class PaymentMethod(ABC):
    @abstractmethod
    def process(self, amount: float, currency: str) -> PaymentResult:
        pass

    @abstractmethod
    def refund(self, transaction_id: str, amount: float) -> RefundResult:
        """
        Sabhi subclasses mein kaam karta hai.
        Crypto mein 'manual_approval' return karega — exception nahi.
        """
        pass


class CardPayment(PaymentMethod):
    def process(self, amount, currency):
        return PaymentResult(
            success=True,
            status='completed',
            transaction_id='txn_card_001'
        )

    def refund(self, transaction_id, amount):
        return RefundResult(
            initiated=True,
            refund_type='automatic',   # Turant ho jaata hai
            status='refunded',
            message=f"Refunded {amount} to original card"
        )


class CryptoPayment(PaymentMethod):
    def process(self, amount, currency):
        return PaymentResult(
            success=True,
            status='pending_blockchain_confirmation',
            transaction_id='txn_crypto_001'
        )

    def refund(self, transaction_id, amount):
        # ✅ Exception nahi — same return type, alag behavior
        return RefundResult(
            initiated=True,
            refund_type='manual_approval',   # Manual hai — clearly bata diya
            status='pending_approval',
            message="Crypto refund submitted for manual review"
        )


class MPesaPayment(PaymentMethod):
    def process(self, amount, currency):
        return PaymentResult(
            success=True,
            status='stk_push_sent',
            transaction_id='txn_mpesa_001'
        )

    def refund(self, transaction_id, amount):
        return RefundResult(
            initiated=True,
            refund_type='automatic',
            status='reversal_initiated',
            message="M-Pesa reversal initiated"
        )


# ✅ Koi bhi PaymentMethod dalo — code nahi todega
def process_refund(payment: PaymentMethod, txn_id: str, amount: float):
    result = payment.refund(txn_id, amount)   # Sabhi ke liye kaam karega

    if result.refund_type == 'automatic':
        print(f"Auto refund done: {result.status}")
    else:
        print(f"Manual approval needed: {result.message}")

    return result


# Substitution works perfectly — LSP ✅
process_refund(CardPayment(),   "txn_001", 10000)
process_refund(CryptoPayment(), "txn_002", 25000)  # No crash!
process_refund(MPesaPayment(),  "txn_003", 5000)
```

### LSP Checklist
```
✅ Child class parent ki jagah safely kaam kare
✅ Parent ka method override karo — same return type
✅ Child mein zyada strict exceptions mat daalo
✅ Preconditions strong mat karo (parent se zyada validation)
✅ Postconditions weak mat karo (parent se kam guarantee)
```

---

## 4. I — Interface Segregation Principle

### Definition
> **"Clients should not be forced to depend on methods they don't use."**
> Ek badi interface mat banao — chhoti chhoti specific interfaces banao.

### Simple Analogy
```
❌ BAD: Ek hi "All-in-one" remote — TV, AC, Fan, Microwave sab buttons ek pe
         Simple TV use karna hai → Microwave button bhi dekh raha ho — confusing

✅ GOOD: Alag alag remote — TV remote, AC remote, Fan remote
         Simple TV → sirf TV remote do
```

---

### ❌ BAD — ISP Violation

```python
# Ek badi interface — sab forced hain sab implement karne ko
from abc import ABC, abstractmethod

class AllInOneWorker(ABC):
    @abstractmethod
    def generate_invoice(self): pass

    @abstractmethod
    def send_email(self): pass

    @abstractmethod
    def generate_pdf(self): pass

    @abstractmethod
    def push_to_sap(self): pass

    @abstractmethod
    def send_sms(self): pass

    @abstractmethod
    def export_to_excel(self): pass


class SimpleInvoiceGenerator(AllInOneWorker):
    def generate_invoice(self):
        print("Invoice generated")

    def send_email(self):
        pass  # ❌ Forced — yeh karna nahi tha

    def generate_pdf(self):
        pass  # ❌ Forced — yeh bhi nahi karna tha

    def push_to_sap(self):
        pass  # ❌ Forced — SAP se koi matlab nahi

    def send_sms(self):
        pass  # ❌ Forced

    def export_to_excel(self):
        pass  # ❌ Forced

# SimpleInvoiceGenerator ko sirf invoice generate karna tha
# But 5 useless methods implement karni padi — ISP violation
```

---

### ✅ GOOD — ISP Applied

```python
# Chhoti chhoti focused interfaces — Youngman Django ka actual mixin pattern

from abc import ABC, abstractmethod


# ─── Interface 1: Invoice generation ───
class InvoiceGeneratable(ABC):
    @abstractmethod
    def generate_invoice(self, order) -> dict:
        pass


# ─── Interface 2: Email notification ───
class EmailNotifiable(ABC):
    @abstractmethod
    def send_invoice_email(self, invoice, recipient: str) -> bool:
        pass


# ─── Interface 3: PDF export ───
class PDFExportable(ABC):
    @abstractmethod
    def export_pdf(self, invoice) -> bytes:
        pass


# ─── Interface 4: SAP sync ───
class SAPSyncable(ABC):
    @abstractmethod
    def push_to_sap(self, invoice) -> bool:
        pass


# ─── Interface 5: SMS notification ───
class SMSNotifiable(ABC):
    @abstractmethod
    def send_sms(self, phone: str, message: str) -> bool:
        pass


# ─── Only what's needed ───

class BasicInvoiceService(InvoiceGeneratable):
    """Sirf invoice generate karo — kuch aur nahi chahiye"""
    def generate_invoice(self, order):
        return {"invoice_no": "INV-001", "amount": order.total}


class FullInvoiceService(
    InvoiceGeneratable,
    EmailNotifiable,
    PDFExportable,
    SAPSyncable
):
    """Full enterprise invoice service"""
    def generate_invoice(self, order):
        return {"invoice_no": "INV-001", "amount": order.total}

    def send_invoice_email(self, invoice, recipient):
        # Postmark email
        return True

    def export_pdf(self, invoice):
        # WeasyPrint — tumne use kiya YES platform mein
        return b"pdf_bytes"

    def push_to_sap(self, invoice):
        # SAP HANA connector — tumhara 4858 lines wala
        return True


class SMSOnlyService(SMSNotifiable):
    """Sirf SMS — Exotel ya Twilio"""
    def send_sms(self, phone, message):
        # Twilio API call
        return True
```

### Real Project — Niroskos ViewSet Mixins (ISP Perfect Example)
```python
# apps/core/mixins/views.py — ACTUAL CODE

# Har mixin ek kaam karta hai — ISP ✅
class AuditMixin:
    """Sirf created_by/updated_by set karo"""
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


class SoftDeleteMixin:
    """Sirf soft delete handle karo"""
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.soft_delete(user=request.user)
        return Response(status=204)


class BulkCreateMixin:
    """Sirf bulk create endpoint do"""
    @action(detail=False, methods=['POST'])
    def bulk_create(self, request):
        serializer = self.get_serializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=201)


class ExportMixin:
    """Sirf CSV export do"""
    @action(detail=False, methods=['GET'])
    def export(self, request):
        queryset = self.get_queryset()
        return self._generate_csv_response(queryset)


class OdooWebhookMixin:
    """Sirf Odoo webhook handle karo"""
    @action(detail=False, methods=['POST'])
    def odoo_sync(self, request):
        self.handle_odoo_payload(request.data)
        return Response({"status": "synced"})


# Usage — sirf zaroori mixins lo, baaki mat lo

class CustomerViewSet(AuditMixin, SoftDeleteMixin, ExportMixin, ModelViewSet):
    pass   # Audit + SoftDelete + Export — sirf yahi chahiye

class InvoiceViewSet(AuditMixin, ExportMixin, ModelViewSet):
    pass   # Invoice ko Odoo sync chahiye hi nahi

class ChallanViewSet(AuditMixin, OdooWebhookMixin, ModelViewSet):
    pass   # Challan ko Odoo sync chahiye — export nahi
```

---

## 5. D — Dependency Inversion Principle

### Definition
> **"High-level modules should not depend on low-level modules. Both should depend on abstractions."**
> Concrete classes pe direct depend mat karo — interface pe depend karo.

### Simple Analogy
```
❌ BAD: Laptop directly Seagate HDD se connected hai
         Seagate band ho gayi → Laptop badlo

✅ GOOD: Laptop → USB Interface → (Seagate HDD / WD HDD / Samsung SSD)
         Koi bhi storage lagao — laptop same rahe
         Interface pe depend karo, implementation pe nahi
```

---

### ❌ BAD — DIP Violation

```python
# High-level module directly low-level pe depend karta hai
class PostmarkEmailService:
    def send(self, to: str, subject: str, body: str):
        import requests
        requests.post("https://api.postmarkapp.com/email", json={
            "From":    "noreply@niroskos.com",
            "To":      to,
            "Subject": subject,
            "HtmlBody": body
        })


class BookingConfirmationService:
    def __init__(self):
        # ❌ DIRECT dependency on concrete class
        self.email_service = PostmarkEmailService()

    def confirm_booking(self, booking):
        booking.status = 'CONFIRMED'

        # ❌ Postmark hardcoded — kal Mailgun use karna ho?
        self.email_service.send(
            to      = booking.user.email,
            subject = "Booking Confirmed!",
            body    = f"Your safari is confirmed: {booking.ref_code}"
        )

# Problem:
# - Postmark → Mailgun switch karna ho → BookingConfirmationService badlo
# - Test likhna mushkil — real email jaayegi test mein
# - Tightly coupled — DIP violation
```

---

### ✅ GOOD — DIP Applied

```python
# Niroskos Communications ka actual pattern
from abc import ABC, abstractmethod


# ─── Abstraction (Interface) ───
class EmailProvider(ABC):
    @abstractmethod
    def send(self, to: str, subject: str, body: str) -> bool:
        pass


# ─── Low-level modules — concrete implementations ───
class PostmarkEmailProvider(EmailProvider):
    def send(self, to, subject, body):
        import requests
        response = requests.post(
            "https://api.postmarkapp.com/email",
            headers={"X-Postmark-Server-Token": "TOKEN"},
            json={"From": "noreply@niroskos.com", "To": to,
                  "Subject": subject, "HtmlBody": body}
        )
        return response.status_code == 200


class MailgunEmailProvider(EmailProvider):
    def send(self, to, subject, body):
        import requests
        response = requests.post(
            "https://api.mailgun.net/v3/niroskos.com/messages",
            auth=("api", "MAILGUN_KEY"),
            data={"from": "noreply@niroskos.com", "to": to,
                  "subject": subject, "html": body}
        )
        return response.status_code == 200


class MockEmailProvider(EmailProvider):
    """Testing ke liye — real email nahi jaayegi"""
    def __init__(self):
        self.sent_emails = []

    def send(self, to, subject, body):
        self.sent_emails.append({"to": to, "subject": subject})
        print(f"[MOCK] Email to {to}: {subject}")
        return True


# ─── High-level module — abstraction pe depend karta hai ───
class BookingConfirmationService:
    def __init__(self, email_provider: EmailProvider):
        # ✅ Interface pe depend karo — concrete nahi
        self.email_provider = email_provider

    def confirm_booking(self, booking) -> bool:
        booking.status = 'CONFIRMED'

        success = self.email_provider.send(   # Polymorphic call
            to      = booking.user.email,
            subject = f"Booking Confirmed — {booking.package.name}",
            body    = self._render_confirmation_email(booking)
        )
        return success

    def _render_confirmation_email(self, booking) -> str:
        return f"""
        <h1>Safari Confirmed!</h1>
        <p>Ref: {booking.ref_code}</p>
        <p>Package: {booking.package.name}</p>
        <p>Date: {booking.travel_date}</p>
        """


# ─── Dependency Injection — bahar se inject karo ───

# Production
service = BookingConfirmationService(
    email_provider=PostmarkEmailProvider()    # Real email
)

# Kal Mailgun pe switch karna ho — sirf yeh line badlo
service = BookingConfirmationService(
    email_provider=MailgunEmailProvider()    # Zero code change in service
)

# Testing — mock inject karo
mock_email = MockEmailProvider()
service    = BookingConfirmationService(email_provider=mock_email)
service.confirm_booking(test_booking)
assert len(mock_email.sent_emails) == 1   # Real email nahi gayi
```

### Real Project — Youngman Django ka actual DIP
```python
# apps/integrations/services/eway_bill.py
# Tumhara actual pattern — EwayBillService

class EwayBillAPIClient(ABC):
    @abstractmethod
    def generate_token(self) -> str: pass

    @abstractmethod
    def generate_bill(self, payload: dict) -> dict: pass

    @abstractmethod
    def cancel_bill(self, bill_no: str) -> bool: pass


class MasterIndiaAPIClient(EwayBillAPIClient):
    """MasterIndia ka actual client"""
    BASE_URL = "https://api.mastersindia.co"

    def generate_token(self):
        response = requests.post(f"{self.BASE_URL}/auth/token", json={...})
        return response.json()['access_token']

    def generate_bill(self, payload):
        response = requests.post(f"{self.BASE_URL}/ewb/generate", json=payload)
        return response.json()

    def cancel_bill(self, bill_no):
        response = requests.post(f"{self.BASE_URL}/ewb/cancel", json={"ewbNo": bill_no})
        return response.status_code == 200


class EwayBillService:
    def __init__(self, api_client: EwayBillAPIClient):
        self.client = api_client   # DIP — interface pe depend

    def create_eway_bill(self, challan) -> dict:
        token   = self.client.generate_token()
        payload = EwayBillPayloadBuilder(challan).build()
        return  self.client.generate_bill(payload)


# Django settings se inject karo
eway_service = EwayBillService(
    api_client=MasterIndiaAPIClient()
)
```

### 3 Ways to Inject Dependency
```python
# Method 1: Constructor Injection (Recommended)
class BookingService:
    def __init__(self, email: EmailProvider, sms: SMSProvider):
        self.email = email
        self.sms   = sms

# Method 2: Method Injection
class BookingService:
    def confirm(self, booking, notifier: EmailProvider):
        notifier.send(booking.user.email, "Confirmed!")

# Method 3: Property Injection (Less common)
class BookingService:
    email_provider: EmailProvider = None  # Set before use
```

---

## 6. All 5 Together — Real System Design

### Complete Notification System (Niroskos)

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List


# ─── ISP — Chhoti interfaces ───
class Sendable(ABC):
    @abstractmethod
    def send(self, recipient: str, message: str) -> bool:
        pass

class Loggable(ABC):
    @abstractmethod
    def log(self, event: str, metadata: dict) -> None:
        pass


# ─── SRP — Har class ka ek kaam ───
class PostmarkChannel(Sendable):
    """SRP: Sirf email send karo"""
    def send(self, recipient, message):
        print(f"[POSTMARK] → {recipient}: {message}")
        return True

class TwilioChannel(Sendable):
    """SRP: Sirf SMS send karo"""
    def send(self, recipient, message):
        print(f"[TWILIO] → {recipient}: {message}")
        return True

class DatabaseLogger(Loggable):
    """SRP: Sirf log karo"""
    def log(self, event, metadata):
        print(f"[DB LOG] {event}: {metadata}")


# ─── OCP — Extension ke liye open ───
class SlackChannel(Sendable):
    """Naya channel — kuch nahi badla"""
    def send(self, recipient, message):
        print(f"[SLACK] #{recipient}: {message}")
        return True


# ─── LSP — Substitutable ───
# PostmarkChannel, TwilioChannel, SlackChannel —
# teeno Sendable ki jagah safely use ho sakte hain


# ─── DIP — Abstraction pe depend ───
class NotificationService:
    """
    SRP: Sirf notifications route karo
    DIP: Sendable interface pe depend karo — concrete nahi
    """
    def __init__(self, channels: List[Sendable], logger: Loggable):
        self.channels = channels   # DIP: inject karo
        self.logger   = logger

    def notify(self, event_type: str, recipient: str, message: str):
        for channel in self.channels:
            # OCP: Naya channel aaye → channels list mein add karo — service mat badlo
            success = channel.send(recipient, message)
            self.logger.log(event_type, {
                "recipient": recipient,
                "channel":   channel.__class__.__name__,
                "success":   success
            })


# ─── Wiring — bahar se compose karo ───
notification_service = NotificationService(
    channels=[
        PostmarkChannel(),
        TwilioChannel(),
        SlackChannel()     # Naya channel add — NotificationService nahi badli
    ],
    logger=DatabaseLogger()
)

notification_service.notify(
    event_type="BOOKING_CONFIRMED",
    recipient ="rahul@gmail.com",
    message   ="Your Masai Mara safari is confirmed!"
)
```

---

## 7. Interview Questions & Answers

---

### Q1: "SOLID explain karo ek real project se"

**Answer (use this exact flow):**
> "Niroskos safari platform mein payment system design karte waqt maine SOLID apply kiya:
>
> **S** — `PaymentService`, `AllocationService`, `OrderService` — teen alag classes. Ek change isolated rehta hai.
>
> **O** — `PaymentMethod` abstract class banayi. Naya payment type aaya — `BankTransferPayment` class likhi, `PaymentService` touch nahi kiya.
>
> **L** — `CardPayment`, `CryptoPayment`, `MPesaPayment` — teeno `PaymentMethod` ki jagah safely use hote hain. Crypto refund mein `NotImplementedError` nahi — `RefundResult(type='manual_approval')` return kiya.
>
> **I** — Django ViewSet mixins — `AuditMixin`, `SoftDeleteMixin`, `ExportMixin` alag alag. ChallanViewSet ko Export nahi chahiye tha — woh mixin liya hi nahi.
>
> **D** — `BookingConfirmationService(email_provider: EmailProvider)` — Postmark inject kiya production mein, MockProvider test mein. Service ko pata hi nahi provider kaun hai."

---

### Q2: "SRP aur ISP mein kya difference hai?"

| | SRP | ISP |
|---|---|---|
| **Focus** | Class ka responsibility | Interface ka size |
| **Question** | "Yeh class kitne kaam karti hai?" | "Yeh interface kitne methods expose karta hai?" |
| **Fix** | Class tod do | Interface tod do |
| **Example** | Invoice class se email hataao | AllInOneWorker ko Printable, Scannable mein tod do |

---

### Q3: "LSP violation kaise detect karein?"

```
🚨 Signs of LSP violation:
1. Child class mein NotImplementedError throw kar rahe ho
2. Parent ka method override mein behaviour completely change ho gaya
3. instanceof check karna pad raha hai:
   if isinstance(payment, CryptoPayment):
       # special handling
   # yeh LSP violation ka symptom hai

✅ Fix:
   Better return types use karo
   Hierarchy redesign karo
   Interface segregate karo
```

---

### Q4: "Dependency Injection aur Dependency Inversion same hai?"

```
DIP  (Principle) → "Abstraction pe depend karo" — WHAT to do
DI   (Technique) → "Dependency bahar se inject karo" — HOW to do it

DIP achieve karne ka ek tarika DI hai.

Framework: Django uses DI via settings
   EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
   # Test mein:
   EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
   # Service code nahi badli — DIP ✅
```

---

### Q5: "SOLID violate karne ke real consequences kya hote hain?"

**Answer (from your experience):**
> "Youngman Laravel ERP mein pehle SRP follow nahi kiya tha — ek Controller mein invoice generate, SAP push, email send — sab kuch tha. Jab SAP API change hua, Controller test karna pada. Jab email provider change kiya, SAP logic dobara test karna pada. Tightly coupled code tha.
>
> Jab Django mein migrate kiya, SRP aur DIP properly follow kiya — `EwayBillService`, `InvoiceRepository`, `NotificationService` alag alag. Ab SAP change hone pe sirf `SAPHANAConnector` test karo — baaki kuch nahi."

---

### Quick Revision — 30 Second Summary

```
S → Ek class, ek kaam
    "InvoiceService sirf invoice banata hai, email nahi bhejta"

O → Purana code mat chedo, extend karo
    "Naya PaymentMethod? Sirf nayi class — service untouched"

L → Child parent ki jagah kaam kare
    "CryptoPayment bhi Payment hai — refund crash nahi karta"

I → Chhoti interfaces — sirf zaroori methods
    "ChallanViewSet ko ExportMixin ki zaroorat nahi thi — liya nahi"

D → Abstraction pe depend karo, concrete pe nahi
    "BookingService(email: EmailProvider) — Postmark ya Mailgun, same code"
```

---

*Last Updated: April 2026 | Prepared for SDE-2 Interview at Interview Kickstart*
