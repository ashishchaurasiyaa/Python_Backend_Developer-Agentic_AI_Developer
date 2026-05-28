"""
Blog App Models
═══════════════════════════════════════════════════════
Models:
  Category  — blog categories
  Tag       — many-to-many tags
  Post      — main blog post (with SoftDelete + Timestamp)
  Comment   — threaded comments on posts

INTERVIEW Topics demonstrated:
  - ForeignKey, ManyToManyField, self-referential FK (parent comment)
  - Custom Manager + QuerySet chaining
  - Meta: indexes, constraints, ordering, verbose_name
  - Property methods on model
  - __str__ / __repr__
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from core.models import BaseModel

User = get_user_model()


# ─── Category ──────────────────────────────────────────────
class Category(models.Model):
    name        = models.CharField(max_length=100, unique=True)
    slug        = models.SlugField(max_length=100, unique=True, blank=True)
    description = models.TextField(blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table    = "blog_categories"
        verbose_name_plural = "categories"
        ordering    = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


# ─── Tag ───────────────────────────────────────────────────
class Tag(models.Model):
    name  = models.CharField(max_length=50, unique=True)
    slug  = models.SlugField(max_length=50, unique=True, blank=True)
    color = models.CharField(max_length=7, default="#3B82F6")  # hex color

    class Meta:
        db_table = "blog_tags"
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


# ─── Post QuerySet + Manager ───────────────────────────────
class PostQuerySet(models.QuerySet):
    """
    INTERVIEW: Custom QuerySet — reusable filter chains.
    Pattern: Post.objects.published().recent().with_author()
    """

    def published(self):
        from django.utils import timezone
        return self.filter(status=Post.Status.PUBLISHED, published_at__lte=timezone.now())

    def draft(self):
        return self.filter(status=Post.Status.DRAFT)

    def by_author(self, user):
        return self.filter(author=user)

    def recent(self, days: int = 30):
        from django.utils import timezone
        cutoff = timezone.now() - timezone.timedelta(days=days)
        return self.filter(published_at__gte=cutoff)

    def with_author(self):
        """Avoid N+1 when accessing post.author.name"""
        return self.select_related("author", "category")

    def with_tags(self):
        """Avoid N+1 when iterating post.tags.all()"""
        return self.prefetch_related("tags")

    def with_comment_count(self):
        """Annotate each post with its comment count."""
        from django.db.models import Count
        return self.annotate(comment_count=Count("comments", distinct=True))

    def with_all_relations(self):
        """Kitchen sink — load everything for list views."""
        return (
            self.with_author()
                .with_tags()
                .with_comment_count()
        )

    def featured(self):
        return self.filter(is_featured=True)


class PostManager(models.Manager):
    def get_queryset(self):
        # Default manager excludes soft-deleted
        return PostQuerySet(self.model, using=self._db).filter(deleted_at__isnull=True)

    def published(self):
        return self.get_queryset().published()

    def draft(self):
        return self.get_queryset().draft()

    def for_user(self, user):
        """Posts visible to this user — own drafts + all published."""
        from django.db.models import Q
        return self.get_queryset().filter(
            Q(status=Post.Status.PUBLISHED) | Q(author=user)
        ).with_author().with_tags()


# ─── Post ──────────────────────────────────────────────────
class Post(BaseModel):
    """Main blog post model."""

    class Status(models.TextChoices):
        DRAFT     = "draft",     "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED  = "archived",  "Archived"

    # Core fields
    title     = models.CharField(max_length=300)
    slug      = models.SlugField(max_length=300, unique=True, blank=True)
    content   = models.TextField()
    excerpt   = models.TextField(blank=True, max_length=500)
    cover_img = models.ImageField(upload_to="posts/covers/", null=True, blank=True)

    # Relationships
    author   = models.ForeignKey(User,     on_delete=models.CASCADE,  related_name="posts")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="posts")
    tags     = models.ManyToManyField(Tag, blank=True, related_name="posts")

    # Status
    status       = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT,
                                    db_index=True)
    is_featured  = models.BooleanField(default=False, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)

    # Counters (denormalized for performance)
    views_count = models.PositiveIntegerField(default=0)
    likes_count = models.PositiveIntegerField(default=0)

    # Reading time
    read_time_minutes = models.PositiveSmallIntegerField(default=1)

    objects = PostManager()  # custom manager

    class Meta:
        db_table = "blog_posts"
        ordering = ["-published_at", "-created_at"]
        indexes  = [
            models.Index(fields=["status", "published_at"]),
            models.Index(fields=["author", "status"]),
            models.Index(fields=["is_featured", "status"]),
        ]
        # Composite unique constraint
        constraints = [
            models.UniqueConstraint(
                fields=["slug"],
                condition=models.Q(deleted_at__isnull=True),
                name="unique_active_slug",
            )
        ]

    def save(self, *args, **kwargs):
        # Auto-generate slug from title
        if not self.slug:
            self.slug = slugify(self.title)[:280]

        # Auto-calculate reading time (avg 200 words/min)
        word_count = len(self.content.split())
        self.read_time_minutes = max(1, word_count // 200)

        super().save(*args, **kwargs)

    def publish(self):
        """Publish the post."""
        from django.utils import timezone
        self.status = self.Status.PUBLISHED
        self.published_at = timezone.now()
        self.save(update_fields=["status", "published_at", "updated_at"])

    @property
    def is_published(self) -> bool:
        return self.status == self.Status.PUBLISHED

    @property
    def short_title(self) -> str:
        return self.title[:50] + "..." if len(self.title) > 50 else self.title

    def __str__(self):
        return f"[{self.status.upper()}] {self.title}"


# ─── Comment ───────────────────────────────────────────────
class Comment(models.Model):
    """
    Blog comment with threaded replies (self-referential FK).

    INTERVIEW: self-referential FK kya hai?
      parent = ForeignKey("self", ...) — comment ka comment (reply)
      parent=None → top-level comment
      parent!=None → reply to parent

    INTERVIEW: null=True vs blank=True fark?
      null=True  — DB level: column can be NULL
      blank=True — Form/Serializer level: field not required
      For string fields: blank=True preferred (empty string vs NULL)
      For non-string (DateTime, FK): null=True + blank=True
    """
    post      = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    author    = models.ForeignKey(User, on_delete=models.CASCADE, related_name="comments")
    parent    = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies"
    )
    content    = models.TextField(max_length=2000)
    is_approved = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "blog_comments"
        ordering = ["created_at"]
        indexes  = [
            models.Index(fields=["post", "is_approved"]),
            models.Index(fields=["author"]),
        ]

    @property
    def is_reply(self) -> bool:
        return self.parent_id is not None

    def __str__(self):
        return f"Comment by {self.author.email} on '{self.post.short_title}'"
