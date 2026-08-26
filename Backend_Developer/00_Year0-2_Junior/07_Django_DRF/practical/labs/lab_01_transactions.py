"""
Lab 01 — Transactions, F() Expressions, SELECT FOR UPDATE
═══════════════════════════════════════════════════════════════════════════════

CONTEXT: Blog post likes counter. Multiple users simultaneously like a post.
         Agar DB update atomic nahi hai, likes kho jaate hain (lost update).

GOAL: Teen patterns seekho —
  1. Naive Python increment (race condition — WRONG way, but write it)
  2. F() expression — single SQL UPDATE statement, atomic
  3. transaction.atomic() + select_for_update() — row-level DB lock

RUN:
    cd practical/
    pytest labs/lab_01_transactions.py -v -p no:odoo

SOCH — Answer ALOUD after completing each TODO:
  Q1: F() kyon atomic hai? Internally kya SQL generate hota hai?
  Q2: F() use karne ke baad post.refresh_from_db() kyon zaroori hai?
  Q3: select_for_update() sirf transaction.atomic() ke andar kaam karta hai — kyon?
  Q4: transfer_likes() mein hum hamesha lower pk first lock karte hain — kyon? Kya hota agar nahi karte?
  Q5: transaction.atomic() ke andar cache.delete() likhna kyon galat hai?
"""

import threading
import pytest
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.core.cache import cache

import factory
from factory.django import DjangoModelFactory
from django.contrib.auth import get_user_model

from blog.models import Post, Category

User = get_user_model()

FEATURED_CACHE_KEY = 'featured_posts'


# ════════════════════════════════════════════════════════════════════════════
# FACTORIES (don't modify)
# ════════════════════════════════════════════════════════════════════════════

class L1UserFactory(DjangoModelFactory):
    class Meta:
        model = User
    email    = factory.Sequence(lambda n: f"l1user{n}@test.com")
    username = factory.Sequence(lambda n: f"l1user{n}")
    password = factory.PostGenerationMethodCall('set_password', 'pass123')


class L1CategoryFactory(DjangoModelFactory):
    class Meta:
        model = Category
    name = factory.Sequence(lambda n: f"L1Cat {n}")


class L1PostFactory(DjangoModelFactory):
    class Meta:
        model = Post
    title       = factory.Sequence(lambda n: f"L1 Post {n}")
    content     = "Content word " * 50
    excerpt     = "Short excerpt."
    author      = factory.SubFactory(L1UserFactory)
    category    = factory.SubFactory(L1CategoryFactory)
    status      = 'published'
    likes_count = 0
    published_at = factory.LazyFunction(timezone.now)


# ════════════════════════════════════════════════════════════════════════════
# TODO 1 — like_post_unsafe()
# ════════════════════════════════════════════════════════════════════════════
"""
Implement the WRONG way to increment likes.
Pattern: GET post → Python +1 → SAVE
This has a race condition: two threads can both read likes=0,
both add 1, and both save 1. Net result = 1 instead of 2.
You still write it because understanding the bug is the first step.

Steps:
  1. post = Post.objects.get(pk=post_id)
  2. post.likes_count += 1
  3. post.save(update_fields=['likes_count'])
"""

def like_post_unsafe(post_id: int) -> None:
    raise NotImplementedError("TODO 1: Implement like_post_unsafe()")


# ════════════════════════════════════════════════════════════════════════════
# TODO 2 — like_post_atomic()
# ════════════════════════════════════════════════════════════════════════════
"""
Implement the CORRECT way using F() expression.
Pattern: Post.objects.filter(pk=post_id).update(likes_count=F('likes_count') + 1)

Generates SQL: UPDATE blog_posts SET likes_count = likes_count + 1 WHERE id = X
The DB does the increment — no Python read, no race condition.

Steps:
  1. Post.objects.filter(pk=post_id).update(likes_count=F('likes_count') + 1)
  (One line is enough.)
"""

def like_post_atomic(post_id: int) -> None:
    raise NotImplementedError("TODO 2: Implement like_post_atomic()")


# ════════════════════════════════════════════════════════════════════════════
# TODO 3 — safe_publish_post()
# ════════════════════════════════════════════════════════════════════════════
"""
Publish a draft post atomically. All DB changes must succeed or rollback together.

Steps INSIDE transaction.atomic():
  1. post = Post.objects.select_for_update().get(pk=post_id)
  2. if post.status != 'draft': raise ValueError("Post is already published")
  3. post.status = 'published'
  4. post.published_at = timezone.now()
  5. post.save(update_fields=['status', 'published_at', 'updated_at'])

AFTER the atomic block (cache ops are NOT transactional — keep outside):
  6. cache.delete(FEATURED_CACHE_KEY)

Return: {'id': post.id, 'published_at': str(post.published_at)}
"""

def safe_publish_post(post_id: int) -> dict:
    raise NotImplementedError("TODO 3: Implement safe_publish_post()")


# ════════════════════════════════════════════════════════════════════════════
# TODO 4 — transfer_likes()
# ════════════════════════════════════════════════════════════════════════════
"""
Transfer `amount` likes from one post to another in a SINGLE transaction.

DEADLOCK PREVENTION: Always lock rows in consistent order (lower pk first).
  - If we don't do this: Thread A locks post 5 waiting for post 3,
    Thread B locks post 3 waiting for post 5 → DEADLOCK.
  - Sorting by pk before locking prevents this.

Steps INSIDE transaction.atomic():
  1. Lock both rows in pk order (use select_for_update() with sorted IDs):
       posts = Post.objects.select_for_update().filter(
           pk__in=[from_post_id, to_post_id]
       ).order_by('pk')
       from_post = posts.get(pk=from_post_id)
       to_post   = posts.get(pk=to_post_id)

  2. if from_post.likes_count < amount:
         raise ValueError("Insufficient likes to transfer")

  3. from_post.likes_count -= amount
     from_post.save(update_fields=['likes_count'])

  4. to_post.likes_count += amount
     to_post.save(update_fields=['likes_count'])
"""

def transfer_likes(from_post_id: int, to_post_id: int, amount: int) -> None:
    raise NotImplementedError("TODO 4: Implement transfer_likes()")


# ════════════════════════════════════════════════════════════════════════════
# TESTS — Don't modify. They verify your TODOs.
# ════════════════════════════════════════════════════════════════════════════

# ── TODO 1 Tests ──────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestUnsafeIncrement:

    def test_single_thread_works(self):
        post = L1PostFactory(likes_count=0)
        like_post_unsafe(post.pk)
        post.refresh_from_db()
        assert post.likes_count == 1, \
            "FAIL: like_post_unsafe() ne likes increment nahi kiya"

    def test_increments_by_one_each_call(self):
        post = L1PostFactory(likes_count=5)
        like_post_unsafe(post.pk)
        like_post_unsafe(post.pk)
        post.refresh_from_db()
        assert post.likes_count == 7, \
            f"FAIL: 2 calls ke baad 7 chahiye, mila {post.likes_count}"


# ── TODO 2 Tests ──────────────────────────────────────────────────────────

@pytest.mark.django_db(transaction=True)
class TestAtomicF:

    def test_increments_correctly(self):
        post = L1PostFactory(likes_count=0)
        like_post_atomic(post.pk)
        post.refresh_from_db()
        assert post.likes_count == 1, \
            "FAIL: like_post_atomic() ne likes increment nahi kiya"

    def test_concurrent_likes_no_lost_updates(self):
        """
        10 concurrent threads, each liking once.
        F() ensures result = exactly 10. Unsafe would give < 10.
        """
        post = L1PostFactory(likes_count=0)
        errors = []

        def do_like():
            try:
                like_post_atomic(post.pk)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=do_like) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Threads mein error aaye: {errors}"
        post.refresh_from_db()
        assert post.likes_count == 10, (
            f"FAIL: 10 likes chahiye, mila {post.likes_count}. "
            "Lost updates detected — kya tumhara F() sahi hai?"
        )

    def test_f_expression_returns_one_row_updated(self):
        """update() ka return value = number of rows updated."""
        post = L1PostFactory(likes_count=0)
        rows = Post.objects.filter(pk=post.pk).update(
            likes_count=F('likes_count') + 1
        )
        assert rows == 1, f"FAIL: update() ne {rows} rows update kiye, 1 chahiye tha"


# ── TODO 3 Tests ──────────────────────────────────────────────────────────

@pytest.mark.django_db(transaction=True)
class TestSafePublish:

    def test_publishes_draft(self):
        post = L1PostFactory(status='draft', published_at=None)
        result = safe_publish_post(post.pk)
        post.refresh_from_db()
        assert post.status == 'published', \
            f"FAIL: status 'published' hona chahiye, mila '{post.status}'"
        assert post.published_at is not None, \
            "FAIL: published_at set hona chahiye"
        assert 'published_at' in result, \
            "FAIL: result dict mein 'published_at' key honi chahiye"

    def test_raises_for_already_published(self):
        post = L1PostFactory(status='published')
        with pytest.raises(ValueError):
            safe_publish_post(post.pk)

    def test_cache_cleared_after_publish(self):
        """
        Cache clear OUTSIDE the transaction (cache is not transactional).
        """
        cache.set(FEATURED_CACHE_KEY, ['old', 'data'])
        post = L1PostFactory(status='draft', published_at=None)
        safe_publish_post(post.pk)
        assert cache.get(FEATURED_CACHE_KEY) is None, \
            "FAIL: FEATURED_CACHE_KEY cache clear nahi hua"

    def test_demonstrates_rollback(self):
        """
        DEMO: transaction.atomic() exception pe sab kuch rollback karta hai.
        Ye test directly tumhara TODO test nahi karta — ye concept demonstrate karta hai.
        """
        post = L1PostFactory(status='draft')

        try:
            with transaction.atomic():
                post.status = 'published'
                post.save()
                raise RuntimeError("Simulated crash mid-transaction")
        except RuntimeError:
            pass

        post.refresh_from_db()
        assert post.status == 'draft', \
            "FAIL: transaction.atomic() ka rollback kaam nahi kiya — concept galat hai"


# ── TODO 4 Tests ──────────────────────────────────────────────────────────

@pytest.mark.django_db(transaction=True)
class TestTransferLikes:

    def test_basic_transfer(self):
        post_a = L1PostFactory(likes_count=20)
        post_b = L1PostFactory(likes_count=5)

        transfer_likes(post_a.pk, post_b.pk, 10)

        post_a.refresh_from_db()
        post_b.refresh_from_db()
        assert post_a.likes_count == 10, \
            f"FAIL: post_a ko 10 likes chahiye, mila {post_a.likes_count}"
        assert post_b.likes_count == 15, \
            f"FAIL: post_b ko 15 likes chahiye, mila {post_b.likes_count}"

    def test_total_conserved(self):
        """Likes transfer hote hain, create/destroy nahi hote."""
        post_a = L1PostFactory(likes_count=50)
        post_b = L1PostFactory(likes_count=30)
        total_before = 80

        transfer_likes(post_a.pk, post_b.pk, 25)

        post_a.refresh_from_db()
        post_b.refresh_from_db()
        total_after = post_a.likes_count + post_b.likes_count
        assert total_after == total_before, \
            f"FAIL: Total likes badal gaye! Before: {total_before}, After: {total_after}"

    def test_insufficient_likes_raises_and_rollbacks(self):
        """Agar likes kam hain toh ValueError — aur koi change nahi hona chahiye."""
        post_a = L1PostFactory(likes_count=3)
        post_b = L1PostFactory(likes_count=10)

        with pytest.raises(ValueError):
            transfer_likes(post_a.pk, post_b.pk, 5)

        post_a.refresh_from_db()
        post_b.refresh_from_db()
        assert post_a.likes_count == 3,  \
            "FAIL: post_a likes change ho gaye despite rollback"
        assert post_b.likes_count == 10, \
            "FAIL: post_b likes change ho gaye despite rollback"


# ═══════════════════════════════════════════════════════════════════════════
# SOCH — Answer ALOUD before moving to Lab 02
# ═══════════════════════════════════════════════════════════════════════════
#
#  Q1: F() kya SQL generate karta hai? `post.likes_count += 1; post.save()` vs
#      `Post.objects.filter(pk=id).update(likes_count=F('likes_count') + 1)`
#      dono mein fark explain karo.
#
#  Q2: like_post_atomic() ke baad agar tumhe post.likes_count print karna ho
#      toh seedha print karna kyon wrong hoga? Kya karna chahiye?
#
#  Q3: safe_publish_post() mein cache.delete() transaction ke ANDAR kyon nahi?
#      Kya hota agar andar hota aur transaction rollback hoti?
#
#  Q4: transfer_likes() mein order_by('pk') se deadlock kyon rukhta hai?
#      Bina order ke kya scenario mein deadlock ho sakta tha?
#
#  Q5: Interview mein poochha: "Bank transfer implement karo — atomically"
#      Ab ye sab padhke ek paragraph mein bolo kaise karoge.
# ═══════════════════════════════════════════════════════════════════════════
