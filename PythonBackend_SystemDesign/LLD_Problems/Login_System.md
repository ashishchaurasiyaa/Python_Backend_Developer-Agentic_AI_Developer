# Login System — LLD
> **Difficulty:** Medium | **Frequency:** ★★★★★ | **Covers:** Auth, JWT, Sessions, OAuth, Security

---

# PART 1: THEORY

---

## 1.1 Authentication vs Authorization

```
Authentication = TUM KON HO? (identity verify karo)
  → Login karo — email + password, OTP, Google
  → "Main Rahul hoon" prove karo

Authorization = TUMHE KYA KARNE KI PERMISSION HAI? (access control)
  → Login ke baad — kaunse resources access kar sakte ho
  → "Rahul admin hai ya normal user?"

Example:
  Authentication: username + password sahi hai → logged in ✓
  Authorization:  logged in Rahul /admin page access kare → 403 Forbidden ✗
                  (authenticated hai, authorized nahi)

Interview tip:
  "AuthN" = Authentication
  "AuthZ" = Authorization
```

---

## 1.2 Password Storage — NEVER Plain Text

```
Plain text store karna = crime
  DB hack ho → sab passwords exposed

MD5 / SHA1 = bhi galat
  Fast hash → brute force / rainbow table attack possible
  MD5("password") = always same hash → precomputed tables se crack

CORRECT approach: Slow + Salted Hash
  bcrypt / argon2 / scrypt

Salt kya hota hai?
  Random string jo password ke saath mix hoti hai before hashing.
  "password" + "xK9mP2" → hash karo

  Same password, different users → different hash (salt alag)
  Rainbow table attack impossible (precomputed table useless)

bcrypt:
  hash = bcrypt.hashpw("mypassword".encode(), bcrypt.gensalt(rounds=12))
  verify = bcrypt.checkpw("mypassword".encode(), hash)

  rounds=12 → 2^12 iterations → deliberately slow → brute force hard
  Rounds double karo → 2x slower for attacker (and for you!)

argon2 (modern, recommended):
  Winner of Password Hashing Competition 2015
  Memory-hard → GPU attacks expensive
  Django uses PBKDF2 by default, argon2 optional
```

---

## 1.3 Session vs Token (JWT) — Two Approaches

```
APPROACH 1: SESSION-BASED (Stateful)
─────────────────────────────────────
Login karo → server session create karta hai → session_id client ko deta hai
Client: session_id cookie mein store
Har request: session_id bhejo → server DB/Redis mein check karo

   Client              Server              Storage
   ──────              ──────              ───────
   POST /login    →    verify password
                  ←    Set-Cookie: sess=abc123
                       Save: {abc123: user_id=1, ...}   → Redis/DB

   GET /profile   →    Cookie: sess=abc123
                       Lookup abc123 in Redis   →    Redis
                  ←    Return profile

Pros:
  ✓ Server pe instant revoke (logout = delete session)
  ✓ Session data server pe safe
  ✓ Small cookie (just an ID)

Cons:
  ✗ Stateful — every server needs Redis/DB access
  ✗ Horizontal scaling mein problem (session affinity ya shared store)
  ✗ CSRF attacks possible (cookie auto-sent)


APPROACH 2: JWT (Stateless)
────────────────────────────
Login karo → server JWT token sign karta hai → client ko deta hai
Client: token localStorage ya cookie mein
Har request: token Authorization header mein bhejo
Server: token signature verify karo → no DB lookup needed

   Client              Server
   ──────              ──────
   POST /login    →    verify password
                  ←    { token: "eyJhbGc..." }

   GET /profile   →    Authorization: Bearer eyJhbGc...
                       Verify signature (no DB!)
                  ←    Return profile

JWT Structure:
  Header.Payload.Signature

  Header:  { "alg": "HS256", "typ": "JWT" }
  Payload: { "user_id": 1, "role": "admin", "exp": 1714900000 }
  Signature: HMAC_SHA256(base64(header) + "." + base64(payload), SECRET_KEY)

  Base64 encoded — NOT encrypted (anyone can decode payload!)
  Tamper-proof — signature verify hogi to pata chalega

Pros:
  ✓ Stateless — no DB lookup per request
  ✓ Works across microservices (all verify same secret)
  ✓ Mobile friendly (no cookies needed)

Cons:
  ✗ Revoke nahi kar sakte before expiry (logout = client-side only)
  ✗ Payload bada ho sakta hai (har request mein bheja jaata)
  ✗ Secret key leak = all tokens compromised


HYBRID (Best Practice — Niroskos pattern):
  Access Token:  JWT, short-lived (15 min) → fast, stateless
  Refresh Token: Opaque, long-lived (7 days) → stored in DB, revocable

  Access expire → Refresh token use karo → new Access token lo
  Logout → Refresh token DB se delete karo (revoked)
```

---

## 1.4 All Login Scenarios

```
USER LOGIN ATTEMPT
      │
      ▼
┌─────────────────────────────────────────────────────────┐
│  STEP 1: Input Validation                               │
│  Email format valid? Password length okay?              │
│  NO → 400 Bad Request (don't even touch DB)             │
└──────────────────────┬──────────────────────────────────┘
                       │ YES
                       ▼
┌─────────────────────────────────────────────────────────┐
│  STEP 2: Rate Limit Check                               │
│  IP ya email pe too many attempts?                      │
│  YES → 429 Too Many Requests (don't process)            │
└──────────────────────┬──────────────────────────────────┘
                       │ NO
                       ▼
┌─────────────────────────────────────────────────────────┐
│  STEP 3: DB Lookup                                      │
│  Email exist karta hai?                                 │
└──────────┬──────────────────────┬───────────────────────┘
           │ YES                  │ NO
           ▼                      ▼
┌──────────────────┐   ┌──────────────────────────────────┐
│ STEP 4: Account  │   │ SCENARIO A: User Not Found        │
│ Status Check     │   │ → Same error as wrong password    │
│                  │   │   "Invalid email or password"     │
│ ACTIVE?          │   │ → Same response TIME (timing safe)│
│ LOCKED?          │   │ → Attempt count++ in Redis        │
│ UNVERIFIED?      │   │ → 401 Unauthorized                │
│ DELETED?         │   └──────────────────────────────────┘
└──────┬───────────┘
       │
  ┌────┴──────────────────────────────────┐
  │                                       │
  ▼                                       ▼
LOCKED                               ACTIVE
  → 423 Locked                           │
  → "Account locked. Try after Xmin"     ▼
  → Or: "Reset password link sent"  ┌────────────────┐
                                    │ STEP 5:        │
UNVERIFIED                          │ Password Check │
  → 403 Forbidden                   └──────┬─────────┘
  → "Verify email first"                   │
  → Resend verification option        ┌────┴────┐
                                      │         │
SOFT DELETED                        WRONG    CORRECT
  → 410 Gone                          │         │
  → "Account deactivated"             ▼         ▼
  → Support contact                SCENARIO B  STEP 6: MFA?
                                   Wrong Pass   │
                                   → attempt++  ├── No MFA → Generate Token
                                   → 5 fails?   │          → Return 200 ✓
                                   → LOCK       └── MFA → OTP/TOTP
                                                         → Verify
                                                         → Token
```

---

## 1.5 Security Threats & Defenses

```
THREAT 1: Brute Force Attack
  Attacker tries millions of passwords
  Defense:
    → Rate limiting (5 attempts → 15 min lockout)
    → Account lockout
    → CAPTCHA after 3 fails
    → IP-based blocking
    → Exponential backoff

THREAT 2: Credential Stuffing
  Attacker uses leaked username/password from other sites
  Users reuse passwords → works on your site too
  Defense:
    → MFA (attacker needs 2nd factor)
    → "Was your password in a breach?" check (HaveIBeenPwned API)
    → Anomaly detection (new location, device)
    → Rate limiting

THREAT 3: Timing Attack
  Attacker measures response time:
    "email not found" → 1ms (no hash comparison)
    "wrong password" → 100ms (hash comparison happens)
  → Attacker knows if email exists!

  Defense:
    → Always run bcrypt.checkpw() even if user not found
    → Use dummy hash for non-existent users
    → Same response time always

THREAT 4: SQL Injection
  Input: email = "' OR '1'='1"
  Bad query: SELECT * FROM users WHERE email = '' OR '1'='1'
  Defense:
    → Parameterized queries (ORM handles this)
    → Never string concatenate SQL

THREAT 5: Session Hijacking
  Attacker steals session cookie
  Defense:
    → Secure flag (HTTPS only)
    → HttpOnly flag (JS can't read)
    → SameSite=Strict (CSRF protection)
    → Session rotation on privilege escalation

THREAT 6: JWT Secret Leak
  If SECRET_KEY leaked → attacker can forge any token
  Defense:
    → Strong secret (256-bit random)
    → Rotate keys periodically
    → Short expiry (15 min access token)
    → Store in env var, never in code

THREAT 7: CSRF (Cross-Site Request Forgery)
  Malicious site submits form as logged-in user
  Defense:
    → CSRF token in forms (Django does this by default)
    → SameSite cookie attribute
    → JWT in Authorization header (not cookie) = immune to CSRF
```

---

## 1.6 OAuth 2.0 / Social Login Flow

```
"Login with Google" ke peeche ka flow:

1. User clicks "Login with Google"
2. App redirects to Google:
   https://accounts.google.com/oauth/authorize
   ?client_id=YOUR_CLIENT_ID
   &redirect_uri=https://yourapp.com/callback
   &scope=email profile
   &state=random_csrf_token        ← CSRF protection
   &response_type=code

3. User logs into Google, grants permission

4. Google redirects back:
   https://yourapp.com/callback?code=AUTH_CODE&state=random_csrf_token

5. Your server exchanges code for tokens:
   POST https://oauth2.googleapis.com/token
   { code, client_id, client_secret, redirect_uri }
   ← { access_token, id_token, refresh_token }

6. Your server decodes id_token → user info (email, name, picture)

7. Your server:
   → Email DB mein hai? → Login karo
   → Email nahi? → Create account → Login karo

Key concepts:
  Auth Code:     short-lived, one-time use (step 4)
  Access Token:  call Google APIs (not your APIs)
  ID Token:      JWT containing user info (this is what you use)
  state param:   CSRF protection — verify it matches what you sent
```

---

## 1.7 MFA (Multi-Factor Authentication)

```
Factors:
  Something you KNOW  → Password
  Something you HAVE  → Phone (OTP), Hardware key
  Something you ARE   → Fingerprint, Face ID

TOTP (Time-based One-Time Password):
  Google Authenticator / Authy
  Algorithm:
    Secret key stored in DB (per user)
    Current time (30-second window)
    HMAC(secret, time_counter) → 6-digit code
    Both app and server compute same code independently

SMS OTP:
  6-digit code, valid 10 min, single use
  Less secure than TOTP (SIM swap attacks)
  Most common in India (Exotel SMS)

Flow:
  Login step 1: email + password → 200 OK, "MFA required" response
  Login step 2: OTP enter karo → full access token milta hai

  Intermediate state: "partially authenticated"
  JWT with mfa_verified: false → only /mfa endpoint accessible
```

---

## 1.8 Password Reset Flow

```
User: "Forgot Password" click karo

WRONG approach:
  → Show security question
  → Or: show old password hint
  → These are weak / legacy

CORRECT approach (token-based):

  1. User enters email
  2. Server: generate cryptographically random token (32 bytes)
  3. Store token in DB:
     { token_hash, user_id, expires_at (1 hour), used: false }
     Store HASH of token — not token itself (same principle as passwords)
  4. Email bhejo: https://app.com/reset?token=RANDOM_TOKEN
  5. User clicks link → enter new password
  6. Server: hash verify karo, expiry check karo, used check karo
  7. Password update karo, token mark as used
  8. All other sessions invalidate karo (security)

Security rules:
  → Token single-use (mark used after first use)
  → Short expiry (1 hour max)
  → Token invalidated if password changed already
  → Rate limit /forgot-password endpoint
  → Don't reveal if email exists:
    "If this email is registered, you'll receive a reset link"
    (same response whether email exists or not)
```

---

## 1.9 Token Storage — Where to Keep JWT?

```
Option 1: localStorage
  ✓ Easy to use
  ✗ XSS attack → malicious JS reads token → game over
  ✗ Never use for sensitive apps

Option 2: sessionStorage
  ✓ Cleared on tab close
  ✗ Still XSS vulnerable

Option 3: HttpOnly Cookie (RECOMMENDED)
  ✓ JS cannot read (HttpOnly flag)
  ✓ XSS safe
  ✓ Auto-sent on every request
  ✗ CSRF vulnerable → fix with SameSite=Strict + CSRF token

Option 4: Memory (in-app state / Redux)
  ✓ XSS safe (JS can't persist across pages)
  ✗ Lost on refresh (need refresh token flow)
  Used by SPAs with refresh token in HttpOnly cookie

Niroskos approach:
  Access token: Authorization header (mobile) / memory (web SPA)
  Refresh token: HttpOnly Secure cookie
  CSRF protection: SameSite=Strict
```

---

# PART 2: PRACTICAL IMPLEMENTATION

---

```python
from __future__ import annotations
import hashlib
import hmac
import os
import secrets
import time
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Optional, Tuple
import re


# ═══════════════════════════════════════════════════════════════
# ENUMS & EXCEPTIONS
# ═══════════════════════════════════════════════════════════════

class AccountStatus(Enum):
    ACTIVE      = "active"
    UNVERIFIED  = "unverified"   # Email not verified yet
    LOCKED      = "locked"       # Too many failed attempts
    DEACTIVATED = "deactivated"  # Admin disabled
    DELETED     = "deleted"      # Soft deleted


class LoginFailureReason(Enum):
    USER_NOT_FOUND       = "user_not_found"
    WRONG_PASSWORD       = "wrong_password"
    ACCOUNT_LOCKED       = "account_locked"
    ACCOUNT_UNVERIFIED   = "account_unverified"
    ACCOUNT_DEACTIVATED  = "account_deactivated"
    RATE_LIMITED         = "rate_limited"
    MFA_REQUIRED         = "mfa_required"
    MFA_INVALID          = "mfa_invalid"


class AuthError(Exception):
    def __init__(self, reason: LoginFailureReason, message: str, http_status: int = 401):
        super().__init__(message)
        self.reason      = reason
        self.http_status = http_status


# ═══════════════════════════════════════════════════════════════
# PASSWORD HASHING
# ═══════════════════════════════════════════════════════════════

class PasswordHasher:
    """
    bcrypt-equivalent using PBKDF2 (no external deps for demo).
    Production: use bcrypt or argon2-cffi.

    pip install bcrypt
    import bcrypt
    hash   = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12))
    valid  = bcrypt.checkpw(password.encode(), hash)
    """

    ITERATIONS = 260_000   # OWASP 2023 recommendation for PBKDF2-SHA256
    SALT_SIZE  = 32        # bytes

    @classmethod
    def hash(cls, password: str) -> str:
        """Returns: iterations$salt_hex$hash_hex"""
        salt  = os.urandom(cls.SALT_SIZE)
        dk    = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, cls.ITERATIONS)
        return f"{cls.ITERATIONS}${salt.hex()}${dk.hex()}"

    @classmethod
    def verify(cls, password: str, stored_hash: str) -> bool:
        """Constant-time comparison — prevents timing attacks"""
        try:
            iterations, salt_hex, hash_hex = stored_hash.split('$')
            salt = bytes.fromhex(salt_hex)
            dk   = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, int(iterations))
            # hmac.compare_digest = constant time (no early exit)
            return hmac.compare_digest(dk.hex(), hash_hex)
        except Exception:
            return False

    @classmethod
    def dummy_verify(cls) -> None:
        """
        Call this when user NOT FOUND to prevent timing attack.
        Without this: user_not_found response = 1ms (no hash)
                      wrong_password response = 100ms (hash comparison)
        Attacker can enumerate emails by measuring response time!
        """
        dummy = "dummy_hash$" + "0" * 64 + "$" + "0" * 64
        cls.verify("dummy", f"260000${'0'*64}${'0'*64}")


# ═══════════════════════════════════════════════════════════════
# USER MODEL
# ═══════════════════════════════════════════════════════════════

@dataclass
class User:
    user_id:         str  = field(default_factory=lambda: str(uuid.uuid4()))
    email:           str  = ""
    phone:           Optional[str] = None
    password_hash:   str  = ""
    status:          AccountStatus = AccountStatus.UNVERIFIED
    role:            str  = "user"          # user / admin / staff
    mfa_enabled:     bool = False
    mfa_secret:      Optional[str] = None   # TOTP secret
    failed_attempts: int  = 0
    locked_until:    Optional[datetime] = None
    email_verified:  bool = False
    created_at:      datetime = field(default_factory=datetime.now)
    last_login:      Optional[datetime] = None

    def is_locked(self) -> bool:
        if self.status == AccountStatus.LOCKED:
            if self.locked_until and datetime.now() > self.locked_until:
                # Lock expired — auto-unlock
                self.status         = AccountStatus.ACTIVE
                self.failed_attempts = 0
                self.locked_until   = None
                return False
            return True
        return False


# ═══════════════════════════════════════════════════════════════
# JWT (Simplified — production use PyJWT)
# ═══════════════════════════════════════════════════════════════

import base64, json

class JWTService:
    """
    Production: pip install PyJWT
    import jwt
    token   = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    """

    SECRET_KEY            = os.environ.get("JWT_SECRET", secrets.token_hex(32))
    ACCESS_TOKEN_EXPIRY   = timedelta(minutes=15)
    REFRESH_TOKEN_EXPIRY  = timedelta(days=7)

    @classmethod
    def _b64_encode(cls, data: dict) -> str:
        return base64.urlsafe_b64encode(
            json.dumps(data, separators=(',', ':')).encode()
        ).rstrip(b'=').decode()

    @classmethod
    def _sign(cls, header_b64: str, payload_b64: str) -> str:
        msg  = f"{header_b64}.{payload_b64}".encode()
        sig  = hmac.new(cls.SECRET_KEY.encode(), msg, hashlib.sha256).digest()
        return base64.urlsafe_b64encode(sig).rstrip(b'=').decode()

    @classmethod
    def create_access_token(cls, user_id: str, role: str, mfa_verified: bool = True) -> str:
        header  = {"alg": "HS256", "typ": "JWT"}
        payload = {
            "sub":          user_id,
            "role":         role,
            "mfa_verified": mfa_verified,
            "iat":          int(time.time()),
            "exp":          int((datetime.now() + cls.ACCESS_TOKEN_EXPIRY).timestamp()),
            "jti":          secrets.token_hex(8),   # JWT ID — for revocation
        }
        h = cls._b64_encode(header)
        p = cls._b64_encode(payload)
        s = cls._sign(h, p)
        return f"{h}.{p}.{s}"

    @classmethod
    def verify_access_token(cls, token: str) -> dict:
        try:
            parts = token.split('.')
            if len(parts) != 3:
                raise ValueError("Invalid token format")
            h, p, s = parts
            expected_sig = cls._sign(h, p)
            if not hmac.compare_digest(s, expected_sig):
                raise ValueError("Invalid signature")
            payload = json.loads(base64.urlsafe_b64decode(p + "=="))
            if payload.get("exp", 0) < time.time():
                raise ValueError("Token expired")
            return payload
        except Exception as e:
            raise AuthError(LoginFailureReason.MFA_INVALID, f"Invalid token: {e}", 401)

    @classmethod
    def create_refresh_token(cls) -> str:
        """Opaque — stored in DB, not JWT"""
        return secrets.token_urlsafe(32)


# ═══════════════════════════════════════════════════════════════
# RATE LIMITER (Reuse from Rate Limiter chapter)
# ═══════════════════════════════════════════════════════════════

class LoginRateLimiter:
    """
    Per-email AND per-IP rate limiting.
    Stricter than API rate limiter — security critical.

    Thresholds:
      5  attempts  per email  per 15 min → lock email
      20 attempts  per IP     per 15 min → block IP
    """

    def __init__(self):
        self._email_attempts: Dict[str, list] = {}
        self._ip_attempts:    Dict[str, list] = {}
        self._blocked_ips:    Dict[str, datetime] = {}
        self._lock = threading.Lock()

    def check_and_record(self, email: str, ip: str) -> None:
        """Raises AuthError if rate limited"""
        with self._lock:
            now      = datetime.now()
            window   = now - timedelta(minutes=15)

            # IP block check
            if ip in self._blocked_ips:
                if now < self._blocked_ips[ip]:
                    raise AuthError(
                        LoginFailureReason.RATE_LIMITED,
                        "Too many login attempts. Try again later.",
                        429
                    )
                del self._blocked_ips[ip]

            # Clean old attempts
            self._email_attempts[email] = [
                t for t in self._email_attempts.get(email, []) if t > window
            ]
            self._ip_attempts[ip] = [
                t for t in self._ip_attempts.get(ip, []) if t > window
            ]

            email_count = len(self._email_attempts.get(email, []))
            ip_count    = len(self._ip_attempts.get(ip, []))

            if email_count >= 5:
                raise AuthError(
                    LoginFailureReason.RATE_LIMITED,
                    "Too many attempts for this email. Try again in 15 minutes.",
                    429
                )
            if ip_count >= 20:
                self._blocked_ips[ip] = now + timedelta(minutes=15)
                raise AuthError(
                    LoginFailureReason.RATE_LIMITED,
                    "Too many requests from your location.",
                    429
                )

            # Record this attempt
            self._email_attempts.setdefault(email, []).append(now)
            self._ip_attempts.setdefault(ip, []).append(now)

    def reset_email(self, email: str) -> None:
        """Clear attempts on successful login"""
        with self._lock:
            self._email_attempts.pop(email, None)


# ═══════════════════════════════════════════════════════════════
# TOKEN STORE (Refresh Tokens + Password Reset Tokens)
# ═══════════════════════════════════════════════════════════════

@dataclass
class StoredToken:
    token_hash:  str
    user_id:     str
    token_type:  str          # "refresh" / "password_reset" / "email_verify"
    expires_at:  datetime
    used:        bool = False
    created_at:  datetime = field(default_factory=datetime.now)

    def is_valid(self) -> bool:
        return not self.used and datetime.now() < self.expires_at


class TokenStore:
    """
    Production: PostgreSQL table with unique hash constraint.
    Store HASH of token — not raw token.
    """

    def __init__(self):
        self._tokens: Dict[str, StoredToken] = {}
        self._lock   = threading.Lock()

    def _hash_token(self, raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode()).hexdigest()

    def store(self, raw_token: str, user_id: str, token_type: str, expires_in: timedelta) -> None:
        token_hash = self._hash_token(raw_token)
        with self._lock:
            self._tokens[token_hash] = StoredToken(
                token_hash  = token_hash,
                user_id     = user_id,
                token_type  = token_type,
                expires_at  = datetime.now() + expires_in
            )

    def verify_and_consume(self, raw_token: str, token_type: str) -> Optional[str]:
        """Returns user_id if valid, None otherwise. Marks as used."""
        token_hash = self._hash_token(raw_token)
        with self._lock:
            stored = self._tokens.get(token_hash)
            if not stored or stored.token_type != token_type or not stored.is_valid():
                return None
            stored.used = True
            return stored.user_id

    def revoke_user_tokens(self, user_id: str, token_type: str) -> None:
        """Revoke all tokens of a type for a user (logout all devices)"""
        with self._lock:
            for token in self._tokens.values():
                if token.user_id == user_id and token.token_type == token_type:
                    token.used = True

    def peek(self, raw_token: str, token_type: str) -> Optional[str]:
        """Check without consuming (for refresh token reuse)"""
        token_hash = self._hash_token(raw_token)
        stored = self._tokens.get(token_hash)
        if stored and stored.token_type == token_type and stored.is_valid():
            return stored.user_id
        return None


# ═══════════════════════════════════════════════════════════════
# OTP SERVICE
# ═══════════════════════════════════════════════════════════════

class OTPService:
    """
    SMS OTP for MFA and phone login.
    Production: Exotel (Niroskos), Twilio, MSG91
    """

    OTP_LENGTH  = 6
    OTP_EXPIRY  = timedelta(minutes=10)

    def __init__(self):
        self._otps: Dict[str, dict] = {}
        self._lock = threading.Lock()

    def generate_and_send(self, identifier: str) -> str:
        """
        identifier: phone number or email
        Returns OTP (in prod: only send via SMS, don't return)
        """
        otp = ''.join([str(secrets.randbelow(10)) for _ in range(self.OTP_LENGTH)])
        otp_hash = hashlib.sha256(otp.encode()).hexdigest()

        with self._lock:
            self._otps[identifier] = {
                "hash":       otp_hash,
                "expires_at": datetime.now() + self.OTP_EXPIRY,
                "attempts":   0
            }

        # Production: exotel_service.send_sms(identifier, f"Your OTP: {otp}")
        print(f"[OTP] Sending to {identifier}: {otp}")
        return otp   # Remove this in production!

    def verify(self, identifier: str, otp: str) -> bool:
        with self._lock:
            stored = self._otps.get(identifier)
            if not stored:
                return False
            if datetime.now() > stored["expires_at"]:
                del self._otps[identifier]
                return False
            if stored["attempts"] >= 3:
                return False   # OTP brute force protection

            stored["attempts"] += 1
            if hmac.compare_digest(hashlib.sha256(otp.encode()).hexdigest(), stored["hash"]):
                del self._otps[identifier]   # Single use
                return True
            return False


# ═══════════════════════════════════════════════════════════════
# INPUT VALIDATION
# ═══════════════════════════════════════════════════════════════

class InputValidator:
    EMAIL_REGEX    = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')
    PASSWORD_MIN   = 8
    PASSWORD_MAX   = 128

    @classmethod
    def validate_email(cls, email: str) -> str:
        email = email.strip().lower()
        if not email or not cls.EMAIL_REGEX.match(email):
            raise ValueError("Invalid email format")
        return email

    @classmethod
    def validate_password(cls, password: str) -> str:
        if len(password) < cls.PASSWORD_MIN:
            raise ValueError(f"Password must be at least {cls.PASSWORD_MIN} characters")
        if len(password) > cls.PASSWORD_MAX:
            raise ValueError(f"Password too long")
        return password

    @classmethod
    def validate_password_strength(cls, password: str) -> list:
        """Returns list of unmet requirements"""
        issues = []
        if not re.search(r'[A-Z]', password): issues.append("uppercase letter")
        if not re.search(r'[a-z]', password): issues.append("lowercase letter")
        if not re.search(r'\d', password):     issues.append("number")
        if not re.search(r'[^A-Za-z0-9]', password): issues.append("special character")
        return issues


# ═══════════════════════════════════════════════════════════════
# AUTH SERVICE — Main Facade
# ═══════════════════════════════════════════════════════════════

@dataclass
class LoginResponse:
    success:       bool
    access_token:  Optional[str] = None
    refresh_token: Optional[str] = None
    mfa_required:  bool = False
    mfa_token:     Optional[str] = None   # Partial auth token for MFA step
    user_id:       Optional[str] = None
    message:       str = ""


class AuthService:
    """
    Facade: orchestrates all auth operations.
    Single entry point for login, register, logout, refresh, reset.
    """

    MAX_FAILED_ATTEMPTS = 5
    LOCK_DURATION       = timedelta(minutes=15)

    def __init__(self):
        self._users:        Dict[str, User]  = {}   # email → User
        self._users_by_id:  Dict[str, User]  = {}   # user_id → User
        self._rate_limiter  = LoginRateLimiter()
        self._token_store   = TokenStore()
        self._otp_service   = OTPService()
        self._jwt_service   = JWTService()
        self._hasher        = PasswordHasher()
        self._validator     = InputValidator()

    # ─── REGISTER ────────────────────────────────────────────

    def register(self, email: str, password: str, role: str = "user") -> User:
        email    = self._validator.validate_email(email)
        password = self._validator.validate_password(password)

        strength_issues = self._validator.validate_password_strength(password)
        if strength_issues:
            raise ValueError(f"Password must contain: {', '.join(strength_issues)}")

        if email in self._users:
            # Don't reveal: "Email already registered"
            # Instead: send "You already have an account" email and return same response
            raise ValueError("Registration failed. Please try again or login.")

        user = User(
            email         = email,
            password_hash = self._hasher.hash(password),
            status        = AccountStatus.UNVERIFIED,
            role          = role
        )
        self._users[email]            = user
        self._users_by_id[user.user_id] = user

        # Send verification email
        verify_token = secrets.token_urlsafe(32)
        self._token_store.store(verify_token, user.user_id, "email_verify", timedelta(hours=24))
        print(f"[AUTH] Verification email → {email}: token={verify_token[:8]}...")

        return user

    # ─── LOGIN ───────────────────────────────────────────────

    def login(self, email: str, password: str, ip: str = "0.0.0.0") -> LoginResponse:
        """
        Full login flow with all scenarios handled.
        Always returns same error message for security.
        Always takes similar time (timing attack prevention).
        """
        # STEP 1: Input validation
        try:
            email = self._validator.validate_email(email)
        except ValueError:
            return LoginResponse(success=False, message="Invalid email or password.")

        # STEP 2: Rate limit check
        try:
            self._rate_limiter.check_and_record(email, ip)
        except AuthError as e:
            return LoginResponse(success=False, message=str(e), mfa_required=False)

        # STEP 3: User lookup
        user = self._users.get(email)

        if user is None:
            # SCENARIO A: User not found
            # Still run dummy hash to prevent timing attack
            self._hasher.dummy_verify()
            self._record_failed_attempt_no_user(email, ip)
            print(f"[AUTH] Login failed — user not found: {email}")
            return LoginResponse(success=False, message="Invalid email or password.")

        # STEP 4: Account status checks
        if user.is_locked():
            minutes_left = int((user.locked_until - datetime.now()).total_seconds() / 60)
            print(f"[AUTH] Login blocked — account locked: {email}")
            return LoginResponse(
                success=False,
                message=f"Account locked. Try again in {minutes_left} minutes."
            )

        if user.status == AccountStatus.UNVERIFIED:
            print(f"[AUTH] Login blocked — email not verified: {email}")
            return LoginResponse(
                success=False,
                message="Please verify your email before logging in."
            )

        if user.status == AccountStatus.DEACTIVATED:
            print(f"[AUTH] Login blocked — account deactivated: {email}")
            return LoginResponse(
                success=False,
                message="Account deactivated. Contact support."
            )

        if user.status == AccountStatus.DELETED:
            # Don't reveal account exists — treat as not found
            self._hasher.dummy_verify()
            return LoginResponse(success=False, message="Invalid email or password.")

        # STEP 5: Password verification
        if not self._hasher.verify(password, user.password_hash):
            # SCENARIO B: Wrong password
            self._record_failed_attempt(user)
            locked_msg = ""
            if user.status == AccountStatus.LOCKED:
                locked_msg = " Account locked for 15 minutes."
            print(f"[AUTH] Login failed — wrong password: {email} (attempt {user.failed_attempts})")
            return LoginResponse(
                success=False,
                message=f"Invalid email or password.{locked_msg}"
            )

        # Password correct — reset failed attempts
        user.failed_attempts = 0
        self._rate_limiter.reset_email(email)

        # STEP 6: MFA check
        if user.mfa_enabled:
            # Issue partial token — only /verify-mfa endpoint accessible
            mfa_token = self._jwt_service.create_access_token(
                user.user_id, user.role, mfa_verified=False
            )
            print(f"[AUTH] MFA required: {email}")
            return LoginResponse(
                success=True,
                mfa_required=True,
                mfa_token=mfa_token,
                message="MFA verification required."
            )

        # STEP 7: Issue tokens
        return self._issue_tokens(user)

    # ─── MFA VERIFY ──────────────────────────────────────────

    def verify_mfa(self, partial_token: str, otp: str) -> LoginResponse:
        """Step 2 of MFA login"""
        try:
            payload = self._jwt_service.verify_access_token(partial_token)
        except AuthError:
            return LoginResponse(success=False, message="Invalid session. Login again.")

        if payload.get("mfa_verified"):
            return LoginResponse(success=False, message="Already authenticated.")

        user = self._users_by_id.get(payload["sub"])
        if not user:
            return LoginResponse(success=False, message="User not found.")

        if not self._otp_service.verify(user.email, otp):
            return LoginResponse(success=False, message="Invalid or expired OTP.")

        return self._issue_tokens(user)

    # ─── REFRESH TOKEN ───────────────────────────────────────

    def refresh_access_token(self, refresh_token: str) -> LoginResponse:
        """Exchange valid refresh token for new access token"""
        user_id = self._token_store.peek(refresh_token, "refresh")
        if not user_id:
            return LoginResponse(success=False, message="Invalid or expired refresh token.")

        user = self._users_by_id.get(user_id)
        if not user or user.status != AccountStatus.ACTIVE:
            return LoginResponse(success=False, message="Account inactive.")

        # Rotate refresh token (invalidate old, issue new)
        self._token_store.verify_and_consume(refresh_token, "refresh")
        new_refresh = self._jwt_service.create_refresh_token()
        self._token_store.store(new_refresh, user_id, "refresh",
                                self._jwt_service.REFRESH_TOKEN_EXPIRY)
        access = self._jwt_service.create_access_token(user.user_id, user.role)

        print(f"[AUTH] Token refreshed: {user.email}")
        return LoginResponse(
            success=True,
            access_token=access,
            refresh_token=new_refresh
        )

    # ─── LOGOUT ──────────────────────────────────────────────

    def logout(self, user_id: str, refresh_token: str = None) -> bool:
        """
        JWT access token can't be revoked (stateless).
        Revoke refresh token → user must re-login after access expires.
        For "logout all devices": revoke all refresh tokens for user.
        """
        if refresh_token:
            self._token_store.verify_and_consume(refresh_token, "refresh")
        print(f"[AUTH] Logout: {user_id}")
        return True

    def logout_all_devices(self, user_id: str) -> bool:
        self._token_store.revoke_user_tokens(user_id, "refresh")
        print(f"[AUTH] Logout all devices: {user_id}")
        return True

    # ─── PASSWORD RESET ──────────────────────────────────────

    def request_password_reset(self, email: str) -> None:
        """
        Always return same response whether email exists or not.
        Security: don't reveal if email is registered.
        """
        user = self._users.get(email.strip().lower())
        if user and user.status == AccountStatus.ACTIVE:
            token = secrets.token_urlsafe(32)
            self._token_store.store(token, user.user_id, "password_reset", timedelta(hours=1))
            # email_service.send(user.email, f"Reset link: /reset?token={token}")
            print(f"[AUTH] Password reset email → {email}: token={token[:8]}...")
        # Always same response to caller regardless
        print(f"[AUTH] Reset requested for: {email} (sent if registered)")

    def reset_password(self, token: str, new_password: str) -> bool:
        """Verify token → update password → invalidate all sessions"""
        try:
            new_password = self._validator.validate_password(new_password)
        except ValueError as e:
            raise AuthError(LoginFailureReason.WRONG_PASSWORD, str(e), 400)

        user_id = self._token_store.verify_and_consume(token, "password_reset")
        if not user_id:
            raise AuthError(
                LoginFailureReason.WRONG_PASSWORD,
                "Invalid or expired reset link.",
                400
            )
        user = self._users_by_id.get(user_id)
        if not user:
            return False

        user.password_hash = self._hasher.hash(new_password)
        # Logout all devices — old tokens useless
        self._token_store.revoke_user_tokens(user_id, "refresh")
        print(f"[AUTH] Password reset complete: {user.email}")
        return True

    # ─── EMAIL VERIFICATION ──────────────────────────────────

    def verify_email(self, token: str) -> bool:
        user_id = self._token_store.verify_and_consume(token, "email_verify")
        if not user_id:
            return False
        user = self._users_by_id.get(user_id)
        if user:
            user.email_verified = True
            user.status         = AccountStatus.ACTIVE
            print(f"[AUTH] Email verified: {user.email}")
            return True
        return False

    # ─── OAUTH (Social Login) ────────────────────────────────

    def oauth_login(self, provider: str, email: str, name: str, provider_id: str) -> LoginResponse:
        """
        Called after OAuth provider returns user info.
        User exists → login. User doesn't exist → auto-register.
        """
        email = email.strip().lower()
        user  = self._users.get(email)

        if not user:
            # Auto-register from OAuth — no password needed
            user = User(
                email        = email,
                password_hash = "",            # No password for OAuth users
                status       = AccountStatus.ACTIVE,  # Pre-verified by provider
                email_verified = True
            )
            self._users[email]              = user
            self._users_by_id[user.user_id] = user
            print(f"[AUTH] OAuth auto-register: {email} via {provider}")

        if user.status != AccountStatus.ACTIVE:
            return LoginResponse(success=False, message="Account inactive.")

        user.last_login = datetime.now()
        return self._issue_tokens(user)

    # ─── HELPERS ─────────────────────────────────────────────

    def _issue_tokens(self, user: User) -> LoginResponse:
        user.last_login = datetime.now()
        access_token  = self._jwt_service.create_access_token(user.user_id, user.role)
        refresh_token = self._jwt_service.create_refresh_token()
        self._token_store.store(
            refresh_token, user.user_id, "refresh",
            self._jwt_service.REFRESH_TOKEN_EXPIRY
        )
        print(f"[AUTH] Login success: {user.email} | role={user.role}")
        return LoginResponse(
            success=True,
            access_token=access_token,
            refresh_token=refresh_token,
            user_id=user.user_id,
            message="Login successful."
        )

    def _record_failed_attempt(self, user: User) -> None:
        user.failed_attempts += 1
        if user.failed_attempts >= self.MAX_FAILED_ATTEMPTS:
            user.status      = AccountStatus.LOCKED
            user.locked_until = datetime.now() + self.LOCK_DURATION
            print(f"[AUTH] Account LOCKED: {user.email} (5 failed attempts)")

    def _record_failed_attempt_no_user(self, email: str, ip: str) -> None:
        """Track failed attempts for non-existent emails too (prevent enumeration)"""
        pass  # Rate limiter already handles this

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        return self._users_by_id.get(user_id)
```

---

## DEMO — All Scenarios

```python
auth = AuthService()

# ─── Register + Verify ───────────────────────────────────────
print("=" * 55)
print("SCENARIO: Register + Verify Email")
print("=" * 55)
user = auth.register("rahul@gmail.com", "SecurePass@123")
# Simulate email verification
verify_token = list(auth._token_store._tokens.values())[0]
raw = "dummy"  # In real test, capture from register
# auth.verify_email(raw_verify_token)
user.status = AccountStatus.ACTIVE  # Force for demo


# ─── Scenario A: User Not Found ──────────────────────────────
print("\n" + "=" * 55)
print("SCENARIO A: User not found")
print("=" * 55)
resp = auth.login("notexist@gmail.com", "anypass", ip="1.2.3.4")
print(f"Response: {resp.message}")   # "Invalid email or password"


# ─── Scenario B: Wrong Password ──────────────────────────────
print("\n" + "=" * 55)
print("SCENARIO B: Wrong password")
print("=" * 55)
for i in range(6):
    resp = auth.login("rahul@gmail.com", "wrongpass", ip="1.2.3.4")
    print(f"Attempt {i+1}: {resp.message}")


# ─── Scenario C: Account Locked ──────────────────────────────
print("\n" + "=" * 55)
print("SCENARIO C: Account now locked")
print("=" * 55)
resp = auth.login("rahul@gmail.com", "SecurePass@123", ip="1.2.3.4")
print(f"Correct password but locked: {resp.message}")


# ─── Reset lock, Normal Login ────────────────────────────────
print("\n" + "=" * 55)
print("SCENARIO D: Normal successful login")
print("=" * 55)
user.status         = AccountStatus.ACTIVE
user.failed_attempts = 0
resp = auth.login("rahul@gmail.com", "SecurePass@123", ip="5.6.7.8")
print(f"Success: {resp.success} | Token: {resp.access_token[:20]}...")


# ─── Refresh Token ───────────────────────────────────────────
print("\n" + "=" * 55)
print("SCENARIO E: Refresh access token")
print("=" * 55)
refresh_resp = auth.refresh_access_token(resp.refresh_token)
print(f"New access token: {refresh_resp.access_token[:20]}...")


# ─── Password Reset ──────────────────────────────────────────
print("\n" + "=" * 55)
print("SCENARIO F: Password Reset")
print("=" * 55)
auth.request_password_reset("rahul@gmail.com")
auth.request_password_reset("ghost@gmail.com")  # Same response


# ─── OAuth Login ─────────────────────────────────────────────
print("\n" + "=" * 55)
print("SCENARIO G: Google OAuth — new user")
print("=" * 55)
oauth_resp = auth.oauth_login("google", "james@gmail.com", "James Mwangi", "google_123")
print(f"OAuth login: {oauth_resp.success} | {oauth_resp.message}")

# Second time — existing user
oauth_resp2 = auth.oauth_login("google", "james@gmail.com", "James Mwangi", "google_123")
print(f"OAuth login again: {oauth_resp2.success}")


# ─── Rate Limiting ───────────────────────────────────────────
print("\n" + "=" * 55)
print("SCENARIO H: Rate limiting (same IP, many attempts)")
print("=" * 55)
# Register multiple test users
for i in range(5):
    try:
        u = auth.register(f"test{i}@gmail.com", "TestPass@123")
        u.status = AccountStatus.ACTIVE
    except: pass

same_ip = "9.9.9.9"
for i in range(25):
    try:
        auth.login(f"test{i%5}@gmail.com", "wrongpass", ip=same_ip)
    except Exception as e:
        print(f"Request {i+1}: {e}")
        break
```

---

## HTTP Response Codes

```
200 OK             → Login success, token issued
400 Bad Request    → Invalid email format, password too short
401 Unauthorized   → Invalid credentials (user not found OR wrong password)
403 Forbidden      → Email not verified, account deactivated
423 Locked         → Too many failed attempts, account locked
429 Too Many Req   → Rate limit exceeded
500 Server Error   → Unexpected error (never reveal internals)

Security rule:
  401 for wrong creds — never distinguish "user not found" vs "wrong password"
  Same error message: "Invalid email or password"
  Same response time (timing attack prevention)
```

---

## Interview Q&A

**Q: "User DB mein nahi hai — kya response doge?"**
> "Same error message: 'Invalid email or password' — user not found aur wrong password dono ke liye same. Reason: agar alag message dein to attacker enumerate kar sakta hai ki kaun se emails registered hain. Timing attack bhi prevent karna hoga — jab user nahi hota tab password hash comparison nahi hoti (fast response). Attacker response time measure karke email existence detect kar sakta hai. Fix: dummy_verify() call karo even when user not found — same bcrypt time lage. Redis mein attempt count bhi track karo non-existent emails ke liye bhi."

**Q: "JWT vs Session — Niroskos mein kya use kiya?"**
> "JWT with refresh token pattern. Access token 15-minute expiry — stateless, no DB lookup per request. Refresh token opaque, 7-day expiry, stored in DB. Access token expire hone pe refresh token use karo naya access token lo. Logout pe refresh token DB se delete karo — user next request pe re-login karna padega (access token expire hone ke baad). This gives: stateless performance benefit of JWT + revocability of session tokens. Mobile clients ke liye especially good — no cookie dependency."

**Q: "Brute force attacks kaise rokoge?"**
> "Multiple layers. First: account-level lockout — 5 consecutive failures → account locked for 15 minutes. Incremental: 5 failures → 15 min, unlock → 3 more failures → 1 hour. Second: IP-based rate limiting — 20 attempts per 15 minutes from one IP → IP blocked. Third: CAPTCHA after 3 failures. Fourth: bcrypt with high rounds — deliberately slow hash means brute force is computationally expensive even for attacker with DB access. Fifth: anomaly detection — new country/device login → require email verification or MFA."

**Q: "Password reset flow — security considerations?"**
> "Token must be: cryptographically random (secrets.token_urlsafe(32)), single-use (mark used after first use), short-lived (1 hour), stored as hash in DB (not raw). Reset page must: invalidate token after use, invalidate all active sessions (user logs out everywhere), not reveal if email is registered. Common mistake: predictable tokens (user_id + timestamp base64) — easily guessable. Another: long-lived tokens — attacker intercepts email, has unlimited time. Another: not invalidating other sessions — attacker already logged in stays in."

---

*Last Updated: April 2026 | SDE-2 Interview Prep*
