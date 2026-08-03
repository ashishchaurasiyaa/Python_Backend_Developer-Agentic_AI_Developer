# Networking Commands

**DevOps Track · Phase 1: Linux**

## Quick Concepts

- **ping** = ICMP echo request — tests basic reachability, not application-level health
- **curl/wget** = HTTP(S) clients — curl for scripting/debugging requests, wget for downloading
- **ssh** = encrypted remote shell / tunnel protocol
- **scp/rsync** = file transfer over SSH — rsync is smarter (delta transfer, resumable)
- **socket** = an (IP, port) endpoint a process binds to or connects from
- **listening vs established** = a socket waiting for connections vs one already talking to a peer

---

## Why This Matters for Backend/DevOps Work

```
- "Is the server even reachable" triage during an incident
- Testing an API endpoint from the CLI before writing client code
- Copying files/deploying artifacts to a remote server
- Finding what's bound to a port before starting a service that needs it
- Setting up SSH key auth so CI/CD can deploy without a password prompt
```

---

## ping — Reachability

```bash
ping example.com                # continuous, Ctrl+C to stop
ping -c 4 example.com             # send exactly 4 packets then stop
ping -i 0.2 example.com             # interval between packets (root needed for <0.2s)
ping -s 1000 example.com              # packet size (test MTU issues)
```

```
ping only proves ICMP reachability — an app can be fully down (port
closed, process crashed) while ping still succeeds, since ICMP is
handled by the kernel, not your application. Never treat "ping works"
as "the service is healthy."
```

---

## curl — HTTP Client / Debugging

```bash
curl https://api.example.com/health          # GET, print body
curl -I https://example.com                    # HEAD only — headers, no body (fast health check)
curl -v https://example.com                      # verbose — full request/response + TLS handshake
curl -s -o /dev/null -w "%{http_code}\n" URL       # just the status code, silent otherwise

curl -X POST https://api.example.com/users \        # method
     -H "Content-Type: application/json" \           # header
     -d '{"name":"alice"}'                             # body

curl -u user:pass https://api.example.com               # basic auth
curl -H "Authorization: Bearer $TOKEN" https://api...     # bearer token

curl -o file.zip https://example.com/file.zip               # save to a named file
curl -O https://example.com/file.zip                          # save using remote filename

curl --retry 3 --retry-delay 2 https://flaky.example.com        # retry on failure
curl -w "@curl-format.txt" -o /dev/null -s https://example.com    # detailed timing breakdown
```

```bash
# Practical: quick health check loop for a deploy script
until curl -sf http://localhost:8000/health > /dev/null; do
  echo "waiting for app..."
  sleep 2
done
echo "app is up"
```

---

## wget — Downloading

```bash
wget https://example.com/file.tar.gz              # download, keep original filename
wget -O out.tar.gz https://example.com/file          # save with a specific name
wget -c https://example.com/bigfile.iso                # resume a partial download
wget -r -np -k https://example.com/docs/                 # mirror a site (recursive, no parent, fix links)
wget --limit-rate=200k https://example.com/file             # throttle bandwidth
```

```
curl vs wget:
  curl — better for scripting API calls, full HTTP verb control, piping
  wget — better for straightforward file/recursive downloads, resumes
         a broken download by default with -c
```

---

## ssh — Remote Shell

```bash
ssh user@host                        # connect
ssh -p 2222 user@host                  # custom port
ssh -i ~/.ssh/prod_key user@host         # specific private key
ssh -v user@host                           # verbose, debug connection issues (-vvv for max)

ssh user@host 'tail -100 /var/log/app.log'   # run one remote command, then exit
ssh user@host 'systemctl status myapp'         # remote status check

ssh -L 5433:db.internal:5432 jump-host           # local port-forward — reach a remote-only DB locally
ssh -R 8080:localhost:3000 remote-host             # reverse tunnel — expose local service to remote
ssh -D 1080 user@host                                # SOCKS5 dynamic proxy
```

### SSH Key-Based Auth Setup

```bash
# 1. Generate a keypair (on your machine)
ssh-keygen -t ed25519 -C "you@example.com"
# creates ~/.ssh/id_ed25519 (private, chmod 600) and id_ed25519.pub (public)

# 2. Copy the public key to the server
ssh-copy-id user@host
# OR manually:
cat ~/.ssh/id_ed25519.pub | ssh user@host 'mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys'

# 3. Test
ssh user@host                     # should log in with NO password prompt

# 4. Harden the server (once key auth works)
sudo sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo sed -i 's/PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
sudo systemctl restart sshd
```

### `~/.ssh/config` — Shortcuts

```
Host prod
    HostName 1.2.3.4
    User deploy
    Port 22
    IdentityFile ~/.ssh/prod_key

Host staging
    HostName staging.example.com
    User deploy

# Now:  ssh prod   →  connects using all settings above
```

---

## scp / rsync — File Transfer

```bash
scp local.txt user@host:/tmp/                   # upload
scp user@host:/tmp/remote.txt ./                  # download
scp -r ./dir user@host:/tmp/                        # recursive (directory)
scp -P 2222 file user@host:/tmp/                      # custom port (capital -P for scp)

rsync -avz local/ user@host:/remote/                    # archive, verbose, compress — the standard combo
rsync -avz --delete local/ user@host:/remote/             # mirror EXACTLY (deletes extra files on remote)
rsync -avz --dry-run local/ user@host:/remote/               # preview what WOULD happen, no changes
rsync -avzP local/ user@host:/remote/                          # + progress bar, resumable partial transfers
rsync -e "ssh -p 2222" -avz local/ user@host:/remote/            # custom SSH port
```

```
scp vs rsync:
  scp    — simple, copies everything every time, fine for small one-off transfers
  rsync  — delta-transfer (only sends CHANGED bytes), resumable, can mirror/delete,
           the correct choice for backups, large directories, repeated syncs
```

---

## traceroute / mtr — Path Diagnostics

```bash
traceroute example.com          # hop-by-hop path to a host
traceroute -I example.com         # use ICMP instead of UDP (some networks block UDP probes)
mtr example.com                     # continuous traceroute + ping stats combined (best for live diagnosis)
```

---

## telnet — Legacy Port Test

```bash
telnet host 5432                  # attempt raw TCP connect — useful ONLY to test "is this port open"
# Ctrl+] then 'quit' to exit

# Modern replacement:
nc -zv host 5432                    # netcat, zero-I/O mode, verbose — cleaner port test
```

---

## netstat / ss — Socket Inspection

```bash
ss -tlnp                    # TCP, Listening, Numeric ports, show Process — daily go-to
ss -tnp                       # all TCP connections (not just listening) + process
ss -unlp                        # UDP listening sockets
ss -s                             # summary stats
ss -tn 'state established'          # only established TCP connections
ss -tn 'sport = :5432'                # connections on a specific source port

netstat -tlnp                           # older equivalent of `ss -tlnp` (may need net-tools installed)
netstat -rn                               # routing table
```

```
netstat is considered legacy — ss (from iproute2) is faster and is
what modern distros ship by default. Know both; use ss.
```

---

## lsof — List Open Files (Including Sockets)

```bash
lsof -i :8080                    # what's using port 8080
lsof -i tcp                        # all TCP connections
lsof -u deploy                       # all open files/sockets owned by user deploy
lsof -p 1234                           # all open files for a specific PID
lsof +D /var/log                         # everything open under a directory
```

---

## Senior Walkthrough: "What's Listening on Port 8080?"

```bash
# Fast path
ss -tlnp | grep :8080
# LISTEN  0  128  0.0.0.0:8080  0.0.0.0:*  users:(("python3",pid=4521,fd=3))

# Alternative
lsof -i :8080
# COMMAND  PID   USER   FD   TYPE DEVICE SIZE/OFF NODE NAME
# python3 4521 deploy    3u  IPv4  81234      0t0  TCP *:8080 (LISTEN)

# Now you have the PID — inspect or kill it
cat /proc/4521/cmdline
kill 4521
```

---

## Senior Tip

```
1. Prefer ss over netstat — it's what's actually installed/maintained
   on modern distros, and it's faster on hosts with many connections.
2. curl -I for a quick health check; curl -v when you need to see the
   full TLS handshake or exact headers for debugging.
3. rsync -avz --dry-run before any --delete rsync in production — a
   typo'd trailing slash can wipe the wrong directory.
4. Disable SSH password auth once key-based auth is confirmed working
   — password auth is the #1 brute-force target on any internet-facing box.
```

## Interview Angle

**Q: Why doesn't a successful `ping` guarantee your app is healthy?**
ICMP is handled entirely in the kernel — it says nothing about whether your application process is running, whether it's accepting connections, or whether it can serve a correct response. Always health-check at the application layer (`curl /health`) too.

**Q: `scp` vs `rsync` for deploying a large directory repeatedly?**
`rsync` — it transfers only the changed bytes (delta-transfer), can resume interrupted transfers, and can mirror a directory exactly with `--delete`. `scp` re-copies everything every run.

**Q: How do you find and kill whatever's holding a port before starting your service?**
`ss -tlnp | grep :<port>` or `lsof -i :<port>` to get the PID, then `kill <pid>` (SIGTERM first, `-9` only if it doesn't respond).
