# Logging Security — What to Log, What Never to Log

## The Core Problem

```python
# Developer writes this innocently:
logger.info(f"Login attempt: user={email}, password={password}")
logger.debug(f"Token issued: {jwt_token}")
logger.error(f"Payment failed: card={card_number}, cvv={cvv}")

# Result:
# - Password in plaintext in log files
# - JWT valid for 15 min → log file reader can impersonate user
# - Card number in logs → PCI DSS violation → massive fine
# - Log aggregation tools (ELK, CloudWatch) ship these to 3rd parties
```

---

## NEVER Log These Fields

```python
SENSITIVE_FIELDS = {
    # Authentication
    "password", "passwd", "pwd", "secret",
    "token", "access_token", "refresh_token", "id_token",
    "api_key", "apikey", "api_secret",
    "authorization",          # the whole header value
    "session_id", "session",

    # Payment / PCI DSS
    "card_number", "cvv", "cvc", "pin",
    "credit_card", "pan",

    # PII (GDPR / DPDP)
    "aadhaar", "ssn", "passport",
    "otp", "totp", "mfa_code",

    # Credentials
    "private_key", "certificate",
    "aws_secret", "aws_access_key",
    "database_url", "connection_string",
}
```

---

## Log Sanitization — Automatic Redaction

### Approach 1: Custom Logging Filter

```python
import logging, re

class SensitiveDataFilter(logging.Filter):
    PATTERNS = [
        # JWT (3 dot-separated base64 parts)
        (re.compile(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+'), '[JWT_REDACTED]'),
        # "password": "..." in JSON strings
        (re.compile(r'"(password|passwd|pwd|secret|token|api_key)":\s*"[^"]*"', re.IGNORECASE),
         r'"\1": "[REDACTED]"'),
        # key=value in query strings / logs
        (re.compile(r'(password|token|secret|api_key)=[^\s&"]+', re.IGNORECASE),
         r'\1=[REDACTED]'),
        # Card numbers (13-19 digits)
        (re.compile(r'\b\d{13,19}\b'), '[CARD_REDACTED]'),
        # Aadhaar (12 digits)
        (re.compile(r'\b\d{4}\s?\d{4}\s?\d{4}\b'), '[AADHAAR_REDACTED]'),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        msg = str(record.getMessage())
        for pattern, replacement in self.PATTERNS:
            msg = pattern.sub(replacement, msg)
        record.msg  = msg
        record.args = ()   # args already interpolated into msg
        return True


# Register filter on all handlers
def setup_logging():
    sensitive_filter = SensitiveDataFilter()
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.addFilter(sensitive_filter)
```

### Approach 2: Dict Sanitizer for Structured Logging

```python
def sanitize(data: dict, sensitive_keys: set = None) -> dict:
    if sensitive_keys is None:
        sensitive_keys = SENSITIVE_FIELDS

    result = {}
    for key, value in data.items():
        if key.lower() in sensitive_keys:
            result[key] = "[REDACTED]"
        elif isinstance(value, dict):
            result[key] = sanitize(value, sensitive_keys)
        elif isinstance(value, list):
            result[key] = [sanitize(v, sensitive_keys) if isinstance(v, dict) else v
                          for v in value]
        else:
            result[key] = value
    return result


# Usage:
import structlog

log = structlog.get_logger()

# WRONG:
log.info("user.login", email=email, password=password)

# CORRECT:
log.info("user.login", **sanitize({"email": email, "password": password}))
# Output: {"email": "user@example.com", "password": "[REDACTED]"}
```

---

## Structured Logging (What TO Log)

### Request Log — Every HTTP Request

```python
import time, uuid
from fastapi import Request

@app.middleware("http")
async def request_logger(request: Request, call_next):
    request_id = str(uuid.uuid4())
    start      = time.perf_counter()

    # Attach to request state for downstream use
    request.state.request_id = request_id

    response = await call_next(request)

    duration_ms = (time.perf_counter() - start) * 1000

    log.info(
        "http.request",
        request_id  = request_id,
        method      = request.method,
        path        = request.url.path,
        status_code = response.status_code,
        duration_ms = round(duration_ms, 2),
        ip          = request.client.host,
        user_agent  = request.headers.get("user-agent", ""),
        # NOTE: do NOT log Authorization header or body
    )
    response.headers["X-Request-ID"] = request_id
    return response
```

### Security Event Log — Authentication & Access

```python
# What to log for security events (NOT passwords)

def log_login_success(user_id: int, ip: str, user_agent: str):
    log.info(
        "auth.login.success",
        user_id    = user_id,      # ✅ ID, not credentials
        ip         = ip,
        user_agent = user_agent,
        # NOT: password, token, session_id
    )

def log_login_failure(email: str, ip: str, reason: str):
    log.warning(
        "auth.login.failure",
        email_hash = hashlib.sha256(email.encode()).hexdigest()[:8],  # partial hash, not plaintext
        ip         = ip,
        reason     = reason,   # "invalid_password" or "user_not_found" — DON'T distinguish to user!
        # NOT: the actual email (PII) — hash it if needed for correlation
    )

def log_access_denied(user_id: int, resource: str, action: str):
    log.warning(
        "authz.denied",
        user_id  = user_id,
        resource = resource,
        action   = action,
    )

def log_token_issued(user_id: int, token_type: str, expires_at: str):
    log.info(
        "auth.token.issued",
        user_id    = user_id,
        token_type = token_type,    # "access" or "refresh"
        expires_at = expires_at,
        # NOT: the token itself
    )
```

### Django Middleware Version

```python
# middleware.py
import logging, time, uuid
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger("security")

class RequestLoggingMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request.request_id = str(uuid.uuid4())
        request._start_time = time.perf_counter()

    def process_response(self, request, response):
        duration_ms = (time.perf_counter() - getattr(request, "_start_time", 0)) * 1000
        user_id     = request.user.id if request.user.is_authenticated else None

        logger.info(
            "http.request",
            extra={
                "request_id":  getattr(request, "request_id", "-"),
                "method":      request.method,
                "path":        request.path,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
                "user_id":     user_id,
                "ip":          request.META.get("REMOTE_ADDR"),
                # NOT: request.POST (may have passwords), headers (may have tokens)
            }
        )
        response["X-Request-ID"] = getattr(request, "request_id", "-")
        return response
```

---

## Audit Logs — Separate from Application Logs

```python
# Audit logs = who did what to which resource, when
# Different from debug/info logs — immutable, long retention, compliance

AUDIT_LOG_TABLE = "audit_events"   # DB or separate log stream

def audit(
    actor_id:    int,
    action:      str,       # "user.password_changed", "order.deleted", "role.assigned"
    resource:    str,       # "user:123", "order:456"
    outcome:     str,       # "success" | "failure"
    ip:          str,
    request_id:  str,
    details:     dict = None,
):
    entry = {
        "actor_id":   actor_id,
        "action":     action,
        "resource":   resource,
        "outcome":    outcome,
        "ip":         ip,
        "request_id": request_id,
        "timestamp":  datetime.utcnow().isoformat(),
        "details":    sanitize(details or {}),   # sanitize before storing
    }
    # Write to append-only audit table / CloudWatch / S3
    audit_logger.info("audit", **entry)

# Usage:
audit(
    actor_id   = request.user.id,
    action     = "user.role_changed",
    resource   = f"user:{target_user_id}",
    outcome    = "success",
    ip         = request.client.host,
    request_id = request.state.request_id,
    details    = {"old_role": "user", "new_role": "admin"},
)
```

---

## Log Levels — What Goes Where

```
DEBUG   → Dev only. NEVER in production. May contain raw SQL, internal state.
INFO    → Normal operations: request completed, user logged in, task enqueued.
WARNING → Unexpected but handled: login failure, rate limit hit, 404.
ERROR   → Exceptions, 5xx, something broke. Always include request_id + traceback.
CRITICAL → Service degraded, DB down, circuit breaker open.

# Production settings.py (Django):
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "sensitive": {"()": "myapp.logging.SensitiveDataFilter"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["sensitive"],
            "formatter": "json",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",    # DEBUG in prod = risk
    },
}
```

---

## structlog — Structured Logging (Recommended)

```python
# pip install structlog
import structlog

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),       # machine-readable JSON
    ]
)

log = structlog.get_logger()

# Bind context for all log lines in a request
structlog.contextvars.bind_contextvars(
    request_id=request_id,
    user_id=user_id,
)

# Every log line in this request automatically has request_id + user_id
log.info("order.created", order_id=123, amount=999.0)
# {"event": "order.created", "order_id": 123, "amount": 999.0,
#  "request_id": "abc-123", "user_id": 42, "timestamp": "2026-08-17T..."}
```

---

## Log Storage & Retention

```
What to send where:

Application logs (INFO/ERROR) → CloudWatch Logs
  → 30-90 day retention
  → CloudWatch Insights for queries

Audit logs → CloudWatch Logs (separate log group) + S3
  → 1-7 year retention (compliance)
  → S3 Glacier for cost

Security events (login failures, access denied) → SIEM or separate stream
  → Real-time alerting

Access logs (ALB, Nginx) → S3
  → 90 day retention
  → Athena for analysis
```

---

## Security Checklist

```
What to NEVER log:
✅ Passwords (any form — plaintext, hashed, partial)
✅ JWT / access tokens / refresh tokens
✅ API keys / secrets
✅ Session IDs
✅ Credit card numbers / CVV
✅ Aadhaar / SSN / passport numbers
✅ OTP / MFA codes
✅ Private keys / certificates
✅ Full Authorization header value
✅ request.POST / request.body blindly (may contain passwords)

Sanitization:
✅ SensitiveDataFilter on all log handlers
✅ Regex-based JWT detection and redaction
✅ Dict sanitizer before logging structured data
✅ Audit log details sanitized before storage

What to always log:
✅ Request ID (every log line in a request)
✅ User ID (not username/email — use ID for correlation)
✅ IP address
✅ HTTP method + path + status + duration_ms
✅ Auth events: login success/failure, token issued, password changed
✅ Access denied events (authz.denied)
✅ Errors with traceback + request_id
✅ Admin/privileged actions (audit log)
```

---

## Interview Q&A

**Q: JWT ko log kyun nahi karna chahiye?**
A: JWT valid hota hai jab tak expire na ho. Agar log file mein hai → log file access karne wala koi bhi us token se user ki taraf se API calls kar sakta hai. Log aggregation tools (Datadog, CloudWatch) bhi token receive kar lete hain — attack surface badh jaata hai.

**Q: Login failure mein "user not found" vs "wrong password" distinct karna chahiye?**
A: Nahi. Distinct error se attacker confirm kar sakta hai ki email registered hai ya nahi — account enumeration attack. Dono cases mein generic message do: "Invalid credentials." Internally log karo reason (audit trail ke liye), but user ko mat batao.

**Q: Request body log karna safe hai?**
A: Mostly nahi — POST body mein password, card numbers, PII ho sakta hai. Ya explicitly whitelist karo kaunse fields log karo, ya bilkul mat karo. Authorization header bhi mat log karo.

**Q: Audit log aur application log mein kya fark hai?**
A: Application log = debugging ke liye (request timing, errors, flow). Audit log = compliance ke liye — immutable record of "who did what to which resource when." Audit logs longer retention, separate storage, tamper-evident hone chahiye. Admin actions, permission changes, data access — sab audit log mein.

**Q: PII log karna legally problematic kyun hai?**
A: GDPR aur India DPDP Act ke under logs bhi "personal data processing" hain. Agar email/name/phone logs mein hain toh: data retention policy apply hoti hai, breach disclosure required hai, "right to erasure" pe logs bhi delete karne padte hain. Solution: user ko user_id se identify karo logs mein, PII mat daalo.
