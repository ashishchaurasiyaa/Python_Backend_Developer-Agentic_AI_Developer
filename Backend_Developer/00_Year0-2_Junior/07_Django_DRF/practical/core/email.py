"""
Django Email Utilities
═══════════════════════════════════════════════════════════════
INTERVIEW: Email backends kab use karte hain?
  console  → development (print to terminal, no real SMTP)
  locmem   → testing (mail.outbox list mein store)
  smtp     → production (real SMTP server)
  filebased → staging (save emails as .eml files for review)

INTERVIEW: send_mail vs EmailMultiAlternatives vs EmailMessage?
  send_mail: simplest — plain text only
  EmailMultiAlternatives: plain text + HTML (most common)
  EmailMessage: full control — attachments, custom headers, BCC, CC

INTERVIEW: Async email kyu?
  SMTP call = 200-500ms blocking → request slow ho jaata hai
  Celery task → non-blocking, retryable on failure
"""

from django.core.mail import EmailMultiAlternatives, send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import logging

log = logging.getLogger(__name__)


# ─── Simple Email ─────────────────────────────────────────

def send_simple_email(subject: str, body: str, to: str | list[str]):
    """Simplest email — plain text."""
    if isinstance(to, str):
        to = [to]
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=None,  # uses DEFAULT_FROM_EMAIL from settings
            recipient_list=to,
            fail_silently=False,
        )
        log.info("Email sent: %s → %s", subject, to)
    except Exception:
        log.exception("Failed to send email: %s", subject)
        raise


# ─── HTML Email ───────────────────────────────────────────

def send_html_email(subject: str, template_name: str, context: dict,
                    to: str | list[str], bcc: list[str] | None = None):
    """
    Send HTML email with plain-text fallback.

    Template: templates/emails/<template_name>.html
    """
    if isinstance(to, str):
        to = [to]

    html_body  = render_to_string(f"emails/{template_name}.html", context)
    plain_body = strip_tags(html_body)

    email = EmailMultiAlternatives(
        subject=subject,
        body=plain_body,              # plain text fallback
        from_email=None,              # DEFAULT_FROM_EMAIL
        to=to,
        bcc=bcc or [],
    )
    email.attach_alternative(html_body, "text/html")

    try:
        email.send()
        log.info("HTML email sent: %s → %s", subject, to)
    except Exception:
        log.exception("Failed to send HTML email: %s", subject)
        raise


# ─── Common Email Functions ───────────────────────────────

def send_welcome_email(user):
    """Send welcome email after registration."""
    send_html_email(
        subject="Welcome to MyApp! 🎉",
        template_name="welcome",
        context={"user": user, "login_url": "https://myapp.com/login"},
        to=user.email,
    )


def send_password_reset_email(user, reset_url: str):
    """Password reset link email."""
    send_html_email(
        subject="Reset your password",
        template_name="password_reset",
        context={"user": user, "reset_url": reset_url},
        to=user.email,
    )


def send_email_verification(user, verification_url: str):
    """Email verification link."""
    send_html_email(
        subject="Verify your email address",
        template_name="email_verification",
        context={"user": user, "verification_url": verification_url},
        to=user.email,
    )


def send_order_confirmation(user, order):
    """Order confirmation with receipt."""
    send_html_email(
        subject=f"Order Confirmed #{order.id}",
        template_name="order_confirmation",
        context={"user": user, "order": order},
        to=user.email,
    )


# ─── Async Email via Celery ───────────────────────────────

def send_email_async(subject: str, body: str, to: str | list[str]):
    """
    Send email asynchronously via Celery.
    Non-blocking — request returns immediately.

    INTERVIEW: transaction.on_commit kyu use karte hain?
      Celery task dispatch hote waqt agar DB transaction rollback ho,
      toh task already queue mein hai — inconsistency.
      on_commit → only enqueue after transaction commits.
    """
    from django.db import transaction

    if isinstance(to, str):
        to = [to]

    def _send():
        try:
            from celery import current_app
            current_app.send_task(
                "core.tasks.send_email_task",
                kwargs={"subject": subject, "body": body, "to": to},
            )
        except Exception:
            # Celery not available — fallback to synchronous
            log.warning("Celery unavailable — sending email synchronously")
            send_simple_email(subject, body, to)

    transaction.on_commit(_send)


# ─── Test: Email in Tests ─────────────────────────────────
"""
INTERVIEW: Test mein email kaise verify karte hain?

# settings/test.py
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# test
from django.core import mail

def test_welcome_email_sent(user):
    send_welcome_email(user)
    assert len(mail.outbox) == 1
    assert mail.outbox[0].subject == "Welcome to MyApp! 🎉"
    assert user.email in mail.outbox[0].to
"""
