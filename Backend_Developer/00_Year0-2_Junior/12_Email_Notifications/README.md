# 📧 Email + Notifications

> **4 theory + 4 practical (1:1).** Notification system **HLD interview ka classic** hai —
> aur real product me sabse zyada "ye kaam nahi kar raha" wali complaint yahin se aati hai.

---

## 📚 Files

| # | Theory | Practical | Kya |
|---|---|---|---|
| 01 | [SMTP fundamentals](01_smtp_fundamentals.md) | [`01_...py`](practical/01_smtp_fundamentals.py) | SMTP protocol, MIME, attachments, **SPF/DKIM/DMARC** (spam folder ka asli reason) |
| 02 | [Transactional email providers](02_transactional_email_providers.md) | [`02_...py`](practical/02_transactional_email_providers.py) | SendGrid/SES/Postmark, webhooks (bounce/open), templates, deliverability |
| 03 | [Push notifications — FCM/APNS](03_push_notifications_fcm_apns.md) | [`03_...py`](practical/03_push_notifications_fcm_apns.py) | Device tokens, token rotation, silent push, payload limits |
| 04 | [Notification system design](04_notification_system_design.md) | [`04_...py`](practical/04_notification_system_design.py) | 🔴 Multi-channel fan-out, preferences, dedup, retry, rate limit |

---

## 🎯 Interview me kya poocha jata hai

- **"Email spam me kyun ja raha hai?"** → SPF/DKIM/DMARC align nahi hai ([01](01_smtp_fundamentals.md)). Yeh jawab bahut kam log de paate hain.
- **"Design a notification system"** → [04](04_notification_system_design.md) full HLD: channel abstraction, user preferences, template service, queue + workers, idempotency (ek hi notification do baar na jaye), retry with backoff, per-user rate limit.
- **"Email bhejte waqt request block hoga?"** → nahi, queue me daalo → [Celery](../../01_Year3-4_Mid/09_Celery/), outbox pattern se guarantee → [outbox](../../01_Year3-4_Mid/05_Microservices/04_outbox_event_sourcing.md)

**Related:** [Celery](../../01_Year3-4_Mid/09_Celery/) · [Microservices outbox](../../01_Year3-4_Mid/05_Microservices/) · [HLD_Problems](../../02_Year5%2B_Senior/01_System_Design/HLD_Problems/) · [WebSocket/SSE (realtime)](../../01_Year3-4_Mid/13_WebSocket_SSE/)
