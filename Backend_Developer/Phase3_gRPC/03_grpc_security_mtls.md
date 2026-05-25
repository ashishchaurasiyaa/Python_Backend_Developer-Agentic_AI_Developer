# gRPC Security — mTLS, JWT, OAuth2, Per-RPC Credentials

## Quick Concepts

**WHAT:**
- **TLS** = encryption in transit + server identity verification (client trusts server)
- **mTLS (Mutual TLS)** = both client AND server verify each other's certificates
- **Channel credentials** = TLS/mTLS at connection level
- **Call credentials** = JWT/OAuth at RPC level (per-request)
- **Composite credentials** = channel + call credentials combined

**WHY gRPC security is critical:**
- gRPC often used for **internal microservices** = high-trust environment
- Without mTLS = any pod on network can call any service
- JWT in metadata = stateless per-user auth
- Per-RPC credentials = different auth per method

**HOW security layers stack:**
```
┌───────────────────────────────────────────────────┐
│  Layer 1: Network — VPC, Security Groups          │
├───────────────────────────────────────────────────┤
│  Layer 2: Transport — TLS / mTLS                  │
├───────────────────────────────────────────────────┤
│  Layer 3: Authentication — JWT / OAuth2 in metadata│
├───────────────────────────────────────────────────┤
│  Layer 4: Authorization — RBAC per RPC method     │
└───────────────────────────────────────────────────┘
```

---

## Interview Questions & Answers

### Q1: TLS vs mTLS in gRPC — kya difference hai aur kab use karein?

**Answer:**

**WHAT:**
| | TLS (one-way) | mTLS (mutual) |
|---|---|---|
| Server verifies client? | ❌ No | ✅ Yes (via client cert) |
| Client verifies server? | ✅ Yes | ✅ Yes |
| Use case | External APIs (HTTPS) | Internal microservices |
| Cert management | Server only | Both sides |

**WHY mTLS for internal services:**
- ✅ **Service-to-service identity** — pod A knows pod B is legitimate
- ✅ **Zero-trust network** — even if attacker on network, can't call services
- ✅ **No JWT validation overhead** for service-to-service calls
- ✅ **Compliance** — many regulations require mTLS for PII

**HOW — Generate certificates:**

```bash
# 1. Create CA (Certificate Authority)
openssl req -x509 -newkey rsa:4096 -keyout ca.key -out ca.crt \
  -days 365 -nodes -subj "/CN=myorg-ca"

# 2. Generate server certificate
openssl req -newkey rsa:4096 -keyout server.key -out server.csr \
  -nodes -subj "/CN=user-service.default.svc.cluster.local"

# SAN (Subject Alternative Name) for K8s service DNS
cat > server.ext <<EOF
subjectAltName = DNS:user-service.default.svc.cluster.local,DNS:localhost,IP:127.0.0.1
EOF

openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out server.crt -days 365 -extfile server.ext

# 3. Generate client certificate (for mTLS)
openssl req -newkey rsa:4096 -keyout client.key -out client.csr \
  -nodes -subj "/CN=order-service"   # ⭐ CN = client identity

openssl x509 -req -in client.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out client.crt -days 365
```

**HOW — Server-side mTLS in Python:**

```python
import grpc

async def serve_with_mtls():
    # Load server cert + key
    with open("server.key", "rb") as f:
        private_key = f.read()
    with open("server.crt", "rb") as f:
        certificate_chain = f.read()
    # Load CA to verify CLIENT certs
    with open("ca.crt", "rb") as f:
        client_ca_cert = f.read()

    server_credentials = grpc.ssl_server_credentials(
        [(private_key, certificate_chain)],
        root_certificates=client_ca_cert,
        require_client_auth=True       # ⭐ CRITICAL: enables mTLS
    )

    server = grpc.aio.server()
    user_service_pb2_grpc.add_UserServiceServicer_to_server(
        UserServiceServicer(), server
    )

    # ⭐ Use add_secure_port (NOT add_insecure_port)
    server.add_secure_port("[::]:50051", server_credentials)
    await server.start()
    await server.wait_for_termination()
```

**HOW — Client-side mTLS:**

```python
import grpc

# Load CA to verify SERVER cert
with open("ca.crt", "rb") as f:
    trusted_certs = f.read()
# Load client cert + key (for server to verify CLIENT)
with open("client.key", "rb") as f:
    client_key = f.read()
with open("client.crt", "rb") as f:
    client_cert = f.read()

credentials = grpc.ssl_channel_credentials(
    root_certificates=trusted_certs,
    private_key=client_key,
    certificate_chain=client_cert,
)

channel = grpc.aio.secure_channel(
    "user-service.default.svc.cluster.local:50051",
    credentials
)
stub = user_service_pb2_grpc.UserServiceStub(channel)
```

---

### Q2: JWT authentication gRPC mein kaise implement karte ho?

**Answer:**

**WHAT:** JWT (JSON Web Token) passed via gRPC metadata header.

**WHY metadata for JWT:**
- ✅ Standard pattern (like HTTP Authorization header)
- ✅ Per-RPC (can vary per call)
- ✅ Stateless (no DB lookup per request)
- ✅ Works with mTLS (composite credentials)

**HOW — Client sends JWT:**

```python
import grpc
import jwt
from datetime import datetime, timedelta

class JWTClientInterceptor(grpc.aio.UnaryUnaryClientInterceptor):
    """
    INTERVIEW: Client interceptor adds JWT to every outgoing call.
    Better than passing metadata=[...] in every call manually.
    """
    def __init__(self, token_provider):
        self.token_provider = token_provider

    async def intercept_unary_unary(self, continuation, client_call_details, request):
        token = await self.token_provider.get_token()
        new_metadata = list(client_call_details.metadata or [])
        new_metadata.append(("authorization", f"Bearer {token}"))

        new_details = grpc.aio.ClientCallDetails(
            method=client_call_details.method,
            timeout=client_call_details.timeout,
            metadata=new_metadata,
            credentials=client_call_details.credentials,
            wait_for_ready=client_call_details.wait_for_ready,
        )
        return await continuation(new_details, request)


# Usage
class TokenProvider:
    def __init__(self, secret):
        self.secret = secret
        self._cached_token = None
        self._expires_at = None

    async def get_token(self):
        # Cache token until 1 min before expiry
        if self._cached_token and self._expires_at > datetime.utcnow() + timedelta(minutes=1):
            return self._cached_token

        # Generate new token
        payload = {
            "sub": "order-service",
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(hours=1),
            "scope": ["users:read", "users:write"],
        }
        self._cached_token = jwt.encode(payload, self.secret, algorithm="HS256")
        self._expires_at = datetime.utcnow() + timedelta(hours=1)
        return self._cached_token


# Build channel with interceptor
channel = grpc.aio.intercept_channel(
    grpc.aio.secure_channel("user-service:50051", credentials),
    JWTClientInterceptor(TokenProvider("secret-key"))
)
```

**HOW — Server validates JWT:**

```python
import grpc
import jwt

class JWTServerInterceptor(grpc.aio.ServerInterceptor):
    """
    INTERVIEW: Server interceptor validates JWT on EVERY incoming call.
    Excluded paths: health check, server reflection.
    """
    EXCLUDED_PATHS = [
        "/grpc.health.v1.Health/Check",
        "/grpc.reflection.v1alpha.ServerReflection/ServerReflectionInfo",
    ]

    def __init__(self, secret_key):
        self.secret_key = secret_key

    async def intercept_service(self, continuation, handler_call_details):
        # Skip excluded paths
        if handler_call_details.method in self.EXCLUDED_PATHS:
            return await continuation(handler_call_details)

        # Extract JWT from metadata
        metadata = dict(handler_call_details.invocation_metadata)
        auth_header = metadata.get("authorization", "")

        if not auth_header.startswith("Bearer "):
            return self._unauthenticated("Missing or invalid Authorization header")

        token = auth_header.replace("Bearer ", "")

        try:
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])

            # ⭐ Validate scopes for this method
            required_scope = self._get_required_scope(handler_call_details.method)
            if required_scope and required_scope not in payload.get("scope", []):
                return self._permission_denied(f"Missing scope: {required_scope}")

            # ⭐ Pass user context to service handler via contextvars
            # (gRPC doesn't have request-scoped context like FastAPI)
            return await continuation(handler_call_details)

        except jwt.ExpiredSignatureError:
            return self._unauthenticated("Token expired")
        except jwt.InvalidTokenError as e:
            return self._unauthenticated(f"Invalid token: {e}")

    def _unauthenticated(self, message):
        async def abort(request, context):
            await context.abort(grpc.StatusCode.UNAUTHENTICATED, message)
        return grpc.unary_unary_rpc_method_handler(abort)

    def _permission_denied(self, message):
        async def abort(request, context):
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, message)
        return grpc.unary_unary_rpc_method_handler(abort)

    def _get_required_scope(self, method: str) -> str | None:
        # Map RPC methods to required scopes
        scope_map = {
            "/userservice.UserService/GetUser":    "users:read",
            "/userservice.UserService/CreateUser": "users:write",
            "/userservice.UserService/DeleteUser": "users:admin",
        }
        return scope_map.get(method)


# Use in server
server = grpc.aio.server(
    interceptors=[JWTServerInterceptor(secret_key="your-secret")]
)
```

---

### Q3: Per-RPC credentials vs Channel credentials — kab kya use karein?

**Answer:**

**WHAT:**
- **Channel credentials** = TLS/mTLS at connection level (1 time setup)
- **Call credentials** = JWT/OAuth per RPC (sent in every call)
- **Composite credentials** = Channel + Call combined

**WHY combine:**
```
Use case: External service authentication
- mTLS proves YOUR service identity to remote
- JWT proves THE USER's identity for the request
- Both needed for "this service is calling on behalf of this user"
```

**HOW — Composite credentials:**

```python
import grpc

# 1. Channel credentials (mTLS)
channel_creds = grpc.ssl_channel_credentials(
    root_certificates=trusted_certs,
    private_key=client_key,
    certificate_chain=client_cert,
)

# 2. Call credentials (JWT — generated per request)
class JWTAuthMetadataPlugin(grpc.AuthMetadataPlugin):
    """
    INTERVIEW: AuthMetadataPlugin runs per RPC.
    More elegant than client interceptor for token injection.
    """
    def __init__(self, token_provider):
        self.token_provider = token_provider

    def __call__(self, context, callback):
        token = self.token_provider.get_sync()  # Must be sync for plugin
        callback([("authorization", f"Bearer {token}")], None)

call_creds = grpc.metadata_call_credentials(
    JWTAuthMetadataPlugin(token_provider)
)

# 3. Composite credentials
composite = grpc.composite_channel_credentials(channel_creds, call_creds)

channel = grpc.aio.secure_channel("user-service:50051", composite)
# ⭐ Now EVERY call automatically has both mTLS + JWT
```

---

### Q4: OAuth2 with gRPC kaise integrate karte ho?

**Answer:**

**WHAT:** OAuth2 = authorization framework. Get access token → use it in gRPC calls.

**WHY OAuth2 over plain JWT:**
- ✅ Standard flows (Client Credentials, Authorization Code)
- ✅ Token refresh built-in
- ✅ Scope-based authorization
- ✅ Integration with Auth0, Keycloak, AWS Cognito

**HOW — Client Credentials flow (service-to-service):**

```python
import httpx
import grpc
import time
from typing import Optional

class OAuth2TokenProvider:
    """
    INTERVIEW: Client Credentials flow for service-to-service.
    Token cached + auto-refreshed.
    """
    def __init__(self, token_url: str, client_id: str, client_secret: str, scope: str):
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
        self._token: Optional[str] = None
        self._expires_at: float = 0

    async def get_token(self) -> str:
        # Return cached if still valid (60s buffer)
        if self._token and time.time() < self._expires_at - 60:
            return self._token

        # Fetch new token
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "scope": self.scope,
                }
            )
            response.raise_for_status()
            data = response.json()

        self._token = data["access_token"]
        self._expires_at = time.time() + data["expires_in"]
        return self._token


# Use with interceptor (from Q2)
token_provider = OAuth2TokenProvider(
    token_url="https://auth.yourapp.com/oauth/token",
    client_id="order-service",
    client_secret="...",
    scope="users:read users:write",
)
```

**HOW — Server validates OAuth2 token (JWKS for asymmetric keys):**

```python
import jwt
import httpx
from functools import lru_cache

class OAuth2ServerInterceptor(grpc.aio.ServerInterceptor):
    """
    INTERVIEW: Validate OAuth2 JWT via JWKS endpoint.
    JWKS = JSON Web Key Set (public keys for verification)
    """
    def __init__(self, jwks_url: str, issuer: str, audience: str):
        self.jwks_url = jwks_url
        self.issuer = issuer
        self.audience = audience

    @lru_cache(maxsize=1)
    def _get_signing_key(self, kid: str):
        # Fetch JWKS, find key matching `kid` header
        response = httpx.get(self.jwks_url)
        jwks = response.json()
        for key in jwks["keys"]:
            if key["kid"] == kid:
                return jwt.algorithms.RSAAlgorithm.from_jwk(key)
        raise ValueError(f"No key found for kid: {kid}")

    async def intercept_service(self, continuation, handler_call_details):
        # ... extract token from metadata (same as Q2)
        token = self._extract_token(handler_call_details)

        # Get key ID from token header
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")

        try:
            payload = jwt.decode(
                token,
                self._get_signing_key(kid),
                algorithms=["RS256"],
                audience=self.audience,
                issuer=self.issuer,
            )
            return await continuation(handler_call_details)
        except jwt.PyJWTError as e:
            return self._unauthenticated(str(e))
```

---

### Q5: API Gateway pattern — JWT validation at gateway vs at each service?

**Answer:**

**WHAT:** Choice of where to validate JWT:
- Gateway-only validation
- Each service validates
- Hybrid (gateway validates + each service re-validates)

**WHY this matters:**

| Approach | Pros | Cons |
|---|---|---|
| **Gateway only** | Fast (one validation), services trust gateway | Single point of failure for security |
| **Each service** | Defense in depth, true zero-trust | Higher latency (validate every hop) |
| **Hybrid** ⭐ | Best of both | Slightly more complex |

**HOW — Hybrid approach:**

```python
# Gateway validates JWT, injects user context as gRPC metadata
class GatewayJWTHandler:
    async def handle_request(self, request, jwt_token):
        # 1. Validate JWT at gateway (slow signature check once)
        payload = jwt.decode(jwt_token, ...)

        # 2. Call downstream gRPC service WITH user context
        metadata = [
            ("x-user-id", str(payload["sub"])),
            ("x-user-roles", ",".join(payload["roles"])),
            ("x-request-id", str(uuid.uuid4())),
            # ⭐ Also pass JWT for downstream re-validation if needed
            ("authorization", f"Bearer {jwt_token}"),
        ]
        return await downstream_stub.SomeMethod(request, metadata=metadata)


# Downstream service trusts gateway-injected headers (mTLS verifies gateway identity)
class DownstreamInterceptor(grpc.aio.ServerInterceptor):
    async def intercept_service(self, continuation, handler_call_details):
        metadata = dict(handler_call_details.invocation_metadata)

        # Verify caller is gateway (via mTLS client cert CN)
        # (caller identity available in context.auth_context())

        # Extract pre-validated user context
        user_id = metadata.get("x-user-id")
        roles = metadata.get("x-user-roles", "").split(",")

        # Store in contextvars for handler access
        # ... continue
```

---

### Q6: Certificate rotation strategy production mein?

**Answer:**

**WHAT:** Certificates expire — need automated rotation without downtime.

**WHY rotation is hard:**
- Long-lived gRPC connections cache server cert
- Rotating server cert without restart = clients see old cert
- mTLS = both sides need synchronized cert rotation

**HOW — 3 approaches ranked by complexity:**

**Option 1: Cert-Manager + Let's Encrypt (Kubernetes)**
```yaml
# Cert-Manager auto-rotates certs
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: user-service-tls
spec:
  secretName: user-service-tls-secret
  duration: 2160h          # 90 days
  renewBefore: 360h        # Renew 15 days before expiry
  dnsNames:
    - user-service.default.svc.cluster.local
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
```

```python
# Server reads from K8s secret (auto-mounted as volume)
# Need to watch file and reload on change
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class CertReloadHandler(FileSystemEventHandler):
    def __init__(self, server):
        self.server = server

    def on_modified(self, event):
        if event.src_path.endswith(".crt"):
            # Reload TLS context
            self.server.reload_credentials(new_credentials())
```

**Option 2: HashiCorp Vault (PKI Secrets Engine)**
```python
import hvac

vault = hvac.Client(url="https://vault.internal:8200", token=...)

# Generate short-lived cert (24 hours)
response = vault.secrets.pki.generate_certificate(
    name="user-service",
    common_name="user-service.default.svc",
    ttl="24h"
)
cert = response["data"]["certificate"]
private_key = response["data"]["private_key"]

# Background task renews every 18 hours
```

**Option 3: AWS Certificate Manager Private CA**
```python
import boto3

acm_pca = boto3.client("acm-pca")
response = acm_pca.issue_certificate(
    CertificateAuthorityArn="arn:aws:acm-pca:...",
    Csr=csr_bytes,
    SigningAlgorithm="SHA256WITHRSA",
    Validity={"Value": 30, "Type": "DAYS"}
)
```

**Critical pattern: Graceful cert reload**
```python
# server.py — reload without restart
class GracefulTLSServer:
    def __init__(self):
        self._server = None
        self._current_creds = None

    def reload_credentials(self):
        # Read fresh certs from disk
        new_creds = self._build_credentials()

        # gRPC doesn't support hot-swap of credentials
        # Pattern: drain old server, start new server on same port
        old_server = self._server
        self._server = self._build_server(new_creds)
        await self._server.start()

        # Drain old (30s grace)
        await old_server.stop(grace=30)
```

---

### Q7: gRPC services ke beech authorization (RBAC) kaise implement karein?

**Answer:**

**WHAT:** RBAC = Role-Based Access Control. Who (subject) can do what (action) on what (resource).

**WHY needed beyond authentication:**
- Auth = "Are you who you say you are?"
- RBAC = "Are you allowed to do this specific thing?"

**HOW — Method-level authorization:**

```python
# decorators.py
import grpc
import functools
from typing import Iterable

def require_scopes(*required_scopes: str):
    """
    INTERVIEW: Decorator for method-level scope checking.
    Use on individual RPC methods that need specific permissions.
    """
    def decorator(method):
        @functools.wraps(method)
        async def wrapper(self, request, context):
            user_scopes = _get_user_scopes_from_context(context)
            missing = set(required_scopes) - set(user_scopes)
            if missing:
                await context.abort(
                    grpc.StatusCode.PERMISSION_DENIED,
                    f"Missing scopes: {missing}"
                )
            return await method(self, request, context)
        return wrapper
    return decorator


def require_role(*allowed_roles: str):
    """Decorator for role-based access."""
    def decorator(method):
        @functools.wraps(method)
        async def wrapper(self, request, context):
            user_roles = _get_user_roles_from_context(context)
            if not set(allowed_roles).intersection(user_roles):
                await context.abort(
                    grpc.StatusCode.PERMISSION_DENIED,
                    f"Requires one of roles: {allowed_roles}"
                )
            return await method(self, request, context)
        return wrapper
    return decorator


# Usage
class UserServiceServicer(user_service_pb2_grpc.UserServiceServicer):

    @require_scopes("users:read")
    async def GetUser(self, request, context):
        return user_pb2.User(...)

    @require_scopes("users:write")
    async def CreateUser(self, request, context):
        return user_pb2.User(...)

    @require_role("admin", "superadmin")
    async def DeleteUser(self, request, context):
        return empty_pb2.Empty()
```

**HOW — Resource-level authorization (e.g., "user can only see their own orders"):**

```python
class OrderServiceServicer(order_pb2_grpc.OrderServiceServicer):

    async def GetOrder(self, request, context):
        order = await db.get_order(request.order_id)

        # ⭐ Resource-level check: order belongs to caller?
        user_id = _get_user_id_from_context(context)
        if order.user_id != user_id and "orders:read_all" not in _get_user_scopes_from_context(context):
            await context.abort(
                grpc.StatusCode.PERMISSION_DENIED,
                "You can only access your own orders"
            )

        return self._order_to_proto(order)
```

---

## Security Checklist

```markdown
### Transport Security
- [ ] mTLS enabled for service-to-service
- [ ] Server certs from trusted CA (Let's Encrypt / private CA)
- [ ] Client certs with proper SAN
- [ ] TLS 1.2+ only
- [ ] Cert rotation automated (30-90 day rotation)

### Authentication
- [ ] JWT signature validation
- [ ] Token expiration enforced
- [ ] JWT issuer + audience verified
- [ ] OAuth2 for human/external clients
- [ ] mTLS for service-to-service

### Authorization
- [ ] Scope-based access for endpoints
- [ ] Role-based access for admin functions
- [ ] Resource-level checks (caller owns resource)
- [ ] Audit log for sensitive operations

### Operational
- [ ] Secrets in Vault/Secrets Manager (not in code)
- [ ] Client cert revocation list maintained
- [ ] Failed auth attempts monitored (alert on spike)
- [ ] Health check endpoint excluded from auth
```

---

## Common Security Pitfalls

| Pitfall | Risk | Fix |
|---|---|---|
| **insecure_channel in prod** | Plain text, eavesdropping | Use secure_channel with mTLS |
| **Self-signed cert in prod** | MITM possible | Use Let's Encrypt or private CA |
| **JWT secret in env var** | Leakable via logs | Use Vault/Secrets Manager |
| **No token expiry** | Stolen token = forever access | Short TTL + refresh tokens |
| **No scope validation** | Any authenticated user can call admin | Method-level RBAC |
| **Auth disabled in dev** | Devs forget to enable in prod | Same config + dummy certs in dev |
| **Health check requires auth** | K8s probes fail | Exclude `/grpc.health.v1.Health/Check` |
| **Cert in Docker image** | Leaks if image public | Mount as K8s secret |
