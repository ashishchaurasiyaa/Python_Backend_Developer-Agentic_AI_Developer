# Lecture 3: Serverless Architecture

> *"Serverless doesn't mean no servers. It means you don't have to think about them."*

**Section 7 — Cloud-Native & Scalable Architecture Styles**

---

## 🎯 Is Lecture Mein Kya Seekhenge?

- **What is serverless** — beyond the buzzword
- **Core traits** of serverless platforms
- **Function as a Service (FaaS)** — the compute model
- **Event triggers** — what activates functions
- **Function lifecycle** — cold start to response
- **Cost model** — pay per execution
- **Cold starts** — performance considerations
- **Vendor lock-in** — the trade-off
- **Use cases & anti-patterns** — when to use it
- **Design principles** — for effective serverless

---

## 1. What Is Serverless?

### The Name Is Misleading

```
"Serverless" doesn't mean NO servers.
It means YOU don't have to think about them.

✓ Infrastructure: managed by provider
✓ Provisioning: automatic
✓ Scaling: automatic
✓ Patching: automatic
✓ You: write code, that's it
```

### Key Characteristics

```
✓ NO server management
✓ PAY-PER-EXECUTION billing
✓ Automatic scaling (zero to ∞)
✓ EVENT-DRIVEN by nature
```

### Compared to Traditional

```
Traditional:
   ✗ Provision VMs / containers
   ✗ Pay for idle resources 24/7
   ✗ Manage OS, runtime, scaling
   ✗ Capacity planning

Serverless:
   ✓ Just write functions
   ✓ Pay only when code runs
   ✓ Zero idle cost
   ✓ Scales automatically
```

---

## 2. Core Traits of Serverless

### Trait 1: Managed Runtime

```
Cloud provider handles:
   ✓ Infrastructure provisioning
   ✓ Security patches
   ✓ Auto-scaling
   ✓ Networking
   ✓ Logging infrastructure

You handle:
   ✓ Writing code
   ✓ Configuration
   ✓ Application logic
```

### Trait 2: Ephemeral Functions

```
Functions are:
   ✓ Short-lived (seconds to minutes)
   ✓ Stateless
   ✓ Single-purpose
   ✓ Fire-and-forget (or invoke-and-respond)
```

### Trait 3: Stateless

```
No reliance on:
   ✗ Local memory between invocations
   ✗ Local filesystem (ephemeral)
   ✗ Long-lived sessions

State stored externally:
   ✓ Database (DynamoDB, etc.)
   ✓ Cache (Redis, etc.)
   ✓ Object storage (S3)
   ✓ Message queues
```

### Trait 4: Granular Billing

```
Billed by:
   ✓ Number of invocations
   ✓ Execution duration (often 100ms increments)
   ✓ Memory allocated

Example AWS Lambda:
   - 1M invocations: $0.20
   - 256MB × 1 second: $0.000004
   
Free tier: 1M requests + 400,000 GB-seconds per month!
```

### Trait 5: Elasticity

```
Scale from 0 to thousands in seconds:
   ✓ Handles spikes automatically
   ✓ No pre-provisioning
   ✓ No capacity planning
   ✓ Pay only for actual usage
```

---

## 3. Function as a Service (FaaS)

### The Core Compute Model

```
You write: small, single-purpose functions
Triggered by: events
Run in: sandboxed environments
Scale: per-invocation
```

### Visual

```
   Event ─────► ┌──────────────┐
                 │  Function    │ ──► Result
                 │  (code +     │
                 │   runtime)   │
                 └──────────────┘
                       │
                       │ Cloud provider manages
                       ▼
                  Sandboxed container
                  (you don't see/manage)
```

### Popular Platforms

```
✓ AWS Lambda           (most mature)
✓ Azure Functions      (Microsoft)
✓ Google Cloud Functions (Google)
✓ Cloudflare Workers   (edge-focused)
✓ Vercel Functions     (frontend-focused)
✓ OpenFaaS             (self-hosted)
```

### Concurrency Model

```
Each event = separate function execution

   Event 1 ──► Container 1 (instance 1)
   Event 2 ──► Container 1 (reused)
   Event 3 ──► Container 2 (new, parallel)
   Event 4 ──► Container 3 (new, parallel)
   
   Scales horizontally automatically.
```

### Configuration

```python
# Sample Lambda config
function_config = {
    "memory_size": 256,        # 128MB to 10GB
    "timeout": 30,             # Seconds (max 15 min)
    "environment_variables": {
        "DATABASE_URL": "...",
    },
    "runtime": "python3.11",
    "handler": "app.handler",
}
```

---

## 4. Event Triggers

### What Activates Functions?

```
Functions are IDLE until an event triggers them.
Multiple trigger types available.
```

### Common Triggers

```
1. HTTP REQUESTS
   ✓ API Gateway / Function URLs
   ✓ Webhooks
   
2. MESSAGING
   ✓ Kafka, SQS, SNS
   ✓ Event brokers
   
3. STORAGE EVENTS
   ✓ S3 object uploaded
   ✓ File deleted
   ✓ Database changes (DynamoDB Streams)
   
4. SCHEDULED (CRON)
   ✓ "Run every hour"
   ✓ "Run daily at 3 AM"
   
5. IoT EVENTS
   ✓ Sensor updates
   ✓ Device telemetry
   
6. WEBHOOKS FROM 3RD PARTIES
   ✓ Stripe payment
   ✓ GitHub push
   ✓ Twilio SMS

7. EDGE EVENTS
   ✓ CDN cache misses
   ✓ Image transformations
```

### Declarative Triggers

```yaml
# Serverless Framework
functions:
  api:
    handler: handler.api
    events:
      - httpApi:
          path: /users
          method: post
  
  process_upload:
    handler: handler.process
    events:
      - s3:
          bucket: my-uploads
          event: s3:ObjectCreated:*
  
  hourly_job:
    handler: handler.cleanup
    events:
      - schedule: rate(1 hour)
```

### Back Pressure Handling

```
Spike in events?
   ✓ Platform queues / batches them
   ✓ Throttles if needed
   ✓ Retries on failure
   ✓ Dead letter queue for poison messages

You don't manage this!
```

---

## 5. Function Lifecycle

### From Event to Response

```
1. Event arrives at edge/regional endpoint
2. Platform checks: warm container available?
   YES → route to it (fast!)
   NO  → spin up new container (cold start)
3. Function code loads (if new container)
4. Function executes
5. Result returned (or queued for async)
6. Container kept warm briefly (~5-15 min)
7. Container eventually destroyed (idle)
```

### Visual

```
   Event
     │
     ▼
   ┌──────────────────┐
   │ Platform         │
   │ Routes event     │
   └──────┬───────────┘
          │
          ▼
   Has warm container?
          │
     ┌────┴────┐
     ▼         ▼
   YES        NO
     │         │
     │         ▼
     │     COLD START (50-2000ms)
     │     ✓ Allocate container
     │     ✓ Load runtime
     │     ✓ Load function code
     │         │
     ▼         ▼
   ┌──────────────────┐
   │ Invoke function  │
   └──────┬───────────┘
          │
          ▼
   ┌──────────────────┐
   │ Return response  │
   └──────────────────┘
```

### Invocation Modes

```
SYNCHRONOUS:
   Caller waits for result
   Example: API Gateway → Lambda
   
ASYNCHRONOUS:
   Platform queues + handles retries
   Example: S3 upload → Lambda
```

---

## 6. Cost Model

### Pay-Per-Execution

```
Cost = Invocations × Duration × Memory

Example (AWS Lambda):
   1M invocations × 200ms × 256MB
   ≈ $0.20 for invocations
   + $0.83 for compute time
   = $1.03/month total
```

### Free Tier (AWS Lambda)

```
PERMANENTLY FREE:
   ✓ 1 million requests/month
   ✓ 400,000 GB-seconds/month

For low traffic:
   ✓ Completely free!
```

### Other Costs

```
✓ API Gateway requests
✓ Data transfer (egress)
✓ CloudWatch logs storage
✓ Other AWS services used
```

### When Serverless Wins on Cost

```
✓ Sporadic / bursty traffic
   - Cron jobs (1x/day)
   - User events (when users active)
   - Variable load

✓ Low average traffic
   - Free tier covers most apps
   
✓ Avoiding idle costs
   - No 24/7 VMs
```

### When Serverless Loses on Cost

```
✗ Constant high traffic
   - Always-on servers cheaper than per-invocation
   
✗ Long-running functions
   - 14-min Lambda = $0.001 per execution!
   - At scale, costs explode
```

---

## 7. Cold Starts

### What Is a Cold Start?

```
First invocation (or after idle):
   Platform must:
   ✓ Allocate container
   ✓ Load runtime (e.g., Python interpreter)
   ✓ Load function code
   ✓ Run initialization

This adds latency before function runs.
```

### Cold Start Times by Runtime

```
JavaScript / Python:  100-500ms
Go:                   10-50ms
Java:                 500-3000ms
.NET:                 500-2000ms
Rust:                 10-30ms
```

### Mitigation Strategies

```
1. PROVISIONED CONCURRENCY (AWS)
   ✓ Pre-allocate warm containers
   ✗ Costs more (paying for idle)
   
2. SMALLER FUNCTIONS
   ✓ Less code = faster load
   ✓ Minimize dependencies
   
3. FASTER RUNTIMES
   ✓ Go, Rust, Python
   ✗ Avoid Java/.NET if cold start matters
   
4. ARM-BASED (Graviton)
   ✓ Faster + cheaper
   
5. LAZY INITIALIZATION
   ✓ Defer heavy work until needed
   
6. KEEP WARM
   ✓ Schedule a "warmup" call every 5 minutes
```

### When Cold Starts Matter

```
✗ User-facing latency-sensitive APIs
✗ Real-time interactions
✗ Synchronous response chains

✓ Background jobs
✓ Async processing
✓ Batch tasks
```

---

## 8. Vendor Lock-In

### The Concern

```
Once you build on a platform:
   ✗ Hard to migrate
   ✗ Tied to proprietary APIs
   ✗ Tied to specific event sources
   ✗ Permissions model differs per cloud
```

### Sources of Lock-In

```
✓ Native event triggers (DynamoDB Streams, S3 events)
✓ IAM/permissions model
✓ Logging integration (CloudWatch, etc.)
✓ Specific SDK calls
✓ Provider-managed services (DynamoDB, etc.)
```

### Mitigation Strategies

```
1. ABSTRACT INFRASTRUCTURE
   ✓ Use frameworks (Serverless Framework, SAM)
   ✓ Infrastructure as Code (Terraform)

2. PORTABLE STANDARDS
   ✓ CloudEvents (event format standard)
   ✓ Knative (Kubernetes-based)
   ✓ OpenFaaS (self-hosted)

3. KEEP LOGIC PURE
   ✓ Business logic in separate functions
   ✓ Provider integrations as thin adapters

4. CONSIDER MULTI-CLOUD
   ✓ Same code on AWS Lambda + Google Cloud Functions
   ✗ Operational complexity
```

### Is Lock-In Always Bad?

```
NO - it's a trade-off!

✓ Pros of accepting lock-in:
   - Move faster
   - Use best-of-breed services
   - Lower initial costs
   
✗ Cons:
   - Migration is hard
   - Pricing can change
   - Feature set tied to provider
   
→ For startups: often worth it
→ For enterprise: plan carefully
```

---

## 9. Use Cases — Where Serverless Shines

### Use Case 1: Image / Video Processing

```
File uploaded to S3 → Lambda triggered
   ✓ Resize image
   ✓ Generate thumbnails
   ✓ Extract metadata
   ✓ Format conversion

Why it works:
   ✓ Sporadic (not constant)
   ✓ Stateless
   ✓ Bursty (many at once OK)
```

### Use Case 2: IoT Data Ingestion

```
Sensors → MQTT broker → Lambda
   ✓ Thousands of events/sec
   ✓ Each: small, simple task
   ✓ No need for always-on servers

Perfect fit!
```

### Use Case 3: Scheduled / Batch Jobs

```
Cron schedule → Lambda
   ✓ "Run daily at 3 AM"
   ✓ "Sync data every hour"
   ✓ "Send weekly reports"

No idle servers needed!
```

### Use Case 4: Chatbots / Voice Assistants

```
User sends message → Lambda processes
   ✓ Handles concurrent users
   ✓ Scales to demand
   ✓ Scales down when idle

Costs match usage!
```

### Use Case 5: SaaS Glue

```
Connect Stripe + Slack + Google Sheets:
   ✓ Stripe webhook → Lambda → Slack notification
   ✓ Few lines of code
   ✓ Pay only when events occur

vs deploying a server just for glue logic? Overkill!
```

### Use Case 6: Edge Functions

```
Cloudflare Workers / Lambda@Edge:
   ✓ Run code AT the CDN edge
   ✓ Ultra-low latency globally
   ✓ Geo-routing, A/B tests, personalization
```

### Real Success Stories

```
✓ Netflix - thumbnail generation
✓ FINRA - 1B+ market events daily
✓ The New York Times - article processing
✓ Coca-Cola - vending machine telemetry
```

---

## 10. Anti-Patterns

### Anti-Pattern 1: Long-Running Jobs

```
❌ Heavy ETL jobs
❌ Video transcoding (full movies)
❌ ML model training

Why bad:
   ✗ 15-minute timeout limit
   ✗ Cost increases linearly with duration
   ✗ Better with containers / batch services

→ Use AWS Batch, ECS, or EC2 instead
```

### Anti-Pattern 2: Low-Latency High-Throughput

```
❌ Financial trading APIs
❌ Real-time gaming
❌ Microsecond-sensitive workloads

Why bad:
   ✗ Cold starts hurt P99 latency
   ✗ Per-invocation overhead
   
→ Use dedicated servers / containers
```

### Anti-Pattern 3: Monolith Lift-and-Shift

```
❌ "Let's put our Rails monolith in Lambda!"

Why bad:
   ✗ Monoliths don't fit function model
   ✗ Slow cold starts (heavy code)
   ✗ Per-invocation costs add up
   
→ Refactor or use containers
```

### Anti-Pattern 4: Synchronous Chains

```
❌ Lambda → Lambda → Lambda → Lambda (waiting)

Why bad:
   ✗ Cold start at each step
   ✗ Cost multiplied
   ✗ Hard to debug

→ Use orchestration (Step Functions) or async
```

### Anti-Pattern 5: Stateful in Functions

```
❌ Storing data in /tmp expecting persistence
❌ In-memory caches between invocations
❌ "I'll just keep the connection alive..."

Why bad:
   ✗ Functions are ephemeral
   ✗ Containers destroyed at any time
   ✗ Different invocations on different containers

→ Use external state (Redis, DynamoDB, etc.)
```

---

## 11. Design Principles

### Principle 1: Design for Statelessness

```
✓ All state EXTERNAL to function
✓ Use DynamoDB, Redis, S3
✓ Pass needed data in event
✓ Don't expect previous invocation state
```

### Principle 2: Embrace Event Choreography

```
✓ Functions react to events
✓ Loose coupling between functions
✓ Easy to add/remove consumers

✗ Avoid tightly coupled function chains
```

### Principle 3: Observe Everything

```
Since functions are ephemeral:
   ✓ Structured logging (JSON)
   ✓ Distributed tracing (X-Ray, OpenTelemetry)
   ✓ Custom metrics (CloudWatch)
   ✓ Error tracking (Sentry)
```

### Principle 4: Fail Gracefully

```
✓ Retries (built into platform)
✓ Dead letter queues for poison messages
✓ Idempotent handlers (safe duplicates)
✓ Circuit breakers for external calls
```

### Principle 5: Start Small, Iterate

```
✓ Start with simple use case
✓ Measure actual costs + performance
✓ Optimize memory + duration
✓ Tune based on real data

→ Serverless rewards fine-grained optimization
```

### Principle 6: Right-Size Memory

```
Memory in Lambda also affects CPU!
   ✓ More memory = more CPU
   ✓ Sometimes higher memory = LOWER cost (faster execution)
   
Test different sizes:
   - 256MB: 800ms
   - 512MB: 400ms (same cost, faster!)
   - 1024MB: 200ms (might be cheaper!)
```

---

## 12. Serverless vs Containers

### When to Choose What

```
┌─────────────────────────────────────────────────────────────┐
│  USE SERVERLESS WHEN                                          │
├─────────────────────────────────────────────────────────────┤
│  ✓ Sporadic / bursty traffic                                  │
│  ✓ Event-driven workloads                                     │
│  ✓ Small focused tasks                                        │
│  ✓ Cost-sensitive at low volume                               │
│  ✓ Quick development                                          │
│  ✓ Limited DevOps capacity                                    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  USE CONTAINERS WHEN                                          │
├─────────────────────────────────────────────────────────────┤
│  ✓ Constant traffic                                           │
│  ✓ Long-running tasks                                         │
│  ✓ Need full control                                          │
│  ✓ Complex dependencies                                       │
│  ✓ Vendor independence                                        │
│  ✓ Predictable workloads                                      │
└─────────────────────────────────────────────────────────────┘
```

### Hybrid Is Common

```
Many systems use BOTH:
   ✓ Serverless for event-driven background tasks
   ✓ Containers for steady-state APIs
   ✓ CDN for static content
```

---

## 13. Summary — Key Takeaways

```
┌──────────────────────────────────────────────────────────────┐
│  ✅ Serverless = no server management                          │
│  ✅ Pay-per-execution (auto-scales 0 to ∞)                     │
│  ✅ FaaS: small functions triggered by events                  │
│  ✅ Many event sources: HTTP, S3, queue, schedule              │
│  ✅ Cold starts add latency on first invocation                │
│  ✅ Vendor lock-in is real but manageable                      │
│  ✅ Great for: bursty, event-driven, small tasks               │
│  ✅ Bad for: long-running, low-latency-critical                │
│  ✅ Design stateless, observable, fail-gracefully              │
│  ✅ Combine with containers for hybrid architecture            │
└──────────────────────────────────────────────────────────────┘
```

### The Universal Rules

```
1. Functions are STATELESS - state goes elsewhere
2. Embrace EVENT-driven design
3. Watch out for COLD START costs (latency)
4. Right-size MEMORY (affects CPU too)
5. Monitor + observe everything
6. Avoid long-running functions
7. Plan for vendor lock-in
8. Combine with other models for hybrid
9. Start small, measure, optimize
10. Use frameworks (Serverless, SAM, Terraform)
```

---

## 🎬 What's Next?

In **Lecture 4**, we'll dive into **Containerization with Docker and Kubernetes** — the foundation of modern cloud-native deployment.

> **Practical file:** [03_Practical_Hands_On.md](03_Practical_Hands_On.md)

---

## 📚 References

- *Serverless Architectures on AWS* — Peter Sbarski
- AWS Lambda documentation
- Serverless Framework docs
- Azure Functions developer guide
- *Cloud Native Patterns* — Cornelia Davis
