# Cryptography Basics — Hashing, HMAC, Symmetric, Asymmetric, TLS

## Quick Concepts

**WHAT:**
- **Hashing** = One-way function (irreversible) — passwords, integrity
- **Encryption** = Reversible — protect data in transit/rest
- **Symmetric** = Same key encrypts + decrypts (AES) — fast
- **Asymmetric** = Public + Private key pair (RSA, ECDSA) — slower
- **HMAC** = Hash-based MAC for authentication (webhook signing)
- **TLS** = Transport encryption (HTTPS) — uses symmetric + asymmetric

**WHY senior engineers MUST know:**
- ❌ Wrong hashing algorithm = passwords cracked
- ❌ No HMAC = webhook can be forged
- ❌ Hardcoded keys = secrets leak in code
- ❌ Wrong cipher mode = "encrypted" data decryptable

**HOW algorithms compare:**

```
Use case             | Algorithm        | Why
---------------------|------------------|-----------------------------
Password hashing     | bcrypt / argon2  | Slow (resists brute force)
General hashing      | SHA-256          | Fast (integrity check)
API signing          | HMAC-SHA256      | Authentication + integrity
Encrypt data at rest | AES-256-GCM      | Fast symmetric
Encrypt in transit   | TLS 1.3          | Hybrid (RSA/ECDSA + AES)
Token signing        | RS256 / ES256    | Asymmetric (verify-only public)
File integrity       | SHA-256 / Blake3 | Fast hashing
```

---

## Interview Questions & Answers

### Q1: Password hashing — bcrypt vs argon2 vs scrypt?

**Answer:**

**WHAT:** Adaptive hash functions designed to be SLOW (resist brute force).

**WHY plain SHA-256 is WRONG for passwords:**
```
SHA-256 is FAST (designed for performance):
- Modern GPU: 10 billion SHA-256/sec
- 8-char password = brute force in hours
- Need 10,000x slower algorithm
```

**HOW — Algorithm comparison:**

| Algorithm | Year | Resists GPU | Memory hard | Recommended |
|---|---|---|---|---|
| **MD5 / SHA-1** | 1991/1995 | ❌ NO | ❌ | ❌ NEVER |
| **PBKDF2** | 2000 | ⚠️ Partial | ❌ | ⚠️ Legacy only |
| **bcrypt** | 1999 | ✅ Yes | ⚠️ Limited | ✅ Good |
| **scrypt** | 2009 | ✅ Yes | ✅ Yes | ✅ Good |
| **argon2id** | 2015 | ✅ Yes | ✅ Yes | ✅ BEST (modern) |

**HOW — bcrypt (most common):**

```python
# pip install bcrypt

import bcrypt

# Hash password (cost factor 12 = 4096 iterations)
password = b"my-secret-password"
hashed = bcrypt.hashpw(password, bcrypt.gensalt(rounds=12))
# Result: b'$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW'
#         │ │  │  │                      │
#         │ │  │  │                      └ hash + salt embedded
#         │ │  │  └ salt
#         │ │  └ cost factor (2^12 iterations)
#         │ └ version (2b)
#         └ identifier ($)

# Verify password
is_valid = bcrypt.checkpw(password, hashed)


# Cost factor tuning:
# Cost 10: ~50ms per hash (default, OK)
# Cost 12: ~200ms (recommended 2024)
# Cost 14: ~800ms (high security)
# Aim: ~300ms (slow enough to deter brute force, fast enough for UX)
```

**HOW — argon2id (modern recommendation):**

```python
# pip install argon2-cffi

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

# Default params (RFC 9106 recommended)
ph = PasswordHasher(
    time_cost=3,        # iterations
    memory_cost=65536,  # 64 MB
    parallelism=4,      # threads
)

# Hash
password = "my-secret-password"
hashed = ph.hash(password)
# Result: $argon2id$v=19$m=65536,t=3,p=4$<salt>$<hash>

# Verify
try:
    ph.verify(hashed, password)
    print("Password valid")
except VerifyMismatchError:
    print("Password invalid")

# ⭐ Auto-upgrade: check if hash needs rehash (params changed)
if ph.check_needs_rehash(hashed):
    new_hash = ph.hash(password)
    # Update DB with new_hash
```

**WHY argon2id over bcrypt (modern recommendation):**
- ✅ Memory-hard (GPU attacks expensive)
- ✅ Resistant to side-channel attacks
- ✅ Tunable parameters
- ✅ Winner of Password Hashing Competition (2015)

---

### Q2: HMAC kya hai? Webhook signing kaise karte hain?

**Answer:**

**WHAT:** HMAC (Hash-based Message Authentication Code) = hash + secret key.

**WHY:**
- Verify message integrity (not tampered)
- Verify sender authenticity (knows secret)
- Used by: AWS API signing, Stripe webhooks, GitHub webhooks

**HOW — HMAC works:**

```
Sender:
  message = "user_id=123&amount=100"
  signature = HMAC-SHA256(secret, message)
  Send: message + signature

Receiver:
  Recomputes: expected = HMAC-SHA256(secret, message)
  Compares: signature == expected ?
  Match → trusted, no tampering
```

**HOW — Webhook signing pattern (Stripe-style):**

```python
import hmac
import hashlib
import time
from typing import Optional

class WebhookSigner:
    """
    INTERVIEW: HMAC webhook signing.
    Prevents spoofed webhooks + replay attacks.
    """
    def __init__(self, secret: str):
        self.secret = secret.encode()

    def sign(self, payload: bytes, timestamp: Optional[int] = None) -> str:
        """
        Format: t={timestamp},v1={signature}
        """
        ts = timestamp or int(time.time())
        signed_payload = f"{ts}.".encode() + payload

        signature = hmac.new(
            self.secret,
            signed_payload,
            hashlib.sha256
        ).hexdigest()

        return f"t={ts},v1={signature}"

    def verify(self, payload: bytes, signature_header: str, tolerance_seconds: int = 300) -> bool:
        """
        Verify webhook signature.
        Rejects if older than tolerance (prevents replay).
        """
        # Parse header
        parts = dict(p.split("=", 1) for p in signature_header.split(","))
        timestamp = int(parts.get("t", 0))
        provided_sig = parts.get("v1", "")

        # ⭐ Reject if too old (replay attack prevention)
        if abs(time.time() - timestamp) > tolerance_seconds:
            return False

        # Recompute expected signature
        signed_payload = f"{timestamp}.".encode() + payload
        expected = hmac.new(
            self.secret,
            signed_payload,
            hashlib.sha256
        ).hexdigest()

        # ⭐ Use constant-time comparison (prevent timing attack)
        return hmac.compare_digest(provided_sig, expected)


# ─── Sender (webhook producer) ─────────────────────────────────
signer = WebhookSigner(secret="whsec_abc123")
payload = b'{"event": "order.created", "id": "ord_123"}'
signature = signer.sign(payload)

# Send HTTP request
import httpx
async with httpx.AsyncClient() as client:
    await client.post(
        "https://example.com/webhooks/orders",
        content=payload,
        headers={
            "Stripe-Signature": signature,
            "Content-Type": "application/json",
        }
    )


# ─── Receiver (webhook consumer) ───────────────────────────────
from fastapi import FastAPI, Request, HTTPException

app = FastAPI()
verifier = WebhookSigner(secret="whsec_abc123")   # Same secret

@app.post("/webhooks/orders")
async def receive_webhook(request: Request):
    # Get raw body (don't parse JSON yet)
    raw_body = await request.body()
    signature = request.headers.get("Stripe-Signature", "")

    # ⭐ Verify signature
    if not verifier.verify(raw_body, signature):
        raise HTTPException(401, "Invalid signature")

    # NOW parse JSON
    import json
    payload = json.loads(raw_body)
    # Process webhook...
```

**Critical: `hmac.compare_digest()` prevents timing attacks:**

```python
# ❌ INSECURE: regular == comparison
if provided_sig == expected:    # Time depends on first different char!
    pass

# ✅ SECURE: constant-time comparison
if hmac.compare_digest(provided_sig, expected):    # Same time always
    pass
```

---

### Q3: Symmetric vs Asymmetric encryption — kab kya?

**Answer:**

**WHAT:**
- **Symmetric** = Same key for encrypt + decrypt
- **Asymmetric** = Public key encrypts, Private key decrypts (or vice versa for signing)

**WHY both exist:**
- Symmetric: FAST (megabytes/sec) — for data
- Asymmetric: SLOW (kilobytes/sec) — for key exchange

**HOW — TLS uses both (hybrid):**
```
1. Client + Server do asymmetric handshake (slow, once)
2. Agree on shared symmetric key
3. Encrypt actual traffic with symmetric (fast)
```

**HOW — AES symmetric encryption:**

```python
# pip install cryptography

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os

# Generate random 256-bit key
key = AESGCM.generate_key(bit_length=256)
# Or load from secret manager (NEVER hardcode)

aesgcm = AESGCM(key)

# Encrypt
plaintext = b"my secret data"
nonce = os.urandom(12)              # ⭐ MUST be unique per encryption
associated_data = b"public-context"  # Optional, authenticated but not encrypted
ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data)

# Decrypt
decrypted = aesgcm.decrypt(nonce, ciphertext, associated_data)
assert decrypted == plaintext

# Storage format: nonce + ciphertext (nonce is NOT secret, must be unique)
encrypted_blob = nonce + ciphertext
```

**WHY AES-GCM (not AES-CBC):**
- ✅ Authenticated (detects tampering)
- ✅ Parallelizable (fast)
- ✅ No padding oracles
- ❌ AES-CBC needs separate MAC

**HOW — RSA asymmetric:**

```python
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization

# Generate key pair (use 2048+ bits in production, 4096 for high security)
private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
)
public_key = private_key.public_key()

# Encrypt with public key
plaintext = b"secret message"
ciphertext = public_key.encrypt(
    plaintext,
    padding.OAEP(                     # ⭐ Use OAEP, NOT PKCS1v15
        mgf=padding.MGF1(algorithm=hashes.SHA256()),
        algorithm=hashes.SHA256(),
        label=None,
    )
)

# Decrypt with private key
plaintext_decrypted = private_key.decrypt(
    ciphertext,
    padding.OAEP(
        mgf=padding.MGF1(algorithm=hashes.SHA256()),
        algorithm=hashes.SHA256(),
        label=None,
    )
)

# Serialize keys for storage
private_pem = private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.BestAvailableEncryption(b"passphrase"),
)
public_pem = public_key.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
)
```

---

### Q4: RSA vs Ed25519 vs ECDSA — kab kya?

**Answer:**

**WHAT:** Different asymmetric algorithms with different trade-offs.

**HOW — Comparison:**

| Algorithm | Key Size | Speed | Security | Use Case |
|---|---|---|---|---|
| **RSA-2048** | 2048 bits | Slow | Good (2030+) | Legacy compat |
| **RSA-4096** | 4096 bits | Very slow | Excellent | High security legacy |
| **ECDSA P-256** | 256 bits | Fast | Excellent | TLS, JWT |
| **Ed25519** | 256 bits | Fastest | Best | Modern (SSH, JWT) |

**Performance comparison (signatures/sec):**
```
RSA-2048:    1000 signatures/sec
RSA-4096:     200 signatures/sec
ECDSA P-256:  10000 signatures/sec
Ed25519:      20000 signatures/sec
```

**HOW — Ed25519 (recommended for new projects):**

```python
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

# Generate
private_key = Ed25519PrivateKey.generate()
public_key = private_key.public_key()

# Sign
message = b"important message"
signature = private_key.sign(message)

# Verify (no exception if valid)
public_key.verify(signature, message)
```

**HOW — JWT signing algorithm choice:**

```python
import jwt

# HS256 — symmetric (server only)
token = jwt.encode({"user": "alice"}, "secret-key", algorithm="HS256")

# RS256 — asymmetric (microservices: only auth server can sign, anyone can verify)
private_key = ...
token = jwt.encode({"user": "alice"}, private_key, algorithm="RS256")
# Other services verify with public_key (no shared secret leak)

# ES256 — ECDSA (faster than RS256)
token = jwt.encode({"user": "alice"}, ec_private_key, algorithm="ES256")

# EdDSA — Ed25519 (fastest, modern)
token = jwt.encode({"user": "alice"}, ed25519_private_key, algorithm="EdDSA")
```

**Decision tree:**
- Single service / monolith → HS256 (HMAC, simpler)
- Multi-service / public API → RS256 or ES256 (asymmetric)
- New project / max performance → EdDSA (Ed25519)

---

### Q5: TLS/SSL handshake step-by-step?

**Answer:**

**WHAT:** Process to establish encrypted connection.

**HOW — TLS 1.3 handshake (1 RTT):**

```
Client                                    Server
  │                                         │
  │  1. ClientHello                         │
  │     - TLS version, cipher suites,       │
  │       supported groups, key share       │
  ├────────────────────────────────────────►│
  │                                         │
  │  2. ServerHello + Certificate +         │
  │     Key Share + Finished                │
  │◄────────────────────────────────────────┤
  │                                         │
  │  3. Verify cert chain (CA → cert)       │
  │  4. Derive shared secret (ECDHE)        │
  │  5. Client Finished                     │
  ├────────────────────────────────────────►│
  │                                         │
  │     ENCRYPTED APPLICATION DATA          │
  │◄═══════════════════════════════════════►│
```

**HOW — Each step explained:**

```python
# Conceptual (real TLS done by OpenSSL/library)

# Step 1: Client Hello
client_hello = {
    "tls_version": "1.3",
    "cipher_suites": ["TLS_AES_256_GCM_SHA384", "TLS_CHACHA20_POLY1305_SHA256"],
    "supported_groups": ["x25519", "secp256r1"],
    "key_share": {"x25519": client_public_key},  # Client's ECDHE key
    "server_name": "api.example.com",            # SNI
}

# Step 2: Server responds
server_response = {
    "selected_cipher": "TLS_AES_256_GCM_SHA384",
    "key_share": {"x25519": server_public_key},
    "certificate": server_cert,                  # Signed by CA
    "certificate_verify": server_signature,
    "encrypted_extensions": {...},
    "finished": server_finished,
}

# Step 3: Client verifies certificate chain
def verify_cert_chain(cert, ca_certs):
    """
    1. Verify cert signed by trusted CA
    2. Check certificate not expired
    3. Check certificate not revoked (CRL/OCSP)
    4. Check certificate domain matches (SAN/CN)
    """
    pass

# Step 4: Derive shared secret (ECDHE = Elliptic Curve Diffie-Hellman Ephemeral)
shared_secret = ECDHE(client_private, server_public)
# Both sides arrive at same secret without transmitting it

# Step 5: Derive symmetric keys
master_key = HKDF(shared_secret)
encryption_key = derive(master_key, "encryption")
mac_key = derive(master_key, "mac")

# Now use AES-GCM with encryption_key for all application data
```

**HOW — Verify cert in Python:**

```python
import ssl
import socket

context = ssl.create_default_context()
context.minimum_version = ssl.TLSVersion.TLSv1_2

# Connect + auto verify
with socket.create_connection(("api.example.com", 443)) as sock:
    with context.wrap_socket(sock, server_hostname="api.example.com") as ssock:
        cert = ssock.getpeercert()
        print(f"Cert subject: {cert['subject']}")
        print(f"Cert issuer: {cert['issuer']}")
        print(f"Valid until: {cert['notAfter']}")
```

---

### Q6: Certificate chain — kya hota hai?

**Answer:**

**WHAT:** Hierarchical trust:
```
Root CA (self-signed, in browser trust store)
   ↓ signs
Intermediate CA
   ↓ signs
Server Certificate (your domain)
```

**WHY chain (not direct):**
- Root CA private key NEVER online (offline, in vault)
- Intermediate CAs handle daily signing
- If intermediate compromised → revoke without losing root

**HOW — Verify chain:**

```python
from cryptography import x509
from cryptography.hazmat.backends import default_backend

def verify_cert_chain(server_cert_pem: bytes, ca_bundle_pem: bytes):
    """
    INTERVIEW: Cert chain verification.
    """
    # Load server cert
    server_cert = x509.load_pem_x509_certificate(server_cert_pem, default_backend())

    # Load CA bundle (intermediate + root)
    ca_certs = []
    while ca_bundle_pem:
        try:
            cert = x509.load_pem_x509_certificate(ca_bundle_pem, default_backend())
            ca_certs.append(cert)
            # Find next certificate in bundle
            # (real impl uses cryptography's verify methods)
        except ValueError:
            break

    # Verify chain:
    # 1. Server cert signed by first CA
    # 2. First CA signed by next CA
    # 3. ... until root CA
    # 4. Root CA in trusted list

    # Also check:
    # - Not expired
    # - Not revoked (CRL or OCSP)
    # - Domain matches SAN

    return True
```

---

### Q7: Let's Encrypt — auto-cert workflow?

**Answer:**

**WHAT:** Free CA with automated cert issuance (ACME protocol).

**HOW — Manual with certbot:**

```bash
# Install certbot
brew install certbot   # macOS
apt install certbot    # Ubuntu

# Get cert (HTTP-01 challenge — easiest)
sudo certbot certonly --standalone \
  -d api.example.com \
  -d www.example.com \
  --email admin@example.com \
  --agree-tos

# Cert files saved to:
# /etc/letsencrypt/live/api.example.com/fullchain.pem  ← cert + intermediates
# /etc/letsencrypt/live/api.example.com/privkey.pem    ← private key

# Auto-renewal (90-day expiry)
sudo certbot renew --dry-run
# Schedule via cron: 0 0,12 * * * certbot renew --quiet
```

**HOW — Kubernetes with cert-manager:**

```yaml
# 1. Install cert-manager
# kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml

# 2. Create ClusterIssuer
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@example.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
      - http01:
          ingress:
            class: nginx

# 3. Annotate Ingress to auto-cert
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: api-ingress
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
    - hosts: [api.example.com]
      secretName: api-tls-secret      # ⭐ Auto-created by cert-manager
  rules:
    - host: api.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: api-service
                port: { number: 80 }
```

---

### Q8: Salt vs Pepper — password hashing context?

**Answer:**

**WHAT:**
- **Salt** = Random per-user value (stored with hash)
- **Pepper** = Secret server-wide value (NOT stored with hash)

**WHY:**
```
Without salt:
- Same password → same hash
- Rainbow tables can crack quickly
- Hash leak = mass password compromise

With salt:
- Same password → different hash (each user)
- Rainbow tables useless
- Hash leak = individual brute force

With pepper:
- Even if DB stolen, pepper still safe
- Adds extra entropy
- Requires server-side secret
```

**HOW:**

```python
import bcrypt
import hmac
import hashlib
import secrets

class PasswordManager:
    """
    INTERVIEW: Defense-in-depth password hashing.
    Salt = automatic (bcrypt embeds it)
    Pepper = HMAC before hashing
    """
    def __init__(self, pepper: bytes):
        self.pepper = pepper   # From secret manager

    def hash_password(self, password: str) -> bytes:
        # Step 1: HMAC with pepper (adds server-side secret)
        peppered = hmac.new(
            self.pepper,
            password.encode(),
            hashlib.sha256
        ).digest()

        # Step 2: bcrypt with auto-salt
        hashed = bcrypt.hashpw(peppered, bcrypt.gensalt(rounds=12))
        return hashed

    def verify_password(self, password: str, stored_hash: bytes) -> bool:
        peppered = hmac.new(
            self.pepper,
            password.encode(),
            hashlib.sha256
        ).digest()
        return bcrypt.checkpw(peppered, stored_hash)


# Initialize with pepper from Secrets Manager
manager = PasswordManager(pepper=load_secret("password_pepper"))

# Hash on signup
user.password_hash = manager.hash_password("user-password")

# Verify on login
is_valid = manager.verify_password(input_password, user.password_hash)
```

---

## Cryptography Checklist

```markdown
### Password Storage
- [ ] bcrypt (cost 12+) OR argon2id
- [ ] NEVER MD5, SHA-1, SHA-256 alone
- [ ] Pepper from secret manager (defense in depth)
- [ ] Auto-rehash on parameter upgrade

### Token Signing
- [ ] HS256 for monolith
- [ ] RS256/ES256/EdDSA for microservices
- [ ] Key rotation via JWKS
- [ ] Short TTL (15 min access tokens)

### Data Encryption
- [ ] AES-256-GCM for symmetric
- [ ] Unique nonce per encryption
- [ ] Keys in AWS KMS / HashiCorp Vault
- [ ] Encrypt at rest AND in transit

### API Signing
- [ ] HMAC-SHA256 for webhooks
- [ ] constant-time compare (hmac.compare_digest)
- [ ] Include timestamp (replay prevention)
- [ ] Document signature format publicly

### TLS
- [ ] TLS 1.2 minimum, prefer 1.3
- [ ] Strong cipher suites only
- [ ] Auto-renew with cert-manager / certbot
- [ ] HSTS preload list
- [ ] Certificate transparency monitoring

### Key Management
- [ ] Generate keys in Hardware Security Module (HSM) if possible
- [ ] Rotate every 90-365 days
- [ ] Use ephemeral keys for forward secrecy
- [ ] Audit log all key usage
```

---

## Common Crypto Pitfalls

| Pitfall | Risk | Fix |
|---|---|---|
| MD5/SHA-1 for passwords | Cracked in seconds | bcrypt/argon2id |
| Plain SHA-256 for passwords | GPU brute force | bcrypt/argon2id |
| `==` comparison for HMAC | Timing attack | `hmac.compare_digest()` |
| Reuse AES nonce | Plaintext recovery | Unique nonce per message |
| AES-CBC without MAC | Padding oracle | AES-GCM (authenticated) |
| RSA-1024 | Crackable today | RSA-2048 minimum |
| Hardcoded keys in code | Repo leak = breach | Secrets manager |
| Self-signed certs in prod | MITM possible | Let's Encrypt / private CA |
| No cert pinning (mobile) | DNS hijack | Pin server cert |
| HTTP fallback | Downgrade attack | HSTS + force HTTPS |
