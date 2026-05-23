# CDN — Content Delivery Network

## WHAT

A **geographically distributed network of servers** (PoPs — Points of Presence) that caches static content close to users to reduce latency.

```
Without CDN:   User (Mumbai) → Origin server (US-East) = 200ms RTT
With CDN:      User (Mumbai) → CDN PoP (Mumbai) = 5ms RTT
```

**Popular CDNs:** Cloudflare, AWS CloudFront, Fastly, Akamai, Google Cloud CDN

---

## WHY Use CDN

| Problem | CDN Solution |
|---|---|
| High latency for distant users | Serve from nearest PoP |
| Origin server overload | CDN absorbs 80-95% of traffic |
| Large file downloads slow | Parallel delivery from edge |
| DDoS attacks | Absorb at CDN edge, not origin |
| SSL termination cost | CDN handles TLS at edge |

---

## HOW CDN Works

### Pull CDN (most common)
```
1. User requests image.png
2. CDN checks local cache → MISS
3. CDN fetches from origin server
4. CDN caches the response (TTL = 24h)
5. Next user request → HIT (served from cache)
```

### Push CDN
```
1. You upload content TO the CDN proactively
2. CDN distributes to all PoPs
3. Good for: large files, video, known-ahead-of-time content
```

---

## Cache Hit vs Miss

```
Cache HIT:   CDN has content → serve instantly (<5ms)
Cache MISS:  CDN fetches from origin → cache → serve (~100-200ms first time)

Cache-Control header controls TTL:
  Cache-Control: max-age=86400    → cache for 1 day
  Cache-Control: no-store         → never cache
  Cache-Control: s-maxage=3600    → CDN caches 1hr, browser follows max-age
```

---

## What CDNs Cache vs Don't Cache

| Cache (static) | Don't Cache (dynamic) |
|---|---|
| Images, videos | User-specific API responses |
| CSS, JS bundles | Authenticated content |
| HTML (static sites) | Real-time data (stock prices) |
| Font files | Shopping carts |
| ML model weights | Session data |

---

## CDN for AI/LLM Systems

```python
# 1. Cache LLM response for identical prompts
import hashlib, json
from functools import lru_cache

def cache_key(prompt: str, model: str) -> str:
    return hashlib.sha256(f"{model}:{prompt}".encode()).hexdigest()

# 2. Serve model files (weights) from CDN
# GGUF models (4-8GB) served via CloudFront → faster download
MODEL_CDN_URL = "https://cdn.example.com/models/llama-3-8b.gguf"

# 3. Static assets (UI, docs) via CDN
# API docs, playground HTML, SDK bundles → CloudFront

# 4. Edge compute (Cloudflare Workers / Lambda@Edge)
# Run lightweight inference or routing at CDN edge
```

---

## CDN Architecture in System Design

```
                    ┌─────────────────────────────┐
                    │         ORIGIN SERVER        │
                    │   (your API / object store)  │
                    └──────────────┬──────────────┘
                                   │ (fetch on miss)
           ┌───────────────────────┼───────────────────────┐
           │                       │                       │
    ┌──────▼──────┐         ┌──────▼──────┐         ┌──────▼──────┐
    │  CDN PoP    │         │  CDN PoP    │         │  CDN PoP    │
    │  US-East    │         │  EU-West    │         │  AP-South   │
    │  (Virginia) │         │  (London)   │         │  (Mumbai)   │
    └──────┬──────┘         └──────┬──────┘         └──────┬──────┘
           │                       │                       │
    ┌──────▼──────┐         ┌──────▼──────┐         ┌──────▼──────┐
    │ US users    │         │ EU users    │         │ India users  │
    └─────────────┘         └─────────────┘         └─────────────┘
```

---

## Cache Invalidation

```bash
# CloudFront — invalidate by path pattern
aws cloudfront create-invalidation \
  --distribution-id E1234567890ABC \
  --paths "/images/*" "/static/app.js"

# Versioned URLs (best practice — no invalidation needed)
# OLD: /static/app.js          → CDN caches indefinitely
# NEW: /static/app.abc123.js   → unique per build = cache forever
```

---

## REAL LIFE ANALOGY

CDN = **Amazon delivery warehouse network**  
Without CDN: Every order ships from 1 central warehouse in Delhi.
With CDN: Warehouses in every city → your order ships from your city = next day delivery.

The central warehouse (origin) only needs to restock the local warehouses (CDN PoPs), not directly serve every customer.

---

## Interview Q&A

**Q: What is the difference between CDN and a cache?**
A: A cache is a general concept (store data to avoid recomputation). A CDN is a specific type of distributed cache — physically closer to users, geographically distributed, focused on HTTP content delivery.

**Q: When should you NOT use a CDN?**
A: (1) Highly dynamic, personalised content that cannot be cached (2) Low-latency real-time systems where even 5ms matters (3) Internal services with no public internet exposure.

**Q: How does CDN help with DDoS?**
A: CDN absorbs attack traffic at the edge (across hundreds of PoPs with terabits of capacity). Origin server never sees the attack traffic. Cloudflare's network capacity is ~348 Tbps — most DDoS attacks can't exceed this.

**Q: What is cache-busting?**
A: Changing the URL/filename of a static asset when it changes (e.g., `app.v2.js`), so the CDN treats it as a new resource and fetches the updated version, while old URLs serve cached files indefinitely.
