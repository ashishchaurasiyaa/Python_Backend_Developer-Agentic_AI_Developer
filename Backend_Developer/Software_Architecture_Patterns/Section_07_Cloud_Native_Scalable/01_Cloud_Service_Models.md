# Lecture 1: Cloud Service Models — IaaS, PaaS, SaaS, and Beyond

> *"The more you abstract, the faster you can move. But sometimes you need that control."*

**Section 7 — Cloud-Native & Scalable Architecture Styles**

---

## 🎯 Is Lecture Mein Kya Seekhenge?

- **Cloud computing as a layered abstraction**
- **IaaS** — Infrastructure as a Service (raw compute)
- **PaaS** — Platform as a Service (managed runtime)
- **SaaS** — Software as a Service (ready-to-use apps)
- **Side-by-side comparison** — control vs convenience
- **Serverless computing** — beyond traditional models
- **Containers** in cloud services
- **CDNs** — content delivery networks
- **Trade-offs** — abstraction vs control

---

## 1. Introduction to Cloud Service Models

### The Big Picture

```
                      LESS control
                          ▲
                          │
          ┌───────────────┴────────────────┐
          │ SaaS                            │  End users
          │ Gmail, Salesforce, Office 365   │
          ├────────────────────────────────┤
          │ PaaS                            │  Software developers
          │ Heroku, App Engine, Beanstalk   │
          ├────────────────────────────────┤
          │ IaaS                            │  IT administrators
          │ AWS EC2, Azure VM, GCE          │
          └────────────────────────────────┘
                          │
                          ▼
                      MORE control
```

### Core Idea

**Cloud services deliver computing over the internet at different LAYERS of abstraction.**

```
✓ The more you abstract → faster you move
✓ The less you abstract → more control
✓ Right choice impacts:
   - Cost
   - Development speed
   - Maintenance overhead
   - Security responsibility
```

### Strategic Lever

```
Choosing service model = strategic decision

Not just technical - affects:
   ✓ Speed of delivery
   ✓ Team responsibilities
   ✓ Compliance posture
   ✓ Total cost of ownership
```

---

## 2. IaaS — Infrastructure as a Service

### Definition

**IaaS = Raw computing resources (VMs, networks, storage) delivered over the cloud.**

### The Stack

```
┌──────────────┐    ← You manage
│     App      │       ✓ App
└──────┬───────┘       ✓ Runtime
       │                ✓ OS config
┌──────┴───────┐
│  Operating   │
│   System     │
└──────┬───────┘
       │
┌──────┴───────┐
│  Virtual     │    ← Cloud provider
│  Machine     │       gives you this
└──────┬───────┘
       │
┌──────┴───────┐
│ Hypervisor   │    ← Provider manages
└──────┬───────┘       (you don't touch)
       │
┌──────┴───────┐
│  Hardware    │
└──────────────┘
```

### Characteristics

```
✓ Maximum control + flexibility
✓ Custom OS, middleware, runtime
✓ Pay-per-use compute
✓ Spin up + tear down on demand

✗ You manage provisioning
✗ You patch OS
✗ You scale manually (or set up autoscaling)
✗ You monitor everything
```

### Examples

```
✓ AWS EC2
✓ Google Compute Engine
✓ Azure Virtual Machines
✓ DigitalOcean Droplets
✓ Linode
```

### Best For

```
✓ Custom infrastructure needs
✓ Migrating legacy apps
✓ Regulated workloads (full control needed)
✓ When you have time + expertise
✗ Quick prototyping (overhead too high)
```

---

## 3. PaaS — Platform as a Service

### Definition

**PaaS = Managed platform abstracting OS + runtime, letting you focus on code.**

### Traditional IaaS vs Modern PaaS

```
┌──────────────────┐         ┌──────────────────┐
│  Traditional IaaS │         │  Modern PaaS      │
├──────────────────┤         ├──────────────────┤
│  Developer        │         │  Developer        │
│       │           │         │       │           │
│       ▼           │         │       ▼           │
│  Manage VM        │         │  Push Code        │
│       │           │         │       │           │
│       ▼           │         │       ▼           │
│  Configure OS     │         │  Platform Handles │
│       │           │         │  Infrastructure   │
│       ▼           │         │                   │
│  Setup Runtime    │         │  (Done!)          │
│       │           │         │                   │
│       ▼           │         │                   │
│  Deploy App       │         │                   │
└──────────────────┘         └──────────────────┘
```

### Characteristics

```
✓ Abstracts OS + runtime
✓ Focus on app logic only
✓ Auto-scaling built in
✓ Auto-patching by provider
✓ Faster deployment

✗ Less control over runtime
✗ Provider's choices on languages/versions
✗ Some apps don't fit "12-factor" model
```

### Examples

```
✓ Heroku
✓ Google App Engine
✓ Azure App Service
✓ AWS Elastic Beanstalk
✓ Vercel (for Next.js)
✓ Railway
✓ Render
```

### Best For

```
✓ Rapid prototyping
✓ Web applications
✓ MVPs and startups
✓ Apps fitting standard patterns
✗ Custom OS / kernel needs
```

---

## 4. SaaS — Software as a Service

### Definition

**SaaS = Fully managed applications delivered over the internet.**

### Characteristics

```
✓ Zero infrastructure management
✓ Zero deployment
✓ Auto updates
✓ Pay subscription (per user/month)
✓ Login + use

✗ No control over features
✗ Locked into provider
✗ Customization limited
✗ Data lives outside your infrastructure
```

### Examples

```
✓ Gmail
✓ Microsoft 365
✓ Salesforce
✓ Slack
✓ Dropbox
✓ Notion
✓ Zoom
```

### Best For

```
✓ Commodity functions (email, files, CRM)
✓ When building yourself adds NO value
✓ Quick adoption
✗ Core differentiators (build it yourself)
✗ Regulated data (sometimes)
```

---

## 5. Side-by-Side Comparison

### The Trade-Off Spectrum

```
┌─────────────────────────────────────────────────────────────┐
│                                                              │
│   IaaS         PaaS           SaaS                          │
│   ─────────────────────────────                              │
│   ▲                                                          │
│   │ Control                                                  │
│   │                                                          │
│   ▼                                                          │
│                                                              │
│             ▼ Convenience ▼                                  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Detailed Comparison

```
┌──────────────────┬──────────┬──────────┬──────────┐
│  ASPECT           │  IaaS     │  PaaS     │  SaaS    │
├──────────────────┼──────────┼──────────┼──────────┤
│  Control          │  Max      │  Medium   │  Min     │
│  Setup time       │  Long     │  Short    │  None    │
│  Manage OS?       │  Yes      │  No       │  No      │
│  Manage runtime?  │  Yes      │  No       │  No      │
│  Manage app?      │  Yes      │  Yes      │  No      │
│  Cost predictable │  Medium   │  High     │  Very    │
│  Vendor lock-in   │  Low      │  Medium   │  High    │
│  Scaling          │  Manual   │  Auto     │  Auto    │
│  Best for         │  Custom   │  Apps     │  Generic │
└──────────────────┴──────────┴──────────┴──────────┘
```

### Responsibility Matrix

```
   ┌─────────────────────────────────────────────────┐
   │  RESPONSIBILITY        │ IaaS │ PaaS │ SaaS    │
   ├────────────────────────┼──────┼──────┼─────────┤
   │  Application code       │  ✓    │  ✓    │  -      │
   │  Data                   │  ✓    │  ✓    │  ✓      │
   │  Runtime                │  ✓    │  -    │  -      │
   │  OS                     │  ✓    │  -    │  -      │
   │  Virtualization         │  -    │  -    │  -      │
   │  Servers                │  -    │  -    │  -      │
   │  Storage                │  -    │  -    │  -      │
   │  Networking             │  -    │  -    │  -      │
   └────────────────────────┴──────┴──────┴─────────┘

   ✓ = You manage
   - = Cloud provider manages
```

---

## 6. Serverless Computing

### Beyond Traditional Models

**Serverless = You don't manage servers AT ALL, even VMs.**

### How It Works

```
   You write small functions
        │
        ▼
   Functions run in response to EVENTS
        │
        ▼
   You pay only when code runs
        │
        ▼
   Auto-scales from 0 to thousands
```

### Characteristics

```
✓ Zero infrastructure management
✓ Pay-per-execution (not per server!)
✓ Auto-scaling (zero to ∞)
✓ Event-driven by design

✗ Cold starts
✗ Execution time limits
✗ Vendor lock-in
✗ Hard to debug
```

### Examples

```
✓ AWS Lambda
✓ Azure Functions
✓ Google Cloud Functions
✓ Cloudflare Workers
✓ Vercel Functions
```

### Best For

```
✓ Event-driven workloads
✓ Variable / unpredictable traffic
✓ Microservices
✓ Glue code between SaaS services
✗ Long-running tasks
✗ High-throughput real-time systems
```

---

## 7. Containers and Cloud Services

### What Containers Bring

```
✓ Package app + dependencies in single unit
✓ Consistent across environments
✓ Lightweight (vs VMs)
✓ Fast startup (seconds vs minutes)
✓ Portable across clouds
```

### Containers vs VMs

```
   VM:                    Container:
   ┌──────────┐          ┌──────────┐
   │   App    │          │   App    │
   ├──────────┤          ├──────────┤
   │  Libs    │          │  Libs    │
   ├──────────┤          ├──────────┤
   │   OS     │          │ (shares  │
   │ (full!)  │          │  host OS)│
   ├──────────┤          ├──────────┤
   │Hypervisor│          │  Docker  │
   ├──────────┤          ├──────────┤
   │ Hardware │          │ Hardware │
   └──────────┘          └──────────┘
   
   Size: GBs              Size: MBs
   Boot: minutes          Boot: seconds
```

### Where Containers Fit

```
IaaS:
   ✓ Run + manage containers yourself
   ✓ Full control
   
PaaS:
   ✓ Platform manages container orchestration
   ✓ Apps just packaged as containers
   
FaaS:
   ✓ Some providers run functions in containers
   ✓ You don't see them
```

### Container Orchestration

```
Kubernetes = the de facto standard
   ✓ Deployment
   ✓ Scaling
   ✓ Networking
   ✓ Service discovery
   ✓ Self-healing
   
(Deep dive in Lecture 4!)
```

---

## 8. CDNs — Content Delivery Networks

### What They Do

**CDNs = globally distributed caches that bring content closer to users.**

### How It Works

```
Without CDN:
   User (India) → Origin server (US) → User
   Latency: 200-300ms

With CDN:
   User (India) → CDN edge (Mumbai) → User
   Latency: 10-30ms (10x faster!)
   
   Edge serves CACHED content
   Origin only hit on cache miss
```

### What CDNs Cache

```
✓ Static images
✓ JavaScript files
✓ CSS files
✓ Videos
✓ Fonts
✓ HTML (sometimes)
```

### Benefits

```
✓ Lower latency
✓ Reduced origin load
✓ Better availability
✓ DDoS protection
✓ Bandwidth savings
```

### Examples

```
✓ Cloudflare
✓ AWS CloudFront
✓ Akamai
✓ Google Cloud CDN
✓ Fastly
✓ Bunny CDN
```

### CDN-Agnostic

```
CDN works with ALL service models:
   ✓ IaaS — speed up your VM-hosted app
   ✓ PaaS — speed up your platform app
   ✓ SaaS — many SaaS use CDNs underneath
```

---

## 9. Choosing the Right Model

### Decision Framework

```
Question 1: Do you have specific OS/kernel needs?
   YES → IaaS

Question 2: Are you building a custom app?
   YES → PaaS or IaaS
   NO  → SaaS

Question 3: Is the workload event-driven?
   YES → Serverless / FaaS

Question 4: How much DevOps capacity do you have?
   LOW    → SaaS or PaaS
   MEDIUM → PaaS
   HIGH   → IaaS

Question 5: How critical is speed-to-market?
   VERY    → SaaS
   HIGH    → PaaS / Serverless
   MEDIUM  → IaaS
```

### Stage-Based Recommendations

```
EARLY STARTUP:
   ✓ SaaS for commodity (email, CRM, payments)
   ✓ PaaS for core app
   ✓ Move fast, focus on product

GROWING COMPANY:
   ✓ PaaS for non-core services
   ✓ IaaS for core differentiators
   ✓ Serverless for event-driven work

ENTERPRISE:
   ✓ Hybrid approach
   ✓ IaaS for compliance-heavy workloads
   ✓ PaaS for new apps
   ✓ SaaS for HR, finance, etc.
```

### Hybrid Reality

```
Most companies use MULTIPLE models:
   ✓ Slack (SaaS) for communication
   ✓ Heroku (PaaS) for staging
   ✓ AWS EC2 (IaaS) for production
   ✓ Lambda (Serverless) for cron jobs
   ✓ CloudFront (CDN) for assets
   
→ Match each workload to its ideal model.
```

---

## 10. Cost Considerations

### IaaS

```
Costs:
   ✓ Compute (per hour)
   ✓ Storage (per GB)
   ✓ Network egress (per GB)
   ✓ Reserved vs on-demand
   
Wastage:
   ✗ Idle VMs still cost money
   ✓ Use auto-scaling + spot instances
```

### PaaS

```
Costs:
   ✓ Per app instance (dyno, etc.)
   ✓ Or per "compute unit"
   ✓ Add-ons (DBs, etc.)
   
Often:
   ✓ Predictable monthly billing
   ✗ Can be 2-3x more than equivalent IaaS
```

### SaaS

```
Costs:
   ✓ Per user / month
   ✓ Sometimes per seat per feature
   
Beware:
   ✗ Costs scale with users
   ✗ Can become expensive at large scale
```

### Serverless

```
Costs:
   ✓ Per invocation
   ✓ Per GB-second of memory
   ✓ Per network call
   
Risks:
   ✗ Runaway costs from bugs/spikes
   ✓ Set budget alerts!
```

---

## 11. Security Considerations

### Shared Responsibility Model

```
┌──────────────────────────────────────────────┐
│  IaaS                                          │
│  ✓ Cloud provider: physical security, hypervisor│
│  ✓ You: everything ABOVE that (OS, app, data) │
├──────────────────────────────────────────────┤
│  PaaS                                          │
│  ✓ Cloud provider: + OS + runtime              │
│  ✓ You: app + data                             │
├──────────────────────────────────────────────┤
│  SaaS                                          │
│  ✓ Cloud provider: almost everything           │
│  ✓ You: data + access control                  │
└──────────────────────────────────────────────┘
```

### Always YOUR Responsibility

```
✓ Application security (vulns, bugs)
✓ Identity + access management
✓ Data encryption (when needed)
✓ Compliance posture
✓ User access controls
```

---

## 12. Vendor Lock-In

### The Risk

```
Easy to start = hard to leave

✗ SaaS: data trapped in their format
✗ PaaS: app uses their proprietary APIs
✗ Serverless: tightly coupled to provider
✓ IaaS: most portable (especially with containers)
```

### Mitigation Strategies

```
✓ Use open standards where possible (OpenAPI, etc.)
✓ Build with containers (portable)
✓ Use Terraform / Pulumi (cloud-agnostic IaC)
✓ Avoid proprietary services for core logic
✓ Plan migration paths upfront
```

---

## 13. Future Trends

### Trend 1: Serverless Containers

```
Cloud Run, AWS Fargate, Azure Container Apps:
   ✓ Combine containers + serverless
   ✓ Pay per use, no servers
   ✓ Standard containers run as functions
```

### Trend 2: Edge Computing

```
Code runs at CDN edge nodes:
   ✓ Cloudflare Workers
   ✓ Vercel Edge Functions
   ✓ Even lower latency than regional cloud
```

### Trend 3: Multi-Cloud

```
Avoid lock-in by using multiple clouds:
   ✓ Tools: Anthos, Azure Arc, AWS Outposts
   ✓ Compute portable via Kubernetes
   ✗ Operational complexity high
```

### Trend 4: Platform Engineering

```
Internal Developer Platforms (IDPs):
   ✓ Build your own PaaS using IaaS
   ✓ Curated developer experience
   ✓ Self-service infrastructure
```

---

## 14. Summary — Key Takeaways

```
┌──────────────────────────────────────────────────────────────┐
│  ✅ Cloud services come in layers: IaaS, PaaS, SaaS           │
│  ✅ Trade-off: control vs convenience                          │
│  ✅ IaaS: max control, max responsibility                      │
│  ✅ PaaS: focus on code, platform handles rest                 │
│  ✅ SaaS: ready-to-use apps, zero infrastructure work          │
│  ✅ Serverless: pay-per-execution, event-driven                │
│  ✅ Containers + Kubernetes: cloud-native standard             │
│  ✅ CDNs: bring content closer to users                        │
│  ✅ Most systems use HYBRID of all of these                    │
│  ✅ Match each workload to its ideal model                     │
└──────────────────────────────────────────────────────────────┘
```

### The Universal Rules

```
1. Start with HIGHEST abstraction that fits
2. Move down (more control) only when needed
3. Use SaaS for commodity functions
4. Use PaaS for standard apps
5. Use IaaS for custom requirements
6. Use Serverless for event-driven workloads
7. Use Containers + K8s as the standard
8. Use CDN for static content
9. Be aware of vendor lock-in
10. Match the model to workload + team maturity
```

---

## 🎬 What's Next?

In **Lecture 2**, we'll explore the **12-Factor App methodology** — the gold standard for building cloud-native, scalable applications.

> **Practical file:** [01_Practical_Hands_On.md](01_Practical_Hands_On.md)

---

## 📚 References

- *Cloud Native Patterns* — Cornelia Davis
- AWS Well-Architected Framework
- *Cloud Computing: Concepts, Technology & Architecture* — Thomas Erl
- Google Cloud documentation
- Azure architecture center
- *Designing Distributed Systems* — Brendan Burns
