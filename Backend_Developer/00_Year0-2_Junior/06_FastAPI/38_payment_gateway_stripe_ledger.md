# Payment Gateway (Stripe PaymentIntents) + Double-Entry Ledger

## Why It Matters (Senior 5 YOE Context)

Payment integration mein ek bug = real paisa galat jagah. Isiliye yeh teen cheezein non-negotiable hain:

- **Money correctness** → float NEVER. Integer minor units (paise/cents) store karo.
- **PCI-DSS scope** → card number tumhare server pe aana hi nahi chahiye. Stripe.js client se directly Stripe ko bhejta hai → tum **SAQ-A** scope mein aa jaate ho (lightest compliance).
- **Authoritative result = WEBHOOK**, synchronous HTTP response nahi. Network drop ho sakta hai, par webhook retry hota hai.
- **Double-entry ledger** → har paisa movement balanced (debit == credit). Append-only. Posted entry ko kabhi UPDATE nahi karte — reverse karte ho ek nayi entry se.

Senior interview: "User ne card confirm kiya, par tumhara `/confirm` API response timeout ho gaya. Customer ko charge hua ya nahi — tum kaise pata karoge aur DB kaise consistent rakhoge?" → Answer is the whole file: idempotency key + webhook as source of truth + ledger entry only on `payment_intent.succeeded`.

---

## Part 1 — Money Correctness FIRST (sabse pehle yeh)

### Float kyun TODTA hai money ko

```python
>>> 0.1 + 0.2
0.30000000000000004        # IEEE-754 binary float — 0.1 exactly represent nahi hota
>>> 0.1 + 0.2 == 0.3
False
```

Float = binary fraction. `0.1` decimal ko binary mein finitely represent nahi kar sakte (jaise 1/3 decimal mein nahi hota). Thousands of transactions ke baad yeh rounding errors accumulate hoke ledger ko unbalanced kar dete hain. **Audit fail.**

### Rule: store money as INTEGER minor units

`₹499.00` = **49900 paise** (int). `$10.50` = **1050 cents** (int). Database column = `BIGINT`. Koi fraction nahi, koi rounding drift nahi. Yeh exactly wahi unit hai jo Stripe API expect karta hai (`amount` = smallest currency unit).

```python
# pip install stripe
from decimal import Decimal, ROUND_HALF_UP

# Currencies ke alag exponents hote hain (most = 2, JPY = 0, BHD = 3).
CURRENCY_MINOR_EXPONENT = {"usd": 2, "eur": 2, "inr": 2, "jpy": 0, "bhd": 3}


def to_minor_units(amount: Decimal, currency: str) -> int:
    """User-facing decimal -> integer minor units. Decimal SIRF boundary pe."""
    exp = CURRENCY_MINOR_EXPONENT[currency.lower()]
    quantum = Decimal(10) ** -exp                      # e.g. Decimal('0.01')
    minor = (amount.quantize(quantum, rounding=ROUND_HALF_UP)
             * (Decimal(10) ** exp))
    return int(minor)                                  # exact int — no float anywhere


def to_display(minor: int, currency: str) -> Decimal:
    """Integer minor units -> Decimal for display ONLY (templates, invoices)."""
    exp = CURRENCY_MINOR_EXPONENT[currency.lower()]
    return (Decimal(minor) / (Decimal(10) ** exp)).quantize(Decimal(10) ** -exp)


# ₹499.00 -> 49900 paise
assert to_minor_units(Decimal("499.00"), "inr") == 49900
assert to_display(49900, "inr") == Decimal("499.00")
# ¥1500 -> 1500 (JPY ka exponent 0, koi paise nahi)
assert to_minor_units(Decimal("1500"), "jpy") == 1500
```

**`Decimal` sirf boundary pe** (user input parse karte waqt, invoice render karte waqt). Internal arithmetic, DB storage, Stripe calls — sab **int minor units**. `Decimal` exact hai par slow + serialization-unfriendly; int fast + unambiguous.

> Production tip: ek currency-aware type use karo (library `py-moneyed` ka `Money`, ya custom `(amount_minor: int, currency: str)` value object) taaki "USD 1050" aur "INR 1050" kabhi accidentally add na ho. Bare int khatarnak hai kyunki currency context kho jaata hai.

---

## Part 2 — Stripe PaymentIntents Flow (modern API, NOT legacy Charges)

Legacy `Charge` API single-shot tha — koi SCA / 3D-Secure support nahi. Modern **PaymentIntent** ek *stateful object* hai jo poora lifecycle track karta hai (authentication, retries, async confirmation). Naya code hamesha PaymentIntents use kare.

### Flow (kaun-kaun se step kahan chalte hain)

```
[ Your Server ]                    [ Browser / Stripe.js ]            [ Stripe ]
     |                                      |                             |
  1. create PaymentIntent  ──────────────────────────────────────────►   |
     (amount=int minor, currency, idempotency_key)                        |
     |  ◄──────────────── client_secret ────────────────────────────────  |
     |                                      |                             |
  2. client_secret bhejo  ───────────────►  |                             |
     (sirf yeh, secret key kabhi nahi)      |                             |
     |                                      | 3. stripe.confirmPayment    |
     |                                      |    (card data DIRECTLY) ──►  |
     |                                      |  ◄── requires_action? 3DS    |
     |                                      |                             |
  4. AUTHORITATIVE RESULT via WEBHOOK  ◄──────────────────────────────── |
     payment_intent.succeeded                                            |
```

**Key insight:** card number **kabhi tumhare server pe nahi aata**. Browser mein Stripe Elements (iframe) card collect karta hai, `client_secret` use karke directly Stripe ko confirm karta hai. Tumhare server ko sirf `client_secret` aur baad mein webhook milta hai. Isi se PCI scope **SAQ-A** ho jaata hai.

### Server: create PaymentIntent

```python
# pip install stripe fastapi
import stripe
from fastapi import FastAPI, Request, Header, HTTPException
from pydantic import BaseModel

stripe.api_key = "sk_test_xxx"            # secret key — SERVER ONLY, never to client
STRIPE_WEBHOOK_SECRET = "whsec_xxx"       # webhook signing secret (alag from api_key)

app = FastAPI()


class CheckoutRequest(BaseModel):
    order_id: str
    amount_minor: int                     # int paise/cents — already converted, no float
    currency: str = "inr"


@app.post("/payments/create-intent")
async def create_intent(req: CheckoutRequest):
    # Idempotency-Key: agar client/network retry kare to Stripe DUPLICATE
    # PaymentIntent nahi banayega — same object return karega. Double-charge se bachao.
    intent = stripe.PaymentIntent.create(
        amount=req.amount_minor,          # MUST be int in smallest unit
        currency=req.currency,
        metadata={"order_id": req.order_id},
        automatic_payment_methods={"enabled": True},
        idempotency_key=f"order:{req.order_id}:create-intent",
    )
    # client_secret bhejo — browser isi se confirm karega.
    # NOTE: yahan se "paid" mat maano. Authoritative result webhook se aayega.
    return {"client_secret": intent.client_secret, "intent_id": intent.id}
```

### Client (browser) — reference (yeh tumhare server pe nahi chalta)

```html
<!-- Stripe.js loads card fields in an iframe Stripe controls.
     Card PAN tumhare DOM / server ko kabhi nahi milta -> PCI SAQ-A. -->
<script src="https://js.stripe.com/v3/"></script>
<script>
  const stripe = Stripe("pk_test_xxx");                 // publishable key (public, safe)
  const elements = stripe.elements({ clientSecret });   // server se aaya
  // ... mount payment element ...
  const { error } = await stripe.confirmPayment({
    elements,
    confirmParams: { return_url: "https://app.example.com/order/complete" },
  });
  // error handle karo; SUCCESS ko backend webhook authoritative maanega.
</script>
```

---

## Part 3 — Idempotency (double-charge ka asli defense)

Do alag idempotency layers hain — dono chahiye:

| Layer | Kya | Kaise |
|-------|-----|-------|
| **Stripe-side** | Stripe pe duplicate PaymentIntent na bane | `idempotency_key=` arg on `create()` calls |
| **Your-side** | Tumhare DB pe duplicate order/ledger na bane | Apni idempotency key + DB unique constraint |

Stripe ki `Idempotency-Key` 24 hours tak result cache karti hai: same key + same params → cached response (no new charge). **Tip:** key ko apne business operation se tie karo (`order:{id}:create-intent`), random UUID se nahi — tabhi retries ka matlab banta hai.

```python
# Outgoing call idempotency — same key on retry = no duplicate side effect
intent = stripe.PaymentIntent.create(
    amount=49900, currency="inr",
    idempotency_key=f"order:{order_id}:create-intent",   # deterministic, business-tied
)
```

> Idempotency ka deep mechanics (Redis SETNX, replay window, DB unique constraint as defense-in-depth) → dekho `22_hmac_webhooks_idempotency.md`.

---

## Part 4 — Webhooks: Authoritative Result (RAW body!)

Synchronous response trust nahi karte. Stripe har payment outcome ko webhook se bhejta hai, aur **retry** karta hai jab tak tum `2xx` na do. Isiliye final "paid" state webhook handler mein commit hoti hai.

### Critical rules

1. **RAW request body chahiye** signature verification ke liye. FastAPI mein `await request.body()` — JSON parse karke re-serialize karoge to bytes badal jaayenge aur signature fail ho jaayegi.
2. **`stripe.Webhook.construct_event(payload, sig_header, secret)`** — yeh signature verify + parse dono karta hai. Manually HMAC mat likho.
3. **Dedupe by `event.id`** — Stripe same event do baar bhej sakta hai (at-least-once delivery).
4. **Return 200 fast, process async** — heavy kaam background mein. Stripe ka timeout chhota hai; slow handler = unnecessary retries.

```python
import stripe
from fastapi import BackgroundTasks, Request, Header, HTTPException

STRIPE_WEBHOOK_SECRET = "whsec_xxx"


@app.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    background: BackgroundTasks,
    stripe_signature: str = Header(None, alias="Stripe-Signature"),
):
    payload = await request.body()        # RAW bytes — re-serialize MAT karo

    # 1. Verify signature + parse. Galat sig ya tampered body -> raise.
    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=stripe_signature,
            secret=STRIPE_WEBHOOK_SECRET,
        )
    except ValueError:
        raise HTTPException(400, "Invalid payload")                    # bad JSON
    except stripe.error.SignatureVerificationError:
        raise HTTPException(400, "Invalid signature")                  # forged / wrong secret

    # 2. Dedupe by event.id (at-least-once delivery). Atomic insert; agar
    #    already-seen hai to fast 200 -> Stripe ko bata do "got it, ruk ja".
    if not mark_event_seen_atomic(event["id"]):                        # False = duplicate
        return {"status": "duplicate"}

    # 3. Quick 200; actual money work background mein. Stripe timeout se bacho.
    background.add_task(handle_stripe_event, event)
    return {"status": "received"}


def handle_stripe_event(event: dict) -> None:
    etype = event["type"]
    obj = event["data"]["object"]                                      # the PaymentIntent/Charge

    if etype == "payment_intent.succeeded":
        # SIRF yahan paisa "received" maano. Ledger entry yahan likho.
        order_id = obj["metadata"]["order_id"]
        record_successful_payment(
            order_id=order_id,
            amount_minor=obj["amount_received"],                       # int minor units
            currency=obj["currency"],
            intent_id=obj["id"],
        )
    elif etype == "payment_intent.payment_failed":
        order_id = obj["metadata"].get("order_id")
        err = (obj.get("last_payment_error") or {}).get("message")
        mark_order_failed(order_id, reason=err)                        # NO ledger entry
    elif etype == "charge.refunded":
        # Refund = REVERSAL ledger entry (niche Part 5 dekho). Original entry UPDATE nahi.
        record_refund(
            intent_id=obj["payment_intent"],
            refunded_minor=obj["amount_refunded"],                     # int minor units
            currency=obj["currency"],
        )
    # baaki event types -> ignore (200 already bheja).
```

> Webhook signature internals (HMAC-SHA256, `t=...,v1=...` format, replay window, `compare_digest`) aur outgoing-webhook retry/DLQ patterns → `22_hmac_webhooks_idempotency.md` aur `10_webhooks_scheduler_monitoring.md`.

---

## Part 5 — Double-Entry Ledger Design

Accounting ka 500-saal purana invariant: **har transaction = balanced debit + credit jo zero pe sum hote hain.** Paisa kahin se aata hai, kahin jaata hai — disappear/appear nahi karta. Software mein yeh tumhe correctness guarantee deta hai.

### Core rules

1. **Har money movement = kam se kam 2 entries** (ek debit, ek credit), jinka sum = 0.
2. **Append-only / immutable** — posted ledger entry ko **kabhi UPDATE/DELETE nahi**.
3. **Balance = SUM of entries** us account ke (ya performance ke liye materialized/cached balance, par source of truth = entries).
4. **Galti / refund = REVERSAL entry** (nayi balanced entry jo effect ko ulta de), original ko touch nahi karte. Audit trail intact rehta hai.
5. **Dono legs ek hi DB transaction mein** likho — warna half-written ledger = unbalanced = corruption.

### Minimal schema

```python
# pip install sqlalchemy
from sqlalchemy import (Column, BigInteger, String, DateTime, ForeignKey,
                        CheckConstraint, func)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Account(Base):
    """Har wallet/cash/revenue account. balance_minor = materialized cache."""
    __tablename__ = "accounts"
    id = Column(String, primary_key=True)               # e.g. 'user:42:wallet'
    type = Column(String, nullable=False)               # asset | liability | revenue | expense
    currency = Column(String(3), nullable=False)
    balance_minor = Column(BigInteger, nullable=False, default=0)   # int minor units cache


class LedgerEntry(Base):
    """
    Immutable, append-only. Ek transfer ke saare legs same transaction_id share
    karte hain. Ek hi 'amount_minor' signed column: + = debit, - = credit.
    INVARIANT: SUM(amount_minor) over a transaction_id == 0.
    """
    __tablename__ = "ledger_entries"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    transaction_id = Column(String, nullable=False, index=True)     # groups legs
    account_id = Column(String, ForeignKey("accounts.id"), nullable=False, index=True)
    amount_minor = Column(BigInteger, nullable=False)               # signed int; +debit / -credit
    currency = Column(String(3), nullable=False)
    # external_ref UNIQUE -> Stripe event ka same intent do baar post na ho (idempotency)
    external_ref = Column(String, unique=True, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        CheckConstraint("amount_minor <> 0", name="nonzero_amount"),
    )
```

> Convention note: yeh schema **signed single-column** use karta hai (`+` debit, `-` credit) — simple aur sum-to-zero check trivial. Doosri valid style: alag `debit_minor` + `credit_minor` columns. Dono industry mein chalte hain; team ki convention follow karo.

### Transfer: dono legs ek transaction mein (atomic)

```python
import uuid
from sqlalchemy.orm import Session


def post_transfer(
    db: Session,
    *,
    from_account: str,
    to_account: str,
    amount_minor: int,                 # int, must be > 0
    currency: str,
    external_ref: str | None = None,   # e.g. Stripe intent id -> dedupe
) -> str:
    """
    Move `amount_minor` from one account to another as a BALANCED pair.
    Debit + credit + balance updates -> SAB ek DB transaction mein (all-or-nothing).
    """
    if amount_minor <= 0:
        raise ValueError("amount_minor must be a positive integer")

    txn_id = str(uuid.uuid4())

    # Leg 1: debit source (+), Leg 2: credit destination (-). Sum = 0. ✅ balanced
    db.add_all([
        LedgerEntry(transaction_id=txn_id, account_id=from_account,
                    amount_minor=+amount_minor, currency=currency,
                    external_ref=external_ref),
        LedgerEntry(transaction_id=txn_id, account_id=to_account,
                    amount_minor=-amount_minor, currency=currency,
                    external_ref=None),
    ])

    # Materialized balances update — SAME transaction. Row lock leke race se bacho.
    src = db.query(Account).filter_by(id=from_account).with_for_update().one()
    dst = db.query(Account).filter_by(id=to_account).with_for_update().one()
    src.balance_minor += amount_minor
    dst.balance_minor -= amount_minor

    db.commit()        # <- atomic: dono legs + dono balances ek saath, ya kuch bhi nahi
    return txn_id
```

`external_ref` pe UNIQUE constraint = agar webhook do baar `record_successful_payment` call kare (Stripe retry / our background re-run), to second insert `IntegrityError` se fail hoga — ledger me duplicate paisa nahi aayega. Yeh DB-level idempotency hai.

### Refund = reversal, NOT update

```python
def record_refund(db: Session, *, intent_id: str, refunded_minor: int, currency: str):
    """
    Refund original entry ko UPDATE nahi karta. Ulti direction ki NAYI balanced
    entry post karta hai. Audit trail: original + reversal dono dikhte hain.
    """
    post_transfer(
        db,
        from_account="revenue:sales",        # paisa wapas revenue se nikla
        to_account="user:42:wallet",         # customer ko credit (ya gateway clearing)
        amount_minor=refunded_minor,         # int minor units
        currency=currency,
        external_ref=f"refund:{intent_id}",  # unique -> double-refund posting block
    )
```

### Reconciliation idea

Roz (cron/APScheduler job) **Stripe balance/payout report** ko apne ledger ke against milao:

- Stripe ke "succeeded" charges ka total (minor units) == tumhare ledger ke corresponding entries ka SUM hona chahiye.
- Mismatch = missed webhook ya double-post → alert + manual review. Stripe ki settlement report import karke per-`intent_id` diff nikalo.
- Bonus invariant check: `SELECT transaction_id, SUM(amount_minor) FROM ledger_entries GROUP BY transaction_id HAVING SUM(amount_minor) <> 0;` — koi bhi row return hui to ledger unbalanced hai (bug!).

> Scheduling/cron mechanics (APScheduler `CronTrigger`, lifespan startup) → `10_webhooks_scheduler_monitoring.md`.

---

## Part 6 — Payment State Machine

PaymentIntent ek finite state machine hai. Tum apne `Order` ko isi se mirror karte ho. Transitions Stripe drive karta hai; tum webhooks se observe karte ho.

```
requires_payment_method  ──confirm──►  requires_confirmation
                                              │
                                              ▼
                                         processing
                                         │       │
                              (3DS/OTP)  │       │
                                         ▼       ▼
                                requires_action  succeeded ✅
                                         │              │
                          (auth fail)    │              ▼
                                         ▼          charge.refunded
                                      canceled        (reversal entry)
```

| State | Matlab | Tumhara action |
|-------|--------|----------------|
| `requires_payment_method` | Naya intent, ya last attempt fail | Customer ko card collect karne do |
| `requires_confirmation` | Method attached, confirm pending | `confirmPayment` (client) |
| `processing` | Stripe authorize kar raha | Wait — koi ledger entry nahi |
| `requires_action` | 3D-Secure / SCA chahiye | Client 3DS challenge complete kare |
| `succeeded` | Paisa captured ✅ | **Webhook pe ledger entry likho**, order fulfill |
| `canceled` | Intent canceled / auth fail | Order fail mark karo, no ledger entry |
| (refund) | `charge.refunded` event | **Reversal** ledger entry |

**Golden rule:** ledger entry **sirf** `payment_intent.succeeded` pe. `processing`/`requires_action` intermediate hain — inpe paisa commit mat karo.

---

## Common Pitfalls

1. **Float for money** — `amount = 49.90` (float). Banao `49900` (int paise). Boundary pe `Decimal`, internally int.
2. **Synchronous response ko source of truth maanna** — `/confirm` ka HTTP 200 ≠ paisa aaya. Sirf webhook authoritative. Timeout pe bhi webhook se truth milegi.
3. **Webhook body parse karke verify** — `await request.json()` se signature TODTI hai. `await request.body()` (raw bytes) use karo, phir `construct_event`.
4. **`event.id` dedupe na karna** — Stripe at-least-once deliver karta hai. Bina dedupe = double ledger entry = double paisa.
5. **Idempotency-Key na bhejna `create()` pe** — network retry = do PaymentIntents = double charge.
6. **Posted ledger entry UPDATE karna** — refund/correction ke liye **reversal entry**, original immutable.
7. **Dono legs alag transactions mein** — crash beech mein = unbalanced ledger. Ek `db.commit()` mein dono.
8. **Mixed currency add karna** — `usd 1050` + `inr 1050` = nonsense. Currency-aware type ya per-currency accounts.
9. **`stripe.api_key` (secret) ko client bhejna** — sirf `publishable key` + `client_secret` client pe jaate hain.
10. **Webhook me heavy sync work** — Stripe timeout → unnecessary retries. Verify + dedupe + 200, baaki background.

---

## Interview Q&A

**Q1:** Money ko float me kyun store nahi karte? Phir kaise karte ho?
**A:** Float = IEEE-754 binary; `0.1` exactly represent nahi hota, `0.1+0.2 != 0.3`. Thousands of txns me rounding drift accumulate hoke ledger unbalance kar deta hai (audit fail). Solution: **integer minor units** (paise/cents) — `BIGINT` column. `Decimal` sirf boundary pe (user input parse / invoice render). Internal + DB + Stripe API sab int. Currency-aware type taaki cross-currency add na ho.

**Q2:** PaymentIntents flow puri batao — card data kahan jaata hai?
**A:** Server `stripe.PaymentIntent.create(amount=int_minor, currency, idempotency_key)` karke `client_secret` return karta hai. Browser Stripe.js/Elements (iframe) me card collect karke `client_secret` se **directly Stripe** ko confirm karta hai — card PAN server pe kabhi nahi aata → PCI **SAQ-A**. Final outcome `payment_intent.succeeded` **webhook** se aata hai, sync response se nahi. Legacy `Charge` API use nahi karte (no SCA support).

**Q3:** `/confirm` response timeout ho gaya — customer charge hua ya nahi, DB consistent kaise?
**A:** Sync response pe depend nahi karta. (1) `create()` pe deterministic `idempotency_key` → retry duplicate charge nahi banata. (2) Truth webhook se: `payment_intent.succeeded` aaya to paid. (3) Ledger entry sirf webhook handler me, `external_ref` (intent id) UNIQUE → re-delivery pe duplicate insert fail. (4) Reconciliation job daily Stripe report vs ledger match karta hai.

**Q4:** Stripe webhook securely kaise handle karoge?
**A:** (1) `await request.body()` se **raw bytes**. (2) `stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)` — signature verify + parse; fail pe 400. (3) `event.id` se dedupe (at-least-once). (4) Fast **200** return, processing **background** me. (5) `succeeded` → ledger; `payment_failed` → mark failed (no ledger); `charge.refunded` → reversal entry. Secret = `whsec_...` (api_key se alag).

**Q5:** Double-entry ledger kya hai aur software me kyun?
**A:** Har money movement = balanced debit+credit jo **zero pe sum** hote hain — paisa create/destroy nahi hota, move hota hai. Append-only/immutable; balance = SUM(entries) (ya materialized cache). Galti/refund = **reversal entry**, original UPDATE nahi → full audit trail. Dono legs **ek DB transaction** me (all-or-nothing) warna unbalanced corruption. Invariant: `GROUP BY transaction_id HAVING SUM <> 0` empty hona chahiye.

**Q6:** Refund ledger me kaise represent karoge?
**A:** Original entry ko **kabhi UPDATE nahi**. Ulti direction ki nayi balanced entry post karta hu (revenue → customer wallet/clearing), `external_ref="refund:{intent}"` UNIQUE taaki double-refund block ho. Trigger `charge.refunded` webhook. Audit me original + reversal dono dikhte hain.

**Q7:** Idempotency ke do levels kaunse?
**A:** (1) **Stripe-side**: `create()` pe `idempotency_key` (24h cache) → Stripe pe duplicate PaymentIntent nahi. Key ko business op se tie karo (`order:{id}:create-intent`), random nahi. (2) **Your-side**: ledger `external_ref` UNIQUE constraint + (optional) Redis SETNX on `event.id` → DB pe duplicate posting nahi. Defense-in-depth — dono chahiye.

**Q8:** PaymentIntent states aur ledger entry timing?
**A:** `requires_payment_method → requires_confirmation → processing → succeeded | requires_action | canceled`. Ledger entry **sirf** `succeeded` pe. `processing`/`requires_action` (3DS/SCA) intermediate — paisa commit nahi. `canceled`/`payment_failed` → order fail, no ledger. Refund alag `charge.refunded` → reversal.

---

## Summary Table

| Concern | Wrong | Right |
|---------|-------|-------|
| Money storage | `float 49.90` | `int 49900` minor units (BIGINT) |
| Decimal usage | Everywhere | Sirf boundary (parse/display) |
| API | Legacy `Charge` | `PaymentIntent` |
| Card data | Your server | Stripe.js iframe → SAQ-A |
| Source of truth | Sync HTTP response | **Webhook** (`succeeded`) |
| Webhook verify | parsed JSON | **raw body** + `construct_event` |
| Dedupe | none | by `event.id` + `external_ref` UNIQUE |
| Double-charge guard | none | `idempotency_key` on `create()` |
| Refund | UPDATE entry | **Reversal** entry |
| Ledger legs | separate commits | **one** DB transaction |

---

## Related Topics

- `22_hmac_webhooks_idempotency.md` — webhook signature (HMAC-SHA256, `Stripe-Signature` format, replay window, `compare_digest`), idempotency internals (Redis SETNX, DB unique constraint)
- `10_webhooks_scheduler_monitoring.md` — webhook retry/backoff, APScheduler (reconciliation cron job), structlog/Prometheus for payment observability
- `06_security_jwt_rbac.md` — securing the checkout/payment endpoints (authN/authZ)
- `09_sqlalchemy_advanced.md` — `with_for_update()` row locks, transaction isolation for the ledger
- `21_rfc7807_problem_details.md` — structured error responses for failed payments
- `../../02_Year5+_Senior/01_System_Design/HLD_Problems/Payment_System.md` — Payment System HLD (scale, sharding, exactly-once at scale)
- `../../02_Year5+_Senior/01_System_Design/LLD_Problems/Payment_System.md` — Payment System LLD (class design, state machine modeling)

## References

- [Stripe PaymentIntents API](https://stripe.com/docs/api/payment_intents)
- [Stripe — Accept a payment (Elements)](https://stripe.com/docs/payments/accept-a-payment)
- [Stripe Idempotent requests](https://stripe.com/docs/api/idempotent_requests)
- [Stripe Webhooks + `construct_event`](https://stripe.com/docs/webhooks)
- [Stripe — Currencies & zero-decimal currencies](https://stripe.com/docs/currencies)
- [Martin Kleppmann / accounting: double-entry as event log] — see also `04_outbox_event_sourcing.md` in Microservices
