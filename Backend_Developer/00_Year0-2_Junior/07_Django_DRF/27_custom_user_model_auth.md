# Custom User Model & Authentication

## Why It Matters

Django default `User` = limited (username-based). Production needs:
- Email-based login
- Custom fields (tenant_id, phone, MFA)
- Custom auth backends (LDAP, SAML, JWT)
- MFA / 2FA

Senior interview: "Email-based login + tenant isolation Django mein design?" → Custom User Model + custom auth backend.

---

## Core Concepts

### AbstractUser vs AbstractBaseUser

**`AbstractUser`** — full default User minus username constraints. Extend for adding fields:

```python
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Adds fields to default User."""
    phone = models.CharField(max_length=20, blank=True)
    is_email_verified = models.BooleanField(default=False)
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.PROTECT, null=True)
```

**`AbstractBaseUser`** — bare minimum. Use for complete customization (e.g., email as username).

```python
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True, db_index=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    date_joined = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    def __str__(self):
        return self.email
```

### Settings

```python
# settings.py
AUTH_USER_MODEL = 'users.User'
```

**Critical:** Set BEFORE first migration. Changing later requires data migration.

### Referencing User in FKs

```python
from django.conf import settings


class Article(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
```

Never `from django.contrib.auth.models import User`. Use `settings.AUTH_USER_MODEL`.

### Custom Authentication Backend

```python
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model


class EmailBackend(ModelBackend):
    """Authenticate via email or username."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        User = get_user_model()
        try:
            user = User.objects.get(email=username)
        except User.DoesNotExist:
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None


# settings.py
AUTHENTICATION_BACKENDS = [
    'users.backends.EmailBackend',
    'django.contrib.auth.backends.ModelBackend',
]
```

### JWT Authentication (simplejwt)

```python
# pip install djangorestframework-simplejwt
INSTALLED_APPS += ['rest_framework_simplejwt']


REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
}


from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': os.environ['JWT_SECRET'],
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}


# urls.py
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView


urlpatterns = [
    path('api/auth/token/', TokenObtainPairView.as_view()),
    path('api/auth/token/refresh/', TokenRefreshView.as_view()),
]
```

### Custom Token Claims

```python
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class CustomTokenObtainSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['email'] = user.email
        token['tenant_id'] = user.tenant_id
        token['is_premium'] = user.is_premium
        return token


class CustomTokenObtainView(TokenObtainPairView):
    serializer_class = CustomTokenObtainSerializer
```

### MFA / 2FA via django-otp

```python
# pip install django-otp django-two-factor-auth
INSTALLED_APPS += [
    'django_otp',
    'django_otp.plugins.otp_totp',
    'django_otp.plugins.otp_static',
    'two_factor',
]


MIDDLEWARE += ['django_otp.middleware.OTPMiddleware']

LOGIN_URL = 'two_factor:login'
LOGIN_REDIRECT_URL = 'home'
TWO_FACTOR_LOGIN_TIMEOUT = 0  # no auto-logout
```

### Password Hasher (Argon2)

```python
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
]


# pip install argon2-cffi
```

### Custom Password Validators

```python
class HaveIBeenPwnedValidator:
    """Check against HIBP API."""

    def validate(self, password, user=None):
        from django.core.exceptions import ValidationError
        import hashlib, requests

        sha1 = hashlib.sha1(password.encode()).hexdigest().upper()
        prefix, suffix = sha1[:5], sha1[5:]

        try:
            r = requests.get(f'https://api.pwnedpasswords.com/range/{prefix}', timeout=3)
            r.raise_for_status()
        except Exception:
            return  # fail open

        for line in r.text.splitlines():
            hash_suffix, count = line.split(':')
            if hash_suffix == suffix and int(count) > 0:
                raise ValidationError(
                    f"Password compromised in {count} breaches",
                    code='compromised',
                )

    def get_help_text(self):
        return "Password must not appear in known data breaches."


# settings.py
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 12}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'myapp.validators.HaveIBeenPwnedValidator'},
]
```

### Session Auth + DRF

```python
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
}
```

Session = browser-friendly. JWT = mobile/SPA. Both can coexist.

---

## Common Pitfalls

### 1. Adding Fields Late

Adding to default User late = harder than starting custom. **Always start with custom User Model** in new projects.

### 2. Hardcoded `User` Imports

```python
from django.contrib.auth.models import User    # WRONG with custom user
```

Use `get_user_model()` or `settings.AUTH_USER_MODEL` in FK.

### 3. Migrating from Default to Custom Later

Possible but complex — requires data migration of `auth_user` table. Better start custom.

### 4. Email Not Unique

Custom User with email login → must set `unique=True` on email. Else can't authenticate.

### 5. PermissionsMixin Forgotten

Without PermissionsMixin, custom user can't have permissions/groups. Always include unless intentional.

### 6. Username Field Without Backend

Set `USERNAME_FIELD='email'` but auth backend looks for `username` → login fails. Custom backend required.

### 7. Sensitive Fields in JWT

```python
token['password_hash'] = user.password   # NEVER
```

JWT is base64 — readable by anyone with token. Only put non-sensitive identifiers.

### 8. Forgetting `is_active` Check

Default `ModelBackend.user_can_authenticate` returns True if `is_active`. Custom backend must replicate.

---

## Interview Q&A

**Q1:** AbstractUser vs AbstractBaseUser?
**A:** AbstractUser: extends default User (keeps username, first_name, last_name, email, permissions). Just add fields. AbstractBaseUser: minimal — define everything yourself. Use AbstractUser for adding fields; AbstractBaseUser for fundamentally different identity model (e.g., email-only login).

**Q2:** Email-based login implementation?
**A:** AbstractBaseUser + UserManager that creates with email + USERNAME_FIELD='email' + REQUIRED_FIELDS=['first_name', 'last_name']. Plus custom auth backend that does `User.objects.get(email=username)`. Add to AUTHENTICATION_BACKENDS.

**Q3:** Custom user start ya later add?
**A:** ALWAYS start with custom user — `AUTH_USER_MODEL = 'users.User'` even if it just extends AbstractUser without changes. Changing later requires complex migration. Even Django docs recommend this.

**Q4:** JWT + Refresh Token implementation?
**A:** djangorestframework-simplejwt — `TokenObtainPairView` issues access (short, 15 min) + refresh (long, 7 days). `ROTATE_REFRESH_TOKENS` issues new refresh on each use. `BLACKLIST_AFTER_ROTATION` prevents replay. Store refresh in httpOnly cookie.

**Q5:** MFA Django mein kaise implement karein?
**A:** django-two-factor-auth (built on django-otp). Provides TOTP (Google Authenticator), backup tokens, phone via Twilio. Override login flow to require OTP after password. Or DRF: custom view that verifies TOTP before issuing JWT.

**Q6:** Password hashing recommendations?
**A:** Argon2id (best — memory-hard, GPU-resistant) via `Argon2PasswordHasher`. PBKDF2 (Django default) is adequate but weaker against GPU. bcrypt OK. PASSWORD_HASHERS list: put new algo first; old as fallback for existing hashes. Django re-hashes on next login.

**Q7:** Session auth + JWT same app mein possible?
**A:** Yes. DRF DEFAULT_AUTHENTICATION_CLASSES = [SessionAuthentication, JWTAuthentication]. Browser uses session cookie + CSRF. Mobile/SPA uses JWT. View tries each in order; first that authenticates wins.

**Q8:** Token revocation strategy?
**A:** JWT stateless — can't revoke individual without DB lookup. Solutions: (1) Short TTL (15 min access). (2) Refresh token in DB (revoke by setting flag). (3) Token blacklist in Redis. (4) `jti` claim + check on each request. Trade-off: stateless speed vs revocability.

---

## Real-World Use Cases

### 1. Multi-Tenant SaaS

User has tenant_id. JWT includes tenant_id claim. Middleware reads from JWT, sets request.tenant_id. Tenant Manager filters all queries.

### 2. OAuth Social Login

`django-allauth` or `social-auth-app-django`. Configure providers (Google, GitHub). Auto-creates User on first login.

### 3. LDAP Integration

`django-auth-ldap`. AUTHENTICATION_BACKENDS includes LDAPBackend. Authenticates against AD/LDAP, creates/syncs Django User.

---

## References

- [Django Custom User](https://docs.djangoproject.com/en/5.0/topics/auth/customizing/#substituting-a-custom-user-model)
- [django-rest-framework-simplejwt](https://django-rest-framework-simplejwt.readthedocs.io/)
- [django-two-factor-auth](https://django-two-factor-auth.readthedocs.io/)
- [django-allauth](https://django-allauth.readthedocs.io/)
