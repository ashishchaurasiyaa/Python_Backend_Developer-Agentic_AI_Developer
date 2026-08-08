# 🎯 Django + DRF — Mini-Index (45 topics)

> Django aur Django REST Framework ka full backend coverage — basics se le kar internals, scaling, aur production hardening tak. Files number order me hain; neeche **theme-wise** group kiye hain.
>
> **Study order:** pehli baar 00→09 sequence me (core + ORM + DRF basics), fir topic-wise deep dive. Har `.md` ke saath uska code [`practical/`](practical/) me hai.
>
> Parent: [00_Year0-2_Junior](../) · Related: [FastAPI](../06_FastAPI/) · [Database_SQL](../04_Database_SQL/)

---

## 1. Core Django (MVT, Forms, Basics)
| # | Topic |
|---|---|
| 00 | [Django Basics & Definition](00_django_basics_definition.md) |
| 32 | [Django Forms — Deep](32_django_forms_deep.md) |
| 37 | [URLs / Views / Templates / Apps — Deep](37_django_urls_views_templates_apps_deep.md) |
| 38 | [Model Inheritance, Meta & Constraints](38_django_model_inheritance_meta_constraints.md) |

## 2. ORM & Data Access
| # | Topic |
|---|---|
| 01 | [ORM Deep Dive](01_orm_deep_dive.md) |
| 05 | [Custom Managers & QuerySets](05_custom_managers_querysets.md) |
| 09 | [Advanced ORM — Subquery](09_advanced_orm_subquery.md) |
| 15 | [N+1 Query Detection](15_n_plus_one_detection.md) |
| 20 | [Generic Relations](20_generic_relations.md) |
| 33 | [QuerySet Internals](33_queryset_internals.md) |
| 34 | [Transactions — Deep](34_transactions_deep.md) |
| 36 | [F() Expressions & Atomic Updates](36_f_expressions_atomic_updates.md) |

## 3. DRF (Building APIs)
| # | Topic |
|---|---|
| 02 | [ViewSets, Serializers & Auth](02_viewsets_serializers_auth.md) |
| 07 | [GenericAPIView & Mixins](07_genericapiview_mixins.md) |
| 18 | [DRF Advanced Patterns](18_drf_advanced_patterns.md) |
| 24 | [DRF File Uploads](24_drf_file_uploads.md) |
| 26 | [DRF API Versioning](26_drf_api_versioning.md) |
| 28 | [DRF Exception Handler](28_drf_exception_handler.md) |
| 29 | [DRF Filtering — Deep](29_drf_filtering_deep.md) |
| 43 | [DRF Content Negotiation](43_drf_content_negotiation.md) |

## 4. Auth & Security
| # | Topic |
|---|---|
| 16 | [Security Hardening](16_security_hardening.md) |
| 21 | [Audit Logging](21_audit_logging.md) |
| 22 | [Object-Level Permissions](22_object_level_permissions.md) |
| 27 | [Custom User Model & Auth](27_custom_user_model_auth.md) |
| 44 | [CORS Handling](44_cors_handling.md) |

## 5. Async, Realtime & Tasks
| # | Topic |
|---|---|
| 03 | [Channels & Middleware](03_django_channels_middleware.md) |
| 08 | [Internals — Signals & Async](08_internals_signals_async.md) |
| 19 | [Async ORM (Django 5)](19_async_orm_django5.md) |
| 30 | [Channels — Deep](30_channels_deep.md) |
| 31 | [Celery + Django Integration](31_celery_django_integration.md) |

## 6. Architecture & Scaling
| # | Topic |
|---|---|
| 04 | [Advanced Patterns](04_advanced_patterns.md) |
| 10 | [Multi-Tenant & API Docs](10_multitenant_apidocs.md) |
| 12 | [Caching Framework](12_caching_framework.md) |
| 13 | [Multi-DB Routing](13_multi_db_routing.md) |
| 25 | [Zero-Downtime Migrations](25_zero_downtime_migrations.md) |

## 7. Ops, Tooling & Admin
| # | Topic |
|---|---|
| 06 | [Testing](06_testing.md) |
| 11 | [Management Commands](11_management_commands.md) |
| 14 | [Admin Customization](14_admin_customization.md) |
| 17 | [Storage Backends (S3)](17_storage_backends_s3.md) |
| 23 | [Settings & 12-Factor](23_settings_12factor.md) |
| 35 | [Django Email](35_django_email.md) |
| 39 | [i18n / l10n](39_django_i18n_l10n.md) |

## 8. Gap-Fill (later additions)
| # | Topic |
|---|---|
| 40 | [MVT, Fields & Relationships — gaps](40_django_mvt_fields_relationships_gaps.md) |
| 41 | [Middleware, Signals & Testing — gaps](41_django_middleware_signals_testing_gaps.md) |
| 42 | [DRF Serializers Advanced — gaps](42_drf_serializers_advanced_gaps.md) |

---

*45 topics grouped into 8 themes. Interview ke liye groups 2 (ORM), 3 (DRF) aur 4 (Auth) sabse zyada matter karte hain. Runnable code → [`practical/`](practical/).*
