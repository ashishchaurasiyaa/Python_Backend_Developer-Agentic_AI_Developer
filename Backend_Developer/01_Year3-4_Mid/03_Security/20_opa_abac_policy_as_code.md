# Authorization Beyond RBAC — ABAC, Policy-as-Code (OPA/Rego), ReBAC

## Quick Concepts

**WHAT:**
- **RBAC** = Role-Based Access Control — `role → permissions` (admin, editor, viewer)
- **ABAC** = Attribute-Based Access Control — decision = function of *attributes* (user.dept, resource.owner, env.time, request.ip)
- **ReBAC** = Relationship-Based Access Control — decision = *graph of relationships* ("user is `editor` of doc which is in folder X")
- **Policy-as-Code** = authz rules likhe jaate hain code/DSL mein (versioned, tested, reviewed), app code mein hardcoded nahi
- **OPA** = Open Policy Agent — general-purpose policy engine, **Rego** language use karta hai
- **PDP / PEP** = Policy *Decision* Point (decide karta hai) vs Policy *Enforcement* Point (enforce karta hai)
- **Zanzibar** = Google ka ReBAC paper → SpiceDB, OpenFGA iska open-source implementation

**WHY beyond RBAC:**
- RBAC simple hai par **role explosion** ho jaata hai: `region × department × seniority × project` → 1000s of roles
- "User apne *own* document edit kar sakta hai" — RBAC mein express karna mushkil (resource ownership = per-row, role nahi)
- "Sirf office hours mein, office IP se, EU data ko" — yeh *attributes* hain, role nahi → ABAC
- "User folder ka editor hai to uske andar sabhi docs edit kar sakta hai" — yeh *relationship* hai → ReBAC
- Authz logic har service mein bikhra hua (scattered) → centralize karo, audit karo, **redeploy ke bina** policy change karo

---

## The Model Progression — RBAC → ABAC → ReBAC

```
RBAC                      ABAC                          ReBAC
────                      ────                          ─────
role → permission         f(attributes) → allow/deny    graph(relationships) → allow/deny

if user.role == "admin"   if user.dept == res.dept      if user --editor--> doc
  allow                      and env.hour in 9..18         allow
                             and req.ip in office_cidr
                                                         (or inherited via folder)

Coarse-grained            Fine-grained, contextual      Fine-grained, hierarchical
Easy to reason about      Flexible, can get complex     Scales to billions of objects
Role explosion at scale   "Policy explosion" risk       Needs a relationship store
```

**WHAT each row means:**

| Model | Decision input | Best fit | Pain point |
|---|---|---|---|
| **RBAC** | `user.role` | Small fixed set of personas (admin/user) | Role explosion; no per-resource ownership |
| **ABAC** | user/resource/env **attributes** | Contextual rules (time, geo, ownership, clearance) | Hard to *audit* "who can access X?" (must evaluate policy) |
| **ReBAC** | **relationships** between subjects & objects | Sharing, folders, orgs, nested groups (Google Docs, GitHub) | Needs a dedicated graph store; eventual consistency |

**WHEN each fits (rule of thumb):**
- 2–10 fixed personas, no ownership → **RBAC** (start here, 80% apps yahin rukte hain)
- Decisions depend on data/context (`owner`, `dept`, `time`, `amount`, `clearance`) → **ABAC**
- "Share with user", nested groups, folder inheritance, billions of objects → **ReBAC** (Zanzibar-style)
- Real systems mix them: **RBAC for coarse + ABAC/ReBAC for fine-grained** (hybrid is normal)

> Important: ABAC RBAC ko *replace* nahi karta — RBAC is a *special case* of ABAC where the only attribute is `user.role`.

---

## Externalized Authorization — PDP vs PEP

**WHAT:** Authorization decision ko application code se *bahar nikaalo* (externalize). Do logical components:

```
        ┌──────────────────────────────────────────────────────┐
        │  Service (FastAPI)                                    │
        │                                                       │
        │   request ──▶  PEP  ── "can Alice DELETE order 42?" ─┐│
        │   (Policy Enforcement Point)                         ││
        │        ▲                                             ││
        │        │  allow / deny  ◀───────────────────────────┘│
        └────────┼──────────────────────────────────────────────┘
                 │ (HTTP POST input JSON, or in-process call)
                 ▼
        ┌──────────────────────────────────────────────────────┐
        │  PDP  (Policy Decision Point)  =  OPA                 │
        │   - evaluates POLICY (Rego)  against  input + data   │
        │   - returns a decision (true/false/object)           │
        │   - does NOT enforce — just decides                  │
        └──────────────────────────────────────────────────────┘
```

- **PEP** = jahan request *enter* karta hai (API gateway, middleware, FastAPI dependency). PEP decision ko *enforce* karta hai (403 throw / allow). PEP **kabhi khud decide nahi karta** — woh poochta hai.
- **PDP** = policy ko *evaluate* karke decision deta hai. OPA yahi hai. PDP stateless hai, koi request block nahi karta.

**WHY separate PDP from PEP (policy vs code separation):**
- **Centralize**: ek hi jagah saare authz rules — 20 microservices alag-alag logic na likhein
- **Audit**: policy ek versioned file hai (Git) → "kis din rule change hua, kisne kiya" trace ho
- **Change without redeploy**: policy push karo PDP ko, services ka deploy nahi chahiye
- **Testable**: policy ke apne unit tests (`opa test`), business logic se decouple
- **Polyglot**: Python, Go, Java sab ek hi OPA ko call karte hain — har language mein authz lib duplicate nahi

**HOW — historical ancestor (XACML):**

```
XACML (eXtensible Access Control Markup Language) — 2003, OASIS standard
  - Pehla mainstream "externalized ABAC" model
  - PDP / PEP / PAP / PIP terminology yahin se aayi:
      PAP = Policy Administration Point (jahan policy likhi/manage hoti hai)
      PIP = Policy Information Point (jahan se missing attributes fetch hote hain)
  - Policy XML mein likhi jaati thi → verbose, samajhna mushkil
  - OPA/Rego, Cedar, etc. = XACML ke ideas, modern + readable DSL ke saath
```

> Interview line: "OPA is XACML's spiritual successor — same PDP/PEP separation, but policy is code (Rego), not XML."

---

## OPA (Open Policy Agent) — Deep Dive

**WHAT:** General-purpose policy engine (CNCF graduated). Tum input JSON dete ho, OPA policy evaluate karke decision deta hai. Authz tak limited nahi — Kubernetes admission, Terraform plans, CI/CD, data filtering, sab.

**HOW OPA runs (deployment models):**

```
1. SIDECAR / DAEMON   — OPA as a separate process (localhost:8181), service HTTP se poochta hai
                        (most common for microservices — language-agnostic)
2. LIBRARY (Go)       — OPA embedded as a Go library, in-process (no network hop, lowest latency)
3. WASM               — policy compiled to WebAssembly, run inside app (any language host)
4. CENTRALIZED        — ek OPA service (not recommended for latency; sidecar > central for hot path)
```

**HOW — Rego ka mental model: `input` and `data`:**

OPA ke paas do documents hote hain:

```
input  =  the QUESTION   →  per-request JSON (current user, method, resource)  — caller bhejta hai
data   =  the FACTS      →  loaded/pushed JSON (role tables, allowlists, ownership maps)  — pre-loaded
```

Rego policy `input` aur `data` dono ko read karke ek result compute karti hai.

### Decision API

OPA ka REST API: policy ke `package authz` ka path `/v1/data/authz` ban jaata hai.

```
POST http://localhost:8181/v1/data/authz/allow
Content-Type: application/json

{ "input": { ... } }          ← request ko "input" key ke andar wrap karo

→ 200 OK
{ "result": true }            ← decision (yahan boolean; object bhi ho sakta hai)
```

- Rule `allow` ko query karna ho to path `/v1/data/<package_path>/<rule>` use karo → yahan `/v1/data/authz/allow`.
- `/v1/data/authz` (rule ke bina) poora package document return karta hai (saari rules ka object).
- API path **hamesha `/v1/data/...`** hota hai — `/v1/policies/...` policy *manage* karne ke liye hai (upload/list), decision ke liye nahi.

### A correct Rego policy (modern syntax)

```rego
# policy.rego  — modern Rego (OPA v0.59+ / OPA 1.0)
# OPA 1.0 mein `if` / `in` / `contains` keywords default hain.
# Agar OPA < 1.0 use kar rahe ho to top par `import rego.v1` likho.
package authz

import rego.v1   # OPA <1.0 ke liye zaroori; OPA 1.0 mein optional (default behaviour)

# Default DENY — fail closed. (Sabse important line.)
default allow := false

# RBAC rule: admin sab kuch GET kar sakta hai
allow if {
    input.method == "GET"
    input.user.role == "admin"
}

# ABAC rule: user apna OWN resource read/update kar sakta hai (ownership attribute)
allow if {
    input.method in {"GET", "PUT"}
    input.user.id == input.resource.owner_id
}

# ABAC rule: contextual — office hours + allowed method
allow if {
    input.method == "POST"
    input.user.department == "finance"
    input.context.hour >= 9
    input.context.hour < 18
}

# ABAC: iterate over a collection with `some ... in`
# "user ke kisi bhi group ko is resource par 'write' grant mila ho"
allow if {
    some grp in input.user.groups
    grp in data.resource_grants[input.resource.id].writers
}
```

Notes on the syntax (yeh exact modern Rego hai):
- `default allow := false` — agar koi `allow if {...}` rule satisfy na ho to `allow` = `false`. **Fail-closed.**
- `allow if { A; B }` — rule tabhi true jab **saari** conditions (AND) true hon. Newline ya `;` se separate.
- Multiple `allow` rules = **OR** (koi bhi ek satisfy ho to `allow` true).
- `:=` = assignment, `==` = comparison (`=` unification se avoid karo readability ke liye).
- `some grp in coll` + condition = "exists" / iteration. `x in coll` membership check hai.
- `{"GET", "PUT"}` = set literal; `input.method in {...}` = membership.

> Common interview gotcha: agar tum `default allow := false` *bhool* jao aur koi rule match na kare, to `allow` **undefined** ho jaata hai (not `false`). PEP ko `result` key hi nahi milegi → handle karna padega. Isliye `default` always likho.

### A Python PEP calling OPA over HTTP

```python
# pip install requests
import requests

OPA_URL = "http://localhost:8181/v1/data/authz/allow"   # /v1/data/<package>/<rule>

def is_allowed(user: dict, method: str, resource: dict, context: dict) -> bool:
    """PEP: OPA (PDP) se decision poochta hai. Khud decide nahi karta."""
    payload = {
        "input": {                       # ⭐ sab kuch "input" ke andar wrap
            "user": user,                # {"id": 7, "role": "user", "department": "finance", "groups": [...]}
            "method": method,            # "GET" / "POST" / "PUT" / "DELETE"
            "resource": resource,        # {"id": "doc-42", "owner_id": 7}
            "context": context,          # {"hour": 14, "ip": "10.0.0.5"}
        }
    }
    resp = requests.post(OPA_URL, json=payload, timeout=2)
    resp.raise_for_status()
    # OPA returns {"result": true} — agar rule undefined ho to "result" key absent
    return resp.json().get("result", False)   # fail-closed default

# Usage
ok = is_allowed(
    user={"id": 7, "role": "user", "department": "finance", "groups": ["fin-writers"]},
    method="PUT",
    resource={"id": "doc-42", "owner_id": 7},
    context={"hour": 14, "ip": "10.0.0.5"},
)
# → True (ownership rule matched: user.id == resource.owner_id)
```

**Production notes:**
- OPA ko **sidecar** (same pod, `localhost`) rakho → network latency ~sub-ms, no cross-node hop.
- `timeout` chhota rakho + **fail-closed** (`.get("result", False)`) — PDP down ho to deny karo, allow nahi.
- High-throughput hot path ke liye decision ko short-TTL cache karo (carefully — stale authz risky hai).

---

## OPA — Real Use Cases

| Use case | Kaise | Tool/Integration |
|---|---|---|
| **Microservice API authz** | PEP (gateway/middleware) → OPA sidecar → allow/deny | `POST /v1/data/...` |
| **Kubernetes admission control** | Cluster mein "no `:latest` images", "must have resource limits" enforce | **OPA Gatekeeper** (admission webhook + Constraints) |
| **Terraform / IaC policy** | `terraform plan` JSON ko OPA se validate ("no public S3 buckets") | `conftest` / OPA in CI |
| **CI/CD pipeline guardrails** | PR/deploy ke time policy check (config, manifests, Dockerfiles) | `conftest test` |
| **Envoy / service mesh** | L7 authz har request par data-plane mein | **Envoy `ext_authz`** filter → OPA (gRPC/HTTP) |
| **Data filtering** | "user ko sirf apne rows dikhao" — OPA partial eval se SQL `WHERE` generate | OPA Partial Evaluation / Compile API |

**HOW — Kubernetes Gatekeeper (ConstraintTemplate snippet):**

```rego
# Gatekeeper ConstraintTemplate ke andar Rego: latest-tag image block karo
package k8srequiredtag

violation contains {"msg": msg} if {
    some container in input.review.object.spec.containers
    endswith(container.image, ":latest")
    msg := sprintf("image '%v' uses :latest tag — pin a version", [container.image])
}
```

(Gatekeeper `violation` rule expect karta hai; non-empty result = admission **deny**.)

---

## Alternatives — Authz Engines Landscape

| Engine | Model | Language/DSL | Niche (one line) |
|---|---|---|---|
| **OPA** | ABAC / general policy | Rego | General-purpose, CNCF standard; K8s + microservices + IaC |
| **Oso** | RBAC/ABAC/ReBAC | Polar | App-embedded library; authz *inside* your app, ORM-friendly |
| **AWS Cedar** | RBAC + ABAC | Cedar | Amazon ka open-source lang; powers **Amazon Verified Permissions**; formally verified, analyzable |
| **Casbin** | RBAC/ABAC (model+policy) | PERM model files | Lightweight multi-language lib (Python `pycasbin`); simple RBAC/ABAC, easy to embed |
| **OpenFGA** | **ReBAC** (Zanzibar) | model DSL + tuples | CNCF; Auth0 origin; relationship tuples store, "fine-grained" sharing |
| **SpiceDB** | **ReBAC** (Zanzibar) | schema DSL + relations | AuthZed; production Zanzibar, consistency tokens (Zookies), high scale |
| **Topaz** | ReBAC + OPA | Rego + directory | OPA + a relationship directory combined (ABAC + ReBAC) |

**HOW — Zanzibar / ReBAC ka core idea (OpenFGA/SpiceDB):**

```
Relationship tuples store karo:   object # relation @ subject
  doc:readme       # owner   @ user:alice
  doc:readme       # parent  @ folder:eng
  folder:eng       # editor  @ group:eng-team#member
  group:eng-team   # member  @ user:bob

Check query:  "Can user:bob edit doc:readme?"
  → engine graph traverse karta hai:
     bob ∈ eng-team#member → eng-team is editor of folder:eng → readme's parent is folder:eng
  → ALLOW (inherited)
```

- RBAC/ABAC mein "who can access X?" mushkil hai (policy evaluate karni padti). Zanzibar mein yeh **reverse index** se fast hai.
- Trade-off: ek dedicated, consistent relationship database chahiye (eventual consistency + "Zookie" consistency tokens).

> Decision rule: **OPA** = contextual/attribute rules + infra policy. **OpenFGA/SpiceDB** = sharing/hierarchy/"google-docs-style" relationships. Dono saath bhi use hote hain.

---

## FastAPI Example — Dependency that calls the PDP (OPA)

OPA ko PDP ke roop mein use karte hue ek reusable FastAPI dependency. Yeh **PEP** hai: decision OPA se aata hai, enforcement (403) yahan hota hai.

```python
# pip install fastapi requests uvicorn
import requests
from fastapi import FastAPI, Depends, HTTPException, Request

app = FastAPI()
OPA_DECISION_URL = "http://localhost:8181/v1/data/authz/allow"

# --- (auth se user nikaalna — JWT decode etc.; yahan stubbed) ---
def get_current_user(request: Request) -> dict:
    # Real app: JWT decode karo (see 01_jwt_oauth2_rbac.md)
    return {
        "id": int(request.headers.get("x-user-id", "0")),
        "role": request.headers.get("x-user-role", "user"),
        "department": request.headers.get("x-user-dept", ""),
        "groups": request.headers.get("x-user-groups", "").split(",") if request.headers.get("x-user-groups") else [],
    }

def opa_decide(opa_input: dict) -> bool:
    """PDP call — fail-closed."""
    try:
        resp = requests.post(OPA_DECISION_URL, json={"input": opa_input}, timeout=2)
        resp.raise_for_status()
        return resp.json().get("result", False)
    except requests.RequestException:
        # PDP down / timeout → DENY (never fail-open for authz)
        return False

def authorize(action: str):
    """
    Dependency factory — har route ko ek 'action' deti hai.
    OPA input banati hai (user + method + resource + context), decision enforce karti hai.
    """
    def _dep(request: Request, user: dict = Depends(get_current_user)) -> dict:
        from datetime import datetime, timezone
        opa_input = {
            "user": user,
            "action": action,                      # "orders:read", "orders:delete"
            "method": request.method,              # GET / DELETE ...
            "path": request.url.path,
            "resource": {
                "id": request.path_params.get("order_id"),
                # ownership jaisa attribute real app mein DB se load hota (PIP)
                "owner_id": int(request.headers.get("x-resource-owner", "0")),
            },
            "context": {
                "hour": datetime.now(timezone.utc).hour,
                "ip": request.client.host if request.client else None,
            },
        }
        if not opa_decide(opa_input):
            raise HTTPException(status_code=403, detail=f"Not authorized for '{action}'")
        return user
    return _dep

# --- Routes ---
@app.get("/orders/{order_id}")
async def read_order(order_id: str, user: dict = Depends(authorize("orders:read"))):
    return {"order_id": order_id, "viewed_by": user["id"]}

@app.delete("/orders/{order_id}")
async def delete_order(order_id: str, user: dict = Depends(authorize("orders:delete"))):
    return {"deleted": order_id}
```

Matching Rego (`package authz`) for the above:

```rego
package authz
import rego.v1

default allow := false

# admin kuch bhi kar sakta hai
allow if { input.user.role == "admin" }

# owner apna order read/delete kar sakta hai (ABAC ownership)
allow if {
    input.action in {"orders:read", "orders:delete"}
    input.user.id == input.resource.owner_id
}
```

**Key design points:**
- Route business logic mein **koi if-role check nahi** — saara authz `authorize(...)` dependency + Rego mein. Policy badli → Rego push karo, FastAPI redeploy nahi.
- Ownership jaise attributes real-world mein DB/cache se aate hain (XACML term: **PIP** — Policy Information Point). Inhe `input.resource` mein bhar do, ya OPA ko `data` document push karo.
- Always **fail-closed** — PDP error = deny.

---

## Interview Questions & Answers

### Q1: RBAC vs ABAC vs ReBAC — kab kya use karoge?

**Answer:**
- **RBAC** — fixed personas (admin/editor/viewer), no per-resource ownership. Simplest; default choice. Pain: **role explosion** jab `region × dept × project` combine ho.
- **ABAC** — decision attributes par depend kare: `user.dept`, `resource.owner_id`, `env.time`, `request.ip`, `amount`. Contextual + per-resource. Pain: "X ko kaun access kar sakta hai?" answer karna mushkil (policy evaluate karni padti).
- **ReBAC** — relationships/graph: sharing, nested groups, folder inheritance (Google Docs, GitHub repos). Zanzibar model (OpenFGA/SpiceDB). Pain: dedicated relationship store + eventual consistency.
- Reality: **hybrid** — coarse RBAC + fine-grained ABAC/ReBAC. ABAC is a superset of RBAC (role = ek attribute).

### Q2: PDP vs PEP kya hai? Kyu alag karte hain?

**Answer:**
- **PEP** (Policy Enforcement Point) = jahan request enter karti hai (gateway/middleware/FastAPI dependency). Decision ko **enforce** karta hai (403 ya allow). Khud decide nahi karta — poochta hai.
- **PDP** (Policy Decision Point) = policy evaluate karke **decide** karta hai (OPA). Stateless, kuch block nahi karta.
- **Kyu alag**: centralize authz, audit (policy = versioned file), **redeploy ke bina** policy change, testable (`opa test`), polyglot (sab languages ek OPA call karein). XACML se aaya pattern (PDP/PEP/PAP/PIP).

### Q3: OPA mein `input` aur `data` mein farak?

**Answer:**
- `input` = **the question** — per-request JSON jo caller bhejta hai (current user, method, resource). Har request par badalta hai.
- `data` = **the facts** — pre-loaded/pushed JSON (role tables, allowlists, ownership maps, config). Relatively static, OPA mein load hota hai.
- Rego dono ko read karke result compute karti hai. Decision call: `POST /v1/data/<package>/<rule>` with `{"input": {...}}`.

### Q4: Yeh Rego policy bug kahan hai?

```rego
package authz
allow if { input.user.role == "admin" }   # `default allow` missing!
```

**Answer:** `default allow := false` **missing** hai. Agar non-admin aaye to koi `allow` rule match nahi karega → `allow` **undefined** ho jaata hai (`false` nahi). API response mein `result` key hi absent hogi. PEP agar `result` ko strictly read kare to crash/ambiguity. Fix:

```rego
package authz
import rego.v1
default allow := false                       # fail-closed
allow if { input.user.role == "admin" }
```
Plus PEP side bhi `json().get("result", False)` — fail-closed dono jagah.

### Q5: OPA ka decision API path kya hai? `/v1/policies` aur `/v1/data` mein farak?

**Answer:**
- **Decision** (evaluate): `POST /v1/data/<package>/<rule>` — e.g. `package authz` + rule `allow` → `POST /v1/data/authz/allow`, body `{"input": {...}}`, response `{"result": ...}`.
- **`/v1/policies/...`** = policy module **manage** karne ke liye (upload/list/delete Rego), evaluation ke liye nahi.
- `/v1/data/authz` (rule ke bina) poora package document deta hai. Galat path ka sabse common mistake.

### Q6: OPA ko sidecar vs library vs centralized — kaun behave better?

**Answer:**
- **Sidecar** (same pod, `localhost:8181`) — most common for microservices. Language-agnostic, sub-ms latency, no cross-node hop. Recommended hot-path ke liye.
- **Library (Go) / WASM** — in-process, lowest latency, no network. Go services ya jab har µs matter kare.
- **Centralized single OPA** — simplest ops par network latency + SPOF; hot authz path ke liye avoid. Sidecar > central.
- Hamesha **fail-closed** + short timeout. Decision cache carefully (stale authz = security risk).

### Q7: OPA kahan-kahan use hota hai sirf API authz ke alawa?

**Answer:** OPA general-purpose hai:
- **Kubernetes admission** — Gatekeeper se "no `:latest`", "resource limits required", "approved registries only".
- **Terraform / IaC** — `conftest` se plan JSON validate ("no public S3", "encryption required").
- **CI/CD** — PR/deploy guardrails (manifests, Dockerfiles, configs).
- **Envoy `ext_authz`** — service mesh data-plane mein L7 per-request authz.
- **Data filtering** — partial evaluation se SQL `WHERE` clause generate ("sirf apne rows").

### Q8: Zanzibar / ReBAC kya solve karta hai jo ABAC nahi karta?

**Answer:** ReBAC **relationships + inheritance** ko first-class banata hai. "User folder ka editor hai → andar ke saare docs edit kar sakta hai", nested groups, "share with user" — yeh sab relationship tuples (`object#relation@subject`) hain. Zanzibar (OpenFGA/SpiceDB) ek **reverse index** rakhta hai → "who can access X?" aur "what can user Y access?" dono fast. ABAC mein yeh policy-evaluation se slow/awkward hai. Cost: dedicated consistent relationship store + consistency tokens (Zookies).

---

## Decision Cheat-Sheet

```markdown
### Pick a model
- [ ] Few fixed personas, no ownership          → RBAC
- [ ] Ownership / time / geo / clearance / amount → ABAC
- [ ] Sharing / nested groups / folder inherit   → ReBAC (Zanzibar)
- [ ] Real prod                                  → hybrid (RBAC coarse + ABAC/ReBAC fine)

### Externalize authz
- [ ] PEP enforces, PDP (OPA) decides — keep them separate
- [ ] Policy in Git (Rego), versioned + code-reviewed
- [ ] `opa test` unit tests for policy
- [ ] OPA as sidecar (localhost), fail-closed, short timeout
- [ ] `default allow := false` in EVERY package
- [ ] Decision API = POST /v1/data/<package>/<rule> with {"input": {...}}

### Engine choice
- [ ] OPA/Rego        → general policy, K8s, IaC, microservice authz
- [ ] Oso / Casbin    → embed authz inside the app (library)
- [ ] AWS Cedar       → analyzable policy, Verified Permissions
- [ ] OpenFGA/SpiceDB → relationship/sharing-heavy (Zanzibar)
```

---

## Related Topics
- `01_jwt_oauth2_rbac.md` — RBAC fundamentals + roles/permissions (yahan se progression shuru)
- `04_oauth2_flows_deep.md` — OAuth2 flows, scopes, token exchange (authn jo authz se pehle aata hai)
- `10_zero_trust_microservices.md` — OPA as the authorization pillar in zero-trust, Envoy/mesh authz, PEP at service layer
- `11_compliance_gdpr_pci.md` — policy-as-code se auditable access control (compliance evidence)
