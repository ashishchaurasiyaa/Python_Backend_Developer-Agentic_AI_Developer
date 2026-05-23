# pytest Advanced — Interview Prep (40 LPA Series)
### Hinglish Theory + Production Patterns

> **Convention**: Hindi explanation in normal text, English terms/code in `code blocks` or **bold**.
> Ye file ek complete reference hai — interview se pehle ek baar zaroor padho.

---

## TABLE OF CONTENTS

1. Testing Philosophy
2. pytest Basics Recap
3. Fixtures Deep Dive
4. @pytest.mark.parametrize
5. Mocking
6. pytest-asyncio
7. Factory Boy + Faker
8. Hypothesis (Property-Based Testing)
9. pytest-cov (Coverage)
10. FastAPI Testing
11. Database Testing
12. Test Organization
13. Interview Q&As (12 questions)

---

## 1. TESTING PHILOSOPHY

### 1.1 Test Pyramid — Kyun Zaroori Hai?

```
        /\
       /E2E\          ← Sabse kam, sabse slow, sabse costly
      /------\
     /  Integ  \      ← Middle ground
    /------------\
   /  Unit Tests  \   ← Sabse zyada, sabse fast, sabse cheap
  /________________\
```

**Unit Test**: Ek akela function ya class test karo. Baaki sab mock karo.
- Fast (milliseconds mein chalta hai)
- Isolated (doosre components pe depend nahi karta)
- Example: `test_calculate_discount()` — sirf discount logic test karo, DB nahi

**Integration Test**: Do ya zyada components ek saath test karo.
- Slow (seconds mein chalta hai)
- Example: `test_user_service_with_real_db()` — service + DB dono real

**E2E (End-to-End) Test**: Poora application test karo, user ki tarah.
- Sabse slow (minutes)
- Example: Selenium/Playwright se browser kholo, login karo, checkout karo

**Interview tip**: "Hum 70-20-10 rule follow karte hain — 70% unit, 20% integration, 10% E2E. Iska matlab CI pipeline fast rehta hai aur feedback loop quick hota hai."

---

### 1.2 TDD — Test Driven Development

**TDD cycle**: Red → Green → Refactor

```
RED     → Pehle test likho jo FAIL ho (feature abhi exist nahi karti)
GREEN   → Minimum code likho jo test PASS kare
REFACTOR → Code clean karo, tests abhi bhi green honay chahiye
```

**Practical example:**

```
Step 1 (RED):
    def test_add_numbers():
        assert add(2, 3) == 5  # add() abhi exist nahi — NameError!

Step 2 (GREEN):
    def add(a, b):
        return a + b  # minimum implementation

Step 3 (REFACTOR):
    def add(a: int, b: int) -> int:
        """Add two integers."""
        return a + b  # type hints add kiye, docstring add kiya
```

**TDD ke fayde**:
- Design better hoti hai (agar test likhna mushkil hai, design mein problem hai)
- Regression bugs nahi aate
- Documentation as code — test itself batata hai function kya karta hai

**TDD ke nuqsaan**:
- Initial speed slow lagti hai (but long term mein fast)
- UI/Frontend pe mushkil hota hai apply karna

---

### 1.3 BDD — Behavior Driven Development

**BDD** TDD ka extension hai jo **Given-When-Then** language use karta hai.

```gherkin
Feature: User Login

  Scenario: Successful login
    Given user "john@example.com" exists with password "secret123"
    When user submits login form with correct credentials
    Then user should be redirected to dashboard
    And user should see "Welcome, John" message
```

Python mein BDD ke liye **pytest-bdd** ya **behave** library use hoti hai.

**Interview mein bolna**: "BDD non-technical stakeholders ke saath communication ke liye useful hai. Product manager bhi test specification likh sakta hai."

---

## 2. PYTEST BASICS RECAP

### 2.1 Test Discovery Rules

pytest automatically yeh files dhundta hai:
- Files jo `test_*.py` ya `*_test.py` se match karti ho
- Functions jo `test_` se start ho
- Classes jo `Test` se start ho (with no `__init__`)

```bash
# Run karne ke tarike:
pytest                          # current directory mein sab
pytest tests/                   # specific folder
pytest tests/test_users.py      # specific file
pytest tests/test_users.py::test_create_user  # specific test
pytest -k "login or auth"       # naam se filter
pytest -v                       # verbose output
pytest -s                       # print() output dikhao (no capture)
pytest --lf                     # last failed tests hi run karo
pytest --ff                     # failed tests pehle run karo
```

### 2.2 assert — pytest ka Magic

Standard Python `assert` use karo — pytest isko **rewrite** karta hai better error messages ke liye:

```python
def test_user_name():
    user = {"name": "Alice", "age": 25}
    assert user["name"] == "Bob"
    # pytest output:
    # AssertionError: assert 'Alice' == 'Bob'
    #   - Alice
    #   + Bob
```

**Common assert patterns**:

```python
assert x == y                    # equality
assert x != y                    # inequality
assert x in collection           # membership
assert x not in collection
assert x is None
assert x is not None
assert isinstance(x, SomeClass)  # type check
assert len(lst) == 5
assert result > 0
assert "error" in response.text  # string containment

# Exception testing:
with pytest.raises(ValueError) as exc_info:
    some_function_that_raises()
assert "invalid input" in str(exc_info.value)

# Approximate equality (floating point):
assert result == pytest.approx(3.14, abs=0.01)
```

### 2.3 Markers Overview

```python
@pytest.mark.skip(reason="Not implemented yet")
@pytest.mark.skipif(sys.platform == "win32", reason="Linux only")
@pytest.mark.xfail(reason="Known bug #123")
@pytest.mark.slow        # custom marker
@pytest.mark.integration # custom marker
```

Custom markers ko `pytest.ini` mein register karo:
```ini
[pytest]
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: marks integration tests
```

---

## 3. FIXTURES DEEP DIVE

**Fixture kya hota hai?** — Woh setup code jo test se pehle run hota hai. Dependency injection ka pytest version.

```python
@pytest.fixture
def my_fixture():
    return {"key": "value"}

def test_something(my_fixture):  # pytest automatically inject karta hai
    assert my_fixture["key"] == "value"
```

---

### 3.1 Fixture Scope — Bahut Important!

**Scope** batata hai ki fixture kitni baar create/destroy hoga.

#### scope="function" (Default)

```python
@pytest.fixture(scope="function")
def fresh_db():
    db = create_test_db()
    yield db
    db.clear()  # har test ke baad cleanup
```

- Har test ke liye **naya instance** banta hai
- Har test ke baad **destroy** hota hai
- Use karo jab: test isolation chahiye, state share nahi karna

#### scope="class"

```python
@pytest.fixture(scope="class")
def shared_client():
    client = TestClient(app)
    yield client
    # class ke sab tests khatam hone ke baad destroy
```

- Ek `TestClass` ke sab tests ke liye **ek instance**
- Use karo jab: related tests ek shared resource use karein

#### scope="module"

```python
@pytest.fixture(scope="module")
def db_connection():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE users (id INT, name TEXT)")
    yield conn
    conn.close()  # module ke sab tests khatam hone pe
```

- Ek `.py` file ke sab tests ke liye **ek instance**
- Use karo jab: DB connection expensive ho aur har test isolate ho sake

#### scope="session"

```python
@pytest.fixture(scope="session")
def test_server():
    server = start_test_server()
    yield server
    server.shutdown()  # poori test session mein sirf ek baar
```

- **Poori pytest run** mein sirf ek baar create/destroy
- Use karo jab: startup bahut expensive ho (e.g., Docker container, test server)

**Scope hierarchy** (broad to narrow):
```
session > module > class > function
```

**Rule**: Broad scope fixture sirf broad/equal scope ki fixtures request kar sakti hai.

```python
# WRONG — session fixture, function scope fixture request kar raha hai
@pytest.fixture(scope="session")
def bad_fixture(fresh_user):  # fresh_user is function-scoped — ERROR!
    pass

# CORRECT
@pytest.fixture(scope="session")
def good_fixture(db_connection):  # db_connection bhi session-scoped
    pass
```

---

### 3.2 yield Fixtures — Setup + Teardown Ek Saath

Pehle `setUp` aur `tearDown` methods alag likhne padte the. `yield` se dono ek jagah:

```python
@pytest.fixture
def managed_file(tmp_path):
    # SETUP — yield se pehle
    filepath = tmp_path / "test.txt"
    filepath.write_text("Hello World")
    print(f"\n[SETUP] File created: {filepath}")
    
    yield filepath  # test ko yeh value milti hai
    
    # TEARDOWN — yield ke baad (test ke baad run hota hai)
    if filepath.exists():
        filepath.unlink()
    print(f"\n[TEARDOWN] File deleted: {filepath}")

def test_read_file(managed_file):
    content = managed_file.read_text()
    assert content == "Hello World"
    # test khatam hone ke baad teardown automatic run hoga
```

**Important**: Teardown **test fail hone pe bhi** run hota hai. Yahi `try/finally` jaisa behavior hai.

```python
@pytest.fixture
def db_transaction(db_connection):
    transaction = db_connection.begin()
    yield db_connection
    transaction.rollback()  # test pass ya fail, rollback hoga
```

---

### 3.3 autouse=True — Auto-Apply Without Requesting

Kuch fixtures hamesha chahiye hote hain — jaise timer, logging setup, etc.

```python
@pytest.fixture(autouse=True)
def reset_config():
    """Har test ke pehle config reset karo."""
    original = config.copy()
    yield
    config.clear()
    config.update(original)

# Ab kisi bhi test mein explicitly request nahi karna
def test_something():
    config["key"] = "modified"
    assert config["key"] == "modified"
# Test ke baad config automatically reset ho jayega
```

**Scope ke saath autouse**:

```python
@pytest.fixture(scope="module", autouse=True)
def setup_test_environment():
    """Module load hone pe environment variables set karo."""
    os.environ["TESTING"] = "true"
    yield
    del os.environ["TESTING"]
```

**Warning**: `autouse` carefully use karo — agar module-level autouse fixture module-wide state change kare, unexpected behavior ho sakta hai.

---

### 3.4 Fixture Dependencies — Fixture Requesting Another Fixture

Fixtures dusri fixtures pe depend kar sakti hain — pytest automatically resolve karta hai:

```python
@pytest.fixture(scope="session")
def db_engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()

@pytest.fixture(scope="function")
def db_session(db_engine):  # db_engine ko request kar raha hai
    with Session(db_engine) as session:
        yield session
        session.rollback()

@pytest.fixture
def existing_user(db_session):  # db_session ko request kar raha hai
    user = User(name="Test User", email="test@example.com")
    db_session.add(user)
    db_session.commit()
    return user

def test_get_user(existing_user, db_session):  # dono fixtures inject
    found = db_session.get(User, existing_user.id)
    assert found.name == "Test User"
```

pytest automatically:
1. `db_engine` create karega (session scope)
2. `db_session` create karega (function scope), `db_engine` pass karega
3. `existing_user` create karega, `db_session` pass karega
4. Test function ko `existing_user` aur `db_session` dono pass karega

---

### 3.5 conftest.py — Scope Visibility

`conftest.py` ek special pytest file hai — isme defined fixtures automatically available ho jaati hain us directory aur uski subdirectories mein.

**Directory structure:**

```
tests/
├── conftest.py              ← Root conftest (sab tests ke liye)
├── unit/
│   ├── conftest.py          ← Sirf unit/ ke tests ke liye
│   └── test_users.py
├── integration/
│   ├── conftest.py          ← Sirf integration/ ke tests ke liye
│   └── test_db.py
└── e2e/
    └── test_checkout.py
```

**Root conftest.py** (tests/conftest.py):
```python
import pytest

@pytest.fixture(scope="session")
def app_settings():
    return {"env": "test", "debug": True}

@pytest.fixture
def test_client(app_settings):
    # yeh fixture sab tests ke liye available
    from myapp import create_app
    app = create_app(app_settings)
    return TestClient(app)
```

**Unit conftest.py** (tests/unit/conftest.py):
```python
@pytest.fixture
def mock_db():
    # sirf tests/unit/ mein available
    return MockDatabase()
```

**Visibility rules:**
- `tests/conftest.py` ki fixtures → sab tests ke liye available
- `tests/unit/conftest.py` ki fixtures → sirf `tests/unit/` ke tests ke liye
- Agar same naam ki fixture dono mein ho → local (nearest) conftest win karti hai

---

### 3.6 Parametrize with Fixtures

```python
@pytest.fixture(params=["sqlite", "postgres"])
def database(request):
    db_type = request.param
    if db_type == "sqlite":
        db = SQLiteDB(":memory:")
    else:
        db = PostgresDB("test_db")
    yield db
    db.close()

def test_insert_user(database):
    # Yeh test dono databases pe run karega
    database.insert({"name": "Alice"})
    assert database.count() == 1
```

---

### 3.7 Fixture Factories — Return a Function

Jab ek hi test mein multiple instances chahiye, factory pattern use karo:

```python
@pytest.fixture
def make_user():
    """Factory fixture — caller decide karega values."""
    created_users = []
    
    def _make_user(name="Default", email=None, role="viewer"):
        if email is None:
            email = f"{name.lower()}@example.com"
        user = {"name": name, "email": email, "role": role}
        created_users.append(user)
        return user
    
    yield _make_user
    
    # Cleanup — sab created users delete karo
    for user in created_users:
        print(f"Cleaning up user: {user['email']}")

def test_user_permissions(make_user):
    admin = make_user(name="Admin", role="admin")
    viewer = make_user(name="Viewer", role="viewer")
    
    assert admin["role"] == "admin"
    assert viewer["role"] == "viewer"
    assert admin["name"] != viewer["name"]
```

---

## 4. @pytest.mark.parametrize

### 4.1 Basic Parametrize

```python
@pytest.mark.parametrize("input_val, expected", [
    (0, True),
    (1, False),
    (-1, False),
    (100, False),
    (None, False),  # edge case
])
def test_is_zero(input_val, expected):
    assert is_zero(input_val) == expected
```

### 4.2 Multiple Parameters

```python
@pytest.mark.parametrize("a, b, expected", [
    (3, 4, 5),        # 3² + 4² = 25 = 5²
    (5, 12, 13),
    (8, 15, 17),
    (0, 0, 0),        # edge case
])
def test_hypotenuse(a, b, expected):
    assert math.isclose(hypotenuse(a, b), expected, rel_tol=1e-9)
```

### 4.3 pytest.param with Marks — Specific Cases Skip/XFail Karo

```python
@pytest.mark.parametrize("email, is_valid", [
    ("user@example.com", True),
    ("invalid-email", False),
    ("user@domain.co.in", True),
    pytest.param(
        "unicode@münchen.de",
        True,
        marks=pytest.mark.skip(reason="Unicode emails not yet supported"),
    ),
    pytest.param(
        "sql'; DROP TABLE users; --@evil.com",
        False,
        marks=pytest.mark.xfail(reason="SQL injection in email not handled"),
    ),
])
def test_email_validation(email, is_valid):
    assert validate_email(email) == is_valid
```

### 4.4 IDs for Readable Output

```python
@pytest.mark.parametrize("role, can_delete", [
    ("admin", True),
    ("moderator", False),
    ("viewer", False),
], ids=["admin-can-delete", "moderator-cannot", "viewer-cannot"])
def test_delete_permission(role, can_delete):
    user = {"role": role}
    assert check_delete_permission(user) == can_delete

# pytest output mein:
# test_delete_permission[admin-can-delete] PASSED
# test_delete_permission[moderator-cannot] PASSED
# test_delete_permission[viewer-cannot] PASSED
```

### 4.5 Indirect Parametrize — Fixture Ko Values Pass Karo

```python
@pytest.fixture
def user_with_role(request):
    """request.param se role milega."""
    role = request.param
    return create_test_user(role=role)

@pytest.mark.parametrize("user_with_role", ["admin", "viewer"], indirect=True)
def test_user_dashboard(user_with_role):
    response = client.get(f"/dashboard", headers=auth_header(user_with_role))
    assert response.status_code == 200
```

### 4.6 Combining Multiple Parametrize Decorators

```python
@pytest.mark.parametrize("status", ["active", "inactive"])
@pytest.mark.parametrize("role", ["admin", "viewer"])
def test_user_combinations(role, status):
    # 4 test cases: admin+active, admin+inactive, viewer+active, viewer+inactive
    user = create_user(role=role, status=status)
    assert user["role"] == role
    assert user["status"] == status
```

---

## 5. MOCKING

**Mock kya hota hai?** — Real dependency ko fake se replace karna taaki:
1. External services pe depend na karo (DB, API, file system)
2. Tests fast aur predictable ho
3. Edge cases (network timeout, DB error) simulate karo

### 5.1 Mock vs MagicMock vs Stub vs Spy

```
Mock        → Blank object jisme koi behavior nahi
MagicMock   → Mock + magic methods (__len__, __iter__, __enter__, etc.) support
Stub        → Hardcoded return value deta hai, interactions track nahi karta
Spy         → Real function call karta hai, lekin calls track karta hai
```

### 5.2 Basic Mock Usage

```python
from unittest.mock import Mock, MagicMock, patch, call

# Simple Mock
mock_func = Mock(return_value=42)
result = mock_func(1, 2, key="value")

assert result == 42
assert mock_func.called             # called? haan
assert mock_func.call_count == 1    # kitni baar
mock_func.assert_called_once_with(1, 2, key="value")
mock_func.assert_called_with(1, 2, key="value")

# Side effect — list se cycle karo
mock_api = Mock(side_effect=[100, 200, 300])
assert mock_api() == 100
assert mock_api() == 200
assert mock_api() == 300
# 4th call pe StopIteration exception

# Side effect — exception raise karo
mock_db = Mock(side_effect=ConnectionError("DB down"))
with pytest.raises(ConnectionError):
    mock_db.query("SELECT 1")
```

### 5.3 return_value vs side_effect

```python
# return_value: hamesha same value return karo
mock = Mock(return_value="hello")
assert mock() == "hello"
assert mock() == "hello"  # same

# side_effect: dynamic behavior
# 1. List: ek ek karke return karo
mock = Mock(side_effect=["first", "second", Exception("fail")])

# 2. Function: har call pe function call karo
def dynamic_response(n):
    return n * 2
mock = Mock(side_effect=dynamic_response)
assert mock(5) == 10
assert mock(3) == 6

# 3. Exception class/instance: raise karo
mock = Mock(side_effect=ValueError("invalid"))
with pytest.raises(ValueError):
    mock()
```

### 5.4 patch — Module Level Mocking

```python
# patch as context manager
def test_with_patch_context():
    with patch("mymodule.requests.get") as mock_get:
        mock_get.return_value.json.return_value = {"status": "ok"}
        result = fetch_data("https://api.example.com")
        assert result == {"status": "ok"}
        mock_get.assert_called_once_with("https://api.example.com")

# patch as decorator
@patch("mymodule.send_email")
@patch("mymodule.database.save")
def test_create_user(mock_save, mock_email):  # reverse order!
    mock_save.return_value = {"id": 1}
    create_user("alice@example.com")
    mock_save.assert_called_once()
    mock_email.assert_called_once_with("alice@example.com", "Welcome!")

# patch.object — specific object ke method ko mock karo
from mymodule import UserService

def test_user_service():
    service = UserService()
    with patch.object(service, "get_user", return_value={"id": 1, "name": "Alice"}):
        result = service.get_user(1)
        assert result["name"] == "Alice"

# patch.dict — dictionary patch karo
import os
with patch.dict(os.environ, {"DATABASE_URL": "sqlite:///:memory:"}):
    assert os.environ["DATABASE_URL"] == "sqlite:///:memory:"
```

### 5.5 AsyncMock — Async Functions Ka Mock

```python
from unittest.mock import AsyncMock
import asyncio

# Regular Mock async function ke liye kaam nahi karta
# AsyncMock use karo

async def fetch_user_from_api(user_id: int) -> dict:
    """Real function jo HTTP call karti hai."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"/users/{user_id}")
        return response.json()

async def get_user_display_name(user_id: int) -> str:
    user = await fetch_user_from_api(user_id)
    return f"{user['first']} {user['last']}"

# Test:
@pytest.mark.asyncio
async def test_get_display_name():
    mock_fetch = AsyncMock(return_value={"first": "John", "last": "Doe"})
    
    with patch("mymodule.fetch_user_from_api", mock_fetch):
        name = await get_user_display_name(123)
    
    assert name == "John Doe"
    mock_fetch.assert_awaited_once_with(123)
    # Note: assert_awaited_once_with — called ki jagah awaited
```

### 5.6 pytest-mock — mocker Fixture

```python
# pytest-mock install: pip install pytest-mock

def test_with_mocker(mocker):
    # mocker.patch — automatically cleanup karta hai test ke baad
    mock_get = mocker.patch("requests.get")
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {"data": [1, 2, 3]}
    
    result = fetch_data()
    assert result == [1, 2, 3]

# mocker.spy — real function call + track
def add(a, b):
    return a + b

def test_spy(mocker):
    spy = mocker.spy(math_module, "add")
    
    result = math_module.add(2, 3)
    
    assert result == 5  # real function call hua
    spy.assert_called_once_with(2, 3)
    assert spy.call_count == 1
```

### 5.7 Mocking Context Managers

```python
from unittest.mock import MagicMock, patch

def read_config_file(path):
    with open(path) as f:
        return json.load(f)

def test_read_config(mocker):
    mock_file_content = '{"debug": true, "port": 8080}'
    mock_open = mocker.mock_open(read_data=mock_file_content)
    mocker.patch("builtins.open", mock_open)
    
    config = read_config_file("config.json")
    
    assert config["debug"] is True
    assert config["port"] == 8080

# Context manager manually mock karna:
def test_context_manager():
    mock_cm = MagicMock()
    mock_cm.__enter__.return_value = mock_cm
    mock_cm.__exit__.return_value = False
    
    with patch("mymodule.SomeContextManager", return_value=mock_cm):
        result = function_using_context_manager()
```

### 5.8 Mocking datetime.now()

```python
from unittest.mock import patch
from datetime import datetime, date

def get_greeting():
    hour = datetime.now().hour
    if hour < 12:
        return "Good Morning"
    elif hour < 17:
        return "Good Afternoon"
    else:
        return "Good Evening"

def test_morning_greeting():
    mock_now = datetime(2024, 1, 15, 9, 30, 0)  # 9:30 AM
    
    with patch("mymodule.datetime") as mock_dt:
        mock_dt.now.return_value = mock_now
        assert get_greeting() == "Good Morning"

def test_evening_greeting():
    mock_now = datetime(2024, 1, 15, 19, 0, 0)  # 7 PM
    
    with patch("mymodule.datetime") as mock_dt:
        mock_dt.now.return_value = mock_now
        assert get_greeting() == "Good Evening"
```

### 5.9 Mocking HTTP Calls — respx aur responses

```python
# httpx ke liye respx:
import httpx
import respx
import pytest

@respx.mock
def test_fetch_user_with_respx():
    respx.get("https://api.example.com/users/1").mock(
        return_value=httpx.Response(200, json={"id": 1, "name": "Alice"})
    )
    
    client = httpx.Client()
    response = client.get("https://api.example.com/users/1")
    assert response.json()["name"] == "Alice"

# requests library ke liye responses:
import responses
import requests

@responses.activate
def test_fetch_with_responses():
    responses.add(
        responses.GET,
        "https://api.example.com/users/1",
        json={"id": 1, "name": "Bob"},
        status=200
    )
    
    resp = requests.get("https://api.example.com/users/1")
    assert resp.json()["name"] == "Bob"
```

---

## 6. PYTEST-ASYNCIO

### 6.1 Basic Async Test

```python
# Install: pip install pytest-asyncio

import pytest
import asyncio

@pytest.mark.asyncio
async def test_async_function():
    result = await some_async_function()
    assert result == expected_value
```

### 6.2 asyncio_mode = "auto" in pytest.ini

Baar baar `@pytest.mark.asyncio` likhna tedious hai. `auto` mode enable karo:

```ini
# pytest.ini
[pytest]
asyncio_mode = auto
```

Ya `pyproject.toml` mein:
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

Ab sirf `async def test_...` likho — decorator ki zarurat nahi.

### 6.3 Async Fixtures

```python
@pytest.fixture
async def async_db():
    """Async DB connection fixture."""
    db = await create_async_db_connection()
    yield db
    await db.close()

@pytest.fixture
async def async_user(async_db):
    user = await async_db.create_user(name="Test", email="test@example.com")
    yield user
    await async_db.delete_user(user.id)

async def test_user_creation(async_user):
    assert async_user.name == "Test"
    assert "@" in async_user.email
```

### 6.4 event_loop Scope — Session-Level Event Loop

```python
# Default: function scope event loop (new event loop per test)
# Production mein session scope prefer karo:

@pytest.fixture(scope="session")
def event_loop():
    """Session-scoped event loop."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
```

**Note**: pytest-asyncio 0.21+ mein `event_loop` fixture override deprecated hai. 
New way:
```python
# pytest.ini
[pytest]
asyncio_mode = auto

# Ya fixture pe scope specify karo:
@pytest.fixture(scope="session")
async def db_pool():
    pool = await create_pool()
    yield pool
    await pool.close()
```

### 6.5 Testing FastAPI with AsyncClient

```python
from httpx import AsyncClient, ASGITransport
from myapp.main import app

@pytest.fixture
async def async_client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client

async def test_get_users(async_client):
    response = await async_client.get("/users")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

async def test_create_user(async_client):
    payload = {"name": "Alice", "email": "alice@example.com"}
    response = await async_client.post("/users", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Alice"
```

---

## 7. FACTORY BOY + FAKER

### 7.1 Kya Hai Aur Kyun Use Karo?

**Factory Boy** se test data create karna easy hota hai — boring boilerplate nahi likhna.

```python
# Without factory_boy (tedious):
user = User(
    name="Test User",
    email="test@example.com",
    age=25,
    is_active=True,
    created_at=datetime.now(),
    # 10 aur fields...
)

# With factory_boy (simple):
user = UserFactory()
admin = UserFactory(role="admin")  # sirf jo chahiye override karo
```

### 7.2 Factory Types

```python
import factory
from faker import Faker

fake = Faker()

# Basic Factory (non-ORM)
class UserFactory(factory.Factory):
    class Meta:
        model = dict  # ya User class
    
    name = factory.Faker("name")
    email = factory.Sequence(lambda n: f"user{n}@test.com")
    age = factory.LazyFunction(lambda: random.randint(18, 65))
    is_active = True

# Django Model Factory
class UserDjangoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "auth.User"
    
    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    password = factory.PostGenerationMethodCall("set_password", "password123")
```

### 7.3 SubFactory — Related Objects

```python
class AddressFactory(factory.Factory):
    class Meta:
        model = dict
    
    street = factory.Faker("street_address")
    city = factory.Faker("city")
    country = factory.Faker("country_code")

class UserFactory(factory.Factory):
    class Meta:
        model = dict
    
    name = factory.Faker("name")
    email = factory.Sequence(lambda n: f"user{n}@example.com")
    address = factory.SubFactory(AddressFactory)  # nested object

# Usage:
user = UserFactory()
assert "street" in user["address"]
assert "city" in user["address"]

# Override nested:
user = UserFactory(address__city="Mumbai")
```

### 7.4 LazyAttribute aur Sequence

```python
class ProductFactory(factory.Factory):
    class Meta:
        model = dict
    
    # Sequence: incrementing number
    sku = factory.Sequence(lambda n: f"SKU-{n:04d}")  # SKU-0001, SKU-0002...
    
    # LazyAttribute: dusre fields pe depend karo
    name = factory.Faker("word")
    slug = factory.LazyAttribute(lambda o: o.name.lower().replace(" ", "-"))
    
    # LazyFunction: callable se value
    created_at = factory.LazyFunction(datetime.now)
    
    # Faker directly
    price = factory.Faker("pydecimal", min_value=10, max_value=9999, right_digits=2)
    description = factory.Faker("paragraph")
```

### 7.5 create_batch — Multiple Objects

```python
# Ek object
user = UserFactory()

# 10 objects
users = UserFactory.build_batch(10)

# Override with batch
admins = UserFactory.build_batch(5, role="admin")

# Pytest mein use karo:
@pytest.fixture
def many_users():
    return UserFactory.build_batch(20)

def test_pagination(many_users):
    assert len(many_users) == 20
    page_1 = many_users[:10]
    assert len(page_1) == 10
```

---

## 8. HYPOTHESIS — PROPERTY-BASED TESTING

### 8.1 Kya Hota Hai?

Traditional testing mein hum specific inputs likhte hain. Hypothesis **automatically** interesting inputs generate karta hai — edge cases jo hum sochte bhi nahi.

```python
# Traditional: hum inputs specify karte hain
@pytest.mark.parametrize("n", [0, 1, -1, 100, -100])
def test_abs_manual(n):
    assert abs(n) >= 0

# Hypothesis: library inputs generate karti hai
from hypothesis import given
import hypothesis.strategies as st

@given(st.integers())
def test_abs_hypothesis(n):
    assert abs(n) >= 0
    # Hypothesis 100 random integers try karega
    # Automatically 0, negative numbers, MAX_INT bhi try karega
```

### 8.2 Common Strategies

```python
import hypothesis.strategies as st

st.integers()                          # koi bhi int
st.integers(min_value=0, max_value=100)
st.floats()
st.floats(allow_nan=False, allow_infinity=False)
st.text()                              # koi bhi string (Unicode bhi!)
st.text(alphabet=st.characters(whitelist_categories=("L",)))  # sirf letters
st.booleans()
st.lists(st.integers())                # integers ki list
st.lists(st.text(), min_size=1, max_size=10)
st.dictionaries(st.text(), st.integers())
st.tuples(st.integers(), st.text())
st.one_of(st.integers(), st.text())    # either type
st.emails()                            # valid email addresses
st.datetimes()
st.none()
st.just(42)                            # fixed value
```

### 8.3 @settings — Control Hypothesis Behavior

```python
from hypothesis import given, settings, HealthCheck

@given(st.lists(st.integers(), min_size=1))
@settings(
    max_examples=500,        # zyada examples try karo (default 100)
    deadline=None,           # slow tests ke liye timeout disable
    suppress_health_check=[HealthCheck.too_slow],
)
def test_sorting_property(lst):
    sorted_lst = sorted(lst)
    assert len(sorted_lst) == len(lst)
    assert sorted_lst == sorted(lst)  # idempotent
```

### 8.4 assume() — Invalid Inputs Filter Karo

```python
from hypothesis import given, assume
import hypothesis.strategies as st

@given(st.integers(), st.integers())
def test_division(a, b):
    assume(b != 0)  # b=0 wale cases skip karo
    result = a / b
    # check properties
    assert (result * b) == pytest.approx(a, rel=1e-9)
```

**Note**: `assume()` use karo agar bahut kam cases skip hote hain. Zyada `assume()` se Hypothesis slow ho jaata hai.

### 8.5 @example() — Always Run Specific Cases

```python
from hypothesis import given, example
import hypothesis.strategies as st

@given(st.integers())
@example(0)       # hamesha 0 try karo
@example(-1)      # hamesha -1 try karo
@example(2**63)   # large number
def test_to_string(n):
    result = str(n)
    assert result.lstrip("-").isdigit()
```

### 8.6 Finding Real Bugs with Hypothesis

```python
# Yeh function mein bug hai:
def safe_divide_list(numbers, divisor):
    return [n / divisor for n in numbers]

@given(
    st.lists(st.floats(allow_nan=False)),
    st.floats(allow_nan=False)
)
def test_safe_divide_list(numbers, divisor):
    assume(divisor != 0.0)
    result = safe_divide_list(numbers, divisor)
    assert len(result) == len(numbers)
    # Hypothesis will find: infinity/infinity = nan, even when divisor != 0
    # Yeh edge case hum manually nahi socha tha!
```

---

## 9. PYTEST-COV (COVERAGE)

### 9.1 Basic Coverage Run

```bash
# Install:
pip install pytest-cov

# Basic run:
pytest --cov=myapp tests/

# HTML report (browser mein dekho):
pytest --cov=myapp --cov-report=html tests/
# htmlcov/index.html open karo

# Terminal mein bhi show karo:
pytest --cov=myapp --cov-report=term-missing tests/

# Output:
# Name                    Stmts   Miss  Cover
# -------------------------------------------
# myapp/models.py            45      5    89%
# myapp/services.py          78      2    97%
# myapp/utils.py             23      0   100%
# -------------------------------------------
# TOTAL                     146      7    95%
```

### 9.2 Branch Coverage

Line coverage sirf batata hai ki line execute hui ya nahi. Branch coverage **if/else** ke dono paths check karta hai.

```python
def classify_age(age):
    if age < 18:         # Branch A: True aur False
        return "minor"
    elif age < 65:       # Branch B: True aur False
        return "adult"
    else:
        return "senior"
```

```bash
pytest --cov=myapp --cov-branch tests/
# Branch coverage line coverage se hamesha kam ya equal hoga
```

### 9.3 .coveragerc Configuration

```ini
# .coveragerc file in root

[run]
source = myapp
branch = True
omit =
    */migrations/*
    */tests/*
    */__main__.py
    */settings*.py

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise NotImplementedError
    if __name__ == .__main__.:
    pass

[html]
directory = htmlcov
```

### 9.4 Coverage Threshold — CI Mein Use Karo

```bash
# CI pipeline mein fail karo agar coverage 80% se kam ho:
pytest --cov=myapp --cov-fail-under=80 tests/

# Sirf specific module check karo:
pytest --cov=myapp.services --cov-fail-under=90 tests/
```

### 9.5 # pragma: no cover

Kuch code cover karna zaruri nahi:

```python
def debug_print(msg):  # pragma: no cover
    print(f"DEBUG: {msg}")

if __name__ == "__main__":  # pragma: no cover
    run_server()
```

---

## 10. FASTAPI TESTING

### 10.1 TestClient — Sync Testing

```python
from fastapi import FastAPI, Depends, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

app = FastAPI()

class UserCreate(BaseModel):
    name: str
    email: str

fake_db = {}

def get_db():
    return fake_db

@app.get("/users/{user_id}")
async def get_user(user_id: int, db=Depends(get_db)):
    if user_id not in db:
        raise HTTPException(status_code=404, detail="User not found")
    return db[user_id]

@app.post("/users", status_code=201)
async def create_user(user: UserCreate, db=Depends(get_db)):
    user_id = len(db) + 1
    db[user_id] = {"id": user_id, **user.dict()}
    return db[user_id]

# Tests:
client = TestClient(app)

def test_create_user():
    response = client.post("/users", json={"name": "Alice", "email": "a@b.com"})
    assert response.status_code == 201
    assert response.json()["name"] == "Alice"

def test_get_user_not_found():
    response = client.get("/users/9999")
    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"
```

### 10.2 Dependency Override — Core Pattern

```python
# Production mein real DB use hoga, test mein fake DB

# Override karo:
def get_fake_db():
    return {"1": {"id": 1, "name": "TestUser"}}

def test_with_overridden_db():
    app.dependency_overrides[get_db] = get_fake_db
    
    try:
        response = client.get("/users/1")
        assert response.status_code == 200
        assert response.json()["name"] == "TestUser"
    finally:
        app.dependency_overrides.clear()  # cleanup!

# Better: fixture use karo
@pytest.fixture
def client_with_fake_db():
    app.dependency_overrides[get_db] = lambda: {"1": {"id": 1, "name": "TestUser"}}
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

### 10.3 Auth Testing

```python
from fastapi import Security
from fastapi.security import HTTPBearer

def get_current_user(token: str = Security(HTTPBearer())):
    # Real JWT validation
    payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    return payload

@app.get("/protected")
async def protected_route(user=Depends(get_current_user)):
    return {"message": f"Hello {user['name']}"}

# Test mein auth mock karo:
def test_protected_route():
    mock_user = {"id": 1, "name": "Alice", "role": "admin"}
    app.dependency_overrides[get_current_user] = lambda: mock_user
    
    response = client.get("/protected")
    assert response.status_code == 200
    assert "Alice" in response.json()["message"]
    
    app.dependency_overrides.clear()
```

---

## 11. DATABASE TESTING

### 11.1 SQLite In-Memory — Fast Unit Tests

```python
import sqlite3
import pytest

@pytest.fixture(scope="module")
def in_memory_db():
    """SQLite in-memory DB — module scope mein create, module end pe destroy."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    
    # Schema create karo
    conn.executescript("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            amount REAL NOT NULL
        );
    """)
    conn.commit()
    
    yield conn
    conn.close()

@pytest.fixture(autouse=True)
def cleanup_db(in_memory_db):
    """Har test ke baad tables clear karo."""
    yield
    in_memory_db.execute("DELETE FROM orders")
    in_memory_db.execute("DELETE FROM users")
    in_memory_db.commit()
```

### 11.2 SQLAlchemy with Test Transactions

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

@pytest.fixture(scope="session")
def engine():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)

@pytest.fixture
def db_session(engine):
    """Har test ke liye new transaction, rollback at end — no pollution."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()  # test ke sab changes undo!
    connection.close()
```

### 11.3 Alembic Migrations in Test DB

```python
# conftest.py
from alembic.config import Config
from alembic import command

@pytest.fixture(scope="session", autouse=True)
def run_migrations():
    """Test DB pe sab migrations apply karo."""
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", "sqlite:///:memory:")
    command.upgrade(alembic_cfg, "head")
    yield
    command.downgrade(alembic_cfg, "base")
```

---

## 12. TEST ORGANIZATION

### 12.1 File Naming Conventions

```
tests/
├── conftest.py
├── unit/
│   ├── conftest.py
│   ├── test_models.py       # Model tests
│   ├── test_services.py     # Service layer tests
│   ├── test_utils.py        # Utility function tests
│   └── test_validators.py
├── integration/
│   ├── conftest.py
│   ├── test_user_flow.py    # Multi-component tests
│   └── test_db_queries.py
└── e2e/
    ├── test_checkout.py
    └── test_login.py
```

### 12.2 Test Classes vs Functions

```python
# Functions: simple, isolated tests ke liye
def test_add_numbers():
    assert add(1, 2) == 3

# Classes: related tests group karne ke liye
class TestUserService:
    """User service ke sab tests ek jagah."""
    
    def test_create_user_success(self, db_session):
        ...
    
    def test_create_user_duplicate_email(self, db_session):
        ...
    
    def test_get_user_by_id(self, db_session, existing_user):
        ...
    
    class TestUserPermissions:
        """Nested class — permissions ke specific tests."""
        
        def test_admin_can_delete(self):
            ...
        
        def test_viewer_cannot_delete(self):
            ...
```

### 12.3 pyproject.toml Configuration

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py", "*_test.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
asyncio_mode = "auto"
addopts = [
    "-v",
    "--tb=short",
    "--strict-markers",
    "--cov=myapp",
    "--cov-report=term-missing",
]
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "integration: integration tests requiring external services",
    "e2e: end-to-end browser tests",
    "smoke: quick sanity check tests",
]

[tool.coverage.run]
branch = true
source = ["myapp"]
omit = ["*/migrations/*", "*/tests/*"]

[tool.coverage.report]
fail_under = 80
show_missing = true
```

### 12.4 CI Mein Markers Use Karo

```bash
# Fast unit tests only (CI PR check):
pytest -m "not slow and not integration and not e2e"

# Integration tests (CI nightly):
pytest -m "integration"

# Everything (pre-release):
pytest

# Smoke tests (post-deploy):
pytest -m "smoke" --timeout=30
```

---

## 13. INTERVIEW Q&As

### Q1: fixture scope ka difference kya hai? Real example do.

**Answer:**

```
function (default): Har test ke liye naya instance. Use karo jab test isolation chahiye.
                   Example: db_session jisme har test apna rollback kare.

class:             Ek TestClass ke sab tests share karte hain.
                   Example: TestClient jo class ke sab tests use karen.

module:            Ek .py file ke sab tests share karte hain.
                   Example: DB connection jo module load hone pe create ho.

session:           Poori pytest run mein sirf ek baar.
                   Example: Docker container start karna, external server launch.
```

**Rule**: Broad scope fixture narrow scope fixture request nahi kar sakti.

---

### Q2: Mock vs Stub vs Spy — difference kya hai?

```
Mock:  Behavior track karta hai + configurable return values.
       assert_called_with(), call_count, etc. check kar sakte ho.
       
Stub:  Sirf hardcoded return value. Calls track nahi karta.
       Example: def get_user_stub(id): return {"id": id, "name": "Test"}
       
Spy:   Real function call karta hai, lekin calls track karta hai.
       mocker.spy() use karta hai. Real code chalta hai + verify kar sakte ho.
```

---

### Q3: AsyncMock kyun chahiye? Regular Mock kaam kyun nahi karta?

Regular `Mock()` ek synchronous object return karta hai. Jab `await mock_func()` karo, Python expect karta hai ki return value **awaitable** ho. Regular Mock ka return value awaitable nahi hota — `TypeError: object MagicMock can't be used in 'await' expression`.

`AsyncMock` ek coroutine return karta hai jo `await` ho sakti hai.

---

### Q4: Property-based testing (Hypothesis) ka kya faida hai?

Hum sirf woh cases test karte hain jo hum sochte hain. Hypothesis automatically **edge cases** generate karta hai jo hum nahi sochte:
- Empty strings, None values
- Very large numbers (overflow)
- Unicode characters
- Empty lists, single-element lists
- Negative numbers

Real example: `sorted()` function test karne ke liye Hypothesis automatically try karta hai `[2^63, -2^63, 0]` — yeh hum manually nahi likhte.

---

### Q5: 100% code coverage ka matlab hai test suite perfect hai?

**Nahi.** Coverage sirf batata hai ki code execute hua — yeh nahi batata ki behavior correct hai.

```python
def add(a, b):
    return a - b  # Bug: minus instead of plus!

def test_add_with_coverage():
    result = add(1, 2)  # Line execute hogi — 100% coverage!
    # assert missing hai!
```

Coverage ek **minimum bar** hai, guarantee nahi. Better metric: mutation testing (mutmut library).

---

### Q6: Unit test kab likhna chahiye aur integration test kab?

```
Unit test: Business logic, pure functions, data transformations, validators.
           Fast feedback, cheap to run, test in isolation.
           
Integration test: DB queries, external API calls, cache behavior,
                  multiple services ka interaction.
                  Slower, but verify karta hai components kaam karte hain saath.

Rule of thumb: Agar test likhne ke liye sirf ek class/function mock karna pare
               aur baaki sab real ho — integration test hai.
```

---

### Q7: Factory Boy vs pytest fixtures — kab kya use karo?

```
Fixtures:      Shared infrastructure setup ke liye — DB connection,
               test client, config. One-time setup jisko tests share karein.
               
Factory Boy:   Domain objects (User, Order, Product) create karne ke liye.
               Har test alag data chahiye jab. Readable aur flexible.
               
Best practice: Fixture + Factory Boy saath use karo:
               fixture → DB session setup karo
               factory → us session mein User, Order create karo
```

---

### Q8: conftest.py visibility rules explain karo.

```
tests/conftest.py           → sab tests ke liye visible
tests/unit/conftest.py      → sirf tests/unit/ ke liye
tests/integration/conftest.py → sirf tests/integration/ ke liye

Nearest conftest wins agar same naam ki fixture ho (local override).

Plugin conftest.py (root ya src/conftest.py) bhi kaam karta hai.
pytest conftest.py ko automatically load karta hai — import nahi karna.
```

---

### Q9: parametrize vs fixture — kab kya use karo?

```
parametrize:   Same test logic, alag-alag input values test karo.
               Example: validate_email() ko 10 emails ke saath test karo.
               
fixture:       Setup/teardown logic, shared resources, complex objects.
               Example: DB session, HTTP client, config object.
               
Combination:   Complex scenarios mein dono saath use karo.
               fixture provides infrastructure, parametrize provides data.
```

---

### Q10: yield fixture mein teardown order kya hota hai?

LIFO order (Last In, First Out) — jis order mein fixtures request hue, teardown ulta hota hai.

```python
# Agar test request kare: fixture_a, fixture_b, fixture_c
# Setup order:    fixture_a setup → fixture_b setup → fixture_c setup → TEST
# Teardown order: fixture_c teardown → fixture_b teardown → fixture_a teardown
```

---

### Q11: autouse fixture ka kya danger hai?

```
1. Hidden behavior: Test dekhne se pata nahi chalta ki autouse fixture kya kar rahi hai.
                    Debugging mushkil ho jata hai.

2. Unintended side effects: Module-scoped autouse fixture global state change kar sakti hai
                             tests ke beech — unexpected failures.

3. Performance: Agar expensive autouse fixture function-scoped hai, hर test slow hoga.

Best practice: autouse sirf clearly needed cases mein use karo — timing, logging.
               Infrastructure fixtures always explicitly request karwao.
```

---

### Q12: TDD mein pehle test fail kyun hona chahiye (RED step)?

1. **Verify test works**: Agar pehle se pass hai, test galat hai ya feature already exist karti hai.
2. **Clear specification**: Failing test clearly define karta hai expected behavior.
3. **No false positives**: Agar test always pass kare, koi guarantee nahi ki feature actually test ho rahi hai.

```python
# RED step mein:
def test_new_feature():
    assert new_feature() == expected  # NameError: new_feature not defined
    
# Agar yeh test PASS ho jaata hai bina code likhe — kuch galat hai!
```

---

## QUICK REFERENCE CHEATSHEET

```bash
# Run commands
pytest                                 # sab tests
pytest -v                             # verbose
pytest -k "user or auth"              # filter by name
pytest -m "not slow"                  # skip slow tests
pytest --lf                           # last failed
pytest -x                             # first failure pe stop
pytest -s                             # show print output
pytest --tb=short                     # short traceback
pytest --cov=app --cov-report=html    # with coverage
pytest -n auto                        # parallel (pytest-xdist)

# Install commands
pip install pytest pytest-asyncio pytest-mock pytest-cov
pip install factory-boy faker hypothesis
pip install respx responses httpx fastapi
```

```python
# Fixture scopes
@pytest.fixture(scope="function")  # default, per test
@pytest.fixture(scope="class")     # per test class
@pytest.fixture(scope="module")    # per file
@pytest.fixture(scope="session")   # entire run

# Markers
@pytest.mark.parametrize("x,y", [(1,2), (3,4)])
@pytest.mark.skip(reason="...")
@pytest.mark.skipif(condition, reason="...")
@pytest.mark.xfail(reason="...")
@pytest.mark.asyncio
@pytest.mark.slow  # custom

# Mock
Mock(return_value=42)
Mock(side_effect=[1, 2, Exception()])
AsyncMock(return_value={"data": []})
patch("module.function")
patch.object(instance, "method")
patch.dict(os.environ, {"KEY": "val"})
```

---

*End of pytest Advanced Theory — 40 LPA Interview Prep*
*Next: 02_sqlalchemy_advanced.md*
