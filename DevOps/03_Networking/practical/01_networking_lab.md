# Networking — Hands-On Labs
**DevOps Track · Phase 3 Practical**

Labs map directly to the three theory files:
- Labs 1 + 2 → `01_osi_tcpip_fundamentals.md` (triage, subnetting, NAT)
- Labs 3 + 4 → `02_protocols.md` (DNS, TLS, SSH, ports)
- Labs 5 + 6 → `03_web_concepts.md` (proxy, load balancing, WebSocket)
- Lab 7 → `01_osi_tcpip_fundamentals.md` + `02_protocols.md` (VPC design + routing)

---

## Prerequisites

```
Tools needed (check before starting):
  curl --version
  dig example.com (or nslookup — dig preferred)
  ping -c 1 example.com
  nc -zv localhost 80 2>&1 | head -1
  openssl s_client --help 2>&1 | head -1
  python3 -m http.server --help 2>&1 | head -1

Linux: ss, ip route — both pre-installed
macOS: netstat -an (substitute for ss), route -n (substitute for ip route)
       lsof -i :PORT  (substitute for ss -tlnp | grep PORT)

No cloud account needed for Labs 1-6.
Lab 7 (VPC design) is pure math/design — no tools required.
```

---

## Lab 1: OSI Layer Triage — "The Site Is Down" (60-second sequence)

**Objective:** Build the muscle memory triage sequence every DevOps/backend engineer runs at the start of an incident. By the end you will know exactly which layer is broken just from the error message.

**Why this matters:**
```
Most "site is down" investigations fail not because the engineer lacks
knowledge but because they start at the WRONG layer.

Example: engineer ssh's to the app server and restarts the process —
but the problem was a BGP route flap at Layer 3. Restarting the app
did nothing. They lost 20 minutes.

The triage sequence forces you to work bottom-up:
  DNS → L3 → L4 → L7
Each step can only be attempted if the layer below it passes.
```

**Task:**

```
Part A — Standard triage sequence (learn the order)

1. DNS check — does the name resolve?
   dig +short example.com
   Expected: one or more IP addresses
   Failure signal: empty output or ";; NXDOMAIN" → problem is DNS (L7 service)

2. L3 check — is the destination IP reachable?
   ping -c 4 example.com
   Expected: 4 packets sent, 0% packet loss, RTT ~50-200ms depending on location
   Failure signal: "100% packet loss" → routing or firewall problem (L3)
   RULE: "ping works" is NOT "the app is healthy". Never close an incident on
   ping alone. ICMP and HTTP are different protocols — a firewall can allow
   ICMP but block TCP 443.

3. L4 check — is the port open and accepting TCP connections?
   nc -zv -w 3 example.com 443
   Expected: "Connection to example.com port 443 [tcp/https] succeeded!"
   Failure 1: "Connection refused" → process not listening, or firewall REJECT
   Failure 2: (hangs then times out) → firewall DROP (silently discards packets)
   KEY DISTINCTION:
     "connection refused"  = L4 reached the host, got RST back — host is UP,
                             nothing listening on that port (or firewalled with REJECT)
     "connection timed out" = L4 packets vanished — host unreachable OR firewalled
                              with DROP. The silence itself is the signal.

4. L7 check — is the app responding correctly?
   curl -sf -o /dev/null -w "Status: %{http_code}\n" https://example.com
   Expected: Status: 200
   If you get 200, DNS + L3 + L4 + app are all working.

5. HTTP timing breakdown — where is the time going?
   curl -o /dev/null -s -w "\
   dns:     %{time_namelookup}s\n\
   tcp:     %{time_connect}s\n\
   tls:     %{time_appconnect}s\n\
   ttfb:    %{time_starttransfer}s\n\
   total:   %{time_total}s\n" https://example.com

   Read these as "time from start to this event completed":
     dns       0.05s → DNS resolution took 50ms
     tcp       0.12s → TCP handshake completed 70ms after DNS
     tls       0.25s → TLS handshake took 130ms
     ttfb      0.31s → server started sending response 60ms after TLS
     total     0.35s → full body received

   Production diagnosis with these numbers:
     dns >> 0.1s   → slow resolver, consider Route53 or 1.1.1.1
     tcp >> 0.2s   → network latency to origin, consider CDN
     tls >> 0.3s   → heavy TLS negotiation, check ssl_session_cache
     ttfb >> 0.5s  → slow backend, check DB queries, not a network problem
```

```
Part B — Deliberately break each layer and classify the failure

Run each command, observe the error, classify the OSI layer:

# DNS failure — NXDOMAIN
dig this-hostname-definitely-does-not-exist-xyz.invalid
curl https://this-hostname-definitely-does-not-exist-xyz.invalid
# Expected: dig returns NXDOMAIN, curl returns "(6) Could not resolve host"

# L4 failure — closed port
nc -zv -w 3 example.com 81
# Expected: "Connection refused" or timeout (port 81 not open on example.com)
curl --connect-timeout 3 http://example.com:81
# Expected: "(7) Failed to connect"

# L7 failure — port open, wrong protocol
curl http://example.com:443
# Expected: TLS/protocol mismatch — the TCP connection SUCCEEDS (port IS open)
# but the server speaks TLS and you sent plaintext HTTP
# Error varies: "(1) Received HTTP/0.9 when not allowed" or SSL alert

Classify each:
  NXDOMAIN:          DNS/L7 service failure (before any TCP connection)
  Port refused:       L4 — network path fine, transport blocked/missing
  Protocol mismatch:  L7 — L3 and L4 both fine, application speaks wrong language
```

<details>
<summary>Solution / walkthrough</summary>

```bash
# Part A

# Step 1: DNS
dig +short example.com
# 93.184.216.34
# (or multiple IPs for load-balanced domains)

# Step 2: L3
ping -c 4 example.com
# 4 packets transmitted, 4 received, 0% packet loss
# round-trip min/avg/max = 7.4/8.1/9.2 ms

# Step 3: L4
nc -zv -w 3 example.com 443
# Connection to example.com port 443 [tcp/https] succeeded!

# Step 4: L7
curl -sf -o /dev/null -w "Status: %{http_code}\n" https://example.com
# Status: 200

# Step 5: Timing
curl -o /dev/null -s -w \
  "dns: %{time_namelookup}s\ntcp: %{time_connect}s\ntls: %{time_appconnect}s\nttfb: %{time_starttransfer}s\ntotal: %{time_total}s\n" \
  https://example.com
# dns:  0.006s   ← DNS cached (sub-10ms = OS cache hit)
# tcp:  0.084s   ← 78ms to TCP handshake complete
# tls:  0.188s   ← 104ms for TLS 1.3 handshake
# ttfb: 0.195s   ← 7ms backend processing time (fast, static HTML)
# total: 0.197s

# Part B

# DNS failure
dig this-hostname-definitely-does-not-exist-xyz.invalid
# ;; ANSWER SECTION: (empty)
# ;; AUTHORITY SECTION:
# invalid.  86400  IN  SOA  ...
# Status: NXDOMAIN
# curl error: Could not resolve host

# L4 failure
nc -zv -w 3 example.com 81
# nc: connect to example.com port 81 (tcp) timed out
# (firewall drops packets silently — no RST = timeout, not refused)

# L7 failure
curl http://example.com:443
# Error response from the TLS layer:
# "Received HTTP/0.9 when not allowed" — server sent TLS ClientHello
# response to our plaintext HTTP request
```

**Key rule to remember:** The triage order is DNS → ping → nc → curl. Never skip levels. If DNS fails, nc and curl will also fail but for the WRONG reported reason — you'll chase a "curl: Failed to connect" when the actual problem was DNS all along.
</details>

---

## Lab 2: Socket States and Port Forensics

**Objective:** Read socket state output the way a doctor reads an ECG — each state tells you something specific about connection health. Learn to detect the three most important signals: who owns a port, CLOSE_WAIT (FD leak), and SYN_RECV (SYN flood).

**Why this matters:**
```
"Port 8080 is already in use" is a message every developer sees.
The instinct is to kill -9 the process. But on a shared box, killing
the wrong process causes an outage. The correct move is:
  1. Find EXACTLY which process owns the port
  2. Verify via TWO independent tools (prevent killing wrong process)
  3. Check if it's the same app crashed and still holding the socket
     (CLOSE_WAIT state) — sometimes you DON'T kill it, you fix the bug

Production significance:
  CLOSE_WAIT = remote side closed, your app hasn't called close() yet
               → file descriptor leak, will exhaust FDs over time
  TIME_WAIT  = your side closed, waiting for delayed packets
               → normal behavior, but high counts mean connection pooling
                 is absent (opening a new TCP connection for every request)
  SYN_RECV   = half-open connections accumulating
               → SYN flood attack or misconfigured client
```

**Task:**

```
Part A — Find and verify a process by port

1. Start a listener:
   python3 -m http.server 8123 &

2. Find which process owns port 8123:
   # Linux:
   ss -tlnp | grep 8123
   # Output format: LISTEN 0 5 0.0.0.0:8123 0.0.0.0:* users:(("python3",pid=XXXX,fd=3))

   # macOS:
   lsof -i :8123
   netstat -an | grep 8123

3. Cross-verify the PID with ps:
   ps aux | grep http.server | grep -v grep
   # PID from ss/lsof and ps must match — this is the safety check
   # before killing anything on a shared machine

4. Verify reachability from a second tool (nc confirms TCP L4, curl confirms L7):
   nc -zv localhost 8123
   curl -I http://localhost:8123

5. Kill via port (not process name):
   # Linux:
   kill $(ss -tlnp | grep ':8123' | grep -oP 'pid=\K[0-9]+')
   # macOS / portable:
   kill $(lsof -t -i:8123)

6. Confirm port is free:
   ss -tlnp | grep 8123    # Linux (no output = port free)
   lsof -i :8123           # macOS (no output = port free)
```

```
Part B — Understand 0.0.0.0 vs 127.0.0.1 as the listening address

Start two servers on different ports with different bind addresses:
   python3 -m http.server 8124 &                    # binds 0.0.0.0 (all interfaces)
   python3 -m http.server 8125 --bind 127.0.0.1 &   # binds loopback only

Check what ss shows:
   ss -tlnp | grep -E '812[45]'
   # 8124: 0.0.0.0:8124 ← reachable from any network interface
   # 8125: 127.0.0.1:8125 ← reachable from localhost ONLY

Test the difference:
   curl http://localhost:8124         # works
   curl http://localhost:8125         # works (localhost = 127.0.0.1)
   curl http://$(hostname -I | awk '{print $1}'):8124   # works (your LAN IP)
   curl http://$(hostname -I | awk '{print $1}'):8125   # FAILS (LAN IP ≠ 127.0.0.1)

Production rule:
  Database processes (PostgreSQL, Redis, MySQL) should bind to 127.0.0.1
  or a private subnet IP — NEVER 0.0.0.0 in production.
  "It works" is not the same as "it's secure."
  ss -tlnp shows you exactly which of your services are exposed.
```

```
Part C — Read all socket states in one view

   ss -s        # summary: total, estab, closed, time-wait, syn-recv counts

   ss -antp     # all TCP sockets with process info
                # -a = all states (not just LISTEN)
                # -n = no name resolution (faster, exact port numbers)
                # -t = TCP only
                # -p = show process

States to know:
   LISTEN     = waiting for incoming connections — normal for servers
   ESTABLISHED = active connection in progress — normal
   TIME_WAIT  = our side closed, waiting 2×MSL (60-120s) for delayed packets
                  many TIME_WAIT = missing connection pool (new TCP per request)
   CLOSE_WAIT = remote side closed, WE haven't called close() yet
                  persists indefinitely = FD leak in your application code
   SYN_RECV   = half-open connections (our SYN-ACK sent, client hasn't ACK'd)
                  counts > ~100 = possible SYN flood attack in progress

Kill servers:
   kill $(lsof -t -i:8124) $(lsof -t -i:8125) 2>/dev/null
```

<details>
<summary>Solution / walkthrough</summary>

```bash
# Part A
python3 -m http.server 8123 &

# Linux:
ss -tlnp | grep 8123
# LISTEN 0 5 0.0.0.0:8123 0.0.0.0:* users:(("python3",pid=12345,fd=3))
#         ↑           ↑                              ↑
#      backlog   bind addr               process name, PID, file descriptor

# macOS:
lsof -i :8123
# COMMAND    PID USER   FD   TYPE DEVICE SIZE/OFF NODE NAME
# python3  12345 user    3u  IPv4  ...        0t0  TCP  *:8123 (LISTEN)

ps aux | grep http.server | grep -v grep
# user 12345 0.0 0.1 ... python3 -m http.server 8123
# PID 12345 = same as ss/lsof ✓

nc -zv localhost 8123
# Connection to localhost port 8123 [tcp/*] succeeded!
curl -I http://localhost:8123
# HTTP/1.0 200 OK

kill $(lsof -t -i:8123)     # macOS / portable
# [1]+ Terminated python3 -m http.server 8123

ss -tlnp | grep 8123    # (no output)

# Part B — 0.0.0.0 vs 127.0.0.1
python3 -m http.server 8124 &
python3 -m http.server 8125 --bind 127.0.0.1 &

ss -tlnp | grep -E '812[45]'
# LISTEN 0 5   0.0.0.0:8124  0.0.0.0:*  users:(("python3",...))
# LISTEN 0 5  127.0.0.1:8125  0.0.0.0:*  users:(("python3",...))
#             ^^^^^^^^^
#             this is why 8125 is only reachable from the same machine

# Part C
ss -s
# Total: 247
# TCP:   18 (estab 5, closed 2, orphaned 0, timewait 1)
# ...

ss -antp | head -20
# State     Recv-Q Send-Q Local Address:Port  Peer Address:Port Process
# LISTEN    0      5      0.0.0.0:8124        0.0.0.0:*         ...
# LISTEN    0      5      127.0.0.1:8125      0.0.0.0:*         ...
# ESTABLISHED 0   0       127.0.0.1:8124      127.0.0.1:54321   ("curl",...)
# TIME_WAIT 0     0       127.0.0.1:54321     127.0.0.1:8124    ...

# Clean up
kill $(lsof -t -i:8124) $(lsof -t -i:8125) 2>/dev/null
```

**CLOSE_WAIT in the real world:** If `ss -antp | grep CLOSE_WAIT` shows dozens or hundreds of entries to the same destination, your application is not closing connections properly. Common causes: missing `response.close()` in Python requests, missing `connection.end()` in Node.js, or a connection pool that never returns connections. The fix is in the application code, not the network.
</details>

---

## Lab 3: DNS — Full Investigation

**Objective:** Understand DNS resolution from the ground up — trace a query through root → TLD → authoritative, inspect TTLs, query all record types, and run the debugging workflow used when DNS changes aren't propagating.

**Why this matters:**
```
"I updated the DNS record but the change isn't working" is one of the
most common production confusion points. The answer is always one of:
  1. The TTL on the old record was high — caches still hold it
  2. You updated the wrong zone / nameserver
  3. Your machine's OS resolver is caching — flush it

dig +trace walks you through exactly which nameservers were queried
at each step. It's the definitive "where is DNS resolution going wrong?"
tool.
```

**Task:**

```
Part A — Basic record lookups (learn the output format)

1. A record (IPv4 address):
   dig example.com
   # Read: QUESTION (what you asked), ANSWER (the response),
   # SERVER (which resolver answered), Query time

   dig +short example.com       # just the IP, no noise
   dig +short example.com A     # explicit record type (same result)

2. TTL — how long until caches expire?
   dig example.com | grep -A3 ";; ANSWER"
   # example.com.   86400   IN   A   93.184.216.34
   #               ^^^^^
   #               TTL in seconds (86400s = 24 hours)
   # Run the same command twice 30 seconds apart — TTL decreases each time
   # (your resolver is counting down to expiry)

3. All common record types:
   dig +short MX gmail.com      # mail server priorities + hostnames
   dig +short TXT google.com    # SPF/DKIM/verification records (one per line)
   dig +short AAAA google.com   # IPv6 address (empty if IPv6 not configured)
   dig +short NS example.com    # authoritative nameservers for this domain
   dig +short CNAME www.github.com    # CNAME → points to another name

4. Reverse DNS (PTR record):
   dig -x 8.8.8.8 +short
   # dns.google.
   # Maps an IP address back to a hostname
   # Used by: spam filters (verify the sending IP has a PTR record),
   #          intrusion detection systems, logging enrichment
```

```
Part B — Trace the full recursive resolution (the 7-step walk)

   dig +trace example.com

   This bypasses your OS resolver and queries from scratch:
     1. Queries a root nameserver (one of the 13 root server clusters)
     2. Root delegates to the .com TLD nameserver
     3. TLD nameserver delegates to example.com's authoritative nameserver
     4. Authoritative nameserver answers with the A record

   Read the output top to bottom — each section is one delegation step.
   Identify which nameserver answered the final authoritative response.
   Identify the TTL on each NS delegation vs the final A record.

   Note: TTLs at each delegation level are independent.
   The NS record TTL (usually 86400s) determines how long resolvers
   cache "who is authoritative for this domain."
   The A record TTL determines how long resolvers cache the IP.
   Changing the A record is fast (wait for A record TTL).
   Migrating to a new nameserver requires waiting for NS record TTL.
```

```
Part C — Query a specific resolver (bypass your OS)

# Query Google's public resolver:
   dig @8.8.8.8 example.com

# Query Cloudflare's resolver:
   dig @1.1.1.1 example.com

# Query your local DNS resolver (common in corporate/VPN setups):
   dig @127.0.0.1 example.com
   # or check /etc/resolv.conf for your nameserver IP:
   cat /etc/resolv.conf
   dig @$(grep nameserver /etc/resolv.conf | head -1 | awk '{print $2}') example.com

# When to use this:
# "The app can't resolve db.internal — but my laptop can"
#   → query the same resolver your app would use:
#      dig @10.0.0.2 db.internal    (AWS VPC resolver is always .2 of the VPC CIDR)
# This tells you: is this a resolver configuration problem or a DNS record problem?
```

```
Part D — Observe DNS caching with TTL countdown

   # Pick a domain with a short TTL (try: github.com, aws.amazon.com)
   dig +short +ttl github.com A
   # Some resolver returns TTL on each record in +ttl mode

   # Repeat 3 times, 10 seconds apart, watch TTL decrease
   for i in 1 2 3; do
     echo "=== run $i ===" && dig github.com | grep -A2 ";; ANSWER" && sleep 10
   done

   # What you see: the ANSWER section TTL decreasing with each query
   # This proves your resolver IS caching — it's not re-querying the
   # authoritative nameserver on every lookup.
   # When TTL reaches 0, the resolver discards the cache entry and
   # makes a fresh query.
```

<details>
<summary>Solution / walkthrough</summary>

```bash
# Part A
dig +short example.com
# 93.184.216.34

dig example.com | grep -A3 ";; ANSWER"
# ;; ANSWER SECTION:
# example.com.   86400   IN   A   93.184.216.34
# TTL = 86400 = 24 hours — changes to this record take up to 24h to propagate

dig +short MX gmail.com
# 5 gmail-smtp-in.l.google.com.
# 10 alt1.gmail-smtp-in.l.google.com.
# 20 alt2.gmail-smtp-in.l.google.com.
# ...
# Lower number = higher priority
# Mail servers try lowest-priority MX first

dig +short TXT google.com | head -5
# "v=spf1 include:_spf.google.com ~all"
# "globalsign-smime-dv=CDYX+XFHUw2wml6/Gb8+59BsH31KzUr6c1l2BfEK..."
# SPF record tells receiving mail servers which IPs are allowed to send email
# for google.com — this is how spam filters validate email legitimacy

dig -x 8.8.8.8 +short
# dns.google.
# 8.8.8.8 is Google's DNS — its PTR record maps back to dns.google

# Part B — +trace output (abbreviated)
dig +trace example.com
# .        86400  IN  NS  a.root-servers.net.  ← root nameservers
# .        86400  IN  NS  b.root-servers.net.
# ...
# com.     172800 IN  NS  a.gtld-servers.net.  ← .com TLD delegation
# ...
# example.com.  86400  IN  NS  a.iana-servers.net.  ← authoritative delegation
# example.com.  86400  IN  A   93.184.216.34         ← final answer

# The trace reveals:
# Root → "I don't know example.com, but here's who handles .com"
# .com TLD → "I don't know example.com, but here's its nameserver"
# Authoritative → "Here's the IP for example.com"

# Part C — specific resolvers
dig @8.8.8.8 example.com +short
# 93.184.216.34

dig @1.1.1.1 example.com +short
# 93.184.216.34

# AWS VPC DNS debugging scenario:
# dig @10.0.0.2 db.internal   ← query the VPC resolver directly
# If this works but the app can't resolve db.internal:
#   → the app is using a different resolver (check /etc/resolv.conf in the container)
# If this ALSO fails:
#   → the Route53 private zone is not associated with this VPC

# Part D — TTL countdown
for i in 1 2 3; do
  echo "=== run $i ===" && dig github.com | grep -A2 ";; ANSWER" && sleep 10
done
# === run 1 ===
# github.com.  60   IN  A  140.82.112.4     ← TTL 60s (github uses short TTLs)
# === run 2 ===
# github.com.  50   IN  A  140.82.112.4     ← 10s elapsed, TTL decreased
# === run 3 ===
# github.com.  40   IN  A  140.82.112.4     ← still decreasing
```

**Production scenario:** "I updated an A record but customers still see the old IP." Check:
1. `dig +short example.com` from your machine → which IP?
2. `dig @8.8.8.8 +short example.com` → does Google see the new IP?
3. `dig +trace example.com` → is the authoritative nameserver even returning the new record?

If step 3 shows the new IP, the record is updated — just waiting for TTL expiry. If step 3 shows the old IP, you updated the wrong record or the wrong zone.
</details>

---

## Lab 4: TLS/HTTPS — Certificate and Handshake Deep-Dive

**Objective:** Inspect TLS connections the way a security engineer does — examine the certificate chain, check expiry, identify the TLS version and cipher, and understand exactly what the handshake negotiates.

**Why this matters:**
```
Cert expiry is the #1 cause of avoidable outages. It has taken down
major companies' APIs for hours. The fix is always trivial — renew the cert.
The failure mode is purely: nobody checked.

openssl s_client is the standard tool for:
  - Verifying which cert a host is actually serving (not which you think)
  - Debugging "unknown CA" errors (chain incomplete)
  - Confirming TLS version negotiated (TLS 1.2 vs 1.3)
  - Checking cert expiry remotely (no server access needed)
```

**Task:**

```
Part A — Examine a real TLS connection

1. Connect and dump the full cert chain:
   openssl s_client -connect example.com:443 -servername example.com < /dev/null
   # -connect       = host:port to connect to
   # -servername    = SNI header (tells the server which cert to serve — critical
   #                  when one IP hosts many domains / certs)
   # < /dev/null    = don't wait for stdin, just connect, show cert, exit

   In the output, find:
   - "Certificate chain" section: which certificates are in the chain?
   - "subject" field: which domain is this cert issued for?
   - "issuer" field: which CA signed it?
   - "SSL-Session: Protocol": which TLS version was negotiated?
   - "SSL-Session: Cipher": which cipher suite?

2. Check cert expiry dates (one-liner):
   echo | openssl s_client -connect example.com:443 -servername example.com 2>/dev/null \
     | openssl x509 -noout -dates
   # notBefore=...
   # notAfter=Nov  5 12:00:00 2025 GMT   ← this is what you monitor
   # If "notAfter" is within 30 days → trigger renewal
   # This is exactly what CloudWatch cert-expiry alarms check

3. Trigger a cert error to understand the failure modes:
   # Wrong hostname (SNI mismatch or cert doesn't cover this name):
   curl https://wrong.host.badssl.com 2>&1
   # curl: (60) SSL: certificate subject name 'wrong.host.badssl.com'
   # does not match target host name 'wrong.host.badssl.com'
   # (or similar mismatch error)

   # Expired cert:
   curl https://expired.badssl.com 2>&1
   # curl: (60) SSL certificate problem: certificate has expired

   # Self-signed cert (no chain to a trusted CA):
   curl https://self-signed.badssl.com 2>&1
   # curl: (60) SSL certificate problem: self signed certificate

   # BYPASS (only for debugging — NEVER in production):
   curl -k https://self-signed.badssl.com
   # -k skips ALL certificate validation — you get no security guarantee
```

```
Part B — Measure TLS overhead in the timing breakdown

Run timing against HTTP and HTTPS on the same host (if available) or
compare TLS 1.2 vs TLS 1.3 timing:

   # Full timing breakdown (from Lab 1, but now focus on the TLS line):
   curl -o /dev/null -s -w \
     "dns: %{time_namelookup}s\ntcp: %{time_connect}s\ntls: %{time_appconnect}s\ntotal: %{time_total}s\n" \
     https://example.com

   Calculate TLS overhead:
     TLS handshake time = time_appconnect - time_connect
     Typical TLS 1.3: 50–150ms (1 RTT)
     Typical TLS 1.2: 100–300ms (2 RTT)

   Why TLS 1.3 is faster:
     TLS 1.2: client → server (ClientHello) → client (ServerHello + cert + done)
              → server (ClientKeyExchange + Finished) → server (Finished)
              = 2 round trips before application data can flow
     TLS 1.3: client → server (ClientHello with key share) → client (ServerHello +
              cert + Finished) → server (Finished)
              = 1 round trip
     0-RTT resumption (session tickets): 0 additional RTTs for reconnects
```

```
Part C — Check what TLS exposes vs hides

1. What is visible to a network observer (Wireshark, corporate proxy):
   The SNI (Server Name Indication) in the ClientHello:
   openssl s_client -connect 93.184.216.34:443 -servername example.com \
     -msg 2>&1 | head -30
   # You can see in the TLS record: the hostname "example.com"
   # This is visible even before encryption is established
   # → ISPs and firewalls can see WHICH site you're visiting (not content)
   # → ESNI/ECH (Encrypted Client Hello) in TLS 1.3 is designed to fix this

2. What is NOT visible to a network observer:
   - The specific URL path (/api/orders/42)
   - HTTP headers (including Authorization, Cookie)
   - Request/response body
   - HTTP method (GET, POST, PUT)
   All of the above are encrypted inside the TLS record.
```

<details>
<summary>Solution / walkthrough</summary>

```bash
# Part A — Full chain inspection
echo | openssl s_client -connect example.com:443 -servername example.com 2>/dev/null
# Certificate chain
# 0 s:CN = www.example.org          ← leaf cert (the actual site)
#   i:C = US, O = DigiCert Inc, CN = DigiCert TLS RSA SHA256 2020 CA1
# 1 s:C = US, O = DigiCert Inc, CN = DigiCert TLS RSA SHA256 2020 CA1 ← intermediate CA
#   i:C = US, O = DigiCert Inc, OU = www.digicert.com, CN = DigiCert Global Root CA
# ---
# Server certificate
# subject=CN = www.example.org
# issuer=C = US, O = DigiCert Inc, CN = DigiCert TLS RSA SHA256 2020 CA1
# ---
# SSL-Session:
#     Protocol  : TLSv1.3
#     Cipher    : TLS_AES_256_GCM_SHA384

# Cert expiry (monitoring-style check):
echo | openssl s_client -connect example.com:443 -servername example.com 2>/dev/null \
  | openssl x509 -noout -dates
# notBefore=Nov  5 00:00:00 2024 GMT
# notAfter=Dec  6 23:59:59 2025 GMT
# Run this from a cron job and alert if (notAfter - today) < 30 days

# Days until expiry (one-liner):
echo | openssl s_client -connect example.com:443 -servername example.com 2>/dev/null \
  | openssl x509 -noout -enddate \
  | awk -F= '{print $2}' \
  | xargs -I{} date -d "{}" +%s 2>/dev/null \
  | xargs -I{} bash -c 'echo $(( ({} - $(date +%s)) / 86400 )) days remaining'
# 127 days remaining

# Part B — TLS timing
curl -o /dev/null -s -w \
  "dns: %{time_namelookup}s\ntcp: %{time_connect}s\ntls: %{time_appconnect}s\ntotal: %{time_total}s\n" \
  https://example.com
# dns:  0.005s
# tcp:  0.083s   ← TCP: 78ms
# tls:  0.184s   ← TLS: 101ms (TLS 1.3, 1 RTT = ~1× network RTT)
# total: 0.191s
# TLS overhead = 0.184 - 0.083 = 101ms ≈ exactly 1× the TCP RTT (78ms)
# This confirms TLS 1.3 (1 RTT). TLS 1.2 would be ~2× the TCP RTT.

# Part C — badssl.com test cases
curl https://expired.badssl.com 2>&1 | head -3
# curl: (60) SSL certificate problem: certificate has expired
# More details here: https://curl.se/docs/sslcerts.html

curl https://self-signed.badssl.com 2>&1 | head -3
# curl: (60) SSL certificate problem: self signed certificate

curl -k https://self-signed.badssl.com -o /dev/null -w "%{http_code}\n"
# 200  ← -k bypasses validation, ONLY for debugging, never in production scripts
```

**Production cert monitoring pattern:**
```bash
# Add to a monitoring cron job:
#!/bin/bash
DOMAIN="api.example.com"
EXPIRY=$(echo | openssl s_client -connect ${DOMAIN}:443 -servername ${DOMAIN} 2>/dev/null \
  | openssl x509 -noout -enddate | cut -d= -f2)
DAYS=$(( ($(date -d "$EXPIRY" +%s) - $(date +%s)) / 86400 ))
if [ "$DAYS" -lt 30 ]; then
  echo "ALERT: cert for ${DOMAIN} expires in ${DAYS} days"
fi
```
</details>

---

## Lab 5: SSH Tunneling and the ProxyJump Pattern

**Objective:** Master all three SSH forwarding modes — local port-forward (reaching a DB from your laptop), remote port-forward (exposing your local dev server), and ProxyJump (multi-hop without agent forwarding). Understand the security difference between them.

**Why this matters:**
```
"I need to run a query against production DB but it's in a private subnet"
→ local port-forward via the bastion host

"QA team needs to see my local dev server but I don't have a public IP"
→ remote port-forward (or ngrok, which is the same concept)

"I need to SSH to an internal host via a bastion, without forwarding
my private key to the bastion"
→ ProxyJump (-J) — modern, safe, does NOT expose your key on the bastion

Understanding these prevents the #1 SSH security mistake: using
agent forwarding (-A) because "it lets me hop to the next server"
without knowing that it leaves your private key accessible to root
on the bastion host.
```

**Task:**

```
Part A — Local Port Forward (simulate "reach a private DB from laptop")

1. Simulate a "remote-only" service:
   # In terminal 1 — simulate a DB that only binds to localhost:
   python3 -m http.server 9000 --bind 127.0.0.1 &
   # This is exactly how PostgreSQL is configured in production:
   # it listens on 127.0.0.1:5432, not 0.0.0.0:5432

2. Verify it is NOT reachable via any IP except localhost:
   curl http://127.0.0.1:9000     # works (loopback)
   curl http://$(hostname -I | awk '{print $1}'):9000  # FAILS
   # This simulates: the DB is accessible from the server itself,
   # but NOT from the public internet or your laptop

3. Set up a local port-forward via SSH to the SAME machine (self-loop for lab):
   ssh -L 9001:127.0.0.1:9000 $(whoami)@localhost -N -f
   # -L 9001:127.0.0.1:9000  = map MY local port 9001 to localhost:9000
   #                            on the SSH server (which is also localhost here)
   # -N = don't run a command, just forward
   # -f = fork to background

4. Reach it via the tunnel:
   curl http://127.0.0.1:9001    # this works now — routed through SSH

5. Confirm the tunnel is visible as an SSH process:
   ss -tlnp | grep 9001    # Linux
   lsof -i :9001           # macOS
   # Should show sshd or ssh process listening on 9001

6. Real-world equivalent:
   ssh -L 5433:db.internal:5432 bastion.example.com -N
   # YOUR localhost:5433 → SSH to bastion → bastion connects to db.internal:5432
   # Your DB client connects to localhost:5433 (tunnel entry point)
   # Actual DB packets travel encrypted inside the SSH connection
   # db.internal never needs to be publicly accessible

Kill: kill $(lsof -t -i:9000) $(lsof -t -i:9001) 2>/dev/null
```

```
Part B — ProxyJump (-J) vs agent forwarding (-A): the security difference

ProxyJump (SAFE — use this):
  ssh -J bastion.example.com internal-host.example.com
  # SSH client connects to bastion first, opens a TCP tunnel through bastion
  # to internal-host, then does a SECOND independent SSH handshake to internal-host
  # Your private key is used ONLY on your local machine
  # Even if bastion is compromised, the attacker cannot use your key to SSH further

Agent forwarding (DANGEROUS — avoid):
  ssh -A bastion.example.com
  # ssh-agent socket is forwarded to the bastion
  # root on bastion can use your ssh-agent to sign challenges as you
  # One compromised bastion host = all hosts you can reach = compromised

In ~/.ssh/config (the clean way to do ProxyJump):
  Host internal-host
      Hostname 10.0.10.50
      User ubuntu
      ProxyJump bastion.example.com
      IdentityFile ~/.ssh/my-key.pem

  # Then just: ssh internal-host
  # SSH reads the config, uses bastion as the jump host automatically
```

```
Part C — SSH hardening check

   # See if your SSH server configuration allows password auth (it shouldn't):
   grep -E "^(PasswordAuthentication|PermitRootLogin|Port)" /etc/ssh/sshd_config 2>/dev/null || \
   echo "Not accessible or not running"
   # In production:
   #   PasswordAuthentication no   ← only key-based auth
   #   PermitRootLogin no          ← never allow direct root SSH
   #   Port 22 (or custom)

   # Check what the SSH server fingerprint is (used to verify known_hosts):
   ssh-keyscan localhost 2>/dev/null
   # This is what gets added to ~/.ssh/known_hosts on first connect
   # If this hash changes unexpectedly → MITM attack warning
   # Reset with: ssh-keygen -R hostname
```

<details>
<summary>Solution / walkthrough</summary>

```bash
# Part A
python3 -m http.server 9000 --bind 127.0.0.1 &

# Direct access via loopback works:
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:9000
# 200

# Direct access via LAN IP fails:
MY_IP=$(hostname -I | awk '{print $1}')
curl --connect-timeout 2 http://${MY_IP}:9000
# curl: (7) Failed to connect — as expected, 127.0.0.1 binding blocks this

# Set up tunnel (self-SSH for lab purposes):
ssh -L 9001:127.0.0.1:9000 $(whoami)@localhost -N -f -o StrictHostKeyChecking=accept-new
# first time: accepts the localhost SSH fingerprint into known_hosts

# Reach via tunnel:
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:9001
# 200 — routed through the SSH tunnel to the "private" service

# See the tunnel listener:
ss -tlnp | grep 9001
# LISTEN 0 128 127.0.0.1:9001  0.0.0.0:*  users:(("ssh",...))

# Production equivalent:
# ssh -L 5433:db.internal:5432 ubuntu@bastion.example.com -N -f
# psql -h localhost -p 5433 -U dbuser mydb
# ← your psql thinks it's talking to localhost, but packets go:
#   localhost:5433 → SSH tunnel → bastion.example.com → db.internal:5432

# Cleanup:
kill $(lsof -t -i:9000) $(lsof -t -i:9001) 2>/dev/null

# Part B — ~/.ssh/config for ProxyJump
cat >> ~/.ssh/config << 'EOF'
# Lab entry — ProxyJump demonstration
# Host bastion-demo
#     Hostname your-bastion-ip
#     User ubuntu
#     IdentityFile ~/.ssh/your-key.pem
#
# Host internal-demo
#     Hostname 10.0.10.50
#     User ubuntu
#     IdentityFile ~/.ssh/your-key.pem
#     ProxyJump bastion-demo
EOF
# (commented out — would only work with real hosts)

# Part C
grep -E "^(PasswordAuthentication|PermitRootLogin)" /etc/ssh/sshd_config 2>/dev/null
# PasswordAuthentication no
# PermitRootLogin no

# Your own known_hosts file (showing what SSH trusts):
cat ~/.ssh/known_hosts | head -5
# Each line: hostname/IP fingerprint-type fingerprint
# SSH checks this on every connect — mismatch = MITM warning
```
</details>

---

## Lab 6: Nginx Reverse Proxy — Build It from Scratch

**Objective:** Configure Nginx as a reverse proxy in front of a local Python server. Add X-Forwarded-For, configure a WebSocket proxy, and observe how requests look on the backend with and without proxy headers.

**Why this matters:**
```
Understanding proxy configuration is not optional for backend engineers:
  - "Why does my app log 127.0.0.1 for every request?" → missing proxy headers
  - "WebSocket works locally but disconnects every 60s in production" → missing
    proxy_read_timeout and Upgrade header in the Nginx config
  - "How do I route /api to one service and /admin to another on one port?"
    → Nginx location blocks

You will configure this yourself repeatedly in real projects.
Building it manually once gives you the mental model to debug it quickly.
```

**Prerequisites:**
```
macOS:   brew install nginx     (starts on http://localhost:8080 by default)
Ubuntu:  sudo apt-get install nginx -y   (starts on http://localhost:80 by default)
Docker:  docker run -d -p 8080:80 -v $(pwd)/nginx.conf:/etc/nginx/nginx.conf nginx
```

**Task:**

```
Part A — Start a backend and configure Nginx in front of it

1. Start the backend (simulates your real app):
   python3 -m http.server 5001 &
   # Backend runs on port 5001, NOT exposed to users

2. Find Nginx config location:
   # macOS (Homebrew): /opt/homebrew/etc/nginx/nginx.conf
   # Ubuntu/Debian:    /etc/nginx/nginx.conf  (and /etc/nginx/sites-enabled/)
   # Find it:  nginx -t 2>&1 | head -1
   nginx -t 2>&1 | head -2

3. Create a minimal proxy config (adjust path for your OS):
   # Save as /tmp/lab_nginx.conf (test config, not system config)
   cat > /tmp/lab_nginx.conf << 'EOF'
   events { worker_connections 1024; }
   http {
     server {
       listen 8090;                    # Nginx listens here (user-facing)
       server_name localhost;

       # Pass real client IP to backend
       proxy_set_header X-Real-IP       $remote_addr;
       proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
       proxy_set_header Host            $host;

       location / {
         proxy_pass http://127.0.0.1:5001;    # forward to backend
       }
     }
   }
   EOF

4. Test and start Nginx with this config:
   nginx -t -c /tmp/lab_nginx.conf      # validate config, shows errors
   nginx -c /tmp/lab_nginx.conf          # start with custom config

5. Test it works:
   curl -I http://localhost:8090
   # Expected: HTTP/1.1 200 OK (proxied from the Python server)

6. Observe the headers the backend would see:
   # The Python HTTP server prints request details to its stdout — look there:
   # 127.0.0.1 - - [10/Aug/2026] "GET / HTTP/1.0" 200
   # (the backend sees 127.0.0.1 as source because Nginx is the proxying agent)
   # With X-Forwarded-For, the backend can read the real client IP from that header.
```

```
Part B — Path-based routing (route /api to different backend)

1. Start a second backend on a different port:
   python3 -m http.server 5002 &

2. Update the config with path-based routing:
   cat > /tmp/lab_nginx.conf << 'EOF'
   events { worker_connections 1024; }
   http {
     server {
       listen 8090;
       server_name localhost;

       proxy_set_header X-Real-IP       $remote_addr;
       proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
       proxy_set_header Host            $host;

       location /api/ {
         proxy_pass http://127.0.0.1:5002;    # API backend
       }

       location / {
         proxy_pass http://127.0.0.1:5001;    # main app backend
       }
     }
   }
   EOF
   nginx -s reload -c /tmp/lab_nginx.conf   # reload without downtime

3. Test path routing:
   curl -s -o /dev/null -w "%{http_code}" http://localhost:8090/
   # 200 — served by backend on 5001
   curl -s -o /dev/null -w "%{http_code}" http://localhost:8090/api/
   # 200 — served by backend on 5002
   # Same port (8090), different backends by path — this is L7 routing
```

```
Part C — WebSocket proxy config (why you need special headers)

To proxy WebSocket through Nginx, you MUST add two headers:
   Upgrade: websocket
   Connection: upgrade

Without these, Nginx treats the connection as plain HTTP,
the 101 Switching Protocols handshake fails, and the WebSocket
connection silently falls back to HTTP or errors.

   cat > /tmp/lab_nginx_ws.conf << 'EOF'
   events { worker_connections 1024; }
   http {
     server {
       listen 8091;

       # Regular HTTP
       location /api/ {
         proxy_pass http://127.0.0.1:5001;
         proxy_set_header Host $host;
         proxy_set_header X-Real-IP $remote_addr;
       }

       # WebSocket — requires Upgrade headers + long read timeout
       location /ws/ {
         proxy_pass http://127.0.0.1:5001;
         proxy_http_version 1.1;
         proxy_set_header Upgrade    $http_upgrade;
         proxy_set_header Connection "upgrade";
         proxy_read_timeout 3600s;     # keep alive for 1 hour between messages
         proxy_send_timeout 3600s;     # symmetric
       }
     }
   }
   EOF

   # Key differences between /api/ and /ws/ location blocks:
   # 1. proxy_http_version 1.1  — HTTP/2 doesn't support Upgrade header
   # 2. Upgrade + Connection headers — trigger the 101 handshake
   # 3. proxy_read_timeout 3600s — prevent the 60s idle disconnect
```

```
Part D — Stop everything

   nginx -s stop -c /tmp/lab_nginx.conf  2>/dev/null
   nginx -s stop -c /tmp/lab_nginx_ws.conf  2>/dev/null
   kill $(lsof -t -i:5001) $(lsof -t -i:5002) 2>/dev/null
```

<details>
<summary>Solution / walkthrough</summary>

```bash
# Part A — complete run
python3 -m http.server 5001 &

nginx -t -c /tmp/lab_nginx.conf
# nginx: the configuration file /tmp/lab_nginx.conf syntax is ok
# nginx: configuration file /tmp/lab_nginx.conf test is successful

nginx -c /tmp/lab_nginx.conf

curl -I http://localhost:8090
# HTTP/1.1 200 OK
# Server: SimpleHTTP/0.6 Python/3.11.0   ← confirmed: came from Python backend
# Connection: keep-alive

# Python server terminal shows:
# 127.0.0.1 - - [10/Aug/2026 12:00:00] "GET / HTTP/1.0" 200

# X-Real-IP in the backend:
# The Python http.server doesn't print headers, but in a real Flask/FastAPI app:
#   request.headers.get("X-Real-IP")       # "127.0.0.1" (our client in this lab)
#   request.headers.get("X-Forwarded-For") # "127.0.0.1"

# Part B — path routing
python3 -m http.server 5002 &

nginx -s reload -c /tmp/lab_nginx.conf
curl -v http://localhost:8090/ 2>&1 | grep "< HTTP"
# < HTTP/1.1 200 OK   ← from 5001

curl -v http://localhost:8090/api/ 2>&1 | grep "< HTTP"
# < HTTP/1.1 200 OK   ← from 5002

# Prove they're different backends by stopping one:
kill $(lsof -t -i:5002) 2>/dev/null
curl -s -o /dev/null -w "%{http_code}" http://localhost:8090/api/
# 502  ← "Bad Gateway" — Nginx can reach port 5002, but nothing is there
#         This is exactly the 502 you see in production when a backend crashes

# Part D — cleanup
nginx -s stop -c /tmp/lab_nginx.conf 2>/dev/null
kill $(lsof -t -i:5001) 2>/dev/null
```

**The 502 / 503 / 504 difference in Nginx:**
```
502 Bad Gateway:
  Nginx reached the backend but got garbage back (or nothing at all)
  Cause: backend process not running, or crashed mid-request
  Fix: check if the backend process is running (systemctl status myapp)

503 Service Unavailable:
  Nginx upstream block has no healthy servers
  All backends failed health checks simultaneously
  Fix: check backend health, scale up, or check your health check config

504 Gateway Timeout:
  Nginx reached the backend but it didn't respond within proxy_read_timeout
  Cause: backend is slow (DB query, external API, heavy computation)
  Fix: investigate backend performance, consider raising timeout for specific routes
```
</details>

---

## Lab 7: Subnetting Math + VPC Design — Cold

**Objective:** Do CIDR math without a calculator, then design a production-realistic VPC subnet layout from scratch. These skills are tested in every "design a VPC" interview question and needed before any Terraform/AWS work.

**Why this matters:**
```
"Let's just use the default VPC" — said by engineers who later spend a week
re-IP'ing subnets because:
  1. They ran out of IPs (picked a /28 for a subnet that got 30 ECS tasks)
  2. They tried to peer with a partner VPC and CIDRs overlapped
  3. They put everything in one subnet and now can't use security groups
     to isolate the DB tier from the app tier

Five minutes of CIDR math before creating the VPC saves days of remediation.
```

**Task:**

```
Problem 1 — CIDR fundamentals (no calculator)

For each prefix length, calculate total addresses and usable hosts:
  /24  → 2^(32-24) = 2^8  = 256  total,  254 usable (256 - 2)
  /27  → 2^(32-27) = 2^5  = 32   total,  30  usable
  /20  → 2^(32-20) = 2^12 = 4096 total,  4094 usable
  /28  → 2^(32-28) = 2^4  = 16   total,  14  usable
  /16  → 2^(32-16) = 2^16 = 65536 total, 65534 usable

The formula:  usable = 2^(32 - prefix) - 2
  -2 removes: the network address (first IP) and broadcast address (last IP)

AWS adds 5 reserved addresses per subnet (not 2):
  Network address:    10.0.1.0    (first)
  VPC router:         10.0.1.1    (second)
  AWS DNS:            10.0.1.2    (third)
  AWS reserved:       10.0.1.3    (fourth)
  Broadcast:          10.0.1.255  (last)
  AWS usable formula: 2^(32 - prefix) - 5
```

```
Problem 2 — VPC subnet layout design

You're given 10.20.0.0/16. Design a 3-AZ production layout.

Requirements:
  - 3 Availability Zones (AZ-a, AZ-b, AZ-c)
  - Each AZ needs: 1 public subnet + 1 private app subnet + 1 private DB subnet
  - That's 9 subnets total
  - Leave room for future expansion in the /16
  - DB subnets should be small (3 RDS instances max + headroom)

Step 1 — Choose subnet sizes:
  Public subnets:   /24 (251 AWS-usable IPs — plenty for NAT GW ENIs, LB nodes)
  App subnets:      /20 (4091 AWS-usable IPs — ECS tasks, EC2 workers)
  DB subnets:       /27 (27 AWS-usable IPs — 3 RDS instances + headroom)

Step 2 — Write out the 9 subnet CIDRs (fill in the table):
  AZ-a public:   10.20.0.0/24    usable: 10.20.0.4  - 10.20.0.254
  AZ-b public:   10.20.1.0/24    usable: 10.20.1.4  - 10.20.1.254
  AZ-c public:   10.20.2.0/24    usable: 10.20.2.4  - 10.20.2.254

  AZ-a app:      10.20.16.0/20   usable: 10.20.16.5 - 10.20.31.254
  AZ-b app:      10.20.32.0/20   usable: 10.20.32.5 - 10.20.47.254
  AZ-c app:      10.20.48.0/20   usable: 10.20.48.5 - 10.20.63.254

  AZ-a db:       10.20.64.0/27   usable: 10.20.64.5 - 10.20.64.30
  AZ-b db:       10.20.64.32/27  usable: 10.20.64.37 - 10.20.64.62
  AZ-c db:       10.20.64.64/27  usable: 10.20.64.69 - 10.20.64.94

Verify: no overlaps, all fit within 10.20.0.0/16, room for future subnets.

Step 3 — Route table assignments:
  Public subnets:  route 0.0.0.0/0 → Internet Gateway (IGW)
  App subnets:     route 0.0.0.0/0 → NAT Gateway in same AZ
  DB subnets:      NO default route (DB tier has no internet access at all)
```

```
Problem 3 — VPC peering CIDR overlap diagnosis

A partner company wants to peer their VPC (10.20.0.0/16) with yours
(10.20.0.0/16).

1. Why does AWS reject this peering connection?
2. What would you recommend if the partner insists their app MUST reach
   your DB tier?
3. A second partner has VPC 172.16.0.0/16. Their route tables show a route
   172.16.100.0/24 → pcx-abc. If your app sends a packet to 172.16.100.5:
   a) Which route matches? (longest-prefix match)
   b) If that route is removed, which route would match instead?
   c) What happens to the packet in case (b)?
```

```
Problem 4 — Verify your subnet math with ipcalc (if available)
   sudo apt-get install -y ipcalc 2>/dev/null || brew install ipcalc 2>/dev/null
   ipcalc 10.20.16.0/20
   # Address:   10.20.16.0           00001010.00010100.0001 0000.00000000
   # Netmask:   255.255.240.0 = 20   11111111.11111111.1111 0000.00000000
   # Wildcard:  0.0.15.255
   # Network:   10.20.16.0/20
   # HostMin:   10.20.16.1
   # HostMax:   10.20.31.254
   # Broadcast: 10.20.31.255
   # Hosts/Net: 4094
   # Cross-check your manual calculation against ipcalc — they should match.
```

<details>
<summary>Solution / walkthrough</summary>

```
Problem 3 answers:

1. CIDR overlap — both VPCs use 10.20.0.0/16.
   VPC peering routes traffic based on destination CIDR.
   If both are 10.20.x.x, the route table has an ambiguous entry:
   "10.20.0.0/16 → which VPC?" — AWS cannot resolve this.
   AWS blocks the peering creation entirely when CIDRs overlap.
   Fix: re-IP one VPC to a non-overlapping range BEFORE peering is needed.
   (Re-IP after the fact = recreate subnets + migrate all resources = painful)

2. If both must communicate and CIDRs are identical:
   Option A: Re-IP your partner's VPC to use a different range (10.30.0.0/16).
   Option B: Don't use VPC peering — use an application-layer integration
             instead: REST API calls from one VPC to the other via an NLB,
             AWS PrivateLink, or Transit Gateway with NAT (complex).
   Option C: If you control both VPCs — VPC peering is out, but Transit Gateway
             with DNAT-based NAT translation can work around overlapping CIDRs
             (very advanced, usually not worth it vs re-IP).

3. Longest-prefix match:
   a) Packet to 172.16.100.5:
      Route 172.16.100.0/24 matches (/24 is more specific than /16)
      Longest-prefix match wins → packet routed via pcx-abc (VPC peering)

   b) If 172.16.100.0/24 route is removed:
      Next longest match: 172.16.0.0/16 (the entire VPC CIDR range)
      Packet still routed, but via the /16 route (different target possibly)

   c) If only the default route (0.0.0.0/0 → NAT GW) matches:
      Packet exits via NAT Gateway → public internet → partner's public IP
      This is wrong (should be private peering, not public internet routing)
      → misconfigured route table: missing the more-specific VPC peering route
```

```
Subnetting mental model (no calculator):

Given: "I need 50 hosts in a subnet"
  1. Next power of 2 ≥ 50 + 5 (AWS reserved) = 55 → 2^6 = 64
  2. Prefix = 32 - 6 = /26
  3. Verify: 2^(32-26) - 5 = 64 - 5 = 59 AWS-usable IPs ✓

Given: "I have /20, what's the next contiguous /20 block starting at 10.20.0.0?"
  /20 = 4096 addresses
  10.20.0.0/20    ends at 10.20.15.255 (10.20.0.0 + 4096 - 1)
  Next /20:       10.20.16.0/20 (starts immediately after)
  Then:           10.20.32.0/20
  Pattern: third octet increments by 16 for each /20 block
  (4096 addresses / 256 per third-octet group = 16 third-octet values per /20)
```
</details>

---

## Self-Check Checklist

**Theory file 01 — OSI/TCP-IP fundamentals:**
- [ ] Can you run the triage sequence (dig → ping → nc → curl -w timing) from memory in the right order?
- [ ] Given `curl: (7) Failed to connect` and `curl: (6) Could not resolve host`, which OSI layer does each indicate?
- [ ] Can you explain what "connection refused" vs "connection timed out" tells you about the firewall rule type (REJECT vs DROP)?
- [ ] Can you calculate usable AWS subnet hosts for any prefix (/24, /27, /20, /28) using 2^(32-prefix) - 5?
- [ ] Can you explain longest-prefix match routing with a 3-route example?
- [ ] Can you describe what SNAT does and why the NAT Gateway needs a connection tracking table?

**Theory file 02 — Protocols:**
- [ ] Can you find what's listening on any port and safely identify + kill only that specific process using TWO independent tools?
- [ ] Can you explain the difference between LISTEN, ESTABLISHED, TIME_WAIT, and CLOSE_WAIT socket states?
- [ ] Can you run `dig +trace example.com` and identify which server gave the authoritative answer?
- [ ] Can you query a specific DNS resolver (`dig @10.0.0.2`) and explain when you'd do this in production?
- [ ] Can you check a TLS certificate's expiry date from the command line with `openssl s_client`?
- [ ] Can you set up `ssh -L local_port:remote_host:remote_port jump_host -N` from memory and explain what each field does?
- [ ] Can you explain why `ssh -J` (ProxyJump) is safer than `ssh -A` (agent forwarding)?

**Theory file 03 — Web concepts:**
- [ ] Can you write an Nginx `location /api/` block that proxies to a backend with X-Forwarded-For?
- [ ] Can you write an Nginx `location /ws/` block that correctly handles WebSocket upgrade?
- [ ] Can you explain the difference between Nginx's 502, 503, and 504 responses (different root causes)?
- [ ] Can you explain what `0.0.0.0` vs `127.0.0.1` as a listening bind address means for security?
- [ ] Can you describe the CIDR overlap problem for VPC peering and what AWS does about it?
- [ ] Can you design a 3-AZ VPC subnet layout from a /16 block, choosing appropriate sizes for public/app/DB tiers?

---

## Related Files

- [`01_osi_tcpip_fundamentals.md`](../01_osi_tcpip_fundamentals.md) — Labs 1, 2, 7 draw from this
- [`02_protocols.md`](../02_protocols.md) — Labs 3, 4, 5 draw from this
- [`03_web_concepts.md`](../03_web_concepts.md) — Lab 6 draws from this
- [`../../01_Linux/practical/01_linux_lab.md`](../../01_Linux/practical/01_linux_lab.md) — Labs 4 and 6 build on Linux process/socket skills
- [`../../07_Cloud_AWS/03_networking_dns_lb.md`](../../07_Cloud_AWS/03_networking_dns_lb.md) — Lab 7 VPC design applies directly here