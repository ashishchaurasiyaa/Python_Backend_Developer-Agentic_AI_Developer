# Dependency Injection + Repository Pattern + State Machine — LLD

## PART 1 — Dependency Injection

### WHAT
**DI** is a design pattern where a class receives its dependencies from the **outside** instead of creating them internally.

```python
# WITHOUT DI — tightly coupled
class UserService:
    def __init__(self):
        self.db   = PostgreSQLConnection("localhost", 5432)   # hardcoded!
        self.cache = RedisCache("redis://localhost")           # hardcoded!
        self.mailer = SMTPMailer("smtp.gmail.com")             # hardcoded!

# WITH DI — loosely coupled
class UserService:
    def __init__(self, db: Database, cache: Cache, mailer: Mailer):
        self.db     = db      # injected from outside
        self.cache  = cache
        self.mailer = mailer
```

### WHY DI

| Problem without DI | DI Solution |
|---|---|
| Hard to test (can't mock) | Inject FakeDB for tests |
| Hard to swap implementation | Inject different impl |
| Hidden dependencies | Dependencies visible in __init__ |
| Global state | Each instance gets its own deps |

### Python DI Patterns

#### Pattern 1 — Constructor Injection (most common)
```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Protocol

# Abstractions (interfaces)
class LLMProvider(Protocol):
    def complete(self, messages: list[dict]) -> str: ...

class Cache(Protocol):
    def get(self, key: str) -> str | None: ...
    def set(self, key: str, value: str, ttl: int) -> None: ...

class Logger(Protocol):
    def info(self, msg: str) -> None: ...

# Concrete implementations
class OpenAIProvider:
    def complete(self, messages: list[dict]) -> str:
        # Real API call
        return "Response from OpenAI"

class RedisCache:
    def get(self, key: str) -> str | None: ...
    def set(self, key: str, value: str, ttl: int): ...

# Service that depends on abstractions, not concretions
class ChatService:
    def __init__(
        self,
        llm:    LLMProvider,
        cache:  Cache,
        logger: Logger,
    ):
        self._llm    = llm
        self._cache  = cache
        self._logger = logger
    
    def chat(self, session_id: str, user_msg: str) -> str:
        cache_key = f"chat:{session_id}:{hash(user_msg)}"
        
        if cached := self._cache.get(cache_key):
            self._logger.info(f"Cache hit: {cache_key}")
            return cached
        
        response = self._llm.complete([
            {"role": "user", "content": user_msg}
        ])
        self._cache.set(cache_key, response, ttl=3600)
        return response


# ── Composition root (wire everything together) ────────────────────────────
def create_chat_service() -> ChatService:
    """Factory function — only place that knows about concrete classes."""
    return ChatService(
        llm    = OpenAIProvider(),
        cache  = RedisCache(),
        logger = logging.getLogger("chat"),
    )

# ── Testing — inject fakes ─────────────────────────────────────────────────
class FakeLLM:
    def complete(self, messages): return "Fake response"

class FakeCache:
    def __init__(self):
        self._data = {}
    def get(self, key): return self._data.get(key)
    def set(self, key, value, ttl): self._data[key] = value

class FakeLogger:
    def info(self, msg): pass

def test_chat_caches_response():
    service = ChatService(FakeLLM(), FakeCache(), FakeLogger())
    r1 = service.chat("s1", "Hello")
    r2 = service.chat("s1", "Hello")  # should be cached
    assert r1 == r2 == "Fake response"
    print("DI test passed ✓")

test_chat_caches_response()
```

#### Pattern 2 — FastAPI Depends() (built-in DI)
```python
from fastapi import FastAPI, Depends

app = FastAPI()

# Dependency providers
def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_cache() -> Cache:
    return RedisCache()

def get_llm() -> LLMProvider:
    return OpenAIProvider()

# Inject into endpoint
@app.post("/chat")
async def chat_endpoint(
    body:  ChatRequest,
    db:    Session       = Depends(get_db),
    cache: Cache         = Depends(get_cache),
    llm:   LLMProvider   = Depends(get_llm),
):
    service = ChatService(llm, cache, logging.getLogger("chat"))
    return {"response": service.chat(body.session_id, body.message)}
```

---

## PART 2 — Repository Pattern

### WHAT
Repository pattern provides a **clean abstraction over data storage**. Business logic doesn't know or care whether data is in PostgreSQL, MongoDB, or a test fixture.

```
Business Logic → Repository Interface → DB Implementation
                                     → Redis Implementation
                                     → Fake/Memory Implementation (tests)
```

### WHY
Without repository: business logic has SQL all over it → hard to test, hard to change DB.

### Python Implementation

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import uuid

@dataclass
class User:
    id:       str
    email:    str
    name:     str
    is_active: bool = True

@dataclass
class Post:
    id:        str
    user_id:   str
    title:     str
    content:   str

# ── Repository Interfaces ─────────────────────────────────────────────────

class UserRepository(ABC):
    @abstractmethod
    def get_by_id(self, user_id: str) -> Optional[User]: ...
    
    @abstractmethod
    def get_by_email(self, email: str) -> Optional[User]: ...
    
    @abstractmethod
    def save(self, user: User) -> User: ...
    
    @abstractmethod
    def delete(self, user_id: str) -> bool: ...
    
    @abstractmethod
    def list_active(self) -> list[User]: ...


class PostRepository(ABC):
    @abstractmethod
    def get_by_id(self, post_id: str) -> Optional[Post]: ...
    
    @abstractmethod
    def get_by_user(self, user_id: str) -> list[Post]: ...
    
    @abstractmethod
    def save(self, post: Post) -> Post: ...
    
    @abstractmethod
    def delete(self, post_id: str) -> bool: ...


# ── PostgreSQL Implementation ─────────────────────────────────────────────

class PostgreSQLUserRepository(UserRepository):
    def __init__(self, session: Session):
        self._session = session
    
    def get_by_id(self, user_id: str) -> Optional[User]:
        row = self._session.query(UserModel).filter_by(id=user_id).first()
        return User(row.id, row.email, row.name, row.is_active) if row else None
    
    def get_by_email(self, email: str) -> Optional[User]:
        row = self._session.query(UserModel).filter_by(email=email).first()
        return User(row.id, row.email, row.name, row.is_active) if row else None
    
    def save(self, user: User) -> User:
        row = self._session.merge(UserModel(
            id=user.id, email=user.email,
            name=user.name, is_active=user.is_active
        ))
        self._session.commit()
        return user
    
    def delete(self, user_id: str) -> bool:
        n = self._session.query(UserModel).filter_by(id=user_id).delete()
        self._session.commit()
        return n > 0
    
    def list_active(self) -> list[User]:
        rows = self._session.query(UserModel).filter_by(is_active=True).all()
        return [User(r.id, r.email, r.name, r.is_active) for r in rows]


# ── In-Memory Implementation (for tests) ─────────────────────────────────

class InMemoryUserRepository(UserRepository):
    def __init__(self):
        self._store: dict[str, User] = {}
    
    def get_by_id(self, user_id: str) -> Optional[User]:
        return self._store.get(user_id)
    
    def get_by_email(self, email: str) -> Optional[User]:
        return next((u for u in self._store.values() if u.email == email), None)
    
    def save(self, user: User) -> User:
        self._store[user.id] = user
        return user
    
    def delete(self, user_id: str) -> bool:
        return bool(self._store.pop(user_id, None))
    
    def list_active(self) -> list[User]:
        return [u for u in self._store.values() if u.is_active]


# ── Business Logic uses Repository interface ──────────────────────────────

class UserService:
    def __init__(self, users: UserRepository, posts: PostRepository):
        self._users = users
        self._posts = posts
    
    def register(self, email: str, name: str) -> User:
        if self._users.get_by_email(email):
            raise ValueError(f"Email already registered: {email}")
        user = User(id=str(uuid.uuid4()), email=email, name=name)
        return self._users.save(user)
    
    def deactivate(self, user_id: str) -> None:
        user = self._users.get_by_id(user_id)
        if not user:
            raise ValueError(f"User not found: {user_id}")
        user.is_active = False
        self._users.save(user)


# ── Tests (no DB needed) ─────────────────────────────────────────────────
def test_user_service():
    repo    = InMemoryUserRepository()
    service = UserService(repo, InMemoryPostRepository())
    
    user = service.register("alice@example.com", "Alice")
    assert user.email == "alice@example.com"
    
    try:
        service.register("alice@example.com", "Alice2")   # duplicate
        assert False, "Should have raised"
    except ValueError:
        pass
    
    print("Repository pattern tests passed ✓")

test_user_service()
```

---

## PART 3 — State Machine Design

### WHAT
A state machine models an object that can be in **one of N states** at a time, transitioning between states based on events.

### WHEN TO USE
- Order lifecycle: draft → pending → confirmed → shipped → delivered
- Agent status: idle → running → waiting → completed → failed
- Connection: disconnected → connecting → connected → reconnecting

### Python Implementation

```python
from enum import Enum, auto
from typing import Callable

class OrderStatus(Enum):
    DRAFT      = auto()
    PENDING    = auto()
    CONFIRMED  = auto()
    SHIPPED    = auto()
    DELIVERED  = auto()
    CANCELLED  = auto()
    REFUNDED   = auto()

class InvalidTransition(Exception): pass

class OrderStateMachine:
    """
    Finite State Machine for Order lifecycle.
    Defines allowed transitions and guards.
    """
    
    # Allowed transitions: {current_state: {event: next_state}}
    TRANSITIONS: dict[OrderStatus, dict[str, OrderStatus]] = {
        OrderStatus.DRAFT: {
            "submit":  OrderStatus.PENDING,
            "discard": OrderStatus.CANCELLED,
        },
        OrderStatus.PENDING: {
            "confirm": OrderStatus.CONFIRMED,
            "cancel":  OrderStatus.CANCELLED,
        },
        OrderStatus.CONFIRMED: {
            "ship":    OrderStatus.SHIPPED,
            "cancel":  OrderStatus.CANCELLED,
        },
        OrderStatus.SHIPPED: {
            "deliver": OrderStatus.DELIVERED,
        },
        OrderStatus.DELIVERED: {
            "refund":  OrderStatus.REFUNDED,
        },
        OrderStatus.CANCELLED: {},    # terminal state
        OrderStatus.REFUNDED:  {},    # terminal state
    }
    
    def __init__(self, initial: OrderStatus = OrderStatus.DRAFT):
        self._state = initial
        self._callbacks: dict[str, list[Callable]] = {}
    
    @property
    def state(self) -> OrderStatus:
        return self._state
    
    def can(self, event: str) -> bool:
        return event in self.TRANSITIONS.get(self._state, {})
    
    def trigger(self, event: str, **kwargs) -> OrderStatus:
        allowed = self.TRANSITIONS.get(self._state, {})
        if event not in allowed:
            raise InvalidTransition(
                f"Cannot '{event}' from state '{self._state.name}'. "
                f"Allowed events: {list(allowed)}"
            )
        old_state  = self._state
        self._state = allowed[event]
        
        # Fire callbacks
        for cb in self._callbacks.get(event, []):
            cb(old_state, self._state, **kwargs)
        
        return self._state
    
    def on(self, event: str, callback: Callable):
        self._callbacks.setdefault(event, []).append(callback)
        return self
    
    def is_terminal(self) -> bool:
        return not bool(self.TRANSITIONS.get(self._state))


# Usage
sm = OrderStateMachine()
sm.on("confirm", lambda old, new, **kw: print(f"Order confirmed! {old.name}→{new.name}"))

print(f"Initial: {sm.state.name}")
sm.trigger("submit")
sm.trigger("confirm")       # prints callback
sm.trigger("ship")
sm.trigger("deliver")
print(f"Final: {sm.state.name}")
print(f"Terminal: {sm.is_terminal()}")

# Bad transition
try:
    sm.trigger("cancel")    # can't cancel delivered order
except InvalidTransition as e:
    print(f"Error: {e}")


# ── Agent State Machine ───────────────────────────────────────────────────

class AgentStatus(Enum):
    IDLE      = auto()
    RUNNING   = auto()
    WAITING   = auto()
    COMPLETED = auto()
    FAILED    = auto()

AGENT_TRANSITIONS = {
    AgentStatus.IDLE: {
        "start": AgentStatus.RUNNING,
    },
    AgentStatus.RUNNING: {
        "wait_for_tool": AgentStatus.WAITING,
        "complete":      AgentStatus.COMPLETED,
        "fail":          AgentStatus.FAILED,
    },
    AgentStatus.WAITING: {
        "tool_done": AgentStatus.RUNNING,
        "timeout":   AgentStatus.FAILED,
    },
    AgentStatus.COMPLETED: {},
    AgentStatus.FAILED:    {},
}
```

---

## Interview Q&A

**Q: What problem does DI solve?**
A: Tight coupling. Without DI, your class creates its own dependencies — you can't test it, can't change the implementation, can't swap in a different version. DI makes dependencies explicit and swappable.

**Q: What is the difference between Repository and DAO (Data Access Object)?**
A: DAO maps to DB tables (CRUD operations on tables). Repository works with domain objects — it may aggregate from multiple tables. Repository hides persistence details; DAO just hides SQL.

**Q: When would you use a State Machine vs if/else?**
A: If/else for 2-3 states. State machine for 4+ states or complex transition rules. State machine self-documents allowed transitions, throws clear errors on invalid ones, and is easily extensible.

**Q: How do you persist State Machine state?**
A: Store `state.name` as a string column in DB. On load, reconstruct: `sm = OrderStateMachine(initial=OrderStatus[row.status])`. Use DB transaction to save state change atomically.
