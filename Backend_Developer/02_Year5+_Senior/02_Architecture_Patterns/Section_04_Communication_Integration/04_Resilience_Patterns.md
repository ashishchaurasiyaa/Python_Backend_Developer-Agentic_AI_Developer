# Lecture 4: Resilience Patterns — Retry, Circuit Breaker, Timeout

> *"Degrade. Don't collapse."*

**Section 4 — Communication & Integration Patterns**

---

## 🎯 Is Lecture Mein Kya Seekhenge?

- **Why resilience matters** — failures are inevitable
- **Graceful failure** — degrade, don't crash
- **Retry pattern** — fixed, exponential backoff, jitter
- **Timeout pattern** — never wait forever
- **Circuit breaker** — three-state dance (closed/open/half-open)
- **Bulkhead pattern** — isolate resources like ship compartments
- **Combining patterns** — layered resilience
- **Design considerations** — when too many retries hurt
- **Observability** — measure what matters
- **Chaos testing** — break things intentionally

---

## 1. Why Resilience Matters

### The Reality of Distributed Systems

```
Modern systems = many moving parts:
   • Microservices
   • Third-party APIs
   • Cloud resources
   • Databases
   • Caches
   • Queues
   • Networks
   • Load balancers

Each is a potential failure point.

→ Failures aren't possible — they're EXPECTED.
```

### The Goal: Controlled Degradation

```
What we want:
   ✓ User experience dips gracefully
   ✓ Slower response > complete crash
   ✓ Cached data > error page
   ✓ Some features degraded > whole site down

What we DON'T want:
   ✗ One slow service crashes everything
   ✗ Retry storms amplifying failures
   ✗ Cascading failures across the system
   ✗ Long waits → thread exhaustion
```

### The Mental Model

```
        Failure
          │
          │
   ┌──────┴──────┐
   │             │
   ▼             ▼
WITH               WITHOUT
RESILIENCE        RESILIENCE
   │                │
   ▼                ▼
Degrade            Collapse
gracefully         catastrophically
   │                │
   ▼                ▼
Buy time           Wake up SRE
to recover         at 3 AM
```

### Key Principle

> **"DEGRADE. DON'T COLLAPSE."**

Every pattern we'll discuss serves this purpose.

---

## 2. Graceful Failure

### What It Means

**Instead of throwing an error, return a SAFE alternative — cached data, default, fallback handler.**

### Visual

```
   User Request: "Show weather"
        │
        ▼
   ┌─────────────┐
   │ Weather API │ ← DOWN
   └─────────────┘
        │
        │ Without graceful failure:
        │   ✗ 500 error to user
        │   ✗ Broken page
        │
        │ With graceful failure:
        │   ✓ Show last cached weather
        │   ✓ Add note: "Updated 2 hrs ago"
        │   ✓ User barely notices
```

### Strategies

```
1. RETURN CACHED DATA
   if api_call_fails:
       return cache.get(key) or default

2. STATIC DEFAULTS
   if can't fetch reviews:
       return "Reviews unavailable"

3. PARTIAL RESPONSES
   if recommendation_service_down:
       return {"products": [...], "recommendations": []}

4. ALTERNATE SOURCES
   if primary_db_down:
       return read_from_replica()

5. SIMPLIFIED VIEW
   if personalization_fails:
       return generic_homepage()
```

### Examples in the Wild

```
✓ Netflix: Recommendations down → shows popular shows
✓ Amazon: Personalization fails → shows trending products
✓ Twitter: Trending unavailable → empty section (not crash)
✓ Gmail: Search slow → returns recent emails first
```

---

## 3. Retry Pattern

### The Idea

```
When an operation fails — especially due to TRANSIENT errors:
   • Network blip
   • Service momentarily slow
   • Temporary glitch
   
Don't give up. Wait briefly and try again.
```

### Why It Works

```
Many failures are TEMPORARY:
   ✓ Network packet lost → retry succeeds
   ✓ Service restarting → retry hits new instance
   ✓ Brief overload → retry after pause works
   
But you must retry SMARTLY.
```

### The Danger: Retry Storms

```
🚨 If 1000 clients all retry aggressively at the same time:
   → Hits failing service with 1000 concurrent requests
   → Worsens the problem
   → Death spiral

→ Always RATE-LIMIT retries.
```

### Retry Visualization

```
Attempt 1 → FAIL
   │
   │ Wait
   ▼
Attempt 2 → FAIL
   │
   │ Wait longer
   ▼
Attempt 3 → SUCCESS ✓
   │
   ▼
Return result
```

### What Counts as Retryable?

```
✓ Network timeouts
✓ Connection errors
✓ 5xx server errors (server side)
✓ Service unavailable
✓ Rate limit (with backoff)

✗ 4xx client errors (your fault, won't change)
✗ Authentication failures
✗ Validation errors
✗ Permission denied
```

---

## 4. Retry Strategies

### Strategy 1: Fixed Delay

```
Wait same time between retries.

Attempt 1: try
   Wait 2s
Attempt 2: try
   Wait 2s
Attempt 3: try
   Wait 2s
Attempt 4: try

✓ Simple
✗ Causes retry storms (everyone retries at same time)
✗ Doesn't give service time to recover
```

### Strategy 2: Exponential Backoff

```
Double the wait time each attempt.

Attempt 1: try
   Wait 2s
Attempt 2: try
   Wait 4s
Attempt 3: try
   Wait 8s
Attempt 4: try
   Wait 16s

✓ Gives service more breathing room
✓ Reduces load over time
✗ Still synchronized retries if many clients
```

### Strategy 3: Exponential Backoff + Jitter (BEST!)

```
Add randomness to delay.

Attempt 1: try
   Wait 2s + random(0-1s)  → 2.7s
Attempt 2: try
   Wait 4s + random(0-2s)  → 5.4s
Attempt 3: try
   Wait 8s + random(0-4s)  → 10.2s

✓ Spreads retries across time
✓ Prevents synchronized waves
✓ Best practice for production
```

### Visual

```
Without Jitter:
   All clients retry at same time → traffic spikes
   
   |█████|     |█████|     |█████|
   t=2s        t=4s        t=8s

With Jitter:
   Retries spread out → smooth traffic
   
   |█|██|█|█|██|██|█|█|
   t=2-3   t=4-6   t=8-12
```

### Code Pattern

```python
async def retry_with_backoff_and_jitter(operation, max_attempts=3):
    for attempt in range(max_attempts):
        try:
            return await operation()
        except RetryableError:
            if attempt == max_attempts - 1:
                raise
            
            base_delay = 2 ** attempt  # 1, 2, 4, 8...
            jitter = random.uniform(0, base_delay * 0.5)
            await asyncio.sleep(base_delay + jitter)
```

---

## 5. Timeout Pattern

### Why Timeouts Are Essential

```
Without timeout:
   Service A ── calls ──► Service B (slow/hung)
       │
       │ Waits forever
       │ Thread blocked
       │ Memory held
       │
       │ Many requests pile up
       │ Service A becomes unresponsive
       │ → Failure cascades to A's callers
```

### The Rule

```
🚨 NEVER wait forever for another service.
🚨 ALWAYS set timeouts on EVERY external call.
```

### What Timeouts Protect

```
✓ Threads (limited pool)
✓ Memory
✓ Database connections
✓ HTTP connections
✓ File descriptors
✓ Other clients waiting for A
```

### The Balancing Act

```
Too short:
   ✗ Cuts off requests that would succeed
   ✗ False failures
   ✗ Unnecessary retries

Too long:
   ✗ Resources held too long
   ✗ Slow failure detection
   ✗ Slows down upstream

The right value:
   ✓ Slightly more than P99 latency
   ✓ Tuned based on real data
   ✓ Different per service/operation
```

### Sample Timeout Values

```
Operation                 Typical Timeout
──────────────────────────────────────────
Fast cache lookup         10-50ms
Database query            100-500ms
External API call         1-5s
Third-party webhook       3-10s
Long-running job          30s-5min
File upload               1-10min
```

### Layered Timeouts

```
Set timeouts at multiple levels:

User-facing API timeout:  30s
   └─ Internal API call:  10s
       └─ DB query:        2s
           └─ Cache:       100ms

Each level shorter than parent — fail fast at lowest level.
```

---

## 6. Circuit Breaker Pattern

### Inspiration: Electrical Fuses

```
🔌 Electrical fuse:
   ✓ Normal current → flows
   ✓ Short circuit → trips, cuts power
   ✓ After fix → reset, current flows again
   
   Protects the rest of the system!
```

### Software Equivalent

```
Track failure rate of calls to a dependency.

✓ Below threshold: closed, requests flow normally
✗ Above threshold: open, requests rejected IMMEDIATELY
↻ After cooldown: half-open, try a test request
```

### The Three States

```
                        ┌─────────────────┐
                        │     CLOSED       │
                        │  (normal flow)   │
                        └────────┬─────────┘
                                  │
                  failures > threshold
                                  │
                                  ▼
                        ┌─────────────────┐
                        │      OPEN        │
                        │ (fail fast,      │
                        │  reject calls)   │
                        └────────┬─────────┘
                                  │
                  cooldown elapsed
                                  │
                                  ▼
                        ┌─────────────────┐
                        │   HALF-OPEN      │
                        │ (try one request)│
                        └────────┬─────────┘
                                  │
                  ┌───────────────┴───────────────┐
                  │                                │
              success                          failure
                  │                                │
                  ▼                                ▼
              CLOSED                           OPEN
              (restored)                       (still broken)
```

### How It Helps

```
Without circuit breaker:
   Service B fails →
   ✗ 1000s of requests pile up waiting
   ✗ Threads exhausted
   ✗ Memory leak
   ✗ Slow cascade
   ✗ All consumers of A start failing

With circuit breaker:
   Service B fails 5 times →
   ✓ Circuit OPENS
   ✓ Next requests INSTANTLY rejected
   ✓ No resources wasted
   ✓ B has time to recover
   ✓ After cooldown: test, then close
```

### Real-World Analogy

```
🏥 Hospital ER triage:
   Normal day: All patients admitted (CLOSED)
   
   Mass casualty: Stop accepting non-critical (OPEN)
   Why? Save resources for critical cases
   
   Situation improves: Try admitting again (HALF-OPEN)
   Stable? → Back to normal (CLOSED)
   Still bad? → Continue rejecting (OPEN)
```

---

## 7. Circuit Breaker in Action

### Scenario: Payment Service Failure

```
Time 00:00 - Service B (Payment) starts failing

Without circuit breaker:
   ┌──────────────────────────────────┐
   │ Service A keeps trying           │
   │ Each call: 5-second timeout      │
   │ 1000 calls/min = 5000 threads    │
   │ Memory exhausted                 │
   │ Service A also dies              │
   └──────────────────────────────────┘
   → DOWN: 30+ minutes

With circuit breaker:
   ┌──────────────────────────────────┐
   │ 5 calls fail → CIRCUIT OPENS     │
   │ Next 1000 calls: instant 503     │
   │ Service A keeps serving others   │
   │ User sees: "Payment temp down"   │
   │ Payment recovers                 │
   │ Circuit half-opens, then closes  │
   └──────────────────────────────────┘
   → IMPACT: Just payment, ~2 minutes
```

### Configuration

```
Common parameters:
   failure_threshold: 5    (failures before opening)
   timeout: 30s            (how long circuit stays open)
   half_open_calls: 1      (test calls in half-open)
   reset_timeout: 60s      (full reset after this)
```

### Fallback Strategy

```python
@circuit_breaker(failure_threshold=5, timeout=30)
async def call_payment_service(amount):
    return await http.post("/payment", ...)

# Usage with fallback
try:
    result = await call_payment_service(100)
except CircuitOpenError:
    # Circuit is open - use fallback
    return {"status": "pending", "message": "Payment queued"}
```

---

## 8. Bulkhead Pattern

### The Ship Analogy

```
🚢 Ship hull divided into watertight compartments
   ✓ One section floods → contained
   ✓ Doesn't spread to other sections
   ✓ Ship stays afloat
   
   Famous example: Titanic had bulkheads
   (Sadly, not enough — but the idea was right)
```

### Software Equivalent

```
Isolate resources by:
   ✓ Service / dependency
   ✓ User type
   ✓ Operation category
   ✓ Priority

→ Failure in one area doesn't drain shared resources.
```

### Without Bulkhead

```
   ┌─────────────────────────────┐
   │  Service A                  │
   │  Single thread pool (100)   │
   │                             │
   │  All requests share:        │
   │    ✗ 90 threads stuck on    │
   │      slow PaymentService    │
   │    ✗ Only 10 left for       │
   │      everyone else          │
   │    ✗ Login slow             │
   │    ✗ Browsing fails         │
   └─────────────────────────────┘
```

### With Bulkhead

```
   ┌─────────────────────────────┐
   │  Service A                  │
   │                             │
   │  Pool 1 (50): Payments      │
   │     ✗ 50 stuck on slow      │
   │                             │
   │  Pool 2 (30): Login         │
   │     ✓ Still working         │
   │                             │
   │  Pool 3 (20): Browsing      │
   │     ✓ Still working         │
   └─────────────────────────────┘
   
   Payment failure CONTAINED!
```

### Bulkhead Types

```
1. THREAD POOL BULKHEAD
   - Separate thread pools per dependency
   - One pool exhausted → others unaffected

2. CONNECTION POOL BULKHEAD
   - Separate DB connection pools
   - Heavy queries don't starve light ones

3. SEMAPHORE BULKHEAD
   - Limit concurrent calls per dependency
   - Lighter than thread pools

4. QUEUE BULKHEAD
   - Separate queues per workflow
   - Background jobs don't starve user requests

5. INSTANCE BULKHEAD
   - Separate service instances per tenant/feature
   - Total isolation
```

### Real Example: E-commerce

```
Pool 1: Catalog (heavy reads)     - 100 threads
Pool 2: Search                    - 50 threads
Pool 3: Cart / Checkout           - 50 threads (high priority)
Pool 4: Recommendations           - 30 threads (low priority)
Pool 5: Reviews                   - 20 threads

If recommendations slows down:
   → Only Pool 4 affected
   → Checkout still works
   → User can still buy!
```

---

## 9. Combining Patterns

### Layered Resilience

```
You rarely use ONE pattern alone.
COMBINE them for full coverage.
```

### Example: Production Web Service Call

```python
@bulkhead(pool="payment", limit=50)              # 1. Bulkhead
@circuit_breaker(failure_threshold=5)            # 2. Circuit breaker
@retry(max_attempts=3, backoff="exponential")    # 3. Retry
@timeout(seconds=5)                              # 4. Timeout
async def call_payment_service(amount):
    return await http.post("/payment", amount=amount)

# Usage
try:
    result = await call_payment_service(100)
except (TimeoutError, CircuitOpenError, RetryExhausted):
    # Fallback                                   # 5. Graceful failure
    return await queue_for_later(amount)
```

### What Each Layer Catches

```
INNER → OUTER

1. TIMEOUT
   • Single request hangs

2. RETRY
   • Transient failures
   • Brief glitches

3. CIRCUIT BREAKER
   • Sustained failures
   • Service unavailable

4. BULKHEAD
   • Resource exhaustion
   • Isolation per dependency

5. GRACEFUL FAILURE
   • All else fails
   • User experience preserved
```

### Visual

```
   Request
      │
      ▼
   ┌────────────────────┐
   │  Bulkhead          │ ← Limit concurrent calls
   └────────┬───────────┘
            │
            ▼
   ┌────────────────────┐
   │  Circuit Breaker   │ ← Fail fast if dependency dead
   └────────┬───────────┘
            │
            ▼
   ┌────────────────────┐
   │  Retry             │ ← Try again on transient errors
   └────────┬───────────┘
            │
            ▼
   ┌────────────────────┐
   │  Timeout           │ ← Never wait too long
   └────────┬───────────┘
            │
            ▼
   ┌────────────────────┐
   │  Actual Service    │
   │  Call              │
   └────────────────────┘
```

---

## 10. Design Considerations

### Consideration 1: Don't Over-Retry

```
🚨 Anti-pattern: Aggressive retries everywhere
   
   1000 clients × 5 retries × failing service
   = 5000 retry waves
   = Service drowns
   
✅ Limit retries (3 max typically)
✅ Use exponential backoff
✅ Add jitter
✅ Coordinate with circuit breaker
```

### Consideration 2: Tune Timeouts Per Service

```
✗ Same timeout everywhere (lazy)
   30s for cache → wasteful
   30s for DB → maybe okay
   30s for slow ML inference → too short
   
✅ Tune per service:
   Cache:        100ms
   DB:           1s
   Internal API: 3s
   External API: 10s
   ML inference: 30s
```

### Consideration 3: Monitor Circuit Breaker

```
Critical metrics:
   ✓ How often does each breaker trip?
   ✓ How long do they stay open?
   ✓ Are fallbacks working?
   
Without metrics → can't tune
```

### Consideration 4: Test Failure Modes

```
✗ Don't wait for production to find bugs
✅ Use chaos engineering:
   - Kill dependencies
   - Inject latency
   - Drop network
   - Throttle CPU
   
See: Lecture 5 — Building Fault Tolerant Systems
```

### Consideration 5: Observability

```
Resilience is invisible without metrics.

Track:
   ✓ Retry counts per service
   ✓ Circuit breaker state changes
   ✓ Timeout occurrences
   ✓ Fallback invocations
   ✓ Bulkhead saturations

Tools:
   ✓ Prometheus + Grafana
   ✓ Datadog
   ✓ New Relic
```

---

## 11. Real-World Implementations

### Netflix Hystrix (Original)

```
Pioneered circuit breaker pattern in Java.
Now in maintenance mode, but influential.
```

### Resilience4j (Java)

```
Modern Java library:
   ✓ Circuit breaker
   ✓ Retry
   ✓ Rate limiter
   ✓ Bulkhead
   ✓ Time limiter
   ✓ Cache
```

### Python Libraries

```
✓ tenacity        — retries with backoff/jitter
✓ circuitbreaker  — circuit breaker
✓ aiobreaker      — async circuit breaker
✓ pybreaker       — sync circuit breaker
```

### Cloud Native (Service Mesh)

```
✓ Istio          — built-in resilience policies
✓ Linkerd        — automatic retries, circuit breaking
✓ Envoy          — sophisticated rules engine

Pros: No code changes
Cons: Need K8s + service mesh
```

---

## 12. Common Anti-Patterns

### Anti-Pattern 1: Retry Without Backoff

```
❌ for _ in range(10):
       try: call_service()
       except: continue

→ Hammers failing service
→ Makes things worse
```

### Anti-Pattern 2: Retry on Everything

```
❌ Retry 4xx errors (won't change!)
❌ Retry validation errors
❌ Retry auth failures

✅ Only retry transient errors
```

### Anti-Pattern 3: Infinite Timeouts

```
❌ requests.get(url)  # No timeout!
   
→ Hangs forever
→ Thread leak
→ Resource exhaustion

✅ Always: requests.get(url, timeout=5)
```

### Anti-Pattern 4: Single Thread Pool for Everything

```
❌ All HTTP calls share one pool
   
→ One slow dependency exhausts pool
→ Everything blocks

✅ Bulkheads per dependency
```

### Anti-Pattern 5: No Fallback

```
❌ If service fails → 500 error
   
→ Bad UX
→ Customer loss

✅ Always design fallback paths
```

### Anti-Pattern 6: Circuit Breaker Without Monitoring

```
❌ Add @circuit_breaker decorator → done!

→ Don't know if it's tripping
→ Can't tune thresholds
→ Surprised when fallbacks invoked

✅ Monitor + alert on circuit state
```

---

## 13. Resilience Patterns Summary

```
┌─────────────────────────────────────────────────────────────────┐
│  PATTERN          │  PROBLEM                       │  TOOL          │
├───────────────────┼────────────────────────────────┼────────────────┤
│  Graceful Failure │  Crash on errors                │  Try/fallback  │
│  Retry            │  Transient failures             │  tenacity      │
│  Timeout          │  Hanging calls                  │  httpx timeout │
│  Circuit Breaker  │  Failing dependency overload    │  circuitbreaker│
│  Bulkhead         │  Resource exhaustion            │  Thread pools  │
│  Backoff          │  Retry storms                   │  Exponential   │
│  Jitter           │  Synchronized retries           │  Random delay  │
└───────────────────┴────────────────────────────────┴────────────────┘
```

---

## 14. The Resilience Mindset

### Before Adding Resilience

Ask:
```
1. WHAT could fail?
   - Network timeout
   - Service unavailable
   - Slow response
   - Auth failure

2. HOW often might it fail?
   - 1% (rare)
   - 10% (occasional)
   - 50% (frequent)

3. WHAT'S the impact?
   - User waits longer
   - Feature unavailable
   - Whole site down

4. WHAT'S the right pattern?
   - Match pattern to failure mode
```

### Resilience Checklist

```
For each external dependency:
   □ Set timeout
   □ Add retry with backoff (if retryable)
   □ Add circuit breaker (if dependency is unreliable)
   □ Use bulkhead (separate resources)
   □ Design fallback (graceful degradation)
   □ Monitor metrics
   □ Test failure modes
```

---

## 15. Summary — Key Takeaways

```
┌──────────────────────────────────────────────────────────────┐
│  ✅ Failures inevitable in distributed systems                │
│  ✅ Goal: degrade gracefully, don't collapse                  │
│  ✅ Graceful failure: serve cached/default data               │
│  ✅ Retry: handle transient failures (with backoff + jitter)  │
│  ✅ Timeout: never wait forever                               │
│  ✅ Circuit breaker: fail fast when dependency dead           │
│  ✅ Bulkhead: isolate resources for containment               │
│  ✅ COMBINE patterns for layered resilience                   │
│  ✅ Monitor everything — resilience is invisible otherwise    │
│  ✅ Test failure modes (chaos engineering)                    │
└──────────────────────────────────────────────────────────────┘
```

### The Universal Rules

```
1. ALWAYS set timeouts on external calls
2. Retry ONLY transient failures
3. Use exponential backoff + jitter
4. Circuit breakers protect against bad dependencies
5. Bulkheads contain resource exhaustion
6. Combine patterns — layered defense
7. Plan fallbacks — graceful degradation
8. Monitor & alert on resilience metrics
9. Test failure scenarios proactively
10. Resilience ≠ perfection. It's controlled degradation.
```

---

## 🎬 What's Next?

In **Lecture 5**, we'll put it all together to **build fault-tolerant systems** — including chaos engineering, observability, and end-to-end resilience design.

> **Practical file:** [04_Practical_Hands_On.md](04_Practical_Hands_On.md)

---

## 📚 References

- *Release It!* — Michael Nygard (must-read!)
- *Site Reliability Engineering* — Google
- *The Pragmatic Programmer* — Hunt & Thomas
- Netflix Tech Blog (Hystrix history)
- AWS Architecture Center — Resilience
- Resilience4j docs (resilience4j.readme.io)
