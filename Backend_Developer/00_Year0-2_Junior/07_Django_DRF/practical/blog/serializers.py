"""
Blog Serializers — Advanced Patterns
══════════════════════════════════════════════════════
INTERVIEW: Dynamic fields serializer kya hota hai?
  Client specify kare ki response mein sirf kaunse fields chahiye:
  GET /api/v1/blog/posts/?fields=id,title,author — bandwidth save

INTERVIEW: Nested serializer write kaise handle karte hain?
  Read (read_only=True): automatic nested data
  Write: override create()/update() — manually process nested data

INTERVIEW: SerializerMethodField vs property?
  SerializerMethodField: serialization-specific computed fields
  @property on model: business logic across the codebase
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Post, Category, Tag, Comment

User = get_user_model()


# ─── Dynamic Fields Mixin ─────────────────────────────────
class DynamicFieldsMixin:
    """
    Allow clients to request only specific fields:
      GET /posts/?fields=id,title,author

    INTERVIEW: Ye pattern REST API bandwidth optimization ke liye common hai.
    GraphQL ka ek lightweight alternative.
    """
    def __init__(self, *args, **kwargs):
        fields = kwargs.pop("fields", None)
        super().__init__(*args, **kwargs)

        if fields:
            # Remove any fields not specified
            allowed = set(fields.split(","))
            existing = set(self.fields.keys())
            for field_name in existing - allowed:
                self.fields.pop(field_name)

    def to_representation(self, instance):
        """Also support ?fields= from request query params."""
        request = self.context.get("request")
        if request:
            fields_param = request.query_params.get("fields")
            if fields_param:
                allowed = set(fields_param.split(","))
                for field_name in set(self.fields.keys()) - allowed:
                    self.fields.pop(field_name, None)
        return super().to_representation(instance)


# ─── Tag Serializer ───────────────────────────────────────
class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Tag
        fields = ["id", "name", "slug", "color"]
        read_only_fields = ["id", "slug"]


# ─── Category Serializer ──────────────────────────────────
class CategorySerializer(serializers.ModelSerializer):
    post_count = serializers.SerializerMethodField()

    class Meta:
        model  = Category
        fields = ["id", "name", "slug", "description", "post_count"]
        read_only_fields = ["id", "slug"]

    def get_post_count(self, obj) -> int:
        # If annotated via with_post_count(), use annotation; else query
        return getattr(obj, "post_count", obj.posts.filter(
            status=Post.Status.PUBLISHED, deleted_at__isnull=True
        ).count())


# ─── Author Summary Serializer ────────────────────────────
class AuthorSummarySerializer(serializers.ModelSerializer):
    """Minimal author info for embedding in post lists."""
    full_name = serializers.CharField(source="full_name", read_only=True)
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model  = User
        fields = ["id", "email", "full_name", "avatar_url"]

    def get_avatar_url(self, obj) -> str | None:
        request = self.context.get("request")
        if obj.avatar and request:
            return request.build_absolute_uri(obj.avatar.url)
        return None


# ─── Comment Serializer ───────────────────────────────────
class CommentSerializer(serializers.ModelSerializer):
    author = AuthorSummarySerializer(read_only=True)
    replies_count = serializers.SerializerMethodField()

    class Meta:
        model  = Comment
        fields = ["id", "author", "content", "parent", "is_reply",
                  "replies_count", "created_at"]
        read_only_fields = ["id", "author", "is_reply", "created_at"]

    def get_replies_count(self, obj) -> int:
        return obj.replies.filter(is_approved=True).count()

    def create(self, validated_data: dict) -> Comment:
        validated_data["author"] = self.context["request"].user
        return super().create(validated_data)


# ─── Post List Serializer (lightweight) ───────────────────
class PostListSerializer(DynamicFieldsMixin, serializers.ModelSerializer):
    """Serializer for list views — no heavy fields like content."""
    author   = AuthorSummarySerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    tags     = TagSerializer(many=True, read_only=True)
    comment_count = serializers.IntegerField(
        source="comment_count",  # from annotation
        read_only=True,
        default=0,
    )

    class Meta:
        model  = Post
        fields = [
            "id", "title", "slug", "excerpt", "cover_img",
            "author", "category", "tags",
            "status", "is_featured", "published_at",
            "views_count", "likes_count", "read_time_minutes",
            "comment_count", "created_at",
        ]
        read_only_fields = fields


# ─── Post Detail Serializer (full content) ────────────────
class PostDetailSerializer(PostListSerializer):
    """Full post for detail view — includes content + top-level comments."""
    recent_comments = serializers.SerializerMethodField()

    class Meta(PostListSerializer.Meta):
        fields = PostListSerializer.Meta.fields + ["content", "recent_comments"]

    def get_recent_comments(self, obj) -> list:
        """Top 5 approved top-level comments."""
        top_comments = obj.comments.filter(
            is_approved=True, parent__isnull=True
        ).select_related("author").order_by("-created_at")[:5]
        return CommentSerializer(top_comments, many=True, context=self.context).data


# ─── Post Write Serializer ────────────────────────────────
class PostCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating/updating posts.
    Handles M2M tags as list of IDs.

    INTERVIEW: tags = PrimaryKeyRelatedField(many=True) kya karta hai?
      - Read: list of tag IDs
      - Write: accepts list of existing tag IDs, sets M2M relation
    """
    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True, required=False
    )

    class Meta:
        model  = Post
        fields = ["title", "content", "excerpt", "cover_img",
                  "category", "tags", "status", "is_featured"]

    def validate_title(self, value: str) -> str:
        if len(value.strip()) < 5:
            raise serializers.ValidationError("Title must be at least 5 characters")
        return value.strip()

    def validate(self, data: dict) -> dict:
        # Drafts don't need excerpt; published posts do
        if data.get("status") == Post.Status.PUBLISHED and not data.get("excerpt"):
            raise serializers.ValidationError(
                {"excerpt": "Excerpt required when publishing a post"}
            )
        return data

    def create(self, validated_data: dict) -> Post:
        tags = validated_data.pop("tags", [])
        validated_data["author"] = self.context["request"].user
        post = Post.objects.create(**validated_data)
        post.tags.set(tags)  # set M2M
        return post

    def update(self, instance: Post, validated_data: dict) -> Post:
        tags = validated_data.pop("tags", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if tags is not None:
            instance.tags.set(tags)  # replace all existing tags
        return instance
