# Core Network Protocols

**DevOps Track · Phase 3: Networking**

## Quick Concepts

- **Port** = a number identifying a specific service/process on a host (0-65535)
- **Well-known ports** = 0-1023, reserved for standard protocols (needs root to bind on Linux)
- **Connection-oriented (TCP)** = handshake first, guaranteed ordered delivery, retransmits lost packets
- **Connectionless (UDP)** = fire-and-forget, no delivery guarantee, lower latency/overhead
- **TLS/SSL** = encryption layer wrapped around a protocol (HTTP→HTTPS, SMTP→SMTPS)

---

## Why This Matters for Backend/DevOps Work

```
Every service you deploy, every firewall rule you write, every
security group in AWS — comes down to "which protocol, which port,
why." This is the vocabulary layer under load balancers, VPNs,
Kubernetes services, and every "connection refused" ticket you'll get.
```

---

## Protocol Reference Table

| Protocol | Port | Purpose | DevOps Scenario |
|---|---|---|---|
| **HTTP** | 80 | Unencrypted web traffic | Redirecting all :80 traffic to :443 in an Nginx/ALB config |
| **HTTPS** | 443 | Encrypted web traffic (HTTP + TLS) | Terminating TLS at a load balancer, renewing a Let's Encrypt cert before it expires |
| **TCP** | (transport layer, no fixed port) | Reliable, ordered, connection-oriented byte stream | Choosing TCP for your app's health-check protocol because dropped/out-of-order packets would break correctness |
| **UDP** | (transport layer, no fixed port) | Fast, connectionless, no delivery guarantee | DNS queries, video/voice streaming, metrics/telemetry (StatsD) where an occasional dropped packet is fine |
| **SSH** | 22 | Encrypted remote shell/tunnel | Restricting inbound :22 to a bastion host's IP only in a security group |
| **FTP** | 21 (control), 20 (data) | File transfer, unencrypted | Legacy — you'll mostly see this migrating AWAY from FTP to SFTP/S3 |
| **SMTP** | 25 (relay), 587 (submission) | Sending email | Configuring an app to send transactional email via SES/SendGrid on port 587 |
| **DNS** | 53 (UDP primarily, TCP for large responses/zone transfers) | Name resolution | Debugging why a service can't resolve an internal hostname — checking Route 53 / CoreDNS |
| **DHCP** | 67 (server), 68 (client) | Automatic IP address assignment | Understanding why a VM got an unexpected IP after a reboot on a DHCP-managed subnet |
| **SSL/TLS** | N/A (wraps other protocols) | Encryption + authentication for data in transit | Choosing TLS 1.2+ only in an Nginx config, rotating certs, debugging handshake failures with `curl -v` |

---

## Deep Dive per Protocol

### HTTP / HTTPS

```
HTTP:  plaintext request/response, port 80
HTTPS: HTTP wrapped in TLS, port 443 — encrypts the payload AND
       (mostly) hides the URL path from network observers, but NOT
       the destination IP/SNI hostname (visible during the handshake)

curl -I http://example.com          # confirm a redirect to https
curl -v https://example.com 2>&1 | grep -i "SSL\|TLS"   # see the negotiated TLS version

DevOps reality: you almost never terminate TLS in your app process in
production — a load balancer (ALB/Nginx) does it, then talks plain
HTTP to the backend over the private network.
```

### HTTP/2 and HTTP/3 (QUIC) — What's Actually Different

```
HTTP/1.1 (the version implicitly assumed everywhere above): one
request per connection at a time, in order — "head-of-line blocking"
at the application level. Workarounds (multiple parallel connections
per browser, sprite-sheeting, JS/CSS bundling) exist ONLY because of
this limitation, and most of them stop being necessary past HTTP/1.1.

HTTP/2 (2015):
  - MULTIPLEXING — many requests/responses interleaved over a SINGLE
    TCP connection, no more head-of-line blocking at the app layer
  - Header compression (HPACK) — repeated headers across requests
    (cookies, user-agent) aren't re-sent in full every time
  - Server push (mostly abandoned in practice — browsers largely
    dropped support; know it existed, don't expect to use it)
  - Still runs over TCP — so TCP-level head-of-line blocking (one
    lost packet stalls ALL multiplexed streams on that connection)
    remains a real limitation HTTP/2 doesn't fully solve

HTTP/3 (built on QUIC, over UDP):
  - Replaces TCP entirely with QUIC (itself built on UDP) — solves
    the TCP-level head-of-line blocking HTTP/2 still has, because
    QUIC multiplexes streams at a layer that doesn't stall ALL
    streams when ONE packet is lost
  - Built-in TLS 1.3 — the transport and encryption handshakes are
    combined into fewer round trips than TCP+TLS negotiated separately
  - Faster connection establishment, especially valuable on lossy/
    high-latency mobile networks — this is WHY CDNs (Cloudflare,
    Google, increasingly CloudFront) push hard on HTTP/3 adoption
```

```bash
curl -I --http2 https://example.com     # force HTTP/2, see if the server supports it
curl -I --http3 https://example.com       # force HTTP/3 (needs a curl build with QUIC support)
curl -v https://example.com 2>&1 | grep -i "using http"   # see which version was negotiated
```

```
DevOps-relevant reality: HTTP/2 and HTTP/3 support usually come FREE
from your load balancer/CDN (ALB, CloudFront, Nginx 1.25+, Cloudflare
all support HTTP/2 out of the box, HTTP/3 increasingly by default) —
you rarely implement the protocol yourself, you ENABLE it in config
and the client negotiates automatically (falling back to HTTP/1.1 for
older clients). Know this exists and why it matters more than needing
to hand-implement anything at the QUIC/frame level.
```

### TCP vs UDP

```
TCP: 3-way handshake (SYN, SYN-ACK, ACK) before any data flows.
     Guarantees ordered, complete delivery via acknowledgments and
     retransmission. Higher overhead, used for HTTP, SSH, database
     connections — anywhere correctness matters more than raw speed.

UDP: No handshake, no guarantee. Fire the packet and hope. Used for
     DNS (small, fast, retriable at the app layer), video/voice
     (a dropped frame is fine, a stall is not), and metrics pipelines
     where losing one data point occasionally doesn't matter.

Interview framing: "would losing this packet silently break the
application, or is it fine to just drop it and move on?" TCP if the
former, UDP if the latter.
```

### SSH

```
Encrypted remote shell + tunneling protocol, port 22 by default.
Key-based auth (see 01_Linux/06_networking_commands.md for setup).

DevOps use: bastion/jump hosts, git-over-ssh, ansible's default
transport, tunneling a remote DB port to your laptop for a one-off query.
```

### FTP

```
Port 21 for control commands, port 20 (or a random high port in
passive mode) for the actual data transfer — this dual-channel,
unencrypted design is WHY FTP is painful behind firewalls/NAT and
why SFTP (SSH-based, port 22) or S3 has mostly replaced it.
```

### SMTP

```
Port 25 — traditional server-to-server mail relay, often BLOCKED
outbound by cloud providers (AWS, GCP) by default to fight spam.
Port 587 — "submission," the port your APPLICATION should use to
send mail through an authenticated relay (SES, SendGrid, Postmark).

DevOps use: configuring app SMTP settings to use 587 + STARTTLS, not
raw port 25, because 25 will often be silently blocked outbound.
```

### DNS

```
Port 53, primarily UDP (fast, small queries) with fallback to TCP for
responses too large for a single UDP packet (zone transfers, DNSSEC).

dig example.com                  # query
dig +short example.com             # just the answer
dig @8.8.8.8 example.com             # query a specific resolver directly
nslookup example.com                   # alternative tool

DevOps use: debugging service discovery in Kubernetes (CoreDNS),
verifying a Route 53 record propagated, diagnosing "works via IP but
not via hostname" issues.
```

Record types (A, AAAA, CNAME, MX, TXT, NS) and Route 53's routing policies (weighted, latency-based, failover, geolocation) are AWS-specific enough to live in their own file rather than duplicated here — full depth: `07_Cloud_AWS/03_networking_dns_lb.md`.

### DHCP

```
Port 67 (server → client offers), port 68 (client → server requests).
Automatically assigns IP, subnet mask, gateway, DNS servers to a host
joining a network.

DevOps use: mostly invisible in cloud environments (VPCs assign IPs
via their own mechanism), but relevant on-prem/bare-metal and when
debugging why a freshly booted VM got a DIFFERENT IP than expected.
```

### SSL/TLS

```
Not a standalone protocol with its own port — it WRAPS other
protocols. TLS is the modern name; SSL is the deprecated predecessor
(SSLv2/v3 are broken, should never be enabled).

Handshake (simplified):
  1. Client Hello (supported TLS versions/ciphers)
  2. Server Hello + certificate (public key, signed by a CA)
  3. Key exchange → both sides derive a shared symmetric session key
  4. Encrypted application data flows from here on

DevOps use: renewing certs (Let's Encrypt/ACM) before expiry, forcing
TLS 1.2+ in Nginx config, debugging `curl -v` handshake failures,
understanding why an expired cert breaks EVERY client at once.
```

---

## Senior Tip

```
1. Know the port numbers cold — 22, 53, 80, 443, 587 come up
   constantly in security group rules, Nginx configs, and interviews.
2. TCP vs UDP choice is a design decision, not a default — ask "can
   this application tolerate a dropped or out-of-order packet?"
3. Outbound port 25 is blocked by default on AWS/GCP/Azure — always
   use 587 (or the provider's transactional email service) for app-sent mail.
4. TLS certificate expiry is one of the most common self-inflicted
   outages — automate renewal (certbot cron/systemd timer, ACM
   auto-renewal) and alert on days-until-expiry.
```

## Interview Angle

**Q: Why does DNS use UDP instead of TCP?**
DNS queries are small and speed-sensitive — UDP avoids the 3-way handshake overhead. If a query is lost, the resolver just retries; the application-level retry is cheaper than TCP's guaranteed-delivery overhead for a payload this small. DNS falls back to TCP only when a response exceeds a single UDP packet (large record sets, zone transfers, DNSSEC).

**Q: Why is port 25 usually blocked outbound on cloud providers, and what should you use instead?**
Port 25 is the classic direct-to-mailserver spam vector; cloud providers block it by default to prevent compromised instances from becoming spam relays. Applications should send mail via port 587 (authenticated submission) through a reputable relay (SES, SendGrid) instead.

**Q: What's the practical difference between SSL and TLS?**
TLS is the modern, secure successor to SSL — SSL 2.0/3.0 have known vulnerabilities and should be disabled everywhere. "SSL" is still used colloquially/in cert names (SSL certificate) but the actual protocol running today is TLS 1.2 or 1.3.

**Q: A curl to your API times out on port 443 but SSH on 22 works fine to the same host — what do you check?**
Likely a security group / firewall rule scoped only to port 22, or nothing is actually listening on 443 (check `ss -tlnp` on the host), or a load balancer/target group health check is failing and routing around the instance.

**Q: What does HTTP/2 actually solve that HTTP/1.1 didn't, and what does HTTP/3 fix that HTTP/2 still has?**
HTTP/1.1 processes one request at a time per connection, causing application-level head-of-line blocking (the workaround was opening multiple parallel connections). HTTP/2 multiplexes many requests over ONE TCP connection, removing that app-level blocking — but it still runs over TCP, so a single lost packet still stalls every multiplexed stream on that connection (TCP-level head-of-line blocking). HTTP/3 replaces TCP with QUIC (over UDP), which multiplexes at a layer where one lost packet only stalls its own stream, not all of them — which is why lossy/high-latency mobile networks benefit from it most.

---

## Related

- [`../07_Cloud_AWS/03_networking_dns_lb.md`](../07_Cloud_AWS/03_networking_dns_lb.md) — DNS record types, Route 53 routing policies, Security Groups vs NACLs
- [`03_web_concepts.md`](03_web_concepts.md) — where these protocols show up in a real request path (proxy, CDN, load balancer, gateway)
- [`../14_Security/01_ssh_ssl_tls_hardening.md`](../14_Security/01_ssh_ssl_tls_hardening.md) — TLS hardening depth beyond the handshake summary above
