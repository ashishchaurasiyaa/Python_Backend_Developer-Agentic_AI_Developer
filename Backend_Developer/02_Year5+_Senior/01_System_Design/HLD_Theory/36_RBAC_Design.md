# RBAC — Role-Based Access Control Design

## WHAT

**RBAC** assigns permissions to **roles**, not individual users. Users are assigned roles.

```
User → Role → Permissions → Resources

alice  → admin  → [read, write, delete] → all resources
bob    → editor → [read, write]         → posts, comments
carol  → viewer → [read]               → public resources
```

**Variations:**
| Model | Description |
|---|---|
| RBAC | User → Role → Permissions (simple) |
| ABAC | Attribute-based (user.department == resource.department) |
| ReBAC | Relationship-based (Google Zanzibar — "user owns resource") |

---

## WHY RBAC

- Don't repeat permission logic in every endpoint
- Adding new user = assign role (not set 50 permissions)
- Audit: easy to see what a role can do
- Principle of Least Privilege: users only get what they need

---

## Database Schema Design

```sql
-- Core tables
CREATE TABLE users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email       VARCHAR(255) UNIQUE NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE roles (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(50) UNIQUE NOT NULL,   -- 'admin', 'editor', 'viewer'
    description TEXT
);

CREATE TABLE permissions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    action      VARCHAR(50) NOT NULL,          -- 'read', 'write', 'delete'
    resource    VARCHAR(100) NOT NULL,         -- 'posts', 'users', 'billing'
    UNIQUE(action, resource)
);

-- Junction tables
CREATE TABLE user_roles (
    user_id     UUID REFERENCES users(id),
    role_id     UUID REFERENCES roles(id),
    PRIMARY KEY (user_id, role_id)
);

CREATE TABLE role_permissions (
    role_id       UUID REFERENCES roles(id),
    permission_id UUID REFERENCES permissions(id),
    PRIMARY KEY (role_id, permission_id)
);
```

---

## Python Implementation

```python
from enum import StrEnum
from dataclasses import dataclass
from functools import wraps
from typing import Callable

class Action(StrEnum):
    READ   = "read"
    WRITE  = "write"
    DELETE = "delete"
    ADMIN  = "admin"

class Resource(StrEnum):
    POSTS    = "posts"
    USERS    = "users"
    BILLING  = "billing"
    SETTINGS = "settings"
    LLM_KEYS = "llm_keys"

@dataclass(frozen=True)
class Permission:
    action:   Action
    resource: Resource

    def __str__(self):
        return f"{self.action}:{self.resource}"


# ── Role definitions ──────────────────────────────────────────────────────────

ROLES: dict[str, set[Permission]] = {
    "admin": {
        Permission(Action.READ,   Resource.POSTS),
        Permission(Action.WRITE,  Resource.POSTS),
        Permission(Action.DELETE, Resource.POSTS),
        Permission(Action.READ,   Resource.USERS),
        Permission(Action.WRITE,  Resource.USERS),
        Permission(Action.DELETE, Resource.USERS),
        Permission(Action.READ,   Resource.BILLING),
        Permission(Action.ADMIN,  Resource.SETTINGS),
        Permission(Action.READ,   Resource.LLM_KEYS),
        Permission(Action.WRITE,  Resource.LLM_KEYS),
    },
    "editor": {
        Permission(Action.READ,  Resource.POSTS),
        Permission(Action.WRITE, Resource.POSTS),
        Permission(Action.READ,  Resource.USERS),
    },
    "viewer": {
        Permission(Action.READ, Resource.POSTS),
    },
    "billing_admin": {
        Permission(Action.READ,  Resource.BILLING),
        Permission(Action.WRITE, Resource.BILLING),
    },
}


# ── RBAC checker ─────────────────────────────────────────────────────────────

class RBACManager:
    def __init__(self, roles_config: dict[str, set[Permission]]):
        self._roles = roles_config

    def get_permissions(self, user_roles: list[str]) -> set[Permission]:
        """Get merged permissions for all user roles."""
        perms: set[Permission] = set()
        for role in user_roles:
            perms |= self._roles.get(role, set())
        return perms

    def has_permission(self, user_roles: list[str],
                       action: Action, resource: Resource) -> bool:
        perms = self.get_permissions(user_roles)
        return Permission(action, resource) in perms

    def check(self, user_roles: list[str],
              action: Action, resource: Resource) -> None:
        """Raise PermissionError if not allowed."""
        if not self.has_permission(user_roles, action, resource):
            raise PermissionError(
                f"Role(s) {user_roles} cannot {action} {resource}"
            )


rbac = RBACManager(ROLES)


# ── FastAPI integration ───────────────────────────────────────────────────────

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

app    = FastAPI()
bearer = HTTPBearer()
SECRET = "your-secret-key"

def get_current_user(creds: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    try:
        payload = jwt.decode(creds.credentials, SECRET, algorithms=["HS256"])
        return {
            "user_id": payload["sub"],
            "roles":   payload.get("roles", []),
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def require_permission(action: Action, resource: Resource):
    """Decorator factory for permission checking."""
    def dependency(user: dict = Depends(get_current_user)) -> dict:
        try:
            rbac.check(user["roles"], action, resource)
        except PermissionError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(exc),
            )
        return user
    return dependency


# Endpoints with RBAC
@app.get("/posts")
def list_posts(user=Depends(require_permission(Action.READ, Resource.POSTS))):
    return {"posts": [...]}

@app.post("/posts")
def create_post(user=Depends(require_permission(Action.WRITE, Resource.POSTS))):
    return {"created": True}

@app.delete("/users/{user_id}")
def delete_user(user_id: str,
                user=Depends(require_permission(Action.DELETE, Resource.USERS))):
    return {"deleted": user_id}

@app.get("/billing")
def view_billing(user=Depends(require_permission(Action.READ, Resource.BILLING))):
    return {"invoice": [...]}
```

---

## JWT with Roles

```python
import jwt
from datetime import datetime, timedelta, timezone

def create_access_token(user_id: str, roles: list[str]) -> str:
    payload = {
        "sub":   user_id,
        "roles": roles,
        "iat":   datetime.now(tz=timezone.utc),
        "exp":   datetime.now(tz=timezone.utc) + timedelta(hours=1),
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")

# Token payload example:
# {
#   "sub": "user-123",
#   "roles": ["editor", "billing_admin"],
#   "exp": 1716300000
# }
```

---

## Multi-Tenant RBAC (SaaS Pattern)

```python
# In SaaS: roles are scoped per organisation
# alice is admin in org-A, viewer in org-B

@dataclass
class OrgRole:
    org_id:    str
    role_name: str

class MultiTenantRBAC:
    def has_permission(self,
                       user_org_roles: list[OrgRole],
                       org_id: str,
                       action: Action,
                       resource: Resource) -> bool:
        # Only check roles for the current org
        user_roles = [r.role_name for r in user_org_roles if r.org_id == org_id]
        return rbac.has_permission(user_roles, action, resource)
```

---

## REAL LIFE ANALOGY

RBAC = **Office building access cards**
- "Intern" card: access to lobby + workspace (read)
- "Engineer" card: all of above + server room (write)
- "Admin" card: all doors including finance, HR (admin)

When a new intern joins → give Intern card. Don't manually configure which doors they can open one by one.

---

## Interview Q&A

**Q: RBAC vs ABAC — when to choose which?**
A: RBAC: simple, role-based rules ("admins can delete"). Good for 90% of cases.
ABAC: complex rules using attributes ("employee can access files in their department created after their hire date"). More flexible, much more complex to implement.

**Q: How do you avoid privilege escalation attacks?**
A: (1) Never trust client-sent role data — always read from DB/JWT signed by server (2) Validate token signature (3) Short-lived access tokens (1h) + refresh tokens (4) Principle of Least Privilege — default all roles to empty.

**Q: Where should RBAC checks live — middleware or controller?**
A: Both. Middleware handles coarse-grained auth (is this endpoint accessible to this role?). Controller handles fine-grained (is this user accessing THEIR resource?). Example: Editor can write posts — middleware allows. But can they edit OTHER users' posts? — controller checks.

**Q: How do you design RBAC for a multi-tenant SaaS?**
A: Roles are scoped to (org_id, role). JWT contains: `{"roles": [{"org_id": "o1", "role": "admin"}, {"org_id": "o2", "role": "viewer"}]}`. Every permission check includes org_id as context.
