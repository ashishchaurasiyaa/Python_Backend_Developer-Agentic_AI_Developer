# Stdlib Networking + Security — socket, ssl, hashlib, hmac, secrets

## Quick Concepts

**WHAT:**
- **socket** = Low-level network I/O (TCP, UDP)
- **ssl** = TLS/SSL support for sockets
- **hashlib** = Hashing (SHA-256, SHA-512, etc.)
- **hmac** = HMAC for message authentication
- **secrets** = Cryptographically secure random
- **base64** = Base64 encoding/decoding
- **binascii** = Binary ↔ ASCII conversions
- **selectors** = High-level I/O multiplexing

**WHY know stdlib networking:**
- Build custom protocols
- Debug network issues
- Understand higher-level libs (requests, aiohttp)
- Performance-critical paths
- Security: hashing, signing, encryption basics

**HOW networking stack:**
```
Application (HTTP, gRPC, custom)
         ↓
TLS / SSL (ssl module)
         ↓
TCP / UDP (socket module)
         ↓
IP / Internet
```

---

## Interview Questions & Answers

### Q1: socket basics — TCP server in Python?

**Answer:**

**WHAT:** socket = endpoint for network communication.

**HOW — Echo TCP server:**

```python
import socket

def tcp_server():
    """
    Simple TCP echo server.
    Listens on port 5000, echoes received data.
    """
    # ⭐ Create socket (IPv4, TCP)
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # ⭐ Reuse address (avoid "Address already in use")
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    server.bind(("127.0.0.1", 5000))
    server.listen(5)  # Backlog: 5 pending connections

    print("Server listening on port 5000...")

    try:
        while True:
            # ⭐ Accept connection (blocks)
            client, addr = server.accept()
            print(f"Client connected: {addr}")

            with client:
                while True:
                    # ⭐ Receive up to 4096 bytes
                    data = client.recv(4096)
                    if not data:
                        break  # Client disconnected
                    print(f"Received: {data.decode()}")
                    # ⭐ Send back (echo)
                    client.sendall(b"Echo: " + data)
    finally:
        server.close()


tcp_server()
```

**HOW — TCP client:**

```python
import socket

def tcp_client():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect(("127.0.0.1", 5000))
        s.sendall(b"Hello, server!")
        response = s.recv(4096)
        print(f"Got: {response.decode()}")


tcp_client()
```

**HOW — Async TCP server (asyncio):**

```python
import asyncio

async def handle_client(reader, writer):
    addr = writer.get_extra_info("peername")
    print(f"Connected: {addr}")

    while True:
        data = await reader.read(4096)
        if not data:
            break
        print(f"Received: {data.decode()}")
        writer.write(b"Echo: " + data)
        await writer.drain()

    writer.close()
    await writer.wait_closed()


async def main():
    server = await asyncio.start_server(handle_client, "127.0.0.1", 5000)
    print("Async server on port 5000")
    async with server:
        await server.serve_forever()


asyncio.run(main())
```

---

### Q2: UDP — kab use karein?

**Answer:**

**WHAT:** UDP = User Datagram Protocol (connectionless, fast).

**WHY UDP over TCP:**
- ✅ Low latency (no handshake)
- ✅ Multicast/broadcast support
- ✅ Stateless
- ❌ No delivery guarantee
- ❌ No ordering
- ❌ No congestion control

**Use cases:** DNS, video streaming, gaming, metrics (StatsD), VoIP

**HOW — UDP server:**

```python
import socket

def udp_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # ⭐ SOCK_DGRAM
    server.bind(("127.0.0.1", 5001))
    print("UDP server on port 5001")

    while True:
        # ⭐ No accept — just receive
        data, addr = server.recvfrom(4096)
        print(f"From {addr}: {data.decode()}")
        # Reply
        server.sendto(b"Echo: " + data, addr)


def udp_client():
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.sendto(b"Hello UDP!", ("127.0.0.1", 5001))
    response, _ = client.recvfrom(4096)
    print(f"Got: {response.decode()}")
```

---

### Q3: TLS/SSL — how to add encryption?

**Answer:**

**WHAT:** ssl module wraps sockets with TLS.

**HOW — TLS server:**

```python
import socket
import ssl

def tls_server():
    # ⭐ Create SSL context
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(certfile="server.crt", keyfile="server.key")

    # Optional: require client cert (mTLS)
    # context.load_verify_locations("ca.crt")
    # context.verify_mode = ssl.CERT_REQUIRED

    # Create regular socket
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 8443))
    server.listen(5)

    print("TLS server on 8443")

    while True:
        client, addr = server.accept()
        # ⭐ Wrap with TLS
        ssl_client = context.wrap_socket(client, server_side=True)
        try:
            data = ssl_client.recv(4096)
            print(f"Got (encrypted): {data.decode()}")
            ssl_client.sendall(b"Hello over TLS")
        finally:
            ssl_client.close()


tls_server()
```

**HOW — TLS client:**

```python
import socket
import ssl

def tls_client():
    # ⭐ Client SSL context (verifies server cert)
    context = ssl.create_default_context()
    # For self-signed (dev only):
    # context.check_hostname = False
    # context.verify_mode = ssl.CERT_NONE

    with socket.create_connection(("example.com", 443)) as sock:
        # ⭐ server_hostname for SNI + cert verification
        with context.wrap_socket(sock, server_hostname="example.com") as tls_sock:
            print(f"TLS version: {tls_sock.version()}")  # TLSv1.3
            print(f"Cipher: {tls_sock.cipher()}")

            tls_sock.sendall(b"GET / HTTP/1.1\r\nHost: example.com\r\n\r\n")
            response = tls_sock.recv(4096)
            print(response.decode())


tls_client()
```

**HOW — Inspect certificate:**

```python
import ssl
import socket

context = ssl.create_default_context()

with socket.create_connection(("example.com", 443)) as sock:
    with context.wrap_socket(sock, server_hostname="example.com") as tls_sock:
        cert = tls_sock.getpeercert()

print(f"Subject: {cert['subject']}")
print(f"Issuer: {cert['issuer']}")
print(f"Valid until: {cert['notAfter']}")
print(f"SAN: {cert.get('subjectAltName')}")
```

---

### Q4: hashlib — secure hashing?

**Answer:**

**WHAT:** Cryptographic hash functions.

**WHY:**
- File integrity (checksums)
- Data deduplication
- Building blocks for HMAC, JWT signing
- NOT for passwords (use bcrypt/argon2 instead!)

**HOW — Common usage:**

```python
import hashlib

# ⭐ SHA-256 (recommended general purpose)
data = b"Hello, world!"
hash_obj = hashlib.sha256(data)
digest_hex = hash_obj.hexdigest()
print(digest_hex)  # 64 chars hex

# Bytes form
digest_bytes = hash_obj.digest()
print(len(digest_bytes))  # 32 bytes


# ⭐ Streaming (large files)
def hash_file(path: str) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):  # 8KB chunks
            hasher.update(chunk)
    return hasher.hexdigest()


# ⭐ Different algorithms
algorithms = {
    "MD5":      hashlib.md5,        # 128 bits — INSECURE for crypto
    "SHA-1":    hashlib.sha1,       # 160 bits — INSECURE for crypto
    "SHA-256":  hashlib.sha256,     # 256 bits — recommended
    "SHA-512":  hashlib.sha512,     # 512 bits — recommended
    "Blake2b":  hashlib.blake2b,    # Faster than SHA-2
    "SHA-3":    hashlib.sha3_256,   # Newer standard
}

for name, algo in algorithms.items():
    print(f"{name}: {algo(b'hello').hexdigest()}")
```

**WHY md5/sha1 INSECURE for crypto:**
- Collision attacks proven
- Can be brute-forced
- Use only for non-security checksums

**HOW — Password hashing (NOT hashlib!):**

```python
# ❌ DON'T do this
password_hash = hashlib.sha256(password.encode()).hexdigest()
# SHA-256 too fast → GPU brute force trivial

# ✅ DO use bcrypt or argon2
import bcrypt
hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12))


# ✅ OR argon2 (modern)
from argon2 import PasswordHasher
ph = PasswordHasher()
hashed = ph.hash(password)
```

---

### Q5: HMAC — message authentication?

**Answer:**

**WHAT:** HMAC = Hash-based Message Authentication Code.

**WHY:**
- Verify message integrity (not tampered)
- Verify sender (knows shared secret)
- Webhook signatures (Stripe, GitHub)
- API request signing (AWS)

**HOW — Sign and verify:**

```python
import hmac
import hashlib

SECRET_KEY = b"shared-secret-key"


def sign(message: bytes) -> str:
    """Sign message with HMAC-SHA256."""
    return hmac.new(SECRET_KEY, message, hashlib.sha256).hexdigest()


def verify(message: bytes, signature: str) -> bool:
    """
    Verify signature.
    ⭐ Use constant-time comparison (prevents timing attacks).
    """
    expected = sign(message)
    return hmac.compare_digest(expected, signature)


# Usage
message = b'{"order_id": 123, "amount": 99.99}'
sig = sign(message)
print(f"Signature: {sig}")

# Receiver verifies
is_valid = verify(message, sig)
print(f"Valid: {is_valid}")

# Tampered
tampered = b'{"order_id": 123, "amount": 999.99}'  # ⚠️ Modified
is_valid = verify(tampered, sig)
print(f"Tampered valid: {is_valid}")  # False
```

**HOW — Webhook verification (Stripe-style):**

```python
import hmac
import hashlib
import time
import json

class WebhookVerifier:
    def __init__(self, secret: str):
        self.secret = secret.encode()

    def sign(self, payload: bytes, timestamp: int = None) -> str:
        """
        Format: t=<timestamp>,v1=<signature>
        Timestamp prevents replay attacks.
        """
        ts = timestamp or int(time.time())
        signed = f"{ts}.".encode() + payload
        signature = hmac.new(self.secret, signed, hashlib.sha256).hexdigest()
        return f"t={ts},v1={signature}"

    def verify(self, payload: bytes, signature_header: str, tolerance: int = 300) -> bool:
        """
        Verify signature.
        Reject if timestamp older than tolerance (replay protection).
        """
        try:
            parts = dict(p.split("=", 1) for p in signature_header.split(","))
            ts = int(parts["t"])
            provided_sig = parts["v1"]
        except (KeyError, ValueError):
            return False

        # ⭐ Reject old timestamps (replay attack)
        if abs(time.time() - ts) > tolerance:
            return False

        # Recompute expected
        signed = f"{ts}.".encode() + payload
        expected = hmac.new(self.secret, signed, hashlib.sha256).hexdigest()

        # ⭐ Constant-time comparison
        return hmac.compare_digest(provided_sig, expected)


# Producer
verifier = WebhookVerifier("whsec_secret123")
payload = b'{"event": "order.created"}'
sig = verifier.sign(payload)

# Consumer
print(verifier.verify(payload, sig))  # True
```

**WHY `hmac.compare_digest` (constant-time):**

```python
# ❌ INSECURE — timing attack possible
if signature == expected:  # Returns at first different char
    pass

# ✅ SECURE — constant time
if hmac.compare_digest(signature, expected):
    pass

# Attacker can measure response time to infer correct chars
# compare_digest avoids this
```

---

### Q6: secrets — cryptographically secure random?

**Answer:**

**WHAT:** Module for security-critical randomness.

**WHY NOT random module:**
```python
import random
random.random()  # ⚠️ Pseudo-random (predictable!)
# Don't use for: passwords, tokens, keys, salts
```

**HOW — secrets module:**

```python
import secrets

# ⭐ Random bytes
key = secrets.token_bytes(32)  # 32 bytes (256 bits)

# ⭐ URL-safe random string
token = secrets.token_urlsafe(32)  # 43 chars, URL-safe base64

# ⭐ Hex string
hex_token = secrets.token_hex(16)  # 32 chars hex

# ⭐ Random choice (cryptographic)
password = "".join(
    secrets.choice("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%")
    for _ in range(16)
)

# ⭐ Random int in range
otp = secrets.randbelow(1000000)  # 0 to 999999
print(f"OTP: {otp:06d}")  # 6-digit OTP

# Constant-time comparison
known = secrets.token_bytes(32)
provided = secrets.token_bytes(32)
secrets.compare_digest(known, provided)  # Same as hmac.compare_digest
```

**HOW — Common patterns:**

```python
import secrets

# Session tokens
session_id = secrets.token_urlsafe(32)

# CSRF tokens
csrf_token = secrets.token_urlsafe(32)

# API keys
api_key = f"sk_live_{secrets.token_urlsafe(40)}"

# Password reset tokens (URL-safe)
reset_token = secrets.token_urlsafe(32)

# OTP for SMS
otp = f"{secrets.randbelow(1000000):06d}"

# Salt for password hashing
salt = secrets.token_bytes(16)
```

---

### Q7: base64 + binascii — encoding/decoding?

**Answer:**

**WHAT:**
- **base64** = Encode binary as ASCII (66% bigger but text-safe)
- **binascii** = Lower-level binary ↔ ASCII

**WHY:**
- Embed binary in JSON
- URL-safe identifiers
- Email attachments
- JWT tokens use base64url

**HOW — base64 encoding:**

```python
import base64

# ⭐ Standard base64
data = b"Hello, world!"
encoded = base64.b64encode(data)
print(encoded)  # b'SGVsbG8sIHdvcmxkIQ=='

# Decode
decoded = base64.b64decode(encoded)
print(decoded)  # b'Hello, world!'


# ⭐ URL-safe base64 (replaces +/  with -_, removes padding)
encoded = base64.urlsafe_b64encode(b"Hello").decode().rstrip("=")
print(encoded)  # SGVsbG8

decoded = base64.urlsafe_b64decode(encoded + "==")  # Add padding back


# ⭐ Image to base64 (data URLs)
with open("image.png", "rb") as f:
    img_data = f.read()
img_b64 = base64.b64encode(img_data).decode()
data_url = f"data:image/png;base64,{img_b64}"
```

**HOW — binascii:**

```python
import binascii

# Hex encoding
data = b"\x00\xff\x42\x10"
hex_str = binascii.hexlify(data).decode()
print(hex_str)  # 00ff4210

# Decode back
data2 = binascii.unhexlify(hex_str)
print(data2)  # b'\x00\xffB\x10'


# CRC32 checksum
crc = binascii.crc32(b"Hello, world!")
print(crc)  # 1486751714
```

---

### Q8: Async DNS resolution?

**Answer:**

**WHAT:** Resolve hostnames to IPs asynchronously.

**HOW — stdlib socket (sync):**

```python
import socket

# Get all IPs
ips = socket.gethostbyname_ex("example.com")
print(ips)  # ('example.com', [], ['93.184.216.34'])

# Reverse lookup
hostname = socket.gethostbyaddr("8.8.8.8")
print(hostname)  # ('dns.google', [], ['8.8.8.8'])
```

**HOW — Async DNS (asyncio):**

```python
import asyncio
import socket

async def resolve(hostname: str):
    loop = asyncio.get_running_loop()
    # ⭐ Use thread executor (socket.gethostbyname is blocking)
    return await loop.getaddrinfo(
        hostname, None, type=socket.SOCK_STREAM
    )


async def main():
    result = await resolve("example.com")
    print(result[0])  # First record
```

**HOW — aiodns (faster, real async):**

```python
# pip install aiodns

import asyncio
import aiodns

async def main():
    resolver = aiodns.DNSResolver()
    result = await resolver.gethostbyname("example.com", socket.AF_INET)
    print(result.addresses)


asyncio.run(main())
```

---

### Q9: selectors — high-level I/O multiplexing?

**Answer:**

**WHAT:** Handle multiple sockets without threads.

**WHY:**
- Lighter than threads
- Used internally by asyncio
- Manual control for custom patterns

**HOW — Simple selector server:**

```python
import selectors
import socket

selector = selectors.DefaultSelector()


def accept(sock):
    client, addr = sock.accept()
    print(f"Connected: {addr}")
    client.setblocking(False)
    # ⭐ Register client for read events
    selector.register(client, selectors.EVENT_READ, data=b"")


def read(client):
    data = client.recv(4096)
    if data:
        print(f"Got: {data.decode()}")
        client.sendall(b"Echo: " + data)
    else:
        # Client disconnected
        selector.unregister(client)
        client.close()


def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 5000))
    server.listen(5)
    server.setblocking(False)

    # ⭐ Register server for read events (= incoming connections)
    selector.register(server, selectors.EVENT_READ, data=None)

    while True:
        # ⭐ Wait for any registered socket to be ready
        events = selector.select(timeout=1)
        for key, mask in events:
            if key.data is None:
                accept(key.fileobj)
            else:
                read(key.fileobj)


main()
```

---

### Q10: Production security stdlib usage?

**Answer:**

**Production scenarios + correct stdlib:**

```python
# ─── 1. Generate API key ──────────────────────────────────
import secrets
api_key = f"sk_live_{secrets.token_urlsafe(40)}"


# ─── 2. Hash password ─────────────────────────────────────
# ❌ stdlib hashlib alone — INSECURE
# ✅ Use bcrypt/argon2 (3rd party but standard)
import bcrypt
hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(12))


# ─── 3. Sign API request (HMAC) ───────────────────────────
import hmac
import hashlib
signature = hmac.new(secret_key, message, hashlib.sha256).hexdigest()


# ─── 4. Verify webhook ────────────────────────────────────
import hmac
is_valid = hmac.compare_digest(provided_sig, expected_sig)


# ─── 5. Generate session ID ───────────────────────────────
import secrets
session_id = secrets.token_urlsafe(32)


# ─── 6. CSRF token ────────────────────────────────────────
import secrets
csrf = secrets.token_urlsafe(32)


# ─── 7. Random salt for password (built into bcrypt/argon2) ─
import secrets
salt = secrets.token_bytes(16)


# ─── 8. File checksum (integrity) ─────────────────────────
import hashlib
def file_checksum(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


# ─── 9. Base64 encode for JSON ────────────────────────────
import base64
img_data_url = f"data:image/png;base64,{base64.b64encode(img_bytes).decode()}"


# ─── 10. JWT token (use PyJWT, not raw HMAC) ──────────────
import jwt
token = jwt.encode({"user_id": 1}, "secret", algorithm="HS256")
```

---

## Security stdlib Cheatsheet

| Task | Right Tool | Wrong Tool |
|---|---|---|
| Random ID | `secrets.token_urlsafe()` | `random.choice()` |
| Random int | `secrets.randbelow()` | `random.randint()` |
| Hash password | `bcrypt` / `argon2` | `hashlib.sha256` |
| File checksum | `hashlib.sha256` | `hashlib.md5` |
| Webhook signature | `hmac` + `hashlib.sha256` | Plain SHA256 |
| Compare secrets | `hmac.compare_digest` | `==` |
| Encrypt data | `cryptography.fernet` | `base64` (not encryption!) |
| API key | `secrets.token_urlsafe(40)` | `uuid.uuid4()` (predictable) |

---

## Networking + Security Checklist

```markdown
### Sockets
- [ ] Always use SO_REUSEADDR
- [ ] Always close connections (with statement)
- [ ] Set timeout (socket.settimeout)
- [ ] Use asyncio for concurrent

### TLS
- [ ] verify_mode=CERT_REQUIRED in production
- [ ] check_hostname=True
- [ ] TLSv1.2 minimum
- [ ] Use ssl.create_default_context()

### Hashing
- [ ] NEVER MD5/SHA-1 for security
- [ ] Use SHA-256+ for checksums
- [ ] Use bcrypt/argon2 for passwords
- [ ] Use HMAC for signatures

### Random
- [ ] secrets for any security
- [ ] random ONLY for non-security
- [ ] secrets.token_urlsafe for IDs

### HMAC
- [ ] hmac.compare_digest (constant time)
- [ ] Include timestamp (replay protection)
- [ ] Use SHA-256 minimum

### Production
- [ ] Don't log secret keys
- [ ] Rotate keys regularly
- [ ] Use environment variables (not hardcoded)
- [ ] Use Secrets Manager in production
```
