"""
Generic Relations — Production Patterns

Polymorphic Comment, Audit Log, Notification system.
"""

# ==========================================================================
# 1. POLYMORPHIC COMMENT (works on any model)
# ==========================================================================

from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType


class Comment(models.Model):
    body = models.TextField()
    author = models.ForeignKey('auth.User', on_delete=models.CASCADE)

    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        db_index=True,
    )
    object_id = models.PositiveIntegerField(db_index=True)
    content_object = GenericForeignKey('content_type', 'object_id')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'blog'
        indexes = [
            models.Index(fields=['content_type', 'object_id', '-created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f'Comment by {self.author} on {self.content_object}'


# Models that can be commented on
class Article(models.Model):
    title = models.CharField(max_length=200)
    body = models.TextField()
    author = models.ForeignKey('auth.User', on_delete=models.CASCADE)

    # Reverse — gives article.comments.all()
    comments = GenericRelation(Comment, related_query_name='article')

    class Meta:
        app_label = 'blog'

    def __str__(self):
        return self.title


class Video(models.Model):
    title = models.CharField(max_length=200)
    url = models.URLField()
    comments = GenericRelation(Comment, related_query_name='video')

    class Meta:
        app_label = 'blog'


class Photo(models.Model):
    image = models.ImageField()
    comments = GenericRelation(Comment, related_query_name='photo')

    class Meta:
        app_label = 'blog'


# ==========================================================================
# 2. HELPER FUNCTIONS
# ==========================================================================

def add_comment(target_obj, author, body):
    """Add a comment to ANY model instance."""
    return Comment.objects.create(
        body=body,
        author=author,
        content_type=ContentType.objects.get_for_model(target_obj),
        object_id=target_obj.pk,
    )


def get_comments_for(target_obj):
    """Fetch all comments on a target."""
    return Comment.objects.filter(
        content_type=ContentType.objects.get_for_model(target_obj),
        object_id=target_obj.pk,
    ).select_related('author').order_by('-created_at')


# Usage
# article = Article.objects.first()
# add_comment(article, request.user, "Great article!")
# article.comments.all()  # via GenericRelation


# ==========================================================================
# 3. AUDIT LOG — Universal change tracking
# ==========================================================================

class Activity(models.Model):
    """Generic activity log — works for any model."""

    actor = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)
    verb = models.CharField(max_length=20)  # 'create', 'update', 'delete'

    target_ct = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    target_id = models.PositiveIntegerField()
    target = GenericForeignKey('target_ct', 'target_id')

    changes = models.JSONField(default=dict, blank=True)  # diff
    metadata = models.JSONField(default=dict, blank=True)  # IP, user agent, etc

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = 'blog'
        indexes = [
            models.Index(fields=['target_ct', 'target_id', '-created_at']),
            models.Index(fields=['actor', '-created_at']),
        ]
        ordering = ['-created_at']


# ==========================================================================
# 4. SIGNAL-BASED AUDIT TRACKING
# ==========================================================================

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

# Track these models
AUDITED_MODELS = ('Article', 'Video', 'Photo', 'Order')


def _should_audit(sender):
    return sender.__name__ in AUDITED_MODELS


@receiver(post_save)
def log_save(sender, instance, created, **kwargs):
    if not _should_audit(sender):
        return
    Activity.objects.create(
        actor=getattr(instance, '_audit_actor', None),
        verb='create' if created else 'update',
        target_ct=ContentType.objects.get_for_model(sender),
        target_id=instance.pk,
        changes=getattr(instance, '_audit_changes', {}),
    )


@receiver(post_delete)
def log_delete(sender, instance, **kwargs):
    if not _should_audit(sender):
        return
    Activity.objects.create(
        actor=getattr(instance, '_audit_actor', None),
        verb='delete',
        target_ct=ContentType.objects.get_for_model(sender),
        target_id=instance.pk,
    )


# ==========================================================================
# 5. NOTIFICATIONS
# ==========================================================================

class Notification(models.Model):
    recipient = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='notifications')
    actor = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='triggered_notifications')

    verb = models.CharField(max_length=50)  # 'commented on', 'liked', 'mentioned'

    target_ct = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True)
    target_id = models.PositiveIntegerField(null=True)
    target = GenericForeignKey('target_ct', 'target_id')

    read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = 'blog'
        indexes = [
            models.Index(fields=['recipient', 'read', '-created_at']),
        ]
        ordering = ['-created_at']


def notify(recipient, actor, verb, target=None):
    return Notification.objects.create(
        recipient=recipient,
        actor=actor,
        verb=verb,
        target_ct=ContentType.objects.get_for_model(target) if target else None,
        target_id=target.pk if target else None,
    )


# Usage
# when commenter posts on article:
# notify(article.author, commenter, 'commented on', target=article)


# ==========================================================================
# 6. BULK GFK RESOLUTION (avoid N+1)
# ==========================================================================

from collections import defaultdict


def prefetch_generic_targets(items, gfk_field='content_object'):
    """
    Manually prefetch GFK targets to avoid N+1.

    Usage:
        comments = list(Comment.objects.all()[:100])
        prefetch_generic_targets(comments)
        for c in comments:
            c._target  # already loaded
    """
    by_ct = defaultdict(list)
    for item in items:
        ct_id = getattr(item, f'{gfk_field}_ct_id', None) or item.content_type_id
        obj_id = getattr(item, f'{gfk_field}_object_id', None) or item.object_id
        by_ct[ct_id].append(obj_id)

    # Bulk fetch per type
    targets = {}
    for ct_id, obj_ids in by_ct.items():
        ct = ContentType.objects.get_for_id(ct_id)
        ModelClass = ct.model_class()
        if ModelClass is None:
            continue
        for obj in ModelClass.objects.filter(pk__in=obj_ids):
            targets[(ct_id, obj.pk)] = obj

    # Attach
    for item in items:
        ct_id = getattr(item, 'content_type_id', None)
        obj_id = getattr(item, 'object_id', None)
        item._target = targets.get((ct_id, obj_id))


# Django 5.1+: GenericPrefetch (cleaner)
"""
from django.contrib.contenttypes.prefetch import GenericPrefetch

comments = Comment.objects.prefetch_related(
    GenericPrefetch('content_object', [
        Article.objects.select_related('author'),
        Video.objects.all(),
        Photo.objects.all(),
    ])
)
for c in comments:
    print(c.content_object)  # no extra query
"""


# ==========================================================================
# 7. DRF SERIALIZATION OF GFK
# ==========================================================================

from rest_framework import serializers


class CommentGFKSerializer(serializers.ModelSerializer):
    """Serialize Comment with GFK target."""

    target_type = serializers.SerializerMethodField()
    target_id = serializers.IntegerField(source='object_id', read_only=True)
    target = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ['id', 'body', 'author', 'target_type', 'target_id', 'target', 'created_at']
        read_only_fields = ['target_type', 'target_id', 'target', 'created_at']

    def get_target_type(self, obj):
        return obj.content_type.model

    def get_target(self, obj):
        target = obj.content_object
        if target is None:
            return None
        # Serialize based on type
        if isinstance(target, Article):
            return {'id': target.pk, 'title': target.title, 'type': 'article'}
        if isinstance(target, Video):
            return {'id': target.pk, 'title': target.title, 'type': 'video'}
        return {'id': target.pk, 'type': obj.content_type.model}


# ==========================================================================
# 8. QUERIES — FILTERING BY TARGET TYPE
# ==========================================================================

# All comments on articles
# article_ct = ContentType.objects.get_for_model(Article)
# article_comments = Comment.objects.filter(content_type=article_ct)

# All comments on a specific article
# article = Article.objects.first()
# article_comments = article.comments.all()

# All comments by user across all targets
# user_comments = Comment.objects.filter(author=user)

# All activities on a specific user's articles
# user_articles_ct = ContentType.objects.get_for_model(Article)
# user_article_ids = Article.objects.filter(author=user).values('pk')
# Activity.objects.filter(target_ct=user_articles_ct, target_id__in=user_article_ids)


# ==========================================================================
# 9. CLEANUP ORPHANED REFERENCES
# ==========================================================================

# Mgmt command to detect/clean orphaned GFK references
"""
File: ops/management/commands/cleanup_orphan_comments.py
"""

from django.core.management.base import BaseCommand


class CleanupOrphanComments(BaseCommand):
    help = "Delete comments whose target object no longer exists"

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        from blog.models import Comment

        orphans = []
        for c in Comment.objects.iterator(chunk_size=1000):
            if c.content_object is None:
                orphans.append(c.pk)

        self.stdout.write(f"Found {len(orphans)} orphan comments")

        if options['dry_run']:
            return

        from django.db import transaction
        with transaction.atomic():
            Comment.objects.filter(pk__in=orphans).delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {len(orphans)}"))
