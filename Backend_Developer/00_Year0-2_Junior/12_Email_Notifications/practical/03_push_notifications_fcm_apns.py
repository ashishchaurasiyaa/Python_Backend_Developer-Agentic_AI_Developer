"""
Push Notifications — FCM & APNs: Production Patterns
=====================================================

Covers the complete backend push-notification stack:

  1.  Device token management (registration, refresh, soft-delete)
  2.  FCM HTTP v1 API — single-device send (OAuth 2.0 service account auth)
  3.  Firebase Admin SDK — single send, multicast, topic-based send
  4.  APNs direct HTTP/2 — JWT provider-token auth
  5.  Notification types — alert, silent/data, rich, provisional
  6.  User preference gating (per-category, quiet hours)
  7.  Rate limiting / throttle guard
  8.  Multi-channel notification dispatcher
  9.  Template renderer
  10. Delivery tracking data model
  11. Web push (VAPID / pywebpush)

External libraries are NOT installed in this learning environment; every
provider call is illustrated as close-to-production code wrapped in a
dry-run stub so the module imports and runs without real credentials.

Dependencies (install when integrating for real):
  # pip install google-auth google-auth-httplib2 requests
  # pip install firebase-admin
  # pip install httpx[http2]
  # pip install pyjwt cryptography
  # pip install pywebpush

Python 3.9+  |  run:  python 03_push_notifications_fcm_apns.py
"""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Logger — use structlog in production; stdlib here for zero dependencies.
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ==========================================================================
# 1. DATA MODELS — device tokens, preferences, delivery records
# ==========================================================================

class Platform(str, Enum):
    """Supported device platforms."""
    IOS = "ios"
    ANDROID = "android"
    WEB = "web"


class NotificationStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    THROTTLED = "throttled"


@dataclass
class DeviceToken:
    """
    One row in the device_tokens table.

    DDL equivalent:
        CREATE TABLE device_tokens (
            user_id    UUID,
            token      TEXT,
            platform   TEXT,
            created_at TIMESTAMPTZ,
            last_used  TIMESTAMPTZ,
            PRIMARY KEY (user_id, token)
        );

    Tokens can change on uninstall, OS update, or app reset.  Always upsert
    on each app launch; never assume a stored token is still valid.
    """
    user_id: str
    token: str
    platform: Platform
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_used: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def touch(self) -> None:
        """Update last_used timestamp on each registration refresh."""
        self.last_used = datetime.now(timezone.utc)


@dataclass
class QuietHours:
    """
    User-defined quiet window; e.g., {"start": "22:00", "end": "07:00"}.
    Stored as JSONB in the notification_preferences table.
    """
    start_hour: int   # 22
    end_hour: int     # 7

    def is_active(self) -> bool:
        """Return True if the current UTC hour falls inside the quiet window."""
        current_hour = datetime.now(timezone.utc).hour
        if self.start_hour > self.end_hour:  # crosses midnight
            return current_hour >= self.start_hour or current_hour < self.end_hour
        return self.start_hour <= current_hour < self.end_hour


@dataclass
class NotificationPreferences:
    """
    DDL equivalent:
        CREATE TABLE notification_preferences (
            user_id     UUID PRIMARY KEY,
            push        JSONB,        -- {"chat": true, "marketing": false}
            email       JSONB,
            quiet_hours JSONB
        );
    """
    user_id: str
    push: Dict[str, bool] = field(default_factory=lambda: {"chat": True, "marketing": True})
    email: Dict[str, bool] = field(default_factory=lambda: {"chat": True, "marketing": False})
    quiet_hours: Optional[QuietHours] = None

    def is_push_enabled(self, category: str) -> bool:
        """Return False if the user has opted out of this push category."""
        return self.push.get(category, True)

    def is_email_enabled(self, category: str) -> bool:
        return self.email.get(category, True)

    def in_quiet_hours(self) -> bool:
        """Return True when no push should be delivered (user asleep)."""
        if self.quiet_hours is None:
            return False
        return self.quiet_hours.is_active()


@dataclass
class DeliveryRecord:
    """
    One row in the notification_deliveries table.

    DDL equivalent:
        CREATE TABLE notification_deliveries (
            id            UUID,
            user_id       UUID,
            channel       TEXT,
            event_type    TEXT,
            status        TEXT,
            provider_id   TEXT,
            sent_at       TIMESTAMPTZ,
            delivered_at  TIMESTAMPTZ NULL,
            error         TEXT NULL
        );
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    channel: str = ""
    event_type: str = ""
    status: NotificationStatus = NotificationStatus.PENDING
    provider_id: Optional[str] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    error: Optional[str] = None

    def mark_sent(self, provider_id: Optional[str] = None) -> None:
        self.status = NotificationStatus.SENT
        self.sent_at = datetime.now(timezone.utc)
        self.provider_id = provider_id

    def mark_failed(self, error: str) -> None:
        self.status = NotificationStatus.FAILED
        self.error = error

    def mark_delivered(self) -> None:
        self.status = NotificationStatus.DELIVERED
        self.delivered_at = datetime.now(timezone.utc)


# ==========================================================================
# 2. IN-MEMORY STORE (replace with real DB in production)
# ==========================================================================

# In production: asyncpg / SQLAlchemy / Prisma pointing at PostgreSQL.
_device_tokens: Dict[str, List[DeviceToken]] = {}          # user_id -> tokens
_preferences: Dict[str, NotificationPreferences] = {}      # user_id -> prefs
_deliveries: List[DeliveryRecord] = []                      # audit log
_throttle_counts: Dict[str, int] = {}                       # user_id -> sends today


def register_device(user_id: str, token: str, platform: Platform) -> DeviceToken:
    """
    Upsert a device token for the given user.

    Called from the mobile app after FCM/APNs returns a fresh registration ID.
    If the token already exists for this user, update last_used; otherwise
    append a new DeviceToken entry.
    """
    existing = _device_tokens.setdefault(user_id, [])
    for dt in existing:
        if dt.token == token:
            dt.touch()
            log.info("Token refreshed  user=%s platform=%s", user_id, platform.value)
            return dt

    new_token = DeviceToken(user_id=user_id, token=token, platform=platform)
    existing.append(new_token)
    log.info("Token registered  user=%s platform=%s", user_id, platform.value)
    return new_token


def remove_token(user_id: str, token: str) -> None:
    """
    Soft-delete a stale token (returned as 410 from APNs or
    'registration-token-not-registered' from FCM).
    """
    tokens = _device_tokens.get(user_id, [])
    before = len(tokens)
    _device_tokens[user_id] = [t for t in tokens if t.token != token]
    if len(_device_tokens[user_id]) < before:
        log.warning("Stale token removed  user=%s", user_id)


def get_user_tokens(user_id: str) -> List[DeviceToken]:
    return _device_tokens.get(user_id, [])


def get_user_prefs(user_id: str) -> NotificationPreferences:
    return _preferences.get(
        user_id,
        NotificationPreferences(user_id=user_id),  # sensible defaults
    )


# ==========================================================================
# 3. FCM HTTP v1 API — service account OAuth 2.0
# ==========================================================================

# pip install google-auth requests
# In production: real credentials loaded from env / secret manager.
FCM_PROJECT_ID = "your-firebase-project"
FCM_SERVICE_ACCOUNT_FILE = "service-account.json"

FCM_V1_URL = (
    "https://fcm.googleapis.com/v1/projects/{project}/messages:send".format(
        project=FCM_PROJECT_ID
    )
)


def _get_fcm_access_token() -> str:
    """
    Exchange the Google service account key for a short-lived OAuth 2.0 token.

    Production usage:
        from google.oauth2 import service_account
        import google.auth.transport.requests

        credentials = service_account.Credentials.from_service_account_file(
            FCM_SERVICE_ACCOUNT_FILE,
            scopes=["https://www.googleapis.com/auth/firebase.messaging"],
        )
        credentials.refresh(google.auth.transport.requests.Request())
        return credentials.token
    """
    # Dry-run stub — returns a placeholder token.
    return "DRY_RUN_ACCESS_TOKEN"


def _build_fcm_message(
    token: str,
    title: str,
    body: str,
    data: Optional[Dict[str, str]] = None,
    silent: bool = False,
) -> Dict[str, Any]:
    """
    Build the FCM HTTP v1 message payload.

    - android.priority = "high" ensures foreground delivery.
    - android.notification.channel_id maps to a NotificationChannel.
    - apns.payload.aps carries iOS alert + badge + sound fields.
    - Setting content_available = True (FCM) / apns-push-type = background
      triggers a silent push that wakes the app without showing a banner.
    """
    message: Dict[str, Any] = {
        "message": {
            "token": token,
            "data": {k: str(v) for k, v in (data or {}).items()},
            "android": {
                "priority": "normal" if silent else "high",
                "notification": {
                    "channel_id": "important_messages",
                    "sound": "default",
                },
            },
            "apns": {
                "headers": {
                    "apns-push-type": "background" if silent else "alert",
                    "apns-priority": "5" if silent else "10",
                },
                "payload": {
                    "aps": {
                        "sound": "default",
                        "badge": 1,
                    },
                },
            },
        }
    }
    if silent:
        message["message"]["apns"]["payload"]["aps"]["content-available"] = 1
    if not silent:
        message["message"]["notification"] = {"title": title, "body": body}

    return message


def send_via_fcm_http_v1(
    token: str,
    title: str,
    body: str,
    data: Optional[Dict[str, str]] = None,
    silent: bool = False,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """
    POST a push notification to the FCM HTTP v1 endpoint.

    Returns the parsed JSON response body from FCM.
    On a real connection:
        Success  -> {"name": "projects/.../messages/0:1234..."}
        Failure  -> {"error": {"code": 400, "message": "...", "status": "..."}}
    """
    payload = _build_fcm_message(token, title, body, data, silent)

    if dry_run:
        log.info(
            "[FCM HTTP v1] DRY-RUN  token=%s...  title=%r",
            token[:12],
            title,
        )
        log.debug("Payload: %s", json.dumps(payload, indent=2))
        return {"name": "projects/{}/messages/DRY_RUN_ID".format(FCM_PROJECT_ID)}

    # Production path (requires: pip install requests google-auth)
    # import requests
    # resp = requests.post(
    #     FCM_V1_URL,
    #     json=payload,
    #     headers={
    #         "Authorization": "Bearer {}".format(_get_fcm_access_token()),
    #         "Content-Type": "application/json",
    #     },
    #     timeout=10,
    # )
    # return resp.json()
    return {}


# ==========================================================================
# 4. FIREBASE ADMIN SDK — multicast & topic-based send
# ==========================================================================

# pip install firebase-admin


def send_via_admin_sdk(
    token: str,
    title: str,
    body: str,
    dry_run: bool = True,
) -> Optional[str]:
    """
    Send a single push via the Firebase Admin Python SDK.

    Returns the FCM message ID string on success.

    Production usage:
        import firebase_admin
        from firebase_admin import credentials, messaging

        cred = credentials.Certificate(FCM_SERVICE_ACCOUNT_FILE)
        firebase_admin.initialize_app(cred)

        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            token=token,
            android=messaging.AndroidConfig(priority="high"),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(sound="default", badge=1)
                )
            ),
        )
        return messaging.send(message)
    """
    if dry_run:
        msg_id = "projects/{}/messages/DRY_RUN_ADMIN".format(FCM_PROJECT_ID)
        log.info("[Firebase Admin] DRY-RUN single send  token=%s...", token[:12])
        return msg_id

    return None


def send_multicast(
    tokens: List[str],
    title: str,
    body: str,
    user_token_map: Optional[Dict[str, str]] = None,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """
    Send the same notification to multiple device tokens in a single FCM call.

    FCM accepts up to 500 tokens per multicast batch.  Inspect
    response.responses to detect per-token failures:
      - 'registration-token-not-registered' -> remove stale token from DB.

    user_token_map maps token -> user_id for cleanup lookups (optional).

    Production usage (firebase_admin.messaging.send_multicast):
        response = messaging.send_multicast(
            messaging.MulticastMessage(
                tokens=tokens,
                notification=messaging.Notification(title=title, body=body),
            )
        )
        for idx, resp in enumerate(response.responses):
            if not resp.success:
                if resp.exception.code == "registration-token-not-registered":
                    remove_token(user_token_map.get(tokens[idx], "?"), tokens[idx])
        return {"success_count": response.success_count,
                "failure_count": response.failure_count}
    """
    if dry_run:
        log.info(
            "[Firebase Admin] DRY-RUN multicast  tokens=%d  title=%r",
            len(tokens),
            title,
        )
        return {
            "success_count": len(tokens),
            "failure_count": 0,
            "responses": [
                {"success": True, "message_id": "dry_run_{}".format(i)}
                for i in range(len(tokens))
            ],
        }

    return {"success_count": 0, "failure_count": 0}


def subscribe_to_topic(tokens: List[str], topic: str, dry_run: bool = True) -> None:
    """
    Subscribe device tokens to an FCM topic so you can push to the whole
    group with a single API call (e.g., "news", "alerts-region-east").

    Production usage:
        from firebase_admin import messaging
        messaging.subscribe_to_topic(tokens, topic)
    """
    if dry_run:
        log.info(
            "[Firebase Admin] DRY-RUN subscribe  topic=%s  tokens=%d",
            topic, len(tokens),
        )


def send_to_topic(
    topic: str,
    title: str,
    body: str,
    dry_run: bool = True,
) -> Optional[str]:
    """
    Push to every device subscribed to `topic`.

    Useful for broadcast events: breaking news, system alerts, promotions.

    Production usage:
        from firebase_admin import messaging
        return messaging.send(
            messaging.Message(
                topic=topic,
                notification=messaging.Notification(title=title, body=body),
            )
        )
    """
    if dry_run:
        log.info(
            "[Firebase Admin] DRY-RUN topic send  topic=%s  title=%r",
            topic, title,
        )
        return "projects/{}/messages/DRY_RUN_TOPIC".format(FCM_PROJECT_ID)

    return None


# ==========================================================================
# 5. APNs DIRECT — HTTP/2 + JWT provider-token auth
# ==========================================================================

# pip install httpx[http2] pyjwt cryptography

APNS_TEAM_ID = "TEAM_ID_HERE"
APNS_KEY_ID = "KEY_ID_HERE"
APNS_BUNDLE_ID = "com.example.app"
# In production load from env / secret manager; never hard-code private keys.
APNS_PRIVATE_KEY_PEM = "-----BEGIN EC PRIVATE KEY-----\n...\n-----END EC PRIVATE KEY-----"

APNS_HOST_PROD = "https://api.push.apple.com"
APNS_HOST_SANDBOX = "https://api.sandbox.push.apple.com"


def _make_apns_jwt() -> str:
    """
    Build a short-lived JWT signed with the APNs ES256 private key.

    The token must be refreshed every 60 minutes; Apple rejects tokens older
    than 1 hour.  In production, cache the token and regenerate proactively
    before expiry.

    Production usage:
        import jwt, time
        token = jwt.encode(
            {"iss": APNS_TEAM_ID, "iat": int(time.time())},
            APNS_PRIVATE_KEY_PEM,
            algorithm="ES256",
            headers={"kid": APNS_KEY_ID},
        )
        return token
    """
    return "DRY_RUN_APNS_JWT"


async def send_via_apns(
    device_token: str,
    title: str,
    body: str,
    custom_data: Optional[Dict[str, Any]] = None,
    silent: bool = False,
    sandbox: bool = True,
    dry_run: bool = True,
) -> int:
    """
    POST a push notification directly to Apple's HTTP/2 gateway.

    APNs response codes:
        200 -> accepted for delivery (not a guarantee the device received it).
        400 -> bad request (malformed JSON / invalid token format).
        403 -> auth failure (JWT invalid / expired, or wrong team ID).
        410 -> token unregistered -> call remove_token() for this device.
        429 -> too many requests -> back off.
        500 -> APNs internal error -> retry with exponential back-off.

    Returns the HTTP status code.

    Production path (requires: pip install httpx[http2]):
        async with httpx.AsyncClient(http2=True) as client:
            response = await client.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code == 410:
            remove_token(user_id, device_token)
        return response.status_code
    """
    host = APNS_HOST_SANDBOX if sandbox else APNS_HOST_PROD
    url = "{}/3/device/{}".format(host, device_token)

    payload: Dict[str, Any] = {
        "custom_data": custom_data or {},
    }

    if silent:
        # Silent / data push — no banner, wakes app to sync in background.
        payload["aps"] = {"content-available": 1}
    else:
        payload["aps"] = {
            "alert": {"title": title, "body": body},
            "sound": "default",
            "badge": 1,
        }

    headers = {
        "authorization": "bearer {}".format(_make_apns_jwt()),
        "apns-topic": APNS_BUNDLE_ID,
        "apns-priority": "5" if silent else "10",
        "apns-push-type": "background" if silent else "alert",
    }

    if dry_run:
        log.info(
            "[APNs] DRY-RUN  token=%s...  title=%r  silent=%s",
            device_token[:12],
            title,
            silent,
        )
        log.debug("URL: %s", url)
        log.debug("Headers: %s", headers)
        log.debug("Payload: %s", json.dumps(payload, indent=2))
        return 200

    # Awaiting here satisfies the async contract even in the dry-run path.
    await asyncio.sleep(0)
    return 200


# ==========================================================================
# 6. WEB PUSH — VAPID / pywebpush
# ==========================================================================

# pip install pywebpush

VAPID_PRIVATE_KEY = "YOUR_VAPID_PRIVATE_KEY"
VAPID_CLAIMS = {"sub": "mailto:admin@example.com"}


def send_web_push(
    subscription: Dict[str, Any],
    title: str,
    body: str,
    dry_run: bool = True,
) -> None:
    """
    Send a Web Push notification to a browser (Chrome, Firefox, Safari).

    `subscription` is the PushSubscription JSON object POSTed by the browser:
        {
          "endpoint": "https://fcm.googleapis.com/fcm/send/...",
          "keys": {"p256dh": "...", "auth": "..."}
        }

    Uses the VAPID protocol for authentication — no Google account required.
    Primarily used in Progressive Web Apps (PWAs).

    Production usage:
        from pywebpush import webpush, WebPushException
        webpush(
            subscription_info=subscription,
            data=json.dumps({"title": title, "body": body}),
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims=VAPID_CLAIMS,
        )
    """
    data = json.dumps({"title": title, "body": body})
    if dry_run:
        log.info(
            "[WebPush] DRY-RUN  endpoint=%s...  title=%r",
            str(subscription.get("endpoint", ""))[:40],
            title,
        )
        log.debug("Data: %s", data)


# ==========================================================================
# 7. RATE LIMITING / THROTTLE GUARD
# ==========================================================================

# Production: store counters in Redis with a TTL of 24 h.
# Here: in-memory daily counter per user (resets on process restart).
DAILY_PUSH_LIMIT = 20


async def is_throttled(user_id: str) -> bool:
    """
    Return True when the user has already received DAILY_PUSH_LIMIT pushes
    today.  In production back this with Redis INCR + EXPIRE.
    """
    count = _throttle_counts.get(user_id, 0)
    if count >= DAILY_PUSH_LIMIT:
        log.warning("Push throttled  user=%s  count=%d", user_id, count)
        return True
    return False


def _increment_throttle(user_id: str) -> None:
    _throttle_counts[user_id] = _throttle_counts.get(user_id, 0) + 1


# ==========================================================================
# 8. USER PREFERENCE GATE
# ==========================================================================

async def should_send_push(user_id: str, category: str) -> bool:
    """
    Evaluate whether a push notification should be delivered.

    Checks (in order):
      1. Daily throttle limit.
      2. User's per-category push opt-in.
      3. Quiet hours window.
    """
    if await is_throttled(user_id):
        return False

    prefs = get_user_prefs(user_id)

    if not prefs.is_push_enabled(category):
        log.info(
            "Push suppressed (user opt-out)  user=%s  category=%s",
            user_id, category,
        )
        return False

    if prefs.in_quiet_hours():
        log.info("Push suppressed (quiet hours)  user=%s", user_id)
        return False

    return True


# ==========================================================================
# 9. TEMPLATE RENDERER
# ==========================================================================

TEMPLATES: Dict[str, Dict[str, Dict[str, str]]] = {
    "order_paid": {
        "push": {
            "title": "Order #{order_id} confirmed",
            "body": "Your payment of ${amount} was successful.",
        },
        "email": {
            "subject": "Payment confirmation — order #{order_id}",
            "html_template": "templates/order_paid.html",
        },
    },
    "chat_message": {
        "push": {
            "title": "{sender} sent you a message",
            "body": "{preview}",
        },
        "email": {
            "subject": "New message from {sender}",
            "html_template": "templates/chat_message.html",
        },
    },
    "marketing_promo": {
        "push": {
            "title": "Special offer just for you",
            "body": "{promo_text}",
        },
        "email": {
            "subject": "You have a new promotion",
            "html_template": "templates/promo.html",
        },
    },
}


def render_template(
    event_type: str,
    channel: str,
    context: Dict[str, Any],
) -> Dict[str, str]:
    """
    Interpolate the named template with the provided context dict.

    Returns a dict of rendered strings, e.g. {"title": "...", "body": "..."}.
    Raises KeyError if event_type or channel is not found in TEMPLATES.
    """
    template = TEMPLATES[event_type][channel]
    return {key: value.format(**context) for key, value in template.items()}


# ==========================================================================
# 10. MULTI-CHANNEL NOTIFICATION DISPATCHER
# ==========================================================================

@dataclass
class Notification:
    """A pending notification to be dispatched across one or more channels."""
    user_id: str
    event_type: str
    context: Dict[str, Any]                          # template variables
    channels: List[str] = field(default_factory=lambda: ["push", "email"])
    category: str = "chat"                           # matches preference key


async def _dispatch_push(notif: "Notification", dry_run: bool = True) -> DeliveryRecord:
    """
    Resolve all device tokens for the user and send across FCM / APNs.
    """
    record = DeliveryRecord(
        user_id=notif.user_id,
        channel="push",
        event_type=notif.event_type,
    )
    tokens = get_user_tokens(notif.user_id)

    if not tokens:
        record.mark_failed("No registered device tokens.")
        return record

    rendered = render_template(notif.event_type, "push", notif.context)
    title = rendered.get("title", "")
    body = rendered.get("body", "")

    for device in tokens:
        if device.platform in (Platform.ANDROID, Platform.IOS):
            result = send_via_fcm_http_v1(
                device.token, title, body, dry_run=dry_run
            )
            provider_id = result.get("name")
            _increment_throttle(notif.user_id)
            record.mark_sent(provider_id)

    return record


async def _dispatch_email(notif: "Notification") -> DeliveryRecord:
    """
    Stub for the email channel — see 01_smtp_fundamentals.py /
    02_transactional_email_providers.py for full implementation.
    """
    record = DeliveryRecord(
        user_id=notif.user_id,
        channel="email",
        event_type=notif.event_type,
    )
    rendered = render_template(notif.event_type, "email", notif.context)
    log.info(
        "[Email] DRY-RUN  user=%s  subject=%r",
        notif.user_id,
        rendered.get("subject", ""),
    )
    record.mark_sent("DRY_RUN_EMAIL_ID")
    return record


async def dispatch_notification(
    notif: "Notification",
    dry_run: bool = True,
) -> List[DeliveryRecord]:
    """
    Multi-channel notification dispatcher.

    Flow:
        1. For each requested channel:
           a. Gate on user preference (opt-out / quiet hours / throttle).
           b. Render the appropriate template.
           c. Send via the relevant provider.
           d. Store a DeliveryRecord for audit / webhook updates.

    Webhook updates (production):
        - FCM batch response  -> mark 'failed' for unregistered tokens.
        - SendGrid / SES event webhook -> mark 'delivered' or 'bounced'.
    """
    records: List[DeliveryRecord] = []

    for channel in notif.channels:
        if channel == "push":
            if not await should_send_push(notif.user_id, notif.category):
                skipped = DeliveryRecord(
                    user_id=notif.user_id,
                    channel=channel,
                    event_type=notif.event_type,
                    status=NotificationStatus.THROTTLED,
                )
                records.append(skipped)
                continue
            record = await _dispatch_push(notif, dry_run=dry_run)

        elif channel == "email":
            prefs = get_user_prefs(notif.user_id)
            if not prefs.is_email_enabled(notif.category):
                log.info(
                    "Email suppressed (opt-out)  user=%s  category=%s",
                    notif.user_id, notif.category,
                )
                continue
            record = await _dispatch_email(notif)

        else:
            log.warning("Unknown channel '%s' — skipping.", channel)
            continue

        _deliveries.append(record)
        records.append(record)

    return records


# ==========================================================================
# 11. SEND-TO-USER HELPER (all tokens for a user, mixed platforms)
# ==========================================================================

async def send_to_user(
    user_id: str,
    title: str,
    body: str,
    data: Optional[Dict[str, str]] = None,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """
    Deliver a push to every device registered under `user_id`.

    In production replace the in-memory token lookup with an async DB query:
        tokens = await db.fetch(
            "SELECT token, platform FROM device_tokens WHERE user_id = $1",
            user_id,
        )
    """
    tokens = get_user_tokens(user_id)
    results: Dict[str, Any] = {"sent": [], "skipped": []}

    for device in tokens:
        if device.platform in (Platform.ANDROID, Platform.IOS):
            result = send_via_fcm_http_v1(
                device.token, title, body, data, dry_run=dry_run
            )
            results["sent"].append({"token": device.token[:12], "result": result})
        elif device.platform == Platform.WEB:
            # Web push subscription stored separately in production.
            results["skipped"].append({"token": device.token[:12], "reason": "web"})

    return results


# ==========================================================================
# 12. DELIVERY AUDIT HELPERS
# ==========================================================================

def get_delivery_records(user_id: Optional[str] = None) -> List[DeliveryRecord]:
    """Return all delivery records, optionally filtered by user_id."""
    if user_id:
        return [r for r in _deliveries if r.user_id == user_id]
    return list(_deliveries)


def delivery_summary() -> Dict[str, int]:
    """Return a count breakdown by status across all tracked deliveries."""
    summary: Dict[str, int] = {}
    for record in _deliveries:
        key = record.status.value
        summary[key] = summary.get(key, 0) + 1
    return summary


# ==========================================================================
# DEMO — runs without any external infrastructure
# ==========================================================================

async def _run_demo() -> None:
    print("\n" + "=" * 68)
    print("  Push Notifications — FCM & APNs — Dry-run Demo")
    print("=" * 68)

    # -----------------------------------------------------------------------
    # Register device tokens for two users.
    # -----------------------------------------------------------------------
    user_alice = "user-alice"
    user_bob = "user-bob"

    register_device(user_alice, "FCM_TOKEN_ALICE_ANDROID_001", Platform.ANDROID)
    register_device(user_alice, "APNS_TOKEN_ALICE_IOS_002", Platform.IOS)
    register_device(user_bob,   "FCM_TOKEN_BOB_ANDROID_003", Platform.ANDROID)

    # Simulate a token refresh (same token, touch last_used).
    register_device(user_alice, "FCM_TOKEN_ALICE_ANDROID_001", Platform.ANDROID)

    # -----------------------------------------------------------------------
    # Set up user preferences.
    # -----------------------------------------------------------------------
    _preferences[user_alice] = NotificationPreferences(
        user_id=user_alice,
        push={"chat": True, "marketing": False},
        quiet_hours=QuietHours(start_hour=23, end_hour=7),
    )
    _preferences[user_bob] = NotificationPreferences(
        user_id=user_bob,
        push={"chat": True, "marketing": True},
    )

    # -----------------------------------------------------------------------
    # FCM HTTP v1 — single device.
    # -----------------------------------------------------------------------
    print("\n--- FCM HTTP v1 (single device) ---")
    send_via_fcm_http_v1(
        token="FCM_TOKEN_ALICE_ANDROID_001",
        title="New message",
        body="Alice, you have a new chat message.",
        dry_run=True,
    )

    # -----------------------------------------------------------------------
    # Firebase Admin SDK — multicast.
    # -----------------------------------------------------------------------
    print("\n--- Firebase Admin SDK multicast ---")
    send_multicast(
        tokens=["FCM_TOKEN_ALICE_ANDROID_001", "FCM_TOKEN_BOB_ANDROID_003"],
        title="System alert",
        body="Scheduled maintenance in 30 minutes.",
        dry_run=True,
    )

    # -----------------------------------------------------------------------
    # Firebase Admin SDK — topic-based send.
    # -----------------------------------------------------------------------
    print("\n--- Firebase Admin SDK topic send ---")
    subscribe_to_topic(["FCM_TOKEN_BOB_ANDROID_003"], "news", dry_run=True)
    send_to_topic("news", "Breaking news", "New article published.", dry_run=True)

    # -----------------------------------------------------------------------
    # APNs direct — alert push.
    # -----------------------------------------------------------------------
    print("\n--- APNs direct (alert) ---")
    status = await send_via_apns(
        device_token="APNS_TOKEN_ALICE_IOS_002",
        title="Payment received",
        body="Your order has been confirmed.",
        sandbox=True,
        dry_run=True,
    )
    print("    APNs returned HTTP {}".format(status))

    # -----------------------------------------------------------------------
    # APNs direct — silent / data push.
    # -----------------------------------------------------------------------
    print("\n--- APNs direct (silent / background) ---")
    await send_via_apns(
        device_token="APNS_TOKEN_ALICE_IOS_002",
        title="",
        body="",
        silent=True,
        custom_data={"sync": "inbox", "count": 5},
        sandbox=True,
        dry_run=True,
    )

    # -----------------------------------------------------------------------
    # Template renderer.
    # -----------------------------------------------------------------------
    print("\n--- Template renderer ---")
    rendered = render_template(
        "order_paid",
        "push",
        {"order_id": "ORD-9921", "amount": "249.00"},
    )
    print("    title : {}".format(rendered["title"]))
    print("    body  : {}".format(rendered["body"]))

    # -----------------------------------------------------------------------
    # Multi-channel dispatcher — chat event for Alice.
    # -----------------------------------------------------------------------
    print("\n--- Multi-channel dispatcher (chat -> push + email) ---")
    notif = Notification(
        user_id=user_alice,
        event_type="chat_message",
        context={"sender": "Bob", "preview": "Hey, are you free tomorrow?"},
        channels=["push", "email"],
        category="chat",
    )
    records = await dispatch_notification(notif, dry_run=True)
    for rec in records:
        print("    channel={}  status={}  id={}".format(
            rec.channel, rec.status.value, rec.id[:8]
        ))

    # -----------------------------------------------------------------------
    # Marketing push — Alice has opted out; should be suppressed.
    # -----------------------------------------------------------------------
    print("\n--- Marketing push for Alice (opted out) ---")
    mkt_notif = Notification(
        user_id=user_alice,
        event_type="marketing_promo",
        context={"promo_text": "50% off this weekend!"},
        channels=["push"],
        category="marketing",
    )
    mkt_records = await dispatch_notification(mkt_notif, dry_run=True)
    for rec in mkt_records:
        print("    channel={}  status={}".format(rec.channel, rec.status.value))

    # -----------------------------------------------------------------------
    # send_to_user helper.
    # -----------------------------------------------------------------------
    print("\n--- send_to_user (all devices for a user) ---")
    result = await send_to_user(
        user_id=user_alice,
        title="Account alert",
        body="A new login was detected from London.",
        dry_run=True,
    )
    print("    sent={}  skipped={}".format(len(result["sent"]), len(result["skipped"])))

    # -----------------------------------------------------------------------
    # Stale token removal (simulates APNs 410 / FCM unregistered).
    # -----------------------------------------------------------------------
    print("\n--- Stale token removal ---")
    before = len(get_user_tokens(user_alice))
    remove_token(user_alice, "APNS_TOKEN_ALICE_IOS_002")
    after = len(get_user_tokens(user_alice))
    print("    Tokens for Alice: {} -> {}".format(before, after))

    # -----------------------------------------------------------------------
    # Web push stub.
    # -----------------------------------------------------------------------
    print("\n--- Web push (VAPID) ---")
    send_web_push(
        subscription={
            "endpoint": "https://fcm.googleapis.com/fcm/send/EXAMPLE_ENDPOINT",
            "keys": {"p256dh": "EXAMPLE_KEY", "auth": "EXAMPLE_AUTH"},
        },
        title="Hello from the web",
        body="Web push works in Chrome, Firefox, and Safari.",
        dry_run=True,
    )

    # -----------------------------------------------------------------------
    # Delivery summary.
    # -----------------------------------------------------------------------
    print("\n--- Delivery summary ---")
    for status_key, count in delivery_summary().items():
        print("    {}: {}".format(status_key, count))

    print("\n" + "=" * 68)
    print("  Demo complete — all calls ran in dry-run mode.")
    print("=" * 68 + "\n")


if __name__ == "__main__":
    asyncio.run(_run_demo())
