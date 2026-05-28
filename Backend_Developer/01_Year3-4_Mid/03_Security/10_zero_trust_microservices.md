# Zero Trust + Microservices Security — mTLS, SPIRE, Service Identity

## Quick Concepts

**WHAT:**
- **Zero Trust** = "Never trust, always verify" — no implicit network trust
- **mTLS (Mutual TLS)** = Both sides verify certificates
- **SPIFFE** = Specification for service identity
- **SPIRE** = Implementation of SPIFFE
- **Service Identity** = Cryptographic identity per service (workload)
- **Workload Attestation** = Proving a workload is who it claims
- **Service Mesh** = Infrastructure layer for service-to-service comm (Istio, Linkerd)

**WHY zero trust:**
- Traditional: "Inside network = trusted" → one breach = lateral movement
- Zero trust: Every request authenticated, regardless of network
- Required by: PCI-DSS, modern security frameworks
- Cloud-native: VPCs not enough (multi-cloud, K8s)

**HOW zero trust layers:**

```
┌──────────────────────────────────────────────────┐
│  Layer 1: Network — VPC, security groups         │  (necessary, not sufficient)
├──────────────────────────────────────────────────┤
│  Layer 2: Identity — mTLS certs per service      │  (who is this caller?)
├──────────────────────────────────────────────────┤
│  Layer 3: Auth — JWT for user context            │  (which user?)
├──────────────────────────────────────────────────┤
│  Layer 4: Authorization — Per-method RBAC        │  (allowed to do what?)
├──────────────────────────────────────────────────┤
│  Layer 5: Audit — Log every call                 │  (for forensics)
└──────────────────────────────────────────────────┘
```

---

## Interview Questions & Answers

### Q1: Zero Trust principles — kya hai aur kyu chahiye?

**Answer:**

**WHAT:** Security model with 3 core principles:

1. **Verify explicitly** — authenticate every request
2. **Least privilege access** — minimum permissions needed
3. **Assume breach** — design as if attackers are already inside

**WHY traditional perimeter security fails:**

```
Traditional ("Castle and Moat"):
- Strong walls (firewall) around network
- Inside = trusted (anyone can talk to anyone)
- Problem: One breached pod = full lateral movement

Real-world example (2017 Equifax):
- Attacker entered via Apache Struts vulnerability
- Inside network = trusted
- Accessed databases, exfiltrated 147 million records
- No mTLS, no service-level auth
```

**HOW Zero Trust differs:**

```
Zero Trust:
- Pod A wants to call Pod B
- Pod A presents identity (cert)
- Pod B verifies cert
- Pod B checks RBAC: "Can pod-a call this method?"
- All calls audited
- Even with breached Pod A → Pod B rejects unauthorized calls
```

**HOW — Implementation pillars:**

| Pillar | Tool/Pattern |
|---|---|
| **Service identity** | SPIRE, mTLS certs, ServiceAccount tokens |
| **Encryption** | mTLS everywhere |
| **Authentication** | JWT (user) + mTLS (service) |
| **Authorization** | OPA, RBAC per method |
| **Network segmentation** | NetworkPolicy, Service Mesh |
| **Observability** | Distributed tracing, audit logs |

---

### Q2: mTLS deep dive — implementation pattern?

**Answer:**

**WHAT:** Both client AND server present certificates.

**WHY for service-to-service:**

```
TLS (one-way):
- Server: "I'm api.example.com" → cert
- Client: trusts cert (browser pattern)
- Client identity: ❓ (need separate auth)

mTLS (mutual):
- Server: "I'm api.example.com" → cert
- Client: trusts server cert
- Client: "I'm order-service" → cert  ⭐
- Server: trusts client cert
- Both authenticated cryptographically
```

**HOW — Manual mTLS in Python:**

```python
# server.py
from fastapi import FastAPI
import ssl

app = FastAPI()

@app.get("/internal/data")
async def get_data(request: Request):
    # ⭐ Extract client cert info
    transport = request.scope.get("transport")
    peer_cert = transport.get_extra_info("peercert")

    if peer_cert:
        subject = dict(x[0] for x in peer_cert["subject"])
        client_cn = subject.get("commonName", "")

        # Authorize based on cert CN
        if client_cn not in ["order-service", "payment-service"]:
            raise HTTPException(403, f"Service {client_cn} not authorized")

    return {"data": "secret"}


# Run with mTLS
# Using gunicorn or uvicorn with SSL config
import uvicorn

uvicorn.run(
    app,
    host="0.0.0.0",
    port=8443,
    ssl_certfile="server.crt",
    ssl_keyfile="server.key",
    ssl_ca_certs="ca.crt",        # ⭐ CA to verify CLIENT certs
    ssl_cert_reqs=ssl.CERT_REQUIRED,  # ⭐ REQUIRE client cert
)
```

**HOW — Client with mTLS:**

```python
import httpx

# Client presents cert
async with httpx.AsyncClient(
    cert=("client.crt", "client.key"),   # ⭐ Client cert
    verify="ca.crt",                      # Verify server with this CA
) as client:
    response = await client.get("https://api.internal/data")
```

**HOW — Cert generation script:**

```bash
#!/bin/bash
# generate-mtls-certs.sh

# 1. CA (Certificate Authority)
openssl req -x509 -newkey rsa:4096 -keyout ca.key -out ca.crt \
  -days 365 -nodes -subj "/CN=zero-trust-ca"

# 2. Server cert
openssl req -newkey rsa:4096 -keyout server.key -out server.csr \
  -nodes -subj "/CN=api.internal"

cat > server.ext <<EOF
subjectAltName = DNS:api.internal,DNS:api,IP:127.0.0.1
EOF

openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key \
  -CAcreateserial -out server.crt -days 365 -extfile server.ext

# 3. Client cert (per service)
for service in "order-service" "payment-service" "user-service"; do
    openssl req -newkey rsa:4096 -keyout "${service}.key" \
      -out "${service}.csr" -nodes -subj "/CN=${service}"

    openssl x509 -req -in "${service}.csr" -CA ca.crt -CAkey ca.key \
      -CAcreateserial -out "${service}.crt" -days 365

    echo "Generated cert for ${service}"
done
```

---

### Q3: SPIFFE/SPIRE — service identity at scale?

**Answer:**

**WHAT:**
- **SPIFFE** = Secure Production Identity Framework For Everyone (spec)
- **SPIRE** = SPIFFE Runtime Environment (implementation)

**WHY beyond manual mTLS:**
- Manual certs: rotation nightmare at scale
- Each service needs cert + key → distribution problem
- SPIRE: automatic, short-lived (hours), workload-attested

**HOW — SPIFFE ID format:**

```
spiffe://example.org/my-app/order-service
       │            │       │
       │            │       └ Workload (service)
       │            └ Trust domain
       └ Scheme
```

**HOW — SVID (SPIFFE Verifiable Identity Document):**

Two formats:
1. **X.509 SVID** — TLS certificate with SPIFFE ID in SAN
2. **JWT SVID** — JWT with SPIFFE ID in `sub` claim

**HOW — SPIRE architecture:**

```
┌─────────────────────────────────────────────────────┐
│                  SPIRE Server                        │
│  - Issues SVIDs                                      │
│  - Trust bundle distribution                         │
│  - Workload registration database                    │
└────────────────────────┬────────────────────────────┘
                         │
                    ┌────┴─────┐
                    │          │
        ┌───────────▼──┐  ┌────▼──────────┐
        │ SPIRE Agent  │  │ SPIRE Agent   │  (one per node)
        │  Node 1      │  │  Node 2       │
        └───────┬──────┘  └────┬──────────┘
                │              │
        ┌───────▼──┐    ┌──────▼─────┐
        │ Workload │    │  Workload  │  (your services)
        │ (Pod A)  │    │  (Pod B)   │
        └──────────┘    └────────────┘
```

**HOW — Setup SPIRE (Kubernetes):**

```yaml
# SPIRE Server (control plane)
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: spire-server
spec:
  serviceName: spire-server
  replicas: 1
  template:
    spec:
      containers:
        - name: spire-server
          image: ghcr.io/spiffe/spire-server:1.8.0
          args: ["-config", "/run/spire/config/server.conf"]
          volumeMounts:
            - name: config
              mountPath: /run/spire/config

---
# SPIRE Agent (on every node as DaemonSet)
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: spire-agent
spec:
  template:
    spec:
      containers:
        - name: spire-agent
          image: ghcr.io/spiffe/spire-agent:1.8.0
          # Each agent connects to spire-server
```

**HOW — Workload registration:**

```bash
# Register a workload entry
kubectl exec -n spire spire-server-0 -- \
  /opt/spire/bin/spire-server entry create \
    -spiffeID spiffe://example.org/ns/default/sa/order-service \
    -parentID spiffe://example.org/ns/spire/sa/spire-agent \
    -selector k8s:ns:default \
    -selector k8s:sa:order-service
```

**HOW — Python workload (using spiffe SDK):**

```python
# pip install spiffe

from spiffe import WorkloadApiClient, SpiffeId

async def get_my_identity():
    """
    INTERVIEW: Workload gets SVID from SPIRE Agent.
    Auto-rotated every hour by SPIRE Agent.
    """
    async with WorkloadApiClient.new() as client:
        # Fetch X.509 SVID
        x509_context = await client.fetch_x509_context()
        svid = x509_context.default_svid

        print(f"My SPIFFE ID: {svid.spiffe_id}")
        # Output: spiffe://example.org/ns/default/sa/order-service

        # Trust bundle (CAs we trust)
        bundle = x509_context.x509_bundle_set
        for trust_domain, trust_bundle in bundle.bundles.items():
            print(f"Trust domain: {trust_domain}")
            print(f"CA certs: {len(trust_bundle.x509_authorities)}")

        return svid

# Use SVID for mTLS
async def call_user_service():
    svid = await get_my_identity()

    # SPIFFE-aware HTTP client
    import httpx
    cert = svid.cert_chain_as_pem.encode()
    key = svid.private_key_as_pem.encode()

    async with httpx.AsyncClient(
        cert=(cert, key),
        verify=trust_bundle_pem,
    ) as client:
        response = await client.get("https://user-service.internal/users/123")
```

---

### Q4: Service mesh security — Istio mTLS auto?

**Answer:**

**WHAT:** Istio sidecar (Envoy) handles mTLS automatically.

**WHY service mesh:**
- ✅ No code changes — mTLS at network layer
- ✅ Auto cert rotation
- ✅ Policy in YAML (not code)
- ✅ Observability built-in

**HOW — Istio mTLS modes:**

```yaml
# Global mTLS for entire mesh
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default
  namespace: istio-system
spec:
  mtls:
    mode: STRICT     # ⭐ REQUIRES mTLS for ALL services
    # Options:
    # - DISABLE: plaintext
    # - PERMISSIVE: accepts both (migration mode)
    # - STRICT: mTLS required
```

**HOW — Per-service mTLS:**

```yaml
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: payment-mtls
  namespace: production
spec:
  selector:
    matchLabels:
      app: payment-service
  mtls:
    mode: STRICT
  # Strict for specific ports
  portLevelMtls:
    8080:
      mode: STRICT
    8443:
      mode: PERMISSIVE
```

**HOW — Authorization policy (RBAC at mesh):**

```yaml
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: payment-access
  namespace: production
spec:
  selector:
    matchLabels:
      app: payment-service
  action: ALLOW
  rules:
    - from:
        - source:
            principals:
              # Only these services can call payment
              - "cluster.local/ns/production/sa/order-service"
              - "cluster.local/ns/production/sa/admin-service"
      to:
        - operation:
            methods: ["GET", "POST"]
            paths: ["/api/payments/*"]
```

**HOW — JWT validation at mesh:**

```yaml
apiVersion: security.istio.io/v1beta1
kind: RequestAuthentication
metadata:
  name: jwt-auth
  namespace: production
spec:
  selector:
    matchLabels:
      app: api-gateway
  jwtRules:
    - issuer: "https://auth.example.com"
      jwksUri: "https://auth.example.com/.well-known/jwks.json"
      forwardOriginalToken: true
```

---

### Q5: Network policies — K8s zero trust at network layer?

**Answer:**

**WHAT:** Kubernetes NetworkPolicy = firewall rules between pods.

**WHY:**
- Default: ALL pods can talk to ALL pods
- Zero trust: explicit allow only

**HOW — Default deny all:**

```yaml
# 1. Deny ALL ingress in namespace (foundation)
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-ingress
  namespace: production
spec:
  podSelector: {}                # ⭐ Empty = applies to all pods
  policyTypes:
    - Ingress
  # No ingress rules = deny all
```

**HOW — Allow specific pods:**

```yaml
# 2. Allow API gateway → payment service only
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: payment-allow-gateway
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: payment-service
  policyTypes:
    - Ingress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: api-gateway
      ports:
        - protocol: TCP
          port: 8080
```

**HOW — Allow specific namespaces:**

```yaml
# 3. Allow from production namespace only
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: db-allow-app
  namespace: data
spec:
  podSelector:
    matchLabels:
      app: postgresql
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              name: production
          podSelector:
            matchLabels:
              tier: backend
      ports:
        - port: 5432
```

**HOW — Egress restrictions:**

```yaml
# 4. Pod can only talk to specific external services
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: payment-egress
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: payment-service
  policyTypes:
    - Egress
  egress:
    # Allow DNS
    - to:
        - namespaceSelector: {}
          podSelector:
            matchLabels:
              k8s-app: kube-dns
      ports:
        - port: 53
          protocol: UDP

    # Allow Stripe API
    - to:
        - ipBlock:
            cidr: 34.102.0.0/16    # Stripe IPs
      ports:
        - port: 443

    # Allow DB
    - to:
        - podSelector:
            matchLabels:
              app: postgresql
      ports:
        - port: 5432
```

---

### Q6: Service-to-service auth — JWT propagation?

**Answer:**

**WHAT:** User's JWT propagates through microservice chain.

**WHY:**
- Service A receives user request with JWT
- Service A calls Service B for that user
- Service B needs user context (RBAC, audit)

**HOW — Pattern 1: JWT propagation (forward original)**

```python
# Service A (forwards user's JWT to downstream)
@app.get("/api/orders")
async def list_orders(request: Request, user=Depends(get_user_from_jwt)):
    user_token = request.headers.get("Authorization", "")

    # Call user-service for user details
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://user-service/users/me",
            headers={
                # ⭐ Forward original user JWT
                "Authorization": user_token,
                # Trace ID
                "X-Request-ID": request.state.request_id,
            }
        )
        user_data = response.json()

    return {"orders": [...], "user": user_data}
```

**HOW — Pattern 2: Service identity + user context (separate)**

```python
# Service A → Service B
# - mTLS: service identity (cert)
# - JWT: user identity (in metadata/headers)
# - Both required

@app.get("/api/orders")
async def list_orders(request: Request, user=Depends(get_user_from_jwt)):
    # Service A's own auth (mTLS + service JWT)
    service_token = await get_service_token()    # OAuth client credentials

    headers = {
        # Service identity
        "Authorization": f"Bearer {service_token}",
        # User context (forward from request)
        "X-User-Id": str(user.id),
        "X-User-Roles": ",".join(user.roles),
        "X-Request-ID": request.state.request_id,
    }

    async with httpx.AsyncClient(cert=(SVID_CERT, SVID_KEY)) as client:
        response = await client.get("https://user-service/users/me", headers=headers)
```

**HOW — Pattern 3: Token exchange (RFC 8693)**

```python
# Service A exchanges user token for service-specific token
async def exchange_token(user_token: str) -> str:
    """
    Get a downstream service-specific token.
    Used to limit scope per service.
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://auth.example.com/token/exchange",
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
                "subject_token": user_token,
                "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
                "audience": "user-service",   # Token only for this service
                "scope": "users:read",
            }
        )
        return response.json()["access_token"]
```

---

### Q7: Mesh vs Application-level auth — kya better?

**Answer:**

**HOW — Comparison:**

| Aspect | Service Mesh (Istio) | Application-level |
|---|---|---|
| **Code changes** | ❌ None | ✅ Auth library |
| **Performance** | ~1ms latency overhead | Native speed |
| **Visibility** | Centralized policy | Distributed |
| **Flexibility** | YAML-based | Code-based (full control) |
| **Debugging** | Mesh complexity | Simpler |
| **Multi-language** | ✅ Works for all | Each language needs lib |
| **Cost** | Sidecar memory/CPU | None |

**HOW — Hybrid approach (recommended):**

```
Mesh handles:
- mTLS encryption
- Service identity verification
- Basic allow/deny rules
- Network-level policies

Application handles:
- User authentication (JWT validation)
- Business logic authorization (RBAC)
- Resource-level checks ("can user X access order Y?")
- Audit logging
```

**Decision rules:**
- **Use mesh only:** Small team, polyglot, simple auth needs
- **App only:** Single language, simple infra, more control
- **Hybrid:** Most production setups (best of both)

---

### Q8: Audit logging — what to log + how?

**Answer:**

**WHAT:** Every security-relevant action logged.

**WHY:**
- Forensics (post-breach investigation)
- Compliance (GDPR, SOC2)
- Anomaly detection
- Performance debugging

**HOW — Audit log fields:**

```python
import structlog

audit_log = structlog.get_logger("audit")

async def log_security_event(
    event_type: str,
    user_id: Optional[int],
    service_id: str,
    resource: str,
    action: str,
    result: str,         # success, failure, denied
    metadata: dict = None,
):
    """
    INTERVIEW: Standardized audit log entry.
    """
    audit_log.info(
        "security_event",
        # ⭐ Mandatory fields
        event_type=event_type,
        timestamp=time.time(),
        user_id=user_id,
        service_id=service_id,
        resource=resource,
        action=action,
        result=result,
        # Tracing
        request_id=current_request_id.get(),
        trace_id=current_trace_id.get(),
        # Network
        client_ip=current_client_ip.get(),
        user_agent=current_user_agent.get(),
        # Custom
        metadata=metadata or {},
    )


# Usage examples
await log_security_event(
    event_type="authentication",
    user_id=user.id,
    service_id="api-gateway",
    resource="/api/login",
    action="login",
    result="success",
    metadata={"mfa_used": True},
)

await log_security_event(
    event_type="authorization",
    user_id=user.id,
    service_id="payment-service",
    resource="/api/payments/123",
    action="DELETE",
    result="denied",
    metadata={"required_role": "admin", "user_roles": ["customer"]},
)

await log_security_event(
    event_type="data_access",
    user_id=user.id,
    service_id="user-service",
    resource="users/456",        # Other user's data
    action="read",
    result="success",
    metadata={"reason": "support_ticket_789"},
)
```

**HOW — Storage + retention:**

```python
# Audit logs: STORE PERMANENTLY (or compliance-required time)

# Stream to multiple destinations
import structlog
from datetime import datetime

audit_log = structlog.get_logger("audit")

class AuditLogger:
    def __init__(self):
        self.cloudwatch_client = boto3.client("logs")
        self.s3_client = boto3.client("s3")

    async def log(self, event_data: dict):
        # 1. structlog → stdout → CloudWatch (real-time)
        audit_log.info("security_event", **event_data)

        # 2. Archive to S3 for long-term retention
        date = datetime.utcnow().strftime("%Y/%m/%d")
        key = f"audit-logs/{date}/{event_data['request_id']}.json"
        await self.s3_client.put_object(
            Bucket="security-audit-logs",
            Key=key,
            Body=json.dumps(event_data),
            ServerSideEncryption="AES256",
            StorageClass="STANDARD_IA",   # Cheaper for rarely accessed
        )

        # 3. Critical events → SNS for real-time alerts
        if event_data["result"] == "denied" and event_data["event_type"] == "authentication":
            await self.cloudwatch_client.put_log_events(...)
```

---

## Zero Trust Checklist

```markdown
### Service Identity
- [ ] Every service has unique identity (cert / SPIFFE ID)
- [ ] mTLS for service-to-service
- [ ] Certs auto-rotated (< 24h TTL preferred)
- [ ] No shared service accounts

### Network
- [ ] Default-deny NetworkPolicy in K8s
- [ ] Explicit allow rules per service
- [ ] Egress restrictions (no random internet)
- [ ] VPC private subnets

### Authentication
- [ ] User: JWT validation
- [ ] Service: mTLS or service JWT
- [ ] Both layers required for sensitive ops
- [ ] Token introspection for opaque tokens

### Authorization
- [ ] Per-method RBAC (not just per-service)
- [ ] Resource-level checks (user can only access own data)
- [ ] OPA or in-app policy engine
- [ ] Mesh-level basic allow/deny

### Audit
- [ ] All security events logged
- [ ] Long-term retention (S3)
- [ ] Real-time alerts on suspicious
- [ ] Monthly review of access patterns

### Operations
- [ ] Secret rotation automated
- [ ] Cert renewal automated
- [ ] Anomaly detection in place
- [ ] Incident response runbook
```
