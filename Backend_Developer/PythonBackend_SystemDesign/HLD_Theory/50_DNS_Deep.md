# 50 — DNS Deep

> The phonebook of the internet. Most engineers know "it resolves names to IPs", but DNS has hidden depth that breaks production systems regularly.

---

## What DNS Does

```
"google.com" → "142.250.190.78"
"api.example.com" → "1.2.3.4"
```

A globally distributed key-value store mapping names → IP addresses (and other records).

---

## Hierarchy

```
Root (.) ── managed by ICANN
  │
  ├── com.
  │     └── google.com.
  │           └── mail.google.com.
  ├── org.
  ├── io.
  └── in.
        └── razorpay.in.
```

Each level managed independently.

---

## Resolution Process

```
1. App calls gethostbyname("api.example.com")
2. OS asks local DNS resolver (configured in /etc/resolv.conf)
3. Resolver checks cache. If miss:

   ┌─ ROOT name server (knows .com nameservers)
   │
   ├─ TLD name server (knows example.com nameservers)
   │
   ├─ Authoritative name server for example.com (knows api.example.com IP)
   │
   ▼
   Returns IP to resolver → returns to OS → returns to app
```

Each step: one UDP query (or TCP if response > 512 bytes).

### Recursive vs Iterative
- **Recursive resolver** (your ISP, Google DNS, Cloudflare 1.1.1.1): does all the work for you.
- **Iterative resolution**: client gets pointed to next server at each step.

---

## DNS Record Types

| Type | Purpose | Example |
|---|---|---|
| A | IPv4 address | example.com → 1.2.3.4 |
| AAAA | IPv6 address | example.com → 2001:... |
| CNAME | Alias to another name | www.example.com → example.com |
| MX | Mail server | example.com → mail.example.com |
| NS | Name server for domain | example.com → ns1.example.com |
| TXT | Arbitrary text | SPF, DMARC, domain verification |
| SRV | Service location | _service._tcp → port + host |
| CAA | Allowed cert issuers | letsencrypt.org |
| PTR | Reverse (IP → name) | 1.2.3.4 → example.com |
| SOA | Zone metadata | serial, refresh, retry |

---

## CNAME vs A vs ALIAS

### A record
Direct: name → IPv4. Can be set at apex (root) of domain.

### CNAME
Indirection: name → another name. Then the new name is looked up.

**Rule:** CNAME can NOT be at apex of domain (the bare `example.com`). Only on subdomains.

### ALIAS (cloud-specific, e.g., AWS Route 53)
Apex-level CNAME-like. Resolved at DNS server, not client. Works at apex.

```
example.com    → ALIAS → mybucket.s3.amazonaws.com
www.example.com → CNAME → example.com
```

---

## TTL — Time To Live

Each DNS record has a TTL (seconds).

```
example.com IN A 1.2.3.4 TTL=300
```

Resolvers cache for that TTL.

### Why TTL matters in production

**Low TTL (60-300s):**
- Fast failover when changing IPs.
- More DNS queries (load on auth servers).
- Used for active-active load balancing.

**High TTL (3600-86400s):**
- Few queries.
- Slow failover (clients cached old IP for hours).
- Used for stable endpoints.

**Production pattern:** Lower TTL before planned IP change.
```
T-24h: change TTL to 60s.
T-0h:  change IP.
T+24h: optionally restore TTL.
```

### TTL is a hint, not a contract
Some clients ignore TTL. Browser caches DNS for 60s minimum often. Java's default DNS cache is "forever" (set `networkaddress.cache.ttl=60`).

---

## DNS Caching Layers

```
[App ──► OS resolver ──► /etc/resolv.conf ──► ISP resolver ──► auth name server]
   │         │                                    │
   └── Local │                                    │
       cache │                                    │
           Cache (until TTL)                  Cache
```

Each layer has its own cache. Invalidation is hard.

---

## DNS Load Balancing

### Round-robin DNS
Multiple A records for same name. Resolver returns them in rotation.

```
example.com IN A 1.2.3.4
example.com IN A 1.2.3.5
example.com IN A 1.2.3.6
```

**Problems:**
- No health checking. Dead IP still returned.
- Cache means client sticks to first received.
- TTL-bound failover.

### Geo-DNS
Auth server returns different IPs based on requester's location.

```
User in US     → 50.1.1.1 (US datacenter)
User in EU     → 51.1.1.1 (EU datacenter)
User in Asia   → 52.1.1.1 (Asia datacenter)
```

Used by: CDNs, multi-region cloud (Route 53 latency-based routing).

### Health-checked DNS
Auth server probes endpoints, only returns healthy ones.

Provided by: Route 53, Cloudflare, Akamai, NS1.

---

## DNS Anycast

Multiple physical servers share same IP address. BGP routes you to nearest one.

Used by:
- Public resolvers: 8.8.8.8, 1.1.1.1, 9.9.9.9.
- Root name servers (13 logical roots, hundreds of physical).
- CDN edge servers.

Result: ultra-low latency.

---

## DNS Security

### Plain DNS = insecure
- UDP, no auth, no encryption.
- Can be spoofed (DNS hijacking).
- Resolver can lie.

### DNSSEC (DNS Security Extensions)
- Signed records via public-key crypto.
- Auth server signs zone with private key.
- Resolver verifies with public key from parent zone.
- Chain of trust up to root.

**Adoption:** ~30% of domains. Complex to deploy correctly.

### DoH (DNS over HTTPS) / DoT (DNS over TLS)
- Encrypts DNS queries between client and resolver.
- Prevents ISP/network from seeing/manipulating queries.
- DoH on port 443 (looks like HTTPS).
- DoT on port 853.

Cloudflare 1.1.1.1, Google 8.8.8.8 support both.

### Encrypted Client Hello (ECH)
- Hides SNI in TLS handshake.
- Combined with DoH/DoT → ISP can't tell which site you're visiting.

---

## Common DNS Issues in Production

### 1. Java DNS caching forever
Default JVM caches DNS resolution forever. If you change an IP, Java app never picks it up.

**Fix:**
```
networkaddress.cache.ttl=60
```
in `java.security` or via `Security.setProperty()`.

### 2. Stale connections after IP change
- App resolved DNS at startup, cached IP.
- Backend IP changed.
- App keeps connecting to old IP until restart.

**Fix:** Use service discovery (Consul, Eureka, K8s Service) or short DNS TTL + close-and-reconnect strategy.

### 3. DNS resolution slow / fails
- Local resolver overloaded.
- Auth server slow.
- Anycast routing weirdness.

**Diagnose:**
```bash
dig +trace example.com    # full resolution path
nslookup example.com
host example.com
```

### 4. Wildcard records gotcha
```
*.example.com → 1.2.3.4
api.example.com → 5.6.7.8
foo.bar.example.com → ???
```

Wildcards match one level. `foo.bar.example.com` is NOT matched by `*.example.com`.

### 5. CNAME chain too long
```
www → web1 → web2 → web3 → ip
```
Each step = DNS query. Some resolvers refuse > 10 hops.

### 6. EDNS Client Subnet (ECS) issues
For geo-DNS to know your location, your resolver tells auth server your subnet. Some resolvers strip this → wrong geo-routing.

---

## DNS in Kubernetes

CoreDNS runs inside cluster as a service:
- Service `my-svc` in namespace `default` → resolvable as `my-svc.default.svc.cluster.local`.
- Pods configured with `/etc/resolv.conf` pointing to CoreDNS.

### Performance pitfall: NDOTS
Default `/etc/resolv.conf` has `ndots: 5`. Means: try domain with each search suffix first.

```bash
curl example.com
# Tries:
#   example.com.default.svc.cluster.local
#   example.com.svc.cluster.local
#   example.com.cluster.local
#   example.com   ← only here
```

Fix: trailing dot or `ndots: 1`. Massive perf win in K8s.

```python
# Append dot
requests.get("https://example.com.")
```

### Conntrack table overflow
DNS uses UDP → tracked in conntrack table.
Lots of DNS queries → table fills → packets dropped.

Fix: tune `nf_conntrack_max`, or use NodeLocal DNS Cache.

---

## Self-Hosted DNS

If you run your own DNS:
- BIND9 (oldest, complex).
- PowerDNS (modern, with DB backend).
- CoreDNS (Go, used in K8s).
- Unbound (recursive resolver).

**Operational must-haves:**
- Multiple geographically distributed servers (Anycast or simple replication).
- Monitoring of NXDOMAIN rate, response time.
- Zone transfer (AXFR) controls.
- DNSSEC key rollover.

---

## Useful Commands

```bash
# Basic
dig example.com
dig example.com MX
dig example.com NS

# Verbose
dig +trace example.com
dig +short example.com

# Specific resolver
dig @8.8.8.8 example.com
dig @1.1.1.1 example.com

# Reverse
dig -x 1.2.3.4

# DNSSEC
dig +dnssec example.com

# DoH (with curl)
curl -H 'accept: application/dns-json' \
     'https://cloudflare-dns.com/dns-query?name=example.com&type=A'
```

---

## DNS Propagation Myth

There's no "propagation" — DNS doesn't push. Resolvers pull.

What people call "propagation":
- Old records expiring from caches around the world.
- Time = max(TTL) of cached records.

**Fast propagation = pre-set short TTL before the change.**

---

## Real-World Setup (Production)

```
example.com  IN  A      → 1.2.3.4 (TTL 60)
www          IN  CNAME  → example.com.
api          IN  A      → 5.6.7.8
api          IN  A      → 5.6.7.9   (multiple for LB)
*.staging    IN  CNAME  → staging.example.com.
mail         IN  MX 10  → mail.example.com.
@            IN  TXT    → "v=spf1 include:_spf.google.com ~all"
_dmarc       IN  TXT    → "v=DMARC1; p=reject; ..."
```

---

## DNS at Massive Scale

### Cloudflare's 1.1.1.1
- 250+ POPs globally.
- Anycast.
- ~14ms average response time globally.
- DNS-over-HTTPS, DNSSEC validation.

### Route 53
- AWS's DNS service.
- Health checks, weighted routing, geo-routing.
- Integrates with AWS load balancers (ALIAS records).

### NS1
- Enterprise DNS.
- Real-time analytics and decision-engines for traffic routing.

---

## Future of DNS

- **HTTPS records (HTTPS/SVCB):** allow specifying HTTPS port + protocol + IPs in one record.
- **Adaptive DNS:** ML-based traffic routing.
- **More DoH/DoT adoption:** less plain-UDP DNS.
- **Decentralized DNS:** blockchain-based name systems (controversial, mostly hype).

---

## Interview Tips

**Common question:** *"How does CDN routing work?"*

**Answer arc:**
1. User types example.com.
2. DNS resolution: their resolver asks the CDN's name server.
3. CDN's DNS uses anycast or geo-resolving to return nearest edge IP.
4. Client connects to that edge.
5. Edge serves cache hit or proxies to origin.

**Bonus question:** *"What if I want zero-downtime migration to a new IP?"*

Steps:
1. Set TTL very low (60s) several days before migration.
2. Wait for old high-TTL records to expire from caches.
3. At T=0, change IP.
4. Within ~60s globally, new IP is live.

---

## TL;DR

- DNS = global hierarchical KV.
- Resolution: recursive resolver walks hierarchy.
- TTL governs caching but is a hint.
- Java caches forever by default — gotcha.
- Use service discovery for fast-changing endpoints.
- DoH/DoT for privacy.
- In K8s, mind ndots default and conntrack.

**Always:** keep DNS in mind during outage triage. "Is DNS working?" is the most-missed early question.
