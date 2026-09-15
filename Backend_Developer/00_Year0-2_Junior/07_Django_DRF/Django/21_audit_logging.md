# Audit Logging — Django Production Patterns

## Why It Matters (Senior 5 YOE Context)

Audit log = **regulatory + debugging + security necessity**:

- **Compliance** → GDPR, SOC 2, HIPAA require "who changed what, when"
- **Debug** → "production data looks wrong, who modified it 3 days ago?"
- **Security** → detect insider abuse, unauthorized access
- **Customer support** → "user says they didn't change X" — verify

Senior interview: "Sensitive customer data field changed without trace. How do you prevent recurrence?" → audit log.

---

## Core Concepts

### Library Options Comparison

| Library | Granularity | Storage | Best For |
|---|---|---|---|
| `django-simple-history` | Per-row snapshots | Mirror tables | Time-travel queries |
| `django-auditlog` | Per-change records | Generic log table | Activity feed |
| `django-reversion` | Versioned objects | JSON + revisions | Rollback support |
| Custom signal-based | Flexible | Your choice | Specific needs |

### django-simple-history (Mirror Tables)

```python
# pip install django-simple-history
INSTALLED_APPS += ['simple_history']
MIDDLEWARE += ['simple_history.middleware.HistoryRequestMiddleware']


from django.db import models
from simple_history.models import HistoricalRecords


class Article(models.Model):
    title = models.CharField(max_length=200)
    body = models.TextField()
    author = models.ForeignKey('auth.User', on_delete=models.CASCADE)

    history = HistoricalRecords()  # creates HistoricalArticle table
```

Each save creates a snapshot. Query history:

```python
article = Article.objects.get(pk=1)

# All historical versions
article.history.all()

# State at specific time
historical = article.history.as_of(datetime(2026, 1, 1))

# Who changed and what
for h in article.history.all():
    print(h.history_date, h.history_user, h.history_change_reason)

# Diff between versions
new_record = article.history.first()
old_record = new_record.prev_record
delta = new_record.diff_against(old_record)
for change in delta.changes:
    print(f"{change.field} changed from {change.old} to {change.new}")
```

### django-auditlog (Generic Log)

```python
# pip install django-auditlog
INSTALLED_APPS += ['auditlog']
MIDDLEWARE += ['auditlog.middleware.AuditlogMiddleware']


from auditlog.registry import auditlog


# Register models
auditlog.register(Article, exclude_fields=['view_count'])
auditlog.register(User, mask_fields=['password', 'email'])


# Query
from auditlog.models import LogEntry

for entry in LogEntry.objects.get_for_object(article):
    print(entry.action, entry.changes_dict, entry.actor, entry.timestamp)
```

### Custom Audit via Signals (Flexible)

```python
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType


class Activity(models.Model):
    actor = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)
    verb = models.CharField(max_length=20)  # 'create', 'update', 'delete'
    target_ct = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    target_id = models.PositiveIntegerField()
    changes = models.JSONField(default=dict)
    metadata = models.JSONField(default=dict)  # IP, user-agent, request_id
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)


# Capture "before" state in pre_save
@receiver(pre_save, sender=Article)
def capture_old_state(sender, instance, **kwargs):
    if instance.pk:
        try:
            old = Article.objects.get(pk=instance.pk)
            instance._audit_old = {
                f.name: getattr(old, f.name)
                for f in sender._meta.fields
            }
        except Article.DoesNotExist:
            instance._audit_old = {}
    else:
        instance._audit_old = {}


@receiver(post_save, sender=Article)
def log_article_change(sender, instance, created, **kwargs):
    changes = {}
    old = getattr(instance, '_audit_old', {})
    for field in sender._meta.fields:
        old_val = old.get(field.name)
        new_val = getattr(instance, field.name)
        if old_val != new_val:
            changes[field.name] = {'old': str(old_val), 'new': str(new_val)}

    if changes or created:
        Activity.objects.create(
            actor=getattr(instance, '_audit_actor', None),
            verb='create' if created else 'update',
            target_ct=ContentType.objects.get_for_model(sender),
            target_id=instance.pk,
            changes=changes,
        )
```

### Auditable Mixin Pattern

```python
class AuditableModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='+',
    )
    updated_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='+',
    )

    class Meta:
        abstract = True


# Use everywhere
class Article(AuditableModel):
    title = models.CharField(max_length=200)


# Set audit user via middleware
class AuditUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Set current user on thread-local
        from . import _audit_local
        _audit_local.user = request.user if request.user.is_authenticated else None
        try:
            return self.get_response(request)
        finally:
            _audit_local.user = None


# Override save to inject user
def audited_save(instance, *args, **kwargs):
    from . import _audit_local
    user = getattr(_audit_local, 'user', None)
    if user:
        if not instance.pk:
            instance.created_by = user
        instance.updated_by = user
    super(type(instance), instance).save(*args, **kwargs)
```

---

## How It Works Internally

### simple-history Storage

Creates `historical_<modelname>` table mirroring original + adds:

- `history_id` (PK of history table)
- `history_date` (when this version was saved)
- `history_change_reason`
- `history_type` ('+' = create, '~' = update, '-' = delete)
- `history_user_id`

Storage cost: ~2x the original table size over time. Plan retention.

### auditlog Storage

Single `auditlog_logentry` table with:

- `object_pk`, `content_type` (target object)
- `action` (create/update/delete)
- `changes_text` (JSON diff)
- `actor`, `timestamp`, `remote_addr`

Much smaller storage; harder time-travel queries.

### Thread-Local for Audit User

```python
# Common pattern — middleware sets thread-local
import threading


_thread_local = threading.local()


def get_current_user():
    return getattr(_thread_local, 'user', None)


class CurrentUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _thread_local.user = request.user if request.user.is_authenticated else None
        try:
            return self.get_response(request)
        finally:
            _thread_local.user = None
```

**Async caveat:** Use `contextvars` instead of thread-local for async views.

---

## Common Pitfalls

### 1. Storage Explosion

```python
# Article table: 1M rows × avg row size 5KB = 5GB
# History table after 1 year: 50M rows × 5KB = 250GB
```

**Fix:** Retention policy + archival:

```python
# Mgmt command — delete history older than 2 years
HistoricalArticle.objects.filter(history_date__lt=cutoff).delete()
```

### 2. Sensitive Field Logging

Logging password, SSN, API keys = security risk if log table compromised:

```python
auditlog.register(User, mask_fields=['password', 'ssn', 'api_key'])
# Stored as '***'
```

### 3. Audit User Not Captured in Background Tasks

Celery tasks have no request → no user. Pass explicitly:

```python
@shared_task
def update_article_task(article_id, user_id):
    user = User.objects.get(pk=user_id)
    article = Article.objects.get(pk=article_id)
    article._audit_actor = user
    article.title = 'New'
    article.save()
```

### 4. Signal Doesn't Fire on `update()`

```python
Article.objects.filter(...).update(title='x')  # NO signal, NO audit
```

**Fix:** Force `.save()` per-instance OR use `bulk_update` + manual audit.

### 5. Race Condition in pre_save Hook

```python
# Two requests simultaneously update same row
# Both load same "old" state → audit log shows both as if from same baseline
```

**Fix:** Use `select_for_update` for serialized updates, or accept eventual consistency in audit.

### 6. Audit Table Without Indexes

Most queries: `WHERE target_ct=X AND target_id=Y ORDER BY created_at DESC`. Without composite index → table scan.

---

## Interview Q&A

**Q1:** Compliance ke liye audit log mandatory hai. Django mein approaches batao.
**A:** Three patterns: (1) **simple-history** — full row snapshots, time-travel queries, ~2x storage. (2) **auditlog** — diff logs, single generic table, smaller storage. (3) **Custom signals + Activity model** — flexible, project-specific. Choose simple-history for compliance (full snapshot for legal), auditlog for activity feeds, custom for specific needs.

**Q2:** Audit log mein password / sensitive fields kaise handle karoge?
**A:** `mask_fields` / `exclude_fields` in registration. Never log raw secrets. For PII (email, phone), consider tokenization. Audit DB itself should be access-restricted (separate DB, KMS-encrypted backups).

**Q3:** Storage explosion ka solution kya?
**A:** Retention policy — delete history older than X (legal min: usually 1-7 years). Partitioning by month (TimescaleDB or pg native). Archive to S3 + Glacier for long-term. Compress JSON changes. Monitor table growth.

**Q4:** Celery task se audit user kaise capture karoge?
**A:** Pass `actor_id` as task arg. Set on instance before save: `instance._audit_actor = User.objects.get(pk=actor_id)`. Or use context manager that sets thread-local within task scope.

**Q5:** `.update()` audit nahi karta — workaround?
**A:** Option 1: Refuse bulk updates on audited models (code review). Option 2: Override Manager `.update()` to log first. Option 3: Use database triggers (most reliable, language-agnostic). Option 4: Switch to per-instance saves with `select_for_update`.

**Q6:** Async views mein audit user kaise track karoge?
**A:** `contextvars` instead of `threading.local`. ContextVar is async-aware — auto-propagates through `await`:
```python
from contextvars import ContextVar
current_user: ContextVar = ContextVar('current_user', default=None)
```
Middleware sets it; signals read it.

**Q7:** Database trigger vs Django signal for audit — kya behtar?
**A:** Trigger pros: catches direct SQL, raw queries, `update()`, all paths. Trigger cons: PostgreSQL/MySQL-specific, less Pythonic, harder to test. Signal pros: rich Python context, easier to test. Signal cons: bypassed by raw SQL/`update()`. For compliance-grade audit: triggers. For app-level: signals.

**Q8:** Audit log queryable kaise rakhoge for support team?
**A:** (1) Composite index on `(target_ct, target_id, -created_at)`. (2) Admin interface with filters (target type, actor, date range). (3) Read-replica for analytics queries. (4) Materialized view for common aggregations (changes per user per day). (5) Export to data warehouse for BI.

---

## Real-World Use Cases

### 1. GDPR Right-to-Access

Customer asks: "Show me all data and changes about me." Use audit log:

```python
def gdpr_export(user_id):
    user = User.objects.get(pk=user_id)
    changes = Activity.objects.filter(
        target_ct=ContentType.objects.get_for_model(User),
        target_id=user_id,
    )
    return {
        'profile': UserSerializer(user).data,
        'changes': [{'when': c.created_at, 'what': c.changes} for c in changes],
    }
```

### 2. Tampering Detection

```python
# Cryptographically sign each audit entry
import hmac, hashlib

class AuditEntry(models.Model):
    # ... fields
    signature = models.CharField(max_length=64)

    def save(self, *args, **kwargs):
        if not self.signature:
            payload = f'{self.actor_id}|{self.verb}|{self.target_id}|{self.created_at}'
            self.signature = hmac.new(
                settings.AUDIT_HMAC_KEY.encode(),
                payload.encode(),
                hashlib.sha256,
            ).hexdigest()
        super().save(*args, **kwargs)
```

### 3. Change Approval Workflow

```python
# Before write: stage in PendingChange. Approver clicks → apply + audit.
class PendingChange(models.Model):
    actor = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    target_ct = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    target_id = models.PositiveIntegerField()
    changes = models.JSONField()
    status = models.CharField(default='pending')
    approved_by = models.ForeignKey('auth.User', null=True, on_delete=models.SET_NULL)
```

---

## References

- [django-simple-history docs](https://django-simple-history.readthedocs.io/)
- [django-auditlog docs](https://django-auditlog.readthedocs.io/)
- [django-reversion docs](https://django-reversion.readthedocs.io/)
- AWS GuardDuty + CloudTrail patterns for audit
