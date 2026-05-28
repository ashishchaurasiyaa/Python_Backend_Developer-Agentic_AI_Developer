# 03 — Push Notifications: FCM & APNs

> Mobile push notifications. Different protocols, different gotchas. Both eventually go through Apple (iOS) and Google (Android).

---

## The Push Notification Stack

```
Your backend → FCM (Google) / APNs (Apple) → User's device
```

You can't push directly. Must go through Google's / Apple's gateways.

---

## Device Tokens

When app installs:
1. App registers with FCM/APNs.
2. FCM/APNs returns a unique device token.
3. App sends token to your backend.
4. Backend stores: (user_id, device_token, platform).
5. Backend sends push by addressing the token.

Tokens can change (uninstall, OS update, app reset). Always update on each app launch.

---

## FCM (Firebase Cloud Messaging) — Android + iOS

Google's unified service. Works for Android natively, iOS via APNs underneath.

### Setup
1. Create Firebase project.
2. Get Service Account JSON.
3. Mobile app installs FCM SDK.

### Send via FCM HTTP v1 API
```python
import google.auth
import google.auth.transport.requests
import requests

def get_access_token():
    credentials = google.oauth2.service_account.Credentials.from_service_account_file(
        "service-account.json",
        scopes=["https://www.googleapis.com/auth/firebase.messaging"]
    )
    credentials.refresh(google.auth.transport.requests.Request())
    return credentials.token

def send_push(device_token, title, body, data=None):
    project_id = "your-firebase-project"
    url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"

    message = {
        "message": {
            "token": device_token,
            "notification": {
                "title": title,
                "body": body
            },
            "data": data or {},
            "android": {
                "priority": "high",
                "notification": {
                    "channel_id": "important_messages",
                    "sound": "default"
                }
            },
            "apns": {
                "payload": {
                    "aps": {
                        "sound": "default",
                        "badge": 1
                    }
                }
            }
        }
    }

    response = requests.post(
        url,
        json=message,
        headers={
            "Authorization": f"Bearer {get_access_token()}",
            "Content-Type": "application/json"
        }
    )
    return response.json()
```

### Via Firebase Admin SDK
```python
import firebase_admin
from firebase_admin import credentials, messaging

cred = credentials.Certificate("service-account.json")
firebase_admin.initialize_app(cred)

def send(token, title, body):
    message = messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        token=token,
        android=messaging.AndroidConfig(priority="high"),
        apns=messaging.APNSConfig(
            payload=messaging.APNSPayload(
                aps=messaging.Aps(sound="default", badge=1)
            )
        )
    )
    response = messaging.send(message)
    return response
```

### Multicast (multiple tokens)
```python
response = messaging.send_multicast(
    messaging.MulticastMessage(
        tokens=[token1, token2, token3],
        notification=...
    )
)

# Inspect failures
for idx, resp in enumerate(response.responses):
    if not resp.success:
        if resp.exception.code == "registration-token-not-registered":
            remove_token(tokens[idx])
```

### Topic-based push
Devices subscribe to topics; you push to topic.

```python
messaging.subscribe_to_topic([token1, token2], "news")

# Push to all subscribers
messaging.send(messaging.Message(
    topic="news",
    notification=...
))
```

---

## APNs (Apple Push Notification service) — iOS direct

If you don't use FCM and push to iOS directly.

### Authentication
- **Provider tokens (JWT)**: modern, easier.
- **Provider certificates**: legacy.

### Send via HTTP/2

```python
import jwt
import time
import httpx

def make_apns_jwt():
    return jwt.encode(
        {"iss": TEAM_ID, "iat": int(time.time())},
        APNS_KEY,
        algorithm="ES256",
        headers={"kid": KEY_ID}
    )

async def send_apns(device_token, title, body):
    payload = {
        "aps": {
            "alert": {"title": title, "body": body},
            "sound": "default",
            "badge": 1
        },
        "custom_data": "..."
    }

    async with httpx.AsyncClient(http2=True) as client:
        response = await client.post(
            f"https://api.push.apple.com/3/device/{device_token}",
            headers={
                "authorization": f"bearer {make_apns_jwt()}",
                "apns-topic": "com.example.app",   # your bundle ID
                "apns-priority": "10",
                "apns-push-type": "alert"
            },
            json=payload
        )
        return response.status_code
```

### APNs response codes
- 200: delivered to APNs (not necessarily device).
- 400: bad request.
- 403: auth fail.
- 410: token unregistered → delete from your DB.
- 429: too many requests.
- 500: APNs internal error.

---

## Notification Types

### Alert (visible push)
Shows banner. Most common.

### Silent / data push
No UI; wakes app to fetch updates.
```python
# FCM
"content_available": True
# APNs
"apns-push-type": "background"
"apns-priority": "5"
```

### Rich push
Images, videos, action buttons.

### Provisional push (iOS 12+)
No permission prompt — delivered to Notification Center quietly.

---

## Best Practices

### Token management
- Refresh tokens on each app launch.
- Soft delete tokens on uninstall (410 from APNs / unregistered from FCM).
- Multiple devices per user supported.

```sql
CREATE TABLE device_tokens (
    user_id    UUID,
    token      TEXT,
    platform   TEXT,    -- 'ios', 'android', 'web'
    created_at TIMESTAMPTZ,
    last_used  TIMESTAMPTZ,
    PRIMARY KEY (user_id, token)
);
```

### Targeting
```python
async def send_to_user(user_id, payload):
    tokens = await db.fetch(
        "SELECT token, platform FROM device_tokens WHERE user_id = $1", user_id
    )
    for tok in tokens:
        await send_push(tok.token, payload, tok.platform)
```

### Rate limiting
Don't bombard users. Apple/Google may auto-throttle. Implement:
- Quiet hours per user.
- Per-app daily limits.
- Deduplication.

### Locale
```python
push.notification.title_loc_key = "WELCOME_TITLE"
push.notification.body_loc_key = "WELCOME_BODY"
# Mobile app handles localization based on device locale
```

### Time-sensitive vs not
Apple has new priority types ("time-sensitive" passes through Focus mode).

---

## User Preferences

```sql
CREATE TABLE notification_preferences (
    user_id     UUID PRIMARY KEY,
    push        JSONB,        -- {"chat": true, "marketing": false}
    email       JSONB,
    quiet_hours JSONB         -- {"start": "22:00", "end": "07:00", "tz": "Asia/Kolkata"}
);
```

Check before sending:
```python
async def should_send(user_id, category):
    prefs = await get_prefs(user_id)
    if not prefs.push.get(category, True):
        return False
    if in_quiet_hours(prefs.quiet_hours):
        return False
    return True
```

---

## Web Push (Browser)

For desktop Chrome, Firefox, Safari.

Uses standard Web Push Protocol (VAPID auth).

```python
from pywebpush import webpush

subscription = {
    "endpoint": "https://fcm.googleapis.com/fcm/send/...",
    "keys": {"p256dh": "...", "auth": "..."}
}

webpush(
    subscription_info=subscription,
    data=json.dumps({"title": "Hello", "body": "World"}),
    vapid_private_key=PRIVATE_KEY,
    vapid_claims={"sub": "mailto:admin@example.com"}
)
```

Mostly used by progressive web apps (PWAs).

---

## Multi-Channel Notification Service Design

```
User event happens
        ↓
Notification Service
        ↓
For each channel (push, email, SMS, in-app):
  - Check user preferences
  - Apply throttle / dedupe
  - Render template
  - Send via provider
        ↓
Track delivery + outcomes
```

```python
class Notification:
    def __init__(self, user_id, event_type, payload, channels=None):
        self.user_id = user_id
        self.event_type = event_type
        self.payload = payload
        self.channels = channels or ["push", "email"]

async def send_notification(notif):
    prefs = await get_user_prefs(notif.user_id)
    for channel in notif.channels:
        if not prefs.is_enabled(channel, notif.event_type):
            continue
        if await is_throttled(notif.user_id, channel):
            continue
        if channel == "push":
            await send_push(notif)
        elif channel == "email":
            await send_email(notif)
        elif channel == "sms":
            await send_sms(notif)
        elif channel == "in_app":
            await save_in_app(notif)
```

---

## Templates

```python
TEMPLATES = {
    "order_paid": {
        "push": {
            "title": "Order #{order_id} paid",
            "body": "Your payment of ${amount} was successful"
        },
        "email": {
            "subject": "Payment confirmation",
            "html_template": "templates/order_paid.html"
        }
    }
}

def render(event_type, channel, payload):
    template = TEMPLATES[event_type][channel]
    return {k: v.format(**payload) for k, v in template.items()}
```

---

## Delivery Tracking

```sql
CREATE TABLE notification_deliveries (
    id            UUID,
    user_id       UUID,
    channel       TEXT,
    event_type    TEXT,
    status        TEXT,        -- 'pending', 'sent', 'delivered', 'failed'
    provider_id   TEXT,        -- ID from FCM/SES
    sent_at       TIMESTAMPTZ,
    delivered_at  TIMESTAMPTZ NULL,
    error         TEXT NULL
);
```

Webhook updates:
```python
# SendGrid webhook → status='delivered'
# FCM batch response → status='failed' if unregistered
```

---

## Costs

| | Per push |
|---|---|
| FCM | Free |
| APNs | Free |
| Web Push | Free |
| SMS (Twilio) | $0.0075-$0.05 |
| Email (SES) | $0.0001 |

Push is essentially free. SMS expensive. Email cheap.

---

## OneSignal / Iterable / Customer.io

If you don't want to build the notification service yourself:
- **OneSignal**: free push, paid features. Easy to integrate.
- **Iterable / Customer.io**: full marketing automation + transactional.
- **Braze**: enterprise.

For startups: OneSignal often sufficient.

For production at scale: build your own service on top of FCM/APNs.

---

## Common Issues

### 1. iOS not receiving
- Bundle ID wrong.
- APNs key expired (1 year lifetime).
- App in background but not "Background App Refresh"-enabled.
- User has Focus mode on.

### 2. Android not receiving
- FCM token expired.
- Battery optimization killing app.
- "Adaptive Notifications" silencing them.

### 3. Tokens accumulating
Don't clean up unregistered tokens → wasted sends. Listen for FCM `unregistered` errors and remove.

### 4. Push not received but no error
APNs/FCM accepted; device offline/throttled. Best-effort delivery.

### 5. Too many notifications → uninstalls
Have an internal "notification budget" per user. Honor preferences.

---

## TL;DR

- FCM = unified Google service (works for iOS too).
- APNs = direct Apple service (HTTP/2 + JWT).
- Always go through their gateways — can't push directly.
- Manage device tokens carefully; refresh and clean up.
- User preferences first-class; respect quiet hours.
- Use multicast for batch; track per-token failures.
- Build notification service with multi-channel support (push + email + SMS + in-app).
- For startups: OneSignal saves work; for scale: roll your own on FCM/APNs.
