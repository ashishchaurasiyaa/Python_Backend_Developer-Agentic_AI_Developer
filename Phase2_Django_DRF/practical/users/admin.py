"""
Django Admin — Custom User Admin
══════════════════════════════════
INTERVIEW: UserAdmin customize kyu karte hain?
  - Email-based login ke liye fieldsets update karna
  - Sensitive fields (password hash) properly dikhana
  - Custom actions (bulk email, export)
  - Inline related models (Profile in same page)
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User, UserProfile


class UserProfileInline(admin.StackedInline):
    """Show profile fields inline in User admin page."""
    model = User.profile.related.related_model if hasattr(User, 'profile') else None
    model = UserProfile
    can_delete = False
    verbose_name_plural = "Profile"
    fk_name = "user"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom admin for email-based User model."""

    # List page
    list_display   = ["email", "full_name", "role", "plan", "is_active",
                      "is_email_verified", "created_at"]
    list_filter    = ["role", "plan", "is_active", "is_email_verified", "is_staff"]
    search_fields  = ["email", "first_name", "last_name", "phone"]
    ordering       = ["-created_at"]
    readonly_fields = ["last_login", "created_at", "updated_at", "last_login_ip"]

    # Detail page — fieldsets
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Personal Info"), {"fields": ("first_name", "last_name", "phone", "bio", "avatar")}),
        (_("Status"), {"fields": ("role", "plan", "is_email_verified")}),
        (_("Permissions"), {
            "fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions"),
            "classes": ("collapse",),
        }),
        (_("Metadata"), {
            "fields": ("last_login", "last_login_ip", "created_at", "updated_at"),
        }),
    )

    # Add user page
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "first_name", "last_name", "password1", "password2",
                       "role", "plan"),
        }),
    )

    # Username field override (we use email)
    USERNAME_FIELD = "email"

    inlines = [UserProfileInline]

    # Custom admin actions
    actions = ["activate_users", "deactivate_users", "upgrade_to_premium"]

    @admin.action(description="Activate selected users")
    def activate_users(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f"{count} users activated.")

    @admin.action(description="Deactivate selected users")
    def deactivate_users(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f"{count} users deactivated.")

    @admin.action(description="Upgrade to Premium")
    def upgrade_to_premium(self, request, queryset):
        count = queryset.update(plan=User.Plan.PREMIUM)
        self.message_user(request, f"{count} users upgraded to premium.")
