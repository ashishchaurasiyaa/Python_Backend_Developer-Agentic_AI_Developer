# Security — SSH, SSL/TLS Hardening & Secrets Management

**DevOps Track · Phase 14: Security**

> Complementary to the app-level coverage in Backend_Developer/ — this covers the infra/ops angle: hardening, deployment, and operating these systems.

## Quick Concepts

- **SSH (Secure Shell)** = encrypted remote-login protocol; the primary door into every server you manage
- **`sshd_config`** = server-side SSH daemon config (`/etc/ssh/sshd_config`) — where hardening lives
- **Key-pair auth** = public key on server (`~/.ssh/authorized_keys`), private key on your machine — no password sent over the wire
- **fail2ban** = daemon that watches auth logs and bans IPs after N failed login attempts
- **SSL/TLS** = Secure Sockets Layer / Transport Layer Security — encrypts traffic between client and server; "SSL" is the old name, everyone actually means TLS now
- **CA (Certificate Authority)** = trusted third party that signs certificates so clients don't have to trust you blindly
- **Certificate chain** = leaf cert → intermediate CA(s) → root CA — browsers trust the root, so the chain proves your leaf cert is legitimate
- **Let's Encrypt** = free, automated CA — issues short-lived (90-day) certs via ACME protocol
- **`ssh-agent`** = holds a decrypted private key in memory for a session, so you're not re-entering its passphrase on every connection
- **CSR (Certificate Signing Request)** = the public-key + identity file you submit to a CA to get a signed certificate back
- **Self-signed cert** = a cert you sign yourself — fine for internal/dev, browsers will warn on public sites
- **Secrets management** = storing credentials (DB passwords, API keys, tokens) outside of code/config files, with access control and rotation

---

## Why This Matters for a DevOps Engineer

```
App-level security (Backend_Developer/03_Security/) answers:
   "How do I write a secure login endpoint?"

Infra-level security (this file) answers:
   "How do I stop someone from SSHing into the box that runs the login endpoint?"
   "How do I make sure traffic to that endpoint is actually encrypted?"
   "How do I stop the DB password from sitting in plaintext in a git repo?"

If the server is compromised, app-level security is irrelevant —
the attacker already has root and can read every secret, every DB row,
every session key. Infra hardening is the outer wall.
```

Real incidents this section prevents:
- Password-auth SSH brute-forced from a botnet within hours of a box going public (happens constantly — check `journalctl -u sshd` on any freshly launched EC2 instance).
- `.env` file with `AWS_SECRET_ACCESS_KEY` committed to a public GitHub repo, scraped by bots within *minutes*, account used to mine crypto ($10k+ bills are common).
- Internal service-to-service traffic sent over plain HTTP inside a VPC "because it's internal anyway" — then the VPC gets a misconfigured peering connection and that traffic is exposed.

---

## SSH Hardening

### The Default State Is Not Safe

Out of the box, most Linux distros ship `sshd` with:
- Password authentication enabled
- Root login enabled (some distros disable this by default now, but assume it isn't)
- Port 22, the first thing every scanner checks

### Hardened `sshd_config`

```ini
# /etc/ssh/sshd_config

# 1. Key-only auth — the single biggest win
PasswordAuthentication no
PubkeyAuthentication yes
ChallengeResponseAuthentication no
KbdInteractiveAuthentication no

# 2. No root login over SSH — use sudo after logging in as a normal user
PermitRootLogin no

# 3. Change the default port (defense-in-depth, NOT real security —
#    it just gets you off the top of automated scanner lists)
Port 2222

# 4. Restrict which users/groups can SSH in at all
AllowGroups ssh-users
# or: AllowUsers deploy ashish

# 5. Limit auth attempts and login grace time
MaxAuthTries 3
LoginGraceTime 20

# 6. Disable empty passwords, X11 forwarding (unless you need it)
PermitEmptyPasswords no
X11Forwarding no

# 7. Idle session timeout
ClientAliveInterval 300
ClientAliveCountMax 2

# 8. Modern key exchange / cipher algorithms only (drop legacy weak ones)
KexAlgorithms curve25519-sha256,diffie-hellman-group16-sha512
Ciphers chacha20-poly1305@openssh.com,aes256-gcm@openssh.com
MACs hmac-sha2-512-etm@openssh.com,hmac-sha2-256-etm@openssh.com
```

```bash
# Apply and verify before disconnecting (ALWAYS keep a second session open
# when editing sshd_config — a typo can lock you out permanently)
sudo sshd -t                      # test config syntax
sudo systemctl restart sshd
sudo systemctl status sshd

# Generate a strong key pair on your local machine
ssh-keygen -t ed25519 -C "ashish@laptop" -f ~/.ssh/prod_key

# Push public key to server (before disabling password auth!)
ssh-copy-id -i ~/.ssh/prod_key.pub -p 2222 deploy@server
```

### Senior Ordering — Don't Lock Yourself Out

```
1. Add your public key to authorized_keys, test login with key.
2. Confirm key login works (open a SECOND terminal, don't close the first).
3. THEN set PasswordAuthentication no and restart sshd.
4. THEN change the port and update firewall rules.
5. THEN disable root login.

Doing this in the wrong order = permanently locked out of a box
with no console access. Cloud providers offer serial/console access
as an escape hatch (AWS EC2 Instance Connect, GCP serial console) —
know how to use it before you need it.
```

### `ssh-agent` and `ssh-add` — Not Re-Entering Your Passphrase Constantly

A passphrase-protected private key (the correct default, per the Senior Tip below) asks for the passphrase on every single SSH connection unless an agent holds the decrypted key in memory for the session.

```bash
eval "$(ssh-agent -s)"        # start an agent, export SSH_AUTH_SOCK/SSH_AGENT_PID
                                 # into the current shell so ssh/scp/git know to use it
ssh-add ~/.ssh/prod_key          # decrypt the key ONCE (prompts for passphrase),
                                    # hold it in the agent's memory for this session
ssh-add -l                          # list keys currently loaded in the agent
ssh-add -D                            # remove ALL keys from the agent (e.g. before
                                         # locking your machine, or ending a session
                                         # on a shared/untrusted host)
```

```bash
# Agent forwarding — use YOUR local agent's keys from a REMOTE host,
# without ever copying the private key onto that remote host at all
ssh -A deploy@bastion-host
# from bastion-host, ssh to an internal box using YOUR agent-held key:
ssh internal-db-host
```

```
Agent forwarding is genuinely convenient (jump host → internal host,
without staging your private key on the jump host) but is also a real
security tradeoff: if the BASTION host is compromised while your agent
is forwarded to it, an attacker there can use your forwarded agent to
authenticate AS YOU to anything else your key can reach, for as long
as your session is open — they don't get the key file itself, but they
get to USE it. Prefer `ProxyJump`/`ProxyCommand` in `~/.ssh/config`
(covered in `01_Linux/06_networking_commands.md`) over `-A` agent
forwarding when the bastion is a lower-trust environment than the
final destination.
```

### fail2ban — Automated Ban on Brute Force

```bash
sudo apt install fail2ban

# /etc/fail2ban/jail.local
[sshd]
enabled = true
port = 2222
filter = sshd
logpath = /var/log/auth.log
maxretry = 5
bantime = 3600      # 1 hour ban
findtime = 600       # within a 10-min window

sudo systemctl restart fail2ban
sudo fail2ban-client status sshd     # see banned IPs
sudo fail2ban-client set sshd unbanip 1.2.3.4
```

---

## SSL Certificates

### The Chain of Trust

```
Root CA (pre-installed in OS/browser trust store)
   │  signs
   ▼
Intermediate CA
   │  signs
   ▼
Leaf certificate (your domain — example.com)

Browser verifies: leaf signed by intermediate, intermediate signed
by a root it already trusts. If any link breaks (expired, wrong
domain, unknown issuer) → browser shows a warning.
```

### Self-Signed vs Let's Encrypt vs Commercial CA

| | Self-signed | Let's Encrypt | Commercial CA (DigiCert, etc.) |
|---|---|---|---|
| Cost | Free | Free | $$ / year |
| Trusted by browsers | No — manual trust needed | Yes | Yes |
| Validity | You choose | 90 days (auto-renewed) | 1 year typically |
| Use case | Internal tools, dev/staging, mTLS between services | Public-facing production sites | EV/OV certs, enterprise contracts, wildcard at scale |
| Automation | Manual | ACME protocol — fully automatable | Usually manual/API |

```bash
# Self-signed cert (internal service, dev)
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem \
    -days 365 -nodes -subj "/CN=internal.local"

# Let's Encrypt via certbot (most common real-world path)
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d example.com -d www.example.com
# certbot edits nginx config, gets cert, sets up auto-renewal cron/systemd timer

# Verify auto-renewal is wired up
sudo systemctl list-timers | grep certbot
sudo certbot renew --dry-run

# Inspect any cert
openssl x509 -in cert.pem -noout -text
openssl s_client -connect example.com:443 -showcerts
```

### Getting a Cert From a Commercial CA — the CSR Step

Let's Encrypt's ACME protocol (above) automates this entirely, but a commercial CA (needed for EV/OV certs, or specific enterprise contract requirements) still uses the classic manual flow: generate a private key, generate a CSR from it, send the CSR to the CA, receive the signed cert back.

```bash
# 1. Generate a private key (keep this SECRET, never send it anywhere)
openssl genrsa -out example.com.key 2048

# 2. Generate a Certificate Signing Request FROM that key — this is
#    what you actually submit to the CA. It contains your public key
#    and identity info, NOT the private key.
openssl req -new -key example.com.key -out example.com.csr \
  -subj "/CN=example.com/O=My Company/C=IN"

# 3. Inspect the CSR before submitting (catch a typo'd CN before
#    paying for/waiting on a cert with the wrong domain in it)
openssl req -in example.com.csr -noout -text

# 4. Submit example.com.csr to the CA through their portal/API —
#    they return a signed certificate (and usually an intermediate
#    chain file) using the public key embedded in your CSR
```

### Checking Certificate Expiry — Scriptable Monitoring

```bash
# Human-readable expiry date
openssl x509 -in cert.pem -noout -enddate
# notAfter=Oct 23 12:00:00 2026 GMT

# Scriptable — exit code 0 if cert is STILL valid beyond N seconds from now,
# exit code 1 if it expires within that window (or already has)
openssl x509 -in cert.pem -noout -checkend 604800   # 604800s = 7 days
echo $?    # 0 = fine for at least 7 more days, 1 = renew NOW

# Check a LIVE server's cert (not a local file) the same way
echo | openssl s_client -connect example.com:443 2>/dev/null \
  | openssl x509 -noout -enddate
```

```
This -checkend pattern is exactly what a cron job / monitoring check
script wraps to alert BEFORE a cert actually expires — tying back to
the earlier point in this repo that TLS expiry is one of the most
common entirely-self-inflicted outages. Automating renewal (certbot's
own timer, above) removes most of the risk, but an explicit expiry
check as a CloudWatch/Prometheus alert (Phase 11) is the belt-and-
suspenders backstop for the day auto-renewal silently fails for some
unrelated reason (DNS validation broke, rate-limited by the CA, etc.).
```

---

## TLS — What Actually Happens on Connect

### Handshake Overview (TLS 1.2, simplified)

```
Client                                Server
  |--- ClientHello (supported ciphers) ---------->|
  |<-- ServerHello + Certificate + key exchange ---|
  |--- verify cert against CA chain --------------|
  |--- key exchange, derive session key ---------->|
  |<================ encrypted traffic ==========>|
```

TLS 1.3 collapses this to fewer round trips (1-RTT, or 0-RTT for resumed
sessions) and removes support for weak/legacy ciphers entirely — no
renegotiation, no RSA key exchange (forward secrecy is mandatory).

### TLS 1.2 vs TLS 1.3 — What Changed

| | TLS 1.2 | TLS 1.3 |
|---|---|---|
| Handshake round trips | 2-RTT | 1-RTT (0-RTT resume) |
| Weak ciphers (RC4, SHA1, static RSA) | Allowed if configured | Removed entirely |
| Forward secrecy | Optional | Mandatory |
| Handshake speed | Slower | Faster — matters at scale |

```nginx
# nginx: enforce modern TLS only
server {
    listen 443 ssl;
    ssl_certificate     /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
}
```

```bash
# Check what a server actually supports
nmap --script ssl-enum-ciphers -p 443 example.com
curl -sI --tlsv1.3 https://example.com    # force TLS 1.3, see if it connects
```

---

## Secrets Management

### The Failure Mode This Fixes

```
Real incident pattern (happens weekly across the industry):

1. Developer hardcodes DB_PASSWORD=prod_secret_123 in a .env file.
2. .env is gitignored... in the NEW repo. It was committed 8 months
   ago before .gitignore was set up, and it's still in git history.
3. Repo goes public (accidentally, or an intern forks it for a demo).
4. GitHub secret-scanning bots — and attackers running the same scan —
   find it within minutes. git log -p finds it even after a later
   commit "removes" the file, because history still has it.
5. Attacker has prod DB credentials.

Fix is NOT "be more careful" — it's removing the ability for this
class of mistake to happen at all.
```

### The Fix — Centralized Secrets Store

Instead of secrets living in `.env` files or config repos, they live in
a dedicated secrets manager: apps fetch them at runtime via API + IAM
auth, never as plaintext files on disk or in git.

**HashiCorp Vault**
```bash
# Store a secret
vault kv put secret/prod/db password="s3cr3t" username="app"

# App fetches it at startup (via Vault Agent or API + short-lived token)
vault kv get -field=password secret/prod/db

# Dynamic secrets — Vault generates a short-lived DB credential per request,
# auto-revoked after TTL. No standing credential to leak.
vault read database/creds/readonly-role
```

**AWS Secrets Manager**
```bash
aws secretsmanager create-secret --name prod/db/password \
    --secret-string '{"username":"app","password":"s3cr3t"}'

aws secretsmanager get-secret-value --secret-id prod/db/password
```

```python
# App-side: fetch at startup, never commit the value
import boto3, json
client = boto3.client("secretsmanager")
secret = json.loads(client.get_secret_value(SecretId="prod/db/password")["SecretString"])
```

### Practical Rules

```
1. .env files for LOCAL dev only — never committed, always in .gitignore
   from the FIRST commit of the repo.
2. CI/CD secrets injected via the pipeline's own secret store
   (GitHub Actions Secrets, GitLab CI Variables) — never in the yaml itself.
3. Production secrets come from Vault / AWS Secrets Manager / GCP Secret
   Manager, fetched at runtime, never baked into a Docker image.
4. Rotate on any suspected exposure — and periodically regardless
   (Vault dynamic secrets automate this).
5. If a secret DOES leak into git history: rotating it is mandatory.
   Deleting the commit does not un-leak it — assume it's cached/scraped.
```

---

## Senior Tip

```
"We disabled password auth" is not a finished sentence without
"...and we verified key login works from a second session before
restarting sshd, and we have console/serial access as a fallback."

The single most common way junior engineers create a P1 incident
in this domain is applying SSH hardening changes in the wrong order
and locking themselves out of a box with no other access path.
```

## Interview Angle

**Q: Why disable password auth instead of just using a strong password?**
Key-pair auth is immune to brute force and credential stuffing — there's
no password to guess or leak. It also enables clean per-user key rotation
and revocation without changing a shared secret.

**Q: What's the actual security value of changing the SSH port?**
Near zero against a targeted attacker (a port scan finds it in seconds).
Real value: it drops you off the noise floor of dumb automated botnet
scans that only hit port 22, which cuts log noise and low-effort
brute-force attempts. It's defense-in-depth, not a primary control.

**Q: Why is TLS 1.3 preferred over 1.2 at scale?**
Fewer round trips (1-RTT vs 2-RTT) means lower handshake latency —
meaningful at high connection-churn scale (mobile clients, many short
requests). It also removes an entire class of legacy cipher
misconfiguration since weak ciphers aren't negotiable at all.

**Q: Where should a database password live in a production system?**
Not in a `.env` file shipped with the container, not in a config
map in plaintext. In Vault or a cloud secrets manager, fetched by
the app at startup via an IAM role or short-lived token — so the
credential itself is never persisted to disk or version control.

**Q: What's the actual security risk of SSH agent forwarding (`-A`), and when would you avoid it?**
Agent forwarding lets a remote host (a bastion, say) use YOUR local agent's keys to authenticate onward, without ever copying your private key there. The risk: if that intermediate host is compromised while your agent is forwarded to it, an attacker there can use your forwarded agent to authenticate as you to anything else your key can reach, for as long as the session stays open — they don't steal the key file, but they get to use it. Prefer `ProxyJump` in `~/.ssh/config` over agent forwarding when the intermediate host is lower-trust than the final destination.

**Q: How do you get automated alerting before a TLS certificate expires, rather than finding out when the site goes down?**
`openssl x509 -in cert.pem -noout -checkend 604800` returns a non-zero exit code if the cert expires within the given window (604800s = 7 days here) — wrap that in a cron job or a scheduled check feeding a CloudWatch/Prometheus alert. This is the backstop for the day automated renewal (certbot's timer) silently fails for an unrelated reason — DNS validation broke, the CA rate-limited a request, etc.

---

## Related

- [02_owasp_container_k8s_security.md](02_owasp_container_k8s_security.md) — OWASP + container/K8s hardening
- [03_iam_vuln_scanning.md](03_iam_vuln_scanning.md) — IAM, RBAC, image scanning
- [../../Backend_Developer/01_Year3-4_Mid/03_Security/08_secrets_management_advanced.md](../../Backend_Developer/01_Year3-4_Mid/03_Security/08_secrets_management_advanced.md) — app-level secrets patterns
