# Adapter Pattern
> **Category:** Structural | **Difficulty:** Easy-Medium | **Interview Frequency:** ★★★★☆

---

## Quick Reference Card
```
Kya karta hai : Incompatible interface ko compatible banata hai — bina original class badhe
Kab use karo  : Third-party API integration, legacy system connect, different interfaces bridge
Key mechanism : Adapter class dono interfaces implement kare — translate kare
Real project  : Niroskos → SAP HANA Adapter | Youngman → MasterIndia GST API Adapter
Pattern type  : Structural
```

---

## PART 1: HINGLISH — Samjhne ke liye

### 1.1 Kya hai?

Adapter pattern ek **translator ki tarah kaam karta hai** — do incompatible interfaces ke beech.

**Simple analogy:**
```
India mein 3-pin plug, Europe mein 2-pin socket.
Travel adapter lagate ho → same device, alag socket mein kaam karta hai.

Tumhara device nahi badla (SAP API)
Socket nahi badla (Tumhari app ka interface)
Adapter ne beech mein translate kiya
```

---

### 1.2 Kab use karo?

```
✅ Third-party API integrate karna hai jiska interface alag hai
✅ Legacy system (purana code) naye system ke saath kaam kare
✅ Multiple providers ka same interface banana (Stripe, Razorpay — same method names)
✅ External library ka interface tumhare application ke saath match nahi karta
✅ Testing mein real API ki jagah mock adapter use karna ho
```

---

### 1.3 Kab mat use karo?

```
❌ Interface already compatible hai — unnecessary layer
❌ Original class modify kar sakte ho — directly fix karo
❌ Zyada translation layers → performance hit aur debugging mushkil
```

---

### 1.4 Code — Hinglish Comments ke saath

```python
from abc import ABC, abstractmethod


# ─── Tumhara Internal Interface — app kya expect karti hai ───
class PaymentGateway(ABC):
    """
    Tumhari app yeh interface expect karti hai.
    Saare payment gateways yeh implement karenge.
    """
    @abstractmethod
    def charge(self, amount: float, currency: str, customer_id: str) -> dict:
        pass

    @abstractmethod
    def refund(self, charge_id: str, amount: float) -> dict:
        pass

    @abstractmethod
    def get_status(self, charge_id: str) -> str:
        pass


# ─── External API 1: Stripe (alag method names hain) ───
class StripeAPI:
    """
    Yeh Stripe ka actual SDK hai — tumne nahi banaya.
    Stripe ke apne method names hain — tumhare se alag.
    """
    def create_payment_intent(self, amount_in_paise: int, currency: str, customer: str):
        # Stripe mein amount paise mein hota hai (100 = Re 1)
        print(f"[STRIPE] PaymentIntent: {amount_in_paise} paise for {customer}")
        return {"id": "pi_stripe_001", "status": "requires_confirmation"}

    def create_refund(self, payment_intent_id: str, amount_in_paise: int):
        print(f"[STRIPE] Refund: {amount_in_paise} paise for {payment_intent_id}")
        return {"id": "re_stripe_001", "status": "succeeded"}

    def retrieve_payment_intent(self, payment_intent_id: str):
        return {"id": payment_intent_id, "status": "succeeded"}


# ─── External API 2: Razorpay (aur alag method names) ───
class RazorpayAPI:
    """Razorpay SDK — Indian payment gateway"""
    def orders_create(self, amount: int, currency: str, notes: dict):
        print(f"[RAZORPAY] Order created: {amount} {currency}")
        return {"id": "order_rp_001", "status": "created"}

    def payments_refund(self, payment_id: str, amount: int):
        print(f"[RAZORPAY] Refund: {amount} for {payment_id}")
        return {"id": "rfnd_rp_001", "status": "processed"}

    def payments_fetch(self, payment_id: str):
        return {"id": payment_id, "status": "captured"}


# ─── Adapter 1: Stripe ko tumhare interface mein dhalo ───
class StripeAdapter(PaymentGateway):
    """
    Stripe ka API → tumhara PaymentGateway interface.
    Adapter mein translation hoti hai.
    """
    def __init__(self, stripe_api: StripeAPI):
        self._stripe = stripe_api  # Wrapped karo

    def charge(self, amount: float, currency: str, customer_id: str) -> dict:
        # Tumhari app rupees mein deti hai → Stripe paise mein chahiye
        amount_paise = int(amount * 100)  # Translation!
        result = self._stripe.create_payment_intent(amount_paise, currency, customer_id)
        # Stripe ka response → tumhara standard response
        return {
            "charge_id":  result["id"],
            "status":     result["status"],
            "amount":     amount,
            "gateway":    "stripe"
        }

    def refund(self, charge_id: str, amount: float) -> dict:
        amount_paise = int(amount * 100)  # Translation!
        result = self._stripe.create_refund(charge_id, amount_paise)
        return {
            "refund_id": result["id"],
            "status":    result["status"]
        }

    def get_status(self, charge_id: str) -> str:
        result = self._stripe.retrieve_payment_intent(charge_id)
        # Stripe status → tumhara standard status
        status_map = {
            "requires_confirmation": "PENDING",
            "processing":           "PROCESSING",
            "succeeded":            "COMPLETED",
            "canceled":             "CANCELLED"
        }
        return status_map.get(result["status"], "UNKNOWN")


# ─── Adapter 2: Razorpay ko tumhare interface mein dhalo ───
class RazorpayAdapter(PaymentGateway):
    """Razorpay ka API → tumhara PaymentGateway interface"""

    def __init__(self, razorpay_api: RazorpayAPI):
        self._razorpay = razorpay_api

    def charge(self, amount: float, currency: str, customer_id: str) -> dict:
        # Razorpay bhi paise mein kaam karta hai
        amount_paise = int(amount * 100)
        result = self._razorpay.orders_create(
            amount   = amount_paise,
            currency = currency,
            notes    = {"customer_id": customer_id}
        )
        return {
            "charge_id": result["id"],
            "status":    "PENDING",
            "amount":    amount,
            "gateway":   "razorpay"
        }

    def refund(self, charge_id: str, amount: float) -> dict:
        result = self._razorpay.payments_refund(charge_id, int(amount * 100))
        return {"refund_id": result["id"], "status": "COMPLETED"}

    def get_status(self, charge_id: str) -> str:
        result = self._razorpay.payments_fetch(charge_id)
        status_map = {
            "created":   "PENDING",
            "captured":  "COMPLETED",
            "refunded":  "REFUNDED",
            "failed":    "FAILED"
        }
        return status_map.get(result["status"], "UNKNOWN")


# ─── Real Project: SAP HANA Adapter (Youngman) ───
class InvoiceGateway(ABC):
    """Tumhara internal invoice interface"""
    @abstractmethod
    def push_invoice(self, invoice_data: dict) -> str:
        pass

    @abstractmethod
    def get_invoice_status(self, doc_number: str) -> str:
        pass


class SAPHANAAPI:
    """
    SAP HANA Service Layer — actual SAP API
    SAP ke apne endpoints aur response format hain
    """
    def post_to_service_layer(self, endpoint: str, payload: dict) -> dict:
        print(f"[SAP] POST {endpoint}: {list(payload.keys())}")
        return {"DocNum": 12345, "DocEntry": 67890, "DocStatus": "O"}

    def get_from_service_layer(self, endpoint: str, doc_entry: int) -> dict:
        return {"DocEntry": doc_entry, "DocStatus": "C", "DocTotal": 50000}


class SAPHANAInvoiceAdapter(InvoiceGateway):
    """
    SAP HANA API → InvoiceGateway interface
    4858+ line connector — yahi kaam karta tha
    """
    SAP_ENDPOINT = "/b1s/v1/Invoices"

    def __init__(self, sap_api: SAPHANAAPI, token_cache):
        self._sap   = sap_api
        self._cache = token_cache

    def push_invoice(self, invoice_data: dict) -> str:
        # Tumhara invoice format → SAP format mein convert karo
        sap_payload = self._to_sap_format(invoice_data)
        result = self._sap.post_to_service_layer(self.SAP_ENDPOINT, sap_payload)
        # SAP ka DocNum → tumhara invoice reference
        return str(result["DocNum"])

    def get_invoice_status(self, doc_number: str) -> str:
        result = self._sap.get_from_service_layer(self.SAP_ENDPOINT, int(doc_number))
        # SAP status code → tumhara status
        sap_status_map = {"O": "OPEN", "C": "CLOSED", "L": "LOCKED"}
        return sap_status_map.get(result["DocStatus"], "UNKNOWN")

    def _to_sap_format(self, invoice: dict) -> dict:
        """Translation logic — tumhara format → SAP format"""
        return {
            "CardCode":    invoice["customer_sap_code"],
            "DocDate":     invoice["invoice_date"].strftime("%Y%m%d"),
            "DocTotal":    float(invoice["total_amount"]),
            "DocumentLines": [
                {
                    "ItemCode":     line["item_code"],
                    "Quantity":     line["quantity"],
                    "UnitPrice":    float(line["unit_price"]),
                    "TaxCode":      line["tax_code"],
                }
                for line in invoice["line_items"]
            ]
        }


# ─── Usage — client ka code same rehta hai ───
class PaymentService:
    def __init__(self, gateway: PaymentGateway):
        self.gateway = gateway  # Adapter inject karo

    def process_payment(self, amount: float, currency: str, customer: str):
        # Same code — Stripe ho ya Razorpay
        result = self.gateway.charge(amount, currency, customer)
        print(f"Charged: {result}")
        return result


# Factory se gateway choose karo
stripe_adapter   = StripeAdapter(StripeAPI())
razorpay_adapter = RazorpayAdapter(RazorpayAPI())

# Same service, alag gateway — Adapter magic
stripe_service   = PaymentService(stripe_adapter)
razorpay_service = PaymentService(razorpay_adapter)

stripe_service.process_payment(1000.0, "INR", "cust_001")
razorpay_service.process_payment(1000.0, "INR", "cust_002")
```

---

### 1.5 Tumhara Real Project Mein Kahan Use Hua

```
Project 1 — Youngman ERP (Production — 4858+ lines):
  → SAPHANAInvoiceAdapter
    Tumhara Invoice model → SAP Service Layer format
    DocDate, CardCode, DocumentLines format mein convert
    SAP DocNum → tumhara invoice reference number
    99% success rate, 10,000+ invoices/month

Project 2 — Youngman Django Backend:
  → MasterIndiaGSTAdapter
    Tumhara Customer model → MasterIndia GSTIN validation API
    API response → tumhara validation result format

Project 3 — Niroskos Safari Platform:
  → Payment provider adapters
    Stripe, Coinbase (Crypto), M-Pesa — sab alag APIs
    Ek common PaymentGateway interface
    PaymentService ko nahi pata provider kaun hai
```

---

## PART 2: ENGLISH — Interviewer ko bolne ke liye

### 2.1 Definition

> **Adapter is a structural pattern that allows objects with incompatible interfaces to collaborate. It acts as a wrapper that converts the interface of one class into the interface expected by the client.**

---

### 2.2 Problem It Solves

```
Problem: Stripe API has create_payment_intent(amount_in_paise, ...)
         Your app expects charge(amount_in_rupees, ...)
         You can't modify Stripe's SDK.
         You don't want Stripe-specific code spread across your app.

Solution: StripeAdapter implements your PaymentGateway interface
          Internally it calls Stripe's API and translates
          Your app only knows PaymentGateway — never Stripe directly
```

---

### 2.3 Key Components

| Component | Role | Example |
|-----------|------|---------|
| **Target Interface** | What client expects | `PaymentGateway(ABC)` |
| **Adaptee** | Existing incompatible class | `StripeAPI`, `SAPHANAAPI` |
| **Adapter** | Bridges target and adaptee | `StripeAdapter(PaymentGateway)` |
| **Client** | Uses target interface | `PaymentService(gateway: PaymentGateway)` |

---

### 2.4 Clean Code Example

```python
from abc import ABC, abstractmethod

# Target Interface (what your app expects)
class StorageProvider(ABC):
    @abstractmethod
    def save(self, key: str, data: bytes) -> str: pass

    @abstractmethod
    def retrieve(self, key: str) -> bytes: pass


# Adaptee 1: AWS S3 (boto3 SDK — different interface)
class AWSS3Client:
    def put_object(self, Bucket: str, Key: str, Body: bytes) -> dict:
        print(f"[S3] Saving {Key} to {Bucket}")
        return {"ETag": "etag123"}

    def get_object(self, Bucket: str, Key: str) -> dict:
        return {"Body": b"file_content"}


# Adaptee 2: Cloudinary (completely different interface)
class CloudinaryClient:
    def upload(self, file_data: bytes, public_id: str, folder: str) -> dict:
        print(f"[CLOUDINARY] Uploading {public_id}")
        return {"secure_url": f"https://cloudinary.com/{folder}/{public_id}"}

    def download(self, public_id: str, folder: str) -> bytes:
        return b"cloudinary_file"


# Adapter 1: S3 → StorageProvider
class S3Adapter(StorageProvider):
    BUCKET = "niroskos-media"

    def __init__(self, s3_client: AWSS3Client):
        self._s3 = s3_client

    def save(self, key: str, data: bytes) -> str:
        self._s3.put_object(Bucket=self.BUCKET, Key=key, Body=data)
        return f"s3://{self.BUCKET}/{key}"

    def retrieve(self, key: str) -> bytes:
        response = self._s3.get_object(Bucket=self.BUCKET, Key=key)
        return response["Body"]


# Adapter 2: Cloudinary → StorageProvider
class CloudinaryAdapter(StorageProvider):
    FOLDER = "niroskos"

    def __init__(self, cloudinary: CloudinaryClient):
        self._cloudinary = cloudinary

    def save(self, key: str, data: bytes) -> str:
        result = self._cloudinary.upload(data, public_id=key, folder=self.FOLDER)
        return result["secure_url"]

    def retrieve(self, key: str) -> bytes:
        return self._cloudinary.download(key, self.FOLDER)


# Client — storage agnostic
class ImageUploadService:
    def __init__(self, storage: StorageProvider):
        self._storage = storage

    def upload_profile_image(self, user_id: str, image_data: bytes) -> str:
        key = f"profiles/{user_id}/avatar.jpg"
        return self._storage.save(key, image_data)


# Switch storage provider — zero code change in service
s3_service          = ImageUploadService(S3Adapter(AWSS3Client()))
cloudinary_service  = ImageUploadService(CloudinaryAdapter(CloudinaryClient()))
```

---

### 2.5 Real Project Answer

**"Where did you use Adapter pattern?"**

> "The most significant use was the SAP HANA integration in Youngman ERP — 4858+ lines of connector code.
>
> SAP Business One has its own Service Layer API with specific endpoints, authentication (session token), request format (CardCode, DocDate, DocumentLines), and response format (DocNum, DocEntry, DocStatus). Our internal system had completely different field names and structures.
>
> I built a `SAPHANAInvoiceAdapter` that implemented our internal `InvoiceGateway` interface. Inside, it translated our invoice data to SAP's format, made the API call, and translated SAP's response back. The business service only called `gateway.push_invoice(data)` — it never knew about SAP's API structure.
>
> This achieved 99% success rate on 10,000+ monthly invoices. When SAP upgraded their API version, we only changed the adapter — zero impact on business logic."

---

### 2.6 Follow-up Q&A

**Q: "Adapter vs Facade — difference?"**
> "Adapter translates one interface to another — same functionality, different interface. Facade simplifies a complex system — hides multiple subsystems behind one simple interface. Example: Adapter makes Stripe work like our PaymentGateway. Facade might be a single `PaymentService.pay()` that internally handles Stripe, fraud detection, notifications, audit logging — hiding all that complexity."

**Q: "Object Adapter vs Class Adapter?"**
> "Object Adapter uses composition — holds a reference to the adaptee. Class Adapter uses inheritance — inherits from both target and adaptee. Python prefers Object Adapter (composition over inheritance). Class Adapter is problematic with multiple inheritance and creates tight coupling."

**Q: "How did you handle API version changes with Adapter?"**
> "When SAP upgraded their Service Layer API, only the `_to_sap_format()` method in the adapter changed — the field mapping was updated. Business service, models, serializers — nothing touched. That's the key benefit: changes in external APIs are isolated to the adapter class."

---

*Last Updated: April 2026 | SDE-2 Interview Prep*
