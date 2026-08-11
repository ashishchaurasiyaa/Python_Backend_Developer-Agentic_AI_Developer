# OSI Model, TCP/IP, IP Addressing & Subnetting

**DevOps Track · Phase 3: Networking**

## Quick Concepts

| Concept | One-line definition |
|--------------------------|----------------------------------------------------------------------|
| **OSI Model** | 7-layer conceptual model of how network communication is broken into stages |
| **TCP/IP Model** | The 4-layer model the real internet actually runs on (OSI is teaching theory) |
| **IP address** | Numeric identifier for a device on a network (IPv4: 32-bit, dotted-decimal) |
| **Subnet** | A logical subdivision of a network — a range of IPs carved from a larger block |
| **CIDR** | `/24` notation expressing how many bits are the network portion |
| **Routing** | Deciding the next hop to forward a packet toward its destination |
| **NAT** | Rewriting IP addresses as traffic crosses a boundary (private → public) |
| **IPv6** | 128-bit successor to IPv4 — enough addresses for every grain of sand on Earth |
| **VPC Peering** | Direct private connection between two VPCs — non-transitive |
| **Transit Gateway** | Managed hub connecting many VPCs through one central point |

---

## Why This Matters for Backend/DevOps Work

```
- Designing a VPC: choosing CIDR ranges so subnets don't overlap
- Debugging "why can't service A reach service B" — is it routing,
  NAT, or a security group / firewall rule?
- Understanding why a Docker container reaches the internet but isn't
  reachable FROM the internet (SNAT + DNAT / port mapping)
- Reading a Kubernetes CNI / AWS VPC diagram without your eyes glazing over
- Interview staple: "explain the OSI model" and "how does NAT work"
```

---

## The OSI Model — 7 Layers

| # | Layer | Function | Example Protocol / Device |
|---|-------|----------|-----------------------------|
| 7 | **Application** | User-facing protocols — what your app speaks | HTTP, DNS, SMTP, FTP |
| 6 | **Presentation** | Data format, encoding, encryption, compression | TLS/SSL, JPEG, UTF-8 |
| 5 | **Session** | Establishes, manages, terminates sessions | Sockets, SSH session, NetBIOS |
| 4 | **Transport** | End-to-end delivery, reliability, ordering | TCP, UDP |
| 3 | **Network** | Logical addressing and routing between networks | IP, ICMP, routers |
| 2 | **Data Link** | Physical addressing on the same local network | Ethernet, MAC addresses, switches |
| 1 | **Physical** | Raw bits over a physical medium | Cables, fiber, radio (Wi-Fi), NICs |

```
Mnemonic (top → bottom): "All People Seem To Need Data Processing"
  Application, Presentation, Session, Transport, Network, Data Link, Physical
```

---

## OSI Layers — In Depth

### What Happens When You Type `https://google.com`

Every HTTP request you make touches all 7 layers — in order downward on the sender, in reverse on the receiver.

```
Layer 7 — Application
  Browser decides: "I need to make an HTTP GET request"
  DNS resolution: "what IP address is google.com?" → 142.250.x.x
  HTTP request built: GET / HTTP/1.1\r\nHost: google.com\r\n...
  TLS: negotiation begins (which cipher, which cert)

Layer 6 — Presentation
  TLS encrypts the HTTP request bytes
  Data serialised/encoded (UTF-8, gzip compression if Content-Encoding)

Layer 5 — Session
  TCP connection state (ESTABLISHED) manages the session
  TLS session ID tracked for potential reuse (session resumption)

Layer 4 — Transport
  TCP: SYN → SYN-ACK → ACK (3-way handshake establishes connection)
  Source port: random ephemeral (e.g. 51234)
  Destination port: 443 (HTTPS)

Layer 3 — Network
  IP packet created: src=192.168.1.10, dst=142.250.x.x
  Routing table consulted: which interface and gateway to use?

Layer 2 — Data Link
  ARP: "what MAC address belongs to my default gateway?"
  Ethernet frame: src_mac=YOUR_NIC, dst_mac=ROUTER_MAC
  Frame has max size: MTU 1500 bytes (large packets get fragmented)

Layer 1 — Physical
  Frame encoded as electrical signal / photons / radio waves
  Transmitted on the wire / fiber / air
```

### OSI as a Debugging Vocabulary

```
Problem observed                  → OSI Layer   → Tool to reach for
─────────────────────────────────────────────────────────────────────
ping fails completely             → L3           → traceroute, ip route show
ping works, port won't connect    → L4           → ss -tlnp, nc -zv host port
port connects, TLS handshake fails → L6          → curl -v, openssl s_client
TLS fine, HTTP 502/504            → L7           → app logs, journalctl
HTTP 200 but wrong data           → L7 app logic → application debugging
```

**Real AWS example — this is why ALB vs NLB matters:**

```
NLB (Network Load Balancer) = Layer 4 TCP/UDP
  Pros: fastest, lowest latency, handles any TCP-based protocol
  Cons: no HTTP awareness, no path routing, no WAF

ALB (Application Load Balancer) = Layer 7 HTTP
  Pros: path routing (/api → service A, /web → service B)
        host routing (api.example.com → target group 1)
        WAF, sticky sessions by cookie, gRPC support
  Cons: slightly slower (must parse HTTP headers)

"Should I use ALB or NLB?" = "do I need layer 7 awareness?"
If you need routing by URL path, header, or hostname → ALB
If you need raw TCP/UDP performance (gaming, VoIP, custom protocol) → NLB
```

---

## TCP/IP Model — What Actually Runs the Internet

| TCP/IP Layer | Maps to OSI | Examples |
|--------------|-------------|----------------------------------------|
| **Application** | 5, 6, 7 | HTTP, DNS, SSH, FTP, SMTP |
| **Transport** | 4 | TCP, UDP |
| **Internet** | 3 | IP, ICMP, routing |
| **Link (Network Access)** | 1, 2 | Ethernet, Wi-Fi, ARP |

```
OSI = the teaching/reference model
  Used in interviews and vendor docs to LOCATE where a problem sits
  ("is this a layer 3 or layer 7 issue?")
  Never actually implemented as 7 discrete modules in software

TCP/IP = the practical 4-layer model the actual internet implements
  The OS network stack (kernel) implements this
  Your application lives at the top (Application layer)
  The kernel handles Transport, Internet, and Link automatically
```

### TCP Three-Way Handshake — Complete Picture

```
CLIENT                          SERVER
  │                               │
  │──── SYN ─────────────────────▶│   "I want to connect, my seq=1000"
  │◀─── SYN-ACK ─────────────────│   "OK, my seq=2000, ack=1001"
  │──── ACK ─────────────────────▶│   "Your ack=2001, we're connected"
  │                               │   ← ESTABLISHED — data can flow
  │═════════ DATA ════════════════▶│
  │◀════════ DATA ═════════════════│
  │                               │
  │──── FIN ─────────────────────▶│   "I'm done sending"
  │◀─── ACK ──────────────────────│
  │◀─── FIN ──────────────────────│   "I'm done too"
  │──── ACK ─────────────────────▶│
  │                               │   ← TIME_WAIT (~60s) then CLOSED

Why the handshake exists:
  Both sides need to agree on sequence numbers before sending data.
  Sequence numbers let TCP: detect lost packets, reorder out-of-order
  delivery, and detect duplicate packets.

TIME_WAIT explained:
  The last ACK might be lost — the server may retransmit its FIN.
  TIME_WAIT keeps state so the retransmitted FIN gets a proper ACK
  rather than confusing a new connection.
  High TIME_WAIT count (ss -s) = lots of short-lived connections
  → fix with HTTP keep-alive or connection pooling.
```

### TCP vs UDP — When to Use Each

```
TCP:
  + Guaranteed delivery (retransmits lost packets automatically)
  + Ordered delivery (seq numbers reassemble out-of-order packets)
  + Flow control (doesn't overwhelm a slow receiver's buffer)
  − Overhead: 3-way handshake, ACKs per segment, retransmit delays
  Use for: HTTP/HTTPS, SSH, databases (MySQL/Postgres), anything where
           data correctness matters more than latency

UDP:
  + No handshake — first packet is data
  + No retransmit overhead
  + Lower latency, higher throughput potential
  − No delivery guarantee: packets can be dropped, duplicated, reordered
  Use for: DNS queries, video streaming, VoIP, online games, QUIC/HTTP3

Real example — DNS uses UDP:
  A DNS query is one tiny packet. A TCP handshake for every lookup would
  triple the packet count before you even get an answer.
  If the UDP response is lost, the resolver just retries after ~100ms.
  UDP is the correct choice here: simple, fast, self-retrying at app level.
```

---

## IPv4 Addressing

### Structure

```
An IPv4 address = 32 bits, written as 4 octets: 192.168.1.10

Binary:   11000000 . 10101000 . 00000001 . 00001010
Decimal:      192  .    168   .     1    .    10

Each octet: 0–255 (8 bits, 2^8 = 256 values)

How to read binary quickly (bit values per position):
  128  64  32  16   8   4   2   1
    1   1   0   0   0   0   0   0  = 128+64 = 192
    1   0   1   0   1   0   0   0  = 128+32+8 = 168
```

### How a Host Decides "Is This On My Network?"

```
Subnet mask ANDed with IP address = network address

IP:      192.168.1.10  = 11000000.10101000.00000001.00001010
Mask:    255.255.255.0  = 11111111.11111111.11111111.00000000
                          ─────────────────────────────────── AND
Network: 192.168.1.0   = 11000000.10101000.00000001.00000000

If destination AND mask = my network address → destination is LOCAL
  → send directly (ARP for MAC address, no router needed)
If destination is on a DIFFERENT network
  → forward to the default gateway (router)

This is why 192.168.1.5 and 192.168.1.200 can talk directly
(same /24 network), but 192.168.1.5 and 10.0.0.1 need a router.
```

### Special IP Ranges — Why They Exist

```
127.0.0.0/8 — Loopback:
  Traffic never leaves the host. The kernel intercepts it internally.
  127.0.0.1 = localhost — always refers to "this machine"
  Use: local DB connections, testing, inter-process communication on same host
  If your app listens on 127.0.0.1:5432, it's ONLY reachable from the same box.

169.254.0.0/16 — Link-Local (APIPA):
  Auto-assigned when DHCP fails ("I couldn't get an IP, so I picked one")
  Never routed beyond the local link.
  Critical: AWS/GCP metadata service lives at 169.254.169.254
    curl http://169.254.169.254/latest/meta-data/instance-id
    → returns the EC2 instance ID, IAM role credentials, AMI ID, etc.
    → reachable from any EC2 instance regardless of VPC/subnet config
    → used by apps to discover their own AWS context at runtime

RFC 1918 Private Ranges (never internet-routable):
  10.0.0.0/8         → large orgs, AWS VPCs commonly use 10.x.x.x/16
  172.16.0.0/12      → Docker's default bridge network (172.17.0.0/16)
  192.168.0.0/16     → home routers, small office networks
  WHY: IPv4 exhaustion. NAT lets thousands of private hosts share one public IP.
```

### Historical Address Classes (Interview Knowledge)

| Class | Range | Default Mask | Use |
|-------|-------|--------------|------------------------------------------------------|
| A | 1.0.0.0 – 126.255.255.255 | /8 | Huge networks (few networks, millions of hosts) |
| B | 128.0.0.0 – 191.255.255.255 | /16 | Medium networks |
| C | 192.0.0.0 – 223.255.255.255 | /24 | Small networks (most common historically) |
| D | 224.0.0.0 – 239.255.255.255 | — | Multicast |
| E | 240.0.0.0 – 255.255.255.255 | — | Reserved/experimental |

```
Classes are obsolete — CIDR replaced them in 1993 because classes were
too wasteful (a company needing 300 hosts had to get a full Class B = 65,534
addresses, wasting 65,234 of them). CIDR lets you allocate exactly /23
(510 hosts) instead. Know classes for interviews; use CIDR in practice.
```

---

## IPv6 — Why It Exists and What's Different

```
The entire IPv4 address space = ~4.3 billion addresses (2^32).
Already exhausted for fresh direct allocation.
That's the ONLY reason NAT and private ranges became mandatory.

IPv6 fixes the root cause:
  128-bit address space = 2^128 ≈ 340 undecillion addresses
  "Enough for every grain of sand on Earth to have its own IP, many times over"
```

### Notation

```
IPv4:  192.168.1.10                          (4 decimal octets)
IPv6:  2001:0db8:0000:0000:0000:ff00:0042:8329  (8 groups of 4 hex digits)

Shortening rules (both can be applied together):
  1. Drop leading zeros in each group: 0db8 → db8, 0042 → 42
  2. ONE consecutive run of all-zero groups collapses to "::"
     (only once — otherwise ambiguous how many zeros "::" represents)

Full:      2001:0db8:0000:0000:0000:ff00:0042:8329
Shortened: 2001:db8::ff00:42:8329

Special addresses:
  ::1          loopback (IPv4 equivalent: 127.0.0.1)
  fe80::/10    link-local (IPv4 equivalent: 169.254.0.0/16)
  ::/0         default route (IPv4 equivalent: 0.0.0.0/0)
```

### What Changes for a Backend/DevOps Engineer

```
NAT becomes unnecessary for address conservation:
  Every device can have a globally routable IPv6 address.
  No need to hide behind a shared public IP.

Security posture changes:
  Without NAT, the FIREWALL (security group/NACL/host firewall) is the
  DELIBERATE security boundary — not an accidental side effect of NAT.
  "NAT was never really a security feature" is the correct senior framing.
  IPv6 removes the accidental protection NAT happened to provide —
  you must be explicit about firewall rules for IPv6-addressed hosts.

Cloud reality:
  AWS VPCs support dual-stack mode (both IPv4 and IPv6 on same VPC/subnet)
  Most orgs run dual-stack rather than IPv6-only — many SaaS APIs and
  legacy systems are still IPv4-only.

EKS IPv6 clusters:
  A busy EKS cluster with one IP per pod can exhaust a VPC's IPv4 space
  before exhausting compute capacity — this is a REAL, common problem.
  IPv6 EKS clusters solve this: each pod gets an IPv6 address from the
  VPC's /56 prefix instead of consuming precious IPv4 addresses.
```

```bash
ip -6 addr show          # show IPv6 addresses on this host
ping6 example.com          # ping over IPv6
curl -6 https://example.com  # force IPv6
```

---

## Subnetting & CIDR

### CIDR Notation — Decoded

```
192.168.1.0/24
             │
             └── 24 = number of NETWORK bits (fixed)
                 32 - 24 = 8 HOST bits (variable)
                 2^8 = 256 total addresses
                 256 - 2 = 254 usable
                 (first = network address, last = broadcast — both reserved)
```

### The Mental Model — How Many Bits Do I Need?

```
I need 50 hosts in a subnet:
  2^n ≥ 50+2 = 52  →  n=6 (2^6=64) → /26 subnet
  64 total, 62 usable. Done.

I need 200 hosts:
  2^n ≥ 202  →  n=8 (2^8=256) → /24 subnet
  256 total, 254 usable.

I need 500 hosts:
  2^n ≥ 502  →  n=9 (2^9=512) → /23 subnet
  512 total, 510 usable.

Formula: usable = 2^(32 - prefix) - 2
  /24 → 2^8  - 2 = 254
  /27 → 2^5  - 2 = 30
  /30 → 2^2  - 2 = 2   (point-to-point links)
  /32 → 2^0  - 2 = -1  → special: single host route (no broadcast)
```

### Common CIDR Blocks Cheat Sheet

| CIDR | Subnet Mask | Total Addresses | Usable Hosts | Common Use |
|------|-------------|-----------------|--------------|-----------------------------------|
| /32 | 255.255.255.255 | 1 | 1 | Single host route, security group rules |
| /30 | 255.255.255.252 | 4 | 2 | Point-to-point links |
| /28 | 255.255.255.240 | 16 | 14 | Small service subnet |
| /27 | 255.255.255.224 | 32 | 30 | Small team subnet |
| /26 | 255.255.255.192 | 64 | 62 | Medium service tier |
| /24 | 255.255.255.0 | 256 | 254 | Standard subnet (most common) |
| /23 | 255.255.254.0 | 512 | 510 | EKS node/pod subnets |
| /20 | 255.255.240.0 | 4,096 | 4,094 | Large EKS pod subnet |
| /16 | 255.255.0.0 | 65,536 | 65,534 | Entire VPC CIDR |

### Worked Subnetting Example

```
Given: 192.168.1.0/24  (256 addresses, 254 usable)
Task: split into 4 equal subnets

Borrow 2 bits from the host portion (2^2 = 4 subnets) → /24 becomes /26

Subnet 1: 192.168.1.0/26    range .0   – .63    usable: .1–.62    broadcast .63
Subnet 2: 192.168.1.64/26   range .64  – .127   usable: .65–.126  broadcast .127
Subnet 3: 192.168.1.128/26  range .128 – .191   usable: .129–.190 broadcast .191
Subnet 4: 192.168.1.192/26  range .192 – .255   usable: .193–.254 broadcast .255

Each /26 = 64 total, 62 usable.
```

### AWS VPC Subnetting — Real Production Design

```
VPC CIDR: 10.0.0.0/16   (65,536 addresses — generous, leave room to grow)

Why /16 for the VPC?
  VPCs can't easily be resized post-creation.
  A /16 lets you carve up to 256 separate /24 subnets without overlap.
  Always overprovision the VPC, right-size the subnets.

Why /24 per subnet (most common choice)?
  256 IPs, minus AWS's 5 reserved per subnet = 251 usable.
  Enough for most service tiers, small enough to keep routes specific.

The 5 AWS-reserved addresses per subnet:
  10.0.1.0   = network address
  10.0.1.1   = VPC router (your default gateway)
  10.0.1.2   = AWS DNS server
  10.0.1.3   = reserved for future AWS use
  10.0.1.255 = broadcast (reserved but not used in VPC)
  → /24 gives 256 - 5 = 251 usable

Typical 3-tier layout:
  10.0.0.0/24   → public subnet AZ-a   (ALB, NAT Gateway)
  10.0.1.0/24   → public subnet AZ-b   (ALB, NAT Gateway)
  10.0.10.0/24  → private subnet AZ-a  (app servers, ECS tasks)
  10.0.11.0/24  → private subnet AZ-b  (app servers, ECS tasks)
  10.0.20.0/24  → database subnet AZ-a (RDS primary)
  10.0.21.0/24  → database subnet AZ-b (RDS standby)

EKS with one IP per pod — needs much larger subnets:
  10.0.32.0/20  → EKS pod subnet AZ-a  (4,091 usable IPs for pods)
  10.0.48.0/20  → EKS pod subnet AZ-b
  A single EKS node with 30 pods = 30 IPs from the subnet.
  With 100 nodes × 30 pods = 3,000 IPs consumed.
  This is why /20 or even /18 per pod subnet is recommended for EKS.
```

---

## Routing Basics

```
A router forwards packets between different networks using a routing
table. It matches the destination IP against known routes and picks
the MOST SPECIFIC (longest prefix) match.

Routing table example:
  Destination        Gateway          Interface
  ─────────────────────────────────────────────
  0.0.0.0/0          203.0.113.1       eth0     ← default route ("send everything here")
  10.0.0.0/16        directly connected eth1    ← local VPC, no gateway needed
  10.0.10.0/24       10.0.0.5          eth1     ← specific subnet via specific gateway
  192.168.1.0/24     10.0.0.5          eth1

Packet to 10.0.10.55:
  Matches 0.0.0.0/0      (0 bits match)
  Matches 10.0.0.0/16    (16 bits match)
  Matches 10.0.10.0/24   (24 bits match) ← LONGEST PREFIX = winner
  → forwarded via 10.0.0.5

Packet to 8.8.8.8:
  Matches 0.0.0.0/0 only → sent to default gateway 203.0.113.1 (internet)
```

```bash
ip route show           # show routing table on Linux
ip route get 8.8.8.8     # which route would be used for this destination?
route -n                  # older equivalent
```

### AWS Route Tables

```
Every subnet in a VPC has an associated route table.
The route table controls WHERE traffic from that subnet goes.

Public subnet route table:
  10.0.0.0/16   → local       (traffic within VPC stays inside)
  0.0.0.0/0     → igw-xxxxx   (default route → Internet Gateway)

Private subnet route table:
  10.0.0.0/16   → local
  0.0.0.0/0     → nat-xxxxx   (default route → NAT Gateway for outbound internet)

Database subnet route table:
  10.0.0.0/16   → local
  (no default route → database instances have NO internet access at all)

"Why can't my app server reach the internet?" debug flow:
  1. Does it have a route table attached?
  2. Does that route table have a 0.0.0.0/0 route?
  3. If private subnet, does the 0.0.0.0/0 point to a NAT Gateway?
  4. Is the NAT Gateway in a PUBLIC subnet with its own internet access?
```

---

## VPC Peering & Transit Gateway

### VPC Peering — Direct, One-to-One

```
VPC A (10.0.0.0/16) ←── peering connection ──→ VPC B (10.1.0.0/16)

What peering does:
  Creates a network route between two VPCs using AWS's backbone.
  Traffic stays on AWS infrastructure (never touches the public internet).

What peering does NOT do automatically:
  It does NOT add routes for you. You MUST manually add:
    In VPC A's route table: 10.1.0.0/16 → pcx-xxxxx (the peering connection)
    In VPC B's route table: 10.0.0.0/16 → pcx-xxxxx
  Without these route entries, hosts still can't reach each other.

Key limitation — NOT transitive:
  VPC A peers with B. VPC B peers with C.
  VPC A CANNOT reach VPC C through B.
  Traffic from A destined for C arrives at B but B has no route back.
  A needs its OWN direct peering with C.
  This is the #1 VPC peering misconception — asked in almost every DevOps interview.

CIDRs must NOT overlap:
  10.0.0.0/16 peering with 10.0.0.0/24 → AWS REJECTS this.
  The routing table would have two routes matching the same addresses —
  ambiguous, no way to decide which direction to forward.
  This is why you design your VPC CIDR layout BEFORE you create anything.
```

### Transit Gateway — Hub-and-Spoke for Many VPCs

```
                    ┌─────────────────┐
   VPC A ───────────┤                 │
   VPC B ───────────┤  Transit Gateway├──── On-prem (via VPN / Direct Connect)
   VPC C ───────────┤    (the hub)    │
   VPC D ───────────┤                 │
                    └─────────────────┘

Each VPC attaches ONCE. The Transit Gateway's own route table controls
which attachments can reach which — you configure routing centrally.

Adding an 11th VPC:
  With peering:  add 10 new peering connections + 20 route table entries
  With TGW:      add 1 attachment + 1 TGW route entry

The N² problem:
  N VPCs needing full mutual connectivity via peering = N(N-1)/2 connections
  5 VPCs  =  10 peering connections
  10 VPCs =  45 peering connections
  Each connection = 2 route table entries (one per side)
  → maintenance burden grows quadratically
  → Transit Gateway turns this into N simple hub attachments
```

| | VPC Peering | Transit Gateway |
|-------------|-------------|----------------|
| **Topology** | Point-to-point, non-transitive | Hub-and-spoke, transitive via TGW route tables |
| **Cost** | Free (data transfer charges apply) | Per-attachment hourly + data processing fee |
| **Scales to many VPCs** | Poorly (N² connections) | Well (N attachments) |
| **Connects to on-prem** | No (needs separate VPN/Direct Connect) | Yes, directly |
| **Use when** | 2–4 VPCs, simple/stable topology | Many VPCs, multi-account, or on-prem needed |

### Site-to-Site VPN and Direct Connect

```
Site-to-Site VPN:
  Encrypted tunnel over the public internet
  Your VPC ← Virtual Private Gateway ← IPSec tunnel ← On-prem router
  Fast to set up (hours, not weeks)
  Variable latency/throughput — rides the public internet
  Bandwidth typically 1.25 Gbps max per tunnel

AWS Direct Connect:
  Dedicated, private physical network link from your data center to AWS
  Consistent low latency and bandwidth (1Gbps or 10Gbps)
  Real provisioning lead time: physical cross-connect at a co-location facility
  Can take weeks to provision, ongoing port charges

Common production pattern:
  Direct Connect as PRIMARY (fast, consistent SLA)
  Site-to-Site VPN as FAILOVER (if the physical link goes down)
  BGP failover routes traffic automatically between the two paths
```

---

## NAT — Network Address Translation — In Depth

```
NAT rewrites IP addresses (and ports) as traffic crosses a boundary.
The core problem it solves: private RFC 1918 addresses are NOT internet-routable.
A packet from 10.0.10.5 destined for google.com would be dropped by
every internet router because no one has a route to 10.0.0.0/8.
NAT rewrites the source to a public IP that IS routable.
```

### SNAT — Source NAT (Outbound)

```
Use case: EC2 in a private subnet downloading a package (pip install, apt update)

Flow:
  1. EC2 (10.0.10.5:54321) sends packet to 8.8.8.8:53 (DNS query)
  2. Packet leaves through the private subnet's default route → NAT Gateway
  3. NAT Gateway rewrites:
       src=10.0.10.5:54321 → src=3.4.5.6:60001  (public Elastic IP:random_port)
  4. NAT Gateway records in connection tracking table:
       3.4.5.6:60001 ↔ 10.0.10.5:54321
  5. Packet sent to internet, reaches 8.8.8.8
  6. 8.8.8.8 replies to 3.4.5.6:60001
  7. NAT Gateway receives reply, looks up port 60001 in tracking table
  8. Rewrites: dst=3.4.5.6:60001 → dst=10.0.10.5:54321
  9. Delivers to the EC2 instance

Why connection tracking is essential:
  Multiple EC2 instances can initiate connections simultaneously.
  The NAT Gateway uses the port number (60001, 60002, ...) to distinguish
  which return traffic belongs to which internal host.
  Without tracking, NAT can't route replies correctly.
```

### DNAT — Destination NAT (Inbound)

```
Use case: ALB receiving traffic and forwarding to backend EC2s

Flow:
  1. Client sends request to ALB public IP 52.x.x.x:443
  2. ALB selects a healthy target: EC2 10.0.10.5:8000
  3. Rewrites:
       dst=52.x.x.x:443 → dst=10.0.10.5:8000
  4. EC2 receives request with source=client's IP (X-Forwarded-For header
     preserves original client IP at layer 7)
  5. EC2 responds to ALB, ALB sends response to the original client

Port forwarding is DNAT:
  iptables DNAT rule: dst=HOST:8080 → dst=CONTAINER:80
  This is exactly what `docker run -p 8080:80` adds to iptables
```

### Docker Networking — NAT Under the Hood

```
docker run -p 8080:80 nginx

What Docker actually does:
  iptables -t nat -A PREROUTING -p tcp --dport 8080 -j DNAT --to 172.17.0.2:80
  iptables -t nat -A POSTROUTING -s 172.17.0.2 -j MASQUERADE  (SNAT)

When you curl localhost:8080:
  Kernel hits the DNAT rule → rewrites dst to 172.17.0.2:80 → container receives it
  Container responds → kernel hits MASQUERADE rule → rewrites src to host IP
  Response delivered to your curl

Why container can reach internet but isn't reachable FROM internet:
  Outbound: container IP (172.17.x.x) SNAT'd to host IP → internet sees host IP
  Inbound:  no DNAT rule for the container's port → packets dropped by default
            Only ports explicitly published (-p) get DNAT rules
```

---

## Senior Tips

```
1. When debugging "can't reach service X," locate the OSI layer first:
   - No ping at all     → L3 (routing / firewall / security group)
   - Ping works, no TCP → L4 (nothing listening, or port blocked)
   - TCP connects, error → L6/L7 (TLS cert, app bug, wrong protocol)

2. Always sketch subnet CIDR ranges BEFORE creating a VPC.
   Overlapping CIDRs between VPCs you later need to peer is painful —
   you can't re-IP a live VPC without significant downtime.

3. Private IP ranges (10.x, 172.16-31.x, 192.168.x) are never
   internet-routable by design — that's WHY NAT exists.
   This is not a bug; it's the intended model for IPv4 scarcity.

4. In AWS, the 5 reserved addresses per subnet (network, router, DNS,
   future, broadcast) matter when sizing subnets — a /28 gives 16
   total but only 11 usable after AWS reserves 5.

5. VPC CIDR planning mistake: 10.0.0.0/24 for your VPC gives only 251
   usable IPs total — if your EKS cluster needs one IP per pod, you're
   done before you're started. Always use /16 for the VPC, carve /24s.
```

---

## Interview Angle

**Q: Explain the OSI model — and why care about it if TCP/IP is what actually runs?**

```
OSI is the diagnostic vocabulary, not an implementation spec.
When you say "layer 3 issue," everyone knows: IP, routing, firewall.
"Layer 7 issue" = application-level, debug the app code.

Layer 1-2: physical and local delivery (cables, MAC addresses, switches)
Layer 3:   IP routing (logical addresses, routing tables, routers)
Layer 4:   TCP/UDP (ports, reliable delivery, connection state)
Layer 5-6: session management, encryption (TLS lives here)
Layer 7:   application protocols (HTTP, DNS, SSH, the actual data)

TCP/IP collapses OSI's 7 layers into 4 and is what the kernel implements.
OSI exists as a shared debugging vocabulary — teams use it to quickly
narrow where a problem sits before picking the right tool.
```

**Q: How many usable hosts in a /27 subnet?**

```
2^(32-27) - 2 = 2^5 - 2 = 32 - 2 = 30
Subtract 2: one for network address (all host bits 0), one for broadcast (all host bits 1).
Both are reserved and cannot be assigned to hosts.
```

**Q: Explain SNAT vs DNAT with a concrete AWS example.**

```
SNAT = rewrites SOURCE address (outbound traffic)
  EC2 10.0.10.5 → internet via NAT Gateway → source rewritten to 3.4.5.6
  Return traffic comes back to 3.4.5.6, NAT Gateway maps it to 10.0.10.5

DNAT = rewrites DESTINATION address (inbound traffic)
  Client → ALB 52.x.x.x:443 → DNAT → EC2 10.0.10.5:8000
  Public endpoint maps to a private backend port

Docker -p 8080:80 = DNAT + SNAT:
  DNAT: incoming :8080 → container :80
  SNAT: outgoing from container → host IP (masquerade)
```

**Q: VPC A peers with B, B peers with C. Can A reach C?**

```
No — peering is NOT transitive.
Traffic from A destined for C arrives at B but B's route table has no
entry pointing C's CIDR at anything useful. B doesn't "forward through
its peering connections" — each peering connection is independent.
A needs its own direct peering to C, OR all three need to attach to a
Transit Gateway which CAN route transitively via its own route tables.
```

**Q: 8 VPCs all need to communicate — peering or Transit Gateway?**

```
Transit Gateway. 8 VPCs with full-mesh peering = N(N-1)/2 = 28 connections,
each requiring route table entries on both sides = 56 route table entries
to maintain. Adding a 9th VPC adds 8 more connections and 16 more entries.
Transit Gateway: 8 attachments to one hub, one central route table.
Adding a 9th: 1 new attachment, 1 new route entry. Simple.
The N² growth of peering is exactly what TGW solves.
```

**Q: Why can't every server just have a public IP? Why NAT at all?**

```
IPv4 has ~4.3 billion addresses (2^32). Already exhausted.
Public IPs are assigned by IANA/RIRs and are a scarce, paid resource.
NAT + private RFC 1918 ranges let an organisation run millions of internal
hosts while consuming only a handful of public IPs.
It also provides an incidental security boundary (private hosts aren't
directly reachable without explicit forwarding) — though that's a side
effect, not the primary purpose. IPv6 is the real long-term fix.
```

**Q: Does IPv6 make NAT obsolete?**

```
NAT becomes unnecessary for address conservation — IPv6's 128-bit space
means every device can have a globally routable address.

But this changes the security model:
  With IPv4+NAT: private hosts are "hidden" behind one public IP —
    incidental protection, accidental but real.
  With IPv6: every host potentially reachable directly —
    the FIREWALL (security group, NACL, iptables) must be the
    explicit and deliberate security boundary.

"NAT was never a security feature" is the correct senior framing,
but IPv6 removes the accidental protection it happened to provide.
Dual-stack is the practical default in 2026 — most orgs run both
rather than IPv6-only, because many SaaS and legacy dependencies
are still IPv4-only.
```

---

## Related

- [`../07_Cloud_AWS/03_networking_dns_lb.md`](../07_Cloud_AWS/03_networking_dns_lb.md) — Security Groups vs NACLs, VPC anatomy, Route 53
- [`../01_Linux/06_networking_commands.md`](../01_Linux/06_networking_commands.md) — diagnostic toolkit (ping, traceroute, ss, dig)
- [`practical/01_networking_lab.md`](practical/01_networking_lab.md) — hands-on subnetting and VPC design