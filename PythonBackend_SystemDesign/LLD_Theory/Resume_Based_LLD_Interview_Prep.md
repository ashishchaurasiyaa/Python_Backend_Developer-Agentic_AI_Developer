# Resume-Based LLD Interview Preparation
## Ashish Kumar Chaurasiya — SDE-2 Interview at Interview Kickstart

> **How to use this file:**
> - Har section mein pehle **khud answer socho** (2-3 min)
> - Phir answer dekho
> - `🎯` = Most likely question
> - `💼` = Tumhara direct project experience connect karo
> - `⚡` = 30-second pitch (memorize this)

---

## MASTER CHECKLIST

```
[ ] SAP HANA Connector — Adapter + Singleton + Token Cache
[ ] Exotel Rate Limiter — Token Bucket + Distributed Lock
[ ] Payment System — Strategy + Idempotency
[ ] Booking State Machine — State Pattern
[ ] Task Queue / Celery — Producer-Broker-Worker
[ ] Multi-Tenant Notification — Abstract Factory
[ ] Redis Caching + Cache Invalidation
[ ] JWT + RBAC + OTP Auth
[ ] Multi-Company DB Design
[ ] Certificate Generation System
```

---

# SECTION 1: SAP HANA CONNECTOR

> 💼 **Your context:** 4,858+ lines connector — customer sync, invoice push, JE creation, payment reconciliation. 10,000+ invoices/month. In-memory token caching (5-min TTL), retry logic, idempotent ops.

---

## 🎯 Q1.1: Design the SAP HANA API Connector. How do you handle token expiry?

### ⚡ 30-Second Pitch
> "SAP HANA uses session-based tokens — expire every 5 minutes. I used Singleton pattern with double-checked locking: if token exists and not expired, return cached. Otherwise acquire lock, check again (second check prevents race), fetch new token. Thread-safe for multiple Celery workers."

### Full Answer

```python
import threading
import time
import requests
from dataclasses import dataclass
from typing import Optional

@dataclass
class SAPToken:
    value: str
    expires_at: float      # Unix timestamp
    
    def is_valid(self) -> bool:
        return time.time() < self.expires_at - 30  # 30s buffer

class SAPTokenStore:
    """
    Singleton: ek hi token store, multiple workers share karte hain
    Double-checked locking: fast path (no lock) + safe path (with lock)
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:          # Double-check
                    cls._instance = super().__new__(cls)
                    cls._instance._token = None
                    cls._instance._token_lock = threading.Lock()
        return cls._instance
    
    def get_token(self) -> str:
        # Fast path — no lock if token valid
        if self._token and self._token.is_valid():
            return self._token.value
        
        # Slow path — acquire lock, fetch new token
        with self._token_lock:
            if self._token and self._token.is_valid():  # Double-check
                return self._token.value
            
            self._token = self._fetch_new_token()
            return self._token.value
    
    def _fetch_new_token(self) -> SAPToken:
        response = requests.post(
            "https://sap-hana-server/b1s/v1/Login",
            json={"CompanyDB": "COMPANY", "UserName": "user", "Password": "pass"},
            timeout=10
        )
        response.raise_for_status()
        session_id = response.json()["SessionId"]
        
        return SAPToken(
            value=session_id,
            expires_at=time.time() + 300   # 5 minutes
        )
    
    def invalidate(self):
        """Force refresh on 401"""
        with self._token_lock:
            self._token = None


class SAPHANAAdapter:
    """
    Adapter Pattern:
    - SAP interface: POST /b1s/v1/Invoices, headers={"B1SESSION": token}
    - Our interface: push_invoice(invoice_data: dict) -> str (SAP doc number)
    
    Adapter bridges the gap — internal code SAP API nahi jaanta
    """
    
    BASE_URL = "https://sap-hana-server/b1s/v1"
    
    def __init__(self):
        self._token_store = SAPTokenStore()
    
    def _headers(self) -> dict:
        return {
            "B1SESSION": self._token_store.get_token(),
            "Content-Type": "application/json"
        }
    
    def _request_with_retry(self, method: str, endpoint: str,
                             data: dict = None, max_retries: int = 3) -> dict:
        """
        Retry with exponential backoff
        On 401 → refresh token, retry once
        On 5xx → exponential backoff
        """
        for attempt in range(max_retries):
            try:
                resp = requests.request(
                    method, f"{self.BASE_URL}/{endpoint}",
                    json=data, headers=self._headers(), timeout=30
                )
                
                if resp.status_code == 401:
                    self._token_store.invalidate()
                    continue  # Retry with fresh token
                
                resp.raise_for_status()
                return resp.json()
            
            except requests.HTTPError as e:
                if attempt == max_retries - 1:
                    raise
                delay = (2 ** attempt) + 0.1  # 1s, 2s, 4s
                time.sleep(delay)
        
        raise Exception("Max retries exceeded")
    
    # Our clean interface — callers don't know about SAP internals
    
    def push_invoice(self, invoice_data: dict) -> str:
        """Returns SAP DocEntry (unique SAP document number)"""
        result = self._request_with_retry("POST", "Invoices", invoice_data)
        return str(result["DocEntry"])
    
    def sync_customer(self, customer_data: dict) -> str:
        result = self._request_with_retry("POST", "BusinessPartners", customer_data)
        return result["CardCode"]
    
    def get_outstanding_balance(self, bp_code: str) -> float:
        result = self._request_with_retry("GET", f"BusinessPartners('{bp_code}')")
        return result.get("CurrentAccountBalance", 0.0)
```

### Idempotency — Invoice Push

```python
# Problem: Network failure ke baad retry → same invoice twice push?
# Solution: SAP DocEntry DB mein store karo before push

class InvoiceSync:
    def push_to_sap(self, invoice_id: str, sap_adapter: SAPHANAAdapter):
        # Check: already pushed?
        existing = db.query(
            "SELECT sap_doc_entry FROM invoices WHERE id = %s", [invoice_id]
        )
        if existing and existing[0]['sap_doc_entry']:
            return existing[0]['sap_doc_entry']   # Already done
        
        # Prepare payload
        data = self._build_sap_payload(invoice_id)
        
        # Push
        doc_entry = sap_adapter.push_invoice(data)
        
        # Save (idempotency key)
        db.execute(
            "UPDATE invoices SET sap_doc_entry = %s WHERE id = %s",
            [doc_entry, invoice_id]
        )
        return doc_entry
```

### Follow-up Questions

**Q: Multiple Celery workers ek saath token fetch karein to?**
> Double-checked locking handle karta hai. `_token_lock` ensure karta hai ki sirf ek worker token fetch kare. Baaki workers lock release hone ka wait karein phir fast path pe chalein — valid token milti hai.

**Q: SAP server down hai — kaise handle karte ho?**
> Circuit Breaker pattern: consecutive failures count karo. 5 failures → circuit OPEN ho jaata hai (fast fail). 60 sec baad → HALF_OPEN (ek trial request). Success → CLOSED. Isse SAP downtime pe humara system request queue nahi bharta.

**Q: Token SAP se 401 aayi retry ke beech mein?**
> `invalidate()` call karte hain, loop continue karta hai — next iteration fresh token se request hoti hai. Sirf ek extra token fetch hoti hai, infinite loop nahi.

---

## 🎯 Q1.2: Adapter Pattern — SAP API vs Internal Interface

### Answer

```
Problem: SAP HANA API interface alag hai humari internal code se:
  SAP:      POST /b1s/v1/Invoices + B1SESSION header + SAP-specific payload
  Internal: push_invoice(invoice: Invoice) → str

Bina Adapter:
  Har jagah SAP-specific code → tightly coupled
  SAP version change → 100 files change

With Adapter:
  SAPHANAAdapter.push_invoice(data) → uniform interface
  SAP version change → sirf adapter change
  Testing: mock adapter inject karo

Class diagram:
InvoiceService → InvoicePushPort (interface)
                      ↑
               SAPHANAAdapter (implements)
               MockSAPAdapter (for tests)
```

---

# SECTION 2: EXOTEL RATE LIMITER

> 💼 **Your context:** Exotel 200 req/min limit — AR collections dialer, click-to-call, IVR routing, bulk calling campaigns. HMAC webhook validation.

---

## 🎯 Q2.1: Design Rate Limiter for Exotel (200 req/min). Which algorithm?

### ⚡ 30-Second Pitch
> "Token Bucket — best for Exotel because it allows bursts. 200 tokens/minute = 3.33/sec refill rate. Lazy refill: calculate elapsed time × rate on every request. For distributed Celery workers, Redis Lua script ensures atomic check-and-consume — no race condition."

### Full Answer

```python
import time
import threading
import redis

# ===== IN-PROCESS: Single Worker =====

class TokenBucketRateLimiter:
    """
    Token Bucket:
    - Bucket mein max `capacity` tokens
    - Har second `refill_rate` tokens add hote hain
    - Request = 1 token consume
    - Burst allowed (bucket full hone tak)
    
    Exotel: capacity=200, refill_rate=200/60=3.33/sec
    """
    
    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.refill_rate = refill_rate     # tokens per second
        self._tokens = float(capacity)
        self._last_refill = time.time()
        self._lock = threading.Lock()
    
    def allow_request(self) -> tuple[bool, float]:
        """Returns (allowed, retry_after_seconds)"""
        with self._lock:
            self._refill()
            
            if self._tokens >= 1:
                self._tokens -= 1
                return True, 0.0
            
            retry_after = (1 - self._tokens) / self.refill_rate
            return False, retry_after
    
    def _refill(self):
        now = time.time()
        elapsed = now - self._last_refill
        add = elapsed * self.refill_rate
        self._tokens = min(self.capacity, self._tokens + add)
        self._last_refill = now


# ===== DISTRIBUTED: Multiple Celery Workers =====

REDIS_SCRIPT = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

local data = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(data[1]) or capacity
local last_refill = tonumber(data[2]) or now

-- Refill
local elapsed = now - last_refill
local add = elapsed * refill_rate
tokens = math.min(capacity, tokens + add)

if tokens >= 1 then
    tokens = tokens - 1
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
    redis.call('EXPIRE', key, 120)
    return 1   -- allowed
else
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
    return 0   -- rejected
end
"""

class DistributedTokenBucketRateLimiter:
    def __init__(self, redis_client, capacity: int, refill_rate: float):
        self.redis = redis_client
        self.capacity = capacity
        self.refill_rate = refill_rate
        self._script = redis_client.register_script(REDIS_SCRIPT)
    
    def allow_request(self, key: str = "exotel") -> bool:
        result = self._script(
            keys=[f"ratelimit:{key}"],
            args=[self.capacity, self.refill_rate, time.time()]
        )
        return bool(result)


# ===== EXOTEL SERVICE with Rate Limiter =====

class RateLimitError(Exception):
    def __init__(self, retry_after: float):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after:.1f}s")

class ExotelService:
    """
    Production: DistributedTokenBucketRateLimiter (Redis-based)
    200 requests/minute = 3.33 tokens/second
    """
    
    def __init__(self, redis_client=None):
        if redis_client:
            self.limiter = DistributedTokenBucketRateLimiter(
                redis_client, capacity=200, refill_rate=200/60
            )
        else:
            self.limiter = TokenBucketRateLimiter(capacity=200, refill_rate=200/60)
    
    def send_sms(self, phone: str, message: str):
        allowed = self.limiter.allow_request("exotel_sms")
        if not allowed:
            raise RateLimitError(retry_after=1.0)
        
        # Actual Exotel API call
        print(f"[Exotel] SMS to {phone}: {message[:30]}...")
    
    def make_call(self, phone: str):
        allowed = self.limiter.allow_request("exotel_call")
        if not allowed:
            raise RateLimitError(retry_after=1.0)
        
        print(f"[Exotel] Call to {phone}")
```

### HMAC Webhook Validation

```python
import hmac
import hashlib

class ExotelWebhookHandler:
    """
    HMAC validation:
    1. Exotel sends: X-Exotel-Signature header
    2. We compute: HMAC-SHA256(secret_key, request_body)
    3. Compare: if match → authentic, else → reject
    
    Replay attack prevention: timestamp check (within 5 min)
    """
    
    SECRET_KEY = "your_exotel_secret"
    MAX_TIMESTAMP_DIFF = 300  # 5 minutes
    
    def validate_webhook(self, body: bytes, signature: str, timestamp: str) -> bool:
        # 1. Timestamp check (replay attack prevention)
        request_time = int(timestamp)
        if abs(time.time() - request_time) > self.MAX_TIMESTAMP_DIFF:
            return False
        
        # 2. HMAC compute
        expected = hmac.new(
            self.SECRET_KEY.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        
        # 3. Constant-time compare (prevent timing attacks)
        return hmac.compare_digest(expected, signature)
```

### Follow-up Questions

**Q: Token Bucket vs Sliding Window — kab kaunsa?**
```
Token Bucket:
✓ Burst allow karta hai (Exotel: 20 calls ek saath phir slow down)
✓ Smooth rate limiting
✗ Exact window guarantee nahi

Sliding Window Counter:
✓ Exact per-minute guarantee
estimate = curr_count + prev_count × (1 - elapsed/window)
✓ Memory efficient
✗ No burst allowed

Exotel ke liye: Token Bucket — bursts needed for AR dialer campaigns
```

**Q: 5 workers ek saath 50 requests each karein (250 total > 200 limit)?**
> Without distributed lock: har worker apna local bucket maintain kare → total 250 requests → Exotel block kare. With Redis Lua script: atomic check-and-consume across all workers → total 200 requests → correct. Lua script atomicity Redis ke single-threaded nature se guaranteed hai.

---

# SECTION 3: PAYMENT SYSTEM

> 💼 **Your context:** Niroskos — Card, Crypto/Web3, M-Pesa, Bank Transfer. Refund approval workflows. 50,000+ daily transactions.

---

## 🎯 Q3.1: Design Multi-Payment System with Idempotency

### ⚡ 30-Second Pitch
> "Strategy Pattern: PaymentGateway ABC with initiate/verify/refund methods. StripeGateway, Web3Gateway, MPesaGateway implement it. Factory creates correct gateway. Idempotency: 3-layer — in-memory request hash check, per-payment distributed lock, DB unique constraint on provider_event_id."

### Full Answer

```python
from abc import ABC, abstractmethod
from typing import Optional
import threading

# ===== STRATEGY: Payment Gateways =====

class PaymentGateway(ABC):
    @abstractmethod
    def initiate_charge(self, amount: float, currency: str, metadata: dict) -> dict:
        pass
    
    @abstractmethod
    def verify_payment(self, provider_payment_id: str) -> dict:
        pass
    
    @abstractmethod
    def initiate_refund(self, provider_payment_id: str, amount: float) -> dict:
        pass
    
    @property
    def requires_manual_refund(self) -> bool:
        return False  # Default: automatic refund


class StripeGateway(PaymentGateway):
    def initiate_charge(self, amount, currency, metadata):
        # stripe.PaymentIntent.create(...)
        return {"provider_payment_id": "pi_xxx", "status": "pending"}
    
    def verify_payment(self, provider_payment_id):
        return {"status": "succeeded", "amount": 1000}
    
    def initiate_refund(self, provider_payment_id, amount):
        # stripe.Refund.create(payment_intent=provider_payment_id, amount=amount)
        return {"refund_id": "re_xxx", "status": "succeeded"}


class Web3Gateway(PaymentGateway):
    """
    Crypto: Ethereum wallet se payment
    Refund = manual (blockchain pe transaction reverse nahi hoti)
    """
    
    def initiate_charge(self, amount, currency, metadata):
        wallet_address = "0x742d35Cc6634C0532925a3b844Bc454e4438f44e"
        return {
            "provider_payment_id": f"0x{metadata.get('txn_hash', '')}",
            "wallet_address": wallet_address,
            "status": "pending_blockchain_confirmation"
        }
    
    def verify_payment(self, provider_payment_id):
        # Web3.py: check transaction confirmations
        return {"status": "confirmed", "confirmations": 12}
    
    def initiate_refund(self, provider_payment_id, amount):
        raise NotImplementedError("Crypto refunds require manual approval workflow")
    
    @property
    def requires_manual_refund(self) -> bool:
        return True   # Always manual for crypto


class MPesaGateway(PaymentGateway):
    def initiate_charge(self, amount, currency, metadata):
        # Daraja API STK push
        return {"provider_payment_id": "mpesa_xxx", "status": "pending"}
    
    def verify_payment(self, provider_payment_id):
        return {"status": "COMPLETED", "amount": amount}
    
    def initiate_refund(self, provider_payment_id, amount):
        # M-Pesa B2C API
        return {"refund_id": "mpesa_refund_xxx"}


# ===== FACTORY =====

class PaymentGatewayFactory:
    _gateways = {
        "stripe": StripeGateway,
        "web3": Web3Gateway,
        "mpesa": MPesaGateway,
    }
    
    @classmethod
    def create(cls, payment_method: str) -> PaymentGateway:
        gateway_class = cls._gateways.get(payment_method)
        if not gateway_class:
            raise ValueError(f"Unknown payment method: {payment_method}")
        return gateway_class()
    
    @classmethod
    def register(cls, name: str, gateway_class):
        """New payment method add karo without changing existing code"""
        cls._gateways[name] = gateway_class


# ===== IDEMPOTENCY — 3 Layer Protection =====

class PaymentService:
    """
    3-layer idempotency:
    Layer 1: In-memory request hash (same request milliseconds mein)
    Layer 2: Distributed lock per payment (processing ke time)
    Layer 3: DB unique constraint on provider_event_id (permanent)
    """
    
    def __init__(self, redis_client=None):
        self._processing = {}           # Layer 1: payment_id → in-flight
        self._lock = threading.Lock()
        self.redis = redis_client
    
    def process_payment(self, booking_id: str, amount: float,
                        payment_method: str, idempotency_key: str) -> dict:
        
        # Layer 1: Already processing?
        with self._lock:
            if idempotency_key in self._processing:
                return {"status": "processing", "message": "Duplicate request"}
            self._processing[idempotency_key] = True
        
        try:
            # Layer 2: Distributed lock (Redis SET NX EX)
            lock_key = f"payment_lock:{idempotency_key}"
            if self.redis:
                acquired = self.redis.set(lock_key, "1", nx=True, ex=30)
                if not acquired:
                    return {"status": "processing", "message": "Already processing"}
            
            try:
                # DB check: already processed? (Layer 3 check before insert)
                existing = self._get_existing_payment(idempotency_key)
                if existing:
                    return {"status": "success", "payment_id": existing["id"],
                            "message": "Already processed"}
                
                # Create payment
                gateway = PaymentGatewayFactory.create(payment_method)
                result = gateway.initiate_charge(amount, "USD", {"booking_id": booking_id})
                
                # Save with idempotency_key (Layer 3: UNIQUE constraint in DB)
                payment = self._save_payment(
                    booking_id=booking_id,
                    amount=amount,
                    idempotency_key=idempotency_key,
                    provider_payment_id=result["provider_payment_id"]
                )
                
                return {"status": "success", "payment_id": payment["id"]}
            
            finally:
                if self.redis:
                    self.redis.delete(lock_key)
        
        finally:
            with self._lock:
                self._processing.pop(idempotency_key, None)
    
    def _get_existing_payment(self, idempotency_key: str):
        # DB query: SELECT * FROM payments WHERE idempotency_key = ?
        pass
    
    def _save_payment(self, **kwargs):
        # INSERT INTO payments (idempotency_key, ...) VALUES (...)
        # DB will raise IntegrityError on duplicate (UNIQUE constraint)
        pass


# ===== WEBHOOK HANDLER =====

class WebhookHandler:
    """
    Provider webhook pe payment confirm karo
    Same event_id dobara aaye → ignore (idempotent)
    """
    
    def __init__(self):
        self._processed_events = set()   # In-memory (Redis mein better)
        self._lock = threading.Lock()
    
    def handle_stripe_webhook(self, event_id: str, event_type: str, data: dict):
        with self._lock:
            if event_id in self._processed_events:
                return {"status": "already_processed"}
            self._processed_events.add(event_id)
        
        if event_type == "payment_intent.succeeded":
            self._confirm_payment(data["payment_intent_id"])
        elif event_type == "payment_intent.payment_failed":
            self._fail_payment(data["payment_intent_id"])
    
    def _confirm_payment(self, provider_payment_id: str):
        # UPDATE bookings SET status='CONFIRMED' WHERE payment_id=...
        pass
```

### Follow-up Questions

**Q: Web3 payment confirm hone mein time lagta hai — kaise handle karo?**
> "Blockchain confirmations async hai — 12+ confirmations chahiye (Ethereum). Flow: (1) Show pending screen, (2) Backend Celery task — poll blockchain every 30s for confirmations. (3) 12 confirmations milne pe → payment CONFIRMED, booking CONFIRMED, notification send. Max wait: 30 minutes. Timeout ke baad: FAILED status, refund process."

**Q: Crypto refund kaise handle kiya?**
> "Web3Gateway.requires_manual_refund = True. Jab refund request aati hai: (1) RefundRequest DB mein create hoti hai (PENDING), (2) Admin dashboard mein dikhti hai, (3) Finance team manually crypto wallet se transfer karti hai, (4) Transaction hash enter karte hain system mein — RefundRequest COMPLETED. Customer ko notification."

---

# SECTION 4: BOOKING STATE MACHINE

> 💼 **Your context:** Niroskos — Draft→Confirm state machine. Youngman Beta — invoicing workflow.

---

## 🎯 Q4.1: Design Booking Lifecycle State Machine

### ⚡ 30-Second Pitch
> "State machine with explicit valid transitions. State enum + transition table. On invalid transition: raise InvalidTransitionError. Side effects (send email, create payment) ko Observer pattern se decouple karo — BookingService events emit karta hai, handlers subscribe karte hain."

### Full Answer

```python
from enum import Enum
from typing import Set, Dict, Callable, List
from dataclasses import dataclass

class BookingStatus(Enum):
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    ALLOCATED = "ALLOCATED"      # Driver/resource assigned
    IN_TRANSIT = "IN_TRANSIT"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    REFUND_PENDING = "REFUND_PENDING"

# Valid transitions — jab koi invalid kare to reject karo
VALID_TRANSITIONS: Dict[BookingStatus, Set[BookingStatus]] = {
    BookingStatus.DRAFT: {BookingStatus.CONFIRMED, BookingStatus.CANCELLED},
    BookingStatus.CONFIRMED: {BookingStatus.ALLOCATED, BookingStatus.CANCELLED},
    BookingStatus.ALLOCATED: {BookingStatus.IN_TRANSIT, BookingStatus.CANCELLED},
    BookingStatus.IN_TRANSIT: {BookingStatus.DELIVERED},
    BookingStatus.DELIVERED: set(),              # Terminal state
    BookingStatus.CANCELLED: {BookingStatus.REFUND_PENDING},
    BookingStatus.REFUND_PENDING: set(),         # Terminal state
}

class InvalidTransitionError(Exception):
    pass

@dataclass
class Booking:
    booking_id: str
    status: BookingStatus = BookingStatus.DRAFT
    
    def transition_to(self, new_status: BookingStatus) -> 'Booking':
        allowed = VALID_TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise InvalidTransitionError(
                f"Cannot transition from {self.status.value} to {new_status.value}. "
                f"Allowed: {[s.value for s in allowed]}"
            )
        self.status = new_status
        return self
    
    def can_cancel(self) -> bool:
        return BookingStatus.CANCELLED in VALID_TRANSITIONS.get(self.status, set())


# ===== OBSERVER: Side Effects Decoupled =====

class BookingEventBus:
    """
    Booking state change → multiple subscribers notify karo
    Email, Payment, Analytics — sab decouple hain
    """
    
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
    
    def subscribe(self, event: str, handler: Callable):
        self._subscribers.setdefault(event, []).append(handler)
    
    def publish(self, event: str, booking: Booking):
        for handler in self._subscribers.get(event, []):
            try:
                handler(booking)
            except Exception as e:
                print(f"[EventBus] Handler error for {event}: {e}")
                # Non-critical handlers fail silently

# Usage:
bus = BookingEventBus()
bus.subscribe("booking.confirmed", lambda b: send_confirmation_email(b))
bus.subscribe("booking.confirmed", lambda b: create_payment_record(b))
bus.subscribe("booking.cancelled", lambda b: initiate_refund(b))


class BookingService:
    def __init__(self, event_bus: BookingEventBus):
        self.event_bus = event_bus
    
    def confirm_booking(self, booking: Booking) -> Booking:
        booking.transition_to(BookingStatus.CONFIRMED)
        self.event_bus.publish("booking.confirmed", booking)
        return booking
    
    def cancel_booking(self, booking: Booking, reason: str) -> Booking:
        if not booking.can_cancel():
            raise InvalidTransitionError(
                f"Booking in {booking.status.value} cannot be cancelled"
            )
        booking.transition_to(BookingStatus.CANCELLED)
        self.event_bus.publish("booking.cancelled", booking)
        return booking
```

### Follow-up Questions

**Q: Payment fail ho jaaye CONFIRMED ke baad?**
> "Saga pattern: CONFIRMED ke baad payment attempt. Fail hone pe compensating transaction — booking CANCELLED, refund_pending = False (koi payment nahi hua). Retry: 3 attempts exponential backoff. All 3 fail → CANCELLED + alert ops team via Celery task."

**Q: State machine DB mein kaise persist karo?**
> "`bookings` table mein `status VARCHAR` column. State change pe `UPDATE bookings SET status=NEW_STATUS, updated_at=NOW() WHERE id=X`. Audit trail: `booking_status_logs` table mein har transition record karo — (booking_id, old_status, new_status, changed_by, changed_at, reason). Kabhi bhi history dekhna ho to available."

---

# SECTION 5: CELERY TASK QUEUE

> 💼 **Your context:** Celery + RabbitMQ async processing, 12+ cron automations, monthly invoice generation, AR auto-blocking.

---

## 🎯 Q5.1: Design Distributed Task Queue (Celery Architecture)

### ⚡ 30-Second Pitch
> "Producer-Broker-Worker model. Producer task enqueue karta hai RabbitMQ/Redis mein. Worker dequeue karta hai, execute karta hai. Failed tasks: retry with exponential backoff, max retries ke baad Dead Letter Queue. task_acks_late=True ensures worker crash hone pe task re-queued hota hai."

### Full Answer

```python
# ===== CELERY CONFIGURATION (Production) =====

CELERY_CONFIG = {
    "broker_url": "amqp://user:pass@rabbitmq:5672//",   # RabbitMQ
    "result_backend": "redis://redis:6379/0",
    
    # Critical for reliability
    "task_acks_late": True,             # Ack AFTER execution (not before)
    "task_reject_on_worker_lost": True, # Re-queue if worker dies mid-task
    "worker_prefetch_multiplier": 1,    # One task at a time per worker
    
    # Queues
    "task_routes": {
        "invoicing.push_to_sap": {"queue": "high_priority"},
        "invoicing.monthly_generation": {"queue": "batch"},
        "notifications.send_sms": {"queue": "notifications"},
    },
    
    # Beat schedule (cron)
    "beat_schedule": {
        "monthly-invoice-generation": {
            "task": "invoicing.generate_monthly_invoices",
            "schedule": "0 1 1 * *",   # 1st of every month at 1 AM
        },
        "ar-auto-blocking": {
            "task": "crm.check_aging_and_block",
            "schedule": "0 9 * * *",   # Daily at 9 AM
        },
        "sap-data-sync": {
            "task": "sap.sync_pending_records",
            "schedule": "*/15 * * * *",  # Every 15 minutes
        },
    }
}


# ===== TASK WITH RETRY + DLQ =====

# In Celery:
# @app.task(bind=True, max_retries=3, queue='high_priority')
# def push_invoice_to_sap(self, invoice_id: str):

class InvoiceTask:
    """
    Simulate Celery task behavior
    """
    MAX_RETRIES = 3
    BASE_DELAY = 2  # seconds
    
    def push_invoice_to_sap(self, invoice_id: str, attempt: int = 1):
        try:
            sap = SAPHANAAdapter()
            invoice_data = self._load_invoice(invoice_id)
            doc_entry = sap.push_invoice(invoice_data)
            
            # Success
            self._mark_synced(invoice_id, doc_entry)
            print(f"[Task] Invoice {invoice_id} pushed to SAP: {doc_entry}")
        
        except Exception as e:
            if attempt < self.MAX_RETRIES:
                delay = self.BASE_DELAY ** attempt  # 2, 4, 8 seconds
                print(f"[Task] Retry {attempt}/{self.MAX_RETRIES} in {delay}s")
                # self.retry(countdown=delay, exc=e)  # Celery syntax
            else:
                # Max retries exceeded → Dead Letter Queue
                self._send_to_dlq(invoice_id, str(e))
                print(f"[Task] Invoice {invoice_id} moved to DLQ after {attempt} attempts")
    
    def _send_to_dlq(self, invoice_id: str, error: str):
        # DLQ table mein insert karo for manual review
        # INSERT INTO dead_letter_queue (task_type, payload, error, created_at)
        # VALUES ('push_invoice_to_sap', '{"invoice_id": ...}', error, NOW())
        pass
    
    def _load_invoice(self, invoice_id: str) -> dict:
        pass
    
    def _mark_synced(self, invoice_id: str, doc_entry: str):
        pass


# ===== AR AUTO-BLOCKING TASK =====

class ARAutoBlockingTask:
    """
    AR aging check — PAN ke basis pe customer auto-block karo
    
    Rule: 
    - 15 days overdue → warning
    - 40 days overdue → auto-block (no new orders)
    
    Yeh mujhe Odoo mein implement karna pada tha
    """
    
    THRESHOLDS = {
        "warning": 15,     # days
        "block": 40,       # days
    }
    
    def check_and_block(self):
        """Daily 9 AM run hota hai"""
        from datetime import date, timedelta
        
        today = date.today()
        
        # 40+ days overdue customers → block
        block_cutoff = today - timedelta(days=self.THRESHOLDS["block"])
        customers_to_block = self._get_overdue_customers(block_cutoff)
        
        for customer_id in customers_to_block:
            self._block_customer(customer_id)
            # Notification to AR team
            print(f"[AR] Customer {customer_id} auto-blocked: 40+ days overdue")
        
        # 15+ days → warning notification to AR team
        warn_cutoff = today - timedelta(days=self.THRESHOLDS["warning"])
        customers_to_warn = self._get_overdue_customers(warn_cutoff, exclude_blocked=True)
        
        for customer_id in customers_to_warn:
            print(f"[AR] Warning: Customer {customer_id} 15+ days overdue")
    
    def _get_overdue_customers(self, cutoff_date, exclude_blocked=False) -> list:
        pass
    
    def _block_customer(self, customer_id: str):
        # UPDATE customers SET is_blocked=True WHERE id=customer_id
        pass
```

### Follow-up Questions

**Q: task_acks_late=True kyun use kiya?**
> "Default (ack_early): task broker se dequeue hote hi acknowledge ho jaata hai. Agar worker crash kare execute karte waqt → task lost. task_acks_late=True: task sirf successfully execute hone ke baad acknowledge hota hai. Worker crash → task re-queued → another worker pick up karta hai. Critical tasks (invoice push, payment) ke liye essential."

**Q: Monthly invoice generation fail ho jaaye half-way through?**
> "Idempotent design: har invoice ke liye check karo — is mahine already generated? `SELECT id FROM invoices WHERE customer_id=X AND period='2024-01'`. Agar exists → skip. Task restart karo safely — already done invoices skip, baaki complete karo. Progress checkpoint: `task_state` table mein last processed customer_id store karo."

---

# SECTION 6: MULTI-TENANT NOTIFICATION SYSTEM

> 💼 **Your context:** Niroskos — Twilio + Postmark (Communications module). CRM — Exotel AR dialer.

---

## 🎯 Q6.1: Design Multi-Tenant Notification System

### ⚡ 30-Second Pitch
> "Abstract Factory — TenantNotificationProviders returns correct Email + SMS provider per tenant. Kenya tenant = Postmark + Twilio. India tenant = custom SMTP + Exotel. Strategy for channel selection: CRITICAL events bypass preferences, MARKETING respect opt-out. Deduplication via Redis SET NX."

### Full Answer

```python
from abc import ABC, abstractmethod

# ===== PROVIDER INTERFACES =====

class EmailProvider(ABC):
    @abstractmethod
    def send_email(self, to: str, subject: str, body: str) -> bool:
        pass

class SMSProvider(ABC):
    @abstractmethod
    def send_sms(self, phone: str, message: str) -> bool:
        pass

# ===== CONCRETE PROVIDERS =====

class PostmarkEmailProvider(EmailProvider):
    def send_email(self, to, subject, body):
        # requests.post("https://api.postmarkapp.com/email", ...)
        print(f"[Postmark] Email to {to}: {subject}")
        return True

class TwilioSMSProvider(SMSProvider):
    def send_sms(self, phone, message):
        # twilio_client.messages.create(...)
        print(f"[Twilio] SMS to {phone}: {message[:30]}")
        return True

class ExotelSMSProvider(SMSProvider):
    def __init__(self):
        self.rate_limiter = TokenBucketRateLimiter(200, 200/60)
    
    def send_sms(self, phone, message):
        allowed, retry_after = self.rate_limiter.allow_request()
        if not allowed:
            raise RateLimitError(retry_after)
        print(f"[Exotel] SMS to {phone}: {message[:30]}")
        return True


# ===== ABSTRACT FACTORY: Tenant Providers =====

class NotificationProviderFactory(ABC):
    @abstractmethod
    def create_email_provider(self) -> EmailProvider:
        pass
    
    @abstractmethod
    def create_sms_provider(self) -> SMSProvider:
        pass

class KenyaTenantProviderFactory(NotificationProviderFactory):
    """Niroskos Kenya → Postmark + Twilio"""
    
    def create_email_provider(self): return PostmarkEmailProvider()
    def create_sms_provider(self): return TwilioSMSProvider()

class IndiaTenantProviderFactory(NotificationProviderFactory):
    """Y Equipment India → Custom SMTP + Exotel"""
    
    def create_email_provider(self): return PostmarkEmailProvider()
    def create_sms_provider(self): return ExotelSMSProvider()


# ===== NOTIFICATION SERVICE =====

TENANT_FACTORIES = {
    "niroskos_ke": KenyaTenantProviderFactory,
    "niroskos_in": IndiaTenantProviderFactory,
}

class NotificationService:
    def __init__(self, tenant_id: str, redis_client=None):
        factory_class = TENANT_FACTORIES.get(tenant_id)
        if not factory_class:
            raise ValueError(f"Unknown tenant: {tenant_id}")
        
        factory = factory_class()
        self.email_provider = factory.create_email_provider()
        self.sms_provider = factory.create_sms_provider()
        self.redis = redis_client
    
    def send(self, event_type: str, user_id: str, channel: str,
             to: str, subject: str, body: str, idempotency_key: str):
        
        # Deduplication (same notification sent twice se bachao)
        if self.redis:
            key = f"notif_sent:{idempotency_key}:{channel}"
            already_sent = not self.redis.set(key, "1", nx=True, ex=3600)
            if already_sent:
                print(f"[Notification] Duplicate prevented: {idempotency_key}")
                return
        
        if channel == "EMAIL":
            self.email_provider.send_email(to, subject, body)
        elif channel == "SMS":
            self.sms_provider.send_sms(to, body)
```

---

# SECTION 7: REDIS CACHING + CACHE INVALIDATION

> 💼 **Your context:** SAP token cache (5-min TTL), Typesense signal-based cache invalidation, Redis distributed lock.

---

## 🎯 Q7.1: Design Cache with Invalidation Strategy

### ⚡ 30-Second Pitch
> "Write-through cache: DB update ke saath cache update. TTL-based expiry. Django signals pe cache invalidation — post_save signal → cache.delete(key). Cache stampede prevention: probabilistic early expiry ya mutex lock. Redis SET NX for distributed lock — Lua script for atomic release."

### Full Answer

```python
import redis
import json
import hashlib
import time
import threading
from functools import wraps

# ===== CACHE DECORATOR =====

def cached(ttl: int = 300, key_prefix: str = ""):
    """
    Function result cache karo
    Typesense search results ke liye use kiya
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Cache key
            key_data = f"{key_prefix}:{func.__name__}:{args}:{kwargs}"
            cache_key = hashlib.md5(key_data.encode()).hexdigest()
            
            # Cache hit?
            cached_result = redis_client.get(cache_key)
            if cached_result:
                return json.loads(cached_result)
            
            # Cache miss → compute
            result = func(*args, **kwargs)
            redis_client.setex(cache_key, ttl, json.dumps(result))
            return result
        return wrapper
    return decorator

# Usage:
# @cached(ttl=300, key_prefix="typesense_search")
# def search_packages(query: str, filters: dict) -> list:
#     return typesense_client.collections['packages'].documents.search(...)


# ===== SIGNAL-BASED CACHE INVALIDATION =====

# Django signal (jaise Typesense mein kiya tha):

# from django.db.models.signals import post_save
# from django.dispatch import receiver
# 
# @receiver(post_save, sender=Package)
# def invalidate_package_cache(sender, instance, **kwargs):
#     """Package update hone pe related cache clear karo"""
#     patterns = [
#         f"package:detail:{instance.id}",
#         f"package:list:*",                    # All list caches
#         f"search:packages:*",                 # Search caches
#     ]
#     for pattern in patterns:
#         keys = redis_client.keys(pattern)    # Careful: expensive on large datasets
#         if keys:
#             redis_client.delete(*keys)


# ===== DISTRIBUTED LOCK (for concurrent operations) =====

RELEASE_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
else
    return 0
end
"""

class RedisDistributedLock:
    """
    Redis SET NX EX — atomic lock
    Token-based release — sirf owner hi release kar sakta hai
    
    Used for: Invoice push deduplication, payment processing
    """
    
    def __init__(self, redis_client, key: str, ttl_seconds: int = 30):
        self.redis = redis_client
        self.key = f"lock:{key}"
        self.ttl = ttl_seconds
        self.token = str(uuid.uuid4())
        self._release_script = redis_client.register_script(RELEASE_SCRIPT)
    
    def __enter__(self):
        acquired = self.redis.set(self.key, self.token, nx=True, ex=self.ttl)
        if not acquired:
            raise LockNotAcquiredError(f"Could not acquire lock: {self.key}")
        return self
    
    def __exit__(self, *args):
        self._release_script(keys=[self.key], args=[self.token])

# Usage:
# try:
#     with RedisDistributedLock(redis_client, f"invoice_push:{invoice_id}", ttl=30):
#         push_to_sap(invoice_id)
# except LockNotAcquiredError:
#     # Already being processed
#     pass


# ===== CACHE STAMPEDE PREVENTION =====

class StampedeProofCache:
    """
    Cache stampede: cache expire hote hi 1000 requests DB hit karein
    Prevention: Probabilistic early expiry + mutex on miss
    """
    
    BETA = 1.0  # Higher = more aggressive early refresh
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self._local_locks = {}
        self._lock = threading.Lock()
    
    def get_or_compute(self, key: str, compute_fn, ttl: int):
        raw = self.redis.get(f"cache:{key}")
        
        if raw:
            data = json.loads(raw)
            # Probabilistic early expiry check
            remaining_ttl = self.redis.ttl(f"cache:{key}")
            if self._should_refresh_early(remaining_ttl, ttl, data.get('compute_time', 0.1)):
                # Background refresh (non-blocking)
                threading.Thread(
                    target=self._refresh, args=(key, compute_fn, ttl), daemon=True
                ).start()
            return data['value']
        
        # Cache miss — single refresh with mutex
        with self._get_local_lock(key):
            # Double-check after acquiring lock
            raw = self.redis.get(f"cache:{key}")
            if raw:
                return json.loads(raw)['value']
            
            start = time.time()
            value = compute_fn()
            compute_time = time.time() - start
            
            self.redis.setex(
                f"cache:{key}", ttl,
                json.dumps({'value': value, 'compute_time': compute_time})
            )
            return value
    
    def _should_refresh_early(self, remaining_ttl, original_ttl, compute_time):
        import math, random
        # XFetch algorithm: probability increases as expiry approaches
        return remaining_ttl <= self.BETA * compute_time * math.log(random.random() * -1)
    
    def _get_local_lock(self, key: str):
        with self._lock:
            if key not in self._local_locks:
                self._local_locks[key] = threading.Lock()
            return self._local_locks[key]
    
    def _refresh(self, key, compute_fn, ttl):
        value = compute_fn()
        self.redis.setex(
            f"cache:{key}", ttl,
            json.dumps({'value': value, 'compute_time': 0.1})
        )
```

---

# SECTION 8: JWT + RBAC + OTP AUTH

> 💼 **Your context:** JWT-protected backoffice API (Niroskos), RBAC, OTP auth (YES Platform), OAuth2.

---

## 🎯 Q8.1: Design Authentication + Authorization System

### ⚡ 30-Second Pitch
> "JWT: access token 15 min + refresh token 7 days (stateless scaling). RBAC: User has Roles, Role has Permissions. Permission check O(1) via Redis cached role-permissions. OTP: 6-digit, SHA256 stored, 3-attempt limit, 10-min expiry. Timing attack prevention: dummy_verify() for unknown emails."

### Full Answer

```python
import hashlib
import secrets
import jwt
import bcrypt
from datetime import datetime, timedelta

# ===== PASSWORD HASHING =====

class PasswordHasher:
    ITERATIONS = 310_000     # PBKDF2 iterations (NIST 2023 recommendation)
    
    def hash_password(self, password: str) -> str:
        salt = secrets.token_hex(32)
        hashed = hashlib.pbkdf2_hmac(
            'sha256', password.encode(), salt.encode(), self.ITERATIONS
        ).hex()
        return f"{salt}:{hashed}"
    
    def verify_password(self, password: str, stored_hash: str) -> bool:
        salt, expected_hash = stored_hash.split(":")
        actual_hash = hashlib.pbkdf2_hmac(
            'sha256', password.encode(), salt.encode(), self.ITERATIONS
        ).hex()
        return hmac.compare_digest(actual_hash, expected_hash)  # Timing-safe
    
    def dummy_verify(self):
        """
        Timing attack prevention:
        Agar email not found → same time lagni chahiye as wrong password
        Otherwise attacker can tell if email exists by response time
        """
        self.verify_password("dummy", "x" * 64 + ":" + "y" * 64)


# ===== JWT SERVICE =====

class JWTService:
    ACCESS_TTL = timedelta(minutes=15)
    REFRESH_TTL = timedelta(days=7)
    SECRET = "your-256-bit-secret"
    ALGORITHM = "HS256"
    
    def create_access_token(self, user_id: str, tenant_id: str,
                            roles: list, mfa_verified: bool = False) -> str:
        payload = {
            "sub": user_id,
            "tenant": tenant_id,
            "roles": roles,
            "mfa": mfa_verified,
            "type": "access",
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + self.ACCESS_TTL
        }
        return jwt.encode(payload, self.SECRET, algorithm=self.ALGORITHM)
    
    def create_refresh_token(self, user_id: str, tenant_id: str) -> str:
        payload = {
            "sub": user_id,
            "tenant": tenant_id,
            "type": "refresh",
            "jti": secrets.token_hex(16),   # JWT ID for revocation
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + self.REFRESH_TTL
        }
        return jwt.encode(payload, self.SECRET, algorithm=self.ALGORITHM)
    
    def verify_token(self, token: str) -> dict:
        try:
            return jwt.decode(token, self.SECRET, algorithms=[self.ALGORITHM])
        except jwt.ExpiredSignatureError:
            raise AuthError("Token expired")
        except jwt.InvalidTokenError:
            raise AuthError("Invalid token")


# ===== RBAC =====

class Permission(Enum):
    VIEW_BOOKING = "view_booking"
    CREATE_BOOKING = "create_booking"
    CANCEL_BOOKING = "cancel_booking"
    VIEW_PAYMENT = "view_payment"
    PROCESS_REFUND = "process_refund"
    MANAGE_STAFF = "manage_staff"
    ADMIN = "admin"

ROLE_PERMISSIONS = {
    "agent": {Permission.VIEW_BOOKING, Permission.CREATE_BOOKING},
    "supervisor": {Permission.VIEW_BOOKING, Permission.CREATE_BOOKING,
                   Permission.CANCEL_BOOKING, Permission.VIEW_PAYMENT},
    "finance": {Permission.VIEW_PAYMENT, Permission.PROCESS_REFUND},
    "admin": set(Permission),   # All permissions
}

def require_permission(permission: Permission):
    """Decorator for RBAC — view pe lagao"""
    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            user_roles = request.user.roles
            user_perms = set()
            for role in user_roles:
                user_perms.update(ROLE_PERMISSIONS.get(role, set()))
            
            if permission not in user_perms:
                raise PermissionError(f"Permission denied: {permission.value}")
            
            return func(request, *args, **kwargs)
        return wrapper
    return decorator

# Usage:
# @require_permission(Permission.PROCESS_REFUND)
# def process_refund_view(request, booking_id):
#     ...


# ===== OTP SERVICE =====

class OTPService:
    OTP_TTL = 600           # 10 minutes
    MAX_ATTEMPTS = 3
    
    def __init__(self, redis_client):
        self.redis = redis_client
    
    def generate_otp(self, user_id: str) -> str:
        otp = str(secrets.randbelow(1_000_000)).zfill(6)
        otp_hash = hashlib.sha256(otp.encode()).hexdigest()
        
        self.redis.setex(
            f"otp:{user_id}",
            self.OTP_TTL,
            f"{otp_hash}:0"   # hash:attempts
        )
        return otp   # Only returned once, sent via SMS/Email
    
    def verify_otp(self, user_id: str, otp: str) -> bool:
        data = self.redis.get(f"otp:{user_id}")
        if not data:
            return False
        
        stored_hash, attempts_str = data.decode().split(":")
        attempts = int(attempts_str)
        
        if attempts >= self.MAX_ATTEMPTS:
            self.redis.delete(f"otp:{user_id}")
            raise AuthError("OTP locked. Too many attempts.")
        
        input_hash = hashlib.sha256(otp.encode()).hexdigest()
        
        if hmac.compare_digest(input_hash, stored_hash):
            self.redis.delete(f"otp:{user_id}")   # Single use
            return True
        
        # Wrong OTP — increment attempts
        self.redis.setex(
            f"otp:{user_id}", self.OTP_TTL,
            f"{stored_hash}:{attempts + 1}"
        )
        return False
```

---

# SECTION 9: MULTI-COMPANY DATABASE DESIGN

> 💼 **Your context:** Odoo 15→17 multi-company migration — cross-company data isolation + shared PAN/contact master data.

---

## 🎯 Q9.1: Design Multi-Company Schema

### ⚡ 30-Second Pitch
> "Companies table — root entity. Contacts have company_id FK but PAN/GST stored in shared master. Row-level isolation: every table has company_id column + DB-level policies. Shared data: res_partner table without company_id for master, with company_id for company-specific view."

### Full Answer

```sql
-- ===== MULTI-COMPANY SCHEMA =====

-- Master company table
CREATE TABLE companies (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(200) NOT NULL,
    pan         VARCHAR(10) UNIQUE,     -- Company's own PAN
    gstin       VARCHAR(15),
    created_at  TIMESTAMP DEFAULT NOW()
);

-- Shared contact master (PAN-level, cross-company)
CREATE TABLE contact_master (
    id          SERIAL PRIMARY KEY,
    pan         VARCHAR(10) UNIQUE NOT NULL,  -- PAN = unique identifier
    name        VARCHAR(200),
    gstin       VARCHAR(15),
    phone       VARCHAR(20),
    email       VARCHAR(200)
);

-- Company-specific contact view
-- (same customer, different relationships per company)
CREATE TABLE company_contacts (
    id              SERIAL PRIMARY KEY,
    company_id      INT NOT NULL REFERENCES companies(id),
    master_id       INT NOT NULL REFERENCES contact_master(id),
    
    -- Company-specific fields
    credit_limit    DECIMAL(15,2) DEFAULT 0,
    is_blocked      BOOLEAN DEFAULT FALSE,
    aging_days      INT DEFAULT 0,
    ar_executive_id INT,
    
    UNIQUE(company_id, master_id)   -- One record per company per contact
);

-- Invoices — company isolated
CREATE TABLE invoices (
    id              SERIAL PRIMARY KEY,
    company_id      INT NOT NULL REFERENCES companies(id),
    contact_id      INT NOT NULL REFERENCES company_contacts(id),
    invoice_number  VARCHAR(50),
    amount          DECIMAL(15,2),
    status          VARCHAR(20),
    sap_doc_entry   VARCHAR(20) UNIQUE,  -- Idempotency: SAP push
    created_at      TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(company_id, invoice_number)   -- Unique per company
);

-- Row-level security (PostgreSQL)
ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;

CREATE POLICY company_isolation ON invoices
    USING (company_id = current_setting('app.current_company_id')::INT);

-- Shared contact search across companies
CREATE INDEX idx_contact_master_pan ON contact_master(pan);
CREATE INDEX idx_invoices_company ON invoices(company_id, status, created_at);
```

```python
# Application layer: company context set karo
class CompanyContext:
    """
    Odoo jaisa: har request mein company_id set karo
    DB queries automatically filtered
    """
    
    _local = threading.local()
    
    @classmethod
    def set_company(cls, company_id: int):
        cls._local.company_id = company_id
        # PostgreSQL session variable set karo
        db.execute(f"SET app.current_company_id = {company_id}")
    
    @classmethod
    def get_company(cls) -> int:
        return getattr(cls._local, 'company_id', None)
    
    @classmethod
    def ensure_company_access(cls, record_company_id: int):
        """Cross-company data access prevent karo"""
        if cls.get_company() != record_company_id:
            raise PermissionError("Cross-company data access denied")
```

---

# SECTION 10: CERTIFICATE GENERATION SYSTEM

> 💼 **Your context:** YES Platform — WeasyPrint + S3 presigned URLs, QR code verification, 99.9% uptime, sub-200ms.

---

## 🎯 Q10.1: Design Certificate Generation System (Sub-200ms)

### ⚡ 30-Second Pitch
> "Sub-200ms achieve kiya S3 presigned URL se — PDF generate karo, S3 mein store karo, presigned URL return karo. Same certificate dobara maange → URL already cached hai (Redis). QR code mein certificate_id + HMAC signature embed karo — verification pe server-side validate karo."

### Full Answer

```python
import hashlib
import hmac
import qrcode
import boto3
from io import BytesIO

class CertificateService:
    """
    Flow:
    1. Generate PDF (WeasyPrint) — ~100-150ms
    2. Upload to S3 — ~20-30ms
    3. Cache S3 key in Redis — ~1ms
    4. Return presigned URL — ~5ms
    Total: ~180ms (under 200ms)
    
    Cache hit: Redis se S3 key milta hai → presigned URL generate → ~10ms
    """
    
    S3_BUCKET = "certificates-bucket"
    URL_EXPIRY = 3600           # 1 hour
    CACHE_TTL = 3600
    HMAC_SECRET = "cert-verification-secret"
    
    def __init__(self, s3_client, redis_client):
        self.s3 = s3_client
        self.redis = redis_client
    
    def generate_certificate(self, cert_id: str, data: dict) -> str:
        """Returns presigned URL"""
        
        # Cache check
        cached_key = self.redis.get(f"cert_s3_key:{cert_id}")
        if cached_key:
            return self._create_presigned_url(cached_key.decode())
        
        # Generate QR code
        qr_data = self._create_qr_payload(cert_id)
        qr_image = self._generate_qr(qr_data)
        
        # Generate PDF
        pdf_content = self._generate_pdf(data, qr_image)
        
        # Upload to S3
        s3_key = f"certificates/{cert_id}.pdf"
        self.s3.put_object(
            Bucket=self.S3_BUCKET,
            Key=s3_key,
            Body=pdf_content,
            ContentType="application/pdf",
            ServerSideEncryption="AES256"
        )
        
        # Cache S3 key
        self.redis.setex(f"cert_s3_key:{cert_id}", self.CACHE_TTL, s3_key)
        
        return self._create_presigned_url(s3_key)
    
    def _create_presigned_url(self, s3_key: str) -> str:
        return self.s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': self.S3_BUCKET, 'Key': s3_key},
            ExpiresIn=self.URL_EXPIRY
        )
    
    def _create_qr_payload(self, cert_id: str) -> str:
        """
        QR = cert_id + HMAC signature
        Tamper-proof: bina secret ke valid signature banana impossible
        """
        signature = hmac.new(
            self.HMAC_SECRET.encode(),
            cert_id.encode(),
            hashlib.sha256
        ).hexdigest()[:16]   # First 16 chars enough
        
        return f"https://verify.yes.com/cert/{cert_id}?sig={signature}"
    
    def verify_certificate(self, cert_id: str, signature: str) -> bool:
        """QR scan pe verification"""
        expected_sig = hmac.new(
            self.HMAC_SECRET.encode(),
            cert_id.encode(),
            hashlib.sha256
        ).hexdigest()[:16]
        
        if not hmac.compare_digest(expected_sig, signature):
            return False  # Tampered
        
        # DB mein check: cert exists and is valid?
        cert = self._get_certificate(cert_id)
        return cert is not None and cert['status'] == 'ACTIVE'
    
    def _generate_pdf(self, data: dict, qr_image) -> bytes:
        # WeasyPrint ka use
        # from weasyprint import HTML
        # html = render_template('certificate.html', **data, qr=qr_image)
        # return HTML(string=html).write_pdf()
        return b"PDF bytes"
    
    def _generate_qr(self, data: str):
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(data)
        qr.make(fit=True)
        return qr.make_image(fill='black', back_color='white')
    
    def _get_certificate(self, cert_id: str):
        pass   # DB query
```

---

# QUICK REVISION CARDS

## Card 1: Pattern → When to Use

```
Singleton       → Token cache (SAP), DB connection pool
Adapter         → SAP API, MasterIndia GST, Exotel (different interfaces)
Strategy        → Payment gateways, Pricing (India/Kenya), Channel selection
Observer        → Booking state change → email/payment/analytics
Factory         → PaymentGateway, NotificationProvider
Abstract Factory→ TenantNotificationProviders (Email+SMS per tenant)
State Machine   → Booking lifecycle, ATM, Elevator
Command         → Move history (undo), Audit trail
Facade          → PaymentService, BookingService (hide complexity)
Decorator       → @require_permission, @cached, @retry
```

## Card 2: Concurrency Tools

```
threading.Lock      → Single resource protect karo (token store)
threading.RLock     → Reentrant (same thread multiple times acquire)
Redis SET NX EX     → Distributed lock (multiple servers/workers)
Lua script          → Atomic multi-step Redis ops (rate limiter)
task_acks_late      → Celery: task re-queue on worker crash
SELECT FOR UPDATE   → DB-level pessimistic lock (booking seat)
Optimistic lock     → version field + UPDATE WHERE version=X
```

## Card 3: Idempotency Layers

```
Layer 1: Client-side  → Idempotency key header (UUID per request)
Layer 2: In-memory    → {key: True} dict + Lock (same process)
Layer 3: Distributed  → Redis SET NX (across workers)
Layer 4: Database     → UNIQUE constraint on idempotency_key column
```

## Card 4: Common Follow-ups + One-liner Answers

```
Q: N+1 query kaise fix kiya?
A: select_related (FK), prefetch_related (reverse FK), annotate (aggregate)

Q: Cache invalidation strategy?
A: Write-through + TTL + signal-based delete on model save

Q: How to prevent double payment?
A: Idempotency key + Redis lock + DB unique constraint (3 layers)

Q: Celery worker crash pe kya hota hai?
A: task_acks_late=True → task re-queued → another worker picks up

Q: JWT vs Session?
A: JWT stateless (scales horizontally), Session needs shared store.
   JWT revocation harder — short TTL (15min) + refresh token pattern.

Q: Database connection pool size?
A: PostgreSQL max_connections / number of processes.
   Typical: 10 connections per worker, 4 workers = 40 connections.

Q: Race condition in ticket booking?
A: SELECT FOR UPDATE (pessimistic) or version field (optimistic).
   High contention → pessimistic. Low contention → optimistic.
```

## Card 5: Tumhara Resume ke Numbers (Memorize)

```
SAP HANA connector    → 4,858+ lines, 10,000+ invoices/month
Exotel rate limit     → 200 req/min
Query optimization    → 60% reduction
Annual revenue        → Rs 100 Crore+ (Rs 50 Crore invoicing)
Odoo modules          → 57+ custom modules
Cron automations      → 12+
Daily transactions    → 50,000+ (Niroskos)
YES Platform certs    → 1,000+/month, sub-200ms, 99.9% uptime
SAP success rate      → 99% across 10,000+ monthly invoices
```

---

# INTERVIEW DAY SCRIPT

## Opening (Jab "Tell me about yourself" puchein)

```
"I'm Ashish, Senior SDE with 3 years 11 months at Y Equipment Services.
I started as PHP Laravel developer building a monolithic ERP, then led
migration to Django microservices. My strongest areas are:

1. Enterprise integrations — built 4,858-line SAP HANA connector
   processing 10,000+ invoices/month

2. Async systems — Celery + RabbitMQ with 12+ cron automations,
   dead letter queues, idempotent task design

3. Multi-tenant platforms — Niroskos safari platform (Django 5.2,
   Web3/Crypto, M-Pesa, Typesense)

I'm strongest in Python backend — Django, DRF, Celery, Redis, PostgreSQL."
```

## When Asked Any LLD Question

```
Step 1 (30 sec): "Iska real-world example mujhe {project} mein mila..."
Step 2 (1 min): Core design — classes, interfaces, patterns
Step 3 (2 min): Code the main class
Step 4 (1 min): "Production mein ye challenges aate hain..." (concurrency, scale)
```

## Common Mistakes to Avoid

```
✗ Design start karne se pehle requirements mat puchna — puch lo!
  "Multi-tenant hai? How many requests/sec? Distributed?"

✗ Complexity mat dikhao unnecessarily — simple se shuru karo
  "Pehle basic design, phir optimize karein"

✗ Don't say "I don't know" — say "Mujhe yeh ek specific case mein
  solve karna pada tha, woh approach tha..."

✗ Thread safety bhool mat jao — har shared resource ke liye mention karo
```

---

*Last updated: April 2026 | Interview Kickstart SDE-2 Prep*
