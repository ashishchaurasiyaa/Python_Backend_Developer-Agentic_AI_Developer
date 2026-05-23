"""Blog Admin — with list_select_related and actions."""
from django.contrib import admin
from .models import Post, Category, Tag, Comment


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display  = ["title", "author", "category", "status", "is_featured",
                     "views_count", "published_at", "created_at"]
    list_filter   = ["status", "is_featured", "category"]
    search_fields = ["title", "content", "author__email"]
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ["tags"]
    raw_id_fields = ["author", "category"]  # FK lookup widget for large datasets
    list_select_related = ["author", "category"]  # avoid N+1 in list

    actions = ["publish_posts", "archive_posts"]

    @admin.action(description="Publish selected posts")
    def publish_posts(self, request, queryset):
        for post in queryset.filter(status=Post.Status.DRAFT):
            post.publish()
        self.message_user(request, "Posts published.")

    @admin.action(description="Archive selected posts")
    def archive_posts(self, request, queryset):
        queryset.update(status=Post.Status.ARCHIVED)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "color"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display  = ["author", "post", "is_approved", "is_reply", "created_at"]
    list_filter   = ["is_approved"]
    search_fields = ["content", "author__email", "post__title"]
    actions       = ["approve_comments"]

    @admin.action(description="Approve selected comments")
    def approve_comments(self, request, queryset):
        queryset.update(is_approved=True)
