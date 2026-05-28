"""
Custom User Model + Auth — Production Patterns
"""

# ==========================================================================
# 1. CUSTOM USER MODEL (AbstractBaseUser — full control)
# ==========================================================================

"""
# users/models.py

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        if not extra_fields.get('is_staff'):
            raise ValueError('Superuser must have is_staff=True')
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True, db_index=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_email_verified = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)

    # Multi-tenant
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.PROTECT, null=True)
    role = models.CharField(max_length=20, default='member')

    date_joined = models.DateTimeField(default=timezone.now)
    last_login = models.DateTimeField(null=True, blank=True)
    last_password_change = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    class Meta:
        db_table = 'users'

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'.strip()

    def get_full_name(self):
        return self.full_name

    def get_short_name(self):
        return self.first_name


# settings.py
# AUTH_USER_MODEL = 'users.User'
"""


# ==========================================================================
# 2. CUSTOM AUTHENTICATION BACKEND
# ==========================================================================

"""
# users/backends.py

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailBackend(ModelBackend):
    \"\"\"Authenticate via email + password.\"\"\"

    def authenticate(self, request, username=None, password=None, **kwargs):
        User = get_user_model()
        try:
            # case-insensitive lookup
            user = User.objects.get(email__iexact=username)
        except User.DoesNotExist:
            # Run hash anyway to prevent timing attacks
            User().set_password(password)
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

    def get_user(self, user_id):
        User = get_user_model()
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None


# settings.py
# AUTHENTICATION_BACKENDS = [
#     'users.backends.EmailBackend',
#     'django.contrib.auth.backends.ModelBackend',
# ]
"""


# ==========================================================================
# 3. JWT WITH SIMPLEJWT
# ==========================================================================

"""
# settings.py

from datetime import timedelta

INSTALLED_APPS += ['rest_framework_simplejwt']

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,

    'ALGORITHM': 'HS256',
    'SIGNING_KEY': os.environ['JWT_SECRET'],

    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}


# urls.py
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenBlacklistView,
)

urlpatterns = [
    path('api/auth/login/', TokenObtainPairView.as_view()),
    path('api/auth/refresh/', TokenRefreshView.as_view()),
    path('api/auth/logout/', TokenBlacklistView.as_view()),
]
"""


# ==========================================================================
# 4. CUSTOM JWT CLAIMS
# ==========================================================================

"""
# users/serializers.py

from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class CustomTokenObtainSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Add custom claims (avoid sensitive data)
        token['email'] = user.email
        token['tenant_id'] = user.tenant_id
        token['role'] = user.role
        token['is_email_verified'] = user.is_email_verified

        return token

    def validate(self, attrs):
        data = super().validate(attrs)

        # Check email verified
        if not self.user.is_email_verified:
            raise serializers.ValidationError({'detail': 'Email not verified'})

        # Update last_login
        from django.utils import timezone
        self.user.last_login = timezone.now()
        self.user.save(update_fields=['last_login'])

        return data


# users/views.py
from rest_framework_simplejwt.views import TokenObtainPairView


class CustomTokenObtainView(TokenObtainPairView):
    serializer_class = CustomTokenObtainSerializer
"""


# ==========================================================================
# 5. PASSWORD VALIDATORS (HIBP + custom)
# ==========================================================================

"""
# users/validators.py

import hashlib
import requests
from django.core.exceptions import ValidationError


class HaveIBeenPwnedValidator:
    \"\"\"Check password against HIBP API (k-anonymity, no plaintext sent).\"\"\"

    def __init__(self, max_count=0):
        self.max_count = max_count

    def validate(self, password, user=None):
        sha1 = hashlib.sha1(password.encode()).hexdigest().upper()
        prefix, suffix = sha1[:5], sha1[5:]

        try:
            resp = requests.get(
                f'https://api.pwnedpasswords.com/range/{prefix}',
                timeout=3,
                headers={'Add-Padding': 'true'},  # privacy
            )
            resp.raise_for_status()
        except requests.RequestException:
            return  # fail open — don't block on API failure

        for line in resp.text.splitlines():
            try:
                hash_suffix, count = line.split(':')
                if hash_suffix == suffix and int(count) > self.max_count:
                    raise ValidationError(
                        f'This password has been seen in {count} known breaches.',
                        code='compromised',
                    )
            except ValueError:
                continue

    def get_help_text(self):
        return 'Your password must not appear in any known data breaches.'


class HistoryValidator:
    \"\"\"Prevent reusing recent passwords.\"\"\"

    def __init__(self, history=5):
        self.history = history

    def validate(self, password, user=None):
        if not user or not user.pk:
            return
        from .models import PasswordHistory

        for old_hash in PasswordHistory.objects.filter(
            user=user
        ).order_by('-created_at')[:self.history].values_list('password_hash', flat=True):
            from django.contrib.auth.hashers import check_password
            if check_password(password, old_hash):
                raise ValidationError(
                    f'Password matches one of your last {self.history} passwords.',
                )


# settings.py
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 12}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'users.validators.HaveIBeenPwnedValidator'},
    {'NAME': 'users.validators.HistoryValidator'},
]
"""


# ==========================================================================
# 6. ARGON2 PASSWORD HASHING
# ==========================================================================

"""
# pip install argon2-cffi

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
]


# Django auto-upgrades hashes on login:
# 1. User logs in, password verified against old hash (PBKDF2)
# 2. Django re-hashes with new algorithm (Argon2)
# 3. Saves new hash
"""


# ==========================================================================
# 7. MFA / TOTP
# ==========================================================================

"""
# pip install django-otp pyotp

# settings.py
INSTALLED_APPS += [
    'django_otp',
    'django_otp.plugins.otp_totp',
    'django_otp.plugins.otp_static',
]
MIDDLEWARE += ['django_otp.middleware.OTPMiddleware']


# Enable TOTP for user (view)
from django_otp.plugins.otp_totp.models import TOTPDevice


@login_required
def enable_mfa(request):
    if request.method == 'POST':
        # Verify provided OTP
        otp = request.POST.get('otp')
        device = TOTPDevice.objects.create(user=request.user, name='default', confirmed=False)
        if device.verify_token(otp):
            device.confirmed = True
            device.save()
            return redirect('mfa-enabled')
        device.delete()
    else:
        # Show QR code
        device = TOTPDevice(user=request.user, name='default')
        # Render QR with device.config_url
        return render(request, 'mfa_setup.html', {'qr_url': device.config_url})


# Force MFA on login
@login_required
def protected_view(request):
    from django_otp.decorators import otp_required

    if not request.user.is_verified():
        return redirect('mfa-login')
    # ... view logic


# Decorator
from django_otp.decorators import otp_required


@otp_required
def sensitive_view(request):
    ...
"""


# ==========================================================================
# 8. SESSION + JWT COEXISTENCE
# ==========================================================================

"""
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        # Try JWT first (mobile/SPA)
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        # Fallback to Session (browser/admin)
        'rest_framework.authentication.SessionAuthentication',
    ],
}


# Browser:
# - Login form → session cookie + CSRF token
# - DRF endpoints work with session
#
# Mobile/SPA:
# - Login API returns JWT
# - Subsequent requests send Bearer token
"""


# ==========================================================================
# 9. EMAIL VERIFICATION FLOW
# ==========================================================================

"""
from django.core.signing import TimestampSigner
from django.core.mail import send_mail


signer = TimestampSigner(salt='email-verify')


def send_verification_email(user):
    token = signer.sign(str(user.pk))
    url = f'https://app.example.com/verify-email?token={token}'
    send_mail(
        subject='Verify your email',
        message=f'Click to verify: {url}',
        from_email='noreply@example.com',
        recipient_list=[user.email],
    )


def verify_email(request):
    token = request.GET.get('token')
    try:
        user_id = signer.unsign(token, max_age=86400)  # 24h validity
    except Exception:
        return HttpResponse('Invalid or expired link', status=400)

    user = User.objects.get(pk=user_id)
    user.is_email_verified = True
    user.email_verified_at = timezone.now()
    user.save(update_fields=['is_email_verified', 'email_verified_at'])
    return HttpResponse('Email verified')
"""


# ==========================================================================
# 10. RATE-LIMITING LOGIN ATTEMPTS (django-axes)
# ==========================================================================

"""
# pip install django-axes

INSTALLED_APPS += ['axes']
MIDDLEWARE += ['axes.middleware.AxesMiddleware']

AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'users.backends.EmailBackend',
    'django.contrib.auth.backends.ModelBackend',
]

AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1  # hours
AXES_LOCKOUT_PARAMETERS = ['ip_address', 'username']
AXES_RESET_ON_SUCCESS = True
AXES_VERBOSE = True
"""


# ==========================================================================
# 11. PASSWORD RESET FLOW (secure)
# ==========================================================================

"""
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes


def request_password_reset(email):
    User = get_user_model()
    try:
        user = User.objects.get(email__iexact=email)
    except User.DoesNotExist:
        # Don't reveal whether email exists (prevents enumeration)
        return

    token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    url = f'https://app.example.com/reset-password/{uid}/{token}/'

    send_mail(
        'Password Reset',
        f'Reset your password: {url}',
        'noreply@example.com',
        [email],
    )


def confirm_password_reset(uid, token, new_password):
    from django.utils.http import urlsafe_base64_decode

    user_id = urlsafe_base64_decode(uid).decode()
    user = User.objects.get(pk=user_id)

    if not default_token_generator.check_token(user, token):
        raise ValidationError('Invalid or expired token')

    user.set_password(new_password)
    user.save()
"""


# ==========================================================================
# 12. CUSTOM USER ADMIN
# ==========================================================================

"""
# users/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DefaultUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(DefaultUserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'is_email_verified', 'is_staff', 'date_joined')
    list_filter = ('is_staff', 'is_email_verified', 'tenant')
    search_fields = ('email', 'first_name', 'last_name', 'phone')
    ordering = ('-date_joined',)

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal', {'fields': ('first_name', 'last_name', 'phone')}),
        ('Tenant', {'fields': ('tenant', 'role')}),
        ('Verification', {'fields': ('is_email_verified', 'email_verified_at')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Dates', {'fields': ('last_login', 'date_joined', 'last_password_change')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'first_name', 'last_name'),
        }),
    )
"""
