"""
Notification System Design — Production Patterns
=================================================
Illustrative, self-contained implementation of all major subsystems described
in 04_notification_system_design.md.  No external infrastructure (Kafka,
Redis, DB) is required to *import* or syntax-check this module; every
component that touches a network is either simulated with in-memory stubs or
gated behind a clearly-labelled "requires infrastructure" block.

Architecture recap (from the theory doc):
  Apps / Services
        │
        ▼
  Notification API  (intake, async, idempotent)
        │
        ▼ (Kafka topic: notifications.requests)
  Notification Engine  (consumer)
    ├── resolve user + preferences
    ├── throttle check  (Redis sorted-set / counter)
    ├── deduplication   (content hash, 24-h window)
    ├── scheduling      (send at user's local time)
    └── template render (event × channel × locale)
        │
        ├──► Push  sender  (FCM / APNs)
        ├──► Email sender  (SES / SendGrid)
        ├──► SMS   sender  (Twilio)
        └──► In-App store  (DB + WebSocket push)
                │
                ▼
         Delivery tracking  (webhook updates → TrackingDB)
         Retry + Dead-Letter Queue

Covered in this file
--------------------
1.  Data models  (NotificationRequest, UserPreferences, DeliveryRecord …)
2.  User preference evaluation  (should_send)
3.  Throttling  (in-memory, mirrors Redis setex pattern)
4.  Deduplication  (content-hash, 24-h window)
5.  Template engine  (event × channel × locale hierarchy)
6.  Locale-aware scheduling  (UTC send-time from user TZ + target time)
7.  Notification engine  (process_notification orchestration)
8.  Per-channel dispatch stubs  (push / email / SMS / in-app)
9.  Retry with exponential back-off + dead-letter queue
10. Delivery tracking store
11. Digest / aggregation logic
12. Idempotency key cache
13. Runnable __main__ demo (pure in-memory, no external deps)

External libraries (illustrative — not imported at module level):
    pip install fastapi uvicorn aiokafka redis aioredis pytz jinja2 structlog
"""

# ===========================================================================
# Standard-library imports only — safe to compile without any pip packages
# ===========================================================================

import asyncio
import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger("notification_system")


# ===========================================================================
# 1. ENUMERATIONS & CONSTANTS
# ===========================================================================

class Channel(str, Enum):
    PUSH   = "push"
    EMAIL  = "email"
    SMS    = "sms"
    IN_APP = "in_app"


class Priority(str, Enum):
    HIGH   = "high"    # bypass throttle for critical alerts
    NORMAL = "normal"
    LOW    = "low"


class DeliveryStatus(str, Enum):
    QUEUED    = "queued"
    SENT      = "sent"
    DELIVERED = "delivered"
    FAILED    = "failed"
    OPENED    = "opened"
    CLICKED   = "clicked"


# Throttle window: max 1 notification per (user, channel, event_type) per hour
THROTTLE_WINDOW_SECONDS: int = 3600

# Deduplication window: 24 hours
DEDUPE_WINDOW_SECONDS: int = 86_400

# Maximum per-channel retry attempts before dead-letter queue
MAX_RETRIES: int = 5


# ===========================================================================
# 2. DATA MODELS
# ===========================================================================

@dataclass
class NotificationRequest:
    """
    Intake payload published to Kafka topic 'notifications.requests'.
    The API layer assigns a UUID and timestamps before enqueuing.
    """
    user_id:       str
    event_type:    str                          # e.g. "order_paid", "marketing"
    payload:       Dict[str, Any]               # template variables
    channels:      List[Channel]                # requested channels
    priority:      Priority      = Priority.NORMAL
    scheduled_at:  Optional[datetime] = None   # None → send immediately
    locale:        Optional[str] = None        # overrides user preference
    # Assigned by the API layer:
    id:            str           = field(default_factory=lambda: str(uuid.uuid4()))
    created_at:    datetime      = field(default_factory=lambda: datetime.now(timezone.utc))
    idempotency_key: Optional[str] = None


@dataclass
class UserProfile:
    """Minimal user record returned from a user-service lookup."""
    id:         str
    email:      str
    phone:      Optional[str]
    push_token: Optional[str]   # FCM / APNs device token
    locale:     str = "en"
    timezone:   str = "UTC"     # IANA timezone string, e.g. "Asia/Kolkata"


@dataclass
class UserPreferences:
    """
    Mirrors the notification_preferences table from the theory doc.

    enabled_channels: {"push": True, "email": True, "sms": False}
    enabled_events:   {"order_paid": ["push", "email"], "marketing": []}
    quiet_hours:      {"start": "22:00", "end": "08:00"}  (user's local time)
    """
    user_id:          str
    enabled_channels: Dict[str, bool]         = field(default_factory=dict)
    enabled_events:   Dict[str, List[str]]    = field(default_factory=dict)
    quiet_hours:      Optional[Dict[str, str]] = None
    locale:           str                      = "en"


@dataclass
class DeliveryRecord:
    """
    Row in notification_deliveries table.
    Status transitions follow webhook callbacks from providers.
    """
    id:              str = field(default_factory=lambda: str(uuid.uuid4()))
    notification_id: str = ""
    user_id:         str = ""
    channel:         str = ""
    event_type:      str = ""
    status:          str = DeliveryStatus.QUEUED.value
    provider:        Optional[str] = None
    provider_id:     Optional[str] = None
    sent_at:         Optional[datetime] = None
    delivered_at:    Optional[datetime] = None
    opened_at:       Optional[datetime] = None
    clicked_at:      Optional[datetime] = None
    error:           Optional[str] = None
    metadata:        Dict[str, Any] = field(default_factory=dict)


@dataclass
class InAppNotification:
    """
    Row in in_app_notifications table.
    Served via REST + real-time WebSocket push.
    """
    id:         str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id:    str = ""
    type:       str = ""
    title:      str = ""
    body:       str = ""
    payload:    Dict[str, Any] = field(default_factory=dict)
    read_at:    Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ===========================================================================
# 3. TEMPLATE ENGINE  (event × channel × locale)
# ===========================================================================

# Template registry — in production, loaded from DB or external config service
# (never hard-coded; this is illustrative only).
TEMPLATES: Dict[str, Dict[str, Dict[str, Dict[str, str]]]] = {
    "order_paid": {
        Channel.PUSH.value: {
            "en": {
                "title": "Order #{order_id} confirmed",
                "body":  "Your payment of ${amount} was received.",
            },
            "hi": {
                "title": "Order #{order_id} confirm ho gaya",
                "body":  "${amount} ka payment confirm hua hai.",
            },
        },
        Channel.EMAIL.value: {
            "en": {
                "subject": "Payment confirmation — order #{order_id}",
                "body":    "Hi {name}, your payment of ${amount} for order #{order_id} "
                           "has been confirmed. Thank you for shopping with us!",
            },
        },
        Channel.SMS.value: {
            "en": {
                "body": "Order #{order_id} paid — ${amount}. Thanks!",
            },
        },
        Channel.IN_APP.value: {
            "en": {
                "title": "Payment confirmed",
                "body":  "Order #{order_id}: ${amount} received.",
            },
        },
    },
    "marketing": {
        Channel.EMAIL.value: {
            "en": {
                "subject": "Special offer just for you!",
                "body":    "Hi {name}, check out our latest deals.",
            },
        },
    },
    "account_login": {
        Channel.PUSH.value: {
            "en": {
                "title": "New login detected",
                "body":  "Someone signed in to your account from {city}.",
            },
        },
        Channel.EMAIL.value: {
            "en": {
                "subject": "Security alert: new login",
                "body":    "Hi {name}, a new sign-in was detected from {city} at {login_time}.",
            },
        },
    },
}

_FALLBACK_LOCALE = "en"


def render_template(
    event_type: str,
    channel: Channel,
    payload: Dict[str, Any],
    locale: str = "en",
) -> Optional[Dict[str, str]]:
    """
    Render a notification template for the given event × channel × locale.
    Falls back to 'en' when the requested locale is absent.
    Returns None if no template is registered for this combination.

    >>> result = render_template("order_paid", Channel.EMAIL, {"order_id": "123", "amount": "9.99", "name": "Alice"})
    >>> result["subject"]
    'Payment confirmation — order #123'
    """
    event_templates = TEMPLATES.get(event_type)
    if not event_templates:
        log.warning("render_template: no templates for event_type=%s", event_type)
        return None

    channel_templates = event_templates.get(channel.value)
    if not channel_templates:
        log.debug("render_template: no template for channel=%s event=%s", channel.value, event_type)
        return None

    locale_template = channel_templates.get(locale) or channel_templates.get(_FALLBACK_LOCALE)
    if not locale_template:
        return None

    try:
        return {key: value.format(**payload) for key, value in locale_template.items()}
    except KeyError as exc:
        log.error("render_template: missing payload key %s for event=%s", exc, event_type)
        return None


# ===========================================================================
# 4. USER PREFERENCE EVALUATION
# ===========================================================================

def should_send(channel: Channel, event_type: str, prefs: UserPreferences) -> bool:
    """
    Return True only when all preference gates pass.

    Rules (from theory doc):
    1. The channel must be enabled globally.
    2. If the event has an explicit channel list, the channel must appear in it.
       An empty list means the event is fully disabled.
    3. If the event is not explicitly configured, default to allow.
    """
    # Gate 1: global channel toggle
    if not prefs.enabled_channels.get(channel.value, True):
        log.debug("should_send: channel=%s disabled for user=%s", channel.value, prefs.user_id)
        return False

    # Gate 2: per-event channel allowlist
    if event_type in prefs.enabled_events:
        allowed = prefs.enabled_events[event_type]
        if channel.value not in allowed:
            log.debug(
                "should_send: channel=%s not in allowlist for event=%s user=%s",
                channel.value, event_type, prefs.user_id,
            )
            return False

    return True


def is_quiet_hours(prefs: UserPreferences, now_utc: Optional[datetime] = None) -> bool:
    """
    Return True if the current UTC moment falls within the user's quiet hours.
    Quiet hours are stored in the user's local clock (HH:MM strings).

    This implementation approximates local time via UTC offset from the user's
    timezone string using stdlib only.  Production code would use pytz or
    zoneinfo for full IANA database support.
    """
    if not prefs.quiet_hours:
        return False

    now_utc = now_utc or datetime.now(timezone.utc)

    # Approximate local time — replace with pytz.timezone(user_tz).localize(...)
    # in production when pytz is available.
    local_now = now_utc  # simplified: assume UTC == local for stub

    start_str = prefs.quiet_hours.get("start", "22:00")
    end_str   = prefs.quiet_hours.get("end",   "08:00")

    start_h, start_m = (int(x) for x in start_str.split(":"))
    end_h,   end_m   = (int(x) for x in end_str.split(":"))

    current_minutes = local_now.hour * 60 + local_now.minute
    start_minutes   = start_h * 60 + start_m
    end_minutes     = end_h   * 60 + end_m

    # Handle overnight windows (e.g. 22:00 → 08:00)
    if start_minutes > end_minutes:
        return current_minutes >= start_minutes or current_minutes < end_minutes
    return start_minutes <= current_minutes < end_minutes


# ===========================================================================
# 5. LOCALE-AWARE SCHEDULING
# ===========================================================================

def schedule_for_local_time(
    user_tz_offset_hours: float,
    target_time_str: str,
    reference_date: Optional[date] = None,
) -> datetime:
    """
    Compute the UTC datetime at which to send a notification that should arrive
    at `target_time_str` (e.g. "09:00") in the user's local time zone.

    `user_tz_offset_hours` is the UTC offset in hours (e.g. +5.5 for IST).
    Production code replaces this with pytz.timezone(user_tz).localize(...).

    Example
    -------
    >>> utc_dt = schedule_for_local_time(5.5, "09:00")
    >>> utc_dt.hour  # 09:00 IST = 03:30 UTC
    3
    """
    ref = reference_date or date.today()
    hour, minute = (int(x) for x in target_time_str.split(":"))

    # Build a naive local datetime, then subtract the UTC offset
    local_naive = datetime(ref.year, ref.month, ref.day, hour, minute, 0)
    offset = timedelta(hours=user_tz_offset_hours)
    utc_dt = local_naive - offset
    return utc_dt.replace(tzinfo=timezone.utc)


# ===========================================================================
# 6. IN-MEMORY STUBS FOR REDIS / KAFKA / DB
#    (replace with real client calls in production)
# ===========================================================================

class _InMemoryKV:
    """
    Simulates Redis key-value store with TTL expiry.
    Mirrors the Redis SETEX / EXISTS / GET / ZADD pattern used throughout.
    """

    def __init__(self) -> None:
        self._store: Dict[str, Any] = {}
        self._expiry: Dict[str, float] = {}

    def _is_alive(self, key: str) -> bool:
        exp = self._expiry.get(key)
        if exp is None:
            return key in self._store
        return time.monotonic() < exp

    def exists(self, key: str) -> bool:
        return self._is_alive(key)

    def get(self, key: str) -> Optional[Any]:
        if self._is_alive(key):
            return self._store.get(key)
        return None

    def set(self, key: str, value: Any) -> None:
        self._store[key] = value

    def setex(self, key: str, ttl_seconds: int, value: Any) -> None:
        self._store[key] = value
        self._expiry[key] = time.monotonic() + ttl_seconds

    def delete(self, key: str) -> None:
        self._store.pop(key, None)
        self._expiry.pop(key, None)

    def zadd(self, name: str, mapping: Dict[str, float]) -> None:
        if name not in self._store:
            self._store[name] = {}
        self._store[name].update(mapping)

    def zrangebyscore(self, name: str, min_score: float, max_score: float) -> List[str]:
        zset = self._store.get(name, {})
        return [k for k, score in zset.items() if min_score <= score <= max_score]

    def zrem(self, name: str, *members: str) -> None:
        zset = self._store.get(name, {})
        for m in members:
            zset.pop(m, None)


class _InMemoryMessageBus:
    """
    Simulates Kafka topics as simple in-memory queues.
    In production, replace with aiokafka.AIOKafkaProducer / AIOKafkaConsumer.
    """

    def __init__(self) -> None:
        self._topics: Dict[str, List[Dict[str, Any]]] = {}

    def send(self, topic: str, message: Dict[str, Any]) -> None:
        self._topics.setdefault(topic, []).append(message)

    def poll(self, topic: str) -> List[Dict[str, Any]]:
        messages = self._topics.pop(topic, [])
        return messages


class _InMemoryDeliveryStore:
    """
    Simulates the notification_deliveries and in_app_notifications tables.
    """

    def __init__(self) -> None:
        self.deliveries: Dict[str, DeliveryRecord] = {}
        self.in_app:     Dict[str, InAppNotification] = {}
        self.dlq:        List[Dict[str, Any]] = []           # dead-letter queue

    def upsert_delivery(self, record: DeliveryRecord) -> None:
        self.deliveries[record.id] = record

    def save_in_app(self, notif: InAppNotification) -> None:
        self.in_app[notif.id] = notif

    def mark_read(self, notif_id: str, user_id: str) -> bool:
        notif = self.in_app.get(notif_id)
        if notif and notif.user_id == user_id:
            notif.read_at = datetime.now(timezone.utc)
            return True
        return False

    def list_in_app(self, user_id: str, limit: int = 20) -> List[InAppNotification]:
        results = [n for n in self.in_app.values() if n.user_id == user_id]
        results.sort(key=lambda n: n.created_at, reverse=True)
        return results[:limit]

    def to_dlq(self, message: Dict[str, Any]) -> None:
        self.dlq.append(message)


# Global singletons (equivalent to injected application-scope clients)
_kv    = _InMemoryKV()
_bus   = _InMemoryMessageBus()
_store = _InMemoryDeliveryStore()

# Simulated user registry (in production: async DB lookup)
_USERS: Dict[str, UserProfile] = {}
_PREFS: Dict[str, UserPreferences] = {}
_IDEMPOTENCY_CACHE: Dict[str, str] = {}     # idempotency_key → notification_id


# ===========================================================================
# 7. THROTTLING  (mirrors Redis SETEX pattern)
# ===========================================================================

def is_throttled(user_id: str, channel: Channel, event_type: str) -> bool:
    """
    Return True if the user has already received a notification for this
    (channel, event_type) combination within the throttle window.

    Mirrors the Redis pattern from the theory doc:
        key = f"throttle:{user_id}:{channel}:{event_type}"
        if redis.exists(key): return True
        redis.setex(key, 3600, 1)
    """
    key = f"throttle:{user_id}:{channel.value}:{event_type}"
    if _kv.exists(key):
        log.debug("throttle: hit for user=%s channel=%s event=%s", user_id, channel.value, event_type)
        return True
    _kv.setex(key, THROTTLE_WINDOW_SECONDS, 1)
    return False


def bypass_throttle_for_high_priority(priority: Priority) -> bool:
    """High-priority notifications (e.g. security alerts) skip throttle checks."""
    return priority == Priority.HIGH


# ===========================================================================
# 8. DEDUPLICATION  (content-hash, 24-h window)
# ===========================================================================

def _content_hash(event_type: str, channel: Channel, payload: Dict[str, Any]) -> str:
    """Stable SHA-256 hash of event + channel + sorted payload."""
    raw = json.dumps(
        {"event": event_type, "channel": channel.value, "payload": payload},
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def is_duplicate(user_id: str, event_type: str, channel: Channel, payload: Dict[str, Any]) -> bool:
    """
    Return True if an identical notification (same content hash) was already
    dispatched to this user within the past 24 hours.

    Mirrors the Redis pattern from the theory doc:
        key = f"dedupe:{user_id}:{content_hash}"
    """
    chash = _content_hash(event_type, channel, payload)
    key   = f"dedupe:{user_id}:{chash}"
    if _kv.exists(key):
        log.debug("dedupe: duplicate detected for user=%s key=%s", user_id, key)
        return True
    _kv.setex(key, DEDUPE_WINDOW_SECONDS, 1)
    return False


# ===========================================================================
# 9. SCHEDULING  (Redis sorted-set approach from theory doc)
# ===========================================================================

def schedule_notification(notif_id: str, send_at_utc: datetime) -> None:
    """
    Enqueue a notification for future delivery using a Redis sorted set.
    Score = Unix timestamp so zrangebyscore can retrieve due items.
    """
    ts = send_at_utc.timestamp()
    _kv.zadd("scheduled_notifs", {notif_id: ts})
    log.info("schedule: notif_id=%s queued for %s UTC", notif_id, send_at_utc.isoformat())


def poll_scheduled_notifications() -> List[str]:
    """
    Retrieve all notification IDs whose scheduled_at has passed.
    Called by the scheduler worker every N seconds.
    """
    now_ts = time.time()
    due = _kv.zrangebyscore("scheduled_notifs", 0, now_ts)
    for notif_id in due:
        _kv.zrem("scheduled_notifs", notif_id)
    return due


# ===========================================================================
# 10. IDEMPOTENCY KEY CACHE  (mirrors Redis GET/SETEX pattern from theory doc)
# ===========================================================================

def check_idempotency(idempotency_key: Optional[str]) -> Optional[str]:
    """Return the existing notification_id if this key was already processed."""
    if not idempotency_key:
        return None
    cache_key = f"notif_idem:{idempotency_key}"
    return _kv.get(cache_key)


def record_idempotency(idempotency_key: Optional[str], notif_id: str) -> None:
    """Cache the result of a processed idempotency key for 24 hours."""
    if not idempotency_key:
        return
    cache_key = f"notif_idem:{idempotency_key}"
    _kv.setex(cache_key, DEDUPE_WINDOW_SECONDS, notif_id)


# ===========================================================================
# 11. API LAYER  (intake — normally a FastAPI endpoint)
# ===========================================================================

def api_create_notification(req: NotificationRequest) -> Dict[str, str]:
    """
    Thin intake layer.  Validates idempotency, assigns an ID, and publishes to
    the Kafka topic.  Returns immediately with status='queued'.

    Production equivalent (from theory doc):
        @app.post("/notifications")
        async def create_notification(req: NotificationRequest, ...):
            ...
            await kafka.send("notifications.requests", {...})
            return {"id": notif_id, "status": "queued"}
    """
    # Idempotency check — return cached result without re-publishing
    existing_id = check_idempotency(req.idempotency_key)
    if existing_id:
        log.info("api: duplicate request, returning cached id=%s", existing_id)
        return {"id": existing_id, "status": "queued (idempotent)"}

    # Publish to Kafka topic
    message: Dict[str, Any] = {
        "id":           req.id,
        "user_id":      req.user_id,
        "event_type":   req.event_type,
        "payload":      req.payload,
        "channels":     [c.value for c in req.channels],
        "priority":     req.priority.value,
        "scheduled_at": req.scheduled_at.isoformat() if req.scheduled_at else None,
        "locale":       req.locale,
        "created_at":   req.created_at.isoformat(),
    }
    _bus.send("notifications.requests", message)
    record_idempotency(req.idempotency_key, req.id)
    log.info("api: notification queued id=%s user=%s event=%s", req.id, req.user_id, req.event_type)
    return {"id": req.id, "status": "queued"}


# ===========================================================================
# 12. PER-CHANNEL DISPATCH STUBS
# ===========================================================================

class RetriableError(Exception):
    """Transient provider error — eligible for exponential back-off retry."""


class NonRetriableError(Exception):
    """Permanent error (e.g. invalid token) — do not retry."""


def _send_push(user: UserProfile, content: Dict[str, str], notif_id: str) -> str:
    """
    Stub: send via FCM / APNs.
    Production: POST to https://fcm.googleapis.com/fcm/send with device token.
    Returns provider message ID.
    """
    if not user.push_token:
        raise NonRetriableError(f"No push token for user {user.id}")
    provider_id = f"fcm_{uuid.uuid4().hex[:8]}"
    log.info(
        "push: sent to token=%s title='%s' notif_id=%s provider_id=%s",
        user.push_token[:12] + "…", content.get("title", ""), notif_id, provider_id,
    )
    return provider_id


def _send_email(user: UserProfile, content: Dict[str, str], notif_id: str) -> str:
    """
    Stub: send via Amazon SES / SendGrid.
    Production: boto3 ses.send_email(...) or sendgrid.send(Message(...)).
    Returns provider message ID.
    """
    provider_id = f"ses_{uuid.uuid4().hex[:8]}"
    log.info(
        "email: sent to=%s subject='%s' notif_id=%s provider_id=%s",
        user.email, content.get("subject", content.get("title", "")), notif_id, provider_id,
    )
    return provider_id


def _send_sms(user: UserProfile, content: Dict[str, str], notif_id: str) -> str:
    """
    Stub: send via Twilio.
    Production: client.messages.create(body=content["body"], to=user.phone, ...).
    Returns provider message SID.
    """
    if not user.phone:
        raise NonRetriableError(f"No phone number for user {user.id}")
    provider_id = f"twilio_{uuid.uuid4().hex[:8]}"
    log.info(
        "sms: sent to=%s body='%s…' notif_id=%s provider_id=%s",
        user.phone, content.get("body", "")[:40], notif_id, provider_id,
    )
    return provider_id


def _save_in_app(user: UserProfile, content: Dict[str, str], notif_id: str, event_type: str) -> str:
    """
    Persist an in-app notification row and simulate a WebSocket push.
    Production: INSERT row → publish to Redis channel → WS subscribers push to client.
    """
    notif = InAppNotification(
        user_id    = user.id,
        type       = event_type,
        title      = content.get("title", ""),
        body       = content.get("body", ""),
        payload    = {},
        created_at = datetime.now(timezone.utc),
    )
    _store.save_in_app(notif)
    # Simulate Redis pub/sub push (production: redis.publish(f"user:{user.id}:notifications", ...))
    log.info(
        "in_app: saved id=%s for user=%s [WebSocket push simulated]",
        notif.id, user.id,
    )
    return notif.id


# ===========================================================================
# 13. DELIVERY TRACKING
# ===========================================================================

def track_delivery(
    notif_id:    str,
    user_id:     str,
    channel:     Channel,
    event_type:  str,
    status:      DeliveryStatus,
    provider:    Optional[str] = None,
    provider_id: Optional[str] = None,
    error:       Optional[str] = None,
) -> DeliveryRecord:
    """
    Upsert a delivery record.  Webhook callbacks call this again to advance
    status from 'sent' to 'delivered', 'opened', 'clicked', etc.
    """
    record = DeliveryRecord(
        notification_id = notif_id,
        user_id         = user_id,
        channel         = channel.value,
        event_type      = event_type,
        status          = status.value,
        provider        = provider,
        provider_id     = provider_id,
        sent_at         = datetime.now(timezone.utc) if status == DeliveryStatus.SENT else None,
        error           = error,
    )
    _store.upsert_delivery(record)
    log.debug(
        "track: notif=%s channel=%s status=%s", notif_id, channel.value, status.value,
    )
    return record


# ===========================================================================
# 14. RETRY WITH EXPONENTIAL BACK-OFF + DEAD-LETTER QUEUE
# ===========================================================================

async def send_with_retry(
    send_fn:    Any,                    # callable: (user, content, notif_id) -> str
    user:       UserProfile,
    content:    Dict[str, str],
    notif_id:   str,
    channel:    Channel,
    event_type: str,
    max_retries: int = MAX_RETRIES,
) -> Optional[str]:
    """
    Call `send_fn` with exponential back-off on RetriableError.
    On NonRetriableError or exhausted retries, log to the dead-letter queue.

    Back-off schedule: 1 s, 2 s, 4 s, 8 s, 16 s  (capped at 300 s).

    Theory doc pattern:
        for attempt in range(max_retries):
            try:
                return await send(notif)
            except RetriableError:
                backoff = min(2 ** attempt, 300)
                await asyncio.sleep(backoff)
            except NonRetriableError:
                ...
                return None
        await kafka.send("notifications.dlq", notif.dict())
    """
    for attempt in range(max_retries):
        try:
            result = send_fn(user, content, notif_id)
            track_delivery(notif_id, user.id, channel, event_type, DeliveryStatus.SENT,
                           provider_id=result)
            return result
        except NonRetriableError as exc:
            log.error(
                "retry: non-retriable error for notif=%s channel=%s: %s",
                notif_id, channel.value, exc,
            )
            track_delivery(notif_id, user.id, channel, event_type, DeliveryStatus.FAILED,
                           error=str(exc))
            return None
        except (RetriableError, Exception) as exc:
            backoff = min(2 ** attempt, 300)
            log.warning(
                "retry: attempt %d/%d for notif=%s channel=%s — backing off %ds: %s",
                attempt + 1, max_retries, notif_id, channel.value, backoff, exc,
            )
            if attempt < max_retries - 1:
                await asyncio.sleep(backoff)

    # All retries exhausted — send to dead-letter queue
    log.error(
        "dlq: all %d retries exhausted for notif=%s channel=%s",
        max_retries, notif_id, channel.value,
    )
    _store.to_dlq({"notification_id": notif_id, "channel": channel.value})
    track_delivery(notif_id, user.id, channel, event_type, DeliveryStatus.FAILED,
                   error="max retries exhausted")
    return None


# ===========================================================================
# 15. DISPATCH  (route to the correct channel handler)
# ===========================================================================

def _dispatch_channel(
    channel:    Channel,
    user:       UserProfile,
    content:    Dict[str, str],
    notif_id:   str,
    event_type: str,
) -> Optional[str]:
    """
    Synchronous dispatch helper.  Wrapped by send_with_retry for async callers.
    Returns a provider ID string on success, raises on failure.
    """
    if channel == Channel.PUSH:
        return _send_push(user, content, notif_id)
    if channel == Channel.EMAIL:
        return _send_email(user, content, notif_id)
    if channel == Channel.SMS:
        return _send_sms(user, content, notif_id)
    if channel == Channel.IN_APP:
        return _save_in_app(user, content, notif_id, event_type)
    raise NonRetriableError(f"Unknown channel: {channel}")


# ===========================================================================
# 16. NOTIFICATION ENGINE  (Kafka consumer logic)
# ===========================================================================

async def process_notification(message: Dict[str, Any]) -> None:
    """
    Core engine: consumes one Kafka message and orchestrates all subsystems.

    Steps (from theory doc):
    1. Resolve user profile.
    2. Load user preferences.
    3. For each requested channel:
       a. Preference gate.
       b. Throttle gate (skipped for HIGH priority).
       c. Deduplication gate.
       d. Quiet-hours / scheduling gate.
       e. Render template.
       f. Dispatch with retry.
    """
    notif_id   = message["id"]
    user_id    = message["user_id"]
    event_type = message["event_type"]
    payload    = message["payload"]
    priority   = Priority(message.get("priority", Priority.NORMAL.value))
    locale_override = message.get("locale")

    scheduled_at_raw = message.get("scheduled_at")
    scheduled_at: Optional[datetime] = None
    if scheduled_at_raw:
        scheduled_at = datetime.fromisoformat(scheduled_at_raw)
        if scheduled_at.tzinfo is None:
            scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)

    channels = [Channel(c) for c in message.get("channels", [])]

    # Resolve user (stub: look up in-memory registry)
    user = _USERS.get(user_id)
    if not user:
        log.error("engine: unknown user_id=%s — dropping notif=%s", user_id, notif_id)
        return

    # Resolve preferences
    prefs = _PREFS.get(user_id, UserPreferences(user_id=user_id))

    # Effective locale: request override > user preference > default
    effective_locale = locale_override or prefs.locale or "en"

    log.info(
        "engine: processing notif=%s event=%s user=%s channels=%s",
        notif_id, event_type, user_id, [c.value for c in channels],
    )

    for channel in channels:
        # Gate 1: user preference
        if not should_send(channel, event_type, prefs):
            log.info("engine: skipping channel=%s (preference gate)", channel.value)
            continue

        # Gate 2: quiet hours — defer to scheduled delivery
        if is_quiet_hours(prefs):
            log.info("engine: quiet hours active — deferring channel=%s", channel.value)
            schedule_notification(notif_id, datetime.now(timezone.utc) + timedelta(hours=1))
            continue

        # Gate 3: scheduled delivery
        if scheduled_at and scheduled_at > datetime.now(timezone.utc):
            log.info(
                "engine: scheduling notif=%s for %s", notif_id, scheduled_at.isoformat(),
            )
            schedule_notification(notif_id, scheduled_at)
            continue

        # Gate 4: throttle (skipped for HIGH priority)
        if not bypass_throttle_for_high_priority(priority):
            if is_throttled(user_id, channel, event_type):
                log.info(
                    "engine: throttled user=%s channel=%s event=%s",
                    user_id, channel.value, event_type,
                )
                continue

        # Gate 5: deduplication
        if is_duplicate(user_id, event_type, channel, payload):
            log.info(
                "engine: duplicate suppressed user=%s channel=%s event=%s",
                user_id, channel.value, event_type,
            )
            continue

        # Render template
        content = render_template(event_type, channel, payload, effective_locale)
        if not content:
            log.warning(
                "engine: no template for event=%s channel=%s locale=%s — skipping",
                event_type, channel.value, effective_locale,
            )
            continue

        # Dispatch with retry
        await send_with_retry(
            send_fn    = lambda u, c, nid, ch=channel, et=event_type: _dispatch_channel(ch, u, c, nid, et),
            user       = user,
            content    = content,
            notif_id   = notif_id,
            channel    = channel,
            event_type = event_type,
        )


async def run_engine_once() -> int:
    """
    Poll the Kafka topic once and process all pending messages.
    Returns the count of messages processed.
    In production this runs as an infinite consumer loop partitioned by user_id.
    """
    messages = _bus.poll("notifications.requests")
    for msg in messages:
        await process_notification(msg)
    return len(messages)


# ===========================================================================
# 17. DIGEST / AGGREGATION
# ===========================================================================

def aggregate_digest(
    user_id:    str,
    channel:    Channel,
    period_min: int = 60,
) -> Dict[str, Any]:
    """
    Inspect pending notifications for a user on a given channel within the
    last `period_min` minutes.  When there are more than 3 items, bundle them
    into a digest rather than sending individually.

    Theory doc pattern:
        if len(pending) > 3:
            send_digest(user_id, pending)
        else:
            for n in pending: send(n)
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=period_min)
    recent = [
        r for r in _store.deliveries.values()
        if r.user_id == user_id
        and r.channel == channel.value
        and r.status == DeliveryStatus.QUEUED.value
        and r.sent_at and r.sent_at >= cutoff
    ]

    if len(recent) > 3:
        log.info(
            "digest: %d items for user=%s channel=%s — sending digest instead",
            len(recent), user_id, channel.value,
        )
        return {"mode": "digest", "count": len(recent), "items": [r.id for r in recent]}

    log.info(
        "digest: %d items for user=%s channel=%s — sending individually",
        len(recent), user_id, channel.value,
    )
    return {"mode": "individual", "count": len(recent), "items": [r.id for r in recent]}


# ===========================================================================
# 18. WEBHOOK HANDLER  (provider callbacks advance delivery status)
# ===========================================================================

def handle_sendgrid_webhook(events: List[Dict[str, Any]]) -> int:
    """
    Process SendGrid event webhook to update delivery status.

    Theory doc pattern:
        @app.post("/webhooks/sendgrid")
        async def sendgrid_webhook(events):
            for event in events:
                UPDATE notification_deliveries SET status = $1 WHERE provider_id = $2
    """
    updated = 0
    status_map = {
        "delivered": DeliveryStatus.DELIVERED,
        "open":      DeliveryStatus.OPENED,
        "click":     DeliveryStatus.CLICKED,
        "bounce":    DeliveryStatus.FAILED,
        "dropped":   DeliveryStatus.FAILED,
    }

    for event in events:
        sg_id  = event.get("sg_message_id", "")
        ev_type = event.get("event", "")
        new_status = status_map.get(ev_type)
        if not new_status:
            continue

        for record in _store.deliveries.values():
            if record.provider_id == sg_id:
                record.status = new_status.value
                if new_status == DeliveryStatus.DELIVERED:
                    record.delivered_at = datetime.now(timezone.utc)
                elif new_status == DeliveryStatus.OPENED:
                    record.opened_at = datetime.now(timezone.utc)
                elif new_status == DeliveryStatus.CLICKED:
                    record.clicked_at = datetime.now(timezone.utc)
                updated += 1
                log.info(
                    "webhook: updated provider_id=%s to status=%s", sg_id, new_status.value,
                )

    return updated


# ===========================================================================
# 19. IN-APP READ ENDPOINT  (marks notification as read)
# ===========================================================================

def mark_in_app_read(notif_id: str, user_id: str) -> bool:
    """
    Equivalent of the theory-doc endpoint:
        POST /notifications/{id}/read
        UPDATE in_app_notifications SET read_at = now()
        WHERE id = $1 AND user_id = $2
    """
    success = _store.mark_read(notif_id, user_id)
    if success:
        log.info("mark_read: notif=%s user=%s", notif_id, user_id)
    return success


# ===========================================================================
# 20. RUNNABLE DEMO  (no external infrastructure required)
# ===========================================================================

async def _run_demo() -> None:
    """
    End-to-end walkthrough of the notification system using in-memory stubs.
    Demonstrates: intake → engine → channel dispatch → delivery tracking.
    """
    print("\n" + "=" * 70)
    print("  Notification System Design — Demo")
    print("=" * 70 + "\n")

    # --- Seed user registry ------------------------------------------------
    alice_id = "user-alice-001"
    _USERS[alice_id] = UserProfile(
        id         = alice_id,
        email      = "alice@example.com",
        phone      = "+91-9876543210",
        push_token = "fcm-token-alice-xyz123",
        locale     = "en",
        timezone   = "Asia/Kolkata",
    )
    _PREFS[alice_id] = UserPreferences(
        user_id          = alice_id,
        enabled_channels = {"push": True, "email": True, "sms": True, "in_app": True},
        enabled_events   = {
            # marketing only via email; push is disabled for marketing
            "marketing": ["email"],
        },
        quiet_hours      = {"start": "22:00", "end": "07:00"},
        locale           = "en",
    )

    # --- Scenario 1: order_paid — all channels ----------------------------
    print("--- Scenario 1: order_paid notification (all channels) ---")
    req1 = NotificationRequest(
        user_id    = alice_id,
        event_type = "order_paid",
        payload    = {"order_id": "ORD-4567", "amount": "1,299.00", "name": "Alice"},
        channels   = [Channel.PUSH, Channel.EMAIL, Channel.SMS, Channel.IN_APP],
        priority   = Priority.HIGH,
        idempotency_key = "idem-order-4567",
    )
    result1 = api_create_notification(req1)
    print(f"  API response: {result1}\n")

    processed1 = await run_engine_once()
    print(f"  Engine processed {processed1} message(s)\n")

    # --- Scenario 2: idempotent duplicate request -------------------------
    print("--- Scenario 2: duplicate request with same idempotency key ---")
    req2 = NotificationRequest(
        user_id    = alice_id,
        event_type = "order_paid",
        payload    = {"order_id": "ORD-4567", "amount": "1,299.00", "name": "Alice"},
        channels   = [Channel.EMAIL],
        idempotency_key = "idem-order-4567",  # same key as req1
    )
    result2 = api_create_notification(req2)
    print(f"  API response (should be cached): {result2}\n")

    # --- Scenario 3: marketing — push should be preference-filtered --------
    print("--- Scenario 3: marketing notification (push blocked by prefs) ---")
    req3 = NotificationRequest(
        user_id    = alice_id,
        event_type = "marketing",
        payload    = {"name": "Alice"},
        channels   = [Channel.PUSH, Channel.EMAIL],
        priority   = Priority.LOW,
    )
    api_create_notification(req3)
    await run_engine_once()
    print()

    # --- Scenario 4: scheduling for user's local 09:00 IST ----------------
    print("--- Scenario 4: schedule for 09:00 IST ---")
    utc_send_time = schedule_for_local_time(
        user_tz_offset_hours = 5.5,     # IST = UTC+5:30
        target_time_str      = "09:00",
    )
    print(f"  09:00 IST = {utc_send_time.strftime('%H:%M')} UTC\n")

    # --- Scenario 5: throttle demonstration --------------------------------
    print("--- Scenario 5: throttle (2nd order_paid push within 1 hour) ---")
    req5 = NotificationRequest(
        user_id    = alice_id,
        event_type = "order_paid",
        payload    = {"order_id": "ORD-9999", "amount": "500.00", "name": "Alice"},
        channels   = [Channel.PUSH],
        priority   = Priority.NORMAL,   # normal priority → throttle applies
    )
    api_create_notification(req5)
    await run_engine_once()
    print()

    # --- Scenario 6: in-app read ----------------------------------------
    print("--- Scenario 6: mark in-app notification as read ---")
    in_app_items = _store.list_in_app(alice_id)
    if in_app_items:
        target = in_app_items[0]
        mark_in_app_read(target.id, alice_id)
        print(f"  Marked notif={target.id[:12]}… as read\n")
    else:
        print("  No in-app notifications found\n")

    # --- Scenario 7: SendGrid webhook ------------------------------------
    print("--- Scenario 7: process a simulated SendGrid webhook ---")
    # Find a sent email delivery record to simulate the webhook
    email_records = [
        r for r in _store.deliveries.values()
        if r.channel == "email" and r.provider_id
    ]
    if email_records:
        fake_events = [{"event": "delivered", "sg_message_id": email_records[0].provider_id}]
        updated = handle_sendgrid_webhook(fake_events)
        print(f"  Webhook updated {updated} record(s)\n")
    else:
        print("  No email delivery records to simulate webhook against\n")

    # --- Summary -----------------------------------------------------------
    print("--- Delivery Summary ---")
    for rec in _store.deliveries.values():
        print(
            f"  notif={rec.notification_id[:8]}…  channel={rec.channel:<8}"
            f"  status={rec.status:<10}  provider_id={rec.provider_id or 'n/a'}"
        )

    print("\n--- Dead-Letter Queue ---")
    if _store.dlq:
        for item in _store.dlq:
            print(f"  {item}")
    else:
        print("  (empty — no failures)")

    print("\n" + "=" * 70)
    print("  Demo complete.")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(_run_demo())
