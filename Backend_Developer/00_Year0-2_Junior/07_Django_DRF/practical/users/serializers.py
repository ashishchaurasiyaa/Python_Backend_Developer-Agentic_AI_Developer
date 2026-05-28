"""
User Serializers
═══════════════════════════════════════════════════════
INTERVIEW: Serializer validation order?
  1. field-level: validate_<field>() — har field ek ek karke
  2. object-level: validate() — saare fields ek saath
  3. validators= list on field/class level

INTERVIEW: ModelSerializer vs Serializer?
  ModelSerializer: model fields auto-detect karta hai
  Serializer: manual field definition — more control, less magic

INTERVIEW: Nested serializer write kaise karte hain?
  Read: `nested = ProfileSerializer(read_only=True)` — easy
  Write: override create()/update() — manually handle nested
"""

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from .models import UserProfile

User = get_user_model()


# ─── Profile Serializer ───────────────────────────────────
class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ["website", "location", "company", "twitter",
                  "github", "followers_count", "following_count"]
        read_only_fields = ["followers_count", "following_count"]


# ─── Read Serializer ──────────────────────────────────────
class UserSerializer(serializers.ModelSerializer):
    """
    Safe serializer for reading user data.
    Never exposes password or sensitive data.
    """
    full_name = serializers.SerializerMethodField()
    profile   = UserProfileSerializer(read_only=True)

    class Meta:
        model  = User
        fields = [
            "id", "email", "first_name", "last_name", "full_name",
            "phone", "avatar", "bio", "role", "plan",
            "is_email_verified", "is_active", "created_at", "profile",
        ]
        read_only_fields = ["id", "email", "role", "plan", "is_email_verified",
                            "is_active", "created_at"]

    def get_full_name(self, obj) -> str:
        return obj.full_name


# ─── Register Serializer ──────────────────────────────────
class UserRegisterSerializer(serializers.ModelSerializer):
    """
    User registration with password confirmation.

    INTERVIEW: write_only=True — field serialization mein nahi aata
    """
    password         = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model  = User
        fields = ["email", "first_name", "last_name", "password", "confirm_password", "phone"]

    def validate_email(self, value: str) -> str:
        """Field-level validation — email uniqueness."""
        normalized = value.lower()
        if User.objects.filter(email=normalized).exists():
            raise serializers.ValidationError("Email already registered")
        return normalized

    def validate_password(self, value: str) -> str:
        """Use Django's built-in password validators."""
        validate_password(value)
        return value

    def validate(self, data: dict) -> dict:
        """Object-level validation — password match."""
        if data["password"] != data.pop("confirm_password"):
            raise serializers.ValidationError({"confirm_password": "Passwords do not match"})
        return data

    def create(self, validated_data: dict) -> User:
        return User.objects.create_user(**validated_data)


# ─── Update Serializer ────────────────────────────────────
class UserUpdateSerializer(serializers.ModelSerializer):
    """Update profile fields — email and role not changeable here."""
    profile = UserProfileSerializer(required=False)

    class Meta:
        model  = User
        fields = ["first_name", "last_name", "phone", "bio", "avatar", "profile"]

    def update(self, instance: User, validated_data: dict) -> User:
        # Handle nested profile update
        profile_data = validated_data.pop("profile", None)

        # Update user fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update profile if provided
        if profile_data:
            UserProfile.objects.filter(user=instance).update(**profile_data)

        return instance


# ─── Change Password Serializer ───────────────────────────
class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_old_password(self, value: str) -> str:
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Incorrect current password")
        return value

    def validate_new_password(self, value: str) -> str:
        validate_password(value)
        return value

    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        return user


# ─── Custom JWT Token Serializer ──────────────────────────
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Add custom claims to JWT payload.

    INTERVIEW: JWT mein custom data kab add karte hain?
    - Frontend ko user info chahiye without extra API call
    - role, plan, subscription info
    - tenant_id (multi-tenant apps)

    Registered in settings:
      SIMPLE_JWT = {"TOKEN_OBTAIN_SERIALIZER": "users.serializers.CustomTokenObtainPairSerializer"}
    """

    @classmethod
    def get_token(cls, user: User):
        token = super().get_token(user)
        # Add custom claims to payload
        token["email"]             = user.email
        token["full_name"]         = user.full_name
        token["role"]              = user.role
        token["plan"]              = user.plan
        token["is_email_verified"] = user.is_email_verified
        return token

    def validate(self, attrs: dict) -> dict:
        """Also return user data alongside the tokens."""
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data
        return data
