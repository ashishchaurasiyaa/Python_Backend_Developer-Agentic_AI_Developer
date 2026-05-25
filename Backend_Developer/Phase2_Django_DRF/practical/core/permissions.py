"""
Custom DRF Permission Classes
════════════════════════════════
INTERVIEW: has_permission vs has_object_permission fark?
  has_permission(request, view):
    - View level check — runs before queryset is fetched
    - List/Create actions: only has_permission runs
    - Use: Is user authenticated? Is user's plan valid?

  has_object_permission(request, view, obj):
    - Object level check — runs for retrieve/update/destroy
    - has_permission MUST pass first for this to run
    - Use: Is this user the owner of this specific object?

INTERVIEW: IsOwnerOrReadOnly ka common use case?
  Blog posts — anyone can read, only author can edit/delete
"""

from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsOwnerOrReadOnly(BasePermission):
    """
    Read access for all authenticated users.
    Write access only for object owner.

    Usage:
        class PostViewSet(ModelViewSet):
            permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]

    Model must have a `user` or `author` FK field.
    """
    owner_field = "user"  # override in subclass if needed

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        owner = getattr(obj, self.owner_field, None)
        return owner == request.user


class IsAdminOrReadOnly(BasePermission):
    """
    Read access for authenticated users.
    Write access only for staff/admin.
    """
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return request.user.is_authenticated
        return request.user.is_authenticated and request.user.is_staff


class IsPremiumUser(BasePermission):
    """Block non-premium users from accessing paid features."""
    message = "Premium subscription required"

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and getattr(request.user, "plan", "free") in ("premium", "enterprise")
        )


class IsVerifiedUser(BasePermission):
    """Block unverified users (email not confirmed)."""
    message = "Please verify your email address first"

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and getattr(request.user, "is_email_verified", False)
        )


class HasRole(BasePermission):
    """
    Role-based permission — specify required roles.

    Usage:
        @action(permission_classes=[HasRole.require("admin", "moderator")])
        def moderate(self, request, pk=None): ...
    """
    required_roles: tuple[str, ...] = ()

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and getattr(request.user, "role", "") in self.required_roles
        )

    @classmethod
    def require(cls, *roles: str) -> type["HasRole"]:
        """Factory method to create a role-specific permission class."""
        return type(
            f"Has{'Or'.join(r.title() for r in roles)}Role",
            (cls,),
            {"required_roles": roles},
        )


# Pre-built role permissions
IsAdminRole     = HasRole.require("admin")
IsModeratorRole = HasRole.require("admin", "moderator")
