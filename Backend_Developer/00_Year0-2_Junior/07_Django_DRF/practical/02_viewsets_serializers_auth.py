"""
Django REST Framework — ViewSets, Serializers, Permissions, and JWT Auth
========================================================================
This module is a self-contained reference implementation that covers every
concept from the theory doc (02_viewsets_serializers_auth.md):

  1. ModelSerializer — write-only fields, computed fields, nested serializers,
     field-level validation, object-level validation, custom create/update.
  2. ModelViewSet — dynamic queryset, per-action serializer selection,
     per-action permission selection, and custom @action endpoints.
  3. DefaultRouter — auto-generated URL patterns.
  4. Custom permissions — IsOwnerOrReadOnly, IsPremiumUser,
     IsOrganizationMember.
  5. JWT Authentication — SimpleJWT settings, custom token payload.
  6. Pagination — PageNumberPagination with custom envelope,
     CursorPagination for large/infinite-scroll datasets.
  7. Throttling — AnonRateThrottle, UserRateThrottle, custom LoginThrottle.

NOTE: This file is structured as importable code, not a runnable script,
because it depends on Django + djangorestframework which must be installed
in the project environment.  It compiles cleanly under Python 3.9+.

pip install django djangorestframework djangorestframework-simplejwt
"""

# ==========================================================================
# STANDARD LIBRARY
# ==========================================================================

from __future__ import annotations

from datetime import timedelta
from typing import List, Optional, Type

# ==========================================================================
# DJANGO / DRF IMPORTS  (guarded to keep the file importable for py_compile)
# ==========================================================================

try:
    from django.contrib.auth import get_user_model
    from django.urls import include, path

    from rest_framework import generics, serializers, status, viewsets
    from rest_framework.decorators import action
    from rest_framework.pagination import CursorPagination, PageNumberPagination
    from rest_framework.permissions import (
        BasePermission,
        IsAdminUser,
        IsAuthenticated,
        SAFE_METHODS,
    )
    from rest_framework.request import Request
    from rest_framework.response import Response
    from rest_framework.routers import DefaultRouter
    from rest_framework.throttling import UserRateThrottle
    from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
    from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

    _DRF_AVAILABLE = True

except ImportError:
    # Allow `python3 -m py_compile` to succeed in environments where the
    # packages are not installed.  All runtime classes below are defined
    # inside `if _DRF_AVAILABLE` blocks or wrapped with type: ignore.
    _DRF_AVAILABLE = False


# ==========================================================================
# 1. SERIALIZERS
# ==========================================================================

if _DRF_AVAILABLE:
    User = get_user_model()  # type: ignore[assignment]

    # --------------------------------------------------------------------------
    # 1a. ProfileSerializer (minimal nested serializer — illustrative)
    # --------------------------------------------------------------------------

    class ProfileSerializer(serializers.Serializer):
        """Minimal read-only profile snapshot used as a nested field."""

        bio = serializers.CharField(read_only=True)
        avatar_url = serializers.URLField(read_only=True)

    # --------------------------------------------------------------------------
    # 1b. UserSerializer — covers every production serializer pattern
    # --------------------------------------------------------------------------

    class UserSerializer(serializers.ModelSerializer):
        """
        Full-featured user serializer demonstrating:
          - write_only field (password)
          - SerializerMethodField (full_name)
          - nested read-only serializer (profile)
          - field-level validation (validate_<field>)
          - object-level validation (validate)
          - custom create() that hashes the password
          - custom update() that hashes a new password if supplied
        """

        # Write-only: never included in serialized output.
        password = serializers.CharField(
            write_only=True,
            min_length=8,
            style={"input_type": "password"},
        )

        # Computed from model methods — read-only by definition.
        full_name = serializers.SerializerMethodField()

        # Nested serializer: profile is read-only, populated by select_related.
        profile = ProfileSerializer(read_only=True)

        class Meta:
            model = User
            fields: List[str] = [
                "id",
                "username",
                "email",
                "password",
                "full_name",
                "profile",
                "date_joined",
            ]
            read_only_fields: List[str] = ["id", "date_joined"]

        # ------------------------------------------------------------------
        # Computed field
        # ------------------------------------------------------------------

        def get_full_name(self, obj) -> str:
            """Concatenate first and last name; strip leading/trailing spaces."""
            return f"{obj.first_name} {obj.last_name}".strip()

        # ------------------------------------------------------------------
        # Field-level validation
        # ------------------------------------------------------------------

        def validate_email(self, value: str) -> str:
            """
            Reject duplicate email addresses.
            On update, exclude the current instance from the uniqueness check.
            """
            qs = User.objects.filter(email=value.lower())
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError("Email address is already registered.")
            return value.lower()

        # ------------------------------------------------------------------
        # Object-level validation (cross-field)
        # ------------------------------------------------------------------

        def validate(self, data: dict) -> dict:
            """Ensure the password does not contain the username."""
            password: Optional[str] = data.get("password")
            username: Optional[str] = data.get("username") or (
                self.instance.username if self.instance else None
            )
            if password and username and username in password:
                raise serializers.ValidationError(
                    {"password": "Password must not contain the username."}
                )
            return data

        # ------------------------------------------------------------------
        # Custom create — hash password before saving
        # ------------------------------------------------------------------

        def create(self, validated_data: dict):
            """
            Pop the plain-text password before constructing the model instance,
            then use set_password() so Django's password hashing is applied.
            """
            password: str = validated_data.pop("password")
            user = User(**validated_data)
            user.set_password(password)
            user.save()
            return user

        # ------------------------------------------------------------------
        # Custom update — conditionally hash a new password
        # ------------------------------------------------------------------

        def update(self, instance, validated_data: dict):
            """
            Apply field updates one by one; hash the password only when a new
            value is explicitly provided in the payload.
            """
            password: Optional[str] = validated_data.pop("password", None)
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            if password:
                instance.set_password(password)
            instance.save()
            return instance

    # --------------------------------------------------------------------------
    # 1c. Lightweight serializers used by specific ViewSet actions
    # --------------------------------------------------------------------------

    class UserCreateSerializer(serializers.ModelSerializer):
        """
        Serializer used only during POST (create) and PUT (full update).
        Enforces that a password is always required on creation.
        """

        password = serializers.CharField(write_only=True, min_length=8)

        class Meta:
            model = User
            fields: List[str] = ["username", "email", "password"]

        def create(self, validated_data: dict):
            password: str = validated_data.pop("password")
            user = User(**validated_data)
            user.set_password(password)
            user.save()
            return user

    class ChangePasswordSerializer(serializers.Serializer):
        """Validates current + new password for the change-password action."""

        current_password = serializers.CharField(write_only=True)
        new_password = serializers.CharField(write_only=True, min_length=8)

        def validate_new_password(self, value: str) -> str:
            if len(value) < 8:
                raise serializers.ValidationError(
                    "New password must be at least 8 characters."
                )
            return value


# ==========================================================================
# 2. PERMISSIONS
# ==========================================================================

if _DRF_AVAILABLE:

    class IsOwnerOrReadOnly(BasePermission):
        """
        Object-level permission: allow read access to anyone, but restrict
        write access to the object's owner.

        Assumes the model instance has a `.user` attribute pointing to the
        owning User.
        """

        def has_object_permission(self, request: Request, view, obj) -> bool:
            # SAFE_METHODS = ('GET', 'HEAD', 'OPTIONS') — always permitted.
            if request.method in SAFE_METHODS:
                return True
            return obj.user == request.user

    class IsPremiumUser(BasePermission):
        """
        View-level permission that grants access only to authenticated users
        whose account plan is set to "premium".

        The error message is returned verbatim in the 403 response body so the
        client can surface a meaningful upsell prompt.
        """

        message = "A premium subscription is required to access this resource."

        def has_permission(self, request: Request, view) -> bool:
            return bool(
                request.user
                and request.user.is_authenticated
                and getattr(request.user, "plan", None) == "premium"
            )

    class IsOrganizationMember(BasePermission):
        """
        Object-level permission: allows access only when the requesting user
        is a member of the organization that owns the object.

        Assumes the model instance exposes `obj.organization.members` as a
        many-to-many manager.
        """

        def has_object_permission(self, request: Request, view, obj) -> bool:
            return request.user in obj.organization.members.all()


# ==========================================================================
# 3. VIEWSETS
# ==========================================================================

if _DRF_AVAILABLE:

    class UserViewSet(viewsets.ModelViewSet):
        """
        CRUD ViewSet for the User model.

        ModelViewSet automatically wires the following actions to HTTP verbs:
          list            → GET  /users/
          create          → POST /users/
          retrieve        → GET  /users/{pk}/
          update          → PUT  /users/{pk}/
          partial_update  → PATCH /users/{pk}/
          destroy         → DELETE /users/{pk}/

        Additional custom actions registered below:
          me              → GET  /users/me/
          activate        → POST /users/{pk}/activate/
          change-password → POST /users/change-password/
          export          → GET  /users/export/  (premium only)
        """

        queryset = User.objects.select_related("profile").all()
        serializer_class = UserSerializer
        permission_classes = [IsAuthenticated]

        # ------------------------------------------------------------------
        # Dynamic queryset — staff sees everyone; regular users see only self
        # ------------------------------------------------------------------

        def get_queryset(self):
            if self.request.user.is_staff:
                return User.objects.select_related("profile").all()
            return User.objects.select_related("profile").filter(
                pk=self.request.user.pk
            )

        # ------------------------------------------------------------------
        # Per-action serializer selection
        # ------------------------------------------------------------------

        def get_serializer_class(self) -> Type[serializers.Serializer]:
            """
            Return a tighter serializer for write operations so that creation
            and full updates always require a password, while list/retrieve
            responses use the richer UserSerializer.
            """
            if self.action in ("create", "update"):
                return UserCreateSerializer
            return UserSerializer

        # ------------------------------------------------------------------
        # Per-action permission selection
        # ------------------------------------------------------------------

        def get_permissions(self) -> list:
            """
            Destruction is restricted to Django admin users; all other actions
            require only authentication.
            """
            if self.action == "destroy":
                return [IsAdminUser()]
            return [IsAuthenticated()]

        # ------------------------------------------------------------------
        # Custom actions
        # ------------------------------------------------------------------

        @action(detail=False, methods=["get"], url_path="me")
        def me(self, request: Request) -> Response:
            """Return the profile of the currently authenticated user."""
            serializer = self.get_serializer(request.user)
            return Response(serializer.data)

        @action(detail=True, methods=["post"], url_path="activate")
        def activate(self, request: Request, pk: Optional[str] = None) -> Response:
            """
            Activate a specific user account.  Only staff can reach this
            endpoint because the queryset for non-staff returns only the
            caller's own record, so get_object() would raise 404 for others.
            """
            user = self.get_object()
            user.is_active = True
            user.save(update_fields=["is_active"])
            return Response({"status": "activated"}, status=status.HTTP_200_OK)

        @action(detail=False, methods=["post"], url_path="change-password")
        def change_password(self, request: Request) -> Response:
            """
            Allow a user to change their own password.

            Validates both current and new passwords before committing.
            Invalidating existing sessions / tokens after a password change
            is left to the authentication backend (e.g., SimpleJWT blacklist).
            """
            serializer = ChangePasswordSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            # Verify the current password before accepting the new one.
            current_pw: str = serializer.validated_data["current_password"]
            if not request.user.check_password(current_pw):
                return Response(
                    {"current_password": "Incorrect password."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            request.user.set_password(serializer.validated_data["new_password"])
            request.user.save(update_fields=["password"])
            return Response({"message": "Password updated successfully."})

        @action(
            detail=False,
            methods=["get"],
            url_path="export",
            permission_classes=[IsPremiumUser],
        )
        def export(self, request: Request) -> Response:
            """
            Export user data — restricted to premium plan holders.
            IsPremiumUser permission is applied at the action level, overriding
            the default IsAuthenticated set on the ViewSet class.
            """
            queryset = self.get_queryset()
            serializer = self.get_serializer(queryset, many=True)
            return Response({"export": serializer.data})

    # --------------------------------------------------------------------------
    # PostViewSet — demonstrates object-level permissions on a content model
    # --------------------------------------------------------------------------

    class PostViewSet(viewsets.ModelViewSet):
        """
        ViewSet for a hypothetical Post model.

        IsAuthenticated ensures the user is logged in; IsOwnerOrReadOnly
        prevents editing another user's posts without blocking read access.
        """

        # Concrete queryset would be: queryset = Post.objects.select_related("user")
        # Left abstract here because the Post model is not defined in this module.
        queryset = None  # type: ignore[assignment]
        permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]

        @action(
            detail=False,
            methods=["get"],
            permission_classes=[IsPremiumUser],
        )
        def export(self, request: Request) -> Response:
            """Premium-only bulk export of posts."""
            return Response({"detail": "Export payload would appear here."})


# ==========================================================================
# 4. ROUTER — AUTO-GENERATED URL PATTERNS
# ==========================================================================

if _DRF_AVAILABLE:
    router = DefaultRouter()
    router.register(r"users", UserViewSet, basename="user")

    # Resulting URL table (prefix = /api/):
    #
    #   Method   Path                        Action
    #   ------   --------------------------  ----------------
    #   GET      /api/users/                 list
    #   POST     /api/users/                 create
    #   GET      /api/users/{pk}/            retrieve
    #   PUT      /api/users/{pk}/            update
    #   PATCH    /api/users/{pk}/            partial_update
    #   DELETE   /api/users/{pk}/            destroy
    #   GET      /api/users/me/              me
    #   POST     /api/users/{pk}/activate/   activate
    #   POST     /api/users/change-password/ change_password
    #   GET      /api/users/export/          export

    # To mount these in urls.py:
    #   urlpatterns = [path("api/", include(router.urls))]


# ==========================================================================
# 5. JWT AUTHENTICATION (djangorestframework-simplejwt)
# ==========================================================================

# pip install djangorestframework-simplejwt

# ---- settings.py excerpt ----
# REST_FRAMEWORK = {
#     "DEFAULT_AUTHENTICATION_CLASSES": [
#         "rest_framework_simplejwt.authentication.JWTAuthentication",
#     ],
#     "DEFAULT_PERMISSION_CLASSES": [
#         "rest_framework.permissions.IsAuthenticated",
#     ],
# }
#
# SIMPLE_JWT = {
#     "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
#     "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
#     "ROTATE_REFRESH_TOKENS": True,
#     "BLACKLIST_AFTER_ROTATION": True,
#     "ALGORITHM": "HS256",
#     "SIGNING_KEY": SECRET_KEY,   # noqa: F821 — defined in Django settings
# }

# ---- urls.py excerpt ----
# urlpatterns += [
#     path("auth/login/",   TokenObtainPairView.as_view()),   # POST → access + refresh
#     path("auth/refresh/", TokenRefreshView.as_view()),       # POST → new access token
# ]

if _DRF_AVAILABLE:

    class CustomTokenSerializer(TokenObtainPairSerializer):
        """
        Extends the default SimpleJWT serializer to embed additional claims
        (full name, role, plan) directly in the access token payload.

        This eliminates an extra database round-trip on the resource server
        because the claims travel with the token rather than requiring a
        userinfo lookup on every request.
        """

        @classmethod
        def get_token(cls, user):
            token = super().get_token(user)

            # Custom claims — keep them small; tokens are base64-encoded
            # and sent on every request.
            token["name"] = user.get_full_name()
            token["role"] = getattr(user, "role", "member")
            token["plan"] = getattr(user, "plan", "free")
            return token

    class CustomTokenView(TokenObtainPairView):
        """Swap in the custom serializer so the enriched token is issued."""

        serializer_class = CustomTokenSerializer


# ==========================================================================
# 6. PAGINATION
# ==========================================================================

if _DRF_AVAILABLE:

    class StandardPagination(PageNumberPagination):
        """
        Page-number pagination with a configurable page size.

        Clients can override the page size up to max_page_size by passing
        ?page_size=N in the query string.  The response envelope includes
        count, total_pages, and navigation links so clients need not parse
        headers.
        """

        page_size: int = 20
        page_size_query_param: str = "page_size"
        max_page_size: int = 100

        def get_paginated_response(self, data) -> Response:
            return Response(
                {
                    "count": self.page.paginator.count,
                    "total_pages": self.page.paginator.num_pages,
                    "next": self.get_next_link(),
                    "previous": self.get_previous_link(),
                    "results": data,
                }
            )

    class OrderCursorPagination(CursorPagination):
        """
        Cursor-based pagination for large or continuously growing datasets
        such as order feeds and activity streams.

        Cursor pagination is preferred over page-number pagination when:
          - The dataset is large (millions of rows).
          - New items are inserted frequently (page drift is unacceptable).
          - Infinite-scroll UI is required.

        The cursor is an opaque, tamper-evident token; clients simply follow
        the `next` link without constructing offsets.
        """

        page_size: int = 20
        ordering: str = "-created_at"   # must be an indexed, stable column

    class OrderViewSet(viewsets.ReadOnlyModelViewSet):
        """
        Read-only ViewSet wired to cursor pagination.
        Swap pagination_class to StandardPagination for regular page navigation.
        """

        pagination_class = OrderCursorPagination
        serializer_class = None  # Replace with your Order serializer.
        queryset = None           # Replace with Order.objects.all()


# ==========================================================================
# 7. THROTTLING (RATE LIMITING)
# ==========================================================================

# ---- settings.py excerpt ----
# REST_FRAMEWORK = {
#     "DEFAULT_THROTTLE_CLASSES": [
#         "rest_framework.throttling.AnonRateThrottle",
#         "rest_framework.throttling.UserRateThrottle",
#     ],
#     "DEFAULT_THROTTLE_RATES": {
#         "anon":  "100/day",
#         "user":  "1000/day",
#         "login": "5/minute",   # strict rate for the login endpoint
#     },
# }

if _DRF_AVAILABLE:

    class LoginThrottle(UserRateThrottle):
        """
        Dedicated throttle class for the authentication endpoint.

        The `scope` attribute must match a key in DEFAULT_THROTTLE_RATES in
        settings.py.  Here it enforces a maximum of 5 login attempts per
        minute per user/IP to mitigate brute-force attacks.
        """

        scope: str = "login"

    class AuthView(generics.GenericAPIView):
        """
        Login view with a strict per-minute throttle applied only to POST
        requests.  Applying LoginThrottle here instead of globally means the
        restriction does not affect unrelated endpoints.
        """

        throttle_classes = [LoginThrottle]

        def post(self, request: Request) -> Response:
            """
            Authenticate with username/password and return a JWT token pair.
            Placeholder — wire this to CustomTokenSerializer or
            TokenObtainPairView in production.
            """
            return Response(
                {"detail": "Wire to CustomTokenSerializer for production use."},
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )


# ==========================================================================
# 8. GLOBAL DRF SETTINGS REFERENCE
# ==========================================================================

# Paste the block below into your Django settings.py and adjust as needed.
#
# REST_FRAMEWORK = {
#     # Authentication
#     "DEFAULT_AUTHENTICATION_CLASSES": [
#         "rest_framework_simplejwt.authentication.JWTAuthentication",
#         "rest_framework.authentication.SessionAuthentication",
#     ],
#     # Permissions
#     "DEFAULT_PERMISSION_CLASSES": [
#         "rest_framework.permissions.IsAuthenticated",
#     ],
#     # Throttling
#     "DEFAULT_THROTTLE_CLASSES": [
#         "rest_framework.throttling.AnonRateThrottle",
#         "rest_framework.throttling.UserRateThrottle",
#     ],
#     "DEFAULT_THROTTLE_RATES": {
#         "anon":  "100/day",
#         "user":  "1000/day",
#         "login": "5/minute",
#     },
#     # Pagination
#     "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
#     "PAGE_SIZE": 20,
#     # Renderer / Parser
#     "DEFAULT_RENDERER_CLASSES": [
#         "rest_framework.renderers.JSONRenderer",
#     ],
#     "DEFAULT_PARSER_CLASSES": [
#         "rest_framework.parsers.JSONParser",
#         "rest_framework.parsers.MultiPartParser",
#     ],
#     # Exception handler
#     "EXCEPTION_HANDLER": "rest_framework.views.exception_handler",
# }
