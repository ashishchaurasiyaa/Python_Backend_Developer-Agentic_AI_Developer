"""
============================================================
CELERY PRIORITY QUEUES — Practical
============================================================
Multi-queue priorities AND RabbitMQ native priorities.

Run:
    # Terminal 1 — high priority worker
    celery -A app worker -Q priority_high -n vip@%h --concurrency=2

    # Terminal 2 — default worker
    celery -A app worker -Q default -n default@%h --concurrency=4

    # Terminal 3 — low priority worker
    celery -A app worker -Q priority_low -n bulk@%h --concurrency=1

    # Trigger tasks
    python 06_celery_priority_queues.py
"""


# ============================================================
# 1. MULTI-QUEUE SETUP (broker-agnostic)
# ============================================================
MULTI_QUEUE_CONFIG = '''
# celeryconfig.py

from celery import Celery
from kombu import Queue, Exchange

app = Celery("myapp")

# Define queues
app.conf.task_queues = (
    Queue("priority_high", Exchange("priority_high"), routing_key="priority_high"),
    Queue("default",       Exchange("default"),       routing_key="default"),
    Queue("priority_low",  Exchange("priority_low"),  routing_key="priority_low"),
    Queue("batch",         Exchange("batch"),         routing_key="batch"),
)

app.conf.task_default_queue = "default"
app.conf.task_default_exchange = "default"
app.conf.task_default_routing_key = "default"

# Route tasks by name pattern
app.conf.task_routes = {
    # Critical (payment, auth)
    "myapp.payments.*":        {"queue": "priority_high"},
    "myapp.auth.*":            {"queue": "priority_high"},

    # Default
    "myapp.emails.transactional":   {"queue": "default"},
    "myapp.notifications.push":     {"queue": "default"},

    # Low priority (bulk operations)
    "myapp.emails.newsletter":      {"queue": "priority_low"},
    "myapp.analytics.update":       {"queue": "priority_low"},

    # Batch (overnight)
    "myapp.reports.daily":          {"queue": "batch"},
}

# Throttle low-priority globally
app.conf.task_annotations = {
    "myapp.emails.newsletter": {"rate_limit": "100/m"},
    "myapp.analytics.update":  {"rate_limit": "1000/m"},
}
'''


# ============================================================
# 2. TASK DEFINITIONS WITH ROUTING
# ============================================================
TASK_DEFINITIONS = '''
from celery import shared_task

# HIGH PRIORITY
@shared_task(queue="priority_high")
def charge_payment(user_id, amount):
    """Critical — process immediately."""
    return process_payment(user_id, amount)

@shared_task(queue="priority_high", autoretry_for=(Exception,), max_retries=3)
def verify_email(user_id):
    """Account verification — user is waiting."""
    return send_verification(user_id)

# DEFAULT
@shared_task    # queue from task_routes
def send_transactional_email(user_id, template):
    return send_email(user_id, template)

# LOW PRIORITY
@shared_task(queue="priority_low", rate_limit="100/m")
def newsletter_email(user_id):
    return send_email(user_id, "newsletter")

# BATCH (nightly)
@shared_task(queue="batch")
def generate_daily_report():
    return create_report()


# DYNAMIC PRIORITY — based on user tier
@shared_task
def send_email(user_id, template, *, _user_tier="free"):
    pass

def enqueue_email(user_id, template, tier="free"):
    queue_map = {
        "enterprise": "priority_high",
        "pro":        "default",
        "free":       "priority_low",
    }
    queue = queue_map.get(tier, "default")
    send_email.apply_async(args=[user_id, template], queue=queue)
'''


# ============================================================
# 3. RUNNING WORKERS PER PRIORITY
# ============================================================
WORKER_COMMANDS = '''
# Strategy 1: DEDICATED workers per priority (recommended)
# Critical worker — small but always available
celery -A myapp worker \\
    -Q priority_high \\
    -n vip@%h \\
    --concurrency=4 \\
    --max-tasks-per-child=1000

# Default worker pool
celery -A myapp worker \\
    -Q default \\
    -n default@%h \\
    --concurrency=10

# Low-priority worker (limited)
celery -A myapp worker \\
    -Q priority_low \\
    -n bulk@%h \\
    --concurrency=2

# Batch worker (runs only during low-traffic hours via Beat or cron)
celery -A myapp worker \\
    -Q batch \\
    -n batch@%h \\
    --concurrency=4 \\
    --autoscale=2,8


# Strategy 2: SHARED workers with priority order
# Worker reads from priority_high first, falls back to default
celery -A myapp worker -Q priority_high,default --concurrency=10
# (Risk: surge of high-pri can starve default — only use for very low overall load)


# Kubernetes deployments
# Critical deployment: minReplicas=2, maxReplicas=20
# Default deployment:  minReplicas=4, maxReplicas=50
# Low-pri deployment:  minReplicas=1, maxReplicas=10
# Use KEDA to scale based on queue length
'''


# ============================================================
# 4. RABBITMQ NATIVE PRIORITY QUEUES
# ============================================================
RABBITMQ_PRIORITY = '''
# Only works with RabbitMQ broker, not Redis/SQS

from kombu import Queue, Exchange

app.conf.task_queues = [
    Queue(
        "priority_queue",
        Exchange("priority_queue"),
        routing_key="priority_queue",
        queue_arguments={"x-max-priority": 10},   # 0-10 priority range
    ),
]

# Apply tasks with priority (0-10, higher = more important)
@app.task
def some_task(data):
    pass

some_task.apply_async(args=[1], queue="priority_queue", priority=9)   # VIP
some_task.apply_async(args=[2], queue="priority_queue", priority=5)   # normal
some_task.apply_async(args=[3], queue="priority_queue", priority=1)   # bulk

# Worker
# celery -A myapp worker -Q priority_queue

# CAVEATS:
# - Recommended max priority = 10 (not 255)
# - More memory overhead per message
# - Doesn't preempt running tasks
# - Can't dedicate workers per priority level
'''


# ============================================================
# 5. PRIORITY-PRESERVING RETRIES
# ============================================================
RETRY_PRESERVE_PRIORITY = '''
from celery import shared_task

@shared_task(bind=True, queue="priority_high")
def critical_task(self, data):
    try:
        process(data)
    except Exception as exc:
        # CRITICAL: explicitly set queue on retry, else goes to default!
        raise self.retry(
            exc=exc,
            queue="priority_high",      # preserve priority
            countdown=2 ** self.request.retries,
            max_retries=5,
        )
'''


# ============================================================
# 6. STARVATION DETECTION + ALERTING
# ============================================================
STARVATION_DETECTION = '''
# Prometheus alert — high-priority queue growing
- alert: HighPriorityQueueBacklog
  expr: celery_queue_length{queue="priority_high"} > 10
  for: 1m
  labels: { severity: page }
  annotations:
    summary: "Priority queue backed up — possible worker shortage"

# Different thresholds per queue
- alert: DefaultQueueBacklog
  expr: celery_queue_length{queue="default"} > 1000
  for: 5m

- alert: LowPriorityQueueBacklog
  expr: celery_queue_length{queue="priority_low"} > 100000
  for: 30m
'''


# ============================================================
# 7. RATE LIMITING LOW-PRIORITY
# ============================================================
RATE_LIMITING = '''
# Per-task rate limit
@app.task(queue="priority_low", rate_limit="100/m")    # 100 per minute
def send_newsletter(email):
    pass

# Per-task with autoretry on rate limit
@app.task(queue="priority_low", rate_limit="10/s", autoretry_for=(Exception,))
def bulk_update(user_id):
    update(user_id)

# Global throttling via signals
from celery.signals import task_prerun
from time import time
import asyncio

@task_prerun.connect
def throttle(task=None, **kwargs):
    if task.name.startswith("myapp.bulk."):
        # Pace bulk tasks
        time.sleep(0.01)
'''


# ============================================================
# 8. DEMO DISPATCH CODE
# ============================================================
DEMO_CODE = '''
# Trigger tasks at different priorities to test
from myapp.tasks import (
    charge_payment, send_transactional_email,
    newsletter_email, generate_daily_report,
)
import asyncio

# Critical
charge_payment.delay(user_id=42, amount=1000)

# Default
send_transactional_email.delay(user_id=42, template="welcome")

# Bulk
for user_id in range(10000):
    newsletter_email.delay(user_id=user_id)

# Batch (scheduled via Celery Beat)
generate_daily_report.delay()


# Mixed dispatch to see queue prioritization
async def dispatch_burst():
    # 100 low-pri
    for i in range(100):
        newsletter_email.delay(i)
    # 10 critical
    for i in range(10):
        charge_payment.delay(i, 100)
    # 50 default
    for i in range(50):
        send_transactional_email.delay(i, "welcome")

    # Watch in Flower / Prometheus:
    # priority_high should drain first
    # default next
    # priority_low last
'''


# ============================================================
# 9. CONDITIONAL ENQUEUE BASED ON USER TIER
# ============================================================
USER_TIER_ROUTING = '''
def enqueue_user_action(user_id: int, action: str):
    """Route to queue based on user's tier."""
    user = User.objects.get(id=user_id)

    if user.tier == "enterprise":
        queue = "priority_high"
    elif user.tier == "pro":
        queue = "default"
    else:
        queue = "priority_low"

    process_action.apply_async(args=[user_id, action], queue=queue)
'''


# ============================================================
# 10. DECISION FLOWCHART
# ============================================================
DECISION_FLOWCHART = """
================================================================
Should this task be priority_high?
================================================================

Q: Is a user actively waiting for this result?
   ├── Yes → priority_high
   └── No:
       Q: Does delay cost money/reputation?
       ├── Yes (e.g., payment, alerts) → priority_high
       └── No:
           Q: Should it run within seconds?
           ├── Yes → default
           └── No:
               Q: Can it run during off-hours?
               ├── Yes → batch
               └── No → priority_low

PRIORITY CRITERIA EXAMPLES:
- priority_high:  payment, account verification, urgent alerts
- default:        transactional emails, search indexing
- priority_low:   analytics, newsletter, cache warming
- batch:          daily reports, log archival, db cleanup
================================================================
"""


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("CELERY PRIORITY QUEUES — Production Setup")
    print("=" * 60)

    print("\n--- 1. MULTI-QUEUE CONFIG ---")
    print(MULTI_QUEUE_CONFIG)
    print("\n--- 2. TASK DEFINITIONS ---")
    print(TASK_DEFINITIONS)
    print("\n--- 3. WORKER COMMANDS ---")
    print(WORKER_COMMANDS)
    print("\n--- 4. RABBITMQ NATIVE PRIORITY ---")
    print(RABBITMQ_PRIORITY)
    print("\n--- 5. PRIORITY-PRESERVING RETRIES ---")
    print(RETRY_PRESERVE_PRIORITY)
    print("\n--- 6. STARVATION DETECTION ---")
    print(STARVATION_DETECTION)
    print("\n--- 7. RATE LIMITING ---")
    print(RATE_LIMITING)
    print("\n--- 8. DEMO DISPATCH ---")
    print(DEMO_CODE)
    print("\n--- 9. USER TIER ROUTING ---")
    print(USER_TIER_ROUTING)
    print(DECISION_FLOWCHART)
