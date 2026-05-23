# Authentication vs Authorization

## Quick Reference Card
```
Authentication → "Tum kaun ho?" — Identity verify karo (login)
Authorization  → "Tum kya kar sakte ho?" — Permissions check karo (access control)
AuthN          → Authentication ka short form
AuthZ          → Authorization ka short form  
RBAC           → Role-Based Access Control — roles ko permissions dene ka standard way
ABAC           → Attribute-Based — more granular than RBAC
Interview hook → "Django: Authentication = JWT | Authorization = custom permission classes + RBAC"
```

---

## PART 1: HINGLISH — Samjhne ke liye

### 1.1 Difference — Simple Analogy

**Analogy: Office building**

- **Authentication** = Security guard → "ID card dikhao" → "Tum Ashish ho" ✓
- **Authorization** = Access card swipe → "Ashish ko 5th floor allowed hai, not 8th floor (CEO office)"

```
AUTHENTICATION:
  Q: Who are you?
  Process: Verify identity (password, biometric, OTP)
  Output: User identity confirmed (or rejected)
  
AUTHORIZATION:
  Q: What can you do?
  Process: Check permissions/roles
  Output: Allow or deny the action
  
EXAMPLE:
  User logs in with email + password → Authentication (identity confirmed)
  User tries to delete another user's booking → Authorization (denied! not your booking)
  
  403 Forbidden = AuthZ failure (you're authenticated but not authorized)
  401 Unauthorized = AuthN failure (you're not authenticated at all)
  
  (Confusingly, 401 is called "Unauthorized" but means "Unauthenticated" — naming mistake in HTTP spec)
```

---

### 1.2 Authentication Methods

```
1. PASSWORD-BASED:
   User sends: username + password
   Server: Hash password, compare with stored hash
   Problem: Password reuse, weak passwords, phishing
   
   NEVER: Store passwords in plain text
   ALWAYS: bcrypt/PBKDF2/argon2 for hashing (slow algorithms — brute force hard)
   
   Django: django.contrib.auth.hashers — PBKDF2 by default

2. TOKEN-BASED (JWT):
   User logs in → Server returns JWT token
   Subsequent requests: Token in Authorization header
   Server: Verify token signature (stateless — no DB lookup)
   
   See: 26_Token_Based_Authentication.md

3. SESSION-BASED:
   User logs in → Server creates session in DB/Redis
   Server returns session_id in cookie
   Subsequent requests: Cookie sent automatically
   Server: Look up session_id in store → find user
   
   Django default: session-based (SESSION_ENGINE)

4. API KEY:
   Static key issued to application (not user)
   Sent in header: Authorization: Api-Key xyz123
   Stored in DB, can be revoked
   Use: Machine-to-machine (service A calls service B)

5. MULTI-FACTOR AUTHENTICATION (MFA):
   Something you know: Password
   Something you have: Phone (TOTP app, SMS code)
   Something you are: Biometric (fingerprint, face)
   
   2FA = 2-Factor Authentication
   TOTP = Time-based One-Time Password (Google Authenticator)

6. OAUTH 2.0 (Delegated Auth):
   "Login with Google/GitHub/Facebook"
   See: 27_OAuth_Authentication.md

7. CERTIFICATE-BASED (mTLS):
   Both client and server have certificates
   Used in: Internal microservices, zero-trust networks
```

---

### 1.3 Authorization Models

#### RBAC — Role-Based Access Control

```
ROLES → group permissions together
USERS → assigned to roles

ROLES:
  admin: all permissions
  manager: view+edit (no delete)
  viewer: view only

PERMISSIONS:
  booking.view
  booking.create
  booking.edit
  booking.delete
  invoice.view
  invoice.create

ROLE → PERMISSIONS MAPPING:
  admin    → ALL
  manager  → booking.view, booking.create, booking.edit, invoice.view, invoice.create
  viewer   → booking.view, invoice.view

USER → ROLE:
  Ashish → admin
  Priya  → manager
  Raju   → viewer

IMPLEMENTATION (Django):
  # Using Django's built-in groups + permissions
  
  from django.contrib.auth.models import Group, Permission
  
  # Create roles (groups)
  manager_group = Group.objects.create(name='Manager')
  
  # Assign permissions to role
  view_booking_perm = Permission.objects.get(codename='view_booking')
  create_booking_perm = Permission.objects.get(codename='add_booking')
  manager_group.permissions.set([view_booking_perm, create_booking_perm])
  
  # Assign user to role
  user.groups.add(manager_group)
  
  # Check permission
  user.has_perm('booking.view_booking')  # True
  user.has_perm('booking.delete_booking')  # False (not in manager role)
  
  # Django REST Framework permission class
  class IsManagerOrAdmin(BasePermission):
      def has_permission(self, request, view):
          return (
              request.user.is_authenticated and
              request.user.groups.filter(name__in=['Manager', 'Admin']).exists()
          )
  
  # Use in view
  class BookingView(APIView):
      permission_classes = [IsAuthenticated, IsManagerOrAdmin]
```

#### ABAC — Attribute-Based Access Control

```
ABAC: More granular — based on attributes of user, resource, environment

Decision based on:
  User attributes:    role=manager, department=sales, level=2
  Resource attributes: owner=user_id, status=active, sensitivity=high
  Environment:         time=business_hours, ip=internal_network

Rules:
  "A manager can edit bookings IF booking.department == manager.department"
  "A user can view their own bookings (booking.user_id == current_user.id)"

EXAMPLE (object-level permission):
  class BookingPermission(BasePermission):
      def has_object_permission(self, request, view, booking):
          # Attribute: booking belongs to requesting user?
          if request.user == booking.user:
              return True  # Own booking — full access
          
          # Attribute: user is manager of booking's company?
          if request.user.is_manager and \
             request.user.company == booking.company:
              return True
          
          # Admin can access everything
          return request.user.is_admin
  
  class BookingViewSet(viewsets.ModelViewSet):
      permission_classes = [IsAuthenticated, BookingPermission]
      
      def get_queryset(self):
          user = self.request.user
          if user.is_admin:
              return Booking.objects.all()
          elif user.is_manager:
              return Booking.objects.filter(company=user.company)
          else:
              return Booking.objects.filter(user=user)  # Own bookings only
```

---

### 1.4 Django Authentication System

```python
# settings.py — Authentication configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',  # For DRF browsable API
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',  # Default: must be logged in
    ],
}

# CUSTOM AUTHENTICATION:
class JWTWithTenantAuthentication(BaseAuthentication):
    def authenticate(self, request):
        token = self._get_token(request)
        if not token:
            return None  # No credentials provided
        
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            user = User.objects.get(id=payload['user_id'])
            
            # Set tenant context on request
            request.tenant = Tenant.objects.get(id=payload['tenant_id'])
            
            return (user, token)
        
        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed('Token has expired')
        except jwt.InvalidTokenError:
            raise AuthenticationFailed('Invalid token')
        except User.DoesNotExist:
            raise AuthenticationFailed('User not found')

# CUSTOM AUTHORIZATION:
class TenantPermission(BasePermission):
    """User can only access their own tenant's data"""
    
    def has_permission(self, request, view):
        return hasattr(request, 'tenant') and request.tenant is not None
    
    def has_object_permission(self, request, view, obj):
        # Object must belong to same tenant
        if hasattr(obj, 'tenant'):
            return obj.tenant == request.tenant
        if hasattr(obj, 'company') and hasattr(obj.company, 'tenant'):
            return obj.company.tenant == request.tenant
        return False

# Require specific permission:
class RequirePermission:
    def __init__(self, permission):
        self.permission = permission
    
    def __call__(self, func):
        @wraps(func)
        def wrapper(view, request, *args, **kwargs):
            if not request.user.has_perm(self.permission):
                raise PermissionDenied(f"Requires {self.permission}")
            return func(view, request, *args, **kwargs)
        return wrapper

class InvoiceView(APIView):
    permission_classes = [IsAuthenticated, TenantPermission]
    
    @RequirePermission('invoice.delete_invoice')
    def delete(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)
        invoice.delete()
        return Response(status=204)
```

---

### 1.5 Common Vulnerabilities

```
AUTHENTICATION VULNERABILITIES:

1. BRUTE FORCE:
   Attack: Try 10,000 passwords for same user
   Defense: Rate limiting (5 attempts → lockout 15 min)
             CAPTCHA after 3 failures
   
   Implementation:
   def check_login_attempts(email):
       key = f'login_attempts:{email}'
       attempts = redis.incr(key)
       if attempts == 1:
           redis.expire(key, 900)  # 15 minute window
       if attempts > 5:
           raise TooManyAttemptsError()

2. CREDENTIAL STUFFING:
   Attack: Use leaked passwords from other sites
   Defense: Have I Been Pwned API check
             MFA requirement for sensitive operations

3. SESSION FIXATION:
   Attack: Attacker sets victim's session ID before login
   Defense: Generate NEW session ID after login
   Django handles this: request.session.cycle_key() on login

4. TIMING ATTACK on password comparison:
   Attack: Measure response time to detect correct password chars
   Defense: Use constant-time comparison
   Python: hmac.compare_digest(stored_hash, computed_hash)
           Never: stored_hash == computed_hash (string comparison shortcuts!)

AUTHORIZATION VULNERABILITIES:

1. IDOR (Insecure Direct Object Reference):
   Attack: GET /api/bookings/123/ → Attacker changes to /api/bookings/456/
   Defense: Check ownership! booking.user == request.user
   
   WRONG:
   def get_booking(request, pk):
       return Booking.objects.get(pk=pk)  # Anyone can access any booking!
   
   RIGHT:
   def get_booking(request, pk):
       return Booking.objects.get(pk=pk, user=request.user)  # Own booking only

2. PRIVILEGE ESCALATION:
   Attack: Regular user calls admin endpoint
   Defense: Check roles/permissions on every endpoint
   Never trust client-sent "role" or "is_admin" in request body

3. MISSING FUNCTION LEVEL ACCESS CONTROL:
   Attack: Admin endpoints not protected (assumed obscurity)
   Defense: EVERY endpoint must have explicit permission check
```

---

### 1.6 Ashish ke projects mein

```
Youngman — Authentication:
  JWT authentication (djangorestframework-simplejwt)
  Token stored in: HttpOnly cookie (secure) or localStorage
  Token refresh: Sliding window (activity refreshes token)
  
  Login flow:
  POST /api/auth/login/ {email, password}
  → Verify credentials
  → Return: access_token (15 min) + refresh_token (30 days)
  → Subsequent requests: Authorization: Bearer {access_token}

Youngman — Authorization:
  Role-based: Admin, Manager, Viewer
  Object-level: Users can only see their company's data
  Multi-tenant: company_id filter on all queries
  
  class YounganPermission(BasePermission):
      def has_object_permission(self, request, view, obj):
          # Object must belong to user's company
          return obj.company == request.user.company

Niroskos — Additional:
  Customer role: Can view/cancel own bookings
  Agent role: Can create bookings for customers
  Admin: Full access
  
  Exotel webhook: No user auth — HMAC signature verification
  SAP internal API: API key in header (machine-to-machine)
```

---

## PART 2: ENGLISH — Interviewer ko bolne ke liye

### 2.1 Definitions

> **Authentication (AuthN)**: The process of verifying the identity of a user or system. "Who are you?" — validated by something you know (password), have (token/phone), or are (biometric).

> **Authorization (AuthZ)**: The process of determining whether an authenticated identity has permission to perform an action or access a resource. "What are you allowed to do?"

> **RBAC (Role-Based Access Control)**: Authorization model where permissions are grouped into roles, and users are assigned roles. Simpler to manage than per-user permissions.

> **ABAC (Attribute-Based Access Control)**: Authorization model where access decisions use attributes of the user, resource, and environment. More granular and flexible than RBAC but more complex.

---

### 2.2 AuthN vs AuthZ Summary

| | Authentication | Authorization |
|--|---------------|---------------|
| Question | Who are you? | What can you do? |
| When | First step | After authentication |
| HTTP Status | 401 Unauthorized | 403 Forbidden |
| Mechanism | Password, JWT, OAuth | RBAC, ABAC, ACL |
| State | Session/Token | Permission check per request |
| Example | Login with email+password | Can this manager delete invoices? |

---

### 2.3 Real Project Answer

> "In Youngman, authentication uses JWT with access tokens (15-minute expiry) and refresh tokens (30-day expiry). Each API request carries the access token in the Authorization header, which Django Rest Framework's JWTAuthentication class verifies by checking the signature against our SECRET_KEY. For authorization, we use a layered approach: first, IsAuthenticated confirms the user is logged in; then, a custom TenantPermission class checks that the requested resource belongs to the user's company. Object-level permissions enforce that users can only access their own company's data, preventing horizontal privilege escalation. Critical operations like invoice deletion require an explicit `has_perm` check for the delete permission, assigned only to admin users."

---

### 2.4 Common Follow-up Q&A

**Q1: What is the difference between 401 and 403?**
> "401 Unauthorized means the request lacks valid authentication credentials — the user hasn't logged in or the token is invalid/expired. The name is misleading (it should be called 'Unauthenticated'). The response includes a `WWW-Authenticate` header telling the client how to authenticate. 403 Forbidden means the request is authenticated but the user lacks permission — the server knows who you are but won't allow the action. No retry with different credentials will help. Example: user correctly logged in (no 401) but trying to access admin panel they don't have access to (403)."

**Q2: How do you prevent IDOR attacks?**
> "IDOR (Insecure Direct Object Reference) happens when an API uses sequential IDs in URLs without checking ownership. A user guesses /api/bookings/124/ and gets someone else's booking. Prevention: (1) Always filter by ownership in queries: `Booking.objects.get(pk=pk, user=request.user)` — this returns 404 for IDs the user doesn't own. (2) Use non-sequential IDs (UUID v4) — harder to guess, but still check ownership. (3) In DRF, override `get_queryset()` to scope all queries to the current user's data — the `get_object()` method then scopes object lookups to this queryset automatically. The scoped queryset approach is the most Django-idiomatic and hardest to accidentally bypass."

**Q3: How do you implement row-level security for multi-tenant apps?**
> "In Django, the standard approach is queryset-level filtering: in every viewset's `get_queryset()`, filter by `company=request.user.company`. This ensures every ORM query is scoped. For safety, we also override `perform_create()` to force `company=request.user.company` on creation — clients can't pass a different company_id. For extra protection at the database level, PostgreSQL Row Level Security policies can be applied: `CREATE POLICY tenant_isolation ON bookings USING (company_id = current_setting('app.company_id')::int)`. This prevents data leaks even from direct SQL queries. We also periodically audit with tests: a test tries to access another company's data and verifies it gets 404, not the resource."

---

## Interview Cheat Sheet

```
Authentication (AuthN) = "Who are you?" → 401 if fails
Authorization (AuthZ) = "What can you do?" → 403 if fails

Authentication methods:
  Password + hash (PBKDF2/bcrypt)
  JWT token (stateless)
  Session cookie (stateful, needs session store)
  API key (machine-to-machine)
  OAuth 2.0 (delegated, "Login with Google")
  MFA (password + TOTP)

Authorization models:
  RBAC: User → Role → Permissions (simple, manageable)
  ABAC: User attrs + Resource attrs → Decision (granular, complex)
  ACL: Per-resource, per-user list (simple, doesn't scale)

Django implementation:
  Authentication: JWTAuthentication, SessionAuthentication
  Authorization:
    - IsAuthenticated (any logged-in user)
    - Custom: has_permission (request level)
    - Custom: has_object_permission (object level)
    - has_perm('app.action_model') for specific permissions
    - get_queryset() filtering (most important for IDOR prevention)

IDOR prevention:
  WRONG: Booking.objects.get(pk=pk)
  RIGHT: Booking.objects.get(pk=pk, user=request.user)

Key vulnerabilities:
  Brute force → rate limiting + lockout
  Timing attack → hmac.compare_digest()
  IDOR → ownership check on every resource
  Privilege escalation → explicit permission on every endpoint

My setup:
  JWT (15min access + 30day refresh)
  TenantPermission: company scoping
  Object-level: booking.user == request.user check
  Exotel webhook: HMAC signature verification
```
