# Command, Composite, Proxy & Flyweight Patterns

---

## 1. Command Pattern

**Intent:** Encapsulate a request as an object. Supports undo, queuing, logging.

```
Client → Command (execute/undo) → Receiver
            │
         Invoker (stores commands, calls execute)
```

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from collections import deque

# ── Command Interface ─────────────────────────────────────────────
class Command(ABC):
    @abstractmethod
    def execute(self) -> None: ...
    @abstractmethod
    def undo(self) -> None: ...

# ── Receiver ──────────────────────────────────────────────────────
class TextEditor:
    def __init__(self):
        self.text = ""
    def insert(self, pos: int, s: str):
        self.text = self.text[:pos] + s + self.text[pos:]
    def delete(self, pos: int, length: int):
        self.text = self.text[:pos] + self.text[pos + length:]
    def __repr__(self): return f"Editor('{self.text}')"

# ── Concrete Commands ─────────────────────────────────────────────
@dataclass
class InsertCommand(Command):
    editor: TextEditor
    pos: int
    text: str

    def execute(self):
        self.editor.insert(self.pos, self.text)

    def undo(self):
        self.editor.delete(self.pos, len(self.text))

@dataclass
class DeleteCommand(Command):
    editor: TextEditor
    pos: int
    length: int
    _deleted: str = field(default="", init=False)

    def execute(self):
        self._deleted = self.editor.text[self.pos:self.pos + self.length]
        self.editor.delete(self.pos, self.length)

    def undo(self):
        self.editor.insert(self.pos, self._deleted)

# ── Invoker ───────────────────────────────────────────────────────
class CommandManager:
    """Stores executed commands for undo/redo support."""

    def __init__(self):
        self._history: deque[Command] = deque()
        self._redo_stack: deque[Command] = deque()

    def execute(self, command: Command):
        command.execute()
        self._history.append(command)
        self._redo_stack.clear()   # new command clears redo

    def undo(self):
        if not self._history: return
        cmd = self._history.pop()
        cmd.undo()
        self._redo_stack.append(cmd)

    def redo(self):
        if not self._redo_stack: return
        cmd = self._redo_stack.pop()
        cmd.execute()
        self._history.append(cmd)

# Demo
editor  = TextEditor()
manager = CommandManager()

manager.execute(InsertCommand(editor, 0, "Hello"))
manager.execute(InsertCommand(editor, 5, " World"))
print(editor)           # Editor('Hello World')

manager.undo()
print(editor)           # Editor('Hello')

manager.redo()
print(editor)           # Editor('Hello World')


# Command Pattern for Task Queue / Job System
class TaskQueue:
    """Commands enqueued and executed asynchronously."""

    def __init__(self):
        self._queue: deque[Command] = deque()

    def enqueue(self, cmd: Command):
        self._queue.append(cmd)

    def process_all(self):
        while self._queue:
            cmd = self._queue.popleft()
            cmd.execute()

# Macro command (composite commands)
class MacroCommand(Command):
    def __init__(self, commands: list[Command]):
        self.commands = commands

    def execute(self):
        for cmd in self.commands: cmd.execute()

    def undo(self):
        for cmd in reversed(self.commands): cmd.undo()
```

**When to use:**
- Undo/redo in editors
- Transaction logging (store command history)
- Request queuing / job schedulers
- Remote execution (RPC encapsulated as command object)

---

## 2. Composite Pattern

**Intent:** Treat individual objects and compositions uniformly. Tree structure.

```
Component (interface)
├── Leaf (no children)    ← File
└── Composite (has children) ← Directory
        ├── Leaf
        └── Composite
                └── Leaf
```

```python
from abc import ABC, abstractmethod
from typing import Optional

# ── Component ────────────────────────────────────────────────────
class FileSystemItem(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def size(self) -> int: ...

    @abstractmethod
    def display(self, indent: int = 0) -> None: ...

    # Default no-op for leaf nodes (don't force add/remove on leaves)
    def add(self, item: "FileSystemItem") -> None:
        raise NotImplementedError("Leaf cannot contain children")

    def remove(self, item: "FileSystemItem") -> None:
        raise NotImplementedError("Leaf cannot contain children")

# ── Leaf ─────────────────────────────────────────────────────────
class File(FileSystemItem):
    def __init__(self, name: str, file_size: int):
        super().__init__(name)
        self._size = file_size

    def size(self) -> int:
        return self._size

    def display(self, indent: int = 0) -> None:
        print(" " * indent + f"📄 {self.name} ({self._size} bytes)")

# ── Composite ─────────────────────────────────────────────────────
class Directory(FileSystemItem):
    def __init__(self, name: str):
        super().__init__(name)
        self._children: list[FileSystemItem] = []

    def add(self, item: FileSystemItem) -> None:
        self._children.append(item)

    def remove(self, item: FileSystemItem) -> None:
        self._children.remove(item)

    def size(self) -> int:
        return sum(child.size() for child in self._children)

    def display(self, indent: int = 0) -> None:
        print(" " * indent + f"📁 {self.name}/ ({self.size()} bytes)")
        for child in self._children:
            child.display(indent + 4)

# Demo
root = Directory("root")
src  = Directory("src")
src.add(File("main.py", 1024))
src.add(File("utils.py", 512))

docs = Directory("docs")
docs.add(File("README.md", 2048))

root.add(src)
root.add(docs)
root.add(File("setup.py", 256))

root.display()
print(f"Total size: {root.size()} bytes")


# GUI Widget Composite (real-world example)
class Widget(ABC):
    @abstractmethod
    def render(self, x: int, y: int) -> None: ...

class Button(Widget):
    def __init__(self, label: str):
        self.label = label
    def render(self, x: int, y: int):
        print(f"Button[{self.label}] at ({x},{y})")

class Panel(Widget):
    """Container widget that renders its children."""
    def __init__(self, name: str):
        self.name = name
        self._widgets: list[Widget] = []

    def add(self, widget: Widget) -> "Panel":
        self._widgets.append(widget)
        return self   # fluent interface

    def render(self, x: int, y: int):
        print(f"Panel[{self.name}] at ({x},{y})")
        for i, w in enumerate(self._widgets):
            w.render(x + 10, y + i * 30)

# Demo
form = Panel("LoginForm")
form.add(Button("Username"))
form.add(Button("Password"))
form.add(Panel("Actions").add(Button("Login")).add(Button("Cancel")))
form.render(0, 0)
```

**When to use:**
- File system (files + directories)
- GUI widgets (panels containing sub-panels)
- Organization hierarchy (employees + departments)
- Menu systems (menu items + sub-menus)

---

## 3. Proxy Pattern

**Intent:** Provide a surrogate/placeholder that controls access to another object.

**Types:**
- Virtual Proxy: lazy initialization (create expensive object on demand)
- Protection Proxy: access control
- Remote Proxy: represents object in different address space
- Caching Proxy: cache results

```python
from abc import ABC, abstractmethod
from functools import wraps
from typing import Optional
import time

# ── Subject Interface ─────────────────────────────────────────────
class Database(ABC):
    @abstractmethod
    def query(self, sql: str) -> list[dict]: ...

    @abstractmethod
    def execute(self, sql: str) -> int: ...

# ── Real Subject ──────────────────────────────────────────────────
class RealDatabase(Database):
    def __init__(self, connection_string: str):
        print(f"Connecting to {connection_string}...")  # expensive!
        self._conn_str = connection_string

    def query(self, sql: str) -> list[dict]:
        print(f"Executing query: {sql}")
        return [{"id": 1, "name": "Alice"}]   # simulate

    def execute(self, sql: str) -> int:
        print(f"Executing: {sql}")
        return 1

# ── Virtual Proxy: lazy init ──────────────────────────────────────
class LazyDatabaseProxy(Database):
    """Don't connect until first use."""

    def __init__(self, connection_string: str):
        self._conn_str = connection_string
        self._db: Optional[RealDatabase] = None

    def _get_db(self) -> RealDatabase:
        if self._db is None:
            self._db = RealDatabase(self._conn_str)
        return self._db

    def query(self, sql: str) -> list[dict]:
        return self._get_db().query(sql)

    def execute(self, sql: str) -> int:
        return self._get_db().execute(sql)

# ── Caching Proxy ─────────────────────────────────────────────────
class CachingDatabaseProxy(Database):
    """Cache SELECT query results in memory."""

    def __init__(self, real_db: Database, ttl_sec: int = 300):
        self._db  = real_db
        self._ttl = ttl_sec
        self._cache: dict[str, tuple[float, list]] = {}   # sql → (expires_at, result)

    def query(self, sql: str) -> list[dict]:
        now = time.time()
        if sql in self._cache:
            expires_at, result = self._cache[sql]
            if now < expires_at:
                print(f"Cache HIT: {sql}")
                return result

        result = self._db.query(sql)
        self._cache[sql] = (now + self._ttl, result)
        print(f"Cache MISS, stored: {sql}")
        return result

    def execute(self, sql: str) -> int:
        # Invalidate cache on writes
        self._cache.clear()
        return self._db.execute(sql)

# ── Protection Proxy ──────────────────────────────────────────────
class ProtectedDatabaseProxy(Database):
    """Check user permissions before allowing operations."""

    ALLOWED_QUERIES = {"SELECT"}
    WRITE_ROLES = {"admin", "writer"}

    def __init__(self, real_db: Database, user_role: str):
        self._db   = real_db
        self._role = user_role

    def query(self, sql: str) -> list[dict]:
        sql_upper = sql.strip().upper()
        if not any(sql_upper.startswith(q) for q in self.ALLOWED_QUERIES):
            raise PermissionError(f"Query not allowed: {sql[:50]}")
        return self._db.query(sql)

    def execute(self, sql: str) -> int:
        if self._role not in self.WRITE_ROLES:
            raise PermissionError(f"Role '{self._role}' cannot execute writes")
        return self._db.execute(sql)

# Demo
db = LazyDatabaseProxy("postgresql://localhost/mydb")
cached_db = CachingDatabaseProxy(db)
protected_db = ProtectedDatabaseProxy(cached_db, user_role="reader")

result = protected_db.query("SELECT * FROM users")
result = protected_db.query("SELECT * FROM users")   # cache hit


# Python's built-in proxy: __getattr__ delegation
class ServiceProxy:
    """Generic proxy using __getattr__ for transparent delegation."""

    def __init__(self, service, logger=None):
        self._service = service
        self._logger  = logger

    def __getattr__(self, name: str):
        attr = getattr(self._service, name)
        if callable(attr):
            def wrapper(*args, **kwargs):
                if self._logger:
                    self._logger.info(f"Calling {name}({args}, {kwargs})")
                result = attr(*args, **kwargs)
                if self._logger:
                    self._logger.info(f"{name} returned {result}")
                return result
            return wrapper
        return attr
```

**When to use:**
- Lazy loading (ORM relationships — SQLAlchemy lazy loading)
- API rate limiting proxy
- Security/authorization layer
- Distributed systems (gRPC stub is a remote proxy)
- Caching layer

---

## 4. Flyweight Pattern

**Intent:** Share common state between many objects to reduce memory usage.

```
Without Flyweight: 1M Character objects, each stores font+size+color+text
With Flyweight:    1M objects, each has position + reference to SHARED style

Intrinsic state (shared):   font, size, color, glyph data
Extrinsic state (unique):   position, selection state
```

```python
from dataclasses import dataclass

# ── Flyweight: shared state ───────────────────────────────────────
@dataclass(frozen=True)    # immutable + hashable → can be shared
class CharacterStyle:
    font:      str
    size:      int
    bold:      bool
    italic:    bool
    color:     str

    def render_info(self) -> str:
        b = "B" if self.bold else ""
        i = "I" if self.italic else ""
        return f"{self.font}{b}{i}/{self.size}/{self.color}"

# ── Flyweight Factory ─────────────────────────────────────────────
class StyleFactory:
    """Returns shared flyweight objects. Caches by style properties."""

    _styles: dict[tuple, CharacterStyle] = {}

    @classmethod
    def get_style(cls, font: str, size: int, bold: bool = False,
                   italic: bool = False, color: str = "black") -> CharacterStyle:
        key = (font, size, bold, italic, color)
        if key not in cls._styles:
            cls._styles[key] = CharacterStyle(font, size, bold, italic, color)
            print(f"Created new style: {key}")
        return cls._styles[key]

    @classmethod
    def count(cls) -> int:
        return len(cls._styles)

# ── Context: unique per character ─────────────────────────────────
@dataclass
class Character:
    char:    str          # the actual character
    x:       int          # position
    y:       int
    style:   CharacterStyle   # shared flyweight reference

    def display(self):
        return f"'{self.char}'@({self.x},{self.y}) style={self.style.render_info()}"

# ── Document ──────────────────────────────────────────────────────
class Document:
    def __init__(self):
        self.characters: list[Character] = []
        self._factory = StyleFactory

    def add_char(self, char: str, x: int, y: int,
                  font: str = "Arial", size: int = 12,
                  bold: bool = False, color: str = "black"):
        style = self._factory.get_style(font, size, bold, False, color)
        self.characters.append(Character(char, x, y, style))

    def memory_stats(self) -> dict:
        total_chars = len(self.characters)
        unique_styles = StyleFactory.count()
        import sys
        style_mem = unique_styles * sys.getsizeof(CharacterStyle("", 0, False, False, ""))
        char_mem  = total_chars * sys.getsizeof(Character("", 0, 0, self.characters[0].style)) if self.characters else 0

        return {
            "total_characters": total_chars,
            "unique_styles":    unique_styles,
            "estimated_savings_ratio": f"{total_chars / max(unique_styles, 1):.0f}x"
        }

# Demo
doc = Document()
# Add 10,000 characters with only 3 unique styles
for i in range(10000):
    if i % 3 == 0:
        doc.add_char("a", i % 80, i // 80, "Arial", 12)
    elif i % 3 == 1:
        doc.add_char("b", i % 80, i // 80, "Arial", 14, bold=True)
    else:
        doc.add_char("c", i % 80, i // 80, "Times", 12, color="red")

stats = doc.memory_stats()
print(stats)
# {'total_characters': 10000, 'unique_styles': 3, 'estimated_savings_ratio': '3333x'}


# Real-world: Game particle system flyweight
@dataclass(frozen=True)
class ParticleType:
    """Shared: color, texture, physics properties."""
    name:     str
    color:    str       # shared texture data
    mass:     float
    drag:     float

@dataclass
class Particle:
    """Unique: position, velocity per particle."""
    x:         float
    y:         float
    vx:        float
    vy:        float
    ptype:     ParticleType   # shared flyweight

    def update(self, dt: float):
        self.x  += self.vx * dt
        self.y  += self.vy * dt
        self.vx *= (1 - self.ptype.drag * dt)
        self.vy *= (1 - self.ptype.drag * dt)

class ParticleSystem:
    def __init__(self):
        self.particles: list[Particle] = []
        self._types: dict[str, ParticleType] = {}

    def register_type(self, name: str, color: str,
                       mass: float, drag: float):
        self._types[name] = ParticleType(name, color, mass, drag)

    def spawn(self, type_name: str, x: float, y: float,
               vx: float, vy: float):
        ptype = self._types[type_name]
        self.particles.append(Particle(x, y, vx, vy, ptype))

    def update(self, dt: float):
        for p in self.particles: p.update(dt)
```

---

## 5. Pattern Comparison

| Pattern | Intent | Key Participants | Common Use Cases |
|---------|--------|-----------------|-----------------|
| Command | Encapsulate request as object | Command, Invoker, Receiver | Undo/redo, job queues, macro recording |
| Composite | Tree of uniform objects | Component, Leaf, Composite | File system, GUI widgets, org hierarchy |
| Proxy | Control access to object | Proxy, RealSubject, Subject | Lazy load, caching, auth, remote calls |
| Flyweight | Share common state | Flyweight, Factory, Context | Characters, particles, icons, tiles |

---

## 6. Interview Questions

**Q1: When would you use the Command pattern vs Strategy pattern?**
> Strategy: swap algorithms at runtime (different sort algorithms). Command: encapsulate action + state for later execution, undo, or queuing. Key difference: Command stores receiver + action as an object that can be queued, logged, or reversed. Strategy is just a behavior swap. Use Command when you need undo history, task queues, or audit logs.

**Q2: How does Composite pattern help with recursive structures?**
> By making Leaf and Composite implement the same interface (Component), client code treats both uniformly. Operations like `size()`, `render()`, `display()` work recursively without type checking. The caller doesn't need to know if it's calling on a file or directory — the tree structure handles recursion internally. Follows Open/Closed: add new leaf/composite types without changing client code.

**Q3: What is the difference between Decorator and Proxy?**
> Both wrap another object but for different purposes. Proxy controls access (lazy load, auth, caching) — interface is identical to real object. Decorator adds behavior (logging, compression, encryption) — same interface but enhanced. Key: Proxy usually manages lifecycle of wrapped object; Decorator usually doesn't. They can look identical in code — the intent and responsibility differ.

**Q4: How does Flyweight reduce memory? What is intrinsic vs extrinsic state?**
> Intrinsic state: shared across instances (font, glyph bitmap, particle texture). Extrinsic state: unique per instance (position, selection, velocity). Flyweight stores only intrinsic state and is shared via a factory. Extrinsic state is stored outside (in the context object or passed as method parameters). For 1M characters with 5 unique fonts: 5 Flyweight objects instead of 1M, each storing font data. Memory reduction proportional to sharing ratio.

**Q5: How do you implement undo/redo with Command pattern?**
> Two stacks: history and redo. `execute(cmd)`: call cmd.execute(), push to history, clear redo. `undo()`: pop from history, call cmd.undo(), push to redo. `redo()`: pop from redo, call cmd.execute(), push to history. Commands must be reversible: store enough state in execute() to reconstruct undo (e.g., DeleteCommand saves deleted text). Composite commands (MacroCommand) undo in reverse order.
