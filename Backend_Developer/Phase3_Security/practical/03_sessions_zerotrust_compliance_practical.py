"""
Phase3_Security — Session Mgmt + Zero Trust + Compliance Practical
=====================================================================
Topics covered:
  1. Secure session cookie setup
  2. Redis-backed session manager
  3. Session fixation prevention (regenerate on login)
  4. Multi-device session management
  5. Global logout (destroy all sessions)
  6. Remember me with token rotation
  7. mTLS server + client patterns
  8. JWT propagation in microservices
  9. GDPR right-to-be-forgotten implementation
  10. PII field-level encryption
  11. Audit logging for SOC2
  12. Data classification + retention

Run:
  python 03_sessions_zerotrust_compliance_practical.py
"""

import asyncio
import hashlib
import hmac
import json
import secrets
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Secure Session Cookies
# INTERVIEW: HttpOnly + Secure + SameSite
# ─────────────────────────────────────────────────────────────────────────────

SECURE_COOKIE_CONFIG = """
# FastAPI secure cookie example
from fastapi import Response

def set_session_cookie(response: Response, session_id: str):
    response.set_cookie(
        key="__Host-session",        # ⭐ __Host- prefix = strictest
        value=session_id,
        httponly=True,                # ⭐ XSS defense (JS can't read)
        secure=True,                  # ⭐ HTTPS only
        samesite="strict",            # ⭐ CSRF defense
        max_age=86400,                # 24 hours
        path="/",
        # NO domain (__Host- requires this)
    )

# Django settings.py
SESSION_COOKIE_NAME = "sessionid"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 86400
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Redis-Backed Session Manager
# INTERVIEW: Multi-instance support
# ─────────────────────────────────────────────────────────────────────────────

class InMemorySessionStore:
    """Simulates Redis (for demo). In production: use Redis."""
    def __init__(self):
        self._data: dict = {}
        self._user_sessions: dict = {}  # user_id → set of session_ids
        self._expirations: dict = {}

    async def get(self, key: str):
        # Check expiration
        if key in self._expirations and self._expirations[key] < time.time():
            self._data.pop(key, None)
            self._expirations.pop(key, None)
            return None
        return self._data.get(key)

    async def setex(self, key: str, ttl: int, value):
        self._data[key] = value
        self._expirations[key] = time.time() + ttl

    async def delete(self, *keys):
        for key in keys:
            self._data.pop(key, None)
            self._expirations.pop(key, None)

    async def sadd(self, key: str, *values):
        self._user_sessions.setdefault(key, set()).update(values)

    async def smembers(self, key: str):
        return self._user_sessions.get(key, set())

    async def srem(self, key: str, *values):
        if key in self._user_sessions:
            self._user_sessions[key] -= set(values)


class SessionManager:
    """
    INTERVIEW: Production session manager.
    - Redis-backed (multi-instance)
    - TTL enforced
    - Per-user session tracking (for global logout)
    """
    def __init__(self, store, ttl_seconds: int = 86400):
        self.store = store
        self.ttl = ttl_seconds

    def _generate_id(self) -> str:
        """Cryptographically random session ID (256 bits)."""
        return secrets.token_urlsafe(32)

    async def create(self, user_id: int, metadata: dict = None) -> str:
        session_id = self._generate_id()
        session_data = {
            "user_id": user_id,
            "created_at": time.time(),
            "last_seen": time.time(),
            "metadata": metadata or {},
        }
        await self.store.setex(
            f"session:{session_id}",
            self.ttl,
            json.dumps(session_data)
        )
        # ⭐ Index session per user (for global logout)
        await self.store.sadd(f"user:{user_id}:sessions", session_id)
        return session_id

    async def get(self, session_id: str) -> Optional[dict]:
        data = await self.store.get(f"session:{session_id}")
        if not data:
            return None
        return json.loads(data) if isinstance(data, str) else data

    async def destroy(self, session_id: str):
        """Single device logout."""
        session = await self.get(session_id)
        if session:
            await self.store.srem(
                f"user:{session['user_id']}:sessions",
                session_id
            )
        await self.store.delete(f"session:{session_id}")

    async def destroy_all_user_sessions(self, user_id: int):
        """Global logout — all devices."""
        session_ids = await self.store.smembers(f"user:{user_id}:sessions")
        if session_ids:
            keys = [f"session:{sid}" for sid in session_ids]
            await self.store.delete(*keys)
            await self.store.delete(f"user:{user_id}:sessions")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Session Fixation Prevention
# INTERVIEW: Always regenerate session ID on login
# ─────────────────────────────────────────────────────────────────────────────

async def secure_login(session_mgr: SessionManager, request_session_id: Optional[str],
                       user_id: int) -> str:
    """
    INTERVIEW: Login flow with session fixation defense.
    """
    # ⭐ DESTROY old session (if any)
    if request_session_id:
        await session_mgr.destroy(request_session_id)

    # ⭐ CREATE new session with DIFFERENT ID
    new_session_id = await session_mgr.create(user_id, metadata={
        "ip": "192.168.1.1",
        "user_agent": "Mozilla/5.0...",
        "login_time": time.time(),
    })

    return new_session_id


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Remember Me Token Rotation
# INTERVIEW: Long-lived but rotated
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class RememberMeToken:
    selector: str        # Public identifier (lookup)
    validator_hash: str  # Hash of secret validator
    user_id: int
    expires_at: datetime


class RememberMeManager:
    """
    INTERVIEW: Persistent login with theft detection.
    Each use issues NEW token (rotation).
    """
    REMEMBER_ME_TTL = timedelta(days=30)

    def __init__(self):
        self._tokens: dict = {}    # selector → RememberMeToken

    def create_token(self, user_id: int) -> tuple[str, str]:
        """
        Returns (cookie_value, internal_record).
        Cookie format: selector:validator
        """
        selector = secrets.token_urlsafe(12)
        validator = secrets.token_urlsafe(32)

        # Store HASH of validator (defense if DB stolen)
        validator_hash = hashlib.sha256(validator.encode()).hexdigest()

        self._tokens[selector] = RememberMeToken(
            selector=selector,
            validator_hash=validator_hash,
            user_id=user_id,
            expires_at=datetime.utcnow() + self.REMEMBER_ME_TTL,
        )

        cookie_value = f"{selector}:{validator}"
        return cookie_value, selector

    def validate_and_rotate(self, cookie_value: str) -> tuple[Optional[int], Optional[str]]:
        """
        INTERVIEW: Validate + rotate (defense against theft).
        Returns (user_id, new_cookie_value).
        """
        if not cookie_value or ":" not in cookie_value:
            return None, None

        selector, validator = cookie_value.split(":", 1)

        record = self._tokens.get(selector)
        if not record:
            return None, None

        # ⭐ Constant-time validator check
        provided_hash = hashlib.sha256(validator.encode()).hexdigest()
        if not hmac.compare_digest(provided_hash, record.validator_hash):
            # ⚠️ Selector found but validator wrong = THEFT
            # Delete ALL user's remember-me tokens
            for sel, rec in list(self._tokens.items()):
                if rec.user_id == record.user_id:
                    del self._tokens[sel]
            return None, None

        # Check expiration
        if record.expires_at < datetime.utcnow():
            del self._tokens[selector]
            return None, None

        # ⭐ ROTATE: Delete old, issue new
        del self._tokens[selector]
        new_cookie, _ = self.create_token(record.user_id)

        return record.user_id, new_cookie


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: mTLS Pattern (Conceptual)
# INTERVIEW: Service-to-service identity
# ─────────────────────────────────────────────────────────────────────────────

MTLS_SERVER_CODE = """
# mTLS server (real Python code with ssl module)
import ssl
import uvicorn
from fastapi import FastAPI, Request, HTTPException

app = FastAPI()

@app.get("/internal/data")
async def get_data(request: Request):
    # ⭐ Extract client cert from TLS context
    transport = request.scope.get("transport")
    peer_cert = transport.get_extra_info("peercert")

    if peer_cert:
        subject = dict(x[0] for x in peer_cert["subject"])
        client_cn = subject.get("commonName", "")

        # Authorize based on cert CN (service identity)
        if client_cn not in ["order-service", "payment-service"]:
            raise HTTPException(403, f"Service {client_cn} not allowed")

    return {"data": "internal"}


# Run with mTLS
uvicorn.run(
    app,
    host="0.0.0.0",
    port=8443,
    ssl_certfile="server.crt",
    ssl_keyfile="server.key",
    ssl_ca_certs="ca.crt",             # ⭐ CA to verify CLIENT certs
    ssl_cert_reqs=ssl.CERT_REQUIRED,   # ⭐ REQUIRE client cert
)
"""


MTLS_CLIENT_CODE = """
# mTLS client
import httpx

# Client presents its cert + verifies server's cert
async with httpx.AsyncClient(
    cert=("client.crt", "client.key"),    # ⭐ Client cert
    verify="ca.crt",                       # Trust this CA for server
) as client:
    response = await client.get("https://api.internal:8443/internal/data")
"""


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: JWT Propagation in Microservices
# INTERVIEW: User context across services
# ─────────────────────────────────────────────────────────────────────────────

class JWTPropagator:
    """
    INTERVIEW: Forward JWT through service chain.
    Service A receives user request → calls Service B with same user context.
    """
    @staticmethod
    def extract_jwt(request_headers: dict) -> Optional[str]:
        auth = request_headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth.replace("Bearer ", "")
        return None

    @staticmethod
    def build_downstream_headers(
        original_jwt: str,
        user_id: int,
        request_id: str,
    ) -> dict:
        """Headers to pass to downstream service."""
        return {
            "Authorization": f"Bearer {original_jwt}",
            "X-User-Id": str(user_id),
            "X-Request-ID": request_id,
            "X-Forwarded-Service": "order-service",
        }


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: GDPR Right to Be Forgotten
# INTERVIEW: Article 17 implementation
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class User:
    id: int
    email: str
    name: str
    phone: Optional[str] = None
    address: Optional[str] = None
    stripe_id: Optional[str] = None
    is_active: bool = True
    deleted_at: Optional[datetime] = None


class GDPRComplianceService:
    """
    INTERVIEW: GDPR-compliant deletion.
    """
    def __init__(self):
        self.users: dict[int, User] = {}

    async def delete_account(self, user_id: int) -> dict:
        """
        Article 17: Right to be forgotten.
        Steps:
        1. Anonymize personal data
        2. Delete user-generated content (or anonymize)
        3. Delete from third parties (Stripe, Mailchimp)
        4. Revoke all sessions/tokens
        5. Log deletion (audit trail)
        6. Schedule hard delete (retention period)
        """
        user = self.users.get(user_id)
        if not user:
            return {"error": "User not found"}

        # ⭐ 1. Anonymize personal data
        user.email = f"deleted-{user_id}@anonymous.local"
        user.name = "DELETED USER"
        user.phone = None
        user.address = None
        user.deleted_at = datetime.utcnow()
        user.is_active = False

        # ⭐ 2. Delete from third parties (simulated)
        if user.stripe_id:
            await self._delete_stripe_customer(user.stripe_id)

        # ⭐ 3. Revoke sessions
        await self._revoke_all_sessions(user_id)

        # ⭐ 4. Log to audit
        await self._audit_log(
            event_type="gdpr_deletion",
            user_id=user_id,
            action="right_to_be_forgotten"
        )

        # ⭐ 5. Schedule hard delete (e.g., 30 days for rollback)
        await self._schedule_hard_delete(user_id, days=30)

        return {"status": "deletion_initiated", "user_id": user_id}

    async def export_user_data(self, user_id: int) -> dict:
        """Article 20: Data portability."""
        user = self.users.get(user_id)
        if not user:
            return {"error": "User not found"}

        return {
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "phone": user.phone,
                "address": user.address,
            },
            "exported_at": datetime.utcnow().isoformat(),
            "format_version": "1.0",
        }

    async def _delete_stripe_customer(self, stripe_id: str):
        # Simulated
        pass

    async def _revoke_all_sessions(self, user_id: int):
        # Simulated
        pass

    async def _audit_log(self, **kwargs):
        # Simulated
        print(f"  AUDIT: {kwargs}")

    async def _schedule_hard_delete(self, user_id: int, days: int):
        # Simulated
        pass


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8: PII Field-Level Encryption
# INTERVIEW: Encrypt sensitive fields before DB storage
# ─────────────────────────────────────────────────────────────────────────────

class FieldEncryption:
    """
    INTERVIEW: Encrypt sensitive fields (PII, payment data).
    Even if DB stolen, encrypted fields useless without key.
    """
    def __init__(self, key: bytes):
        try:
            from cryptography.fernet import Fernet
            # Fernet expects base64-encoded 32-byte key
            import base64
            if len(key) != 44:    # Fernet key length
                key = base64.urlsafe_b64encode(key[:32].ljust(32, b'\0'))
            self.cipher = Fernet(key)
            self._available = True
        except ImportError:
            self._available = False

    def encrypt(self, plaintext: str) -> str:
        if not self._available or not plaintext:
            return plaintext
        return self.cipher.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        if not self._available or not ciphertext:
            return ciphertext
        return self.cipher.decrypt(ciphertext.encode()).decode()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 9: Data Classification
# INTERVIEW: Tag data by sensitivity
# ─────────────────────────────────────────────────────────────────────────────

class DataClassification(Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    HIGHLY_RESTRICTED = "highly_restricted"


CLASSIFICATION_HANDLING = {
    DataClassification.PUBLIC: {
        "encrypt": False,
        "log_access": False,
        "retention": "unlimited",
    },
    DataClassification.INTERNAL: {
        "encrypt": False,
        "log_access": False,
        "retention": "5_years",
    },
    DataClassification.CONFIDENTIAL: {
        "encrypt": True,
        "log_access": True,
        "retention": "based_on_consent",
    },
    DataClassification.RESTRICTED: {
        "encrypt": True,
        "log_access": True,
        "retention": "minimum_required",
        "additional_controls": ["MFA_required", "audit_strict"],
    },
    DataClassification.HIGHLY_RESTRICTED: {
        "encrypt": True,
        "log_access": True,
        "retention": "minimum_required",
        "additional_controls": ["HSM_storage", "separate_systems"],
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 10: Audit Logger
# INTERVIEW: SOC2/HIPAA compliance
# ─────────────────────────────────────────────────────────────────────────────

class AuditLogger:
    """
    INTERVIEW: SOC2-compliant audit logging.
    """
    REQUIRED_FIELDS = [
        "event_id", "event_type", "timestamp",
        "user_id", "source_ip", "action", "result"
    ]

    def __init__(self):
        self._logs: list = []

    def log(self, event_type: str, **kwargs):
        entry = {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            **kwargs,
        }

        # In production:
        # 1. CloudWatch Logs (real-time)
        # 2. S3 (7-year retention for SOC2)
        # 3. SIEM (security monitoring)
        self._logs.append(entry)
        print(f"  AUDIT: {json.dumps(entry, default=str)}")

    def get_logs(self, user_id: Optional[int] = None) -> list:
        if user_id:
            return [log for log in self._logs if log.get("user_id") == user_id]
        return self._logs


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 11: Demos
# ─────────────────────────────────────────────────────────────────────────────

async def demo_session_lifecycle():
    print("\n[Session Lifecycle Demo]")
    store = InMemorySessionStore()
    mgr = SessionManager(store, ttl_seconds=3600)

    # Create session
    session_id = await mgr.create(user_id=42, metadata={"ip": "1.2.3.4"})
    print(f"  Created session: {session_id[:20]}...")

    # Retrieve
    data = await mgr.get(session_id)
    print(f"  Retrieved: user_id={data['user_id']}")

    # Multi-device
    session_id2 = await mgr.create(user_id=42)
    session_id3 = await mgr.create(user_id=42)
    print(f"  User has 3 active sessions")

    # Single device logout
    await mgr.destroy(session_id)
    print(f"  Logged out 1 device, still active: 2")

    # Global logout
    await mgr.destroy_all_user_sessions(user_id=42)
    remaining = await store.smembers("user:42:sessions")
    print(f"  Global logout — remaining sessions: {len(remaining)}")


async def demo_session_fixation():
    print("\n[Session Fixation Prevention Demo]")
    store = InMemorySessionStore()
    mgr = SessionManager(store)

    # Pre-login: user has anonymous session
    old_session = await mgr.create(user_id=0, metadata={"anonymous": True})
    print(f"  Pre-login session: {old_session[:20]}...")

    # Login — must regenerate
    new_session = await secure_login(mgr, old_session, user_id=42)
    print(f"  Post-login session: {new_session[:20]}...")

    assert old_session != new_session
    old_data = await mgr.get(old_session)
    assert old_data is None, "Old session must be destroyed"
    print("  ✅ Session ID changed + old destroyed (fixation prevented)")


def demo_remember_me_rotation():
    print("\n[Remember Me Token Rotation Demo]")
    mgr = RememberMeManager()

    # Initial create
    cookie1, _ = mgr.create_token(user_id=42)
    print(f"  Initial cookie: {cookie1[:30]}...")

    # Use it (gets rotated)
    user_id, cookie2 = mgr.validate_and_rotate(cookie1)
    print(f"  After validate: cookie rotated to {cookie2[:30]}...")
    assert cookie1 != cookie2
    print("  ✅ Token rotated on use")

    # Try to use old cookie (theft simulation)
    user_id, cookie3 = mgr.validate_and_rotate(cookie1)
    print(f"  Old cookie reuse: user_id={user_id} (None expected)")
    assert user_id is None
    print("  ✅ Theft detected — all tokens revoked")


async def demo_gdpr_deletion():
    print("\n[GDPR Right to Be Forgotten Demo]")
    service = GDPRComplianceService()

    # Setup user
    service.users[1] = User(
        id=1, email="alice@example.com", name="Alice",
        phone="555-1234", address="123 Main St"
    )

    # Delete
    result = await service.delete_account(user_id=1)
    print(f"  Result: {result}")

    # Verify anonymized
    user = service.users[1]
    print(f"  Email after deletion: {user.email}")
    print(f"  Name after deletion: {user.name}")
    print(f"  Phone after deletion: {user.phone}")
    assert user.email.startswith("deleted-")
    assert user.is_active is False


async def demo_data_export():
    print("\n[GDPR Data Export Demo]")
    service = GDPRComplianceService()
    service.users[1] = User(
        id=1, email="alice@example.com", name="Alice",
        phone="555-1234", address="123 Main St"
    )

    data = await service.export_user_data(user_id=1)
    print(f"  Exported data: {json.dumps(data, indent=2, default=str)[:200]}...")


def demo_field_encryption():
    print("\n[Field-Level Encryption Demo]")
    key = secrets.token_bytes(32)
    encryption = FieldEncryption(key)

    # Encrypt sensitive field
    plaintext = "555-12-3456"  # SSN
    encrypted = encryption.encrypt(plaintext)
    print(f"  Plaintext: {plaintext}")
    print(f"  Encrypted: {encrypted[:50]}...")

    # Decrypt
    decrypted = encryption.decrypt(encrypted)
    print(f"  Decrypted: {decrypted}")
    assert decrypted == plaintext


def demo_audit_logging():
    print("\n[Audit Logging Demo]")
    auditor = AuditLogger()

    # Log various events
    auditor.log(
        event_type="authentication",
        user_id=42,
        source_ip="192.168.1.1",
        action="login",
        result="success"
    )

    auditor.log(
        event_type="authorization",
        user_id=42,
        source_ip="192.168.1.1",
        action="DELETE /api/admin/users/100",
        result="denied",
        reason="missing_admin_role"
    )

    auditor.log(
        event_type="data_access",
        user_id=42,
        source_ip="192.168.1.1",
        action="read",
        resource="user/100/medical_records",
        result="success",
        classification="restricted"
    )

    user_logs = auditor.get_logs(user_id=42)
    print(f"\n  Total logs for user 42: {len(user_logs)}")


# ─────────────────────────────────────────────────────────────────────────────
# Q&A
# ─────────────────────────────────────────────────────────────────────────────

QA = [
    ("Why HttpOnly cookie?",
     "JavaScript cannot read = XSS can't steal session.\n"
     "     Best practice: always HttpOnly for auth cookies."),

    ("SameSite=Strict vs Lax?",
     "Strict: NEVER sent cross-site (best CSRF defense)\n"
     "     Lax: Sent on top-level navigation (less strict but more compatible)\n"
     "     Lax is default in modern browsers (Chrome 80+)."),

    ("Why regenerate session ID on login?",
     "Session fixation: attacker sets known session ID.\n"
     "     User logs in → attacker uses same ID = account takeover.\n"
     "     Always destroy old + create new ID on auth boundary."),

    ("Remember me vs session token?",
     "Session: short-lived (hours), for active use\n"
     "     Remember me: long-lived (30 days), for re-auth\n"
     "     Rotate remember me on each use (theft detection)."),

    ("How global logout works for JWT?",
     "Option 1: token_version in DB → increment on logout-all\n"
     "     Option 2: JTI blacklist in Redis (TTL = token exp)\n"
     "     Trade-off: stateless vs revocable"),

    ("mTLS vs API key for service auth?",
     "API key: shared secret, can leak in logs/code\n"
     "     mTLS: cryptographic identity, hard to forge\n"
     "     mTLS for zero-trust microservices."),

    ("GDPR deletion — hard or soft?",
     "Initial: soft delete (anonymize) + retention period for rollback\n"
     "     After 30 days: hard delete\n"
     "     Some data MUST be kept (financial 7 years)"),

    ("Why field-level encryption?",
     "Defense in depth: DB stolen ≠ data exposed\n"
     "     Encrypt PII (SSN, medical) at column level\n"
     "     Search/index on hash + range queries via separate index"),

    ("SOC2 audit log fields?",
     "event_id, event_type, timestamp, user_id\n"
     "     source_ip, user_agent, action, resource, result\n"
     "     Retention: 1-7 years depending on framework"),

    ("Why pepper + salt?",
     "Salt: per-user (in DB) → prevents rainbow tables\n"
     "     Pepper: server-wide (secret manager) → DB leak still need pepper"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    print("=" * 60)
    print("SESSIONS + ZERO TRUST + COMPLIANCE PRACTICAL")
    print("=" * 60)

    await demo_session_lifecycle()
    await demo_session_fixation()
    demo_remember_me_rotation()
    await demo_gdpr_deletion()
    await demo_data_export()
    demo_field_encryption()
    demo_audit_logging()

    print("\n[Data Classification Handling]")
    for level, handling in CLASSIFICATION_HANDLING.items():
        print(f"  {level.value:<22}: {handling}")

    print("\n[Q&A Summary]")
    for q, a in QA:
        print(f"\n  Q: {q}")
        print(f"  A: {a}")

    print("\n" + "=" * 60)
    print("FILES TO KNOW:")
    print("  session_manager.py     → Redis-backed sessions")
    print("  remember_me.py         → Long-lived token rotation")
    print("  mtls_server.py         → Service-to-service mTLS")
    print("  gdpr_service.py        → Right to be forgotten + export")
    print("  field_encryption.py    → PII encryption")
    print("  audit_logger.py        → SOC2-compliant logging")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
