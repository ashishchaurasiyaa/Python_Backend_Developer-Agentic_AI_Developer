# Lecture 1 — Practical Hands-On: MVC, MVP, MVVM

> **Theory file:** [01_MVC_MVP_MVVM.md](01_MVC_MVP_MVVM.md)

---

## 🎯 Is Practical Mein Kya Banayenge?

Same simple "Counter / Todo" feature implemented three ways:

1. ✅ **MVC** in Flask (Python) — classic web style
2. ✅ **MVP** in pure Python (testable, view as interface)
3. ✅ **MVVM** in Python + Tkinter-style with observable binding
4. ✅ **Side-by-side test comparison** — see why MVP/MVVM win on testability

By end: aap practically samajh jaoge ki **kab kaunsa pattern use karna** hai.

---

## 1. Project Structure

```
ui_patterns_demo/
├── mvc_flask/
│   ├── app.py
│   ├── models/
│   │   └── todo.py
│   ├── templates/
│   │   └── index.html
│   └── controllers/
│       └── todo_controller.py
│
├── mvp_python/
│   ├── model.py
│   ├── view_interface.py
│   ├── console_view.py
│   ├── presenter.py
│   ├── main.py
│   └── tests/
│       └── test_presenter.py
│
├── mvvm_python/
│   ├── model.py
│   ├── viewmodel.py
│   ├── observable.py
│   ├── view.py
│   ├── main.py
│   └── tests/
│       └── test_viewmodel.py
│
└── README.md
```

---

## 2. 🏗 MVC — Flask Todo App

### `mvc_flask/models/todo.py`

```python
class Todo:
    def __init__(self, id, title, done=False):
        self.id = id
        self.title = title
        self.done = done


class TodoStore:
    def __init__(self):
        self._items = []
        self._next_id = 1

    def all(self):
        return list(self._items)

    def add(self, title):
        todo = Todo(self._next_id, title)
        self._items.append(todo)
        self._next_id += 1
        return todo

    def toggle(self, id):
        for t in self._items:
            if t.id == id:
                t.done = not t.done
                return t
        return None
```

### `mvc_flask/controllers/todo_controller.py`

```python
from flask import Blueprint, render_template, request, redirect, url_for
from ..models.todo import TodoStore

bp = Blueprint("todo", __name__)
store = TodoStore()


@bp.route("/")
def index():
    todos = store.all()
    return render_template("index.html", todos=todos)


@bp.route("/add", methods=["POST"])
def add():
    title = request.form.get("title", "").strip()
    if title:
        store.add(title)
    return redirect(url_for("todo.index"))


@bp.route("/toggle/<int:id>")
def toggle(id):
    store.toggle(id)
    return redirect(url_for("todo.index"))
```

### `mvc_flask/templates/index.html`

```html
<!doctype html>
<title>Todos (MVC)</title>
<h1>My Todos</h1>
<form action="/add" method="post">
    <input name="title" placeholder="What to do?">
    <button>Add</button>
</form>
<ul>
    {% for t in todos %}
    <li>
        <a href="/toggle/{{ t.id }}">
            {% if t.done %}✓{% else %}○{% endif %} {{ t.title }}
        </a>
    </li>
    {% endfor %}
</ul>
```

### `mvc_flask/app.py`

```python
from flask import Flask
from controllers.todo_controller import bp

app = Flask(__name__)
app.register_blueprint(bp)

if __name__ == "__main__":
    app.run(debug=True)
```

**Run:**

```bash
cd mvc_flask
pip install flask
python app.py
# Open http://localhost:5000
```

### MVC Observations

```
✓ Controller mixes routing + logic + redirect orchestration
✓ View (Jinja template) accesses model fields directly
✓ Hard to unit-test "what happens when user toggles"
   without spinning up Flask test client
```

---

## 3. 🧪 MVP — Testable Console Todo

### `mvp_python/model.py`

```python
from dataclasses import dataclass


@dataclass
class Todo:
    id: int
    title: str
    done: bool = False


class TodoModel:
    def __init__(self):
        self._items: list[Todo] = []
        self._next_id = 1

    def all(self):
        return list(self._items)

    def add(self, title: str) -> Todo:
        todo = Todo(self._next_id, title)
        self._items.append(todo)
        self._next_id += 1
        return todo

    def toggle(self, id: int) -> Todo | None:
        for t in self._items:
            if t.id == id:
                t.done = not t.done
                return t
        return None
```

### `mvp_python/view_interface.py`

```python
from abc import ABC, abstractmethod
from .model import Todo


class TodoView(ABC):
    """Contract the Presenter uses to talk to ANY view."""

    @abstractmethod
    def render(self, todos: list[Todo]) -> None: ...

    @abstractmethod
    def show_error(self, msg: str) -> None: ...
```

### `mvp_python/console_view.py`

```python
from .view_interface import TodoView


class ConsoleTodoView(TodoView):
    def render(self, todos):
        print("\n=== Todos ===")
        if not todos:
            print("  (empty)")
        for t in todos:
            mark = "✓" if t.done else "○"
            print(f"  [{t.id}] {mark} {t.title}")
        print()

    def show_error(self, msg):
        print(f"ERROR: {msg}")
```

### `mvp_python/presenter.py`

```python
from .model import TodoModel
from .view_interface import TodoView


class TodoPresenter:
    def __init__(self, model: TodoModel, view: TodoView):
        self.model = model
        self.view = view

    def on_show(self):
        self.view.render(self.model.all())

    def on_add(self, title: str):
        title = (title or "").strip()
        if not title:
            self.view.show_error("Title cannot be empty")
            return
        self.model.add(title)
        self.view.render(self.model.all())

    def on_toggle(self, id: int):
        if self.model.toggle(id) is None:
            self.view.show_error(f"Todo {id} not found")
            return
        self.view.render(self.model.all())
```

### `mvp_python/main.py`

```python
from .model import TodoModel
from .console_view import ConsoleTodoView
from .presenter import TodoPresenter


def repl():
    presenter = TodoPresenter(TodoModel(), ConsoleTodoView())
    presenter.on_show()
    while True:
        cmd = input("cmd (add/toggle/quit): ").strip().split(maxsplit=1)
        if not cmd:
            continue
        op = cmd[0]
        arg = cmd[1] if len(cmd) > 1 else ""
        if op == "add":
            presenter.on_add(arg)
        elif op == "toggle":
            presenter.on_toggle(int(arg))
        elif op == "quit":
            break


if __name__ == "__main__":
    repl()
```

### `mvp_python/tests/test_presenter.py`

```python
import pytest
from ..model import TodoModel
from ..view_interface import TodoView
from ..presenter import TodoPresenter


class FakeView(TodoView):
    def __init__(self):
        self.renders = []
        self.errors = []

    def render(self, todos):
        self.renders.append([(t.id, t.title, t.done) for t in todos])

    def show_error(self, msg):
        self.errors.append(msg)


def test_add_renders_new_list():
    view = FakeView()
    p = TodoPresenter(TodoModel(), view)
    p.on_add("Buy milk")
    assert view.renders[-1] == [(1, "Buy milk", False)]


def test_empty_title_shows_error():
    view = FakeView()
    p = TodoPresenter(TodoModel(), view)
    p.on_add("   ")
    assert view.errors == ["Title cannot be empty"]
    assert view.renders == []


def test_toggle_flips_done():
    view = FakeView()
    p = TodoPresenter(TodoModel(), view)
    p.on_add("Test")
    p.on_toggle(1)
    assert view.renders[-1] == [(1, "Test", True)]


def test_toggle_unknown_id_errors():
    view = FakeView()
    p = TodoPresenter(TodoModel(), view)
    p.on_toggle(99)
    assert view.errors == ["Todo 99 not found"]
```

**Run tests:**

```bash
cd mvp_python
pytest tests/
```

### MVP Observations

```
✓ View is just an interface — easily mocked (FakeView)
✓ Presenter has all logic and is 100% testable
✓ Can swap ConsoleTodoView ↔ WebView ↔ GUIView
   without touching Presenter
```

---

## 4. 🔄 MVVM — Observable Binding in Python

### `mvvm_python/observable.py`

```python
class Observable:
    """Simple observable property — emits change events."""

    def __init__(self, value=None):
        self._value = value
        self._listeners = []

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, new):
        if new != self._value:
            self._value = new
            for cb in self._listeners:
                cb(new)

    def bind(self, callback):
        self._listeners.append(callback)
        callback(self._value)  # initial sync
```

### `mvvm_python/model.py`

```python
from dataclasses import dataclass


@dataclass
class Todo:
    id: int
    title: str
    done: bool = False


class TodoModel:
    def __init__(self):
        self._items = []
        self._next_id = 1

    def all(self):
        return list(self._items)

    def add(self, title):
        t = Todo(self._next_id, title)
        self._items.append(t)
        self._next_id += 1
        return t

    def toggle(self, id):
        for t in self._items:
            if t.id == id:
                t.done = not t.done
                return t
        return None
```

### `mvvm_python/viewmodel.py`

```python
from .model import TodoModel
from .observable import Observable


class TodoViewModel:
    def __init__(self):
        self._model = TodoModel()
        # observable properties bound by the View
        self.todos = Observable([])
        self.error = Observable("")
        self.draft_title = Observable("")

    # commands (called by View)
    def add(self):
        title = (self.draft_title.value or "").strip()
        if not title:
            self.error.value = "Title cannot be empty"
            return
        self.error.value = ""
        self._model.add(title)
        self.draft_title.value = ""
        self.todos.value = self._model.all()

    def toggle(self, id):
        if self._model.toggle(id) is None:
            self.error.value = f"Todo {id} not found"
            return
        self.error.value = ""
        self.todos.value = self._model.all()
```

### `mvvm_python/view.py`

```python
from .viewmodel import TodoViewModel


class ConsoleView:
    """View knows ViewModel — but NOT the other way around."""

    def __init__(self, vm: TodoViewModel):
        self.vm = vm
        # 1-way binding: when VM changes, re-render
        vm.todos.bind(self._render_todos)
        vm.error.bind(self._render_error)

    def _render_todos(self, todos):
        print("\n=== Todos ===")
        for t in todos:
            mark = "✓" if t.done else "○"
            print(f"  [{t.id}] {mark} {t.title}")

    def _render_error(self, msg):
        if msg:
            print(f"!! {msg}")

    def repl(self):
        while True:
            cmd = input("cmd> ").strip().split(maxsplit=1)
            if not cmd:
                continue
            op = cmd[0]
            arg = cmd[1] if len(cmd) > 1 else ""
            if op == "add":
                # 2-way binding simulation: View pushes to VM property
                self.vm.draft_title.value = arg
                self.vm.add()
            elif op == "toggle":
                self.vm.toggle(int(arg))
            elif op == "quit":
                break
```

### `mvvm_python/main.py`

```python
from .viewmodel import TodoViewModel
from .view import ConsoleView


if __name__ == "__main__":
    vm = TodoViewModel()
    ConsoleView(vm).repl()
```

### `mvvm_python/tests/test_viewmodel.py`

```python
from ..viewmodel import TodoViewModel


def test_add_updates_todos_observable():
    vm = TodoViewModel()
    seen = []
    vm.todos.bind(lambda v: seen.append([t.title for t in v]))

    vm.draft_title.value = "Test"
    vm.add()

    assert seen[-1] == ["Test"]
    assert vm.draft_title.value == ""  # cleared after add
    assert vm.error.value == ""


def test_empty_title_sets_error_observable():
    vm = TodoViewModel()
    vm.draft_title.value = "   "
    vm.add()
    assert vm.error.value == "Title cannot be empty"


def test_no_view_needed_to_test():
    """The big MVVM win — no View needed at all in tests."""
    vm = TodoViewModel()
    vm.draft_title.value = "A"
    vm.add()
    vm.draft_title.value = "B"
    vm.add()
    vm.toggle(1)
    titles = [(t.id, t.title, t.done) for t in vm.todos.value]
    assert titles == [(1, "A", True), (2, "B", False)]
```

### MVVM Observations

```
✓ ViewModel has NO reference to View
✓ View binds to observables → automatic updates
✓ Tests touch only ViewModel + Observables (no View at all)
✓ Cleanest separation of the three patterns
```

---

## 5. Side-by-Side Test Comparison

```
┌──────────┬───────────────────────────────────────────────┐
│ Pattern  │ Test Setup Complexity                         │
├──────────┼───────────────────────────────────────────────┤
│ MVC      │ Need Flask test client                        │
│          │ POST to /add, GET /, parse HTML response      │
│          │ Slow + brittle                                │
├──────────┼───────────────────────────────────────────────┤
│ MVP      │ Mock View interface (FakeView)                │
│          │ Call Presenter methods directly               │
│          │ Fast unit test, no UI involved                │
├──────────┼───────────────────────────────────────────────┤
│ MVVM     │ Touch ViewModel observables                   │
│          │ No View needed at all                         │
│          │ Fastest, cleanest                             │
└──────────┴───────────────────────────────────────────────┘
```

---

## 6. When to Use Which (Cheat Sheet)

```
MVC
   ✓ Server-rendered web apps (Rails, Django, ASP.NET)
   ✓ Simple CRUD apps
   ✗ Highly interactive client UIs

MVP
   ✓ Pre-binding Android (legacy)
   ✓ Heavy UI logic that must be unit-tested
   ✓ When framework has no native binding

MVVM
   ✓ Modern Android (Jetpack)
   ✓ WPF / WinUI / Xamarin / .NET MAUI
   ✓ SwiftUI / Combine
   ✓ Anywhere with data binding support
```

---

## 7. ✅ Hands-On Checklist

```
□ Ran MVC Flask app, added/toggled a todo
□ Ran MVP REPL, observed FakeView in tests
□ Ran MVVM REPL, watched observables fire on changes
□ Compared test suites — felt the difference in setup cost
□ Identified which pattern fits your current project
```

---

## 🔗 Next

- Next: [02_MVU_VIPER.md](02_MVU_VIPER.md) — unidirectional UI patterns
