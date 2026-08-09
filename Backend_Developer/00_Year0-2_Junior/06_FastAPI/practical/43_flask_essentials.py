"""
Flask Essentials vs FastAPI — Same API, Two Frameworks, Side by Side
====================================================================

Companion to 43_flask_essentials_vs_fastapi.md.

This is ONE runnable file containing TWO complete implementations of the same
tiny stock-screener API:

    GET    /api/health           -> liveness + which framework answered
    GET    /api/stocks           -> list all stocks (optional ?sector= filter)
    GET    /api/stocks/{symbol}  -> one stock, 404 (structured) if unknown
    POST   /api/stocks           -> create; invalid payload -> 400 (Flask) / 422 (FastAPI)
    GET    /api/whoami           -> per-request context demo (g vs Depends)

Part A = Flask 3.x: app factory + Blueprint + before_request/teardown + `g`
                    + custom error handlers + MANUAL validation.
Part B = FastAPI:   APIRouter + Depends (yield teardown) + Pydantic + response_model
                    + exception_handler.

The __main__ block exercises BOTH through their in-process test clients, so no
server, no port, no network is needed.  Run it and read the printed diff.

Run:
    pip install "flask[async]" fastapi httpx      # httpx powers TestClient
    python 43_flask_essentials.py

Degrades gracefully:
    * Flask missing   -> Part A skipped, Part B still runs (prints pip hint).
    * FastAPI/httpx missing -> Part B skipped, Part A still runs.
    * asgiref missing -> the Flask async-view caveat demo is skipped.

Key lesson (see section 6): a Flask `async def` view runs via
asgiref's async_to_sync -- the worker thread BLOCKS until the coroutine
finishes.  It buys intra-request fan-out, NOT server concurrency.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Annotated, Any


# ==========================================================================
# 0. OPTIONAL-DEPENDENCY GUARDS
# ==========================================================================
# Neighbour practicals in this folder assume the happy path; this file cannot,
# because its whole point is comparing two frameworks and one of them may not
# be installed.  Each half is guarded independently so the file is ALWAYS
# runnable and always teaches something.

try:
    import flask  # noqa: F401  (imported for the version banner only)
    from flask import Blueprint, Flask, g, jsonify, request

    HAS_FLASK = True
    FLASK_HINT = ""
except ImportError:  # pragma: no cover - depends on environment
    HAS_FLASK = False
    FLASK_HINT = 'pip install "flask[async]"'

try:
    from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel, Field, field_validator

    HAS_FASTAPI = True
    FASTAPI_HINT = ""
except ImportError:  # pragma: no cover - depends on environment
    HAS_FASTAPI = False
    FASTAPI_HINT = "pip install fastapi"

# TestClient is guarded SEPARATELY from FastAPI itself: it is a thin wrapper
# over httpx, so it breaks on an httpx/starlette version mismatch even when
# FastAPI works perfectly.  Section 9 falls back to driving the ASGI callable
# by hand in that case -- which is all TestClient really does anyway.
try:
    from fastapi.testclient import TestClient  # needs a compatible httpx

    HAS_TESTCLIENT = True
except ImportError:  # pragma: no cover
    HAS_TESTCLIENT = False

try:
    import asgiref  # noqa: F401  -- required by Flask for `async def` views

    HAS_ASGIREF = True
except ImportError:  # pragma: no cover
    HAS_ASGIREF = False


# ==========================================================================
# 1. SHARED DOMAIN — framework-agnostic, on purpose
# ==========================================================================
# Both halves talk to this same "repository".  Keeping the domain free of any
# framework import is the single biggest thing that makes a Flask -> FastAPI
# migration cheap: only the edge (routing/validation/serialisation) changes.


@dataclass
class Stock:
    symbol: str
    name: str
    sector: str
    price: float


@dataclass
class StockRepo:
    """Toy in-memory store.  Stands in for a SQLAlchemy Session."""

    rows: dict[str, Stock] = field(default_factory=dict)
    closed: bool = False

    def all(self, sector: str | None = None) -> list[Stock]:
        rows = list(self.rows.values())
        if sector:
            rows = [r for r in rows if r.sector.lower() == sector.lower()]
        return sorted(rows, key=lambda r: r.symbol)

    def get(self, symbol: str) -> Stock | None:
        return self.rows.get(symbol.upper())

    def add(self, stock: Stock) -> Stock:
        self.rows[stock.symbol.upper()] = stock
        return stock

    def close(self) -> None:
        # Real repos close a DB connection here.  We only flip a flag so the
        # demo can PROVE that teardown actually ran in both frameworks.
        self.closed = True


SEED = [
    Stock("TCS", "Tata Consultancy Services", "IT", 3890.50),
    Stock("INFY", "Infosys", "IT", 1543.20),
    Stock("HDFCBANK", "HDFC Bank", "Banking", 1678.90),
    Stock("ITC", "ITC Limited", "FMCG", 448.75),
]

VALID_SECTORS = {"IT", "Banking", "FMCG", "Pharma", "Auto", "Energy"}

# Every repo instance created during the run, so the demo can assert that the
# per-request teardown closed them (Flask: teardown_request, FastAPI: finally).
CREATED_REPOS: list[StockRepo] = []


def new_repo() -> StockRepo:
    repo = StockRepo(rows={s.symbol: Stock(**vars(s)) for s in SEED})
    CREATED_REPOS.append(repo)
    return repo


class StockNotFound(Exception):
    """Domain error — each framework maps it to a 404 its own way."""

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        super().__init__(f"unknown symbol: {symbol}")


# ==========================================================================
# ==========================================================================
# PART A — FLASK 3.x
# ==========================================================================
# ==========================================================================

if HAS_FLASK:

    # ----------------------------------------------------------------------
    # 2. BLUEPRINT — deferred route registration
    # ----------------------------------------------------------------------
    # Routes are attached to the Blueprint now, but NOTHING is registered on a
    # real app until create_app() calls register_blueprint().  That deferral is
    # exactly what lets the same blueprint be mounted on many apps / prefixes.
    #
    # Note the url_prefix is NOT here -- it is supplied at registration time.
    # (FastAPI puts prefix on APIRouter itself, i.e. at DEFINITION time.)

    stocks_bp = Blueprint("stocks", __name__)

    # ----------------------------------------------------------------------
    # 2.1 before_request / teardown_request + `g`
    # ----------------------------------------------------------------------
    # `g` is a per-REQUEST namespace (the name is historical and misleading).
    # It is a werkzeug LocalProxy over a contextvars.ContextVar -- since Flask
    # 2.0 these are ContextVars, NOT thread-locals.  Flask pushes a
    # RequestContext before the view and pops it after, destroying `g`.
    #
    # The cost: view signatures LIE.  `def get_stock(symbol)` gives no hint
    # that it also reads g.repo and g.request_id.

    @stocks_bp.before_request
    def open_request_scope():
        g.request_id = request.headers.get("X-Request-ID") or f"flask-{uuid.uuid4().hex[:8]}"
        g.repo = new_repo()          # per-request "DB session"
        g.started_at = time.perf_counter()
        # Returning a Response here would SHORT-CIRCUIT the view.
        # That is how Flask does blueprint-wide auth:
        #     if not ok: return jsonify(error="unauthorized"), 401

    @stocks_bp.teardown_request
    def close_request_scope(exc: BaseException | None):
        # Runs even if the view raised.  Note: teardown must never assume the
        # attribute exists -- before_request may have failed before setting it.
        repo = g.pop("repo", None)
        if repo is not None:
            repo.close()

    @stocks_bp.after_request
    def add_request_id_header(response):
        response.headers["X-Request-ID"] = getattr(g, "request_id", "-")
        return response

    # ----------------------------------------------------------------------
    # 2.2 ROUTES — note how much of the work is MANUAL
    # ----------------------------------------------------------------------

    def _dump(stock: Stock) -> dict[str, Any]:
        """Hand-written serialiser.  FastAPI's response_model replaces this."""
        return {
            "symbol": stock.symbol,
            "name": stock.name,
            "sector": stock.sector,
            "price": round(stock.price, 2),
        }

    @stocks_bp.get("/health")
    def health():
        return jsonify(status="ok", framework="flask", request_id=g.request_id)

    @stocks_bp.get("/stocks")
    def list_stocks():
        # Query params: manual extraction, manual type handling, no docs.
        sector = request.args.get("sector")
        if sector and sector not in VALID_SECTORS:
            # Nobody generated this check for us -- and nobody will notice if a
            # future route forgets it.
            return jsonify(error="bad_request",
                           message=f"unknown sector: {sector}"), 400
        rows = g.repo.all(sector)
        return jsonify(count=len(rows), items=[_dump(r) for r in rows])

    @stocks_bp.get("/stocks/<symbol>")
    def get_stock(symbol: str):
        # `<symbol>` is a string converter.  For ints you would write
        # `<int:stock_id>` -- a Flask-specific mini-DSL in the URL string.
        stock = g.repo.get(symbol)
        if stock is None:
            raise StockNotFound(symbol)      # handled by the app errorhandler
        return jsonify(_dump(stock))

    @stocks_bp.post("/stocks")
    def create_stock():
        # ------------------------------------------------------------------
        # THE MANUAL VALIDATION BLOCK.  This is the single best argument for
        # Pydantic: ~25 lines here vs. a 6-line model in Part B, and this code
        # must be re-written (and re-reviewed) for every POST endpoint.
        # ------------------------------------------------------------------
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify(error="bad_request", message="body must be a JSON object"), 400

        errors: list[dict[str, str]] = []
        for key in ("symbol", "name", "sector", "price"):
            if key not in payload:
                errors.append({"field": key, "message": "missing"})

        symbol = payload.get("symbol")
        if symbol is not None and (not isinstance(symbol, str) or not 1 <= len(symbol) <= 12):
            errors.append({"field": "symbol", "message": "must be a 1-12 char string"})

        sector = payload.get("sector")
        if sector is not None and sector not in VALID_SECTORS:
            errors.append({"field": "sector", "message": f"must be one of {sorted(VALID_SECTORS)}"})

        price = payload.get("price")
        if price is not None:
            # Note bool is a subclass of int in Python -- easy to forget, and a
            # class of bug Pydantic simply does not have.
            if isinstance(price, bool) or not isinstance(price, (int, float)):
                errors.append({"field": "price", "message": "must be a number"})
            elif price <= 0:
                errors.append({"field": "price", "message": "must be > 0"})

        if errors:
            return jsonify(error="validation_error", details=errors), 400

        stock = g.repo.add(
            Stock(symbol=str(symbol).upper(), name=str(payload["name"]),
                  sector=str(sector), price=float(price))
        )
        return jsonify(_dump(stock)), 201

    @stocks_bp.get("/whoami")
    def whoami():
        # The point of this endpoint: request-scoped state comes from an
        # AMBIENT global, not from arguments.
        return jsonify(
            framework="flask",
            request_id=g.request_id,
            context_mechanism="werkzeug LocalProxy over contextvars.ContextVar",
            repo_is_per_request=True,
        )

    # ----------------------------------------------------------------------
    # 2.3 A Flask 3.x ASYNC view — the caveat, demonstrated
    # ----------------------------------------------------------------------
    # Registered only when asgiref is importable (`pip install "flask[async]"`).
    # Flask wraps this coroutine in asgiref.sync.async_to_sync: a fresh event
    # loop runs it to completion while the WSGI worker thread BLOCKS.
    #
    #   * WIN:  asyncio.gather inside ONE request -> 3 x 50ms becomes ~50ms.
    #   * NOT A WIN: during that await, this worker serves NO other request.
    #     Server concurrency is still workers x threads.  The bottleneck is the
    #     WSGI protocol (response is finalised when the callable returns), not
    #     the view.

    if HAS_ASGIREF:

        async def _fake_upstream(symbol: str, delay: float = 0.05) -> dict[str, Any]:
            await asyncio.sleep(delay)          # stands in for httpx.AsyncClient
            return {"symbol": symbol, "quote": 100.0}

        @stocks_bp.get("/fanout")
        async def fanout():
            t0 = time.perf_counter()
            results = await asyncio.gather(
                _fake_upstream("TCS"), _fake_upstream("INFY"), _fake_upstream("ITC")
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000
            return jsonify(
                note="3 x 50ms upstream calls ran concurrently INSIDE one request",
                caveat="the WSGI worker thread was blocked the whole time",
                elapsed_ms=round(elapsed_ms, 1),
                results=results,
            )

    # ----------------------------------------------------------------------
    # 3. APP FACTORY
    # ----------------------------------------------------------------------
    # Why a factory instead of a module-level `app = Flask(__name__)`:
    #   (a) every test builds a fresh app with its own config,
    #   (b) extensions live in their own module and bind via init_app(app),
    #       which breaks the circular-import knot,
    #   (c) several apps can coexist in one process.

    def create_app(config: dict[str, Any] | None = None) -> "Flask":
        app = Flask(__name__)
        app.config.update(TESTING=False)
        if config:
            app.config.update(config)

        # url_prefix supplied HERE, at registration time (contrast: APIRouter).
        app.register_blueprint(stocks_bp, url_prefix="/api")

        # ---- error handlers: domain error -> HTTP shape --------------------
        @app.errorhandler(StockNotFound)
        def handle_not_found(exc: StockNotFound):
            return jsonify(error="not_found", symbol=exc.symbol,
                           request_id=getattr(g, "request_id", "-")), 404

        @app.errorhandler(404)
        def handle_404(exc):
            # Flask's DEFAULT 404 is HTML.  For a JSON API you must override it
            # or clients get an HTML blob where JSON was promised.
            return jsonify(error="not_found", message="no such route"), 404

        @app.errorhandler(Exception)
        def handle_unexpected(exc: Exception):
            # Catch-all so 500s stay JSON.  In production: log with traceback
            # and never leak str(exc) to the client.
            return jsonify(error="internal_error", type=type(exc).__name__), 500

        return app


# ==========================================================================
# ==========================================================================
# PART B — FASTAPI (same five endpoints)
# ==========================================================================
# ==========================================================================

if HAS_FASTAPI:

    # ----------------------------------------------------------------------
    # 4. PYDANTIC MODELS — validation moves INTO the signature
    # ----------------------------------------------------------------------
    # Compare with the 25-line manual block in create_stock() above.  Here the
    # rules are declarative, they are enforced before the handler body runs,
    # AND they generate the OpenAPI schema, so /docs can never drift.

    class StockIn(BaseModel):
        symbol: str = Field(min_length=1, max_length=12)
        name: str = Field(min_length=1, max_length=120)
        sector: str
        price: float = Field(gt=0)

        @field_validator("sector")
        @classmethod
        def sector_must_be_known(cls, v: str) -> str:
            if v not in VALID_SECTORS:
                raise ValueError(f"must be one of {sorted(VALID_SECTORS)}")
            return v

        @field_validator("symbol")
        @classmethod
        def upper(cls, v: str) -> str:
            return v.upper()

    class StockOut(BaseModel):
        symbol: str
        name: str
        sector: str
        price: float

    class StockList(BaseModel):
        count: int
        items: list[StockOut]

    # ----------------------------------------------------------------------
    # 5. DEPENDENCIES — the replacement for before_request + g + teardown
    # ----------------------------------------------------------------------
    # ONE yield-dependency covers what Flask spread over three hooks
    # (before_request / g / teardown_request), and the `finally` runs even if
    # the endpoint raised.

    def get_repo():
        repo = new_repo()
        try:
            yield repo
        finally:
            repo.close()

    def get_request_id(req: Request) -> str:
        # `request.state` is FastAPI's closest analogue to Flask's `g`.  Use it
        # only for genuinely cross-cutting values (request-id for logging);
        # everything else belongs in the signature as a Depends.
        rid = req.headers.get("X-Request-ID") or f"fastapi-{uuid.uuid4().hex[:8]}"
        req.state.request_id = rid
        return rid

    RepoDep = Annotated[StockRepo, Depends(get_repo)]
    RidDep = Annotated[str, Depends(get_request_id)]

    # ----------------------------------------------------------------------
    # 6. APIRouter — prefix/tags/deps declared where the router is DEFINED
    # ----------------------------------------------------------------------
    # A blueprint-wide `@bp.before_request` auth check becomes:
    #     APIRouter(..., dependencies=[Depends(require_api_key)])
    # i.e. visible in the declaration instead of buried in a hook.

    router = APIRouter(
        prefix="/api",
        tags=["stocks"],
        responses={404: {"description": "Unknown symbol"}},
    )

    @router.get("/health")
    async def health_fastapi(rid: RidDep):
        return {"status": "ok", "framework": "fastapi", "request_id": rid}

    @router.get("/stocks", response_model=StockList)
    async def list_stocks_fastapi(repo: RepoDep, sector: str | None = None):
        # `sector: str | None = None` is inferred as a QUERY param, is typed,
        # and shows up in /docs -- no request.args.get(), no manual check.
        if sector and sector not in VALID_SECTORS:
            raise HTTPException(400, f"unknown sector: {sector}")
        rows = repo.all(sector)
        return {"count": len(rows), "items": rows}

    @router.get("/stocks/{symbol}", response_model=StockOut)
    async def get_stock_fastapi(symbol: str, repo: RepoDep, rid: RidDep):
        # `rid` is declared even though the happy path ignores it: that is what
        # populates request.state.request_id for the exception handler below.
        # Flask's `g` gets this for free from before_request -- the FastAPI
        # trade-off is that ambient state must be asked for explicitly.
        stock = repo.get(symbol)
        if stock is None:
            raise StockNotFound(symbol)
        # Returning the dataclass directly: response_model validates it and
        # FILTERS unknown fields.  That filtering is a migration trap -- an
        # extra field the Flask version used to leak silently disappears.
        return stock

    @router.post("/stocks", response_model=StockOut, status_code=201)
    async def create_stock_fastapi(payload: StockIn, repo: RepoDep):
        # Body already parsed, coerced and validated.  Handler body = 2 lines.
        stock = repo.add(Stock(**payload.model_dump()))
        return stock

    @router.get("/whoami")
    async def whoami_fastapi(rid: RidDep, repo: RepoDep):
        return {
            "framework": "fastapi",
            "request_id": rid,
            "context_mechanism": "explicit Depends() parameters",
            "repo_is_per_request": True,
        }

    # ----------------------------------------------------------------------
    # 7. APP FACTORY + EXCEPTION HANDLERS
    # ----------------------------------------------------------------------
    # Asymmetry worth knowing: FastAPI exception handlers are APP-level.  Flask
    # can scope one to a single blueprint (@bp.errorhandler); to get that in
    # FastAPI you need a custom APIRoute class.

    def create_fastapi_app() -> "FastAPI":
        app = FastAPI(
            title="Stock Screener (FastAPI half)",
            description="Same endpoints as the Flask half -- compare the code.",
            version="1.0.0",
        )
        app.include_router(router)

        @app.exception_handler(StockNotFound)
        async def not_found_handler(req: Request, exc: StockNotFound):
            return JSONResponse(
                status_code=404,
                content={
                    "error": "not_found",
                    "symbol": exc.symbol,
                    "request_id": getattr(req.state, "request_id", "-"),
                },
            )

        return app


# ==========================================================================
# 8. THE MAPPING TABLE (printed by the demo)
# ==========================================================================

MAPPING = [
    ("Blueprint('x', __name__)",          "APIRouter(prefix=..., tags=[...])"),
    ("register_blueprint(bp, url_prefix)", "include_router(router)  # prefix on router"),
    ("@bp.route('/<int:id>')",             "@router.get('/{id}')  + id: int"),
    ("request.args.get('q')",              "q: str | None = None"),
    ("request.get_json() + manual ifs",    "payload: StockIn   (Pydantic)"),
    ("request.headers.get('X-Key')",       "x_key: Annotated[str, Header()]"),
    ("jsonify(d), 201",                    "return d + status_code=201, response_model="),
    ("abort(404) / return {...}, 404",     "raise HTTPException(404, ...)"),
    ("@app.errorhandler(Exc)",             "@app.exception_handler(Exc)"),
    ("@bp.before_request (auth)",          "APIRouter(dependencies=[Depends(auth)])"),
    ("g.repo + teardown_request",          "Depends(get_repo) with yield/finally"),
    ("current_app.config['X']",            "Depends(get_settings) -> BaseSettings"),
    ("app.test_client()",                  "TestClient(app)"),
    ("monkeypatch g / test_request_context", "app.dependency_overrides[dep] = fake"),
]

EXTENSION_MAP = [
    ("Flask-SQLAlchemy",   "plain SQLAlchemy 2.0 + Depends(get_db)"),
    ("Flask-Migrate",      "Alembic directly"),
    ("Flask-Login",        "Depends(get_current_user) / fastapi-users"),
    ("Marshmallow",        "Pydantic v2 (built in)"),
    ("Flask-RESTX",        "native FastAPI + auto /docs"),
    ("Flask-Limiter",      "slowapi"),
    ("Flask-Caching",      "fastapi-cache2 / raw redis"),
    ("Flask-CORS",         "CORSMiddleware (built in)"),
    ("Flask-Admin",        "sqladmin / starlette-admin  (Flask still ahead)"),
    ("Flask-SocketIO",     "native @app.websocket + broadcaster"),
]


# ==========================================================================
# 9. IN-PROCESS CLIENTS — and a hand-rolled ASGI one
# ==========================================================================
# No server, no port, no network.  Flask's test_client() dispatches straight
# into the WSGI callable; FastAPI's TestClient does the same for ASGI.
#
# TestClient is a thin httpx wrapper, so a starlette/httpx version mismatch
# breaks it even when FastAPI itself is fine.  MiniASGIClient below is the
# fallback -- and it doubles as the clearest possible illustration of section
# 1 of the lesson: an ASGI app is JUST `await app(scope, receive, send)`.
#
# Compare with the WSGI signature Flask implements:
#     def app(environ, start_response) -> Iterable[bytes]
# One sync call, one return value.  Below, the response arrives as a STREAM of
# events (http.response.start, then one or more http.response.body) -- that
# event stream is exactly why ASGI can do streaming, SSE and WebSockets and
# WSGI cannot.


@dataclass
class MiniResponse:
    status_code: int
    body: bytes
    headers: dict[str, str]

    def json(self) -> Any:
        return json.loads(self.body or b"null")


class MiniASGIClient:
    """~40-line in-process ASGI client.  Enough for GET/POST with JSON."""

    def __init__(self, app: Any) -> None:
        self.app = app

    def get(self, url: str, headers: dict[str, str] | None = None) -> MiniResponse:
        return self._request("GET", url, None, headers)

    def post(self, url: str, json: Any = None,  # noqa: A002 - mirrors httpx's API
             headers: dict[str, str] | None = None) -> MiniResponse:
        return self._request("POST", url, json, headers)

    def _request(self, method: str, url: str, body_obj: Any,
                 headers: dict[str, str] | None) -> MiniResponse:
        return asyncio.run(self._call(method, url, body_obj, headers or {}))

    async def _call(self, method: str, url: str, body_obj: Any,
                    headers: dict[str, str]) -> MiniResponse:
        path, _, query = url.partition("?")
        body = b"" if body_obj is None else json.dumps(body_obj).encode()

        raw_headers: list[tuple[bytes, bytes]] = [(b"host", b"testserver")]
        if body:
            raw_headers.append((b"content-type", b"application/json"))
            raw_headers.append((b"content-length", str(len(body)).encode()))
        raw_headers += [(k.lower().encode(), v.encode()) for k, v in headers.items()]

        # This dict IS the ASGI "scope" from the lesson.  Note scope["type"]:
        # "websocket" and "lifespan" scopes flow through the same callable,
        # which is why ASGI frameworks get those protocols for free.
        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.1"},
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": query.encode(),
            "root_path": "",
            "headers": raw_headers,
            "client": ("127.0.0.1", 50000),
            "server": ("testserver", 80),
        }

        status = 500
        out = bytearray()
        resp_headers: dict[str, str] = {}

        async def receive() -> dict[str, Any]:
            # The app awaits this to pull the request body (possibly in chunks).
            return {"type": "http.request", "body": body, "more_body": False}

        async def send(message: dict[str, Any]) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                for k, v in message.get("headers", []):
                    resp_headers[k.decode()] = v.decode()
            elif message["type"] == "http.response.body":
                out.extend(message.get("body", b""))

        await self.app(scope, receive, send)
        return MiniResponse(status, bytes(out), resp_headers)


def make_client(app: Any) -> tuple[Any, str]:
    """Prefer the real TestClient; fall back to MiniASGIClient. Returns (client, label)."""
    if HAS_TESTCLIENT:
        try:
            return TestClient(app), "fastapi.testclient.TestClient"
        except TypeError:
            # Classic symptom of starlette < 0.37 with httpx >= 0.28:
            #   TypeError: Client.__init__() got an unexpected keyword argument 'app'
            pass
    return MiniASGIClient(app), "MiniASGIClient (raw ASGI — httpx/starlette mismatch)"


# ==========================================================================
# 9b. DEMO DRIVERS
# ==========================================================================


def _banner(text: str) -> None:
    print()
    print("=" * 74)
    print(text)
    print("=" * 74)


def _show(label: str, status: int, body: Any) -> None:
    rendered = json.dumps(body, default=str)
    if len(rendered) > 150:
        rendered = rendered[:147] + "..."
    print(f"  {label:<34} -> {status}  {rendered}")


def demo_flask() -> None:
    _banner("PART A — FLASK 3.x  (app factory + Blueprint + g + manual validation)")
    if not HAS_FLASK:
        print(f"  SKIPPED: Flask is not installed.  Install with:  {FLASK_HINT}")
        return

    app = create_app({"TESTING": True})
    client = app.test_client()          # <- in-process WSGI dispatch

    r = client.get("/api/health")
    _show("GET /api/health", r.status_code, r.get_json())
    print(f"  {'(after_request header)':<34} -> X-Request-ID: {r.headers.get('X-Request-ID')}")

    r = client.get("/api/stocks")
    _show("GET /api/stocks", r.status_code, r.get_json())

    r = client.get("/api/stocks?sector=IT")
    _show("GET /api/stocks?sector=IT", r.status_code, r.get_json())

    r = client.get("/api/stocks?sector=Crypto")
    _show("GET /api/stocks?sector=Crypto", r.status_code, r.get_json())

    r = client.get("/api/stocks/tcs")
    _show("GET /api/stocks/tcs", r.status_code, r.get_json())

    r = client.get("/api/stocks/NOPE")
    _show("GET /api/stocks/NOPE (errorhandler)", r.status_code, r.get_json())

    r = client.post("/api/stocks", json={"symbol": "WIPRO", "name": "Wipro",
                                         "sector": "IT", "price": 512.4})
    _show("POST /api/stocks (valid)", r.status_code, r.get_json())

    r = client.post("/api/stocks", json={"symbol": "", "sector": "Crypto", "price": -5})
    _show("POST /api/stocks (invalid)", r.status_code, r.get_json())
    print("     ^ 400 with a HAND-WRITTEN error shape; every POST route repeats this code.")

    r = client.get("/api/whoami")
    _show("GET /api/whoami", r.status_code, r.get_json())

    r = client.get("/api/does-not-exist")
    _show("GET /api/does-not-exist", r.status_code, r.get_json())
    print("     ^ without the @app.errorhandler(404) override this would be HTML.")

    if HAS_ASGIREF:
        r = client.get("/api/fanout")
        _show("GET /api/fanout (async view)", r.status_code, r.get_json())
        print("     ^ 3 x 50ms concurrent INSIDE one request (async_to_sync);")
        print("       the WSGI worker thread stayed blocked -> no cross-request win.")
    else:
        print('  /api/fanout skipped: pip install "flask[async]" (needs asgiref)')

    closed = [r for r in CREATED_REPOS if r.closed]
    print(f"\n  teardown_request check: {len(closed)}/{len(CREATED_REPOS)} repos closed "
          f"(per-request resource freed in a SEPARATE hook from where it was created)")


def demo_fastapi() -> None:
    _banner("PART B — FASTAPI  (APIRouter + Depends + Pydantic + response_model)")
    if not HAS_FASTAPI:
        print(f"  SKIPPED: FastAPI/httpx not installed.  Install with:  {FASTAPI_HINT}")
        return

    before = len(CREATED_REPOS)
    app = create_fastapi_app()
    client, client_label = make_client(app)   # <- in-process ASGI dispatch
    print(f"  client: {client_label}\n")

    r = client.get("/api/health")
    _show("GET /api/health", r.status_code, r.json())

    r = client.get("/api/stocks")
    _show("GET /api/stocks", r.status_code, r.json())

    r = client.get("/api/stocks?sector=IT")
    _show("GET /api/stocks?sector=IT", r.status_code, r.json())

    r = client.get("/api/stocks?sector=Crypto")
    _show("GET /api/stocks?sector=Crypto", r.status_code, r.json())

    r = client.get("/api/stocks/tcs")
    _show("GET /api/stocks/tcs", r.status_code, r.json())

    r = client.get("/api/stocks/NOPE")
    _show("GET /api/stocks/NOPE (exc handler)", r.status_code, r.json())

    r = client.post("/api/stocks", json={"symbol": "wipro", "name": "Wipro",
                                         "sector": "IT", "price": 512.4})
    _show("POST /api/stocks (valid)", r.status_code, r.json())
    print("     ^ symbol lower-cased in the request, upper-cased by a field_validator.")

    r = client.post("/api/stocks", json={"symbol": "", "sector": "Crypto", "price": -5})
    _show("POST /api/stocks (invalid)", r.status_code, r.json())
    print("     ^ 422 generated by Pydantic. ZERO validation code in the handler;")
    print("       each error carries a `loc` path the frontend can map to a field.")

    r = client.get("/api/whoami")
    _show("GET /api/whoami", r.status_code, r.json())

    r = client.get("/api/does-not-exist")
    _show("GET /api/does-not-exist", r.status_code, r.json())
    print("     ^ JSON by default -- no override needed.")

    spec = client.get("/openapi.json").json()
    paths = sorted(spec["paths"])
    print(f"\n  GET /openapi.json      -> {len(paths)} documented paths: {paths}")
    print("     ^ free, always in sync with the code, and the source of generated")
    print("       TypeScript clients.  Flask needs flask-smorest/apispec for this.")

    repos = CREATED_REPOS[before:]
    closed = [r for r in repos if r.closed]
    print(f"\n  yield-dependency teardown check: {len(closed)}/{len(repos)} repos closed "
          f"(setup + teardown live in ONE function, `finally` runs even on errors)")


def demo_dependency_override() -> None:
    """The testing story: Flask's `g` vs FastAPI's dependency_overrides."""
    _banner("TESTING — swapping a per-request dependency")
    if not HAS_FASTAPI:
        print(f"  SKIPPED: {FASTAPI_HINT}")
        return

    app = create_fastapi_app()

    empty = StockRepo(rows={})

    def fake_repo():
        yield empty

    app.dependency_overrides[get_repo] = fake_repo      # one line
    client, _ = make_client(app)
    r = client.get("/api/stocks")
    _show("GET /api/stocks (repo overridden)", r.status_code, r.json())
    app.dependency_overrides.clear()

    print("     ^ FastAPI: app.dependency_overrides[get_repo] = fake_repo")
    print("       Flask equivalent: monkeypatch a module global, or push a fake")
    print("       request context with app.test_request_context() -- because the")
    print("       repo arrived via `g`, not via an argument you can substitute.")


def demo_comparison_tables() -> None:
    _banner("MIGRATION CHEAT SHEET — Flask construct -> FastAPI construct")
    print(f"  {'FLASK':<42} {'FASTAPI'}")
    print(f"  {'-' * 42} {'-' * 46}")
    for flask_side, fastapi_side in MAPPING:
        print(f"  {flask_side:<42} {fastapi_side}")

    print()
    print(f"  {'EXTENSION':<42} {'FASTAPI EQUIVALENT'}")
    print(f"  {'-' * 42} {'-' * 46}")
    for ext, equiv in EXTENSION_MAP:
        print(f"  {ext:<42} {equiv}")


def demo_takeaways() -> None:
    _banner("TAKEAWAYS")
    print("""
  1. Same 5 endpoints. The FastAPI half is shorter mostly because validation
     and serialisation moved from handler bodies into the type signature.

  2. Flask's context (`g`) is ambient: convenient, untyped, invisible in
     signatures, awkward to substitute in tests.  FastAPI's Depends is the
     same capability made explicit -- and therefore overridable.

  3. Flask spreads one resource's lifecycle over before_request + g +
     teardown_request.  FastAPI puts it in one yield-dependency.

  4. Flask 3 `async def` views work, but via async_to_sync: the WSGI worker
     blocks.  Good for intra-request fan-out (asyncio.gather), useless for
     server concurrency -- that limit is the WSGI protocol itself.

  5. Migration rule #1: while your ORM is still sync, port endpoints as `def`,
     NOT `async def`.  Starlette runs `def` endpoints in a threadpool (safe,
     gthread-like).  A blocking call inside `async def` freezes the whole
     event loop -- worse than Flask ever was.

  6. Migration trap: response_model FILTERS unknown fields, and error bodies
     change shape (`error` -> `detail`, 400 -> 422).  Diff real responses
     before cutting clients over.

  7. Flask is still the right answer for server-rendered admin/CRUD apps
     (Flask-Admin + Flask-Login + WTForms) and for CPU-bound services where
     ASGI's concurrency benefit does not exist.
""".rstrip())


# ==========================================================================
# 10. COMMON MISTAKES — quick reference
# ==========================================================================

COMMON_MISTAKES = """
COMMON MISTAKES WHEN COMPARING / MIGRATING FLASK -> FASTAPI
============================================================

1.  "FastAPI is faster" with no mechanism
    -> The win is concurrency density on I/O waits, not per-request speed.
       CPU-bound endpoints gain nothing.

2.  Calling Flask's context globals "thread-locals"
    -> Since Flask 2.0 they are LocalProxy objects over contextvars.ContextVar.

3.  Believing Flask 3 async views add server concurrency
    -> async_to_sync blocks the worker thread; only intra-request fan-out wins.

4.  Porting every endpoint to `async def` while the ORM is still sync
    -> One blocking call freezes the event loop for ALL requests.
       Port as `def` first; go async when the driver is async (asyncpg).

5.  Estimating a migration without grepping `from flask import g`
    -> Deep helpers silently read g.user / g.db; that grep IS the real scope.

6.  Forgetting Flask's default 404/500 pages are HTML
    -> A JSON API must override @app.errorhandler(404) and a catch-all.

7.  Adding response_model without diffing real responses
    -> It filters unknown fields; clients lose data silently.

8.  Turning up gevent worker_connections without auditing libraries
    -> Any C-level socket that is not monkey-patched blocks the whole hub.

9.  Using uvicorn.workers.UvicornWorker
    -> Deprecated; install the separate `uvicorn-worker` package,
       or just run `uvicorn --workers N`.

10. Keeping the same small DB pool after moving to ASGI
    -> The bottleneck moves from the framework to downstream resources.
"""


# ==========================================================================
# MAIN
# ==========================================================================

if __name__ == "__main__":
    print("Flask Essentials vs FastAPI — one file, two implementations, zero servers")
    print(f"  flask installed:   {HAS_FLASK}   {FLASK_HINT}")
    print(f"  fastapi installed: {HAS_FASTAPI}   {FASTAPI_HINT}")
    print(f"  asgiref installed: {HAS_ASGIREF}  (needed for Flask async views)")

    demo_flask()
    demo_fastapi()
    demo_dependency_override()
    demo_comparison_tables()
    demo_takeaways()
    print(COMMON_MISTAKES)

    if HAS_FASTAPI:
        print("To explore the FastAPI half interactively:")
        print("  uvicorn 43_flask_essentials:create_fastapi_app --factory --reload")
        print("  # then open http://127.0.0.1:8000/docs")
    if HAS_FLASK:
        print("To run the Flask half:")
        print("  gunicorn -w 4 '43_flask_essentials:create_app()'   # WSGI, sync workers")
