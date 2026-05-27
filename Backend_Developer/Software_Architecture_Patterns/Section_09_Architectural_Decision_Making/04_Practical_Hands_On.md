# Lecture 4 — Practical Hands-On: Architecture Anti-Patterns

> **Theory file:** [04_Architecture_AntiPatterns.md](04_Architecture_AntiPatterns.md)

---

## 🎯 Is Practical Mein Kya Banayenge?

1. ✅ **Detect chatty services** — script to walk call graph + flag fan-out
2. ✅ **Detect over-modularization** — file-count-to-feature ratio script
3. ✅ **Detect god classes** — find files > N lines + count responsibilities
4. ✅ **Refactor demo** — God class → focused classes via strangler fig
5. ✅ **CI guardrails** — fail builds when anti-patterns regress

By end: aap automatically detect kar sakte ho jab anti-patterns sneak in karte hain.

---

## 1. Detect Chatty Services

### `detect_chatty.py`

```python
"""
Walk a service-call manifest, flag services with high fan-out per request.
Manifest: list of (service, depends_on_in_request) tuples.
"""

from collections import defaultdict


def analyze(call_manifest: list[tuple[str, str]], threshold: int = 5):
    fan_out = defaultdict(set)
    for caller, callee in call_manifest:
        fan_out[caller].add(callee)

    print(f"{'Service':<25s}{'Fan-out':>10s}{'Flag'}")
    print("─" * 50)
    for svc, deps in sorted(fan_out.items()):
        count = len(deps)
        flag = "  ⚠ CHATTY" if count >= threshold else ""
        print(f"{svc:<25s}{count:>10d}{flag}")


if __name__ == "__main__":
    # Simulated production trace
    manifest = [
        # OrderService fan-out (suspicious)
        ("OrderService", "UserService"),
        ("OrderService", "NameService"),
        ("OrderService", "AddressService"),
        ("OrderService", "PrefService"),
        ("OrderService", "ProductService"),
        ("OrderService", "InventoryService"),
        ("OrderService", "PricingService"),
        ("OrderService", "DiscountService"),
        ("OrderService", "TaxService"),

        # PaymentService — reasonable
        ("PaymentService", "OrderService"),
        ("PaymentService", "UserService"),

        # NotificationService — reasonable
        ("NotificationService", "UserService"),
        ("NotificationService", "TemplateService"),
    ]
    analyze(manifest, threshold=5)
```

### Sample Output

```
Service                      Fan-out  Flag
──────────────────────────────────────────────────
NotificationService                2
OrderService                       9  ⚠ CHATTY
PaymentService                     2
```

### How to Get Real Data

```
✓ OpenTelemetry traces → export trace IDs
✓ Group spans by root → count distinct downstream services
✓ Aggregate over 24h of production traffic
```

---

## 2. Detect Over-Modularization

### `detect_over_modular.py`

```python
"""
Ratio = python files / "feature-like" folders.
A high ratio for a small feature set → red flag.
"""
import os
import sys


def count_files(root: str, ext: str = ".py") -> int:
    n = 0
    for _, _, files in os.walk(root):
        n += sum(1 for f in files if f.endswith(ext))
    return n


def count_top_level_features(root: str) -> int:
    # heuristic: subdirectories at depth 1 of "domains" or "modules" or "features"
    candidates = ["domains", "modules", "features", "src/domains"]
    for c in candidates:
        path = os.path.join(root, c)
        if os.path.isdir(path):
            return sum(1 for d in os.listdir(path) if os.path.isdir(os.path.join(path, d)))
    # fallback
    return max(1, len([d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d))]))


def analyze(root: str):
    files = count_files(root)
    features = count_top_level_features(root)
    ratio = files / max(features, 1)
    print(f"📁 root:          {root}")
    print(f"📄 .py files:     {files}")
    print(f"🎯 features:      {features}")
    print(f"📊 files/feature: {ratio:.1f}")
    print()
    if ratio > 20:
        print("⚠  HIGH ratio — likely over-modular.")
        print("   Investigate: collapse single-use interfaces / adapters / helpers.")
    elif ratio > 10:
        print("🟡 Moderate. Watch for growth.")
    else:
        print("✅ Looks healthy.")


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    analyze(root)
```

### Run on This Repo

```bash
python detect_over_modular.py /Users/youngmanindia/Documents/PythonRevision/Backend_Developer
```

---

## 3. Detect God Classes

### `detect_god_class.py`

```python
"""
Flag .py files that:
  - exceed N lines
  - contain > M methods
  - touch many "domain words" (heuristic)
"""
import ast
import sys


DOMAIN_KEYWORDS = [
    "user", "auth", "billing", "payment", "order",
    "product", "notification", "email", "report",
    "session", "permission", "audit", "search",
]


def analyze_file(path: str, max_lines=400, max_methods=15):
    with open(path) as f:
        src = f.read()
    lines = src.count("\n")
    tree = ast.parse(src)
    classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    flags = []
    for cls in classes:
        methods = [m for m in cls.body if isinstance(m, ast.FunctionDef)]
        method_count = len(methods)
        # count distinct domain keywords used in method names
        domains_touched = {
            kw for m in methods for kw in DOMAIN_KEYWORDS if kw in m.name.lower()
        }
        if lines > max_lines or method_count > max_methods or len(domains_touched) >= 4:
            flags.append({
                "class": cls.name,
                "lines_in_file": lines,
                "methods": method_count,
                "domains_touched": sorted(domains_touched),
            })
    return flags


if __name__ == "__main__":
    for path in sys.argv[1:]:
        flagged = analyze_file(path)
        if flagged:
            print(f"\n⚠ {path}")
            for f in flagged:
                print(f"  class {f['class']}  "
                      f"lines={f['lines_in_file']}  "
                      f"methods={f['methods']}  "
                      f"domains={f['domains_touched']}")
```

### Run

```bash
python detect_god_class.py path/to/UserController.py path/to/*.py
```

---

## 4. Refactor Demo — Strangler Fig

### Before: God Class

#### `legacy/user_controller.py`

```python
class UserController:
    def __init__(self, db, mailer, billing_api, cache):
        self.db = db
        self.mailer = mailer
        self.billing_api = billing_api
        self.cache = cache

    # user CRUD
    def create_user(self, data): ...
    def update_user(self, id, data): ...
    def delete_user(self, id): ...

    # auth
    def authenticate(self, email, pw): ...
    def reset_password(self, email): ...

    # billing
    def calculate_invoice(self, id): ...
    def charge_user(self, id): ...

    # notifications
    def send_welcome_email(self, id): ...
    def send_password_reset_email(self, id): ...

    # ...20 more methods
```

### After: Split with Strangler Fig

#### `services/auth_service.py`

```python
class AuthService:
    def authenticate(self, email, pw): ...
    def reset_password(self, email): ...
```

#### `services/billing_service.py`

```python
class BillingService:
    def calculate_invoice(self, id): ...
    def charge_user(self, id): ...
```

#### `services/notification_service.py`

```python
class NotificationService:
    def send_welcome_email(self, id): ...
    def send_password_reset_email(self, id): ...
```

#### `legacy/user_controller.py` (now a facade)

```python
class UserController:
    """Backward-compat facade — delegates to new services."""

    def __init__(self, db, mailer, billing_api, cache):
        self.auth = AuthService(db)
        self.billing = BillingService(billing_api)
        self.notif = NotificationService(mailer)
        # user CRUD stays here for now
        self.db = db

    def authenticate(self, email, pw):
        return self.auth.authenticate(email, pw)

    def calculate_invoice(self, id):
        return self.billing.calculate_invoice(id)

    def send_welcome_email(self, id):
        return self.notif.send_welcome_email(id)

    # CRUD still here — extract next iteration
    def create_user(self, data): ...
```

### Migration Plan

```
✓ Iteration 1: extract Auth (this file)
✓ Iteration 2: callers migrate to AuthService directly
✓ Iteration 3: remove auth methods from facade
✓ Iteration 4: extract Billing  → repeat
✓ Iteration 5: extract Notification → repeat
✓ Iteration 6: extract User CRUD → repeat
✓ Iteration 7: delete UserController
```

---

## 5. CI Guardrails

### `.github/workflows/arch_guard.yml`

```yaml
name: Architecture Guards

on: [pull_request]

jobs:
  guard:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Run god class detector
        run: |
          # Fail if any class > 400 lines or > 15 methods
          python tools/detect_god_class.py $(git ls-files '*.py') > god_report.txt
          if grep -q "⚠" god_report.txt; then
            echo "❌ Architectural drift detected — see god_report.txt"
            cat god_report.txt
            exit 1
          fi

      - name: Run modularity ratio check
        run: |
          python tools/detect_over_modular.py . > modular_report.txt
          if grep -q "HIGH ratio" modular_report.txt; then
            echo "❌ Over-modularization risk — see modular_report.txt"
            cat modular_report.txt
            exit 1
          fi
```

### What This Catches

```
✓ A PR that pushes UserController past 400 lines → blocked
✓ A PR that adds 50 files in 1 new feature folder → flagged
✓ Architectural drift becomes a code-review topic, not a year-end regret
```

---

## 6. Anti-Pattern Detection Cheat Sheet

```
Symptom                              → Check                  → Tool
─────────────────────────────────────────────────────────────────────────
Single request hits 10+ services     → fan-out per request    → detect_chatty.py
Build time creeping up               → file count growth      → detect_over_modular.py
PR touches 5+ files for 1 logic chg  → coupling                → manual diff
One class > 400 lines                → God class                → detect_god_class.py
"Where does this go?" in reviews     → unclear ownership        → domain modeling
1-day task takes 1 week              → cognitive load            → onboarding survey
```

---

## 7. ✅ Hands-On Checklist

```
□ Ran detect_chatty.py on your manifest / OTel traces
□ Ran detect_over_modular.py on your repo, noted ratio
□ Ran detect_god_class.py, identified worst offenders
□ Drafted a strangler-fig plan for one God class
□ Added at least one CI guard for architectural drift
```

---

## 🔗 Next

- Next: [05_Domain_Driven_Design_Influence.md](05_Domain_Driven_Design_Influence.md)
