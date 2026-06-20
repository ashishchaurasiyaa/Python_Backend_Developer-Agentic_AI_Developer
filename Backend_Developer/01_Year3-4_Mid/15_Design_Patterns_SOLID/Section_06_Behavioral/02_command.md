# Command

## 1. Intent

Encapsulate a request as an **object**, so you can: parameterize callers, queue/log/schedule operations, and support undo.

## 2. Problem

You want to decouple "the thing that triggers an action" from "the thing that performs it" — and you want the action to be a first-class value you can pass around, store, retry, or undo.

Examples:
- Job queue: producer creates a job, worker picks it up later.
- Undo/redo stack.
- Macro recording.
- Transactional outbox.

## 3. Solution (UML sketch)

```
┌──────────┐       ┌─────────────────┐
│ Invoker  │──────>│  <<Command>>    │
└──────────┘       ├─────────────────┤
                   │ +execute()      │
                   └─────────────────┘
                          △
                          │
                ┌──────────────────┐         ┌────────────┐
                │ ConcreteCommand  │────────>│ Receiver   │
                ├──────────────────┤  uses   └────────────┘
                │ +execute()       │
                └──────────────────┘

┌──────────┐
│  Client  │── creates ConcreteCommand, sets Receiver, gives to Invoker
└──────────┘
```

## 4. Participants

- **Command** — interface with `execute()`.
- **ConcreteCommand** — knows the receiver and the parameters; calls receiver.
- **Receiver** — does the actual work.
- **Invoker** — holds and triggers commands (doesn't know what they do).
- **Client** — wires commands and receivers together.

## 5. Python implementation

### Classical

```python
from typing import Protocol

class Command(Protocol):
    def execute(self) -> None: ...
    def undo(self) -> None: ...

class TextEditor:                       # Receiver
    def __init__(self): self.text = ""
    def append(self, s):  self.text += s
    def remove(self, n):  self.text = self.text[:-n]

class TypeCommand:                       # ConcreteCommand
    def __init__(self, editor: TextEditor, s: str):
        self.editor, self.s = editor, s
    def execute(self): self.editor.append(self.s)
    def undo(self):    self.editor.remove(len(self.s))

class CommandQueue:                      # Invoker
    def __init__(self): self.stack: list[Command] = []
    def run(self, cmd: Command):
        cmd.execute(); self.stack.append(cmd)
    def undo(self):
        if self.stack: self.stack.pop().undo()

ed = TextEditor()
q  = CommandQueue()
q.run(TypeCommand(ed, "Hello "))
q.run(TypeCommand(ed, "world"))
print(ed.text)      # 'Hello world'
q.undo()
print(ed.text)      # 'Hello '
```

### Pythonic — `Callable` as Command

In Python any callable already satisfies "execute". For one-shot Commands:

```python
from dataclasses import dataclass
from typing import Callable

@dataclass
class Job:
    fn: Callable
    args: tuple = ()
    kwargs: dict = None
    def execute(self):
        return self.fn(*self.args, **(self.kwargs or {}))

queue: list[Job] = []
queue.append(Job(print, ("hi",)))
queue.append(Job(send_email, ("a@b", "subj", "body")))

for j in queue: j.execute()
```

Celery's `task.s(...)` signature is literally this.

## 6. Backend examples

- **Celery** — `task.delay()` serialises a Command (task name + args) to the broker.
- **Django management commands** — each `Command.handle()` is a Command object.
- **Django admin actions** — bulk operations registered as callables operating on querysets.
- **GraphQL mutations / REST POST handlers** — each is essentially a Command.
- **Transactional outbox / event sourcing** — store Commands in DB; replay.
- **CI/CD pipelines** — each step is a Command; the pipeline is the Invoker.

## 7. Pros / Cons

**Pros**
- Decouples invocation from implementation.
- Commands are storable, queueable, retryable.
- Enables undo/redo, audit logs, deferred execution.

**Cons**
- One class per action — verbose for simple cases.
- Undo is genuinely hard for non-trivial actions (side effects, idempotency).

**Don't use when**
- The action is invoked once, immediately. A function call is enough.
- You don't need queueing/undo/logging/retry.

## 8. Related patterns

- **Memento** — stores state for undo, often paired with Command.
- **Composite** — MacroCommand: a command made of commands.
- **Chain of Responsibility** — handlers process Commands.
- **Observer** — Commands can be triggered by events.

## 9. Self-check

1. What four capabilities does turning an action into an object enable?
2. How is Celery's `task.delay` a Command?
3. What's the hard part about undo?
4. When is Command overkill in Python?
5. Difference between Command and Strategy.
