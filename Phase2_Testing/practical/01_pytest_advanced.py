"""
pytest Advanced — Practical Examples (40 LPA Series)
=====================================================
Run with:
    pytest 01_pytest_advanced.py -v
    python 01_pytest_advanced.py

Install dependencies:
    pip install pytest pytest-asyncio pytest-mock pytest-cov
    pip install factory-boy faker hypothesis
    pip install fastapi httpx

Structure:
    Section 1 — Basic Fixtures + conftest patterns
    Section 2 — Parametrize
    Section 3 — Mocking
    Section 4 — FastAPI Testing
    Section 5 — Async Tests
    Section 6 — Factory Boy
    Section 7 — Hypothesis
    Section 8 — Coverage Demo
    Section 9 — Markers + Slow Tests
"""

import asyncio
import json
import math
import os
import random
import sys
import time
from datetime import datetime, date
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, Mock, call, patch

import pytest

# Module name helper — when run via pytest the module name is NOT '__main__'
# Using sys.modules trick ensures patch target is always correct.
_THIS_MODULE = sys.modules[__name__]

# ── SECTION 1 ─────────────────────────────────────────────────────────────────
# Basic Fixtures + conftest patterns
# In-file fixtures demonstrate all 4 scopes (normally conftest.py mein hoge)
# ──────────────────────────────────────────────────────────────────────────────


# ── Simulated in-memory "database" for this demo ──────────────────────────────

_SESSION_DB = {}       # session-level shared state
_MODULE_LOG = []       # module-level log


def _create_table(db: dict, table: str):
    db.setdefault(table, {})


def _insert(db: dict, table: str, record: dict) -> int:
    table_data = db.setdefault(table, {})
    new_id = (max(table_data.keys(), default=0)) + 1
    table_data[new_id] = {"id": new_id, **record}
    return new_id


def _get(db: dict, table: str, record_id: int) -> Optional[dict]:
    return db.get(table, {}).get(record_id)


# ── Scope: session ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def db_connection():
    """
    scope="session" — poori test session mein sirf ek baar create/destroy.
    Expensive connections (real DB, Docker) ke liye use karo.
    """
    print("\n[SESSION SETUP] db_connection created")
    _SESSION_DB.clear()
    _create_table(_SESSION_DB, "users")
    _create_table(_SESSION_DB, "orders")
    yield _SESSION_DB
    print("\n[SESSION TEARDOWN] db_connection closed")
    _SESSION_DB.clear()


# ── Scope: module ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def db_table(db_connection):
    """
    scope="module" — ek .py file ke sab tests ke liye ek instance.
    db_connection (session scope) pe depend karna VALID hai — broad scope ok.
    """
    print("\n[MODULE SETUP] db_table ready")
    _MODULE_LOG.append("module_setup")
    yield db_connection
    print("\n[MODULE TEARDOWN] db_table cleanup")
    _MODULE_LOG.append("module_teardown")


# ── Scope: function (default) ──────────────────────────────────────────────────

@pytest.fixture(scope="function")
def fresh_user(db_table):
    """
    scope="function" (default) — har test ke liye fresh instance.
    Yield ke baad teardown chalta hai — even if test fails.
    """
    print("\n[FUNCTION SETUP] Creating fresh test user")
    user_id = _insert(db_table, "users", {"name": "Test User", "email": "test@example.com"})
    yield _get(db_table, "users", user_id)
    # Teardown: user delete karo
    db_table["users"].pop(user_id, None)
    print(f"\n[FUNCTION TEARDOWN] User {user_id} deleted")


# ── autouse=True fixture ───────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def test_timer():
    """
    autouse=True — har test mein automatically apply hota hai.
    Test ko explicitly request nahi karna.
    Use case: timing, logging, resetting global state.
    """
    start = time.perf_counter()
    yield
    elapsed = time.perf_counter() - start
    # Slow tests ke liye warning (>1 second)
    if elapsed > 1.0:
        print(f"\n[SLOW TEST WARNING] Test took {elapsed:.3f}s")


# ── yield fixture with explicit setup/teardown prints ─────────────────────────

@pytest.fixture
def managed_temp_file(tmp_path):
    """
    yield fixture — setup BEFORE yield, teardown AFTER yield.
    tmp_path pytest ka built-in fixture hai (temporary directory).
    """
    filepath = tmp_path / "test_data.json"
    data = {"users": [], "orders": []}
    filepath.write_text(json.dumps(data))
    print(f"\n[SETUP] Temp file created: {filepath}")

    yield filepath

    # Teardown — test fail ho ya pass, yeh chalega
    if filepath.exists():
        filepath.unlink()
    print(f"\n[TEARDOWN] Temp file deleted")


# ── Fixture factory ────────────────────────────────────────────────────────────

@pytest.fixture
def make_user(db_table):
    """
    Fixture factory — returns a function, not a value.
    Use karo jab ek test mein multiple customized instances chahiye.
    """
    created_ids = []

    def _factory(name="Alice", email=None, role="viewer", age=25):
        if email is None:
            email = f"{name.lower().replace(' ', '.')}@example.com"
        uid = _insert(db_table, "users", {"name": name, "email": email, "role": role, "age": age})
        created_ids.append(uid)
        return _get(db_table, "users", uid)

    yield _factory

    # Cleanup all created users
    for uid in created_ids:
        db_table["users"].pop(uid, None)


# ── Tests for Section 1 ────────────────────────────────────────────────────────

class TestFixtureScopes:
    """Fixture scope behavior demonstrate karta hai."""

    def test_session_scope_persists(self, db_connection):
        """db_connection session-scoped hai — same dict across tests."""
        db_connection["__test_key__"] = "session_value"
        assert db_connection["__test_key__"] == "session_value"

    def test_session_scope_shared(self, db_connection):
        """Session fixture ka state pichle test se carry forward hota hai."""
        # Previous test ne set kiya tha — abhi bhi hai
        assert db_connection["__test_key__"] == "session_value"
        del db_connection["__test_key__"]  # cleanup

    def test_fresh_user_created(self, fresh_user):
        """function-scoped fixture — har test ke liye naya user."""
        assert fresh_user is not None
        assert fresh_user["name"] == "Test User"
        assert fresh_user["id"] > 0

    def test_fresh_user_is_new_instance(self, fresh_user, db_table):
        """Dusra test — fresh user ek NAYA object hai."""
        # fresh_user fixture ne naya user create kiya is test ke liye
        assert fresh_user["name"] == "Test User"

    def test_managed_file_read_write(self, managed_temp_file):
        """yield fixture — file exists during test, deleted after."""
        assert managed_temp_file.exists()
        content = json.loads(managed_temp_file.read_text())
        assert "users" in content
        assert "orders" in content

    def test_fixture_factory_multiple(self, make_user):
        """Fixture factory — ek test mein multiple customized users."""
        admin = make_user(name="AdminUser", role="admin", age=30)
        viewer = make_user(name="ViewerUser", role="viewer", age=22)
        guest = make_user(name="GuestUser", role="guest")

        assert admin["role"] == "admin"
        assert viewer["role"] == "viewer"
        assert guest["role"] == "guest"
        # Sab alag objects hain
        assert admin["id"] != viewer["id"] != guest["id"]

    def test_fixture_factory_defaults(self, make_user):
        """Factory defaults work karte hain."""
        user = make_user()
        assert user["name"] == "Alice"
        assert user["email"] == "alice@example.com"
        assert user["role"] == "viewer"
        assert user["age"] == 25


# ── SECTION 2 ─────────────────────────────────────────────────────────────────
# Parametrize — same test logic, alag inputs
# ──────────────────────────────────────────────────────────────────────────────


# Helper functions to test
def is_palindrome(s: str) -> bool:
    cleaned = s.lower().replace(" ", "")
    return cleaned == cleaned[::-1]


def categorize_age(age: int) -> str:
    if age < 0:
        raise ValueError("Age cannot be negative")
    if age < 13:
        return "child"
    if age < 18:
        return "teenager"
    if age < 65:
        return "adult"
    return "senior"


def safe_divide(a: float, b: float) -> float:
    if b == 0:
        raise ZeroDivisionError("Cannot divide by zero")
    return a / b


def validate_email(email: str) -> bool:
    """Basic email validation."""
    if not isinstance(email, str):
        return False
    parts = email.split("@")
    if len(parts) != 2:
        return False
    local, domain = parts
    return bool(local) and "." in domain


# ── Basic parametrize ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("word, expected", [
    ("racecar", True),
    ("hello", False),
    ("A man a plan a canal Panama", True),
    ("", True),           # empty string edge case
    ("a", True),          # single character
])
def test_is_palindrome(word, expected):
    assert is_palindrome(word) == expected


# ── Multiple params ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("age, expected_category", [
    (0, "child"),
    (5, "child"),
    (12, "child"),
    (13, "teenager"),
    (17, "teenager"),
    (18, "adult"),
    (30, "adult"),
    (64, "adult"),
    (65, "senior"),
    (90, "senior"),
])
def test_categorize_age(age, expected_category):
    assert categorize_age(age) == expected_category


def test_categorize_age_negative():
    with pytest.raises(ValueError, match="negative"):
        categorize_age(-1)


# ── pytest.param with marks ────────────────────────────────────────────────────

@pytest.mark.parametrize("email, is_valid", [
    ("user@example.com", True),
    ("invalid-no-at-sign", False),
    ("user@domain.co.in", True),
    ("@nodomain.com", False),
    ("user@nodot", False),
    pytest.param(
        "user+tag@example.com",
        True,
        id="email-with-plus-tag",
    ),
    pytest.param(
        "",
        False,
        id="empty-string",
    ),
    pytest.param(
        "unicode@münchen.de",
        True,
        marks=pytest.mark.skip(reason="Unicode domains not yet supported in validator"),
        id="unicode-domain-skip",
    ),
])
def test_validate_email(email, is_valid):
    assert validate_email(email) == is_valid


# ── IDs for readable output ────────────────────────────────────────────────────

@pytest.mark.parametrize("a, b, expected", [
    (10.0, 2.0, 5.0),
    (7.0, 2.0, 3.5),
    (0.0, 5.0, 0.0),
    (-9.0, 3.0, -3.0),
], ids=[
    "10-div-2",
    "7-div-2-float",
    "zero-numerator",
    "negative-numerator",
])
def test_safe_divide(a, b, expected):
    assert safe_divide(a, b) == pytest.approx(expected)


def test_safe_divide_zero():
    with pytest.raises(ZeroDivisionError):
        safe_divide(5, 0)


# ── Combining multiple parametrize ────────────────────────────────────────────

@pytest.mark.parametrize("prefix", ["Mr", "Ms", "Dr"])
@pytest.mark.parametrize("name", ["Alice", "Bob"])
def test_greeting_combinations(prefix, name):
    """2 * 3 = 6 test cases automatically generate honge."""
    greeting = f"{prefix}. {name}"
    assert greeting.startswith(prefix)
    assert name in greeting


# ── Indirect parametrize ──────────────────────────────────────────────────────

@pytest.fixture
def user_by_role(request):
    """Indirect fixture — request.param se role milta hai."""
    role = request.param
    permissions = {
        "admin": ["read", "write", "delete"],
        "editor": ["read", "write"],
        "viewer": ["read"],
    }
    return {"role": role, "permissions": permissions.get(role, [])}


@pytest.mark.parametrize("user_by_role, can_delete", [
    ("admin", True),
    ("editor", False),
    ("viewer", False),
], indirect=["user_by_role"])
def test_delete_permission_indirect(user_by_role, can_delete):
    has_delete = "delete" in user_by_role["permissions"]
    assert has_delete == can_delete


# ── SECTION 3 ─────────────────────────────────────────────────────────────────
# Mocking
# ──────────────────────────────────────────────────────────────────────────────


# ── Helper functions/classes to mock ──────────────────────────────────────────

class PaymentGateway:
    def charge(self, amount: float, card_token: str) -> dict:
        """Real implementation would call Stripe/Razorpay API."""
        raise NotImplementedError("Real gateway not available in tests")

    def refund(self, payment_id: str) -> dict:
        raise NotImplementedError


class NotificationService:
    def send_email(self, to: str, subject: str, body: str) -> bool:
        raise NotImplementedError

    def send_sms(self, phone: str, message: str) -> bool:
        raise NotImplementedError


class OrderService:
    def __init__(self, gateway: PaymentGateway, notifier: NotificationService):
        self.gateway = gateway
        self.notifier = notifier

    def place_order(self, user_email: str, amount: float, card_token: str) -> dict:
        payment = self.gateway.charge(amount, card_token)
        if payment.get("status") != "success":
            raise RuntimeError("Payment failed")
        self.notifier.send_email(user_email, "Order Confirmed", f"Your order of ₹{amount} is placed.")
        return {"order_id": payment["transaction_id"], "amount": amount, "status": "placed"}


def fetch_user_profile(user_id: int) -> dict:
    """Simulates HTTP call to user service."""
    raise NotImplementedError("Real HTTP call not available in tests")


def get_current_time_greeting() -> str:
    """Returns greeting based on current hour."""
    hour = datetime.now().hour
    if hour < 12:
        return "Good Morning"
    elif hour < 17:
        return "Good Afternoon"
    return "Good Evening"


class UserRepository:
    def find_by_id(self, user_id: int) -> Optional[dict]:
        raise NotImplementedError

    def save(self, user: dict) -> dict:
        raise NotImplementedError


# ── Basic Mock with return_value ──────────────────────────────────────────────

class TestBasicMocking:

    def test_mock_return_value(self):
        """Mock hamesha configured value return karta hai."""
        mock_fn = Mock(return_value={"id": 1, "name": "Alice"})
        result = mock_fn(42)
        assert result == {"id": 1, "name": "Alice"}
        mock_fn.assert_called_once_with(42)
        assert mock_fn.call_count == 1

    def test_mock_side_effect_list(self):
        """side_effect list: ek ek karke values return karo."""
        mock_api = Mock(side_effect=[100, 200, 300])
        assert mock_api() == 100
        assert mock_api() == 200
        assert mock_api() == 300
        with pytest.raises(StopIteration):
            mock_api()  # list exhausted

    def test_mock_side_effect_exception_on_third(self):
        """Pehle 2 calls succeed, 3rd pe exception."""
        mock_db = Mock(side_effect=[
            {"id": 1},
            {"id": 2},
            ConnectionError("DB timeout on 3rd call"),
        ])
        assert mock_db()["id"] == 1
        assert mock_db()["id"] == 2
        with pytest.raises(ConnectionError, match="timeout"):
            mock_db()

    def test_mock_side_effect_function(self):
        """side_effect as function — dynamic response."""
        def double(n):
            return n * 2
        mock_fn = Mock(side_effect=double)
        assert mock_fn(5) == 10
        assert mock_fn(3) == 6
        assert mock_fn(0) == 0

    def test_patch_as_context_manager(self):
        """patch context manager — scope ke andar mock, bahar real."""
        with patch("os.path.exists", return_value=True) as mock_exists:
            assert os.path.exists("/fake/path") is True
            mock_exists.assert_called_once_with("/fake/path")
        # Context se bahar nikle — real os.path.exists

    def test_patch_object_on_class_method(self):
        """patch.object — specific instance ke method ko mock karo."""
        repo = UserRepository()
        with patch.object(repo, "find_by_id", return_value={"id": 99, "name": "Mocked"}):
            result = repo.find_by_id(99)
        assert result["name"] == "Mocked"

    def test_patch_dict_environment(self):
        """patch.dict — environment variables temporarily change karo."""
        original = os.environ.get("APP_ENV", "not_set")
        with patch.dict(os.environ, {"APP_ENV": "testing", "DEBUG": "true"}):
            assert os.environ["APP_ENV"] == "testing"
            assert os.environ["DEBUG"] == "true"
        # Restore ho gaya
        assert os.environ.get("APP_ENV", "not_set") == original

    def test_order_service_with_mocks(self):
        """Real integration: OrderService ko mocks inject karo."""
        mock_gateway = Mock(spec=PaymentGateway)
        mock_gateway.charge.return_value = {
            "status": "success",
            "transaction_id": "txn_123",
        }

        mock_notifier = Mock(spec=NotificationService)
        mock_notifier.send_email.return_value = True

        service = OrderService(mock_gateway, mock_notifier)
        result = service.place_order("alice@example.com", 999.0, "card_tok_abc")

        assert result["order_id"] == "txn_123"
        assert result["status"] == "placed"

        mock_gateway.charge.assert_called_once_with(999.0, "card_tok_abc")
        mock_notifier.send_email.assert_called_once_with(
            "alice@example.com", "Order Confirmed", "Your order of ₹999.0 is placed."
        )

    def test_order_service_payment_failure(self):
        """Payment fail hone pe RuntimeError raise hona chahiye."""
        mock_gateway = Mock(spec=PaymentGateway)
        mock_gateway.charge.return_value = {"status": "declined"}

        mock_notifier = Mock(spec=NotificationService)

        service = OrderService(mock_gateway, mock_notifier)
        with pytest.raises(RuntimeError, match="Payment failed"):
            service.place_order("alice@example.com", 500.0, "bad_card")

        # Email send nahi hona chahiye jab payment fail ho
        mock_notifier.send_email.assert_not_called()

    def test_mock_datetime_now_morning(self):
        """
        datetime.now() ko mock karke time control karo.
        patch.object(_THIS_MODULE, "datetime") — module name mein digits hone par
        string-based patch kaam nahi karta, isliye patch.object use karo.
        """
        mock_morning = datetime(2024, 6, 15, 9, 30, 0)  # 9:30 AM

        with patch.object(_THIS_MODULE, "datetime") as mock_dt:
            mock_dt.now.return_value = mock_morning
            greeting = get_current_time_greeting()

        assert greeting == "Good Morning"

    def test_mock_datetime_now_evening(self):
        """Evening greeting test."""
        mock_evening = datetime(2024, 6, 15, 19, 0, 0)  # 7 PM

        with patch.object(_THIS_MODULE, "datetime") as mock_dt:
            mock_dt.now.return_value = mock_evening
            greeting = get_current_time_greeting()

        assert greeting == "Good Evening"

    def test_mock_open_context_manager(self):
        """builtins.open ko mock karke file reading test karo."""
        mock_content = '{"name": "Alice", "role": "admin"}'

        with patch("builtins.open", create=True) as mock_open_fn:
            mock_file = MagicMock()
            mock_file.__enter__.return_value = mock_file
            mock_file.__exit__.return_value = False
            mock_file.read.return_value = mock_content
            mock_open_fn.return_value = mock_file

            with open("config.json") as f:
                content = f.read()

        assert content == mock_content
        mock_open_fn.assert_called_once_with("config.json")


# ── pytest-mock: mocker fixture ───────────────────────────────────────────────

class TestPytestMock:
    """
    pytest-mock ke tests.
    'mocker' fixture automatically cleanup karta hai — patch manually close nahi karna.
    Install: pip install pytest-mock
    """

    def test_mocker_patch(self, mocker):
        """
        mocker.patch.object — automatic cleanup after test.
        Note: string-based patch requires valid Python identifier as module name.
        Files starting with digits (like '01_...') use patch.object(module, attr).
        """
        mock_fetch = mocker.patch.object(_THIS_MODULE, "fetch_user_profile")
        mock_fetch.return_value = {"id": 1, "name": "Mocked User", "email": "mock@test.com"}

        result = fetch_user_profile(1)

        assert result["name"] == "Mocked User"
        mock_fetch.assert_called_once_with(1)

    def test_mocker_spy(self, mocker):
        """
        mocker.spy — REAL function call karta hai lekin calls track karta hai.
        Stub ya Mock se alag: actual code execute hota hai.
        """
        spy = mocker.spy(math, "sqrt")

        result = math.sqrt(16)

        assert result == 4.0
        spy.assert_called_once_with(16)
        assert spy.call_count == 1

    def test_mocker_multiple_patches(self, mocker):
        """Multiple patches in one test with mocker."""
        mock_gateway = mocker.patch.object(PaymentGateway, "charge")
        mock_gateway.return_value = {"status": "success", "transaction_id": "txn_999"}

        mock_notifier = mocker.patch.object(NotificationService, "send_email")
        mock_notifier.return_value = True

        gateway = PaymentGateway()
        result = gateway.charge(100.0, "tok_abc")

        assert result["status"] == "success"
        mock_gateway.assert_called_once_with(100.0, "tok_abc")


# ── SECTION 4 ─────────────────────────────────────────────────────────────────
# FastAPI Testing
# ──────────────────────────────────────────────────────────────────────────────

try:
    from fastapi import Depends, FastAPI, HTTPException, Header
    from fastapi.testclient import TestClient
    from pydantic import BaseModel
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

pytestmark_fastapi = pytest.mark.skipif(
    not FASTAPI_AVAILABLE, reason="fastapi not installed"
)

if FASTAPI_AVAILABLE:
    # ── Mini FastAPI app ───────────────────────────────────────────────────────

    class UserCreate(BaseModel):
        name: str
        email: str
        role: str = "viewer"

    class UserResponse(BaseModel):
        id: int
        name: str
        email: str
        role: str

    # Production mein: real DB session; tests mein: override karenge
    _FAKE_DB_STORE: dict = {}

    def get_db() -> dict:
        return _FAKE_DB_STORE

    def get_current_user(authorization: str = Header(default=None)) -> dict:
        """Simple auth: Authorization: Bearer <name> header check karo."""
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Unauthorized")
        token = authorization.split(" ", 1)[1]
        if token == "invalid":
            raise HTTPException(status_code=403, detail="Forbidden")
        return {"name": token, "role": "viewer"}

    app = FastAPI(title="Test App")

    @app.get("/health")
    async def health_check():
        return {"status": "ok", "version": "1.0.0"}

    @app.get("/users", response_model=list)
    async def list_users(db: dict = Depends(get_db)):
        return list(db.get("users", {}).values())

    @app.get("/users/{user_id}")
    async def get_user(user_id: int, db: dict = Depends(get_db)):
        users = db.get("users", {})
        if user_id not in users:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        return users[user_id]

    @app.post("/users", status_code=201)
    async def create_user(user: UserCreate, db: dict = Depends(get_db)):
        users = db.setdefault("users", {})
        # Duplicate email check
        for existing in users.values():
            if existing["email"] == user.email:
                raise HTTPException(status_code=409, detail="Email already exists")
        new_id = max(users.keys(), default=0) + 1
        users[new_id] = {"id": new_id, **user.model_dump()}
        return users[new_id]

    @app.delete("/users/{user_id}", status_code=204)
    async def delete_user(
        user_id: int,
        db: dict = Depends(get_db),
        current_user: dict = Depends(get_current_user),
    ):
        users = db.get("users", {})
        if user_id not in users:
            raise HTTPException(status_code=404, detail="User not found")
        del users[user_id]

    @app.get("/protected")
    async def protected_route(current_user: dict = Depends(get_current_user)):
        return {"message": f"Hello, {current_user['name']}!", "role": current_user["role"]}


@pytest.fixture
def isolated_db():
    """Har test ke liye fresh empty DB."""
    test_store = {}
    yield test_store


@pytest.fixture
def test_client_with_db(isolated_db):
    """TestClient + dependency override combo."""
    if not FASTAPI_AVAILABLE:
        pytest.skip("fastapi not installed")
    app.dependency_overrides[get_db] = lambda: isolated_db
    client = TestClient(app)
    yield client, isolated_db
    app.dependency_overrides.clear()


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="fastapi not installed")
class TestFastAPISync:
    """TestClient (sync) — most common approach."""

    def test_health_check(self, test_client_with_db):
        client, _ = test_client_with_db
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_create_user(self, test_client_with_db):
        client, db = test_client_with_db
        payload = {"name": "Alice", "email": "alice@test.com", "role": "admin"}
        response = client.post("/users", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Alice"
        assert data["id"] > 0

    def test_get_existing_user(self, test_client_with_db):
        client, db = test_client_with_db
        # Pehle user create karo
        create_resp = client.post(
            "/users", json={"name": "Bob", "email": "bob@test.com"}
        )
        user_id = create_resp.json()["id"]

        # Ab get karo
        get_resp = client.get(f"/users/{user_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == "Bob"

    def test_get_nonexistent_user_404(self, test_client_with_db):
        client, _ = test_client_with_db
        response = client.get("/users/9999")
        assert response.status_code == 404
        assert "9999" in response.json()["detail"]

    def test_duplicate_email_409(self, test_client_with_db):
        client, _ = test_client_with_db
        payload = {"name": "Charlie", "email": "charlie@test.com"}
        client.post("/users", json=payload)  # first — succeeds
        resp = client.post("/users", json=payload)  # second — duplicate
        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"]

    def test_list_users_empty(self, test_client_with_db):
        client, _ = test_client_with_db
        response = client.get("/users")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_users_after_creation(self, test_client_with_db):
        client, _ = test_client_with_db
        client.post("/users", json={"name": "User1", "email": "u1@test.com"})
        client.post("/users", json={"name": "User2", "email": "u2@test.com"})
        response = client.get("/users")
        assert len(response.json()) == 2

    def test_protected_route_with_auth(self, test_client_with_db):
        """Auth header se user info inject karo."""
        client, _ = test_client_with_db
        response = client.get(
            "/protected",
            headers={"Authorization": "Bearer John"}
        )
        assert response.status_code == 200
        assert "John" in response.json()["message"]

    def test_protected_route_unauthorized(self, test_client_with_db):
        """Authorization header missing — 401."""
        client, _ = test_client_with_db
        response = client.get("/protected")
        assert response.status_code == 401

    def test_delete_user_with_auth(self, test_client_with_db):
        """Delete requires auth."""
        client, _ = test_client_with_db
        # User create karo
        create_resp = client.post(
            "/users", json={"name": "DeleteMe", "email": "del@test.com"}
        )
        user_id = create_resp.json()["id"]

        # Auth ke saath delete karo
        del_resp = client.delete(
            f"/users/{user_id}",
            headers={"Authorization": "Bearer AdminUser"},
        )
        assert del_resp.status_code == 204

        # User gone
        get_resp = client.get(f"/users/{user_id}")
        assert get_resp.status_code == 404

    def test_dependency_override(self, isolated_db):
        """Dependency override manually demonstrate karo."""
        if not FASTAPI_AVAILABLE:
            pytest.skip("fastapi not installed")
        custom_db = {"users": {1: {"id": 1, "name": "PreloadedUser", "email": "pre@test.com", "role": "admin"}}}
        app.dependency_overrides[get_db] = lambda: custom_db
        try:
            client = TestClient(app)
            response = client.get("/users/1")
            assert response.status_code == 200
            assert response.json()["name"] == "PreloadedUser"
        finally:
            app.dependency_overrides.clear()


# ── SECTION 5 ─────────────────────────────────────────────────────────────────
# Async Tests
# ──────────────────────────────────────────────────────────────────────────────


# ── Async helper functions ────────────────────────────────────────────────────

async def async_fetch_data(url: str) -> dict:
    """Real mein httpx call karti. Tests mein mock karenge."""
    raise NotImplementedError("Real HTTP call")


async def async_process_users(user_ids: list) -> list:
    """Multiple users ko concurrently fetch karo (asyncio.gather)."""
    tasks = [async_fetch_data(f"/users/{uid}") for uid in user_ids]
    results = await asyncio.gather(*tasks)
    return results


async def async_calculate(n: int) -> int:
    """Simple async computation."""
    await asyncio.sleep(0)  # Yield control
    return n * n


async def async_retry(func, max_retries: int = 3):
    """Retry logic — fail hone pe dobara try karo."""
    for attempt in range(max_retries):
        try:
            return await func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(0)  # tests mein sleep=0
    return None


# ── Async fixture ──────────────────────────────────────────────────────────────

@pytest.fixture
async def async_test_db():
    """
    Async fixture — async DB setup/teardown simulate karta hai.
    pytest-asyncio asyncio_mode=auto mein automatically async fixtures support karta hai.
    """
    db = {"initialized": True, "records": {}}
    await asyncio.sleep(0)  # async initialization simulate karo
    yield db
    db.clear()
    await asyncio.sleep(0)  # async cleanup


# ── Async tests ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_async_calculate():
    """Basic async test — @pytest.mark.asyncio decorator."""
    result = await async_calculate(5)
    assert result == 25


@pytest.mark.asyncio
async def test_async_calculate_multiple():
    results = [await async_calculate(n) for n in range(5)]
    assert results == [0, 1, 4, 9, 16]


@pytest.mark.asyncio
async def test_async_fixture(async_test_db):
    """Async fixture use karna."""
    assert async_test_db["initialized"] is True
    async_test_db["records"]["key1"] = "value1"
    assert async_test_db["records"]["key1"] == "value1"


@pytest.mark.asyncio
async def test_async_mock_with_asyncmock():
    """
    AsyncMock — async function ko mock karo.
    patch.object use karo jab module name valid Python identifier nahi ho.
    """
    mock_fetch = AsyncMock(return_value={"id": 1, "name": "Mocked"})

    with patch.object(_THIS_MODULE, "async_fetch_data", mock_fetch):
        result = await async_fetch_data("/users/1")

    assert result["name"] == "Mocked"
    mock_fetch.assert_awaited_once_with("/users/1")


@pytest.mark.asyncio
async def test_asyncio_gather_with_mock():
    """asyncio.gather ke saath multiple async mock calls."""
    mock_fetch = AsyncMock(side_effect=[
        {"id": 1, "name": "Alice"},
        {"id": 2, "name": "Bob"},
        {"id": 3, "name": "Charlie"},
    ])

    with patch.object(_THIS_MODULE, "async_fetch_data", mock_fetch):
        results = await async_process_users([1, 2, 3])

    assert len(results) == 3
    assert results[0]["name"] == "Alice"
    assert results[2]["name"] == "Charlie"
    assert mock_fetch.await_count == 3


@pytest.mark.asyncio
async def test_async_retry_success_on_second():
    """Retry logic: pehli call fail, doosri succeed."""
    call_count = 0

    async def flaky():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise ConnectionError("Flaky connection")
        return {"data": "success"}

    result = await async_retry(flaky, max_retries=3)
    assert result["data"] == "success"
    assert call_count == 2


@pytest.mark.asyncio
async def test_async_retry_all_fail():
    """Sab retries fail ho jayen — exception raise honi chahiye."""
    async def always_fails():
        raise ValueError("Always fails")

    with pytest.raises(ValueError, match="Always fails"):
        await async_retry(always_fails, max_retries=3)


@pytest.mark.asyncio
async def test_asyncmock_side_effect_exception():
    """AsyncMock se exception raise karo."""
    mock_api = AsyncMock(side_effect=TimeoutError("Request timed out"))

    with pytest.raises(TimeoutError, match="timed out"):
        await mock_api()


# ── SECTION 6 ─────────────────────────────────────────────────────────────────
# Factory Boy + Faker
# ──────────────────────────────────────────────────────────────────────────────

try:
    import factory
    from faker import Faker
    FACTORY_BOY_AVAILABLE = True
except ImportError:
    FACTORY_BOY_AVAILABLE = False

if FACTORY_BOY_AVAILABLE:
    fake = Faker()
    Faker.seed(42)  # reproducible results

    # ── Factories ──────────────────────────────────────────────────────────────

    class AddressFactory(factory.Factory):
        class Meta:
            model = dict

        street = factory.Faker("street_address")
        city = factory.Faker("city")
        state = factory.Faker("state")
        country = factory.Faker("country_code")
        pincode = factory.Faker("postcode")

    class UserFactory(factory.Factory):
        class Meta:
            model = dict

        # Sequence: unique incrementing value
        id = factory.Sequence(lambda n: n + 1)
        # Faker: random realistic data
        name = factory.Faker("name")
        # LazyAttribute: other fields pe depend
        email = factory.LazyAttribute(
            lambda o: f"{o.name.lower().replace(' ', '.')}_{o.id}@example.com"
        )
        # LazyFunction: callable se value
        age = factory.LazyFunction(lambda: random.randint(18, 65))
        # SubFactory: nested object
        address = factory.SubFactory(AddressFactory)
        # Static value
        is_active = True
        role = "viewer"
        # Faker directly on field
        phone = factory.Faker("phone_number")

    class OrderFactory(factory.Factory):
        class Meta:
            model = dict

        id = factory.Sequence(lambda n: 1000 + n)
        # SubFactory: related object
        user = factory.SubFactory(UserFactory)
        # LazyAttribute: user ka email use karo
        billing_email = factory.LazyAttribute(lambda o: o.user["email"])
        amount = factory.Faker("pyfloat", min_value=100, max_value=50000, right_digits=2)
        status = "pending"
        created_at = factory.LazyFunction(datetime.now)

    class ProductFactory(factory.Factory):
        class Meta:
            model = dict

        id = factory.Sequence(lambda n: n + 100)
        sku = factory.Sequence(lambda n: f"SKU-{n:04d}")
        name = factory.Faker("word")
        slug = factory.LazyAttribute(lambda o: o.name.lower().replace(" ", "-"))
        price = factory.Faker("pydecimal", min_value=10, max_value=9999, right_digits=2)
        stock = factory.LazyFunction(lambda: random.randint(0, 500))
        category = factory.Iterator(["electronics", "clothing", "food", "books"])


@pytest.mark.skipif(not FACTORY_BOY_AVAILABLE, reason="factory-boy not installed")
class TestFactoryBoy:

    def test_create_single_user(self):
        user = UserFactory()
        assert "name" in user
        assert "@" in user["email"]
        assert 18 <= user["age"] <= 65
        assert user["is_active"] is True
        assert user["role"] == "viewer"

    def test_user_with_subfactory_address(self):
        user = UserFactory()
        assert "address" in user
        addr = user["address"]
        assert "street" in addr
        assert "city" in addr
        assert "country" in addr

    def test_override_fields_at_creation(self):
        """Factory create karte time fields override karo."""
        admin = UserFactory(role="admin", age=30, is_active=False)
        assert admin["role"] == "admin"
        assert admin["age"] == 30
        assert admin["is_active"] is False

    def test_sequence_is_unique(self):
        """Sequence field har factory call pe alag value deta hai."""
        users = [UserFactory() for _ in range(5)]
        ids = [u["id"] for u in users]
        assert len(set(ids)) == 5  # sab unique

    def test_create_batch(self):
        """create_batch — ek saath multiple objects."""
        users = UserFactory.build_batch(10)
        assert len(users) == 10
        emails = [u["email"] for u in users]
        assert len(set(emails)) == 10  # unique emails

    def test_create_batch_with_override(self):
        """Batch mein sab ko same role dena."""
        admins = UserFactory.build_batch(5, role="admin")
        assert all(u["role"] == "admin" for u in admins)
        assert len(admins) == 5

    def test_order_with_user_subfactory(self):
        """Order automatically ek User create karta hai."""
        order = OrderFactory()
        assert "user" in order
        assert order["billing_email"] == order["user"]["email"]
        assert float(order["amount"]) >= 100

    def test_order_with_specific_user(self):
        """SubFactory override — apna user pass karo."""
        my_user = UserFactory(name="Specific User", email="specific@test.com")
        order = OrderFactory(user=my_user)
        assert order["user"]["name"] == "Specific User"
        assert order["billing_email"] == "specific@test.com"

    def test_product_sequence_and_slug(self):
        """Product ki SKU sequence aur auto-generated slug."""
        p1 = ProductFactory()
        p2 = ProductFactory()
        assert p1["sku"] != p2["sku"]
        assert p1["slug"] == p1["name"].lower().replace(" ", "-")

    def test_product_iterator(self):
        """Iterator strategy — predefined values cycle karta hai."""
        products = [ProductFactory() for _ in range(8)]
        categories = [p["category"] for p in products]
        valid = {"electronics", "clothing", "food", "books"}
        assert all(c in valid for c in categories)


# ── SECTION 7 ─────────────────────────────────────────────────────────────────
# Hypothesis — Property-Based Testing
# ──────────────────────────────────────────────────────────────────────────────

try:
    from hypothesis import assume, example, given, settings
    import hypothesis.strategies as st
    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False


# ── Functions to property-test ────────────────────────────────────────────────

def reverse_string(s: str) -> str:
    return s[::-1]


def sort_and_deduplicate(lst: list) -> list:
    return sorted(set(lst))


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Value ko min aur max ke beech mein rakh."""
    return max(min_val, min(max_val, value))


def encode_decode(data: str) -> str:
    """Simple base64 encode then decode — should be identity."""
    import base64
    encoded = base64.b64encode(data.encode("utf-8"))
    decoded = base64.b64decode(encoded).decode("utf-8")
    return decoded


@pytest.mark.skipif(not HYPOTHESIS_AVAILABLE, reason="hypothesis not installed")
class TestHypothesis:

    @given(st.text())
    def test_reverse_twice_is_identity(self, s):
        """Kisi bhi string ko do baar reverse karo — original milna chahiye."""
        assert reverse_string(reverse_string(s)) == s

    @given(st.lists(st.integers(), min_size=1))
    def test_sort_is_idempotent(self, lst):
        """Sort ek baar karo ya do baar — same result."""
        assert sorted(sorted(lst)) == sorted(lst)

    @given(st.lists(st.integers(), min_size=1))
    def test_sort_preserves_length_or_less(self, lst):
        """Sort ke baad elements kam ya equal hone chahiye (duplicates hate karein)."""
        sorted_lst = sorted(lst)
        assert len(sorted_lst) == len(lst)

    @given(st.lists(st.integers(), min_size=2))
    def test_sorted_order_property(self, lst):
        """Sorted list mein koi bhi element apne next se bada nahi hona chahiye."""
        result = sorted(lst)
        for i in range(len(result) - 1):
            assert result[i] <= result[i + 1]

    @given(st.integers(min_value=0), st.integers(min_value=1))
    def test_division_result_type(self, a, b):
        """a/b ka result float hona chahiye (b != 0 guaranteed by min_value=1)."""
        result = a / b
        assert isinstance(result, (int, float))

    @given(st.floats(min_value=-1e6, max_value=1e6, allow_nan=False),
           st.floats(min_value=-1e6, max_value=1e6, allow_nan=False),
           st.floats(min_value=-1e6, max_value=1e6, allow_nan=False))
    def test_clamp_within_bounds(self, value, min_val, max_val):
        """clamp ka result hamesha [min_val, max_val] ke andar hona chahiye."""
        assume(min_val <= max_val)  # invalid range skip karo
        result = clamp(value, min_val, max_val)
        assert min_val <= result <= max_val

    @given(st.floats(min_value=-1e6, max_value=1e6, allow_nan=False),
           st.floats(min_value=-1e6, max_value=1e6, allow_nan=False),
           st.floats(min_value=-1e6, max_value=1e6, allow_nan=False))
    def test_clamp_identity_when_in_range(self, value, min_val, max_val):
        """Value already in range hai toh clamp us value ko return kare."""
        assume(min_val <= max_val)
        # Value ko range mein force karo
        value_in_range = clamp(value, min_val, max_val)
        # Dubara clamp karne pe same result
        assert clamp(value_in_range, min_val, max_val) == value_in_range

    @given(st.text())
    @example("")             # hamesha empty string test karo
    @example("Hello World") # hamesha yeh test karo
    @example("unicode: こんにちは")  # unicode test
    def test_encode_decode_identity(self, s):
        """Encode then decode = original string."""
        assert encode_decode(s) == s

    @given(st.lists(st.integers()))
    @settings(max_examples=200)  # zyada examples try karo
    def test_deduplicate_has_unique_elements(self, lst):
        """sort_and_deduplicate ke result mein koi duplicate nahi hona chahiye."""
        result = sort_and_deduplicate(lst)
        assert len(result) == len(set(result))

    @given(st.text(min_size=1))
    def test_palindrome_property(self, s):
        """Double-reversed string palindrome check."""
        # s + reversed(s) hamesha palindrome hona chahiye
        combined = s + s[::-1]
        assert is_palindrome(combined)


# ── SECTION 8 ─────────────────────────────────────────────────────────────────
# Coverage Demo — Multiple branches ko cover karo
# ──────────────────────────────────────────────────────────────────────────────
#
# Run coverage:
#   pytest 01_pytest_advanced.py --cov=. --cov-report=term-missing -v
#
# Expected output (example):
#   Name                         Stmts   Miss  Cover
#   ------------------------------------------------
#   01_pytest_advanced.py          350      12    97%
#
# Branch coverage:
#   pytest 01_pytest_advanced.py --cov=. --cov-branch --cov-report=term-missing
# ──────────────────────────────────────────────────────────────────────────────


def calculate_shipping(
    weight_kg: float,
    destination: str,
    is_express: bool = False,
    is_member: bool = False,
) -> dict:
    """
    Shipping cost calculate karo.

    Multiple branches hain — coverage ke liye sab cover karne honge:
    1. weight negative
    2. domestic vs international
    3. express vs regular
    4. member discount
    5. free shipping threshold
    """
    if weight_kg <= 0:
        raise ValueError("Weight must be positive")

    if destination == "domestic":
        base_rate = 50.0
        per_kg = 10.0
    elif destination == "international":
        base_rate = 200.0
        per_kg = 50.0
    else:
        raise ValueError(f"Unknown destination: {destination}")

    cost = base_rate + (weight_kg * per_kg)

    if is_express:
        cost *= 1.5

    if is_member:
        cost *= 0.85  # 15% member discount

    # Free shipping for domestic orders > 1000
    if destination == "domestic" and cost > 1000 and not is_express:
        cost = 0.0

    return {
        "cost": round(cost, 2),
        "currency": "INR",
        "estimated_days": 1 if is_express else (3 if destination == "domestic" else 7),
    }


class TestCalculateShipping:
    """calculate_shipping ke sab branches cover karo."""

    def test_domestic_regular(self):
        result = calculate_shipping(2.0, "domestic")
        assert result["cost"] == 70.0  # 50 + 2*10
        assert result["estimated_days"] == 3

    def test_domestic_express(self):
        result = calculate_shipping(2.0, "domestic", is_express=True)
        assert result["cost"] == 105.0  # (50 + 20) * 1.5
        assert result["estimated_days"] == 1

    def test_international_regular(self):
        result = calculate_shipping(1.0, "international")
        assert result["cost"] == 250.0  # 200 + 1*50
        assert result["estimated_days"] == 7

    def test_member_discount(self):
        result = calculate_shipping(2.0, "domestic", is_member=True)
        expected = round(70.0 * 0.85, 2)  # 15% discount
        assert result["cost"] == expected

    def test_free_shipping_threshold(self):
        """Domestic order > 1000 aur not express — free shipping."""
        result = calculate_shipping(100.0, "domestic", is_express=False)
        # 50 + 100*10 = 1050 > 1000 → free
        assert result["cost"] == 0.0

    def test_express_no_free_shipping(self):
        """Express pe free shipping nahi milti."""
        result = calculate_shipping(100.0, "domestic", is_express=True)
        assert result["cost"] > 0.0

    def test_negative_weight_raises(self):
        with pytest.raises(ValueError, match="positive"):
            calculate_shipping(-1.0, "domestic")

    def test_zero_weight_raises(self):
        with pytest.raises(ValueError):
            calculate_shipping(0.0, "domestic")

    def test_unknown_destination_raises(self):
        with pytest.raises(ValueError, match="Unknown destination"):
            calculate_shipping(1.0, "mars")

    def test_member_international(self):
        """Member discount international pe bhi kaam karta hai."""
        result = calculate_shipping(2.0, "international", is_member=True)
        expected = round(300.0 * 0.85, 2)  # 200 + 2*50 = 300, then 15% off
        assert result["cost"] == expected


# ── SECTION 9 ─────────────────────────────────────────────────────────────────
# Markers + Slow Tests
# ──────────────────────────────────────────────────────────────────────────────
#
# Custom markers ko pytest.ini / pyproject.toml mein register karo:
#
#   [pytest]
#   markers =
#       slow: slow tests (deselect with '-m "not slow"')
#       integration: tests requiring external services
#       smoke: quick sanity checks
#
# Run commands:
#   pytest -m "not slow"                # slow tests skip
#   pytest -m "integration"             # sirf integration
#   pytest -m "smoke"                   # sanity check
#   pytest -m "not slow and not integration"  # fast tests only (CI)
# ──────────────────────────────────────────────────────────────────────────────


def compute_fibonacci(n: int) -> int:
    """Recursive Fibonacci (deliberately slow for large n)."""
    if n <= 1:
        return n
    return compute_fibonacci(n - 1) + compute_fibonacci(n - 2)


def bubble_sort(arr: list) -> list:
    """O(n²) sort — slow for large inputs."""
    arr = arr.copy()
    n = len(arr)
    for i in range(n):
        for j in range(n - i - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    return arr


@pytest.mark.slow
def test_fibonacci_large():
    """
    @pytest.mark.slow — CI mein skip karo: pytest -m "not slow"
    Yeh test slow hai kyunki recursive Fibonacci exponential hai.
    """
    result = compute_fibonacci(30)
    assert result == 832040


@pytest.mark.slow
def test_bubble_sort_large():
    """Large list bubble sort — slow test."""
    lst = list(range(500, 0, -1))  # 500 numbers in reverse
    result = bubble_sort(lst)
    assert result == list(range(1, 501))


@pytest.mark.integration
def test_real_world_integration():
    """
    @pytest.mark.integration — external services chahiye.
    Is test mein hum just verify karte hain ki marker kaam karta hai.
    Real integration test mein: DB, Redis, external API calls honge.
    """
    # Simulate: check environment variable
    env = os.environ.get("TESTING", "true")
    assert env in ("true", "false", "1", "0", None, "")


@pytest.mark.integration
def test_database_connection_integration():
    """
    Integration test: real SQLite connection (in-memory).
    pytest -m "not integration" se skip karo agar DB nahi chahiye.
    """
    import sqlite3
    conn = sqlite3.connect(":memory:")
    cursor = conn.execute("SELECT sqlite_version()")
    version = cursor.fetchone()[0]
    assert version  # version string exist karna chahiye
    conn.close()


@pytest.mark.skip(reason="Feature not implemented yet — planned for v2.0")
def test_future_feature_graphql():
    """
    @pytest.mark.skip — hamesha skip karta hai.
    Use karo: work in progress, planned features, broken environments.
    """
    # Yeh kabhi execute nahi hoga jab tak manually unskip na karo
    result = graphql_query("{ users { id name } }")
    assert result["data"]["users"] is not None


@pytest.mark.xfail(reason="Known bug: issue #456 — negative discount not handled", strict=False)
def test_negative_discount_known_bug():
    """
    @pytest.mark.xfail — expected failure.
    strict=False: XFAIL (expected fail) ya XPASS (unexpectedly passes) dono ok.
    strict=True: XPASS pe test FAIL hoga — useful jab bug fix confirm karna ho.
    """
    # Yeh bug hai: negative amount pe discount apply nahi hota correctly
    result = calculate_shipping(-0.001, "domestic")  # This will raise ValueError
    # Agar yahan pahunche toh test unexpectedly passed


@pytest.mark.xfail(raises=ValueError, strict=True)
def test_xfail_strict_exception():
    """
    strict=True + raises: specifically yeh exception expect karte hain.
    Agar exception nahi aayi — test FAIL hoga.
    """
    calculate_shipping(0, "domestic")  # ValueError expected


@pytest.mark.smoke
def test_basic_sanity_check():
    """
    @pytest.mark.smoke — post-deploy quick sanity.
    Run after deployment: pytest -m "smoke" --timeout=30
    """
    assert 1 + 1 == 2
    assert isinstance([], list)
    assert "python" in "python testing"


@pytest.mark.smoke
def test_imports_work():
    """Critical imports available hain."""
    import json
    import os
    import sys
    assert json
    assert os
    assert sys


# ── Parametrize + Markers Combination ──────────────────────────────────────────

@pytest.mark.parametrize("n, expected", [
    (0, 0),
    (1, 1),
    (5, 5),
    (10, 55),
    pytest.param(35, 9227465, marks=pytest.mark.slow, id="fib-35-slow"),
])
def test_fibonacci_parametrized(n, expected):
    """
    Normal cases fast hain, fib-35 slow — sirf woh marked hai.
    pytest -m "not slow" chalao — fib-35 skip hoga, baaki run karenge.
    """
    assert compute_fibonacci(n) == expected


# ── Final Integration Test ─────────────────────────────────────────────────────

class TestEndToEnd:
    """Multiple sections ke components saath test karo."""

    def test_factory_with_shipping(self):
        """Factory Boy se user banao, phir shipping calculate karo."""
        if not FACTORY_BOY_AVAILABLE:
            pytest.skip("factory-boy not installed")

        user = UserFactory(is_active=True)
        # User exist karta hai — shipping calculate karo
        order = OrderFactory(user=user)
        shipping = calculate_shipping(2.5, "domestic")

        assert user["is_active"] is True
        assert float(order["amount"]) >= 100
        assert shipping["cost"] > 0
        assert shipping["currency"] == "INR"

    def test_mock_combined_flow(self, mocker):
        """Mocking + async simulate karna."""
        mock_payment = Mock(return_value={"status": "success", "transaction_id": "txn_end_to_end"})

        with patch.object(PaymentGateway, "charge", mock_payment):
            gw = PaymentGateway()
            result = gw.charge(500.0, "tok_test")

        assert result["status"] == "success"
        mock_payment.assert_called_once_with(500.0, "tok_test")


# ──────────────────────────────────────────────────────────────────────────────
# Entry point — python 01_pytest_advanced.py se directly run karo
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Direct python run: pytest call karo
    pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "-m", "not slow",  # slow tests skip karo direct run mein
        "--no-header",
    ])
