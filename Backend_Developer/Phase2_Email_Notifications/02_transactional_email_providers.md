# 02 — Transactional Email Providers

> SendGrid, AWS SES, Mailgun, Postmark, Resend. How to integrate, choose, and operate.

---

## Why Use a Provider

| Self-hosted SMTP | Provider |
|---|---|
| Manage IP reputation | Provider does |
| Bounce/complaint handling | Webhooks + auto-suppression |
| Deliverability | Hard | Excellent |
| Cost (low volume) | Cheap (own infra) | $0-50/month |
| Cost (high volume) | Cheaper at huge scale | $$ at scale |
| Setup time | Days-weeks | Minutes |
| Compliance (DMARC) | DIY | Automated |

For 99% of apps: use a provider.

---

## Provider Comparison

| Provider | Pricing | Strengths | Weaknesses |
|---|---|---|---|
| **AWS SES** | $0.10/1000 emails | Cheapest at scale, AWS integration | Setup complex, sandbox by default |
| **SendGrid (Twilio)** | $19.95/40K/month and up | Mature, marketing + transactional | Pricey, occasional reputation issues |
| **Mailgun** | $35/50K/month and up | Developer-friendly, EU/US infra | Less feature-rich |
| **Postmark** | $15/10K/month | Best deliverability, transactional-focused | Pricey per unit, no marketing |
| **Resend** | $20/50K/month | Modern API, React Email | Newer player |
| **Mailchimp** | $20+/month | Best for marketing | Less for pure transactional |
| **Sendinblue / Brevo** | Generous free tier | Email + SMS | Less popular in US |

**Pick:**
- Lowest cost, AWS shop → **SES**.
- Best transactional reliability → **Postmark**.
- Modern Python/JS-friendly → **Resend**.
- Marketing + transactional combined → **SendGrid** or **Mailchimp**.

---

## AWS SES (Simple Email Service)

### Setup
1. Verify your domain (add DNS records: SPF, DKIM).
2. Move out of sandbox (request increase from AWS).
3. Get SMTP creds OR use API.

### Send via SMTP
```python
import aiosmtplib
from email.message import EmailMessage

msg = EmailMessage()
msg["From"] = "noreply@yourdomain.com"
msg["To"] = "user@example.com"
msg["Subject"] = "Hello"
msg.set_content("Plain text body")
msg.add_alternative("<p>HTML body</p>", subtype="html")

await aiosmtplib.send(
    msg,
    hostname="email-smtp.us-east-1.amazonaws.com",
    port=587,
    username=SES_SMTP_USERNAME,
    password=SES_SMTP_PASSWORD,
    start_tls=True
)
```

### Send via API (boto3)
```python
import boto3

ses = boto3.client("sesv2", region_name="us-east-1")
ses.send_email(
    FromEmailAddress="noreply@yourdomain.com",
    Destination={"ToAddresses": ["user@example.com"]},
    Content={
        "Simple": {
            "Subject": {"Data": "Hello"},
            "Body": {
                "Text": {"Data": "Plain"},
                "Html": {"Data": "<b>HTML</b>"}
            }
        }
    }
)
```

### Bounce/Complaint webhook (SNS topic)
SES publishes events to SNS. Subscribe Lambda or HTTP webhook.

```json
{
  "notificationType": "Bounce",
  "bounce": {
    "bouncedRecipients": [{"emailAddress": "bad@example.com"}],
    "bounceType": "Permanent"
  }
}
```

Auto-suppress hard bounces in your DB.

### Pros
- Cheapest at scale.
- Native AWS integration.
- High volume capacity.

### Cons
- Sandbox limits initially.
- Less polished UX.
- Reputation requires warm-up.

---

## SendGrid

### Setup
```bash
pip install sendgrid
```

```python
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

message = Mail(
    from_email="noreply@yourdomain.com",
    to_emails="user@example.com",
    subject="Hello",
    plain_text_content="Plain",
    html_content="<b>HTML</b>"
)

sg = SendGridAPIClient(api_key="...")
response = sg.send(message)
print(response.status_code)
```

### Async with aiohttp
```python
import aiohttp

async def send_sendgrid(to, subject, html):
    async with aiohttp.ClientSession() as session:
        await session.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={
                "personalizations": [{"to": [{"email": to}]}],
                "from": {"email": "noreply@yourdomain.com"},
                "subject": subject,
                "content": [{"type": "text/html", "value": html}]
            }
        )
```

### Webhook events
SendGrid POSTs to your webhook URL with array of events:
```json
[
  {"event": "delivered", "email": "user@x.com", "timestamp": 1700000000},
  {"event": "open", "email": "user@x.com", "url": "..."},
  {"event": "bounce", "email": "bad@x.com", "type": "blocked"}
]
```

Validate signature:
```python
import hmac, hashlib

def verify(payload, signature, timestamp):
    secret = "your_webhook_secret"
    expected = hmac.new(secret.encode(), (timestamp + payload).encode(), "sha256").hexdigest()
    return hmac.compare_digest(expected, signature)
```

---

## Postmark

Best for purely transactional (sign-up, receipts, password reset).

```python
import requests

response = requests.post(
    "https://api.postmarkapp.com/email",
    headers={
        "Accept": "application/json",
        "X-Postmark-Server-Token": "..."
    },
    json={
        "From": "noreply@yourdomain.com",
        "To": "user@example.com",
        "Subject": "Hello",
        "HtmlBody": "<b>Hello</b>",
        "TextBody": "Hello",
        "MessageStream": "outbound"
    }
)
```

### Strengths
- Excellent deliverability.
- Separate "streams" for transactional vs broadcast.
- Detailed analytics.

---

## Resend

Modern, dev-focused (made by ex-React team).

```bash
pip install resend
```

```python
import resend

resend.api_key = "re_..."

resend.Emails.send({
    "from": "noreply@yourdomain.com",
    "to": "user@example.com",
    "subject": "Hello",
    "html": "<b>Hello!</b>",
})
```

### React Email integration
Compose emails as React components, render to HTML.

---

## Templates

Provider-side templates: define once, reuse with variables.

### SendGrid template
```python
message = Mail(
    from_email="noreply@yourdomain.com",
    to_emails="user@example.com"
)
message.template_id = "d-abc123"
message.dynamic_template_data = {
    "first_name": "Alice",
    "reset_link": "https://app.com/reset/xyz"
}
sg.send(message)
```

### Custom templates (Jinja2)
```python
from jinja2 import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader("templates"))
html = env.get_template("welcome.html").render(name="Alice", link=link)

await send_email(to=user.email, subject="Welcome", html=html)
```

### MJML for responsive HTML
Email HTML is stuck in the 90s. MJML compiles to email-safe HTML.

```mjml
<mjml>
  <mj-body>
    <mj-section>
      <mj-column>
        <mj-text>Hello {{ name }}</mj-text>
        <mj-button href="{{ link }}">Click here</mj-button>
      </mj-column>
    </mj-section>
  </mj-body>
</mjml>
```

```python
from mjml import mjml_to_html

mjml_str = open("welcome.mjml").read()
html = mjml_to_html(mjml_str).html
```

---

## Sending at Scale (Background Queue Pattern)

Don't send in request path. Use a queue.

### Celery example
```python
from celery import Celery

celery = Celery("tasks", broker="redis://...")

@celery.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 5, "countdown": 30}
)
def send_email_task(self, to, subject, html):
    response = sendgrid.send(...)
    if response.status_code >= 500:
        raise Retry()

# In API
@app.post("/signup")
async def signup(req):
    user = await create_user(req)
    send_email_task.delay(user.email, "Welcome", html_body)
    return user
```

### Throttling
Many providers have rate limits. Use Celery `rate_limit`:

```python
@celery.task(rate_limit="100/s")
def send_email_task(...): ...
```

---

## Bounce/Suppression Handling

```python
async def handle_bounce_webhook(event):
    if event["type"] == "bounce":
        if event["bounce_type"] == "permanent":
            await db.execute(
                "INSERT INTO suppressed_emails (email, reason) VALUES ($1, $2) "
                "ON CONFLICT (email) DO NOTHING",
                event["email"], "hard_bounce"
            )

async def send_email(to, ...):
    suppressed = await db.fetch_one(
        "SELECT 1 FROM suppressed_emails WHERE email = $1", to
    )
    if suppressed:
        return  # skip
    await provider.send(...)
```

Never send to suppressed addresses. Hurts reputation.

---

## Multi-Provider Failover

```python
PROVIDERS = [PostmarkProvider(), SendGridProvider(), SESProvider()]

async def send_email_with_failover(to, subject, html):
    for provider in PROVIDERS:
        try:
            return await provider.send(to, subject, html)
        except ProviderError as e:
            log.warn(f"{provider.name} failed: {e}")
            continue
    raise AllProvidersFailedError()
```

Useful for redundancy. Beware: emails from different providers have different SPF — DMARC needs all providers covered.

---

## Email Analytics

Track via webhooks:
- Sent (queued by provider).
- Delivered (recipient mail server accepted).
- Bounced (hard or soft).
- Opened (tracking pixel loaded).
- Clicked (link tracking URL).
- Marked as spam (feedback loop).
- Unsubscribed.

Aggregate per template + per audience → optimize.

---

## Cost Estimation

Example: 100K signup welcome emails/day.

- AWS SES: 100K × $0.0001 = $10/day = $300/month.
- SendGrid Essentials: $35/month for 50K/month → would need a $90 plan for 100K/day = 3M/month.
- Postmark: $50/month for 50K/month, $400/month for 300K/month → 3M/month = thousands.

SES dominates at high volume.

---

## Internationalization

```python
msg.set_content("こんにちは", charset="utf-8")
msg["Subject"] = Header("件名", "utf-8").encode()
```

Modern email libs handle UTF-8 automatically. Subject lines: use RFC 2047 encoding.

For RTL languages (Arabic, Hebrew), MJML supports `dir="rtl"`.

---

## Testing

### Inbucket / MailHog (local)
```bash
docker run -d -p 1025:1025 -p 1080:8025 mailhog/mailhog
```

```python
await aiosmtplib.send(msg, hostname="localhost", port=1025)
# Browse http://localhost:8025
```

### Mailtrap (cloud)
Same idea, hosted. Catches all email in sandbox.

### Provider sandbox
SES sandbox lets you send to verified addresses only.

---

## Compliance

### GDPR
- Lawful basis for sending (consent, contract).
- Easy unsubscribe.
- Data retention limits.
- Right to delete.

### CAN-SPAM (US)
- Accurate "From" + sender info.
- Unsubscribe link.
- Honor unsubscribe within 10 days.
- Physical address in footer.

### CASL (Canada)
Stricter than CAN-SPAM.

### India
DLT (Distributed Ledger Technology) registration required for transactional SMS, not email.

---

## TL;DR

- Use a provider (SES, Postmark, SendGrid, Resend) — don't self-host.
- SES = cheapest at scale.
- Postmark = best deliverability for transactional.
- Send via background queue, never inline.
- Handle bounces via webhooks → suppression list.
- Templates via Jinja or provider-managed.
- MJML for responsive HTML.
- Auto-respect suppressions, follow CAN-SPAM/GDPR.
