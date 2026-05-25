# 14 — DDoS Mitigation

> Distributed Denial of Service: overwhelm your service with traffic so legitimate users can't access. Modern attacks reach Tbps scale.

---

## DDoS Attack Categories

### Layer 3 (Network)
Floods packets at IP layer.
- ICMP flood, UDP flood.
- Amplification attacks (DNS, NTP, memcached reflection).

### Layer 4 (Transport)
SYN floods, ACK floods. Exhaust TCP connection table.

### Layer 7 (Application)
HTTP request flood. Looks like normal traffic but at huge volume. Hardest to detect.

### Slowloris
Open many TCP connections; send headers slowly to keep them alive. Exhausts connection slots.

---

## Recent DDoS Records

- 2022: Cloudflare mitigated 26M RPS attack.
- 2023: 71M RPS attack.
- 2024: 5.6 Tbps (record).

You can't survive these alone. Need provider-level mitigation.

---

## Defense Layers

```
   Attacker
      │
      ▼
   Anycast / Scrubbing center   ← absorbs volumetric
      │
      ▼
   CDN edge                      ← absorbs L7 caching what it can
      │
      ▼
   WAF                           ← filters bad requests
      │
      ▼
   Load Balancer                 ← rate limits
      │
      ▼
   Your app                      ← graceful degradation
```

Each layer absorbs / filters.

---

## Provider-Level Protection

### Cloudflare DDoS
- Free tier: unlimited DDoS protection (L3/4).
- Anycast network of 250+ POPs.
- Auto-detection + mitigation in seconds.

### AWS Shield
- Standard: free, covers L3/L4 attacks.
- Advanced ($3000/month): L7 protection, response team, cost protection.

### Akamai Prolexic
- Enterprise-grade. Used by banks, governments.

### Google Cloud Armor
- L3-L7. Integrated with Google's network.

For most apps: **Cloudflare free tier** is excellent.

---

## How Mitigation Works

### Anycast
Same IP advertised from many locations. BGP routes traffic to nearest data center. Attack distributes across many POPs; no single POP overwhelmed.

### Scrubbing
Traffic routed through provider's data centers; analyzed; malicious dropped; clean forwarded to origin.

### Challenge-response
Suspicious requests get JavaScript / CAPTCHA challenge. Bots can't solve; legit users pass through.

### Rate limiting
Per-IP, per-region, per-endpoint thresholds.

---

## Volumetric Attack Defense

Attacks 100s of Gbps to Tbps.

**Strategies:**
- **Anycast** (Cloudflare-style).
- **Black hole routing** (drop all traffic to target IP).
- **Sinkhole** (redirect to honeypot).
- **BGP nullroute** (announce more specific route, divert).

You can't host yourself in this case. Use a provider.

---

## L7 Attack Defense

Attackers send HTTP requests that look legit but in huge volume.

### Detection
- Sudden traffic spike.
- High RPS from few IPs.
- Unusual request patterns (e.g., all hitting one endpoint).
- High proportion of 404s (scanning).
- Suspicious user agents.

### Mitigation
- **Rate limiting** per IP.
- **CAPTCHA** for suspicious.
- **JS challenge** (legit browsers solve, bots can't).
- **Geo blocking** if attack from specific countries.
- **WAF rules** for attack patterns.

### Cloudflare's "I'm Under Attack" mode
Toggle on → all visitors get JS challenge before reaching origin. Drastically reduces legit + attack traffic; you weather the storm.

---

## App-Level Defenses

Last line of defense.

### Rate limit per IP
```python
async def rate_limit_ip(ip, limit=100, window=60):
    key = f"rl:ip:{ip}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, window)
    if count > limit:
        raise HTTPException(429, "Too many requests")
```

### Rate limit per token / API key
```python
async def rate_limit_token(token, limit=1000, window=60):
    ...
```

### Per-endpoint limits
Expensive endpoints have stricter limits.

### Connection limits (Nginx)
```nginx
limit_conn_zone $binary_remote_addr zone=addr:10m;
server {
    limit_conn addr 10;   # max 10 simultaneous connections per IP
}
```

### Slowloris protection (Nginx)
```nginx
client_body_timeout 10s;
client_header_timeout 10s;
keepalive_timeout 5s 5s;
send_timeout 10s;
```

Close slow connections.

---

## Anycast at the Provider Level

Anycast = same IP from many locations. Best DDoS defense built-in.

```
Attacker sends to 1.2.3.4
  → routed by BGP to nearest POP
  → spread across 250+ data centers
  → no single point overwhelmed
```

You need:
- Multiple POPs (Cloudflare, AWS Global Accelerator).
- BGP announcement infrastructure.

Most teams: use Cloudflare. Don't build your own.

---

## Black Holing

Last-resort: drop all traffic to attacked IP.

ISPs can null-route at upstream. Effective but cuts you off from legit users.

### BGP Flowspec
More surgical: drop specific patterns (UDP/443 from /16 range).

---

## CAPTCHA / Bot Defense

### Types
- **reCAPTCHA v2:** "I'm not a robot" + image puzzles.
- **reCAPTCHA v3:** invisible scoring.
- **hCaptcha:** alternative.
- **Cloudflare Turnstile:** privacy-focused, no image puzzles.

### When to challenge
- After N failed attempts.
- Suspicious user agent.
- Geo anomaly.
- High velocity.

Don't challenge everyone — kills UX.

---

## Caching to Absorb Attacks

If WAF blocked is too strict, fall back: serve cached responses to everyone.

### CDN cache pin
```http
Cache-Control: public, max-age=3600
```

Even if origin overwhelmed, cache hits served by CDN.

### Static fallback page
"Site temporarily under heavy load. Please try again."

Better than 503 / timeout.

---

## Cost-Based Attacks

Attacker burns your cloud budget by triggering expensive operations.

### Examples
- Hitting search with random complex queries.
- Triggering image processing.
- File upload endpoints.
- Auth attempts (each = bcrypt CPU).

### Defense
- Resource-aware rate limiting.
- Quotas per user / IP.
- Auto-scaling caps (limit max instances).
- Cost monitoring + alerts.
- Cloudflare's "Origin Shield" caches expensive responses.

---

## Application-Level Brute Force

Login endpoint floods to crack passwords.

### Defenses
- Rate limit per username (5 failed attempts → lock 15 min).
- Rate limit per IP (10 failed across users → IP throttled).
- CAPTCHA after 3 failures.
- Account lockout (with notify-on-unlock email).
- Detect credential stuffing patterns.
- IP reputation (Have I Been Pwned).

```python
async def login(req):
    fail_key = f"fail:{req.username}"
    failures = await redis.get(fail_key) or 0
    if int(failures) > 5:
        raise HTTPException(429, "Too many attempts")

    try:
        user = await authenticate(req)
        await redis.delete(fail_key)
        return user
    except AuthError:
        await redis.incr(fail_key)
        await redis.expire(fail_key, 900)
        raise
```

---

## SYN Flood Defense

Tcp SYN packets consume connection table without completing handshake.

### Defenses
- **SYN cookies** (kernel-level; Linux has it on by default).
- **Connection rate limiting** at firewall.
- **TCP fast open** (cuts setup time).

```bash
# Linux: enable SYN cookies
sysctl -w net.ipv4.tcp_syncookies=1
```

Most distros enable by default.

---

## Amplification Attacks

Attacker sends small request with spoofed source IP; server responds large packet to victim.

### Examples
- DNS amplification (1:50 ratio).
- NTP amplification (1:500).
- Memcached amplification (1:50,000).

### Defenses (server-side)
- Don't expose recursive DNS publicly.
- Don't expose memcached/redis to internet.
- Rate-limit response sizes.

### Defenses (target-side)
- Block UDP at edge if you don't use it.
- BCP38: prevent IP spoofing at ISP level.

---

## Real-Time Response Plan

When under attack:

### Immediate (first 5 min)
1. Confirm it's a DDoS (vs traffic spike from launch).
2. Enable "Under Attack" mode at CDN.
3. Identify attack vector (UI, logs).
4. Mute non-critical alerts.

### Short-term (5-30 min)
1. Block obvious attack patterns (IPs, user agents).
2. Tighten rate limits.
3. Enable challenges.
4. Cache more aggressively.
5. Scale up if attack survivable.

### Long-term (30 min+)
1. Engage provider's DDoS response team if needed.
2. BGP nullroute if amplification.
3. Investigate post-incident.

---

## Cost of an Attack

- Lost revenue from downtime.
- Cloud bill spike (auto-scale + transfer costs).
- Engineering time.
- Reputation damage.

### Insurance
Cyber insurance covers DDoS impact for enterprise.

### Cloudflare cost protection
Their Pro/Business/Enterprise plans absorb traffic; you don't pay for attack bandwidth.

---

## DDoS-Resilient Architecture

### Design choices that help
- Stateless services (easier to scale).
- CDN-friendly responses (Cache-Control headers).
- Async/background work (degrades gracefully).
- Circuit breakers between services.
- Per-tenant resource limits.
- Connection pooling on DBs.

### Things that hurt
- Synchronous external API calls (one slow downstream → all threads blocked).
- Expensive per-request operations.
- Unbounded internal queues.
- No rate limits.

---

## Testing Your Defenses

Use ethical load testing:
- **Locust:** Python load testing.
- **k6:** modern load testing.
- **Vegeta:** HTTP load tool.

Or controlled DDoS services (with authorization):
- **MazeBolt RADAR.**
- **NimbusDDOS.**

NEVER test against systems you don't own without explicit permission. Illegal.

---

## Common Mistakes

### 1. Relying solely on auto-scaling
Auto-scaling has limits. Some attacks scale faster than your scaling.

### 2. No CDN
Direct exposure → attack hits you directly.

### 3. No rate limits at app level
WAF is good but not enough.

### 4. Storing attack logs forever
Floods log infra. Sample or rotate.

### 5. Not testing failover
Cold-start under attack = bad.

### 6. Reactive only
Wait for attack → too late. Set up provider + monitoring proactively.

### 7. No incident playbook
First attack = chaos.

---

## TL;DR

- Modern DDoS goes to Tbps; can't fight alone.
- Use a provider (Cloudflare free tier is excellent).
- Defense in depth: Anycast/CDN → WAF → LB rate limit → app rate limit.
- Volumetric attacks: provider mitigates.
- L7 attacks: rate limits, challenges, caching.
- App-level: rate limit per IP/token/endpoint.
- Have a runbook for under-attack scenarios.
- Test before you need it.
