# Payment System / Wallet — LLD
> **Difficulty:** Hard | **Frequency:** ★★★★★ | **Your Strength:** Real production experience

---

## Requirements

```
1. Accept payments via multiple methods — Card, UPI, Crypto, M-Pesa, Bank Transfer
2. Each payment must be idempotent — duplicate requests ignored, not double-charged
3. Payment state machine — PENDING → PROCESSING → COMPLETED → FAILED → REFUNDED
4. Wallet system — users have balance; can top-up, debit, transfer
5. Wallet ledger — every transaction recorded (double-entry accounting)
6. Partial payments — a booking can be paid in multiple installments
7. Refund flow — full or partial, method-specific (Stripe sync, Crypto manual)
8. Webhook handling — external provider fires event → update our state
9. Concurrent safety — two requests for same payment must not double-charge
10. Retry with backoff — failed payments auto-retry with exponential delay
```

---

## State Machine

```
                    ┌─────────────────────────────────────────────────┐
                    │                PAYMENT LIFECYCLE                 │
                    └─────────────────────────────────────────────────┘

    [create()]          [initiate()]        [webhook/confirm()]
  ─────────────►  PENDING  ──────────►  PROCESSING  ──────────►  COMPLETED
                    │                      │                         │
                    │ [expire()]            │ [fail()]                │ [refund()]
                    ▼                      ▼                         ▼
                 EXPIRED                FAILED                  REFUND_PENDING
                                          │                         │
                                          │ [retry()]               │ [process_refund()]
                                          ▼                         ▼
                                        PENDING                  REFUNDED
                                    (new attempt)

    VALID_TRANSITIONS = {
        PENDING:        [PROCESSING, EXPIRED, CANCELLED],
        PROCESSING:     [COMPLETED, FAILED],
        COMPLETED:      [REFUND_PENDING],
        REFUND_PENDING: [REFUNDED, REFUND_FAILED],
        FAILED:         [PENDING],          ← retry creates new PENDING attempt
        REFUNDED:       [],                 ← terminal
        EXPIRED:        [],                 ← terminal
        CANCELLED:      [],                 ← terminal
    }
```

---

## Core Design — Class Hierarchy

```
PaymentGateway (ABC)          ← Strategy Interface
    ├── StripeGateway          ← Card payments (sync webhook)
    ├── RazorpayGateway        ← India card/UPI
    ├── Web3Gateway            ← Crypto USDT/ETH (blockchain scan)
    └── MPesaGateway           ← Africa mobile money

Payment                        ← State machine + idempotency key
PaymentAttempt                 ← Each try (retry = new attempt)
Wallet                         ← Balance holder
WalletLedger                   ← Immutable log (double-entry)
PaymentAllocation              ← Payment → OrderItem mapping (partial)
IdempotencyStore               ← Prevent duplicate processing
WebhookHandler                 ← Route provider events → state updates
PaymentService (Facade)        ← Orchestrates everything
```

---

## Full Implementation

```python
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Any
import threading
import uuid
import time


# ═══════════════════════════════════════════════════════════════
# ENUMS & EXCEPTIONS
# ═══════════════════════════════════════════════════════════════

class PaymentStatus(Enum):
    PENDING        = "pending"
    PROCESSING     = "processing"
    COMPLETED      = "completed"
    FAILED         = "failed"
    REFUND_PENDING = "refund_pending"
    REFUNDED       = "refunded"
    EXPIRED        = "expired"
    CANCELLED      = "cancelled"


class PaymentMethod(Enum):
    CARD          = "card"
    UPI           = "upi"
    CRYPTO        = "crypto"
    MPESA         = "mpesa"
    BANK_TRANSFER = "bank_transfer"
    WALLET        = "wallet"       # Pay from internal wallet balance


class WalletTransactionType(Enum):
    CREDIT  = "credit"    # Money in  (top-up, refund received)
    DEBIT   = "debit"     # Money out (payment, withdrawal)


class InvalidPaymentTransitionError(Exception):
    pass

class InsufficientWalletBalanceError(Exception):
    pass

class IdempotencyConflictError(Exception):
    """Same idempotency key, different parameters — reject"""
    pass

class DuplicateRequestError(Exception):
    """Same idempotency key, same parameters — return cached result"""
    pass


# ═══════════════════════════════════════════════════════════════
# PAYMENT STATE MACHINE
# ═══════════════════════════════════════════════════════════════

class PaymentStateMachine:
    VALID_TRANSITIONS: Dict[PaymentStatus, List[PaymentStatus]] = {
        PaymentStatus.PENDING:        [PaymentStatus.PROCESSING, PaymentStatus.EXPIRED, PaymentStatus.CANCELLED],
        PaymentStatus.PROCESSING:     [PaymentStatus.COMPLETED, PaymentStatus.FAILED],
        PaymentStatus.COMPLETED:      [PaymentStatus.REFUND_PENDING],
        PaymentStatus.REFUND_PENDING: [PaymentStatus.REFUNDED, PaymentStatus.FAILED],
        PaymentStatus.FAILED:         [PaymentStatus.PENDING],
        PaymentStatus.REFUNDED:       [],
        PaymentStatus.EXPIRED:        [],
        PaymentStatus.CANCELLED:      [],
    }

    @classmethod
    def transition(cls, payment: 'Payment', new_status: PaymentStatus) -> None:
        allowed = cls.VALID_TRANSITIONS.get(payment.status, [])
        if new_status not in allowed:
            raise InvalidPaymentTransitionError(
                f"Cannot move {payment.status.value} → {new_status.value}. "
                f"Allowed: {[s.value for s in allowed]}"
            )
        old_status = payment.status
        payment.status = new_status
        payment.updated_at = datetime.now()
        print(f"[STATE] Payment {payment.payment_id}: {old_status.value} → {new_status.value}")


# ═══════════════════════════════════════════════════════════════
# STRATEGY PATTERN — Payment Gateway Interface
# ═══════════════════════════════════════════════════════════════

@dataclass
class GatewayChargeResult:
    success:            bool
    provider_txn_id:    str         # Stripe charge_id / Razorpay payment_id
    status:             str         # Provider's own status string
    gateway_response:   dict        # Raw response — store for debugging
    client_secret:      Optional[str] = None   # Stripe: for frontend confirm
    redirect_url:       Optional[str] = None   # Razorpay: payment page URL
    deposit_address:    Optional[str] = None   # Crypto: wallet address
    error_message:      Optional[str] = None


@dataclass
class GatewayRefundResult:
    success:         bool
    refund_id:       str
    amount_refunded: Decimal
    requires_manual: bool = False   # Crypto: needs ops team action
    error_message:   Optional[str] = None


class PaymentGateway(ABC):
    """
    Strategy Interface — har gateway ka alag implementation hai
    Context (PaymentService) sirf iss interface se baat karta hai
    """

    @abstractmethod
    def initiate_charge(
        self,
        amount: Decimal,
        currency: str,
        idempotency_key: str,
        metadata: dict
    ) -> GatewayChargeResult:
        """Payment initiate karo — returns provider reference"""
        pass

    @abstractmethod
    def verify_payment(self, provider_event_id: str) -> bool:
        """Webhook/polling se confirm karo — payment hua ya nahi"""
        pass

    @abstractmethod
    def initiate_refund(
        self,
        provider_txn_id: str,
        amount: Decimal,
        reason: str
    ) -> GatewayRefundResult:
        pass

    @property
    @abstractmethod
    def gateway_name(self) -> str:
        pass

    @property
    def supports_instant_refund(self) -> bool:
        """Override karo agar instant refund nahi chahiye"""
        return True


# ─── Concrete Strategy 1: Stripe (Card/International) ───

class StripeGateway(PaymentGateway):
    """
    Niroskos mein use — international card payments
    Sync webhook — stripe.com/docs/webhooks
    Idempotency: Stripe natively supports idempotency keys
    """

    @property
    def gateway_name(self): return "stripe"

    def initiate_charge(self, amount, currency, idempotency_key, metadata):
        # Stripe amount = paise (multiply by 100)
        amount_in_cents = int(amount * 100)
        print(f"[STRIPE] PaymentIntent: {amount_in_cents} {currency} | key={idempotency_key}")

        # stripe.PaymentIntent.create(
        #     amount=amount_in_cents,
        #     currency=currency.lower(),
        #     idempotency_key=idempotency_key,   ← Stripe handles duplicate natively
        #     metadata=metadata
        # )
        return GatewayChargeResult(
            success=True,
            provider_txn_id=f"pi_{uuid.uuid4().hex[:16]}",
            status="requires_payment_method",
            client_secret="pi_secret_xyz_secret_abc",
            gateway_response={"object": "payment_intent", "amount": amount_in_cents}
        )

    def verify_payment(self, provider_event_id):
        # Stripe webhook: event.type == 'payment_intent.succeeded'
        print(f"[STRIPE] Verifying event: {provider_event_id}")
        return True  # webhook ne confirm kar diya

    def initiate_refund(self, provider_txn_id, amount, reason):
        print(f"[STRIPE] Refund {amount} for {provider_txn_id}")
        # stripe.Refund.create(payment_intent=provider_txn_id, amount=int(amount*100))
        return GatewayRefundResult(
            success=True,
            refund_id=f"re_{uuid.uuid4().hex[:8]}",
            amount_refunded=amount
        )


# ─── Concrete Strategy 2: Razorpay (India Card/UPI/NetBanking) ───

class RazorpayGateway(PaymentGateway):
    """India-specific — Card, UPI, NetBanking, Wallets"""

    @property
    def gateway_name(self): return "razorpay"

    def initiate_charge(self, amount, currency, idempotency_key, metadata):
        # Razorpay amount = paise
        amount_in_paise = int(amount * 100)
        print(f"[RAZORPAY] Order create: {amount_in_paise} INR")

        # razorpay_client.order.create({
        #     'amount': amount_in_paise,
        #     'currency': 'INR',
        #     'receipt': idempotency_key,   ← Razorpay receipt = our idempotency key
        #     'notes': metadata
        # })
        order_id = f"order_{uuid.uuid4().hex[:14]}"
        return GatewayChargeResult(
            success=True,
            provider_txn_id=order_id,
            status="created",
            redirect_url=f"https://api.razorpay.com/checkout/{order_id}",
            gateway_response={"order_id": order_id, "amount": amount_in_paise}
        )

    def verify_payment(self, provider_event_id):
        # razorpay_client.utility.verify_payment_signature(...)
        print(f"[RAZORPAY] Signature verify: {provider_event_id}")
        return True

    def initiate_refund(self, provider_txn_id, amount, reason):
        print(f"[RAZORPAY] Refund {amount} for {provider_txn_id}")
        return GatewayRefundResult(
            success=True,
            refund_id=f"rfnd_{uuid.uuid4().hex[:8]}",
            amount_refunded=amount
        )


# ─── Concrete Strategy 3: Web3 / Crypto (USDT, ETH) ───

class Web3Gateway(PaymentGateway):
    """
    Niroskos mein use — USDT/ETH payments for international safari bookings
    Blockchain scan = async — Celery task every 10 seconds tak confirm nahi hota
    Refund = MANUAL — blockchain pe reverse nahi hota automatically
    """

    @property
    def gateway_name(self): return "crypto"

    @property
    def supports_instant_refund(self): return False  # Manual approval needed

    def initiate_charge(self, amount, currency, idempotency_key, metadata):
        # Generate deposit address for this specific payment
        # web3_client.generate_deposit_address(amount, currency)
        deposit_address = f"0x{uuid.uuid4().hex[:40]}"
        print(f"[CRYPTO] Deposit address: {deposit_address} | {amount} USDT")
        return GatewayChargeResult(
            success=True,
            provider_txn_id=f"crypto_pending_{idempotency_key}",
            status="awaiting_blockchain_confirmation",
            deposit_address=deposit_address,
            gateway_response={
                "address": deposit_address,
                "network": "ERC20",
                "expires_in": 3600,
                "amount_usdt": str(amount)
            }
        )

    def verify_payment(self, provider_event_id):
        # Celery task: scan blockchain for transaction to deposit_address
        # This gets called periodically until confirmed (up to 12 block confirmations)
        print(f"[CRYPTO] Blockchain scan: {provider_event_id}")
        # web3.eth.get_transaction(tx_hash) + check confirmations >= 12
        return True

    def initiate_refund(self, provider_txn_id, amount, reason):
        # Cannot auto-refund — add to manual refund queue
        print(f"[CRYPTO] Manual refund queued: {amount} USDT for {provider_txn_id}")
        return GatewayRefundResult(
            success=True,
            refund_id=f"manual_refund_{uuid.uuid4().hex[:8]}",
            amount_refunded=amount,
            requires_manual=True  # Operations team processes this
        )


# ─── Concrete Strategy 4: M-Pesa (Africa mobile money) ───

class MPesaGateway(PaymentGateway):
    """Africa (Kenya, Tanzania) — STK push to phone number"""

    @property
    def gateway_name(self): return "mpesa"

    def initiate_charge(self, amount, currency, idempotency_key, metadata):
        phone = metadata.get('phone', '')
        print(f"[MPESA] STK push → {phone}: {amount} KES")
        # mpesa_client.stk_push(phone=phone, amount=amount, reference=idempotency_key)
        return GatewayChargeResult(
            success=True,
            provider_txn_id=f"ws_CO_{uuid.uuid4().hex[:10]}",
            status="stk_push_sent",
            gateway_response={"CheckoutRequestID": f"ws_CO_{idempotency_key}"}
        )

    def verify_payment(self, provider_event_id):
        print(f"[MPESA] Confirmation callback: {provider_event_id}")
        return True

    def initiate_refund(self, provider_txn_id, amount, reason):
        print(f"[MPESA] M-Pesa reversal: {amount} KES")
        # mpesa_client.reversal(transaction_id=provider_txn_id, amount=amount)
        return GatewayRefundResult(
            success=True,
            refund_id=f"reversal_{provider_txn_id}",
            amount_refunded=amount
        )


# ─── Gateway Registry (Factory + Strategy combo) ───

class PaymentGatewayFactory:
    """
    String se gateway object banao — OCP follow karo.
    DB mein method store → factory se gateway milti hai.
    """
    _gateways: Dict[str, type] = {
        PaymentMethod.CARD.value:          StripeGateway,
        PaymentMethod.UPI.value:           RazorpayGateway,
        PaymentMethod.CRYPTO.value:        Web3Gateway,
        PaymentMethod.MPESA.value:         MPesaGateway,
        PaymentMethod.BANK_TRANSFER.value: StripeGateway,  # Stripe ACH
    }

    @classmethod
    def get(cls, method: PaymentMethod) -> PaymentGateway:
        gateway_class = cls._gateways.get(method.value)
        if not gateway_class:
            raise ValueError(f"No gateway for method: {method.value}")
        return gateway_class()

    @classmethod
    def register(cls, method: str, gateway_class: type) -> None:
        """New gateway add karo bina factory modify kiye — OCP"""
        cls._gateways[method] = gateway_class


# ═══════════════════════════════════════════════════════════════
# IDEMPOTENCY — Duplicate Request Handler
# ═══════════════════════════════════════════════════════════════

@dataclass
class IdempotencyRecord:
    key:        str
    request_hash: str          # Hash of (amount + currency + method) — same params check
    response:   Optional[dict] # Cached result to return for duplicates
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime = field(default_factory=lambda: datetime.now() + timedelta(hours=24))

    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at


class IdempotencyStore:
    """
    Prevent double-charging:
    - Same key + same params   → return cached result (duplicate request)
    - Same key + diff params   → reject (conflict error)
    - New key                  → proceed, store result

    In Niroskos: provider_event_id unique constraint on Transaction model
    In PaymentAllocation: idempotency_key unique per order_item + payment_type
    """

    def __init__(self):
        self._store: Dict[str, IdempotencyRecord] = {}
        self._lock = threading.Lock()

    def check(self, idempotency_key: str, request_hash: str) -> Optional[dict]:
        """
        Returns:
          None          → new request, proceed
          dict          → duplicate, return cached response
          raises        → conflict (same key, different params)
        """
        with self._lock:
            record = self._store.get(idempotency_key)

            if record is None or record.is_expired():
                return None  # New request

            if record.request_hash != request_hash:
                raise IdempotencyConflictError(
                    f"Idempotency key '{idempotency_key}' used with different parameters"
                )

            # Same key + same params = duplicate request → return cached
            print(f"[IDEMPOTENCY] Duplicate request — returning cached: {idempotency_key}")
            return record.response

    def store(self, idempotency_key: str, request_hash: str, response: dict) -> None:
        with self._lock:
            self._store[idempotency_key] = IdempotencyRecord(
                key=idempotency_key,
                request_hash=request_hash,
                response=response
            )


# ═══════════════════════════════════════════════════════════════
# PAYMENT MODEL — Core Domain Object
# ═══════════════════════════════════════════════════════════════

@dataclass
class PaymentAttempt:
    """
    Har retry = new attempt.
    Payment (parent) failed ho → new attempt PENDING create hota hai.
    History preserved.
    """
    attempt_id:       str = field(default_factory=lambda: str(uuid.uuid4()))
    attempt_number:   int = 1
    gateway:          str = ""
    provider_txn_id:  str = ""          # Stripe pi_xxx / Razorpay order_xxx
    status:           str = "pending"
    gateway_response: dict = field(default_factory=dict)
    error_message:    str = ""
    created_at:       datetime = field(default_factory=datetime.now)
    completed_at:     Optional[datetime] = None


class Payment:
    """
    Idempotency Key: booking_id + attempt_number (or client-provided key)
    Provider Event ID: Stripe/Razorpay webhook event_id — unique DB constraint
    """

    def __init__(
        self,
        booking_id:      str,
        amount:          Decimal,
        currency:        str,
        method:          PaymentMethod,
        idempotency_key: str,
        payer_email:     str = "",
        payer_phone:     str = "",
        metadata:        dict = None
    ):
        self.payment_id:       str           = str(uuid.uuid4())
        self.booking_id:       str           = booking_id
        self.amount:           Decimal       = amount
        self.currency:         str           = currency
        self.method:           PaymentMethod = method
        self.idempotency_key:  str           = idempotency_key
        self.payer_email:      str           = payer_email
        self.payer_phone:      str           = payer_phone
        self.metadata:         dict          = metadata or {}
        self.status:           PaymentStatus = PaymentStatus.PENDING
        self.provider_txn_id:  str           = ""     # Set after gateway call
        self.provider_event_id: str          = ""     # Set after webhook
        self.attempts:         List[PaymentAttempt] = []
        self.refund_id:        Optional[str] = None
        self.refunded_amount:  Decimal       = Decimal('0')
        self.created_at:       datetime      = datetime.now()
        self.updated_at:       datetime      = datetime.now()
        self._lock = threading.Lock()        # Concurrent webhook safety

    @property
    def current_attempt(self) -> Optional[PaymentAttempt]:
        return self.attempts[-1] if self.attempts else None

    @property
    def is_terminal(self) -> bool:
        return self.status in (
            PaymentStatus.COMPLETED,
            PaymentStatus.REFUNDED,
            PaymentStatus.EXPIRED,
            PaymentStatus.CANCELLED
        )

    def transition(self, new_status: PaymentStatus) -> None:
        PaymentStateMachine.transition(self, new_status)

    def __repr__(self):
        return f"Payment({self.payment_id[:8]}... | {self.amount} {self.currency} | {self.status.value})"


# ═══════════════════════════════════════════════════════════════
# WALLET — Internal Balance + Double-Entry Ledger
# ═══════════════════════════════════════════════════════════════

@dataclass
class WalletLedgerEntry:
    """
    IMMUTABLE — never update, never delete.
    Double-entry: har debit ke liye ek credit hota hai (opposite account mein)

    Example:
      User tops up Rs 5000 →
        credit entry: user_wallet +5000 (balance in)
        debit  entry: platform_wallet -5000 (balance out) [if tracking platform)

    In Niroskos: WalletTransaction model — append-only ledger
    """
    entry_id:      str = field(default_factory=lambda: str(uuid.uuid4()))
    wallet_id:     str = ""
    txn_type:      WalletTransactionType = WalletTransactionType.CREDIT
    amount:        Decimal = Decimal('0')
    balance_after: Decimal = Decimal('0')   # Snapshot — audit trail
    reference_id:  str = ""                 # payment_id / booking_id / refund_id
    description:   str = ""
    created_at:    datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        # Ledger entries are immutable — freeze after creation
        object.__setattr__(self, '_frozen', True)


class Wallet:
    """
    Optimistic locking for concurrent balance updates:
      version field — each update increments it
      update WHERE version = current_version — if 0 rows updated → retry

    In production (Django ORM):
      Wallet.objects.filter(id=self.id, version=self.version)
                    .update(balance=new_balance, version=self.version+1)
    """

    def __init__(self, user_id: str, currency: str = "INR"):
        self.wallet_id: str     = str(uuid.uuid4())
        self.user_id:   str     = user_id
        self.currency:  str     = currency
        self.balance:   Decimal = Decimal('0')
        self.version:   int     = 0          # Optimistic locking version
        self.ledger:    List[WalletLedgerEntry] = []
        self._lock = threading.Lock()

    def top_up(self, amount: Decimal, reference_id: str, description: str = "Top up") -> WalletLedgerEntry:
        """Credit wallet — top-up, refund received"""
        if amount <= 0:
            raise ValueError("Top-up amount must be positive")

        with self._lock:
            self.balance += amount
            self.version += 1
            entry = WalletLedgerEntry(
                wallet_id=self.wallet_id,
                txn_type=WalletTransactionType.CREDIT,
                amount=amount,
                balance_after=self.balance,
                reference_id=reference_id,
                description=description
            )
            self.ledger.append(entry)
            print(f"[WALLET] TOP-UP +{amount} | Balance: {self.balance} | Ref: {reference_id}")
            return entry

    def debit(self, amount: Decimal, reference_id: str, description: str = "Payment") -> WalletLedgerEntry:
        """Debit wallet — payment or withdrawal"""
        if amount <= 0:
            raise ValueError("Debit amount must be positive")

        with self._lock:
            if self.balance < amount:
                raise InsufficientWalletBalanceError(
                    f"Balance {self.balance} < required {amount}"
                )
            self.balance -= amount
            self.version += 1
            entry = WalletLedgerEntry(
                wallet_id=self.wallet_id,
                txn_type=WalletTransactionType.DEBIT,
                amount=amount,
                balance_after=self.balance,
                reference_id=reference_id,
                description=description
            )
            self.ledger.append(entry)
            print(f"[WALLET] DEBIT -{amount} | Balance: {self.balance} | Ref: {reference_id}")
            return entry

    def get_statement(self) -> List[WalletLedgerEntry]:
        """Immutable history — audit trail"""
        return list(self.ledger)  # Copy — protect internal list


# ═══════════════════════════════════════════════════════════════
# PAYMENT ALLOCATION — Partial Payments
# ═══════════════════════════════════════════════════════════════

@dataclass
class PaymentAllocation:
    """
    Niroskos mein: ek booking ke liye multiple payments ho sakti hain.
    Example:
      Booking total = Rs 1,50,000
      Allocation 1 = Rs 50,000 (advance — card)
      Allocation 2 = Rs 1,00,000 (balance — crypto)

    Idempotency key: booking_id + allocation_number
    Django Signal: post_save on PaymentAllocation → booking.refresh_payment_cache()
    """
    allocation_id:   str     = field(default_factory=lambda: str(uuid.uuid4()))
    booking_id:      str     = ""
    payment_id:      str     = ""
    amount:          Decimal = Decimal('0')
    allocation_type: str     = "standard"    # advance / balance / partial
    idempotency_key: str     = ""            # booking_id + seq_number — unique
    created_at:      datetime = field(default_factory=datetime.now)


class AllocationService:
    """
    After payment COMPLETED → allocate amount to booking.
    Booking cache (amount_paid, balance_due) refresh after allocation.
    """

    def __init__(self):
        self._allocations: Dict[str, List[PaymentAllocation]] = {}

    def allocate(
        self,
        booking_id: str,
        payment_id: str,
        amount: Decimal,
        idempotency_key: str
    ) -> PaymentAllocation:
        # Idempotency check — same key? Return existing
        existing = self._find_by_idempotency_key(idempotency_key)
        if existing:
            print(f"[ALLOCATION] Duplicate — returning existing: {idempotency_key}")
            return existing

        allocation = PaymentAllocation(
            booking_id=booking_id,
            payment_id=payment_id,
            amount=amount,
            idempotency_key=idempotency_key
        )
        if booking_id not in self._allocations:
            self._allocations[booking_id] = []
        self._allocations[booking_id].append(allocation)

        # Django Signal equivalent:
        # post_save.send(sender=PaymentAllocation, instance=allocation, created=True)
        # → update_booking_cache_on_allocation() fires
        print(f"[ALLOCATION] Allocated {amount} to booking {booking_id}")
        return allocation

    def get_booking_payment_summary(self, booking_id: str) -> dict:
        allocations = self._allocations.get(booking_id, [])
        total_paid = sum(a.amount for a in allocations)
        return {
            "booking_id":   booking_id,
            "amount_paid":  total_paid,
            "allocations":  len(allocations)
        }

    def _find_by_idempotency_key(self, key: str) -> Optional[PaymentAllocation]:
        for allocations in self._allocations.values():
            for alloc in allocations:
                if alloc.idempotency_key == key:
                    return alloc
        return None


# ═══════════════════════════════════════════════════════════════
# RETRY MECHANISM — Exponential Backoff
# ═══════════════════════════════════════════════════════════════

class RetryConfig:
    MAX_ATTEMPTS:    int   = 3
    BASE_DELAY:      float = 1.0   # seconds
    MAX_DELAY:       float = 60.0  # cap
    BACKOFF_FACTOR:  float = 2.0   # exponential: 1, 2, 4, 8...

    @classmethod
    def delay_for_attempt(cls, attempt_number: int) -> float:
        """
        attempt 1 → 1s
        attempt 2 → 2s
        attempt 3 → 4s (capped at MAX_DELAY)
        In Celery: self.retry(countdown=delay, max_retries=MAX_ATTEMPTS)
        """
        delay = cls.BASE_DELAY * (cls.BACKOFF_FACTOR ** (attempt_number - 1))
        return min(delay, cls.MAX_DELAY)


# ═══════════════════════════════════════════════════════════════
# WEBHOOK HANDLER — Provider Event → Payment State Update
# ═══════════════════════════════════════════════════════════════

class WebhookHandler:
    """
    Stripe/Razorpay/MPesa → webhook → PaymentService update karo.

    Security:
      Stripe   → stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
      Razorpay → razorpay_client.utility.verify_webhook_signature(body, sig, secret)
      MPesa    → IP whitelist + token validation

    Idempotency:
      provider_event_id = Stripe's evt_xxx / Razorpay's pay_xxx
      DB unique constraint → duplicate webhook = IntegrityError → return 200 (already processed)
    """

    def __init__(self, payment_service: 'PaymentService'):
        self._payment_service = payment_service
        self._processed_events: set = set()   # In prod: DB unique constraint
        self._lock = threading.Lock()

    def handle(self, provider: str, event_id: str, event_type: str, payload: dict) -> dict:
        # Idempotency check — same event_id? Already processed?
        with self._lock:
            if event_id in self._processed_events:
                print(f"[WEBHOOK] Already processed: {event_id} — returning 200")
                return {"status": "already_processed"}
            self._processed_events.add(event_id)

        print(f"[WEBHOOK] {provider} | {event_type} | {event_id}")

        # Route by event type
        payment_id = payload.get('payment_id') or payload.get('metadata', {}).get('payment_id')
        if not payment_id:
            return {"status": "ignored", "reason": "no payment_id in payload"}

        if event_type in ('payment_intent.succeeded', 'payment.captured', 'transaction_confirmed'):
            self._payment_service.confirm_payment(payment_id, event_id)
        elif event_type in ('payment_intent.payment_failed', 'payment.failed'):
            self._payment_service.fail_payment(payment_id, payload.get('error_message', ''))
        elif event_type in ('charge.refunded', 'refund.processed'):
            self._payment_service.complete_refund(payment_id, payload.get('refund_id', ''))

        return {"status": "processed", "event_id": event_id}


# ═══════════════════════════════════════════════════════════════
# PAYMENT SERVICE — Facade (Orchestrates Everything)
# ═══════════════════════════════════════════════════════════════

class PaymentService:
    """
    Facade — caller ko sirf PaymentService se baat karni hai.
    Internally: Strategy (gateway) + Idempotency + State Machine + Wallet + Allocation.

    Niroskos pattern:
      apps/payments/services/payment_service.py
      apps/payments/services/allocation_service.py
      apps/payments/signals.py (Observer — post_save on PaymentAllocation)
    """

    def __init__(self):
        self._payments:          Dict[str, Payment]  = {}
        self._wallets:           Dict[str, Wallet]   = {}
        self._idempotency_store  = IdempotencyStore()
        self._allocation_service = AllocationService()
        self._service_lock       = threading.Lock()

    # ─── Create & Initiate ───────────────────────────────────

    def create_payment(
        self,
        booking_id:      str,
        amount:          Decimal,
        currency:        str,
        method:          PaymentMethod,
        idempotency_key: str,
        payer_email:     str = "",
        payer_phone:     str = "",
        metadata:        dict = None
    ) -> Payment:
        """
        Step 1: Create payment record.
        Idempotency key = client-provided (e.g., f"booking_{booking_id}_attempt_1")
        """
        # Idempotency check — same key? Return existing payment
        request_hash = f"{amount}_{currency}_{method.value}"
        cached = self._idempotency_store.check(idempotency_key, request_hash)
        if cached:
            existing_id = cached.get('payment_id')
            if existing_id and existing_id in self._payments:
                return self._payments[existing_id]

        payment = Payment(
            booking_id=booking_id,
            amount=amount,
            currency=currency,
            method=method,
            idempotency_key=idempotency_key,
            payer_email=payer_email,
            payer_phone=payer_phone,
            metadata=metadata or {}
        )
        self._payments[payment.payment_id] = payment
        self._idempotency_store.store(
            idempotency_key,
            request_hash,
            {'payment_id': payment.payment_id}
        )
        print(f"[PAYMENT] Created: {payment.payment_id} | {amount} {currency} | {method.value}")
        return payment

    def initiate_payment(self, payment_id: str) -> GatewayChargeResult:
        """
        Step 2: Hit gateway — move PENDING → PROCESSING.
        Returns client_secret (Stripe) or redirect_url (Razorpay) or deposit_address (Crypto).
        """
        payment = self._get_payment(payment_id)

        with payment._lock:
            if payment.status == PaymentStatus.PROCESSING:
                print(f"[PAYMENT] Already processing: {payment_id}")
                return None  # Idempotent — don't re-initiate

            payment.transition(PaymentStatus.PROCESSING)

        # Strategy — gateway select karo
        gateway = PaymentGatewayFactory.get(payment.method)

        attempt = PaymentAttempt(
            attempt_number=len(payment.attempts) + 1,
            gateway=gateway.gateway_name
        )
        payment.attempts.append(attempt)

        # Gateway call
        result = gateway.initiate_charge(
            amount=payment.amount,
            currency=payment.currency,
            idempotency_key=payment.idempotency_key,
            metadata={
                'payment_id': payment.payment_id,
                'booking_id': payment.booking_id,
                **payment.metadata
            }
        )

        attempt.provider_txn_id  = result.provider_txn_id
        attempt.gateway_response = result.gateway_response
        payment.provider_txn_id  = result.provider_txn_id

        if not result.success:
            payment.transition(PaymentStatus.FAILED)
            attempt.status = "failed"
            attempt.error_message = result.error_message or "Gateway initiation failed"

        return result

    # ─── Webhook Confirmations ───────────────────────────────

    def confirm_payment(self, payment_id: str, provider_event_id: str) -> None:
        """
        Called by WebhookHandler when provider confirms success.
        provider_event_id = Stripe evt_xxx — unique constraint in DB.
        Concurrent webhooks: lock ensures only one confirms.
        """
        payment = self._get_payment(payment_id)

        with payment._lock:
            # Idempotency — same event_id already processed?
            if payment.provider_event_id == provider_event_id:
                print(f"[PAYMENT] Webhook already processed: {provider_event_id}")
                return

            if payment.status != PaymentStatus.PROCESSING:
                print(f"[PAYMENT] Cannot confirm — status={payment.status.value}")
                return

            payment.provider_event_id = provider_event_id
            payment.transition(PaymentStatus.COMPLETED)

            if payment.current_attempt:
                payment.current_attempt.status       = "completed"
                payment.current_attempt.completed_at = datetime.now()

        # Allocate payment to booking (post-confirmation)
        alloc_key = f"{payment.booking_id}_{payment.payment_id}"
        self._allocation_service.allocate(
            booking_id=payment.booking_id,
            payment_id=payment.payment_id,
            amount=payment.amount,
            idempotency_key=alloc_key
        )
        print(f"[PAYMENT] CONFIRMED: {payment_id} | Event: {provider_event_id}")

    def fail_payment(self, payment_id: str, error_message: str = "") -> None:
        payment = self._get_payment(payment_id)
        with payment._lock:
            payment.transition(PaymentStatus.FAILED)
            if payment.current_attempt:
                payment.current_attempt.status = "failed"
                payment.current_attempt.error_message = error_message

    # ─── Retry ───────────────────────────────────────────────

    def retry_payment(self, payment_id: str) -> Optional[GatewayChargeResult]:
        """
        FAILED → PENDING (state machine allows this).
        New attempt with exponential backoff delay.
        In production: Celery task with countdown=delay.
        """
        payment = self._get_payment(payment_id)

        if payment.status != PaymentStatus.FAILED:
            print(f"[RETRY] Cannot retry — status={payment.status.value}")
            return None

        attempt_number = len(payment.attempts) + 1
        if attempt_number > RetryConfig.MAX_ATTEMPTS:
            print(f"[RETRY] Max attempts ({RetryConfig.MAX_ATTEMPTS}) reached — giving up")
            payment.transition(PaymentStatus.CANCELLED)
            return None

        delay = RetryConfig.delay_for_attempt(attempt_number)
        print(f"[RETRY] Attempt {attempt_number} scheduled after {delay}s delay")
        # In Celery: self.retry(countdown=delay, max_retries=MAX_ATTEMPTS)
        # Here: simulate
        # time.sleep(delay)  # Do NOT do this in prod — use Celery

        payment.transition(PaymentStatus.PENDING)
        return self.initiate_payment(payment_id)

    # ─── Refund ──────────────────────────────────────────────

    def initiate_refund(
        self,
        payment_id: str,
        amount: Optional[Decimal] = None,  # None = full refund
        reason: str = "customer_request"
    ) -> GatewayRefundResult:
        """
        COMPLETED → REFUND_PENDING.
        Partial refund: amount < payment.amount.
        """
        payment = self._get_payment(payment_id)

        with payment._lock:
            payment.transition(PaymentStatus.REFUND_PENDING)

        refund_amount = amount if amount else payment.amount
        if refund_amount > payment.amount - payment.refunded_amount:
            raise ValueError(f"Refund {refund_amount} exceeds remaining {payment.amount - payment.refunded_amount}")

        gateway = PaymentGatewayFactory.get(payment.method)
        result  = gateway.initiate_refund(payment.provider_txn_id, refund_amount, reason)

        if result.requires_manual:
            # Crypto — add to manual refund queue, keep REFUND_PENDING
            print(f"[REFUND] Manual refund queued — ops team will process")
        else:
            payment.refunded_amount += result.amount_refunded
            print(f"[REFUND] {refund_amount} refunded via {gateway.gateway_name}")

        return result

    def complete_refund(self, payment_id: str, refund_id: str) -> None:
        """Called by webhook when refund confirmed by provider"""
        payment = self._get_payment(payment_id)
        with payment._lock:
            payment.refund_id = refund_id
            payment.transition(PaymentStatus.REFUNDED)
        print(f"[REFUND] Completed: {payment_id} | Refund: {refund_id}")

    # ─── Wallet Payment ──────────────────────────────────────

    def pay_from_wallet(
        self,
        user_id:    str,
        booking_id: str,
        amount:     Decimal,
        idempotency_key: str
    ) -> Payment:
        """
        Internal wallet balance se payment — no external gateway.
        Atomic: debit wallet + create completed payment in one step.
        """
        wallet = self._get_or_create_wallet(user_id)

        # Idempotency check
        request_hash = f"{amount}_wallet_{booking_id}"
        cached = self._idempotency_store.check(idempotency_key, request_hash)
        if cached:
            existing_id = cached.get('payment_id')
            if existing_id:
                return self._payments[existing_id]

        # Debit wallet — raises InsufficientWalletBalanceError if low
        wallet.debit(amount, reference_id=booking_id, description=f"Booking {booking_id}")

        # Create payment directly as COMPLETED (no external gateway)
        payment = Payment(
            booking_id=booking_id, amount=amount,
            currency=wallet.currency, method=PaymentMethod.WALLET,
            idempotency_key=idempotency_key
        )
        payment.status = PaymentStatus.COMPLETED

        self._payments[payment.payment_id] = payment
        self._idempotency_store.store(idempotency_key, request_hash, {'payment_id': payment.payment_id})

        # Allocate
        self._allocation_service.allocate(
            booking_id=booking_id,
            payment_id=payment.payment_id,
            amount=amount,
            idempotency_key=f"wallet_{idempotency_key}"
        )
        return payment

    # ─── Wallet Management ───────────────────────────────────

    def top_up_wallet(self, user_id: str, amount: Decimal, payment_id: str) -> Wallet:
        """After external payment COMPLETED → credit wallet"""
        wallet = self._get_or_create_wallet(user_id)
        wallet.top_up(amount, reference_id=payment_id, description="Wallet top-up")
        return wallet

    def get_wallet_balance(self, user_id: str) -> Decimal:
        wallet = self._wallets.get(user_id)
        return wallet.balance if wallet else Decimal('0')

    # ─── Helpers ─────────────────────────────────────────────

    def _get_payment(self, payment_id: str) -> Payment:
        payment = self._payments.get(payment_id)
        if not payment:
            raise ValueError(f"Payment not found: {payment_id}")
        return payment

    def _get_or_create_wallet(self, user_id: str) -> Wallet:
        if user_id not in self._wallets:
            self._wallets[user_id] = Wallet(user_id=user_id)
        return self._wallets[user_id]

    def get_payment_status(self, payment_id: str) -> dict:
        p = self._get_payment(payment_id)
        return {
            "payment_id":    p.payment_id,
            "status":        p.status.value,
            "amount":        str(p.amount),
            "currency":      p.currency,
            "method":        p.method.value,
            "attempts":      len(p.attempts),
            "provider_txn":  p.provider_txn_id,
            "refunded":      str(p.refunded_amount)
        }
```

---

## Demo: All Flows

```python
# ═══ Setup ═══
service         = PaymentService()
webhook_handler = WebhookHandler(service)


# ─── Flow 1: Card Payment (Stripe) ───────────────────────────
print("\n" + "="*55)
print("FLOW 1: Card Payment via Stripe")
print("="*55)

payment = service.create_payment(
    booking_id      = "BKG-001",
    amount          = Decimal("150000"),
    currency        = "INR",
    method          = PaymentMethod.CARD,
    idempotency_key = "booking_BKG001_attempt_1",
    payer_email     = "rahul@gmail.com"
)
result = service.initiate_payment(payment.payment_id)
print(f"Client secret: {result.client_secret}")

# Simulate Stripe webhook arriving
webhook_handler.handle(
    provider   = "stripe",
    event_id   = "evt_stripe_001",
    event_type = "payment_intent.succeeded",
    payload    = {"payment_id": payment.payment_id}
)

# Duplicate webhook — should be ignored
webhook_handler.handle(
    provider   = "stripe",
    event_id   = "evt_stripe_001",   # Same event_id
    event_type = "payment_intent.succeeded",
    payload    = {"payment_id": payment.payment_id}
)
print(service.get_payment_status(payment.payment_id))


# ─── Flow 2: Crypto Payment (Web3) ───────────────────────────
print("\n" + "="*55)
print("FLOW 2: Crypto Payment")
print("="*55)

crypto_payment = service.create_payment(
    booking_id      = "BKG-002",
    amount          = Decimal("2000"),    # USD
    currency        = "USDT",
    method          = PaymentMethod.CRYPTO,
    idempotency_key = "booking_BKG002_crypto_1"
)
crypto_result = service.initiate_payment(crypto_payment.payment_id)
print(f"Send USDT to: {crypto_result.deposit_address}")
# → Celery task blockchain_scanner.delay() runs every 10s until confirmed


# ─── Flow 3: Idempotency — Duplicate Request ─────────────────
print("\n" + "="*55)
print("FLOW 3: Duplicate Request (network retry)")
print("="*55)

# Client sends same request twice (network retry)
p1 = service.create_payment(
    booking_id="BKG-003", amount=Decimal("50000"),
    currency="INR", method=PaymentMethod.UPI,
    idempotency_key="booking_BKG003_attempt_1"  # Same key
)
p2 = service.create_payment(
    booking_id="BKG-003", amount=Decimal("50000"),
    currency="INR", method=PaymentMethod.UPI,
    idempotency_key="booking_BKG003_attempt_1"  # Same key — duplicate!
)
print(f"Same payment returned: {p1.payment_id == p2.payment_id}")  # True


# ─── Flow 4: Retry on Failure ────────────────────────────────
print("\n" + "="*55)
print("FLOW 4: Payment Failure + Retry")
print("="*55)

failed_payment = service.create_payment(
    booking_id="BKG-004", amount=Decimal("75000"),
    currency="INR", method=PaymentMethod.CARD,
    idempotency_key="booking_BKG004_attempt_1"
)
service.initiate_payment(failed_payment.payment_id)

# Simulate failure webhook
service.fail_payment(failed_payment.payment_id, "card_declined")
print(f"Status after failure: {failed_payment.status.value}")

# Retry — exponential backoff
retry_result = service.retry_payment(failed_payment.payment_id)
print(f"Status after retry: {failed_payment.status.value}")


# ─── Flow 5: Refund ──────────────────────────────────────────
print("\n" + "="*55)
print("FLOW 5: Full Refund")
print("="*55)

refund_payment = service.create_payment(
    booking_id="BKG-005", amount=Decimal("100000"),
    currency="INR", method=PaymentMethod.CARD,
    idempotency_key="booking_BKG005_attempt_1"
)
service.initiate_payment(refund_payment.payment_id)
webhook_handler.handle("stripe", "evt_refund_001", "payment_intent.succeeded",
                        {"payment_id": refund_payment.payment_id})

# Initiate refund
refund_result = service.initiate_refund(refund_payment.payment_id, reason="booking_cancelled")
# Webhook confirms refund
webhook_handler.handle("stripe", "evt_refund_done_001", "charge.refunded",
                        {"payment_id": refund_payment.payment_id,
                         "refund_id": refund_result.refund_id})
print(f"Final status: {refund_payment.status.value}")


# ─── Flow 6: Wallet ──────────────────────────────────────────
print("\n" + "="*55)
print("FLOW 6: Wallet Top-up + Pay from Wallet")
print("="*55)

# User tops up wallet with card
topup_payment = service.create_payment(
    booking_id="wallet_topup", amount=Decimal("20000"),
    currency="INR", method=PaymentMethod.CARD,
    idempotency_key="topup_user123_001"
)
service.initiate_payment(topup_payment.payment_id)
webhook_handler.handle("stripe", "evt_topup_001", "payment_intent.succeeded",
                        {"payment_id": topup_payment.payment_id})
service.top_up_wallet("user123", Decimal("20000"), topup_payment.payment_id)

print(f"Wallet balance: {service.get_wallet_balance('user123')}")

# Pay from wallet
wallet_payment = service.pay_from_wallet(
    user_id         = "user123",
    booking_id      = "BKG-006",
    amount          = Decimal("15000"),
    idempotency_key = "booking_BKG006_wallet_1"
)
print(f"Wallet payment status: {wallet_payment.status.value}")
print(f"Remaining balance: {service.get_wallet_balance('user123')}")


# ─── Flow 7: Partial Payments (Niroskos Pattern) ─────────────
print("\n" + "="*55)
print("FLOW 7: Partial Payments (advance + balance)")
print("="*55)

# Booking Rs 1,50,000 — pay in two installments
# Advance: Rs 50,000 (card)
advance = service.create_payment(
    booking_id="BKG-007", amount=Decimal("50000"),
    currency="INR", method=PaymentMethod.CARD,
    idempotency_key="booking_BKG007_advance"
)
service.initiate_payment(advance.payment_id)
webhook_handler.handle("stripe", "evt_advance_001", "payment_intent.succeeded",
                        {"payment_id": advance.payment_id})

# Balance: Rs 1,00,000 (UPI)
balance = service.create_payment(
    booking_id="BKG-007", amount=Decimal("100000"),
    currency="INR", method=PaymentMethod.UPI,
    idempotency_key="booking_BKG007_balance"
)
service.initiate_payment(balance.payment_id)
webhook_handler.handle("razorpay", "evt_balance_001", "payment_intent.succeeded",
                        {"payment_id": balance.payment_id})

summary = service._allocation_service.get_booking_payment_summary("BKG-007")
print(f"Booking BKG-007 — Total paid: {summary['amount_paid']} ({summary['allocations']} payments)")
```

---

## Concurrency: How Double-Charge is Prevented

```python
# Scenario: Two simultaneous card payment requests for same booking
# (network retry + user double-click)

import threading

service2 = PaymentService()
results  = []

def attempt_payment(idempotency_key: str):
    p = service2.create_payment(
        booking_id="CONCURRENT-001", amount=Decimal("100000"),
        currency="INR", method=PaymentMethod.CARD,
        idempotency_key=idempotency_key  # Same key = same request
    )
    results.append(p.payment_id)

# Two threads — same idempotency key
t1 = threading.Thread(target=attempt_payment, args=("bkg_concurrent_1",))
t2 = threading.Thread(target=attempt_payment, args=("bkg_concurrent_1",))
t1.start(); t2.start()
t1.join();  t2.join()

# Both get same payment_id — one charge only
print(f"Same payment: {results[0] == results[1]}")   # True
print(f"Unique payments: {len(set(results))}")        # 1

# Three-layer protection:
# 1. Idempotency key   → same key = cached response
# 2. payment._lock     → confirm() only runs once
# 3. DB unique on provider_event_id → even if both slip through, DB rejects duplicate
```

---

## Niroskos Real-World Mapping

| LLD Component | Niroskos Equivalent |
|---|---|
| `PaymentGateway(ABC)` | `PaymentMethod` abstract class in `apps/payments/` |
| `StripeGateway` | `StripePaymentMethod` — Card (sync webhook) |
| `Web3Gateway` | `CryptoPaymentMethod` — USDT/ETH via Web3.py |
| `MPesaGateway` | `MPesaPaymentMethod` — Africa mobile money |
| `Payment` model | `Transaction` model — status field + provider_event_id (unique) |
| `PaymentAttempt` | Each Celery retry = new attempt tracked in Transaction |
| `Wallet` | `WalletBalance` model per subsidiary |
| `WalletLedger` | `WalletTransaction` model — append-only |
| `PaymentAllocation` | `PaymentAllocation` model — booking_id + order_item_id + amount |
| `AllocationService` | `apps/payments/services/allocation_service.py` |
| `IdempotencyStore` | `provider_event_id` unique constraint on Transaction |
| `WebhookHandler` | `apps/payments/views/webhook_views.py` |
| `RetryConfig` | Celery task with `self.retry(countdown=backoff)` |
| `confirm_payment()` | `PaymentAllocation post_save signal → booking.refresh_payment_cache()` |
| `pay_from_wallet()` | `WalletPaymentMethod` — debit balance, skip gateway |

---

## Interview Q&A

**Q: "How do you prevent double-charging?"**
> "Three layers of protection. First, every payment request carries a client-generated idempotency key — if the same key comes twice, we return the cached result without hitting the gateway. This handles network retries. Second, when the webhook confirmation arrives, there's a lock on the Payment object so two simultaneous webhooks can't both execute confirm_payment(). Third, provider_event_id has a unique database constraint — even if both slip through the lock somehow, the DB rejects the second insert. In Niroskos, this was a unique constraint on Transaction.provider_event_id, and we returned HTTP 200 (not 4xx) for duplicate webhook events so the provider doesn't keep retrying."

**Q: "What happens if the payment service crashes between initiate and webhook?"**
> "The payment is in PROCESSING state in our DB. When the service restarts, a background job (Celery beat task) scans for payments stuck in PROCESSING for more than 15 minutes. For Stripe, it queries the Stripe API using the stored provider_txn_id to get the current status and reconciles. For Crypto, the blockchain scanner task resumes from where it left off — it uses the deposit_address to check for incoming transactions. This is the recovery mechanism — it's why we store the provider_txn_id at initiation time, not just at confirmation."

**Q: "How does the retry mechanism work?"**
> "Retry is a new PaymentAttempt, not modifying the failed one — this preserves the audit trail. The state machine allows FAILED → PENDING. We use exponential backoff: attempt 1 after 1 second, attempt 2 after 2 seconds, attempt 3 after 4 seconds — capped at 60 seconds. In Celery: self.retry(countdown=delay, max_retries=3). After 3 failed attempts, the payment moves to CANCELLED and we notify the customer with an email to try a different payment method."

**Q: "Explain the Wallet ledger design."**
> "Double-entry accounting principle — every transaction has two sides. When a user tops up Rs 5000: we credit their wallet ledger (+5000) and debit the platform's income ledger (+5000 revenue). Ledger entries are immutable — we never update or delete them, only append. This gives us a perfect audit trail. Balance is derived by summing the ledger entries. In production, we cache the current balance in a Wallet.balance field (with optimistic locking via a version field) and only re-derive from ledger during reconciliation runs. The version field prevents lost updates in concurrent balance changes — we do WHERE id=X AND version=current, increment version in the UPDATE."

**Q: "How do you handle partial payments?"**
> "A Booking has a total_amount field. Payments are separate from allocations — a payment can exist without being allocated, and an allocation links a specific payment to a specific booking line item. After each PaymentAllocation save, a Django Signal fires and calls booking.refresh_payment_cache() which sums all PaymentAllocations for that booking to update the cached amount_paid and balance_due fields. This avoids N+1 queries on the booking list view — we show amount_paid from the cache, not by joining payments every time."

**Q: "Strategy pattern — why not just if-elif for gateways?"**
> "With if-elif, every new payment method requires modifying PaymentService. We support 4 methods — adding a 5th means touching existing production code. With Strategy, adding M-Pesa was one new class that implements PaymentGateway — zero changes to PaymentService. It also means each gateway is independently testable with a mock. For the registry, I use a dict mapping string keys to gateway classes — this lets database configuration drive which gateway to use without code changes. The factory creates the gateway instance from the method string."

---

## Patterns Used

| Pattern | Where | Why |
|---|---|---|
| **Strategy** | PaymentGateway ABC + 4 concrete gateways | Swap gateway without touching PaymentService |
| **State Machine** | Payment status transitions | Prevent invalid states (REFUNDED → PROCESSING) |
| **Facade** | PaymentService | Single entry point — hides complexity |
| **Factory** | PaymentGatewayFactory | String → gateway object, OCP |
| **Observer** | Django post_save signal on PaymentAllocation | Cache refresh, decoupled from payment flow |
| **Template Method** | RetryConfig.delay_for_attempt() | Algorithm skeleton — concrete step varies |
| **Singleton** | IdempotencyStore (process-level) | Single source of truth for duplicate detection |

---

*Last Updated: April 2026 | SDE-2 Interview Prep — Niroskos Payment System*
