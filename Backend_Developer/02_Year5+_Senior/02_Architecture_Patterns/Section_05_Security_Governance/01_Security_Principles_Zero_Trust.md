# Lecture 1: Security Principles & Zero Trust

> *"Never trust. Always verify. Never assume."*

**Section 5 — Security & Governance in Architecture**

---

## 🎯 Is Lecture Mein Kya Seekhenge?

- **Why security is architectural** — not an afterthought
- **Evolution from perimeter security to Zero Trust**
- **CIA Triad** — Confidentiality, Integrity, Availability
- **Principle of Least Privilege** — minimum access only
- **Defense in Depth** — layered security
- **Zero Trust model** — never trust, always verify
- **Threat modeling** — STRIDE, DREAD frameworks
- **Identity as the new perimeter**
- **Cloud-native security challenges**
- **DevSecOps culture** — security shifted left
- **Challenges in Zero Trust adoption**

---

## 1. Evolving Security Paradigms

### The Old World — Perimeter Security

```
                      ┌────────────────┐
                      │   Firewall     │
   Internet ─────────►│   + VPN        │
                      │  (castle wall) │
                      └────────┬───────┘
                                │
                                ▼
                      ┌─────────────────┐
                      │  Trusted Zone   │
                      │                  │
                      │  ✓ Users         │
                      │  ✓ Servers       │
                      │  ✓ Databases     │
                      │  ✓ Everyone      │
                      │    inside is     │
                      │    "safe"        │
                      └─────────────────┘

   Assumption: "If you're inside the network, you're trusted"
```

### Why It Doesn't Work Anymore

```
Modern reality:
   ✗ Cloud services
   ✗ Remote work
   ✗ BYOD (Bring Your Own Device)
   ✗ Mobile users
   ✗ Third-party integrations
   ✗ Microservices
   
→ The perimeter is GONE.
→ Users, apps, data are EVERYWHERE.
```

### The New World — Zero Trust

```
              ┌──────────────────────────────────┐
              │      ZERO TRUST                   │
              │                                    │
   ┌────────┐ │   ┌──────────────────────┐       │ ┌──────────┐
   │ Phone  │─┤───►│ Identity & Context    │      │ │ Cloud    │
   └────────┘ │   │       Check           │       │ │  SaaS    │
              │   └──────────┬───────────┘       │ └──────────┘
   ┌────────┐ │              │                    │  ┌──────────┐
   │ Laptop │─┤              ▼                    │  │ Internal │
   └────────┘ │       Verify EVERY request        │  │   App    │
              │       regardless of location      │  └──────────┘
              └──────────────────────────────────┘

   Rule: "Never trust. Always verify."
```

### Side-by-Side Comparison

```
┌──────────────────────────┬──────────────────────────┐
│  PERIMETER SECURITY       │  ZERO TRUST              │
├──────────────────────────┼──────────────────────────┤
│  Trust inside network     │  Trust nothing            │
│  Firewall/VPN-centric     │  Identity-centric         │
│  One-time auth at boundary│  Continuous verification  │
│  Network location matters │  Context matters          │
│  "Castle and moat"         │  "Airport security"       │
│  Worked in 1990s/2000s    │  Works for cloud era      │
└──────────────────────────┴──────────────────────────┘
```

---

## 2. Core Security Principles

### The CIA Triad

```
                    ┌──────────────────────────┐
                    │   CONFIDENTIALITY        │
                    │   (Data stays private)   │
                    └─────────────┬────────────┘
                                  │
                    ┌─────────────┴────────────┐
                    │       CIA TRIAD          │
                    │  (Foundation of security)│
                    └─────────────┬────────────┘
                                  │
              ┌───────────────────┼───────────────────┐
              ▼                   ▼                   ▼
        ┌──────────┐         ┌──────────┐       ┌──────────┐
        │INTEGRITY │         │AVAILABLE │       │ (= CIA)  │
        │ Data not │         │   When   │       │          │
        │ tampered │         │ needed   │       │          │
        └──────────┘         └──────────┘       └──────────┘
```

### Each Pillar Explained

```
┌──────────────────────────────────────────────────────────────┐
│  CONFIDENTIALITY                                              │
│  Data stays private, only authorized parties see it           │
│                                                                │
│  Examples:                                                     │
│  • Encryption at rest                                          │
│  • Encryption in transit (TLS)                                 │
│  • Access controls                                             │
│  • Authentication                                              │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│  INTEGRITY                                                    │
│  Data not tampered with, accurate and complete                │
│                                                                │
│  Examples:                                                     │
│  • Digital signatures                                          │
│  • Hashing (SHA-256)                                           │
│  • Checksums                                                   │
│  • Audit logs                                                  │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│  AVAILABILITY                                                 │
│  System & data accessible when needed                          │
│                                                                │
│  Examples:                                                     │
│  • Load balancing                                              │
│  • DDoS protection                                             │
│  • Redundancy & failover                                       │
│  • Backups                                                     │
└──────────────────────────────────────────────────────────────┘
```

### Principle of Least Privilege (PoLP)

```
🔑 Give the MINIMUM access needed. Nothing more.

Examples:
   ✓ Read-only DB access for reporting services
   ✓ Single S3 bucket access for upload service
   ✓ No SSH access to production
   ✓ Time-limited admin privileges (just-in-time access)

❌ Anti-patterns:
   ✗ Everyone is admin
   ✗ Service has full DB access "just in case"
   ✗ Permanent credentials
   ✗ Shared service accounts
```

### Defense in Depth

```
🛡 Multiple layers of security, like an onion:

   Layer 1: Edge (WAF, DDoS protection, CDN)
        ↓
   Layer 2: Network (Firewall, segmentation)
        ↓
   Layer 3: Application (Authentication, validation)
        ↓
   Layer 4: Data (Encryption, access control)
        ↓
   Layer 5: Monitoring (Logs, alerts, SIEM)

If one layer fails → others still hold
   
   No single point of failure for security.
```

### Visual

```
   ┌─────────────────────────────────────┐
   │  🌐 Edge (CDN + WAF)                 │
   │  ┌────────────────────────────────┐ │
   │  │  🛡 Network (Firewall + Mesh)  │ │
   │  │  ┌──────────────────────────┐  │ │
   │  │  │  🔐 Application (Auth)    │  │ │
   │  │  │  ┌────────────────────┐  │  │ │
   │  │  │  │  💾 Data (Encrypt)  │  │  │ │
   │  │  │  │                     │  │  │ │
   │  │  │  └────────────────────┘  │  │ │
   │  │  └──────────────────────────┘  │ │
   │  └────────────────────────────────┘ │
   └─────────────────────────────────────┘
```

---

## 3. What Is Zero Trust?

### Definition

**Zero Trust = An architectural model that eliminates implicit trust and requires continuous verification of every access request, regardless of origin.**

### The Three Core Tenets

```
1. NEVER TRUST IMPLICITLY
   ✓ No "trusted network"
   ✓ Every request must be verified

2. ALWAYS VERIFY EXPLICITLY
   ✓ Check identity, device, context
   ✓ Continuous, not one-time

3. ASSUME BREACH
   ✓ Plan for compromise
   ✓ Limit blast radius
   ✓ Minimize lateral movement
```

### Visual: Zero Trust Decision Flow

```
   User ──► Request
            │
            ▼
   ┌─────────────────┐
   │ Identity Check  │
   │ Who are you?    │
   └────────┬────────┘
            │
            ▼
   ┌─────────────────┐
   │ Device Check    │
   │ Is your device  │
   │ secure?         │
   └────────┬────────┘
            │
            ▼
   ┌─────────────────┐
   │ Context Check   │
   │ Location, time, │
   │ behavior        │
   └────────┬────────┘
            │
            ▼
   ┌─────────────────┐
   │ Access Allowed? │
   └────┬───────┬────┘
        │       │
       YES     NO
        │       │
        ▼       ▼
   ┌──────┐ ┌────────┐
   │GRANT │ │ DENY   │
   └──────┘ └────────┘
```

### Continuous Authentication

```
Traditional:
   Login once → trusted for hours
   
Zero Trust:
   Every request → verify identity
                 → check device
                 → assess context
                 → allow or deny

Examples of context:
   ✓ Time of day
   ✓ Geographic location
   ✓ Network type (corporate, public WiFi, mobile)
   ✓ Device posture (patched, compliant)
   ✓ User behavior (typical patterns)
   ✓ Resource sensitivity
```

---

## 4. Principle of Least Privilege (Deep Dive)

### Why It Matters

```
If credentials are compromised:
   With ALL permissions → catastrophic damage
   With LEAST permissions → limited damage
   
   = Minimize blast radius
```

### Implementation Strategies

```
✓ Role-Based Access Control (RBAC)
   • Define roles: admin, editor, viewer
   • Assign users to roles
   • Roles have specific permissions

✓ Attribute-Based Access Control (ABAC)
   • Decisions based on attributes
   • Context-aware (time, location, etc.)
   • Fine-grained control

✓ Just-in-Time (JIT) Access
   • Permissions granted only when needed
   • Time-limited
   • Approval workflows

✓ Just-Enough-Access (JEA)
   • Minimum permissions for task
   • Scoped to specific resources
```

### Example: Database Access

```
❌ Anti-pattern:
   Service user has GRANT ALL PRIVILEGES on DB
   
✅ Best practice:
   Service user can:
   - SELECT from orders, users tables
   - INSERT into events table
   - CANNOT DELETE
   - CANNOT modify schema
   - CANNOT access other DBs
```

### Regular Audits

```
Permissions should be:
   ✓ Reviewed quarterly
   ✓ Reduced when no longer needed
   ✓ Documented & justified
   ✓ Logged & monitored
```

---

## 5. Threat Modeling

### Think Like an Attacker

```
To build secure systems:
   1. Identify critical assets
      "What's worth protecting?"
   
   2. Map entry points
      "Where can attackers get in?"
   
   3. Assess threats
      "What could go wrong?"
   
   4. Prioritize risks
      "What matters most?"
   
   5. Design mitigations
      "How do we defend?"
```

### STRIDE Framework

```
Identifies threats by category:

S - SPOOFING        → Impersonating someone
T - TAMPERING       → Modifying data
R - REPUDIATION     → Denying actions
I - INFORMATION DISCLOSURE → Leaking data
D - DENIAL OF SERVICE → Crashing system
E - ELEVATION OF PRIVILEGE → Gaining unauthorized access
```

### DREAD Framework (Ranking)

```
Score threats by:

D - DAMAGE             → How bad if exploited?
R - REPRODUCIBILITY    → How easily can it be repeated?
E - EXPLOITABILITY     → How hard is the attack?
A - AFFECTED USERS     → How many users impacted?
D - DISCOVERABILITY    → How easily found?

Each scored 1-10. Total helps prioritize.
```

### Example Threat Model

```
Asset: User payment data
Entry: Payment API endpoint

Threats (STRIDE):
   S - Attacker impersonates user → mitigate with strong auth
   T - Modify payment amount     → mitigate with HMAC signing
   R - User denies payment      → mitigate with audit logs
   I - Leak card numbers        → mitigate with PCI compliance, tokenization
   D - Flood API with requests  → mitigate with rate limiting
   E - Escalate to admin        → mitigate with least privilege

Each gets prioritized via DREAD.
```

---

## 6. Perimeter-Less Trust

### The Old Perimeter Is Gone

```
Once upon a time:
   ✓ Office building
   ✓ One network
   ✓ Clear boundary

Today:
   ✗ Office + remote
   ✗ Multi-cloud (AWS + Azure + GCP)
   ✗ SaaS apps (Salesforce, Office365, etc.)
   ✗ Mobile devices
   ✗ Third-party APIs
   ✗ Personal devices

→ No clear perimeter to defend.
```

### Lateral Movement

```
Old model:
   Attacker breaks ONE thing → still locked out
   
New reality:
   Attacker compromises ONE point → moves freely inside
   
Zero Trust prevents this:
   Every internal hop also requires authentication
   Service-to-service mTLS
   Network microsegmentation
```

### Security Travels With Data

```
In a perimeter-less world:
   ✓ Encryption everywhere (in transit + at rest)
   ✓ Identity-based access (not network-based)
   ✓ Continuous monitoring
   ✓ Data classification + DLP (Data Loss Prevention)
```

---

## 7. Identity as the New Perimeter

### Identity Is Everything

```
In Zero Trust, the PERIMETER is the IDENTITY.

Old: "Are you inside my network?"
New: "Who are you really?"
```

### Strong Identity Verification

```
✓ Username + password (necessary, not sufficient)
✓ Multi-factor authentication (MFA)
   - Something you know (password)
   - Something you have (phone, token)
   - Something you are (biometric)

✓ Passwordless authentication
   - FIDO2 / WebAuthn
   - Hardware keys
   - Passkeys (Apple, Google)

✓ Risk-based authentication
   - Step up for unusual context
   - "Logging in from a new device? Verify with phone"
```

### Access Control Models

```
RBAC (Role-Based):
   User assigned role → role has permissions
   Simple, predictable
   "John is admin → John can do everything admins do"

ABAC (Attribute-Based):
   Decision based on attributes
   Flexible, context-aware
   "Allow IF: user.department = finance AND time = work_hours"

ReBAC (Relationship-Based):
   Decision based on relationships
   "Allow IF: user owns this document"

PBAC (Policy-Based):
   Decision based on policies
   "Allow IF: policy_engine.evaluate(request) = ALLOW"
```

### When to Use Which

```
RBAC:
   ✓ Clear, static roles
   ✓ Enterprise apps
   ✗ Doesn't scale to fine-grained needs

ABAC:
   ✓ Dynamic, contextual decisions
   ✓ Complex multi-tenant systems
   ✗ Harder to audit

Combined:
   Most real systems use BOTH
   RBAC for broad strokes, ABAC for fine details
```

---

## 8. Cloud-Native Security Needs

### Cloud Brings New Challenges

```
Traditional infrastructure:
   ✓ Static
   ✓ Long-lived
   ✓ Network-bounded

Cloud-native:
   ✗ Dynamic (containers spin up/down)
   ✗ Ephemeral (minutes to hours)
   ✗ Cross-region
   ✗ Mixed services (own + third-party)

→ Need new security approaches.
```

### Key Cloud Security Concerns

```
1. DYNAMIC WORKLOADS
   • Containers, Kubernetes, serverless
   • Identity per workload (not per server)
   • Workload identity (SPIFFE/SPIRE)

2. INFRASTRUCTURE AS CODE
   • Security must also be code
   • Policy as Code (OPA/Rego)
   • Scan IaC before deployment

3. EPHEMERAL RESOURCES
   • Logs disappear with containers
   • Need centralized observability
   • Real-time threat detection

4. SHARED RESPONSIBILITY MODEL
   • Cloud provider secures THE CLOUD
   • YOU secure WHAT'S IN the cloud
   • Misconfigurations are #1 cause of breaches
```

### Cloud Security Best Practices

```
✓ Encrypt everything (rest + transit)
✓ Use IAM properly (least privilege)
✓ Enable logging for all services
✓ Set up automated alerts
✓ Use cloud-native security tools
   - AWS GuardDuty, Macie, Security Hub
   - Azure Defender, Sentinel
   - GCP Security Command Center
✓ Scan container images
✓ Network policies (CNI, Calico)
✓ Service mesh for mTLS (Istio, Linkerd)
```

---

## 9. Zero Trust Building Blocks

### The Foundation

```
Zero Trust isn't a product. It's an architecture.

You need:
   1. IDENTITY & ACCESS MANAGEMENT (IAM)
   2. NETWORK MICROSEGMENTATION
   3. CONTINUOUS MONITORING
   4. DEVICE SECURITY
```

### 1. Identity & Access Management (IAM)

```
Core of Zero Trust.

✓ Strong authentication (MFA, passwordless)
✓ Centralized identity provider (Okta, Auth0, Azure AD)
✓ Identity for every entity:
   - Users
   - Services
   - Devices
   - APIs
   - Workloads
```

### 2. Network Microsegmentation

```
Break network into small zones.

❌ Without:
   Compromise web tier → access entire network
   
✅ With:
   Compromise web tier → ONLY web tier accessible
   Database, internal APIs unreachable

Tools:
   ✓ Kubernetes Network Policies
   ✓ AWS Security Groups (fine-grained)
   ✓ Service Mesh (Istio AuthorizationPolicy)
   ✓ Software-defined perimeter
```

### 3. Continuous Monitoring

```
Zero Trust is not one-and-done.

Continuously:
   ✓ Observe user behavior
   ✓ Detect anomalies
   ✓ Flag unusual access patterns
   ✓ Update policies based on data

Tools:
   ✓ SIEM (Splunk, Sumo Logic, Datadog)
   ✓ UEBA (User & Entity Behavior Analytics)
   ✓ XDR (Extended Detection & Response)
```

### 4. Device Security

```
Verify device trustworthiness:
   ✓ Is it patched?
   ✓ Is it encrypted?
   ✓ Is antivirus running?
   ✓ Is it managed (corporate-owned)?
   
Failed device check → restricted access
   Maybe allow read-only, deny sensitive operations
```

---

## 10. DevSecOps Culture

### Shifting Security Left

```
Traditional:
   Security audit AFTER development → bugs found late, expensive to fix
   
DevSecOps:
   Security throughout development → catch issues early
```

### Shift Left Visualization

```
PLAN ──► CODE ──► BUILD ──► TEST ──► DEPLOY ──► OPERATE
   ↑       ↑       ↑          ↑         ↑          ↑
   │       │       │          │         │          │
Threat  Secure   SAST      DAST     Policy    Monitoring
Model    Code   Scans     Scans     Gates     Alerts
                Image
                Scans
                
   SECURITY EMBEDDED AT EVERY STAGE
```

### Key Practices

```
1. SECURE BY DESIGN
   ✓ Threat model new features
   ✓ Review architecture for security
   ✓ Design for least privilege

2. SECURE CODE
   ✓ Code reviews with security lens
   ✓ Linting & static analysis
   ✓ Security training for devs

3. AUTOMATED SECURITY
   ✓ SAST (Static Application Security Testing)
   ✓ DAST (Dynamic Application Security Testing)
   ✓ SCA (Software Composition Analysis)
   ✓ Container scanning
   ✓ IaC scanning

4. SECURE CI/CD
   ✓ Signed commits
   ✓ Signed artifacts
   ✓ Secret scanning
   ✓ Policy gates
   ✓ Limit deployment permissions
```

### Tooling Ecosystem

```
Code level:
   ✓ Snyk, SonarQube, Checkmarx (SAST)
   ✓ TruffleHog, GitGuardian (secret scanning)

Build/Deploy:
   ✓ Trivy, Clair (container scanning)
   ✓ Cosign (image signing)
   ✓ Open Policy Agent (policy as code)

Runtime:
   ✓ Falco (runtime threat detection)
   ✓ Sysdig, Aqua, Prisma Cloud
```

---

## 11. Challenges in Zero Trust Adoption

### Challenge 1: Legacy Systems

```
Problem:
   Old apps not built for fine-grained access
   Can't easily add MFA, modern auth
   
Solution:
   Reverse proxy for authentication
   API gateway for legacy systems
   Identity-aware proxies (Cloudflare Access, Google BeyondCorp)
   Incremental modernization
```

### Challenge 2: Cultural Resistance

```
Problem:
   "Why do I need to verify every time?"
   Friction = user complaints
   IT teams overwhelmed
   
Solution:
   ✓ Education about WHY
   ✓ Make it smooth (SSO + MFA, passwordless)
   ✓ Risk-based (only step-up when needed)
   ✓ Executive sponsorship
```

### Challenge 3: Identity Management Complexity

```
Problem:
   Hundreds of services
   Thousands of users
   Multiple devices per user
   External contractors
   
Solution:
   ✓ Centralized identity provider
   ✓ Identity governance tools
   ✓ Automated provisioning/deprovisioning
   ✓ Regular access reviews
```

### Challenge 4: Visibility Gap

```
Problem:
   Can't decide trust without context
   Can't enforce policies you can't see
   
Solution:
   ✓ Centralized logging
   ✓ SIEM/XDR for correlation
   ✓ Real-time analytics
   ✓ Behavioral baselines
```

### Challenge 5: Cost & Effort

```
Problem:
   New tools, new processes, retraining
   
Reality:
   ✓ Phased rollout (start with critical assets)
   ✓ Quick wins first (MFA everywhere)
   ✓ Cost of breach >> cost of Zero Trust
```

---

## 12. The Zero Trust Journey

### Phase 1: Foundation (Months 0-6)

```
✓ MFA everywhere
✓ Centralize identity (SSO via IdP)
✓ Inventory of assets, users, devices
✓ Network visibility tools
```

### Phase 2: Identity (Months 6-12)

```
✓ Strong authentication for all services
✓ Workload identity (SPIFFE, service mesh)
✓ Least privilege everywhere
✓ Just-in-time access for admin work
```

### Phase 3: Microsegmentation (Months 12-18)

```
✓ Network segmentation (per service, per workload)
✓ Service mesh with mTLS
✓ Identity-aware proxy
✓ Encrypt internal traffic
```

### Phase 4: Continuous Verification (Months 18+)

```
✓ Real-time risk scoring
✓ Behavioral analytics
✓ Automated policy adjustments
✓ Chaos engineering for security
```

---

## 13. Real-World Examples

### Google's BeyondCorp

```
Google pioneered Zero Trust internally (2011).

✓ No trusted internal network
✓ All access via identity-aware proxy
✓ Decisions based on:
   - User identity
   - Device state
   - Context
   - Resource sensitivity
✓ Works from anywhere (no VPN!)
```

### Microsoft

```
Adopted Zero Trust internally.
Now offers products implementing it:
   ✓ Azure AD Conditional Access
   ✓ Microsoft Defender suite
   ✓ Zero Trust Maturity Model
```

### NIST SP 800-207

```
US government standard for Zero Trust.
Defines:
   ✓ 7 tenets of Zero Trust
   ✓ Logical components
   ✓ Deployment scenarios
   ✓ Reference architecture
```

---

## 14. Common Anti-Patterns

### Anti-Pattern 1: VPN as Zero Trust

```
❌ "We have a VPN, so we're Zero Trust"

VPN = trust the network. Opposite of Zero Trust!
```

### Anti-Pattern 2: Buy a Tool, Done

```
❌ "We bought a Zero Trust solution"

Zero Trust = architecture, not a product
Tools enable it, but the design is yours.
```

### Anti-Pattern 3: All-or-Nothing

```
❌ "We'll roll out Zero Trust everywhere at once"

Result: Massive friction, project fails

✅ Phased approach
   - Start with critical assets
   - Quick wins first
   - Expand gradually
```

### Anti-Pattern 4: Static Policies

```
❌ Once defined, never updated

Threats evolve. Policies must too.

✅ Continuous review
✅ Behavioral feedback loops
✅ Auto-adjustment based on risk
```

### Anti-Pattern 5: Identity Silos

```
❌ Different identity systems for different apps

Result: Inconsistent enforcement, gaps

✅ Centralized identity provider
✅ Federate when needed
```

---

## 15. Summary — Key Takeaways

```
┌──────────────────────────────────────────────────────────────┐
│  ✅ Perimeter security is dead in the cloud era               │
│  ✅ Zero Trust = "Never trust. Always verify."                │
│  ✅ CIA Triad: Confidentiality, Integrity, Availability        │
│  ✅ Least Privilege: minimum access needed                     │
│  ✅ Defense in Depth: multiple security layers                 │
│  ✅ Identity is the new perimeter                              │
│  ✅ Threat modeling: STRIDE, DREAD frameworks                  │
│  ✅ DevSecOps: security shifted LEFT                           │
│  ✅ Cloud-native needs new approaches                          │
│  ✅ Zero Trust is a JOURNEY, not a destination                 │
└──────────────────────────────────────────────────────────────┘
```

### The Universal Rules

```
1. Never trust implicitly — verify EVERY request
2. Apply least privilege EVERYWHERE
3. Defense in depth — layer your protections
4. Identity is THE perimeter
5. Encrypt everything (rest + transit)
6. Continuous monitoring + behavioral analytics
7. Automate security (DevSecOps)
8. Threat model new designs proactively
9. Assume breach — limit blast radius
10. Security is a JOURNEY, not a one-time setup
```

---

## 🎬 What's Next?

In **Lecture 2**, we'll dive deep into **Authentication & Identity** — exploring OAuth 2.0 and OpenID Connect, the de-facto standards for delegated authorization and user identity in modern systems.

> **Practical file:** [01_Practical_Hands_On.md](01_Practical_Hands_On.md)

---

## 📚 References

- *Zero Trust Networks* — Evan Gilman, Doug Barth
- NIST SP 800-207 — Zero Trust Architecture
- Google BeyondCorp papers
- Microsoft Zero Trust Maturity Model
- CIS Critical Security Controls
- OWASP Top 10
