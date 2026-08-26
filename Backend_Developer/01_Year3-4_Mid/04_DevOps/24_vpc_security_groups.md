# VPC + Security Groups — Network Architecture

## VPC Kya Hai?

Virtual Private Cloud = AWS mein tumhara apna isolated network.
Default VPC har region mein hota hai (172.31.0.0/16), but production ke liye custom VPC banao.

```
AWS Region (ap-south-1)
└── VPC: 10.0.0.0/16
      ├── AZ-1a
      │     ├── Public Subnet:  10.0.1.0/24  ← ALB, Bastion Host
      │     └── Private Subnet: 10.0.3.0/24  ← EC2, RDS
      └── AZ-1b
            ├── Public Subnet:  10.0.2.0/24  ← ALB (second AZ)
            └── Private Subnet: 10.0.4.0/24  ← EC2, RDS (Multi-AZ standby)
```

---

## CIDR Notation

```
10.0.0.0/16  →  65,536 IPs  (entire VPC)
10.0.1.0/24  →  256 IPs     (one subnet)
10.0.1.0/28  →  16 IPs      (small subnet)

/16 = first 16 bits fixed, last 16 bits variable
```

AWS reserves 5 IPs per subnet (first 4 + last 1), so /24 = 251 usable.

---

## Public vs Private Subnet

| | Public Subnet | Private Subnet |
|---|---|---|
| Route to internet | Internet Gateway (direct) | NAT Gateway (outbound only) |
| Resources | ALB, Bastion Host, NAT GW | EC2 app servers, RDS, ElastiCache |
| Public IP | Yes (assigned) | No |
| Inbound from internet | Yes | No (only via ALB/Bastion) |

**Rule:** Database aur app servers KABHI public subnet mein mat daalo.

---

## Routing

### Internet Gateway (IGW)
- VPC attach hota hai → public subnet resources internet se accessible hoti hain
- Bidirectional: inbound + outbound

### NAT Gateway
- Private subnet resources ko internet jaane deta hai (software updates, external API calls)
- **Outbound only** — internet se koi seedha private subnet nahi aa sakta
- Highly available: NAT GW public subnet mein hota hai, Elastic IP ke saath

```
Private EC2 → NAT Gateway (public subnet) → IGW → Internet
Internet    → NAT Gateway tak nahi pahunch sakta (no inbound)
```

### Route Table
```
Public Subnet Route Table:
  10.0.0.0/16  →  local       (VPC internal traffic)
  0.0.0.0/0    →  igw-xxx     (internet ke liye)

Private Subnet Route Table:
  10.0.0.0/16  →  local
  0.0.0.0/0    →  nat-xxx     (outbound only)
```

---

## Security Groups (SG) — Stateful Firewall

**Stateful = agar inbound allow hai toh outbound response automatically allowed hai.**

```
Internet
   ↓ 443 (HTTPS)
ALB Security Group: allow inbound 443 from 0.0.0.0/0
   ↓ 8000 (Gunicorn)
EC2 Security Group: allow inbound 8000 from ALB-SG only
   ↓ 5432 (PostgreSQL)
RDS Security Group: allow inbound 5432 from EC2-SG only
```

**Security Group referencing (best practice):**
```
# RDS SG inbound rule:
Source: sg-xxxxxxxx (EC2's Security Group ID)  ← NOT a CIDR range
Port:   5432

# EC2 SG inbound rule:
Source: sg-yyyyyyyy (ALB's Security Group ID)
Port:   8000
```
Isse RDS sirf EC2 se accessible hai, IP change hone pe kuch update nahi karna.

### Key Properties
- **Allow rules only** — deny rule nahi hota SG mein
- **Stateful** — return traffic automatically allowed
- Multiple SGs ek instance pe lag sakti hain
- Default: outbound all allowed, inbound all denied

---

## Network ACL (NACL) — Stateless Firewall

| | Security Group | NACL |
|---|---|---|
| Level | Instance level | Subnet level |
| State | Stateful | Stateless |
| Rules | Allow only | Allow + Deny |
| Evaluation | All rules | Rule number order (lower first) |
| Default | Allow outbound, deny inbound | Allow all (default NACL) |

**Stateless = inbound allow karo, outbound bhi explicitly allow karna padega.**

**Typical use:** NACL se specific IPs block karo (e.g., known malicious ranges). Day-to-day control SG se karo.

---

## Bastion Host Pattern

SSH directly EC2 private subnet mein nahi ja sakte (no public IP).

```
Developer
   ↓ SSH port 22
Bastion Host (public subnet, Elastic IP)
   ↓ SSH port 22
EC2 (private subnet)
```

**Modern alternative:** AWS Systems Manager Session Manager — no SSH keys, no open port 22, audit trail.

---

## VPC Peering + Endpoints

### VPC Peering
- Do VPCs ke beech private connection
- Transitive nahi (A↔B, B↔C ne A↔C nahi hota)

### VPC Endpoint
- AWS services tak traffic internet se nahi jaata
```
EC2 (private subnet)
   ↓ VPC Endpoint (Gateway type for S3)
S3  ← traffic stays within AWS network
```
Types: Gateway (S3, DynamoDB — free), Interface (most other services — charged)

---

## Production Architecture Diagram

```
Internet
    ↓ HTTPS 443
Route 53
    ↓
ALB (Public Subnet, AZ-1a + AZ-1b)
    │
    ├── SG: allow 443 from 0.0.0.0/0
    │
    ↓ HTTP 8000
EC2 Auto Scaling Group (Private Subnet, AZ-1a + AZ-1b)
    │
    ├── SG: allow 8000 from ALB-SG
    ├── IAM Role: S3 + SQS + SecretsManager
    │
    ↓ 6379          ↓ 5432
ElastiCache Redis   RDS PostgreSQL (Primary + Standby)
    │                   │
    SG: allow 6379      SG: allow 5432
    from EC2-SG         from EC2-SG only
```

---

## Interview Q&A

**Q: Public aur Private subnet ka difference kya hai?**
A: Public subnet mein route table mein Internet Gateway ka route hota hai — resources seedha internet se accessible hain. Private subnet mein sirf NAT Gateway ka route hota hai — outbound internet ja sakta hai, lekin inbound nahi aa sakta. EC2 aur RDS private mein rakhte hain, sirf ALB public mein.

**Q: Security Group vs NACL?**
A: SG instance-level, stateful, allow-only. NACL subnet-level, stateless, allow+deny. Zyada cases mein SG kaafi hai. NACL tab use karo jab IP-level blocking chahiye (DDoS mitigation mein specific IPs drop karna).

**Q: EC2 private subnet mein hai, software update kaise karega?**
A: NAT Gateway ke through. Private subnet ki route table mein `0.0.0.0/0 → nat-xxx` hota hai. NAT GW public subnet mein hota hai, woh IGW se internet access karta hai. Inbound traffic nahi aata.

**Q: RDS publicly accessible nahi hai, app kaise connect karega?**
A: App (EC2) aur RDS dono same VPC ke private subnets mein hain. VPC internal routing se connect hote hain. RDS SG mein sirf EC2's SG se 5432 allow hota hai. Internet se koi RDS nahi dekh sakta.

**Q: VPC Endpoint kyun use karte hain?**
A: EC2 private subnet se S3 access karna ho toh normally traffic NAT GW → IGW → S3 jaata hai (internet pe). VPC Gateway Endpoint lagao → traffic AWS backbone pe rehta hai, faster + cheaper + no NAT charges.
