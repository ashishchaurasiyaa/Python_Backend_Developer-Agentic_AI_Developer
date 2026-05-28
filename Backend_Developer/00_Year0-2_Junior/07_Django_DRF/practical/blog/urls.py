"""Blog App URLs."""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PostViewSet, CategoryViewSet, TagViewSet

app_name = "blog"

router = DefaultRouter()
router.register(r"posts",      PostViewSet,    basename="post")
router.register(r"categories", CategoryViewSet, basename="category")
router.register(r"tags",       TagViewSet,     basename="tag")

urlpatterns = [
    path("", include(router.urls)),
]

# Auto-generated + custom URLs:
# GET    /api/v1/blog/posts/                    → list
# POST   /api/v1/blog/posts/                    → create
# GET    /api/v1/blog/posts/{id}/               → retrieve
# PUT    /api/v1/blog/posts/{id}/               → update
# PATCH  /api/v1/blog/posts/{id}/               → partial_update
# DELETE /api/v1/blog/posts/{id}/               → destroy (soft)
# POST   /api/v1/blog/posts/{id}/publish/       → publish
# POST   /api/v1/blog/posts/{id}/like/          → like
# GET    /api/v1/blog/posts/featured/           → featured
# GET    /api/v1/blog/posts/{id}/comments/      → comments
# POST   /api/v1/blog/posts/{id}/comments/add/  → add_comment
#
# GET    /api/v1/blog/categories/               → list
# GET    /api/v1/blog/categories/{id}/          → retrieve
#
# GET    /api/v1/blog/tags/                     → list (all)
