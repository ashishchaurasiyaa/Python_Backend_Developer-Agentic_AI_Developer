"""
FastAPI Lab 05 — RFC 7807 Problem Details Error Handling
============================================================
OBJECTIVE: replace FastAPI's default `{"detail": "..."}` error shape with the
RFC 7807 `application/problem+json` shape via a custom exception + handler.

TASK:
  1. TODO 1: define `OutOfStockError` with `type`, `title`, `status` set as
     class attributes.
  2. TODO 2: implement the exception handler — build the 5-field problem
     body and return it with `media_type="application/problem+json"`.
  3. Run: python 05_rfc7807_error_handling.py

Prereq: pip install fastapi httpx   (no Docker needed — everything is in-process)
"""

from __future__ import annotations

import asyncio

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

app = FastAPI(title="Lab 05 — RFC 7807 Error Handling")


# ─────────────────────────────────────────────────────────────
# TODO 1: define the custom exception. RFC 7807 problem members:
#   type (a URI identifying the problem type), title (short human summary),
#   status (HTTP status code repeated in the body — yes, on purpose, so the
#   body is self-describing even if middleware strips the real status).
#   Hint:
#       class OutOfStockError(Exception):
#           type = "https://api.lab/problems/out-of-stock"
#           title = "Item is out of stock"
#           status = 409
#           def __init__(self, item_id: str):
#               self.item_id = item_id
#               super().__init__(self.title)
class OutOfStockError(Exception):
    def __init__(self, item_id: str):
        self.item_id = item_id
        super().__init__("out of stock")
# ─────────────────────────────────────────────────────────────


@app.exception_handler(OutOfStockError)
async def out_of_stock_handler(request: Request, exc: OutOfStockError) -> JSONResponse:
    # ─────────────────────────────────────────────────────
    # TODO 2: build the RFC 7807 body — ALL FIVE fields are required by this
    #   lab's contract: type, title, status, detail, instance.
    #   `instance` should identify THIS occurrence — the request path is the
    #   conventional choice.
    #   Hint:
    #       body = {
    #           "type": exc.type,
    #           "title": exc.title,
    #           "status": exc.status,
    #           "detail": f"Item '{exc.item_id}' is currently out of stock",
    #           "instance": str(request.url.path),
    #       }
    #       return JSONResponse(
    #           status_code=exc.status,
    #           content=body,
    #           media_type="application/problem+json",
    #       )
    return JSONResponse(status_code=500, content={"detail": "not RFC 7807 shaped yet"})
    # ─────────────────────────────────────────────────────


@app.get("/items/{item_id}/reserve")
async def reserve_item(item_id: str):
    if item_id == "sold-out-widget":
        raise OutOfStockError(item_id)
    return {"item_id": item_id, "reserved": True}


async def main() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        print("\n[1] Happy path — GET /items/widget-1/reserve")
        r1 = await client.get("/items/widget-1/reserve")
        print(f"  status={r1.status_code} body={r1.json()}")

        print("\n[2] Out of stock — GET /items/sold-out-widget/reserve")
        r2 = await client.get("/items/sold-out-widget/reserve")
        print(f"  status={r2.status_code} content-type={r2.headers.get('content-type')}")
        print(f"  body={r2.json()}")

    print("\n" + "─" * 55)
    body = r2.json()
    required_fields = {"type", "title", "status", "detail", "instance"}
    checks = {
        "status code == 409": r2.status_code == 409,
        "Content-Type is application/problem+json": r2.headers.get("content-type", "").startswith(
            "application/problem+json"
        ),
        "all 5 RFC 7807 fields present": required_fields.issubset(body.keys()),
        "status field matches HTTP status": body.get("status") == 409,
        "instance == request path": body.get("instance") == "/items/sold-out-widget/reserve",
    }
    for label, ok in checks.items():
        print(f"  {'✅' if ok else '❌'} {label}")

    if all(checks.values()):
        print("\n✅ PASS — error response is correctly RFC 7807 shaped")
    else:
        print("\n❌ FAIL")
        missing = required_fields - body.keys()
        if missing:
            print(f"   Missing fields: {missing} — check TODO 2's body dict.")
        if not checks["Content-Type is application/problem+json"]:
            print("   Content-Type wrong — check `media_type=` on the JSONResponse in TODO 2.")
        if not checks["status code == 409"]:
            print("   Status code wrong — check TODO 1's `status = 409` and TODO 2's `status_code=exc.status`.")

    print("""
THINK (answer out loud):
  1. Why does the problem body repeat `status` when the HTTP response line
     already carries it? What consumer would care about the body copy?
  2. `type` is meant to be a dereferenceable URI in a mature API (a page
     documenting that problem type). What's the fallback value RFC 7807
     defines when you don't have one yet?
  3. How would you extend this pattern to also reshape FastAPI's *built-in*
     validation errors (422) into the same problem+json envelope, so
     clients only ever parse one error shape?
  4. Where does `instance` differ from `type` conceptually — one identifies
     a category of problem, the other identifies this ONE occurrence. Why
     does that distinction matter for log correlation?
""")


if __name__ == "__main__":
    asyncio.run(main())
