"""
Payment Gateway (Stripe PaymentIntents) + Double-Entry Ledger — Production Patterns
=====================================================================================

Covers every concern a senior engineer must own around money movement:

  1. Money correctness — integer minor units, never float, Decimal only at the boundary.
  2. Stripe PaymentIntents flow — create intent -> client_secret -> Stripe.js ->
     webhook as the authoritative result (NOT the synchronous HTTP response).
  3. Idempotency — two layers: Stripe-side idempotency_key + DB-side UNIQUE constraint
     on external_ref to block duplicate ledger postings.
  4. Webhook handling — raw-body signature verification, event-id deduplication,
     fast 200 + background processing.
  5. Double-entry ledger — append-only, balanced debit/credit pairs in one DB
     transaction; reversal entries for refunds; materialized balance cache.
  6. Payment state machine — PaymentIntent FSM mirrored to Order status.
  7. Reconciliation invariant — SQL check to catch any unbalanced transaction.

External infra (Postgres, Stripe live keys) is NOT required to import or syntax-check
this module.  Replace placeholder values (sk_test_xxx, whsec_xxx) with real ones for
a live environment.

Usage:
    # Start the server (requires stripe, fastapi, sqlalchemy, uvicorn):
    # pip install stripe fastapi uvicorn sqlalchemy structlog
    uvicorn 38_payment_gateway_stripe_ledger:app --reload
"""

# ==========================================================================
# IMPORTS & GLOBAL CONFIG
# ==========================================================================

# pip install stripe fastapi uvicorn sqlalchemy structlog
import os
import uuid
import logging
from contextlib import asynccontextmanager
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Optional

import stripe
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    String,
    create_engine,
    event as sa_event,
    func,
    text,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

import structlog

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Stripe credentials — load from environment in production; never hard-code.
# ---------------------------------------------------------------------------
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "sk_test_xxx")
STRIPE_WEBHOOK_SECRET: str = os.environ.get("STRIPE_WEBHOOK_SECRET", "whsec_xxx")


# ==========================================================================
# 1. MONEY CORRECTNESS — integer minor units, Decimal only at the boundary
# ==========================================================================

# Most currencies use 2 decimal places (cents/paise).
# Zero-decimal currencies (JPY, KRW) use exponent 0.
# A few currencies use 3 (BHD, KWD).
CURRENCY_MINOR_EXPONENT: dict[str, int] = {
    "usd": 2,
    "eur": 2,
    "gbp": 2,
    "inr": 2,
    "aud": 2,
    "cad": 2,
    "jpy": 0,   # yen — no sub-unit
    "krw": 0,   # Korean Won
    "bhd": 3,   # Bahraini Dinar
    "kwd": 3,   # Kuwaiti Dinar
}


def to_minor_units(amount: Decimal, currency: str) -> int:
    """
    Convert a user-facing Decimal amount to integer minor units.

    ``Decimal`` is used ONLY at this boundary to avoid IEEE-754 float drift.
    The result is a plain int — safe for DB storage (BIGINT) and Stripe API calls.

    Examples:
        to_minor_units(Decimal("499.00"), "inr")  -> 49900   (paise)
        to_minor_units(Decimal("10.50"),  "usd")  -> 1050    (cents)
        to_minor_units(Decimal("1500"),   "jpy")  -> 1500    (yen, no sub-unit)
    """
    ccy = currency.lower()
    if ccy not in CURRENCY_MINOR_EXPONENT:
        raise ValueError(f"Unsupported currency: {currency!r}")
    exp = CURRENCY_MINOR_EXPONENT[ccy]
    quantum = Decimal(10) ** -exp                           # e.g. Decimal("0.01")
    rounded = amount.quantize(quantum, rounding=ROUND_HALF_UP)
    return int(rounded * (Decimal(10) ** exp))              # exact int — no float


def to_display(minor: int, currency: str) -> Decimal:
    """
    Convert integer minor units back to a Decimal for display (templates, invoices).

    This is the ONLY other boundary where Decimal is appropriate.  Never use the
    result of this function for arithmetic — work in minor units internally.

    Examples:
        to_display(49900, "inr")  -> Decimal("499.00")
        to_display(1050,  "usd")  -> Decimal("10.50")
        to_display(1500,  "jpy")  -> Decimal("1500")
    """
    ccy = currency.lower()
    exp = CURRENCY_MINOR_EXPONENT[ccy]
    value = Decimal(minor) / (Decimal(10) ** exp)
    return value.quantize(Decimal(10) ** -exp)


# Quick sanity assertions (run at import time, zero cost in production).
assert to_minor_units(Decimal("499.00"), "inr") == 49900
assert to_display(49900, "inr") == Decimal("499.00")
assert to_minor_units(Decimal("1500"), "jpy") == 1500
assert to_display(1500, "jpy") == Decimal("1500")
assert to_minor_units(Decimal("10.50"), "usd") == 1050


# ==========================================================================
# 2. SQLALCHEMY MODELS — double-entry ledger schema
# ==========================================================================

Base = declarative_base()

# In production: postgresql+psycopg2://user:pass@host/db
# Here we default to an in-memory SQLite so py_compile + demo work without Postgres.
DATABASE_URL: str = os.environ.get(
    "DATABASE_URL", "sqlite:///:memory:"
)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    poolclass=StaticPool if DATABASE_URL.startswith("sqlite") else None,
    echo=False,
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class AccountType(str, Enum):
    """Standard accounting account types for the chart of accounts."""
    asset = "asset"          # cash, receivables, wallet balances
    liability = "liability"  # money owed to customers (outstanding payouts)
    revenue = "revenue"      # income from sales
    expense = "expense"      # refunds, fees, chargebacks


class Account(Base):
    """
    Represents a financial account (wallet, revenue bucket, clearing account).

    ``balance_minor`` is a materialized cache updated in the same DB transaction
    as ledger entries.  Source of truth is always the SUM of LedgerEntry rows.
    """
    __tablename__ = "accounts"

    id = Column(String, primary_key=True)               # e.g. "user:42:wallet"
    type = Column(String, nullable=False)               # AccountType value
    currency = Column(String(3), nullable=False)
    # Materialized cache for fast reads; must equal SUM(amount_minor) for this account.
    balance_minor = Column(BigInteger, nullable=False, default=0)


class LedgerEntry(Base):
    """
    Immutable, append-only ledger row.

    INVARIANT: For every ``transaction_id``, SUM(amount_minor) == 0.
    Positive amount_minor = debit (money flowing INTO an account from this perspective).
    Negative amount_minor = credit (money flowing OUT).

    ``external_ref`` carries the Stripe intent/refund ID and has a UNIQUE constraint —
    this is the DB-level idempotency guard against duplicate webhook delivery.
    """
    __tablename__ = "ledger_entries"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    transaction_id = Column(String, nullable=False, index=True)  # groups the two legs
    account_id = Column(String, ForeignKey("accounts.id"), nullable=False, index=True)
    amount_minor = Column(BigInteger, nullable=False)            # signed; + debit / - credit
    currency = Column(String(3), nullable=False)
    external_ref = Column(String, unique=True, nullable=True)    # Stripe event ref; UNIQUE
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        CheckConstraint("amount_minor <> 0", name="ck_ledger_nonzero_amount"),
    )


class ProcessedEvent(Base):
    """
    Records every Stripe event ID that has been processed.

    Unique constraint on ``event_id`` provides atomic deduplication: the first
    handler wins; duplicates raise IntegrityError and return early.
    """
    __tablename__ = "processed_events"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    event_id = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())


class Order(Base):
    """
    Application order row — mirrors PaymentIntent state transitions from webhooks.
    """
    __tablename__ = "orders"

    id = Column(String, primary_key=True)                      # e.g. "order-uuid"
    user_id = Column(String, nullable=False)
    amount_minor = Column(BigInteger, nullable=False)
    currency = Column(String(3), nullable=False)
    # PaymentIntent states: requires_payment_method | requires_confirmation |
    # processing | requires_action | succeeded | canceled
    payment_status = Column(String, nullable=False, default="pending")
    stripe_intent_id = Column(String, nullable=True, unique=True)
    failure_reason = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


# ==========================================================================
# 3. DATABASE HELPERS
# ==========================================================================

def get_db() -> Session:
    """FastAPI dependency: yields a DB session and closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def seed_accounts(db: Session) -> None:
    """
    Create the minimum set of accounts needed for the payment flow.
    In production these rows are seeded via a migration, not at startup.
    """
    defaults = [
        Account(id="revenue:sales",    type=AccountType.revenue,   currency="inr", balance_minor=0),
        Account(id="user:42:wallet",   type=AccountType.asset,     currency="inr", balance_minor=0),
        Account(id="gateway:stripe",   type=AccountType.asset,     currency="inr", balance_minor=0),
    ]
    for acct in defaults:
        existing = db.get(Account, acct.id)
        if not existing:
            db.add(acct)
    db.commit()


# ==========================================================================
# 4. FASTAPI LIFESPAN — startup/teardown (replaces deprecated on_event)
# ==========================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create tables and seed accounts on startup."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_accounts(db)
    finally:
        db.close()
    log.info("startup_complete", database=DATABASE_URL)
    yield
    log.info("shutdown")


app = FastAPI(
    title="Payment Gateway + Double-Entry Ledger",
    description="Stripe PaymentIntents + immutable ledger — production patterns",
    version="1.0.0",
    lifespan=lifespan,
)


# ==========================================================================
# 5. PYDANTIC REQUEST / RESPONSE MODELS
# ==========================================================================

class CheckoutRequest(BaseModel):
    """
    Body for POST /payments/create-intent.

    ``amount_minor`` must already be in integer minor units (paise, cents, etc.).
    The client is responsible for calling ``to_minor_units`` before sending.
    """
    order_id: str
    amount_minor: int        # integer minor units — never float
    currency: str = "inr"

    @field_validator("amount_minor")
    @classmethod
    def positive_amount(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("amount_minor must be a positive integer")
        return v

    @field_validator("currency")
    @classmethod
    def known_currency(cls, v: str) -> str:
        if v.lower() not in CURRENCY_MINOR_EXPONENT:
            raise ValueError(f"Unsupported currency: {v!r}")
        return v.lower()


class IntentResponse(BaseModel):
    client_secret: str
    intent_id: str


# ==========================================================================
# 6. STRIPE PAYMENTINTENT CREATION
# ==========================================================================

@app.post("/payments/create-intent", response_model=IntentResponse)
async def create_payment_intent(req: CheckoutRequest) -> IntentResponse:
    """
    Step 1 of the PaymentIntents flow.

    Creates a Stripe PaymentIntent and returns the ``client_secret`` to the browser.
    The browser's Stripe.js uses this secret to confirm the payment DIRECTLY with
    Stripe — card PAN never reaches this server (PCI SAQ-A scope).

    Idempotency key is deterministic and tied to the business operation so that
    any network-level retry from the client never creates a duplicate charge.

    DO NOT mark the order as paid here.  The authoritative result comes via webhook.
    """
    try:
        intent = stripe.PaymentIntent.create(
            amount=req.amount_minor,          # must be int in smallest unit
            currency=req.currency,
            metadata={"order_id": req.order_id},
            automatic_payment_methods={"enabled": True},
            # Deterministic key: same order + same operation = same PaymentIntent
            # (Stripe caches the result for 24 h — no duplicate charge on retry).
            idempotency_key=f"order:{req.order_id}:create-intent",
        )
    except stripe.error.StripeError as exc:
        log.error("stripe_create_intent_failed", order_id=req.order_id, error=str(exc))
        raise HTTPException(status_code=502, detail="Payment provider error")

    log.info(
        "payment_intent_created",
        order_id=req.order_id,
        intent_id=intent.id,
        amount_minor=req.amount_minor,
        currency=req.currency,
    )
    # Return ONLY client_secret (and intent id for reference).
    # NEVER return the secret API key or any server-side secret here.
    return IntentResponse(client_secret=intent.client_secret, intent_id=intent.id)


# ==========================================================================
# 7. STRIPE WEBHOOK HANDLER
# ==========================================================================

@app.post("/webhooks/stripe", status_code=200)
async def stripe_webhook(
    request: Request,
    background: BackgroundTasks,
    stripe_signature: Optional[str] = Header(None, alias="Stripe-Signature"),
) -> dict:
    """
    Authoritative payment result handler.

    Rules (non-negotiable):
    1. Raw bytes — ``await request.body()``.  Re-serialising after JSON parse
       changes whitespace and breaks the HMAC signature.
    2. ``stripe.Webhook.construct_event`` verifies the signature AND parses JSON
       atomically.  Do not write your own HMAC check.
    3. Deduplicate by ``event.id`` (Stripe delivers at-least-once).
    4. Return 200 immediately; hand off heavy work to BackgroundTasks.
       Stripe's timeout is short — slow handlers cause needless retries.
    """
    payload: bytes = await request.body()   # RAW bytes — do NOT parse to JSON first

    # --- Signature verification ---
    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=stripe_signature or "",
            secret=STRIPE_WEBHOOK_SECRET,
        )
    except ValueError:
        # Malformed payload / not valid JSON.
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        # Wrong signing secret or tampered body.
        raise HTTPException(status_code=400, detail="Invalid signature")

    # --- Atomic deduplication by event.id ---
    db = SessionLocal()
    try:
        already_seen = _mark_event_seen(db, event["id"])
    finally:
        db.close()

    if already_seen:
        log.info("webhook_duplicate_skipped", event_id=event["id"], event_type=event["type"])
        return {"status": "duplicate"}

    # --- Dispatch to background (fast 200 to Stripe) ---
    background.add_task(_handle_stripe_event, event)
    log.info("webhook_received", event_id=event["id"], event_type=event["type"])
    return {"status": "received"}


def _mark_event_seen(db: Session, event_id: str) -> bool:
    """
    Insert a ProcessedEvent row.  Returns True if already seen (duplicate),
    False if this is the first time we are processing this event_id.

    The UNIQUE constraint on ``event_id`` makes this operation atomic —
    two concurrent webhook deliveries cannot both succeed.
    """
    try:
        db.add(ProcessedEvent(event_id=event_id))
        db.commit()
        return False    # first delivery
    except IntegrityError:
        db.rollback()
        return True     # duplicate


def _handle_stripe_event(event: dict) -> None:
    """
    Background task: inspect the event type and update the ledger / order state.

    The GOLDEN RULE: write a ledger entry ONLY on ``payment_intent.succeeded``.
    Intermediate states (processing, requires_action) and failed states do NOT
    produce ledger entries.
    """
    etype: str = event["type"]
    obj: dict = event["data"]["object"]

    db = SessionLocal()
    try:
        if etype == "payment_intent.succeeded":
            # Paisa captured — this is the ONLY moment we consider the payment real.
            order_id: str = obj["metadata"]["order_id"]
            _record_successful_payment(
                db,
                order_id=order_id,
                amount_minor=obj["amount_received"],   # int minor units from Stripe
                currency=obj["currency"],
                intent_id=obj["id"],
            )

        elif etype == "payment_intent.payment_failed":
            order_id = obj["metadata"].get("order_id")
            err_msg = (obj.get("last_payment_error") or {}).get("message")
            _mark_order_failed(db, order_id=order_id, reason=err_msg)

        elif etype == "charge.refunded":
            _record_refund(
                db,
                intent_id=obj["payment_intent"],
                refunded_minor=obj["amount_refunded"],  # int minor units
                currency=obj["currency"],
            )

        else:
            # Unhandled event types: log and ignore.
            # We already returned 200 to Stripe — no retry will be triggered.
            log.debug("webhook_event_ignored", event_type=etype)

    except Exception as exc:
        log.error("webhook_handler_error", event_type=etype, error=str(exc))
        db.rollback()
    finally:
        db.close()


# ==========================================================================
# 8. DOUBLE-ENTRY LEDGER OPERATIONS
# ==========================================================================

def post_transfer(
    db: Session,
    *,
    from_account: str,
    to_account: str,
    amount_minor: int,              # must be positive int
    currency: str,
    external_ref: Optional[str] = None,   # Stripe intent/refund id for idempotency
) -> str:
    """
    Post a balanced double-entry transfer between two accounts.

    Debit (positive amount_minor) on ``from_account`` and credit (negative) on
    ``to_account`` are written in a SINGLE DB transaction — all-or-nothing.
    A partial write would leave the ledger unbalanced, which is corruption.

    ``external_ref`` on the debit leg has a UNIQUE constraint.  If the same Stripe
    intent is delivered twice, the second insert raises IntegrityError and the
    caller can catch it as a duplicate (DB-level idempotency).

    Returns the new transaction_id (UUID string).
    """
    if amount_minor <= 0:
        raise ValueError("amount_minor must be a positive integer")

    txn_id = str(uuid.uuid4())

    # Leg 1: DEBIT source account (+amount_minor).  Leg 2: CREDIT destination (-amount_minor).
    # Sum of the two legs = 0 → balanced.  This is the double-entry invariant.
    db.add_all([
        LedgerEntry(
            transaction_id=txn_id,
            account_id=from_account,
            amount_minor=+amount_minor,     # debit (positive)
            currency=currency,
            external_ref=external_ref,      # UNIQUE — idempotency guard on this leg
        ),
        LedgerEntry(
            transaction_id=txn_id,
            account_id=to_account,
            amount_minor=-amount_minor,     # credit (negative)
            currency=currency,
            external_ref=None,              # only one leg carries the external ref
        ),
    ])

    # Update materialized balance cache under row-level locks.
    # ``with_for_update()`` prevents a concurrent transfer from racing on the
    # same account rows between our read and our write.
    src = db.query(Account).filter_by(id=from_account).with_for_update().one()
    dst = db.query(Account).filter_by(id=to_account).with_for_update().one()
    src.balance_minor += amount_minor
    dst.balance_minor -= amount_minor

    db.commit()   # atomic: both ledger rows + both balance updates, or nothing
    log.info(
        "ledger_transfer_posted",
        txn_id=txn_id,
        from_account=from_account,
        to_account=to_account,
        amount_minor=amount_minor,
        currency=currency,
        external_ref=external_ref,
    )
    return txn_id


def _record_successful_payment(
    db: Session,
    *,
    order_id: str,
    amount_minor: int,
    currency: str,
    intent_id: str,
) -> None:
    """
    Called ONLY from the ``payment_intent.succeeded`` webhook branch.

    Writes a balanced ledger transfer from the Stripe gateway clearing account to
    revenue, then marks the order as succeeded.

    ``external_ref=intent_id`` on the ledger row means a second webhook delivery
    for the same intent will hit the UNIQUE constraint and raise IntegrityError —
    zero risk of double-posting income.
    """
    try:
        post_transfer(
            db,
            from_account="gateway:stripe",  # money arrived from Stripe's side
            to_account="revenue:sales",     # recognised as earned revenue
            amount_minor=amount_minor,
            currency=currency,
            external_ref=f"pi:{intent_id}", # "pi:" prefix prevents collision with refund refs
        )
    except IntegrityError:
        db.rollback()
        log.warning("payment_already_posted", intent_id=intent_id)
        return

    # Mirror the PaymentIntent state into our Order row.
    order = db.query(Order).filter_by(id=order_id).first()
    if order:
        order.payment_status = "succeeded"
        order.stripe_intent_id = intent_id
        db.commit()

    log.info("payment_succeeded_recorded", order_id=order_id, intent_id=intent_id)


def _mark_order_failed(
    db: Session,
    *,
    order_id: Optional[str],
    reason: Optional[str],
) -> None:
    """
    Called from the ``payment_intent.payment_failed`` webhook branch.

    Updates order status only — NO ledger entry is written because no money moved.
    """
    if not order_id:
        return
    order = db.query(Order).filter_by(id=order_id).first()
    if order:
        order.payment_status = "canceled"
        order.failure_reason = reason
        db.commit()
    log.info("payment_failed_recorded", order_id=order_id, reason=reason)


def record_refund(
    db: Session,
    *,
    intent_id: str,
    refunded_minor: int,
    currency: str,
) -> None:
    """
    Post a REVERSAL entry for a refund.

    The original payment ledger row is NEVER updated or deleted — that would destroy
    the audit trail.  Instead, a new balanced pair flows in the opposite direction:
    revenue -> customer wallet (or gateway clearing), making the net effect zero.

    ``external_ref="refund:{intent_id}"`` is distinct from ``"pi:{intent_id}"``
    so that both the original payment and its refund can coexist in the ledger with
    unique external_ref values.
    """
    try:
        post_transfer(
            db,
            from_account="revenue:sales",   # money leaves the revenue bucket
            to_account="user:42:wallet",    # returned to the customer wallet
            amount_minor=refunded_minor,
            currency=currency,
            external_ref=f"refund:{intent_id}",  # UNIQUE: blocks double-refund posting
        )
    except IntegrityError:
        db.rollback()
        log.warning("refund_already_posted", intent_id=intent_id)
        return

    log.info("refund_recorded", intent_id=intent_id, refunded_minor=refunded_minor)


# Expose record_refund via private alias for internal webhook dispatcher.
_record_refund = record_refund


# ==========================================================================
# 9. PAYMENT STATE MACHINE — ORDER STATUS TRANSITIONS
# ==========================================================================

# PaymentIntent states (from Stripe docs) and their meaning for our Order:
#
# requires_payment_method  ->  Customer has not attached a card yet.
# requires_confirmation    ->  Payment method attached; awaiting confirmPayment().
# processing               ->  Stripe is authorising; WAIT — no ledger action.
# requires_action          ->  3D-Secure / SCA challenge required from the customer.
# succeeded                ->  Captured.  POST ledger entry.  Fulfil order.
# canceled                 ->  Intent expired or authentication failed.  No ledger.
# (charge.refunded)        ->  Post reversal entry; original entry is NOT touched.

PAYMENTINTENT_TERMINAL_STATES = frozenset({"succeeded", "canceled"})
PAYMENTINTENT_INTERMEDIATE_STATES = frozenset({"processing", "requires_action"})

# Mapping from Stripe event type to the order status we write.
STRIPE_EVENT_TO_ORDER_STATUS: dict[str, str] = {
    "payment_intent.succeeded":       "succeeded",
    "payment_intent.payment_failed":  "canceled",
    "payment_intent.canceled":        "canceled",
    "payment_intent.processing":      "processing",
    "payment_intent.requires_action": "requires_action",
}


# ==========================================================================
# 10. RECONCILIATION — invariant checks
# ==========================================================================

def check_ledger_balance(db: Session) -> list[dict]:
    """
    Detect any transaction where the sum of legs is not zero.

    A non-empty result means there is a bug: an entry was written without its
    counterpart, or one leg was deleted.  In production, run this as a daily
    scheduled job and alert on any rows returned.

    SQL equivalent:
        SELECT transaction_id, SUM(amount_minor) AS imbalance
        FROM ledger_entries
        GROUP BY transaction_id
        HAVING SUM(amount_minor) <> 0;
    """
    rows = db.execute(
        text(
            "SELECT transaction_id, SUM(amount_minor) AS imbalance "
            "FROM ledger_entries "
            "GROUP BY transaction_id "
            "HAVING SUM(amount_minor) <> 0"
        )
    ).fetchall()
    if rows:
        log.error("ledger_imbalance_detected", count=len(rows), rows=[dict(r._mapping) for r in rows])
    return [dict(r._mapping) for r in rows]


def account_balance_from_entries(db: Session, account_id: str, currency: str) -> int:
    """
    Recompute account balance from raw ledger entries (the authoritative source).

    Use this to verify the ``Account.balance_minor`` materialized cache is correct.
    """
    result = db.execute(
        text(
            "SELECT COALESCE(SUM(amount_minor), 0) AS balance "
            "FROM ledger_entries "
            "WHERE account_id = :account_id AND currency = :currency"
        ),
        {"account_id": account_id, "currency": currency},
    ).scalar()
    return int(result)


# ==========================================================================
# 11. DEMO — runs without Stripe live keys or Postgres
# ==========================================================================

def _run_local_demo() -> None:
    """
    Standalone demo that exercises all ledger operations against in-memory SQLite.

    Shows:
      - to_minor_units / to_display boundary conversions
      - post_transfer balanced pair
      - Duplicate external_ref protection (idempotency guard)
      - record_refund reversal entry
      - Reconciliation invariant check
    """
    print("\n" + "=" * 64)
    print("  Payment Gateway + Double-Entry Ledger — Local Demo")
    print("=" * 64 + "\n")

    # ------------------------------------------------------------------
    # 1. Money conversion at the boundary
    # ------------------------------------------------------------------
    print("--- 1. Money boundary conversion ---")
    amount_str = "499.00"
    currency = "inr"
    minor = to_minor_units(Decimal(amount_str), currency)
    back = to_display(minor, currency)
    print(f"  User input : INR {amount_str}")
    print(f"  Minor units: {minor} paise  (sent to Stripe)")
    print(f"  Display    : INR {back}     (rendered on invoice)\n")

    usd_minor = to_minor_units(Decimal("10.50"), "usd")
    print(f"  USD 10.50  -> {usd_minor} cents")
    jpy_minor = to_minor_units(Decimal("1500"), "jpy")
    print(f"  JPY 1500   -> {jpy_minor} yen (zero-decimal currency)\n")

    # ------------------------------------------------------------------
    # 2. Create tables and seed accounts (in-memory SQLite)
    # ------------------------------------------------------------------
    print("--- 2. Database setup ---")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    seed_accounts(db)
    print("  Accounts seeded: gateway:stripe, revenue:sales, user:42:wallet\n")

    # ------------------------------------------------------------------
    # 3. Simulate a successful payment webhook
    # ------------------------------------------------------------------
    print("--- 3. Successful payment ledger posting ---")
    intent_id = "pi_demo_001"
    try:
        post_transfer(
            db,
            from_account="gateway:stripe",
            to_account="revenue:sales",
            amount_minor=minor,
            currency=currency,
            external_ref=f"pi:{intent_id}",
        )
        print(f"  Transfer posted: {minor} paise from gateway -> revenue")
    except IntegrityError:
        db.rollback()
        print("  [idempotency] Transfer already posted — skipped\n")

    # ------------------------------------------------------------------
    # 4. Idempotency guard — second delivery of the same intent
    # ------------------------------------------------------------------
    print("\n--- 4. Duplicate webhook delivery (idempotency) ---")
    try:
        post_transfer(
            db,
            from_account="gateway:stripe",
            to_account="revenue:sales",
            amount_minor=minor,
            currency=currency,
            external_ref=f"pi:{intent_id}",   # same ref -> UNIQUE violation
        )
        print("  ERROR: duplicate was not blocked!")
    except IntegrityError:
        db.rollback()
        print("  Duplicate blocked by UNIQUE constraint on external_ref — correct.\n")

    # ------------------------------------------------------------------
    # 5. Refund — reversal entry, original untouched
    # ------------------------------------------------------------------
    print("--- 5. Refund reversal entry ---")
    refund_amount = to_minor_units(Decimal("100.00"), "inr")  # partial refund
    record_refund(db, intent_id=intent_id, refunded_minor=refund_amount, currency=currency)
    print(f"  Reversal posted: {refund_amount} paise from revenue -> user wallet")
    print("  Original ledger entry was NOT modified.\n")

    # ------------------------------------------------------------------
    # 6. Materialized balances
    # ------------------------------------------------------------------
    print("--- 6. Materialized balances ---")
    for acct_id in ["gateway:stripe", "revenue:sales", "user:42:wallet"]:
        acct = db.get(Account, acct_id)
        recomputed = account_balance_from_entries(db, acct_id, currency)
        match_ok = "OK" if acct.balance_minor == recomputed else "MISMATCH"
        display = to_display(abs(acct.balance_minor), currency)
        print(f"  {acct_id:<26}  balance={acct.balance_minor:>8} paise "
              f"({display} INR)  [{match_ok}]")

    # ------------------------------------------------------------------
    # 7. Reconciliation invariant check
    # ------------------------------------------------------------------
    print("\n--- 7. Reconciliation invariant (sum per txn must be 0) ---")
    imbalances = check_ledger_balance(db)
    if imbalances:
        print(f"  ALERT: {len(imbalances)} unbalanced transaction(s) found!")
        for row in imbalances:
            print(f"  -> {row}")
    else:
        print("  All transactions balanced (sum == 0 for every transaction_id).")

    # ------------------------------------------------------------------
    # 8. All ledger entries
    # ------------------------------------------------------------------
    print("\n--- 8. Ledger audit trail (all entries, append-only) ---")
    entries = db.query(LedgerEntry).all()
    for e in entries:
        sign = "+" if e.amount_minor > 0 else ""
        print(f"  id={e.id:<3} txn={e.transaction_id[:8]}...  "
              f"account={e.account_id:<26} amount={sign}{e.amount_minor:>8}  "
              f"ref={e.external_ref}")

    db.close()
    print("\n" + "=" * 64)
    print("  Demo complete.")
    print("=" * 64 + "\n")


if __name__ == "__main__":
    _run_local_demo()
