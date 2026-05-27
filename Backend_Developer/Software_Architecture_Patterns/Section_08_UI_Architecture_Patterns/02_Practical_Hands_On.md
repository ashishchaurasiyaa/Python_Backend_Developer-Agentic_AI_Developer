# Lecture 2 — Practical Hands-On: MVU & VIPER

> **Theory file:** [02_MVU_VIPER.md](02_MVU_VIPER.md)

---

## 🎯 Is Practical Mein Kya Banayenge?

1. ✅ **MVU loop** built from scratch in Python (counter app)
2. ✅ **Redux-style** store + reducer + actions in pure Python
3. ✅ **Time-travel debugging** demo (action log + replay)
4. ✅ **VIPER skeleton** in Python — all 5 layers wired up
5. ✅ **Mock-based testing** at every VIPER layer

By end: aap dono pattern ke loop ko code level pe samjho.

---

## 1. Project Structure

```
mvu_viper_demo/
├── mvu_counter/
│   ├── mvu.py
│   ├── time_travel.py
│   └── tests/
│       └── test_mvu.py
│
├── redux_python/
│   ├── store.py
│   ├── reducers.py
│   ├── actions.py
│   └── tests/
│       └── test_store.py
│
└── viper_python/
    ├── entity.py
    ├── interactor.py
    ├── presenter.py
    ├── view.py
    ├── router.py
    ├── main.py
    └── tests/
        ├── test_interactor.py
        ├── test_presenter.py
        └── test_router.py
```

---

## 2. 🔁 MVU Loop — Counter

### `mvu_counter/mvu.py`

```python
from dataclasses import dataclass, replace
from typing import Callable, Literal


# === Model ===
@dataclass(frozen=True)
class Model:
    count: int = 0
    history: tuple = ()  # immutable log of messages


# === Messages ===
@dataclass(frozen=True)
class Increment: pass


@dataclass(frozen=True)
class Decrement: pass


@dataclass(frozen=True)
class Reset: pass


Message = Increment | Decrement | Reset


# === Update (pure function) ===
def update(msg: Message, model: Model) -> Model:
    new_history = model.history + (msg,)
    if isinstance(msg, Increment):
        return replace(model, count=model.count + 1, history=new_history)
    if isinstance(msg, Decrement):
        return replace(model, count=model.count - 1, history=new_history)
    if isinstance(msg, Reset):
        return replace(model, count=0, history=new_history)
    return model


# === View (pure function) ===
def view(model: Model) -> str:
    return f"[Count = {model.count}]  history: {len(model.history)} messages"


# === Runtime loop ===
class MvuRuntime:
    def __init__(self, initial: Model, render: Callable[[str], None]):
        self.model = initial
        self.render = render

    def dispatch(self, msg: Message):
        self.model = update(msg, self.model)
        self.render(view(self.model))
```

### `mvu_counter/time_travel.py`

```python
from .mvu import Model, update, view, Increment, Decrement, Reset


def replay(messages: list) -> list[Model]:
    """Replay actions to reconstruct every intermediate state."""
    states = [Model()]
    for msg in messages:
        states.append(update(msg, states[-1]))
    return states


def time_travel_demo():
    log = [Increment(), Increment(), Increment(), Decrement(), Reset()]
    states = replay(log)
    print("=== Time Travel ===")
    for i, s in enumerate(states):
        print(f"  step {i}: {view(s)}")


if __name__ == "__main__":
    time_travel_demo()
```

### `mvu_counter/tests/test_mvu.py`

```python
from ..mvu import Model, update, view, Increment, Decrement, Reset


def test_update_is_pure_function():
    m1 = Model(count=5)
    m2 = update(Increment(), m1)
    # original untouched
    assert m1.count == 5
    # new model
    assert m2.count == 6


def test_view_is_deterministic():
    m = Model(count=42)
    assert view(m) == view(m)  # same input → same output


def test_decrement_then_reset():
    m = Model()
    m = update(Decrement(), m)
    m = update(Decrement(), m)
    m = update(Reset(), m)
    assert m.count == 0
    assert len(m.history) == 3
```

**Run:**

```bash
cd mvu_counter
python -m time_travel
pytest tests/
```

---

## 3. 🗃 Redux-Style Store in Python

### `redux_python/actions.py`

```python
ADD_TODO = "ADD_TODO"
TOGGLE_TODO = "TOGGLE_TODO"
CLEAR_DONE = "CLEAR_DONE"


def add_todo(title):
    return {"type": ADD_TODO, "payload": {"title": title}}


def toggle_todo(id):
    return {"type": TOGGLE_TODO, "payload": {"id": id}}


def clear_done():
    return {"type": CLEAR_DONE}
```

### `redux_python/reducers.py`

```python
from .actions import ADD_TODO, TOGGLE_TODO, CLEAR_DONE


def initial_state():
    return {"next_id": 1, "items": []}


def todos_reducer(state, action):
    """Pure function: (state, action) → newState."""
    if state is None:
        return initial_state()

    t = action["type"]

    if t == ADD_TODO:
        new_item = {
            "id": state["next_id"],
            "title": action["payload"]["title"],
            "done": False,
        }
        return {
            "next_id": state["next_id"] + 1,
            "items": state["items"] + [new_item],
        }

    if t == TOGGLE_TODO:
        id_ = action["payload"]["id"]
        items = [
            ({**i, "done": not i["done"]} if i["id"] == id_ else i)
            for i in state["items"]
        ]
        return {**state, "items": items}

    if t == CLEAR_DONE:
        items = [i for i in state["items"] if not i["done"]]
        return {**state, "items": items}

    return state
```

### `redux_python/store.py`

```python
class Store:
    def __init__(self, reducer):
        self._reducer = reducer
        self._state = reducer(None, {"type": "@@INIT"})
        self._listeners = []
        self._log = []   # all dispatched actions (time-travel ready)

    def get_state(self):
        return self._state

    def dispatch(self, action):
        self._log.append(action)
        self._state = self._reducer(self._state, action)
        for cb in self._listeners:
            cb(self._state)

    def subscribe(self, callback):
        self._listeners.append(callback)
        callback(self._state)

    # Time-travel helpers
    def get_log(self):
        return list(self._log)

    def replay_until(self, n):
        state = self._reducer(None, {"type": "@@INIT"})
        for a in self._log[:n]:
            state = self._reducer(state, a)
        return state
```

### `redux_python/tests/test_store.py`

```python
from ..store import Store
from ..reducers import todos_reducer
from ..actions import add_todo, toggle_todo, clear_done


def test_dispatch_updates_state():
    store = Store(todos_reducer)
    store.dispatch(add_todo("Buy milk"))
    s = store.get_state()
    assert len(s["items"]) == 1
    assert s["items"][0]["title"] == "Buy milk"


def test_subscribers_notified():
    store = Store(todos_reducer)
    seen = []
    store.subscribe(lambda s: seen.append(len(s["items"])))
    store.dispatch(add_todo("A"))
    store.dispatch(add_todo("B"))
    assert seen == [0, 1, 2]  # initial + 2 dispatches


def test_time_travel():
    store = Store(todos_reducer)
    store.dispatch(add_todo("A"))
    store.dispatch(add_todo("B"))
    store.dispatch(toggle_todo(1))
    store.dispatch(clear_done())

    # Replay up to step 2 → state after first 2 actions
    snapshot = store.replay_until(2)
    titles = [t["title"] for t in snapshot["items"]]
    assert titles == ["A", "B"]
    assert all(t["done"] is False for t in snapshot["items"])
```

### Demo Script

```python
# redux_python/demo.py
from .store import Store
from .reducers import todos_reducer
from .actions import add_todo, toggle_todo, clear_done


def print_state(s):
    print("STATE:", [(i["id"], i["title"], i["done"]) for i in s["items"]])


if __name__ == "__main__":
    store = Store(todos_reducer)
    store.subscribe(print_state)

    store.dispatch(add_todo("Learn MVU"))
    store.dispatch(add_todo("Build Redux"))
    store.dispatch(toggle_todo(1))
    store.dispatch(clear_done())

    print("\n=== Replay history ===")
    for i in range(len(store.get_log()) + 1):
        print(f"  step {i}: {store.replay_until(i)}")
```

---

## 4. 🏛 VIPER Skeleton — User Profile Module

### `viper_python/entity.py`

```python
from dataclasses import dataclass


@dataclass
class User:
    id: int
    name: str
    email: str
```

### `viper_python/interactor.py`

```python
from .entity import User


class UserRepository:
    """Pretend DB / API."""

    _users = {
        1: User(1, "Alice", "alice@example.com"),
        2: User(2, "Bob", "bob@example.com"),
    }

    def fetch(self, id: int) -> User | None:
        return self._users.get(id)


class ProfileInteractor:
    """All business logic lives here. NO UI knowledge."""

    def __init__(self, repo: UserRepository):
        self.repo = repo

    def load_profile(self, user_id: int) -> dict:
        user = self.repo.fetch(user_id)
        if not user:
            return {"ok": False, "error": "User not found"}
        return {
            "ok": True,
            "data": {"name": user.name, "email": user.email},
        }
```

### `viper_python/view.py`

```python
class ProfileView:
    """Passive — only renders what Presenter tells it."""

    def __init__(self):
        self.presenter = None  # injected by Router

    def render(self, vm: dict):
        print(f"\n👤 {vm['name']}")
        print(f"   ✉  {vm['email']}")

    def show_error(self, msg: str):
        print(f"\n❌ {msg}")

    # user events
    def on_appear(self, user_id):
        self.presenter.view_did_appear(user_id)

    def on_logout(self):
        self.presenter.logout_tapped()
```

### `viper_python/presenter.py`

```python
class ProfilePresenter:
    """Coordinator — no business logic, no data access."""

    def __init__(self, interactor, router):
        self.interactor = interactor
        self.router = router
        self.view = None  # set by Router

    def view_did_appear(self, user_id):
        result = self.interactor.load_profile(user_id)
        if not result["ok"]:
            self.view.show_error(result["error"])
            return
        # Format for view
        data = result["data"]
        vm = {
            "name": data["name"].upper(),
            "email": data["email"],
        }
        self.view.render(vm)

    def logout_tapped(self):
        self.router.route_to_login()
```

### `viper_python/router.py`

```python
from .view import ProfileView
from .presenter import ProfilePresenter
from .interactor import ProfileInteractor, UserRepository


class Router:
    """Owns navigation + module assembly."""

    def build_profile_module(self) -> ProfileView:
        view = ProfileView()
        interactor = ProfileInteractor(UserRepository())
        presenter = ProfilePresenter(interactor, self)

        # wire up
        view.presenter = presenter
        presenter.view = view
        return view

    def route_to_login(self):
        print("\n→ Navigating to LOGIN screen")
```

### `viper_python/main.py`

```python
from .router import Router


if __name__ == "__main__":
    router = Router()
    profile_view = router.build_profile_module()
    profile_view.on_appear(user_id=1)
    profile_view.on_appear(user_id=999)  # not found
    profile_view.on_logout()
```

### `viper_python/tests/test_interactor.py`

```python
from ..interactor import ProfileInteractor, UserRepository


def test_load_existing_user():
    interactor = ProfileInteractor(UserRepository())
    res = interactor.load_profile(1)
    assert res["ok"] is True
    assert res["data"]["name"] == "Alice"


def test_load_missing_user():
    interactor = ProfileInteractor(UserRepository())
    res = interactor.load_profile(999)
    assert res["ok"] is False
    assert "not found" in res["error"]
```

### `viper_python/tests/test_presenter.py`

```python
from ..presenter import ProfilePresenter


class FakeView:
    def __init__(self):
        self.rendered = None
        self.error = None

    def render(self, vm):
        self.rendered = vm

    def show_error(self, msg):
        self.error = msg


class FakeInteractor:
    def __init__(self, result):
        self.result = result

    def load_profile(self, _):
        return self.result


class FakeRouter:
    def __init__(self):
        self.went_to_login = False

    def route_to_login(self):
        self.went_to_login = True


def test_presenter_formats_data():
    interactor = FakeInteractor({"ok": True, "data": {"name": "Alice", "email": "a@x.com"}})
    router = FakeRouter()
    p = ProfilePresenter(interactor, router)
    p.view = FakeView()
    p.view_did_appear(1)
    assert p.view.rendered == {"name": "ALICE", "email": "a@x.com"}


def test_presenter_shows_error():
    interactor = FakeInteractor({"ok": False, "error": "Boom"})
    p = ProfilePresenter(interactor, FakeRouter())
    p.view = FakeView()
    p.view_did_appear(1)
    assert p.view.error == "Boom"


def test_logout_routes_to_login():
    router = FakeRouter()
    p = ProfilePresenter(FakeInteractor({"ok": True, "data": {"name": "X", "email": "x"}}), router)
    p.view = FakeView()
    p.logout_tapped()
    assert router.went_to_login is True
```

---

## 5. VIPER Layer Testability

```
┌────────────┬────────────────────────────────────────┐
│  Layer     │  How to Test                           │
├────────────┼────────────────────────────────────────┤
│ Interactor │ Real or fake Repository                │
│ Presenter  │ FakeView + FakeInteractor + FakeRouter │
│ View       │ Snapshot tests or UI automation        │
│ Router     │ Mock module factories                  │
│ Entity     │ Plain data — no tests needed           │
└────────────┴────────────────────────────────────────┘
```

→ **Every layer mockable**. That's VIPER's superpower.

---

## 6. ⚖️ MVU vs VIPER — Code Smell Cheat Sheet

```
You see:                          → Pattern hint:
─────────────────────────────────────────────────────────
single Store + dispatch(action)   → MVU/Redux
pure (state, action) → newState   → MVU/Redux
5 files per feature folder        → VIPER
Router class for navigation       → VIPER
view = func(model)                → MVU
Interactor + Entity terms         → VIPER
```

---

## 7. ✅ Hands-On Checklist

```
□ Built MVU loop, ran time-travel demo
□ Implemented Redux store + reducer + replay
□ Verified subscribers fire on dispatch
□ Built VIPER module with all 5 layers
□ Wrote isolated tests for Interactor + Presenter
□ Mocked View + Router to test Presenter
```

---

## 🔗 Next

- Next: [03_Offline_First_Sync.md](03_Offline_First_Sync.md)
