"""
Lab 04 — Django Signals: post_save Handlers
═══════════════════════════════════════════════════════════════════════════════

CONTEXT: When a blog post is published:
  1. The "featured posts" cache must be invalidated (stale data risk)
  2. Subscribers should be notified (email/push/WebSocket)

Both reactions should happen automatically whenever Post.status changes
to 'published' — without the publishing code knowing about cache or email.
This is the core value of signals: decoupled side effects.

GOAL: Write signal handlers and connect them to Post's post_save signal.

HOW SIGNALS WORK:
  1. Django calls post_save.send(sender=Post, instance=post, created=False, ...)
     after every Post.save()
  2. Every connected handler receives the instance
  3. Handler logic runs synchronously (in the same request/transaction)

IN PRODUCTION: You'd connect signals in AppConfig.ready() so they load once.
In this lab: we connect/disconnect per test (clean, no leakage).

RUN:
    cd practical/
    pytest labs/lab_04_signals.py -v -p no:odoo

SOCH — Answer ALOUD after completing each TODO:
  Q1: Signal handler transaction ke andar run hota hai ya bahar?
      (Same transaction — agar handler fail ho, publishing bhi fail hoti hai)
  Q2: Email bhejne wala code signal handler mein kyon WRONG hai?
      (HTTP timeout → save() fails → 500 error)
  Q3: Sahi tarika kya hai? (Hint: Celery task — handler sirf task enqueue kare)
  Q4: Kab post_save fire hota hai? (created=True first time, created=False on update)
  Q5: signal.disconnect() test mein kyon zaroori hai?
      (Without it: signal leaks into next test, side effects multiply)
"""

import pytest
import factory
from factory.django import DjangoModelFactory
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models.signals import post_save

from blog.models import Post, Category

User = get_user_model()

FEATURED_CACHE_KEY = 'featured_posts'


# ════════════════════════════════════════════════════════════════════════════
# FACTORIES (don't modify)
# ════════════════════════════════════════════════════════════════════════════

class L4UserFactory(DjangoModelFactory):
    class Meta:
        model = User
    email    = factory.Sequence(lambda n: f"l4user{n}@test.com")
    username = factory.Sequence(lambda n: f"l4user{n}")
    password = factory.PostGenerationMethodCall('set_password', 'pass123')


class L4CategoryFactory(DjangoModelFactory):
    class Meta:
        model = Category
    name = factory.Sequence(lambda n: f"L4Cat {n}")


class L4PostFactory(DjangoModelFactory):
    class Meta:
        model = Post
    title    = factory.Sequence(lambda n: f"L4 Post {n}")
    content  = "Content word " * 50
    excerpt  = "Short excerpt."
    author   = factory.SubFactory(L4UserFactory)
    category = factory.SubFactory(L4CategoryFactory)
    status   = 'draft'   # NOTE: draft by default so signal doesn't fire on creation


# ════════════════════════════════════════════════════════════════════════════
# In-memory notification log (stands in for Celery/email in tests)
# ════════════════════════════════════════════════════════════════════════════

notifications_sent: list[dict] = []


# ════════════════════════════════════════════════════════════════════════════
# TODO 1 — clear_featured_cache_on_publish
# ════════════════════════════════════════════════════════════════════════════
"""
Signal handler: delete the featured posts cache when a post is published.

Signature: def handler(sender, instance, created, **kwargs)

Logic:
  if instance.status == 'published':
      cache.delete(FEATURED_CACHE_KEY)

Do NOT cache.delete() for every save — only when status = published.
(A draft save should NOT clear the cache.)
"""

def clear_featured_cache_on_publish(sender, instance, created, **kwargs):
    pass  # TODO 1: Implement — clear FEATURED_CACHE_KEY when published


# ════════════════════════════════════════════════════════════════════════════
# TODO 2 — notify_subscribers_on_publish
# ════════════════════════════════════════════════════════════════════════════
"""
Signal handler: log a notification when a post is published.
In production: this would enqueue a Celery task.
In this lab: append to notifications_sent list.

Logic:
  if instance.status == 'published':
      notifications_sent.append({
          'type': 'new_post',
          'post_id': instance.pk,
          'title': instance.title,
      })
"""

def notify_subscribers_on_publish(sender, instance, created, **kwargs):
    pass  # TODO 2: Implement — append notification dict to notifications_sent


# ════════════════════════════════════════════════════════════════════════════
# TODO 3 — connect_signals()
# ════════════════════════════════════════════════════════════════════════════
"""
Connect both handlers to Post's post_save signal.

post_save.connect(handler, sender=Model)

Connect:
  - clear_featured_cache_on_publish → Post
  - notify_subscribers_on_publish   → Post
"""

def connect_signals() -> None:
    pass  # TODO 3: Connect both handlers to Post's post_save signal


# ════════════════════════════════════════════════════════════════════════════
# Test fixture: connect before each test, disconnect and clear after
# ════════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def signals_lifecycle():
    """
    Connect signals → run test → disconnect.
    This prevents signal leakage between tests.
    """
    connect_signals()
    notifications_sent.clear()
    cache.clear()
    yield
    post_save.disconnect(clear_featured_cache_on_publish, sender=Post)
    post_save.disconnect(notify_subscribers_on_publish, sender=Post)
    notifications_sent.clear()
    cache.clear()


# ════════════════════════════════════════════════════════════════════════════
# TESTS — Don't modify. They verify your TODOs.
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_cache_cleared_when_post_published():
    """Publishing a post → featured posts cache delete hona chahiye."""
    cache.set(FEATURED_CACHE_KEY, ['stale', 'featured', 'data'])
    assert cache.get(FEATURED_CACHE_KEY) is not None, "Setup: cache set nahi hua"

    post = L4PostFactory()
    post.status = 'published'
    post.save()

    assert cache.get(FEATURED_CACHE_KEY) is None, (
        "FAIL: Cache clear nahi hua after publishing. "
        "clear_featured_cache_on_publish() check karo — "
        "post_save.connect() kiya? status == 'published' check kiya?"
    )


@pytest.mark.django_db
def test_cache_not_cleared_for_draft_save():
    """Draft post save karne se cache clear NAHI hona chahiye."""
    cache.set(FEATURED_CACHE_KEY, ['fresh', 'data'])

    post = L4PostFactory()   # status = 'draft' by default
    post.content = "Updated content for draft"
    post.save()

    cached = cache.get(FEATURED_CACHE_KEY)
    assert cached is not None, (
        "FAIL: Draft save pe cache clear ho gaya — "
        "handler mein status == 'published' condition check karo"
    )


@pytest.mark.django_db
def test_notification_sent_on_publish():
    """Post publish hone pe ek notification queue hona chahiye."""
    post = L4PostFactory()
    post.status = 'published'
    post.save()

    assert len(notifications_sent) == 1, (
        f"FAIL: 1 notification chahiye, mila {len(notifications_sent)}. "
        "notify_subscribers_on_publish() check karo."
    )
    notif = notifications_sent[0]
    assert notif['post_id'] == post.pk, \
        f"FAIL: notification mein wrong post_id: {notif['post_id']}"
    assert notif['type'] == 'new_post', \
        f"FAIL: notification type 'new_post' hona chahiye, mila: {notif['type']}"
    assert notif['title'] == post.title, \
        f"FAIL: notification title galat: {notif['title']}"


@pytest.mark.django_db
def test_notification_not_sent_for_draft_save():
    """Draft save pe koi notification nahi bhejni chahiye."""
    post = L4PostFactory()
    post.content = "Updated draft content"
    post.save()

    assert len(notifications_sent) == 0, (
        f"FAIL: Draft save pe {len(notifications_sent)} notifications bheje gaye. "
        "Handler mein status check galat hai."
    )


@pytest.mark.django_db
def test_both_handlers_fire_on_publish():
    """Publishing ek post → cache clear + notification dono hone chahiye."""
    cache.set(FEATURED_CACHE_KEY, ['data'])
    post = L4PostFactory()
    post.status = 'published'
    post.save()

    assert cache.get(FEATURED_CACHE_KEY) is None, \
        "FAIL: Cache clear nahi hua (handler 1 fail)"
    assert len(notifications_sent) == 1, \
        f"FAIL: Notification nahi aaya (handler 2 fail) — count: {len(notifications_sent)}"


@pytest.mark.django_db
def test_publish_twice_fires_signal_twice():
    """
    Agar same post twice publish hoti hai (e.g. update after publish),
    signal dono baar fire hota hai.
    Ye normal behaviour hai — production mein idempotency handle karo.
    """
    post = L4PostFactory()

    post.status = 'published'
    post.save()
    count_after_first = len(notifications_sent)

    post.likes_count = 5
    post.save()  # Second save — status is still 'published'
    count_after_second = len(notifications_sent)

    assert count_after_second > count_after_first, \
        "Signal dono saves pe fire hona chahiye"


# ═══════════════════════════════════════════════════════════════════════════
# SOCH — Answer ALOUD before moving to Lab 05
# ═══════════════════════════════════════════════════════════════════════════
#
#  Q1: Signal handler same transaction mein run karta hai.
#      Agar notify_subscribers() mein exception aaye, publishing fail ho jaayegi.
#      Production mein ye kaise fix karte hain?
#      (Answer: Celery task — handler bas task_enqueue() kare, actual work async)
#
#  Q2: post_save signal kab kab fire hota hai?
#      (Every .save() — create aur update dono pe)
#      Sirf create pe chahiye? → use pre_save ya check created=True
#
#  Q3: Hum test mein signals_lifecycle fixture use kar rahe hain.
#      Production mein signals kahan connect karte hain?
#      (In AppConfig.ready() — blog/apps.py mein)
#
#  Q4: Signal se tight coupling kyon hoti hai? Kab alternative use karein?
#      (Agar handler order important ho, ya transaction boundary matter kare)
#      (Alternative: explicit service layer call karo view mein)
#
#  Q5: Test 6 (publish_twice_fires_signal_twice) kya problem reveal karta hai?
#      (Idempotency — notification 2 baar bhejte ho. Fix: check `created` kwarg
#       ya check if status just changed from non-published to published)
# ═══════════════════════════════════════════════════════════════════════════
