# OSI Model, TCP/IP, IP Addressing & Subnetting

**DevOps Track · Phase 3: Networking**

## Quick Concepts

- **OSI Model** = 7-layer conceptual model of how network communication is broken into stages
- **TCP/IP Model** = the 4-layer model the real internet actually runs on (OSI is teaching theory)
- **IP address** = numeric identifier for a device on a network (IPv4: 32-bit, dotted-decimal)
- **Subnet** = a logical subdivision of a network
- **CIDR** = Classless Inter-Domain Routing — `/24` notation expressing subnet size
- **Routing** = deciding the next hop to forward a packet toward its destination
- **NAT** = Network Address Translation — rewriting IP addresses as traffic crosses a boundary (e.g. private → public)
- **IPv6** = 128-bit successor to IPv4, designed to solve address exhaustion — vastly larger address space, different notation
- **VPC Peering** = a direct, private network connection between two VPCs, as if they were on the same network
- **Transit Gateway** = a managed hub that connects many VPCs (and on-prem networks) through one central point, instead of a full peering mesh

---

## Why This Matters for Backend/DevOps Work

```
- Designing a VPC: choosing CIDR ranges for subnets so they don't overlap
- Debugging "why can't service A reach service B" — is it a routing,
  NAT, or security-group/firewall problem?
- Understanding why a Docker container can reach the internet but
  isn't reachable FROM the internet (that's NAT + port mapping)
- Reading a Kubernetes CNI / AWS VPC diagram without your eyes glazing over
- Interview staple: "explain the OSI model" and "how does NAT work"
```

---

## The OSI Model — 7 Layers

| # | Layer | Function | Example Protocol / Device |
|---|---|---|---|
| 7 | **Application** | User-facing protocols, what your app actually speaks | HTTP, DNS, SMTP, FTP |
| 6 | **Presentation** | Data format/encoding, encryption, compression | TLS/SSL, JPEG, ASCII/UTF-8 |
| 5 | **Session** | Establishes/manages/terminates sessions between hosts | Sockets, SSH session, NetBIOS |
| 4 | **Transport** | End-to-end delivery, reliability, ordering | TCP, UDP |
| 3 | **Network** | Logical addressing and routing between networks | IP, ICMP, routers |
| 2 | **Data Link** | Physical addressing on the same local network | Ethernet, MAC address, switches |
| 1 | **Physical** | Raw bits over a physical medium | Cables, fiber, radio (Wi-Fi), NICs, hubs |

```
Mnemonic (top to bottom): "All People Seem To Need Data Processing"
  Application, Presentation, Session, Transport, Network, Data Link, Physical
```

### TCP/IP Model — What Actually Runs the Internet

| TCP/IP Layer | Maps to OSI Layers | Examples |
|---|---|---|
| **Application** | 5, 6, 7 | HTTP, DNS, SSH, FTP |
| **Transport** | 4 | TCP, UDP |
| **Internet** | 3 | IP, ICMP, routing |
| **Link (Network Access)** | 1, 2 | Ethernet, Wi-Fi, ARP |

```
OSI is the teaching/reference model (used constantly in interviews and
vendor documentation to LOCATE where a problem sits — "is this a
layer 3 or layer 7 issue?"). TCP/IP is the practical 4-layer model the
actual internet stack implements.
```

---

## IPv4 Addressing

### Structure

```
An IPv4 address is 32 bits, written as 4 octets: 192.168.1.10
Each octet: 0-255 (8 bits)

Binary:  11000000.10101000.00000001.00001010
Decimal:      192  .   168   .   1   .   10
```

### Historical Address Classes (mostly obsolete post-CIDR, but still asked in interviews)

| Class | Range | Default Mask | Typical Use |
|---|---|---|---|
| A | 1.0.0.0 – 126.255.255.255 | /8 (255.0.0.0) | Huge networks (few networks, tons of hosts) |
| B | 128.0.0.0 – 191.255.255.255 | /16 (255.255.0.0) | Medium networks |
| C | 192.0.0.0 – 223.255.255.255 | /24 (255.255.255.0) | Small networks (most common historically) |
| D | 224.0.0.0 – 239.255.255.255 | — | Multicast |
| E | 240.0.0.0 – 255.255.255.255 | — | Reserved/experimental |

### Public vs Private Ranges

```
Private (RFC 1918) — NOT routable on the public internet:
   10.0.0.0    – 10.255.255.255      (10.0.0.0/8)    — large orgs, AWS VPCs commonly use this
   172.16.0.0  – 172.31.255.255      (172.16.0.0/12) — Docker's default bridge network range
   192.168.0.0 – 192.168.255.255     (192.168.0.0/16) — home/small office routers

Everything else = public, globally routable (assigned by IANA/RIRs).

Special:
   127.0.0.0/8         loopback (127.0.0.1 = localhost)
   169.254.0.0/16       link-local (auto-assigned when DHCP fails; also AWS/GCP metadata service at 169.254.169.254)
```

---

## IPv6 — Why It Exists and What's Different

```
The entire IPv4 address space is ~4.3 billion addresses (2^32) —
already effectively exhausted for fresh direct allocation, which is
the whole reason NAT + private ranges (above) became mandatory rather
than optional. IPv6 fixes the root cause with a 128-bit address space
(2^128 addresses — commonly described as "enough for every grain of
sand on Earth to have its own IP, many times over").
```

### Notation

```
IPv4:  192.168.1.10                                     (4 decimal octets)
IPv6:  2001:0db8:0000:0000:0000:ff00:0042:8329             (8 groups of 4 hex digits)

Shortened (two rules, both allowed together):
  - Leading zeros in a group can be dropped:  0db8 → db8
  - ONE run of consecutive all-zero groups can collapse to "::"
    (only once per address — otherwise it's ambiguous how many
    zero-groups "::" stands for)

2001:0db8:0000:0000:0000:ff00:0042:8329
  →  2001:db8::ff00:42:8329

Loopback:      ::1                (equivalent to IPv4's 127.0.0.1)
Link-local:    fe80::/10           (equivalent role to IPv4's 169.254.0.0/16)
```

### What Actually Changes for a Backend/DevOps Engineer

```
- NAT becomes UNNECESSARY for address conservation — IPv6 has enough
  addresses that every device can get a real, globally routable one.
  (NAT66 exists for other reasons — mostly renumbering-avoidance and
  habit — but it isn't solving address scarcity anymore.)
- Security posture changes: without NAT hiding internal hosts behind
  one public IP, the FIREWALL (security group/NACL/host firewall)
  becomes the actual security boundary, not an incidental side effect
  of NAT. "NAT was never a security feature" is the correct senior
  framing here, but it's worth being deliberate about firewalling
  IPv6-enabled hosts explicitly rather than assuming NAT-equivalent
  protection.
- Cloud reality in 2026: AWS VPCs support DUAL-STACK mode (both IPv4
  and IPv6 CIDR blocks on the same VPC/subnet) — most orgs run
  dual-stack rather than IPv6-only, because plenty of external
  dependencies (some SaaS APIs, some legacy internal systems) are
  still IPv4-only. EKS supports IPv6 clusters directly, useful when
  you'd otherwise run out of IPv4 addresses in a large VPC (a real,
  common problem: a busy EKS cluster can exhaust a VPC's IPv4 address
  space with one IP per pod, well before it exhausts compute capacity).
```

```bash
ip -6 addr show          # Linux — show IPv6 addresses on this host
ping6 example.com          # or: ping -6 example.com
curl -6 https://example.com  # force curl to use IPv6
```

**Interview framing:** IPv6 questions are usually really testing "do you understand WHY NAT and private ranges exist" (address scarcity) rather than requiring you to do IPv6 subnetting math by hand — know the notation, know that NAT stops being necessary (not that it becomes impossible), and know that dual-stack is the practical default most teams actually run.

---

## Subnetting & CIDR

### CIDR Notation

```
192.168.1.0/24
             └── number of bits in the NETWORK portion of the address
                 remaining bits (32 - 24 = 8) = HOST bits = 2^8 = 256 addresses
                 (254 usable — network address + broadcast address are reserved)
```

### Common CIDR Blocks Cheat Sheet

| CIDR | Subnet Mask | Total Addresses | Usable Hosts |
|---|---|---|---|
| /32 | 255.255.255.255 | 1 | 1 (single host route) |
| /30 | 255.255.255.252 | 4 | 2 (common for point-to-point links) |
| /29 | 255.255.255.248 | 8 | 6 |
| /28 | 255.255.255.240 | 16 | 14 |
| /27 | 255.255.255.224 | 32 | 30 |
| /26 | 255.255.255.192 | 64 | 62 |
| /25 | 255.255.255.128 | 128 | 126 |
| /24 | 255.255.255.0 | 256 | 254 |
| /23 | 255.255.254.0 | 512 | 510 |
| /16 | 255.255.0.0 | 65,536 | 65,534 |

### Worked Subnetting Example

```
Given: 192.168.1.0/24  (256 addresses, 254 usable)
Task: split it into 4 equal subnets

Borrow 2 bits from the host portion (2^2 = 4 subnets) → /24 becomes /26

Subnet 1: 192.168.1.0/26     range 192.168.1.0   – 192.168.1.63    (usable: .1–.62,   broadcast .63)
Subnet 2: 192.168.1.64/26    range 192.168.1.64  – 192.168.1.127   (usable: .65–.126, broadcast .127)
Subnet 3: 192.168.1.128/26   range 192.168.1.128 – 192.168.1.191   (usable: .129–.190, broadcast .191)
Subnet 4: 192.168.1.192/26   range 192.168.1.192 – 192.168.1.255   (usable: .193–.254, broadcast .255)

Each /26 subnet = 64 addresses total, 62 usable
  (first address = network ID, last address = broadcast — both reserved)
```

### Worked Example: AWS VPC Subnetting

```
VPC CIDR: 10.0.0.0/16   (65,536 addresses)

  10.0.0.0/24    → public subnet A   (AZ-a)   — 256 addrs, hosts ALB/NAT gateway
  10.0.1.0/24    → public subnet B   (AZ-b)
  10.0.10.0/24   → private subnet A  (AZ-a)   — app servers, no direct internet route
  10.0.11.0/24   → private subnet B  (AZ-b)
  10.0.20.0/24   → database subnet A (AZ-a)   — RDS, most locked down

This is exactly why CIDR math matters day-to-day — you're carving up
a VPC's address space so subnets don't overlap and have room to grow.
```

### Quick Math Shortcut

```
Usable hosts per subnet = 2^(32 - prefix) - 2
   /24 → 2^8  - 2 = 254
   /27 → 2^5  - 2 = 30
   /30 → 2^2  - 2 = 2
```

---

## Routing Basics

```
A router forwards packets between different networks based on a
routing table — matching the destination IP against known routes and
picking the most specific (longest prefix) match.

Simplified routing table:
Destination        Gateway         Interface
0.0.0.0/0           203.0.113.1     eth0     ← default route ("everything else goes here")
10.0.0.0/16          -               eth1     ← directly connected, no gateway needed
192.168.1.0/24        10.0.0.5        eth1

"Longest prefix match" — if a packet matches both 0.0.0.0/0 and
10.0.0.0/16, the more specific /16 route wins.
```

```bash
ip route show           # Linux — show routing table
route -n                  # older equivalent
```

---

## Connecting Networks — VPC Peering & Transit Gateway

Routing (above) covers forwarding *within* one network. Real infrastructure usually needs traffic flowing *between* separate VPCs (a shared-services VPC, a data VPC, per-team VPCs) or between a VPC and an on-prem network — this section is how.

### VPC Peering — Direct, One-to-One

```
VPC A (10.0.0.0/16)  <--- peering connection --->  VPC B (10.1.0.0/16)

Each side adds a ROUTE in its own route table pointing the other
VPC's CIDR at the peering connection — peering itself doesn't route
anything automatically, it just makes the connection POSSIBLE; you
still explicitly add routes on both sides.

Key limitations:
  - NOT transitive: if A peers with B, and B peers with C, A CANNOT
    reach C through B. A needs its OWN direct peering connection to C.
    This is the single most common peering misunderstanding.
  - CIDRs must NOT overlap between the two VPCs (see the lab's
    worked example) — AWS refuses to establish the peering connection
    at all if they do, because it can't unambiguously route.
  - Works cross-region and cross-account, not just within one account.
```

```
A few peered VPCs: peering is simple and cheap (no extra device to
manage, free to create).
Many VPCs needing to talk to each other: peering becomes an N² mesh
problem — 5 VPCs all needing mutual connectivity is 10 separate
peering connections, 10 VPCs is 45. This is exactly the problem
Transit Gateway solves.
```

### Transit Gateway — Hub-and-Spoke for Many VPCs

```
                    ┌─────────────────┐
   VPC A ───────────┤                 │
   VPC B ───────────┤  Transit Gateway├─────── On-prem (via VPN/
   VPC C ───────────┤    (the hub)    │         Direct Connect)
   VPC D ───────────┤                 │
                    └─────────────────┘

Each VPC attaches to the Transit Gateway ONCE. The Transit Gateway's
own route table decides which attachments can reach which — turning
an N² peering mesh into N simple hub connections. Adding an 11th VPC
to the network means one new attachment, not ten new peering connections.
```

| | VPC Peering | Transit Gateway |
|---|---|---|
| Topology | Point-to-point, non-transitive | Hub-and-spoke, can be made transitive via its own route tables |
| Cost | Free (data transfer charges still apply) | Hourly charge per attachment + data processing charge |
| Scales to many VPCs | Poorly (N² connections) | Well (N attachments) |
| Connects to on-prem | No (needs separate VPN/Direct Connect) | Yes, directly — a common design is "everything, including on-prem, attaches to one Transit Gateway" |
| Use when | A handful of VPCs, simple/stable topology | Many VPCs, multi-account org, or on-prem needs to reach several VPCs uniformly |

### Site-to-Site VPN and Direct Connect — Reaching On-Prem

```
Site-to-Site VPN    → encrypted tunnel over the public internet between
                       your VPC (via a Virtual Private Gateway) and an
                       on-prem router — fast to set up, variable
                       latency/throughput since it rides the public internet
Direct Connect        → a dedicated, private physical network link from
                       your data center to AWS — consistent low latency
                       and bandwidth, but a real provisioning lead time
                       (physical cross-connect) and ongoing cost

Common pattern: Direct Connect as primary (fast, consistent), Site-to-
Site VPN as an automatic FAILOVER path if the dedicated link drops —
you get most of the cost benefit of a dedicated line with a cheap
backup for the rare outage.
```

**Interview framing:** "peering vs Transit Gateway" is really a question about topology and scale — a strong answer names the N² mesh problem explicitly ("at 3-4 VPCs peering is fine, past that you're maintaining a combinatorial mess of route table entries, which is when Transit Gateway earns its per-attachment cost").

---

## NAT — Network Address Translation

```
NAT rewrites IP addresses (and often ports) as traffic crosses a
boundary — typically translating private, non-routable addresses to
a public one so many internal hosts can share one external IP.

SNAT (Source NAT) — rewrites the SOURCE address. Used for OUTBOUND
traffic from private hosts to the internet.

   [App server 10.0.10.5] --SNAT--> [NAT Gateway public IP 3.4.5.6] --> Internet
   Outbound packet: src=10.0.10.5 → rewritten to src=3.4.5.6
   Return traffic comes back to 3.4.5.6, NAT gateway maps it back to 10.0.10.5

DNAT (Destination NAT) — rewrites the DESTINATION address. Used for
INBOUND traffic, e.g. exposing an internal service to the outside
world (port forwarding, load balancer to backend).

   Internet --> [Public IP 3.4.5.6:443] --DNAT--> [Internal app 10.0.10.5:8000]
   Inbound packet: dst=3.4.5.6:443 → rewritten to dst=10.0.10.5:8000
```

```
Real-world mapping:
  - AWS NAT Gateway in a public subnet = SNAT for private subnet
    instances to reach the internet (e.g. pip install, apt update)
    without being directly reachable FROM the internet.
  - AWS ALB/NLB forwarding to a target group = effectively DNAT —
    public endpoint maps to private backend IP:port.
  - Docker's default bridge networking uses iptables SNAT/DNAT rules
    to let containers reach the internet and to publish container
    ports to the host (-p 8080:80).
```

---

## Senior Tip

```
1. When debugging "can't reach service X," locate the OSI layer first:
   - No ping at all → layer 3 (routing/firewall) or layer 1/2 (physical/link)
   - Ping works, port closed → layer 4 (nothing listening, or a firewall rule)
   - Port open, garbage response → layer 7 (app bug, wrong protocol)
2. Always sketch subnet CIDR ranges on paper/whiteboard before creating
   a VPC — overlapping CIDRs between VPCs you later peer/connect is a
   painful redo.
3. Private IP ranges (10.x, 172.16-31.x, 192.168.x) are never
   internet-routable — that's WHY NAT exists, not an accident.
```

## Interview Angle

**Q: Explain the OSI model in one sentence per layer, and why does anyone care about it if TCP/IP is what actually runs?**
OSI is the diagnostic vocabulary — when you say "this is a layer 4 vs layer 7 problem" everyone in networking/DevOps instantly knows what class of tool to reach for (firewall/port vs app-level debugging). TCP/IP is the simpler 4-layer model that maps to what's actually implemented in the internet stack.

**Q: How many usable hosts in a /27 subnet, and how do you calculate it?**
2^(32-27) - 2 = 2^5 - 2 = 30. Subtract 2 for the reserved network address and broadcast address.

**Q: Explain SNAT vs DNAT with a concrete AWS example.**
SNAT rewrites the source address — an EC2 instance in a private subnet reaching the internet via a NAT Gateway has its private source IP rewritten to the NAT Gateway's public IP. DNAT rewrites the destination — an ALB receiving a request on its public IP:443 and forwarding it to a target's private IP:8000 is destination NAT.

**Q: Why can't you just use a public IP directly on every server instead of dealing with NAT/private ranges?**
IPv4 address space is limited (~4.3 billion addresses, already exhausted for direct allocation). Private ranges + NAT let organizations run millions of internal hosts behind a handful of public IPs — plus it's a security boundary: private hosts aren't directly reachable from the internet unless explicitly NAT'd/forwarded.

**Q: VPC A is peered with VPC B, and VPC B is peered with VPC C. Can A reach C?**
No — VPC peering is not transitive. A needs its own direct peering connection (or a shared Transit Gateway attachment) to reach C; traffic can't hop through B's peering connections. This is the single most common misunderstanding about how peering works.

**Q: You have 8 VPCs that all need to talk to each other, plus an on-prem data center. Peering or Transit Gateway?**
Transit Gateway. 8 VPCs needing full mutual connectivity via peering is 28 separate peering connections (N(N-1)/2), each with its own route table entries on both sides — a maintenance burden that grows quadratically. Transit Gateway turns this into 8 simple hub attachments (plus one for the on-prem VPN/Direct Connect link), and adding a 9th VPC later is one new attachment instead of 8 new peering connections.

**Q: Does IPv6 mean NAT becomes obsolete?**
NAT becomes *unnecessary for address conservation*, since IPv6's address space is large enough that every device can have a real, globally routable address — but that also means the firewall (security groups, NACLs, host firewall) becomes the actual, deliberate security boundary, rather than incidentally relying on NAT to hide internal hosts. "NAT was never really a security feature to begin with" is the correct senior framing, but IPv6 removes the accidental protection NAT happened to provide.

---

## Related

- [`../07_Cloud_AWS/03_networking_dns_lb.md`](../07_Cloud_AWS/03_networking_dns_lb.md) — Security Groups vs NACLs in full depth, VPC/subnet anatomy, Route 53 DNS record types and routing policies
- [`../01_Linux/06_networking_commands.md`](../01_Linux/06_networking_commands.md) — the diagnostic toolkit (ping, traceroute/mtr, ss/netstat, dig) for actually debugging what this file describes conceptually
- [`practical/01_networking_lab.md`](practical/01_networking_lab.md) — Lab 4 subnets a VPC by hand; its overlapping-CIDR solution note is the direct consequence of the VPC Peering section above
