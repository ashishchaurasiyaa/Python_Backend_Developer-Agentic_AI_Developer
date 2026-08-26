# Compliance — GDPR, PCI-DSS, HIPAA, SOC2 for Developers

## Quick Concepts

**WHAT:**
- **GDPR** = EU privacy regulation (2018) — protects EU residents
- **PCI-DSS** = Payment Card Industry Data Security Standard
- **HIPAA** = US health data privacy (Healthcare)
- **SOC2** = Service Organization Controls (audit framework)
- **Data Classification** = Public / Internal / Confidential / Restricted
- **PII** = Personally Identifiable Information
- **PHI** = Protected Health Information

---

## Andar kya hota hai — "Right to Erasure" Distributed System Mein Kaise Implement Hoti Hai, PCI Tokenization

### GDPR erasure — ek DELETE query kaafi nahi hai

```
User ka data kahan-kahan hai (production DB ke alawa):
  - Read replicas (async replicate hoke abhi tak nahi pahuncha ho sakta)
  - Backups (weekly/daily snapshots — un mein data still exists)
  - Caches (Redis mein TTL tak reh sakta hai)
  - Logs (application logs mein PII accidentally print hui ho sakti)
  - Analytics/data-warehouse pipelines (already copy ho chuka)

Real implementation: (1) production row ko SOFT-DELETE/anonymize turant,
  (2) ek scheduled JOB jo backups ke restore-time pe bhi erasure re-apply
  kare (ya backups ki apni retention/expiry policy erasure SLA ke andar
  ho), (3) cache INVALIDATE karo, (4) DATA MAPPING document rakho (yeh
  jaanna ki PII kahan-kahan store hoti hai, taaki erasure request aane
  par SAB jagah pata ho, guess na karna pade)
```

Isiliye "GDPR compliant hona" ek engineering DESIGN decision hai (data
mapping + erasure-propagation pipeline pehle se banani padti hai), request
aane ke baad scramble karna kaam nahi karta.

### PCI-DSS tokenization — ENCRYPTION nahi, kuch aur hai

```
Encryption: real card number ek KEY se encrypt hota hai — key ho to
  REVERSE (decrypt) kiya ja sakta hai. Key compromise = data compromise.

Tokenization: real card number PAYMENT PROCESSOR (Stripe/Razorpay) ke
  paas store hota hai. Tumhare system ko sirf ek TOKEN milta hai (jaise
  "tok_a1b2c3") jiska real card number se KOI MATHEMATICAL relationship
  nahi — yeh ek RANDOM reference hai processor ke apne vault mein.
```

Poora tumhara database breach ho jaaye, tokens kisi kaam ke nahi (koi key
nahi jo unhe "card number" mein wapas convert kar sake) — yehi wajah hai
tokenization encryption se STRONGER guarantee deta hai PCI scope ke liye:
tumhare system mein KABHI real card number aata hi nahi, isliye tumhara
system PCI audit scope se BAHAR ho sakta hai (processor apna scope khud
handle karta hai).
- **Right to be Forgotten** = GDPR Article 17

**WHY compliance matters:**
- ❌ GDPR fines: up to 4% global revenue or €20M
- ❌ PCI-DSS non-compliance: bank can revoke card processing
- ❌ HIPAA fines: $50K-$1.5M per violation
- ❌ No SOC2 = enterprise customers won't buy

**HOW compliance affects code:**

```
┌──────────────────────────────────────────────────┐
│  Data Collection                                  │
│  → Consent management, purpose limitation         │
├──────────────────────────────────────────────────┤
│  Data Storage                                     │
│  → Encryption at rest, classification, retention  │
├──────────────────────────────────────────────────┤
│  Data Processing                                  │
│  → Pseudonymization, audit logs                   │
├──────────────────────────────────────────────────┤
│  Data Transit                                     │
│  → TLS 1.2+, mTLS for internal                    │
├──────────────────────────────────────────────────┤
│  Data Deletion                                    │
│  → Right to be forgotten, automated cleanup       │
└──────────────────────────────────────────────────┘
```

---

## Interview Questions & Answers

### Q1: GDPR — backend developer ko kya implement karna hai?

**Answer:**

**WHAT:** EU regulation for data protection. Applies if you have EU users.

**Key principles:**

| Principle | What it means |
|---|---|
| **Lawfulness** | Have legal basis (consent, contract, legitimate interest) |
| **Purpose limitation** | Use data only for stated purpose |
| **Data minimization** | Collect only what's necessary |
| **Accuracy** | Keep data correct, allow corrections |
| **Storage limitation** | Delete when no longer needed |
| **Security** | Encrypt, access control |
| **Accountability** | Document everything |

**HOW — Article 17: Right to be Forgotten**

```python
@app.delete("/api/account/delete")
async def gdpr_delete_account(user=Depends(get_current_user)):
    """
    INTERVIEW: GDPR-compliant account deletion.
    Returns 200 once data marked for deletion.
    """
    user_id = user.id

    # ⭐ 1. Anonymize data (preserve audit trail integrity)
    await db.users.update(user_id, {
        "email": f"deleted-{user_id}@anonymous.local",
        "name": "DELETED USER",
        "phone": None,
        "address": None,
        "date_of_birth": None,
        "deleted_at": datetime.utcnow(),
        "is_active": False,
    })

    # ⭐ 2. Delete user-generated content (or anonymize)
    await db.posts.update_many(
        {"user_id": user_id},
        {"author_name": "Deleted User", "user_id": None}
    )

    # ⭐ 3. Delete media files from S3
    await s3.delete_objects(
        Bucket="user-uploads",
        Delete={"Objects": [{"Key": f"users/{user_id}/*"}]}
    )

    # ⭐ 4. Revoke all sessions/tokens
    await session_mgr.destroy_all_user_sessions(user_id)
    await db.refresh_tokens.revoke_all_for_user(user_id)

    # ⭐ 5. Remove from third-party services
    await stripe_client.delete_customer(user.stripe_id)
    await mailchimp_client.remove_subscriber(user.email)

    # ⭐ 6. Log deletion (audit, kept for compliance)
    await audit_log.log_security_event(
        event_type="data_deletion",
        user_id=user_id,
        action="gdpr_right_to_be_forgotten",
        result="success",
    )

    # ⭐ 7. Schedule hard delete after retention period (some data must be kept)
    await schedule_hard_delete(user_id, days=30)

    return {"status": "deletion_initiated"}


# Backup retention rules
# - Active user data: as needed for service
# - Deleted user data: 30 days (rollback period)
# - Financial records: 7 years (tax law)
# - Audit logs: forever (or as required)
```

**HOW — Article 20: Data Portability**

```python
@app.get("/api/account/export")
async def gdpr_data_export(user=Depends(get_current_user)):
    """
    User can download all their data in machine-readable format.
    """
    user_data = {
        "user": await db.users.get(user.id, anonymize=False),
        "orders": await db.orders.get_for_user(user.id),
        "posts": await db.posts.get_for_user(user.id),
        "comments": await db.comments.get_for_user(user.id),
        "payments": await db.payments.get_for_user(user.id),
        "audit_log": await db.audit_logs.get_for_user(user.id),
        "metadata": {
            "exported_at": datetime.utcnow().isoformat(),
            "format_version": "1.0",
        }
    }

    # Return as downloadable JSON
    from fastapi.responses import StreamingResponse
    import io
    json_bytes = json.dumps(user_data, indent=2, default=str).encode()

    return StreamingResponse(
        io.BytesIO(json_bytes),
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename=user-data-{user.id}.json"
        }
    )
```

**HOW — Article 7: Consent management**

```python
class ConsentManager:
    """
    INTERVIEW: Track user consent with version + timestamp.
    Must be:
    - Freely given
    - Specific (per purpose)
    - Informed
    - Unambiguous
    """
    CONSENT_PURPOSES = [
        "essential",            # Required for service
        "analytics",            # Optional analytics
        "marketing",            # Marketing emails
        "third_party_sharing",  # Sharing with partners
    ]

    async def record_consent(self, user_id: int, purpose: str, granted: bool, ip: str):
        await db.consents.create(
            user_id=user_id,
            purpose=purpose,
            granted=granted,
            granted_at=datetime.utcnow(),
            policy_version="v2.0",       # ⭐ Track which version
            ip_address=ip,
        )

    async def can_send_marketing(self, user_id: int) -> bool:
        consent = await db.consents.get_latest(user_id, purpose="marketing")
        return consent and consent.granted


# Middleware blocks if consent missing
@app.middleware("http")
async def check_consent_for_analytics(request: Request, call_next):
    response = await call_next(request)

    # Only set analytics cookies if consent
    if not await consent_mgr.can_use_analytics(request.user.id):
        # Remove analytics cookies, don't track
        pass

    return response
```

---

### Q2: PII handling — encryption + pseudonymization?

**Answer:**

**WHAT:**
- **PII** = Anything that identifies a person (email, name, phone, IP)
- **Pseudonymization** = Replace PII with tokens (reversible by authorized parties)
- **Anonymization** = Make impossible to re-identify

**HOW — Field-level encryption:**

```python
from cryptography.fernet import Fernet
import os

class FieldEncryption:
    """
    INTERVIEW: Encrypt sensitive fields before DB storage.
    Even if DB stolen, encrypted fields useless without key.
    """
    def __init__(self):
        # Key from Secrets Manager (NEVER hardcode)
        self.key = os.environ["FIELD_ENCRYPTION_KEY"].encode()
        self.cipher = Fernet(self.key)

    def encrypt(self, plaintext: str) -> str:
        if not plaintext:
            return ""
        return self.cipher.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        if not ciphertext:
            return ""
        return self.cipher.decrypt(ciphertext.encode()).decode()


# SQLAlchemy custom type
from sqlalchemy.types import TypeDecorator, String

class EncryptedString(TypeDecorator):
    """Custom column type that auto-encrypts."""
    impl = String

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.encryption = FieldEncryption()

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return self.encryption.encrypt(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return self.encryption.decrypt(value)


# Use in model
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, index=True)              # Searchable (not encrypted)
    ssn = Column(EncryptedString(500))              # ⭐ Auto-encrypted
    credit_card_last4 = Column(String)              # OK (last 4 only)
    address = Column(EncryptedString(1000))         # ⭐ Auto-encrypted
```

**HOW — Pseudonymization (separate identity table):**

```python
# Identity table: real PII
class UserIdentity(Base):
    __tablename__ = "user_identities"
    id = Column(Integer, primary_key=True)
    pseudonym_id = Column(String, unique=True)      # Random token
    email = Column(EncryptedString)
    name = Column(EncryptedString)
    phone = Column(EncryptedString)


# Activity table: only pseudonym
class UserActivity(Base):
    __tablename__ = "user_activities"
    id = Column(Integer, primary_key=True)
    pseudonym_id = Column(String, index=True)       # ⭐ Not real ID
    action = Column(String)
    timestamp = Column(DateTime)


# Analytics can join only via pseudonym (no real PII visible)
# Authorized service can map pseudonym → real identity
```

---

### Q3: PCI-DSS — payment data handling?

**Answer:**

**WHAT:** Security standards for handling credit card data.

**WHY:**
- Banks require it for card processing
- Fines + loss of payment privileges for violations
- 12 main requirements

**Key principle: DON'T STORE CARD DATA**
- Use payment tokenization (Stripe, Razorpay, Braintree)
- Never log full card numbers
- PAN (Primary Account Number) NEVER in plain text

**HOW — Stripe tokenization (recommended pattern):**

```python
# ❌ DO NOT do this
class Order(Base):
    card_number = Column(String)          # ❌ Full card number — PCI nightmare
    cvv = Column(String)                  # ❌ NEVER store CVV
    expiry = Column(String)


# ✅ DO this
class Order(Base):
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    amount = Column(Decimal)
    stripe_payment_intent_id = Column(String)    # ⭐ Reference only
    card_last4 = Column(String(4))               # ⭐ OK to store (display only)
    card_brand = Column(String)                   # "visa", "mc"
    status = Column(String)


import stripe

@app.post("/api/orders/{order_id}/pay")
async def create_payment_intent(order_id: int, user=Depends(get_user)):
    order = await db.orders.get(order_id)

    # ⭐ Stripe handles ALL card data — we never see it
    intent = stripe.PaymentIntent.create(
        amount=int(order.amount * 100),    # cents
        currency="usd",
        customer=user.stripe_customer_id,
        metadata={"order_id": order_id},
    )

    await db.orders.update(order_id, {
        "stripe_payment_intent_id": intent.id,
        "status": "awaiting_payment"
    })

    # Return client_secret for frontend
    return {"client_secret": intent.client_secret}


# Frontend uses Stripe.js — card data goes directly Stripe → bank
# Backend never sees card number
```

**HOW — Webhook verification (PCI-compliant):**

```python
@app.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    signature = request.headers.get("Stripe-Signature")

    try:
        # ⭐ Verify webhook signature (HMAC)
        event = stripe.Webhook.construct_event(
            payload,
            signature,
            os.environ["STRIPE_WEBHOOK_SECRET"]
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(401, "Invalid signature")

    if event.type == "payment_intent.succeeded":
        intent = event.data.object
        order_id = intent.metadata["order_id"]

        await db.orders.update(order_id, {
            "status": "paid",
            "paid_at": datetime.utcnow(),
            "card_last4": intent.charges.data[0].payment_method_details.card.last4,
        })

    return {"received": True}
```

**HOW — Logging best practices:**

```python
# ❌ NEVER log full card numbers
log.info("processing card", card="4242424242424242")    # ❌ PCI violation!

# ✅ Mask before logging
def mask_card(card_number: str) -> str:
    """Mask card to last 4."""
    return "****" + card_number[-4:]

log.info("processing card", card=mask_card("4242424242424242"))    # "****4242"

# ✅ Auto-redact in structlog
import re

def redact_card_numbers(logger, method_name, event_dict):
    """Structlog processor to redact PCI data."""
    for key, value in event_dict.items():
        if isinstance(value, str):
            # Match 13-19 digit numbers (card-like)
            event_dict[key] = re.sub(
                r"\b\d{13,19}\b",
                "[REDACTED-CARD]",
                value
            )
    return event_dict

structlog.configure(processors=[
    redact_card_numbers,
    # ... other processors
])
```

---

### Q4: SOC2 — type 1 vs type 2 + technical controls?

**Answer:**

**WHAT:**
- **SOC2** = Service Organization Controls 2 (AICPA audit)
- **Type 1** = Point-in-time (snapshot of controls)
- **Type 2** = Over period (6-12 months, controls actually working)

**Trust Service Criteria (TSCs):**

| TSC | What |
|---|---|
| **Security** | Protection against unauthorized access |
| **Availability** | System available as committed |
| **Processing Integrity** | Complete, valid, accurate |
| **Confidentiality** | Confidential info protected |
| **Privacy** | Personal info collected/used per policy |

**HOW — Technical controls developers implement:**

```python
# 1. Access Control (CC6.1)
# - MFA for admin accounts
# - Role-based access
# - Least privilege

# 2. Encryption (CC6.7)
# - TLS 1.2+ everywhere
# - Encryption at rest
# - Key rotation

# 3. Audit Logging (CC7.2)
# - Log all access to sensitive data
# - Centralize logs
# - Retention 1+ year

# 4. Change Management (CC8.1)
# - Code review required
# - CI/CD pipeline (no direct prod access)
# - Deployment audit trail

# 5. Vulnerability Management (CC7.1)
# - Regular dependency scans (safety, snyk)
# - Container scanning (Trivy)
# - Pen testing

# 6. Incident Response (CC7.3)
# - PagerDuty alerts
# - Runbooks
# - Post-mortem process

# 7. Business Continuity (A1.1)
# - Multi-AZ deployment
# - Database backups (tested!)
# - Disaster recovery plan
```

**HOW — Compliance-friendly logging:**

```python
class SOC2AuditLogger:
    """
    INTERVIEW: SOC2-required audit fields.
    """
    REQUIRED_EVENT_TYPES = [
        "user_login",
        "user_logout",
        "user_create",
        "user_delete",
        "permission_grant",
        "permission_revoke",
        "data_access",
        "data_modification",
        "data_deletion",
        "configuration_change",
        "deployment",
        "failed_authentication",
        "privilege_escalation",
    ]

    async def log(self, event_type: str, **kwargs):
        if event_type not in self.REQUIRED_EVENT_TYPES:
            log.warning(f"Unknown SOC2 event type: {event_type}")

        entry = {
            # ⭐ Required for SOC2 audit
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": kwargs.get("user_id"),
            "user_email": kwargs.get("user_email"),
            "source_ip": kwargs.get("source_ip"),
            "user_agent": kwargs.get("user_agent"),
            "action": kwargs.get("action"),
            "resource": kwargs.get("resource"),
            "result": kwargs.get("result"),  # success, failure, denied
            "details": kwargs.get("details", {}),
            # System
            "service": kwargs.get("service"),
            "environment": os.environ.get("ENV"),
            "request_id": kwargs.get("request_id"),
        }

        # 1. CloudWatch (real-time monitoring)
        cloudwatch_logger.info(json.dumps(entry))

        # 2. S3 (long-term retention — 7 years for SOC2)
        await self.archive_to_s3(entry)

        # 3. SIEM (security monitoring)
        await self.send_to_siem(entry)
```

---

### Q5: HIPAA — health data handling?

**Answer:**

**WHAT:** US regulation for Protected Health Information (PHI).

**WHO must comply:**
- Healthcare providers
- Health insurers
- Business associates (you, if you handle PHI for them)

**HOW — Technical requirements:**

```python
# 1. Access controls
# - Unique user identification
# - Automatic logoff
# - Encryption + decryption

# 2. Audit controls
# - Log all PHI access
# - Retain 6 years minimum

# 3. Integrity
# - PHI not altered/destroyed improperly
# - Use checksums, digital signatures

# 4. Transmission security
# - Encrypt in transit (TLS 1.2+)
# - Verify integrity


class HIPAACompliantAPI:
    """
    INTERVIEW: HIPAA-compliant patient data handling.
    """
    @app.get("/api/patients/{patient_id}/records")
    async def get_patient_records(
        patient_id: str,
        user=Depends(get_current_user)
    ):
        # ⭐ 1. Strict access control
        if not await self.can_access_patient(user, patient_id):
            await audit_log.log(
                event_type="phi_access_denied",
                user_id=user.id,
                resource=f"patient/{patient_id}",
                result="denied",
            )
            raise HTTPException(403, "Not authorized to access this patient")

        # ⭐ 2. Audit log (REQUIRED)
        await audit_log.log(
            event_type="phi_access",
            user_id=user.id,
            user_role=user.role,
            patient_id=patient_id,
            resource="medical_records",
            action="read",
            result="success",
        )

        records = await db.medical_records.get_for_patient(patient_id)

        # ⭐ 3. Minimum necessary (don't return more than needed)
        return [self.filter_for_user_role(r, user.role) for r in records]

    async def can_access_patient(self, user, patient_id) -> bool:
        # Various access rules:
        # - Patient themselves
        # - Patient's assigned doctor
        # - Doctor in same hospital department (if break-glass)
        # - Insurance company with explicit consent
        return await self.check_access_rules(user, patient_id)
```

---

### Q6: Data retention — automated cleanup?

**Answer:**

**WHAT:** Automatic deletion of data based on age/policy.

**WHY:**
- GDPR storage limitation principle
- Reduce breach impact (less data = less to leak)
- Lower storage costs

**HOW — Retention policy per data type:**

```python
RETENTION_POLICIES = {
    # User data — keep while active, delete on account closure
    "user_account": "until_deletion_request",

    # Audit logs — compliance often requires 1-7 years
    "audit_logs": timedelta(days=2555),    # 7 years

    # Session data — short
    "sessions": timedelta(days=30),

    # Webhook delivery attempts
    "webhook_logs": timedelta(days=90),

    # API access logs
    "access_logs": timedelta(days=365),

    # Soft-deleted records
    "soft_deleted": timedelta(days=30),    # 30-day rollback window

    # Application logs
    "app_logs": timedelta(days=90),

    # Backups
    "daily_backups": timedelta(days=30),
    "monthly_backups": timedelta(days=365),

    # Marketing data (with consent)
    "marketing": timedelta(days=730),      # 2 years

    # Financial records (tax law)
    "financial": timedelta(days=2555),     # 7 years
}


# Celery scheduled task
@celery_app.task
def cleanup_expired_data():
    """
    Runs daily at 2 AM.
    Hard-deletes data past retention.
    """
    now = datetime.utcnow()

    # Sessions
    cutoff = now - RETENTION_POLICIES["sessions"]
    db.sessions.delete_before(cutoff)

    # Webhook logs
    cutoff = now - RETENTION_POLICIES["webhook_logs"]
    db.webhook_logs.delete_before(cutoff)

    # Soft-deleted users → hard delete
    cutoff = now - RETENTION_POLICIES["soft_deleted"]
    expired_users = db.users.find_soft_deleted_before(cutoff)
    for user in expired_users:
        # Final scrub
        await delete_user_hard(user.id)

    # Audit log to S3, delete from primary DB
    cutoff = now - timedelta(days=90)        # Keep 3 months hot in DB
    old_logs = db.audit_logs.get_before(cutoff)
    for log in old_logs:
        await archive_to_s3(log)
    db.audit_logs.delete_before(cutoff)


# Schedule
celery_app.conf.beat_schedule = {
    "cleanup-expired-data": {
        "task": "tasks.cleanup_expired_data",
        "schedule": crontab(hour=2, minute=0),
    },
}
```

---

### Q7: Data classification — kya kahan jaa sakta?

**Answer:**

**WHAT:** Categorize data by sensitivity level.

**HOW — Classification scheme:**

| Level | Examples | Where allowed |
|---|---|---|
| **Public** | Marketing pages, blog posts | Anywhere |
| **Internal** | Engineering wikis, internal metrics | Internal services |
| **Confidential** | Customer emails, names, addresses | Encrypted, restricted access |
| **Restricted** | Passwords, SSN, payment data | Encrypted, audit logged |
| **Highly Restricted** | Cryptographic keys, biometrics | HSM, separate systems |

**HOW — Tag data in code:**

```python
from enum import Enum
from sqlalchemy import event

class DataClassification(Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    HIGHLY_RESTRICTED = "highly_restricted"


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    # ⭐ Tag columns with classification (via comment or metadata)
    name = Column(String, info={"classification": DataClassification.CONFIDENTIAL})
    email = Column(String, info={"classification": DataClassification.CONFIDENTIAL})
    ssn = Column(EncryptedString, info={"classification": DataClassification.RESTRICTED})


# Enforce rules in query layer
class QueryAuditMiddleware:
    """
    Log access to RESTRICTED+ fields.
    Block certain fields from being logged.
    """
    def __init__(self, db):
        event.listen(db.engine, "after_execute", self.audit_query)

    def audit_query(self, conn, clauseelement, multiparams, params, execution_options, result):
        # Check if query touches restricted fields
        for col in clauseelement.columns:
            if col.info.get("classification") == DataClassification.RESTRICTED:
                audit_log.log(
                    event_type="restricted_data_access",
                    table=clauseelement.table.name,
                    column=col.name,
                )
```

---

### Q8: Data Processing Agreement — third parties?

**Answer:**

**WHAT:** Contract with vendors who process your users' data.

**WHY required by GDPR:**
- Vendor = data processor
- You = data controller
- DPA defines responsibilities

**HOW — Common third parties + considerations:**

| Vendor | Type | Considerations |
|---|---|---|
| **Stripe** | Payment processor | PCI compliant, signed DPA |
| **SendGrid/Mailgun** | Email | Has user emails — DPA |
| **Datadog/Sentry** | Monitoring | May contain PII in logs — DPA |
| **AWS** | Cloud | DPA available, signs BAA for HIPAA |
| **Slack** | Internal comms | If used for customer support |
| **Google Analytics** | Analytics | DPA, anonymize IPs |
| **Auth0/Cognito** | Auth | Has user identities — DPA |

**HOW — Sub-processor list (transparency):**

```python
# Maintain public list of vendors processing user data
SUB_PROCESSORS = [
    {
        "name": "AWS",
        "purpose": "Infrastructure hosting",
        "location": "us-east-1, ap-south-1",
        "data_categories": ["all"],
        "dpa_url": "https://aws.amazon.com/compliance/data-protection/",
    },
    {
        "name": "Stripe",
        "purpose": "Payment processing",
        "location": "Global",
        "data_categories": ["email", "name", "billing_address"],
        "dpa_url": "https://stripe.com/legal/dpa",
    },
    {
        "name": "Sentry",
        "purpose": "Error tracking",
        "location": "US",
        "data_categories": ["user_id", "ip_address"],
        "dpa_url": "https://sentry.io/legal/dpa/",
    },
]

@app.get("/legal/sub-processors")
async def list_sub_processors():
    """Public page listing all data processors."""
    return SUB_PROCESSORS
```

---

## Compliance Checklist (All Frameworks)

```markdown
### Universal (Apply to Most)
- [ ] Encryption at rest (AWS KMS / disk encryption)
- [ ] Encryption in transit (TLS 1.2+)
- [ ] Access controls (RBAC + MFA for admin)
- [ ] Audit logging (all access to sensitive data)
- [ ] Long-term log retention (1-7 years)
- [ ] Incident response plan documented
- [ ] Regular security training

### GDPR
- [ ] Privacy policy with required clauses
- [ ] Consent management (per purpose)
- [ ] Data export endpoint
- [ ] Account deletion endpoint
- [ ] Cookie consent banner
- [ ] DPO appointed (if required)
- [ ] DPAs with all sub-processors
- [ ] Breach notification process (<72h)

### PCI-DSS
- [ ] NEVER store CVV
- [ ] NEVER store full PAN unencrypted
- [ ] Use payment tokenization (Stripe)
- [ ] PCI-DSS compliant network (segmented)
- [ ] Annual security testing
- [ ] Logs retained 1 year

### HIPAA
- [ ] BAA with AWS / cloud providers
- [ ] Encrypt PHI in transit + rest
- [ ] Audit logs 6+ years
- [ ] Automatic logoff
- [ ] Access controls per-patient
- [ ] Breach notification process

### SOC2 Type 2
- [ ] Code review required for all changes
- [ ] No direct production access
- [ ] Multi-AZ deployment
- [ ] Tested backups
- [ ] Vendor risk reviews
- [ ] Security awareness training
- [ ] Quarterly access reviews
- [ ] Vulnerability scanning weekly
```

---

## Quick Compliance Reference

| Compliance | Industry | Geography | Key Penalty |
|---|---|---|---|
| **GDPR** | All (if EU users) | EU | 4% revenue or €20M |
| **CCPA** | All (if CA users) | California, USA | $7500 per violation |
| **PCI-DSS** | Payments | Global | Bank fines + revocation |
| **HIPAA** | Healthcare | USA | $50K-$1.5M per violation |
| **SOC2** | B2B SaaS | Global (USA-driven) | Lost enterprise deals |
| **ISO 27001** | All | Global | Certification loss |
| **FedRAMP** | US government | USA | Lost gov contracts |
