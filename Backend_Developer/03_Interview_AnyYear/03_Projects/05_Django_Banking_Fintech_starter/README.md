# Banking / Fintech Backend

Spec: [../05_Django_Banking_Fintech.md](../05_Django_Banking_Fintech.md)

## Status — verified, not assumed

The original file here was a TODO scaffold (a bare `manage.py`, no Django
project, no models). It's now a working core implementation of the
correctness-critical part of the spec — built, containerized, and checked
live against a real Postgres, not just "should work."

| Area | What's real | Verified how |
|---|---|---|
| Double-entry ledger | `Transaction` + `LedgerEntry`, every money movement writes exactly 2 balanced rows ([`ledger/models.py`](ledger/models.py), [`ledger/services.py`](ledger/services.py)) | `pytest tests/test_transfers.py::test_double_entry_sums_to_zero` — asserts the sum is exactly 0 |
| ACID transfers | `SELECT FOR UPDATE` + `django.db.transaction.atomic()` around every balance change | `pytest tests/test_concurrency.py` — 10 real threads, 10 separate DB connections, fire concurrent transfers at the same account simultaneously; **exactly 5 succeed, 5 correctly reject with insufficient funds, final balance is never negative** |
| Idempotency | DB unique constraint on `idempotency_key` (correctness) + Redis cache fast-path (latency) ([`ledger/services.py`](ledger/services.py), [`ledger/views.py`](ledger/views.py)) | `pytest tests/test_transfers.py::test_retry_with_same_idempotency_key_does_not_double_move_money` and the API-level equivalent — same key retried, same transaction returned, money moved once |
| Reversal | New reverse transaction; original's ledger rows are never touched | `pytest tests/test_transfers.py::test_reversal_creates_new_transaction_and_preserves_original` — diffs the original's `LedgerEntry` rows before/after, byte-identical |
| Reconciliation | `manage.py reconcile_balances` — ledger-derived balance vs. cached `Balance.current_balance`, exits 1 on mismatch | `pytest tests/test_reconciliation.py` (clean run + a deliberately tampered balance is caught); also run manually against the live stack — see below |
| Immutable audit log | Postgres `BEFORE UPDATE OR DELETE` trigger on `ledger_auditlog`, not just an app-level convention ([`ledger/migrations/0002_audit_log_append_only.py`](ledger/migrations/0002_audit_log_append_only.py)) | `docker compose exec postgres psql ... -c "UPDATE ledger_auditlog SET action='tampered' WHERE id=1"` → genuinely rejected with `ERROR: audit_log is append-only: UPDATE is not permitted` |
| Auth | JWT (`djangorestframework-simplejwt`), 15 min access / 7 day rotating refresh per spec section 16 | `pytest tests/test_auth_accounts.py` |
| Docker | Multi-stage build, non-root user, healthcheck, docker-compose with dependent healthchecks | `docker compose up -d --build` → all 3 services `healthy`; every endpoint above curled against the live stack before writing tests |

**19/19 tests passing.** Run them yourself:

```bash
docker compose up -d
.venv/bin/pip install -r requirements.txt
POSTGRES_HOST=localhost POSTGRES_PORT=5434 REDIS_URL=redis://localhost:6381/0 \
  .venv/bin/python -m pytest tests/ -v
```

## What's deliberately deferred (stretch goals, not gaps)

The full spec targets a 5M-user, 10M-txn/day neobank with KYC, cards, and
regulator-grade reporting. This starter builds the part that demonstrates
the architecture decisions — the correctness core — not the full product
surface. Left out on purpose:

- **KYC workflow (OCR, face match, `django-fsm` state machine)** — spec
  section 11. No identity verification exists; every signed-up user can
  open accounts and move money immediately. A real deployment would gate
  account activation behind KYC approval.
- **Celery + RabbitMQ async pipeline** — spec section 18. Reconciliation
  runs as a plain management command (same logic as the spec's
  `reconcile_balances` Celery task, different scheduler — see
  [`ledger/management/commands/reconcile_balances.py`](ledger/management/commands/reconcile_balances.py)).
  No Kafka event stream, no async notification workers.
- **Monthly PDF statements (WeasyPrint + S3)** — spec section 13. Not
  implemented; `GET /accounts/{id}/statements` from the spec's API list
  doesn't exist here.
- **Cards, UPI/NEFT/IMPS integration** — spec sections 14, real payment
  rails need a partner bank/PSP relationship this starter obviously
  doesn't have. `TransferService` is written so a real gateway integration
  would plug in at the same seam deposits/withdrawals already use.
- **OTP for large transfers, 2FA** — spec section 16 flags transfers over
  ₹10K for OTP confirmation. The per-transaction ₹1L cap is enforced
  (`MAX_TRANSACTION_AMOUNT`); the OTP step itself is not.
- **Column-level PII encryption, SAR/velocity fraud detection** — spec
  sections 12, 16. No Aadhaar/PAN fields exist at all (KYC is deferred),
  so there's nothing to encrypt yet; no suspicious-activity detection job.
- **Multi-AZ Postgres, WAF, 5K TPS load test** — spec section 6/23,
  infrastructure-scale concerns out of reach of a local Docker Compose
  stack.

## Architecture notes worth knowing for an interview

- **Deposits and withdrawals are transfers, not a separate code path.**
  `TransferService.deposit()`/`.withdraw()` both call `.transfer()` against
  a system "cash" account (`get_or_create_system_account()` in
  [`ledger/services.py`](ledger/services.py)) — the same double-entry trick
  spec section 4's second example describes. Result: there is exactly one
  code path in the entire project that can move money, which is exactly
  the property you want to be able to say out loud in an interview.
- **Lock ordering to avoid deadlock.** The spec's own reference
  `TransferService.transfer()` (section 7) locks `source` then `dest` in
  request order. Two concurrent transfers moving money in opposite
  directions between the same pair of accounts would then deadlock —
  thread A holds source's lock waiting for dest, thread B holds dest's
  lock waiting for source. This implementation locks both accounts in a
  fixed order (ascending `id`) regardless of which side is source/dest —
  see the comment in `TransferService.transfer()`.
- **Idempotency is DB-guaranteed, not cache-guaranteed.** The Redis
  `idem:{key}` cache in [`ledger/views.py`](ledger/views.py) is a latency
  optimization only — a cache eviction can never cause a double-charge,
  because `TransferService.transfer()` itself checks
  `Transaction.objects.filter(idempotency_key=...)` against the DB's
  unique constraint before doing anything else. This is a stronger
  guarantee than the spec's `IdempotencyMiddleware` (section 8), which is
  cache-only and would double-charge on a cache miss for a key that
  actually already succeeded.
- **Failed money-movement responses aren't cached.** Only a
  successful (2xx) result is written to the idempotency cache — a retried
  request after a transient failure gets a fresh attempt, not a permanently
  pinned error, mirroring Stripe's actual behavior.
- **Audit log append-only-ness is enforced by Postgres, not Django.** A
  `BEFORE UPDATE OR DELETE` trigger (migration `0002`) rejects mutation at
  the database level — a Python-only guard (e.g. overriding `save()`)
  wouldn't stop someone with a raw DB shell from editing history, which
  defeats the entire point of an audit trail.

## How to run

```bash
docker compose up -d --build
open http://localhost:8003/admin       # Django admin (createsuperuser first)
```

Ports are offset from this repo's other two dockerized projects
(`08_FastAPI_OpenAI_RAG_Backend_starter` on 8001, `03_FastAPI_URL_Shortener_Scale_starter`
on 8002) so all three stacks can run at once: app→**8003**, Postgres→**5434**, Redis→**6381**.

```bash
# quick manual check
curl -s -X POST localhost:8003/auth/signup -H 'content-type: application/json' \
  -d '{"username":"alice","password":"CorrectHorse9!"}'
TOKEN=$(curl -s -X POST localhost:8003/auth/login -H 'content-type: application/json' \
  -d '{"username":"alice","password":"CorrectHorse9!"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access'])")
curl -s -X POST localhost:8003/accounts -H "Authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' -d '{"account_type":"savings"}'
curl -s -X POST localhost:8003/transactions/deposit -H "Authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' -H 'Idempotency-Key: demo-1' -d '{"account":1,"amount":"500.00"}'

# reconciliation
docker compose exec app python manage.py reconcile_balances
```

## Milestones (from spec) — what's done

- **Week 1** — Django project + DRF, User + Account models, JWT auth, deposit/withdraw → **done**
- **Week 2** — Double-entry ledger, `TransferService` with `SELECT FOR UPDATE`, idempotency, reconciliation script → **done**
- **Week 3** — KYC submission + state machine, OTP verification → **deferred** (see above)
- **Week 4** — Statements, Excel export, ops dashboard → **deferred**
- **Week 5** — UPI/webhooks/notifications → **deferred**
- **Week 6** — Multi-AZ, WAF, 5K TPS load test → **deferred** (infra-scale, out of reach locally)
