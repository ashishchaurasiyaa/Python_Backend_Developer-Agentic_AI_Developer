# Lecture 6 — Practical Hands-On: Edge Architecture

> **Theory file:** [06_Edge_Architecture.md](06_Edge_Architecture.md)

---

## 🎯 Is Practical Mein Kya Banayenge?

Real edge implementations:

1. ✅ **Cloudflare Workers** — auth, geo, A/B
2. ✅ **CloudFront + Lambda@Edge** — image optimization
3. ✅ **Vercel Edge Functions** — Next.js integration
4. ✅ **Edge KV** — distributed storage
5. ✅ **API Aggregation** at the edge
6. ✅ **Rate limiting** at edge
7. ✅ **Bot detection** + WAF rules
8. ✅ **Multi-region** failover
9. ✅ **Performance comparison** — origin vs edge
10. ✅ **Production deployment**

By end: aap **production edge architecture** bana sakte ho.

---

## 1. ☁️ Cloudflare Workers Setup

### Install Wrangler

```bash
$ npm install -g wrangler
$ wrangler login
```

### Create Project

```bash
$ wrangler init my-edge-worker
$ cd my-edge-worker
```

### `wrangler.toml`

```toml
name = "my-edge-worker"
main = "src/index.js"
compatibility_date = "2024-01-01"

[env.production]
routes = [
  { pattern = "example.com/*", zone_name = "example.com" }
]

# KV namespace
[[kv_namespaces]]
binding = "MY_KV"
id = "abc123..."

# Durable Objects (for stateful)
[[durable_objects.bindings]]
name = "RATE_LIMITER"
class_name = "RateLimiter"
```

### `src/index.js` — Basic Worker

```javascript
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    
    // Health check
    if (url.pathname === '/health') {
      return new Response('OK', { status: 200 });
    }
    
    // Forward everything else to origin
    return fetch(request);
  }
};
```

### Deploy

```bash
$ wrangler deploy

# Worker now runs at 285+ Cloudflare edges globally!
$ curl https://example.com/health
# OK
```

---

## 2. 🌍 Geo-Based Content

### `src/geo.js`

```javascript
export default {
  async fetch(request) {
    // Cloudflare automatically detects geo
    const country = request.cf?.country || 'US';
    const continent = request.cf?.continent || 'NA';
    const city = request.cf?.city || 'Unknown';
    const timezone = request.cf?.timezone || 'UTC';
    
    // Inject geo as headers for origin
    const modifiedRequest = new Request(request, {
      headers: new Headers({
        ...Object.fromEntries(request.headers),
        'X-User-Country': country,
        'X-User-Continent': continent,
        'X-User-City': city,
        'X-User-Timezone': timezone,
      })
    });
    
    // Country-specific redirects
    const url = new URL(request.url);
    
    if (url.pathname === '/' && country === 'JP') {
      return Response.redirect('https://jp.example.com', 302);
    }
    if (url.pathname === '/' && country === 'DE') {
      return Response.redirect('https://de.example.com', 302);
    }
    
    // Block specific countries (legal compliance)
    const blockedCountries = ['XX', 'YY'];  // OFAC list
    if (blockedCountries.includes(country)) {
      return new Response('Service unavailable in your region', { 
        status: 451 
      });
    }
    
    return fetch(modifiedRequest);
  }
};
```

---

## 3. 🧪 A/B Testing at Edge

### `src/ab_test.js`

```javascript
const EXPERIMENT_NAME = 'new_signup_flow';
const VARIANT_PROBABILITY = 0.5;  // 50/50 split

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    
    // Only run experiment on signup pages
    if (!url.pathname.startsWith('/signup')) {
      return fetch(request);
    }
    
    // Get or assign variant
    const cookies = parseCookies(request.headers.get('Cookie') || '');
    let variant = cookies[`exp_${EXPERIMENT_NAME}`];
    
    if (!variant) {
      // New user - assign variant
      variant = Math.random() < VARIANT_PROBABILITY ? 'control' : 'treatment';
    }
    
    // Route to appropriate backend
    const backendUrl = variant === 'treatment'
      ? `https://v2.example.com${url.pathname}${url.search}`
      : `https://v1.example.com${url.pathname}${url.search}`;
    
    const response = await fetch(backendUrl);
    
    // Set cookie for consistency
    const newResponse = new Response(response.body, response);
    if (!cookies[`exp_${EXPERIMENT_NAME}`]) {
      newResponse.headers.append(
        'Set-Cookie',
        `exp_${EXPERIMENT_NAME}=${variant}; Path=/; Max-Age=${60 * 60 * 24 * 30}; SameSite=Lax`
      );
    }
    
    // Track impression (async, don't block)
    ctx.waitUntil(
      logImpression(env, {
        experiment: EXPERIMENT_NAME,
        variant: variant,
        country: request.cf?.country,
        timestamp: Date.now(),
      })
    );
    
    return newResponse;
  }
};

function parseCookies(cookieString) {
  const cookies = {};
  cookieString.split(';').forEach(cookie => {
    const [name, value] = cookie.trim().split('=');
    if (name && value) cookies[name] = value;
  });
  return cookies;
}

async function logImpression(env, data) {
  await env.ANALYTICS_KV.put(
    `imp:${Date.now()}:${Math.random()}`,
    JSON.stringify(data),
    { expirationTtl: 86400 * 30 }  // Keep 30 days
  );
}
```

---

## 4. 🔐 Authentication at Edge

### `src/auth.js`

```javascript
import { jwtVerify } from 'jose';

const PUBLIC_KEY = `-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...
-----END PUBLIC KEY-----`;

const PUBLIC_PATHS = ['/health', '/public/', '/login', '/static/'];

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    
    // Skip auth for public paths
    if (PUBLIC_PATHS.some(p => url.pathname.startsWith(p))) {
      return fetch(request);
    }
    
    // Extract token
    const authHeader = request.headers.get('Authorization');
    const cookieToken = parseCookies(request.headers.get('Cookie') || '')['auth_token'];
    const token = authHeader?.replace('Bearer ', '') || cookieToken;
    
    if (!token) {
      return new Response(JSON.stringify({ error: 'Unauthorized' }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' }
      });
    }
    
    try {
      // Verify JWT LOCALLY at edge (no origin round-trip!)
      const publicKey = await crypto.subtle.importKey(
        'spki',
        pemToBuffer(PUBLIC_KEY),
        { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' },
        false,
        ['verify']
      );
      
      const { payload } = await jwtVerify(token, publicKey, {
        issuer: 'auth.example.com',
        audience: 'api.example.com',
      });
      
      // Add user info as headers for backend
      const modifiedRequest = new Request(request, {
        headers: new Headers({
          ...Object.fromEntries(request.headers),
          'X-User-Id': payload.sub,
          'X-User-Email': payload.email,
          'X-User-Roles': JSON.stringify(payload.roles || []),
        })
      });
      
      return fetch(modifiedRequest);
    
    } catch (error) {
      console.error('Auth error:', error);
      return new Response(JSON.stringify({ error: 'Invalid token' }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' }
      });
    }
  }
};
```

---

## 5. 🚦 Rate Limiting at Edge

### `src/rate_limit.js`

```javascript
export default {
  async fetch(request, env) {
    const ip = request.headers.get('CF-Connecting-IP');
    const userId = request.headers.get('X-User-Id');
    
    // Use user ID if authenticated, else IP
    const key = userId || ip;
    const limit = userId ? 1000 : 100;  // Higher for authenticated
    
    // Token bucket algorithm
    const now = Date.now();
    const windowSeconds = 60;
    const windowKey = `rl:${key}:${Math.floor(now / 1000 / windowSeconds)}`;
    
    // Atomic counter via Durable Object
    const limiter = env.RATE_LIMITER.get(
      env.RATE_LIMITER.idFromName(key)
    );
    
    const currentCount = await limiter.fetch(
      new Request('https://internal/increment', {
        method: 'POST',
        body: JSON.stringify({ key: windowKey, limit })
      })
    ).then(r => r.json());
    
    if (currentCount.exceeded) {
      return new Response('Rate limit exceeded', {
        status: 429,
        headers: {
          'Retry-After': '60',
          'X-RateLimit-Limit': limit.toString(),
          'X-RateLimit-Remaining': '0',
          'X-RateLimit-Reset': (Math.floor(now / 1000) + windowSeconds).toString(),
        }
      });
    }
    
    const response = await fetch(request);
    
    // Add rate limit headers
    const newResponse = new Response(response.body, response);
    newResponse.headers.set('X-RateLimit-Limit', limit.toString());
    newResponse.headers.set('X-RateLimit-Remaining', (limit - currentCount.count).toString());
    
    return newResponse;
  }
};

// Durable Object class
export class RateLimiter {
  constructor(state, env) {
    this.state = state;
  }
  
  async fetch(request) {
    const { key, limit } = await request.json();
    const count = (await this.state.storage.get(key)) || 0;
    
    if (count >= limit) {
      return Response.json({ exceeded: true, count });
    }
    
    await this.state.storage.put(key, count + 1);
    await this.state.storage.setAlarm(Date.now() + 60000);  // Auto-expire
    
    return Response.json({ exceeded: false, count: count + 1 });
  }
}
```

---

## 6. 🤖 Bot Detection + WAF

### `src/bot_protection.js`

```javascript
export default {
  async fetch(request, env) {
    // Cloudflare bot management
    const botScore = request.cf?.botManagement?.score || 100;
    const verifiedBot = request.cf?.botManagement?.verifiedBot;
    const corporateProxy = request.cf?.botManagement?.corporateProxy;
    
    // Block low-score bots (unless verified like Googlebot)
    if (botScore < 30 && !verifiedBot) {
      // Log + block
      await env.SECURITY_LOG.put(
        `block:${Date.now()}:${request.headers.get('CF-Connecting-IP')}`,
        JSON.stringify({
          reason: 'bot',
          botScore,
          userAgent: request.headers.get('User-Agent'),
        })
      );
      
      return new Response('Access denied', { status: 403 });
    }
    
    // Show CAPTCHA for borderline
    if (botScore < 60 && request.method !== 'GET') {
      return Response.redirect('https://example.com/captcha', 302);
    }
    
    // Block known bad user agents
    const ua = request.headers.get('User-Agent') || '';
    const blockedUAs = ['python-requests', 'scrapy', 'curl'];
    if (blockedUAs.some(b => ua.toLowerCase().includes(b))) {
      // Allow some, log others
      if (!request.headers.get('X-API-Key')) {
        return new Response('Access denied', { status: 403 });
      }
    }
    
    // Pass through if all checks pass
    return fetch(request);
  }
};
```

---

## 7. 📸 Image Optimization at Edge

### Cloudflare Image Resizing

```javascript
export default {
  async fetch(request) {
    const url = new URL(request.url);
    
    // Match: /img/photo.jpg?w=800&h=600&q=85&f=webp
    if (!url.pathname.startsWith('/img/')) {
      return fetch(request);
    }
    
    const width = parseInt(url.searchParams.get('w')) || 800;
    const height = parseInt(url.searchParams.get('h')) || null;
    const quality = parseInt(url.searchParams.get('q')) || 85;
    const format = url.searchParams.get('f') || 'auto';
    
    // Cloudflare Image Resizing API
    const imageUrl = `https://origin.example.com${url.pathname}`;
    
    return fetch(imageUrl, {
      cf: {
        image: {
          width: width,
          height: height,
          quality: quality,
          format: format,  // auto = WebP/AVIF when supported
          fit: 'scale-down',
        }
      }
    });
  }
};
```

### Use in HTML

```html
<!-- Browser supports modern formats? Auto serves WebP/AVIF -->
<img src="/img/hero.jpg?w=1200&q=85" 
     srcset="/img/hero.jpg?w=400 400w,
             /img/hero.jpg?w=800 800w,
             /img/hero.jpg?w=1200 1200w"
     sizes="(max-width: 600px) 400px, (max-width: 1200px) 800px, 1200px">
```

---

## 8. 🔀 API Aggregation at Edge

### `src/api_gateway.js`

```javascript
export default {
  async fetch(request) {
    const url = new URL(request.url);
    
    // Dashboard endpoint - aggregate from multiple backends
    if (url.pathname === '/api/dashboard') {
      const userId = request.headers.get('X-User-Id');
      
      // Fan out in parallel
      const [user, orders, recs, notifs] = await Promise.allSettled([
        fetch(`https://users.api.example.com/${userId}`),
        fetch(`https://orders.api.example.com/users/${userId}/recent`),
        fetch(`https://recs.api.example.com/${userId}`),
        fetch(`https://notifications.api.example.com/${userId}`),
      ]);
      
      // Build response with graceful degradation
      const result = {
        user: user.status === 'fulfilled' ? await user.value.json() : null,
        orders: orders.status === 'fulfilled' ? await orders.value.json() : [],
        recommendations: recs.status === 'fulfilled' ? await recs.value.json() : [],
        notifications: notifs.status === 'fulfilled' ? await notifs.value.json() : [],
        timestamp: new Date().toISOString(),
      };
      
      return new Response(JSON.stringify(result), {
        headers: {
          'Content-Type': 'application/json',
          'Cache-Control': 'private, max-age=10',  // Cache 10s per user
        }
      });
    }
    
    return fetch(request);
  }
};
```

---

## 9. ☁️ AWS CloudFront + Lambda@Edge

### Lambda@Edge Function

```python
"""
Triggered at CloudFront edge.
Can modify request/response.
"""
import json
import base64

def lambda_handler(event, context):
    """Triggered at viewer-request"""
    request = event['Records'][0]['cf']['request']
    
    # Get country from CloudFront headers
    country = request.get('headers', {}).get('cloudfront-viewer-country', [{}])[0].get('value', 'US')
    
    # Redirect non-US to country-specific site
    if country == 'JP':
        return {
            'status': '302',
            'statusDescription': 'Found',
            'headers': {
                'location': [{
                    'key': 'Location',
                    'value': 'https://jp.example.com' + request['uri']
                }]
            }
        }
    
    # Add custom header
    if 'headers' not in request:
        request['headers'] = {}
    request['headers']['x-country'] = [{'key': 'X-Country', 'value': country}]
    
    return request
```

### Deploy via SAM

```yaml
# template.yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Resources:
  GeoRedirectFunction:
    Type: AWS::Serverless::Function
    Properties:
      Runtime: python3.11
      Handler: index.lambda_handler
      Role: !GetAtt LambdaEdgeRole.Arn
      AutoPublishAlias: live
  
  CloudFrontDistribution:
    Type: AWS::CloudFront::Distribution
    Properties:
      DistributionConfig:
        Origins:
          - Id: origin
            DomainName: origin.example.com
            CustomOriginConfig:
              OriginProtocolPolicy: https-only
        
        DefaultCacheBehavior:
          TargetOriginId: origin
          ViewerProtocolPolicy: redirect-to-https
          LambdaFunctionAssociations:
            - EventType: viewer-request
              LambdaFunctionARN: !Ref GeoRedirectFunction.Version
```

---

## 10. 📊 Performance Comparison

### Setup

```bash
# Test endpoint without edge
$ curl -w "@curl-format.txt" -o /dev/null -s https://origin.example.com/

# Test through edge
$ curl -w "@curl-format.txt" -o /dev/null -s https://example.com/
```

### `curl-format.txt`

```
time_namelookup:  %{time_namelookup}s
time_connect:     %{time_connect}s
time_appconnect:  %{time_appconnect}s
time_starttransfer: %{time_starttransfer}s
time_total:       %{time_total}s
```

### Sample Results

```
Without edge (direct to origin):
   time_namelookup:    0.012s
   time_connect:       0.052s (to US datacenter)
   time_appconnect:    0.124s (TLS handshake)
   time_starttransfer: 0.187s (TTFB)
   time_total:         0.234s

With edge (Cloudflare):
   time_namelookup:    0.008s
   time_connect:       0.012s (to local edge)
   time_appconnect:    0.034s
   time_starttransfer: 0.045s (TTFB!)
   time_total:         0.058s

→ 4x faster!
```

### Cache Hit Verification

```bash
$ curl -I https://example.com/static/logo.png

# First request:
HTTP/2 200
cf-cache-status: MISS
age: 0

# Second request (immediate):
HTTP/2 200
cf-cache-status: HIT
age: 5

# Third request (different geographic location via VPN):
HTTP/2 200
cf-cache-status: HIT  ← Cached at THAT edge too
age: 10
```

---

## 11. 🌍 Multi-Region Failover

### Geo Failover Setup

```javascript
const ORIGINS = {
  'NA': 'https://us.api.example.com',
  'EU': 'https://eu.api.example.com',
  'AS': 'https://asia.api.example.com',
};

const FALLBACK = 'https://us.api.example.com';

export default {
  async fetch(request) {
    const continent = request.cf?.continent || 'NA';
    const preferredOrigin = ORIGINS[continent] || FALLBACK;
    
    try {
      // Try preferred origin
      const response = await fetch(preferredOrigin + new URL(request.url).pathname, {
        ...request,
        cf: {
          // Timeout fast - failover quickly
          resolveOverride: preferredOrigin,
        },
        signal: AbortSignal.timeout(2000),  // 2s timeout
      });
      
      if (response.ok) {
        return response;
      }
      
      throw new Error(`Origin returned ${response.status}`);
    
    } catch (error) {
      console.error(`Preferred origin failed: ${error.message}, falling back`);
      
      // Try other origins
      for (const [region, origin] of Object.entries(ORIGINS)) {
        if (origin === preferredOrigin) continue;
        
        try {
          const fallbackResponse = await fetch(origin + new URL(request.url).pathname);
          if (fallbackResponse.ok) {
            return fallbackResponse;
          }
        } catch (e) {
          continue;
        }
      }
      
      return new Response('All origins unavailable', { status: 503 });
    }
  }
};
```

---

## 12. Key Learnings Summary

```
✅ Cloudflare Workers with global deployment
✅ Geo-based content + routing at edge
✅ A/B testing with cookie persistence
✅ JWT validation at edge (no origin call!)
✅ Distributed rate limiting via Durable Objects
✅ Bot detection + WAF rules
✅ Image optimization (resize, format conversion)
✅ API aggregation with graceful degradation
✅ Lambda@Edge for CloudFront
✅ Multi-region failover

🎯 Production edge stack:
   Cloudflare CDN + Workers
   + Lambda@Edge for AWS
   + Edge KV for state
   + Multi-region origins
   + Real-time analytics
```

---

## 🎬 What's Next?

In **Lecture 7**, we'll wrap up with **Observability** — making distributed systems visible.

> **Next lecture:** [07_Observability.md](07_Observability.md)

---

## 📚 Try It Yourself

1. Deploy **Cloudflare Worker** for geo routing
2. Implement **A/B test** with edge persistence
3. Build **edge-side auth** with JWT verification
4. Set up **CloudFront + Lambda@Edge**
5. Measure **before/after** latency improvement
