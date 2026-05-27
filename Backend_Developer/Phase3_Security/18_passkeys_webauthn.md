# Security — Passkeys & WebAuthn (FIDO2) for Backend Devs
**Phase 3 Security | Senior Backend + Agentic AI**

## Quick Concepts

- **WebAuthn** = W3C standard JS API for public-key authentication in browsers
- **FIDO2** = umbrella spec (WebAuthn + CTAP) for passwordless auth
- **CTAP2** = Client-to-Authenticator Protocol (browser ↔ authenticator)
- **Authenticator** = the device holding the private key (Touch ID, Windows Hello, YubiKey, phone)
- **Passkey** = a discoverable, syncable WebAuthn credential (Apple/Google/Microsoft sync them via cloud)
- **RP (Relying Party)** = your backend (the website / service)
- **Attestation** = proof of authenticator origin (during registration)
- **Assertion** = signed proof of possession (during login)
- **Public key** = stored on your server
- **Private key** = NEVER leaves the authenticator
- **Phishing-resistant** = passkeys cryptographically bind to your domain — can't be tricked by lookalike sites

---

## Why Every Backend Dev Must Know This in 2026

```
Adoption explosion (as of 2026):
─────────────────────────────────
✓ Apple — passkeys on iOS / macOS (iCloud Keychain sync)
✓ Google — passkeys on Android + Chrome (Google Password Manager)
✓ Microsoft — Windows Hello + Authenticator
✓ Major sites — Google, Microsoft, Amazon, PayPal, Best Buy,
                eBay, GitHub, Adobe, Shopify, Uber, Stripe
✓ 1Password, Bitwarden, Dashlane — all support passkeys

Why orgs are switching:
─────────────────────────
✗ Passwords are 80% of breaches
✗ Phishing kits steal MFA codes (SMS, TOTP)
✗ Account takeovers cost billions

✓ Passkeys are phishing-resistant by design
✓ Better UX (Face ID instead of password+OTP)
✓ Lower support costs (no password resets)
```

**Senior interview question: "Design passwordless auth for a fintech app."**
→ The answer is passkeys.

---

## Passkeys vs Old WebAuthn vs MFA — Quick Comparison

| Aspect | Password + TOTP | WebAuthn (classic) | Passkeys |
|---|---|---|---|
| Phishable | ✗ Yes | ✓ No | ✓ No |
| Device required | ✗ No | ✓ Yes (1 per device) | ✓ But synced! |
| Lost device = lockout | ✗ No | ✓ Often | ✗ No (cloud sync) |
| Multi-device | ✓ Yes | ✗ Need re-registration | ✓ Auto-syncs |
| UX | 😞 (2 steps) | 😐 (per device) | 😍 (Face ID once) |
| Server stores | password hash | public key | public key |
| User shares secret? | ✗ Yes (password) | ✓ No | ✓ No |

---

## The Two Ceremonies

### 1. Registration (one-time)

```
   User                  Browser              Your Backend          Authenticator
    │                      │                       │                     │
    │  "Sign me up"        │                       │                     │
    │─────────────────────►│                       │                     │
    │                      │  POST /register/start │                     │
    │                      │──────────────────────►│                     │
    │                      │                       │  Generates challenge │
    │                      │     options {        │  Stores in session   │
    │                      │   challenge, rpId,   │                     │
    │                      │   user, pubKeyCred } │                     │
    │                      │◄──────────────────────│                     │
    │                      │                                            │
    │                      │   navigator.credentials.create()           │
    │                      │───────────────────────────────────────────►│
    │   Face ID prompt     │                                            │
    │◄────────────────────────────────────────────────────────────────│
    │   Authorize          │                                            │
    │─────────────────────────────────────────────────────────────────►│
    │                      │                                            │
    │                      │   ◄ pubKey + attestation ──────────────────│
    │                      │                       │                     │
    │                      │  POST /register/finish│                     │
    │                      │──────────────────────►│  Verify attestation │
    │                      │                       │  Store public key   │
    │                      │   { success: true }   │                     │
    │                      │◄──────────────────────│                     │
```

### 2. Login (every time)

```
   User                  Browser              Your Backend          Authenticator
    │                      │  POST /login/start    │                     │
    │                      │──────────────────────►│  challenge          │
    │                      │   options {challenge} │  store in session   │
    │                      │◄──────────────────────│                     │
    │                      │                                            │
    │                      │   navigator.credentials.get()              │
    │                      │───────────────────────────────────────────►│
    │   Face ID            │                                            │
    │◄────────────────────────────────────────────────────────────────│
    │   Authorize          │                                            │
    │─────────────────────────────────────────────────────────────────►│
    │                      │   ◄ signed assertion ──────────────────────│
    │                      │  POST /login/finish   │                     │
    │                      │──────────────────────►│  Verify signature   │
    │                      │                       │  with stored pubKey │
    │                      │   { token: "jwt..."} │  Issue session      │
    │                      │◄──────────────────────│                     │
```

---

## Python Libraries (2026)

```
Recommended:
   ✓ webauthn (Duo) — pip install webauthn
       https://github.com/duo-labs/py_webauthn
       Most popular, well-maintained, simple API

Alternatives:
   - fido2 (Yubico) — lower-level, supports CTAP
   - python-fido2 — comprehensive but heavier
```

---

## FastAPI Implementation (End-to-End)

### Install

```bash
pip install fastapi 'webauthn>=2.0' redis sqlalchemy
```

### Schema

```python
# models.py
from sqlalchemy import Column, String, LargeBinary, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
import uuid

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, nullable=False, index=True)
    display_name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    credentials = relationship("Credential", back_populates="user")


class Credential(Base):
    """One row per registered passkey (a user can have many)."""
    __tablename__ = "credentials"

    id = Column(String, primary_key=True)  # base64url-encoded credential ID
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    public_key = Column(LargeBinary, nullable=False)
    sign_count = Column(Integer, default=0)  # anti-cloning counter
    transports = Column(String)  # comma-separated: "internal,hybrid"
    device_name = Column(String)  # "iPhone 15 — Touch ID"
    backed_up = Column(Integer, default=0)  # 1 = synced (true passkey)
    aaguid = Column(String)  # authenticator make/model
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used = Column(DateTime)

    user = relationship("User", back_populates="credentials")
```

### Configuration

```python
# config.py
RP_ID = "acme.com"                # your domain (NOT including https://)
RP_NAME = "Acme Corp"
RP_ORIGIN = "https://acme.com"    # full origin for verification

# For dev:
# RP_ID = "localhost"
# RP_ORIGIN = "http://localhost:3000"
```

### Registration Endpoints

```python
# routes_register.py
from fastapi import APIRouter, Depends, HTTPException
from webauthn import (
    generate_registration_options,
    verify_registration_response,
    options_to_json,
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    ResidentKeyRequirement,
    UserVerificationRequirement,
    AuthenticatorAttachment,
    PublicKeyCredentialDescriptor,
)
import json
from .config import RP_ID, RP_NAME, RP_ORIGIN
from .deps import get_db, get_redis, get_current_user

router = APIRouter(prefix="/auth/passkey")


@router.post("/register/start")
def register_start(
    user=Depends(get_current_user),
    db=Depends(get_db),
    redis=Depends(get_redis),
):
    """Generate challenge for new passkey registration."""

    # Exclude already-registered credentials (prevent duplicates)
    existing = db.query(Credential).filter_by(user_id=user.id).all()
    exclude = [
        PublicKeyCredentialDescriptor(id=bytes.fromhex(c.id))
        for c in existing
    ]

    options = generate_registration_options(
        rp_id=RP_ID,
        rp_name=RP_NAME,
        user_id=user.id.encode(),       # bytes, must be stable
        user_name=user.email,
        user_display_name=user.display_name,
        exclude_credentials=exclude,
        authenticator_selection=AuthenticatorSelectionCriteria(
            # Prefer platform authenticator (Touch ID, Face ID, Windows Hello)
            # but allow cross-platform (security keys, phones via hybrid)
            authenticator_attachment=AuthenticatorAttachment.PLATFORM,
            # Discoverable credential = a passkey (resident key on device)
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
    )

    # Store challenge in session (5 min TTL)
    redis.setex(
        f"register_challenge:{user.id}",
        300,
        options.challenge,
    )

    # Return as JSON the browser can pass to navigator.credentials.create()
    return json.loads(options_to_json(options))


@router.post("/register/finish")
def register_finish(
    credential_response: dict,
    device_name: str = "Unknown device",
    user=Depends(get_current_user),
    db=Depends(get_db),
    redis=Depends(get_redis),
):
    """Verify attestation and persist the public key."""

    expected_challenge = redis.get(f"register_challenge:{user.id}")
    if not expected_challenge:
        raise HTTPException(400, "Challenge expired or missing")

    try:
        verification = verify_registration_response(
            credential=credential_response,
            expected_challenge=expected_challenge,
            expected_origin=RP_ORIGIN,
            expected_rp_id=RP_ID,
            require_user_verification=True,
        )
    except Exception as e:
        raise HTTPException(400, f"Verification failed: {e}")

    # Persist credential
    cred = Credential(
        id=verification.credential_id.hex(),
        user_id=user.id,
        public_key=verification.credential_public_key,
        sign_count=verification.sign_count,
        device_name=device_name,
        backed_up=int(verification.credential_backed_up),
        aaguid=verification.aaguid,
    )
    db.add(cred)
    db.commit()

    # Clean up challenge
    redis.delete(f"register_challenge:{user.id}")

    return {
        "verified": True,
        "credential_id": cred.id,
        "is_passkey": cred.backed_up == 1,  # synced = true passkey
    }
```

### Login Endpoints

```python
# routes_login.py
from fastapi import APIRouter, Depends, HTTPException
from webauthn import (
    generate_authentication_options,
    verify_authentication_response,
    options_to_json,
)
from webauthn.helpers.structs import (
    PublicKeyCredentialDescriptor,
    UserVerificationRequirement,
)
import json
import uuid

router = APIRouter(prefix="/auth/passkey")


@router.post("/login/start")
def login_start(
    payload: dict,  # { "email": "...", optional }
    db=Depends(get_db),
    redis=Depends(get_redis),
):
    """Begin login. Two modes:
       1. Email provided: scope to that user's credentials (allow_credentials)
       2. No email: discoverable passkey flow (allow_credentials = [])
    """

    email = payload.get("email")
    allow_creds = []

    if email:
        user = db.query(User).filter_by(email=email).first()
        if not user:
            raise HTTPException(404, "User not found")
        creds = db.query(Credential).filter_by(user_id=user.id).all()
        allow_creds = [
            PublicKeyCredentialDescriptor(id=bytes.fromhex(c.id))
            for c in creds
        ]

    options = generate_authentication_options(
        rp_id=RP_ID,
        allow_credentials=allow_creds,  # [] = discoverable
        user_verification=UserVerificationRequirement.PREFERRED,
    )

    # Anonymous session ID (until we know which user)
    session_id = str(uuid.uuid4())
    redis.setex(f"login_challenge:{session_id}", 300, options.challenge)

    return {
        "session_id": session_id,
        "options": json.loads(options_to_json(options)),
    }


@router.post("/login/finish")
def login_finish(
    payload: dict,  # { "session_id": "...", "credential": {...} }
    db=Depends(get_db),
    redis=Depends(get_redis),
):
    """Verify assertion, issue session token."""

    session_id = payload["session_id"]
    credential_response = payload["credential"]

    expected_challenge = redis.get(f"login_challenge:{session_id}")
    if not expected_challenge:
        raise HTTPException(400, "Challenge expired")

    # Look up credential by id (which is rawId from browser response)
    cred_id_hex = credential_response["id"]
    # Note: browser sends base64url; convert to hex to match our DB
    import base64
    cred_id_bytes = base64.urlsafe_b64decode(cred_id_hex + "==")
    cred = db.query(Credential).filter_by(id=cred_id_bytes.hex()).first()
    if not cred:
        raise HTTPException(404, "Credential not found")

    try:
        verification = verify_authentication_response(
            credential=credential_response,
            expected_challenge=expected_challenge,
            expected_origin=RP_ORIGIN,
            expected_rp_id=RP_ID,
            credential_public_key=cred.public_key,
            credential_current_sign_count=cred.sign_count,
            require_user_verification=True,
        )
    except Exception as e:
        raise HTTPException(401, f"Auth failed: {e}")

    # Anti-cloning: sign counter must always increase
    if verification.new_sign_count <= cred.sign_count and cred.sign_count > 0:
        # Possible cloned authenticator — log and alert security team
        # In strict mode, reject. In permissive, just log.
        pass

    cred.sign_count = verification.new_sign_count
    cred.last_used = datetime.utcnow()
    db.commit()

    # Issue session
    user = cred.user
    token = create_jwt(user.id)  # your existing JWT helper

    redis.delete(f"login_challenge:{session_id}")

    return {
        "verified": True,
        "user_id": user.id,
        "email": user.email,
        "token": token,
    }
```

### Credential Management (List, Rename, Revoke)

```python
@router.get("/credentials")
def list_credentials(user=Depends(get_current_user), db=Depends(get_db)):
    creds = db.query(Credential).filter_by(user_id=user.id).all()
    return [
        {
            "id": c.id,
            "device_name": c.device_name,
            "is_passkey": c.backed_up == 1,
            "last_used": c.last_used,
            "created_at": c.created_at,
        }
        for c in creds
    ]


@router.delete("/credentials/{cred_id}")
def revoke_credential(
    cred_id: str,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    cred = db.query(Credential).filter_by(id=cred_id, user_id=user.id).first()
    if not cred:
        raise HTTPException(404, "Not found")

    # Prevent users from removing their LAST passkey + having no fallback
    total = db.query(Credential).filter_by(user_id=user.id).count()
    if total <= 1 and not user.has_password_fallback:
        raise HTTPException(400, "Cannot remove last credential without a fallback")

    db.delete(cred)
    db.commit()
    return {"revoked": True}
```

---

## Browser JavaScript (For Reference)

```javascript
// Registration
async function registerPasskey() {
  // 1. Get options from server
  const optsRes = await fetch('/auth/passkey/register/start', { method: 'POST' });
  const opts = await optsRes.json();

  // 2. Decode base64url fields
  opts.challenge = base64UrlToBuffer(opts.challenge);
  opts.user.id = base64UrlToBuffer(opts.user.id);
  opts.excludeCredentials?.forEach(c => c.id = base64UrlToBuffer(c.id));

  // 3. Call WebAuthn API
  const credential = await navigator.credentials.create({ publicKey: opts });

  // 4. Send back to server
  const body = {
    id: credential.id,
    rawId: bufferToBase64Url(credential.rawId),
    type: credential.type,
    response: {
      attestationObject: bufferToBase64Url(credential.response.attestationObject),
      clientDataJSON: bufferToBase64Url(credential.response.clientDataJSON),
    },
  };
  return fetch('/auth/passkey/register/finish', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

// Login (discoverable)
async function loginWithPasskey() {
  const optsRes = await fetch('/auth/passkey/login/start', {
    method: 'POST',
    body: JSON.stringify({}),  // no email = discoverable
  });
  const { session_id, options } = await optsRes.json();

  options.challenge = base64UrlToBuffer(options.challenge);
  options.allowCredentials?.forEach(c => c.id = base64UrlToBuffer(c.id));

  const assertion = await navigator.credentials.get({ publicKey: options });

  return fetch('/auth/passkey/login/finish', {
    method: 'POST',
    body: JSON.stringify({
      session_id,
      credential: {
        id: assertion.id,
        rawId: bufferToBase64Url(assertion.rawId),
        type: assertion.type,
        response: {
          authenticatorData: bufferToBase64Url(assertion.response.authenticatorData),
          clientDataJSON: bufferToBase64Url(assertion.response.clientDataJSON),
          signature: bufferToBase64Url(assertion.response.signature),
          userHandle: assertion.response.userHandle
            ? bufferToBase64Url(assertion.response.userHandle)
            : null,
        },
      },
    }),
  });
}
```

---

## Interview Questions & Answers

### Q1: Passkey vs password — explain to a non-technical PM

**Answer:**

Password: a secret string both you and the server know. If the server's DB leaks, attackers get the hash → can brute-force it. Phishing sites can trick you into typing the password into a fake URL.

Passkey: a key pair where the private key never leaves your phone/laptop. The server only stores your public key (useless to attackers if leaked). When you log in, your device signs a challenge with the private key — the server verifies it with the public key. Phishing-resistant because the signature is bound to the real domain.

```
Password breach impact: catastrophic (passwords reused on 100 sites)
Passkey breach impact:  near-zero (public key is meant to be public)
```

### Q2: Where is the private key actually stored?

**Answer:**

Depends on the authenticator:

```
Platform authenticator (Touch ID, Face ID, Windows Hello):
   → Secure Enclave / TPM / Strongbox
   → Hardware-isolated chip
   → Not accessible to OS, apps, or attackers with root

Roaming authenticator (YubiKey, security key):
   → Dedicated hardware chip
   → Can't be exported

Synced passkeys (Apple iCloud Keychain, Google Password Manager):
   → End-to-end encrypted in cloud
   → Recoverable from any device with iCloud/Google login
   → Trade-off: convenience vs pure hardware isolation
```

### Q3: What happens when a user loses their device?

**Answer:**

Three recovery scenarios:

```
1. Synced passkeys (most common in 2026):
   → User signs in to new device with Apple/Google/Microsoft account
   → Passkeys auto-sync from cloud
   → Re-authenticate with biometrics on new device

2. Multiple passkeys registered:
   → User logs in with another registered device (phone, laptop)
   → Adds the new device as another passkey

3. Account recovery (fallback):
   → Email magic link / recovery code / support flow
   → MUST design this carefully — it's the weakest link
```

Senior insight: **plan recovery from day 1**. Most passkey rollouts fail here.

### Q4: How do you implement "passkey or password" hybrid during migration?

**Answer:**

```python
# Phase 1: Add passkey option (don't remove password yet)
@router.post("/login")
async def login(body: dict):
    if body.get("method") == "passkey":
        return await login_with_passkey(body)
    else:
        return await login_with_password(body)

# Phase 2: Encourage passkey adoption
#   - Banner after login: "Set up a passkey — faster login!"
#   - Email campaigns
#   - Show passkey CTA on password reset

# Phase 3: Password-optional
#   - New signups: passkey-only by default
#   - Existing users: keep password as backup but hide UI

# Phase 4: Password-deprecated
#   - Remove password from UI
#   - Email recovery + passkey-only

# Migration metric to track:
#   - % of users with at least 1 passkey
#   - % of logins via passkey
```

### Q5: What's the difference between `attestation` and `assertion`?

**Answer:**

```
Attestation (during registration):
   ✓ Proof of which AUTHENTICATOR is being registered
   ✓ Signed by authenticator's manufacturer key
   ✓ Tells you: "this is a real YubiKey 5C / iPhone secure enclave"
   ✓ Optional — most consumer apps don't enforce
   ✓ Required in high-security (banking, govt) to enforce
     hardware-only authenticators

Assertion (during login):
   ✓ Proof user POSSESSES the registered authenticator
   ✓ Signed by the credential's private key
   ✓ Tells you: "the holder of this private key authorized this login"
   ✓ ALWAYS verified — this is the actual login proof
```

### Q6: Why is `sign_count` important?

**Answer:**

The authenticator increments a counter each time it signs an assertion. The server stores the last seen count.

```
On login:
   if new_sign_count <= stored_sign_count:
      → Possible CLONED authenticator!
      → Two devices both signed at counter = 5

Strict mode: reject the login + revoke credential
Permissive: log + alert security team, allow login

Caveat:
   ✗ Some passkeys (Apple, Google synced) DON'T increment the counter
   ✗ They always return 0 — sign_count check doesn't apply
   ✓ Hardware keys (YubiKey) increment properly
```

Senior insight: the spec is evolving on this. Apple's stance: synced passkeys can't have a reliable counter, so don't use counter to detect cloning. Use other signals (device binding, behavioral).

### Q7: How do you handle a user with multiple passkeys across devices?

**Answer:**

```python
# Each device registers separately → one Credential row per device

# When user logs in:
#   - Discoverable flow (no email) → device picks any registered passkey
#   - Email flow → server sends allow_credentials with all of user's creds

# UI shows credential management page:
#   GET /auth/passkey/credentials
#   [
#     { id, device_name: "iPhone 15 - Face ID", last_used, is_passkey: true },
#     { id, device_name: "MacBook Pro - Touch ID", last_used, is_passkey: true },
#     { id, device_name: "YubiKey 5C", last_used, is_passkey: false },  # not synced
#   ]

# User can rename, revoke, or add new passkeys
# Last-login tracking helps identify stale credentials
```

### Q8: What's `rp_id` and how do you set it for production?

**Answer:**

`rp_id` is the registrable domain that owns the passkey. Sets the phishing-resistance scope.

```
Production:
   rp_id = "acme.com"
   → Passkey works on acme.com AND subdomains (app.acme.com, www.acme.com)
   → Does NOT work on evil-acme.com (phishing-resistant)

Development:
   rp_id = "localhost"
   → Only works on http://localhost:*

Multi-region same brand:
   rp_id = "acme.com"  (the common parent)
   → Works on us.acme.com, eu.acme.com

Cross-domain (NOT possible):
   ✗ rp_id cannot be "acme.com" but used on acme.in
   ✗ Each brand domain needs its own passkey

Pitfall:
   ✗ Setting rp_id = "www.acme.com" → won't work on app.acme.com
   ✓ Always set to the parent registrable domain
```

### Q9: How do you store the public key in the DB?

**Answer:**

The public key from WebAuthn is raw COSE bytes (CBOR-encoded key material). Store as BLOB / `LargeBinary`.

```python
# SQLAlchemy
public_key = Column(LargeBinary, nullable=False)

# Postgres
public_key BYTEA NOT NULL

# When using:
verification = verify_authentication_response(
    credential=...,
    credential_public_key=cred.public_key,  # raw bytes
    ...
)
```

Do NOT:

```
✗ Base64-encode it as VARCHAR (wasted space + extra encoding)
✗ Try to extract the actual EC/RSA params separately
```

### Q10: How do passkeys integrate with your existing JWT / session?

**Answer:**

Passkeys are a **login mechanism** — they replace "username + password verification." Everything after login stays the same.

```
Old flow:
   1. POST /login { username, password }
   2. Server verifies bcrypt hash
   3. Issues JWT
   4. Client uses JWT for subsequent requests

New flow with passkeys:
   1. POST /auth/passkey/login/start → challenge
   2. Browser: navigator.credentials.get()
   3. POST /auth/passkey/login/finish → server verifies signature
   4. Issues JWT (same as before)
   5. Client uses JWT for subsequent requests

→ Drop-in replacement at the login step only
→ Sessions, refresh tokens, RBAC all unchanged
```

### Q11: What are the failure modes and how do you debug them?

**Answer:**

```
1. "InvalidStateError" on registration
   → Browser rejected because credential already exists
   → Fix: properly populate exclude_credentials with existing creds

2. "NotAllowedError" on login
   → User cancelled, biometric failed, or timeout
   → Fix: clear error UI, suggest password fallback

3. "SecurityError"
   → rp_id mismatch with origin
   → Fix: ensure RP_ID is the registrable domain of RP_ORIGIN

4. Signature verification fails
   → Wrong public key fetched, or clientDataJSON tampered
   → Fix: verify the credential lookup is correct,
            check rawId vs id encoding

5. Challenge mismatch
   → Session expired between start and finish
   → Fix: increase TTL (5 min is safe), don't lose Redis on restart

6. CORS issues with WebAuthn
   → Browsers require same-origin for credentials.create/get
   → Fix: serve frontend + backend on same registrable domain
```

### Q12: How do you handle account recovery without falling back to passwords?

**Answer:**

This is THE hardest part of passkey rollout. Options ranked by security:

```
Best — Multiple passkeys
   ✓ Force users to register ≥ 2 passkeys
     (e.g., phone + laptop)
   ✓ If one lost, login with other

Good — Recovery codes (one-time)
   ✓ Generate 10 single-use codes at signup
   ✓ User prints / saves to password manager
   ✓ Each code can do "register new passkey" once

OK — Email magic link
   ✗ Email account itself is now the recovery vector
   ✗ If email compromised → game over
   ✓ Better than nothing for low-risk apps

Risky — SMS / phone
   ✗ SIM swap attacks
   ✗ Only as last resort

Worst — "Customer support resets it"
   ✗ Social engineering attack surface
   ✗ Used by support people = attackers' favorite vector
```

Senior recommendation: **multiple passkeys + recovery codes**.

---

## Production Checklist

```markdown
# Passkey Production Readiness

## Design
- [ ] Decide: passkey-only OR passkey + fallback (password / magic link)?
- [ ] Recovery flow designed and tested
- [ ] Multi-device guidance for users
- [ ] Migration plan for existing password users

## Security
- [ ] rp_id matches registrable domain
- [ ] Challenge stored server-side (Redis with TTL)
- [ ] expected_origin and expected_rp_id validated
- [ ] require_user_verification = True
- [ ] sign_count monitored (with caveat for synced passkeys)
- [ ] Rate limit /register/start and /login/start
- [ ] Audit log every passkey creation and use

## UX
- [ ] Browser support check (feature detect navigator.credentials)
- [ ] Clear "Set up a passkey" prompt after signup/login
- [ ] Credential management page (list, rename, revoke)
- [ ] Error messages are human (not "InvalidStateError")
- [ ] Fallback option visible (if applicable)

## Compliance
- [ ] DPDP: passkey use logged as user-initiated action
- [ ] GDPR: public keys = pseudonymous data (still PII)
- [ ] Retention: revoke credentials on account deletion

## Observability
- [ ] Metric: % of logins via passkey vs password
- [ ] Metric: passkey registration funnel completion
- [ ] Alert: spike in sign_count violations (cloned authenticators)
- [ ] Alert: spike in NotAllowedError (user cancellations)
```

---

## Common Pitfalls

```
1. rp_id wrong → all passkeys break silently
   ✗ rp_id = "https://acme.com"  (includes scheme)
   ✓ rp_id = "acme.com"

2. Challenge not stored → can't verify
   ✗ Generating challenge but not persisting
   ✓ Always store in Redis/DB with TTL

3. Base64 encoding mismatch
   ✗ Browser sends base64url, server expects base64
   ✓ Use urlsafe_b64decode + add padding

4. Mixing up rawId vs id
   ✗ Storing the JS string `id` (base64url) but looking up by rawId hex
   ✓ Be consistent — store as bytes, encode same way each time

5. Not testing on multiple browsers
   ✗ Works on Chrome, breaks on Safari (or vice versa)
   ✓ Test Chrome / Safari / Firefox / Edge minimum

6. Skipping userVerification
   ✗ user_verification = DISCOURAGED → passkey not phishing-resistant
   ✓ user_verification = PREFERRED (or REQUIRED for high-security)

7. Forgetting credential exclusion
   ✗ User can register the same passkey twice → confusing UX
   ✓ Always populate exclude_credentials on /register/start

8. No graceful degradation
   ✗ Older browser → blank page
   ✓ Feature detect + show password fallback
```

---

## When NOT to Use Passkeys

```
✗ Internal-only services with strict on-prem auth
   → Use Kerberos / mTLS / SAML instead

✗ Headless / API-only services (M2M)
   → Use OAuth2 client credentials / mTLS

✗ Legacy users who can't update browsers / devices
   → Maintain password+TOTP fallback

✗ Embedded devices without authenticator chips
   → Different threat model
```

---

## Future (2026-2028)

```
✓ Cross-device flows getting better (hybrid transport)
✓ Conditional UI (autofill-style passkey picker) — already in browsers
✓ Browser-built support in all major browsers (universal)
✓ Government IDs as passkey authenticators (India Aadhaar piloting)
✓ Passwordless mandates emerging in regulated industries
✓ NIST 800-63B revision favoring phishing-resistant authenticators
```

---

## Resources

```
✓ https://passkeys.dev — comprehensive guide
✓ https://www.w3.org/TR/webauthn-2/ — WebAuthn spec
✓ https://github.com/duo-labs/py_webauthn — Python lib
✓ FIDO Alliance docs — https://fidoalliance.org/passkeys/
✓ Apple — https://developer.apple.com/passkeys/
✓ Google — https://developers.google.com/identity/passkeys
```

---

## Senior Mantras

```
1. Passkeys are a UX revolution, not just a security upgrade.

2. Plan recovery BEFORE rollout. Most failed rollouts die here.

3. Don't remove passwords until > 80% of MAU have a passkey.

4. Sign-count check is dying (synced passkeys break it).
   Use device binding + behavioral signals for cloning detection.

5. rp_id is the most common bug. Get it right ONCE.

6. Test on real devices, not just emulators.
   iOS Simulator + Android emulator behave differently
   from real Touch ID / Face ID.

7. Don't roll your own. Use webauthn (Duo) library.

8. Audit log EVERY passkey operation. Forensics matter.
```

---

## Related Topics in This Repo

- [01_jwt_oauth2_rbac.md](01_jwt_oauth2_rbac.md) — JWT issuance after passkey login
- [03_jwt_vulnerabilities_2fa_secrets.md](03_jwt_vulnerabilities_2fa_secrets.md) — 2FA context
- [04_oauth2_flows_deep.md](04_oauth2_flows_deep.md) — OAuth2 flows
- [09_session_management.md](09_session_management.md) — session after passkey
- [17_india_dpdp_compliance.md](17_india_dpdp_compliance.md) — passkey + DPDP
- [Phase2_FastAPI/05_security_jwt.md](../Phase2_FastAPI/05_security_jwt.md) — FastAPI security
