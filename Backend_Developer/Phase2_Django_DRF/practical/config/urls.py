"""
Root URL Configuration
═══════════════════════
API Structure:
  /api/v1/auth/    — JWT login, refresh, logout
  /api/v1/users/   — User CRUD + /me endpoint
  /api/v1/blog/    — Posts, Categories, Tags, Comments
  /ws/chat/<room>/ — WebSocket chat
  /admin/          — Django admin
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenBlacklistView,
)

urlpatterns = [
    # Django Admin
    path("admin/", admin.site.urls),

    # JWT Auth endpoints
    path("api/v1/auth/login/",   TokenObtainPairView.as_view(),   name="token_obtain_pair"),
    path("api/v1/auth/refresh/", TokenRefreshView.as_view(),      name="token_refresh"),
    path("api/v1/auth/logout/",  TokenBlacklistView.as_view(),    name="token_blacklist"),

    # App routers
    path("api/v1/users/", include("users.urls", namespace="users")),
    path("api/v1/blog/",  include("blog.urls",  namespace="blog")),

    # DRF Browsable API login (dev only)
    path("api-auth/", include("rest_framework.urls")),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
