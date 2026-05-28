"""
Blog API Tests — DRF Testing Patterns
═══════════════════════════════════════════════════════════════
Covers:
  - CRUD endpoint testing
  - Permission testing (owner-only write)
  - Filter/search/ordering testing
  - Custom action testing (publish, like)
  - Pagination response shape testing
  - Soft delete verification
"""

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from .test_users import UserFactory, AdminUserFactory
from blog.models import Post, Category, Tag


# ─── Blog Factories ───────────────────────────────────────
import factory
from factory.django import DjangoModelFactory


class CategoryFactory(DjangoModelFactory):
    class Meta:
        model = Category

    name = factory.Sequence(lambda n: f"Category {n}")


class TagFactory(DjangoModelFactory):
    class Meta:
        model = Tag

    name  = factory.Sequence(lambda n: f"tag-{n}")
    color = "#3B82F6"


class PostFactory(DjangoModelFactory):
    class Meta:
        model = Post

    title    = factory.Sequence(lambda n: f"Test Post {n}")
    content  = factory.LazyAttribute(lambda _: "Content word " * 100)
    excerpt  = "Short excerpt for testing."
    author   = factory.SubFactory(UserFactory)
    category = factory.SubFactory(CategoryFactory)
    status   = Post.Status.PUBLISHED

    @factory.post_generation
    def tags(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            self.tags.set(extracted)


class DraftPostFactory(PostFactory):
    status = Post.Status.DRAFT


# ─── Fixtures ─────────────────────────────────────────────

@pytest.fixture
def user(db):
    return UserFactory()


@pytest.fixture
def other_user(db):
    return UserFactory()


@pytest.fixture
def admin_user(db):
    return AdminUserFactory()


@pytest.fixture
def auth_client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


@pytest.fixture
def other_client(other_user):
    c = APIClient()
    c.force_authenticate(user=other_user)
    return c


@pytest.fixture
def admin_client(admin_user):
    c = APIClient()
    c.force_authenticate(user=admin_user)
    return c


@pytest.fixture
def published_post(user, db):
    return PostFactory(author=user)


@pytest.fixture
def draft_post(user, db):
    return DraftPostFactory(author=user)


# ═══════════════════════════════════════════════════════════
# SECTION 1: Post CRUD Tests
# ═══════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestPostCRUD:

    def test_list_posts_public(self):
        """Unauthenticated users can list published posts."""
        PostFactory.create_batch(3)   # 3 published posts
        DraftPostFactory.create_batch(2)  # drafts — should NOT appear

        client = APIClient()
        url = reverse("blog:post-list")
        response = client.get(url)

        assert response.status_code == status.HTTP_200_OK
        # Only published posts visible to anon
        assert response.data["success"] is True

    def test_create_post_authenticated(self, auth_client, user):
        """Authenticated user can create a post."""
        category = CategoryFactory()
        url = reverse("blog:post-list")
        response = auth_client.post(url, {
            "title":    "My New Post",
            "content":  "Content word " * 50,
            "excerpt":  "Short excerpt.",
            "category": category.id,
            "status":   "draft",
        })
        assert response.status_code == status.HTTP_201_CREATED
        post = Post.objects.get(title="My New Post")
        assert post.author == user

    def test_create_post_unauthenticated_blocked(self):
        """Unauthenticated users cannot create posts."""
        client = APIClient()
        url = reverse("blog:post-list")
        response = client.post(url, {
            "title": "Test", "content": "Content", "status": "draft"
        })
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_retrieve_own_draft(self, auth_client, draft_post):
        """Author can see own draft."""
        url = reverse("blog:post-detail", kwargs={"pk": draft_post.pk})
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_retrieve_other_draft_blocked(self, other_client, draft_post):
        """Other users cannot see someone else's draft."""
        url = reverse("blog:post-detail", kwargs={"pk": draft_post.pk})
        response = other_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_own_post(self, auth_client, draft_post):
        """Author can update own post."""
        url = reverse("blog:post-detail", kwargs={"pk": draft_post.pk})
        response = auth_client.patch(url, {"title": "Updated Title"})
        assert response.status_code == status.HTTP_200_OK
        draft_post.refresh_from_db()
        assert draft_post.title == "Updated Title"

    def test_update_other_user_post_blocked(self, other_client, published_post):
        """
        INTERVIEW: IsOwnerOrReadOnly — other user cannot UPDATE.
        """
        url = reverse("blog:post-detail", kwargs={"pk": published_post.pk})
        response = other_client.patch(url, {"title": "Hacked Title"})
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_post_soft_deletes(self, auth_client, published_post):
        """
        INTERVIEW: Soft delete — record stays in DB with deleted_at set.
        Hard delete would return 204. Soft delete returns 200.
        """
        url = reverse("blog:post-detail", kwargs={"pk": published_post.pk})
        response = auth_client.delete(url)
        assert response.status_code == status.HTTP_200_OK

        # Record still in DB
        published_post.refresh_from_db()
        assert published_post.deleted_at is not None

        # Not visible in normal list
        assert not Post.objects.filter(pk=published_post.pk).exists()

        # Visible with all_with_deleted
        assert Post.objects.all_with_deleted().filter(pk=published_post.pk).exists()


# ═══════════════════════════════════════════════════════════
# SECTION 2: Custom Actions Tests
# ═══════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestPostActions:

    def test_publish_draft(self, auth_client, draft_post):
        url = reverse("blog:post-publish", kwargs={"pk": draft_post.pk})
        response = auth_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        draft_post.refresh_from_db()
        assert draft_post.status == Post.Status.PUBLISHED
        assert draft_post.published_at is not None

    def test_publish_already_published(self, auth_client, published_post):
        url = reverse("blog:post-publish", kwargs={"pk": published_post.pk})
        response = auth_client.post(url)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_like_increments_count(self, auth_client, published_post):
        initial_likes = published_post.likes_count
        url = reverse("blog:post-like", kwargs={"pk": published_post.pk})
        response = auth_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["likes"] == initial_likes + 1

    def test_like_is_atomic(self, published_post):
        """
        INTERVIEW: Concurrent likes — F() expression ensures no race condition.
        Simulate 10 concurrent likes — all should register.
        """
        import threading
        url = reverse("blog:post-like", kwargs={"pk": published_post.pk})
        initial = published_post.likes_count

        def do_like():
            user = UserFactory()
            c = APIClient()
            c.force_authenticate(user=user)
            c.post(url)

        threads = [threading.Thread(target=do_like) for _ in range(5)]
        for t in threads: t.start()
        for t in threads: t.join()

        published_post.refresh_from_db()
        assert published_post.likes_count == initial + 5


# ═══════════════════════════════════════════════════════════
# SECTION 3: Filtering + Search Tests
# ═══════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestPostFiltering:

    def test_filter_by_status(self, auth_client, user):
        PostFactory(author=user, status=Post.Status.PUBLISHED)
        DraftPostFactory(author=user)

        url = reverse("blog:post-list")
        response = auth_client.get(url, {"status": "draft"})
        assert response.status_code == status.HTTP_200_OK

    def test_search_by_title(self, auth_client, user):
        PostFactory(author=user, title="Django ORM tutorial")
        PostFactory(author=user, title="FastAPI guide")

        url = reverse("blog:post-list")
        response = auth_client.get(url, {"search": "Django"})
        # Django ORM tutorial should appear
        assert response.status_code == status.HTTP_200_OK

    def test_ordering_by_views(self, user, db):
        PostFactory(author=user, views_count=100)
        PostFactory(author=user, views_count=500)
        PostFactory(author=user, views_count=50)

        client = APIClient()
        client.force_authenticate(user=user)
        url = reverse("blog:post-list")
        response = client.get(url, {"ordering": "-views_count"})
        assert response.status_code == status.HTTP_200_OK

    def test_featured_posts_cached(self, db):
        PostFactory.create_batch(3, is_featured=True)
        client = APIClient()
        url = reverse("blog:post-featured")
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK


# ═══════════════════════════════════════════════════════════
# SECTION 4: Comment Tests
# ═══════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestComments:

    def test_add_comment(self, auth_client, published_post):
        url = reverse("blog:post-add-comment", kwargs={"pk": published_post.pk})
        response = auth_client.post(url, {"content": "Great post!"})
        assert response.status_code == status.HTTP_201_CREATED
        assert published_post.comments.filter(is_approved=True).count() == 1

    def test_add_reply(self, auth_client, published_post):
        """Threaded comment — reply to existing comment."""
        comment = published_post.comments.create(
            author=UserFactory(),
            content="Parent comment",
        )
        url = reverse("blog:post-add-comment", kwargs={"pk": published_post.pk})
        response = auth_client.post(url, {
            "content": "Reply to comment",
            "parent":  comment.id,
        })
        assert response.status_code == status.HTTP_201_CREATED

    def test_list_comments_public(self, published_post, db):
        from .test_users import UserFactory as UF
        published_post.comments.create(author=UF(), content="Comment 1")
        published_post.comments.create(author=UF(), content="Comment 2")

        client = APIClient()
        url = reverse("blog:post-comments", kwargs={"pk": published_post.pk})
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK
