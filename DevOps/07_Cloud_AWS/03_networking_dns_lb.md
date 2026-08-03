# Cloud (AWS) — Networking, DNS & Load Balancing: VPC, Route 53, ALB/NLB
**DevOps Track · Phase 7: Cloud (AWS)**

## Quick Concepts

- **VPC** = Virtual Private Cloud — an isolated, private network you fully control inside AWS
- **Subnet** = a subdivision of a VPC's IP range, tied to exactly one Availability Zone
- **Public subnet** = has a route to an Internet Gateway (resources can have public IPs)
- **Private subnet** = no direct route to the internet (resources reach out only via NAT)
- **Route Table** = the rulebook deciding where traffic from a subnet is allowed to go
- **Internet Gateway (IGW)** = the VPC's door to the public internet, attached once per VPC
- **NAT Gateway** = lets private-subnet resources reach the internet *outbound* without being reachable *inbound*
- **Security Group (SG)** = stateful, instance-level firewall — allow rules only
- **NACL** = Network ACL — stateless, subnet-level firewall — allow and deny rules
- **Route 53** = AWS's managed DNS service, plus health checks and traffic routing policies
- **ALB** = Application Load Balancer — Layer 7 (HTTP/HTTPS aware)
- **NLB** = Network Load Balancer — Layer 4 (raw TCP/UDP, no protocol awareness)

---

## VPC — The Network Foundation

### Anatomy

```
VPC: 10.0.0.0/16                                    (up to 65,536 IPs)
│
├── AZ: ap-south-1a
│   ├── Public Subnet   10.0.1.0/24   → route to IGW
│   └── Private Subnet  10.0.11.0/24  → route to NAT Gateway (in the public subnet)
│
├── AZ: ap-south-1b
│   ├── Public Subnet   10.0.2.0/24   → route to IGW
│   └── Private Subnet  10.0.12.0/24  → route to NAT Gateway
│
└── AZ: ap-south-1c
    ├── Public Subnet   10.0.3.0/24   → route to IGW
    └── Private Subnet  10.0.13.0/24  → route to NAT Gateway
```

This 3-AZ, public+private pattern is the near-universal starting template for a production VPC — it's what Terraform's official `vpc` module and the AWS Landing Zone reference architecture both default to.

### Public vs Private Subnet — What Actually Makes the Difference

```
It is NOT about whether instances in the subnet have public IPs.
It IS about the subnet's ROUTE TABLE.

Public subnet's route table has:  0.0.0.0/0 → igw-xxxxx
Private subnet's route table has: 0.0.0.0/0 → nat-xxxxx   (or no route at all)

An instance with a public IP sitting in a subnet whose route table has
no route to an IGW is still unreachable from the internet — the route
table decides, not the presence of a public IP.
```

### What Goes Where

```
Public subnet   → load balancers, NAT Gateways, bastion hosts
                  (anything that legitimately needs to be internet-facing)

Private subnet  → application servers, databases, internal caches
                  (everything that should NEVER be directly internet-reachable —
                   they still reach the internet OUTBOUND for package updates,
                   API calls to third parties, etc. via the NAT Gateway)
```

### Internet Gateway vs NAT Gateway

| | Internet Gateway | NAT Gateway |
|---|---|---|
| Direction | Bidirectional — inbound AND outbound | Outbound-initiated only |
| Attached to | The VPC (one per VPC) | A specific subnet (usually public) |
| Used by | Public subnet resources | Private subnet resources needing outbound internet |
| Cost | Free | Hourly charge + per-GB data processing charge |
| Purpose | "The internet can reach me, I can reach it" | "I can reach the internet, it cannot initiate contact with me" |

**Cost gotcha worth knowing**: NAT Gateways are billed per-AZ and per-GB processed — a 3-AZ setup with 3 NAT Gateways running 24/7 is a real, recurring line item on the bill. A single shared NAT Gateway (cheaper, less resilient — one AZ failure takes out egress for the whole VPC) is a common cost-vs-resilience tradeoff discussion in interviews.

### Route Tables

```bash
aws ec2 create-route-table --vpc-id vpc-0123456789abcdef0

aws ec2 create-route \
  --route-table-id rtb-0abc123 \
  --destination-cidr-block 0.0.0.0/0 \
  --gateway-id igw-0def456

aws ec2 associate-route-table \
  --subnet-id subnet-0aaa111 \
  --route-table-id rtb-0abc123
```

Every subnet is associated with exactly one route table (a VPC's "main" route table is the default if none is explicitly associated). Read a route table like a list of "if destination matches X, send via Y" rules, most-specific match wins.

---

## Security Groups vs NACLs — The Comparison Interviewers Actually Ask For

| | Security Group | Network ACL |
|---|---|---|
| Scope | Attached to ENI / instance | Attached to a subnet, applies to everything in it |
| State | **Stateful** — response traffic auto-allowed | **Stateless** — must explicitly allow both directions |
| Rule types | Allow only | Allow AND Deny |
| Rule evaluation | All rules evaluated, most permissive wins | Rules evaluated **in number order**, first match wins |
| Default behavior | Deny all inbound, allow all outbound | Default NACL allows all; custom NACLs deny all until you add rules |
| Typical use | Primary, day-to-day firewalling — "can this app talk to that DB" | Secondary layer — subnet-wide IP blocklisting, extra defense-in-depth |

### The Stateful vs Stateless Distinction, Concretely

```
Security Group (stateful):
  Inbound rule:  allow 443/tcp from 0.0.0.0/0
  → a client's response packets (from your server back to the client)
    are AUTOMATICALLY allowed out, even with zero outbound rules,
    because the SG tracks connection state.

NACL (stateless):
  Inbound rule:  allow 443/tcp from 0.0.0.0/0
  → you must ALSO add an outbound rule allowing the ephemeral port
    range (typically 1024-65535/tcp) back to 0.0.0.0/0, or the
    response packets get dropped on the way out. NACLs don't
    remember that the inbound request happened.
```

This exact gap — "I opened port 443 inbound on my NACL and clients still can't connect" — is one of the most common real debugging scenarios and a favorite interview trap question. The fix is always: check the NACL's *outbound* rules for the ephemeral port range.

### Rule Ordering Matters for NACLs, Not for SGs

```
NACL rules have numbers (e.g. 100, 110, 200) and are evaluated in order,
lowest first — the FIRST matching rule wins, later rules are never
consulted for that packet.

  Rule 100: DENY 0.0.0.0/0 all traffic
  Rule 200: ALLOW 10.0.0.0/16 all traffic
  → rule 100 matches first for ANY traffic and denies it — rule 200
    never gets a chance to run. Numbering must go most-specific-first.

Security Groups have no such ordering concept — every applicable rule
across every attached SG is evaluated together, and if ANY rule allows
the traffic, it's allowed (deny doesn't exist as a rule type at all).
```

---

## Route 53 — DNS and Traffic Routing

### Routing Policies

| Policy | Behavior | Typical Use |
|---|---|---|
| **Simple** | One record, one (or a static list of) value(s), no health checks | A single-server dev environment |
| **Weighted** | Split traffic across multiple records by assigned weight (e.g. 90/10) | Canary releases, gradual migration to a new stack |
| **Latency-based** | Routes to the region with the lowest measured latency for the requester | Multi-region deployments serving global users |
| **Failover** | Primary record served while healthy; automatically switches to secondary on health check failure | Active-passive DR (disaster recovery) setup |
| **Geolocation** | Routes based on the requester's actual geographic location | Legal/content restrictions, localized content |
| **Geoproximity** | Like geolocation but with a "bias" to shift traffic volume between regions | Fine-tuned regional traffic shaping (requires Route 53 Traffic Flow) |
| **Multivalue Answer** | Returns multiple healthy IPs, client picks — lightweight DNS-level load balancing | Simple HA without a full load balancer, combined with health checks |

```bash
aws route53 change-resource-record-sets \
  --hosted-zone-id Z1234567890ABC \
  --change-batch '{
    "Changes": [{
      "Action": "CREATE",
      "ResourceRecordSet": {
        "Name": "api.example.com",
        "Type": "A",
        "SetIdentifier": "primary",
        "Failover": "PRIMARY",
        "AliasTarget": {
          "HostedZoneId": "Z35SXDOTRQ7X7K",
          "DNSName": "prod-alb-123456.ap-south-1.elb.amazonaws.com",
          "EvaluateTargetHealth": true
        },
        "HealthCheckId": "abcd1234-health-check-id"
      }
    }]
  }'
```

**Interview-relevant nuance**: an "Alias" record (AWS-specific extension of DNS) pointed at an ALB/CloudFront/S3 endpoint is preferred over a plain CNAME at the zone apex, because CNAMEs are disallowed at the root domain by the DNS spec, and Alias records resolve at the AWS DNS layer with no extra lookup cost (no TTL-bound external hop).

---

## Load Balancers — ALB vs NLB

| | ALB (Application Load Balancer) | NLB (Network Load Balancer) |
|---|---|---|
| OSI Layer | 7 (HTTP/HTTPS/gRPC) | 4 (TCP/UDP/TLS passthrough) |
| Routing awareness | Path-based, host-based, header-based routing rules | No content awareness — pure connection forwarding |
| Latency | Slightly higher (terminates and inspects HTTP) | Ultra-low, near line-rate |
| Static IP | No (DNS name only) | Yes — one static IP per AZ, or bring-your-own Elastic IP |
| Use case | Microservices routing, path-based APIs, WebSocket, gRPC | Extreme throughput, static IP requirement, non-HTTP protocols, preserving client source IP at the TCP layer |
| Target types | Instance, IP, Lambda function | Instance, IP, ALB (chaining) |
| SSL/TLS | Terminates TLS, can inspect/route on headers | Can terminate (TLS listener) or pure passthrough |
| Health checks | HTTP/HTTPS path-based (`GET /health`) | TCP/HTTP, connection-based |

### Path-Based Routing on ALB — Common Microservices Pattern

```
Listener :443 (HTTPS)
  ├── Rule: path = /api/orders/*      → target-group: orders-service
  ├── Rule: path = /api/users/*       → target-group: users-service
  ├── Rule: host = admin.example.com  → target-group: admin-service
  └── Default rule                    → target-group: web-frontend
```

This is how a single ALB fronts multiple backend microservices without needing a separate load balancer (and separate DNS record, separate cert) per service — a very common cost and simplicity win over one-LB-per-service.

### When NLB Beats ALB

```
- You need a fixed IP address for a partner's firewall allowlist
  (ALB's IP addresses can change; NLB gives you a stable one per AZ)
- Extremely high throughput / millions of requests per second with
  minimal added latency
- Non-HTTP protocol (raw TCP service, MQTT, custom binary protocol)
- You need to preserve the original client IP at the TCP layer without
  relying on X-Forwarded-For (which ALB adds but requires app-level trust)
```

---

## Senior Tip

```
A production-grade VPC design you should be able to sketch on a
whiteboard from memory:

  3 AZs, each with a public + private subnet pair
  IGW attached to the VPC
  NAT Gateway per AZ (or one shared, with the resilience tradeoff called out)
  ALB in the public subnets, targets (EC2/ECS tasks) in the private subnets
  RDS Multi-AZ in private subnets, security group only allows traffic
    from the app tier's security group (SG-to-SG reference, not a raw CIDR)
  Route 53 failover or latency routing at the DNS layer above it all

Referencing a security group BY security-group-ID in another SG's rule
(instead of a CIDR block) is a senior-level detail — it means the rule
still works correctly even if the app tier's IPs change on every deploy,
because ASG membership, not IP address, is what's being trusted.
```

## Interview Angle

**Q: A client says they can reach your ALB's HTTPS endpoint but requests to a specific internal microservice path always time out. Where do you look, in order?**

1. ALB listener rules — is there actually a rule matching that path, or is it silently falling to a default that points elsewhere?
2. Target group health checks — are the targets registered and passing health checks (`aws elbv2 describe-target-health`)?
3. Security group on the target instances/tasks — does it allow inbound from the ALB's security group on the target port?
4. If the target is in a private subnet, confirm the private subnet's route table and NACL aren't blocking the path (rare, but check NACL outbound ephemeral ports if NACLs were customized).

---

## Related

- [01_iam_compute_ec2.md](01_iam_compute_ec2.md) — Security Groups at instance launch time
- [02_storage_database.md](02_storage_database.md) — RDS subnet placement
- [04_containers_ecs_eks.md](04_containers_ecs_eks.md) — ALB target groups pointing at ECS/EKS services
- [../../Backend_Developer/00_Year0-2_Junior/01_Foundations/03_networking_fundamentals.md](../../Backend_Developer/00_Year0-2_Junior/01_Foundations/03_networking_fundamentals.md) — OSI layers, TCP/IP basics underneath this
