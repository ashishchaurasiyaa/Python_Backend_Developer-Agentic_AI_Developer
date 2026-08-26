# FastAPI Labs — Runnable Exercises

> [`../practical/`](../practical/) holds 42 production-quality **reference modules** — read them to see the shape of the real thing. This folder is for **doing**: real TODO stubs you fill in, wired to endpoints you actually call, with each lab verifying its own behavior and printing PASS/FAIL.

## Setup (once)

```bash
cd Backend_Developer/00_Year0-2_Junior/06_FastAPI/labs
pip install fastapi httpx pyjwt sqlalchemy aiosqlite pytest pytest-asyncio pydantic[email] fakeredis
```

No Docker and no external services required — everything runs in-process. Lab 3 and 07 use `aiosqlite` (in-memory SQLite). Lab 10 uses `fakeredis` (in-process Redis — no server needed). To swap in real Postgres or Redis, change only the `DATABASE_URL` / Redis host string — the async API doesn't change.

## Labs

| # | Lab | What it teaches | How to run |
|---|---|---|---|
| 1 | [01_dependency_injection_db_session](01_dependency_injection_db_session.py) | `yield`-based dependencies, teardown guarantee | `python 01_*.py` |
| 2 | [02_jwt_auth_dependency](02_jwt_auth_dependency.py) | JWT creation, `get_current_user`, 401 handling | `python 02_*.py` |
| 3 | [03_async_sqlalchemy_crud](03_async_sqlalchemy_crud.py) | Async SQLAlchemy 2.0 CRUD | `pytest 03_*.py -v` |
| 4 | [04_background_task_idempotency](04_background_task_idempotency.py) | `BackgroundTasks` + idempotency key dedup | `python 04_*.py` |
| 5 | [05_rfc7807_error_handling](05_rfc7807_error_handling.py) | Custom exception → RFC 7807 `problem+json` | `python 05_*.py` |
| 6 | [06_pydantic_v2_validators](06_pydantic_v2_validators.py) | field_validator, model_validator, ConfigDict, computed_field, Annotated types | `python 06_*.py` |
| 7 | [07_async_sqlalchemy_transactions](07_async_sqlalchemy_transactions.py) | select_for_update, atomic transfers, rollback | `pytest 07_*.py -v` |
| 8 | [08_fastapi_testing_dependency_overrides](08_fastapi_testing_dependency_overrides.py) | dependency_overrides, AsyncClient, fixture teardown | `pytest 08_*.py -v` |
| 9 | [09_custom_fastapi_middleware](09_custom_fastapi_middleware.py) | BaseHTTPMiddleware: CorrelationID, Timing, BlockedIP, Maintenance | `python 09_*.py` |
| 10 | [10_redis_rate_limiting](10_redis_rate_limiting.py) | Fixed window, sliding window, token bucket via fakeredis | `python 10_*.py` |

Every file has **TODO** blocks with a hint naming the actual API to use. Fill them in, run the file — each lab prints its own ✅/❌ verdict.

## Protocol

```
1. Open the lab file, read the module docstring's OBJECTIVE + TASK
2. Fill in the TODO block(s) — hints show exact API / pattern to use
3. Run it:
     python 0N_*.py                                  (labs 1, 2, 4, 5, 6, 9, 10)
     pytest 0N_*.py -v  (or -v -p no:odoo)           (labs 3, 7, 8)
   ✅ → move to the next lab; ❌ → read the printed guidance, fix, rerun
4. Answer SOCH questions ALOUD before moving on — that's what interviews ask.
```

## Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'jwt'` / `'aiosqlite'` / `'fakeredis'` | Re-run the `pip install` line above |
| `pytest` fails with `ModuleNotFoundError: No module named 'odoo'` | Global pytest-odoo plugin conflict — run `pytest <file> -v -p no:odoo` |
| Lab 2's expired-token returns 200 | TODO 1 forgot `exp` claim, or TODO 2 isn't catching `jwt.ExpiredSignatureError` |
| Lab 6 `discounted_price` missing from response | Add `@computed_field` + `@property` decorators on the method |
| Lab 7 `select_for_update` ignored in SQLite | SQLite doesn't enforce row locks — the code is correct, Postgres behaviour differs |
| Lab 8 `clear_overrides` fixture not working | Ensure `autouse=True` on the fixture, and `app.dependency_overrides.clear()` after `yield` |
| Lab 10 `fakeredis` not found | `pip install fakeredis` — `fakeredis.aioredis` needs the base package |

---

**Related:** [theory files](../) · [reference modules](../practical/) · [Kafka labs](../../../01_Year3-4_Mid/07_Kafka/labs/) (the template this folder follows) · [Celery labs](../../../01_Year3-4_Mid/09_Celery/labs/)
