# Notification System — LLD
> **Difficulty:** Medium | **Frequency:** ★★★★★ | **Your Strength:** Niroskos Communications module

---

## Requirements

```
1. Multiple channels — Email, SMS, Push, Slack, WhatsApp
2. Channel selection per event type (booking confirmed → email+sms, not push)
3. Per-user preferences — user ne SMS opt-out kiya → skip
4. Template system — same event, different content per channel
5. Multi-tenant — India subsidiary → Postmark, Africa → SendGrid
6. Retry on failure — Celery + exponential backoff
7. Deduplication — same notification nahi jaaye twice
8. Priority queues — OTP = critical, newsletter = low
9. Delivery tracking — sent/delivered/failed status
10. Observer pattern — booking confirm → notification trigger (decoupled)
```

---

## Architecture

```
Event Source                    Notification System
(BookingService,    ──────►    ┌──────────────────────────────────────┐
 PaymentService,               │  NotificationService (Facade)        │
 Django Signal)                │    ↓                                 │
                               │  EventRouter                         │
                               │    ↓ (which channels?)               │
                               │  ChannelSelector (Strategy)          │
                               │    ↓                                 │
                               │  TemplateEngine                      │
                               │    ↓ (render content)                │
                               │  UserPreferenceFilter                │
                               │    ↓ (user opted out? skip)          │
                               │  DeduplicationStore                  │
                               │    ↓ (already sent? skip)            │
                               │  PriorityQueue (Celery tasks)        │
                               │    ↓                                 │
                               │  Channel Providers (Strategy)        │
                               │    ├── EmailProvider                 │
                               │    ├── SMSProvider                   │
                               │    ├── PushProvider                  │
                               │    └── SlackProvider                 │
                               └──────────────────────────────────────┘
```

---

## Full Implementation

```python
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set
import threading
import uuid
import time


# ═══════════════════════════════════════════════════════════════
# ENUMS & DOMAIN OBJECTS
# ═══════════════════════════════════════════════════════════════

class NotificationChannel(Enum):
    EMAIL    = "email"
    SMS      = "sms"
    PUSH     = "push"
    SLACK    = "slack"
    WHATSAPP = "whatsapp"


class NotificationPriority(Enum):
    CRITICAL = 1    # OTP, payment failure — send immediately
    HIGH     = 2    # Booking confirmed, payment receipt
    NORMAL   = 3    # Reminders, updates
    LOW      = 4    # Newsletter, promotions


class NotificationStatus(Enum):
    PENDING   = "pending"
    QUEUED    = "queued"
    SENT      = "sent"
    DELIVERED = "delivered"
    FAILED    = "failed"
    SKIPPED   = "skipped"     # User preference or dedup


class EventType(Enum):
    # Booking events
    BOOKING_CONFIRMED     = "booking_confirmed"
    BOOKING_CANCELLED     = "booking_cancelled"
    BOOKING_REMINDER      = "booking_reminder"
    # Payment events
    PAYMENT_COMPLETED     = "payment_completed"
    PAYMENT_FAILED        = "payment_failed"
    REFUND_PROCESSED      = "refund_processed"
    # Auth events
    OTP_REQUESTED         = "otp_requested"
    PASSWORD_RESET        = "password_reset"
    # Staff events
    STAFF_ASSIGNED        = "staff_assigned"
    # Ops events
    HIGH_VALUE_BOOKING    = "high_value_booking"


@dataclass
class NotificationContext:
    """
    Event se nikla data — template rendering + channel routing ke liye.
    Niroskos: booking confirmed → context has booking details.
    """
    event_type:      EventType
    user_id:         str
    tenant_id:       str                          # Multi-tenant: niroskos_ke / niroskos_tz
    priority:        NotificationPriority
    data:            Dict[str, Any]               # Template variables
    idempotency_key: str                          # Dedup key
    email:           Optional[str]  = None
    phone:           Optional[str]  = None
    device_tokens:   List[str]      = field(default_factory=list)
    slack_channel:   Optional[str]  = None
    created_at:      datetime       = field(default_factory=datetime.now)


@dataclass
class Notification:
    """One dispatched notification — one channel, one recipient"""
    notification_id: str            = field(default_factory=lambda: str(uuid.uuid4()))
    context_key:     str            = ""          # Links to NotificationContext
    channel:         NotificationChannel = NotificationChannel.EMAIL
    recipient:       str            = ""          # email / phone / device_token
    subject:         str            = ""
    body:            str            = ""
    status:          NotificationStatus = NotificationStatus.PENDING
    attempts:        int            = 0
    provider_msg_id: str            = ""          # Postmark message_id / Exotel sid
    error_message:   str            = ""
    sent_at:         Optional[datetime] = None
    created_at:      datetime       = field(default_factory=datetime.now)


# ═══════════════════════════════════════════════════════════════
# STRATEGY 1: CHANNEL SELECTION
# Which channels to use for each event type?
# ═══════════════════════════════════════════════════════════════

class ChannelSelector(ABC):
    @abstractmethod
    def get_channels(
        self,
        event_type: EventType,
        context: NotificationContext
    ) -> List[NotificationChannel]:
        pass


class RuleBasedChannelSelector(ChannelSelector):
    """
    Event type → channel list.
    Niroskos: booking_confirmed → [email, sms]
              otp_requested     → [sms]          (only SMS, fast)
              high_value_booking → [email, slack] (ops team alert)
              payment_failed    → [email, sms, push]
    """

    # Config-driven rules — DB ya settings se load karo
    CHANNEL_RULES: Dict[EventType, List[NotificationChannel]] = {
        EventType.BOOKING_CONFIRMED:  [NotificationChannel.EMAIL, NotificationChannel.SMS],
        EventType.BOOKING_CANCELLED:  [NotificationChannel.EMAIL, NotificationChannel.SMS],
        EventType.BOOKING_REMINDER:   [NotificationChannel.EMAIL, NotificationChannel.PUSH],
        EventType.PAYMENT_COMPLETED:  [NotificationChannel.EMAIL, NotificationChannel.SMS],
        EventType.PAYMENT_FAILED:     [NotificationChannel.EMAIL, NotificationChannel.SMS,
                                       NotificationChannel.PUSH],
        EventType.REFUND_PROCESSED:   [NotificationChannel.EMAIL],
        EventType.OTP_REQUESTED:      [NotificationChannel.SMS],   # SMS only — speed critical
        EventType.PASSWORD_RESET:     [NotificationChannel.EMAIL],
        EventType.STAFF_ASSIGNED:     [NotificationChannel.EMAIL, NotificationChannel.PUSH],
        EventType.HIGH_VALUE_BOOKING: [NotificationChannel.EMAIL, NotificationChannel.SLACK],
    }

    def get_channels(self, event_type, context) -> List[NotificationChannel]:
        channels = self.CHANNEL_RULES.get(event_type, [NotificationChannel.EMAIL])

        # Dynamic rule: critical priority → always add SMS if phone available
        if (context.priority == NotificationPriority.CRITICAL
                and NotificationChannel.SMS not in channels
                and context.phone):
            channels = list(channels) + [NotificationChannel.SMS]

        return channels


# ═══════════════════════════════════════════════════════════════
# STRATEGY 2: CHANNEL PROVIDERS (Abstract Factory per tenant)
# ═══════════════════════════════════════════════════════════════

@dataclass
class ProviderResult:
    success:        bool
    provider_msg_id: str
    error_message:  str = ""


class EmailProvider(ABC):
    @abstractmethod
    def send(self, to: str, subject: str, body: str, metadata: dict) -> ProviderResult:
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass


class SMSProvider(ABC):
    @abstractmethod
    def send(self, to: str, message: str, metadata: dict) -> ProviderResult:
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass


class PushProvider(ABC):
    @abstractmethod
    def send(self, device_tokens: List[str], title: str, body: str, data: dict) -> ProviderResult:
        pass


class SlackProvider(ABC):
    @abstractmethod
    def send(self, channel: str, message: str, blocks: list = None) -> ProviderResult:
        pass


# ─── Concrete Providers ───────────────────────────────────────

class PostmarkEmailProvider(EmailProvider):
    """
    Niroskos: India tenant → Postmark
    Transactional email, high deliverability
    """
    @property
    def provider_name(self): return "postmark"

    def send(self, to, subject, body, metadata):
        print(f"[POSTMARK] → {to} | Subject: {subject[:40]}")
        # postmarkclient.emails.send(From='noreply@niroskos.com',
        #                            To=to, Subject=subject, HtmlBody=body,
        #                            MessageStream='outbound')
        return ProviderResult(success=True, provider_msg_id=f"postmark_{uuid.uuid4().hex[:8]}")


class SendGridEmailProvider(EmailProvider):
    """Africa tenant → SendGrid"""
    @property
    def provider_name(self): return "sendgrid"

    def send(self, to, subject, body, metadata):
        print(f"[SENDGRID] → {to} | Subject: {subject[:40]}")
        return ProviderResult(success=True, provider_msg_id=f"sg_{uuid.uuid4().hex[:8]}")


class ExotelSMSProvider(SMSProvider):
    """
    Niroskos: Exotel SMS — India + Africa
    Rate limit: 200 req/min (Rate Limiter wala chapter!)
    """
    @property
    def provider_name(self): return "exotel"

    def send(self, to, message, metadata):
        print(f"[EXOTEL SMS] → {to}: {message[:50]}")
        # requests.post(EXOTEL_URL, auth=(SID, TOKEN),
        #               data={'From': SENDER_ID, 'To': to, 'Body': message})
        return ProviderResult(success=True, provider_msg_id=f"exotel_{uuid.uuid4().hex[:8]}")


class TwilioSMSProvider(SMSProvider):
    """International fallback"""
    @property
    def provider_name(self): return "twilio"

    def send(self, to, message, metadata):
        print(f"[TWILIO SMS] → {to}: {message[:50]}")
        return ProviderResult(success=True, provider_msg_id=f"twilio_{uuid.uuid4().hex[:8]}")


class FCMPushProvider(PushProvider):
    """Firebase Cloud Messaging — Android + iOS"""
    def send(self, device_tokens, title, body, data):
        print(f"[FCM PUSH] → {len(device_tokens)} devices | {title}")
        # firebase_admin.messaging.MulticastMessage(tokens=device_tokens,
        #     notification=messaging.Notification(title=title, body=body), data=data)
        return ProviderResult(success=True, provider_msg_id=f"fcm_{uuid.uuid4().hex[:8]}")


class SlackWebhookProvider(SlackProvider):
    """
    Niroskos: #bookings channel — high-value booking alerts for ops team
    Observer pattern: BookingService fires event → Slack notified
    """
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send(self, channel, message, blocks=None):
        print(f"[SLACK] #{channel}: {message[:60]}")
        # requests.post(self.webhook_url, json={'text': message, 'blocks': blocks})
        return ProviderResult(success=True, provider_msg_id=f"slack_{uuid.uuid4().hex[:8]}")


# ─── Provider Factory (Abstract Factory per tenant) ──────────

class TenantNotificationProviders:
    """
    Per-tenant provider set.
    India:  Postmark + Exotel + FCM + Slack
    Africa: SendGrid + Exotel + FCM + Slack (same SMS provider, diff email)

    Abstract Factory pattern — compatible family per tenant.
    """
    def __init__(
        self,
        email_provider: EmailProvider,
        sms_provider:   SMSProvider,
        push_provider:  Optional[PushProvider]  = None,
        slack_provider: Optional[SlackProvider] = None,
    ):
        self.email = email_provider
        self.sms   = sms_provider
        self.push  = push_provider
        self.slack = slack_provider


TENANT_PROVIDERS: Dict[str, TenantNotificationProviders] = {
    "niroskos_ke": TenantNotificationProviders(        # Kenya
        email_provider = SendGridEmailProvider(),
        sms_provider   = ExotelSMSProvider(),
        push_provider  = FCMPushProvider(),
        slack_provider = SlackWebhookProvider("https://hooks.slack.com/niroskos_ke"),
    ),
    "niroskos_in": TenantNotificationProviders(        # India
        email_provider = PostmarkEmailProvider(),
        sms_provider   = ExotelSMSProvider(),
        push_provider  = FCMPushProvider(),
        slack_provider = SlackWebhookProvider("https://hooks.slack.com/niroskos_in"),
    ),
}


# ═══════════════════════════════════════════════════════════════
# TEMPLATE ENGINE
# ═══════════════════════════════════════════════════════════════

@dataclass
class NotificationTemplate:
    event_type: EventType
    channel:    NotificationChannel
    subject:    str   = ""    # Email only
    body:       str   = ""    # Template string with {placeholders}
    tenant_id:  Optional[str] = None  # None = default, override per tenant


class TemplateEngine:
    """
    Event type + channel → rendered subject + body.
    Niroskos: Django templates ya simple .format() — jinja2 style.
    """

    _templates: Dict[tuple, NotificationTemplate] = {
        # (event_type, channel) → template
        (EventType.BOOKING_CONFIRMED, NotificationChannel.EMAIL): NotificationTemplate(
            event_type = EventType.BOOKING_CONFIRMED,
            channel    = NotificationChannel.EMAIL,
            subject    = "Booking Confirmed — {ref_code} | Niroskos Safaris",
            body       = """
Hi {customer_name},

Your safari booking is confirmed!

  Reference:  {ref_code}
  Package:    {package_name}
  Date:       {travel_date}
  Guests:     {guests}
  Amount:     {currency} {amount}

Our team will contact you 48 hours before the safari.

Warm regards,
Niroskos Safaris Team
            """.strip()
        ),
        (EventType.BOOKING_CONFIRMED, NotificationChannel.SMS): NotificationTemplate(
            event_type = EventType.BOOKING_CONFIRMED,
            channel    = NotificationChannel.SMS,
            body       = "Niroskos: Booking {ref_code} confirmed for {travel_date}. "
                         "Amount: {currency}{amount}. Questions? Reply HELP."
        ),
        (EventType.PAYMENT_COMPLETED, NotificationChannel.EMAIL): NotificationTemplate(
            event_type = EventType.PAYMENT_COMPLETED,
            channel    = NotificationChannel.EMAIL,
            subject    = "Payment Receipt — {ref_code}",
            body       = "Hi {customer_name}, payment of {currency}{amount} received "
                         "for booking {ref_code}. Balance due: {currency}{balance_due}."
        ),
        (EventType.PAYMENT_COMPLETED, NotificationChannel.SMS): NotificationTemplate(
            event_type = EventType.PAYMENT_COMPLETED,
            channel    = NotificationChannel.SMS,
            body       = "Niroskos: Payment {currency}{amount} received for {ref_code}. "
                         "Balance: {currency}{balance_due}."
        ),
        (EventType.OTP_REQUESTED, NotificationChannel.SMS): NotificationTemplate(
            event_type = EventType.OTP_REQUESTED,
            channel    = NotificationChannel.SMS,
            body       = "{otp} is your Niroskos verification code. Valid for 10 minutes. "
                         "Do not share with anyone."
        ),
        (EventType.HIGH_VALUE_BOOKING, NotificationChannel.SLACK): NotificationTemplate(
            event_type = EventType.HIGH_VALUE_BOOKING,
            channel    = NotificationChannel.SLACK,
            body       = ":money_with_wings: *High-value booking!* "
                         "Ref: {ref_code} | {currency}{amount} | {customer_name} | {package_name}"
        ),
        (EventType.PAYMENT_FAILED, NotificationChannel.EMAIL): NotificationTemplate(
            event_type = EventType.PAYMENT_FAILED,
            channel    = NotificationChannel.EMAIL,
            subject    = "Payment Failed — Action Required",
            body       = "Hi {customer_name}, your payment of {currency}{amount} failed. "
                         "Reason: {failure_reason}. Please retry: {retry_url}"
        ),
        (EventType.BOOKING_REMINDER, NotificationChannel.EMAIL): NotificationTemplate(
            event_type = EventType.BOOKING_REMINDER,
            channel    = NotificationChannel.EMAIL,
            subject    = "Safari Reminder — {days_until} days to go!",
            body       = "Hi {customer_name}, your safari {ref_code} is in {days_until} days. "
                         "Date: {travel_date}. Meeting point: {meeting_point}."
        ),
    }

    def render(
        self,
        event_type: EventType,
        channel:    NotificationChannel,
        data:       dict
    ) -> tuple[str, str]:
        """Returns (subject, body) — subject empty for SMS/Push"""
        template = self._templates.get((event_type, channel))
        if not template:
            # Fallback — generic
            subject = f"Notification: {event_type.value}"
            body    = f"You have a notification regarding {event_type.value}. Data: {data}"
            return subject, body

        try:
            subject = template.subject.format(**data) if template.subject else ""
            body    = template.body.format(**data)
        except KeyError as e:
            # Missing template variable — log and use partial render
            subject = template.subject
            body    = f"[Template error: missing {e}] {template.body}"

        return subject, body


# ═══════════════════════════════════════════════════════════════
# USER PREFERENCE FILTER
# ═══════════════════════════════════════════════════════════════

@dataclass
class UserNotificationPreferences:
    user_id:            str
    opted_out_channels: Set[NotificationChannel] = field(default_factory=set)
    opted_out_events:   Set[EventType]           = field(default_factory=set)
    quiet_hours_start:  Optional[int] = None     # Hour (0-23) — no non-critical notifications
    quiet_hours_end:    Optional[int] = None
    preferred_language: str = "en"


class UserPreferenceFilter:
    """
    Niroskos: User email opt-out (unsubscribe link in footer).
    Staff ne certain alerts disable kiye.
    Critical events (OTP, payment_failed) → preference ignore karo.
    """

    def __init__(self):
        self._preferences: Dict[str, UserNotificationPreferences] = {}

    def set_preferences(self, prefs: UserNotificationPreferences) -> None:
        self._preferences[prefs.user_id] = prefs

    def should_send(
        self,
        user_id:   str,
        channel:   NotificationChannel,
        event:     EventType,
        priority:  NotificationPriority
    ) -> tuple[bool, str]:
        """Returns (should_send, reason_if_skipped)"""

        # Critical priority — always send regardless of preferences
        if priority == NotificationPriority.CRITICAL:
            return True, ""

        prefs = self._preferences.get(user_id)
        if not prefs:
            return True, ""   # No prefs = send everything

        if channel in prefs.opted_out_channels:
            return False, f"user opted out of {channel.value}"

        if event in prefs.opted_out_events:
            return False, f"user opted out of {event.value}"

        # Quiet hours check (skip non-critical during quiet hours)
        if prefs.quiet_hours_start is not None and prefs.quiet_hours_end is not None:
            current_hour = datetime.now().hour
            in_quiet = self._in_quiet_hours(
                current_hour, prefs.quiet_hours_start, prefs.quiet_hours_end
            )
            if in_quiet and priority.value > NotificationPriority.HIGH.value:
                return False, f"quiet hours ({prefs.quiet_hours_start}-{prefs.quiet_hours_end})"

        return True, ""

    def _in_quiet_hours(self, current: int, start: int, end: int) -> bool:
        if start <= end:
            return start <= current < end
        else:   # Wraps midnight: 22-6
            return current >= start or current < end


# ═══════════════════════════════════════════════════════════════
# DEDUPLICATION
# ═══════════════════════════════════════════════════════════════

class DeduplicationStore:
    """
    Same notification nahi jaaye twice (e.g., webhook fires twice).
    Key = idempotency_key + channel
    TTL = 24 hours (same event same day = duplicate)

    In production: Redis SET NX with TTL
    """

    def __init__(self):
        self._store: Dict[str, datetime] = {}
        self._lock  = threading.Lock()
        self._ttl   = timedelta(hours=24)

    def is_duplicate(self, idempotency_key: str, channel: NotificationChannel) -> bool:
        dedup_key = f"{idempotency_key}:{channel.value}"
        with self._lock:
            if dedup_key in self._store:
                if datetime.now() - self._store[dedup_key] < self._ttl:
                    return True
                # TTL expired — not a duplicate anymore
                del self._store[dedup_key]
            return False

    def mark_sent(self, idempotency_key: str, channel: NotificationChannel) -> None:
        dedup_key = f"{idempotency_key}:{channel.value}"
        with self._lock:
            self._store[dedup_key] = datetime.now()


# ═══════════════════════════════════════════════════════════════
# CHANNEL DISPATCHER — sends via correct provider
# ═══════════════════════════════════════════════════════════════

class ChannelDispatcher:
    """
    Notification + Provider → send via correct channel.
    Retry logic here (or delegate to Celery).
    """

    MAX_ATTEMPTS = 3
    BASE_DELAY   = 1.0    # seconds (exponential backoff)

    def dispatch(
        self,
        notification: Notification,
        channel:      NotificationChannel,
        providers:    TenantNotificationProviders,
        context:      NotificationContext
    ) -> ProviderResult:
        for attempt in range(1, self.MAX_ATTEMPTS + 1):
            try:
                result = self._send(notification, channel, providers, context)
                if result.success:
                    notification.status         = NotificationStatus.SENT
                    notification.provider_msg_id = result.provider_msg_id
                    notification.sent_at         = datetime.now()
                    notification.attempts        = attempt
                    return result

                notification.error_message = result.error_message

            except Exception as e:
                notification.error_message = str(e)
                print(f"[DISPATCH] Attempt {attempt} failed: {e}")

            if attempt < self.MAX_ATTEMPTS:
                delay = self.BASE_DELAY * (2 ** (attempt - 1))
                print(f"[DISPATCH] Retry in {delay}s (attempt {attempt}/{self.MAX_ATTEMPTS})")
                time.sleep(delay)

        # All attempts failed
        notification.status   = NotificationStatus.FAILED
        notification.attempts = self.MAX_ATTEMPTS
        print(f"[DISPATCH] FAILED after {self.MAX_ATTEMPTS} attempts: {notification.notification_id}")
        return ProviderResult(success=False, provider_msg_id="",
                              error_message=notification.error_message)

    def _send(
        self,
        notification: Notification,
        channel:      NotificationChannel,
        providers:    TenantNotificationProviders,
        context:      NotificationContext
    ) -> ProviderResult:
        if channel == NotificationChannel.EMAIL:
            return providers.email.send(
                to       = notification.recipient,
                subject  = notification.subject,
                body     = notification.body,
                metadata = {"notification_id": notification.notification_id}
            )
        elif channel == NotificationChannel.SMS:
            return providers.sms.send(
                to       = notification.recipient,
                message  = notification.body,
                metadata = {"notification_id": notification.notification_id}
            )
        elif channel == NotificationChannel.PUSH:
            return providers.push.send(
                device_tokens = context.device_tokens,
                title         = notification.subject or "Niroskos",
                body          = notification.body,
                data          = context.data
            )
        elif channel == NotificationChannel.SLACK:
            return providers.slack.send(
                channel = context.slack_channel or "bookings",
                message = notification.body
            )
        else:
            raise ValueError(f"Unsupported channel: {channel}")


# ═══════════════════════════════════════════════════════════════
# OBSERVER PATTERN — Event Listeners
# ═══════════════════════════════════════════════════════════════

class NotificationObserver(ABC):
    """
    Observer interface — different modules subscribe to notification events.
    Decouples event source from notification logic.
    """
    @abstractmethod
    def on_notification_sent(self, notification: Notification) -> None:
        pass

    @abstractmethod
    def on_notification_failed(self, notification: Notification) -> None:
        pass


class AuditLogObserver(NotificationObserver):
    """Every notification attempt logged — compliance requirement"""
    def on_notification_sent(self, notification):
        print(f"[AUDIT] SENT | {notification.channel.value} → {notification.recipient} "
              f"| msg_id={notification.provider_msg_id}")
        # NotificationLog.objects.create(...)

    def on_notification_failed(self, notification):
        print(f"[AUDIT] FAILED | {notification.channel.value} → {notification.recipient} "
              f"| error={notification.error_message}")


class DeliveryTrackingObserver(NotificationObserver):
    """Track delivery for analytics dashboard"""
    def __init__(self):
        self._stats: Dict[str, int] = {
            "sent": 0, "failed": 0,
            "email_sent": 0, "sms_sent": 0,
            "push_sent": 0, "slack_sent": 0
        }

    def on_notification_sent(self, notification):
        self._stats["sent"] += 1
        self._stats[f"{notification.channel.value}_sent"] += 1

    def on_notification_failed(self, notification):
        self._stats["failed"] += 1

    @property
    def stats(self) -> dict:
        return dict(self._stats)


class AlertObserver(NotificationObserver):
    """If critical notification fails → alert ops team on Slack"""
    def on_notification_sent(self, n): pass

    def on_notification_failed(self, notification):
        # Only alert for critical failures (OTP, payment)
        print(f"[ALERT] Critical notification failed: "
              f"{notification.channel.value} to {notification.recipient}")
        # SlackWebhookProvider().send('#ops-alerts', f'CRITICAL: notification failed...')


# ═══════════════════════════════════════════════════════════════
# NOTIFICATION SERVICE — Facade
# ═══════════════════════════════════════════════════════════════

class NotificationService:
    """
    Facade — caller sends one NotificationContext, everything else handled internally.

    Flow:
      context → channel_selector → [email, sms]
              → template_engine  → rendered subject+body per channel
              → pref_filter      → user opted out? skip
              → dedup_store      → already sent? skip
              → dispatcher       → send via provider (retry on fail)
              → observers        → audit log, tracking, alerts

    Niroskos equivalent:
      apps/communications/services/notification_service.py
      Called from:
        booking_signals.py (post_save Booking → BOOKING_CONFIRMED)
        payment_signals.py (post_save PaymentAllocation → PAYMENT_COMPLETED)
        tasks.py (Celery periodic → BOOKING_REMINDER 48h before travel)
    """

    def __init__(self):
        self._channel_selector   = RuleBasedChannelSelector()
        self._template_engine    = TemplateEngine()
        self._pref_filter        = UserPreferenceFilter()
        self._dedup_store        = DeduplicationStore()
        self._dispatcher         = ChannelDispatcher()
        self._observers: List[NotificationObserver] = []
        self._notifications: List[Notification] = []
        self._lock = threading.Lock()

    def subscribe(self, observer: NotificationObserver) -> None:
        self._observers.append(observer)

    def send(self, context: NotificationContext) -> List[Notification]:
        """
        Main entry point.
        Returns list of Notification objects (one per channel attempted).
        """
        channels = self._channel_selector.get_channels(context.event_type, context)
        providers = TENANT_PROVIDERS.get(context.tenant_id)

        if not providers:
            print(f"[NOTIF] No providers for tenant: {context.tenant_id}")
            return []

        dispatched = []

        for channel in channels:
            notification = self._process_channel(context, channel, providers)
            if notification:
                dispatched.append(notification)

        return dispatched

    def _process_channel(
        self,
        context:   NotificationContext,
        channel:   NotificationChannel,
        providers: TenantNotificationProviders
    ) -> Optional[Notification]:

        # 1. Check user preference
        should_send, reason = self._pref_filter.should_send(
            context.user_id, channel, context.event_type, context.priority
        )
        if not should_send:
            print(f"[NOTIF] Skipped ({reason}): {channel.value} for {context.user_id}")
            return self._make_skipped_notification(context, channel, reason)

        # 2. Deduplication check
        if self._dedup_store.is_duplicate(context.idempotency_key, channel):
            print(f"[NOTIF] Dedup skip: {context.idempotency_key} {channel.value}")
            return self._make_skipped_notification(context, channel, "duplicate")

        # 3. Render template
        subject, body = self._template_engine.render(
            context.event_type, channel, context.data
        )

        # 4. Determine recipient
        recipient = self._get_recipient(context, channel)
        if not recipient:
            print(f"[NOTIF] No recipient for channel {channel.value}")
            return None

        # 5. Build notification object
        notification = Notification(
            context_key = context.idempotency_key,
            channel     = channel,
            recipient   = recipient,
            subject     = subject,
            body        = body
        )

        with self._lock:
            self._notifications.append(notification)

        # 6. Dispatch (with retry)
        result = self._dispatcher.dispatch(notification, channel, providers, context)

        # 7. Mark dedup after successful send
        if result.success:
            self._dedup_store.mark_sent(context.idempotency_key, channel)

        # 8. Notify observers
        self._notify_observers(notification)

        return notification

    def _get_recipient(self, context: NotificationContext, channel: NotificationChannel) -> Optional[str]:
        if channel == NotificationChannel.EMAIL:
            return context.email
        elif channel == NotificationChannel.SMS:
            return context.phone
        elif channel == NotificationChannel.PUSH:
            return context.device_tokens[0] if context.device_tokens else None
        elif channel == NotificationChannel.SLACK:
            return context.slack_channel or "bookings"
        return None

    def _make_skipped_notification(
        self, context: NotificationContext, channel: NotificationChannel, reason: str
    ) -> Notification:
        n = Notification(
            context_key = context.idempotency_key,
            channel     = channel,
            recipient   = "",
            status      = NotificationStatus.SKIPPED,
            error_message = reason
        )
        with self._lock:
            self._notifications.append(n)
        return n

    def _notify_observers(self, notification: Notification) -> None:
        for observer in self._observers:
            try:
                if notification.status == NotificationStatus.SENT:
                    observer.on_notification_sent(notification)
                elif notification.status == NotificationStatus.FAILED:
                    observer.on_notification_failed(notification)
            except Exception as e:
                print(f"[NOTIF] Observer error: {e}")

    def get_history(self) -> List[Notification]:
        return list(self._notifications)

    def set_user_preferences(self, prefs: UserNotificationPreferences) -> None:
        self._pref_filter.set_preferences(prefs)
```

---

## Django Signals Integration (Niroskos Pattern)

```python
# apps/communications/signals.py
# Observer pattern — BookingService knows nothing about notifications

from django.db.models.signals import post_save
from django.dispatch import receiver

# @receiver(post_save, sender=Booking)
# def notify_booking_confirmed(sender, instance, created, **kwargs):
#     """
#     Subject:  Booking model (Django)
#     Observer: this function
#     Signal:   post_save
#
#     Booking saved as CONFIRMED → notification fires.
#     BookingService mein koi notification code nahi — fully decoupled.
#     """
#     if instance.status == BookingStatus.CONFIRMED and created is False:
#         context = NotificationContext(
#             event_type      = EventType.BOOKING_CONFIRMED,
#             user_id         = str(instance.customer.id),
#             tenant_id       = instance.subsidiary.code,
#             priority        = NotificationPriority.HIGH,
#             idempotency_key = f"booking_confirmed_{instance.id}",
#             email           = instance.customer.email,
#             phone           = instance.customer.phone,
#             data = {
#                 'customer_name': instance.customer.get_full_name(),
#                 'ref_code':      instance.ref_code,
#                 'package_name':  instance.package.name,
#                 'travel_date':   instance.travel_date.strftime('%d %b %Y'),
#                 'guests':        instance.guests,
#                 'currency':      instance.currency,
#                 'amount':        instance.total_amount,
#             }
#         )
#         notification_service.send(context)


# Celery task for scheduled reminders (48h before safari)
# @shared_task
# def send_booking_reminders():
#     """
#     Periodic Celery task — every hour, check upcoming bookings.
#     Bookings where travel_date = tomorrow + 1 day → send reminder.
#     """
#     upcoming = Booking.objects.filter(
#         travel_date=date.today() + timedelta(days=2),
#         status=BookingStatus.PAID,
#         reminder_sent=False
#     )
#     for booking in upcoming:
#         context = NotificationContext(
#             event_type      = EventType.BOOKING_REMINDER,
#             user_id         = str(booking.customer.id),
#             tenant_id       = booking.subsidiary.code,
#             priority        = NotificationPriority.NORMAL,
#             idempotency_key = f"reminder_48h_{booking.id}",
#             email           = booking.customer.email,
#             data = {
#                 'customer_name': booking.customer.get_full_name(),
#                 'ref_code':      booking.ref_code,
#                 'travel_date':   booking.travel_date.strftime('%d %b %Y'),
#                 'days_until':    2,
#                 'meeting_point': booking.package.meeting_point,
#             }
#         )
#         notification_service.send(context)
#         booking.reminder_sent = True
#         booking.save(update_fields=['reminder_sent'])
```

---

## Demo

```python
# ─── Setup ───────────────────────────────────────────────────
tracker  = DeliveryTrackingObserver()
audit    = AuditLogObserver()
alerter  = AlertObserver()

svc = NotificationService()
svc.subscribe(tracker)
svc.subscribe(audit)
svc.subscribe(alerter)


# ─── Flow 1: Booking Confirmed ────────────────────────────────
print("=" * 55)
print("FLOW 1: Booking Confirmed → Email + SMS")
print("=" * 55)

context = NotificationContext(
    event_type      = EventType.BOOKING_CONFIRMED,
    user_id         = "user_123",
    tenant_id       = "niroskos_ke",
    priority        = NotificationPriority.HIGH,
    idempotency_key = "booking_confirmed_BKG001",
    email           = "rahul@gmail.com",
    phone           = "+254712345678",
    data = {
        "customer_name": "Rahul Sharma",
        "ref_code":      "BKG-001",
        "package_name":  "Masai Mara Safari 3D/2N",
        "travel_date":   "15 May 2026",
        "guests":        2,
        "currency":      "KES",
        "amount":        "85,000",
    }
)
notifications = svc.send(context)
print(f"Dispatched: {len(notifications)} notifications")


# ─── Flow 2: OTP → SMS only (critical) ────────────────────────
print("\n" + "=" * 55)
print("FLOW 2: OTP → SMS only (critical priority)")
print("=" * 55)

otp_context = NotificationContext(
    event_type      = EventType.OTP_REQUESTED,
    user_id         = "user_456",
    tenant_id       = "niroskos_in",
    priority        = NotificationPriority.CRITICAL,
    idempotency_key = "otp_user456_1714900000",
    phone           = "+919876543210",
    data            = {"otp": "847291"}
)
svc.send(otp_context)


# ─── Flow 3: High-value booking → Email + Slack (ops alert) ───
print("\n" + "=" * 55)
print("FLOW 3: High-value Booking → Email + Slack")
print("=" * 55)

hv_context = NotificationContext(
    event_type      = EventType.HIGH_VALUE_BOOKING,
    user_id         = "user_789",
    tenant_id       = "niroskos_ke",
    priority        = NotificationPriority.HIGH,
    idempotency_key = "high_value_BKG002",
    email           = "vip@client.com",
    slack_channel   = "bookings",
    data = {
        "customer_name": "James Mwangi",
        "ref_code":      "BKG-002",
        "package_name":  "Private Conservancy — 7D/6N",
        "currency":      "USD",
        "amount":        "12,500",
    }
)
svc.send(hv_context)


# ─── Flow 4: User opted out of SMS ────────────────────────────
print("\n" + "=" * 55)
print("FLOW 4: User opted out of SMS")
print("=" * 55)

svc.set_user_preferences(UserNotificationPreferences(
    user_id            = "user_optout",
    opted_out_channels = {NotificationChannel.SMS}
))

optout_context = NotificationContext(
    event_type      = EventType.BOOKING_CONFIRMED,
    user_id         = "user_optout",
    tenant_id       = "niroskos_ke",
    priority        = NotificationPriority.HIGH,
    idempotency_key = "booking_confirmed_BKG003",
    email           = "optout@gmail.com",
    phone           = "+254799999999",
    data = {
        "customer_name": "Jane Doe", "ref_code": "BKG-003",
        "package_name": "Budget Safari", "travel_date": "20 May 2026",
        "guests": 1, "currency": "KES", "amount": "45,000",
    }
)
notifications = svc.send(optout_context)
for n in notifications:
    print(f"  {n.channel.value}: {n.status.value} ({n.error_message or 'ok'})")


# ─── Flow 5: Deduplication ─────────────────────────────────────
print("\n" + "=" * 55)
print("FLOW 5: Duplicate event (signal fires twice)")
print("=" * 55)

same_key_context = NotificationContext(
    event_type      = EventType.PAYMENT_COMPLETED,
    user_id         = "user_123",
    tenant_id       = "niroskos_ke",
    priority        = NotificationPriority.HIGH,
    idempotency_key = "payment_completed_PAY001",   # Same key both times
    email           = "rahul@gmail.com",
    phone           = "+254712345678",
    data = {
        "customer_name": "Rahul Sharma", "ref_code": "BKG-001",
        "currency": "KES", "amount": "85,000", "balance_due": "0",
    }
)
print("First send:")
svc.send(same_key_context)
print("Second send (duplicate — should be skipped):")
svc.send(same_key_context)


# ─── Stats ─────────────────────────────────────────────────────
print("\n" + "=" * 55)
print("DELIVERY STATS")
print("=" * 55)
print(tracker.stats)
```

---

## Interview Q&A

**Q: "Notification system ka design explain karo — Niroskos Communications module."**
> "Niroskos mein notifications ek dedicated communications module mein tha. Booking confirm hone pe Django Signal fire hota tha — post_save on Booking. Signal handler ne NotificationService.send() call kiya with a NotificationContext. BookingService ko kuch nahi pata tha notifications ke baare mein — fully decoupled Observer pattern.
>
> NotificationService internally: Channel Selector decides email+SMS for booking events, Template Engine renders channel-specific content, User Preference Filter checks if customer ne SMS opt-out kiya tha, Dedup Store checks if same event already sent (webhook can fire twice), then Channel Dispatcher sends via Postmark (India) or SendGrid (Africa) for email, Exotel for SMS.
>
> For bulk reminders — 48 hours before safari — a Celery periodic task ran every hour, queried upcoming bookings, and called the same NotificationService. Same code path, whether triggered by signal or scheduled task."

**Q: "Multi-tenant notifications — different providers per tenant?"**
> "Abstract Factory pattern. Each tenant has a TenantNotificationProviders object — a compatible family of email, SMS, push, and Slack providers. Kenya tenant gets SendGrid + Exotel + FCM. India tenant gets Postmark + Exotel + FCM. The NotificationService fetches the right providers by tenant_id and passes them to the Channel Dispatcher. Adding a new tenant means creating one TenantNotificationProviders instance and adding it to the registry — zero changes to dispatch logic."

**Q: "How do you prevent the same notification going twice?"**
> "Two layers. First, idempotency key — every NotificationContext has a key like booking_confirmed_{booking_id}. Before sending any channel, we check Redis: has this key + channel combination been sent in the last 24 hours? If yes, skip. After successful send, we mark it in Redis with SET NX. Second, Django Signal post_save can fire for multiple updates — we guard with a status check: only trigger notification when status transitions to CONFIRMED, not on every save."

**Q: "User opted out of SMS — how is that handled?"**
> "UserPreferenceFilter holds per-user preferences — opted_out_channels set and opted_out_events set. Before rendering and dispatching, we call should_send(user_id, channel, event, priority). If channel is in opted_out_channels, return False with reason. One exception: CRITICAL priority (OTP, payment failure) bypasses preference filters entirely — you can't opt out of your OTP. This matches TRAI guidelines — transactional messages are exempt from DND."

**Q: "How does the retry work?"**
> "ChannelDispatcher has 3 attempts with exponential backoff — 1s, 2s, 4s. If all 3 fail, notification status becomes FAILED and AlertObserver fires a Slack message to #ops-alerts for critical notifications. In production, this retry happens inside a Celery task — so the backoff is Celery's countdown parameter, not time.sleep(). The Celery task receives a notification_id, fetches the Notification object, and re-dispatches. This way the web process isn't blocked waiting."

---

## Patterns Used

| Pattern | Where | Why |
|---|---|---|
| **Observer** | Django Signal → NotificationService | BookingService decoupled from notification logic |
| **Strategy** | ChannelSelector, EmailProvider, SMSProvider | Swap channel rules and providers independently |
| **Abstract Factory** | TenantNotificationProviders | Compatible provider family per tenant |
| **Facade** | NotificationService.send() | Single entry point — hides all complexity |
| **Template Method** | TemplateEngine.render() | Skeleton same — subject+body varies per channel |
| **Chain of Responsibility** | pref_filter → dedup → dispatch | Each step can short-circuit the pipeline |

---

*Last Updated: April 2026 | SDE-2 Interview Prep — Niroskos Communications Module*
