"""
Celery + Django Integration — Production Patterns
"""

# ==========================================================================
# 1. CELERY APP SETUP
# ==========================================================================

"""
# config/celery.py

import os
from celery import Celery
from celery.signals import worker_ready


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')


app = Celery('myapp')
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks.py in all installed apps
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')


@worker_ready.connect
def at_start(sender, **kwargs):
    print('Worker ready')
    # Optionally: enqueue startup tasks
"""


# ==========================================================================
# 2. __init__.py — Make Celery available
# ==========================================================================

"""
# config/__init__.py

from .celery import app as celery_app


__all__ = ('celery_app',)
"""


# ==========================================================================
# 3. SETTINGS
# ==========================================================================

CELERY_SETTINGS = """
# settings.py

INSTALLED_APPS += [
    'django_celery_beat',
    'django_celery_results',
]


# Broker (Redis recommended)
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://redis:6379/1')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://redis:6379/2')

# Or use django-celery-results (stores in Django DB)
# CELERY_RESULT_BACKEND = 'django-db'

CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE   # match Django

# Always eager in tests
CELERY_TASK_ALWAYS_EAGER = False
CELERY_TASK_EAGER_PROPAGATES = True

# Result storage
CELERY_RESULT_EXPIRES = 3600    # 1 hour
CELERY_TASK_IGNORE_RESULT = False   # set True per-task if not needed

# Time limits
CELERY_TASK_TIME_LIMIT = 600        # hard kill at 10 min
CELERY_TASK_SOFT_TIME_LIMIT = 540   # SoftTimeLimitExceeded at 9 min
CELERY_TASK_TRACK_STARTED = True

# Worker tuning
CELERY_WORKER_PREFETCH_MULTIPLIER = 4   # prefetch 4 tasks per worker
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000   # restart worker after N tasks (avoid leaks)
CELERY_WORKER_DISABLE_RATE_LIMITS = False

# Routing
CELERY_TASK_ROUTES = {
    'emails.tasks.*': {'queue': 'emails'},
    'reports.tasks.*': {'queue': 'reports'},
    'ai.tasks.*': {'queue': 'ai_heavy'},
    '*': {'queue': 'default'},
}

# Default queue
CELERY_TASK_DEFAULT_QUEUE = 'default'

# Beat scheduler
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# Or static schedule
from celery.schedules import crontab
CELERY_BEAT_SCHEDULE = {
    'daily-cleanup': {
        'task': 'core.tasks.cleanup_old_sessions',
        'schedule': crontab(hour=3, minute=0),
    },
}
"""


# ==========================================================================
# 4. TASK PATTERNS
# ==========================================================================

"""
# myapp/tasks.py

from celery import shared_task, group, chain
from celery.exceptions import SoftTimeLimitExceeded, MaxRetriesExceededError
from celery.utils.log import get_task_logger


logger = get_task_logger(__name__)


# Simple task
@shared_task
def send_welcome_email(user_id):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    user = User.objects.get(pk=user_id)
    # ... send email logic
    logger.info(f'Sent welcome email to {user.email}')
    return user.email


# Task with retry
@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 5},
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def fetch_external_data(self, url):
    import httpx
    try:
        resp = httpx.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            # Don't retry 404
            raise self.retry(exc=e, max_retries=0)
        raise
    except SoftTimeLimitExceeded:
        logger.warning(f'Soft time limit, task {self.request.id}')
        # Cleanup if needed
        raise


# Idempotent task
@shared_task
def charge_customer(order_id):
    from blog.models import Order

    order = Order.objects.get(pk=order_id)
    if order.status == 'paid':
        logger.info(f'Order {order_id} already paid, skipping')
        return 'already_paid'

    # Stripe charge
    # ... business logic
    order.status = 'paid'
    order.save()
    return 'paid'


# Long-running with chunked progress
@shared_task(bind=True)
def process_users_bulk(self, user_ids):
    total = len(user_ids)
    for i, uid in enumerate(user_ids):
        process_one_user(uid)

        # Update progress (custom state)
        if i % 100 == 0:
            self.update_state(
                state='PROGRESS',
                meta={'current': i, 'total': total},
            )

    return {'processed': total}


def process_one_user(uid):
    # ... business logic
    pass


# Task with custom error handling
@shared_task(bind=True, max_retries=3)
def risky_task(self, arg):
    try:
        return do_risky_thing(arg)
    except KnownTransientError as e:
        # Retry
        raise self.retry(exc=e, countdown=2 ** self.request.retries)
    except MaxRetriesExceededError:
        # Final failure — alert
        logger.error(f'Task failed permanently for arg={arg}')
        notify_ops(f'Task failed: {arg}')
        raise


def do_risky_thing(arg):
    pass


def notify_ops(msg):
    pass


class KnownTransientError(Exception):
    pass


# Periodic task
@shared_task
def cleanup_old_sessions():
    from django.contrib.sessions.models import Session
    from django.utils import timezone

    deleted = Session.objects.filter(expire_date__lt=timezone.now()).delete()
    logger.info(f'Cleaned up {deleted[0]} expired sessions')


# Task that triggers another
@shared_task
def schedule_email_for_all(template_name):
    from django.contrib.auth import get_user_model
    User = get_user_model()

    user_ids = list(User.objects.filter(is_active=True).values_list('id', flat=True))

    # Dispatch a task per user (parallel via group)
    job = group(
        send_template_email.s(uid, template_name)
        for uid in user_ids
    )
    result = job.apply_async()
    return {'queued': len(user_ids), 'group_id': result.id}


@shared_task
def send_template_email(user_id, template_name):
    pass
"""


# ==========================================================================
# 5. CANVAS — CHAIN / GROUP / CHORD
# ==========================================================================

"""
from celery import chain, group, chord


# Sequential — output passed to next
result = chain(
    fetch_data.s('https://api.example.com'),
    parse_data.s(),
    save_to_db.s(),
).apply_async()


# Parallel — multiple at once
result = group(
    process_image.s(image_id)
    for image_id in image_ids
).apply_async()
result.get()   # list of all results


# Group + callback (after all complete)
chord(
    group(fetch_url.s(url) for url in urls),
    aggregate_results.s(),
).apply_async()


# Complex workflow
workflow = chain(
    fetch_user_data.s(user_id),
    group(
        compute_metric_a.s(),
        compute_metric_b.s(),
        compute_metric_c.s(),
    ),
    combine_metrics.s(),
    send_report.s(user_id),
).apply_async()
"""


# ==========================================================================
# 6. DISPATCHING TASKS
# ==========================================================================

"""
from myapp.tasks import send_welcome_email


# Fire and forget
send_welcome_email.delay(user.id)


# With options
send_welcome_email.apply_async(
    args=[user.id],
    countdown=60,            # 60s delay
    expires=300,             # discard if not picked in 5 min
    priority=9,              # 0-9, higher = sooner (broker-dependent)
    queue='emails',
    headers={'request_id': req_id},
)


# Schedule for specific time
from datetime import datetime, timezone
send_welcome_email.apply_async(
    args=[user.id],
    eta=datetime(2026, 12, 25, 9, 0, tzinfo=timezone.utc),
)
"""


# ==========================================================================
# 7. RESULTS HANDLING
# ==========================================================================

"""
# Fire and forget
send_welcome_email.delay(user.id)


# Get result (BLOCKS — avoid in views)
result = send_welcome_email.delay(user.id)
value = result.get(timeout=10)


# Poll later (good pattern)
result = task.delay(...)
task_id = result.id

# Later (e.g., via REST endpoint)
from celery.result import AsyncResult

result = AsyncResult(task_id)
state = result.state   # PENDING, STARTED, SUCCESS, FAILURE
if result.ready():
    if result.successful():
        return result.result
    else:
        return {'error': str(result.result)}


# DB-stored result (django-celery-results)
from django_celery_results.models import TaskResult


task = TaskResult.objects.get(task_id=task_id)
"""


# ==========================================================================
# 8. ASYNC VIEW + TASK STATUS POLLING
# ==========================================================================

"""
# views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from celery.result import AsyncResult


class StartLongTaskView(APIView):
    def post(self, request):
        result = generate_report.delay(request.user.id)
        return Response({'task_id': result.id, 'status': 'started'}, status=202)


class TaskStatusView(APIView):
    def get(self, request, task_id):
        result = AsyncResult(task_id)
        if result.state == 'PENDING':
            return Response({'state': 'pending'})
        elif result.state == 'PROGRESS':
            return Response({
                'state': 'in_progress',
                **result.info,   # current, total
            })
        elif result.state == 'SUCCESS':
            return Response({
                'state': 'completed',
                'result': result.result,
            })
        elif result.state == 'FAILURE':
            return Response({
                'state': 'failed',
                'error': str(result.info),
            }, status=500)
"""


# ==========================================================================
# 9. RUNNING WORKERS (production)
# ==========================================================================

WORKER_COMMANDS = """
# Single worker
celery -A config worker -l info

# Multiple worker types
celery -A config worker -Q default -c 8 -n default@%h
celery -A config worker -Q emails -c 4 -n emails@%h
celery -A config worker -Q ai_heavy -c 2 -n ai@%h

# With autoscale
celery -A config worker --autoscale=10,3 -l info

# With concurrency strategy
celery -A config worker -P prefork -c 8       # default, multi-process
celery -A config worker -P gevent -c 100      # for I/O-bound
celery -A config worker -P solo                # single-threaded (debugging)

# Beat (periodic tasks) — separate process
celery -A config beat -l info -S django_celery_beat.schedulers:DatabaseScheduler

# Flower (monitoring UI)
celery -A config flower --port=5555

# All-in-one for dev only
celery -A config worker -l info -B   # worker + beat in same process
"""


# ==========================================================================
# 10. SYSTEMD UNIT (production)
# ==========================================================================

SYSTEMD_UNIT = """
# /etc/systemd/system/celery-default.service

[Unit]
Description=Celery default worker
After=network.target redis.service postgresql.service

[Service]
Type=forking
User=app
Group=app
EnvironmentFile=/etc/celery/celery.conf
WorkingDirectory=/app
ExecStart=/app/.venv/bin/celery -A config worker -Q default -c 8 --pidfile=/run/celery/default.pid --logfile=/var/log/celery/default.log -l info --detach
ExecStop=/bin/kill -s QUIT $MAINPID
ExecReload=/bin/kill -s HUP $MAINPID
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target


# systemctl enable celery-default
# systemctl start celery-default
"""


# ==========================================================================
# 11. KUBERNETES DEPLOYMENT
# ==========================================================================

K8S_DEPLOYMENT = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: celery-worker
spec:
  replicas: 3
  selector:
    matchLabels:
      app: celery-worker
  template:
    metadata:
      labels:
        app: celery-worker
    spec:
      containers:
      - name: worker
        image: myapp:latest
        command:
          - celery
          - -A
          - config
          - worker
          - -l
          - info
          - --concurrency=4
        env:
          - name: CELERY_BROKER_URL
            valueFrom:
              secretKeyRef:
                name: app-secrets
                key: redis-url
        resources:
          requests:
            cpu: 500m
            memory: 1Gi
          limits:
            cpu: 2
            memory: 2Gi
        livenessProbe:
          exec:
            command: ["celery", "-A", "config", "inspect", "ping"]
          periodSeconds: 60
        readinessProbe:
          exec:
            command: ["celery", "-A", "config", "inspect", "ping"]
          periodSeconds: 30


---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: celery-beat
spec:
  replicas: 1    # only ONE beat for periodic tasks!
  selector:
    matchLabels:
      app: celery-beat
  template:
    spec:
      containers:
      - name: beat
        image: myapp:latest
        command:
          - celery
          - -A
          - config
          - beat
          - -S
          - django_celery_beat.schedulers:DatabaseScheduler
"""


# ==========================================================================
# 12. TESTING
# ==========================================================================

"""
# settings/test.py
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = 'memory://'
CELERY_RESULT_BACKEND = 'cache+memory://'


# tests/test_tasks.py
from django.test import TestCase, override_settings
from myapp.tasks import send_welcome_email


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class TaskTests(TestCase):
    def test_send_welcome_email(self):
        user = User.objects.create(email='test@example.com')
        result = send_welcome_email.delay(user.id)
        self.assertEqual(result.state, 'SUCCESS')
        self.assertTrue(result.successful())


# pytest fixture
import pytest


@pytest.fixture(autouse=True)
def celery_eager(settings):
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True
"""
