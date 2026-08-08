"""
FastAPI Lab 01 — DB Session Dependency (yield + teardown contract)
====================================================================
OBJECTIVE: build a `yield`-based dependency that opens a DB session, hands it
to the endpoint, and GUARANTEES cleanup runs — even when the endpoint raises.

TASK:
  1. TODO 1: implement `get_db()` as a generator dependency — open the
     session, `yield` it to the endpoint, then close it in a `finally` block.
  2. TODO 2: wire `get_db` into the `/users/{user_id}` endpoint via `Depends()`.
  3. Run: python 01_dependency_injection_db_session.py

Prereq: pip install fastapi httpx   (no Docker needed — everything is in-process)

Note: this lab drives the app with `httpx.AsyncClient(transport=ASGITransport(...))`
(same pattern as ../practical/07_testing_sqlalchemy.py) rather than
`fastapi.testclient.TestClient`, because `TestClient` requires an
httpx/starlette version pairing that doesn't always line up — the
ASGITransport route works with any recent httpx.
"""

from __future__ import annotations

import asyncio

from fastapi import Depends, FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient


# ==========================================================================
# FAKE SESSION — stands in for a real SQLAlchemy Session/AsyncSession.
# The important part for this lab isn't the DB driver, it's the LIFECYCLE:
# a session must be closed after every request, success or failure.
# ==========================================================================

class FakeSession:
    """Tracks open/close calls so the test can prove teardown actually ran."""

    opened_count = 0
    closed_count = 0

    def __init__(self) -> None:
        FakeSession.opened_count += 1
        self.is_closed = False

    def get_user(self, user_id: int) -> dict | None:
        users = {1: {"id": 1, "name": "Ada Lovelace"}, 2: {"id": 2, "name": "Alan Turing"}}
        return users.get(user_id)

    def close(self) -> None:
        self.is_closed = True
        FakeSession.closed_count += 1


# ─────────────────────────────────────────────────────────────
# TODO 1: implement the yield-dependency.
#   FastAPI dependencies that `yield` instead of `return` split into two
#   halves: everything before `yield` runs before the endpoint, everything
#   after runs after the endpoint returns — and Starlette guarantees the
#   after-half still runs if the endpoint raises, AS LONG AS it's wrapped
#   in try/finally here.
#   Hint:
#       def get_db():
#           session = FakeSession()
#           try:
#               yield session
#           finally:
#               session.close()
def get_db():
    session = FakeSession()
    return session  # WRONG: no yield, no finally — cleanup never runs
# ─────────────────────────────────────────────────────────────


app = FastAPI(title="Lab 01 — DB Session Dependency")


@app.get("/users/{user_id}")
def read_user(
    user_id: int,

    # ─────────────────────────────────────────────────────
    # TODO 2: wire get_db in via Depends() so FastAPI manages the
    #         open/yield/close lifecycle for this request.
    #         Hint: db: FakeSession = Depends(get_db)
    db=None,
    # ─────────────────────────────────────────────────────
):
    if db is None:
        raise HTTPException(status_code=500, detail="TODO 2 not wired — db dependency missing")
    user = db.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    return user


@app.get("/users/{user_id}/boom")
def read_user_boom(user_id: int, db=Depends(get_db)):
    """Deliberately raises AFTER the dependency has been injected — proves
    that cleanup runs even on the error path, not just the happy path."""
    raise HTTPException(status_code=500, detail="simulated failure mid-request")


async def main() -> None:
    FakeSession.opened_count = 0
    FakeSession.closed_count = 0

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        print("\n[1] Happy path — GET /users/1")
        resp = await client.get("/users/1")
        print(f"  status={resp.status_code} body={resp.json()}")

        print("\n[2] Error path — GET /users/1/boom (endpoint raises 500)")
        resp2 = await client.get("/users/1/boom")
        print(f"  status={resp2.status_code}")

    print("\n" + "─" * 55)
    print(f"  sessions opened: {FakeSession.opened_count}")
    print(f"  sessions closed: {FakeSession.closed_count}")

    ok_status = resp.status_code == 200 and resp.json() == {"id": 1, "name": "Ada Lovelace"}
    ok_teardown = FakeSession.opened_count == FakeSession.closed_count and FakeSession.closed_count >= 2

    if ok_status and ok_teardown:
        print(f"✅ PASS — request succeeded AND every opened session was closed "
              f"({FakeSession.closed_count}/{FakeSession.opened_count})")
    else:
        print("❌ FAIL")
        if not ok_status:
            print("   Response wrong — check TODO 2 (is db actually wired via Depends()?)")
        if not ok_teardown:
            print(f"   Teardown mismatch: opened={FakeSession.opened_count} "
                  f"closed={FakeSession.closed_count} — check TODO 1 (yield + finally).")
            print("   If closed_count is 0: get_db() is still using `return`, not `yield`.")

    print("""
THINK (answer out loud):
  1. Why must the `session.close()` live in a `finally` block instead of just
     after the `yield`? What happens on the error path if it doesn't?
  2. If `get_db` opened a transaction, where would `commit()` vs `rollback()`
     go relative to the `yield`?
  3. What's the difference between a dependency that `return`s a session and
     one that `yield`s it, from FastAPI's perspective?
  4. Would this same shape work for `async def get_db()` with an
     AsyncSession? What would change?
""")


if __name__ == "__main__":
    asyncio.run(main())
