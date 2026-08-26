# Django DRF — Advanced Topic Labs

5 labs, Kafka/Celery format: TODO stubs → implement → PASS/FAIL verify → SOCH aloud.

## Setup

```bash
cd Backend_Developer/00_Year0-2_Junior/07_Django_DRF/practical/
pip install -r requirements.txt

# Run migrations first (uses SQLite by default)
python manage.py migrate
```

## How to Run Each Lab

```bash
# Lab 01 — Transactions + F() + select_for_update
pytest labs/lab_01_transactions.py -v -p no:odoo

# Lab 02 — API Versioning
pytest labs/lab_02_api_versioning.py -v -p no:odoo

# Lab 03 — Custom CSV Renderer
pytest labs/lab_03_csv_renderer.py -v -p no:odoo

# Lab 04 — Django Signals
pytest labs/lab_04_signals.py -v -p no:odoo

# Lab 05 — Custom Throttling
pytest labs/lab_05_throttling.py -v -p no:odoo

# All labs in one shot
pytest labs/ -v -p no:odoo
```

## Lab Summary

| Lab | Topic | Key Concept | TODOs |
|-----|-------|-------------|-------|
| 01  | Transactions | F() vs select_for_update | 4 functions |
| 02  | API Versioning | request.version + serializer routing | 3 items |
| 03  | CSV Renderer | BaseRenderer.render() | 2 classes |
| 04  | Signals | post_save connect/disconnect | 3 handlers |
| 05  | Throttling | AnonRateThrottle scope | 3 classes |
| 06  | N+1 + select_related + prefetch_related | Query count proof via CaptureQueriesContext | 5 functions |
| 07  | Nested Serializers + Validation | M2M create/update, cross-field validate() | 5 items |
| 08  | Custom Middleware | CorrelationID, SlowRequest, BlockedIP, Maintenance | 4 classes |
| 09  | Cursor vs Offset Pagination | Stability demo, COUNT difference | 4 classes |
| 10  | Cache-Aside + Invalidation + Stampede | cache.get/set/delete, lock pattern | 4 functions |
| 11  | RBAC + Object-Level Permissions | has_permission vs has_object_permission | 4 classes |
| 12  | Async Views + sync_to_async | asyncio.gather, SynchronousOnlyOperation | 4 functions |

## Run New Labs

```bash
# Lab 06 — N+1 query problem
pytest labs/lab_06_n_plus_one_select_related_prefetch.py -v -p no:odoo

# Lab 07 — Nested Serializers
pytest labs/lab_07_nested_serializers_validation.py -v -p no:odoo

# Lab 08 — Custom Middleware
pytest labs/lab_08_custom_middleware.py -v -p no:odoo

# Lab 09 — Cursor vs Offset Pagination
pytest labs/lab_09_cursor_vs_offset_pagination.py -v -p no:odoo

# Lab 10 — Caching + Invalidation
pytest labs/lab_10_caching_invalidation.py -v -p no:odoo

# Lab 11 — RBAC + Object Permissions
pytest labs/lab_11_rbac_object_permissions.py -v -p no:odoo

# Lab 12 — Async Views
pytest labs/lab_12_async_views_sync_boundary.py -v -p no:odoo
```

## PASS/FAIL Convention

- `FAIL:` prefix in assert message = your TODO is wrong
- `NotImplementedError` = TODO not filled in yet
- All tests PASS = lab complete, move to next lab

## SOCH Protocol

SOCH questions are at the bottom of each lab file.
**Answer them ALOUD** (not in your head) before moving to the next lab.
Spoken explanation = interview preparation.
