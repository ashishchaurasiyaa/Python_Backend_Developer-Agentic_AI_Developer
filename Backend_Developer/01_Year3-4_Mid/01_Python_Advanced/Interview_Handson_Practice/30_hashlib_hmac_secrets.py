"""
================================================================================
TOPIC: hashlib / hmac / secrets — Security primitives (hashing, signatures, tokens)
================================================================================

KYA HOTA HAI:
    Teen alag-alag stdlib modules, teen alag kaam ke liye:
      - hashlib: ek-tarfa (one-way) hash — content/integrity ke liye (sha256).
        Same input -> same hash, par hash se input wapas nikalna feasible nahi.
      - hmac: keyed hash — ek SHARED SECRET ke saath hash, taaki "ye message
        sach me hamare partner se aaya aur tampered nahi" verify ho sake.
      - secrets: cryptographically-secure RANDOM bytes/tokens generate karta
        (API tokens, reset tokens, session ids). random.* se predictable hota,
        secrets se nahi.

KYO NEED PADI:
    Plain hash (sha256) integrity ke liye fast aur badhiya hai, par PASSWORD ke
    liye kaafi NAHI — bina salt rainbow-table se crack ho jaata, aur itna fast
    hai ki brute-force aasaan. Signature compare karne me agar normal `==` use
    karo to wo byte-by-byte early-exit karta -> TIMING ATTACK leak. Aur tokens
    agar random.* se banaye (seedable, predictable PRNG) to attacker guess kar
    leta. In teeno gaps ko hashlib(scrypt/pbkdf2) + hmac.compare_digest + secrets
    bharte hain.

KAISE USE KARTE HAIN:
    - Integrity: hashlib.sha256(data).hexdigest() -> file checksum / ETag / cache key.
    - Password: hashlib.scrypt(pwd, salt=os.urandom(16), n=..., r=8, p=1) ya
      hashlib.pbkdf2_hmac("sha256", pwd, salt, iterations) — per-user random salt
      store karo, verify pe constant-time compare.
    - Signature: hmac.new(secret, raw_body, sha256).hexdigest(); verify ke liye
      hmac.compare_digest(expected, received) (constant-time).
    - Tokens: secrets.token_urlsafe(32) / token_hex(16); compare secrets.compare_digest.

KAHAN USE HOTA HAI (backend scenarios):
    1. Exotel dialer webhook (aur Razorpay/PayU/M-Pesa): incoming POST ke raw body
       pe HMAC-SHA256 recompute karke header signature se compare_digest — galat
       ya forged callbacks reject. Ye exactly tumne kiya hai.
    2. Niroskos multi-tenant Django: user passwords scrypt/pbkdf2 + per-user salt;
       password reset + email-verify tokens secrets.token_urlsafe se.
    3. SAP HANA connector idempotency: payload ka sha256 "content hash" -> dedupe
       key, taaki same sync dobara apply na ho.
    4. Caching/CDN: response body ka sha256 = ETag / Redis cache key.
    5. API auth: per-client API tokens secrets se generate; DB me unka hash store,
       compare constant-time.

INTERVIEW ANSWER (English — recite this):
    "I keep three security primitives separate by purpose. hashlib gives one-way
    hashes like SHA-256 for content integrity — file checksums, ETags, cache keys,
    and idempotency keys — where I just need a fast, deterministic fingerprint. The
    rule I never break is to never store passwords as a plain SHA-256: it has no
    per-user salt so it's vulnerable to rainbow tables, and it's deliberately fast,
    which makes brute force cheap. For passwords I use a slow, salted KDF — scrypt
    or pbkdf2_hmac — with a unique random salt per user and a high work factor, so
    each guess is expensive. hmac is for authenticity: I compute an HMAC-SHA256 over
    the exact raw request body with a shared secret and verify it against the
    provider's header — that's exactly how I verify Razorpay, PayU and Exotel
    webhooks. The critical detail there is that I compare with hmac.compare_digest,
    not ==, because == short-circuits on the first differing byte and leaks timing
    that an attacker can use to forge a signature. Finally, for anything random and
    security-sensitive — API tokens, password-reset tokens, session ids — I use the
    secrets module, never random, because random is a seedable, predictable PRNG and
    secrets is backed by the OS CSPRNG."

================================================================================
Run:
    python 30_hashlib_hmac_secrets.py        # saare sections chalao
    python 30_hashlib_hmac_secrets.py 2 5    # sirf section 2 aur 5

Sections:
    1. DEMO  — hashlib.sha256 integrity: file checksum / ETag / cache key / idempotency
    2. REAL  — password hashing: scrypt + pbkdf2_hmac + per-user salt + verify
    3. REAL  — Exotel/Razorpay-style webhook HMAC verify (compute + compare_digest)
    4. DEMO  — secrets: token_urlsafe/token_hex for API/reset/session tokens
    5. BREAK — sha256(password) alone broken; == on signatures = timing attack;
               random.* tokens predictable -> fixes (scrypt+salt, compare_digest, secrets)
    6. TODO  — tum khud likho: verify_webhook() constant-time HMAC check
================================================================================
"""
from __future__ import annotations

import hashlib
import hmac
import os
import random
import secrets
import sys


# === SECTION 1: DEMO — hashlib.sha256 integrity (checksum / ETag / cache key) ===
def _sha256_hex(data: bytes) -> str:
    # one-way digest: same bytes -> hamesha same hex. Integrity ke liye perfect.
    return hashlib.sha256(data).hexdigest()


def section1() -> None:
    print("\n=== SECTION 1: DEMO — hashlib.sha256 integrity (checksum/ETag/cache key) ===")

    body = b'{"txn_id":"T-1001","amount":4999,"currency":"INR"}'
    digest = _sha256_hex(body)
    print(f"    payload bytes ({len(body)}B) -> sha256: {digest}")
    print(f"    deterministic? same input dobara -> {_sha256_hex(body) == digest}")

    # ek byte badlo -> poora hash badal jaata (avalanche). Tamper turant pakdo.
    tampered = body.replace(b"4999", b"9999")
    print(f"    1 field tamper -> sha256: {_sha256_hex(tampered)[:16]}...  (totally different)")

    # USE-CASE 1: file checksum — bade file ko chunk-by-chunk feed karo (memory safe)
    h = hashlib.sha256()
    for chunk in (b"line1\n", b"line2\n", b"line3\n"):
        h.update(chunk)                 # streaming update — pura file RAM me load nahi
    print(f"    file checksum (chunked update): {h.hexdigest()[:16]}...")

    # USE-CASE 2: ETag / cache key — response body ka hash. Client ke ETag se match
    # ho to 304 Not Modified bhej do. Cache key bhi yahi digest.
    etag = f'"{_sha256_hex(body)[:16]}"'
    print(f"    HTTP ETag for response = {etag}")
    print(f"    Redis cache key        = resp:{_sha256_hex(body)[:24]}")

    # USE-CASE 3: SAP HANA idempotency — payload ka content-hash = dedupe key.
    # Same sync dobara aaya to same hash -> already-applied detect.
    print(f"    SAP HANA idempotency key (content hash) = {_sha256_hex(body)[:32]}")
    print("  -> sha256: fast, deterministic, one-way. Integrity/dedupe ke liye. (NOT passwords!)")


# === SECTION 2: REAL — password hashing: scrypt + pbkdf2_hmac + per-user salt ===
def hash_password_scrypt(password: str) -> tuple[bytes, bytes]:
    """scrypt: memory-hard KDF. Per-user RANDOM salt (os.urandom) + tunable cost.
    Returns (salt, derived_key). DB me dono store karte (salt + hash)."""
    salt = os.urandom(16)                          # per-user unique random salt
    # n = CPU/memory cost (power of 2), r = block size, p = parallelism.
    # n yahan demo ke liye chhota (fast test); prod me 2**14+ rakhte.
    dk = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return salt, dk


def verify_password_scrypt(password: str, salt: bytes, expected: bytes) -> bool:
    """Verify: same salt + params se dobara derive karo, fir CONSTANT-TIME compare.
    `==` MAT use karo (timing leak) — hmac.compare_digest se compare."""
    candidate = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return hmac.compare_digest(candidate, expected)


def hash_password_pbkdf2(password: str, iterations: int = 200_000) -> tuple[bytes, int, bytes]:
    """pbkdf2_hmac alternative: HMAC ko `iterations` baar repeat -> slow on purpose.
    Returns (salt, iterations, derived_key). iterations bhi store karte (future me
    badha sako bina purane hashes tode)."""
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations, dklen=32)
    return salt, iterations, dk


def section2() -> None:
    print("\n=== SECTION 2: REAL — password hashing (scrypt + pbkdf2 + per-user salt) ===")

    pwd = "S3cr3t-Niroskos!"

    # scrypt
    salt, stored = hash_password_scrypt(pwd)
    print(f"    scrypt  salt={salt.hex()[:12]}.. hash={stored.hex()[:16]}.. (per-user salt random)")
    print(f"    login OK  (correct pwd)  -> {verify_password_scrypt(pwd, salt, stored)}")
    print(f"    login NO  (wrong pwd)    -> {verify_password_scrypt('wrong', salt, stored)}")

    # do users SAME password -> alag salt -> alag hash. Rainbow table bekaar.
    salt2, stored2 = hash_password_scrypt(pwd)
    print(f"    same password, 2 users -> different stored hash? {stored != stored2}  (salt ka kamaal)")

    # pbkdf2_hmac variant
    psalt, iters, phash = hash_password_pbkdf2(pwd)
    again = hashlib.pbkdf2_hmac("sha256", pwd.encode(), psalt, iters, dklen=32)
    print(f"    pbkdf2  iters={iters} -> verify (constant-time): "
          f"{hmac.compare_digest(again, phash)}")
    print("  -> per-user random salt + slow KDF + constant-time verify = sahi password storage.")


# === SECTION 3: REAL — Exotel/Razorpay-style webhook HMAC verify ===
def compute_signature(secret: bytes, raw_body: bytes) -> str:
    """Provider (Exotel/Razorpay/Stripe) shared secret se raw body pe HMAC-SHA256
    banata aur header me bhejta. Hum bhi EXACT raw bytes pe wahi recompute karte."""
    return hmac.new(secret, raw_body, hashlib.sha256).hexdigest()


def verify_webhook_signature(secret: bytes, raw_body: bytes, header_sig: str) -> bool:
    """Constant-time verify: recompute karo aur compare_digest se match karo.
    NOTE: raw_body EXACTLY wahi bytes hone chahiye jo wire pe aaye — JSON ko
    re-serialize MAT karo (key order/spacing badal jaata -> signature mismatch)."""
    expected = compute_signature(secret, raw_body)
    return hmac.compare_digest(expected, header_sig)   # timing-safe


def section3() -> None:
    print("\n=== SECTION 3: REAL — webhook HMAC verify (Exotel/Razorpay style) ===")

    shared_secret = b"whsec_exotel_dialer_shared_key"
    # Exotel se aaya raw POST body (bytes as-received) + header signature:
    raw_body = b'{"event":"call.completed","call_sid":"CA42","duration":"73"}'
    incoming_header_sig = compute_signature(shared_secret, raw_body)  # provider ne bheja

    ok = verify_webhook_signature(shared_secret, raw_body, incoming_header_sig)
    print(f"    genuine callback     -> verified? {ok}  (process the event)")

    # Attacker body tamper karta (duration badha ke billing fraud) par signature
    # naya nahi bana sakta (secret nahi hai) -> mismatch -> REJECT.
    forged = raw_body.replace(b'"73"', b'"9999"')
    bad = verify_webhook_signature(shared_secret, forged, incoming_header_sig)
    print(f"    tampered body, old sig -> verified? {bad}  (REJECT 401 — forged)")

    # Galat secret (kisi aur ne sign kiya) -> mismatch.
    wrong_secret = verify_webhook_signature(b"wrong_secret", raw_body, incoming_header_sig)
    print(f"    wrong shared secret    -> verified? {wrong_secret}  (REJECT)")
    print("  -> recompute HMAC over RAW body + compare_digest = forge-proof, timing-safe.")


# === SECTION 4: DEMO — secrets: API tokens / reset tokens / session ids ===
def section4() -> None:
    print("\n=== SECTION 4: DEMO — secrets for tokens (API/reset/session) ===")

    # token_urlsafe(n): n random BYTES -> URL-safe base64 text (length > n). Reset
    # links / session ids me daal sakte (no +,/,= ki dikkat).
    reset_token = secrets.token_urlsafe(32)
    print(f"    password-reset token (token_urlsafe 32B): {reset_token}")
    print(f"      len={len(reset_token)} chars, URL-safe (links me safe)")

    # token_hex(n): n random bytes -> 2n hex chars. API keys / opaque ids ke liye.
    api_key = "sk_live_" + secrets.token_hex(16)
    print(f"    API key (token_hex 16B): {api_key}")

    # secrets.choice / randbelow: secure random pick (OTP-ish, par OTP rate-limit karo!)
    otp = "".join(secrets.choice("0123456789") for _ in range(6))
    print(f"    6-digit OTP (secrets.choice): {otp}")

    # Token COMPARE bhi constant-time: DB-stored token vs incoming token.
    stored, incoming = reset_token, reset_token
    print(f"    secrets.compare_digest(stored, incoming) -> {secrets.compare_digest(stored, incoming)}")
    print(f"    every call unique? {secrets.token_hex(8) != secrets.token_hex(8)}  (CSPRNG, unguessable)")
    print("  -> secrets = OS CSPRNG. Tokens/ids isise banao, random.* se KABHI nahi.")


# === SECTION 5: BREAK IT / GOTCHA — 3 classic security mistakes + fixes ===
def _naive_unsafe_equal(a: str, b: str) -> bool:
    """GALAT compare: Python `==` strings ko byte-by-byte compare karta aur PEHLE
    mismatch pe ruk jaata (short-circuit). Match prefix jitna lamba, utni der —
    yahi timing signal attacker ko ek-ek char guess karne deta (timing attack)."""
    return a == b


def section5() -> None:
    print("\n=== SECTION 5: BREAK IT — 3 security mistakes + fixes ===")

    # ---- MISTAKE 1: sha256(password) alone (no salt, too fast) ----
    print("  [1] WRONG: passwords ko plain sha256 me store karna")
    pwd = "password123"
    plain = hashlib.sha256(pwd.encode()).hexdigest()
    plain_again = hashlib.sha256(pwd.encode()).hexdigest()
    print(f"      sha256('password123') = {plain[:24]}...")
    print(f"      no salt -> har user ka same pwd = SAME hash? {plain == plain_again}")
    print("      => rainbow table: precomputed hash->pwd lookup turant crack karta.")
    print("      => + sha256 super-fast hai -> GPU pe billions/sec brute force.")
    print("      FIX: scrypt/pbkdf2 + per-user random salt + high cost (Section 2):")
    salt, derived = hash_password_scrypt(pwd)
    salt2, derived2 = hash_password_scrypt(pwd)            # same pwd, doosra user
    print(f"           scrypt same pwd, 2 users -> different hash? {derived != derived2}  (salted+slow)")

    # ---- MISTAKE 2: == to compare signatures (timing attack, not constant-time) ----
    print("\n  [2] WRONG: signature/token compare with `==` (timing attack)")
    secret = b"whsec_demo"
    body = b'{"ok":true}'
    real_sig = compute_signature(secret, body)
    attacker_guess = "0" * len(real_sig)
    print(f"      `==` compare (early-exit, leaks timing) -> "
          f"{_naive_unsafe_equal(real_sig, attacker_guess)}")
    print("      => `==` first-diff pe ruk jaata; response-time se attacker char-by-char")
    print("         signature reconstruct kar sakta. Wrong answer to nahi, par LEAKY.")
    print("      FIX: hmac.compare_digest — hamesha FULL length compare (constant-time):")
    print(f"           compare_digest(real, guess) -> {hmac.compare_digest(real_sig, attacker_guess)}")
    print(f"           compare_digest(real, real)  -> {hmac.compare_digest(real_sig, real_sig)}")

    # ---- MISTAKE 3: random.* for tokens (predictable PRNG) ----
    print("\n  [3] WRONG: random.* se tokens banana (predictable)")
    random.seed(1234)                                     # attacker ye seed guess/leak kar sakta
    predictable = f"{random.getrandbits(64):016x}"
    random.seed(1234)                                     # same seed -> SAME 'token' fir se!
    reproduced = f"{random.getrandbits(64):016x}"
    print(f"      random token = {predictable}")
    print(f"      same seed se reproduce ho gaya? {predictable == reproduced}  (Mersenne Twister: deterministic)")
    print("      => random ek seedable, predictable PRNG hai — session id/token kabhi nahi.")
    print("      FIX: secrets (OS CSPRNG) — unguessable, non-reproducible:")
    print(f"           secrets.token_hex(8) = {secrets.token_hex(8)} (har baar naya, unpredictable)")


# === SECTION 6: TODO — tum khud likho: verify_webhook() constant-time HMAC ===
def verify_webhook(secret: bytes, raw_body: bytes, header_sig: str) -> bool:
    """
    TODO (tum implement karo):
      Ek payment/Exotel webhook verifier likho jo TIMING-SAFE ho.
        1. `secret` aur `raw_body` se HMAC-SHA256 hexdigest compute karo:
               expected = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
        2. `expected` ko `header_sig` se CONSTANT-TIME compare karo:
               return hmac.compare_digest(expected, header_sig)
        3. `==` se compare MAT karna (timing attack), aur raw_body ko re-serialize
           mat karna — jaisa aaya waisa hi bytes use karo.

    Expected behaviour (section6 verify karega):
        secret = b"whsec_test"; body = b'{"amount":100}'
        good   = hmac.new(secret, body, hashlib.sha256).hexdigest()
        verify_webhook(secret, body, good)                 -> True
        verify_webhook(secret, body, "deadbeef")           -> False
        verify_webhook(b"other", body, good)               -> False
    """
    raise NotImplementedError("TODO: verify_webhook ka body likho (hmac.new + compare_digest)")


def section6() -> None:
    print("\n=== SECTION 6: TODO — verify_webhook() constant-time HMAC (tum likho) ===")
    secret = b"whsec_test"
    body = b'{"amount":100}'
    good = hmac.new(secret, body, hashlib.sha256).hexdigest()
    try:
        checks = [
            ("genuine sig -> True", verify_webhook(secret, body, good) is True),
            ("bad sig -> False", verify_webhook(secret, body, "deadbeef") is False),
            ("wrong secret -> False", verify_webhook(b"other", body, good) is False),
        ]
        for label, ok in checks:
            print(f"    [{'PASS' if ok else 'FAIL'}] {label}")
    except NotImplementedError as e:
        print(f"  abhi unimplemented (TODO complete karo): {e}")
    except Exception as e:
        print(f"  TODO adhura/galat lag raha: {type(e).__name__}: {e}")


# === MAIN DISPATCHER ===
def main() -> None:
    sections = {
        "1": section1,
        "2": section2,
        "3": section3,
        "4": section4,
        "5": section5,
        "6": section6,
    }
    args = sys.argv[1:]
    to_run = args if args else list(sections.keys())
    for key in to_run:
        fn = sections.get(key)
        if fn is None:
            print(f"[skip] unknown section: {key!r} (valid: {', '.join(sections)})")
            continue
        fn()


if __name__ == "__main__":
    main()
