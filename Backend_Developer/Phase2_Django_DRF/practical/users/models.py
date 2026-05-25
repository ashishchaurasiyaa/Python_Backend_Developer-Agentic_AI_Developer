"""
Custom User Model
═══════════════════════════════════════════════════════
INTERVIEW: Kyu Custom User Model chahiye?
  - Default Django User: username-based login, no extra fields
  - Custom model: email-based login + role + plan + avatar + phone
  - CRITICAL: Set AUTH_USER_MODEL BEFORE first migration
    Baad mein change karna almost impossible hai

INTERVIEW: AbstractUser vs AbstractBaseUser fark?
  AbstractUser:
    + Django ka default User fields rakho + apne fields add karo
    + Easiest option for most projects

  AbstractBaseUser:
    + Complete control — apna UserManager, fields, password etc.
    - More boilerplate required
    - Use when: completely different login system (phone OTP, SSO only)
"""

from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    """Custom manager — email-based login instead of username."""

    def create_user(self, email: str, password: str | None = None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        extra_fields.setdefault("is_active", True)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)  # auto-hashes
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.ADMIN)
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """
    Extended User model.

    Uses email as login identifier.
    Adds: role, plan, phone, avatar, is_email_verified.
    """

    class Role(models.TextChoices):
        USER      = "user",      _("User")
        MODERATOR = "moderator", _("Moderator")
        ADMIN     = "admin",     _("Admin")

    class Plan(models.TextChoices):
        FREE       = "free",       _("Free")
        PREMIUM    = "premium",    _("Premium")
        ENTERPRISE = "enterprise", _("Enterprise")

    # Remove username as identifier — use email
    username = None  # type: ignore[assignment]
    email    = models.EmailField(_("email address"), unique=True)

    # Extra fields
    phone             = models.CharField(max_length=20, blank=True, db_index=True)
    avatar            = models.ImageField(upload_to="avatars/", null=True, blank=True)
    bio               = models.TextField(blank=True)
    role              = models.CharField(max_length=20, choices=Role.choices, default=Role.USER)
    plan              = models.CharField(max_length=20, choices=Plan.choices, default=Plan.FREE)
    is_email_verified = models.BooleanField(default=False)
    last_login_ip     = models.GenericIPAddressField(null=True, blank=True)
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    # Use email as login field
    USERNAME_FIELD  = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]  # used by createsuperuser

    objects = UserManager()  # custom manager

    class Meta:
        db_table = "users"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["role", "plan"]),
        ]

    def __str__(self):
        return self.email

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip() or self.email

    @property
    def is_premium(self) -> bool:
        return self.plan in (self.Plan.PREMIUM, self.Plan.ENTERPRISE)

    @property
    def is_admin_role(self) -> bool:
        return self.role == self.Role.ADMIN


class UserProfile(models.Model):
    """
    Extended profile — created automatically via signal when User is created.

    INTERVIEW: Why separate Profile model vs fields on User?
    - Separation of concerns — auth data vs profile data
    - Profile can have many-to-many (skills, interests)
    - Different access patterns (profile rarely needed in auth checks)
    """
    user         = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    website      = models.URLField(blank=True)
    location     = models.CharField(max_length=100, blank=True)
    company      = models.CharField(max_length=100, blank=True)
    twitter      = models.CharField(max_length=50, blank=True)
    github       = models.CharField(max_length=50, blank=True)
    followers_count = models.PositiveIntegerField(default=0)
    following_count = models.PositiveIntegerField(default=0)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "user_profiles"

    def __str__(self):
        return f"Profile({self.user.email})"
