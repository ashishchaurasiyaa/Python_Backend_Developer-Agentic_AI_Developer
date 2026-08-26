"""
Lab 11 — RBAC + Object-Level Permissions
═══════════════════════════════════════════════════════════════════════════════

ARCHITECTURE — DRF Permission System:

    REQUEST → Authentication → Permissions → View

    Two levels of permission checks:

    1. VIEW-LEVEL: has_permission(request, view)
       ─────────────────────────────────────────
       Runs BEFORE the view. Controls access to the endpoint.
       List/Create actions → only has_permission runs.
       Example: "Is user authenticated?" "Does user have 'blog.view_post' perm?"

    2. OBJECT-LEVEL: has_object_permission(request, view, obj)
       ───────────────────────────────────────────────────────
       Runs AFTER has_permission passes.
       Only for Retrieve/Update/Destroy (single object) actions.
       Example: "Is this user the owner of THIS specific post?"
       ⚠️  GenericAPIView calls check_object_permissions() → calls has_object_permission
       ⚠️  APIView must manually call self.check_object_permissions(request, obj)

    PERMISSION COMPOSITION (AND logic — all must pass):
       permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
       → IsAuthenticated.has_permission AND IsOwnerOrReadOnly.has_permission
       → IsOwnerOrReadOnly.has_object_permission

    RBAC DESIGN (Role-Based Access Control):
       User model has: role = 'user' | 'moderator' | 'admin'

       Permissions table:
         Action         | user        | moderator       | admin
         ─────────────────────────────────────────────────────
         Read post      | ✅ (own)    | ✅ (all)        | ✅ (all)
         Create post    | ✅          | ✅              | ✅
         Edit post      | ✅ (own)    | ❌              | ✅ (all)
         Delete post    | ✅ (own)    | ✅ (all)        | ✅ (all)
         Publish post   | ❌          | ✅ (own)        | ✅ (all)
         Moderate cmts  | ❌          | ✅              | ✅

CONTEXT:
  Blog platform with three roles. Implement permission classes that enforce
  the RBAC table above.

RUN:
    cd practical/
    pytest labs/lab_11_rbac_object_permissions.py -v -p no:odoo

SOCH — Answer ALOUD:
  Q1: has_permission vs has_object_permission — kab kaunsa call hota hai?
  Q2: Kya has_object_permission bina has_permission ke run ho sakta hai?
  Q3: SAFE_METHODS kya hain? kyon read-only exceptions dete hain?
  Q4: 20 different permissions hain toh ek hi permission class mein dalo ya alag-alag?
  Q5: DRF ka DjangoModelPermissions kya hai? Kab use karo?
"""

import pytest
from rest_framework import serializers
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.views import APIView
from rest_framework.generics import RetrieveUpdateDestroyAPIView
from rest_framework.response import Response
from rest_framework.permissions import BasePermission, IsAuthenticated, SAFE_METHODS
from rest_framework import status
from rest_framework.exceptions import PermissionDenied

import factory
from factory.django import DjangoModelFactory
from django.contrib.auth import get_user_model
from django.utils import timezone

from blog.models import Post, Category, Comment

User = get_user_model()


# ════════════════════════════════════════════════════════════════════════════
# FACTORIES
# ════════════════════════════════════════════════════════════════════════════

class L11UserFactory(DjangoModelFactory):
    class Meta:
        model = User
    email    = factory.Sequence(lambda n: f"l11user{n}@test.com")
    username = factory.Sequence(lambda n: f"l11user{n}")
    password = factory.PostGenerationMethodCall('set_password', 'pass123')
    role     = 'user'

class L11ModeratorFactory(L11UserFactory):
    role = 'moderator'

class L11AdminFactory(L11UserFactory):
    role = 'admin'
    is_staff = True

class L11CategoryFactory(DjangoModelFactory):
    class Meta:
        model = Category
    name = factory.Sequence(lambda n: f"L11Cat{n}")

class L11PostFactory(DjangoModelFactory):
    class Meta:
        model = Post
    title        = factory.Sequence(lambda n: f"L11 Post {n}")
    content      = "Content word " * 60
    excerpt      = "Excerpt."
    author       = factory.SubFactory(L11UserFactory)
    category     = factory.SubFactory(L11CategoryFactory)
    status       = 'draft'
    published_at = factory.LazyFunction(timezone.now)


# ════════════════════════════════════════════════════════════════════════════
# MINIMAL SERIALIZER
# ════════════════════════════════════════════════════════════════════════════

class PostSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Post
        fields = ['id', 'title', 'content', 'status', 'author_id']


# ════════════════════════════════════════════════════════════════════════════
# TODO 1 — IsPostOwner
# ════════════════════════════════════════════════════════════════════════════
"""
Implement IsPostOwner(BasePermission):

  message = "You can only modify your own posts."

  has_object_permission(self, request, view, obj):
    - SAFE_METHODS (GET, HEAD, OPTIONS): allow all authenticated users → return True
    - Write methods (POST, PUT, PATCH, DELETE): only allow if obj.author == request.user
    - Return True/False

  Note: has_permission is not overridden → defaults to True (view-level handled by
  IsAuthenticated in permission_classes = [IsAuthenticated, IsPostOwner])
"""

class IsPostOwner(BasePermission):
    message = "You can only modify your own posts."

    def has_object_permission(self, request, view, obj):
        raise NotImplementedError(
            "TODO 1: Allow SAFE_METHODS for all, write only for obj.author == request.user"
        )


# ════════════════════════════════════════════════════════════════════════════
# TODO 2 — CanModeratePost
# ════════════════════════════════════════════════════════════════════════════
"""
Implement CanModeratePost(BasePermission):
  Moderators and Admins can delete/update any post.
  Regular users can only modify their own.

  has_permission(self, request, view):
    - Must be authenticated: return request.user.is_authenticated

  has_object_permission(self, request, view, obj):
    - SAFE_METHODS: allow all → True
    - Admin role: allow all → True
    - Moderator role: allow DELETE and PATCH (not PUT full-replace unless own) → True
    - User role: only if obj.author == request.user → True/False

  Roles from User.Role: 'user', 'moderator', 'admin'
"""

class CanModeratePost(BasePermission):
    message = "You don't have permission to moderate this post."

    def has_permission(self, request, view):
        raise NotImplementedError(
            "TODO 2a: Return request.user.is_authenticated"
        )

    def has_object_permission(self, request, view, obj):
        raise NotImplementedError(
            "TODO 2b: Admin=all, Moderator=delete/patch, User=own only"
        )


# ════════════════════════════════════════════════════════════════════════════
# TODO 3 — CanPublishPost
# ════════════════════════════════════════════════════════════════════════════
"""
Implement CanPublishPost(BasePermission):
  Only moderators and admins can publish posts (set status='published').
  Regular users can only set status='draft' or 'archived'.

  has_permission(self, request, view):
    - return request.user.is_authenticated

  has_object_permission(self, request, view, obj):
    - If request.method not in ('PUT', 'PATCH'): return True (not a write op)
    - Check request.data.get('status') == 'published'
    - If trying to publish: allow only if role in ('moderator', 'admin')
    - Otherwise: return True

  Note: This is a "field-level" permission — only certain roles can set certain values.
"""

class CanPublishPost(BasePermission):
    message = "Only moderators and admins can publish posts."

    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        raise NotImplementedError(
            "TODO 3: Allow publish (status=published) only for moderator/admin roles"
        )


# ════════════════════════════════════════════════════════════════════════════
# TODO 4 — PostDetailView (wire permission classes)
# ════════════════════════════════════════════════════════════════════════════
"""
Implement PostDetailView(APIView) with RBAC permissions:

  permission_classes = [IsAuthenticated, CanModeratePost]

  get(self, request, pk):
    post = get_object_or_404(Post, pk=pk)
    self.check_object_permissions(request, post)   ← CRITICAL for object-level
    serializer = PostSerializer(post)
    return Response(serializer.data)

  patch(self, request, pk):
    post = get_object_or_404(Post, pk=pk)
    self.check_object_permissions(request, post)
    serializer = PostSerializer(post, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)

  delete(self, request, pk):
    post = get_object_or_404(Post, pk=pk)
    self.check_object_permissions(request, post)
    post.delete()
    return Response(status=204)

⚠️  INTERVIEW: Why self.check_object_permissions(request, obj)?
    APIView does NOT auto-call has_object_permission. You must call it explicitly.
    GenericAPIView/ViewSet calls it via get_object(). Plain APIView must do it manually.
"""

class PostDetailView(APIView):
    permission_classes = [IsAuthenticated, CanModeratePost]

    def get(self, request, pk):
        raise NotImplementedError("TODO 4a: get post, check_object_permissions, return serialized")

    def patch(self, request, pk):
        raise NotImplementedError("TODO 4b: partial update with object permission check")

    def delete(self, request, pk):
        raise NotImplementedError("TODO 4c: delete with object permission check")


# ════════════════════════════════════════════════════════════════════════════
# TESTS
# ════════════════════════════════════════════════════════════════════════════

api_factory = APIRequestFactory()


@pytest.mark.django_db
def test_owner_can_edit_own_post():
    """Post owner should be able to PATCH their own post."""
    user = L11UserFactory()
    post = L11PostFactory(author=user)

    perm = IsPostOwner()
    request = api_factory.patch(f'/posts/{post.id}/', {'title': 'Updated'}, format='json')
    request.user = user

    assert perm.has_object_permission(request, None, post), (
        "FAIL: Owner should have write permission on their own post"
    )


@pytest.mark.django_db
def test_non_owner_cannot_edit_post():
    """Non-owner should NOT be able to PATCH someone else's post."""
    owner   = L11UserFactory()
    other   = L11UserFactory()
    post    = L11PostFactory(author=owner)

    perm    = IsPostOwner()
    request = api_factory.patch(f'/posts/{post.id}/', {'title': 'Hacked'}, format='json')
    request.user = other

    assert not perm.has_object_permission(request, None, post), (
        "FAIL: Non-owner should NOT have write permission on another user's post"
    )


@pytest.mark.django_db
def test_anyone_can_read_post_with_is_post_owner():
    """IsPostOwner allows GET for all authenticated users."""
    reader = L11UserFactory()
    owner  = L11UserFactory()
    post   = L11PostFactory(author=owner)

    perm    = IsPostOwner()
    request = api_factory.get(f'/posts/{post.id}/')
    request.user = reader

    assert perm.has_object_permission(request, None, post), (
        "FAIL: IsPostOwner should allow GET (read) for all authenticated users"
    )


@pytest.mark.django_db
def test_admin_can_delete_any_post():
    """Admin role can delete any post (not just own)."""
    admin  = L11AdminFactory()
    owner  = L11UserFactory()
    post   = L11PostFactory(author=owner)

    perm    = CanModeratePost()
    request = api_factory.delete(f'/posts/{post.id}/')
    request.user = admin

    assert perm.has_object_permission(request, None, post), (
        "FAIL: Admin should be able to delete any post"
    )


@pytest.mark.django_db
def test_moderator_can_delete_any_post():
    """Moderator role can delete any post."""
    moderator = L11ModeratorFactory()
    owner     = L11UserFactory()
    post      = L11PostFactory(author=owner)

    perm    = CanModeratePost()
    request = api_factory.delete(f'/posts/{post.id}/')
    request.user = moderator

    assert perm.has_object_permission(request, None, post), (
        "FAIL: Moderator should be able to delete any post"
    )


@pytest.mark.django_db
def test_regular_user_cannot_delete_others_post():
    """Regular user cannot delete another user's post."""
    user1 = L11UserFactory()
    user2 = L11UserFactory()
    post  = L11PostFactory(author=user1)

    perm    = CanModeratePost()
    request = api_factory.delete(f'/posts/{post.id}/')
    request.user = user2

    assert not perm.has_object_permission(request, None, post), (
        "FAIL: Regular user should NOT delete another user's post"
    )


@pytest.mark.django_db
def test_regular_user_can_delete_own_post():
    """Regular user can delete their own post."""
    user = L11UserFactory()
    post = L11PostFactory(author=user)

    perm    = CanModeratePost()
    request = api_factory.delete(f'/posts/{post.id}/')
    request.user = user

    assert perm.has_object_permission(request, None, post), (
        "FAIL: Regular user should be able to delete their OWN post"
    )


@pytest.mark.django_db
def test_moderator_can_publish_post():
    """Moderator can set status=published."""
    moderator = L11ModeratorFactory()
    post = L11PostFactory(author=L11UserFactory())

    perm = CanPublishPost()
    request = api_factory.patch(f'/posts/{post.id}/', {'status': 'published'}, format='json')
    request.user = moderator

    assert perm.has_object_permission(request, None, post), (
        "FAIL: Moderator should be able to publish posts"
    )


@pytest.mark.django_db
def test_regular_user_cannot_publish_post():
    """Regular user cannot set status=published."""
    user = L11UserFactory()
    post = L11PostFactory(author=user)

    perm = CanPublishPost()
    request = api_factory.patch(f'/posts/{post.id}/', {'status': 'published'}, format='json')
    request.user = user

    assert not perm.has_object_permission(request, None, post), (
        "FAIL: Regular user should NOT be able to publish posts"
    )


@pytest.mark.django_db
def test_post_detail_view_get_returns_200_for_any_user():
    """GET /posts/<pk>/ should return 200 for any authenticated user."""
    user = L11UserFactory()
    post = L11PostFactory()

    request = api_factory.get(f'/posts/{post.id}/')
    force_authenticate(request, user=user)

    view     = PostDetailView.as_view()
    response = view(request, pk=post.id)

    assert response.status_code == 200, (
        f"FAIL: GET should return 200. Got {response.status_code}: {response.data}"
    )


@pytest.mark.django_db
def test_post_detail_view_delete_403_for_regular_user():
    """DELETE by non-owner regular user should get 403."""
    user  = L11UserFactory()
    owner = L11UserFactory()
    post  = L11PostFactory(author=owner)

    request = api_factory.delete(f'/posts/{post.id}/')
    force_authenticate(request, user=user)

    view     = PostDetailView.as_view()
    response = view(request, pk=post.id)

    assert response.status_code == 403, (
        f"FAIL: Non-owner delete should return 403. Got {response.status_code}"
    )


@pytest.mark.django_db
def test_post_detail_view_delete_204_for_moderator():
    """DELETE by moderator should succeed with 204."""
    moderator = L11ModeratorFactory()
    post      = L11PostFactory(author=L11UserFactory())

    request = api_factory.delete(f'/posts/{post.id}/')
    force_authenticate(request, user=moderator)

    view     = PostDetailView.as_view()
    response = view(request, pk=post.id)

    assert response.status_code == 204, (
        f"FAIL: Moderator delete should return 204. Got {response.status_code}"
    )
    assert not Post.objects.filter(id=post.id).exists(), (
        "FAIL: Post should be deleted from DB"
    )


# ════════════════════════════════════════════════════════════════════════════
# SOCH
# ════════════════════════════════════════════════════════════════════════════

"""
SOCH (Answer ALOUD):

Q1: has_permission vs has_object_permission — exact mein kab kaunsa call hota hai?
    List GET: only has_permission
    Retrieve GET: has_permission → get_object() → check_object_permissions → has_object_permission
    Create POST: only has_permission
    Update PATCH: has_permission → get_object() → check_object_permissions → has_object_permission

Q2: APIView mein manually self.check_object_permissions(request, obj) kyon likhna padta hai?
    (GenericAPIView.get_object() automatically calls it. Plain APIView does not. Forgetting = security hole)

Q3: permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
    AND logic hai ya OR logic?
    (AND — ALL must pass. For OR logic: from rest_framework.permissions import OR operator)

Q4: DRF mein "unauthenticated user" hit kare:
    IsAuthenticated.has_permission → False → 401 Unauthorized
    But first: WWW-Authenticate header kaise aata hai?
    (Authentication class adds it when request.auth is None)

Q5: Enterprise RBAC design mein Django's built-in Permission model (codename) use karo ya
    custom role field? Trade-offs kya hain?
    (Built-in: per-object too coarse, lots of DB queries. Custom role: simpler, less flexible)
"""
