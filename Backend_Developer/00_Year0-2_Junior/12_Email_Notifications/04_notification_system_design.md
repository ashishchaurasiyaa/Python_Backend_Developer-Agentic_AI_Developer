# 04 — Notification System Design

> The architecture pattern for handling user notifications across email, push, SMS, in-app. Production-grade design.

---

## Requirements

### Functional
- Send notifications across channels: push (FCM, APNs), email, SMS, in-app.
- Per-user channel preferences.
- Templates with personalization.
- Multi-language support.
- Scheduling (send at user's local 9am).
- Deduplication.
- Throttling.
- Delivery tracking.
- Bounce / unsubscribe handling.

### Non-Functional
- 10M notifications/day, peak 100K/sec.
- p99 latency < 5s end-to-end.
- 99.9% delivery success.
- Multi-region.
- Audit trail.

---

## High-Level Architecture

```
   Apps/Services
        │
        ▼
   ┌──────────────────────┐
   │  Notification API    │  (intake)
   └─────────┬────────────┘
             │
             ▼
   ┌──────────────────────┐
   │   Kafka              │  topic: notifications.requests
   └─────────┬────────────┘
             │
             ▼
   ┌──────────────────────┐
   │  Notification Engine │  (consumer)
   │  - Resolve user      │
   │  - Pick channels      │
   │  - Check prefs        │
   │  - Apply throttle     │
   │  - Render templates   │
   │  - Schedule           │
   └─────┬─┬─┬─┬───────────┘
         │ │ │ │
         ▼ ▼ ▼ ▼
       (Push) (Email) (SMS) (In-App)
        │     │      │      │
        ▼     ▼      ▼      ▼
       FCM   SES   Twilio   DB+WS
        │     │      │      │
        └─────┴──────┴──────┘
              │
              ▼
         Webhook updates
              │
              ▼
         Tracking DB
```

---

## API Layer (Intake)

```python
@app.post("/notifications")
async def create_notification(req: NotificationRequest):
    notif_id = str(uuid.uuid4())
    await kafka.send("notifications.requests", {
        "id": notif_id,
        "user_id": req.user_id,
        "event_type": req.event_type,
        "payload": req.payload,
        "channels": req.channels,
        "priority": req.priority,
        "scheduled_at": req.scheduled_at,
        "created_at": datetime.utcnow().isoformat(),
    })
    return {"id": notif_id, "status": "queued"}
```

API is thin; pushes to Kafka for buffering and async processing.

### Idempotency
Use `idempotency_key` header:
```python
@app.post("/notifications")
async def create(req, idempotency_key: str = Header(None)):
    if idempotency_key:
        cached = await redis.get(f"notif_idem:{idempotency_key}")
        if cached: return json.loads(cached)
    # ... create + cache
```

---

## Notification Engine (Consumer)

Reads from Kafka and processes.

```python
async def process_notification(req):
    user = await get_user(req.user_id)
    prefs = await get_preferences(user.id)

    for channel in req.channels:
        if not should_send(channel, req.event_type, prefs):
            continue
        if await is_throttled(user.id, channel, req.event_type):
            continue
        if req.scheduled_at and req.scheduled_at > now():
            await schedule_for_later(req, channel)
            continue

        content = render_template(req.event_type, channel, req.payload, user.locale)
        await dispatch(channel, user, content, req.id)


async def dispatch(channel, user, content, notif_id):
    handlers = {
        "push": send_push,
        "email": send_email,
        "sms": send_sms,
        "in_app": save_in_app
    }
    try:
        result = await handlers[channel](user, content)
        await track_delivery(notif_id, channel, "sent", result)
    except Exception as e:
        await track_delivery(notif_id, channel, "failed", error=str(e))
        await retry_or_dlq(notif_id, channel)
```

---

## Preferences

```sql
CREATE TABLE notification_preferences (
    user_id        UUID PRIMARY KEY,
    enabled_channels JSONB,     -- {"push": true, "email": true, "sms": false}
    enabled_events  JSONB,       -- {"order_paid": ["push","email"], "marketing": []}
    quiet_hours    JSONB,         -- {"start": "22:00", "end": "08:00", "tz": "..."}
    locale         TEXT,
    last_updated   TIMESTAMPTZ
);
```

```python
def should_send(channel, event, prefs):
    if not prefs.enabled_channels.get(channel, True):
        return False
    if event in prefs.enabled_events:
        return channel in prefs.enabled_events[event]
    return True  # default allow
```

---

## Templates

Hierarchy:
- Event type (e.g., `order_paid`).
- Channel (push, email, sms).
- Locale (en, hi, es).
- Template string with variables.

```yaml
order_paid:
  push:
    en:
      title: "Order #{order_id} paid"
      body: "Your payment of ${amount} was confirmed"
    hi:
      title: "Order #{order_id} ka payment ho gaya"
      body: "${amount} ka payment confirm ho gaya hai"
  email:
    en:
      subject: "Payment confirmation"
      html_template: "order_paid_en.html"
```

```python
def render(event, channel, payload, locale="en"):
    template = TEMPLATES[event][channel][locale]
    return {
        "title": template["title"].format(**payload),
        "body": template["body"].format(**payload)
    }
```

For HTML emails: Jinja2 or MJML.

---

## Throttling & Deduplication

### Throttle: prevent spam
```python
async def is_throttled(user_id, channel, event_type):
    # Max 1 notification per type per hour
    key = f"throttle:{user_id}:{channel}:{event_type}"
    if await redis.exists(key):
        return True
    await redis.setex(key, 3600, 1)
    return False
```

### Dedupe: same content not sent twice
```python
async def is_duplicate(user_id, content_hash):
    key = f"dedupe:{user_id}:{content_hash}"
    if await redis.exists(key):
        return True
    await redis.setex(key, 86400, 1)
    return False
```

---

## Scheduling

For "send tomorrow at 9am":

### Option A: Redis sorted set
```python
async def schedule(notif_id, send_at_ts):
    await redis.zadd("scheduled_notifs", {notif_id: send_at_ts})

# Worker
async def scheduler_loop():
    while True:
        now_ts = time.time()
        due = await redis.zrangebyscore("scheduled_notifs", 0, now_ts, start=0, num=100)
        for notif_id in due:
            await redis.zrem("scheduled_notifs", notif_id)
            notif = await db.fetch_notif(notif_id)
            await dispatch(notif)
        await asyncio.sleep(5)
```

### Option B: Database column
```sql
CREATE TABLE pending_notifications (
    id          UUID,
    scheduled_at TIMESTAMPTZ,
    payload     JSONB,
    INDEX (scheduled_at) WHERE status = 'pending'
);

-- Scheduler polls:
SELECT * FROM pending_notifications
WHERE scheduled_at <= now() AND status = 'pending'
ORDER BY scheduled_at LIMIT 100
FOR UPDATE SKIP LOCKED;
```

### Option C: Cron-style with Celery beat
Less flexible but simple.

---

## Locale & Time Zone

For "Send at 9am local time":
```python
import pytz

def schedule_for_local_time(user_tz, target_time_str):
    tz = pytz.timezone(user_tz)
    local_dt = datetime.combine(date.today(), time.fromisoformat(target_time_str))
    utc_dt = tz.localize(local_dt).astimezone(pytz.utc)
    return utc_dt.timestamp()
```

Store user TZ; compute UTC send time.

---

## Delivery Tracking

```sql
CREATE TABLE notification_deliveries (
    id              UUID PRIMARY KEY,
    notification_id UUID,
    user_id         UUID,
    channel         TEXT,
    event_type      TEXT,
    status          TEXT,    -- 'queued', 'sent', 'delivered', 'failed', 'opened', 'clicked'
    provider        TEXT,
    provider_id     TEXT,
    sent_at         TIMESTAMPTZ,
    delivered_at    TIMESTAMPTZ NULL,
    opened_at       TIMESTAMPTZ NULL,
    clicked_at      TIMESTAMPTZ NULL,
    error           TEXT,
    metadata        JSONB
);
CREATE INDEX ON notification_deliveries(user_id, sent_at DESC);
```

Webhook handlers update status:
```python
@app.post("/webhooks/sendgrid")
async def sendgrid_webhook(events: list[dict]):
    for event in events:
        await db.execute(
            "UPDATE notification_deliveries "
            "SET status = $1, delivered_at = $2 "
            "WHERE provider_id = $3",
            event["event"], parse_ts(event["timestamp"]), event["sg_message_id"]
        )
```

---

## Retry & Dead Letter

```python
async def send_with_retry(notif, max_retries=5):
    for attempt in range(max_retries):
        try:
            return await send(notif)
        except RetriableError:
            backoff = min(2 ** attempt, 300)
            await asyncio.sleep(backoff)
        except NonRetriableError as e:
            await track_delivery(notif.id, status="failed", error=str(e))
            return None
    # All retries exhausted
    await kafka.send("notifications.dlq", notif.dict())
```

DLQ messages reviewed manually or by alerting.

---

## In-App Notifications

For UI badges, notification center.

```sql
CREATE TABLE in_app_notifications (
    id          UUID PRIMARY KEY,
    user_id     UUID,
    type        TEXT,
    title       TEXT,
    body        TEXT,
    payload     JSONB,
    read_at     TIMESTAMPTZ NULL,
    created_at  TIMESTAMPTZ
);
CREATE INDEX ON in_app_notifications(user_id, created_at DESC);
```

Real-time delivery:
- Insert to DB.
- Publish to Redis: `user:{uid}:notifications`.
- WS subscriber pushes to active session.

Mark as read:
```python
@app.post("/notifications/{id}/read")
async def read(id: UUID, user=Depends(get_user)):
    await db.execute(
        "UPDATE in_app_notifications SET read_at = now() WHERE id = $1 AND user_id = $2",
        id, user.id
    )
```

---

## Aggregation / Digest

Instead of 10 emails per hour: combine into one digest.

```python
async def aggregate_digest(user_id, channel, period_min=60):
    pending = await db.fetch(
        "SELECT * FROM notifications WHERE user_id = $1 AND channel = $2 "
        "AND status = 'pending' AND created_at > now() - interval '%d min'",
        user_id, channel, period_min
    )
    if len(pending) > 3:
        # Send digest instead of individual
        await send_digest(user_id, pending)
    else:
        for n in pending:
            await send(n)
```

---

## Multi-Tenancy

For SaaS:
- Tenant has own templates, branding.
- Per-tenant rate limits.
- Per-tenant analytics.

```sql
CREATE TABLE tenant_templates (
    tenant_id UUID,
    event_type TEXT,
    channel TEXT,
    locale TEXT,
    body TEXT,
    PRIMARY KEY (tenant_id, event_type, channel, locale)
);
```

---

## Analytics Dashboard

Per-tenant metrics:
- Sent / delivered / failed counts.
- Open rate, click rate.
- Channel performance.
- Top events triggering notifications.

Query Clickhouse / time-series DB for fast aggregations.

---

## Compliance Surface

- User can opt out of all marketing (one-click).
- Logs of who unsubscribed when.
- Retention policy (delete after 90 days, etc.).
- GDPR delete: when user account deleted, purge their notification history.

---

## Common Pitfalls

### 1. Sending in API request
Slow; blocks API. Always queue.

### 2. No throttling
User receives 50 notifications per hour → uninstalls.

### 3. Hard-coded templates in code
Can't update without deploy. Use DB or external config.

### 4. No retries for transient failures
Lower delivery rates.

### 5. Ignoring webhooks
Bounce stats not tracked → reputation degrades silently.

### 6. Forgetting user preferences
Sending to disabled channels.

### 7. Same notification across all channels
Spammy. Use channel hierarchy: push first, email if no push, etc.

### 8. No timezone awareness
3am push wakes user up.

---

## Scaling to 10M/day

- API: stateless, horizontal scale.
- Kafka topics partitioned by user_id (or event_type).
- Engine consumers: 1 per partition.
- Redis cluster for throttles + dedupe.
- DB sharded by user_id.
- Provider connections pooled per region.

---

## Real-World Examples

### Slack
Push for mentions, in-app for everything, email digest for unread.

### Booking.com
Push on booking confirmation; SMS day before; email receipts.

### Instagram
Push for likes/comments; aggregated digest if many.

### LinkedIn
Email digest of network activity; opt-in granularity.

### Stripe (developer-facing)
Email + dashboard; webhooks for system-to-system.

---

## TL;DR

- Multi-channel: push, email, SMS, in-app.
- API → Kafka → Engine → Per-channel sender.
- User preferences + throttling + dedupe mandatory.
- Templates with locale + channel + event type.
- Track delivery via webhooks.
- Schedule for user's local time.
- Aggregate to avoid spam.
- DLQ for failures.
- Stateless services for scale.
- Industry-standard architecture for any consumer-facing app.
