# Design Ad Server / Online Advertising Platform

---

## 1. Requirements

### Functional
- Advertisers create campaigns (creative, targeting, budget, bid).
- Publishers send ad requests for impression slots.
- Ad selection in real time: match request to best ad.
- Track impression, click, conversion events.
- Frequency capping (don't show same ad to user > N times/day).
- Budget pacing (don't burn daily budget by 10am).
- Real-time bidding (RTB) integration for external demand.
- Reporting dashboard for advertisers.
- Brand safety (no ad on flagged content).

### Non-Functional
- 1M ad requests/sec at peak.
- Response time < 100ms total (advertiser sees the page in ~200ms).
- 99.99% availability.
- Eventually consistent reporting (5-min lag acceptable).
- Strong consistency on budget enforcement.

---

## 2. Scale Estimation

| Metric | Number |
|---|---|
| Ad requests/sec peak | 1M |
| Active campaigns | 100K |
| Ad creatives | 1M (banners, videos) |
| Impressions/day | 50B |
| Clicks/day | 500M (1% CTR) |
| Conversions/day | 5M (1% of clicks) |
| Tracking storage | 50B × 200 bytes | 10 TB/day |
| User profiles | 1B unique IDs |

---

## 3. High-Level Architecture

```
              Publishers              Advertisers
                 │                          │
                 │ (ad req)            (campaigns)
                 ▼                          ▼
        ┌────────────┐            ┌─────────────┐
        │ Ad Edge    │            │ Campaign    │
        │ Service    │            │ Mgmt API    │
        │ (1M QPS)   │            └──────┬──────┘
        └─────┬──────┘                   │
              │                          │
   ┌──────────┼────────────┐      ┌──────▼──────┐
   │          │            │      │ Postgres    │
┌──▼───┐ ┌────▼────┐ ┌─────▼──┐   │ (campaigns) │
│Target│ │ Bid /   │ │Frequen.│   └─────────────┘
│ing   │ │ Rank    │ │ Cap    │
└──┬───┘ └────┬────┘ └────┬───┘
   │          │            │
   └──────────┼────────────┘
              │
        ┌─────▼──────┐
        │ Event      │   ─→  Kafka  ─→  Aggregator
        │ Tracker    │                        │
        └────────────┘                        ▼
                                       ┌──────────────┐
                                       │ Reporting    │
                                       │ (Clickhouse) │
                                       └──────────────┘
```

---

## 4. The Ad Request Flow (100ms budget)

```
0ms   Publisher → Ad Edge: GET /ad?slot=...&user_cookie=...
5ms   Edge: cookie sync → user_profile lookup (Redis, in-memory)
10ms  Targeting filter: match user attrs to campaign targeting rules
30ms  Eligible pool: ~50-500 ads
40ms  Bid + rank: bid_amount × predicted_CTR × quality_score
60ms  Frequency cap check (Redis)
70ms  Budget check (campaigns with budget remaining)
75ms  Pick winner
80ms  Log impression intent → Kafka
85ms  Return creative URL + tracking pixel
100ms Done
```

---

## 5. Ad Edge Service

In-memory ad inventory, low latency.

### Data layout
- Campaigns + creatives in process memory (refreshed every minute).
- User profile cache in Redis.
- Frequency cap in Redis.

```python
class AdEdge:
    def __init__(self):
        self.campaigns: dict = {}  # in-memory, refreshed via gossip / pull
        self.refresh_loop()

    async def select_ad(self, req: AdRequest) -> AdResponse:
        # 1. User profile
        user = await self.get_user_profile(req.user_id)

        # 2. Targeting filter
        eligible = self.filter_targeting(user, req.context)

        # 3. Budget + frequency caps
        eligible = await self.filter_budget(eligible)
        eligible = await self.filter_frequency(user, eligible)

        # 4. Rank
        scored = [(ad, self.score(ad, user, req)) for ad in eligible]
        winner = max(scored, key=lambda x: x[1])[0] if scored else None

        # 5. Log + return
        if winner:
            await self.log_impression(winner, user, req)
            return AdResponse(creative=winner.creative_url, tracker=tracking_pixel)
        return AdResponse(no_ad=True)

    def score(self, ad, user, req):
        return ad.bid_cpm * predict_ctr(ad, user) * ad.quality_score
```

---

## 6. Targeting Engine

Match request to ads based on attributes:
- Geographic (country, city).
- Demographic (age, gender, language).
- Behavioral (interests, recent browsing).
- Contextual (page topic, keywords).
- Device (mobile, desktop, app).

### Index design — inverted index per attribute
```
country:US        → [campaign_1, campaign_5, campaign_42, ...]
country:IN        → [campaign_2, ...]
age:18-24         → [campaign_1, ...]
interest:cars     → [campaign_5, ...]
```

Algorithm:
```python
def find_matching(user, context):
    # AND across attributes
    sets = [
        self.index.get(f"country:{user.country}"),
        self.index.get(f"interest:{user.interest}"),
        ...
    ]
    return set.intersection(*sets)
```

For 100K campaigns × 50 attr each = 5M index entries → fits in memory.

### Hierarchical / range targeting
Age `25-30` matches campaigns targeting `18-50`. Use range trees or interval trees.

---

## 7. Bid + Predicted CTR

### Bid_CPM × pCTR × quality
- **bid_cpm**: advertiser's bid per 1000 impressions.
- **pCTR**: predicted click-through-rate, ML model trained on historical clicks.
- **quality_score**: creative quality + landing page experience.

### pCTR model
- Trained offline: features (user, campaign, context).
- Real-time inference: gradient-boosted trees (~0.5ms) or precomputed lookup table.

```python
class PCtrModel:
    def __init__(self):
        self.model = xgboost.load("ctr_model.bin")

    def predict(self, ad, user, context) -> float:
        features = build_features(ad, user, context)
        return self.model.predict([features])[0]
```

---

## 8. Real-Time Bidding (External Demand)

OpenRTB protocol for integrating external DSPs (Demand-Side Platforms).

```
Publisher → Ad Edge → broadcast to N DSPs (100ms total)
                          │
                       (each bids on impression)
                          │
                    Best bid wins
                          │
                    Return ad to publisher
```

### Latency-critical
- Parallel HTTP/2 calls to all DSPs.
- 50ms timeout — slow DSPs lose.
- Persistent connections to known DSPs.

```python
async def rtb_auction(req: AdRequest, dsps: list[DSP]) -> Bid:
    bid_req = build_openrtb_request(req)
    tasks = [dsp.bid(bid_req, timeout=0.05) for dsp in dsps]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    valid_bids = [b for b in results if isinstance(b, Bid)]
    return max(valid_bids, key=lambda b: b.price) if valid_bids else None
```

---

## 9. Frequency Capping

"Show ad X no more than 3 times to user Y per day."

### Implementation: Redis counter

```python
async def check_freq_cap(user_id, campaign_id, max_per_day=3):
    key = f"fcap:{user_id}:{campaign_id}:{date.today()}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, 86400)
    return count <= max_per_day
```

**Trade-off:** Increments before serve, so if ad isn't actually served (e.g., budget exhausted), we over-count. Compensate by adjusting limits.

### Cross-device frequency capping
Same user on phone + laptop should share cap.
- Need user identity resolution (logged in users get persistent ID; cookie-based for anonymous).

---

## 10. Budget Pacing

Daily budget = $1000. Want to spend gradually, not all in first hour.

### Algorithms

**Smooth pacing:**
- Target spend rate = budget / 86400 sec.
- Track actual spend; throttle if ahead, accelerate if behind.

**Multi-armed bandit:**
- ε-greedy: 90% of time pick highest scoring ad, 10% explore.

```python
async def should_serve(campaign, current_time):
    spent_today = await get_spent(campaign.id, today)
    expected_spent = campaign.budget * (current_time.hour / 24)
    if spent_today > expected_spent * 1.1:  # ahead by 10%
        return random.random() < 0.3   # serve 30% of time
    return True
```

### Hard budget cap
- Distributed counter problem at 1M QPS — Redis with eventual consistency.
- Slight overspend possible (~1%); accept it or use stricter coordination.

---

## 11. Event Tracking

Every impression/click/conversion → Kafka.

### Event structure
```json
{
  "event_type": "click",
  "ad_id": "...",
  "campaign_id": "...",
  "user_id": "...",
  "publisher": "...",
  "ts": "...",
  "context": { ... },
  "ip": "...",
  "user_agent": "..."
}
```

### Tracking pixel
- Returned with ad: 1x1 transparent GIF with query params.
- Browser fetches → server logs.

```html
<img src="https://track.adsrv.com/impression?ad_id=abc&user=xyz" width="1" height="1">
```

### Click tracking
- Click URL: redirect through tracker → log → redirect to advertiser.

```python
@app.get("/click")
async def track_click(ad_id, user_id, destination):
    await kafka.produce("clicks", {...})
    return RedirectResponse(destination)
```

---

## 12. Click Fraud Detection

Click fraud = bots clicking ads, fake users, etc.

### Signals
- High click velocity from single IP.
- Click without impression (visit URL directly).
- No mouse movement / weird patterns.
- IP from data center range.
- User-agent mismatch.

### Detection
Async stream-processing job (Flink/Spark) flags suspicious clicks.

```python
def is_fraud(click, recent_clicks):
    if click.ip in datacenter_ips: return True
    if recent_clicks_from(click.ip, 60) > 100: return True
    if click.user_agent in known_bot_uas: return True
    if not click.mouse_events: return True
    return False
```

Fraudulent clicks excluded from advertiser billing.

---

## 13. Reporting

Advertisers see: impressions, clicks, CTR, conversions, spend.

### Pipeline
```
Events → Kafka → Stream processor (Flink) →
  Aggregations per minute → Clickhouse
```

### Clickhouse table
```sql
CREATE TABLE ad_events (
    event_date Date,
    event_time DateTime,
    campaign_id UUID,
    ad_id UUID,
    publisher String,
    event_type String,
    user_id String,
    cost Float64
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(event_date)
ORDER BY (campaign_id, event_date, event_time);
```

### Query
```sql
SELECT
    toDate(event_time) AS day,
    countIf(event_type='impression') AS imp,
    countIf(event_type='click') AS clicks,
    countIf(event_type='conversion') AS conversions,
    SUM(cost) AS spend
FROM ad_events
WHERE campaign_id = ? AND event_date >= today() - 30
GROUP BY day;
```

Clickhouse handles billion-row aggregates in seconds.

---

## 14. User Profile

Profile = attributes used for targeting.

### Sources
- 1st party: site behavior, purchases, account info.
- 3rd party (deprecated): cookies from data brokers.

### Storage
- Profile: ~5KB per user × 1B users = 5 TB.
- Redis sharded for hot users.
- Cassandra/DynamoDB for full profile store.

### Cookie sync
Cross-domain identity resolution via cookie matching.

---

## 15. Creative Storage

- Image/video creatives stored in S3.
- CDN (CloudFront) serves to end users.
- Pre-cached at edge (highest-traffic creatives).

```
s3://ad-creatives/{advertiser_id}/{ad_id}/banner_300x250.jpg
```

---

## 16. Brand Safety

- Don't serve luxury car ad on news article about car crash.
- Content classification (NLP) tags pages.
- Advertisers specify exclusions ("no violence content").
- Filter at ad selection time.

---

## 17. Multi-Region

Edge servers in 20+ regions globally.
- Each region has full ad inventory cache.
- Campaign updates propagate via gossip (~30s).
- Budget shared across regions — eventually consistent.
- User profile from nearest region with replication.

---

## 18. APIs

```
GET  /ad?slot=...&context=...&user=...    # serve ad (publisher)
POST /campaigns                            # create campaign
GET  /campaigns/{id}/stats                 # reporting
POST /events/track                         # impression/click pixel
POST /rtb/bid                              # OpenRTB bid request
```

---

## 19. Trade-offs

| Decision | Trade-off |
|---|---|
| In-memory ads | Fast, but RAM per server scales with inventory |
| Inverted-index targeting | O(1) filter, costly to update |
| Eventual budget | Slight overspend, simpler scaling |
| External RTB | Higher revenue, latency risk |
| Tracking pixels | Universal, blocked by ad blockers |
| Clickhouse for reports | Cheap, complex ops |

---

## 20. Follow-up Questions

- **"How would you handle cookie-less world (third-party cookies deprecation)?"** → First-party identifiers (login, email hash), contextual targeting, Topics API, FLEDGE/Protected Audience.
- **"How to A/B test ranking changes?"** → Random assign users to bucket A/B at edge; track conversion lift.
- **"What about privacy regulations (GDPR, CCPA)?"** → Consent management platform; serve non-targeted ads to non-consenting users; honor data deletion.
- **"Latency to first ad on slow connection?"** → Pre-fetch top ad while page loads; serve generic ad if network slow.
- **"How to handle hot campaigns (everyone wants same impression)?"** → Hash-based partitioning of campaign data, additional replicas, second-price auction to dampen overbidding.
- **"How to detect bot traffic in real-time?"** → CAPTCHA challenges (sparingly), TLS fingerprinting, device fingerprint coherence.
