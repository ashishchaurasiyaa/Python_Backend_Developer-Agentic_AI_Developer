# Lecture 6: Edge Architecture — CDNs and Edge Functions

> *"Bring compute and content closer to users for speed at global scale."*

**Section 7 — Cloud-Native & Scalable Architecture Styles**

---

## 🎯 Is Lecture Mein Kya Seekhenge?

- **Why edge architecture** — global latency challenge
- **CDNs** — Content Delivery Networks deep dive
- **CDN caching** — hit/miss flow
- **Edge functions** — dynamic logic at the edge
- **Edge use cases** — geo, A/B, auth, rate limiting
- **Edge vs origin compute**
- **Major platforms** — Cloudflare, CloudFront, Vercel
- **Challenges** — debugging, state, cold starts
- **Best practices** — designing edge-first

---

## 1. What Is Edge Architecture?

### The Problem

```
Traditional model:
   ✓ App + data in centralized region (e.g., US-East)
   ✗ Users globally distributed
   
   User in Mumbai → US-East round-trip = 250ms
   User in Sydney → US-East round-trip = 300ms
   
→ Performance suffers for distant users.
```

### Edge Solution

```
Bring compute + data CLOSER to users:
   ✓ CDNs distribute static content
   ✓ Edge functions run dynamic logic
   ✓ Cached at hundreds of locations worldwide

Result:
   ✓ 10-50ms latency vs 250ms
   ✓ Faster page loads
   ✓ Better global experience
```

### The Edge Network

```
   ┌─────────────────────────────────────────────────┐
   │              CLOUDFLARE EDGE NETWORK              │
   │                                                    │
   │   ●─●─●     ●─●─●     ●─●─●     ●─●─●            │
   │   US      Europe    Asia    Australia            │
   │   (50)    (40)      (30)    (10)                  │
   │                                                    │
   │   285+ cities worldwide                            │
   │   Sub-50ms to 95% of Internet users               │
   └─────────────────────────────────────────────────┘
```

---

## 2. What Is a CDN?

### Definition

**CDN = Globally distributed network of caching servers near users.**

### What CDNs Cache

```
✓ Images (JPG, PNG, WebP)
✓ Videos (MP4, HLS streams)
✓ JavaScript bundles
✓ CSS stylesheets
✓ Fonts
✓ HTML (sometimes)
✓ API responses (with care)
```

### Benefits

```
✓ LOWER LATENCY
   Users get content from nearby edge

✓ REDUCED ORIGIN LOAD
   Less traffic to your servers

✓ SCALABILITY
   Handles traffic spikes via edge

✓ AVAILABILITY
   Multiple edge locations = redundancy

✓ DDoS PROTECTION
   Filtered at edge before reaching origin

✓ BANDWIDTH SAVINGS
   Origin bandwidth costs reduced
```

### Popular CDN Providers

```
✓ Cloudflare        (most generous free tier!)
✓ AWS CloudFront    (AWS-native)
✓ Google Cloud CDN  (GCP-native)
✓ Azure CDN         (Microsoft)
✓ Akamai            (enterprise legacy)
✓ Fastly            (developer-focused)
✓ Bunny CDN         (budget-friendly)
✓ KeyCDN            (simple)
```

---

## 3. How CDN Caching Works

### Cache Flow

```
   User Request
        │
        ▼
   ┌──────────────┐
   │ Edge Server  │
   │ (nearest)    │
   └──────┬───────┘
          │
          │ Check cache
          ▼
       Cache hit?
          │
     ┌────┴────┐
     ▼         ▼
   YES        NO
     │         │
     │         ▼
     │     Fetch from origin
     │         │
     │         ▼
     │     Cache it locally
     │         │
     └────┬────┘
          │
          ▼
   Return to user
```

### Cache Hit vs Miss

```
CACHE HIT (good!):
   User → Edge cache → User
   Latency: 10-50ms
   No origin server hit

CACHE MISS (rare):
   User → Edge → Origin → Edge cache → User
   First request: slower
   Subsequent requests: cached!
```

### Cache Control Headers

```http
# Long cache for immutable assets
Cache-Control: public, max-age=31536000, immutable
# (1 year cache, never changes)

# Medium cache for HTML
Cache-Control: public, max-age=300
# (5 min cache)

# No cache for API responses (usually)
Cache-Control: no-store, no-cache, must-revalidate

# Vary by accepted encoding
Vary: Accept-Encoding
```

### Cache Invalidation

```
When you update content:
   
   Option 1: Wait for TTL to expire
   Option 2: Manual purge
      $ curl -X POST "https://api.cloudflare.com/.../purge_cache" \
          -H "Authorization: Bearer ..." \
          -d '{"files": ["https://example.com/styles.css"]}'
   
   Option 3: Cache busting via URL
      styles.css?v=1.2.3 (changes URL when updated)
      styles.abc123.css (build-time hash)
```

### Edge Analytics

```
Most CDNs provide:
   ✓ Cache hit ratio (target: > 90%)
   ✓ Geographic distribution
   ✓ Latency by region
   ✓ Bandwidth usage
   ✓ Top URLs
   ✓ Bot traffic detection
```

---

## 4. What Are Edge Functions?

### Beyond Static Content

```
CDNs cache static content.
But what about DYNAMIC logic?
   ✗ User-specific personalization
   ✗ Geo-based redirects
   ✗ Authentication
   ✗ A/B testing
   ✗ Request transformation

→ Edge Functions!
```

### Definition

**Edge Functions = lightweight, serverless functions running at CDN edge nodes.**

### Comparison to Traditional Serverless

```
┌──────────────────┬─────────────────┬─────────────────┐
│  ASPECT           │  Lambda (region)│  Edge Functions │
├──────────────────┼─────────────────┼─────────────────┤
│  Cold start       │  100-2000ms     │  <10ms          │
│  Location         │  1 region       │  Hundreds       │
│  Latency          │  Variable       │  Always close   │
│  Compute power    │  Up to 10GB RAM │  Limited        │
│  Memory limits    │  256MB-10GB     │  128MB usually  │
│  Execution time   │  Up to 15 min   │  Up to 30s      │
│  Best for         │  Heavy work     │  Light logic    │
└──────────────────┴─────────────────┴─────────────────┘
```

### Popular Platforms

```
✓ Cloudflare Workers
✓ Vercel Edge Functions
✓ Netlify Edge Functions
✓ AWS Lambda@Edge
✓ Fastly Compute@Edge
✓ Deno Deploy
```

---

## 5. Edge Logic Use Cases

### Use Case 1: Geolocation-Based Content

```javascript
// Cloudflare Worker
export default {
  async fetch(request) {
    const country = request.cf.country;
    
    // Redirect to country-specific site
    if (country === 'JP') {
      return Response.redirect('https://jp.example.com', 302);
    }
    if (country === 'DE') {
      return Response.redirect('https://de.example.com', 302);
    }
    
    return fetch(request);  // Default
  }
};
```

### Use Case 2: A/B Testing

```javascript
export default {
  async fetch(request) {
    // Get or assign A/B group via cookie
    const cookies = parseCookies(request.headers.get('Cookie'));
    let abGroup = cookies['ab_group'];
    
    if (!abGroup) {
      abGroup = Math.random() < 0.5 ? 'A' : 'B';
    }
    
    // Route to different backends
    const backendUrl = abGroup === 'A' 
      ? 'https://v1.example.com' 
      : 'https://v2.example.com';
    
    const response = await fetch(backendUrl + new URL(request.url).pathname);
    
    // Set cookie for persistence
    const newResponse = new Response(response.body, response);
    newResponse.headers.set('Set-Cookie', `ab_group=${abGroup}; Max-Age=2592000`);
    
    return newResponse;
  }
};
```

### Use Case 3: Authentication

```javascript
export default {
  async fetch(request) {
    const url = new URL(request.url);
    
    // Skip auth for public paths
    if (url.pathname.startsWith('/public/')) {
      return fetch(request);
    }
    
    // Validate JWT
    const authHeader = request.headers.get('Authorization');
    if (!authHeader) {
      return new Response('Unauthorized', { status: 401 });
    }
    
    try {
      const token = authHeader.replace('Bearer ', '');
      const payload = await verifyJWT(token);  // Local verification!
      
      // Add user info as header
      const modifiedRequest = new Request(request, {
        headers: {
          ...Object.fromEntries(request.headers),
          'X-User-Id': payload.sub,
          'X-User-Email': payload.email,
        }
      });
      
      return fetch(modifiedRequest);
    } catch (e) {
      return new Response('Invalid token', { status: 401 });
    }
  }
};
```

### Use Case 4: Rate Limiting

```javascript
export default {
  async fetch(request, env) {
    const ip = request.headers.get('CF-Connecting-IP');
    const key = `rate_limit:${ip}`;
    
    // Use KV store at edge
    const count = parseInt(await env.RATE_LIMIT.get(key) || '0');
    
    if (count >= 100) {  // 100 requests per minute
      return new Response('Too many requests', { status: 429 });
    }
    
    await env.RATE_LIMIT.put(key, (count + 1).toString(), {
      expirationTtl: 60,  // 1 minute window
    });
    
    return fetch(request);
  }
};
```

### Use Case 5: Bot Detection

```javascript
export default {
  async fetch(request) {
    // Cloudflare bot scoring (CF Pro+)
    const botScore = request.cf.botManagement.score;
    
    if (botScore < 30) {  // Suspicious
      // Challenge or block
      return new Response('Access denied', { status: 403 });
    }
    
    return fetch(request);
  }
};
```

### Use Case 6: Real-Time Analytics

```javascript
export default {
  async fetch(request, env) {
    const response = await fetch(request);
    
    // Async log to analytics (don't block response)
    waitUntil(env.ANALYTICS.writeDataPoint({
      indexes: [request.cf.country],
      blobs: [request.url, request.headers.get('User-Agent')],
      doubles: [Date.now()],
    }));
    
    return response;
  }
};
```

---

## 6. Edge vs Origin Compute

### Edge Compute

```
✓ Lightweight, stateless logic
✓ Latency-critical
✓ Geographically distributed
✓ Stateless

Examples:
   ✓ Redirects
   ✓ Header manipulation
   ✓ Auth checks
   ✓ Geolocation
   ✓ Cache decisions
   ✓ Bot detection
```

### Origin Compute

```
✓ Heavy processing
✓ Stateful operations
✓ Database access
✓ Long-running tasks

Examples:
   ✓ Business logic
   ✓ Database queries
   ✓ ML inference
   ✓ Image processing
   ✓ Complex transformations
```

### Decision Framework

```
USE EDGE for:
   ✓ Cacheable static content
   ✓ Authentication / authorization
   ✓ A/B testing
   ✓ Geo routing
   ✓ Request transformation
   ✓ Rate limiting
   ✓ Lightweight personalization

USE ORIGIN for:
   ✓ Database operations
   ✓ Heavy computation
   ✓ Large file processing
   ✓ Stateful workflows
   ✓ Complex business logic
```

### Hybrid (Most Common)

```
   Browser
      │
      ▼
   Edge Function   ← Light logic (auth, A/B, geo)
      │
      ▼
   CDN cache check ← Cached if possible
      │
      ▼
   Origin Server   ← Heavy logic if needed
      │
      ▼
   Database
```

---

## 7. Major Edge Platforms

### Cloudflare

```
✓ Workers (JavaScript runtime)
✓ Workers KV (key-value store)
✓ Durable Objects (stateful)
✓ R2 (S3-compatible storage)
✓ D1 (SQL database at edge)
✓ Pages (static + Workers)
✓ Stream (video)

Pricing: Generous free tier!
   - 100K requests/day free
   - $5/month for 10M requests
```

### AWS CloudFront + Lambda@Edge

```
✓ CloudFront (CDN)
✓ Lambda@Edge (functions at edge)
✓ CloudFront Functions (lighter, faster)
✓ Tight AWS integration

Pricing:
   - CloudFront: pay per GB + requests
   - Lambda@Edge: per invocation + duration
```

### Vercel

```
✓ Optimized for Next.js
✓ Edge Functions
✓ Edge Config (config at edge)
✓ Edge Middleware (every request)
✓ KV store
✓ Image optimization at edge

Pricing: Free hobby, pay per usage
```

### Netlify

```
✓ Edge Functions (Deno runtime)
✓ Jamstack focus
✓ Form handling
✓ Identity / auth
✓ Site rebuilds
```

### Fastly Compute@Edge

```
✓ WebAssembly runtime (fastest!)
✓ Real-time logging
✓ Granular control
✓ Enterprise-focused
```

---

## 8. Challenges of Edge Architecture

### Challenge 1: Debugging Is Harder

```
✗ Code runs in hundreds of locations
✗ Each may have different versions briefly
✗ Logs distributed across regions
✗ Hard to reproduce region-specific bugs

Mitigations:
   ✓ Centralized logging
   ✓ Request IDs for tracing
   ✓ Real-time error tracking (Sentry)
   ✓ Feature flags for safe rollout
```

### Challenge 2: Compute Limits

```
Edge functions have strict limits:
   ✗ Memory: typically 128MB
   ✗ Execution time: 30s max (often less)
   ✗ Limited libraries available
   ✗ Bundle size constraints

Implications:
   ✓ Keep functions small
   ✓ Avoid heavy dependencies
   ✓ No long-running operations
```

### Challenge 3: Cold Starts

```
Edge functions are FAST:
   ✓ Cloudflare Workers: 5ms
   ✓ Vercel Edge: 50ms
   ✓ vs traditional Lambda: 500-2000ms

But not zero!
   ✗ Infrequently accessed routes still have cold starts
   ✗ Large function bundles slower
```

### Challenge 4: State and Consistency

```
Distributed across regions:
   ✗ No shared in-memory state
   ✗ Eventual consistency challenges
   ✗ Database replication needed

Solutions:
   ✓ Edge KV stores (eventually consistent)
   ✓ Durable Objects (Cloudflare)
   ✓ Pass state via cookies
   ✓ Use central DB for strong consistency
```

### Challenge 5: Observability

```
Standard tools don't fully support edge:
   ✗ APM tools limited
   ✗ Distributed tracing harder
   ✗ Logs go to vendor systems
   ✗ Metrics fragmented

Improving but not mature.
```

---

## 9. Best Practices

### Practice 1: Use Edge for the Right Things

```
✓ Stateless logic
✓ Latency-critical operations
✓ Lightweight transformations
✓ Caching decisions

✗ Don't use for:
   ✗ Heavy compute
   ✗ Long-running tasks
   ✗ Stateful workflows
```

### Practice 2: Avoid External Calls

```
Each external call from edge:
   ✗ Adds latency
   ✗ May undermine edge benefits

✓ Keep logic SELF-CONTAINED
✓ Use edge storage (KV) where possible
✓ Cache aggressively
```

### Practice 3: Cache Aggressively

```
Always ask first:
   "Can this be CACHED?"

✓ Cache hit > edge compute > origin compute

✓ Cache for as long as safe (immutable assets: 1 year)
✓ Use cache versioning (URL hashes)
✓ Cache API responses where safe
```

### Practice 4: Test Globally

```
Different regions can behave differently:
   ✗ Latency varies
   ✗ Some edges fail
   ✗ Configurations propagate slowly

Tests:
   ✓ Synthetic monitoring from multiple regions
   ✓ Real User Monitoring (RUM)
   ✓ Test edges individually
```

### Practice 5: Monitor Edge Metrics

```
Track:
   ✓ Cache hit ratio (target: > 90%)
   ✓ Edge function latency
   ✓ Error rates per region
   ✓ Cold start frequency
   ✓ Origin bandwidth (should decrease!)
```

### Practice 6: Design Edge-First

```
Mindset shift:
   ✗ "Push everything to origin"
   ✓ "What can happen at the edge?"

   Examples:
   ✓ Auth at edge → reject bad requests early
   ✓ Geo at edge → route to right backend
   ✓ Bot detection → block before origin
   ✓ Personalization → at edge if possible
```

---

## 10. Real-World Example: E-Commerce

### Edge-Optimized Architecture

```
   User in India
        │
        ▼
   Cloudflare Edge (Mumbai)
        │
        ├─► Static assets (CSS, JS, images) ✓ CACHED
        │
        ├─► User auth (JWT validation) ✓ AT EDGE
        │
        ├─► Geo routing (India-specific content) ✓ AT EDGE
        │
        ├─► A/B test routing ✓ AT EDGE
        │
        ├─► Product images (cached) ✓ FROM EDGE
        │
        └─► Dynamic data → Origin
            │
            ▼
         Backend (Mumbai region)
            │
            ▼
         Database (read replica)

Result:
   ✓ 90% of requests handled at edge
   ✓ Origin sees only 10% of traffic
   ✓ Latency: 30ms (vs 250ms without edge)
   ✓ Cost: dramatically lower
```

---

## 11. Modern Edge Patterns

### Pattern 1: Image Optimization at Edge

```javascript
// Cloudflare Worker - resize images on-demand
export default {
  async fetch(request) {
    const url = new URL(request.url);
    const params = url.searchParams;
    
    // /image.jpg?w=800&h=600&q=85
    const width = params.get('w');
    const height = params.get('h');
    const quality = params.get('q');
    
    // Cloudflare Image Resizing
    return fetch(url.pathname, {
      cf: {
        image: {
          width: width,
          height: height,
          quality: quality,
          format: 'auto',  // Auto WebP/AVIF
        },
      },
    });
  }
};
```

### Pattern 2: API Aggregation at Edge

```javascript
export default {
  async fetch(request) {
    // Fan out to multiple services in parallel
    const [user, orders, recs] = await Promise.all([
      fetch('https://api.example.com/users/123'),
      fetch('https://api.example.com/users/123/orders'),
      fetch('https://recs.example.com/123'),
    ]);
    
    // Combine + return
    return new Response(JSON.stringify({
      user: await user.json(),
      orders: await orders.json(),
      recommendations: await recs.json(),
    }), {
      headers: { 'Content-Type': 'application/json' }
    });
  }
};
```

### Pattern 3: WebSocket Termination

```javascript
// Some edges support WebSockets
export default {
  async fetch(request) {
    if (request.headers.get('Upgrade') !== 'websocket') {
      return new Response('Expected WebSocket', { status: 400 });
    }
    
    // Upgrade to WebSocket
    const [client, server] = Object.values(new WebSocketPair());
    server.accept();
    
    server.addEventListener('message', event => {
      server.send(`Echo: ${event.data}`);
    });
    
    return new Response(null, { status: 101, webSocket: client });
  }
};
```

---

## 12. Summary — Key Takeaways

```
┌──────────────────────────────────────────────────────────────┐
│  ✅ Edge architecture = bring compute + data near users        │
│  ✅ CDNs cache static content at hundreds of locations         │
│  ✅ Edge functions run dynamic logic at the edge               │
│  ✅ Massive latency improvement (10x faster)                   │
│  ✅ Use cases: auth, A/B, geo, rate limit, personalization     │
│  ✅ Edge != Origin: complement, don't replace                  │
│  ✅ Cold starts much faster than traditional serverless        │
│  ✅ Challenges: debugging, state, compute limits               │
│  ✅ Cache aggressively, keep logic light                       │
│  ✅ Edge-first design mindset                                  │
└──────────────────────────────────────────────────────────────┘
```

### The Universal Rules

```
1. CACHE before compute
2. EDGE before origin
3. Lightweight functions only
4. Self-contained (avoid external calls)
5. Stateless (use edge KV for state)
6. Test from multiple regions
7. Monitor cache hit ratio (>90% goal)
8. Use CDN for ALL static content
9. Implement security at edge (DDoS, WAF)
10. Combine edge + origin for best results
```

---

## 🎬 What's Next?

In **Lecture 7**, we'll wrap up Section 7 with **Observability** — making distributed systems visible.

> **Practical file:** [06_Practical_Hands_On.md](06_Practical_Hands_On.md)

---

## 📚 References

- Cloudflare Workers documentation
- AWS CloudFront + Lambda@Edge docs
- Vercel Edge Functions guide
- *Building Real-World Apps with Edge Computing* — books
- *Web Performance Calendar* (Cloudflare blog)
