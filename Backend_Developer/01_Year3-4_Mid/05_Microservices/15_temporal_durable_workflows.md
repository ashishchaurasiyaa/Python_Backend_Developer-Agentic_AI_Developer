# Microservices — Temporal & Durable Workflow Execution
**Microservices · Year 3-4 | Senior Backend + Agentic AI**

## Quick Concepts

- **Temporal** = open-source durable execution platform (workflow-as-code)
- **Durable execution** = your code's state survives crashes, restarts, deploys
- **Workflow** = the "orchestration" function — what happens, in what order
- **Activity** = the "work" — actual side effects (API calls, DB writes)
- **Worker** = process that polls Temporal for tasks and runs your code
- **Task queue** = where work is dispatched (1 queue → N workers)
- **Signal** = external event sent into a running workflow
- **Query** = read state from a running workflow (no side effect)
- **Replay** = on resume, workflow re-runs deterministically, skipping completed steps
- **History** = full audit log of every event in a workflow

---

## Why Temporal Is a 2026 Senior Topic

```
Problem: long-running distributed workflows are HARD
─────────────────────────────────────────────────────
✗ "Process payment, charge card, ship item, send email,
    handle refund if anything fails"
   → easy on paper, painful in code

Traditional approaches:
   ✗ Saga pattern → manual compensation logic everywhere
   ✗ Step Functions / Cadence → vendor lock-in (AWS / LinkedIn)
   ✗ Custom retry loops → hard to test, harder to debug
   ✗ Database state machines → tons of boilerplate, race conditions

Temporal's promise:
   ✓ Write the orchestration as plain async code
   ✓ Temporal handles: retries, timeouts, cancellation, state,
                       crashes, deploys, observability
   ✓ Code looks normal — durability is invisible
```

**Senior interview Q (2026):** "How would you design a multi-step async workflow that survives crashes?"
→ The 2026 answer is increasingly: Temporal (or DBOS, Inngest, Restate as alternatives).

---

## Temporal vs Saga vs Step Functions vs Celery

| Aspect | Celery | Saga pattern | AWS Step Functions | Temporal |
|---|---|---|---|---|
| Long-running (days/weeks) | ✗ | 🟡 (manual) | ✓ | ✓ |
| Survives crash mid-workflow | 🟡 (limited) | 🟡 (state in DB) | ✓ | ✓ |
| Code-based workflow | ✗ (just tasks) | ✓ | ✗ (JSON DSL) | ✓ |
| Vendor lock-in | None | None | AWS-only | Open source |
| Built-in retries / timeouts | 🟡 | Manual | ✓ | ✓ |
| Test workflows locally | 🟡 | ✓ | ✗ (need AWS) | ✓ |
| Visibility / replay | Limited | Manual | UI | UI + replay |
| Multi-language | Python | Any | Any (via Lambda) | Many SDKs |
| Operational complexity | Low | None (in app) | None (managed) | Medium-High |

**When Temporal wins:** complex workflows, durability is non-negotiable, polyglot teams, need replay debugging.

**When Celery is fine:** background jobs, fire-and-forget, simple retries.

---

## Architecture Overview

```
   Your App                 Temporal Server               Your Workers
   ────────                 ───────────────                ─────────────
   ┌──────────┐             ┌──────────────────┐         ┌─────────────┐
   │  Start   │────────────►│   gRPC Frontend  │         │  Workflow   │
   │ workflow │             │                  │◄────────│   Worker    │
   │          │             │  ┌────────────┐  │         │             │
   │  Signals │────────────►│  │ History DB │  │◄────────│  Activity   │
   │          │             │  │ (PG/MySQL/ │  │         │   Worker    │
   │  Queries │◄────────────│  │ Cassandra) │  │         │             │
   └──────────┘             │  └────────────┘  │         └─────────────┘
                            │                  │
                            │  Matching        │   long-poll
                            │  Service         │◄──── tasks
                            │  (task queues)   │
                            └──────────────────┘
```

Key insight: Temporal stores **events** (decisions made + activity results) — not application state directly.
On replay, your workflow code re-runs, but completed steps return cached results instantly.

---

## Hello World — Python SDK

### Install

```bash
pip install temporalio
```

### 1. Activity (the actual work)

```python
# activities.py
from temporalio import activity


@activity.defn
async def charge_card(user_id: int, amount_cents: int) -> str:
    """Side-effectful work. Can fail. Will be retried by Temporal."""
    # call Stripe
    payment_id = await stripe_charge(user_id, amount_cents)
    return payment_id


@activity.defn
async def ship_order(order_id: int, address: dict) -> str:
    tracking = await shipping_api.create_shipment(order_id, address)
    return tracking


@activity.defn
async def send_email(to: str, subject: str, body: str) -> None:
    await mailer.send(to, subject, body)
```

### 2. Workflow (the orchestration)

```python
# workflows.py
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from activities import charge_card, ship_order, send_email


@workflow.defn
class OrderWorkflow:
    @workflow.run
    async def run(self, user_id: int, order_id: int, amount: int, email: str, address: dict) -> dict:
        # Step 1 — charge (with retries, timeout)
        payment_id = await workflow.execute_activity(
            charge_card,
            args=[user_id, amount],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=1),
                maximum_attempts=5,
                non_retryable_error_types=["CardDeclinedError"],
            ),
        )

        # Step 2 — ship
        try:
            tracking = await workflow.execute_activity(
                ship_order,
                args=[order_id, address],
                start_to_close_timeout=timedelta(minutes=2),
            )
        except Exception:
            # Compensating action: refund
            await workflow.execute_activity(
                refund_payment,
                args=[payment_id],
                start_to_close_timeout=timedelta(seconds=30),
            )
            raise

        # Step 3 — email confirmation
        await workflow.execute_activity(
            send_email,
            args=[email, "Order shipped!", f"Tracking: {tracking}"],
            start_to_close_timeout=timedelta(seconds=10),
        )

        return {"payment_id": payment_id, "tracking": tracking}
```

### 3. Worker (runs both)

```python
# worker.py
import asyncio
from temporalio.client import Client
from temporalio.worker import Worker

from activities import charge_card, ship_order, send_email, refund_payment
from workflows import OrderWorkflow


async def main():
    client = await Client.connect("localhost:7233")

    worker = Worker(
        client,
        task_queue="orders",
        workflows=[OrderWorkflow],
        activities=[charge_card, ship_order, send_email, refund_payment],
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
```

### 4. Starter — Trigger Workflow (e.g., from FastAPI)

```python
# starter.py (or inside FastAPI route)
from temporalio.client import Client
from workflows import OrderWorkflow


async def start_order(user_id: int, order_id: int, amount: int, email: str, address: dict):
    client = await Client.connect("localhost:7233")
    handle = await client.start_workflow(
        OrderWorkflow.run,
        args=[user_id, order_id, amount, email, address],
        id=f"order-{order_id}",     # idempotency: same id = same workflow
        task_queue="orders",
    )
    return handle.id


# FastAPI integration
@app.post("/orders/{order_id}/checkout")
async def checkout(order_id: int, body: dict):
    workflow_id = await start_order(
        body["user_id"], order_id, body["amount"], body["email"], body["address"]
    )
    return {"workflow_id": workflow_id, "status": "started"}


@app.get("/orders/{order_id}/status")
async def status(order_id: int):
    client = await Client.connect("localhost:7233")
    handle = client.get_workflow_handle(f"order-{order_id}")
    desc = await handle.describe()
    return {"status": desc.status.name, "id": handle.id}
```

→ Workflow runs, survives crashes, retries failures, all without you managing state.

---

## Determinism — The Core Rule

Workflow code must be **deterministic** — re-running it (on replay) must produce the same sequence of activity calls.

### ✗ DON'T do this in workflow code:

```python
# These break replay:
import random
import datetime

@workflow.defn
class Bad:
    @workflow.run
    async def run(self):
        x = random.random()              # ✗ non-deterministic
        now = datetime.datetime.now()    # ✗ wall clock
        with open("/tmp/file") as f:     # ✗ I/O
            data = f.read()
        await asyncio.sleep(5)           # ✗ use workflow.sleep
        requests.get("...")              # ✗ direct network call
```

### ✓ DO use Temporal primitives:

```python
@workflow.defn
class Good:
    @workflow.run
    async def run(self):
        # Use Temporal's deterministic randomness
        x = workflow.random().random()

        # Use Temporal's deterministic clock
        now = workflow.now()

        # Use Temporal's sleep (cancellable, replayable)
        await workflow.sleep(timedelta(seconds=5))

        # Side effects go in activities
        data = await workflow.execute_activity(read_file)
```

**Rule of thumb:** Workflows = pure logic. Side effects → activities.

---

## Signals & Queries

### Signal — Push Data Into Workflow

```python
@workflow.defn
class ApprovalWorkflow:
    def __init__(self):
        self.approved = False
        self.rejected = False
        self.comment = ""

    @workflow.signal
    def approve(self, comment: str):
        self.approved = True
        self.comment = comment

    @workflow.signal
    def reject(self, comment: str):
        self.rejected = True
        self.comment = comment

    @workflow.run
    async def run(self, request_id: str):
        # Wait up to 7 days for human approval
        await workflow.wait_condition(
            lambda: self.approved or self.rejected,
            timeout=timedelta(days=7),
        )

        if self.approved:
            return await workflow.execute_activity(process_request, request_id)
        return {"status": "rejected", "comment": self.comment}


# Sending the signal (from FastAPI):
handle = client.get_workflow_handle(f"approval-{req_id}")
await handle.signal(ApprovalWorkflow.approve, "Looks good!")
```

### Query — Read State Without Side Effects

```python
@workflow.defn
class CountingWorkflow:
    def __init__(self):
        self.count = 0

    @workflow.query
    def get_count(self) -> int:
        return self.count

    @workflow.run
    async def run(self):
        while True:
            await workflow.sleep(timedelta(seconds=60))
            self.count += 1


# From outside:
handle = client.get_workflow_handle("counter-1")
count = await handle.query(CountingWorkflow.get_count)
```

---

## Real-World Patterns

### Pattern 1: Saga with Automatic Compensation

```python
@workflow.defn
class TravelBookingWorkflow:
    @workflow.run
    async def run(self, req: dict) -> dict:
        flight_id = None
        hotel_id = None
        car_id = None

        try:
            flight_id = await workflow.execute_activity(book_flight, req["flight"])
            hotel_id = await workflow.execute_activity(book_hotel, req["hotel"])
            car_id = await workflow.execute_activity(book_car, req["car"])
        except Exception as e:
            # Compensate in reverse order
            if car_id:
                await workflow.execute_activity(cancel_car, car_id)
            if hotel_id:
                await workflow.execute_activity(cancel_hotel, hotel_id)
            if flight_id:
                await workflow.execute_activity(cancel_flight, flight_id)
            raise

        return {"flight": flight_id, "hotel": hotel_id, "car": car_id}
```

### Pattern 2: Scheduled / Recurring

```python
@workflow.defn
class DailyReportWorkflow:
    @workflow.run
    async def run(self):
        while True:
            await workflow.sleep(timedelta(days=1))
            await workflow.execute_activity(generate_report)
            # `continue_as_new` for long loops (avoids huge history)
            if workflow.info().history_length > 10_000:
                workflow.continue_as_new()
```

### Pattern 3: Parent → Child Workflows

```python
@workflow.defn
class ParentWorkflow:
    @workflow.run
    async def run(self, user_ids: list[int]):
        # Spawn child workflow per user
        handles = []
        for user_id in user_ids:
            h = await workflow.start_child_workflow(
                ProcessUserWorkflow.run,
                args=[user_id],
                id=f"process-user-{user_id}",
            )
            handles.append(h)

        # Wait for all children
        results = await asyncio.gather(*handles)
        return results
```

### Pattern 4: Human-In-The-Loop Approval

```python
# Combine signal + sleep
@workflow.defn
class ExpenseApprovalWorkflow:
    def __init__(self):
        self.decision = None

    @workflow.signal
    def submit_decision(self, approved: bool, by: str):
        self.decision = (approved, by)

    @workflow.run
    async def run(self, expense: dict):
        # Send to Slack/email for approval
        await workflow.execute_activity(send_approval_request, expense)

        # Wait for human (max 3 days, escalate after 1)
        try:
            await workflow.wait_condition(
                lambda: self.decision is not None,
                timeout=timedelta(days=1),
            )
        except TimeoutError:
            await workflow.execute_activity(escalate_to_manager, expense)
            await workflow.wait_condition(
                lambda: self.decision is not None,
                timeout=timedelta(days=2),
            )

        approved, by = self.decision
        if approved:
            await workflow.execute_activity(disburse, expense)
        return {"approved": approved, "by": by}
```

### Pattern 5: Polling External System

```python
@workflow.defn
class WaitForStatusWorkflow:
    @workflow.run
    async def run(self, external_id: str):
        for _ in range(100):  # 100 attempts max
            status = await workflow.execute_activity(
                check_status,
                args=[external_id],
                start_to_close_timeout=timedelta(seconds=10),
            )
            if status == "done":
                return status
            await workflow.sleep(timedelta(seconds=30))
        raise TimeoutError("External status never reached 'done'")
```

---

## Deployment

### Self-Host Docker Compose

```yaml
# Quick local setup
version: "3"
services:
  postgresql:
    image: postgres:16
    environment:
      POSTGRES_USER: temporal
      POSTGRES_PASSWORD: temporal

  temporal:
    image: temporalio/auto-setup:1.24.0
    depends_on:
      - postgresql
    environment:
      DB: postgresql
      DB_PORT: 5432
      POSTGRES_USER: temporal
      POSTGRES_PWD: temporal
      POSTGRES_SEEDS: postgresql
    ports:
      - 7233:7233

  temporal-ui:
    image: temporalio/ui:2.31.0
    depends_on:
      - temporal
    environment:
      TEMPORAL_ADDRESS: temporal:7233
    ports:
      - 8080:8080
```

→ `docker compose up` → Temporal server + UI at http://localhost:8080.

### Production Considerations

```
Components needed:
   ✓ Temporal server cluster (3+ nodes recommended)
   ✓ Database backend (Postgres / MySQL / Cassandra)
   ✓ Workers — your code (scale horizontally)
   ✓ UI (read-only consumer of server)

Storage scaling:
   ✓ Cassandra recommended for > 10k workflows/day
   ✓ Postgres fine for moderate scale
   ✓ Configure retention (90-day default for completed workflows)

Multi-region:
   ✓ Temporal Cluster Replication (since 2024)
   ✓ Multi-region failover

Managed alternative:
   ✓ Temporal Cloud — official SaaS
   ✓ Costs ~$200-1000/month for moderate workloads
```

---

## Observability

### Built-in UI

Workflow execution history visualized in the Temporal UI: events, retries, durations, activity attempts, etc. Replay debugging.

### Metrics

```
Temporal exposes Prometheus metrics:
   ✓ temporal_request_latency
   ✓ temporal_workflow_completed_total
   ✓ temporal_workflow_failed_total
   ✓ temporal_activity_execution_latency
   ✓ temporal_task_schedule_to_start_latency
```

### Logging in Activities

```python
@activity.defn
async def my_activity(...):
    activity.logger.info("starting", extra={"context": ...})
    # Activity logs are correlated to workflow in UI
```

---

## Testing

### Unit Test Workflow (No Server Needed)

```python
import pytest
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from workflows import OrderWorkflow
from activities import charge_card, ship_order


@pytest.mark.asyncio
async def test_order_workflow():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test",
            workflows=[OrderWorkflow],
            activities=[charge_card, ship_order],
        ):
            result = await env.client.execute_workflow(
                OrderWorkflow.run,
                args=[1, 100, 5000, "a@b.com", {"city": "Mumbai"}],
                id="test-order",
                task_queue="test",
            )
            assert result["payment_id"]
```

### Mock Activities

```python
async def fake_charge_card(user_id, amount):
    return "fake-payment-123"

async with Worker(
    env.client,
    task_queue="test",
    workflows=[OrderWorkflow],
    activities=[fake_charge_card, ...],
):
    ...
```

→ Test workflows independent of real external systems.

---

## Interview Questions & Answers

### Q1: What problem does Temporal solve that a queue + DB state machine doesn't?

**Answer:**

Queue + DB approach forces you to:
1. Persist workflow state in your DB
2. Handle retries manually for each step
3. Build state machines (states + transitions)
4. Handle crashes mid-step (where was I?)
5. Implement timeouts, signals, queries by hand
6. Test all the failure paths

Temporal handles all six. Your code looks like a normal async function. The durability is invisible — the runtime + event sourcing under the hood make it crash-proof. You stop writing state machine boilerplate.

### Q2: What's "durable execution"?

**Answer:**

Code that resumes from where it stopped after any failure — process crash, host failure, deploy, network partition.

Achieved via:
1. **Event sourcing** — every decision + result stored in Temporal's history
2. **Deterministic replay** — on resume, code re-runs and re-applies history, skipping completed steps via cached results
3. **At-least-once activity execution** with deduplication via activity IDs

Result: your `await charge_card(...)` is guaranteed to either succeed exactly once, or fail with a known terminal state.

### Q3: How is Temporal different from AWS Step Functions?

**Answer:**

```
AWS Step Functions:
   ✓ Managed
   ✓ Integrates deeply with AWS
   ✗ DSL (JSON / YAML) — not code
   ✗ Limited expressiveness
   ✗ Vendor lock-in
   ✗ Hard to test locally

Temporal:
   ✓ Code (Python / TS / Java / Go / .NET)
   ✓ Open source (self-host or Temporal Cloud)
   ✓ Strong testing story
   ✓ Same workflow runs in any cloud
   ✗ Operational complexity (if self-host)

Pick Step Functions if AWS-only + simple workflows.
Pick Temporal for complex orchestration, code-based logic, polyglot teams.
```

### Q4: Why must workflows be deterministic?

**Answer:**

On crash, Temporal replays the workflow by re-running your code while applying recorded events. If `random.random()` returns a different value on replay than originally, the workflow may take a different branch — divergence — and Temporal fails the workflow.

Hence:
- No `random`, `now()`, `os.environ`, network calls in workflow code
- Use `workflow.now()`, `workflow.random()`, `workflow.sleep()`
- Side effects go in **activities** (which run once and have their results cached)

### Q5: When would you NOT use Temporal?

**Answer:**

```
✗ Simple fire-and-forget background jobs
   → Celery / Sidekiq is sufficient

✗ High-frequency, sub-millisecond operations
   → Temporal adds RPC overhead

✗ Pure messaging without orchestration
   → Kafka / RabbitMQ

✗ Single-step async tasks
   → asyncio.create_task is enough

✗ Team has no DevOps capacity AND budget is tight
   → Even Temporal Cloud has costs

Best fit:
   ✓ Multi-step workflows
   ✓ Long durations (minutes to weeks)
   ✓ Need durability + observability + replay
```

### Q6: How do you migrate a Celery-based saga to Temporal?

**Answer:**

```
Step 1 — Audit current saga
   ✓ Identify each step
   ✓ Identify compensation logic
   ✓ Identify error handling

Step 2 — Map to Temporal
   ✓ Each step → activity
   ✓ Orchestration → workflow
   ✓ Compensation → try/except in workflow

Step 3 — Run side-by-side
   ✓ New orders → Temporal
   ✓ Old orders → Celery (until drained)
   ✓ Feature flag to gate

Step 4 — Decommission Celery sagas
   ✓ Verify all in-flight workflows complete
   ✓ Remove old code

Migration time: weeks for one workflow,
                months for a full system.
```

### Q7: How do you handle workflow versioning?

**Answer:**

Problem: workflow code changes, but workflows started on old code must complete deterministically.

Solutions:

```python
# 1. continue_as_new — long-running workflows restart with new code
if version_old:
    workflow.continue_as_new(new_args)

# 2. patched() — branch on workflow ID for safe updates
if workflow.patched("v2-flow"):
    # New behavior
    await new_activity()
else:
    # Original behavior
    await old_activity()

# After all old workflows drain, deprecate:
# workflow.deprecate_patch("v2-flow")
```

Senior tip: **never make breaking changes to running workflows**. Always patch or continue_as_new.

### Q8: How do you debug a failed workflow?

**Answer:**

Temporal's killer feature: complete history replay.

```
1. Open the workflow in UI
2. See every event:
   - When started
   - Each activity attempted, succeeded, retried
   - Signals received
   - Errors with stack traces

3. Re-run replay locally:
   ✓ Download history JSON
   ✓ Replay against worker code
   ✓ See exactly where it diverges/fails

4. Fix code, deploy new worker version
   ✓ Workflow can resume mid-flight on new code (if non-breaking)
```

This is impossible with Celery/RabbitMQ workflows. Senior insight: **replay-debugging alone justifies Temporal for complex flows.**

---

## Common Pitfalls

```
1. ✗ Non-deterministic code in workflow
   → import random; random.random() in workflow
   ✓ workflow.random().random()

2. ✗ Long-running CPU-bound code in workflow
   → Workflows aren't for compute; they orchestrate
   ✓ Move compute to activities, run on separate workers

3. ✗ Huge workflow history (millions of events)
   → Replay becomes slow, memory grows
   ✓ Use continue_as_new every N iterations

4. ✗ Activities without idempotency
   → Retries cause double-charges
   ✓ Activities must be idempotent (use idempotency keys)

5. ✗ Forgetting timeouts
   → Activity blocks forever
   ✓ Always set start_to_close_timeout

6. ✗ Treating queries as side-effects
   → Queries are pure reads; no DB writes in them
   ✓ Use signals for state changes

7. ✗ Calling Temporal client inside workflow
   → Don't trigger workflows from workflows via direct client
   ✓ Use workflow.execute_child_workflow

8. ✗ Sharing state via global variables
   → Multi-worker = state inconsistency
   ✓ All state lives on workflow instance (self.x)

9. ✗ Skipping replay tests on code change
   → Old workflows break on deploy
   ✓ Run replay test against historical workflows

10. ✗ Self-hosting without ops capacity
    → Temporal Server is non-trivial
    ✓ Start with Temporal Cloud, migrate later
```

---

## Alternatives to Know

```
Restate         — durable execution, Java-first, simpler model
DBOS            — durable execution in TS/Python via Postgres
Inngest         — event-driven workflows, dev-friendly, managed
Cadence         — Uber's predecessor to Temporal (still used)
Conductor       — Netflix's orchestrator
Argo Workflows  — K8s-native batch workflows
Prefect         — data engineering workflows (lighter)
Airflow         — batch / data workflows (heavyweight)
```

**Trend:** durable execution is winning over hand-rolled state machines. Temporal is the leader; DBOS and Restate are simpler alternatives gaining traction.

---

## Senior Mantras

```
1. Workflows orchestrate. Activities do.

2. Workflows must be deterministic. Always.

3. Activities must be idempotent. Always.

4. Set timeouts on every activity. Never indefinite.

5. Use signals for external events. Queries for reads.

6. continue_as_new for long-running workflows.
   Otherwise history balloons.

7. Replay tests are non-negotiable before deploy.

8. Start with Temporal Cloud. Self-host when scale demands.

9. Migrate from Celery/Saga gradually. One workflow at a time.

10. Temporal is overkill for fire-and-forget. Right for orchestration.
```

---

## Resources

```
✓ https://temporal.io — official
✓ https://docs.temporal.io — comprehensive docs
✓ https://learn.temporal.io — courses
✓ https://github.com/temporalio/samples-python — Python examples
✓ Temporal YouTube — production case studies
✓ "Designing Durable Workflows" — blog series
```

---

## Related Topics

- [04_outbox_event_sourcing.md](04_outbox_event_sourcing.md) — alternative for cross-service consistency
- [05_event_sourcing_cqrs.md](05_event_sourcing_cqrs.md) — Temporal uses event sourcing internally
- [07_kafka_event_streaming.md](07_kafka_event_streaming.md) — Temporal can coexist with Kafka
- [14_cell_based_architecture.md](14_cell_based_architecture.md) — cell-aware workflow design
- [../02_Year5+_Senior/01_System_Design/HLD_Problems/Design_Agent_Orchestration.md](../../02_Year5+_Senior/01_System_Design/HLD_Problems/Design_Agent_Orchestration.md) — Temporal for agent orchestration
- [../01_Year3-4_Mid/09_Celery/](../09_Celery) — when Celery is enough
