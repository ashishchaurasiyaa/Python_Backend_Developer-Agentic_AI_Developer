"""
============================================================
CELERY TASK ROUTING — Practical
============================================================
Working examples of:
1. task_routes mapping
2. Router classes (dynamic routing)
3. RabbitMQ topic exchanges
4. Per-queue specialized workers
5. Conditional routing based on payload
6. Multi-tenant routing
7. Inspect routing decisions
"""


# ============================================================
# 1. STATIC ROUTING via task_routes
# ============================================================
STATIC_ROUTES = '''
from celery import Celery
from kombu import Exchange, Queue

app = Celery("myapp")

# Define exchanges
emails_ex   = Exchange("emails",  type="topic")
ml_ex       = Exchange("ml",      type="topic")
default_ex  = Exchange("default", type="direct")

# Define queues with bindings
app.conf.task_queues = (
    # Email queues — topic-based routing
    Queue("emails_critical",      emails_ex, routing_key="email.*.critical"),
    Queue("emails_transactional", emails_ex, routing_key="email.txn.*"),
    Queue("emails_marketing",     emails_ex, routing_key="email.mkt.*"),

    # ML queues
    Queue("ml_gpu", ml_ex, routing_key="ml.gpu.*"),
    Queue("ml_cpu", ml_ex, routing_key="ml.cpu.*"),

    # Default
    Queue("default", default_ex, routing_key="default"),
)

app.conf.task_default_queue = "default"
app.conf.task_default_exchange = "default"
app.conf.task_default_routing_key = "default"

# Static routing rules
app.conf.task_routes = {
    "myapp.emails.welcome": {
        "exchange": "emails",
        "routing_key": "email.txn.welcome",
    },
    "myapp.emails.alert_critical": {
        "exchange": "emails",
        "routing_key": "email.txn.critical",     # → emails_critical AND emails_transactional
    },
    "myapp.emails.newsletter": {
        "exchange": "emails",
        "routing_key": "email.mkt.newsletter",
    },
    "myapp.ml.train_deep_model": {
        "exchange": "ml",
        "routing_key": "ml.gpu.train",
        "priority": 5,
    },
    "myapp.ml.predict_simple": {
        "exchange": "ml",
        "routing_key": "ml.cpu.predict",
    },
}
'''


# ============================================================
# 2. ROUTER CLASS (dynamic routing)
# ============================================================
ROUTER_CLASS = '''
class CustomRouter:
    """Router class — fine-grained logic per task."""

    def route_for_task(self, task, args=None, kwargs=None, **opts):
        kwargs = kwargs or {}

        # Image processing — route based on size
        if task == "myapp.image.process":
            size = kwargs.get("size_bytes", 0)
            hires = kwargs.get("hires", False)

            if hires or size > 50_000_000:
                return {"queue": "gpu_heavy"}
            if size > 5_000_000:
                return {"queue": "cpu_heavy"}
            return {"queue": "default"}

        # ML routing
        if task.startswith("myapp.ml."):
            return {"queue": "ml_gpu" if "train" in task else "ml_cpu"}

        # Tenant tier
        tenant_id = kwargs.get("tenant_id")
        if tenant_id:
            tier = get_tenant_tier(tenant_id)
            if tier == "enterprise":
                return {"queue": "priority_high"}

        # Geographic
        region = kwargs.get("region")
        if region:
            return {"queue": f"tasks_{region}"}

        return None    # fall through to task_routes / default

# Register router
app.conf.task_routes = (CustomRouter(),)
'''


# ============================================================
# 3. SAMPLE TASKS WITH ROUTES
# ============================================================
SAMPLE_TASKS = '''
from celery import shared_task

# Auto-routed via task_routes
@shared_task
def send_welcome_email(user_id):
    # routed by task_routes: "myapp.emails.welcome"
    pass

@shared_task
def send_critical_alert(user_id, alert):
    # routed by task_routes: "myapp.emails.alert_critical"
    pass

# Explicit per-call routing override
@shared_task
def generic_task(data):
    pass

# Send to specific queue per call
generic_task.apply_async(args=[1], queue="urgent")
generic_task.apply_async(args=[2], queue="batch")

# Send with full routing options
generic_task.apply_async(
    args=[3],
    exchange="emails",
    routing_key="email.txn.welcome",
    queue="emails_transactional",
)

# Image processing — route decided by router class
@shared_task
def process_image(image_id, size_bytes=0, hires=False):
    pass

# These all route differently based on kwargs
process_image.apply_async(args=[1], kwargs={"size_bytes": 1000})        # → default
process_image.apply_async(args=[2], kwargs={"size_bytes": 10_000_000})  # → cpu_heavy
process_image.apply_async(args=[3], kwargs={"hires": True})             # → gpu_heavy
'''


# ============================================================
# 4. SPECIALIZED WORKER COMMANDS
# ============================================================
WORKER_COMMANDS = '''
# CRITICAL EMAILS — high concurrency, low capacity workers
celery -A myapp worker \\
    -Q emails_critical \\
    --concurrency=4 \\
    --pool=gevent \\
    -n emails-critical@%h \\
    --max-tasks-per-child=500

# TRANSACTIONAL EMAILS — I/O bound, gevent
celery -A myapp worker \\
    -Q emails_transactional \\
    --concurrency=50 \\
    --pool=gevent \\
    -n emails-txn@%h

# MARKETING EMAILS — rate-limited, separate pool
celery -A myapp worker \\
    -Q emails_marketing \\
    --concurrency=10 \\
    --pool=gevent \\
    -n emails-mkt@%h

# ML GPU — solo pool (one task per worker = no GPU contention)
CUDA_VISIBLE_DEVICES=0 celery -A myapp worker \\
    -Q ml_gpu \\
    --pool=solo \\
    --concurrency=1 \\
    -n ml-gpu-0@%h

# Multiple GPUs = multiple workers
CUDA_VISIBLE_DEVICES=1 celery -A myapp worker \\
    -Q ml_gpu \\
    --pool=solo --concurrency=1 -n ml-gpu-1@%h

# ML CPU — prefork pool for batch inference
celery -A myapp worker \\
    -Q ml_cpu \\
    --pool=prefork \\
    --concurrency=8 \\
    -n ml-cpu@%h

# CPU-HEAVY image processing — limit by RAM
celery -A myapp worker \\
    -Q cpu_heavy \\
    --concurrency=2 \\
    --max-memory-per-child=1000000 \\   # 1GB limit
    -n cpu-heavy@%h

# DEFAULT worker
celery -A myapp worker \\
    -Q default \\
    --concurrency=8 \\
    -n default@%h
'''


# ============================================================
# 5. KUBERNETES DEPLOYMENTS (per worker type)
# ============================================================
KUBE_DEPLOYMENTS = '''
# k8s deployments — one per worker type

---
apiVersion: apps/v1
kind: Deployment
metadata: { name: celery-emails-txn }
spec:
  replicas: 4
  selector: { matchLabels: { worker: emails-txn } }
  template:
    metadata: { labels: { worker: emails-txn } }
    spec:
      containers:
      - name: celery
        image: myapp:latest
        command:
          - celery
          - "-A"
          - myapp
          - worker
          - "-Q"
          - emails_transactional
          - --pool=gevent
          - --concurrency=50
        resources:
          requests: { cpu: 250m, memory: 256Mi }

---
apiVersion: apps/v1
kind: Deployment
metadata: { name: celery-ml-gpu }
spec:
  replicas: 2
  selector: { matchLabels: { worker: ml-gpu } }
  template:
    metadata: { labels: { worker: ml-gpu } }
    spec:
      nodeSelector:
        accelerator: nvidia-tesla-t4
      containers:
      - name: celery
        image: myapp-ml:latest
        command:
          - celery
          - "-A"
          - myapp
          - worker
          - "-Q"
          - ml_gpu
          - --pool=solo
          - --concurrency=1
        resources:
          limits:
            nvidia.com/gpu: 1
'''


# ============================================================
# 6. MULTI-TENANT ROUTING
# ============================================================
MULTI_TENANT_ROUTING = '''
class TenantRouter:
    """Route based on tenant tier."""

    TIER_QUEUE = {
        "enterprise": "tier_1_dedicated",
        "pro":        "tier_2_shared",
        "free":       "tier_3_shared",
    }

    def __init__(self):
        # Local cache to avoid DB hit per task
        from cachetools import TTLCache
        self.tier_cache = TTLCache(maxsize=10000, ttl=300)

    def get_tier(self, tenant_id):
        if tenant_id not in self.tier_cache:
            self.tier_cache[tenant_id] = lookup_db(tenant_id)
        return self.tier_cache[tenant_id]

    def route_for_task(self, task, args=None, kwargs=None, **opts):
        tenant_id = (kwargs or {}).get("tenant_id")
        if not tenant_id:
            return None
        tier = self.get_tier(tenant_id)
        queue = self.TIER_QUEUE.get(tier, "tier_3_shared")
        return {"queue": queue}

app.conf.task_routes = (TenantRouter(),)
'''


# ============================================================
# 7. GEOGRAPHIC ROUTING
# ============================================================
GEO_ROUTING = '''
class GeoRouter:
    """Route to region-specific workers."""

    def route_for_task(self, task, args=None, kwargs=None, **opts):
        region = (kwargs or {}).get("region", "us-east-1")
        return {"queue": f"region_{region}"}

# Deploy region-specific workers
# - Workers in us-east-1 consume "region_us-east-1"
# - Workers in eu-west-1 consume "region_eu-west-1"
# - Cross-region traffic reduced
'''


# ============================================================
# 8. INSPECT QUEUE STATE
# ============================================================
INSPECT_QUEUES = '''
from celery import Celery
app = Celery("myapp", broker="redis://localhost:6379/0")

# Inspect API
inspect = app.control.inspect()

# Active tasks per worker
active = inspect.active()
# {'worker1@host': [{'id': 'task-id', 'name': 'task.name', ...}]}

# Tasks claimed but not started
reserved = inspect.reserved()

# Stats (broker info, queue info)
stats = inspect.stats()
print(stats["worker1@host"]["broker"])
print(stats["worker1@host"]["pool"])

# Registered tasks
print(inspect.registered())

# Revoked tasks
print(inspect.revoked())


# Programmatic queue length (RabbitMQ)
import pyrabbit2
client = pyrabbit2.Client("localhost:15672", "guest", "guest")
info = client.get_queue("/", "emails_transactional")
print(f"Pending: {info['messages_ready']}")

# Programmatic (Redis broker)
import redis
r = redis.Redis()
length = r.llen("emails_transactional")
print(f"Pending: {length}")
'''


# ============================================================
# 9. DEBUG ROUTING DECISIONS
# ============================================================
DEBUG_ROUTING = '''
from celery import current_app

# What queue would a task go to?
def trace_routing(task_name, **kwargs):
    sig = current_app.signature(task_name, kwargs=kwargs)
    # Apply routing rules
    for router in current_app.conf.task_routes:
        if callable(router):
            result = router(task_name, kwargs=kwargs)
        elif isinstance(router, dict):
            result = router.get(task_name)
        if result:
            return result
    return {"queue": current_app.conf.task_default_queue}

# Use
print(trace_routing("myapp.image.process", size_bytes=20_000_000))
# {'queue': 'cpu_heavy'}

# Or actually apply, then check
sig = my_task.signature(args=[1])
print(sig.options)
'''


# ============================================================
# 10. EXCHANGE TYPES COMPARISON
# ============================================================
EXCHANGE_TYPES = """
================================================================
RABBITMQ EXCHANGE TYPES — Decision Guide
================================================================

DIRECT (default):
  routing_key = queue name exactly
  Use for: simple 1-to-1 routing
  Example: routing_key="emails" → queue "emails"

TOPIC:
  routing_key = pattern with wildcards
  * = one word, # = zero or more words
  Use for: fan-out by category/severity
  Example: "email.*.urgent" matches "email.txn.urgent" AND "email.mkt.urgent"

FANOUT:
  Ignores routing key, sends to ALL bound queues
  Use for: broadcast (cache invalidation, config refresh)

HEADERS:
  Match on message headers, not routing key
  Use for: rare — when key isn't enough
  Example: headers={"region": "us", "priority": "high"}
================================================================
"""


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("CELERY TASK ROUTING — Production Setup")
    print("=" * 60)

    print("\n--- 1. STATIC ROUTES ---")
    print(STATIC_ROUTES)
    print("\n--- 2. ROUTER CLASS ---")
    print(ROUTER_CLASS)
    print("\n--- 3. SAMPLE TASKS ---")
    print(SAMPLE_TASKS)
    print("\n--- 4. WORKER COMMANDS ---")
    print(WORKER_COMMANDS)
    print("\n--- 5. KUBERNETES DEPLOYMENTS ---")
    print(KUBE_DEPLOYMENTS)
    print("\n--- 6. MULTI-TENANT ROUTING ---")
    print(MULTI_TENANT_ROUTING)
    print("\n--- 7. GEOGRAPHIC ROUTING ---")
    print(GEO_ROUTING)
    print("\n--- 8. INSPECT QUEUES ---")
    print(INSPECT_QUEUES)
    print("\n--- 9. DEBUG ROUTING ---")
    print(DEBUG_ROUTING)
    print(EXCHANGE_TYPES)
