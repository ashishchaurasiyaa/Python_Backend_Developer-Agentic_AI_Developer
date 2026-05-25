# Back-of-Envelope Estimation — System Design Calculations

## WHAT

Quick mental math to estimate system capacity **before designing** — helps you choose the right architecture, DB, and infrastructure.

Interviewers test this to check if you think like a real engineer, not just a coder.

---

## WHY It Matters

- Tells you: do you need 1 server or 100?
- Tells you: SQL or NoSQL?
- Tells you: cache needed or not?
- Tells you: how much storage per year?

---

## Key Numbers to Memorize

### Time
```
1 ms   = 10^-3 s
1 µs   = 10^-6 s
1 ns   = 10^-9 s

L1 cache:      ~1 ns
L2 cache:      ~4 ns
RAM read:      ~100 ns
SSD read:      ~100 µs  (100,000 ns)
HDD read:      ~10 ms   (10,000,000 ns)
Network RT:    ~1-100 ms (same DC: 0.5ms, cross-continent: 150ms)
```

### Throughput
```
1 Gbps network  = 125 MB/s
SSD write:      ~500 MB/s
HDD write:      ~100 MB/s
PostgreSQL:     ~10k-50k simple queries/sec
Redis:          ~100k ops/sec
Kafka:          ~1M msgs/sec per broker
```

### Data Sizes
```
char:       1 byte
int/float:  4-8 bytes
UUID:       16 bytes
URL:        ~100 bytes
Tweet:      ~280 bytes
Profile:    ~1 KB
Photo:      ~200 KB (thumbnail) / ~3 MB (full)
Video min:  ~50 MB (720p)
```

### Scale Reference
```
1 million   = 10^6
1 billion   = 10^9
1 trillion  = 10^12

1 KB = 10^3 bytes
1 MB = 10^6 bytes
1 GB = 10^9 bytes
1 TB = 10^12 bytes
1 PB = 10^15 bytes
```

---

## Estimation Framework (5 steps)

```
1. Clarify scope   — DAU, read/write ratio, geography
2. Estimate QPS    — queries per second
3. Estimate storage — per day, per year
4. Estimate bandwidth — in/out per second
5. Choose architecture based on numbers
```

---

## WORKED EXAMPLE 1 — Design Twitter

### Step 1: Clarify
- 300 million DAU (daily active users)
- 50% tweet per day
- 10 tweets read per user per day

### Step 2: QPS

```
Writes:
  150M users × 1 tweet/day = 150M tweets/day
  150M / 86,400 sec ≈ 1,750 writes/sec (peak: ~3x) = ~5,000 writes/sec

Reads:
  300M × 10 reads/day = 3B reads/day
  3B / 86,400 ≈ 34,700 reads/sec (peak: ~100k/sec)
  
Read:Write ratio = ~20:1 → heavy read system → cache aggressively
```

### Step 3: Storage

```
Per tweet:  content(280B) + user_id(8B) + timestamp(8B) + metadata(50B) ≈ 350 bytes
Daily:      150M × 350 bytes = 52.5 GB/day
Yearly:     52.5 × 365 ≈ 19 TB/year (text only)

Media (10% tweets have images, avg 200KB):
  15M × 200KB = 3 TB/day = 1.1 PB/year → need object storage (S3)
```

### Step 4: Bandwidth

```
Writes: 1,750 writes/sec × 350 bytes = ~600 KB/s
Reads:  34,700 reads/sec × 350 bytes = ~12 MB/s  (text)
```

### Step 5: Architecture Conclusion
- Read:Write 20:1 → Cache timeline (Redis)
- 1.1 PB/yr images → S3 / CDN
- 5k writes/sec → Kafka fanout, not synchronous
- Single SQL DB not enough → sharding by user_id

---

## WORKED EXAMPLE 2 — URL Shortener

### Assumptions
- 100M new URLs/day
- 10:1 read:write → 1B redirects/day

### QPS
```
Writes: 100M / 86,400 ≈ 1,200/sec
Reads:  1B / 86,400    ≈ 11,600/sec (peak ~50k/sec)
```

### Storage
```
Per URL record:
  short_code(7 bytes) + long_url(200 bytes) + timestamp(8B) + user_id(8B) ≈ 225 bytes

Daily:  100M × 225 bytes = 22.5 GB/day
5 year: 22.5 × 365 × 5  = 41 TB  → manageable in single DB + sharding
```

### Short Code Space
```
7-char base62 (a-z, A-Z, 0-9):  62^7 = 3.5 trillion combinations
100M URLs/day × 365 × 10 years = 365 billion total → fits in 62^7 ✓
```

---

## WORKED EXAMPLE 3 — LLM API Service (Agentic AI context)

### Assumptions
- 1M DAU using AI chat
- 10 requests per user per day
- Avg request: 1,000 input tokens + 500 output tokens
- Model: gpt-4o-mini

### QPS
```
10M requests/day / 86,400 ≈ 116 req/sec
Peak (8am-10pm): 116 × 2 ≈ 230 req/sec
```

### Token throughput
```
Input:  116 req/sec × 1,000 tokens = 116,000 tokens/sec
Output: 116 req/sec × 500 tokens  = 58,000 tokens/sec
```

### Storage (conversation history)
```
Per message: ~2 KB (tokens + metadata)
Per session: 20 messages = 40 KB
Daily: 1M users × 40 KB = 40 GB/day
Monthly: 40 × 30 = 1.2 TB → PostgreSQL + S3 archival
```

### Cost estimate
```
gpt-4o-mini: $0.15/1M input tokens, $0.60/1M output tokens
Daily cost:
  Input:  116,000 tokens/sec × 86,400 = 10B tokens → $1,500/day
  Output: 58,000 × 86,400 = 5B tokens → $3,000/day
  Total: ~$4,500/day = ~$135,000/month
  → Need aggressive caching for repeated queries!
```

---

## Python Helper for Estimations

```python
def qps(daily_events: float, peak_multiplier: float = 3) -> dict:
    """Calculate QPS from daily events."""
    avg = daily_events / 86_400
    return {"avg_qps": avg, "peak_qps": avg * peak_multiplier}

def storage_per_year(daily_bytes: float) -> dict:
    """Convert daily bytes to yearly storage."""
    yearly = daily_bytes * 365
    return {
        "daily_GB":  daily_bytes / 1e9,
        "yearly_TB": yearly / 1e12,
        "5yr_TB":    yearly * 5 / 1e12,
    }

# Example: Twitter tweets
r = qps(150_000_000)       # 150M writes/day
print(f"Write QPS: avg={r['avg_qps']:.0f}, peak={r['peak_qps']:.0f}")

s = storage_per_year(150_000_000 * 350)  # 150M tweets × 350 bytes
print(f"Storage: {s['daily_GB']:.1f} GB/day, {s['yearly_TB']:.1f} TB/year")
```

---

## Interview Q&A

**Q: How many servers to handle 10,000 requests/sec?**
A: Depends on request complexity. Simple API: 1 server handles ~1,000-5,000 req/sec. So 2-10 servers + load balancer. Always add redundancy: if 2 servers needed → deploy 3.

**Q: How do you estimate storage for a photo-sharing app?**
A: DAU × photos per user per day × avg photo size. 10M DAU × 2 photos × 3MB = 60 TB/day → need object storage (S3), CDN for reads.

**Q: Why is peak QPS important?**
A: Systems must handle peak load (not average). Use peak = 2-3× average for daily peaks, and plan for viral/event spikes (10×). Always size for peak.
