# 01 — SMTP & Email Fundamentals

> The protocol that delivers ~300 billion emails per day. Old, weird, and still critical.

---

## What SMTP Is

**Simple Mail Transfer Protocol** — sends email between servers.

```
Sender → MTA (your server) → MTA (recipient server) → Mailbox
                       SMTP                  SMTP
```

Email retrieval is a different protocol: POP3 or IMAP.

---

## SMTP Conversation

Plain text protocol:

```
$ telnet smtp.example.com 25
220 smtp.example.com ESMTP ready
> EHLO myclient.com
250-Hello myclient.com
250-AUTH PLAIN LOGIN
250 STARTTLS
> STARTTLS
220 Go ahead
[TLS handshake]
> EHLO myclient.com
> AUTH PLAIN <base64-credentials>
235 OK
> MAIL FROM:<sender@example.com>
250 OK
> RCPT TO:<recipient@example.com>
250 OK
> DATA
354 Send message
> Subject: Hello
>
> Body content here
> .
250 OK; queued
> QUIT
221 Bye
```

Each step has a 3-digit response code.

---

## Ports

| Port | Use | Notes |
|---|---|---|
| 25 | Server-to-server SMTP | Often blocked by ISPs for clients |
| 465 | SMTPS (implicit TLS) | Submission, deprecated but used |
| 587 | Submission (STARTTLS) | Modern client-to-server |
| 2525 | Alternative submission | Some providers (when 25/587 blocked) |

**App sending email → use 587 with STARTTLS.**

---

## Sending Email in Python

### Standard library `smtplib`

```python
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

msg = MIMEMultipart("alternative")
msg["Subject"] = "Hello"
msg["From"] = "sender@example.com"
msg["To"] = "recipient@example.com"
msg.attach(MIMEText("Plain text", "plain"))
msg.attach(MIMEText("<b>HTML</b>", "html"))

with smtplib.SMTP("smtp.gmail.com", 587) as server:
    server.starttls()
    server.login("user", "app-password")
    server.send_message(msg)
```

### Async via `aiosmtplib`
```python
import aiosmtplib

await aiosmtplib.send(
    msg,
    hostname="smtp.gmail.com",
    port=587,
    username="user",
    password="pwd",
    start_tls=True
)
```

---

## Email Anatomy

### Headers

```
From: Sender <sender@example.com>
To: alice@example.com, bob@example.com
Cc: charlie@example.com
Bcc: hidden@example.com   (NOT sent to recipients in actual email)
Subject: Hello
Date: Mon, 1 Jan 2024 00:00:00 +0000
Message-ID: <unique-id@example.com>
In-Reply-To: <prev-id@example.com>
References: <thread-root-id@example.com>
Reply-To: noreply@example.com
List-Unsubscribe: <mailto:unsubscribe@example.com>
Content-Type: multipart/alternative; boundary="..."
MIME-Version: 1.0
```

### Body
Plain text OR HTML OR both (multipart/alternative).

Attachments: multipart/mixed with base64-encoded parts.

---

## MIME (Multipurpose Internet Mail Extensions)

Allows non-ASCII content + attachments via encoding.

```
Content-Type: multipart/mixed; boundary="boundary1"

--boundary1
Content-Type: multipart/alternative; boundary="boundary2"

--boundary2
Content-Type: text/plain; charset=utf-8
Hello!

--boundary2
Content-Type: text/html; charset=utf-8
<b>Hello!</b>

--boundary2--

--boundary1
Content-Type: image/png
Content-Disposition: attachment; filename="image.png"
Content-Transfer-Encoding: base64

iVBORw0KGgoAAAANSUhEU...
--boundary1--
```

Python's `email` package handles this complexity.

---

## Deliverability — Why Your Email Goes to Spam

Major signals for spam filters:

### 1. SPF (Sender Policy Framework)
DNS TXT record listing servers allowed to send for your domain.

```
example.com.  TXT  "v=spf1 include:_spf.google.com include:sendgrid.net ~all"
```

Receiving server checks: "Did this email come from an allowed IP?"

### 2. DKIM (DomainKeys Identified Mail)
Cryptographic signature in email header.

```
DKIM-Signature: v=1; a=rsa-sha256; d=example.com; s=mail; ...
```

Public key in DNS:
```
mail._domainkey.example.com  TXT  "v=DKIM1; k=rsa; p=MII..."
```

Receiver verifies signature → confirms message authenticity.

### 3. DMARC (Domain-based Message Authentication, Reporting & Conformance)
Policy for handling SPF/DKIM failures.

```
_dmarc.example.com  TXT  "v=DMARC1; p=reject; rua=mailto:dmarc@example.com"
```

`p=reject` → reject failing email.
`p=quarantine` → put in spam.
`p=none` → log only.

### 4. Reverse DNS
The sending IP must have a PTR record pointing to a domain.

```
$ host 1.2.3.4
4.3.2.1.in-addr.arpa  PTR  mail.example.com
```

### 5. IP reputation
Senders with history of spam complaints get blacklisted.

### 6. Content
- HTML/text mismatch.
- Lots of caps, exclamation marks, "FREE!!!".
- All-image emails.
- Misspelled "viagra"-like words.
- Suspicious URLs.

---

## Hard vs Soft Bounce

- **Soft bounce**: temporary (mailbox full, server down). Retry later.
- **Hard bounce**: permanent (invalid address, domain doesn't exist). Don't retry.

Track bounce rate. > 5% hard bounce → ISPs will block you.

---

## Email Lifecycle (Producer Side)

```
1. Your app composes message.
2. Submit to outgoing SMTP server (587).
3. SMTP relays to recipient's MX servers.
4. Recipient server queues, scans for spam.
5. Delivered to mailbox / quarantined / bounced.
6. Bounce or feedback loop notifications return.
```

Modern apps don't deal with steps 3-6 directly — use a transactional email provider (file 02).

---

## Headers Worth Setting

```
From: Acme <noreply@acme.com>      → friendly name
Reply-To: support@acme.com           → so replies go to a real inbox
Message-ID: <{uuid}@acme.com>        → for threading + bounce tracking
List-Unsubscribe: <https://...>      → required for marketing emails
List-Unsubscribe-Post: List-Unsubscribe=One-Click
X-Mailer: AcmeApp                    → identify your service
```

---

## MX Records

```
$ dig MX gmail.com
gmail.com.  3600  IN  MX  5  gmail-smtp-in.l.google.com.
gmail.com.  3600  IN  MX  10 alt1.gmail-smtp-in.l.google.com.
...
```

Lower priority = preferred. SMTP servers try in priority order, fail over.

---

## Common Errors

| Code | Meaning |
|---|---|
| 220 | Service ready |
| 221 | Closing connection |
| 235 | Auth success |
| 250 | OK |
| 354 | Start mail input |
| 421 | Service not available (try later) |
| 450 | Mailbox unavailable, try later |
| 451 | Local error, try later |
| 452 | Insufficient storage |
| 500 | Syntax error |
| 535 | Auth failed |
| 550 | Mailbox unavailable (hard fail) |
| 551 | User not local |
| 552 | Storage exceeded |
| 553 | Mailbox name invalid |
| 554 | Transaction failed |

---

## Self-Hosted vs Provider

### Self-hosted (Postfix, Sendmail, Exim)
- Cheap if you have ops.
- Full control.
- Hard to maintain deliverability.
- IP reputation building takes months.
- Generally a bad idea for transactional email in 2026.

### Cloud SMTP (Postfix on cloud VM)
Same as self-hosted, less ops.

### Transactional email provider (SendGrid, SES, Mailgun, Postmark)
- Best deliverability.
- Webhooks for bounces/opens/clicks.
- API + SMTP relay.
- Few cents per thousand emails.

**Recommendation:** Use a provider. (File 02.)

---

## Receiving Email

If you need to receive (inbound):
- **Postfix + Dovecot** for self-hosted.
- **AWS SES inbound**: SES processes incoming and forwards to S3/SNS/Lambda.
- **Mailgun routes**: routes inbound to your webhook.

Use cases:
- Bounce processing.
- Reply-by-email (e.g., comment on ticket).
- Email parsing apps.

---

## Email-as-API Pattern

App publishes "user.signed_up" event → notification service composes email → sends via provider.

```python
@app.post("/signup")
async def signup(req: SignupRequest):
    user = await create_user(req)
    await kafka.send("notifications", {
        "type": "welcome_email",
        "user_id": user.id,
        "to": user.email
    })
    return {"user": user}
```

Notification service consumes:
```python
async for msg in consumer:
    if msg.type == "welcome_email":
        await send_welcome(msg.user_id, msg.to)
```

Decoupling ensures API isn't blocked by slow SMTP.

---

## Anti-Spam Best Practices

### Sender
1. Verify SPF, DKIM, DMARC.
2. Send only to opted-in recipients.
3. Provide easy unsubscribe.
4. Avoid spam words/excessive formatting.
5. Monitor bounce + complaint rates.
6. Warm up new sending IPs gradually.

### Content
1. Plain text + HTML versions.
2. Real From address (not no-reply@unknown.com).
3. Personalized (recipient's name, etc.).
4. Tracking pixels optional (some receivers block).
5. Don't include large images inline.

### List hygiene
1. Use double opt-in.
2. Remove hard bounces immediately.
3. Re-engagement campaigns for inactive subscribers.
4. Suppression lists.

---

## Common Mistakes

### 1. Hardcoded SMTP credentials in code
Use env vars or secrets manager.

### 2. Synchronous SMTP send blocking API
Each send = 100-2000ms. Use background queue.

### 3. No retries
SMTP transient failures common. Retry with backoff.

### 4. Sending to known invalid addresses
Hard bounces hurt reputation.

### 5. Same template for transactional + marketing
Mixed types get mixed signals from receivers.

### 6. No unsubscribe link
Hurts deliverability + may be illegal (CAN-SPAM, GDPR).

---

## TL;DR

- SMTP = text-based protocol for sending email.
- Port 587 with STARTTLS for app→server.
- MIME for HTML + attachments.
- SPF + DKIM + DMARC mandatory for deliverability.
- Hard bounces hurt reputation more than soft.
- Use a transactional email provider in production.
- Send via background queue, not in request path.
- Track bounces, complaints, opens.
