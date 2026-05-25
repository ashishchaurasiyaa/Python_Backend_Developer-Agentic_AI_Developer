# Django Email — Templates, Async, Attachments

## Why It Matters

Email = critical for every app: verification, password reset, notifications, newsletters. Production:
- **Async via Celery** (don't block requests)
- **Templates** (HTML + text)
- **Attachments**
- **SMTP failures handling**
- **Bulk sending**
- **Email service providers** (SendGrid, AWS SES, Mailgun)

Senior interview: "Email failure handling, async sending, deliverability?"

---

## Core Concepts

### Settings

```python
# settings.py
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

# SMTP
EMAIL_HOST = 'smtp.sendgrid.net'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'apikey'
EMAIL_HOST_PASSWORD = os.environ['SENDGRID_API_KEY']

DEFAULT_FROM_EMAIL = 'noreply@example.com'
SERVER_EMAIL = 'errors@example.com'   # for error emails
EMAIL_SUBJECT_PREFIX = '[MyApp] '

EMAIL_TIMEOUT = 10   # seconds


# Dev — console backend
# EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Tests
# EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# Or file backend (writes to file instead of sending)
# EMAIL_BACKEND = 'django.core.mail.backends.filebased.EmailBackend'
# EMAIL_FILE_PATH = '/tmp/emails'
```

### Basic Send

```python
from django.core.mail import send_mail


send_mail(
    subject='Welcome',
    message='Plain text body',
    from_email='noreply@example.com',
    recipient_list=['user@example.com'],
    fail_silently=False,    # raise on error (recommended)
)
```

### Multipart (HTML + Text)

```python
from django.core.mail import EmailMultiAlternatives


msg = EmailMultiAlternatives(
    subject='Welcome to MyApp',
    body='Plain text version',          # fallback for non-HTML clients
    from_email='noreply@example.com',
    to=['user@example.com'],
    reply_to=['support@example.com'],
)
msg.attach_alternative('<h1>Welcome!</h1><p>...</p>', 'text/html')
msg.send()
```

### Template-Based

```python
# templates/emails/welcome.html
"""
{% extends 'emails/base.html' %}
{% block content %}
<h1>Welcome {{ name }}!</h1>
<p>Click here: <a href="{{ verify_url }}">Verify</a></p>
{% endblock %}
"""


# templates/emails/welcome.txt
"""
Welcome {{ name }}!

Click here to verify: {{ verify_url }}
"""


# Send
from django.template.loader import render_to_string


def send_welcome(user):
    context = {
        'name': user.first_name,
        'verify_url': f'https://app.example.com/verify?token={token}',
    }

    text = render_to_string('emails/welcome.txt', context)
    html = render_to_string('emails/welcome.html', context)

    msg = EmailMultiAlternatives(
        subject='Welcome!',
        body=text,
        from_email='noreply@example.com',
        to=[user.email],
    )
    msg.attach_alternative(html, 'text/html')
    msg.send()
```

### Attachments

```python
msg = EmailMultiAlternatives(...)

# From file
msg.attach_file('/path/to/invoice.pdf')

# From bytes
msg.attach('invoice.pdf', pdf_bytes, 'application/pdf')

# Inline image (for HTML emails)
import base64
with open('logo.png', 'rb') as f:
    img_data = base64.b64encode(f.read()).decode()
# Then in HTML: <img src="data:image/png;base64,{{ img_data }}">

# Or via Content-ID for compatibility
from email.mime.image import MIMEImage
with open('logo.png', 'rb') as f:
    img = MIMEImage(f.read())
img.add_header('Content-ID', '<logo>')
msg.attach(img)
# In HTML: <img src="cid:logo">
```

### Async via Celery

```python
# tasks.py
from celery import shared_task


@shared_task(autoretry_for=(Exception,), max_retries=5, retry_backoff=True)
def send_email_async(subject, body, to, html=None, attachments=None):
    msg = EmailMultiAlternatives(
        subject=subject,
        body=body,
        from_email='noreply@example.com',
        to=to,
    )
    if html:
        msg.attach_alternative(html, 'text/html')
    if attachments:
        for fname, content, mime in attachments:
            msg.attach(fname, content, mime)
    msg.send()


# Usage
send_email_async.delay(
    subject='Hi',
    body='Hello',
    to=['user@example.com'],
)
```

### Use `on_commit` to Avoid Sending Before Commit

```python
@transaction.atomic
def signup(email):
    user = User.objects.create(email=email)
    # If we send here directly, email could go before commit
    # If transaction rolls back, orphan email sent

    transaction.on_commit(
        lambda: send_welcome_email.delay(user.id)
    )
```

### Bulk Email (Mass Mail)

```python
from django.core.mail import send_mass_mail


messages = [
    ('Subject 1', 'Body 1', 'from@example.com', ['user1@example.com']),
    ('Subject 2', 'Body 2', 'from@example.com', ['user2@example.com']),
]
send_mass_mail(messages, fail_silently=False)
```

Reuses single SMTP connection — much faster than N individual `send_mail`.

### Connection Reuse

```python
from django.core.mail import get_connection


with get_connection() as connection:
    for user in users:
        msg = EmailMessage(
            subject='Newsletter',
            body=...,
            to=[user.email],
            connection=connection,
        )
        msg.send()
```

### Anymail (Multi-Provider)

```python
# pip install django-anymail[sendgrid]
INSTALLED_APPS += ['anymail']

ANYMAIL = {
    'SENDGRID_API_KEY': os.environ['SENDGRID_API_KEY'],
}

EMAIL_BACKEND = 'anymail.backends.sendgrid.EmailBackend'

# Provider-specific features:
msg.metadata = {'user_id': user.id}    # tracked in SendGrid
msg.tags = ['welcome', 'onboarding']
msg.track_clicks = True
msg.track_opens = True
```

### Webhook Handling (Bounces, Opens)

```python
# urls.py
urlpatterns += [path('anymail/', include('anymail.urls'))]


# settings.py
ANYMAIL = {
    'WEBHOOK_SECRET': os.environ['ANYMAIL_WEBHOOK_SECRET'],
}


# Connect signals
from anymail.signals import tracking


@receiver(tracking)
def email_event(sender, event, esp_name, **kwargs):
    if event.event_type == 'bounced':
        User.objects.filter(email=event.recipient).update(email_bounced=True)
```

### Email Validation

```python
from django.core.validators import EmailValidator


validator = EmailValidator()
try:
    validator(email)
except ValidationError:
    # Invalid format
    pass


# Stronger: DNS MX record check
import dns.resolver


def is_email_deliverable(email):
    domain = email.split('@')[1]
    try:
        dns.resolver.resolve(domain, 'MX')
        return True
    except Exception:
        return False
```

### Templated Email Service

```python
class EmailService:
    @staticmethod
    def send_template(template_name, context, to, subject=None):
        text = render_to_string(f'emails/{template_name}.txt', context)
        html = render_to_string(f'emails/{template_name}.html', context)

        # Subject can be in template
        if not subject:
            subject = render_to_string(f'emails/{template_name}.subject.txt', context).strip()

        msg = EmailMultiAlternatives(
            subject=subject,
            body=text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=to if isinstance(to, list) else [to],
        )
        msg.attach_alternative(html, 'text/html')

        from .tasks import dispatch_email
        transaction.on_commit(
            lambda: dispatch_email.delay(
                msg.subject, msg.body, msg.to, html=html
            )
        )


# Usage
EmailService.send_template(
    'welcome',
    {'user': user, 'verify_url': '...'},
    to=user.email,
)
```

---

## Common Pitfalls

### 1. Sync Email in Request

```python
def view(request):
    send_mail(...)   # blocks 1-5 seconds
```

User waits. Always async via Celery.

### 2. Hardcoded Email Templates

Mixing HTML + Python = unmaintainable. Use Django templates.

### 3. No Bounce Handling

Sending to bounced emails → ISP marks you spam → deliverability drops. Track bounces, suppress sending.

### 4. SMTP Credentials in Code

Never. Env vars + secrets manager.

### 5. Plain SMTP Without TLS

```python
EMAIL_USE_TLS = False   # plain — credentials in clear over network
```

Always TLS (port 587) or SSL (port 465).

### 6. Missing Text Alternative

HTML-only emails marked spam by some clients. Always provide plain text fallback.

### 7. No Retry on Transient Failure

```python
send_mail(..., fail_silently=False)   # raises → propagates
```

Wrap in Celery task with `autoretry_for`. SMTP servers fail temporarily; retry usually succeeds.

### 8. Sender Reputation Issues

- Send from your domain (not gmail.com)
- Set up SPF, DKIM, DMARC
- Use dedicated IP for high volume
- Warm up new IPs gradually
- Honor unsubscribes

---

## Interview Q&A

**Q1:** Production email sending architecture?
**A:** App → Celery task → SMTP/ESP (SendGrid/SES/Mailgun). Async dispatch via `on_commit` (after DB commit). Templates rendered server-side (HTML + text). Retry on transient errors. Track bounces + opens via webhooks. Suppression list for bounced emails.

**Q2:** Sync vs async email — choose karne ka logic?
**A:** Sync only for transactional logs / dev / when result must be confirmed (rare). Always async for user-facing flows. Reduces request latency, allows retry, decouples failure. Use Celery (or RQ) + queue.

**Q3:** Bounces handle kaise karte ho?
**A:** Webhook from ESP (SendGrid, Mailgun, AWS SES) → endpoint. Parse event. Mark user.email_bounced=True. Suppress future sends to that email. Cleanup: query bounced users, re-validate via DNS MX after some weeks.

**Q4:** HTML email rendering challenges?
**A:** Email clients have varied + dated CSS support (no flexbox, limited media queries). Use table-based layouts, inline styles. Test in Litmus/Email on Acid. Use existing templates (MJML, Foundation for Emails). Plain text fallback mandatory.

**Q5:** Bulk send performance?
**A:** `send_mass_mail` reuses SMTP connection. For huge volumes: ESP bulk APIs (SendGrid Bulk Send), Marketing Cloud platforms (Customer.io, Mailchimp). Don't loop send_mail() — slow + risk of being rate-limited / IP blocked.

**Q6:** Email template management?
**A:** Django templates for transactional. For marketing/A-B test: external service (Customer.io, Iterable). API-driven — pass user_id + event, template managed externally by marketing team. Reduces deploy friction.

**Q7:** SPF / DKIM / DMARC?
**A:** Email auth standards. SPF: which IPs can send for your domain. DKIM: cryptographic signature of email. DMARC: policy + reporting (reject/quarantine on auth fail). Set via DNS records. ESP usually walks you through.

**Q8:** Email testing strategy?
**A:** Dev: `console.EmailBackend` (print to console) or `filebased`. Tests: `locmem.EmailBackend` + assert against `mail.outbox`. Staging: real ESP with test inbox (mailtrap.io). Prod: gradual rollout, monitor bounce rates, spam complaints.

---

## Real-World Use Cases

### 1. Signup Welcome Flow

```python
@transaction.atomic
def register(email, password):
    user = User.objects.create_user(email=email, password=password)
    transaction.on_commit(lambda: send_welcome_email.delay(user.id))
    return user


@shared_task(autoretry_for=(Exception,), max_retries=5, retry_backoff=True)
def send_welcome_email(user_id):
    user = User.objects.get(pk=user_id)
    token = email_token_signer.sign(str(user.pk))
    verify_url = f'https://app.example.com/verify?token={token}'

    EmailService.send_template(
        'welcome',
        context={'name': user.first_name, 'verify_url': verify_url},
        to=user.email,
        subject='Welcome to MyApp',
    )
```

### 2. Password Reset

```python
@shared_task
def send_password_reset(user_id):
    user = User.objects.get(pk=user_id)
    token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    reset_url = f'https://app.example.com/reset/{uid}/{token}/'

    EmailService.send_template(
        'password_reset',
        context={'reset_url': reset_url, 'name': user.first_name},
        to=user.email,
    )
```

### 3. Daily Digest

```python
@shared_task
def send_daily_digest():
    users = User.objects.filter(daily_digest=True)
    for user in users.iterator():
        recent_articles = Article.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=1),
            category__in=user.subscribed_categories.all(),
        )[:10]
        if recent_articles:
            send_email_async.delay(
                subject='Your daily digest',
                template='daily_digest',
                context={'articles': list(recent_articles.values()), 'name': user.first_name},
                to=[user.email],
            )
```

---

## References

- [Django Email](https://docs.djangoproject.com/en/5.0/topics/email/)
- [django-anymail](https://anymail.dev/)
- [SendGrid Python SDK](https://github.com/sendgrid/sendgrid-python)
- [MJML](https://mjml.io/) — responsive email framework
- "Email Geeks" Slack community
