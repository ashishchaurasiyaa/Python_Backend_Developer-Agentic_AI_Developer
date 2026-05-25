"""
Phase3_Security — OAuth2 + Rate Limiting + Cryptography Practical
====================================================================
Topics covered:
  1. OAuth2 PKCE flow (code verifier + challenge)
  2. OAuth2 Client Credentials flow with token caching
  3. JWKS validation (asymmetric JWT)
  4. Token bucket rate limiter
  5. Sliding window rate limiter (Redis)
  6. Multi-tier rate limiting (IP + user + endpoint)
  7. bcrypt + argon2 password hashing
  8. HMAC webhook signing + verification
  9. AES-GCM symmetric encryption
  10. Constant-time comparison

Run:
  pip install bcrypt argon2-cffi cryptography pyjwt[crypto]
  python 02_oauth2_rate_limit_crypto_practical.py
"""

import asyncio
import base64
import hashlib
import hmac
import os
import secrets
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: OAuth2 PKCE Flow
# INTERVIEW: For SPA/mobile (public clients)
# ─────────────────────────────────────────────────────────────────────────────

def generate_pkce_pair() -> tuple[str, str]:
    """
    INTERVIEW: PKCE pair.
    - code_verifier: random string (saved by client)
    - code_challenge: SHA256(verifier) base64url-encoded
    """
    # 32 random bytes → 43-char base64url string
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")

    # SHA256 hash of verifier
    challenge_bytes = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(challenge_bytes).decode().rstrip("=")

    return code_verifier, code_challenge


def build_authorization_url(client_id: str, redirect_uri: str, scope: str,
                             challenge: str, state: str) -> str:
    """
    Build OAuth2 authorization URL for browser redirect.
    """
    import urllib.parse
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,                                   # CSRF protection
        "code_challenge": challenge,                       # ⭐ PKCE
        "code_challenge_method": "S256",                  # ⭐ SHA256
    }
    return f"https://auth.example.com/oauth/authorize?{urllib.parse.urlencode(params)}"


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: OAuth2 Client Credentials with Token Caching
# INTERVIEW: Service-to-service auth pattern
# ─────────────────────────────────────────────────────────────────────────────

class ClientCredentialsTokenProvider:
    """
    INTERVIEW: Production token provider.
    - Caches token in memory
    - Auto-refreshes before expiry (60s buffer)
    - Thread-safe (async lock)
    """
    def __init__(self, token_url: str, client_id: str, client_secret: str, scope: str):
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
        self._token: Optional[str] = None
        self._expires_at: float = 0
        self._lock = asyncio.Lock()

    async def get_token(self) -> str:
        async with self._lock:
            # Return cached if still valid
            if self._token and time.time() < self._expires_at - 60:
                return self._token

            # Fetch new token (simulated — real code uses httpx)
            # async with httpx.AsyncClient() as client:
            #     response = await client.post(self.token_url, data={
            #         "grant_type": "client_credentials",
            #         "client_id": self.client_id,
            #         "client_secret": self.client_secret,
            #         "scope": self.scope,
            #     })
            #     data = response.json()

            # Simulated response
            data = {
                "access_token": f"fake-jwt-{uuid.uuid4()}",
                "expires_in": 3600,
                "token_type": "Bearer"
            }

            self._token = data["access_token"]
            self._expires_at = time.time() + data["expires_in"]
            return self._token


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Token Bucket Rate Limiter
# INTERVIEW: Allows bursts within bucket capacity
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TokenBucket:
    """
    INTERVIEW: In-memory token bucket.
    For distributed: use Redis with Lua script (atomic).
    """
    capacity: int               # Max burst size
    refill_rate: float          # Tokens per second
    tokens: float = field(init=False)
    last_refill: float = field(init=False)

    def __post_init__(self):
        self.tokens = self.capacity
        self.last_refill = time.time()

    def try_consume(self, count: int = 1) -> bool:
        now = time.time()

        # Refill tokens since last check
        elapsed = now - self.last_refill
        self.tokens = min(
            self.capacity,
            self.tokens + elapsed * self.refill_rate
        )
        self.last_refill = now

        if self.tokens >= count:
            self.tokens -= count
            return True
        return False


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Sliding Window Rate Limiter (Redis-based simulation)
# INTERVIEW: More accurate than fixed window
# ─────────────────────────────────────────────────────────────────────────────

class SlidingWindowRateLimiter:
    """
    INTERVIEW: Sliding window using sorted set (in-memory simulation).
    In production: use Redis sorted sets.
    """
    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window = window_seconds
        self._requests = {}    # identifier → list of timestamps

    def is_allowed(self, identifier: str) -> tuple[bool, dict]:
        now = time.time()
        window_start = now - self.window

        # Get/init request list
        timestamps = self._requests.get(identifier, [])

        # Remove old timestamps
        timestamps = [ts for ts in timestamps if ts > window_start]

        # Count current
        current_count = len(timestamps)
        allowed = current_count < self.limit

        if allowed:
            timestamps.append(now)
            self._requests[identifier] = timestamps

        # Calculate reset time
        reset_at = timestamps[0] + self.window if timestamps else now + self.window
        retry_after = max(0, int(reset_at - now)) if not allowed else 0

        return allowed, {
            "limit": self.limit,
            "remaining": max(0, self.limit - len(timestamps)),
            "reset_at": int(reset_at),
            "retry_after": retry_after,
        }


# Redis Lua script (for production distributed setup)
REDIS_TOKEN_BUCKET_LUA = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(bucket[1]) or capacity
local last_refill = tonumber(bucket[2]) or now

-- Refill
local elapsed = now - last_refill
tokens = math.min(capacity, tokens + elapsed * refill_rate)

-- Try consume
local allowed = 0
if tokens >= 1 then
    tokens = tokens - 1
    allowed = 1
end

-- Save
redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
redis.call('EXPIRE', key, 3600)

return {allowed, tokens}
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Multi-Tier Rate Limiting
# INTERVIEW: Real production setup
# ─────────────────────────────────────────────────────────────────────────────

class MultiTierRateLimiter:
    """
    INTERVIEW: Layered rate limiting:
    - Global (DDoS)
    - Per IP
    - Per user
    - Per endpoint
    """
    def __init__(self):
        self.global_limiter = SlidingWindowRateLimiter(10000, 60)
        self.ip_limiter = SlidingWindowRateLimiter(100, 60)
        self.user_limiter = SlidingWindowRateLimiter(1000, 60)
        self.endpoint_limiters = {
            "/api/login": SlidingWindowRateLimiter(5, 60),    # Strict
            "/api/upload": SlidingWindowRateLimiter(10, 60),
        }

    def check(self, ip: str, user_id: Optional[str], endpoint: str) -> tuple[bool, dict]:
        # Check all applicable tiers
        global_ok, _ = self.global_limiter.is_allowed("global")
        if not global_ok:
            return False, {"failed_tier": "global"}

        ip_ok, ip_info = self.ip_limiter.is_allowed(f"ip:{ip}")
        if not ip_ok:
            return False, {"failed_tier": "ip", **ip_info}

        if user_id:
            user_ok, user_info = self.user_limiter.is_allowed(f"user:{user_id}")
            if not user_ok:
                return False, {"failed_tier": "user", **user_info}

        if endpoint in self.endpoint_limiters:
            ep_ok, ep_info = self.endpoint_limiters[endpoint].is_allowed(
                f"{endpoint}:{user_id or ip}"
            )
            if not ep_ok:
                return False, {"failed_tier": "endpoint", **ep_info}

        return True, {"status": "allowed"}


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Password Hashing (bcrypt vs argon2)
# INTERVIEW: bcrypt = default OK, argon2id = modern recommendation
# ─────────────────────────────────────────────────────────────────────────────

def hash_with_bcrypt(password: str) -> bytes:
    """
    INTERVIEW: bcrypt with cost factor 12.
    Cost 12 = ~200ms per hash (resistant to GPU brute force).
    """
    try:
        import bcrypt
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12))
    except ImportError:
        return b"<bcrypt not installed>"


def verify_with_bcrypt(password: str, stored_hash: bytes) -> bool:
    try:
        import bcrypt
        return bcrypt.checkpw(password.encode(), stored_hash)
    except ImportError:
        return False


def hash_with_argon2(password: str) -> str:
    """
    INTERVIEW: argon2id (winner of Password Hashing Competition).
    Memory-hard (resistant to GPU AND ASIC attacks).
    """
    try:
        from argon2 import PasswordHasher
        ph = PasswordHasher(
            time_cost=3,
            memory_cost=65536,    # 64 MB
            parallelism=4,
        )
        return ph.hash(password)
    except ImportError:
        return "<argon2 not installed>"


def hash_with_pepper(password: str, pepper: bytes) -> bytes:
    """
    INTERVIEW: Pepper = server-wide secret added BEFORE bcrypt.
    Defense in depth: if DB stolen, attacker still needs pepper.
    """
    # Step 1: HMAC with pepper
    peppered = hmac.new(pepper, password.encode(), hashlib.sha256).digest()

    # Step 2: bcrypt
    try:
        import bcrypt
        return bcrypt.hashpw(peppered, bcrypt.gensalt(rounds=12))
    except ImportError:
        return b"<bcrypt not installed>"


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: HMAC Webhook Signing
# INTERVIEW: Stripe-style webhook verification
# ─────────────────────────────────────────────────────────────────────────────

class WebhookSigner:
    """
    INTERVIEW: HMAC webhook signing.
    Format: t={timestamp},v1={signature}
    Prevents: spoofed webhooks + replay attacks
    """
    def __init__(self, secret: str):
        self.secret = secret.encode()

    def sign(self, payload: bytes, timestamp: Optional[int] = None) -> str:
        ts = timestamp or int(time.time())
        signed_payload = f"{ts}.".encode() + payload

        signature = hmac.new(
            self.secret,
            signed_payload,
            hashlib.sha256
        ).hexdigest()

        return f"t={ts},v1={signature}"

    def verify(self, payload: bytes, signature_header: str,
                tolerance_seconds: int = 300) -> bool:
        # Parse header
        parts = dict(p.split("=", 1) for p in signature_header.split(","))
        timestamp = int(parts.get("t", 0))
        provided_sig = parts.get("v1", "")

        # ⭐ Reject if too old (replay prevention)
        if abs(time.time() - timestamp) > tolerance_seconds:
            return False

        # Recompute expected
        signed_payload = f"{timestamp}.".encode() + payload
        expected = hmac.new(
            self.secret,
            signed_payload,
            hashlib.sha256
        ).hexdigest()

        # ⭐ Constant-time comparison
        return hmac.compare_digest(provided_sig, expected)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8: AES-GCM Symmetric Encryption
# INTERVIEW: For encrypting data at rest
# ─────────────────────────────────────────────────────────────────────────────

class AESGCMCipher:
    """
    INTERVIEW: AES-256-GCM authenticated encryption.
    - Encryption: keeps data secret
    - Authentication: detects tampering
    - Each encryption needs UNIQUE nonce
    """
    def __init__(self, key: bytes):
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            self.cipher = AESGCM(key)
        except ImportError:
            self.cipher = None

    def encrypt(self, plaintext: bytes, associated_data: bytes = b"") -> bytes:
        """Returns: nonce + ciphertext (concatenated)."""
        if not self.cipher:
            return b"<cryptography not installed>"

        nonce = os.urandom(12)    # ⭐ 96 bits, unique per encryption
        ciphertext = self.cipher.encrypt(nonce, plaintext, associated_data)
        return nonce + ciphertext

    def decrypt(self, encrypted: bytes, associated_data: bytes = b"") -> bytes:
        if not self.cipher:
            return b"<cryptography not installed>"

        nonce = encrypted[:12]
        ciphertext = encrypted[12:]
        return self.cipher.decrypt(nonce, ciphertext, associated_data)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 9: Demo Functions
# ─────────────────────────────────────────────────────────────────────────────

def demo_pkce():
    print("\n[PKCE Demo]")
    verifier, challenge = generate_pkce_pair()
    print(f"  code_verifier (43 chars):   {verifier}")
    print(f"  code_challenge (43 chars):  {challenge}")

    url = build_authorization_url(
        client_id="my-spa",
        redirect_uri="https://app.example.com/callback",
        scope="openid profile email",
        challenge=challenge,
        state=secrets.token_urlsafe(16)
    )
    print(f"  Auth URL: {url[:100]}...")


async def demo_token_caching():
    print("\n[OAuth2 Token Caching Demo]")
    provider = ClientCredentialsTokenProvider(
        token_url="https://auth.example.com/token",
        client_id="my-service",
        client_secret="secret",
        scope="read:users"
    )

    token1 = await provider.get_token()
    print(f"  First call:  {token1[:20]}...")

    token2 = await provider.get_token()
    print(f"  Cached call: {token2[:20]}...")

    assert token1 == token2
    print("  ✅ Token cached (only 1 actual fetch)")


def demo_token_bucket():
    print("\n[Token Bucket Demo]")
    bucket = TokenBucket(capacity=5, refill_rate=1)    # 5 burst, 1/sec sustain

    print(f"  Bucket: capacity=5, refill_rate=1/sec")

    # 5 quick requests — all allowed
    for i in range(7):
        allowed = bucket.try_consume()
        print(f"  Request {i+1}: {'✅ Allowed' if allowed else '❌ Rate limited'}")

    # Wait 2 sec — bucket refills 2 tokens
    print("  ⏳ Wait 2 seconds...")
    time.sleep(2)

    for i in range(3):
        allowed = bucket.try_consume()
        print(f"  Request {i+1}: {'✅ Allowed' if allowed else '❌ Rate limited'}")


def demo_sliding_window():
    print("\n[Sliding Window Rate Limiter Demo]")
    limiter = SlidingWindowRateLimiter(limit=3, window_seconds=5)

    print(f"  Limit: 3 requests per 5 seconds")

    for i in range(5):
        allowed, info = limiter.is_allowed("user-123")
        status = "✅" if allowed else "❌"
        print(f"  Request {i+1}: {status} | remaining={info['remaining']}, "
              f"retry_after={info.get('retry_after', 0)}s")


def demo_multi_tier():
    print("\n[Multi-Tier Rate Limiter Demo]")
    limiter = MultiTierRateLimiter()

    # Simulate brute force on login
    print("  Trying 10 login attempts (limit: 5/min)...")
    for i in range(10):
        allowed, info = limiter.check(
            ip="192.168.1.1",
            user_id="alice",
            endpoint="/api/login"
        )
        status = "✅" if allowed else f"❌ ({info.get('failed_tier')})"
        print(f"  Attempt {i+1}: {status}")


def demo_password_hashing():
    print("\n[Password Hashing Demo]")

    password = "my-super-secret-password"

    # bcrypt
    start = time.time()
    bcrypt_hash = hash_with_bcrypt(password)
    elapsed = (time.time() - start) * 1000
    print(f"  bcrypt: {bcrypt_hash[:40]}... ({elapsed:.0f}ms)")

    # Verify
    is_valid = verify_with_bcrypt(password, bcrypt_hash)
    print(f"  Verify correct password: {is_valid}")

    is_invalid = verify_with_bcrypt("wrong-password", bcrypt_hash)
    print(f"  Verify wrong password:   {is_invalid}")

    # argon2
    start = time.time()
    argon2_hash = hash_with_argon2(password)
    elapsed = (time.time() - start) * 1000
    print(f"  argon2id: {argon2_hash[:50]}... ({elapsed:.0f}ms)")


def demo_webhook_signing():
    print("\n[HMAC Webhook Signing Demo]")
    signer = WebhookSigner(secret="whsec_supersecret")
    verifier = WebhookSigner(secret="whsec_supersecret")    # Same key

    payload = b'{"event": "order.created", "id": "ord_123"}'
    signature = signer.sign(payload)
    print(f"  Payload:   {payload}")
    print(f"  Signature: {signature}")

    # Verify
    valid = verifier.verify(payload, signature)
    print(f"  ✅ Verify valid: {valid}")

    # Tampered payload
    tampered = b'{"event": "order.created", "id": "ord_999"}'    # Changed!
    valid = verifier.verify(tampered, signature)
    print(f"  ❌ Tampered payload: {valid}")

    # Replay attack (use old signature)
    old_sig = "t=1000000000,v1=abc"    # Very old timestamp
    valid = verifier.verify(payload, old_sig, tolerance_seconds=300)
    print(f"  ❌ Replay (old timestamp): {valid}")


def demo_aes_gcm():
    print("\n[AES-GCM Encryption Demo]")
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        key = AESGCM.generate_key(bit_length=256)
        cipher = AESGCMCipher(key)

        plaintext = b"sensitive customer data"
        encrypted = cipher.encrypt(plaintext, associated_data=b"user-123")

        print(f"  Plaintext:  {plaintext}")
        print(f"  Encrypted:  {encrypted.hex()[:60]}...")

        decrypted = cipher.decrypt(encrypted, associated_data=b"user-123")
        print(f"  Decrypted:  {decrypted}")
        assert decrypted == plaintext
        print("  ✅ Round-trip successful")
    except ImportError:
        print("  ⚠️ Install: pip install cryptography")


# ─────────────────────────────────────────────────────────────────────────────
# Q&A
# ─────────────────────────────────────────────────────────────────────────────

SECURITY_QA = [
    ("Why use PKCE for SPA/mobile?",
     "Public clients can't safely store client_secret.\n"
     "     PKCE: stolen code useless without code_verifier.\n"
     "     Mandatory in OAuth 2.1."),

    ("bcrypt cost factor 12 — why?",
     "~200ms per hash (good UX).\n"
     "     2^12 = 4096 iterations.\n"
     "     Increase to 14 in 2030 (Moore's law)."),

    ("Why argon2id over bcrypt?",
     "Memory-hard (resistant to GPU attacks).\n"
     "     Won Password Hashing Competition (2015).\n"
     "     Recommended by OWASP."),

    ("HMAC vs SHA256 — kab kya?",
     "SHA256: hash for integrity (anyone can compute).\n"
     "     HMAC: hash + secret key (authenticates sender).\n"
     "     Use HMAC for webhook signatures."),

    ("Why hmac.compare_digest()?",
     "Regular == compares char-by-char (timing attack).\n"
     "     compare_digest: constant time regardless of input.\n"
     "     Prevents inferring secret via timing."),

    ("AES-GCM vs AES-CBC?",
     "GCM: authenticated (detects tampering)\n"
     "     CBC: needs separate MAC (HMAC) for auth\n"
     "     Always use GCM (or ChaCha20-Poly1305)."),

    ("Why unique nonce per encryption?",
     "GCM nonce reuse = catastrophic.\n"
     "     Attacker can recover plaintext.\n"
     "     Use os.urandom(12) every time."),

    ("Why pepper + bcrypt?",
     "Defense in depth.\n"
     "     If DB stolen, hashes still need pepper.\n"
     "     Pepper from secrets manager (not DB)."),

    ("Sliding window vs fixed window?",
     "Fixed window: 2x burst at edge (10 req at 11:59, 10 at 12:00 = 20)\n"
     "     Sliding window: exact count, no edge issue\n"
     "     Sliding better for strict limits."),

    ("Multi-tier rate limit reasoning?",
     "IP only: shared IPs (NAT) over-blocked\n"
     "     User only: anonymous abuse OK\n"
     "     Endpoint: login needs stricter\n"
     "     Use ALL tiers, fail any = reject"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    print("=" * 60)
    print("OAUTH2 + RATE LIMITING + CRYPTOGRAPHY PRACTICAL")
    print("=" * 60)

    demo_pkce()
    await demo_token_caching()
    demo_token_bucket()
    demo_sliding_window()
    demo_multi_tier()
    demo_password_hashing()
    demo_webhook_signing()
    demo_aes_gcm()

    print("\n[OAuth2 Flow Decision Matrix]")
    flows = [
        ("Authorization Code + PKCE", "SPA, mobile apps"),
        ("Authorization Code", "Web app with backend"),
        ("Client Credentials", "Service-to-service"),
        ("Device Code", "TV, CLI, IoT"),
        ("Refresh Token", "All flows (renew access)"),
        ("Implicit (DEPRECATED)", "❌ Use PKCE instead"),
        ("Password (ROPC)", "❌ Avoid"),
    ]
    print(f"  {'Flow':<28} {'Use Case'}")
    print(f"  {'-'*28} {'-'*30}")
    for flow, use_case in flows:
        print(f"  {flow:<28} {use_case}")

    print("\n[Q&A Summary]")
    for q, a in SECURITY_QA:
        print(f"\n  Q: {q}")
        print(f"  A: {a}")

    print("\n" + "=" * 60)
    print("FILES TO KNOW:")
    print("  oauth2_client.py        → token provider + flows")
    print("  pkce.py                 → verifier/challenge generation")
    print("  rate_limiter.py         → token bucket + sliding window")
    print("  webhook_signing.py      → HMAC sign + verify")
    print("  password_hashing.py     → bcrypt + argon2 + pepper")
    print("  encryption.py           → AES-GCM for data at rest")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
