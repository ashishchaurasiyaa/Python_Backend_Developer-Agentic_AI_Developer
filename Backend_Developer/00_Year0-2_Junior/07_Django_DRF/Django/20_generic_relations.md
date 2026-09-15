# Generic Relations & ContentTypes — Polymorphic FK

## Why It Matters (Senior 5 YOE Context)

Generic Relations = **one FK that can point to any model**. Use cases:

- **Audit log** → one table tracks changes across all models
- **Comments** → comment on Articles, Photos, Videos (polymorphic)
- **Activity feed** → "user X liked Y" where Y can be anything
- **Tagging** → tag any model
- **Notifications** → reference target object of any type

Without generic relations, you'd need N FK columns (one per related model) or N separate tables.

Senior interview: "How do you build a comments system that works on Articles, Videos, and Photos?" → GenericForeignKey.

---

## Core Concepts

### ContentType Framework Basics

```python
from django.contrib.contenttypes.models import ContentType
from blog.models import Article


# Get ContentType for a model
ct = ContentType.objects.get_for_model(Article)
print(ct.app_label, ct.model)  # 'blog', 'article'
print(ct.id)                   # numeric id stored in DB

# Resolve model from ct
ModelClass = ct.model_class()
instance = ct.get_object_for_this_type(pk=1)
```

### GenericForeignKey Model

```python
from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType


class Comment(models.Model):
    body = models.TextField()
    author = models.ForeignKey('auth.User', on_delete=models.CASCADE)

    # GFK = 3 fields: content_type + object_id + virtual GFK
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        db_index=True,
    )
    object_id = models.PositiveIntegerField(db_index=True)
    content_object = GenericForeignKey('content_type', 'object_id')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['content_type', 'object_id']),  # critical
        ]
```

### GenericRelation (Reverse Side)

```python
class Article(models.Model):
    title = models.CharField(max_length=200)
    body = models.TextField()
    # Reverse — gives article.comments.all()
    comments = GenericRelation(Comment)


class Video(models.Model):
    title = models.CharField(max_length=200)
    comments = GenericRelation(Comment)


# Usage
article = Article.objects.get(pk=1)
article.comments.all()         # all comments on this article
article.comments.create(
    body='Great!',
    author=user,
)  # content_type + object_id auto-set
```

### Adding a Comment to Any Object

```python
from django.contrib.contenttypes.models import ContentType


def add_comment(obj, user, body):
    ct = ContentType.objects.get_for_model(obj)
    return Comment.objects.create(
        body=body,
        author=user,
        content_type=ct,
        object_id=obj.pk,
    )


# Works for any model
add_comment(article, user, "Nice article!")
add_comment(video, user, "Cool video!")
```

### Querying — Comments on Specific Type

```python
# All comments on articles
ct = ContentType.objects.get_for_model(Article)
Comment.objects.filter(content_type=ct)

# All comments on a specific article (or use article.comments)
Comment.objects.filter(content_type=ct, object_id=article.pk)

# Multiple types
cts = ContentType.objects.get_for_models(Article, Video)
Comment.objects.filter(content_type__in=cts.values())
```

### Bulk Resolve Generic Targets (Avoid N+1)

```python
# Naive — N+1
for c in Comment.objects.all():
    print(c.content_object.title)  # 1 query each


# Better — manual bulk fetch
from collections import defaultdict


def resolve_targets(comments):
    by_ct = defaultdict(list)
    for c in comments:
        by_ct[c.content_type_id].append(c.object_id)

    targets = {}  # (ct_id, obj_id) → instance
    for ct_id, obj_ids in by_ct.items():
        ct = ContentType.objects.get_for_id(ct_id)
        ModelClass = ct.model_class()
        for obj in ModelClass.objects.filter(pk__in=obj_ids):
            targets[(ct_id, obj.pk)] = obj

    for c in comments:
        c.cached_target = targets.get((c.content_type_id, c.object_id))


# Better — django.contrib.contenttypes.prefetch.GenericPrefetch (Django 5.1+)
from django.contrib.contenttypes.prefetch import GenericPrefetch

comments = Comment.objects.prefetch_related(
    GenericPrefetch('content_object', [
        Article.objects.all(),
        Video.objects.all(),
    ])
)
for c in comments:
    print(c.content_object.title)  # no extra query
```

---

## How It Works Internally

### Storage Format

```sql
CREATE TABLE blog_comment (
    id SERIAL PRIMARY KEY,
    body TEXT,
    content_type_id INTEGER REFERENCES django_content_type(id),
    object_id INTEGER,
    INDEX (content_type_id, object_id)
);
```

`content_type_id` + `object_id` together identify the target object. No DB FK to target — Django enforces.

### `get_for_model()` Caching

`ContentType.objects.get_for_model(Article)` is cached per-process (since 1.7). Fast in practice.

### `GenericRelation.delete()` Cascading

```python
class Article(models.Model):
    comments = GenericRelation(Comment)


article.delete()  # comments via GenericRelation auto-deleted (CASCADE-like)
```

Without `GenericRelation`, deleting Article leaves orphan comments. Use signal or GR.

---

## Common Pitfalls

### 1. No FK Integrity at DB Level

```python
article.delete()  # without GenericRelation
# Comments still exist with dangling object_id
```

**Fix:** Always use `GenericRelation` on the parent OR cleanup signal.

### 2. Indexing — Single Field Not Enough

```python
# BAD — query slow
class Meta:
    indexes = []

# GOOD — composite index
class Meta:
    indexes = [models.Index(fields=['content_type', 'object_id'])]
```

### 3. Filtering by `content_object__field` — Doesn't Work

```python
# WRONG — can't follow GFK in filter
Comment.objects.filter(content_object__title='Hello')

# RIGHT — filter by content_type then objects
ct = ContentType.objects.get_for_model(Article)
articles = Article.objects.filter(title='Hello')
Comment.objects.filter(content_type=ct, object_id__in=articles.values('pk'))
```

### 4. Serialization in DRF

```python
class CommentSerializer(serializers.ModelSerializer):
    # Need custom field for GFK
    target_type = serializers.SerializerMethodField()
    target_id = serializers.IntegerField(source='object_id')

    def get_target_type(self, obj):
        return obj.content_type.model

    class Meta:
        model = Comment
        fields = ['id', 'body', 'target_type', 'target_id']
```

### 5. Migration Issues

```python
# Renaming model breaks ContentType references
# Use RenameModel migration which auto-updates
```

### 6. Performance — Heavy Polymorphic Lookups

GFK = lots of small JOIN/lookup overhead. For high-traffic features (likes, votes), consider separate tables per type or denormalized counters.

---

## Interview Q&A

**Q1:** GenericForeignKey use cases?
**A:** (1) Audit log — one Activity model tracks changes across all entities. (2) Polymorphic comments — comment on multiple types. (3) Notifications — target can be Article/User/Comment. (4) Tagging — tag any model. (5) Activity feeds — actor + verb + target where target varies.

**Q2:** GenericForeignKey ke trade-offs?
**A:** Pro: flexibility, single table. Con: no DB-level FK integrity (dangling references possible), can't JOIN through filter, slower than direct FK due to type+id lookup, harder to add DB constraints. Use only when polymorphism is essential.

**Q3:** Cascade delete kaise kaam karta hai GFK ke saath?
**A:** GFK doesn't cascade at DB level. Add `GenericRelation` on parent → Django ORM cascades on `.delete()`. Or attach `post_delete` signal to manually clean up. SQL-level FK does nothing for GFK.

**Q4:** N+1 GFK ke saath kaise avoid karoge?
**A:** Django 5.1+: `prefetch_related(GenericPrefetch('content_object', [QuerySet1, QuerySet2]))`. Before that: manual — group by content_type_id, bulk-fetch each type, attach in Python. Or denormalize: cache common fields in Comment table (target_title, target_url).

**Q5:** Indexing strategy for GFK?
**A:** Composite index on `(content_type_id, object_id)` — most queries filter by both. Optional partial indexes for common content types. Don't index either alone — composite covers both.

**Q6:** Audit log via GFK kaise design karoge?
**A:**
```python
class Activity(models.Model):
    actor = models.ForeignKey(User)
    verb = models.CharField()  # 'created', 'updated', 'deleted'
    target_ct = models.ForeignKey(ContentType)
    target_id = models.PositiveIntegerField()
    target = GenericForeignKey('target_ct', 'target_id')
    changes = models.JSONField()  # diff
    created_at = models.DateTimeField(auto_now_add=True)
```
Track via signals or middleware.

**Q7:** GenericRelation reverse query slow lag rahi — fix?
**A:** Check composite index. Try denormalization: store comment_count column on Article + signal updater. For very hot queries, use materialized view aggregating per-target counts.

**Q8:** Polymorphic FK alternative — Django mein kya?
**A:** (1) GenericForeignKey (built-in, simple). (2) `django-polymorphic` package (true OOP polymorphism, models inherit). (3) Concrete FK per type (denormalized, multiple nullable FKs). (4) JSON field with `{type, id}` (no Django ORM benefits).

---

## Real-World Use Cases

### 1. Universal Audit Log

```python
class Activity(models.Model):
    actor = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)
    verb = models.CharField(max_length=20)  # 'create', 'update', 'delete'

    target_ct = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    target_id = models.PositiveIntegerField()
    target = GenericForeignKey('target_ct', 'target_id')

    changes = models.JSONField(default=dict)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [models.Index(fields=['target_ct', 'target_id'])]


# Signal handler — log all model changes
@receiver(post_save)
def log_save(sender, instance, created, **kwargs):
    if not isinstance(instance, models.Model):
        return
    if sender._meta.app_label in {'auth', 'sessions', 'contenttypes'}:
        return
    Activity.objects.create(
        actor=getattr(instance, 'last_modified_by', None),
        verb='create' if created else 'update',
        target_ct=ContentType.objects.get_for_model(sender),
        target_id=instance.pk,
    )
```

### 2. Notifications

```python
class Notification(models.Model):
    recipient = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    actor = models.ForeignKey('auth.User', related_name='triggered_notifications', on_delete=models.CASCADE)
    verb = models.CharField(max_length=50)

    target_ct = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    target_id = models.PositiveIntegerField()
    target = GenericForeignKey('target_ct', 'target_id')

    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


# When user comments on article:
Notification.objects.create(
    recipient=article.author,
    actor=commenter,
    verb='commented on',
    target=article,
)
```

### 3. Tags via GR

```python
class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)


class TaggedItem(models.Model):
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')


class Article(models.Model):
    tags = GenericRelation(TaggedItem)
```

---

## References

- [Django ContentTypes framework](https://docs.djangoproject.com/en/5.0/ref/contrib/contenttypes/)
- [`django-activity-stream`](https://github.com/justquick/django-activity-stream) — activity feeds with GFK
- [`django-taggit`](https://github.com/jazzband/django-taggit) — generic tagging
- Real-world example: GitHub's notification model is GFK-based
