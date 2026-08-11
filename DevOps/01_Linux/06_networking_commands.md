# Networking Commands

**DevOps Track · Phase 1: Linux**

## Quick Concepts

| Concept | One-line definition |
|------------------------------------|----------------------------------------------------------------------|
| **ping** | ICMP echo — tests basic reachability, NOT application health |
| **curl/wget** | HTTP(S) clients — curl for scripting/debugging, wget for downloads |
| **ssh** | Encrypted remote shell + tunneling protocol |
| **scp/rsync** | File transfer over SSH — rsync is smarter (delta, resumable) |
| **socket** | An (IP, port) endpoint a process binds to or connects from |
| **listening vs established** | Waiting for connections vs actively talking to a peer |

---

## Quick Concepts — In Depth

### Socket — What It Actually Is

```
A socket is an (IP address, port number) pair.
It's the OS abstraction that lets two processes communicate over a network.

Two states:
  LISTENING    → process called bind() + listen() on a port, waiting for connections
  ESTABLISHED  → full TCP connection exists between two endpoints

When you run ss -tlnp:
  LISTEN  0  128  0.0.0.0:8080  0.0.0.0:*  → process waiting on port 8080
  ESTAB   0  0    10.0.1.5:8080  10.0.1.10:51234 → active connection from a client
```

### TCP Lifecycle (the mental model behind all socket debugging)

```
SYN →                  (client initiates)
     ← SYN-ACK         (server acknowledges)
ACK →                  (3-way handshake complete → ESTABLISHED)
... data flows ...
FIN → / ← FIN          (graceful close)
                        → TIME_WAIT (short wait before port reuse)
```

---

## Why This Matters for Backend/DevOps Work

```
- "Is the server even reachable" triage during an incident
- Testing an API endpoint from the CLI before writing client code
- Copying files/deploying artifacts to a remote server
- Finding what's bound to a port before starting a service
- SSH tunnels to access private VPC databases from your laptop
- Setting up key-based auth so CI/CD can deploy without a password
```

---

## ping — Reachability

```bash
ping example.com              # continuous, Ctrl+C to stop
ping -c 4 example.com          # exactly 4 packets then stop
ping -i 0.5 example.com         # interval between packets
ping -s 1472 example.com         # test MTU — 1472 + 28 IP/ICMP headers = 1500 bytes (Ethernet MTU)
ping -W 1 example.com             # 1 second timeout per packet (useful in scripts)
```

### What ping tests and what it does NOT

```
ping tests: kernel-to-kernel ICMP reachability (routing, ICMP-level firewall)

ping does NOT test:
  - Whether your application process is running
  - Whether the port is open (could be firewalled at the app port)
  - Whether the app returns correct responses
  - TLS certificate validity
  - DNS resolution for app hostnames

A server can:
  - Respond to ping AND have the app process crashed
  - Respond to ping AND have port 8080 firewalled
  - Not respond to ping AND have the app working perfectly (ICMP blocked)

NEVER use "ping works" as confirmation an incident is resolved.
Use curl http://host/health — that tests DNS, routing, port, app layer.
```

```bash
# In scripts: check host reachability before attempting SSH
if ping -c 1 -W 2 "$HOST" > /dev/null 2>&1; then
    echo "Host reachable"
else
    echo "Unreachable — check routing/firewall"
fi
```

---

## curl — HTTP Client / Debugging

```bash
curl https://api.example.com/health              # GET, print body
curl -I https://example.com                       # HEAD only — headers, no body
curl -v https://example.com                        # verbose: full request + response + TLS handshake
curl -s -o /dev/null -w "%{http_code}\n" URL        # status code only, silent otherwise

curl -X POST https://api.example.com/users \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer $TOKEN" \
     -d '{"name":"alice","email":"alice@example.com"}'

curl -o file.zip https://example.com/file.zip        # save to named file
curl -O https://example.com/file.zip                  # save using remote filename
curl --retry 3 --retry-delay 2 https://flaky.example.com  # retry on failure
```

### Key Flags Decoded

```bash
curl -s            # silent: no progress bar, no error messages to stderr
curl -S             # show errors even with -s (use -sS together)
curl -f              # fail on HTTP errors: exit code 22 on 4xx/5xx
                      # without -f: curl exits 0 even on 404/500
curl -sf URL           # silent + fail = "succeed only on HTTP 2xx" — use in health checks
curl -L                 # follow redirects (off by default)
curl -k                  # skip TLS cert verification (NEVER in production)
curl --max-time 10        # total request timeout in seconds
curl --connect-timeout 5   # connection phase timeout only
```

### curl Timing Breakdown — Diagnose Slow Requests

```bash
cat > /tmp/curl-format.txt << 'EOF'
  dns_lookup:      %{time_namelookup}s
  tcp_connect:     %{time_connect}s
  tls_handshake:   %{time_appconnect}s
  ttfb:            %{time_starttransfer}s
  total:           %{time_total}s
  http_code:       %{http_code}
EOF

curl -w "@/tmp/curl-format.txt" -o /dev/null -s https://api.example.com/health
# dns_lookup:      0.003s
# tcp_connect:     0.045s
# tls_handshake:   0.142s   ← high? cert chain issue or slow OCSP
# ttfb:            0.312s    ← high? app is slow to respond (database query?)
# total:           0.315s

# TTFB (time to first byte) = pure application latency
# TLS handshake high → cert chain problem or CA OCSP check slow
# TCP connect high  → network routing issue or server overloaded
```

### Health Check Patterns

```bash
# Wait for app to start (deploy script):
until curl -sf http://localhost:8000/health > /dev/null; do
    echo "waiting for app..."
    sleep 2
done
echo "app is up"

# Status code check:
STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://api.example.com/health)
[ "$STATUS" -eq 200 ] && echo "OK" || echo "FAILED: $STATUS"

# Parse JSON response:
curl -sf https://api.example.com/health \
  | python3 -c "import json,sys; d=json.load(sys.stdin); sys.exit(0 if d['status']=='ok' else 1)"
```

### Debugging Authentication

```bash
curl -u username:password https://api.example.com/protected   # basic auth
curl -H "Authorization: Bearer $JWT_TOKEN" https://api.example.com/protected  # bearer
curl -b "session=abc123" https://api.example.com/profile       # cookie

# Save and reuse cookies (simulate a browser login session):
curl -c /tmp/cookies.txt -b /tmp/cookies.txt \
     -X POST -d "user=alice&pass=secret" https://example.com/login
curl -c /tmp/cookies.txt -b /tmp/cookies.txt https://example.com/dashboard
```

---

## wget — Downloading

```bash
wget https://example.com/file.tar.gz              # download, original filename
wget -O out.tar.gz https://example.com/file         # save with specific name
wget -c https://example.com/bigfile.iso               # resume a partial download
wget --limit-rate=200k https://example.com/file         # throttle bandwidth
```

```
curl vs wget:
  curl — better for scripting API calls, full HTTP verb control, piping output
  wget — better for straightforward file/recursive downloads, resume (-c)
```

---

## ssh — Remote Shell

```bash
ssh user@host                           # connect
ssh -p 2222 user@host                    # custom port
ssh -i ~/.ssh/prod_key user@host          # specific private key
ssh -v user@host                           # verbose — debug connection (-vvv for max)

ssh user@host 'tail -100 /var/log/app.log'  # run one remote command, then exit
ssh user@host 'systemctl status myapp'
```

### SSH Authentication Flow

```
1. TCP connect to port 22
2. Key exchange → agree on ciphers
3. Server sends its host key fingerprint
4. Client checks ~/.ssh/known_hosts:
     Found + matches → proceed
     Found + changed → WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED
     Not found       → prompt user to accept (adds to known_hosts on yes)
5. Authentication:
     Public key: client signs a challenge with private key → server verifies
     Password:   client sends encrypted password → server checks /etc/shadow
6. Shell session opens
```

### SSH Key Setup

```bash
# 1. Generate keypair (on your machine)
ssh-keygen -t ed25519 -C "you@example.com"
# Creates: ~/.ssh/id_ed25519 (private, chmod 600) and ~/.ssh/id_ed25519.pub (public)

# 2. Copy public key to server
ssh-copy-id user@host
# OR manually:
cat ~/.ssh/id_ed25519.pub | ssh user@host \
  'mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys'

# 3. Test — should log in with NO password
ssh user@host

# 4. Harden sshd once key auth is confirmed:
sudo vim /etc/ssh/sshd_config
# PasswordAuthentication no    ← no brute-force possible
# PermitRootLogin no            ← root only via sudo from normal user
# MaxAuthTries 3
# AllowUsers deploy

sudo sshd -t                  # syntax check BEFORE applying
sudo systemctl reload sshd    # reload, not restart — existing sessions survive
```

### Port Forwarding

```bash
# LOCAL forward — reach a private VPC resource from your laptop
ssh -L 5433:db.internal:5432 bastion-host
# laptop:5433 → SSH tunnel → bastion → db.internal:5432
# Usage: psql -h localhost -p 5433  (actually hits the private DB)

# REVERSE tunnel — expose your local service to a remote server
ssh -R 8080:localhost:3000 remote-host
# remote-host:8080 → SSH tunnel → your laptop:3000
# Usage: webhook testing, client demos of local dev

# DYNAMIC SOCKS5 proxy — route all traffic through SSH
ssh -D 1080 jump-host
# Configure browser SOCKS5 proxy: localhost:1080
# All browser traffic routes through jump-host
```

### `~/.ssh/config` — Professional Multi-Server Management

```
Host prod-web
    HostName 10.0.1.5
    User deploy
    IdentityFile ~/.ssh/prod_key
    Port 22

Host prod-db
    HostName 10.0.2.10
    User deploy
    IdentityFile ~/.ssh/prod_key
    ProxyJump prod-web          # SSH through prod-web to reach prod-db automatically

Host staging
    HostName staging.example.com
    User deploy
    IdentityFile ~/.ssh/staging_key

# Usage:
# ssh prod-web    → direct
# ssh prod-db     → auto-hops through prod-web
# ssh staging     → uses staging key
```

### `known_hosts` — Avoiding the MITM Footgun

```bash
# First connect: server fingerprint shown, user prompted to accept
# Typing yes → adds to ~/.ssh/known_hosts

# If server's key changes (server rebuilt, or MITM):
# WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!
# → INVESTIGATE before typing yes
#   Legitimate: server was rebuilt → remove old entry:
ssh-keygen -R hostname-or-ip
#   Then reconnect and accept the new key.
#   Suspicious: unexpected change on a network you don't control → treat as MITM.

# CI/CD: suppress strict checking for ephemeral hosts (fresh EC2):
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null user@host
# Only in controlled environments — this disables MITM protection
```

---

## scp / rsync — File Transfer

```bash
scp local.txt user@host:/tmp/              # upload
scp user@host:/tmp/remote.txt ./            # download
scp -r ./dir user@host:/tmp/                 # recursive
scp -P 2222 file user@host:/tmp/              # custom port (capital -P for scp)

rsync -avz local/ user@host:/remote/          # standard combo: archive, verbose, compress
rsync -avz --delete local/ user@host:/remote/  # mirror (delete extra files on remote)
rsync -avz --dry-run local/ user@host:/remote/   # PREVIEW — no changes made
rsync -avzP local/ user@host:/remote/              # + progress bar, resume partial
rsync -e "ssh -p 2222" -avz local/ user@host:/remote/  # custom SSH port
rsync -avz --exclude='.git' --exclude='node_modules' src/ user@host:/deploy/
```

**The trailing slash trap:**

```bash
rsync src/  user@host:/dst/   # copies CONTENTS of src/ into /dst/
rsync src   user@host:/dst/   # copies src DIR ITSELF → /dst/src/
# Always --dry-run before --delete to verify the slash is correct
```

**rsync for incremental backups (hardlink-based):**

```bash
# Each day = full snapshot but only changed files take extra disk space
rsync -avz --link-dest=/backup/yesterday /data/ /backup/today/
# Changed files → new copy
# Unchanged files → hardlink to yesterday's version (no extra space)
```

```
scp vs rsync:
  scp    — copies everything every time, simple, fine for small one-off transfers
  rsync  — delta-transfer (only changed bytes), resumable, can mirror with --delete
           correct choice for: deploys, backups, large dirs, repeated syncs
```

---

## traceroute / mtr — Network Path Debugging

```bash
traceroute example.com             # hop-by-hop path
traceroute -I example.com           # ICMP mode (better through some firewalls)
traceroute -T -p 443 example.com     # TCP mode on port 443 (test real app path)

mtr example.com                      # live: traceroute + continuous ping stats
mtr -n example.com                    # no DNS lookups (faster)
mtr --report -n -c 100 example.com     # 100-packet report — share with network team
```

**Reading the output:**

```
traceroute:
  1  10.0.0.1     0.4 ms   (your router)
  2  203.0.113.1  3.2 ms   (ISP gateway)
  3  * * *                  (router blocks ICMP probes — normal, not a problem)
  4  198.51.100.2  45.1 ms  (backbone)
  5  example.com   48.2 ms  (destination)

High latency jump at hop N → bottleneck between hop N-1 and N
All hops fine but destination slow → app-level issue, not network
* * * = ICMP TTL-exceeded blocked at that router (not an outage)

mtr adds packet loss % per hop:
  203.0.113.1   10% loss → potential ISP issue
  If ALL hops after N show loss → problem IS at hop N (backpressure)
  If only hop N shows loss → that router deprioritizes ICMP (not real loss)
```

---

## netcat (nc) — TCP Swiss Army Knife

```bash
nc -zv host 5432          # test if port is open (zero I/O, verbose)
nc -zv host 5432 2>&1 | grep -q "succeeded" && echo "open" || echo "closed"

# Manual HTTP request (for hosts without curl):
printf "GET / HTTP/1.0\r\nHost: example.com\r\n\r\n" | nc example.com 80

# Pure bash port test (no extra tools — works inside minimal containers):
echo > /dev/tcp/host/5432 2>/dev/null && echo "port open" || echo "port closed"
```

---

## ss — Socket Statistics

```bash
ss -tlnp          # TCP, Listening, Numeric ports, show Process — daily go-to
ss -tnp            # all TCP connections (not just listening) + process
ss -ulnp            # UDP listening sockets
ss -s               # summary: total sockets by state
ss -tn 'state established'    # filter by state
ss -tn 'dport = :443'          # filter by destination port
ss -tn 'sport = :5432'          # filter by source port

# Count connections per remote IP (detect connection floods):
ss -tn state established | awk '{print $5}' | cut -d: -f1 | sort | uniq -c | sort -rn
```

**Socket states decoded:**

```
LISTEN       Waiting for connections (server, bound port)
ESTABLISHED  Full connection open (data flowing)
TIME_WAIT    Connection closed, waiting ~60s before port reuse — normal
             Many TIME_WAIT = high connection turnover (HTTP without keep-alive)
CLOSE_WAIT   Remote closed, we haven't closed yet
             Many CLOSE_WAIT = app not calling close() after EOF → file descriptor leak
SYN_SENT     We initiated, waiting for SYN-ACK
SYN_RECV     Got SYN, sent SYN-ACK, waiting for ACK
             Many SYN_RECV = SYN flood attack in progress
```

---

## lsof — Network File Descriptors

```bash
lsof -i :8080                # what process is on port 8080
lsof -i tcp                   # all TCP connections
lsof -i :8080 -sTCP:LISTEN     # LISTENING socket only (not established connections)
lsof -i TCP -sTCP:ESTABLISHED   # all established connections
lsof -u deploy                   # all open files/sockets for user deploy
lsof -p 1234                      # all open files/sockets for PID 1234
```

---

## Senior Walkthrough: Network Incident Response

### "App is down — network or app issue?"

```bash
# 1. Can we reach the host at all?
ping -c 4 server-ip

# 2. Is the port open?
nc -zv server-ip 8080

# 3. Does the app respond to HTTP?
curl -sv http://server-ip:8080/health
# -s = silent (clean output), -v = show headers and TLS

# 4. TLS cert problem?
curl -sv https://server-ip:8080/health 2>&1 | grep -E "TLS|SSL|certificate|expire"

# 5. DNS resolution issue? (common in microservices)
nslookup service-name.internal
dig service-name.internal +short
```

### "Connection refused" vs "Connection timed out"

```
Connection refused:
  → Port is NOT open
  → Process isn't running, or bound to a different interface (127.0.0.1 not 0.0.0.0)
  → RST packet returned immediately

Connection timed out:
  → Host/port is reachable but packets are being dropped (no RST)
  → Firewall blocking (security group, iptables)
  → Routing issue
  → Host is down

On EC2: "timed out" → check security group inbound rules first.
On a VM: "timed out" → check iptables / firewall rules.
These two errors need completely different fixes.
```

### What's Listening on Port 8080?

```bash
ss -tlnp | grep :8080
# LISTEN  0  128  0.0.0.0:8080  0.0.0.0:*  users:(("gunicorn",pid=4521,fd=5))

lsof -i :8080
# COMMAND   PID   USER  FD  TYPE  DEVICE  SIZE  NODE  NAME
# gunicorn 4521  deploy  5u  IPv4  81234   0t0   TCP   *:8080 (LISTEN)

# Kill it:
kill 4521
# or one-liner:
kill $(lsof -t -i:8080)
```

---

## Senior Tips

```
1. Prefer ss over netstat — faster, always installed on modern distros.
2. curl -I for quick health check; curl -v when you need full TLS details.
3. Always rsync --dry-run before --delete — a trailing slash typo can
   wipe the wrong directory.
4. Disable SSH password auth once key auth is confirmed — password auth
   is the #1 brute-force target on any internet-facing server.
5. Bind internal services to 127.0.0.1, not 0.0.0.0 — a DB listening
   on 0.0.0.0 is reachable by anyone who can reach the host's IP.
```

---

## Interview Angle

**Q: Why doesn't a successful `ping` guarantee your app is healthy?**

```
ping tests ICMP reachability — handled entirely by the kernel.
It says nothing about:
  - Whether your application process is running
  - Whether the port is open or accepting connections
  - Whether the app returns correct HTTP responses
  - TLS cert validity

A server can respond to ping while the app process is completely crashed.
Real health check: curl -sf https://hostname/health
  → tests DNS, routing, port, TLS, and application response layer.
```

**Q: `scp` vs `rsync` for deploying a large directory repeatedly?**

```
rsync:
  - Transfers only CHANGED bytes (delta algorithm) — huge speed difference
  - Can resume interrupted transfers
  - Mirrors exactly with --delete
  - Skips files with --exclude

scp re-copies everything every run regardless of what changed.

Use rsync for: deploys, backups, large directories, anything repeated.
Use scp for: quick one-off file copy.
```

**Q: How would you securely access a private VPC database from your laptop?**

```
SSH local port forwarding:
  ssh -L 5433:db.internal:5432 bastion-host

Now: psql -h localhost -p 5433 → actually hits db.internal:5432

The DB only sees connections from bastion-host (private IP).
No DB port is exposed to the internet.
No VPN needed — the SSH connection IS the secure tunnel.
```

**Q: `ss -tlnp` shows `0.0.0.0:8080` vs `127.0.0.1:8080` — what's the difference?**

```
0.0.0.0:8080   → listening on ALL interfaces
                → accessible from anywhere that can route to this host on port 8080

127.0.0.1:8080 → listening on loopback only
                → accessible ONLY from processes on the same machine
                → NOT reachable from outside even if the firewall allows 8080

Security implication:
  Internal services (Redis, Postgres) should bind to 127.0.0.1.
  Binding to 0.0.0.0 exposes them to anyone who can reach the host.
```

**Q: How do you find and kill whatever is holding a port before starting your service?**

```bash
ss -tlnp | grep :<port>    # get PID from the users column
lsof -i :<port>             # alternative, more detail
kill <pid>                   # SIGTERM first
sleep 5
kill -0 <pid> 2>/dev/null && kill -9 <pid>   # force only if still alive

# One-liner:
kill $(lsof -t -i:<port>)
```