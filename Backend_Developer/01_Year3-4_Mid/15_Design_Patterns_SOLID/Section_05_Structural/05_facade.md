# Facade

## 1. Intent

Provide a **simple, unified interface** to a complex subsystem. The Facade *narrows* what callers see.

## 2. Problem

A subsystem (a library, a cluster of services, an orchestration of 5 SDK calls) exposes a wide API. Callers only need a fraction. Forcing them to learn the whole API:
- Couples them to internal classes.
- Repeats orchestration boilerplate in every caller.

Symptoms:
- A workflow of 6+ method calls reproduced in every service.
- Callers depending on internal classes of a library.
- "Use only these 3 of the 80 functions" tribal knowledge.

## 3. Solution (UML sketch)

```
                ┌─────────────────┐
   Client ────> │     Facade      │
                ├─────────────────┤
                │ +simple_op()    │
                └─────────────────┘
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
   ┌─────────┐   ┌─────────┐    ┌──────────┐
   │ SubsysA │   │ SubsysB │    │ SubsysC  │
   └─────────┘   └─────────┘    └──────────┘
```

## 4. Participants

- **Facade** — narrow interface; orchestrates subsystem calls.
- **Subsystem classes** — do the real work; not hidden, just not promoted to callers.
- **Client** — uses Facade, blissfully unaware of internals.

## 5. Python implementation

```python
# Subsystem: 4 separate clients
class S3:
    def upload(self, key, data): ...
    def get_url(self, key): ...
class ImageProcessor:
    def resize(self, data, w, h): ...
    def thumbnail(self, data, size): ...
class DB:
    def save_media(self, owner_id, url): ...
class CDN:
    def purge(self, url): ...

# Facade
class MediaService:
    def __init__(self, s3: S3, ip: ImageProcessor, db: DB, cdn: CDN):
        self.s3, self.ip, self.db, self.cdn = s3, ip, db, cdn

    def upload_profile_picture(self, owner_id: int, raw: bytes) -> str:
        thumb = self.ip.thumbnail(raw, size=256)
        key   = f"users/{owner_id}/avatar.jpg"
        self.s3.upload(key, thumb)
        url   = self.s3.get_url(key)
        self.db.save_media(owner_id, url)
        self.cdn.purge(url)
        return url

# Client
media = MediaService(S3(), ImageProcessor(), DB(), CDN())
url = media.upload_profile_picture(1, raw_bytes)
```

The route handler calls one method instead of orchestrating four subsystems.

## 6. Backend examples

- **`requests` library** — `requests.get(url)` is a facade over `Session`, `PreparedRequest`, `Adapter`, `URLLib3 ConnectionPool`. You *can* drop down; you usually don't.
- **Django's `User.objects.create_user(...)`** — facade over hashing, saving, signals, default group assignment.
- **`celery.shared_task` / `task.delay`** — facade over broker connection, serialization, routing.
- **`pandas.read_csv`** — facade over parser, dtype inference, NA handling, chunked reading.
- **`subprocess.run`** — facade over `Popen`, pipes, wait, stream capture.

## 7. Pros / Cons

**Pros**
- Easier onboarding (callers learn one method, not a subsystem).
- Decouples callers from internal classes.
- Centralises orchestration / cross-cutting policies (logging, retry, auth).

**Cons**
- Can hide too much — escape hatches needed for advanced callers.
- Can grow into a God object if it accumulates every workflow.

**Don't use when**
- Subsystem is already simple.
- Different callers need very different orchestrations — multiple narrow facades > one fat facade.

## 8. Facade vs Adapter vs Proxy — the wrapper family

| | Goal | Interface |
|---|---|---|
| **Adapter** | Translate to expected interface | Different in / different out |
| **Facade** | Simplify a wide subsystem | Narrow new interface; subsystem unchanged |
| **Proxy** | Control access | Same interface in / same out |
| **Decorator** | Add behaviour | Same interface; recursive wrap |

## 9. Related patterns

- **Mediator** — Facade is one-way (callers → subsystem). Mediator coordinates many peers two-way.
- **Singleton** — Facades are often instantiated once.
- **Abstract Factory** — sometimes used inside a Facade to assemble the right subsystem.

## 9. Self-check

1. Facade vs Adapter, in one sentence.
2. Give two backend examples of Facade you've used today without thinking.
3. When does a Facade grow into a God object, and how to prevent it?
4. Why must a Facade still allow access to the subsystem?
5. Difference between Facade and Mediator.
