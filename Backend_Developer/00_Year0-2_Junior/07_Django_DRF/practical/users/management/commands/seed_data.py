"""
Custom Management Command — seed_data
══════════════════════════════════════
INTERVIEW: Management commands kab use karte hain?
  - Initial data seeding (dev/staging)
  - Data migrations with complex business logic
  - Batch processing (cleanup, backfill, report generation)
  - Scheduled tasks (cron via Celery Beat OR crontab + manage.py)

INTERVIEW: BaseCommand ka structure?
  help         = one-line description
  add_arguments() = argparse-style CLI args
  handle()     = main logic

INTERVIEW: transaction.atomic() + dry-run pattern?
  dry_run mode: run all logic inside transaction, then rollback
  → Test exactly what WOULD happen without touching DB

Usage:
  python manage.py seed_data
  python manage.py seed_data --users=50 --posts=200
  python manage.py seed_data --dry-run
"""

import random
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone


FIRST_NAMES = ["Alice", "Bob", "Charlie", "Diana", "Evan", "Fiona", "George", "Hannah"]
LAST_NAMES  = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller"]
ROLES       = ["user", "user", "user", "moderator", "admin"]
PLANS       = ["free", "free", "premium", "enterprise"]
CATEGORIES  = ["Python", "Django", "FastAPI", "System Design", "Databases", "AI/ML"]
TAGS        = ["python", "django", "fastapi", "rest-api", "postgresql", "redis",
               "celery", "docker", "kubernetes", "ai", "llm", "tutorial"]


class Command(BaseCommand):
    help = "Seed development database with test data"

    def add_arguments(self, parser):
        parser.add_argument("--users",  type=int, default=10,  help="Number of users to create")
        parser.add_argument("--posts",  type=int, default=30,  help="Number of posts to create")
        parser.add_argument("--dry-run", action="store_true",  help="Preview without DB changes")
        parser.add_argument("--clear",   action="store_true",  help="Clear existing data first")

    def handle(self, *args, **options):
        user_count  = options["users"]
        post_count  = options["posts"]
        dry_run     = options["dry_run"]
        clear_first = options["clear"]

        self.stdout.write(
            self.style.WARNING(f"Seeding: {user_count} users, {post_count} posts "
                               f"[dry_run={dry_run}]")
        )

        try:
            with transaction.atomic():
                if clear_first:
                    self._clear_data()

                users      = self._create_users(user_count)
                categories = self._create_categories()
                tags       = self._create_tags()
                posts      = self._create_posts(users, categories, tags, post_count)

                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Created: {len(users)} users, {len(categories)} categories, "
                        f"{len(tags)} tags, {len(posts)} posts"
                    )
                )

                if dry_run:
                    # Rollback — preview only
                    transaction.set_rollback(True)
                    self.stdout.write(self.style.WARNING("DRY RUN — no changes saved"))

        except Exception as e:
            raise CommandError(f"Seeding failed: {e}") from e

    def _clear_data(self):
        from blog.models import Post, Category, Tag, Comment
        from django.contrib.auth import get_user_model
        User = get_user_model()

        Post.objects.all_with_deleted().hard_delete()
        Comment.objects.all().delete()
        Category.objects.all().delete()
        Tag.objects.all().delete()
        User.objects.filter(is_staff=False).delete()
        self.stdout.write("  ✓ Cleared existing data")

    def _create_users(self, count: int) -> list:
        from django.contrib.auth import get_user_model
        User = get_user_model()

        users = []
        for i in range(count):
            first = random.choice(FIRST_NAMES)
            last  = random.choice(LAST_NAMES)
            email = f"{first.lower()}.{last.lower()}{i}@example.com"

            if User.objects.filter(email=email).exists():
                continue

            user = User.objects.create_user(
                email=email,
                password="TestPass123!",
                first_name=first,
                last_name=last,
                role=random.choice(ROLES),
                plan=random.choice(PLANS),
                is_email_verified=random.choice([True, True, False]),
            )
            users.append(user)

        # Always create a known test admin
        admin, _ = User.objects.get_or_create(
            email="admin@example.com",
            defaults={
                "first_name": "Admin",
                "last_name": "User",
                "role": "admin",
                "plan": "enterprise",
                "is_staff": True,
                "is_superuser": True,
                "is_email_verified": True,
            },
        )
        admin.set_password("Admin123!")
        admin.save()

        self.stdout.write(f"  ✓ {len(users)} users  (admin@example.com / Admin123!)")
        return users

    def _create_categories(self) -> list:
        from blog.models import Category
        cats = []
        for name in CATEGORIES:
            cat, _ = Category.objects.get_or_create(name=name)
            cats.append(cat)
        self.stdout.write(f"  ✓ {len(cats)} categories")
        return cats

    def _create_tags(self) -> list:
        from blog.models import Tag
        tags = []
        for name in TAGS:
            tag, _ = Tag.objects.get_or_create(name=name)
            tags.append(tag)
        self.stdout.write(f"  ✓ {len(tags)} tags")
        return tags

    def _create_posts(self, users, categories, tags, count: int) -> list:
        from blog.models import Post

        if not users:
            self.stdout.write(self.style.WARNING("  No users — skipping posts"))
            return []

        posts = []
        for i in range(count):
            author   = random.choice(users)
            category = random.choice(categories)
            status   = random.choice(["published", "published", "draft"])
            title    = f"Post #{i+1}: {random.choice(CATEGORIES)} Deep Dive"
            content  = f"This is the content of post {i+1}. " * 50  # ~250 words

            post = Post(
                title=title,
                content=content,
                excerpt=f"A deep dive into {category.name} best practices.",
                author=author,
                category=category,
                status=status,
                is_featured=(i % 10 == 0),
                views_count=random.randint(0, 5000),
                likes_count=random.randint(0, 200),
            )

            if status == "published":
                post.published_at = timezone.now() - timezone.timedelta(
                    days=random.randint(0, 365)
                )

            post.save()

            # Assign 2-4 random tags
            post.tags.set(random.sample(tags, k=random.randint(2, min(4, len(tags)))))
            posts.append(post)

        self.stdout.write(f"  ✓ {len(posts)} posts")
        return posts
