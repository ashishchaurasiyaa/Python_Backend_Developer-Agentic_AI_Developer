"""
Blog Views
══════════════════════════════════════════════════════
Demonstrates:
  - ModelViewSet with get_serializer_class() per action
  - get_queryset() for access control + eager loading
  - Filtering, search, ordering
  - Custom actions
  - Transactions + select_for_update
  - Caching (cache_page + cache.set/get)
  - Atomic operations
"""

from django.db import transaction
from django.db.models import F
from django.core.cache import cache
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAuthenticated, AllowAny
from rest_framework.response import Response

from core.pagination import StandardPageNumberPagination
from core.permissions import IsOwnerOrReadOnly, IsAdminOrReadOnly
from .models import Post, Category, Tag, Comment
from .serializers import (
    PostListSerializer, PostDetailSerializer, PostCreateUpdateSerializer,
    CategorySerializer, TagSerializer, CommentSerializer,
)
from .filters import PostFilter


# ─── Post ViewSet ─────────────────────────────────────────
class PostViewSet(viewsets.ModelViewSet):
    """
    Full CRUD for blog posts + custom actions.

    List:     GET    /api/v1/blog/posts/
    Create:   POST   /api/v1/blog/posts/
    Detail:   GET    /api/v1/blog/posts/{id}/
    Update:   PUT    /api/v1/blog/posts/{id}/
    Partial:  PATCH  /api/v1/blog/posts/{id}/
    Delete:   DELETE /api/v1/blog/posts/{id}/
    Publish:  POST   /api/v1/blog/posts/{id}/publish/
    Like:     POST   /api/v1/blog/posts/{id}/like/
    Featured: GET    /api/v1/blog/posts/featured/
    """
    permission_classes    = [IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]
    filterset_class       = PostFilter
    search_fields         = ["title", "excerpt", "content"]   # SearchFilter
    ordering_fields       = ["published_at", "created_at", "views_count", "likes_count"]
    ordering              = ["-published_at"]                  # default ordering

    def get_queryset(self):
        """
        Load eagerly to avoid N+1.
        For unauthenticated: only published.
        For authenticated: own drafts + all published.
        """
        user = self.request.user

        if user.is_authenticated:
            qs = Post.objects.for_user(user)
        else:
            qs = Post.objects.published().with_all_relations()

        # For list view: annotate with comment count
        if self.action == "list":
            qs = qs.with_comment_count()

        return qs

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return PostCreateUpdateSerializer
        if self.action == "retrieve":
            return PostDetailSerializer
        return PostListSerializer

    def retrieve(self, request, *args, **kwargs):
        """Increment view count atomically when post is read."""
        instance = self.get_object()
        # F() expression — atomic increment in DB (no race condition)
        Post.objects.filter(pk=instance.pk).update(views_count=F("views_count") + 1)
        serializer = self.get_serializer(instance)
        return Response({"success": True, "data": serializer.data})

    def destroy(self, request, *args, **kwargs):
        """Soft delete via BaseModel.delete()."""
        instance = self.get_object()
        instance.delete()  # SoftDeleteMixin.delete() → sets deleted_at
        return Response({"success": True, "message": "Post deleted"},
                        status=status.HTTP_200_OK)

    # ── Custom Actions ─────────────────────────────────────

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, IsOwnerOrReadOnly])
    def publish(self, request, pk=None):
        """
        POST /api/v1/blog/posts/{id}/publish/
        Publish a draft post.
        Uses transaction to ensure consistency.
        """
        post = self.get_object()

        if post.is_published:
            return Response(
                {"success": False, "error": {"message": "Post already published"}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            post.publish()

        return Response({
            "success": True,
            "data": {
                "message": "Post published",
                "published_at": post.published_at,
            },
        })

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def like(self, request, pk=None):
        """
        POST /api/v1/blog/posts/{id}/like/
        Atomic like increment — no race conditions.

        INTERVIEW: F() expression kyu use karte hain?
          likes_count = F("likes_count") + 1
          → single UPDATE likes_count = likes_count + 1 in SQL
          → atomic — no read-modify-write race condition
          Compare to:
          post.likes_count += 1; post.save()  ← WRONG (race condition)
        """
        post = self.get_object()
        Post.objects.filter(pk=post.pk).update(likes_count=F("likes_count") + 1)
        # Refresh to get updated value
        post.refresh_from_db(fields=["likes_count"])
        return Response({"success": True, "data": {"likes": post.likes_count}})

    @action(detail=False, methods=["get"], permission_classes=[AllowAny])
    @method_decorator(cache_page(300))  # cache for 5 minutes
    def featured(self, request):
        """
        GET /api/v1/blog/posts/featured/
        Featured posts — cached for 5 minutes.

        INTERVIEW: cache_page vs cache.set/get?
          cache_page: whole view response cache (simple, coarse)
          cache.set/get: fine-grained — only cache specific queryset/data
        """
        posts = (
            Post.objects.published()
                .with_all_relations()
                .featured()
                .with_comment_count()[:6]
        )
        serializer = PostListSerializer(posts, many=True, context={"request": request})
        return Response({"success": True, "data": serializer.data})

    @action(detail=True, methods=["get"], permission_classes=[AllowAny])
    def comments(self, request, pk=None):
        """GET /api/v1/blog/posts/{id}/comments/ — top-level comments."""
        post = self.get_object()
        comments = (
            post.comments
                .filter(is_approved=True, parent__isnull=True)
                .select_related("author")
                .prefetch_related("replies__author")
                .order_by("-created_at")
        )

        page = self.paginate_queryset(comments)
        if page is not None:
            serializer = CommentSerializer(page, many=True, context={"request": request})
            return self.get_paginated_response(serializer.data)

        serializer = CommentSerializer(comments, many=True, context={"request": request})
        return Response({"success": True, "data": serializer.data})

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated],
            url_path="comments/add")
    def add_comment(self, request, pk=None):
        """POST /api/v1/blog/posts/{id}/comments/add/"""
        post = self.get_object()
        serializer = CommentSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        comment = serializer.save(post=post)
        return Response(
            {"success": True, "data": CommentSerializer(comment).data},
            status=status.HTTP_201_CREATED,
        )


# ─── Category ViewSet ─────────────────────────────────────
class CategoryViewSet(viewsets.ModelViewSet):
    """CRUD for categories — write ops admin-only."""
    queryset           = Category.objects.all()
    serializer_class   = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]
    search_fields      = ["name", "description"]
    ordering_fields    = ["name", "created_at"]
    pagination_class   = StandardPageNumberPagination


# ─── Tag ViewSet ──────────────────────────────────────────
class TagViewSet(viewsets.ModelViewSet):
    queryset           = Tag.objects.all()
    serializer_class   = TagSerializer
    permission_classes = [IsAdminOrReadOnly]
    search_fields      = ["name"]
    ordering_fields    = ["name"]
    pagination_class   = None  # return all tags (usually small dataset)
