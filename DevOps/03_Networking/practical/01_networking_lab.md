# Networking — Hands-On Lab
**DevOps Track · Phase 3 Practical**

## Prerequisites

- A terminal with `curl`, `dig` (or `nslookup`), `ping`, and ideally `ss`/`netstat`/`nc`/`traceroute` (Linux/WSL2 has all of these; macOS has most, `ss` is Linux-only — use `netstat` or `lsof -i` as the substitute, called out inline).
- No cloud account required for Labs 1-3. Lab 4 (subnetting) is pure paper/math, no tools needed at all beyond a terminal to double check with `ipcalc` if you have it (`sudo apt install ipcalc` on Ubuntu, or just verify by hand).
- Optional: a free container/VM (Docker Desktop or a Killercoda/Play with Docker sandbox) if you want to safely experiment with `iptables`/network namespaces without touching your real machine's network stack — not required for these labs, but useful if you want to go further than what's asked here.

---

## Lab 1: Diagnose "Is It Even Reachable" (curl / ping / dig)

**Objective:** Build the exact triage sequence a DevOps engineer runs in the first 60 seconds of "the site is down."

**Task:**
1. Pick a real public site (e.g. `example.com`) and run a reachability check with `ping -c 4`. Note the round-trip times.
2. Resolve its DNS with `dig example.com` (or `nslookup example.com` if `dig` isn't installed) and identify which record type answered, and the TTL.
3. Confirm the web service itself (not just the network) is actually serving traffic — use `curl -I` to get just the headers, and separately `curl -sf -o /dev/null -w "%{http_code}\n"` to get just the status code.
4. Now deliberately point at something that WILL fail differently at each layer, and classify which OSI layer each failure belongs to:
   - A hostname that doesn't resolve at all (e.g. `this-does-not-exist-12345.invalid`)
   - A real host but a closed/firewalled port (e.g. `nc -zv -w 3 example.com 81` — this will hang/refuse, since port 81 isn't listening)
   - A real host, open port, but the wrong protocol (try `curl http://example.com:443` — plain HTTP to the HTTPS port)
5. Write one sentence for each of the 3 failures above stating which OSI/TCP-IP layer it points to (per the lesson's "no ping → layer 3, port closed → layer 4, garbage response → layer 7" framework).

<details>
<summary>Solution / walkthrough</summary>

```bash
# 1. Basic reachability
ping -c 4 example.com
# 4 packets transmitted, 4 received, 0% packet loss, round-trip ~XXms
# NOTE: a successful ping only proves ICMP/network-layer reachability —
# it says nothing about whether the actual web service is healthy.

# 2. DNS resolution
dig example.com
# ;; ANSWER SECTION:
# example.com.        86400   IN      A       93.184.216.34
# TTL (86400s = 24h) tells you how long resolvers will cache this answer
# before re-querying — relevant when you change a record and wonder why
# some clients still hit the old IP.
dig +short example.com     # just the IP, no noise

# 3. Application-layer checks
curl -I https://example.com
# HTTP/2 200
# content-type: text/html; charset=UTF-8
# ...
curl -sf -o /dev/null -w "%{http_code}\n" https://example.com
# 200

# 4a. DNS failure — doesn't resolve at all
dig this-does-not-exist-12345.invalid
# ;; ANSWER SECTION: (empty) — NXDOMAIN
curl https://this-does-not-exist-12345.invalid
# curl: (6) Could not resolve host: this-does-not-exist-12345.invalid

# 4b. Closed port — connects at the network layer but nothing listens
nc -zv -w 3 example.com 81
# nc: connect to example.com port 81 (tcp) timed out: Operation now in progress
# (or "Connection refused" depending on whether a firewall drops vs rejects)

# 4c. Wrong protocol on an open port
curl http://example.com:443
# curl: (1) Received HTTP/0.9 when not allowed, or a TLS/protocol
# mismatch error — the TCP connection succeeds (port IS open), but
# what's listening speaks TLS, not plaintext HTTP

# 5. Layer classification
# 4a (NXDOMAIN)        -> not really an OSI data-path layer at all, it's
#                         an application-layer (L7) service (DNS) failing
#                         BEFORE any connection attempt can even happen.
# 4b (port closed)      -> Layer 4 (Transport) — the network path (L3) is
#                         fine, but nothing is listening on that port, or
#                         a firewall is blocking it at the transport layer.
# 4c (wrong protocol)   -> Layer 7 (Application) — the TCP handshake (L4)
#                         succeeded fully, but the payload exchanged
#                         doesn't match what either side expects.
```
</details>

---

## Lab 2: Port and Socket Investigation

**Objective:** Get comfortable finding out what's listening where, and killing it safely — the same skill from the Linux phase, now from a pure networking angle.

**Task:**
1. Start a trivial local listener on a high port: `python3 -m http.server 8123` (leave it running in one terminal).
2. From a second terminal, confirm something is listening on port 8123 using `ss -tlnp` (Linux) or `netstat -an | grep 8123` / `lsof -i :8123` (macOS/portable).
3. Confirm you can reach it with `curl -I http://localhost:8123` and separately with `nc -zv localhost 8123`.
4. Find the PID of the listening process from the socket tool's output, then cross-check it against `ps aux | grep http.server` — confirm they match.
5. Kill it via the port (not the process name) using the one-liner pattern from the Linux networking lesson: `kill $(lsof -t -i:8123)` (or the `ss`-based PID you already found).
6. Confirm the port is now free by re-running your socket check from step 2 — it should show nothing.

<details>
<summary>Solution / walkthrough</summary>

```bash
# Terminal 1
python3 -m http.server 8123

# Terminal 2
ss -tlnp | grep 8123
# LISTEN 0 5 0.0.0.0:8123 0.0.0.0:* users:(("python3",pid=48213,fd=3))
# macOS alternative:
lsof -i :8123
# COMMAND   PID  USER   FD   TYPE ... NAME
# python3 48213  you     3u  IPv4 ...  TCP *:8123 (LISTEN)

curl -I http://localhost:8123
# HTTP/1.0 200 OK

nc -zv localhost 8123
# Connection to localhost port 8123 [tcp/*] succeeded!

ps aux | grep http.server | grep -v grep
# you  48213  0.0  ...  python3 -m http.server 8123
# PID matches what ss/lsof reported — confirms it's the same process

kill $(lsof -t -i:8123)
# or, on Linux without lsof:
# kill $(ss -tlnp | grep 8123 | grep -oP 'pid=\K[0-9]+')

ss -tlnp | grep 8123
# (no output — port is free)
```

**Why cross-check PID against `ps aux`:** in a real incident, you often find a port occupied by something unexpected (a leftover process from a crashed deploy, or a second instance of your app that never shut down). Confirming the PID via TWO independent tools before killing it avoids accidentally killing the wrong process on a shared/multi-tenant box.
</details>

---

## Lab 3: SSH Tunneling — Reach a "Remote-Only" Service Locally

**Objective:** Practice the local port-forward pattern that lets you reach a database or internal service that's only bound to localhost on a remote box — a daily-use skill for anyone doing backend/DevOps work against real infrastructure.

> This lab needs an actual SSH-reachable host (a free-tier cloud VM works well, or a second machine/VM on your LAN). If you don't have one, do steps 1-3 against `localhost` itself (SSH into your own machine) to prove the mechanics, then read the walkthrough's explanation for the "remote box" case.

**Task:**
1. On the remote host, start a service bound ONLY to localhost so it's unreachable directly from outside: `python3 -m http.server 9000 --bind 127.0.0.1` (run this over your existing SSH session on the remote box, backgrounded or in a second SSH session).
2. From your OWN machine, confirm you genuinely cannot reach it directly: `curl --connect-timeout 3 http://<remote-ip>:9000` should fail/timeout.
3. Set up a local port-forward: `ssh -L 9001:localhost:9000 user@remote-host` (this maps YOUR local port 9001 through the SSH connection to the REMOTE host's localhost:9000).
4. While that SSH session stays open, from a new terminal on your own machine: `curl -I http://localhost:9001` — this should now succeed, proxied entirely through the SSH tunnel.
5. Explain in your own words (one or two sentences) why this is the standard way to reach a production database that's intentionally not exposed to the public internet.

<details>
<summary>Solution / walkthrough</summary>

```bash
# On the remote host (via a normal ssh user@remote-host session)
python3 -m http.server 9000 --bind 127.0.0.1 &

# From your own machine — direct access fails, as expected/intended
curl --connect-timeout 3 http://<remote-ip>:9000
# curl: (28) Connection timed out (or refused, depending on firewall)
# — the service is bound to 127.0.0.1 on the REMOTE box, so it never
# even receives packets addressed to the remote box's public/external IP

# Local port-forward — YOUR port 9001 tunnels through SSH to the
# REMOTE box's own localhost:9000
ssh -L 9001:localhost:9000 user@remote-host
# (leave this session open — it IS the tunnel)

# New terminal, same machine as you
curl -I http://localhost:9001
# HTTP/1.0 200 OK
# — you're talking to 127.0.0.1:9001 on YOUR machine, which SSH is
# silently forwarding, encrypted, to 127.0.0.1:9000 on the remote box
```

**Why this matters for databases:** production databases are almost always bound to a private subnet / localhost-only, with no direct route from the public internet — this is a deliberate security boundary (see the Docker/AWS phases on private subnets + NAT). `ssh -L 5433:db.internal:5432 bastion-host` is the standard way an engineer runs a one-off query against a locked-down production DB from their laptop: the DB is never exposed to the internet, but a specific SSH-authenticated user can tunnel to it through a bastion/jump host they DO have access to. This exact command appears in the Linux phase's networking-commands lesson — this lab is where you actually feel why it exists.
</details>

---

## Lab 4: Subnet a VPC by Hand (No Tools, Just Math)

**Objective:** Prove you can do the CIDR math cold — the exact skill tested in "design a VPC" interview questions and needed before ever touching Terraform/AWS console.

**Task:**

You're given `10.20.0.0/16` for a new VPC (65,536 addresses). Design a 3-AZ layout with public and private subnets per AZ, by hand:

1. Split the `/16` into 6 equal `/20` subnets (256 × 4 = enough room per subnet, leaves growth room within the /16). Write out all 6 subnet ranges with their first usable IP, last usable IP, and broadcast address.
2. Assign them: AZ-a public, AZ-a private, AZ-b public, AZ-b private, AZ-c public, AZ-c private.
3. For ONE of the private subnets, calculate exactly how many usable hosts it has, showing the `2^(32-prefix) - 2` formula.
4. A teammate proposes putting the RDS database in a `/28` carved out of one of the private subnets (for tighter security-group scoping) instead of using the whole /20 directly for app servers. How many usable hosts does that /28 give you, and is that enough for a database tier with 1 primary + 2 read replicas + headroom? Show the math.
5. Explain, in one sentence, why `10.20.0.0/16` peered later with another VPC also using `10.20.0.0/16` would be a real production problem (tie back to the lesson's CIDR-overlap warning).

<details>
<summary>Solution / walkthrough</summary>

```
1. 10.20.0.0/16 split into 6 x /20 (borrowing 4 bits: /16 -> /20, 2^4 = 16
   possible /20s, we're only using 6 of them, leaving 10 free for future growth)

   Subnet 1 (AZ-a public):  10.20.0.0/20    usable 10.20.0.1   - 10.20.15.254   broadcast 10.20.15.255
   Subnet 2 (AZ-a private): 10.20.16.0/20   usable 10.20.16.1  - 10.20.31.254   broadcast 10.20.31.255
   Subnet 3 (AZ-b public):  10.20.32.0/20   usable 10.20.32.1  - 10.20.47.254   broadcast 10.20.47.255
   Subnet 4 (AZ-b private): 10.20.48.0/20   usable 10.20.48.1  - 10.20.63.254   broadcast 10.20.63.255
   Subnet 5 (AZ-c public):  10.20.64.0/20   usable 10.20.64.1  - 10.20.79.254   broadcast 10.20.79.255
   Subnet 6 (AZ-c private): 10.20.80.0/20   usable 10.20.80.1  - 10.20.95.254   broadcast 10.20.95.255

   (each /20 = 4096 addresses total, 4094 usable — plenty of room per AZ,
   and 10 more /20 blocks remain unused in 10.20.96.0/20 through
   10.20.240.0/20 for future subnets: databases, caches, a 4th AZ, etc.)

2. Assignment — see labels above (public = has IGW route, private = NAT
   Gateway route, per the lesson's "route table decides" rule).

3. Usable hosts in one /20 private subnet (e.g. 10.20.16.0/20):
   2^(32-20) - 2 = 2^12 - 2 = 4096 - 2 = 4094 usable hosts
   (subtract 2 for the network address 10.20.16.0 and the broadcast
   address 10.20.31.255, both reserved)

4. A /28 carved for RDS:
   2^(32-28) - 2 = 2^4 - 2 = 16 - 2 = 14 usable hosts
   14 is comfortably enough for 1 primary + 2 read replicas (3 hosts)
   plus real headroom for a 4th replica, a bastion/jump ENI, or an RDS
   proxy endpoint — a /28 is a deliberately tight, easy-to-audit
   security-group scope for a database tier that will never need
   hundreds of IPs, versus dumping the DB into the full /20 alongside
   app servers where a broader CIDR-based SG rule would be needed.

5. Overlapping CIDR problem:
   VPC peering routes traffic based on destination CIDR — if BOTH VPCs
   use 10.20.0.0/16, the peering connection can't unambiguously route
   traffic (which 10.20.5.10 do you mean, VPC A's or VPC B's?), so AWS
   simply won't let you establish the peering connection at all — this
   is exactly why the lesson says "sketch CIDR ranges before creating
   a VPC," because fixing an overlap after the fact usually means
   re-IP'ing an entire VPC's subnets, a painful, high-risk migration.
```
</details>

---

## Self-Check Checklist

- [ ] Can you run the "is it reachable" triage sequence (ping → dig → curl -I → curl status code) from memory, in the right order?
- [ ] Given a failure, can you classify it as a DNS / L3 / L4 / L7 problem within a few seconds?
- [ ] Can you find what's listening on a port and safely kill only that specific process (not just "something with a similar name")?
- [ ] Can you set up an SSH local port-forward from memory (`ssh -L <local>:<remote-host>:<remote-port> <ssh-host>`) and explain what each field means?
- [ ] Can you explain SNAT vs DNAT with a concrete example, without reading the definitions first?
- [ ] Can you calculate usable hosts for any CIDR prefix (`/24`, `/27`, `/20`, `/28`) without a calculator?
- [ ] Can you design a multi-AZ, public+private VPC subnet layout from a given CIDR block, on paper?
- [ ] Can you explain why two VPCs with overlapping CIDR ranges can't be peered?
- [ ] Do you know which ports are well-known cold: 22, 53, 80, 443, 587?
- [ ] Can you explain why a successful `ping` doesn't prove your application is healthy?
