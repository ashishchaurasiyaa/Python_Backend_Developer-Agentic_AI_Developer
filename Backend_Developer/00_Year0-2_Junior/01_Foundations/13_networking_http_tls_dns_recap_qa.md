# Networking — HTTP, TLS, DNS Recap Q&A (Interview Deep Dive)

> Self-test recap of [03_networking_fundamentals.md](03_networking_fundamentals.md) and [03_networking_deepdive_hinglish.md](03_networking_deepdive_hinglish.md), Round 3b (HTTP anatomy, HTTP/1.1 vs HTTP/2, TLS handshake, DNS resolution). Format: analogy → concept → live proof (real numbers/output from this machine).

---

## Topic 1. HTTP Request/Response Anatomy + Status Codes

**Analogy:** A formal application letter — Method+Path+Version is the subject line ("POST /api/users, HTTP/1.1"), headers are the envelope's extra info (content type, sender identity, auth token), body is the actual letter content (only present for POST/PUT, usually absent for GET).

### Live Proof (see [http_anatomy_raw_server_demo.py](http_anatomy_raw_server_demo.py))

```
Method:  POST
Path:    /api/users
Version: HTTP/1.1
Headers:
  Host: 127.0.0.1:62812
  Content-Type: application/json
  Content-Length: 29
  Authorization: Bearer abc123
  Connection: close
Body:    b'{"name": "Ashish", "age": 25}'
```
`Content-Length: 29` matches the body's exact byte length — since TCP has no message boundaries (see networking core recap, Topic 5), HTTP must explicitly tell the receiver where the body ends.

### Status Codes — Live Proof (see [http_status_codes_demo.py](http_status_codes_demo.py))

```
200 OK · 201 Created · 204 No Content · 304 Not Modified
400 Bad Request · 401 Unauthorized · 403 Forbidden · 404 Not Found
409 Conflict · 422 Unprocessable Entity · 429 Too Many Requests · 500 Internal Server Error
```

**Interview-critical distinctions:**
- **401 vs 403**: 401 = authentication problem ("log in first"), response should carry `WWW-Authenticate`. 403 = authorization problem ("you're logged in, but not allowed").
- **400 vs 422**: 400 = malformed request (bad JSON syntax). 422 = syntactically valid but semantically invalid (e.g. a number in an email field).
- **Category ranges:** 1xx informational, 2xx success, 3xx redirection, 4xx client error, 5xx server error.
- **Retry logic:** retry-with-backoff makes sense on 500/503, but retrying a 501 (Not Implemented) is pointless.

---

## Topic 2. HTTP/1.1 vs HTTP/2

**Analogy:** HTTP/1.1 keep-alive = a single-counter bank branch where you don't need a new token (new TCP connection) each visit, but only one customer is served at a time. HTTP/2 multiplexing = the same building now has multiple counters inside one entrance (one TCP connection) — multiple customers served in parallel.

### Live Proof 1 — Connection Reuse Speedup (see [http1_connection_reuse_timing_demo.py](http1_connection_reuse_timing_demo.py))

```
50 requests, NEW TCP connection each time: 13.0 ms total (0.260 ms/req)
50 requests, ONE reused connection:         5.9 ms total (0.117 ms/req)
Speedup from reuse: 2.2x
```
Every new connection re-pays the 3-way handshake (plus TLS handshake for HTTPS) — keep-alive pays that cost once, then reuses the connection.

### Live Proof 2 — Real ALPN Negotiation to HTTP/2 (see [http2_multiplexing_demo.py](http2_multiplexing_demo.py))

```
* Connected to example.com (172.66.147.243) port 443
* ALPN: curl offers h2,http/1.1
* ALPN: server accepted h2
* using HTTP/2
```
**ALPN** (Application-Layer Protocol Negotiation) is a TLS handshake extension where client and server agree on the HTTP version to use — zero extra round trips needed.

### Key improvements table

| Feature | HTTP/1.1 | HTTP/2 |
|---|---|---|
| Multiplexing | One request at a time per connection (browsers historically opened ~6 parallel connections as a workaround) | Multiple parallel interleaved streams on **one** TCP connection |
| Header compression | Full headers sent in plaintext every request | **HPACK** — repeated headers encoded once, referenced afterward |
| Framing | Text-based | Binary framing (faster/less ambiguous parsing) |
| Server push | No | Yes (rarely used in practice now, being deprecated by browsers) |

**Important nuance:** HTTP/2 multiplexing is application-layer, but it still rides on TCP — a single lost TCP packet blocks *all* multiplexed streams (TCP-level head-of-line blocking persists). This is exactly why **HTTP/3 (QUIC, UDP-based)** exists: its own reliable transport layer means one stream's packet loss doesn't block other streams.

---

## Topic 3. TLS Handshake + Certificate Chain

**Analogy:** A wax-sealed confidential letter — you don't trust the seal on its own; you trace it through a notary, whose seal is certified by a higher authority, up to one you already trust (a government). TLS certificate chains work identically.

**Why TLS exists:** encryption (no eavesdropping), integrity (no undetected tampering), authentication (server is who it claims to be).

### TLS 1.3 Handshake (simplified)

```
Client --ClientHello (ciphers, ALPN, key share)--> Server
Client <--ServerHello + certificate + key share + Finished-- Server
Client --Finished--> Server
        [Encrypted application data starts]
```
TLS 1.3 does this in **1 round trip** (TLS 1.2 needed 2), making HTTPS connection setup noticeably faster.

### Live Proof — Real Certificate Chain from `example.com:443` (see [tls_certificate_chain_demo.py](tls_certificate_chain_demo.py))

```
[0] Subject: CN=example.com                              (LEAF -- what your browser sees)
    Issuer:  CN=Cloudflare TLS Issuing ECC CA 3
[1] Subject: CN=Cloudflare TLS Issuing ECC CA 3            (INTERMEDIATE)
    Issuer:  CN=SSL.com TLS Transit ECC CA R2
[2] Subject: CN=SSL.com TLS Transit ECC CA R2              (further up towards ROOT)
    Issuer:  CN=SSL.com TLS ECC Root CA 2022
```
Chain of trust: browser trusts a **Root CA** (preinstalled in its trust store). Root → Intermediate → Issuing CA → leaf cert, each link verified by digital signature. Any broken link = "Not Secure" warning. Every cert has `NotBefore`/`NotAfter` — expired certs are a classic real-world outage cause (hence auto-renewal tools like Let's Encrypt/Certbot).

### Senior debugging tools

```bash
openssl s_client -connect example.com:443 -servername example.com   # full chain + handshake + cipher + expiry
curl -vI https://example.com                                         # -v shows TLS handshake + ALPN in terminal
```

**Interview trap:** self-signed certs fail validation because the chain never reaches a trusted root — the cert signs itself, so nothing external can vouch for it.

---

## Topic 4. DNS Resolution

**Analogy:** A phone-book hierarchy — country directory → state directory → city directory → the actual number. DNS resolves a domain name to an IP through a similar chain of authorities.

### Live Proof — Real Root → TLD → Authoritative Walk (see [dns_trace_hierarchy_demo.py](dns_trace_hierarchy_demo.py), `dig +trace example.com`)

```
Hop 1 (ROOT servers):        "don't know .com, but here are the 13 root servers" (34ms)
Hop 2 (.com TLD servers):    "don't know example.com, but here are its nameservers
                               (hera.ns.cloudflare.com, elliott.ns.cloudflare.com)" (23ms)
Hop 3 (Cloudflare authoritative): "here's the actual answer:
                               example.com. 300 IN A 104.20.23.154
                               example.com. 300 IN A 172.66.147.243" (145ms)
```
3 real hops resolved `example.com` — Root → `.com` TLD → Cloudflare (authoritative). Latency increased at each hop (34ms → 23ms → 88ms → 145ms), the deepest/most specific authority being the slowest.

### Record Types — Live Proof (see [dns_record_types_demo.py](dns_record_types_demo.py), `google.com`)

```
A     172.217.26.46                          -> IPv4 address
AAAA  2404:6800:4009:816::200e               -> IPv6 address
MX    10 smtp.google.com.                     -> mail server + priority
NS    ns4.google.com.                         -> authoritative nameserver
TXT   "v=spf1 include:_spf.google.com ~all"   -> arbitrary text; common for domain
                                                  ownership verification & SPF (anti-spoofing)
```
**Backend-relevant:** `TXT` records show up constantly when setting up email services (SendGrid, Google Workspace) — "add this TXT record to verify domain ownership."

### TTL Caching — Live Proof (see [dns_ttl_caching_demo.py](dns_ttl_caching_demo.py)) — with an honest caveat

```
Query 1: TTL = 261
Waiting 5 real seconds...
Query 2: TTL = 300   <- went UP, not down as naively expected
```
TTL didn't monotonically decrease as expected — because each `dig` call can hit a **different resolver path/cache**, or the record refreshed in between. Real nuance: **TTL is only meaningfully comparable within the same resolver's cache**, not across different queries/resolvers. Concept still holds: TTL = how long a resolver may serve a cached answer before re-querying.

**Why TTL matters operationally:** during a server IP migration, a long TTL (e.g. 3600s) means some users keep hitting the old IP for up to an hour after cutover. Best practice: lower TTL (e.g. 60s) *before* a planned migration.

### The complete picture (DNS + TCP + TLS + HTTP together)

```
1. Browser resolves example.com via DNS -> 172.66.147.243
2. TCP 3-way handshake to 172.66.147.243:443
3. TLS handshake (ALPN negotiates HTTP/2), certificate chain verified
4. HTTP/2 request sent over the encrypted, multiplexed connection
5. HTTP response returned
```
Every layer covered in this recap session (encapsulation, IP/port, TCP, TLS, HTTP, DNS) is a real step in this one chain.

---

## Round 3b Scorecard

Taught fresh with live proof for all 4 topics (user had not attempted these beforehand — same as Round 3a). Revisit before interviews:
- 401 vs 403, 400 vs 422 status code distinctions
- Why HTTP/2 multiplexing still has TCP-level head-of-line blocking (motivates HTTP/3/QUIC)
- Certificate chain of trust — Root → Intermediate → Leaf, and why self-signed certs fail
- DNS hierarchy (Root → TLD → Authoritative) and why lowering TTL before migration matters
