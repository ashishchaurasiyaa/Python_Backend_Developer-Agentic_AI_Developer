"""
User Views (DRF ViewSets + APIView)
═══════════════════════════════════════════════════════
INTERVIEW: ModelViewSet vs GenericAPIView vs APIView?
  APIView:
    + Maximum control, no magic
    - Most boilerplate
    Use: unusual patterns, non-model views

  GenericAPIView + mixins:
    + Pick only the operations you want
    Use: partial CRUD (list + create but no delete)

  ModelViewSet:
    + All CRUD in one class, Router auto-generates URLs
    Use: standard CRUD resources

  ReadOnlyModelViewSet:
    + Only list + retrieve
    Use: public catalog-style endpoints

INTERVIEW: get_queryset() vs queryset attribute fark?
  queryset = ... (class level):
    - Set once at class definition
    - Django caches it — stale data risk in long-running processes

  def get_queryset(self):
    + Called per request — fresh, can use request.user, query params
    + For user-scoped data: filter by request.user
"""

from django.contrib.auth import get_user_model
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers
from rest_framework import viewsets, generics, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from core.permissions import IsOwnerOrReadOnly, IsPremiumUser
from .serializers import (
    UserSerializer,
    UserRegisterSerializer,
    UserUpdateSerializer,
    ChangePasswordSerializer,
)
from .signals import user_email_verified

User = get_user_model()


# ─── Registration Throttle ────────────────────────────────
class RegistrationThrottle(UserRateThrottle):
    scope = "login"  # 5/minute


# ─── Registration View ────────────────────────────────────
class RegisterView(generics.CreateAPIView):
    """
    POST /api/v1/users/register/
    Public — no auth required.
    """
    serializer_class = UserRegisterSerializer
    permission_classes = [AllowAny]
    throttle_classes  = [RegistrationThrottle]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return Response(
            {
                "success": True,
                "data": {
                    "user": UserSerializer(user).data,
                    "message": "Registration successful. Please verify your email.",
                },
            },
            status=status.HTTP_201_CREATED,
        )


# ─── User ViewSet ─────────────────────────────────────────
class UserViewSet(viewsets.ModelViewSet):
    """
    CRUD endpoints for Users.

    GET    /api/v1/users/           → list (admin only)
    POST   /api/v1/users/           → create (use /register/ instead)
    GET    /api/v1/users/{id}/      → retrieve
    PUT    /api/v1/users/{id}/      → update
    PATCH  /api/v1/users/{id}/      → partial update
    DELETE /api/v1/users/{id}/      → deactivate (soft)
    GET    /api/v1/users/me/        → current user profile
    POST   /api/v1/users/me/change-password/ → change password
    POST   /api/v1/users/{id}/verify-email/ → verify email
    """
    http_method_names = ["get", "put", "patch", "delete", "post", "head", "options"]

    def get_queryset(self):
        """
        INTERVIEW: Admin sab dekhe, normal user sirf apna.
        select_related("profile") — N+1 fix for profile access.
        """
        qs = User.objects.select_related("profile").filter(is_active=True)
        if self.request.user.is_staff:
            return qs
        return qs.filter(id=self.request.user.id)

    def get_serializer_class(self):
        if self.action in ("update", "partial_update"):
            return UserUpdateSerializer
        return UserSerializer

    def get_permissions(self):
        if self.action == "list":
            return [IsAdminUser()]
        if self.action in ("update", "partial_update", "destroy"):
            return [IsAuthenticated(), IsOwnerOrReadOnly()]
        return [IsAuthenticated()]

    def destroy(self, request, *args, **kwargs):
        """Soft delete — deactivate instead of hard delete."""
        user = self.get_object()
        user.is_active = False
        user.save(update_fields=["is_active"])
        return Response({"success": True, "message": "Account deactivated"},
                        status=status.HTTP_200_OK)

    # ── Custom Actions ─────────────────────────────────────

    @action(detail=False, methods=["get"], url_path="me")
    @method_decorator(cache_page(60))             # cache for 60 seconds
    @method_decorator(vary_on_headers("Authorization"))  # per-user cache
    def me(self, request):
        """GET /api/v1/users/me/ — current user profile."""
        serializer = UserSerializer(request.user)
        return Response({"success": True, "data": serializer.data})

    @action(detail=False, methods=["patch"], url_path="me/update",
            serializer_class=UserUpdateSerializer)
    def update_me(self, request):
        """PATCH /api/v1/users/me/update/ — update own profile."""
        serializer = UserUpdateSerializer(
            request.user, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"success": True, "data": UserSerializer(request.user).data})

    @action(detail=False, methods=["post"], url_path="me/change-password",
            serializer_class=ChangePasswordSerializer)
    def change_password(self, request):
        """POST /api/v1/users/me/change-password/"""
        serializer = ChangePasswordSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"success": True, "message": "Password updated successfully"})

    @action(detail=True, methods=["post"], url_path="verify-email",
            permission_classes=[IsAdminUser])
    def verify_email(self, request, pk=None):
        """POST /api/v1/users/{id}/verify-email/ — admin triggers verification."""
        user = self.get_object()
        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])
        user_email_verified.send(sender=User, instance=user)
        return Response({"success": True, "message": "Email verified"})

    @action(detail=False, methods=["get"], url_path="premium-only",
            permission_classes=[IsAuthenticated, IsPremiumUser])
    def premium_dashboard(self, request):
        """GET /api/v1/users/premium-only/ — premium users only."""
        return Response({"success": True, "data": {"message": "Welcome to premium!"}})
