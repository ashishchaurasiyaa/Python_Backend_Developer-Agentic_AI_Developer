# Flask Essentials vs FastAPI — WSGI vs ASGI, Blueprints vs Routers, Migration Story

> **Interview angle:** "Tumne stock screener FastAPI me kyun banaya, Flask me kyun nahi?" — yeh sabse common cross-framework question hai. Galat jawab: "FastAPI fast hai." Sahi jawab: protocol (WSGI vs ASGI), validation layer (Pydantic), contract generation (OpenAPI), aur DI — chaar concrete cheezein, har ek ke saath aapke project ka specific use-case.

**One-line truth:** Flask ek **WSGI** framework hai jahan har request ek worker/thread ko *block* karke rakhti hai aur context **implicit globals** (`request`, `g`) se aata hai; FastAPI ek **ASGI** framework hai jahan I/O par request *await* hoti hai aur context **explicit dependencies** se aata hai. Baaki sab (speed, docs, validation) isi do differences ka natural consequence hai.

---

## Quick Reference Card

| Dimension | Flask 3.x | FastAPI |
|---|---|---|
| Protocol | WSGI (sync callable) | ASGI (async callable) |
| Server | gunicorn / uWSGI / waitress | uvicorn / hypercorn / granian |
| Concurrency per worker | 1 (sync worker), N threads (gthread), N greenlets (gevent) | thousands of awaiting coroutines |
| Route grouping | `Blueprint` | `APIRouter` |
| Request context | `request` / `g` / `current_app` — implicit proxies (ContextVar-backed) | function params + `Depends()` — explicit |
| Validation | manual, or Marshmallow / WTForms / pydantic bolted on | Pydantic v2 built into signature |
| Serialization | `jsonify()` + you shape the dict | `response_model=` (filters + validates output) |
| API docs | flask-smorest / apispec / flasgger | auto `/docs` + `/openapi.json`, zero config |
| DI | none (extensions + `g` + factory closures) | first-class `Depends` with caching, overrides, yield-teardown |
| Testing | `app.test_client()` | `TestClient(app)` (httpx-backed) + `dependency_overrides` |
| Type hints | optional, decorative | load-bearing (drive parsing, validation, docs) |
| Background work | Celery / RQ | Celery / arq / `BackgroundTasks` |
| WebSockets | Flask-SocketIO (separate stack) | native (`@app.websocket`) |
| Best at | server-rendered Jinja apps, admin panels, small internal tools | JSON APIs, I/O fan-out, streaming, typed contracts |

---

## 1. WSGI vs ASGI — Asli Difference Yahi Hai

Baaki sab isi se derive hota hai. Dono protocols ka core ek function signature hai:

```python
# WSGI (PEP 3333) — Flask ka world.
# Ek SYNC callable. Return karte waqt hi response complete hai.
def wsgi_app(environ, start_response):
    #  environ        = dict with CGI-ish keys: REQUEST_METHOD, PATH_INFO, wsgi.input...
    #  start_response = callback jise status + headers dete ho
    start_response("200 OK", [("Content-Type", "text/plain")])
    return [b"hello"]                  # iterable of bytes — bas.

# ASGI — FastAPI/Starlette ka world.
# Ek ASYNC callable. Response ek stream of EVENTS hai.
async def asgi_app(scope, receive, send):
    #  scope   = dict: {"type": "http"|"websocket"|"lifespan", "path": ..., "headers": ...}
    #  receive = await karke incoming events lo (request body chunks, ws messages, disconnect)
    #  send    = await karke outgoing events bhejo (response start, body chunks)
    await send({"type": "http.response.start", "status": 200,
                "headers": [(b"content-type", b"text/plain")]})
    await send({"type": "http.response.body", "body": b"hello"})
```

Teen consequences jo directly interview me bolne layak hain:

1. **Concurrency model.** WSGI callable return hone tak worker busy hai. Agar wo function ke andar `requests.get()` 200ms le raha hai, wo worker 200ms tak *kuch nahi* kar sakta. ASGI me `await httpx.get()` par event loop us coroutine ko suspend karke doosri request uthata hai — **ek** worker hazaaron in-flight requests hold kar sakta hai (jab tak wo I/O par wait kar rahi hain).
2. **Protocols.** WSGI scope me sirf ek HTTP request-response hai. ASGI `scope["type"]` me `websocket` aur `lifespan` bhi hai — isliye FastAPI me WebSockets, SSE aur startup/shutdown hooks native hain, jabki Flask me WebSockets ke liye alag stack (Flask-SocketIO + eventlet/gevent) chahiye.
3. **Streaming.** ASGI me response body multiple `send()` events hai, isliye SSE/streaming natural hai. WSGI me generator return kar sakte ho par backpressure aur client-disconnect detection weak hai.

> **Senior Tip:** ASGI "faster" nahi hai per-request. Ek CPU-bound request ASGI par utna hi time legi. Fayda **concurrency density** me hai — I/O wait ke dauraan worker free ho jaata hai. Isliye ASGI ka gain CPU-bound workload me lagbhag zero hai; I/O-heavy (DB, HTTP fan-out, LLM calls) me dramatic hai.

---

## 2. Flask ka Mental Model — App Factory, Blueprint, Context

### 2.1 App Factory Pattern

Module-level `app = Flask(__name__)` chhote scripts me theek hai, par production me **factory** standard hai:

```python
# app/__init__.py
from flask import Flask
from .extensions import db, migrate           # extension objects, app se UNBOUND
from .api.stocks import stocks_bp

def create_app(config_object="config.Production") -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)

    # "init_app" pattern — extension ko app ke saath ab bind karte hain.
    db.init_app(app)
    migrate.init_app(app, db)

    app.register_blueprint(stocks_bp, url_prefix="/api/stocks")

    @app.errorhandler(404)
    def not_found(e):
        return {"error": "not_found"}, 404

    return app
```

Factory kyun: (a) har test alag app instance bana sakta hai alag config ke saath, (b) circular imports se bachte ho (extensions ek alag module me rehte hain), (c) ek process me multiple apps mount kar sakte ho.

**FastAPI equivalent:** wahi pattern kaam karta hai (`def create_app() -> FastAPI`), bas zaroori kam hai — kyunki config Pydantic `BaseSettings` se aata hai aur DB session `Depends` se, dono app object par hang nahi karte. Testing me `dependency_overrides` factory ki 80% zaroorat khatam kar deta hai.

### 2.2 Request Context, `g`, aur "Thread-Locals"

Flask ka signature move: `request` ek argument nahi hai, ek **global import** hai.

```python
from flask import request, g, current_app, session

@app.route("/whoami")
def whoami():
    ip = request.remote_addr        # kaunsi request? "current" wali.
    return {"ip": ip, "rid": g.request_id}
```

Yeh kaam kaise karta hai: `request`/`g`/`current_app`/`session` asli objects nahi, **`LocalProxy`** objects hain. Har attribute access par proxy ek context-local variable lookup karta hai aur usme rakhe *actual* object par forward karta hai. Flask har request ke shuru me `RequestContext` push karta hai aur end me pop.

```
                    ┌─────────────────────────────────────────┐
 request aayi  ───► │ app.push(RequestContext)                │
                    │   _cv_request.set(ctx)   ← ContextVar    │
                    └─────────────────────────────────────────┘
                                   │
      view function  `request.args` ─► LocalProxy.__getattr__
                                   ─► _cv_request.get().request.args
                                   │
                    ┌─────────────────────────────────────────┐
 response gayi ───► │ ctx.pop()  → g destroyed, teardown fired │
                    └─────────────────────────────────────────┘
```

**Accuracy detail jo log galat bolte hain:** Flask 2.0 se yeh **thread-locals nahi, `contextvars.ContextVar` hain** (`flask.globals._cv_request`, `_cv_app`). Isi wajah se Flask ke async views me bhi context sahi propagate hota hai. Interview me "Flask uses thread-locals" bolna 2019 tak sahi tha; aaj sahi line hai: *"Werkzeug's `LocalProxy` over a `ContextVar`, historically thread-locals."*

`g` = "globals for **one** request" (naam confusing hai). Har request ka `g` naya hai, request khatam hote hi mar jaata hai:

```python
@app.before_request
def load_user():
    g.request_id = request.headers.get("X-Request-ID", str(uuid4()))
    g.user = authenticate(request.headers.get("Authorization"))   # har view me available

@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()
```

**Trade-off:** `g` bahut convenient hai — koi bhi helper function, kisi bhi depth par, `from flask import g` karke user utha sakta hai. Yahi uska problem bhi hai:

- Function signature jhoot bolti hai — `def compute_score(symbol)` dekh ke pata nahi chalta ki wo andar `g.user` aur `g.db` bhi use kar raha hai.
- Test karne ke liye poora request context fake karna padta hai (`app.test_request_context()`), sirf argument pass nahi kar sakte.
- Static analysis / type checker `g.anything` par kuch nahi bol sakta — `g` untyped hai.

FastAPI ka `Depends` isi ka ulta hai: **implicit ambient state → explicit parameter**.

```python
# FastAPI: wahi cheez, par signature me likhi hui
async def whoami(user: Annotated[User, Depends(get_current_user)],
                 rid: Annotated[str, Depends(get_request_id)]):
    return {"user": user.id, "rid": rid}
# Test: dependency_overrides[get_current_user] = lambda: FakeUser()  — bas.
```

> **Senior Tip:** FastAPI me bhi ek "g jaisa" escape hatch hai — `request.state.x` (middleware set karta hai, endpoint padhta hai). Wo `g` ke saare downsides carry karta hai. Use karo sirf tab jab value cross-cutting ho aur har endpoint ki signature me dalna shor ho (jaise request-id for logging), warna `Depends`.

### 2.3 Blueprints

Blueprint = **deferred registration ka bundle**. Blueprint par decorator lagate ho, par route tab tak register nahi hota jab tak `app.register_blueprint()` na ho.

```python
from flask import Blueprint

stocks_bp = Blueprint("stocks", __name__)

@stocks_bp.route("/<symbol>")
def get_stock(symbol):
    ...

# app me:
app.register_blueprint(stocks_bp, url_prefix="/api/stocks")
# endpoint naam ban gaya "stocks.get_stock" → url_for("stocks.get_stock", symbol="TCS")
```

Blueprint ke apne hooks hote hain — `@bp.before_request` (sirf is blueprint ke routes par), `@bp.errorhandler` (blueprint ke andar raise hui exceptions), aur `@bp.app_errorhandler` (poore app ke liye, blueprint file me likha hua).

---

## 3. Blueprint vs APIRouter — Side by Side

Structurally yeh lagbhag 1:1 map karta hai; asli farq **cross-cutting concerns kahan attach hote hain** me hai.

```python
# ─────────────────────── FLASK ───────────────────────
from flask import Blueprint, g, jsonify, request

stocks_bp = Blueprint("stocks", __name__)

@stocks_bp.before_request                 # ← auth: har route se pehle, implicitly
def require_key():
    if request.headers.get("X-API-Key") != CONF_KEY:
        return jsonify(error="unauthorized"), 401
    g.db = SessionLocal()                 # ← per-request resource, g par

@stocks_bp.teardown_request               # ← teardown alag hook me
def close_db(exc):
    g.pop("db", lambda: None)

@stocks_bp.get("/<symbol>")
def get_stock(symbol):                    # ← db kahan se aaya? g se. signature chup hai.
    row = g.db.get(Stock, symbol)
    if row is None:
        return jsonify(error="not_found"), 404
    return jsonify(symbol=row.symbol, price=row.price)   # shape manually likhi

app.register_blueprint(stocks_bp, url_prefix="/api/stocks")
```

```python
# ─────────────────────── FASTAPI ───────────────────────
from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated

router = APIRouter(
    prefix="/api/stocks",
    tags=["stocks"],                      # ← /docs me grouping
    dependencies=[Depends(require_key)],  # ← auth: router-level, DECLARED
    responses={401: {"description": "Bad API key"}},
)

def get_db():                             # ← yield-dependency = setup + teardown ek jagah
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/{symbol}", response_model=StockOut)   # ← output contract enforced
async def get_stock(symbol: str, db: Annotated[Session, Depends(get_db)]):
    row = db.get(Stock, symbol)                     # ← db signature me hai
    if row is None:
        raise HTTPException(404, "not_found")
    return row                                      # ← response_model filter karega

app.include_router(router)
```

| Concern | Flask Blueprint | FastAPI APIRouter |
|---|---|---|
| URL prefix | `register_blueprint(..., url_prefix=)` (registration site) | `APIRouter(prefix=)` (definition site) |
| Auth for whole group | `@bp.before_request` returning a response | `APIRouter(dependencies=[Depends(auth)])` |
| Per-request resource | set on `g`, teardown in separate hook | one `yield` dependency, setup+teardown together |
| Errors | `@bp.errorhandler(Exc)` | `@app.exception_handler(Exc)` (app-level only) |
| Nesting | `bp.register_blueprint(child_bp)` (Flask 2.0+) | `router.include_router(child_router)` |
| Docs grouping | manual (flask-smorest `Blp`) | `tags=` → automatic |
| Response shape | `jsonify(...)` — aapki zimmedari | `response_model=` — validate + filter |

**Ek asymmetry yaad rakho:** FastAPI me `exception_handler` **app-level** hota hai, router-level nahi. Flask me `@bp.errorhandler` sirf us blueprint ke liye scope hota hai. Agar FastAPI me per-router error mapping chahiye, toh custom `APIRoute` class ya router-scoped middleware likhni padegi.

---

## 4. Flask 3.x Async Views — Bada Caveat

Flask 2.0+ me `async def` views allowed hain (`pip install "flask[async]"`, jo `asgiref` laata hai). Log dekhte hain "arre Flask me bhi async hai" — aur galat conclusion nikal lete hain.

```python
# Flask 3.x — yeh VALID hai aur chalega:
@app.get("/quote/<symbol>")
async def quote(symbol):
    async with httpx.AsyncClient() as c:
        r = await c.get(f"https://api.example.com/{symbol}")
    return r.json()
```

Andar kya hota hai:

```
Flask (WSGI) worker thread
   │
   ├─ view async hai? → asgiref.sync.async_to_sync(view)
   │
   ├─ ek NAYA event loop banao (ya per-thread loop reuse karo)
   │
   ├─ loop.run_until_complete(coroutine)   ← thread YAHIN block hai
   │       (loop me sirf YEH ek coroutine hai — koi doosri request nahi)
   │
   └─ result mila → loop se bahar → WSGI response return
```

**Isliye:** `await` ke dauraan wo worker thread **kisi doosri request ko serve nahi karta**. Concurrency abhi bhi `workers × threads` hi hai, jaise sync view me thi. Overhead ulta *badh* gaya (per-request event loop setup).

Toh Flask async views kis kaam ki hain?

- **Ek request ke andar internal fan-out.** `asyncio.gather()` se 5 upstream APIs parallel call kar sakte ho — 5×200ms serial ki jagah ~200ms. Yeh real win hai.
- Async-only libraries (kuch SDKs) ko call karne ke liye.

Kis kaam ki **nahi**: server ki throughput/connection-scaling badhane ke liye. Wo WSGI protocol ki limitation hai, view function ki nahi.

> **Interview line:** "Flask 3 async views `async_to_sync` ke through chalte hain — worker thread coroutine ke complete hone tak block rehta hai. Intra-request fan-out ke liye useful, cross-request concurrency ke liye bekaar, kyunki bottleneck WSGI protocol hai jo ek callable ke return par response finalize karta hai."

Ulta case bhi jaan lo: **FastAPI me `def` (sync) endpoint** likho toh Starlette use anyio threadpool (default 40 threads) me bhej deta hai — yaani gunicorn-gthread jaisa behaviour. Aur `async def` ke andar blocking call (`time.sleep`, sync `psycopg2`) likh do toh **poora event loop freeze** — Flask se bhi bura. (Detail: `39_async_def_vs_def_threadpool_deep.md`.)

---

## 5. Deployment — gunicorn+gevent vs uvicorn

```bash
# ── Flask (WSGI) ─────────────────────────────────────────────
gunicorn -w 4 "app:create_app()"                       # sync worker
gunicorn -w 4 -k gthread --threads 8 "app:create_app()"  # threaded
gunicorn -w 4 -k gevent --worker-connections 1000 app:app  # greenlets
```

| Worker | Concurrency per worker | Kaise | Dhyan |
|---|---|---|---|
| `sync` (default) | **1** | ek request, poori | Simplest, predictable. 4 workers = 4 concurrent requests. Slow upstream = instant queue. |
| `gthread` | `--threads N` | OS threads | I/O wait par GIL release hota hai, isliye I/O-bound me kaam karta hai. Memory per thread ~8MB stack. Realistic ceiling: dozens. |
| `gevent` / `eventlet` | 100s–1000s | greenlets + **monkey-patching** | `monkey.patch_all()` socket/time/threading ko replace karta hai taaki blocking calls yield karein. |

**gevent ka asli catch (yahi interview me pucha jaata hai):** monkey-patching *implicit* aur *global* hai. Jo bhi library C-level socket use karti hai (kuch DB drivers, `grpcio`, native extensions) wo patch nahi hoti — wo call poore hub ko block kar degi, aur debug karna narak hai kyunki traceback me kuch normal dikhta hai. Patch ko `import` se **pehle** karna padta hai, warna half-patched state milti hai. Yaani: gevent async-jaisi concurrency deta hai *bina* async/await likhe, par cost hai "kaunsi library patch-safe hai" ka permanent tax.

```bash
# ── FastAPI (ASGI) ───────────────────────────────────────────
uvicorn app:app --host 0.0.0.0 --port 8000 --workers 4
# ya process-manager ke liye gunicorn ke saath:
gunicorn -w 4 -k uvicorn_worker.UvicornWorker app:app     # pip install uvicorn-worker
```

Note: `uvicorn.workers.UvicornWorker` (uvicorn ke andar wala) ab **deprecated** hai — alag `uvicorn-worker` package use karo, ya seedha `uvicorn --workers`. Kubernetes me generally `uvicorn --workers 1` per pod aur scaling replicas se karte hain (per-pod CPU limit ke saath multiple workers ka koi matlab nahi).

**Sizing mental model:**

```
WSGI sync:    max in-flight = workers                     (e.g. 4)
WSGI gthread: max in-flight = workers × threads           (e.g. 4 × 8 = 32)
WSGI gevent:  max in-flight = workers × worker_connections (e.g. 4 × 1000, agar patching sahi hai)
ASGI uvicorn: max in-flight = workers × (jitni coroutines memory allow kare)
              — practical limit DB connection pool aur upstream rate limits banti hain, framework nahi
```

Yeh aakhri line important hai: FastAPI par jaate hi bottleneck framework se hat kar **downstream** par chala jaata hai. 5000 concurrent requests accept kar lena aur 10-connection Postgres pool rakhna = 4990 requests pool par queue. ASGI me connection pooling, timeouts aur circuit breakers *zyada* zaroori ho jaate hain, kam nahi.

---

## 6. "Faster" — Numbers ko Honestly Kaise Bolein

Interview me raw RPS quote karna trap hai (agla sawaal: "kis hardware par? kis payload par?"). Jo bolna chahiye:

| Scenario | Flask (gunicorn sync, 4w) | FastAPI (uvicorn, 4w) | Kyun |
|---|---|---|---|
| Trivial JSON echo, no I/O | baseline | ~2–4× throughput | Starlette ka lighter request path + no WSGI env building; farq framework overhead ka hai, magic ka nahi |
| Endpoint with 200ms upstream HTTP | ~20 req/s ceiling (4 workers ÷ 0.2s) | 1000s req/s, latency flat | Yahi asli farq hai — await par worker free |
| Pure CPU work (hashing, pandas) | same | **same ya thoda kharab** | Event loop CPU ko fast nahi karta; `async def` me daala toh sab freeze |
| Request validation (10-field model) | manual `if` checks ya Marshmallow | Pydantic v2 (Rust core), Marshmallow se ~5–20× tez | Validation ab framework me hai, aapke code me nahi |

**Bolne ka tarika:** "Hello-world benchmarks me FastAPI/Starlette ka farq framework overhead ka hai — real apps me wo noise hai. Jo farq matter karta hai wo concurrency model ka hai: 200ms upstream call par ek sync gunicorn worker 5 req/s karta hai, ek uvicorn worker hazaaron in-flight rakh sakta hai. Maine apne load test me X dekha tha — number machine-dependent hai, shape nahi."

> **Senior Tip:** Agar interviewer numbers push kare aur aapne khud measure nahi kiya, toh bol do: "measure nahi kiya, isliye number nahi bolunga — lekin bottleneck kahan hoga wo bata sakta hoon." Yeh galat number bolne se hamesha behtar score karta hai.

---

## 7. Extensions Ecosystem Mapping

Flask ki sabse badi taakat uska extension ecosystem hai. Migration plan banate waqt yeh table hi asli homework hai:

| Flask extension | Kya karta tha | FastAPI equivalent | Note |
|---|---|---|---|
| **Flask-SQLAlchemy** | session lifecycle + `db.Model` base | **plain SQLAlchemy 2.0** + `Depends(get_db)` | FastAPI me wrapper ki zaroorat nahi — `yield` dependency session ka lifecycle handle kar deti hai |
| **Flask-Migrate** | Alembic wrapper (`flask db upgrade`) | **Alembic** directly (`alembic upgrade head`) | Wrapper hi hata do; `08_pydantic_settings_alembic.md` dekho |
| **Flask-Login** | session cookie + `current_user` | `Depends(get_current_user)`, `OAuth2PasswordBearer`, ya `fastapi-users` | Yahi wo jagah hai jahan Flask ka ecosystem abhi bhi zyada mature hai (server-rendered login flows) |
| **Flask-JWT-Extended** | JWT encode/decode/refresh | `pyjwt` / `python-jose` + dependency | `06_security_jwt_rbac.md` |
| **Flask-WTF / WTForms** | form parsing + CSRF | Pydantic models + `Form()`; CSRF khud lagana padega | HTML forms wale apps me FastAPI ka gap real hai |
| **Marshmallow / Flask-Marshmallow** | schema validate + dump | **Pydantic v2** (built-in) | Sabse bada single win — validation framework me aa gaya |
| **Flask-RESTful / Flask-RESTX** | Resource classes + Swagger | native FastAPI + `APIRouter` | RESTX ka Swagger FastAPI me built-in hai |
| **flask-smorest / apispec** | OpenAPI generation | built-in `/openapi.json` | Flask side par yeh gap ka best patch hai |
| **Flask-Caching** | `@cache.cached` | `fastapi-cache2`, ya seedha redis + decorator | `23_fastapi_caching.md` |
| **Flask-Limiter** | rate limiting | **slowapi** (same `limits` library) | `41_fastapi_rate_limiting.md` |
| **Flask-CORS** | CORS headers | `CORSMiddleware` (Starlette, built-in) | |
| **Flask-Mail** | SMTP | `fastapi-mail`, ya provider SDK | |
| **Flask-Admin** | auto CRUD admin UI | `sqladmin` / `starlette-admin` | Flask-Admin abhi bhi zyada feature-rich — **Flask ke haq me strong point** |
| **Flask-SocketIO** | WebSockets/long-poll | native `@app.websocket` + `broadcaster` | `15_websocket_scaling_patterns.md` |
| **Flask-Session** | server-side sessions | `SessionMiddleware` (Starlette) | Starlette wala signed-cookie hai; server-side ke liye khud Redis lagao |
| **Jinja templates** (built-in) | HTML rendering | `Jinja2Templates` (Starlette) | Kaam karta hai, par Flask ka DX behtar hai (`url_for`, auto template folder) |
| **Blinker signals** | app events | koi direct equivalent nahi — middleware / event bus | Migration me yeh chupa hua kaam hai |
| **Flask-DebugToolbar** | in-page debug panel | koi equivalent nahi — `/docs` + structured logs + APM | |
| **Celery** | background jobs | Celery (same), ya `arq`, ya `BackgroundTasks` chhote kaam ke liye | Celery dono me same chalti hai |

**Pattern dekha?** Adhi Flask extensions **wrappers** thin the (SQLAlchemy, Alembic, limits). FastAPI me aap seedha underlying library use karte ho, kyunki DI system wo lifecycle glue de deta hai jo wrapper de raha tha. Bachi hui extensions (Flask-Admin, Flask-Login, DebugToolbar, WTForms) sab **server-rendered HTML** wali duniya ki hain — aur wahi Flask ka bacha hua strong territory hai.

---

## 8. Flask Abhi Bhi Sahi Jawab Kab Hai

Agar aap interview me bolo "Flask dead hai", toh senior interviewer aapko wahin catch kar lega. Honest list:

1. **Server-rendered Jinja app / admin panel.** Flask-Admin + Flask-Login + Flask-WTF ka combo FastAPI me reproduce karne me hafte lagenge. FastAPI HTML render kar sakta hai, par uska ecosystem JSON-API ke liye bana hai.
2. **CPU-bound service.** ML inference, image processing, pandas crunching — async se zero fayda. `gunicorn -w N` sync workers simple aur predictable hai. (FastAPI use karo toh endpoint `def` rakhna, `async def` nahi.)
3. **Chhota internal tool / webhook receiver / script with an endpoint.** 40 lines ka Flask app padhne me aasan hai; Pydantic models + routers wahan ceremony hai.
4. **WSGI-only infra.** Legacy `mod_wsgi`, kuch PaaS/enterprise deployment targets, ya aisi security/APM tooling jo sirf WSGI hook karti ho.
5. **Team ka async experience zero hai.** Ek blocking `psycopg2` call `async def` ke andar poore event loop ko freeze kar deti hai aur symptom "sab kuch random slow" jaisa dikhta hai. Flask me wo galti *possible hi nahi*. Framework ka worst-case behaviour bhi selection criteria hai.
6. **Codebase already deeply Flask hai aur kaam kar raha hai.** "Rewrite karke 30% latency" business case shayad hi kabhi paas hota hai. Flask 3 + `flask-smorest` (Marshmallow schemas + OpenAPI) gap ka bada hissa band kar deta hai bina rewrite ke.

> **Interview Angle:** "Flask kab choose karoge?" ka sabse strong jawab: *"Server-rendered admin/CRUD jahan Flask-Admin/Flask-Login ecosystem hi product ka 60% hai, aur CPU-bound services jahan ASGI ka concurrency benefit exist hi nahi karta. Dono jagah FastAPI extra complexity hai bina payoff ke."*

---

## 9. Migration Story — Flask → FastAPI

Real migration "sab kuch rewrite" nahi hoti. **Strangler fig** hoti hai.

### Step 0 — Pehle decide karo ki worth hai kya

Migrate karo jab: (a) endpoints I/O-bound hain aur upstream fan-out kar rahe hain, (b) frontend/mobile teams ko typed contract chahiye aur aap manually Swagger maintain kar rahe ho, (c) WebSockets/SSE chahiye, (d) validation bugs production me aa rahe hain. Sirf "FastAPI modern hai" — nahi.

### Step 1 — FastAPI ko shell banao, Flask ko mount kar do

```python
# main.py — naya ASGI entrypoint
from fastapi import FastAPI
from a2wsgi import WSGIMiddleware          # pip install a2wsgi
from legacy.app import create_app as create_flask_app

app = FastAPI(title="Screener API")

# NAYE endpoints yahan (native ASGI, full FastAPI)
from api.stocks import router as stocks_router
app.include_router(stocks_router)

# PURANA Flask app jaisa hai waisa chalta rahega, ek WSGI bridge ke peeche
app.mount("/legacy", WSGIMiddleware(create_flask_app()))
```

Note: Starlette/FastAPI ka apna `WSGIMiddleware` deprecated ho chuka hai — `a2wsgi` use karo. **Important:** bridge ke peeche Flask abhi bhi blocking hai; a2wsgi use threadpool me chalata hai, magic nahi karta. Bridge ek *migration ramp* hai, permanent architecture nahi.

Alternative (aksar saaf): dono apps alag process me chalao aur nginx/ingress par path ke hisaab se route karo. Debugging aasan, blast radius chhota.

### Step 2 — Mechanical translations

| Flask | FastAPI |
|---|---|
| `Blueprint("x", __name__)` | `APIRouter(prefix=..., tags=[...])` |
| `@bp.route("/<int:id>")` | `@router.get("/{id}")` with `id: int` |
| `request.args.get("q")` | `q: str \| None = None` (query param) |
| `request.get_json()` + manual checks | `body: StockIn` (Pydantic) |
| `request.headers.get("X-Key")` | `x_key: Annotated[str, Header()]` |
| `jsonify(d), 201` | `return d` + `status_code=201`, `response_model=` |
| `abort(404)` / `return {...}, 404` | `raise HTTPException(404, ...)` |
| `@app.errorhandler(Exc)` | `@app.exception_handler(Exc)` |
| `@app.before_request` (auth) | router `dependencies=[Depends(auth)]` |
| `@app.before_request` (all routes) | HTTP middleware |
| `g.db`, `teardown_appcontext` | `Depends(get_db)` with `yield` |
| `current_app.config["X"]` | `Depends(get_settings)` → `BaseSettings` |
| `app.test_client()` | `TestClient(app)` |
| monkeypatch/mocks for `g` | `app.dependency_overrides[dep] = fake` |

### Step 3 — Traps jo migration me maarte hain

1. **Sabko `async def` bana dena.** Aapka ORM abhi bhi sync hai (`psycopg2`/sync SQLAlchemy). `async def` + blocking DB call = event loop freeze = Flask se *bhi kharab* p99. **Rule: migration me endpoints `def` (sync) rakho.** Starlette unhe threadpool me chalayega — behaviour gunicorn-gthread jaisa, safe. Async par baad me jao, jab driver bhi async ho (`asyncpg`).
2. **`g` ka har use dhundho.** Deep helper functions chupke se `g.user` padh rahe honge; woh FastAPI me `ImportError`/runtime error nahi degi — hosakta hai import hi ho jaaye aur "working outside of request context" runtime par phate. Poore repo me `from flask import g` grep karo, ye migration ka asli scope hai.
3. **Response shape silently badalna.** `jsonify` sab kuch bhej deta tha; `response_model` extra fields **filter** kar deta hai. Migration ke waqt real responses ko diff karo, warna client chupchaap fields kho dega.
4. **Error format badalna.** Flask ka `{"error": "..."}` vs FastAPI ka `{"detail": ...}` aur 400 vs 422 — clients yeh parse kar rahe hote hain. Purana shape preserve karne ke liye custom exception handlers likho (`21_rfc7807_problem_details.md`).
5. **Blinker signals / Flask-specific hooks.** Inka koi 1:1 equivalent nahi — explicitly redesign karna padega.
6. **Sessions/cookies aur CSRF.** Flask ka `session` + CSRF Flask-WTF se aata tha. FastAPI me yeh aapki zimmedari hai.

---

## 10. "Why FastAPI over Flask?" — Stock Screener wala Jawab

Yeh sawaal aapke project ke context me pucha jaayega. Generic answer weak lagta hai; **project-specific** answer strong. Screener ka shape: user ek filter set bhejta hai, backend N market-data providers ko hit karta hai, results merge/rank karta hai, live prices stream karta hai.

**Chaar reasons, har ek ek concrete requirement se juda:**

**1. Concurrency — screener ek fan-out workload hai.**
> "Ek screen request 30–50 symbols par quote + fundamentals fetch karti hai, har upstream call ~150–300ms. Flask ke sync worker par yeh serial hoti (30 × 200ms ≈ 6s) ya mujhe gevent monkey-patching pe depend karna padta. FastAPI me `asyncio.gather` se poora batch ~300ms me aata hai, aur wait ke dauraan wahi worker doosre users ki requests serve karta rehta hai. Yaani latency aur throughput dono ek hi property se aaye."

**2. Pydantic validation — upstream data untrusted hai.**
> "Market data providers schema chupchaap badalte hain — kabhi `price` string aata hai, kabhi field missing. Flask me yeh `request.get_json()` ke baad manual `if`-checks ya Marshmallow schemas hote. FastAPI me request aur upstream response dono Pydantic models hain: coercion, `Decimal` handling, aur galat data par ek structured 422 jisme `loc` exact field batata hai. Pydantic v2 ka core Rust me hai, toh yeh check hot path me bhi sasta hai."

**3. OpenAPI — frontend ke saath contract.**
> "Frontend React par hai. FastAPI `/openapi.json` deta hai, jisse hum TypeScript types generate karte hain — schema badla toh frontend build par hi fail hota hai, production me nahi. Flask me yahi karne ke liye flask-smorest/apispec lagana padta aur spec code se drift karti."

**4. DI — per-request DB session, auth, aur testability.**
> "`Depends(get_db)` ek `yield` dependency hai: session banti hai, endpoint chalta hai, `finally` me band hoti hai — chahe exception aaye ya na aaye. Auth `Depends(get_current_user)` router-level hai. Tests me `dependency_overrides` se ek line me fake user/DB inject ho jaata hai, jabki Flask me `g` ko monkeypatch karne ke liye request-context fake karna padta."

**Plus ek honesty line jo answer ko senior banati hai:**
> "Trade-off yeh hai ki ranking/scoring wala CPU-bound hissa async se kuch nahi paata — wo endpoints maine `def` rakhe hain taaki Starlette unhe threadpool me chalaye aur event loop free rahe. Agar poora product server-rendered admin hota to main Flask hi choose karta."

Aur agar interviewer poochhe "sirf performance ke liye?" — bolo **nahi**: "raw speed 4th reason hai. Pehle teen (concurrency model, validation, contract) design-level hain; ek hello-world benchmark ka number production me matter nahi karta."

---

## 11. Common Mistakes Checklist

- [ ] ❌ "FastAPI Flask se fast hai" bolna bina yeh bataye ki *kyun* (concurrency model, framework overhead nahi)
- [ ] ❌ Flask ke context globals ko "thread-locals" bolna — Flask 2.0+ me `ContextVar` hain
- [ ] ❌ Yeh samajhna ki Flask 3 ke `async def` views se server ki concurrency badh jaati hai (nahi — `async_to_sync`, thread block hi rehta hai)
- [ ] ❌ Migration me saare endpoints `async def` bana dena jab ORM abhi sync hai → event loop freeze
- [ ] ❌ `g` ke saare usages grep kiye bina migration estimate dena
- [ ] ❌ gevent workers ka number badha dena bina yeh check kiye ki saari libraries monkey-patch-safe hain
- [ ] ❌ `uvicorn.workers.UvicornWorker` use karna (deprecated) — `uvicorn-worker` package lo
- [ ] ❌ ASGI par ja kar connection pool waisa hi chhota rakhna — bottleneck framework se DB par shift ho jaata hai
- [ ] ❌ `response_model` lagate waqt purani response se diff na karna → clients ke fields chupchaap gayab
- [ ] ❌ Interview me "Flask legacy hai" bolna — Flask-Admin/Jinja/CPU-bound cases abhi bhi valid hain

---

## 12. Interview Q&A

**Q1: WSGI aur ASGI me exact technical difference kya hai?**
WSGI ek **sync callable** hai — `app(environ, start_response)` jo bytes ka iterable return karta hai; return hone par response poora ho chuka hai, isliye ek worker ek time par ek hi request hold kar sakta hai. ASGI ek **async callable** hai — `await app(scope, receive, send)`, jahan request aur response dono **events ka stream** hain. Isse teen cheezein milti hain jo WSGI me nahi: (1) I/O par await karke worker free karna, yaani ek process me hazaaron in-flight requests; (2) `scope["type"]` me `websocket` aur `lifespan`, isliye WebSockets/startup-shutdown native; (3) proper streaming with backpressure aur disconnect detection. Note: ASGI per-request *fast* nahi hai — CPU-bound kaam me koi fayda nahi.

**Q2: Flask ka `g` kya hai aur FastAPI me uska equivalent kya hai?**
`g` ek per-request namespace hai (naam ke bawajood global nahi) jise `LocalProxy` ek `ContextVar` ke upar expose karta hai; Flask request ke start me context push karta hai, end me pop — tab `g` destroy ho jaata hai. Kaam ka: ek `before_request` me DB session ya user set karo, kisi bhi depth ke function me `from flask import g` karke uthao. Downside: function signature jhoot bolti hai, testing ke liye request context fake karna padta hai, aur type checking zero. FastAPI me iska equivalent `Depends()` hai — wahi value **parameter** ban jaati hai, `yield` dependency setup+teardown ek jagah rakhti hai, aur tests me `app.dependency_overrides` se ek line me swap ho jaati hai. FastAPI ka `request.state` `g` ka closest analogue hai, par usko sirf cross-cutting cheezon (request-id) ke liye rakho.

**Q3: Flask 3 me `async def` views hain — toh FastAPI ki kya zaroorat?**
Flask async views `asgiref.sync.async_to_sync` se chalte hain: worker thread ek event loop banata hai aur `run_until_complete` par **block** karta hai. Us loop me sirf wahi ek coroutine hoti hai, doosri requests nahi. Toh server ki concurrency abhi bhi `workers × threads` hi hai. Fayda sirf **intra-request** fan-out ka hai — `asyncio.gather` se 5 upstream calls parallel. Cross-request concurrency ke liye protocol hi badalna padega, kyunki WSGI callable ke return par response finalize hota hai. FastAPI/ASGI me har awaiting request loop ko chhod deti hai, isliye ek worker hazaaron connections hold karta hai.

**Q4: gunicorn+gevent vs uvicorn — kaun kab?**
gevent aapko async-jaisi concurrency deta hai **bina** code me `async/await` likhe — monkey-patching socket/time/threading ko greenlet-aware bana deti hai. Yeh legacy sync codebases ke liye best hai jahan rewrite possible nahi. Costs: patching global aur implicit hai, patch `import` se pehle honi chahiye, aur koi bhi C-level socket use karne wali library (kuch DB drivers, grpcio, native extensions) hub ko block kar degi — failure mode dhundhna mushkil hai. uvicorn me concurrency **explicit** hai: `await` dikhta hai code me, isliye blocking call review me pakdi jaati hai, aur WebSockets/HTTP-2/streaming protocol level par supported hai. Naya code = ASGI/uvicorn. Purana sync code jise scale karna hai bina rewrite = gevent, aankh khuli rakh kar. Aur haan: `uvicorn.workers.UvicornWorker` deprecated hai, ab `uvicorn-worker` package.

**Q5: Blueprint aur APIRouter me farq?**
Structure lagbhag same — dono deferred route registration ke bundles hain, dono nest ho sakte hain (`bp.register_blueprint` / `router.include_router`). Farq cross-cutting concerns me hai. Blueprint me auth `@bp.before_request` hota hai jo response return karke short-circuit karta hai, per-request resources `g` par jaate hain, aur teardown alag hook me. APIRouter me `dependencies=[Depends(auth)]` **declaration me** dikhta hai, resources `yield` dependencies hain (setup+teardown ek function me), `tags=` se `/docs` grouping free milti hai, aur `response_model` output ko validate+filter karta hai. Ek asymmetry: FastAPI me exception handlers **app-level** hote hain, jabki Flask me `@bp.errorhandler` blueprint-scoped ho sakta hai.

**Q6: Ek Flask app ko FastAPI par kaise migrate karoge, without a big-bang rewrite?**
Strangler fig. FastAPI ko naya entrypoint banao, purane Flask app ko `a2wsgi`'s `WSGIMiddleware` se `/legacy` par mount kar do (Starlette ka built-in WSGIMiddleware deprecated hai), ya dono ko alag process me chala kar nginx se path-route karo. Phir endpoint-by-endpoint port karo: Blueprint→APIRouter, `request.get_json()`→Pydantic model, `abort`→`HTTPException`, `before_request`→router dependency, `g.db`→`Depends(get_db)` with `yield`. **Sabse important safety rule:** shuru me sab endpoints `def` rakho, `async def` nahi — ORM abhi sync hai aur `async def` me blocking call event loop freeze kar degi; Starlette `def` endpoints ko threadpool me chalata hai jo gthread jaisa safe behaviour hai. Traps: `from flask import g` ke saare usages grep karo (asli scope wahi hai), `response_model` ke filtering se response diff karo, error body shape (`error` vs `detail`, 400 vs 422) clients ke liye preserve karo, aur blinker signals ka koi equivalent nahi hai.

**Q7: Flask abhi bhi kab better hai?**
Server-rendered apps aur admin panels (Flask-Admin, Flask-Login, Flask-WTF ka ecosystem FastAPI me nahi hai); CPU-bound services (async se zero gain — sync gunicorn workers simpler aur predictable); chhote internal tools jahan Pydantic+routers ka ceremony overkill hai; WSGI-only infra; aur aisi teams jinka async experience nahi hai — kyunki Flask me "blocking call ne poora server freeze kar diya" wali galti structurally possible hi nahi hai. Existing Flask codebase me `flask-smorest` add karke OpenAPI + Marshmallow validation mil jaati hai bina rewrite ke — migration ka business case usse compare karna chahiye.

**Q8: Pydantic ne Flask ke Marshmallow se aage kya diya?**
Do cheezein. **Location:** Marshmallow schemas view ke andar explicitly call hoti hain (`schema.load(request.json)`), toh koi view bhool sakta hai; Pydantic model function **signature** me hai, toh validation skip karna structurally mushkil hai — aur wahi signature OpenAPI schema bhi generate karti hai, yaani spec kabhi drift nahi karti. **Cost:** Pydantic v2 ka validation core Rust (`pydantic-core`) me hai, toh hot path par yeh pure-Python validation se kaafi sasta hai. Bonus: Pydantic ke errors structured hote hain (`loc` array exact nested field path deta hai), jo frontend field-mapping ke liye direct use ho jaata hai.

---

## Related
- [[13_asgi_internals_uvicorn_tuning]] — ASGI scope/receive/send aur uvicorn tuning ka deep dive
- [[39_async_def_vs_def_threadpool_deep]] — `async def` vs `def`, threadpool, aur event loop freeze
- [[02_dependency_injection]] — `Depends`, yield-teardown, dependency_overrides (Flask ke `g` ka replacement)
- [[04_testing_sqlalchemy]] — `TestClient` + overrides vs Flask ka `test_client()`
- [[41_fastapi_rate_limiting]] — slowapi (Flask-Limiter ka equivalent)
- [[08_pydantic_settings_alembic]] — `BaseSettings` (config) aur raw Alembic (Flask-Migrate ka equivalent)
