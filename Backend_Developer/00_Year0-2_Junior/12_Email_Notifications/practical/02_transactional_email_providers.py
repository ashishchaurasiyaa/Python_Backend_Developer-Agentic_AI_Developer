"""
Transactional Email Providers — Production Patterns
====================================================
Covers: AWS SES (SMTP + API), SendGrid, Postmark, Resend,
        Jinja2 templates, bounce/suppression handling,
        multi-provider failover, background-queue pattern,
        webhook signature verification, and compliance notes.

All code is structured as importable, production-ready building
blocks.  The __main__ block runs a dry-run demo that requires no
external infrastructure.

Dependencies (install only what you use):
    pip install aiosmtplib          # async SMTP (SES SMTP path)
    pip install boto3               # AWS SES API path
    pip install sendgrid            # SendGrid SDK
    pip install aiohttp             # SendGrid async HTTP path
    pip install requests            # Postmark / Resend sync
    pip install resend              # Resend SDK
    pip install jinja2              # local template rendering
    pip install mjml                # MJML → email-safe HTML
    pip install celery[redis]       # background queue
"""

from __future__ import annotations

import asyncio
import dataclasses
import hashlib
import hmac
import json
import logging
import smtplib
import time
from abc import ABC, abstractmethod
from email.header import Header
from email.message import EmailMessage
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


# ==========================================================================
# 1. SHARED EMAIL MESSAGE DATACLASS
# ==========================================================================

@dataclasses.dataclass
class EmailPayload:
    """Provider-agnostic email payload passed to every send function."""

    to: str
    subject: str
    html_body: str
    text_body: str
    from_address: str = "noreply@yourdomain.com"
    reply_to: Optional[str] = None
    # Metadata for analytics / idempotency
    message_stream: str = "outbound"
    tags: Optional[Dict[str, str]] = None


# ==========================================================================
# 2. ABSTRACT PROVIDER BASE CLASS
# ==========================================================================

class EmailProvider(ABC):
    """
    All concrete providers implement this interface so callers
    can swap providers without changing business logic.
    """

    name: str = "base"

    @abstractmethod
    async def send(self, payload: EmailPayload) -> Dict[str, Any]:
        """
        Send an email.

        Returns a dict with at minimum:
            {"provider": str, "message_id": str, "status": int}
        Raises ProviderError on non-retryable failures.
        Raises RetryableError on transient failures (5xx, network).
        """


class ProviderError(Exception):
    """Non-retryable provider failure (invalid API key, bad address …)."""


class RetryableError(Exception):
    """Transient failure — caller should retry with back-off."""


# ==========================================================================
# 3. AWS SES — SMTP PATH (aiosmtplib)
# ==========================================================================

# pip install aiosmtplib

SES_SMTP_HOST = "email-smtp.us-east-1.amazonaws.com"
SES_SMTP_PORT = 587


def build_ses_smtp_message(payload: EmailPayload) -> EmailMessage:
    """
    Construct a stdlib EmailMessage from an EmailPayload.

    Uses the stdlib email package directly so no third-party
    SDK is required for the SMTP path.
    """
    msg = EmailMessage()
    msg["From"] = payload.from_address
    msg["To"] = payload.to
    # RFC 2047 encoding ensures non-ASCII subjects are transmitted safely.
    msg["Subject"] = Header(payload.subject, "utf-8").encode()
    if payload.reply_to:
        msg["Reply-To"] = payload.reply_to

    msg.set_content(payload.text_body, charset="utf-8")
    msg.add_alternative(payload.html_body, subtype="html", charset="utf-8")
    return msg


class SESSmtpProvider(EmailProvider):
    """
    Send via AWS SES SMTP endpoint.

    Pros: no additional SDK, works with any SMTP-capable lib.
    Cons: SMTP credentials rotate; prefer the API path for new projects.

    Setup:
        1. Verify your domain in SES (add SPF + DKIM DNS records).
        2. Request sandbox removal (AWS Support).
        3. Create SMTP credentials in SES console → IAM user.
    """

    name = "ses_smtp"

    def __init__(self, username: str, password: str,
                 host: str = SES_SMTP_HOST, port: int = SES_SMTP_PORT) -> None:
        self._username = username
        self._password = password
        self._host = host
        self._port = port

    async def send(self, payload: EmailPayload) -> Dict[str, Any]:
        # aiosmtplib is imported lazily so the class remains importable
        # even when the package is not installed.
        try:
            import aiosmtplib  # type: ignore
        except ImportError as exc:
            raise ProviderError("aiosmtplib not installed: pip install aiosmtplib") from exc

        msg = build_ses_smtp_message(payload)
        try:
            result = await aiosmtplib.send(
                msg,
                hostname=self._host,
                port=self._port,
                username=self._username,
                password=self._password,
                start_tls=True,
            )
            return {"provider": self.name, "message_id": str(result), "status": 200}
        except aiosmtplib.SMTPException as exc:
            raise RetryableError(f"SMTP error: {exc}") from exc


# ==========================================================================
# 4. AWS SES — API PATH (boto3 SESv2)
# ==========================================================================

# pip install boto3

class SESApiProvider(EmailProvider):
    """
    Send via AWS SES v2 API using boto3.

    Advantages over SMTP:
        - Richer error responses.
        - No credential rotation required (IAM role preferred).
        - Supports configuration sets for analytics.
    """

    name = "ses_api"

    def __init__(self, region: str = "us-east-1",
                 configuration_set: Optional[str] = None) -> None:
        self._region = region
        self._configuration_set = configuration_set

    def _client(self):  # type: ignore[return]
        try:
            import boto3  # type: ignore
        except ImportError as exc:
            raise ProviderError("boto3 not installed: pip install boto3") from exc
        return boto3.client("sesv2", region_name=self._region)

    async def send(self, payload: EmailPayload) -> Dict[str, Any]:
        # boto3 is synchronous; run in a thread pool to avoid blocking.
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._send_sync, payload)

    def _send_sync(self, payload: EmailPayload) -> Dict[str, Any]:
        ses = self._client()
        kwargs: Dict[str, Any] = {
            "FromEmailAddress": payload.from_address,
            "Destination": {"ToAddresses": [payload.to]},
            "Content": {
                "Simple": {
                    "Subject": {"Data": payload.subject, "Charset": "UTF-8"},
                    "Body": {
                        "Text": {"Data": payload.text_body, "Charset": "UTF-8"},
                        "Html": {"Data": payload.html_body, "Charset": "UTF-8"},
                    },
                }
            },
        }
        if self._configuration_set:
            kwargs["ConfigurationSetName"] = self._configuration_set

        try:
            response = ses.send_email(**kwargs)
            return {
                "provider": self.name,
                "message_id": response.get("MessageId", ""),
                "status": 200,
            }
        except Exception as exc:
            error_code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
            if error_code in ("MessageRejected", "InvalidParameterValue"):
                raise ProviderError(f"SES API error: {exc}") from exc
            raise RetryableError(f"SES transient error: {exc}") from exc


# ==========================================================================
# 5. SES BOUNCE / COMPLAINT WEBHOOK (SNS notification handler)
# ==========================================================================

def parse_ses_sns_notification(raw_body: str) -> Optional[Dict[str, Any]]:
    """
    Parse an AWS SNS notification forwarded from SES.

    SES publishes Bounce and Complaint events to an SNS topic.
    Subscribe an HTTPS endpoint (your webhook) to that topic.

    Example SNS payload:
        {
          "notificationType": "Bounce",
          "bounce": {
            "bouncedRecipients": [{"emailAddress": "bad@example.com"}],
            "bounceType": "Permanent"
          }
        }

    Returns a normalised dict or None if the notification is not
    a bounce/complaint.
    """
    try:
        envelope = json.loads(raw_body)
        inner_message = json.loads(envelope.get("Message", "{}"))
    except (json.JSONDecodeError, TypeError):
        log.warning("Could not parse SES SNS notification")
        return None

    notification_type = inner_message.get("notificationType")

    if notification_type == "Bounce":
        bounce = inner_message.get("bounce", {})
        bounce_type = bounce.get("bounceType", "")
        recipients = [
            r["emailAddress"]
            for r in bounce.get("bouncedRecipients", [])
        ]
        return {
            "type": "bounce",
            "bounce_type": "permanent" if bounce_type == "Permanent" else "soft",
            "recipients": recipients,
        }

    if notification_type == "Complaint":
        complaint = inner_message.get("complaint", {})
        recipients = [
            r["emailAddress"]
            for r in complaint.get("complainedRecipients", [])
        ]
        return {
            "type": "complaint",
            "recipients": recipients,
        }

    return None


# ==========================================================================
# 6. SENDGRID PROVIDER (async REST via aiohttp)
# ==========================================================================

# pip install aiohttp

SENDGRID_API_URL = "https://api.sendgrid.com/v3/mail/send"


class SendGridProvider(EmailProvider):
    """
    Send via the SendGrid v3 REST API using aiohttp.

    Strengths: mature platform, marketing + transactional.
    Weakness:  pricier than SES at high volume.

    Pricing (2024): $19.95 / 40K emails per month and up.
    """

    name = "sendgrid"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def send(self, payload: EmailPayload) -> Dict[str, Any]:
        try:
            import aiohttp  # type: ignore
        except ImportError as exc:
            raise ProviderError("aiohttp not installed: pip install aiohttp") from exc

        body = {
            "personalizations": [
                {"to": [{"email": payload.to}]}
            ],
            "from": {"email": payload.from_address},
            "subject": payload.subject,
            "content": [
                {"type": "text/plain", "value": payload.text_body},
                {"type": "text/html", "value": payload.html_body},
            ],
        }
        if payload.reply_to:
            body["reply_to"] = {"email": payload.reply_to}

        async with aiohttp.ClientSession() as session:
            async with session.post(
                SENDGRID_API_URL,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=body,
            ) as resp:
                if resp.status == 202:
                    message_id = resp.headers.get("X-Message-Id", "")
                    return {"provider": self.name, "message_id": message_id, "status": 202}
                if resp.status >= 500:
                    raise RetryableError(f"SendGrid 5xx: {resp.status}")
                error_text = await resp.text()
                raise ProviderError(f"SendGrid error {resp.status}: {error_text}")


def verify_sendgrid_webhook(
    payload_bytes: bytes,
    signature: str,
    timestamp: str,
    webhook_secret: str,
) -> bool:
    """
    Validate the HMAC-SHA256 signature on incoming SendGrid event webhooks.

    SendGrid signs the concatenation of timestamp + raw body.
    Compare using hmac.compare_digest to prevent timing attacks.
    """
    expected = hmac.new(
        webhook_secret.encode(),
        (timestamp + payload_bytes.decode()).encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def parse_sendgrid_webhook_events(raw_body: str) -> List[Dict[str, Any]]:
    """
    Parse the array of events that SendGrid POSTs to your webhook URL.

    Relevant event types: delivered, open, click, bounce, spamreport,
    unsubscribe, group_unsubscribe.

    Returns a list of normalised event dicts.
    """
    try:
        events: List[Dict[str, Any]] = json.loads(raw_body)
    except json.JSONDecodeError:
        log.warning("Could not decode SendGrid webhook body")
        return []

    normalised: List[Dict[str, Any]] = []
    for event in events:
        normalised.append({
            "event": event.get("event"),
            "email": event.get("email"),
            "timestamp": event.get("timestamp"),
            "bounce_type": event.get("type"),          # "blocked" / "bounce"
            "url": event.get("url"),                   # for click events
        })
    return normalised


# ==========================================================================
# 7. SENDGRID — PROVIDER-SIDE DYNAMIC TEMPLATE
# ==========================================================================

class SendGridTemplateEmail:
    """
    Send a provider-managed template email via the SendGrid SDK.

    Use provider-side templates when:
        - Non-developers need to edit the template.
        - You want A/B testing via the SendGrid dashboard.

    # pip install sendgrid
    """

    @staticmethod
    def send(
        to: str,
        template_id: str,
        dynamic_data: Dict[str, Any],
        from_address: str = "noreply@yourdomain.com",
        api_key: str = "",
    ) -> int:
        """
        Send a dynamic template.  Returns the HTTP status code.

        Example dynamic_data:
            {"first_name": "Alice", "reset_link": "https://app.com/reset/xyz"}
        """
        try:
            from sendgrid import SendGridAPIClient  # type: ignore
            from sendgrid.helpers.mail import Mail  # type: ignore
        except ImportError as exc:
            raise ProviderError("sendgrid not installed: pip install sendgrid") from exc

        message = Mail(
            from_email=from_address,
            to_emails=to,
        )
        message.template_id = template_id
        message.dynamic_template_data = dynamic_data

        sg = SendGridAPIClient(api_key=api_key)
        response = sg.send(message)
        return response.status_code


# ==========================================================================
# 8. POSTMARK PROVIDER
# ==========================================================================

# pip install requests

POSTMARK_API_URL = "https://api.postmarkapp.com/email"


class PostmarkProvider(EmailProvider):
    """
    Send via the Postmark REST API.

    Postmark is purpose-built for transactional email (password reset,
    receipts, sign-up confirmation).  It maintains strict separation
    between transactional and broadcast "message streams" to protect
    deliverability.

    Pricing (2024): $15 / 10K emails per month.
    Best deliverability among major providers.
    """

    name = "postmark"

    def __init__(self, server_token: str) -> None:
        self._token = server_token

    async def send(self, payload: EmailPayload) -> Dict[str, Any]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._send_sync, payload)

    def _send_sync(self, payload: EmailPayload) -> Dict[str, Any]:
        try:
            import requests  # type: ignore
        except ImportError as exc:
            raise ProviderError("requests not installed: pip install requests") from exc

        body: Dict[str, Any] = {
            "From": payload.from_address,
            "To": payload.to,
            "Subject": payload.subject,
            "HtmlBody": payload.html_body,
            "TextBody": payload.text_body,
            "MessageStream": payload.message_stream,
        }
        if payload.reply_to:
            body["ReplyTo"] = payload.reply_to

        resp = requests.post(
            POSTMARK_API_URL,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Postmark-Server-Token": self._token,
            },
            json=body,
            timeout=10,
        )

        data = resp.json()
        if resp.status_code == 200:
            return {
                "provider": self.name,
                "message_id": data.get("MessageID", ""),
                "status": 200,
            }
        if resp.status_code >= 500:
            raise RetryableError(f"Postmark 5xx: {resp.status_code}")
        raise ProviderError(f"Postmark error {resp.status_code}: {data}")


# ==========================================================================
# 9. RESEND PROVIDER
# ==========================================================================

# pip install resend

class ResendProvider(EmailProvider):
    """
    Send via Resend — a modern, developer-focused email API.

    Strengths: clean Python SDK, React Email integration,
               50K emails / month at $20.
    Weakness:  newer player, smaller ecosystem than SendGrid.
    """

    name = "resend"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def send(self, payload: EmailPayload) -> Dict[str, Any]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._send_sync, payload)

    def _send_sync(self, payload: EmailPayload) -> Dict[str, Any]:
        try:
            import resend  # type: ignore
        except ImportError as exc:
            raise ProviderError("resend not installed: pip install resend") from exc

        resend.api_key = self._api_key
        response = resend.Emails.send({
            "from": payload.from_address,
            "to": payload.to,
            "subject": payload.subject,
            "html": payload.html_body,
            "text": payload.text_body,
        })
        return {
            "provider": self.name,
            "message_id": response.get("id", ""),
            "status": 200,
        }


# ==========================================================================
# 10. LOCAL JINJA2 TEMPLATE RENDERING
# ==========================================================================

# pip install jinja2

def render_jinja2_template(
    template_name: str,
    context: Dict[str, Any],
    template_dir: str = "templates",
) -> str:
    """
    Render an HTML email from a Jinja2 template file.

    Use this approach when:
        - Your team maintains templates in version control.
        - You want full Python-side control over rendering.

    Example template (templates/welcome.html):
        <p>Hi {{ name }},</p>
        <p>Click <a href="{{ link }}">here</a> to verify.</p>
    """
    try:
        from jinja2 import Environment, FileSystemLoader  # type: ignore
    except ImportError as exc:
        raise ProviderError("jinja2 not installed: pip install jinja2") from exc

    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=True,          # prevents XSS in email HTML
    )
    template = env.get_template(template_name)
    return template.render(**context)


def render_jinja2_string(template_str: str, context: Dict[str, Any]) -> str:
    """
    Render a Jinja2 template from a string (no file I/O).

    Useful for unit tests and inline templates.
    """
    try:
        from jinja2 import Environment  # type: ignore
    except ImportError as exc:
        raise ProviderError("jinja2 not installed: pip install jinja2") from exc

    env = Environment(autoescape=True)
    return env.from_string(template_str).render(**context)


# ==========================================================================
# 11. MJML — RESPONSIVE EMAIL HTML
# ==========================================================================

# pip install mjml

EXAMPLE_MJML = """
<mjml>
  <mj-body>
    <mj-section>
      <mj-column>
        <mj-text font-size="20px">Hello {{ name }}</mj-text>
        <mj-button href="{{ link }}">Verify Email</mj-button>
      </mj-column>
    </mj-section>
  </mj-body>
</mjml>
"""


def mjml_to_email_html(mjml_source: str) -> str:
    """
    Compile MJML markup to email-safe HTML.

    MJML abstracts away the table-based layout tricks required to
    make emails render correctly across Outlook, Gmail, and Apple Mail.

    Workflow:
        1. Design in MJML.
        2. Compile at deploy time (or render on the fly).
        3. Pass compiled HTML to any provider's send function.
    """
    try:
        from mjml import mjml_to_html  # type: ignore
    except ImportError as exc:
        raise ProviderError("mjml not installed: pip install mjml") from exc

    result = mjml_to_html(mjml_source)
    if result.errors:
        raise ProviderError(f"MJML compilation errors: {result.errors}")
    return result.html


# ==========================================================================
# 12. IN-MEMORY SUPPRESSION LIST
# ==========================================================================

class SuppressionList:
    """
    Track addresses that must never receive email.

    In production, replace this with a database-backed store
    (e.g. PostgreSQL table, Redis set) so state survives restarts.

    Rules:
        - Hard bounce  → suppress permanently.
        - Spam report  → suppress permanently.
        - Soft bounce  → track count; suppress after threshold.
    """

    SOFT_BOUNCE_THRESHOLD = 3

    def __init__(self) -> None:
        self._hard_suppressed: set = set()
        self._soft_bounce_counts: Dict[str, int] = {}

    def add_hard_suppress(self, email: str, reason: str) -> None:
        """Permanently suppress an address."""
        self._hard_suppressed.add(email.lower())
        log.info("Suppressed %s: %s", email, reason)

    def record_soft_bounce(self, email: str) -> None:
        """Increment the soft-bounce counter; auto-suppress at threshold."""
        key = email.lower()
        self._soft_bounce_counts[key] = self._soft_bounce_counts.get(key, 0) + 1
        if self._soft_bounce_counts[key] >= self.SOFT_BOUNCE_THRESHOLD:
            self.add_hard_suppress(email, "soft_bounce_threshold_exceeded")

    def is_suppressed(self, email: str) -> bool:
        return email.lower() in self._hard_suppressed

    def __len__(self) -> int:
        return len(self._hard_suppressed)


# ==========================================================================
# 13. BOUNCE / COMPLAINT WEBHOOK HANDLER
# ==========================================================================

def handle_bounce_event(
    email: str,
    bounce_type: str,  # "permanent" or "soft"
    suppression_list: SuppressionList,
) -> None:
    """
    Process a bounce event received from any provider webhook.

    Hard bounces (permanent): suppress immediately.
    Soft bounces (transient): count toward auto-suppression threshold.

    IMPORTANT: Never send to a suppressed address.
    Each hard bounce hurts your sender reputation with ISPs.
    """
    if bounce_type == "permanent":
        suppression_list.add_hard_suppress(email, "hard_bounce")
    else:
        suppression_list.record_soft_bounce(email)


def handle_complaint_event(
    email: str,
    suppression_list: SuppressionList,
) -> None:
    """
    Process a spam-complaint (feedback-loop) event.

    All major providers surface these via webhooks.
    Suppress the address immediately to protect reputation.
    """
    suppression_list.add_hard_suppress(email, "spam_complaint")


# ==========================================================================
# 14. SUPPRESSION-AWARE SEND WRAPPER
# ==========================================================================

async def send_with_suppression_check(
    payload: EmailPayload,
    provider: EmailProvider,
    suppression_list: SuppressionList,
) -> Optional[Dict[str, Any]]:
    """
    Check the suppression list before delegating to the provider.

    Returns None (silently skips) if the address is suppressed,
    or the provider result dict on success.
    """
    if suppression_list.is_suppressed(payload.to):
        log.info("Skipping suppressed address: %s", payload.to)
        return None
    return await provider.send(payload)


# ==========================================================================
# 15. MULTI-PROVIDER FAILOVER
# ==========================================================================

class AllProvidersFailedError(Exception):
    """Raised when every provider in the failover chain has failed."""


async def send_with_failover(
    payload: EmailPayload,
    providers: List[EmailProvider],
    suppression_list: Optional[SuppressionList] = None,
) -> Dict[str, Any]:
    """
    Try each provider in order, falling back on transient failures.

    Non-retryable ProviderErrors bubble up immediately (no point
    trying the same payload on another provider if the payload
    itself is invalid).

    DMARC note: if providers are configured in your DNS, ensure
    all providers are covered by your SPF record and DKIM setup.
    """
    if suppression_list and suppression_list.is_suppressed(payload.to):
        log.info("Skipping suppressed address in failover: %s", payload.to)
        return {"provider": "suppressed", "message_id": "", "status": 0}

    last_error: Optional[Exception] = None
    for provider in providers:
        try:
            result = await provider.send(payload)
            log.info("Sent via %s to %s", provider.name, payload.to)
            return result
        except RetryableError as exc:
            log.warning("%s failed (retryable): %s", provider.name, exc)
            last_error = exc
            continue
        except ProviderError:
            # Non-retryable — re-raise immediately.
            raise

    raise AllProvidersFailedError(
        f"All {len(providers)} providers failed. Last error: {last_error}"
    )


# ==========================================================================
# 16. BACKGROUND QUEUE PATTERN (Celery)
# ==========================================================================

# pip install celery[redis]

CELERY_TASK_SKELETON = '''
"""
Background email task — paste into tasks.py in a Celery app.

Key principles:
    1. Never send email in the HTTP request path.
       Offload to a queue so the API response is fast.
    2. Retry on transient failures with exponential back-off.
    3. Apply rate_limit to stay within provider quotas.
    4. Log each attempt for observability.
"""
from celery import Celery, Task

celery = Celery("tasks", broker="redis://localhost:6379/0")


@celery.task(
    bind=True,
    autoretry_for=(RetryableError,),
    retry_kwargs={"max_retries": 5, "countdown": 30},
    rate_limit="100/s",          # provider quota guard
)
def send_email_task(
    self: Task,
    to: str,
    subject: str,
    html_body: str,
    text_body: str = "",
) -> None:
    """Celery task that calls the chosen provider."""
    import asyncio
    payload = EmailPayload(
        to=to, subject=subject,
        html_body=html_body, text_body=text_body,
    )
    provider = PostmarkProvider(server_token="...")
    asyncio.run(provider.send(payload))


# In your FastAPI endpoint:
#
# @app.post("/signup")
# async def signup(req: SignupRequest):
#     user = await create_user(req)
#     send_email_task.delay(
#         to=user.email,
#         subject="Welcome to our service",
#         html_body=render_jinja2_string(WELCOME_TMPL, {"name": user.name}),
#     )
#     return user
'''


# ==========================================================================
# 17. PROVIDER COST COMPARISON (reference data)
# ==========================================================================

PROVIDER_COST_TABLE = [
    {
        "provider": "AWS SES",
        "usd_per_1k": 0.10,
        "free_tier": "62K/month (if from EC2)",
        "strength": "Cheapest at scale, native AWS integration",
        "weakness": "Sandbox by default, complex initial setup",
    },
    {
        "provider": "SendGrid",
        "usd_per_1k": 0.50,          # Essentials plan ~$19.95 / 40K
        "free_tier": "100/day",
        "strength": "Mature platform, marketing + transactional",
        "weakness": "Pricier than SES at volume",
    },
    {
        "provider": "Mailgun",
        "usd_per_1k": 0.70,
        "free_tier": "5K for 3 months",
        "strength": "Developer-friendly, EU and US infrastructure",
        "weakness": "Less feature-rich than SendGrid",
    },
    {
        "provider": "Postmark",
        "usd_per_1k": 1.50,          # $15 / 10K
        "free_tier": "100/month",
        "strength": "Best deliverability, strict transactional focus",
        "weakness": "Expensive per unit, no marketing streams",
    },
    {
        "provider": "Resend",
        "usd_per_1k": 0.40,          # $20 / 50K
        "free_tier": "3K/month",
        "strength": "Modern API, React Email integration",
        "weakness": "Newer player, smaller ecosystem",
    },
]


def print_cost_comparison(monthly_volume: int = 100_000) -> None:
    """Print a cost estimate table for a given monthly email volume."""
    print(f"\nCost estimate for {monthly_volume:,} emails/month")
    print("-" * 60)
    print(f"{'Provider':<12} {'USD/1K':>8}  {'Monthly Cost':>14}  Strength")
    print("-" * 60)
    for row in PROVIDER_COST_TABLE:
        monthly_cost = row["usd_per_1k"] * monthly_volume / 1000
        print(
            f"{row['provider']:<12} "
            f"${row['usd_per_1k']:>7.2f}  "
            f"${monthly_cost:>13,.2f}  "
            f"{row['strength']}"
        )
    print()


# ==========================================================================
# 18. INTERNATIONALIZATION HELPERS
# ==========================================================================

def encode_subject_rfc2047(subject: str, charset: str = "utf-8") -> str:
    """
    Encode a non-ASCII email subject line using RFC 2047.

    Required for Japanese, Arabic, Hebrew, and other non-ASCII subjects.
    Modern libraries (aiosmtplib, sendgrid SDK) handle this automatically,
    but this function is useful when constructing raw messages manually.
    """
    return Header(subject, charset).encode()


# ==========================================================================
# 19. TESTING HELPERS
# ==========================================================================

class MockEmailProvider(EmailProvider):
    """
    In-memory provider for unit tests.

    Captures sent payloads; never makes network calls.
    Raises ProviderError if the recipient starts with "fail@".
    """

    name = "mock"

    def __init__(self) -> None:
        self.sent: List[EmailPayload] = []
        self.call_count: int = 0

    async def send(self, payload: EmailPayload) -> Dict[str, Any]:
        self.call_count += 1
        if payload.to.startswith("fail@"):
            raise ProviderError(f"Mock reject: {payload.to}")
        self.sent.append(payload)
        return {
            "provider": self.name,
            "message_id": f"mock-{self.call_count}",
            "status": 200,
        }


MAILHOG_DOCKER_CMD = (
    "docker run -d -p 1025:1025 -p 1080:8025 mailhog/mailhog\n"
    "# SMTP trap on localhost:1025\n"
    "# Web UI:   http://localhost:8025\n"
    "# Use aiosmtplib.send(..., hostname='localhost', port=1025)"
)

MAILTRAP_NOTE = (
    "Mailtrap (https://mailtrap.io) provides a hosted SMTP sandbox.\n"
    "Configure your provider SMTP to point to Mailtrap in development.\n"
    "All outbound email is captured — no real delivery occurs."
)


# ==========================================================================
# 20. COMPLIANCE REFERENCE
# ==========================================================================

COMPLIANCE_NOTES = {
    "CAN-SPAM (US)": [
        "Accurate 'From', 'To', and routing information.",
        "Honest subject lines — no deceptive headers.",
        "Clearly identified as an advertisement if commercial.",
        "Physical postal address in the email footer.",
        "Clear opt-out / unsubscribe mechanism in every email.",
        "Honor unsubscribe requests within 10 business days.",
    ],
    "GDPR (EU)": [
        "Lawful basis for processing (consent, contract, legitimate interest).",
        "Explicit opt-in for marketing; pre-ticked boxes are invalid.",
        "Easy, single-click unsubscribe.",
        "Data retention limits — do not store email data indefinitely.",
        "Right to erasure — delete address and preferences on request.",
    ],
    "CASL (Canada)": [
        "Express consent required before sending commercial messages.",
        "Stricter than CAN-SPAM — implied consent is time-limited (2 years).",
        "Mandatory identification of sender and contact information.",
        "Functional unsubscribe mechanism.",
    ],
}


# ==========================================================================
# 21. DRY-RUN DEMO (no external infrastructure required)
# ==========================================================================

async def _demo() -> None:
    """
    Demonstrate the key patterns using the MockEmailProvider.
    No API keys, network access, or installed SDKs are needed.
    """
    print("=" * 60)
    print("Transactional Email Providers — Dry-Run Demo")
    print("=" * 60)

    # --- Suppression list ------------------------------------------------
    suppression = SuppressionList()
    suppression.add_hard_suppress("blocked@example.com", "manual")
    assert suppression.is_suppressed("blocked@example.com")
    assert not suppression.is_suppressed("good@example.com")
    print("\n[1] Suppression list: OK")

    # --- Soft-bounce auto-suppression ------------------------------------
    soft_addr = "soft@example.com"
    for _ in range(SuppressionList.SOFT_BOUNCE_THRESHOLD):
        suppression.record_soft_bounce(soft_addr)
    assert suppression.is_suppressed(soft_addr)
    print(f"[2] Soft-bounce auto-suppression after "
          f"{SuppressionList.SOFT_BOUNCE_THRESHOLD} bounces: OK")

    # --- Webhook signature verification (SendGrid) -----------------------
    secret = "webhook_secret_example"
    timestamp = str(int(time.time()))
    raw = b'[{"event":"delivered","email":"user@x.com"}]'
    sig = hmac.new(
        secret.encode(),
        (timestamp + raw.decode()).encode(),
        hashlib.sha256,
    ).hexdigest()
    assert verify_sendgrid_webhook(raw, sig, timestamp, secret)
    print("[3] SendGrid webhook HMAC verification: OK")

    # --- RFC 2047 subject encoding ---------------------------------------
    encoded = encode_subject_rfc2047("こんにちは")
    assert encoded.startswith("=?utf-8?")
    print(f"[4] RFC 2047 subject encoding: {encoded}")

    # --- Jinja2 inline template ------------------------------------------
    tmpl = "Hello {{ name }}, click <a href='{{ link }}'>here</a>."
    try:
        html = render_jinja2_string(tmpl, {"name": "Alice", "link": "https://example.com"})
        assert "Alice" in html
        print(f"[5] Jinja2 inline template render: OK  →  {html[:60]}…")
    except ProviderError as _exc:
        print(f"[5] Jinja2 inline template render: SKIPPED ({_exc})")

    # --- Mock provider send ----------------------------------------------
    mock = MockEmailProvider()
    payload = EmailPayload(
        to="user@example.com",
        subject="Welcome!",
        html_body="<b>Welcome, Alice!</b>",
        text_body="Welcome, Alice!",
    )
    result = await mock.send(payload)
    assert result["status"] == 200
    assert len(mock.sent) == 1
    print(f"[6] MockEmailProvider.send: {result}")

    # --- Suppression-aware send ------------------------------------------
    suppressed_payload = EmailPayload(
        to="blocked@example.com",
        subject="You should not receive this",
        html_body="...",
        text_body="...",
    )
    skipped = await send_with_suppression_check(suppressed_payload, mock, suppression)
    assert skipped is None
    assert mock.call_count == 1    # not called again
    print("[7] Suppression-aware send correctly skipped blocked address: OK")

    # --- Multi-provider failover -----------------------------------------
    failing_mock = MockEmailProvider()
    # Force all sends to raise RetryableError
    original_send = failing_mock.send

    async def always_fail(p: EmailPayload) -> Dict[str, Any]:
        raise RetryableError("simulated failure")

    failing_mock.send = always_fail  # type: ignore[method-assign]
    good_mock = MockEmailProvider()

    result2 = await send_with_failover(
        payload,
        providers=[failing_mock, good_mock],
    )
    assert result2["provider"] == "mock"
    print(f"[8] Failover from failing provider to good provider: {result2}")

    # --- SES SNS bounce notification parsing ----------------------------
    sns_body = json.dumps({
        "Message": json.dumps({
            "notificationType": "Bounce",
            "bounce": {
                "bounceType": "Permanent",
                "bouncedRecipients": [{"emailAddress": "bad@example.com"}],
            }
        })
    })
    event = parse_ses_sns_notification(sns_body)
    assert event is not None
    assert event["type"] == "bounce"
    assert event["bounce_type"] == "permanent"
    handle_bounce_event("bad@example.com", "permanent", suppression)
    assert suppression.is_suppressed("bad@example.com")
    print(f"[9] SES bounce webhook parsed and suppressed: {event}")

    # --- SendGrid webhook event parsing ----------------------------------
    sg_body = json.dumps([
        {"event": "delivered", "email": "ok@example.com", "timestamp": 1700000000},
        {"event": "bounce", "email": "gone@example.com", "type": "blocked"},
    ])
    events = parse_sendgrid_webhook_events(sg_body)
    assert len(events) == 2
    print(f"[10] SendGrid webhook events parsed: {[e['event'] for e in events]}")

    # --- Cost comparison -------------------------------------------------
    print_cost_comparison(monthly_volume=50_000)

    print("=" * 60)
    print("All demo assertions passed.")
    print("=" * 60)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    asyncio.run(_demo())
