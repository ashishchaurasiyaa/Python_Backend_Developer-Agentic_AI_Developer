"""
DRF — GenericAPIView, Mixins, Concrete Views, and ViewSets
===========================================================

Covers the full DRF view hierarchy from lowest-level to highest-level:

  APIView  →  GenericAPIView + Mixins  →  Concrete Generic Views  →  ViewSet

All code in this module is structured as importable, runnable Django/DRF code.
Because Django requires a configured settings module, no ``if __name__ == "__main__"``
block that starts a server is included — the patterns are designed to be copied
verbatim into a real Django project.

Theory doc grounded:
    Backend_Developer/00_Year0-2_Junior/07_Django_DRF/07_genericapiview_mixins.md

Install requirements:
    pip install djangorestframework django
"""

# ==========================================================================
# 0. REQUIRED IMPORTS (all standard DRF — no extra packages)
# ==========================================================================

# NOTE: The imports below will resolve only when Django is configured and
# djangorestframework is installed.  They are purposely kept at module scope
# so any static analyser / IDE can resolve them.  In a real project these
# imports live inside views.py / viewsets.py.

from __future__ import annotations

from typing import List, Optional, Any

# Django
from django.db import models
from django.contrib.auth import get_user_model

# DRF core
from rest_framework import generics, mixins, viewsets, serializers, status
from rest_framework.decorators import action
from rest_framework.permissions import (
    AllowAny,
    IsAuthenticated,
    BasePermission,
)
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


# ==========================================================================
# 1. DOMAIN MODELS — Blog app (Post, Tag, Comment)
# ==========================================================================

User = get_user_model()


class Tag(models.Model):
    """Simple tag for classifying posts."""

    name: str = models.CharField(max_length=60, unique=True)

    class Meta:
        app_label = "blog"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class PostQuerySet(models.QuerySet):
    """Custom queryset that exposes semantic filter helpers."""

    def published(self) -> "PostQuerySet":
        return self.filter(status="published")

    def featured(self) -> "PostQuerySet":
        return self.filter(is_featured=True)

    def with_all_relations(self) -> "PostQuerySet":
        return self.select_related("author", "category").prefetch_related("tags")


class PostManager(models.Manager):
    """Attach the custom queryset to the model manager."""

    def get_queryset(self) -> PostQuerySet:
        return PostQuerySet(self.model, using=self._db)

    def published(self) -> PostQuerySet:
        return self.get_queryset().published()


class Category(models.Model):
    name: str = models.CharField(max_length=100, unique=True)

    class Meta:
        app_label = "blog"

    def __str__(self) -> str:
        return self.name


class Post(models.Model):
    STATUS_CHOICES = [("draft", "Draft"), ("published", "Published")]

    title: str = models.CharField(max_length=200)
    body: str = models.TextField()
    author: Any = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="posts"
    )
    category: Any = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="posts",
    )
    tags: Any = models.ManyToManyField(Tag, blank=True, related_name="posts")
    status: str = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="draft"
    )
    is_featured: bool = models.BooleanField(default=False)
    created_at: Any = models.DateTimeField(auto_now_add=True)
    updated_at: Any = models.DateTimeField(auto_now=True)

    objects = PostManager()

    class Meta:
        app_label = "blog"
        ordering = ["-created_at"]

    def publish(self) -> None:
        """Transition a draft post to published state."""
        self.status = "published"
        self.save(update_fields=["status", "updated_at"])

    def __str__(self) -> str:
        return self.title


class Comment(models.Model):
    post: Any = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    author: Any = models.ForeignKey(User, on_delete=models.CASCADE, related_name="comments")
    body: str = models.TextField()
    is_approved: bool = models.BooleanField(default=False)
    created_at: Any = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "blog"
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"Comment by {self.author} on '{self.post}'"


# ==========================================================================
# 2. SERIALIZERS
# ==========================================================================

class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name"]


class PostListSerializer(serializers.ModelSerializer):
    """Lightweight serializer used for list actions — avoids heavy body field."""

    author_name: Any = serializers.CharField(source="author.get_full_name", read_only=True)

    class Meta:
        model = Post
        fields = ["id", "title", "author_name", "status", "is_featured", "created_at"]


class PostDetailSerializer(serializers.ModelSerializer):
    """Full serializer used for retrieve, create, and update actions."""

    tags = TagSerializer(many=True, read_only=True)

    class Meta:
        model = Post
        fields = [
            "id", "title", "body", "author", "category",
            "tags", "status", "is_featured", "created_at", "updated_at",
        ]
        read_only_fields = ["author", "created_at", "updated_at"]


class PostCreateSerializer(serializers.ModelSerializer):
    """Write-only serializer — accepts writable fields for create/update."""

    class Meta:
        model = Post
        fields = ["title", "body", "category", "tags", "status", "is_featured"]

    def create(self, validated_data: dict) -> Post:
        # Inject the authenticated user as author automatically.
        request = self.context["request"]
        validated_data["author"] = request.user
        return super().create(validated_data)


class UserRegisterSerializer(serializers.ModelSerializer):
    """Minimal registration serializer (email + password only)."""

    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ["email", "password"]

    def create(self, validated_data: dict) -> Any:
        return User.objects.create_user(**validated_data)


class CommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ["id", "body", "is_approved", "created_at"]
        read_only_fields = ["is_approved", "created_at"]


# ==========================================================================
# 3. CUSTOM PERMISSIONS
# ==========================================================================

class IsOwnerOrReadOnly(BasePermission):
    """
    Object-level permission: allow read for everyone, write only for the author.
    Safe methods (GET, HEAD, OPTIONS) are always permitted.
    """

    def has_object_permission(self, request: Request, view: Any, obj: Any) -> bool:
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        # obj.author must be the requesting user for write operations.
        return obj.author == request.user


# ==========================================================================
# 4. LEVEL 1 — APIView (maximum manual control)
# ==========================================================================

class UserListAPIView(APIView):
    """
    Pure APIView: all logic is written by hand.
    Every HTTP method is an explicit method on the class.

    URL:
        path("users/", UserListAPIView.as_view())
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        users = User.objects.all()
        # Using values() to avoid needing a full UserSerializer here.
        data = list(users.values("id", "username", "email"))
        return Response(data)

    def post(self, request: Request) -> Response:
        serializer = UserRegisterSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# ==========================================================================
# 5. LEVEL 2a — GenericAPIView + Mixins (plug-in individual operations)
# ==========================================================================

class PostListMixinView(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    generics.GenericAPIView,
):
    """
    GenericAPIView wired with two mixins:
      - ListModelMixin   → self.list()
      - CreateModelMixin → self.create()

    The developer must still map HTTP verbs to mixin methods explicitly.
    This gives fine-grained control over which operations are exposed.

    URL:
        path("posts/", PostListMixinView.as_view())
    """

    queryset = Post.objects.with_all_relations()
    serializer_class = PostListSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Return a paginated list of posts."""
        return self.list(request, *args, **kwargs)  # from ListModelMixin

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Create a new post and return 201 with the new resource."""
        return self.create(request, *args, **kwargs)  # from CreateModelMixin


# ==========================================================================
# 6. LEVEL 2b — Concrete Generic Views (recommended shortcut for standard CRUD)
# ==========================================================================

# ---------- Tag (read-only list) -------------------------------------------

class TagListView(generics.ListAPIView):
    """
    GET /tags/  →  Return all tags.
    No authentication required — tags are public.

    Concrete class: ListAPIView = ListModelMixin + GenericAPIView (GET list only).
    """

    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [AllowAny]


# ---------- User registration (write-only) ----------------------------------

class RegisterView(generics.CreateAPIView):
    """
    POST /auth/register/  →  Create a new user account.

    Concrete class: CreateAPIView = CreateModelMixin + GenericAPIView (POST only).
    Open to unauthenticated requests by design.
    """

    serializer_class = UserRegisterSerializer
    permission_classes = [AllowAny]


# ---------- Post list + create ----------------------------------------------

class PostListCreateView(generics.ListCreateAPIView):
    """
    GET  /posts/  →  Paginated list of published posts.
    POST /posts/  →  Create a new post (authenticated users only).

    Concrete class: ListCreateAPIView = List + Create + GenericAPIView.
    """

    serializer_class = PostListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self) -> PostQuerySet:
        """
        Unauthenticated users see only published posts.
        Authenticated users also see their own drafts.
        """
        qs = Post.objects.with_all_relations()
        if self.request.user.is_authenticated:
            return qs.filter(
                models.Q(status="published") | models.Q(author=self.request.user)
            )
        return qs.filter(status="published")

    def get_serializer_class(self) -> type:
        """Use the write serializer on POST, the lightweight one on GET."""
        if self.request.method == "POST":
            return PostCreateSerializer
        return PostListSerializer


# ---------- Post retrieve-only ----------------------------------------------

class PostDetailView(generics.RetrieveAPIView):
    """
    GET /posts/{pk}/  →  Full detail for a single post.

    Concrete class: RetrieveAPIView = RetrieveModelMixin + GenericAPIView.
    """

    queryset = Post.objects.with_all_relations()
    serializer_class = PostDetailSerializer
    permission_classes = [AllowAny]


# ---------- Post retrieve + update + delete ---------------------------------

class PostRUDView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /posts/{pk}/  →  retrieve
    PUT    /posts/{pk}/  →  full update
    PATCH  /posts/{pk}/  →  partial update
    DELETE /posts/{pk}/  →  destroy

    Concrete class: RetrieveUpdateDestroyAPIView = Retrieve + Update + Destroy
    Ownership is enforced at object level by IsOwnerOrReadOnly.
    """

    queryset = Post.objects.all()
    serializer_class = PostDetailSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]

    def perform_destroy(self, instance: Post) -> None:
        """
        Override destroy to soft-delete instead of hard-delete.
        Simply set status=draft and save; do not call instance.delete().
        """
        instance.status = "draft"
        instance.save(update_fields=["status", "updated_at"])


# ---------- User own-profile (GET + PATCH, no list) -------------------------

class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    GET   /users/me/  →  Return the authenticated user's profile.
    PATCH /users/me/  →  Partial update of the authenticated user's profile.

    Non-standard URL — /users/me/ — proves why concrete views beat ViewSets
    for custom-URL endpoints.
    """

    serializer_class = UserRegisterSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self) -> Any:
        """
        Override get_object() so the URL never exposes a {pk}.
        The object is always the requesting user.
        """
        return self.request.user


# ---------- Update-only avatar upload example --------------------------------

class UserAvatarUpdateView(generics.UpdateAPIView):
    """
    PATCH /users/me/avatar/  →  Upload / replace the user's avatar.

    Concrete class: UpdateAPIView = UpdateModelMixin + GenericAPIView (PUT + PATCH).
    In real usage the serializer would validate an ImageField.
    """

    serializer_class = UserRegisterSerializer  # replace with AvatarSerializer in production
    permission_classes = [IsAuthenticated]

    def get_object(self) -> Any:
        return self.request.user


# ==========================================================================
# 7. LEVEL 3 — ModelViewSet (all CRUD + Router URL generation)
# ==========================================================================

class PostViewSet(viewsets.ModelViewSet):
    """
    Full CRUD ViewSet for the Post resource.

    Router auto-generates the following URLs — no manual path() needed:
        GET    /posts/             → list
        POST   /posts/             → create
        GET    /posts/{pk}/        → retrieve
        PUT    /posts/{pk}/        → update
        PATCH  /posts/{pk}/        → partial_update
        DELETE /posts/{pk}/        → destroy
        GET    /posts/featured/    → @action (custom)
        POST   /posts/{pk}/publish/ → @action (custom)
        GET    /posts/{pk}/similar/ → @action (custom)
        GET    /posts/{pk}/comments/ → @action (custom)
        POST   /posts/{pk}/comments/ → @action (custom)
    """

    # Default queryset + serializer (overridden per-action below)
    queryset = Post.objects.with_all_relations()
    serializer_class = PostListSerializer

    # -------------------------------------------------------------------------
    # 7a. get_queryset — dynamic filtering based on action + user
    # -------------------------------------------------------------------------

    def get_queryset(self) -> PostQuerySet:
        """
        Return a filtered queryset based on the current action and the
        authentication state of the requesting user.

        - list: published posts + the user's own drafts (if authenticated)
        - detail actions: same rule, but a single object is resolved by pk
        """
        qs = Post.objects.with_all_relations()

        if self.action == "list":
            if self.request.user.is_authenticated:
                return qs.filter(
                    models.Q(status="published")
                    | models.Q(author=self.request.user)
                )
            return qs.filter(status="published")

        # For retrieve, update, partial_update, destroy:
        # authenticated users can see their own drafts.
        if self.request.user.is_authenticated:
            return qs.filter(
                models.Q(status="published")
                | models.Q(author=self.request.user)
            )
        return qs.filter(status="published")

    # -------------------------------------------------------------------------
    # 7b. get_serializer_class — lightweight for list, full for detail/write
    # -------------------------------------------------------------------------

    def get_serializer_class(self) -> type:
        """
        Select the appropriate serializer for the current action:
          - list      → PostListSerializer   (id, title, author_name only)
          - retrieve  → PostDetailSerializer (full content + nested tags)
          - write ops → PostCreateSerializer (writable fields only)
        """
        action_map = {
            "list":           PostListSerializer,
            "retrieve":       PostDetailSerializer,
            "create":         PostCreateSerializer,
            "update":         PostCreateSerializer,
            "partial_update": PostCreateSerializer,
        }
        return action_map.get(self.action, PostListSerializer)

    # -------------------------------------------------------------------------
    # 7c. get_permissions — per-action permission matrix
    # -------------------------------------------------------------------------

    def get_permissions(self) -> List[BasePermission]:
        """
        Permission matrix:
          - list / retrieve / featured / similar / comments (GET) → AllowAny
          - create                                                 → IsAuthenticated
          - update / partial_update / destroy / publish           → IsAuthenticated + IsOwnerOrReadOnly
        """
        if self.action in ("list", "retrieve", "featured"):
            return [AllowAny()]
        if self.action in ("update", "partial_update", "destroy"):
            return [IsAuthenticated(), IsOwnerOrReadOnly()]
        return [IsAuthenticated()]

    # -------------------------------------------------------------------------
    # 7d. perform_create — inject authenticated user as author
    # -------------------------------------------------------------------------

    def perform_create(self, serializer: serializers.BaseSerializer) -> None:
        """Save the new post with the requesting user as its author."""
        serializer.save(author=self.request.user)

    # -------------------------------------------------------------------------
    # 7e. @action — resource-level (detail=False): GET /posts/featured/
    # -------------------------------------------------------------------------

    @action(detail=False, methods=["get"], permission_classes=[AllowAny])
    def featured(self, request: Request) -> Response:
        """
        Return the six most-recent featured posts.
        URL: GET /posts/featured/
        """
        posts = Post.objects.published().featured()[:6]
        serializer = PostListSerializer(posts, many=True)
        return Response(serializer.data)

    # -------------------------------------------------------------------------
    # 7f. @action — object-level (detail=True): POST /posts/{pk}/publish/
    # -------------------------------------------------------------------------

    @action(detail=True, methods=["post"])
    def publish(self, request: Request, pk: Optional[int] = None) -> Response:
        """
        Transition a draft post to published state.
        Only the post's author can trigger this action.
        URL: POST /posts/{pk}/publish/
        """
        post: Post = self.get_object()  # triggers object-level permission check
        if post.status == "published":
            return Response(
                {"detail": "Post is already published."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        post.publish()
        return Response({"status": "published"})

    # -------------------------------------------------------------------------
    # 7g. @action — custom url_path: GET /posts/{pk}/similar/
    # -------------------------------------------------------------------------

    @action(
        detail=True,
        methods=["get"],
        url_path="similar",
        url_name="similar",
        permission_classes=[AllowAny],
    )
    def similar_posts(self, request: Request, pk: Optional[int] = None) -> Response:
        """
        Return up to five published posts in the same category (excluding self).
        URL: GET /posts/{pk}/similar/
        """
        post: Post = self.get_object()
        similar = (
            Post.objects.published()
            .filter(category=post.category)
            .exclude(pk=post.pk)[:5]
        )
        return Response(PostListSerializer(similar, many=True).data)

    # -------------------------------------------------------------------------
    # 7h. @action — multiple HTTP methods: GET + POST /posts/{pk}/comments/
    # -------------------------------------------------------------------------

    @action(detail=True, methods=["get", "post"], url_path="comments")
    def comments(self, request: Request, pk: Optional[int] = None) -> Response:
        """
        GET  /posts/{pk}/comments/  →  list approved comments for the post
        POST /posts/{pk}/comments/  →  add a new comment (authenticated)
        """
        post: Post = self.get_object()

        if request.method == "GET":
            approved_comments = post.comments.filter(is_approved=True)
            return Response(CommentSerializer(approved_comments, many=True).data)

        # POST — create a new comment
        serializer = CommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(post=post, author=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# ==========================================================================
# 8. ReadOnlyModelViewSet — read-only resource (list + retrieve only)
# ==========================================================================

class TagViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for the Tag resource.
    Exposes only list and retrieve — no create / update / delete.

    Router generates:
        GET /tags/       → list
        GET /tags/{pk}/  → retrieve
    """

    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [AllowAny]


# ==========================================================================
# 9. URL WIRING (urls.py reference — do not import, shows the pattern only)
# ==========================================================================

URL_PATTERNS_REFERENCE = """
# --- urls.py (blog app) ---

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register("posts", views.PostViewSet,    basename="post")
router.register("tags",  views.TagViewSet,     basename="tag")

urlpatterns = [
    # ViewSet + Router URLs (all CRUD + custom @actions auto-generated)
    path("api/v1/", include(router.urls)),

    # Concrete generic view URLs — manual, non-standard endpoints
    path("api/v1/auth/register/",      views.RegisterView.as_view(),      name="register"),
    path("api/v1/users/me/",           views.UserProfileView.as_view(),   name="user-profile"),
    path("api/v1/users/me/avatar/",    views.UserAvatarUpdateView.as_view(), name="user-avatar"),

    # GenericAPIView + Mixins demo endpoint
    path("api/v1/posts/mixin-demo/",   views.PostListMixinView.as_view(), name="post-mixin-demo"),
]
"""


# ==========================================================================
# 10. DECISION GUIDE — When to use which view class
# ==========================================================================

DECISION_GUIDE = """
Need                                     Use
─────────────────────────────────────────────────────────────────────────────
Full CRUD resource + auto URLs        →  ModelViewSet + Router
Read-only resource (GET only)         →  ReadOnlyModelViewSet + Router
Standard CRUD, manual URL control     →  RetrieveUpdateDestroyAPIView etc.
Login / Auth / Registration           →  CreateAPIView (or plain APIView)
Custom business logic (no DB model)   →  APIView
Webhook receiver                      →  APIView  (no serializer needed)
Admin data export                     →  generics.ListAPIView
User's own profile (GET + PATCH)      →  RetrieveUpdateAPIView + get_object()
Fine-grained mixin selection          →  GenericAPIView + chosen Mixins

Concrete generic view quick reference:
  ListAPIView                 → GET   (list)
  CreateAPIView               → POST
  RetrieveAPIView             → GET   (detail)
  UpdateAPIView               → PUT + PATCH
  DestroyAPIView              → DELETE
  ListCreateAPIView           → GET (list) + POST
  RetrieveUpdateAPIView       → GET (detail) + PUT + PATCH
  RetrieveDestroyAPIView      → GET (detail) + DELETE
  RetrieveUpdateDestroyAPIView → GET + PUT + PATCH + DELETE
"""
