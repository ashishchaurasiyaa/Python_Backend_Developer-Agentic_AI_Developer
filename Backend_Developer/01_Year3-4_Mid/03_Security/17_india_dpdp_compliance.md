# Security — India DPDP Act 2023 Compliance for Backend Devs
**Security · Year 3-4 | Senior Backend + Agentic AI**

## Quick Concepts
- **DPDP Act** = Digital Personal Data Protection Act, 2023 — India's primary data protection law (operative 2025)
- **Data Principal** = individual whose data is processed (your users)
- **Data Fiduciary** = entity processing data (your company)
- **Significant Data Fiduciary (SDF)** = large-volume processors (extra obligations)
- **Data Processor** = third party processing on behalf of Fiduciary
- **Consent Manager** = registered entity that manages user consents
- **DPB** = Data Protection Board of India (regulator)
- **Penalty** = up to **₹250 crore** per violation
- **Localization** = certain data must stay in India (notified categories)

---

## Why Every Indian Backend Dev Must Know This

```
Penalties for non-compliance:
─────────────────────────
• Failure to prevent data breach          → up to ₹250 crore
• Failure to notify breach to DPB + users → up to ₹200 crore
• Failure to fulfill obligations to children → up to ₹200 crore
• Non-compliance with SDF duties           → up to ₹150 crore
• Breach of any other provision            → up to ₹50 crore
```

**Your code = compliance surface area.** Every API endpoint, log line, DB column is potentially regulated.

---

## DPDP vs GDPR — Quick Comparison

| Aspect | DPDP (India) | GDPR (EU) |
|---|---|---|
| Effective | 2023 (rules 2025) | 2018 |
| Penalty max | ₹250 cr (~$30M) | 4% global revenue or €20M |
| Consent | Free, specific, informed | Same |
| Right to be forgotten | Right to erasure (similar) | Right to erasure |
| Data localization | Sector-specific | None |
| Children's data | < 18 yrs (vs GDPR's 16) | < 16 yrs |
| Cross-border transfer | Whitelist countries (govt notified) | Adequacy decisions |
| Breach notification | "As soon as possible" to DPB + Principal | 72 hours to DPA |

---

## Interview Questions & Answers

### Q1: DPDP ke 5 core obligations kya hain backend dev ke liye?

**Answer:**

1. **Lawful processing** — consent or legitimate use (e.g., employment, govt service)
2. **Purpose limitation** — collect only what's needed for stated purpose
3. **Data minimization** — don't store extra fields "just in case"
4. **Storage limitation** — delete when purpose fulfilled
5. **Security safeguards** — "reasonable security" (encryption, access control)
6. **Breach notification** — report to DPB + Principal ASAP
7. **Rights fulfillment** — access, correction, erasure, grievance redressal
8. **Children's data** — parental consent mandatory; no profiling/tracking under 18

---

### Q2: Consent management — implementation pattern?

**Answer:** Consent must be **free, specific, informed, unconditional, unambiguous, with affirmative action** (no pre-ticked boxes).

```python
# Schema
CREATE TABLE consents (
    id UUID PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    purpose TEXT NOT NULL,                  -- "marketing_email", "analytics_tracking"
    purpose_version INT NOT NULL,            -- bump when wording changes
    granted BOOLEAN NOT NULL,
    granted_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,                  -- NULL if active
    notice_shown_text TEXT NOT NULL,         -- exact text user saw
    notice_language TEXT NOT NULL,           -- DPDP requires Indian languages too
    ip_address INET,
    user_agent TEXT,
    consent_artifact JSONB                   -- signed proof
);
CREATE INDEX idx_consents_user_purpose ON consents(user_id, purpose) WHERE revoked_at IS NULL;

CREATE TABLE consent_notices (
    id UUID PRIMARY KEY,
    purpose TEXT NOT NULL,
    version INT NOT NULL,
    text_en TEXT NOT NULL,
    text_hi TEXT NOT NULL,                   -- Hindi required
    text_other JSONB,                        -- {bn, ta, te, mr, gu, ...} — DPDP requires 22 scheduled languages on request
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (purpose, version)
);
```

```python
# Pydantic models
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID, uuid4

class ConsentGrant(BaseModel):
    user_id: int
    purpose: str = Field(..., description="Specific, narrowly-scoped purpose")
    notice_version: int
    language: str = Field("en", pattern="^(en|hi|bn|ta|te|mr|gu|kn|ml|pa|or|as|sa|ks|sd|kok|mai|brx|sat|doi|mni|ne|ur)$")
    granted: bool

@app.post("/consents")
async def grant_consent(
    consent: ConsentGrant,
    request: Request,
    user: User = Depends(get_current_user),
):
    # Verify notice exists
    notice = await db.fetch_one(
        "SELECT * FROM consent_notices WHERE purpose = :p AND version = :v",
        {"p": consent.purpose, "v": consent.notice_version},
    )
    if not notice:
        raise HTTPException(400, "Invalid consent notice")

    # Create immutable consent artifact
    artifact = {
        "user_id": user.id,
        "purpose": consent.purpose,
        "notice_version": consent.notice_version,
        "notice_text": getattr(notice, f"text_{consent.language}"),
        "granted": consent.granted,
        "timestamp": datetime.utcnow().isoformat(),
        "ip": request.client.host,
        "user_agent": request.headers.get("user-agent"),
    }
    # Sign with HMAC for tamper-evidence
    artifact["signature"] = sign_hmac(artifact, settings.CONSENT_HMAC_KEY)

    consent_id = uuid4()
    await db.execute(
        """
        INSERT INTO consents (id, user_id, purpose, purpose_version, granted, granted_at, notice_shown_text, notice_language, ip_address, user_agent, consent_artifact)
        VALUES (:id, :uid, :p, :v, :g, NOW(), :text, :lang, :ip, :ua, :art)
        """,
        {
            "id": consent_id,
            "uid": user.id,
            "p": consent.purpose,
            "v": consent.notice_version,
            "g": consent.granted,
            "text": artifact["notice_text"],
            "lang": consent.language,
            "ip": request.client.host,
            "ua": request.headers.get("user-agent"),
            "art": json.dumps(artifact),
        },
    )
    return {"id": consent_id, "status": "recorded"}

# Check consent before processing
async def has_consent(user_id: int, purpose: str) -> bool:
    result = await db.fetch_one(
        """
        SELECT granted FROM consents
        WHERE user_id = :uid AND purpose = :p AND revoked_at IS NULL
        ORDER BY granted_at DESC LIMIT 1
        """,
        {"uid": user_id, "p": purpose},
    )
    return result and result.granted

# Enforce in business logic
@app.post("/marketing/send-email")
async def send_marketing_email(req: EmailReq, user: User = Depends(get_user)):
    if not await has_consent(user.id, "marketing_email"):
        raise HTTPException(403, "User has not consented to marketing emails")
    await email_service.send(...)
```

---

### Q3: Right to erasure (deletion) — kaise implement karte hain?

**Answer:** User can request deletion; you have ~30 days. Must cascade to all systems.

```python
@app.delete("/users/me")
async def delete_my_account(
    user: User = Depends(get_current_user),
    confirmation: str = Body(..., regex="^DELETE-MY-ACCOUNT$"),
):
    # 1. Create deletion request (don't delete immediately — 7 day cooling off)
    request_id = uuid4()
    await db.execute(
        """
        INSERT INTO deletion_requests (id, user_id, requested_at, scheduled_for, status)
        VALUES (:id, :uid, NOW(), NOW() + INTERVAL '7 days', 'pending')
        """,
        {"id": request_id, "uid": user.id},
    )

    # 2. Disable account immediately
    await db.execute("UPDATE users SET status = 'pending_deletion' WHERE id = :id", {"id": user.id})

    # 3. Schedule background job
    await celery_app.send_task("execute_deletion", args=[str(request_id)], eta=datetime.utcnow() + timedelta(days=7))

    return {"status": "scheduled", "deletion_date": (datetime.utcnow() + timedelta(days=7)).isoformat()}

@celery_app.task
def execute_deletion(request_id: str):
    """Cascade delete across all systems."""
    user_id = get_user_id(request_id)

    # Order matters — most recent activity first
    deletion_plan = [
        # Application data
        ("DELETE FROM messages WHERE user_id = :uid", {"uid": user_id}),
        ("DELETE FROM orders WHERE user_id = :uid", {"uid": user_id}),
        ("DELETE FROM sessions WHERE user_id = :uid", {"uid": user_id}),

        # PII fields — anonymize instead if needed for analytics
        ("UPDATE audit_logs SET user_id = NULL, ip_address = '0.0.0.0' WHERE user_id = :uid", {"uid": user_id}),
        ("UPDATE payments SET user_email = NULL WHERE user_id = :uid", {"uid": user_id}),

        # Finally, user record
        ("DELETE FROM users WHERE id = :uid", {"uid": user_id}),
    ]

    for sql, params in deletion_plan:
        db.execute(sql, params)

    # External systems (must propagate!)
    delete_from_elasticsearch(user_id)
    delete_from_s3(f"users/{user_id}/")
    delete_from_kafka_compacted_topics(user_id)
    delete_from_third_party("intercom", user_id)
    delete_from_third_party("segment", user_id)
    delete_from_third_party("mixpanel", user_id)

    # Tombstone for audit (keep deletion_request, not user data)
    db.execute(
        "UPDATE deletion_requests SET status = 'completed', completed_at = NOW() WHERE id = :id",
        {"id": request_id},
    )

    # Notify user
    send_email(get_email_before_delete(user_id), "Your data has been deleted")
```

**Edge cases:**
- **Legal hold** — financial records (RBI mandates 8-10 yr retention) override deletion
- **Pending transactions** — can't delete user with open orders
- **Audit logs** — anonymize (replace `user_id` with hash) instead of delete
- **Backups** — cannot delete from snapshots; document retention + expiry

---

### Q4: Data localization requirements?

**Answer:** DPDP allows govt to notify specific countries as restricted. RBI/SEBI separately mandate Indian localization for financial data.

```python
# Region routing based on data type
DATA_LOCALIZATION_RULES = {
    "payment_data": ["IN"],                   # RBI: must stay in India
    "health_records": ["IN"],                 # NDHM guidelines
    "telecom_records": ["IN"],                # DoT/TRAI
    "general_pii": ["IN", "SG", "US-WEST-2"],  # less restrictive (depends on govt notification)
    "analytics_anon": ["*"],                   # anonymized = no restriction
}

def get_storage_region(user_country: str, data_type: str) -> str:
    """Pick region respecting localization."""
    if user_country == "IN":
        allowed = DATA_LOCALIZATION_RULES.get(data_type, ["IN"])
        return "ap-south-1" if "IN" in allowed else allowed[0]
    # Non-Indian users — flexible
    return choose_nearest_region(user_country)

# Sharding pattern
class StorageRouter:
    REGION_DBS = {
        "ap-south-1": "postgresql://india-db.acme.com",  # Mumbai
        "ap-south-2": "postgresql://hyderabad-db.acme.com",  # Hyderabad (backup)
        "us-east-1": "postgresql://us-db.acme.com",
    }

    async def get_db(self, user_id: int, data_type: str):
        user = await load_user(user_id)
        region = get_storage_region(user.country, data_type)
        return await get_connection(self.REGION_DBS[region])

# Enforce in middleware
@app.middleware("http")
async def localization_middleware(request: Request, call_next):
    user = request.state.user
    if user and user.country == "IN":
        # Indian user data MUST go to ap-south-1
        request.state.db_region = "ap-south-1"
    response = await call_next(request)
    return response
```

**RBI Payment Data Localization (2018):**
- Full transaction data must be stored ONLY in India
- Foreign processing allowed only for cross-border txns
- Foreign copy must be deleted within 24 hours

---

### Q5: Breach notification workflow?

**Answer:** "As soon as possible" — interpret as < 72 hours like GDPR. Must notify DPB + affected Principals.

```python
class BreachIncident(BaseModel):
    detected_at: datetime
    breach_type: str           # "unauthorized_access", "data_loss", "ransomware", "leak"
    affected_user_count: int
    data_categories: list[str] # "name", "email", "phone", "financial", "health"
    root_cause: str
    remediation: str
    affected_user_ids: list[int]

async def report_breach(incident: BreachIncident):
    """DPDP-compliant breach response."""

    # 1. Internal log (immutable)
    breach_id = uuid4()
    await db.execute(
        """
        INSERT INTO breach_log (id, detected_at, type, affected_count, categories, root_cause, remediation, status)
        VALUES (:id, :dt, :t, :cnt, :cats, :rc, :rem, 'investigating')
        """,
        {
            "id": breach_id,
            "dt": incident.detected_at,
            "t": incident.breach_type,
            "cnt": incident.affected_user_count,
            "cats": json.dumps(incident.data_categories),
            "rc": incident.root_cause,
            "rem": incident.remediation,
        },
    )

    # 2. Notify Data Protection Board (within 72h)
    # DPB has online portal — submit electronically
    await dpb_client.submit_breach_report({
        "fiduciary_name": "Acme India Pvt Ltd",
        "fiduciary_address": "...",
        "dpo_contact": "dpo@acme.com",
        "breach_id": str(breach_id),
        "incident_at": incident.detected_at.isoformat(),
        "discovered_at": datetime.utcnow().isoformat(),
        "data_categories": incident.data_categories,
        "principals_affected_count": incident.affected_user_count,
        "harm_likelihood": "high|medium|low",
        "remediation_taken": incident.remediation,
        "language_codes": ["en", "hi"],  # bilingual notice
    })

    # 3. Notify each affected Data Principal
    for user_id in incident.affected_user_ids:
        user = await load_user(user_id)
        # Send via primary contact method (email/SMS/in-app)
        notice = render_breach_notice(
            user_lang=user.preferred_language,
            incident=incident,
            steps_user_should_take=[
                "Change your password immediately",
                "Enable 2FA if not already",
                "Monitor your accounts for unusual activity",
            ],
        )
        await send_notification(user.id, "Important: Data Breach Notice", notice)

    # 4. Public notice (if large breach)
    if incident.affected_user_count > 10_000:
        await publish_public_advisory(incident)

    # 5. Cooperate with DPB investigation
    await preserve_evidence(breach_id)
```

---

### Q6: Children's data (< 18 yrs) — special handling?

**Answer:** Parental consent mandatory. NO profiling, behavioral monitoring, targeted advertising.

```python
# Age gate
@app.post("/users/signup")
async def signup(req: SignupRequest):
    age = calculate_age(req.date_of_birth)

    if age < 18:
        # Children flow — require parental consent
        parental_consent_token = uuid4()
        await db.execute(
            """
            INSERT INTO pending_parental_consents (token, child_email, child_name, dob, requested_at)
            VALUES (:t, :e, :n, :d, NOW())
            """,
            {"t": str(parental_consent_token), "e": req.email, "n": req.name, "d": req.date_of_birth},
        )
        # Send consent request to parent
        await send_email(
            req.parent_email,
            f"Approve {req.name}'s account at Acme",
            consent_link=f"https://acme.com/consent/{parental_consent_token}",
        )
        return {"status": "pending_parental_consent"}

    # Adult flow — normal signup
    return await create_user(req)

# Restrictions for child accounts
class ChildAccountMiddleware:
    async def __call__(self, request: Request, call_next):
        user = request.state.user
        if user and user.is_child:
            # Block these features
            blocked_paths = [
                "/analytics/track",
                "/ads/personalized",
                "/recommendations/personalized",
                "/profile/build-shadow-profile",
            ]
            if any(request.url.path.startswith(p) for p in blocked_paths):
                raise HTTPException(403, "Feature not available for minors")
        return await call_next(request)

# Verifiable parental consent (must be auditable)
CREATE TABLE parental_consents (
    id UUID PRIMARY KEY,
    child_user_id BIGINT REFERENCES users(id),
    parent_name TEXT,
    parent_email TEXT,
    parent_phone TEXT,
    verification_method TEXT,  -- "digilocker", "aadhaar_otp", "credit_card_charge", "signed_pdf"
    verified_at TIMESTAMPTZ,
    verification_artifact JSONB,
    revoked_at TIMESTAMPTZ
);
```

**Acceptable verification methods (US COPPA-influenced, DPDP rules pending):**
- DigiLocker-based age verification
- Aadhaar OTP via Parent's Aadhaar (UIDAI flow)
- Credit card micro-charge (parent's card)
- Signed PDF + ID proof upload

---

### Q7: DPO (Data Protection Officer) — when required + what they do?

**Answer:** Significant Data Fiduciary (SDF) MUST appoint a DPO. Threshold = volume + sensitivity (notified by DPB).

```python
# Estimated SDF criteria (to be notified):
# - > 5M Indian users
# - Sensitive data processing (health, financial, biometric)
# - Children's data at scale
# - Cross-border transfers

# DPO Responsibilities (must be exposed in your platform):
# - Public contact info for users
# - Grievance handling
# - DPB liaison
# - Internal compliance audits

@app.get("/grievance/contact")
async def dpo_contact():
    """Required public endpoint."""
    return {
        "dpo_name": "Priya Sharma",
        "dpo_email": "dpo@acme.com",
        "dpo_phone": "+91-22-XXXXXXXX",
        "dpo_address": "Acme India Pvt Ltd, ...",
        "grievance_portal": "https://acme.com/grievance",
        "response_sla_days": 30,
        "languages_supported": ["en", "hi", "ta", "te"],
    }

# Grievance flow
@app.post("/grievance/submit")
async def submit_grievance(req: GrievanceRequest):
    grievance_id = uuid4()
    await db.execute(
        """
        INSERT INTO grievances (id, user_id, category, description, submitted_at, status, response_due)
        VALUES (:id, :uid, :cat, :desc, NOW(), 'open', NOW() + INTERVAL '30 days')
        """,
        {
            "id": grievance_id,
            "uid": req.user_id,
            "cat": req.category,  # "consent", "access", "deletion", "correction", "breach"
            "desc": req.description,
        },
    )

    # Notify DPO
    await notify_dpo(grievance_id, urgency="normal")

    return {
        "id": grievance_id,
        "ack_message": "Grievance received. Response within 30 days.",
        "tracking_url": f"https://acme.com/grievance/{grievance_id}",
    }
```

---

### Q8: Compliance audit checklist for your codebase?

**Answer:** Run quarterly. Document everything.

```markdown
# DPDP Compliance Audit Checklist

## 1. Data Mapping
- [ ] List all tables containing PII
- [ ] Document purpose for each PII column
- [ ] Identify data flows (intake, processing, sharing, deletion)
- [ ] Map third-party processors (Stripe, Twilio, AWS, etc.)
- [ ] Document data residency (which region stores what)

## 2. Lawful Basis
- [ ] Every collection has documented lawful basis
- [ ] Consent records exist for consent-based processing
- [ ] Legitimate use justifications written (employment, govt service)
- [ ] No "creep" — fields not in original purpose are removed

## 3. Consent Implementation
- [ ] Consent notices in English + at least Hindi
- [ ] No pre-ticked checkboxes
- [ ] Granular per-purpose consent (not bundled)
- [ ] Easy withdrawal mechanism
- [ ] Withdrawal as easy as grant
- [ ] Consent versioning + re-prompt on changes

## 4. Rights Implementation
- [ ] /me/data endpoint exports user's data (machine-readable)
- [ ] /me/correct endpoint accepts corrections
- [ ] /me/delete endpoint triggers deletion workflow
- [ ] /grievance endpoint files complaints
- [ ] SLA: 30 days response for all requests

## 5. Security
- [ ] Encryption at rest (TDE / column-level for PII)
- [ ] Encryption in transit (TLS 1.3)
- [ ] Access logs for all PII reads
- [ ] Least-privilege IAM
- [ ] MFA for admin access
- [ ] Regular security audits (SAST/DAST)

## 6. Children
- [ ] Age gate at signup
- [ ] Parental consent flow
- [ ] No profiling / targeted ads for < 18
- [ ] Stricter security for child accounts

## 7. Breach Response
- [ ] Detection mechanism (IDS/anomaly)
- [ ] Runbook for breach scenarios
- [ ] DPB notification template ready
- [ ] User notification template (bilingual)
- [ ] Drills run quarterly

## 8. Documentation
- [ ] Privacy Notice (current, dated, signed)
- [ ] Internal Privacy Policy (employee-facing)
- [ ] DPO appointment letter (if SDF)
- [ ] DPIA (Data Protection Impact Assessment) for high-risk processing
- [ ] Data Processing Agreements with processors

## 9. Cross-border
- [ ] List countries data is transferred to
- [ ] Each transfer falls in whitelist OR has explicit consent
- [ ] Standard Contractual Clauses (SCCs) with processors

## 10. Vendors
- [ ] DPA signed with each data processor
- [ ] Processor compliance verified
- [ ] Sub-processor approval process
```

---

## Implementation Patterns

### Per-column encryption for PII

```python
from cryptography.fernet import Fernet
from sqlalchemy.types import TypeDecorator, String

# Generate key once, store in AWS Secrets Manager / Vault
ENCRYPTION_KEY = os.environ["DPDP_PII_KEY"]
cipher = Fernet(ENCRYPTION_KEY)

class EncryptedString(TypeDecorator):
    """SQLAlchemy column type — auto encrypt/decrypt."""
    impl = String

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return cipher.encrypt(value.encode()).decode()

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return cipher.decrypt(value.encode()).decode()

# Usage
class User(Base):
    id = Column(Integer, primary_key=True)
    email = Column(EncryptedString(500))           # encrypted at rest
    phone = Column(EncryptedString(50))            # encrypted at rest
    aadhaar_last_4 = Column(EncryptedString(20))   # never store full Aadhaar!
    pan = Column(EncryptedString(50))
```

### Access audit logging

```python
@app.middleware("http")
async def pii_access_audit(request: Request, call_next):
    response = await call_next(request)

    # Log every PII access for compliance
    if request.url.path.startswith(("/users/", "/admin/users/")):
        await audit_log({
            "actor_id": request.state.user.id if request.state.user else None,
            "action": f"{request.method} {request.url.path}",
            "target_user_id": extract_user_id(request.url.path),
            "ip": request.client.host,
            "timestamp": datetime.utcnow().isoformat(),
            "result": "success" if response.status_code < 400 else "denied",
        })

    return response
```

---

## Production Gotchas

| Gotcha | Fix |
|---|---|
| Consent in pre-ticked checkbox | Use opt-in only; explicit user action |
| Bundled consent ("agree to all") | Granular per purpose |
| Hidden data sharing with 3rd parties | List every processor in notice |
| Backups contain deleted user data | Document retention; tombstone in restore |
| Logs leak PII | Sanitize logger; PII redaction middleware |
| Email IDs in error messages | Generic error responses |
| Aadhaar stored fully | Store only last 4 + hash; never full number |
| Cross-border transfer without consent | Check whitelist; get explicit consent |
| Children's birthdates not verified | Robust age verification |
| Forgot to expose DPO contact | Mandatory public page |

---

## Senior-level Checklist

- [ ] Data Protection Officer (DPO) appointed if SDF
- [ ] Privacy Notice in English + Hindi + scheduled languages on request
- [ ] Consent system with granular purposes + versioning
- [ ] Right to access endpoint (export user data)
- [ ] Right to correction endpoint
- [ ] Right to erasure endpoint with cascade deletion
- [ ] Grievance redressal portal with 30-day SLA
- [ ] Breach detection + 72-hour notification workflow
- [ ] Children's data protection (age gate, parental consent, no profiling)
- [ ] PII encryption at rest (column-level)
- [ ] PII access audit logs
- [ ] Cross-border transfer compliance (whitelist or consent)
- [ ] Data localization for financial/health data (Indian servers)
- [ ] DPA (Data Processing Agreement) with every processor
- [ ] Quarterly compliance audit
- [ ] DPIA (Data Protection Impact Assessment) for high-risk processing
- [ ] Annual compliance training for engineers

---

## Penalties Summary (₹ in crore)

| Violation | Max Fine |
|---|---|
| Fail to prevent breach | **250** |
| Fail to notify breach | **200** |
| Children's data violation | **200** |
| SDF obligation failure | **150** |
| Any other DPDP breach | **50** |

**For a startup**: even ₹50 cr can shut you down. **Compliance is cheaper than penalty.**

---

## Related Docs
- `08_secrets_management_advanced.md` — encryption keys
- `11_compliance_gdpr_pci.md` — international standards
- `00_Year0-2_Junior/06_FastAPI/06_security_jwt_rbac.md` — auth foundation
- `00_Year0-2_Junior/06_FastAPI/33_prompt_injection_security.md` — AI-era security
- `01_Year3-4_Mid/04_DevOps/15_multi_region_deployment.md` — data localization infra

## External References
- DPDP Act 2023 official PDF: https://www.meity.gov.in/data-protection-framework
- MeitY DPDP page: https://www.meity.gov.in
- RBI Data Localization circular: https://www.rbi.org.in
- Comparison with GDPR: https://gdpr.eu (for cross-reference)
