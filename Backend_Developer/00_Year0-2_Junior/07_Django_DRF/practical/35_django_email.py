"""
Django Email — Production Patterns
"""

from django.core.mail import (
    send_mail,
    send_mass_mail,
    EmailMessage,
    EmailMultiAlternatives,
    get_connection,
)
from django.template.loader import render_to_string
from django.conf import settings
from django.db import transaction


# ==========================================================================
# 1. SETTINGS (env-driven)
# ==========================================================================

"""
# settings.py

import os


if DEBUG:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
else:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = os.environ['EMAIL_HOST']
    EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
    EMAIL_USE_TLS = True
    EMAIL_HOST_USER = os.environ['EMAIL_HOST_USER']
    EMAIL_HOST_PASSWORD = os.environ['EMAIL_HOST_PASSWORD']
    EMAIL_TIMEOUT = 10

DEFAULT_FROM_EMAIL = 'MyApp <noreply@example.com>'
SERVER_EMAIL = 'errors@example.com'
EMAIL_SUBJECT_PREFIX = '[MyApp] '


# Anymail (multi-provider)
INSTALLED_APPS += ['anymail']

EMAIL_BACKEND = 'anymail.backends.sendgrid.EmailBackend'
# OR: 'anymail.backends.amazon_ses.EmailBackend'
# OR: 'anymail.backends.mailgun.EmailBackend'

ANYMAIL = {
    'SENDGRID_API_KEY': os.environ['SENDGRID_API_KEY'],
}
"""


# ==========================================================================
# 2. BASIC SEND
# ==========================================================================

def basic_send(to_email):
    send_mail(
        subject='Hello',
        message='Plain text body',
        from_email=None,    # uses DEFAULT_FROM_EMAIL
        recipient_list=[to_email],
        fail_silently=False,   # raise on errors
    )


# ==========================================================================
# 3. MULTIPART (HTML + Text)
# ==========================================================================

def send_multipart(to_email, name):
    """HTML + plain text fallback."""

    text_body = f'Hello {name},\n\nWelcome to MyApp.\n\nVisit https://app.example.com'
    html_body = f"""
    <html>
    <body>
        <h1>Welcome, {name}!</h1>
        <p>Visit <a href="https://app.example.com">our site</a></p>
    </body>
    </html>
    """

    msg = EmailMultiAlternatives(
        subject='Welcome',
        body=text_body,
        from_email='noreply@example.com',
        to=[to_email],
        reply_to=['support@example.com'],
        headers={'X-Custom-Header': 'value'},
    )
    msg.attach_alternative(html_body, 'text/html')
    msg.send()


# ==========================================================================
# 4. TEMPLATE-BASED EMAIL SERVICE
# ==========================================================================

class EmailService:
    """Production-grade template-based email sending."""

    @staticmethod
    def send(template_name, context, to, subject=None, from_email=None, attachments=None):
        """
        Render {template_name}.txt + {template_name}.html templates from
        templates/emails/. Optional {template_name}.subject.txt for subject.
        """
        if not isinstance(to, (list, tuple)):
            to = [to]

        text = render_to_string(f'emails/{template_name}.txt', context)

        try:
            html = render_to_string(f'emails/{template_name}.html', context)
        except Exception:
            html = None

        if not subject:
            try:
                subject = render_to_string(f'emails/{template_name}.subject.txt', context).strip()
            except Exception:
                subject = template_name.replace('_', ' ').title()

        msg = EmailMultiAlternatives(
            subject=subject,
            body=text,
            from_email=from_email or settings.DEFAULT_FROM_EMAIL,
            to=to,
        )

        if html:
            msg.attach_alternative(html, 'text/html')

        if attachments:
            for att in attachments:
                if isinstance(att, str):
                    msg.attach_file(att)
                else:
                    # (filename, content, mimetype)
                    msg.attach(*att)

        return msg.send(fail_silently=False)


# ==========================================================================
# 5. ASYNC VIA CELERY
# ==========================================================================

"""
# tasks.py

from celery import shared_task
import logging


log = logging.getLogger(__name__)


@shared_task(
    autoretry_for=(Exception,),
    max_retries=5,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    rate_limit='100/m',   # max 100 emails per minute
)
def send_email_async(
    template_name,
    context,
    to,
    subject=None,
    attachments=None,
):
    from blog.services import EmailService
    try:
        EmailService.send(
            template_name=template_name,
            context=context,
            to=to,
            subject=subject,
            attachments=attachments,
        )
    except Exception as e:
        log.error(f'Email send failed to {to}: {e}', exc_info=True)
        raise   # triggers retry
"""


# ==========================================================================
# 6. on_commit PATTERN (avoid orphan emails)
# ==========================================================================

"""
@transaction.atomic
def signup(email, password):
    user = User.objects.create_user(email=email, password=password)

    # Generate verification token
    from django.core.signing import TimestampSigner
    signer = TimestampSigner(salt='email-verify')
    token = signer.sign(str(user.pk))

    verify_url = f'https://app.example.com/verify?token={token}'

    # AFTER commit only
    transaction.on_commit(lambda: send_email_async.delay(
        template_name='welcome',
        context={
            'name': user.first_name,
            'verify_url': verify_url,
        },
        to=user.email,
    ))

    return user
"""


# ==========================================================================
# 7. ATTACHMENTS
# ==========================================================================

def send_with_attachments(to_email, name):
    msg = EmailMultiAlternatives(
        subject='Your invoice',
        body=f'Hi {name}, attached is your invoice.',
        from_email='billing@example.com',
        to=[to_email],
    )

    # From file
    # msg.attach_file('/path/to/invoice.pdf')

    # From bytes
    pdf_bytes = b'%PDF-1.4...'   # mock
    msg.attach('invoice.pdf', pdf_bytes, 'application/pdf')

    # Generated CSV
    import csv, io
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(['Item', 'Amount'])
    writer.writerow(['Service', 100])
    msg.attach('items.csv', buf.getvalue(), 'text/csv')

    msg.send()


# Inline image (HTML email)
def send_with_inline_image(to_email):
    from email.mime.image import MIMEImage

    msg = EmailMultiAlternatives(
        subject='With logo',
        body='Plain version',
        from_email='noreply@example.com',
        to=[to_email],
    )

    html = """
    <html>
    <body>
        <img src="cid:logo" alt="Logo">
        <p>Hello!</p>
    </body>
    </html>
    """
    msg.attach_alternative(html, 'text/html')

    # Inline image with CID
    with open('logo.png', 'rb') as f:
        img = MIMEImage(f.read())
    img.add_header('Content-ID', '<logo>')
    img.add_header('Content-Disposition', 'inline')
    msg.attach(img)

    msg.send()


# ==========================================================================
# 8. BULK SENDING
# ==========================================================================

def bulk_send_individual(users, subject_template, body_template, context_fn):
    """Send N personalized emails efficiently."""
    with get_connection() as conn:
        for user in users.iterator(chunk_size=100):
            context = context_fn(user)
            text = body_template.format(**context)

            msg = EmailMessage(
                subject=subject_template.format(**context),
                body=text,
                from_email='noreply@example.com',
                to=[user.email],
                connection=conn,    # reuse connection
            )
            try:
                msg.send()
            except Exception as e:
                # Log + continue
                print(f'Failed: {user.email}: {e}')


# Or send_mass_mail (no personalization)
def bulk_mass_mail():
    messages = (
        (f'Subject {i}', f'Body {i}', 'from@example.com', [f'user{i}@example.com'])
        for i in range(100)
    )
    send_mass_mail(tuple(messages), fail_silently=False)


# ==========================================================================
# 9. ANYMAIL (provider-specific features)
# ==========================================================================

def send_with_anymail(to_email, user_id):
    """Provider-specific tags, metadata, tracking."""
    msg = EmailMultiAlternatives(
        subject='Welcome',
        body='Plain text',
        to=[to_email],
    )

    # Anymail extensions (work with any provider)
    msg.metadata = {'user_id': str(user_id), 'campaign': 'welcome_v2'}
    msg.tags = ['onboarding', 'welcome']
    msg.track_clicks = True
    msg.track_opens = True
    msg.send_at = None    # immediate; or datetime for scheduled

    msg.send()


# ==========================================================================
# 10. WEBHOOK HANDLING (bounces, opens)
# ==========================================================================

"""
# urls.py
urlpatterns += [path('anymail/', include('anymail.urls'))]


# settings.py
ANYMAIL = {
    'SENDGRID_API_KEY': '...',
    'WEBHOOK_SECRET': 'random-secret-for-validation',
}


# signals.py
from django.dispatch import receiver
from anymail.signals import tracking


@receiver(tracking)
def handle_email_event(sender, event, esp_name, **kwargs):
    if event.event_type == 'bounced':
        # Hard bounce — mark email invalid
        User.objects.filter(email=event.recipient).update(
            email_status='bounced',
            email_bounced_at=event.timestamp,
        )

    elif event.event_type == 'complained':
        # User marked as spam
        User.objects.filter(email=event.recipient).update(
            email_status='complained',
            unsubscribed=True,
        )

    elif event.event_type == 'opened':
        # Track engagement (optional)
        EmailEvent.objects.create(
            user_email=event.recipient,
            event_type='opened',
            timestamp=event.timestamp,
        )
"""


# ==========================================================================
# 11. EMAIL TEMPLATE STRUCTURE
# ==========================================================================

"""
templates/
    emails/
        base.html                    # base layout with header/footer
        welcome.subject.txt          # "Welcome to MyApp"
        welcome.txt                  # plain text version
        welcome.html                 # HTML version (extends base.html)
        password_reset.subject.txt
        password_reset.txt
        password_reset.html
        order_confirmation.subject.txt
        order_confirmation.txt
        order_confirmation.html


# emails/base.html
'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial; max-width: 600px; }
        .header { background: #f0f0f0; padding: 20px; }
        .footer { font-size: 12px; color: #888; margin-top: 40px; }
    </style>
</head>
<body>
    <div class="header"><img src="cid:logo" alt="MyApp"></div>
    <div class="content">
        {% block content %}{% endblock %}
    </div>
    <div class="footer">
        © {{ year }} MyApp
        <br>
        <a href="{{ unsubscribe_url }}">Unsubscribe</a>
    </div>
</body>
</html>
'''
"""


# ==========================================================================
# 12. SUPPRESSION LIST (don't email bounced)
# ==========================================================================

class EmailSuppressionList:
    """In-memory or DB-backed list of emails to skip."""

    @staticmethod
    def is_suppressed(email):
        from users.models import User
        return User.objects.filter(
            email__iexact=email,
        ).exclude(
            email_status='active',
        ).exists()

    @staticmethod
    def suppress(email, reason):
        from users.models import User
        User.objects.filter(email__iexact=email).update(
            email_status=reason,
        )


def safe_send(to_email, *args, **kwargs):
    if EmailSuppressionList.is_suppressed(to_email):
        return False
    send_mail(recipient_list=[to_email], *args, **kwargs)
    return True


# ==========================================================================
# 13. TESTING
# ==========================================================================

"""
# settings/test.py
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'


# tests
from django.core import mail
from django.test import TestCase


class EmailTests(TestCase):
    def test_welcome_email_sent(self):
        mail.outbox.clear()
        signup('alice@example.com', 'password')

        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertIn('Welcome', email.subject)
        self.assertEqual(email.to, ['alice@example.com'])
        self.assertIn('verify', email.body)
        # HTML alternative
        self.assertEqual(len(email.alternatives), 1)
        html, mime = email.alternatives[0]
        self.assertEqual(mime, 'text/html')
        self.assertIn('Welcome', html)
"""


# ==========================================================================
# 14. EMAIL HEALTH METRICS
# ==========================================================================

EMAIL_METRICS_TO_TRACK = """
# Prometheus metrics:
- emails_sent_total (counter, labels: template, status=sent|failed|suppressed)
- email_send_duration_seconds (histogram)
- email_bounce_rate (gauge — should be < 2%)
- email_complaint_rate (gauge — should be < 0.1%)
- email_queue_depth (gauge)

# Alerts:
- bounce_rate > 5% (ISP may flag as spam)
- queue_depth > 10000 (Celery backlog)
- send_failures > 5% (provider issue)
- complaint_rate > 0.1% (template / list quality issue)
"""
