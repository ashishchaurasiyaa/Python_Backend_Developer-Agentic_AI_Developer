"""
SMTP & Email Fundamentals — Production Patterns
================================================
Grounded in: Backend_Developer/00_Year0-2_Junior/12_Email_Notifications/01_smtp_fundamentals.md

Covers:
  1.  SMTP port reference and connection strategy
  2.  Plain-text email (smtplib, stdlib only)
  3.  Multipart alternative email (plain-text + HTML)
  4.  Email with file attachment (multipart/mixed + multipart/alternative)
  5.  Production-ready email headers (Message-ID, Reply-To, List-Unsubscribe, X-Mailer)
  6.  Async SMTP via aiosmtplib (illustrative — requires pip install aiosmtplib)
  7.  Retry helper with exponential back-off (handles soft bounces / transient 4xx)
  8.  SMTP response code reference
  9.  Deliverability checklist (SPF / DKIM / DMARC / bounce handling)
 10.  Email-as-API pattern (event-driven, non-blocking)
 11.  __main__ demo (builds and prints email objects; no live SMTP server required)

Installation hints
------------------
# Standard library only — no pip install needed for sections 1–7, 10, 11
# pip install aiosmtplib        ← section 6 async sender
# pip install structlog         ← structured logging used in retry helper
"""

from __future__ import annotations

import asyncio
import base64
import logging
import smtplib
import ssl
import time
import uuid
from dataclasses import dataclass, field
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from functools import wraps
from typing import Callable, Dict, List, Optional

log = logging.getLogger(__name__)


# ==========================================================================
# 1. SMTP PORT REFERENCE
# ==========================================================================
#
# Port 25  → server-to-server relay (blocked by most ISPs for end-clients)
# Port 465 → SMTPS — implicit TLS from the start (deprecated, still used)
# Port 587 → Submission — STARTTLS upgrade (recommended for apps)
# Port 2525 → Alternative submission (used when 25/587 are blocked)
#
# Rule of thumb: applications MUST use port 587 + STARTTLS.

SMTP_PORTS: Dict[int, str] = {
    25:   "Server-to-server relay (avoid in client code)",
    465:  "SMTPS — implicit TLS (deprecated but operational)",
    587:  "Submission — STARTTLS (use this for app → provider)",
    2525: "Alternative submission (fallback when 587 blocked)",
}

# STARTTLS (587): plain socket → EHLO → STARTTLS → TLS handshake → EHLO → AUTH
# SMTPS (465):   TLS socket from the first byte → EHLO → AUTH


# ==========================================================================
# 2. SMTP CONNECTION SETTINGS DATA CLASS
# ==========================================================================

@dataclass
class SMTPConfig:
    """All connection settings for an outgoing SMTP relay."""

    host: str
    port: int = 587
    username: str = ""
    password: str = ""          # Use env var / secrets manager — never hard-code
    use_starttls: bool = True   # True for port 587; set False for port 465
    use_ssl: bool = False       # True for port 465 (implicit TLS)
    timeout: int = 30           # Seconds; prevents indefinite hangs
    sender_name: str = "Acme App"
    sender_address: str = "noreply@example.com"

    @classmethod
    def from_env(cls) -> "SMTPConfig":
        """
        Production usage: read all credentials from environment variables.

            import os
            config = SMTPConfig(
                host=os.environ["SMTP_HOST"],
                port=int(os.environ.get("SMTP_PORT", "587")),
                username=os.environ["SMTP_USERNAME"],
                password=os.environ["SMTP_PASSWORD"],
            )
        """
        import os
        return cls(
            host=os.environ.get("SMTP_HOST", "smtp.gmail.com"),
            port=int(os.environ.get("SMTP_PORT", "587")),
            username=os.environ.get("SMTP_USERNAME", ""),
            password=os.environ.get("SMTP_PASSWORD", ""),
            sender_name=os.environ.get("SMTP_SENDER_NAME", "Acme App"),
            sender_address=os.environ.get("SMTP_SENDER_ADDRESS", "noreply@acme.com"),
        )


# ==========================================================================
# 3. PLAIN-TEXT EMAIL
# ==========================================================================

def build_plain_text_email(
    *,
    from_address: str,
    to_addresses: List[str],
    subject: str,
    body: str,
    cc_addresses: Optional[List[str]] = None,
    reply_to: Optional[str] = None,
) -> MIMEText:
    """
    Build a minimal plain-text MIMEText message.

    Returns a MIMEText object ready for smtplib.SMTP.send_message().
    """
    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = from_address
    msg["To"] = ", ".join(to_addresses)
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=False)  # RFC 2822 date in UTC
    msg["Message-ID"] = make_msgid(domain=from_address.split("@")[-1])

    if cc_addresses:
        msg["Cc"] = ", ".join(cc_addresses)
    if reply_to:
        msg["Reply-To"] = reply_to

    return msg


# ==========================================================================
# 4. MULTIPART/ALTERNATIVE EMAIL (PLAIN TEXT + HTML)
# ==========================================================================

def build_multipart_email(
    *,
    from_name: str,
    from_address: str,
    to_addresses: List[str],
    subject: str,
    plain_body: str,
    html_body: str,
    reply_to: Optional[str] = None,
    list_unsubscribe_url: Optional[str] = None,
    mailer_name: str = "AcmeApp",
) -> MIMEMultipart:
    """
    Build a multipart/alternative message with both plain-text and HTML parts.

    Email clients pick the richest part they can render (HTML if possible,
    plain-text as fallback).  Always include both — HTML-only emails are a
    deliverability red flag.

    MIME structure
    --------------
    multipart/alternative
        text/plain   (fallback)
        text/html    (preferred)
    """
    msg = MIMEMultipart("alternative")

    # --- Core headers ---
    msg["From"] = f"{from_name} <{from_address}>"
    msg["To"] = ", ".join(to_addresses)
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=False)
    msg["Message-ID"] = make_msgid(domain=from_address.split("@")[-1])
    msg["MIME-Version"] = "1.0"

    # --- Optional production headers ---
    if reply_to:
        msg["Reply-To"] = reply_to

    if list_unsubscribe_url:
        # Required by Gmail / Yahoo bulk-sender guidelines (Feb 2024)
        msg["List-Unsubscribe"] = f"<{list_unsubscribe_url}>"
        msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

    msg["X-Mailer"] = mailer_name

    # --- Body parts (plain-text BEFORE html — clients prefer the last match) ---
    msg.attach(MIMEText(plain_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body,  "html",  "utf-8"))

    return msg


# ==========================================================================
# 5. EMAIL WITH ATTACHMENT (MULTIPART/MIXED)
# ==========================================================================

@dataclass
class EmailAttachment:
    """Represents a single file attachment."""

    filename: str
    content: bytes
    mime_type: str = "application/octet-stream"


def build_email_with_attachments(
    *,
    from_name: str,
    from_address: str,
    to_addresses: List[str],
    subject: str,
    plain_body: str,
    html_body: str,
    attachments: Optional[List[EmailAttachment]] = None,
    reply_to: Optional[str] = None,
) -> MIMEMultipart:
    """
    Build a multipart/mixed email that contains body + file attachments.

    MIME structure
    --------------
    multipart/mixed
        multipart/alternative
            text/plain
            text/html
        application/octet-stream  (attachment 1)
        application/octet-stream  (attachment 2)
        ...
    """
    outer = MIMEMultipart("mixed")
    outer["From"] = f"{from_name} <{from_address}>"
    outer["To"] = ", ".join(to_addresses)
    outer["Subject"] = subject
    outer["Date"] = formatdate(localtime=False)
    outer["Message-ID"] = make_msgid(domain=from_address.split("@")[-1])

    if reply_to:
        outer["Reply-To"] = reply_to

    # Inner alternative (text + html)
    alternative = MIMEMultipart("alternative")
    alternative.attach(MIMEText(plain_body, "plain", "utf-8"))
    alternative.attach(MIMEText(html_body,  "html",  "utf-8"))
    outer.attach(alternative)

    # Attachments — base64-encoded, as per MIME spec
    for attachment in (attachments or []):
        main_type, sub_type = attachment.mime_type.split("/", 1)
        part = MIMEApplication(attachment.content, Name=attachment.filename)
        part["Content-Disposition"] = f'attachment; filename="{attachment.filename}"'
        part["Content-Transfer-Encoding"] = "base64"
        # Encode manually for illustration; MIMEApplication does this internally
        outer.attach(part)

    return outer


# ==========================================================================
# 6. SYNCHRONOUS SMTP SENDER
# ==========================================================================

class SMTPSender:
    """
    Synchronous SMTP sender.

    Usage
    -----
    config = SMTPConfig(host="smtp.gmail.com", username="user", password="app-pwd")
    sender = SMTPSender(config)
    sender.send(msg)

    Warning: each send() call occupies a thread for 100–2 000 ms.
    In a web API, always dispatch email to a background task / queue
    rather than calling send() inside the request handler.
    """

    def __init__(self, config: SMTPConfig) -> None:
        self._config = config

    # ------------------------------------------------------------------
    # Internal: build a connected & authenticated SMTP connection
    # ------------------------------------------------------------------

    def _connect(self) -> smtplib.SMTP:
        cfg = self._config

        if cfg.use_ssl:
            # Port 465 — TLS from the very first byte (SMTPS)
            context = ssl.create_default_context()
            server = smtplib.SMTP_SSL(cfg.host, cfg.port, timeout=cfg.timeout, context=context)
        else:
            # Port 587 — plain connection, then upgrade via STARTTLS
            server = smtplib.SMTP(cfg.host, cfg.port, timeout=cfg.timeout)

        server.ehlo()  # Identify ourselves to the server

        if cfg.use_starttls and not cfg.use_ssl:
            server.starttls(context=ssl.create_default_context())
            server.ehlo()  # Re-identify after TLS upgrade (required by spec)

        if cfg.username:
            server.login(cfg.username, cfg.password)

        return server

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send(self, msg: MIMEMultipart) -> None:
        """
        Open a connection, send one message, close.

        In production, reuse a persistent connection (or connection pool)
        for bulk sending rather than opening/closing per email.
        """
        with self._connect() as server:
            server.send_message(msg)
            log.info("Email sent to %s", msg["To"])

    def send_many(self, messages: List[MIMEMultipart]) -> Dict[str, Optional[Exception]]:
        """
        Send multiple messages over a single SMTP connection.

        Returns a dict mapping each Message-ID to None (success) or the exception raised.
        """
        results: Dict[str, Optional[Exception]] = {}

        with self._connect() as server:
            for msg in messages:
                msg_id = msg.get("Message-ID", "unknown")
                try:
                    server.send_message(msg)
                    results[msg_id] = None
                    log.info("Sent message %s", msg_id)
                except smtplib.SMTPException as exc:
                    results[msg_id] = exc
                    log.error("Failed to send %s: %s", msg_id, exc)

        return results


# ==========================================================================
# 7. ASYNC SMTP SENDER (requires: pip install aiosmtplib)
# ==========================================================================
#
# In async web frameworks (FastAPI, Starlette, aiohttp), the synchronous
# smtplib.SMTP blocks the event loop.  Use aiosmtplib instead.

async def send_async(
    msg: MIMEMultipart,
    config: SMTPConfig,
) -> None:
    """
    Send a pre-built MIME message asynchronously.

    Requires: pip install aiosmtplib

    Example
    -------
    await send_async(email_msg, config)
    """
    try:
        import aiosmtplib  # type: ignore[import]
    except ImportError:
        raise ImportError(
            "aiosmtplib is required for async sending.  "
            "Install it with: pip install aiosmtplib"
        )

    await aiosmtplib.send(
        msg,
        hostname=config.host,
        port=config.port,
        username=config.username,
        password=config.password,
        start_tls=config.use_starttls,
        use_tls=config.use_ssl,
    )
    log.info("Async email sent to %s", msg["To"])


# ==========================================================================
# 8. RETRY WITH EXPONENTIAL BACK-OFF (handles soft bounces / transient 4xx)
# ==========================================================================
#
# Transient SMTP errors (421, 450, 451, 452) should be retried after a delay.
# Permanent errors (5xx) must NOT be retried — they are hard failures.

#: SMTP response codes that indicate a temporary problem — retry is appropriate.
SOFT_BOUNCE_CODES = {421, 450, 451, 452}

#: SMTP response codes that indicate a permanent failure — do not retry.
HARD_BOUNCE_CODES = {500, 535, 550, 551, 552, 553, 554}


class MaxRetriesExceededError(Exception):
    """Raised when all retry attempts are exhausted for a transient SMTP error."""


def retry_on_soft_bounce(
    max_retries: int = 3,
    base_delay_seconds: float = 2.0,
    backoff_factor: float = 2.0,
) -> Callable:
    """
    Decorator that retries a function on transient SMTP errors.

    Retry schedule (default): 2 s → 4 s → 8 s, then raise.
    Permanent (5xx) errors are re-raised immediately without retrying.

    Parameters
    ----------
    max_retries:
        Maximum number of additional attempts after the first failure.
    base_delay_seconds:
        Initial wait before the first retry.
    backoff_factor:
        Multiplier applied to the delay after each retry.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exc: Optional[Exception] = None
            delay = base_delay_seconds

            for attempt in range(1, max_retries + 2):  # +1 for the initial try
                try:
                    return func(*args, **kwargs)
                except smtplib.SMTPResponseException as exc:
                    code = exc.smtp_code

                    if code in HARD_BOUNCE_CODES:
                        log.error(
                            "Hard bounce (code %d) — will not retry: %s",
                            code, exc.smtp_error,
                        )
                        raise  # Hard failures must surface immediately

                    if code in SOFT_BOUNCE_CODES:
                        last_exc = exc
                        if attempt <= max_retries:
                            log.warning(
                                "Soft bounce (code %d), retry %d/%d in %.1f s: %s",
                                code, attempt, max_retries, delay, exc.smtp_error,
                            )
                            time.sleep(delay)
                            delay *= backoff_factor
                        continue

                    raise  # Unknown code — do not suppress

                except smtplib.SMTPServerDisconnected as exc:
                    # Server closed the connection unexpectedly — treat as transient
                    last_exc = exc
                    if attempt <= max_retries:
                        log.warning(
                            "Server disconnected, retry %d/%d in %.1f s",
                            attempt, max_retries, delay,
                        )
                        time.sleep(delay)
                        delay *= backoff_factor
                    continue

            raise MaxRetriesExceededError(
                f"All {max_retries} retries exhausted."
            ) from last_exc

        return wrapper
    return decorator


# ==========================================================================
# 9. SMTP RESPONSE CODE REFERENCE
# ==========================================================================

SMTP_CODES: Dict[int, str] = {
    # 2xx — Success
    220: "Service ready",
    221: "Closing transmission channel",
    235: "Authentication successful",
    250: "Requested mail action OK",
    251: "User not local; will forward",
    354: "Start mail input; end with <CRLF>.<CRLF>",
    # 4xx — Transient failures (retry later)
    421: "Service not available (try later)",
    450: "Mailbox unavailable (try later)",
    451: "Local error in processing (try later)",
    452: "Insufficient system storage (try later)",
    # 5xx — Permanent failures (do not retry)
    500: "Syntax error / command unrecognised",
    501: "Syntax error in parameters",
    503: "Bad sequence of commands",
    535: "Authentication credentials invalid",
    550: "Mailbox unavailable — permanent",
    551: "User not local",
    552: "Exceeded storage allocation",
    553: "Mailbox name not allowed",
    554: "Transaction failed",
}


def describe_smtp_code(code: int) -> str:
    """Return a human-readable description for an SMTP response code."""
    return SMTP_CODES.get(code, f"Unknown SMTP code {code}")


# ==========================================================================
# 10. DELIVERABILITY REFERENCE (SPF / DKIM / DMARC / Bounce / Content)
# ==========================================================================

DELIVERABILITY_CHECKLIST = """
DNS Records
-----------
SPF   example.com.  TXT  "v=spf1 include:_spf.google.com include:sendgrid.net ~all"
      Authorises specific IPs / services to send on behalf of your domain.

DKIM  mail._domainkey.example.com  TXT  "v=DKIM1; k=rsa; p=MII..."
      Cryptographic signature proves the message was not tampered with in transit.

DMARC _dmarc.example.com  TXT  "v=DMARC1; p=reject; rua=mailto:dmarc@example.com"
      Policy for SPF/DKIM failures:
        p=none      — monitor only
        p=quarantine — move to spam
        p=reject    — discard the message

Reverse DNS  The sending IP must have a PTR record pointing back to your mail domain.

Bounce handling
---------------
Soft bounce (4xx): temporary — mailbox full, server busy.  Retry with back-off.
Hard bounce (5xx): permanent — invalid address.  Remove immediately; >5% hurts reputation.

Content guidelines
------------------
- Always include both plain-text and HTML parts.
- Avoid all-caps words, excessive punctuation, and spam trigger phrases.
- Include a real From address, not no-reply@unknown.com.
- Personalise where possible (recipient name, etc.).
- Provide a one-click List-Unsubscribe header (mandatory for bulk senders).
- Do not embed large images inline; use hosted URLs.

List hygiene
------------
- Use confirmed (double) opt-in.
- Remove hard bounces immediately after the first occurrence.
- Run re-engagement campaigns; suppress persistently inactive addresses.
- Warm up new sending IPs gradually (start at hundreds/day, ramp over weeks).

Sending architecture
--------------------
- Never call send() inside a synchronous request handler.
- Publish an event (Kafka, SQS, Redis Streams) and let a dedicated
  notification worker consume it and dispatch the email asynchronously.
- This decouples email latency from your API response time.
"""


# ==========================================================================
# 11. EMAIL-AS-API / EVENT-DRIVEN PATTERN
# ==========================================================================
#
# App emits an event; a dedicated notification service processes it and sends
# the email.  This keeps the primary API fast and email concerns isolated.

@dataclass
class EmailEvent:
    """Lightweight event payload published to a message queue."""

    event_type: str                   # e.g. "welcome_email", "password_reset"
    recipient_email: str
    recipient_name: str
    metadata: Dict[str, str] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))


def build_welcome_email(event: EmailEvent, config: SMTPConfig) -> MIMEMultipart:
    """
    Compose a welcome email from an EmailEvent.

    Called by the notification worker after consuming the event from the queue.
    """
    plain = (
        f"Hi {event.recipient_name},\n\n"
        "Welcome to Acme! Your account is now active.\n\n"
        "Visit https://acme.com/dashboard to get started.\n\n"
        "— The Acme Team"
    )
    html = f"""\
<!DOCTYPE html>
<html>
<body>
  <p>Hi <strong>{event.recipient_name}</strong>,</p>
  <p>Welcome to <strong>Acme</strong>! Your account is now active.</p>
  <p><a href="https://acme.com/dashboard">Open your dashboard →</a></p>
  <p>— The Acme Team</p>
  <p><small><a href="https://acme.com/unsubscribe?email={event.recipient_email}">
  Unsubscribe</a></small></p>
</body>
</html>"""

    return build_multipart_email(
        from_name=config.sender_name,
        from_address=config.sender_address,
        to_addresses=[event.recipient_email],
        subject="Welcome to Acme!",
        plain_body=plain,
        html_body=html,
        reply_to="support@acme.com",
        list_unsubscribe_url=(
            f"https://acme.com/unsubscribe?email={event.recipient_email}"
        ),
    )


async def notification_worker(queue: asyncio.Queue, config: SMTPConfig) -> None:
    """
    Async worker that drains an in-process event queue and sends emails.

    In production, replace asyncio.Queue with a real broker consumer
    (aiokafka, aio-pika for RabbitMQ, boto3 for SQS, etc.).
    """
    while True:
        event: EmailEvent = await queue.get()

        if event.event_type == "welcome_email":
            msg = build_welcome_email(event, config)
            try:
                await send_async(msg, config)
            except Exception as exc:
                log.error(
                    "Failed to send %s to %s: %s",
                    event.event_type, event.recipient_email, exc,
                )
            finally:
                queue.task_done()

        else:
            log.warning("Unhandled event type: %s", event.event_type)
            queue.task_done()


# ==========================================================================
# 12. __MAIN__ DEMO — builds and inspects emails without a live SMTP server
# ==========================================================================

if __name__ == "__main__":
    import textwrap

    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    print("\n" + "=" * 70)
    print("SMTP FUNDAMENTALS — BUILD & INSPECT DEMO")
    print("=" * 70)

    # -----------------------------------------------------------------
    # Demo config (credentials are placeholders — no live connection made)
    # -----------------------------------------------------------------
    demo_config = SMTPConfig(
        host="smtp.gmail.com",
        port=587,
        username="your-username@gmail.com",
        password="your-app-password",    # never hard-code in real code
        sender_name="Acme App",
        sender_address="noreply@acme.com",
    )

    print("\n[1] SMTP Ports")
    print("-" * 40)
    for port, description in SMTP_PORTS.items():
        print(f"  {port:>4} — {description}")

    # -----------------------------------------------------------------
    # Build a plain-text email and display its headers
    # -----------------------------------------------------------------
    print("\n[2] Plain-Text Email Headers")
    print("-" * 40)
    plain_msg = build_plain_text_email(
        from_address="noreply@acme.com",
        to_addresses=["alice@example.com"],
        subject="Your account is ready",
        body="Hi Alice,\n\nYour Acme account has been activated.\n\n— Acme Team",
        reply_to="support@acme.com",
    )
    for key in ("From", "To", "Subject", "Date", "Message-ID", "Reply-To"):
        print(f"  {key}: {plain_msg[key]}")

    # -----------------------------------------------------------------
    # Build a multipart email and display its MIME parts
    # -----------------------------------------------------------------
    print("\n[3] Multipart/Alternative Email (text + HTML)")
    print("-" * 40)
    multi_msg = build_multipart_email(
        from_name="Acme App",
        from_address="noreply@acme.com",
        to_addresses=["alice@example.com", "bob@example.com"],
        subject="Your monthly report",
        plain_body="Here is your report.\n\nhttps://acme.com/reports/42",
        html_body="<p>Here is your <a href='https://acme.com/reports/42'>report</a>.</p>",
        reply_to="support@acme.com",
        list_unsubscribe_url="https://acme.com/unsubscribe?uid=42",
        mailer_name="AcmeApp/1.0",
    )
    print(f"  Content-Type  : {multi_msg.get_content_type()}")
    print(f"  From          : {multi_msg['From']}")
    print(f"  To            : {multi_msg['To']}")
    print(f"  List-Unsubscribe: {multi_msg['List-Unsubscribe']}")
    print(f"  MIME parts    :")
    for part in multi_msg.walk():
        if part.get_content_type() != multi_msg.get_content_type():
            print(f"    - {part.get_content_type()}")

    # -----------------------------------------------------------------
    # Build an email with a synthetic attachment
    # -----------------------------------------------------------------
    print("\n[4] Email with Attachment")
    print("-" * 40)
    fake_pdf = b"%PDF-1.4 synthetic content for demo"
    attached_msg = build_email_with_attachments(
        from_name="Acme App",
        from_address="noreply@acme.com",
        to_addresses=["alice@example.com"],
        subject="Your invoice — Acme",
        plain_body="Please find your invoice attached.",
        html_body="<p>Please find your invoice <strong>attached</strong>.</p>",
        attachments=[
            EmailAttachment(
                filename="invoice_2026_06.pdf",
                content=fake_pdf,
                mime_type="application/pdf",
            )
        ],
        reply_to="billing@acme.com",
    )
    print(f"  Content-Type: {attached_msg.get_content_type()}")
    print("  MIME walk:")
    for part in attached_msg.walk():
        cd = part.get("Content-Disposition", "")
        label = f" ({cd})" if cd else ""
        print(f"    - {part.get_content_type()}{label}")

    # -----------------------------------------------------------------
    # SMTP response code lookup
    # -----------------------------------------------------------------
    print("\n[5] SMTP Response Code Reference (selected)")
    print("-" * 40)
    for code in (220, 250, 354, 421, 450, 535, 550, 554):
        print(f"  {code} — {describe_smtp_code(code)}")

    # -----------------------------------------------------------------
    # Deliverability checklist (truncated for readability)
    # -----------------------------------------------------------------
    print("\n[6] Deliverability Checklist (excerpt)")
    print("-" * 40)
    excerpt = DELIVERABILITY_CHECKLIST.strip().splitlines()[:16]
    for line in excerpt:
        print(f"  {line}")
    print("  ...")

    # -----------------------------------------------------------------
    # EmailEvent / event-driven pattern demo
    # -----------------------------------------------------------------
    print("\n[7] Event-Driven Email Pattern")
    print("-" * 40)
    event = EmailEvent(
        event_type="welcome_email",
        recipient_email="alice@example.com",
        recipient_name="Alice",
    )
    welcome_msg = build_welcome_email(event, demo_config)
    print(f"  Event ID     : {event.event_id}")
    print(f"  Event type   : {event.event_type}")
    print(f"  Email subject: {welcome_msg['Subject']}")
    print(f"  From         : {welcome_msg['From']}")
    print(f"  To           : {welcome_msg['To']}")

    # -----------------------------------------------------------------
    # Retry decorator demonstration (simulates transient failure)
    # -----------------------------------------------------------------
    print("\n[8] Retry Decorator (simulated soft bounce)")
    print("-" * 40)

    def _run_retry_demo() -> None:
        call_count_ref = [0]  # mutable container avoids nonlocal in module scope

        @retry_on_soft_bounce(max_retries=2, base_delay_seconds=0.01, backoff_factor=2.0)
        def _simulated_send() -> str:
            call_count_ref[0] += 1
            if call_count_ref[0] < 3:
                raise smtplib.SMTPResponseException(
                    code=451, msg=b"Local error - try later"
                )
            return "sent"

        result = _simulated_send()
        print(f"  Succeeded after {call_count_ref[0]} attempt(s): {result}")

    _run_retry_demo()

    print("\n" + "=" * 70)
    print("DEMO COMPLETE — all MIME objects built without a live SMTP server.")
    print("To send for real, instantiate SMTPConfig with real credentials and")
    print("call SMTPSender(config).send(msg), or await send_async(msg, config).")
    print("=" * 70 + "\n")
