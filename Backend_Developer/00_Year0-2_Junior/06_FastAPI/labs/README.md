# FastAPI Labs — Runnable Exercises

> [`../practical/`](../practical/) holds 42 production-quality **reference modules** — read them to see the shape of the real thing. This folder is for **doing**: real TODO stubs you fill in, wired to endpoints you actually call, with each lab verifying its own behavior and printing PASS/FAIL.

## Setup (once)

```bash
cd Backend_Developer/00_Year0-2_Junior/06_FastAPI/labs
pip install fastapi httpx pyjwt sqlalchemy aiosqlite pytest pytest-asyncio
```

No Docker and no external services are required for any of these five labs — everything runs in-process. Lab 3 needs a database, but it uses `aiosqlite` (in-memory) instead of Postgres for exactly this reason: it keeps every lab in this folder runnable with nothing but `pip install`. If you want Postgres parity with the rest of this repo's labs (Kafka/Celery), swap Lab 3's `DATABASE_URL` for `postgresql+asyncpg://...` — the async SQLAlchemy code itself doesn't change.

## Labs

| # | Lab | What it teaches | Verify how |
|---|---|---|---|
| 1 | [01_dependency_injection_db_session](01_dependency_injection_db_session.py) | `yield`-based dependencies, teardown-on-error guarantee | Fake session's open/close counters must match after both a normal request and a request where the endpoint raises |
| 2 | [02_jwt_auth_dependency](02_jwt_auth_dependency.py) | JWT creation, `get_current_user` dependency, 401 handling | No token / expired token / garbage token all get 401; a valid token gets 200 with the right subject |
| 3 | [03_async_sqlalchemy_crud](03_async_sqlalchemy_crud.py) | Async SQLAlchemy 2.0 CRUD against a real engine | Real `pytest` asserts: `user.id is not None`, fetched row matches, missing id returns `None`, duplicate email raises `IntegrityError` |
| 4 | [04_background_task_idempotency](04_background_task_idempotency.py) | `BackgroundTasks` + `Idempotency-Key` dedup | Same key fired twice increments a side-effect counter once; a different key increments it again |
| 5 | [05_rfc7807_error_handling](05_rfc7807_error_handling.py) | Custom exception + handler → RFC 7807 `problem+json` | Response `Content-Type` and all five required fields (`type`, `title`, `status`, `detail`, `instance`) are checked |

Every file has **TODO** blocks with a hint naming the actual API to use. Fill them in, then run the file — each lab prints its own ✅/❌ verdict with specific guidance on which TODO is likely still wrong.

## Protocol

```
1. Open the lab file, read the module docstring's OBJECTIVE + TASK
2. Fill in the TODO block(s) — hints point at ../practical/ and the
   matching ../*.md theory file for background
3. Run it:
     python 0N_....py                       (labs 1, 2, 4, 5)
     pytest 03_async_sqlalchemy_crud.py -v   (lab 3)
   ✅ → move to the next lab; ❌ → read the printed guidance, fix, rerun
4. Every lab ends with a "THINK" section — answer those out loud before
   moving on. That's what actually gets asked in interviews, not the code.
```

## Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'jwt'` / `'aiosqlite'` | Re-run the `pip install` line above — Lab 2 needs `pyjwt`, Lab 3 needs `aiosqlite` |
| `pytest` immediately fails with `ModuleNotFoundError: No module named 'odoo'` | An unrelated global `pytest-odoo` plugin is installed on this machine and autoloads for every project. Run `pytest 03_async_sqlalchemy_crud.py -v -p no:odoo` instead |
| Lab 2's expired-token case returns 200 instead of 401 | TODO 1 forgot the `exp` claim, or TODO 2 isn't catching `jwt.ExpiredSignatureError` (make sure it's under the broader `jwt.PyJWTError`) |
| Lab 1's `closed_count` stays 0 | `get_db()` is still using `return` instead of `yield` + `finally` |
| Lab 4's counter goes above 2 | TODO 1 isn't checking `seen_keys` before scheduling the background task |

---

**Related:** [theory files](../) · [reference modules](../practical/) · [Kafka labs](../../../01_Year3-4_Mid/07_Kafka/labs/) (the template this folder follows) · [Celery labs](../../../01_Year3-4_Mid/09_Celery/labs/)
