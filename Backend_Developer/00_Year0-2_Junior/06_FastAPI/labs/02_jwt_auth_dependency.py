"""
FastAPI Lab 02 — JWT Auth Dependency
======================================
OBJECTIVE: implement token creation and a `get_current_user` dependency that
correctly rejects missing, malformed, AND expired tokens with 401 — not 200.

TASK:
  1. TODO 1: implement `create_access_token()` — encode a JWT with an `exp`
     claim.
  2. TODO 2: implement `get_current_user()` — decode + validate the token,
     raise 401 on any failure (missing header, bad signature, expired).
  3. Run: python 02_jwt_auth_dependency.py

Prereq: pip install fastapi httpx pyjwt
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from httpx import ASGITransport, AsyncClient

SECRET_KEY = "lab-secret-do-not-use-in-prod-min-32-bytes-long"
ALGORITHM = "HS256"

bearer_scheme = HTTPBearer(auto_error=False)


# ─────────────────────────────────────────────────────────────
# TODO 1: build a signed JWT that expires `expires_minutes` from now.
#   A JWT without an `exp` claim never expires — that's the #1 real-world
#   JWT bug. Every access token needs one.
#   Hint:
#       payload = {"sub": subject, "exp": datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)}
#       return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
def create_access_token(subject: str, expires_minutes: int = 15) -> str:
    return "TODO-not-a-real-token"
# ─────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────
# TODO 2: decode + validate the bearer token, return the subject on success,
#   raise HTTPException(401) on ANY failure — missing header, bad signature,
#   OR expired token (jwt.decode raises jwt.ExpiredSignatureError for the
#   last one; jwt.PyJWTError is the base class that catches all JWT errors).
#   Hint:
#       if credentials is None:
#           raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing token")
#       try:
#           payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
#       except jwt.PyJWTError:
#           raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or expired token")
#       return payload["sub"]
async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    return "TODO-always-returns-fixed-user"  # WRONG: never checks the token at all
# ─────────────────────────────────────────────────────────────


app = FastAPI(title="Lab 02 — JWT Auth Dependency")


@app.get("/public")
async def public():
    return {"message": "anyone can see this"}


@app.get("/me")
async def me(user: str = Depends(get_current_user)):
    return {"user": user}


async def main() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:

        print("\n[1] No token — GET /me")
        r1 = await client.get("/me")
        print(f"  status={r1.status_code}")

        print("\n[2] Valid token — GET /me")
        good_token = create_access_token("alice")
        r2 = await client.get("/me", headers={"Authorization": f"Bearer {good_token}"})
        print(f"  status={r2.status_code} body={r2.text}")

        print("\n[3] Expired token — GET /me")
        expired_token = create_access_token("alice", expires_minutes=-5)  # already expired
        r3 = await client.get("/me", headers={"Authorization": f"Bearer {expired_token}"})
        print(f"  status={r3.status_code}")

        print("\n[4] Garbage token — GET /me")
        r4 = await client.get("/me", headers={"Authorization": "Bearer not-a-jwt-at-all"})
        print(f"  status={r4.status_code}")

    print("\n" + "─" * 55)
    checks = {
        "no token → 401": r1.status_code == 401,
        "valid token → 200 + correct user": r2.status_code == 200 and r2.json().get("user") == "alice",
        "expired token → 401 (NOT 200)": r3.status_code == 401,
        "garbage token → 401": r4.status_code == 401,
    }
    for label, ok in checks.items():
        print(f"  {'✅' if ok else '❌'} {label}")

    if all(checks.values()):
        print("\n✅ PASS — all four auth cases behave correctly")
    else:
        print("\n❌ FAIL")
        if not checks["valid token → 200 + correct user"]:
            print("   TODO 1 or TODO 2 likely wrong — a real valid token should authenticate.")
        if not checks["expired token → 401 (NOT 200)"]:
            print("   This is the classic bug: TODO 1 forgot the `exp` claim, or TODO 2")
            print("   isn't catching jwt.ExpiredSignatureError (make sure it's under PyJWTError).")
        if not checks["no token → 401"] or not checks["garbage token → 401"]:
            print("   TODO 2 isn't rejecting missing/invalid tokens — check the credentials is-None")
            print("   and try/except paths.")

    print("""
THINK (answer out loud):
  1. Why is `exp` non-negotiable on an access token? What's the blast radius
     of a token that never expires and leaks?
  2. `jwt.PyJWTError` catches ExpiredSignatureError, InvalidSignatureError,
     DecodeError, etc. in one except block — when would you want to
     distinguish "expired" from "tampered" in the response, and why might
     you NOT want to (info leakage to an attacker)?
  3. This lab stores the secret as a literal string. What changes in a real
     deployment (rotation, asymmetric RS256 + JWKS, secret storage)?
  4. Where would a refresh-token flow fit around this dependency?
""")


if __name__ == "__main__":
    asyncio.run(main())
