# Design Payment Gateway (UPI-Scale — Razorpay / PhonePe / Juspay)

> **Scope note:** This is the HLD companion to the class-level design in
> [`../LLD_Problems/Payment_System.md`](../LLD_Problems/Payment_System.md).
> That file owns the Strategy-pattern gateway classes, the in-process state machine,
> the wallet/ledger objects, and retry-with-backoff code. This file owns everything
> the LLD cannot see: scale numbers, service boundaries, NPCI/bank hops, reconciliation,
> ledger sharding, and PSP routing. Interviewer "design Razorpay" bole to yahi file hai.

---

## 1. Requirements

### Functional
- Merchant creates a payment intent (order) → customer pays via UPI / card / netbanking / wallet.
- UPI collect + intent flows (VPA resolution, deep-link to PSP app, QR).
- Card flows with tokenization (RBI mandate — no raw PAN storage by merchants).
- Payment status query (merchant polls) + outbound webhooks (we push).
- Refunds — full and partial, T+N credit to customer.
- Settlement to merchants (T+1 for most, instant settlement as paid feature).
- Reconciliation against bank/NPCI files — every rupee accounted for.
- Route each transaction across multiple PSPs/acquiring banks (success-rate optimization).
- Dashboard: merchant sees payments, settlements, refunds, disputes.

### Non-Functional
- **Scale:** ~500M transactions/day at peak (India UPI scale — festival sales, cricket finals).
- **Correctness over availability for money movement** — never double-debit, never lose a credit.
- **Latency:** payment create < 100ms (P99); end-to-end UPI txn 3-10s (bank hops dominate, not us).
- **Durability:** zero data loss for ledger — RPO = 0 for financial records.
- **Availability:** 99.99% for the payment-create path; degraded mode must still accept payments.
- **Compliance:** PCI-DSS L1 for card data, RBI tokenization mandate, data-localization (India).
- **Auditability:** every state change replayable; regulators can ask for any txn's full history.

### Explicitly out of scope (say this in the interview)
- Issuing bank internals, NPCI switch internals (we integrate, we don't build).
- Lending/credit products, fraud-scoring ML model internals (mention hooks only).

---

## 2. Back-of-Envelope Estimation

| Metric | Calculation | Result |
|---|---|---|
| Transactions/day (peak day) | given | 500M |
| Average TPS | 500M / 86,400 | ~5,800 TPS |
| Peak TPS | 4-5× average (8-10 PM spike, sale events) | ~25,000-30,000 TPS |
| Status polls + page loads | 20 reads per txn | ~500K reads/sec peak |
| Payment record size | payment + attempts + events | ~2 KB |
| Payment storage/day | 500M × 2 KB | ~1 TB/day |
| Ledger entries/txn | ≥ 4 postings (debit/credit × legs) × 300 B | ~600 GB/day |
| Webhook deliveries/day | ~3 events per txn (created/success/settled) | 1.5B/day, ~17K/sec avg |
| Recon file size (T+1) | 500M rows × 200 B per bank file row | ~100 GB/day to crunch |
| Ledger retention | 7-10 years (RBI) | multi-PB cold storage |

**Key insight to state out loud:** reads (status checks) are ~20× writes, but the *hard*
problem is not read scale — it is write correctness at 25K TPS with money attached.
Cache the reads; never cache your way around the writes.

---

## 3. API Design

All money in **paise (integer)** — floats are a rejection-level mistake in a payments interview.

```
# ── Merchant-facing (authenticated via API key + HMAC signature) ──────────

POST /v1/orders                          # create payment intent
  Headers: Idempotency-Key: <merchant-generated UUID>
  Body:    { amount: 150000, currency: "INR", receipt: "bkg_881",
             notes: {...}, callback_url: "https://merchant.com/cb" }
  → 201 { order_id: "order_Nx7...", status: "created" }

POST /v1/orders/{order_id}/payments      # attempt payment on an order
  Headers: Idempotency-Key: <uuid>
  Body:    { method: "upi", vpa: "rahul@okhdfc", flow: "collect" }
  → 202 { payment_id: "pay_Kj2...", status: "pending", next: {...} }

GET  /v1/payments/{payment_id}           # status poll (heavily cached)
  → 200 { status: "success" | "pending" | "failed" | "reversed", ... }

POST /v1/refunds
  Headers: Idempotency-Key: <uuid>
  Body:    { payment_id: "pay_Kj2...", amount: 50000 }   # partial allowed
  → 202 { refund_id: "rfnd_...", status: "pending" }

GET  /v1/settlements?date=2026-08-07     # merchant settlement report

# ── Inbound callbacks (from PSP / bank / NPCI-side) ───────────────────────

POST /internal/callbacks/{psp_name}      # signature-verified, idempotent by psp_ref_id

# ── Outbound webhooks (us → merchant) ─────────────────────────────────────

POST {merchant.webhook_url}
  Headers: X-Signature: HMAC-SHA256(body, merchant_secret)
  Body:    { event: "payment.captured", payload: {...}, event_id: "evt_..." }
  # Merchant must respond 2xx; we retry with backoff for 24h otherwise.
```

Design decisions worth naming:
- `Idempotency-Key` is a **header, not body** — it belongs to the request, not the resource.
- Payment create returns **202 + pending**, never blocks on the bank. UPI takes seconds;
  HTTP connections don't wait for NPCI.
- Order vs Payment split: one order, many payment *attempts* (retry with another VPA/card
  creates a new payment under the same order). Mirrors `Payment`/`PaymentAttempt` in the LLD.

---

## 4. High-Level Architecture

```
   Merchant server / Checkout SDK / UPI apps
        │
   ┌────▼─────────┐
   │ Edge / WAF   │  TLS termination, bot filtering, per-merchant rate limits
   └────┬─────────┘
   ┌────▼─────────┐
   │ API Gateway  │  authN (API key + HMAC), idempotency middleware, routing
   └────┬─────────┘
        │
  ┌─────┼──────────────────────┬──────────────────────┐
  │     │                      │                      │
┌─▼─────▼────┐        ┌────────▼────────┐    ┌────────▼────────┐
│  Payment   │        │  Refund Service │    │ Status/Query    │
│  Service   │        └────────┬────────┘    │ Service (reads) │
│ (state     │                 │             │ + Redis cache   │
│  machine)  │                 │             └─────────────────┘
└─┬───────┬──┘                 │
  │       │ outbox             │
  │  ┌────▼─────────┐          │
  │  │    Kafka      │◄────────┘
  │  │ payment_events│──────────────┬───────────────┬─────────────┐
  │  └───────────────┘              │               │             │
  │                        ┌────────▼───────┐ ┌─────▼──────┐ ┌────▼─────┐
  │                        │ Webhook        │ │ Ledger     │ │ Analytics│
  │                        │ Dispatcher     │ │ Service    │ │ / Risk   │
  │                        │ (retries, DLQ) │ │ (postings) │ │ pipeline │
  │                        └────────────────┘ └─────┬──────┘ └──────────┘
  │                                                 │
┌─▼──────────────┐                          ┌───────▼────────┐
│ Router / PSP   │                          │ Recon &        │
│ Orchestrator   │                          │ Settlement Svc │◄── bank/NPCI
│ (circuit       │                          │ (T+1 batch)    │    MIS files
│  breakers)     │                          └────────────────┘
└─┬────┬────┬────┘
  │    │    │
┌─▼─┐┌─▼─┐┌─▼──────┐        ┌──────────────────────────────────┐
│PSP││PSP││Acquirer│        │ Storage:                         │
│ A ││ B ││ Bank   │─▶NPCI  │  Postgres/Vitess (payments,      │
└───┘└───┘└────────┘  switch│    sharded by merchant_id)       │
                            │  Ledger DB (append-only, sharded)│
                            │  Redis (idempotency, status cache)│
                            │  S3 (recon files, audit archive) │
                            │  Token Vault (PCI-DSS island)    │
                            └──────────────────────────────────┘
```

Every arrow that moves money is **async + durable** (outbox → Kafka), never fire-and-forget.

---

## 5. Deep Dive: Idempotency Keys End-to-End

One key is not enough. There are **three independent idempotency layers**, one per trust
boundary — interviewers probe exactly this.

```
Layer 1: Merchant → Us          Idempotency-Key header (merchant retries)
Layer 2: Us → PSP/Bank          our txn_ref forwarded (network timeout between us & bank)
Layer 3: PSP/Bank → Us          psp_ref_id / RRN dedup (bank retries callbacks)
```

### Layer 1 — API middleware (Redis fast path + DB source of truth)

```python
async def idempotency_middleware(request, handler):
    key = request.headers.get("Idempotency-Key")
    if not key:
        return error_400("Idempotency-Key required for POST")

    scoped = f"idem:{request.merchant_id}:{key}"      # scope per merchant!
    body_hash = sha256(request.raw_body)

    # Atomic claim: first request wins, concurrent duplicate gets 'IN_PROGRESS'
    claimed = await redis.set(scoped, f"LOCK:{body_hash}", nx=True, ex=86400)
    if not claimed:
        stored = await redis.get(scoped)
        if stored.startswith("LOCK:"):
            if stored != f"LOCK:{body_hash}":
                return error_422("same key, different payload")   # conflict
            return error_409("request in progress, retry later")  # concurrent dup
        return json_response(stored)                              # replay cached response

    response = await handler(request)
    if response.status < 500:                # never cache 5xx — allow retry
        await redis.set(scoped, response.body, ex=86400)
    return response
```

Redis alone is NOT enough (Redis can lose data). The **payments table carries
`UNIQUE(merchant_id, idempotency_key)`** — Redis is the fast path, the constraint is the law.

### Layer 2 — the nasty one: timeout between us and the bank

We call the PSP, the connection drops. Did the debit happen? **Unknown.**

Rules:
- Generate `txn_ref` (our ID) BEFORE the PSP call, persist it, send it in the request.
- On timeout → payment stays `PENDING`, never auto-fail (bank may still process it).
- A **status-inquiry job** polls the PSP's verify API using `txn_ref` until terminal state
  or expiry window (UPI: typically re-check for up to 90 seconds, then rely on callback/recon).
- Same `txn_ref` re-sent = PSP-side dedup. Never mint a new ref for a retry of the same attempt.

### Layer 3 — inbound callback dedup

`UNIQUE(psp_ref_id)` on the callbacks table. Duplicate callback → insert fails →
**return 200 anyway** (4xx makes the bank retry forever). Identical to the
`provider_event_id` constraint in the LLD file, just stated at the DB-schema level.

---

## 6. Deep Dive: Exactly-Once Payment State Machine

"Exactly-once" over a network is a lie; what we actually build is
**at-least-once delivery + idempotent, guarded state transitions** = effectively-once.

```
                 attempt        bank/NPCI says
   [order paid   created        yes/no
    intent]         │              │
  CREATED ────► PENDING ──────► SUCCESS ────► REVERSED
                    │    └─────► FAILED         (credit back: refund,
                    │                            auto-reversal, chargeback)
                    └──────────► EXPIRED
                                (no callback + inquiry says unknown after window)

  Terminal: FAILED, EXPIRED, REVERSED (SUCCESS is terminal for the debit leg;
  REVERSED is a *new money movement*, not an un-happening of SUCCESS)
```

### Transition = compare-and-swap in the DB, never read-then-write

```sql
-- The single most important query in the system.
-- Concurrency-safe: two racing callbacks → exactly one row updated.
UPDATE payments
SET    status = 'SUCCESS', psp_ref_id = :rrn, updated_at = now()
WHERE  payment_id = :id
AND    status = 'PENDING';          -- guard clause = the state machine

-- rowcount == 1 → we own this transition → emit event via outbox (same txn)
-- rowcount == 0 → someone else already transitioned → read current state, ack, do nothing
```

### Outbox pattern — state change and event are atomic

Transition and event-publish must not diverge (DB commits, Kafka publish fails → ledger
never hears about the success → money black hole). Solution is the transactional outbox:

```sql
BEGIN;
  UPDATE payments SET status='SUCCESS' WHERE payment_id=:id AND status='PENDING';
  INSERT INTO outbox (aggregate_id, event_type, payload)
       VALUES (:id, 'payment.success', :json);
COMMIT;
-- Relay process tails outbox → Kafka. At-least-once → consumers dedup by event_id.
```

Full mechanics in the mid-track lesson:
[`../../../01_Year3-4_Mid/05_Microservices/04_outbox_event_sourcing.md`](../../../01_Year3-4_Mid/05_Microservices/04_outbox_event_sourcing.md)
(runnable version: `01_Year3-4_Mid/05_Microservices/practical/04_outbox_idempotency.py`).

### Webhook retries (us → merchant)

- Kafka consumer per merchant-shard, delivery attempt → 2xx or retry.
- Backoff schedule: 1m, 5m, 30m, 2h, 6h, 24h → then DLQ + merchant dashboard alert.
- Ordering is NOT guaranteed across events — merchants must treat webhooks as
  *notifications* and call `GET /payments/{id}` as source of truth. Say this; it's the
  correct contract and interviewers reward it.
- Signature: HMAC over exact bytes, timestamp in signed payload (replay window ±5 min).

Multi-service money flows (payment + booking + inventory) ride on sagas, not 2PC —
see [`../HLD_Theory/59_Saga_Pattern.md`](../HLD_Theory/59_Saga_Pattern.md) and
[`../../02_Architecture_Patterns/Section_06_Event_Driven_Reactive/04_Saga_Outbox_Patterns.md`](../../02_Architecture_Patterns/Section_06_Event_Driven_Reactive/04_Saga_Outbox_Patterns.md).

---

## 7. Deep Dive: Double-Entry Ledger

The payments table answers "what did the customer do"; the **ledger** answers
"where is the money". They are different systems. LLD-level ledger objects (immutable
entries, balance snapshots) are in the LLD file — here is the schema + invariants at scale.

### Schema

```sql
CREATE TABLE ledger_accounts (
    account_id    BIGINT PRIMARY KEY,
    owner_type    TEXT NOT NULL,     -- 'merchant' | 'customer_escrow' | 'psp' | 'fees' | 'gst'
    owner_id      BIGINT NOT NULL,
    currency      CHAR(3) NOT NULL DEFAULT 'INR'
);

CREATE TABLE journal_entries (        -- one business event
    entry_id      BIGINT PRIMARY KEY, -- Snowflake: time-sortable
    txn_ref       TEXT NOT NULL,      -- payment_id / refund_id / settlement_id
    entry_type    TEXT NOT NULL,      -- 'capture' | 'refund' | 'settlement' | 'fee' ...
    created_at    TIMESTAMPTZ NOT NULL,
    UNIQUE (txn_ref, entry_type)      -- idempotent posting: replayed event = no-op
);

CREATE TABLE postings (               -- the actual debits/credits
    posting_id    BIGINT PRIMARY KEY,
    entry_id      BIGINT NOT NULL REFERENCES journal_entries,
    account_id    BIGINT NOT NULL,
    direction     CHAR(1) NOT NULL CHECK (direction IN ('D','C')),
    amount_paise  BIGINT NOT NULL CHECK (amount_paise > 0)
);
-- INVARIANT (enforced in service layer + verified by recon):
--   per entry_id: SUM(debits) == SUM(credits). Always. No exceptions.
-- Postings are APPEND-ONLY. No UPDATE, no DELETE, ever. Mistakes are fixed
-- by a reversing entry, never by editing history.
```

### Example: ₹1,500 UPI capture, 2% fee + GST

```
journal_entry: capture / pay_Kj2x

postings:
  D  customer_escrow_hdfc      150000     (money entered our nodal account)
  C  merchant:8812             146460     (what merchant will get)
  C  fees_income               3000       (our 2% MDR)
  C  gst_payable               540        (18% GST on fee)
                               ──────
  Debits 150000 == Credits 150000  ✓
```

Balance = `SUM(postings)` per account — but at 25K TPS you never sum from genesis:
maintain **running balances with periodic checkpoints** (daily balance snapshot per
account; live balance = snapshot + postings since). Recon re-derives from scratch and
compares — drift = P0 incident.

---

## 8. Deep Dive: Hot Accounts & Ledger Sharding

The fee-income account and big-merchant accounts appear in a huge share of entries. A row-lock
per posting on `fees_income` serializes the entire system → throughput collapses.

**Techniques, in the order you should present them:**

1. **Don't lock on write at all.** Postings are inserts (append-only) — inserts don't
   contend. Only *enforced-balance* accounts (customer wallets, prepaid) need a
   read-check; internal accounts (fees, escrow) are allowed to go arbitrarily positive
   → pure insert, zero contention.
2. **Sub-account striping for hot accounts.** Split `fees_income` into
   `fees_income_00..fees_income_63`; post to `hash(txn_ref) % 64`; reporting sums stripes.
   Same trick as sharded counters.
3. **Shard the ledger by account_id** (Vitess/Citus or app-level). Both postings of most
   entries hit different shards → cross-shard entry. Options: (a) saga-style two-phase
   posting with a pending/confirmed flag, or (b) route the *entry* to the shard of the
   debited account and replicate the credit via idempotent async posting — recon verifies
   the pair completed. Never distributed 2PC at this TPS.
4. **Wallet debits (balance must not go negative):** optimistic concurrency —
   `UPDATE balances SET balance = balance - :amt, version = version + 1
   WHERE account_id = :id AND version = :v AND balance >= :amt` → retry on rowcount 0.
   For a pathological hot wallet: serialize through a single-writer queue per account
   (mini stock-exchange pattern — cf. `Design_Stock_Exchange.md` single-threaded matching).

---

## 9. Deep Dive: Reconciliation & T+1 Settlement

The truth about payments: **your DB, the PSP's DB, and the bank's DB disagree every
single day.** Recon is the system that finds and fixes the disagreements. Interviews at
Razorpay/Juspay almost always land here.

### Settlement timeline

```
T+0  09:14  customer pays ₹1,500 → money lands in nodal/escrow bank account
T+0  23:59  cutoff — day's transactions frozen for settlement batch
T+1  early  bank/NPCI MIS files arrive (SFTP/API): every txn they saw, with RRN + status
T+1  morn.  RECON runs: 3-way match  (our ledger  vs  PSP file  vs  bank statement)
T+1  eve.   settlement batch: merchant gets ₹1,46,460 via NEFT/IMPS; ledger entry:
              D customer_escrow_hdfc 146460  /  C merchant_payable→bank 146460
```

### 3-way matching

```python
def reconcile(day):
    ours  = load_ledger_captures(day)          # keyed by txn_ref
    psp   = load_psp_mis_file(day)             # keyed by our txn_ref + their RRN
    bank  = load_bank_statement(day)           # nodal account credits

    for ref in ours.keys() | psp.keys():
        o, p = ours.get(ref), psp.get(ref)
        match (o, p):
            case (o, p) if o and p and o.amount == p.amount and both_success(o, p):
                mark_reconciled(ref)
            case (o, None):
                # We say SUCCESS, PSP file silent → suspense; re-inquire; if PSP
                # confirms failure → auto-reverse: mark REVERSED + refund customer
                open_exception(ref, kind="OURS_NOT_IN_PSP")
            case (None, p):
                # PSP charged customer, we never marked success (lost callback!)
                # → replay: force status-inquiry, transition PENDING→SUCCESS late
                open_exception(ref, kind="PSP_NOT_IN_OURS")
            case (o, p) if o.amount != p.amount:
                open_exception(ref, kind="AMOUNT_MISMATCH")   # human queue, rare

    assert bank_total(bank) == sum_reconciled() + suspense_delta(day)
```

### Mismatch classes and their fixes

| Mismatch | Cause | Resolution |
|---|---|---|
| We PENDING, bank SUCCESS | callback lost | recon promotes to SUCCESS (late), webhook fires |
| We SUCCESS, bank FAILED | callback spoof/bug or bank reversal | auto-reverse + refund + alert |
| In PSP file, absent in ours | we crashed before persisting attempt | create from PSP record, investigate |
| Amount mismatch | partial capture, currency, fat-finger | human exception queue |
| Bank total ≠ ledger total | anything above, in aggregate | blocks settlement until explained |

**Suspense account** = ledger account where every unexplained rupee lives until resolved.
Non-zero suspense older than 48h pages a human. This is how "every rupee accounted for"
is actually operationalized.

---

## 10. Deep Dive: PSP/Bank Routing & Circuit Breaking

Indian bank uptime is... variable. HDFC UPI down at 8 PM is a Tuesday. A gateway's core
value proposition is **success-rate arbitrage**: route each txn to whichever PSP/bank
currently completes it best.

```python
class PspRouter:
    """
    Score = success_rate (sliding window) blended with latency & cost.
    Circuit breaker per (psp, bank, method) tuple — HDFC-via-PSP-A can be
    down while HDFC-via-PSP-B is fine.
    """
    WINDOW_SEC = 120

    def pick(self, txn) -> str:
        candidates = self.eligible(txn.method, txn.issuer_bank)   # e.g. ['pspA','pspB']
        scored = []
        for psp in candidates:
            cb = self.breaker[(psp, txn.issuer_bank, txn.method)]
            if cb.state == "OPEN":
                continue                          # bank/psp pair is fried — skip
            s = (0.7 * self.success_rate(psp, txn.issuer_bank)    # last 2 min
                 + 0.2 * self.latency_score(psp)
                 + 0.1 * self.cost_score(psp))                    # per-txn fee
            if cb.state == "HALF_OPEN":
                s *= 0.1                          # trickle traffic to probe recovery
            scored.append((s, psp))
        if not scored:
            raise AllRoutesDown(txn.issuer_bank)  # → queue-and-retry or fail fast w/ message
        return max(scored)[1]
```

- **Breaker granularity matters:** open per `(psp, issuer_bank, method)`, not per PSP —
  otherwise one flaky bank blackholes a healthy PSP.
- **HALF_OPEN probing** with 1-5% traffic; success-rate on the probe cohort decides close/re-open.
- **Success-rate windows must be short** (1-2 min) — bank outages are spiky; a 1-hour
  window reacts after the sale event is over.
- Failover retry on a *different* rail is safe only pre-debit; after a debit-side timeout
  you must status-inquire first (Layer-2 idempotency, §5) — else double debit.

---

## 11. Deep Dive: UPI Flow Specifics

What actually happens on a UPI collect, and why callbacks are asymmetric:

```
1. Customer enters VPA "rahul@okhdfc" on checkout
2. VPA RESOLUTION: we → our PSP → NPCI → payee PSP (@okhdfc → HDFC's PSP)
      → returns account-holder name for display ("RAHUL KUMAR — confirm?")
      Cache VPA→(bank, name, validity) with short TTL; validation ≠ balance check.
3. COLLECT REQUEST: we → PSP → NPCI → customer's UPI app (push notification)
4. Customer enters UPI PIN in their app        ← we are NOT in this loop at all
5. DEBIT: issuer bank debits customer; NPCI switches to beneficiary bank; credit lands
6. CALLBACK CHAIN: issuer → NPCI → our PSP → us          ← the fragile part
7. We CAS PENDING→SUCCESS, outbox event, webhook to merchant
```

**Callback asymmetry — the crux:**
- The **debit leg is synchronous-ish** inside NPCI's switch (issuer must answer in
  seconds or NPCI times the leg out — "deemed" outcomes exist).
- The **notification back to us is best-effort async**. Step 6 can be delayed minutes
  or lost. So the customer's money is gone, merchant screen still says pending —
  UPI's most famous UX failure.
- Defense in depth: (a) callback (fast path) → (b) active status inquiry every
  ~15-30s while PENDING → (c) T+1 recon catches the last stragglers (§9). Three nets.
- Never mark FAILED on inquiry-timeout alone; UPI has "deemed approved" cases where
  the txn succeeds *after* the window. EXPIRED for us = stop showing spinner; recon
  still owns the final truth, and a late SUCCESS becomes refund-or-fulfil per merchant policy.

Intent flow (customer's UPI app opens with prefilled details, they approve) has the same
callback asymmetry — only steps 1-3 differ (deep link `upi://pay?...` instead of collect push).

---

## 12. Deep Dive: Tokenization & PCI-DSS Scope Reduction

PCI-DSS compliance cost scales with **where card data (PAN) travels**. Strategy: shrink
the compliance boundary to one tiny hardened service — the **token vault** — and keep the
other 200 microservices out of scope.

```
Checkout (browser)                    CDE = Cardholder Data Environment
   │  card fields are an IFRAME served by vault domain —
   │  PAN never touches merchant page OR our main API
   ▼
┌───────────────────────┐   everything else sees ONLY tokens
│  TOKEN VAULT (CDE)    │──────────────────────────────────────┐
│  - PAN encrypted:     │        token_9f2ab...                │
│    AES-256-GCM, DEK   │   ┌────────────┐  ┌──────────┐  ┌────▼─────┐
│    per record, KEK in │   │ Payment Svc│  │ Ledger   │  │ Analytics│
│    HSM, key rotation  │   │ (no PAN!)  │  │ (no PAN!)│  │ (no PAN!)│
│  - detokenize ONLY    │   └────────────┘  └──────────┘  └──────────┘
│    toward acquirer/   │
│    card network       │
└───────────────────────┘
```

- **RBI CoF mandate (2022):** merchants/aggregators may not store PAN; card-on-file must
  be **network tokens** (Visa VTS / Mastercard MDES / RuPay) — per (card × merchant) token,
  issued by the network, useless if leaked from one merchant.
- Vault properties: separate VPC + accounts, no outbound internet except card networks,
  dual-control key ceremonies, audit log on every detokenize, rate-limited detokenize API.
- Last-4 + network + expiry stored *outside* the vault for display — that metadata is not PAN.
- UPI flows never touch PAN at all — one more reason UPI-first gateways are cheaper to run.

---

## 13. Storage Choices

| Data | Store | Why |
|---|---|---|
| Payments, orders, refunds | Postgres/MySQL sharded by `merchant_id` (Vitess) | ACID transitions, merchant-scoped queries stay single-shard |
| Ledger (journal + postings) | Postgres, sharded by `account_id`, append-only | constraints + audit; inserts scale, no update contention |
| Idempotency fast path, status cache | Redis cluster | TTL'd, hot, loss-tolerant (DB constraint backs it) |
| Event backbone | Kafka (keyed by `payment_id` → per-payment ordering) | replay, fan-out to ledger/webhook/risk |
| Recon files, audit archive | S3 + Parquet, Athena/Spark for the 3-way match | 100 GB/day batch crunch |
| 7-10 yr retention | S3 Glacier tier | RBI retention at sane cost |

Why shard payments by `merchant_id` and not `payment_id`: every merchant-facing read
(dashboard, settlement report, list payments) is merchant-scoped → single shard.
Celebrity-merchant hot shard (Flipkart on sale day) → split that merchant across
sub-shards by hash(payment_id) within their namespace — same hot-key playbook as
timelines in `Design_Twitter_X.md`, different domain.

---

## 14. Failure Scenarios

| Scenario | Handling |
|---|---|
| Timeout on PSP debit call | Stay PENDING; status-inquiry loop; recon as last net. NEVER assume failure |
| Duplicate merchant request | Layer-1 idempotency: cached response replay (§5) |
| Duplicate/late bank callback | `UNIQUE(psp_ref_id)` + CAS guard; return 200 |
| Kafka down | Outbox absorbs — rows accumulate, relay drains on recovery; payment path unaffected |
| Ledger consumer lag | Payments proceed; ledger is async but monitored; settlement blocks if lag > threshold |
| Bank down at peak (HDFC 8 PM) | Circuit breaker opens per (psp,bank,method); router shifts traffic (§10) |
| ALL routes to issuer down | Fail fast with clear customer message; queue collect-retry is worse UX than honesty |
| Region failure | Active-passive for write path (sync replica, RPO 0); reads active-active |
| Webhook endpoint (merchant) down | Retry schedule → DLQ → dashboard alert; merchant polls as fallback |
| Recon finds bank credit we never saw | Exception queue → replay from PSP record → late SUCCESS + webhook |

---

## 15. Trade-offs

| Decision | Trade-off |
|---|---|
| Async everywhere + outbox | Effectively-once correctness; merchants must handle eventual status (202-then-webhook) |
| Ledger separate from payments DB | Clean audit + independent scaling; recon must verify the two agree |
| Sub-account striping for hot accounts | Insert throughput; reporting must aggregate stripes |
| Short success-rate windows for routing | Fast outage reaction; noisy on low-volume (psp,bank) pairs — need min-sample floors |
| Token vault as isolated CDE | PCI scope = 1 service; detokenize hop adds latency on card path |
| CAS-guarded transitions (no SELECT FOR UPDATE) | No lock queues at 25K TPS; "lost" transitions must re-read + ack, code is subtler |
| Fail-fast when all routes down | Honest UX, no ghost queue; lost GMV during outage — business will push back, hold the line |

---

## 16. Related Material (this repo)

- **LLD ground (don't repeat in interview if asked HLD):**
  [`../LLD_Problems/Payment_System.md`](../LLD_Problems/Payment_System.md) — gateway Strategy
  classes, state-machine code, idempotency store, wallet objects, retry/backoff, webhook handler classes.
- **Outbox + consumer idempotency mechanics:**
  [`../../../01_Year3-4_Mid/05_Microservices/04_outbox_event_sourcing.md`](../../../01_Year3-4_Mid/05_Microservices/04_outbox_event_sourcing.md)
  and runnable `01_Year3-4_Mid/05_Microservices/practical/04_outbox_idempotency.py`.
- **Sagas for multi-service money flows:**
  [`../HLD_Theory/59_Saga_Pattern.md`](../HLD_Theory/59_Saga_Pattern.md),
  [`../../02_Architecture_Patterns/Section_06_Event_Driven_Reactive/04_Saga_Outbox_Patterns.md`](../../02_Architecture_Patterns/Section_06_Event_Driven_Reactive/04_Saga_Outbox_Patterns.md),
  runnable `../HLD_Code/02_saga_orchestration/saga.py`.
- **Single-writer hot-key handling:** `Design_Stock_Exchange.md` §6 (same idea as per-account serialization, §8 here).

---

## 17. Interview Questions

**Q1: How do you guarantee a customer is never double-charged?**
> Three idempotency layers, one per trust boundary. Merchant→us: `Idempotency-Key` header, Redis atomic claim for the fast path, `UNIQUE(merchant_id, idempotency_key)` in the DB as the actual guarantee. Us→bank: our `txn_ref` is minted and persisted *before* the PSP call and reused verbatim on retries, so the PSP dedups; on timeout we status-inquire, never re-initiate blind. Bank→us: `UNIQUE(psp_ref_id)` on callbacks plus a CAS-guarded transition, and duplicates get HTTP 200 so the bank stops retrying. Any single layer can fail; the composition holds.

**Q2: What does "exactly-once" mean in your design, since it's theoretically impossible?**
> Delivery is at-least-once everywhere — retries, duplicate callbacks, Kafka redelivery. Exactly-once is reconstructed at the *effect* level: every state transition is a conditional UPDATE (`WHERE status='PENDING'`), so N duplicate triggers produce exactly one transition; every ledger posting is keyed by `UNIQUE(txn_ref, entry_type)`, so replayed events post once. At-least-once delivery + idempotent effects = effectively-once.

**Q3: Why a double-entry ledger — isn't a `balance` column enough?**
> A balance column tells you what the number is, not why. Double-entry forces every movement to name its source and destination, and `SUM(debits)=SUM(credits)` per entry is a machine-checkable invariant — corruption is detectable, not silent. It's append-only, so the audit trail is the data structure itself, and recon can re-derive any balance from history and diff against the checkpoint. With just a balance column, a lost update is indistinguishable from a legitimate state.

**Q4: Walk me through what happens when the bank callback never arrives.**
> Payment sits in PENDING. Net one: active status-inquiry job polls the PSP verify API every 15-30s during the live window. Net two: if still unknown at window end, we mark EXPIRED for UX (stop the spinner) but do *not* treat it as financial truth. Net three: T+1 recon 3-way match finds the bank-side SUCCESS with no matching ledger entry, opens a `PSP_NOT_IN_OURS` exception, replays the transition late — customer gets a delayed confirmation or an auto-refund per merchant policy. Money is never silently lost; worst case it's slow.

**Q5: How does reconciliation actually work at 500M txn/day?**
> Batch job on T+1: load our ledger captures, the PSP MIS file, and the nodal bank statement — roughly 100 GB — into a Spark/Athena 3-way match keyed on txn_ref/RRN. Matched rows are marked reconciled; every mismatch class (ours-not-in-PSP, PSP-not-in-ours, amount mismatch) routes to an automated fix or a human exception queue. Unexplained money sits in a suspense ledger account, and settlement to merchants is blocked until the bank total equals reconciled total plus explained suspense. Suspense aging past 48h pages someone.

**Q6: Bank X's success rate just dropped from 92% to 40%. What happens in your system?**
> The router's 2-minute sliding-window success rate for (psp, bankX, upi) collapses, the circuit breaker for that tuple trips OPEN, and traffic shifts to alternate PSPs reaching the same bank — breaker granularity is per (psp, bank, method), because bankX-via-pspA can be dead while bankX-via-pspB is fine. HALF_OPEN probes 1-5% of traffic to detect recovery. If *every* route to bankX is open, we fail fast with a clear message rather than queueing debits — a queued UPI debit against a flapping bank is how you manufacture double-debits.

**Q7: Where does the outbox pattern sit and why is it non-negotiable here?**
> Between the state machine and Kafka. The transition UPDATE and the event INSERT commit in one DB transaction; a relay tails the outbox into Kafka. Without it there's a window where the payment is SUCCESS in the DB but the ledger/webhook/settlement pipeline never hears — that's not a bug, it's missing money. The cost is at-least-once emission, which is fine because every consumer is idempotent (Q2).

**Q8: How do you scale the ledger past a single database?**
> First, exploit that postings are append-only inserts — no update contention. Second, stripe hot internal accounts (fees, escrow) into N sub-accounts and post to hash(txn_ref)%N; reports sum the stripes. Third, shard by account_id; cross-shard entries either go saga-style (pending→confirmed flag) or post the debit-shard entry synchronously and replicate the credit idempotently async, with recon verifying pair completion. The only accounts needing balance enforcement on the hot path are customer wallets — optimistic version-check UPDATE, and a single-writer queue for pathological hot wallets. No distributed 2PC anywhere.

**Q9: What is UPI callback asymmetry and how do you design around it?**
> The debit leg (customer app → issuer → NPCI) completes within NPCI's switch in seconds, but the notification chain back to the gateway (issuer → NPCI → PSP → us) is best-effort async — delayed or dropped routinely. So the customer's account is debited while our status is PENDING. Design answer: never trust the callback as the only signal — callback for speed, active inquiry for the live window, recon for the tail. And never fail a UPI txn purely on timeout, because "deemed approved" late successes exist.

**Q10: How does tokenization reduce PCI-DSS scope, concretely?**
> PCI scope covers every system that stores, processes, or transmits PAN. We collapse that to one vault service: card fields on checkout are an iframe served from the vault's domain, so PAN goes browser→vault directly, and every other service only ever sees an opaque token. The vault detokenizes solely toward the card networks, keeps PANs AES-256-GCM encrypted with per-record DEKs under an HSM-held KEK, and lives in an isolated network. Result: PCI L1 audit boundary is one small service instead of the whole platform. On top of that, RBI's CoF mandate means stored cards are network tokens (VTS/MDES) — per card-per-merchant, worthless if exfiltrated.

**Q11: Why 202 + webhook instead of a synchronous payment API?**
> UPI takes 3-10 seconds through hops we don't control; holding HTTP connections at 25K TPS is connection-pool suicide, and a dropped connection after a completed debit is an ambiguity factory. So: 202 with PENDING, then webhook push plus polling as fallback. Webhooks are at-least-once and unordered by contract, so the merchant treats them as hints and `GET /payments/{id}` as truth. This contract is *why* the internal exactly-once machinery can stay simple.

**Q12: Refund flow — what's different from payment flow?**
> Refund is a new money movement referencing the original, never a mutation of it: SUCCESS payment → REVERSED via a fresh reversing journal entry (never edit postings). Partial refunds must satisfy `SUM(refunds) <= captured amount`, enforced with the same CAS/version discipline as wallet debits. Refunds ride the original rail (UPI refund to the same VPA via RRN reference), can fail independently, and have their own recon stream in the T+1 files. Also, refunds pay out of *our* settled pool before we recover from the merchant's next settlement — a working-capital detail interviewers at gateways love to hear you know.
