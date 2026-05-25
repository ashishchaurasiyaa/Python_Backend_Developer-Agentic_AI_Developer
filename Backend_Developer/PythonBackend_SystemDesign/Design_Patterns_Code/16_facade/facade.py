"""
============================================================
FACADE PATTERN — Practical Implementation
============================================================
Run:  python facade.py
"""
from dataclasses import dataclass, field
from typing import Protocol


# ============================================================
# SUBSYSTEMS — complex, independent components
# ============================================================
class InventoryService:
    def __init__(self):
        self._stock = {"sku-1": 10, "sku-2": 5, "sku-3": 0}

    def check_stock(self, sku: str, qty: int) -> bool:
        return self._stock.get(sku, 0) >= qty

    def reserve(self, sku: str, qty: int):
        if not self.check_stock(sku, qty):
            raise ValueError(f"Out of stock: {sku}")
        self._stock[sku] -= qty
        print(f"  [Inventory] Reserved {qty} of {sku}")


class PaymentGateway:
    def charge(self, card_token: str, amount: float) -> str:
        if amount > 10000:
            raise ValueError("Amount too high")
        txn_id = f"txn_{hash(card_token) % 10000}"
        print(f"  [Payment] Charged ${amount} → {txn_id}")
        return txn_id


class ShippingService:
    def schedule(self, address: str, items: list[str]) -> str:
        tracking = f"track_{hash(address) % 100000}"
        print(f"  [Shipping] Scheduled to {address}, tracking={tracking}")
        return tracking


class EmailService:
    def send(self, to: str, subject: str, body: str):
        print(f"  [Email] To: {to} | Subject: {subject}")


class AnalyticsService:
    def track_event(self, event: str, properties: dict):
        print(f"  [Analytics] {event}: {properties}")


class AuditLog:
    def log(self, action: str, user_id: int, details: dict):
        print(f"  [Audit] user={user_id} action={action}")


# ============================================================
# FACADE — simplifies the entire order flow
# ============================================================
@dataclass
class OrderRequest:
    user_id: int
    user_email: str
    items: list[dict]    # [{"sku": "sku-1", "qty": 2, "price": 100}]
    shipping_address: str
    card_token: str


@dataclass
class OrderResult:
    success: bool
    order_id: str | None = None
    txn_id: str | None = None
    tracking: str | None = None
    error: str | None = None


class OrderFacade:
    """Single entry point for placing orders."""

    def __init__(
        self,
        inventory: InventoryService,
        payment: PaymentGateway,
        shipping: ShippingService,
        email: EmailService,
        analytics: AnalyticsService,
        audit: AuditLog,
    ):
        self.inventory = inventory
        self.payment = payment
        self.shipping = shipping
        self.email = email
        self.analytics = analytics
        self.audit = audit

    def place_order(self, req: OrderRequest) -> OrderResult:
        order_id = f"ord_{req.user_id}_{hash(str(req.items)) % 10000}"
        try:
            # 1. Reserve inventory
            for item in req.items:
                self.inventory.reserve(item["sku"], item["qty"])

            # 2. Charge payment
            total = sum(it["price"] * it["qty"] for it in req.items)
            txn_id = self.payment.charge(req.card_token, total)

            # 3. Schedule shipping
            skus = [it["sku"] for it in req.items]
            tracking = self.shipping.schedule(req.shipping_address, skus)

            # 4. Send confirmation email
            self.email.send(
                to=req.user_email,
                subject=f"Order {order_id} confirmed",
                body=f"Your order has shipped — tracking: {tracking}",
            )

            # 5. Track analytics
            self.analytics.track_event("order_placed", {
                "order_id": order_id,
                "total": total,
                "items": len(req.items),
            })

            # 6. Audit log
            self.audit.log("place_order", req.user_id, {
                "order_id": order_id,
                "amount": total,
            })

            return OrderResult(True, order_id, txn_id, tracking)

        except Exception as e:
            self.audit.log("order_failed", req.user_id, {"error": str(e)})
            return OrderResult(False, error=str(e))


# ============================================================
# REAL-WORLD: Authentication Facade
# ============================================================
class UserRepo:
    _users = {"a@x.com": {"id": 1, "password_hash": "hash:secret", "active": True}}
    def get_by_email(self, email): return self._users.get(email)


class PasswordHasher:
    def verify(self, plain, hashed): return f"hash:{plain}" == hashed
    def hash(self, plain): return f"hash:{plain}"


class TokenService:
    def create(self, user_id): return f"jwt.{user_id}.signed"
    def revoke(self, token): print(f"  [Token] Revoked {token}")


class SessionStore:
    _sessions = {}
    def save(self, token, user_id):
        self._sessions[token] = user_id
        print(f"  [Session] Saved {token}")


class AuthFacade:
    def __init__(self, repo, hasher, tokens, sessions, audit):
        self.repo = repo
        self.hasher = hasher
        self.tokens = tokens
        self.sessions = sessions
        self.audit = audit

    def login(self, email: str, password: str) -> str:
        user = self.repo.get_by_email(email)
        if not user or not user.get("active"):
            self.audit.log("login_failed", 0, {"email": email, "reason": "user_not_found"})
            raise ValueError("Invalid credentials")
        if not self.hasher.verify(password, user["password_hash"]):
            self.audit.log("login_failed", user["id"], {"reason": "bad_password"})
            raise ValueError("Invalid credentials")
        token = self.tokens.create(user["id"])
        self.sessions.save(token, user["id"])
        self.audit.log("login_success", user["id"], {})
        return token


# ============================================================
# REAL-WORLD: HTTP Client Facade (mimics requests/boto3 style)
# ============================================================
class HTTPClientFacade:
    """Hides connection pooling, retries, auth, logging."""
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key
        self._connection_pool = "pool_initialized"

    def get(self, path: str, **params):
        return self._request("GET", path, params=params)

    def post(self, path: str, json: dict = None):
        return self._request("POST", path, json=json)

    def _request(self, method: str, path: str, **kwargs):
        url = f"{self.base_url}{path}"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        # Internally would: retry, pool, sign, log, metrics
        print(f"  [HTTP] {method} {url} (auth applied, retries=3)")
        return {"status": 200, "data": "..."}


# ============================================================
# DEMOS
# ============================================================
def demo_order_facade():
    print("=" * 60)
    print("DEMO 1: Order Facade — checkout flow")
    print("=" * 60)
    facade = OrderFacade(
        inventory=InventoryService(),
        payment=PaymentGateway(),
        shipping=ShippingService(),
        email=EmailService(),
        analytics=AnalyticsService(),
        audit=AuditLog(),
    )

    req = OrderRequest(
        user_id=42,
        user_email="ashish@example.com",
        items=[
            {"sku": "sku-1", "qty": 2, "price": 500},
            {"sku": "sku-2", "qty": 1, "price": 300},
        ],
        shipping_address="Bengaluru, India",
        card_token="tok_visa_xyz",
    )
    result = facade.place_order(req)
    print(f"\n  Result: {result}")


def demo_auth_facade():
    print("\n" + "=" * 60)
    print("DEMO 2: Auth Facade — login flow")
    print("=" * 60)
    facade = AuthFacade(
        repo=UserRepo(),
        hasher=PasswordHasher(),
        tokens=TokenService(),
        sessions=SessionStore(),
        audit=AuditLog(),
    )
    try:
        token = facade.login("a@x.com", "secret")
        print(f"\n  Login successful, token={token}")
    except ValueError as e:
        print(f"  Login failed: {e}")


def demo_http_facade():
    print("\n" + "=" * 60)
    print("DEMO 3: HTTP Client Facade (boto3-style)")
    print("=" * 60)
    client = HTTPClientFacade("https://api.example.com", "secret-key")
    client.get("/users/42")
    client.post("/users", json={"name": "Ashish"})


def demo_facade_failure():
    print("\n" + "=" * 60)
    print("DEMO 4: Facade handles failure gracefully")
    print("=" * 60)
    facade = OrderFacade(
        inventory=InventoryService(),
        payment=PaymentGateway(),
        shipping=ShippingService(),
        email=EmailService(),
        analytics=AnalyticsService(),
        audit=AuditLog(),
    )
    req = OrderRequest(
        user_id=99,
        user_email="bad@example.com",
        items=[{"sku": "sku-3", "qty": 1, "price": 100}],  # out of stock
        shipping_address="X",
        card_token="tok",
    )
    result = facade.place_order(req)
    print(f"\n  Result: {result}")


if __name__ == "__main__":
    demo_order_facade()
    demo_auth_facade()
    demo_http_facade()
    demo_facade_failure()

    print("\n" + "=" * 60)
    print("KEY TAKEAWAYS")
    print("=" * 60)
    print("""
1. Facade = simplified entry point to complex subsystem
2. Orchestrate subsystems, don't reimplement them
3. Inject dependencies for testability
4. Examples: SDK clients, BFF, service layer, ORM
5. Keep thin — no business logic, just coordination
6. Provide both facade AND direct subsystem access
""")
