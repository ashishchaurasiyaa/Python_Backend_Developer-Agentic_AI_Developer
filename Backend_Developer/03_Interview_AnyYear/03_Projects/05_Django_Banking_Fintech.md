# Project 5: Banking / Fintech Backend

**Stack:** Django 5 + DRF + Postgres + Redis + Celery + Kafka + WeasyPrint + Docker
**Build Time:** 4-6 weeks
**Difficulty:** ⭐⭐⭐⭐⭐ (Correctness-critical, compliance-heavy)
**Resume Strength:** ⭐⭐⭐⭐⭐ (High-pay fintech opportunities)

---

## 1. Project Overview & Business Problem

### What it is
A digital banking backend — accounts, deposits, withdrawals, transfers, transaction history, statements, KYC, and compliance reporting. Like a bank-as-a-service or neobank backend.

### Why build this
- **ACID + consistency challenges:** The hardest correctness problems in backend.
- **Indian fintech booming:** Razorpay, CRED, Jupiter, Slice all need backends like this.
- **High compensation:** Fintech pays among the highest in tech.
- **Real-world rigor:** Audit trails, idempotency, double-entry — patterns that scale to any high-stakes domain.

### Real-world analogues
- Stripe Treasury / Connect
- Razorpay X
- CRED
- Jupiter
- Mercury
- Wise
- Cash App
- PayPal
- N26 (EU)

---

## 2. Requirements

### Functional
- **User onboarding** with KYC (Aadhaar/PAN/Document upload).
- **Account creation** (savings, current, joint, escrow).
- **Deposits & withdrawals**.
- **P2P transfers** (account-to-account).
- **External transfers** (bank ACH/IMPS/NEFT/UPI in India, ACH/Wire in US).
- **Transaction history** (filterable, searchable).
- **Statements** (PDF, monthly).
- **Recurring payments** (standing instructions).
- **Cards** (virtual + physical, with controls).
- **Notifications** (transaction alerts via SMS, email, push).
- **Disputes & refunds**.
- **Compliance reports** (KYC docs, transaction monitoring).

### Non-Functional
- 100% accurate balance computation (no off-by-one).
- ACID guarantees on every transaction.
- Audit log: immutable, append-only.
- KYC compliance.
- PCI DSS-ready (for cards).
- 99.99% availability for read; 99.95% for write.
- Multi-region with strict data residency (India data stays in India).
- All transactions reconciled daily.

---

## 3. Scale Estimation

| Metric | Number |
|---|---|
| Users | 5M |
| Accounts | 7M (some users have multiple) |
| Daily active users | 1M |
| Transactions/day | 10M |
| Peak transactions/sec | 1K (steady), 5K (e.g., salary day) |
| Average transaction amount | ₹500 ($6) |
| Total balance under management | ₹500 Cr ($60M) |
| Audit log entries/day | 50M (each txn = multiple log entries) |
| Storage (transactions, 5 years) | ~3.5B rows = ~700GB |

---

## 4. The Core: Double-Entry Bookkeeping

Every transaction has two sides — credit and debit. Sum of all credits = sum of all debits. Always.

### Why?
- Self-validating (run reconciliation; sum should be 0).
- Industry standard (every accounting system).
- Required for regulatory compliance.

### Example
**User A transfers ₹500 to User B**:
```
Entry 1: User A account → -500 (debit)
Entry 2: User B account → +500 (credit)
Sum: 0 ✓
```

**User A deposits ₹1000 from external source**:
```
Entry 1: User A account → +1000 (credit)
Entry 2: Cash/Float/External account → -1000 (debit)
Sum: 0 ✓
```

### Failure of double-entry
If you only track per-account balance:
- Race condition can lose money.
- No way to reconcile.
- Disputes hard to investigate.

---

## 5. High-Level Architecture

```
                       ┌──────────────┐
                       │   Cloudflare │ (WAF + DDoS)
                       └──────┬───────┘
                              │
                       ┌──────▼───────┐
                       │   API GW     │
                       └──────┬───────┘
                              │
        ┌─────────┬───────────┼──────────┬──────────┐
        │         │           │          │          │
    ┌───▼───┐ ┌───▼───┐  ┌────▼────┐ ┌───▼────┐ ┌───▼────┐
    │ Auth  │ │ KYC   │  │  Txn    │ │ Card   │ │Reports │
    │ Svc   │ │ Svc   │  │  Engine │ │ Svc    │ │ Svc    │
    └───┬───┘ └───┬───┘  └────┬────┘ └───┬────┘ └───┬────┘
        │         │            │           │          │
        └─────────┴────────────┼───────────┴──────────┘
                               │
                ┌──────────────┼──────────────┐
                │              │              │
            ┌───▼────┐    ┌────▼────┐    ┌────▼────┐
            │Postgres│    │  Redis  │    │  Kafka  │
            │+Replicas│   │         │    │         │
            └────────┘    └─────────┘    └────┬────┘
                                              │
                              ┌───────────────┼───────────────┐
                              │               │               │
                         ┌────▼─────┐   ┌─────▼─────┐   ┌────▼─────┐
                         │Reconcile │   │Notify     │   │Audit Log │
                         │ Worker   │   │ Worker    │   │Worker    │
                         └──────────┘   └───────────┘   └──────────┘
```

---

## 6. Data Model

### Ledger-based (double-entry)

```sql
-- Users
CREATE TABLE users (
    id              BIGSERIAL PRIMARY KEY,
    email           TEXT UNIQUE,
    phone_number    TEXT UNIQUE,
    full_name       TEXT NOT NULL,
    date_of_birth   DATE,
    address         JSONB,
    pan_number      TEXT UNIQUE,    -- India
    aadhaar_hash    TEXT,            -- never store raw
    kyc_status      TEXT,            -- 'pending', 'verified', 'rejected'
    kyc_level       INT DEFAULT 0,   -- 0=none, 1=basic, 2=full
    is_active       BOOL DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Accounts
CREATE TABLE accounts (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES users(id),
    account_number  TEXT UNIQUE NOT NULL,    -- 14-digit
    ifsc_code       TEXT,                     -- bank routing
    account_type    TEXT NOT NULL,             -- 'savings', 'current', 'escrow'
    currency        CHAR(3) NOT NULL DEFAULT 'INR',
    status          TEXT DEFAULT 'active',     -- 'active', 'frozen', 'closed'
    opened_at       TIMESTAMPTZ DEFAULT now(),
    closed_at       TIMESTAMPTZ
);
CREATE INDEX idx_accounts_user ON accounts(user_id);

-- Transactions (one row per logical transaction)
CREATE TABLE transactions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idempotency_key TEXT UNIQUE NOT NULL,        -- prevents double-charge
    txn_type        TEXT NOT NULL,                -- 'transfer', 'deposit', 'withdrawal'
    status          TEXT NOT NULL,                -- 'pending', 'success', 'failed', 'reversed'
    amount          NUMERIC(15, 4) NOT NULL,      -- 4 decimal places for crypto support
    currency        CHAR(3) NOT NULL,
    source_account  BIGINT REFERENCES accounts(id),
    dest_account    BIGINT REFERENCES accounts(id),
    description     TEXT,
    external_ref    TEXT,                          -- payment gateway reference
    initiated_by    BIGINT REFERENCES users(id),
    initiated_at    TIMESTAMPTZ DEFAULT now(),
    completed_at    TIMESTAMPTZ,
    failed_reason   TEXT,
    metadata        JSONB DEFAULT '{}'
);
CREATE INDEX idx_txn_source ON transactions(source_account, initiated_at DESC);
CREATE INDEX idx_txn_dest ON transactions(dest_account, initiated_at DESC);

-- Ledger entries (the double-entry side)
CREATE TABLE ledger_entries (
    id              BIGSERIAL PRIMARY KEY,
    transaction_id  UUID NOT NULL REFERENCES transactions(id),
    account_id      BIGINT NOT NULL REFERENCES accounts(id),
    entry_type      CHAR(1) NOT NULL,             -- 'D' (debit), 'C' (credit)
    amount          NUMERIC(15, 4) NOT NULL,
    balance_after   NUMERIC(15, 4) NOT NULL,      -- denormalized for audit
    created_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_ledger_account ON ledger_entries(account_id, id);
CREATE INDEX idx_ledger_txn ON ledger_entries(transaction_id);

-- Balance cache (current balance per account)
CREATE TABLE balances (
    account_id      BIGINT PRIMARY KEY REFERENCES accounts(id),
    current_balance NUMERIC(15, 4) NOT NULL DEFAULT 0,
    available_balance NUMERIC(15, 4) NOT NULL DEFAULT 0,  -- minus holds
    version         INT NOT NULL DEFAULT 0,                -- optimistic lock
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- Pending holds (for cards, escrow)
CREATE TABLE balance_holds (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id      BIGINT NOT NULL,
    amount          NUMERIC(15, 4) NOT NULL,
    reason          TEXT,
    expires_at      TIMESTAMPTZ,
    released_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Audit log (immutable)
CREATE TABLE audit_log (
    id              BIGSERIAL PRIMARY KEY,
    actor_id        BIGINT,
    action          TEXT NOT NULL,
    resource_type   TEXT,
    resource_id     TEXT,
    before          JSONB,
    after           JSONB,
    metadata        JSONB,
    ip_address      INET,
    created_at      TIMESTAMPTZ DEFAULT now()
);
-- Partitioned by month
```

### Why both `transactions` and `ledger_entries`?
- `transactions` = the logical operation (UI shows this).
- `ledger_entries` = the accounting reality (2+ rows per transaction).

You can ALWAYS derive balance from `ledger_entries`. The `balances` table is just a cache for fast reads.

---

## 7. Transaction Engine (The Critical Path)

### Money transfer flow

```python
from django.db import transaction
from decimal import Decimal

class TransferService:
    def transfer(
        self,
        source_account_id: int,
        dest_account_id: int,
        amount: Decimal,
        idempotency_key: str,
        description: str = None
    ):
        # Idempotency check
        existing = Transaction.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            return existing

        # Validate amount
        if amount <= 0:
            raise InvalidAmountError()
        if amount > Decimal("100000"):  # ₹1L limit per txn
            raise AmountExceedsLimitError()

        with transaction.atomic():
            # Lock source account (FOR UPDATE)
            source = Account.objects.select_for_update().get(id=source_account_id)
            dest = Account.objects.select_for_update().get(id=dest_account_id)

            # Check account states
            if source.status != "active":
                raise AccountFrozenError()
            if dest.status != "active":
                raise AccountFrozenError()

            # Check balance
            source_balance = Balance.objects.select_for_update().get(account_id=source.id)
            if source_balance.available_balance < amount:
                raise InsufficientFundsError()

            # Create the transaction record
            txn = Transaction.objects.create(
                idempotency_key=idempotency_key,
                txn_type="transfer",
                status="pending",
                amount=amount,
                currency=source.currency,
                source_account=source,
                dest_account=dest,
                description=description,
                initiated_by_id=source.user_id,
            )

            # Create ledger entries (double-entry)
            new_source_balance = source_balance.current_balance - amount
            new_dest_balance = Balance.objects.select_for_update().get(account_id=dest.id).current_balance + amount

            LedgerEntry.objects.bulk_create([
                LedgerEntry(
                    transaction=txn,
                    account=source,
                    entry_type="D",
                    amount=amount,
                    balance_after=new_source_balance
                ),
                LedgerEntry(
                    transaction=txn,
                    account=dest,
                    entry_type="C",
                    amount=amount,
                    balance_after=new_dest_balance
                ),
            ])

            # Update balance cache
            Balance.objects.filter(account_id=source.id).update(
                current_balance=F("current_balance") - amount,
                available_balance=F("available_balance") - amount,
                version=F("version") + 1
            )
            Balance.objects.filter(account_id=dest.id).update(
                current_balance=F("current_balance") + amount,
                available_balance=F("available_balance") + amount,
                version=F("version") + 1
            )

            # Mark transaction success
            txn.status = "success"
            txn.completed_at = timezone.now()
            txn.save()

            # Audit log
            AuditLog.objects.create(
                actor_id=source.user_id,
                action="transfer.completed",
                resource_type="transaction",
                resource_id=str(txn.id),
                after={"amount": float(amount), "source": source.id, "dest": dest.id}
            )

        # Outside transaction: publish event
        kafka_producer.send("transactions", {
            "txn_id": str(txn.id),
            "type": "transfer",
            "amount": float(amount),
            "source_user_id": source.user_id,
            "dest_user_id": dest.user_id,
        })

        return txn
```

### Why `SELECT FOR UPDATE`?
Prevents two concurrent transfers from the same account causing race condition.

### Why `F` expressions?
Atomic update at DB level: `UPDATE balances SET current_balance = current_balance - X`. Never load-then-write.

---

## 8. Idempotency (Non-Negotiable)

Every write API requires `Idempotency-Key` header.

```python
class IdempotencyMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.method != "POST":
            return None

        key = request.headers.get("Idempotency-Key")
        if not key:
            return JsonResponse({"error": "Idempotency-Key required"}, status=400)

        # Check cache
        cached = cache.get(f"idem:{key}")
        if cached:
            return JsonResponse(cached["body"], status=cached["status"])

        request.idempotency_key = key

    def process_response(self, request, response):
        if hasattr(request, "idempotency_key") and 200 <= response.status_code < 300:
            cache.set(f"idem:{request.idempotency_key}", {
                "body": json.loads(response.content),
                "status": response.status_code
            }, timeout=86400)  # 24h
        return response
```

Stripe's pattern. Critical.

---

## 9. Balance Reconciliation

Daily job: verify `balances` table matches sum of ledger entries.

```python
@shared_task
def reconcile_balances():
    accounts = Account.objects.filter(status="active")
    discrepancies = []

    for account in accounts:
        ledger_balance = LedgerEntry.objects.filter(account=account).aggregate(
            balance=Sum(
                Case(
                    When(entry_type="C", then=F("amount")),
                    When(entry_type="D", then=-F("amount")),
                )
            )
        )["balance"] or Decimal("0")

        cache_balance = Balance.objects.get(account=account).current_balance

        if abs(ledger_balance - cache_balance) > Decimal("0.0001"):
            discrepancies.append({
                "account_id": account.id,
                "ledger": float(ledger_balance),
                "cache": float(cache_balance),
                "diff": float(cache_balance - ledger_balance)
            })

    if discrepancies:
        send_alert("CRITICAL: Balance discrepancies", discrepancies)

    return discrepancies
```

**Best case:** zero discrepancies daily.

**If discrepancy:** stop transactions until investigated.

---

## 10. Transaction Reversal (Refund)

```python
class ReversalService:
    def reverse(self, original_txn_id: UUID, reason: str, idempotency_key: str):
        original = Transaction.objects.get(id=original_txn_id)

        if original.status != "success":
            raise CannotReverseError("Original transaction not successful")

        if Transaction.objects.filter(
            metadata__reversal_of=str(original.id),
            status="success"
        ).exists():
            raise AlreadyReversedError()

        # Create reverse transaction (swap source/dest)
        return self.transfer_service.transfer(
            source_account_id=original.dest_account_id,
            dest_account_id=original.source_account_id,
            amount=original.amount,
            idempotency_key=idempotency_key,
            description=f"Reversal of {original_txn_id}",
        )
```

Don't UPDATE the original. Don't UPDATE ledger entries. Create a new reverse transaction. Audit-friendly.

---

## 11. KYC Workflow

```python
class KYCSubmission(models.Model):
    STATUSES = [
        ("submitted", "Submitted"),
        ("in_review", "In Review"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("needs_more_info", "Needs More Info"),
    ]

    user = models.OneToOneField(User, on_delete=PROTECT)
    pan_doc_url = models.URLField()
    aadhaar_front_url = models.URLField()
    aadhaar_back_url = models.URLField()
    selfie_url = models.URLField()
    status = models.CharField(max_length=20, choices=STATUSES, default="submitted")
    rejection_reason = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True)
    reviewer = models.ForeignKey(User, related_name="kyc_reviewed", null=True, on_delete=SET_NULL)
```

### State machine (using `django-fsm`)

```python
from django_fsm import FSMField, transition

class KYCSubmission(models.Model):
    status = FSMField(default="submitted")

    @transition(field=status, source="submitted", target="in_review")
    def start_review(self, reviewer):
        self.reviewer = reviewer

    @transition(field=status, source="in_review", target="approved")
    def approve(self):
        self.user.kyc_status = "verified"
        self.user.kyc_level = 2
        self.user.save()
        # Trigger account activation
        send_kyc_approved_email.delay(self.user.id)

    @transition(field=status, source="in_review", target="rejected")
    def reject(self, reason):
        self.rejection_reason = reason
        # Notify user
        send_kyc_rejected_email.delay(self.user.id)
```

### Auto-KYC (ML-assisted)
Pass docs through:
- OCR: extract PAN number, name, DOB.
- Aadhaar verification: query UIDAI / DigiLocker API.
- Face match: selfie vs Aadhaar photo.
- PEP screening: politically exposed persons list.
- Sanctions lists: OFAC, UN.

Most pass automatically; flagged ones go to manual review.

---

## 12. Compliance & Audit

### Audit log invariants
- **Append-only:** No UPDATE / DELETE.
- **Tamper-evident:** Optional cryptographic hash chain.
- **Comprehensive:** Every sensitive action.

```python
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=Transaction)
def audit_transaction(sender, instance, created, **kwargs):
    AuditLog.objects.create(
        actor_id=instance.initiated_by_id,
        action=f"transaction.{'created' if created else 'updated'}",
        resource_type="transaction",
        resource_id=str(instance.id),
        after=model_to_dict(instance)
    )
```

### Suspicious Activity Reporting (SAR)
- Detect patterns: large transactions, rapid in/out, multiple small transactions to same account.
- Flag for review.
- File SAR with regulator if confirmed.

```python
@shared_task
def detect_suspicious_activity():
    # Velocity rule: > 10 transfers in 1 hour
    suspicious = Transaction.objects.filter(
        initiated_at__gte=now() - timedelta(hours=1)
    ).values("source_account").annotate(
        n=Count("id")
    ).filter(n__gt=10)

    for s in suspicious:
        flag_account_for_review(s["source_account"], reason="High velocity")
```

### Retention
- KYC docs: 5 years after account closure.
- Transactions: 10 years.
- Audit logs: 7 years.
- All data residency in India (or relevant jurisdiction).

---

## 13. Statements (PDF Generation)

```python
@shared_task
def generate_monthly_statement(account_id, year, month):
    account = Account.objects.get(id=account_id)
    user = account.user

    transactions = Transaction.objects.filter(
        Q(source_account=account) | Q(dest_account=account),
        initiated_at__year=year,
        initiated_at__month=month,
        status="success"
    ).order_by("initiated_at")

    opening = LedgerEntry.objects.filter(
        account=account,
        created_at__lt=datetime(year, month, 1)
    ).last()
    opening_balance = opening.balance_after if opening else 0

    context = {
        "user": user, "account": account,
        "transactions": transactions,
        "opening_balance": opening_balance,
        "month_year": f"{year}-{month:02d}",
    }

    html = render_to_string("statements/monthly.html", context)

    from weasyprint import HTML
    pdf = HTML(string=html).write_pdf()

    # Upload to S3
    s3_key = f"statements/{user.id}/{account_id}/{year}_{month:02d}.pdf"
    s3.put_object(Bucket="bank-statements", Key=s3_key, Body=pdf, ServerSideEncryption="AES256")

    # Email
    send_statement_email.delay(user.id, account_id, s3_key)

    return s3_key
```

Cron at end of each month: generate for all active accounts.

---

## 14. External Payment Integration

### UPI (India)
- Integration with NPCI / banks via PSP partner.
- VPA-based addressing (user@bank).
- Real-time payment.

```python
class UPIService:
    def initiate_payment(self, source_vpa, dest_vpa, amount, idempotency_key):
        # Call PSP partner API
        response = requests.post(
            "https://psp.example.com/upi/pay",
            json={
                "source": source_vpa,
                "dest": dest_vpa,
                "amount": float(amount),
                "ref_id": idempotency_key
            }
        )

        return response.json()

    def handle_callback(self, payload, signature):
        # Verify signature
        # Update transaction status based on payload
        ...
```

### NEFT / IMPS (India bank transfers)
- IMPS: real-time (24x7), instant.
- NEFT: batched, slow (sometimes 4h).
- Integration via partner bank API.

### Cards
- Hosted payment page (PCI scope minimization).
- Tokenization (don't store card numbers).
- 3D Secure / OTP authentication.

---

## 15. APIs

```
# Auth
POST   /auth/signup
POST   /auth/login                       (with 2FA if enabled)
POST   /auth/verify-2fa
POST   /auth/refresh

# KYC
POST   /kyc/submit                       (upload docs)
GET    /kyc/status

# Accounts
GET    /accounts
POST   /accounts                          (open new)
GET    /accounts/{id}
GET    /accounts/{id}/balance
DELETE /accounts/{id}                     (close)

# Transactions
GET    /transactions?from=&to=&type=    (with pagination)
POST   /transactions/transfer            { source_acc, dest_acc, amount } + Idempotency-Key
POST   /transactions/deposit             { account, amount, source } + Idempotency-Key
POST   /transactions/withdraw            { account, amount, dest_bank } + Idempotency-Key
GET    /transactions/{id}
POST   /transactions/{id}/reverse        (admin)

# Statements
GET    /accounts/{id}/statements         (list available)
GET    /accounts/{id}/statements/{ym}    (download PDF)

# Cards (if implementing)
GET    /cards
POST   /cards                            (issue virtual)
PATCH  /cards/{id}                       (freeze, set limits)

# Beneficiaries
GET    /beneficiaries
POST   /beneficiaries                    (add)
DELETE /beneficiaries/{id}

# Standing instructions (recurring)
POST   /standing-instructions

# Disputes
POST   /disputes                         (raise dispute)
GET    /disputes
```

---

## 16. Authentication & Security

### Multi-factor authentication
- Username + password.
- SMS OTP for sensitive actions.
- Biometric (mobile app).
- TOTP (Google Authenticator).

### Session management
- Short-lived JWT (15 min).
- Refresh token (7 days, single-use).
- Force logout on suspicious activity.

### Sensitive action confirmation
For transfers > ₹10K: OTP required even with valid session.

```python
@api_view(["POST"])
def transfer(request):
    if request.data["amount"] > 10000:
        # Verify recent OTP
        otp_session = OTPSession.objects.filter(
            user=request.user,
            verified=True,
            verified_at__gte=now() - timedelta(minutes=5)
        ).first()
        if not otp_session:
            return Response({"error": "OTP required"}, status=403)
    # ...
```

### Encryption
- TLS 1.3 only.
- Database at rest: AWS RDS encryption.
- Sensitive PII (Aadhaar) encrypted at column level.

---

## 17. Caching Strategy

| Cache | TTL |
|---|---|
| User profile | 5 min |
| Account list | 1 min |
| Balance | 10 sec (with `version` check for stale read) |
| Transaction history | 1 min (per filter set) |
| Statement PDF URL (S3 signed) | 1 hour |

**Balance caching is risky** — always source of truth = DB. Cache only "approximate balance for display"; for transactions, ALWAYS read fresh with `SELECT FOR UPDATE`.

---

## 18. Async Tasks (Celery)

### Tasks

```python
@shared_task(autoretry_for=(Exception,), max_retries=5)
def send_transaction_alert(txn_id):
    txn = Transaction.objects.get(id=txn_id)
    # Send SMS + email + push
    sms_service.send(txn.source_account.user.phone, format_sms(txn))
    email_service.send(...)
    push_service.send(...)

@shared_task
def daily_reconciliation():
    # Run reconcile_balances + alert if discrepancies
    pass

@shared_task
def generate_all_monthly_statements():
    for account in Account.objects.filter(status="active"):
        generate_monthly_statement.delay(account.id, last_month.year, last_month.month)

@shared_task
def expire_kyc_review():
    # KYC pending > 7 days → escalate
    pass

@shared_task
def standing_instruction_runner():
    # Execute due recurring transfers
    pass
```

### Schedule

```python
CELERY_BEAT_SCHEDULE = {
    "daily-reconciliation": {
        "task": "tasks.daily_reconciliation",
        "schedule": crontab(hour=2, minute=0),
    },
    "monthly-statements": {
        "task": "tasks.generate_all_monthly_statements",
        "schedule": crontab(day_of_month=1, hour=1, minute=0),
    },
    "standing-instructions": {
        "task": "tasks.standing_instruction_runner",
        "schedule": crontab(hour="*", minute=0),
    },
    "fraud-detection": {
        "task": "tasks.detect_suspicious_activity",
        "schedule": crontab(minute="*/15"),
    },
}
```

---

## 19. Deployment Architecture

### Production (AWS — India region)

```
                  ┌──────────────┐
                  │  Cloudflare  │
                  │  (with WAF)  │
                  └──────┬───────┘
                         │
                  ┌──────▼───────┐
                  │   ALB        │
                  └──────┬───────┘
                         │
       ┌─────────────────┼─────────────────┐
       ▼                 ▼                 ▼
   ┌────────┐       ┌────────┐       ┌────────┐
   │EKS Pod │       │EKS Pod │       │EKS Pod │
   │Django  │       │Django  │       │Celery  │
   └────┬───┘       └────┬───┘       └────┬───┘
        └────────┬───────┘                │
                 ▼                        │
        ┌────────────────┐                │
        │ RDS Postgres   │◄───────────────┘
        │  (Multi-AZ)    │
        │  + 3 Read Reps │
        └────────────────┘
                 │
        ┌────────▼────────┐
        │ ElastiCache     │
        │   Redis         │
        └─────────────────┘
                 │
        ┌────────▼────────┐
        │   Amazon MQ     │
        │  (RabbitMQ)     │
        └─────────────────┘
                 │
        ┌────────▼────────┐
        │      S3         │
        │ (statements,    │
        │  KYC docs)      │
        └─────────────────┘
```

### Security
- VPC with private subnets for DB.
- IAM roles per service.
- Secrets Manager for credentials.
- WAF rules for OWASP top 10.

---

## 20. Senior-Level Showcases

### A. Double-entry bookkeeping
Industry-standard accounting; reconcilable; auditable.

### B. ACID transactions with `SELECT FOR UPDATE`
Pessimistic locking; zero race conditions on balance.

### C. Idempotency on every write
Stripe-grade duplicate prevention.

### D. Atomic balance updates via `F` expressions
No load-then-save races.

### E. Immutable audit log
Append-only; partitioned by month; compliance-ready.

### F. Daily reconciliation
Self-validating system; alerts on discrepancy.

### G. State-machine workflows (KYC, disputes)
`django-fsm` enforces valid transitions.

### H. Column-level encryption for PII
Aadhaar, PAN encrypted at rest with separate key.

### I. Compliance-ready (PCI DSS, RBI)
Data residency, retention, encryption, access controls.

### J. Reversal pattern (never modify history)
Refund = new reverse transaction; original preserved.

---

## 21. Implementation Roadmap

### Week 1: Foundation
- [ ] Django project + DRF setup.
- [ ] User + Account models + admin.
- [ ] Basic auth (JWT).
- [ ] Simple deposit/withdraw (no double-entry yet).

### Week 2: Ledger + Idempotency
- [ ] Double-entry: ledger_entries table.
- [ ] Transfer service with `SELECT FOR UPDATE`.
- [ ] Idempotency middleware.
- [ ] Balance reconciliation script.

### Week 3: KYC + Workflows
- [ ] KYC submission with file upload (S3).
- [ ] State machine (django-fsm).
- [ ] Admin review interface.
- [ ] OTP verification flow.

### Week 4: Statements + Reporting
- [ ] Monthly statement generation (WeasyPrint).
- [ ] Excel export.
- [ ] Audit log queries.
- [ ] Dashboard for ops team.

### Week 5: External Integrations
- [ ] Mock UPI integration.
- [ ] Webhook handling.
- [ ] SMS/email notifications.
- [ ] Push notifications.

### Week 6: Production
- [ ] Multi-AZ Postgres.
- [ ] Secrets management.
- [ ] WAF rules.
- [ ] Load test 5K TPS.
- [ ] Compliance documentation.

---

## 22. Common Pitfalls & Solutions

### Pitfall 1: Lost money via race condition
**Symptom:** Concurrent transfers → balance off.
**Solution:** `SELECT FOR UPDATE` + `F` expressions, transaction isolation.

### Pitfall 2: Double-charge on retry
**Symptom:** Network blip; client retries; user charged twice.
**Solution:** Idempotency keys (Stripe pattern).

### Pitfall 3: Float arithmetic errors
**Symptom:** ₹0.30 + ₹0.40 = ₹0.6999999...
**Solution:** Use `Decimal`, never `float`. NUMERIC(15, 4) in DB.

### Pitfall 4: Audit log mutated
**Symptom:** Compliance violation.
**Solution:** Postgres triggers blocking UPDATE/DELETE on audit_log; partition + archive monthly.

### Pitfall 5: Currency conversion errors
**Symptom:** USD/INR exchange rates inconsistent across transactions.
**Solution:** Store rate at transaction time; never recompute historical.

### Pitfall 6: KYC docs leaked
**Symptom:** Aadhaar / PAN exposed.
**Solution:** S3 server-side encryption + presigned URLs only + retention policy.

### Pitfall 7: Database connection exhaustion under load
**Symptom:** All Django workers stuck.
**Solution:** PgBouncer in transaction mode + connection pool tuning.

---

## 23. Performance Benchmarks

| Metric | Target |
|---|---|
| Read p99 (balance, history) | < 100ms |
| Write p99 (transfer) | < 500ms |
| Reconciliation (5M accounts) | < 30 min |
| Statement generation (1 account) | < 10s |
| Concurrent users | 100K |
| Transactions/sec (sustained) | 1K |
| Transactions/sec (peak) | 5K |

---

## 24. Resume Bullets

- Built a fintech banking backend in Django with double-entry bookkeeping, ACID-guaranteed transactions via `SELECT FOR UPDATE`, and atomic balance updates supporting 5M users and 10M daily transactions.
- Implemented Stripe-style idempotency, daily ledger reconciliation, and immutable audit logs partitioned monthly — passed third-party security audit.
- Designed KYC workflow with state machine, automated OCR + face match, and manual review queue, achieving 80% auto-approval rate.

---

## 25. Interview Talking Points

- **"How do you ensure no money is lost in concurrent transfers?"** → SELECT FOR UPDATE + atomic F-expression updates + double-entry as self-check.
- **"What if the same transfer is requested twice (network retry)?"** → Idempotency key required; second request returns first's response.
- **"How do you handle a discrepancy between balance and ledger?"** → Daily reconcile job; alert ops; FREEZE transactions until investigated.
- **"How do you handle PCI DSS / compliance?"** → Don't store raw card data (tokenize); encrypt PII; immutable audit log; data residency.
- **"How do you reverse a transaction?"** → New reverse transaction; never edit original.
- **"Why double-entry?"** → Self-validating; sum of debits = sum of credits; reconcile-able.

---

## 26. Stretch Goals

- **Multi-currency:** Per-account currency; auto-conversion at txn time.
- **Cards (virtual + physical):** Via partner like Marqeta or Stripe Issuing.
- **Recurring billing / subscriptions.**
- **Lending:** Loans + EMIs + interest calculation.
- **Investments:** Stocks, mutual funds via partner brokerage.
- **International transfers:** SWIFT integration.
- **Crypto:** Wallet integration.
- **AI fraud detection:** Real-time scoring.
- **Open banking APIs:** Allow third-party access (with user consent).
- **Beneficiary verification:** Penny drop / IFSC validation.

---

## 27. Tech Stack Summary

| Layer | Choice | Why |
|---|---|---|
| **Framework** | Django + DRF | Mature, admin, ORM, security |
| **DB** | Postgres | ACID, NUMERIC type, partitioning |
| **Cache** | Redis | Idempotency, rate limit |
| **Queue** | Celery + RabbitMQ | Mature async |
| **Reports** | WeasyPrint | HTML → PDF for statements |
| **Storage** | S3 (encrypted) | KYC docs, statements |
| **State machine** | django-fsm | Workflow rules |
| **Auth** | JWT + 2FA | Multi-factor |
| **Encryption** | django-cryptography | Column-level PII encryption |
| **Compliance** | django-simple-history | Change tracking |
| **Monitoring** | Prometheus + Grafana + Sentry | Observability |

---

## TL;DR

- Banking backend in Django with double-entry bookkeeping.
- ACID via SELECT FOR UPDATE + F expressions; zero race conditions on balance.
- Idempotency on every write API.
- KYC state machine; daily reconciliation; immutable audit log.
- 5M users, 10M txns/day, 1K TPS sustained.
- 4-6 weeks build time.
- **Highest-resume-impact fintech project; demonstrates correctness rigor + compliance + complex domain.**
