# Core Network Protocols

**DevOps Track · Phase 3: Networking**

## Quick Concepts

| Concept | One-line definition |
|------------------------------|----------------------------------------------------------------------|
| **Port** | A number (0–65535) identifying a specific service/process on a host |
| **Well-known ports** | 0–1023, reserved for standard protocols (root required to bind on Linux) |
| **Connection-oriented (TCP)** | Handshake first, guaranteed ordered delivery, retransmits lost packets |
| **Connectionless (UDP)** | Fire-and-forget, no delivery guarantee, lower latency/overhead |
| **TLS/SSL** | Encryption layer wrapped around a protocol (HTTP→HTTPS, SMTP→SMTPS) |

---

## Quick Concepts — In Depth

### Ports — The Mental Model

```
An IP address is the building. A port is the apartment number.

IP  10.0.10.5  =  the building (the server)
Port 8000      =  apartment 8000  =  your FastAPI app
Port 5432      =  apartment 5432  =  PostgreSQL
Port 6379      =  apartment 6379  =  Redis

When a packet arrives at 10.0.10.5:8000, the kernel looks up which
process called bind() on port 8000 and delivers it there.

Port ranges:
  0–1023      Well-known ports — root required to bind on Linux
              Why: a non-root process binding port 80/443 could
              impersonate a web server — root requirement is the safety gate
  1024–49151  Registered ports — MySQL:3306, Postgres:5432, Redis:6379
  49152–65535 Ephemeral ports — OS assigns these to CLIENT sockets
              When you curl google.com, your OS picks a random port here
              as the source port; google replies to that port
```

---

## Why This Matters for Backend/DevOps Work

```
Every service you deploy, every firewall rule you write, every security
group in AWS — comes down to "which protocol, which port, why."
This is the vocabulary layer under load balancers, VPNs, Kubernetes
services, and every "connection refused" ticket you'll get.
```

---

## Protocol Reference Table

| Protocol | Port | Purpose | DevOps Scenario |
|----------|------|---------|-----------------|
| **HTTP** | 80 | Unencrypted web traffic | Redirect all :80 → :443 in Nginx/ALB config |
| **HTTPS** | 443 | HTTP + TLS | Terminate TLS at load balancer, renew Let's Encrypt cert |
| **SSH** | 22 | Encrypted remote shell + tunnel | Restrict :22 to bastion IP only in security group |
| **DNS** | 53 UDP/TCP | Name resolution | Debug CoreDNS in Kubernetes, Route 53 propagation |
| **SMTP relay** | 25 | Server-to-server mail | BLOCKED by AWS/GCP by default — never use for app mail |
| **SMTP submit** | 587 | Authenticated mail submission | App → SES/SendGrid with STARTTLS |
| **DHCP server** | 67 | Auto IP assignment | Rarely touched in cloud; matters on-prem |
| **FTP** | 21/20 | Unencrypted file transfer | Legacy — migrate to SFTP/S3 |
| **TCP** | (transport) | Reliable ordered byte stream | HTTP, SSH, databases — correctness > speed |
| **UDP** | (transport) | Fast, connectionless | DNS, video, metrics — speed > correctness |

---

## HTTP / HTTPS — In Depth

### HTTP Request/Response Anatomy

```
A raw HTTP/1.1 request (what curl actually sends over the wire):

GET /api/users/42 HTTP/1.1\r\n
Host: api.example.com\r\n
Authorization: Bearer eyJhbGc...\r\n
Accept: application/json\r\n
Connection: keep-alive\r\n
\r\n                           ← blank line = end of headers, body follows

Every component:
  Method    GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS
  Path      /api/users/42  (the resource identifier)
  Version   HTTP/1.1 (or 2 or 3)
  Host      tells the server WHICH virtual host you want
            one IP can serve hundreds of domains via the Host header
            → this is how shared hosting and multi-tenant ALBs work
  Connection: keep-alive
            reuse the TCP connection for the next request
            avoids paying the 3-way handshake cost on every request
```

### HTTP Status Codes — Production Reading

```
1xx — Informational   100 Continue, 101 Switching Protocols (WebSocket upgrade)
2xx — Success         200 OK, 201 Created, 204 No Content
3xx — Redirect        301 Moved Permanently (cached), 302 Found (not cached)
                      304 Not Modified (use browser cache), 307/308 (keep method)
4xx — Client error    400 Bad Request, 401 Unauthorised, 403 Forbidden
                      404 Not Found, 409 Conflict, 422 Unprocessable Entity
                      429 Too Many Requests (add retry with exponential backoff)
5xx — Server error    500 Internal Server Error
                      502 Bad Gateway
                      503 Service Unavailable
                      504 Gateway Timeout

Production diagnosis:
  502 Bad Gateway      → ALB/nginx can't reach the backend
                         App crashed? Wrong port? Health check failing?
                         Check: ss -tlnp on the backend, journalctl -u myapp

  503 Service Unavailable → no healthy targets in load balancer target group
                            All backends failing health checks
                            Check: ALB target group health, auto-scaling events

  504 Gateway Timeout  → backend is alive but too slow (query timeout, DB lock,
                         downstream API hanging)
                         Check: slow query logs, app tracing, DB lock waits

  429 Too Many Requests → rate limit hit; client must back off
                          Add retry logic with exponential backoff + jitter
```

### HTTPS — What TLS Actually Does

```
Without TLS: your request travels as plaintext over every router between
you and the server. An attacker on the path sees the exact URL, all
headers, the Authorization token, the full request body. Nothing is hidden.

TLS 1.3 handshake (simplified):

  Client ──────── ClientHello ──────────────────▶ Server
    "I support TLS 1.3, here are my cipher suites,
     here is my key_share for Diffie-Hellman"

  Client ◀─────── ServerHello + Certificate ────── Server
    "Let's use TLS 1.3 + AES-256-GCM-SHA384"
    "Here's my cert, signed by Let's Encrypt"

  Client verifies the certificate:
    ✓ Is it signed by a trusted CA in my trust store?
    ✓ Does CN/SAN match the hostname I'm connecting to?
    ✓ Is it not expired?
    If any check fails → TLS error, connection aborted

  Client ──────── Finished (encrypted) ───────────▶ Server
    Both sides derived the same symmetric session key
    via Diffie-Hellman WITHOUT transmitting it directly

  ══════ All subsequent data encrypted with session key ══════

What TLS HIDES:
  ✓ HTTP method, path, query string, headers, body, cookies, tokens
  ✓ Response body and headers

What TLS does NOT hide:
  ✗ Destination IP (visible in the IP header — always)
  ✗ Destination hostname (sent in SNI — Server Name Indication —
    during ClientHello so the server knows which cert to serve)
  ✗ Approximate amount of data (packet sizes are visible)
```

**TLS in production — configs you'll write:**

```nginx
# nginx — enforce TLS 1.2+ minimum, disable weak ciphers
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
ssl_prefer_server_ciphers off;   # let client choose (TLS 1.3 best practice)

# HTTP → HTTPS redirect on same server block
server {
    listen 80;
    server_name example.com;
    return 301 https://$host$request_uri;
}

# HSTS — tell browsers to ALWAYS use HTTPS for this domain
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
# After adding HSTS: browsers won't even attempt HTTP for 1 year
# Be sure HTTPS works perfectly before setting this — no easy undo
```

**Certificate chain — why "unknown CA" errors happen:**

```
Your cert is signed by:  Let's Encrypt Intermediate CA
That intermediate CA is signed by:  ISRG Root X1
ISRG Root X1 is self-signed:  trusted root in all OS/browser trust stores

Client verification path:
  your_cert → intermediate CA → root CA (in trust store) = OK ✓

"Certificate verify failed" errors:
  1. Server sends only its own cert (not the full chain)
     Fix: configure Nginx/app to send the full chain file
     (fullchain.pem from Let's Encrypt, not just cert.pem)

  2. Client trust store doesn't have the root CA
     Fix: common in corporate/internal CAs — add the CA cert to
     the client's trust store, or pass -cacert to curl

  3. Self-signed cert — no CA at all
     Fix: use a real CA, or add --insecure to curl (test only)

Debug:
openssl s_client -connect api.example.com:443 -showcerts
  → shows exactly what chain the server presents
  → "Verify return code: 0 (ok)" = valid chain
  → any other code = the specific verification failure
```

**Cert expiry — the most common self-inflicted outage:**

```
An expired cert doesn't warn — it hard-blocks ALL clients immediately.
Every browser, curl call, SDK, and service-to-service call fails.

Automation:
  Let's Encrypt + certbot:  certbot renew via cron or systemd timer
  AWS ACM:                  free auto-renewal when attached to ALB/CloudFront
                            NEVER expires if still attached to a resource

Monitoring:
  Alert when cert expires in < 30 days
  Check: openssl s_client -connect host:443 | openssl x509 -noout -dates
  CloudWatch metric: DaysToExpiry via a Lambda that runs weekly
```

---

## HTTP/2 and HTTP/3 — What Actually Changed

### HTTP/1.1 — The Baseline Problem

```
HTTP/1.1: one request per TCP connection at a time, processed in order.
"Head-of-line blocking" — request 2 waits for request 1 to complete.

Browser workaround: open ~6 parallel TCP connections per origin.
Each TCP+TLS connection = 2–3 RTT setup overhead before first byte.
On a 100ms RTT connection: 200–300ms setup cost per connection.

This inefficiency spawned entire optimization industries:
  sprite sheets (combine images), CSS/JS bundling, domain sharding,
  inlining critical CSS — ALL workarounds for HTTP/1.1 limitations,
  mostly unnecessary with HTTP/2+.
```

### HTTP/2 — Multiplexing on One Connection

```
Key improvement: MULTIPLEXING
  Many requests/responses interleaved over ONE TCP connection.
  No more head-of-line blocking at the APPLICATION layer.
  No more need for 6 parallel connections.

Header compression (HPACK):
  HTTP/1.1: repeated headers (Cookie, User-Agent, Accept) sent in full
            on EVERY request — can be hundreds of bytes of overhead
  HTTP/2: shared header table between client and server
          repeat headers sent as tiny deltas (~2–3 bytes per repeated header)

Still runs over TCP:
  One lost TCP packet stalls ALL multiplexed streams on that connection
  until the lost packet is retransmitted (TCP-level head-of-line blocking)
  HTTP/2 eliminates app-level blocking but not transport-level blocking

Real-world impact: 20–50% faster page loads on slow connections.
```

### HTTP/3 — QUIC Replaces TCP

```
HTTP/3 is built on QUIC (transport protocol over UDP).

QUIC solves TCP head-of-line blocking:
  Each stream is independent at the transport layer.
  One lost packet only stalls ITS OWN stream, not all streams.
  On a 2% packet-loss mobile network: this matters enormously.

0-RTT resumption:
  If you've connected to this server before, the first packet
  can contain data — no handshake round trip at all.
  HTTP/1.1 TCP+TLS = 2–3 RTTs. HTTP/3 = 0 RTTs on resumption.

Built-in TLS 1.3:
  QUIC combines the transport and encryption handshakes.
  QUIC 1-RTT vs TCP+TLS 2–3 RTTs for new connections.

Where you see HTTP/3 in production:
  CloudFront  → HTTP/3 available, opt-in
  Cloudflare  → HTTP/3 by default
  ALB         → HTTP/2 client-to-ALB, HTTP/1.1 ALB-to-backend
  gRPC        → requires HTTP/2 exclusively
```

```bash
curl -I --http2 https://api.example.com     # force HTTP/2
curl -v https://api.example.com 2>&1 | grep -i "using http"   # see negotiated version
```

---

## DNS — Full Resolution Flow

### How a DNS Query Actually Works

```
You type: api.example.com in your app

Step 1: Check /etc/hosts (local overrides — always checked first)
        /etc/hosts: 127.0.0.1 localhost  → resolved immediately

Step 2: Check OS DNS cache (systemd-resolved or nscd)
        If cached and TTL not expired → return immediately

Step 3: Query the configured resolver (AWS VPC: 10.0.0.2, home: 8.8.8.8)

If the resolver doesn't have it cached, recursive lookup begins:

Step 4: Resolver → Root Name Server (there are 13 sets worldwide)
        "Who handles .com?"
        Root NS: "Ask the .com TLD server at 192.5.6.30"

Step 5: Resolver → .com TLD Server
        "Who handles example.com?"
        TLD NS: "Ask ns1.example.com at 205.251.x.x"

Step 6: Resolver → ns1.example.com (authoritative nameserver)
        "What is api.example.com?"
        Auth NS: "10.0.10.5, TTL=300"

Step 7: Resolver caches the answer for TTL=300 seconds (5 minutes)
        Returns 10.0.10.5 to your application

Performance:
  Cached: < 1ms
  Uncached: ~100ms (involves multiple hops across the internet)
  Low TTL (e.g. TTL=30 for blue/green deploys): forces frequent lookups,
  adds latency at scale — don't use TTL < 60s in steady state
```

### DNS Record Types

```
A      hostname → IPv4 address
       api.example.com. IN A 10.0.10.5

AAAA   hostname → IPv6 address
       api.example.com. IN AAAA 2001:db8::1

CNAME  hostname → another hostname (alias, not to an IP)
       www.example.com. IN CNAME example.com.
       NEVER use CNAME at the zone apex (example.com. itself) —
       RFC disallows it; use ALIAS/ANAME in Route 53 instead

MX     which server handles email for this domain
       example.com. IN MX 10 mail.example.com.  (10 = priority)

TXT    arbitrary text — used for:
       SPF:  v=spf1 include:amazonses.com ~all  (who can send email for us)
       DKIM: v=DKIM1; k=rsa; p=<publickey>   (email signing verification)
       Ownership proof: google-site-verification=abc123

NS     which DNS servers are authoritative for this domain
       example.com. IN NS ns1.example.com.

PTR    reverse DNS: IP → hostname
       5.10.0.10.in-addr.arpa. IN PTR api.example.com.
       Used in: email reputation scoring, server identification in logs
```

### DNS Debugging

```bash
dig api.example.com                      # full query output
dig +short api.example.com               # just the answer IPs
dig @8.8.8.8 api.example.com             # query specific resolver (Google)
dig @10.0.0.2 api.example.com            # query VPC DNS directly (AWS)
dig api.example.com +trace               # full resolution chain: root → TLD → auth
dig api.example.com MX                   # query specific record type
dig -x 10.0.10.5                         # reverse DNS lookup (PTR)

# "Works via IP but not hostname" debugging:
dig myservice.svc.cluster.local          # in Kubernetes pod
kubectl exec -it mypod -- cat /etc/resolv.conf   # what DNS server the pod uses
kubectl get pods -n kube-system | grep coredns   # is CoreDNS running?

# TTL inspection:
dig api.example.com | grep -A2 "ANSWER SECTION"
# api.example.com. 297 IN A 10.0.10.5
#                  ^^^ this is the remaining TTL in seconds
```

---

## SMTP — Email Protocol

```
Port 25:  server-to-server relay (MTA to MTA, no auth required by design)
          BLOCKED outbound by AWS, GCP, Azure by default on all instances.
          Reason: a compromised instance could send millions of spam emails
          directly to recipient mail servers.

Port 587: authenticated submission (your app → mail relay)
          Requires: username + password (or API key)
          STARTTLS: upgrades connection to TLS after initial plain handshake
          This is what SES, SendGrid, Postmark, Mailgun all use.

Port 465: SMTPS — SMTP over TLS from the start (older, still used)

Your app's SMTP config should always be:
  SMTP_HOST=email-smtp.us-east-1.amazonaws.com
  SMTP_PORT=587
  SMTP_USE_TLS=true
  SMTP_USER=AKIA...
  SMTP_PASS=...

SES alternative — use the AWS SDK (boto3) directly:
  Skips SMTP entirely, more reliable, better delivery event tracking.
  ses.send_email(Source=..., Destination=..., Message=...)
```

---

## SSH — Full Protocol Understanding

```
SSH does much more than a remote terminal:

1. Remote command execution (non-interactive):
   ssh user@host 'systemctl status myapp'
   ssh user@host 'journalctl -u myapp -n 50 --no-pager'
   ssh user@host 'pg_dump mydb' > local_backup.sql   # pipe DB dump locally

2. File transfer:
   scp, rsync — both use SSH as transport

3. Port forwarding:
   ssh -L 5433:db.internal:5432 bastion   → reach private DB from laptop
   ssh -R 8080:localhost:3000 server       → expose local service to remote

4. ProxyJump — multi-hop without key exposure:
   ssh -J bastion.example.com final-server
   # or in ~/.ssh/config:
   Host prod-db
       ProxyJump bastion.example.com
   # Better than agent forwarding: key never leaves your machine

5. SSH agent forwarding (-A):
   ssh -A bastion-host
   Your laptop's private key is usable on bastion for further hops.
   Risk: if bastion is compromised, attacker gets your key.
   Safer alternative: ProxyJump (key only on your machine)
```

**SSH hardening:**

```bash
# /etc/ssh/sshd_config — minimum production settings:
PasswordAuthentication no    # eliminates brute-force attack surface
PermitRootLogin no           # root only via sudo from a named user
PubkeyAuthentication yes
MaxAuthTries 3               # 3 key attempts then disconnect
AllowUsers deploy ci-user    # whitelist — unlisted users always rejected
Protocol 2                   # SSH1 is cryptographically broken
LoginGraceTime 30            # 30s to complete auth, then disconnect
ClientAliveInterval 300      # server pings client every 5min
ClientAliveCountMax 2        # disconnect after 2 missed pings

# Syntax-check BEFORE reloading (avoid locking yourself out):
sudo sshd -t && sudo systemctl reload sshd
```

---

## DHCP — How Hosts Get Their IP

```
DHCP DORA handshake:
  Client   → DISCOVER (broadcast: "is there a DHCP server?")
  Server   → OFFER    (broadcast: "I offer you 10.0.1.50")
  Client   → REQUEST  (broadcast: "I want 10.0.1.50")
  Server   → ACK      (unicast: "It's yours for 24 hours")

The lease includes:
  IP address       10.0.1.50
  Subnet mask      255.255.255.0
  Default gateway  10.0.1.1
  DNS servers      10.0.0.2 (VPC DNS)
  Lease time       86400s (24h) — client must renew before expiry

In AWS VPC:
  DHCP is automatic and invisible — every subnet has a built-in DHCP server
  You configure DNS via DHCP options sets (custom DNS, domain search suffix)
  Elastic IPs are assigned outside DHCP — they're static public IPs

On-prem risk:
  DHCP lease expires → different IP assigned → all hostnames still point to
  old IP in static configs. Fix: use static IPs or DHCP reservations for servers.

If DHCP fails: host gets 169.254.x.x (link-local APIPA)
  This is the diagnostic signal: 169.254.x.x = "this machine couldn't get a DHCP lease"
```

---

## Senior Tips

```
1. Know port numbers cold: 22, 53, 80, 443, 587 — these appear in
   security groups, Nginx configs, and interviews constantly.

2. TCP vs UDP is a design decision: "can this app tolerate a dropped
   or out-of-order packet?" Yes → UDP. No → TCP.

3. Outbound port 25 is blocked on all major cloud providers by default.
   Use port 587 (authenticated submission) or the cloud provider's
   transactional email service (SES, SendGrid). Never fight the block.

4. TLS cert expiry is one of the most common self-inflicted outages.
   Automate renewal AND set an alert for < 30 days remaining.
   ACM certificates attached to ALB never expire — prefer ACM over
   manually managed certs whenever possible.

5. "502 Bad Gateway" = the load balancer can't reach your backend.
   Check: is the process running (ss -tlnp)? Is it on the right port?
   Is the security group allowing the ALB's IP to reach the backend?

6. Low DNS TTLs (< 60s) add latency at scale. Use short TTL (60s)
   only during deployments when you need fast DNS propagation.
   In steady state, TTL=300 or higher is better for performance.
```

---

## Interview Angle

**Q: Why does DNS use UDP instead of TCP?**

```
DNS queries are small (typically < 512 bytes) and speed-sensitive.
UDP avoids the 3-way handshake overhead — you save 1 RTT per query.
At scale (millions of DNS lookups per hour), that 1 RTT matters enormously.

If a UDP response is lost, the resolver retries after ~100ms.
Application-level retry is cheaper than TCP's guaranteed-delivery overhead
for a payload this small.

DNS falls back to TCP when:
  - Response exceeds 512 bytes (large DNSSEC responses, TXT records)
  - Zone transfers (full copy of a DNS zone, can be MBs)
```

**Q: Why is port 25 blocked on cloud providers? What should you use?**

```
Port 25 (SMTP relay) requires no authentication in the classic design.
A compromised EC2 instance could send millions of spam emails directly
to recipient mail servers — the block prevents cloud IPs from being
blacklisted as spam sources.

Use port 587 (STARTTLS authenticated submission) through a reputable
relay: AWS SES, SendGrid, Postmark, Mailgun.
Better: use the AWS SDK (boto3 ses.send_email) — no SMTP at all.
```

**Q: What's the difference between TLS 1.2 and TLS 1.3?**

```
TLS 1.2: 2 round trips for the handshake (2 RTTs before data)
         Supports weaker cipher suites (RC4, 3DES — should be disabled)
         Session resumption requires storing session state server-side

TLS 1.3: 1 round trip for new connections (1 RTT before data)
         0-RTT for resumed sessions (data in the first packet)
         Only modern cipher suites allowed — no weak options to misconfigure
         Forward secrecy mandatory — past sessions can't be decrypted
                                     even if the private key is later stolen

In practice: configure ssl_protocols TLSv1.2 TLSv1.3 — drop 1.0 and 1.1
which are deprecated. Most browsers dropped 1.0/1.1 in 2020.
```

**Q: A curl to your API times out on port 443, but SSH on 22 works fine to the same host — what do you check?**

```
1. Is anything listening on 443?
   ss -tlnp | grep :443   (on the backend host)
   → If empty: process crashed or is bound to wrong port

2. Security group / firewall:
   Does the inbound rule allow :443 from your IP?
   (Common mistake: only :22 was added when setting up the instance)

3. Load balancer health check:
   Is the ALB target group healthy?
   ALB returns 502 if no healthy targets, 504 if target is timing out

4. TLS termination:
   Is TLS being terminated at the ALB (and backend only gets :80)?
   Then curl https://BACKEND_IP:443 would fail — curl https://ALB_DNS:443 would work
```

**Q: What does HTTP/2 solve that HTTP/1.1 doesn't, and what does HTTP/3 fix that HTTP/2 still has?**

```
HTTP/1.1 → HTTP/2:
  Problem: one request per TCP connection at a time (app head-of-line blocking)
  Fix: multiplexing — many requests over ONE connection simultaneously
  Also: HPACK header compression (repeated headers sent as tiny diffs)
  Remaining problem: TCP head-of-line blocking — one lost packet stalls
  ALL streams on the connection until retransmitted (TCP's design)

HTTP/2 → HTTP/3:
  Problem: TCP-level head-of-line blocking (one lost packet stalls all streams)
  Fix: QUIC (over UDP) — each stream is independent at the transport layer,
  one lost packet only delays its own stream
  Also: 0-RTT connection resumption, built-in TLS 1.3 (fewer handshake RTTs)
  Biggest benefit: high packet-loss networks (mobile, satellite, international)
```

**Q: Explain the TLS handshake and what gets verified.**

```
Simplified TLS 1.3 (1 RTT):
  1. ClientHello: "I support TLS 1.3, here are cipher suites + DH key_share"
  2. ServerHello + Certificate: "here's my cert, let's use AES-256-GCM"
  3. Client verifies cert:
       - Signed by trusted CA (in trust store)?
       - CN/SAN matches the hostname we're connecting to?
       - Not expired?
  4. Both sides derive same symmetric key via DH (key never transmitted)
  5. Finished — data encrypted with symmetric key from here on

What this protects against:
  - Eavesdropping: data encrypted end-to-end
  - MITM: cert verification ensures you're talking to the real server
  - Replay attacks: each session has unique keys (forward secrecy in TLS 1.3)
```

---

## Related

- [`../07_Cloud_AWS/03_networking_dns_lb.md`](../07_Cloud_AWS/03_networking_dns_lb.md) — DNS record types, Route 53 routing policies, Security Groups vs NACLs
- [`03_web_concepts.md`](03_web_concepts.md) — where these protocols appear in a real request path (proxy, CDN, load balancer, API gateway)
- [`../14_Security/01_ssh_ssl_tls_hardening.md`](../14_Security/01_ssh_ssl_tls_hardening.md) — TLS hardening depth beyond the handshake summary above