"""
Users App URL Configuration
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, RegisterView

app_name = "users"

router = DefaultRouter()
router.register(r"", UserViewSet, basename="user")

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("", include(router.urls)),
]

# Auto-generated URLs from router:
# GET    /api/v1/users/                    → list (admin)
# GET    /api/v1/users/{id}/               → retrieve
# PUT    /api/v1/users/{id}/               → update
# PATCH  /api/v1/users/{id}/               → partial_update
# DELETE /api/v1/users/{id}/               → destroy (soft)
# GET    /api/v1/users/me/                 → me
# PATCH  /api/v1/users/me/update/          → update_me
# POST   /api/v1/users/me/change-password/ → change_password
# POST   /api/v1/users/{id}/verify-email/  → verify_email
# GET    /api/v1/users/premium-only/       → premium_dashboard
