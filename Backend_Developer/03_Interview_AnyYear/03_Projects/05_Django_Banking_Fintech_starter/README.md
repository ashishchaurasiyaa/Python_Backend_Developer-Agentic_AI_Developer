# Banking / Fintech Backend — Starter

Spec: [../05_Django_Banking_Fintech.md](../05_Django_Banking_Fintech.md)

## What to build

Digital banking backend with double-entry bookkeeping, ACID-guaranteed money transfers (`SELECT FOR UPDATE`), Stripe-style idempotency, KYC state machine, daily ledger reconciliation, monthly PDF statements.  Target: 5M users, 10M transactions/day, 1K TPS sustained.

## How to run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Infrastructure
docker run -d --name pg -e POSTGRES_PASSWORD=dev -p 5432:5432 postgres:16
docker run -d --name redis -p 6379:6379 redis:7
docker run -d --name rabbit -p 5672:5672 rabbitmq:3

# Django project setup (run once)
django-admin startproject banking .
python manage.py startapp accounts
python manage.py startapp ledger
python manage.py startapp kyc
python manage.py startapp compliance

python manage.py migrate
python manage.py runserver
```

## Milestones (from spec)

- **Week 1** — Django project, User + Account models, JWT auth, simple deposit/withdraw
- **Week 2** — Double-entry ledger (Transaction + LedgerEntry), TransferService with `SELECT FOR UPDATE`, idempotency middleware, reconciliation script
- **Week 3** — KYC submission, FSMField state machine (django-fsm), OTP for large transfers
- **Week 4** — Monthly statement PDF (WeasyPrint + S3), audit log, GDPR export
- **Week 5** — UPI/NEFT stubs, SMS/email notifications, webhook handling
- **Week 6** — Multi-AZ Postgres, WAF, load test 5K TPS

## Key patterns to implement

1. Double-entry: every transfer creates 2 `LedgerEntry` rows (debit source, credit dest); sum always = 0.
2. `SELECT FOR UPDATE` on Balance row prevents concurrent transfers over-spending.
3. `Balance.objects.filter(...).update(current_balance=F("current_balance") - amount)` — atomic, never load-then-save.
4. Idempotency middleware: check `idem:{key}` in Redis before processing; cache response 24h.
5. Reversal = new reverse Transaction (never UPDATE original rows) — preserves audit trail.
