# 99 · SOLID in FastAPI + Django (Where each principle lives in your stack)

Concrete sightings — so the principles stop feeling academic.

## Single Responsibility (SRP)

### FastAPI
- **Route handler vs service vs repository** — three layers, three reasons to change.
  ```python
  # routes/orders.py — only HTTP concerns
  @router.post("/orders")
  def create(payload: OrderIn, svc: OrderService = Depends()):
      return svc.place(payload)
  ```
- **Pydantic models** — one model per use-case (`OrderIn`, `OrderOut`, `OrderDB`) instead of one fat `Order`. Each has a single reason to change.

### Django / DRF
- **`models` vs `serializers` vs `views` vs `signals`** — Django's layout *is* SRP. Resist putting business logic in `models.py` just because Django docs put it there.
- **Custom `Manager` classes** — pull complex queries out of the model body (`Order.objects.unpaid()` lives on `OrderManager`, not on `Order`).

## Open/Closed (OCP)

### FastAPI
- **Dependency overrides** — add a new auth strategy by registering a new `Depends`, no edit to handlers.
- **Middleware stack** — drop in a logging or tracing middleware; the framework doesn't change.

### Django
- **Custom user model** via `AUTH_USER_MODEL` — extend without forking auth.
- **DRF generic views** — override `get_queryset`, `perform_create`; the base view is closed.
- **Signals** — `post_save.connect(send_welcome_email)`; the model never learns about emails.

## Liskov Substitution (LSP)

### FastAPI / starlette
- All response types (`JSONResponse`, `HTMLResponse`, `StreamingResponse`) substitute for `Response`. Anywhere `Response` works, all of them work.

### Django
- DB backends — `sqlite`, `postgres`, `mysql` all conform to the same ORM contract; tests run on sqlite, prod on postgres.
- **Antipattern alert:** custom `Manager` that silently filters out soft-deleted rows is an LSP violation — callers expect "all rows" and get a subset. Use an explicit method (`Order.all_objects.all()`).

## Interface Segregation (ISP)

### FastAPI
- Split request/response models so each endpoint depends only on the fields it needs (`UserCreate` vs `UserUpdate` vs `UserPublic`).

### Django
- **Class-based view mixins** — `ListModelMixin`, `CreateModelMixin`, … you take only the capabilities you want.
- **DRF permission classes** — `IsAuthenticated`, `IsAdminUser`, `IsOwner`; compose per view instead of one God permission class.

## Dependency Inversion (DIP)

### FastAPI
- `Depends()` **is** DI in two characters. Inject repos, clients, settings.
  ```python
  def get_db() -> Session: ...
  def get_cache() -> Cache: ...
  
  @app.get("/users/{uid}")
  def read_user(uid: int, db = Depends(get_db), cache = Depends(get_cache)):
      ...
  ```
- **Override in tests** with `app.dependency_overrides`.

### Django
- DI is less first-class. Mechanisms used in practice:
  - **Settings module** (`settings.EMAIL_BACKEND`) — concrete chosen at startup, business code addresses an abstract symbol.
  - **`django.contrib.auth.get_user_model()`** instead of importing a concrete `User`.
  - **`apps.get_model('app','Model')`** for cross-app refs.
- For complex projects, people add a DI container (e.g., `dependency-injector`) or roll their own factory functions.

## SOLID compliance checklist (use before merging a PR)

- [ ] **SRP** — every class/file has one reason to change. Name it out loud.
- [ ] **OCP** — adding the next variant requires *new* code, not editing existing methods.
- [ ] **LSP** — substituting any subclass/protocol implementation does not break callers.
- [ ] **ISP** — clients depend only on the methods they actually call.
- [ ] **DIP** — business logic imports protocols, not concretes; concretes wired at the edge.

If you can answer all 5 with a sentence each, the PR is sound.

## Self-check

1. Where does the composition root live in a FastAPI project?
2. Why are Django signals an OCP win? What's the cost?
3. Give a likely LSP violation hidden in a custom Django `Manager`.
4. Why does ISP feel "free" in Python compared to Java?
5. Name two ways Django achieves DI without a formal DI container.
