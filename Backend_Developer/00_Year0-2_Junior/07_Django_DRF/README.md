# 🎯 Django + DRF — Mini-Index (47 topics)

> Django aur Django REST Framework ab **physically alag folders** me hain — [`Django/`](Django/) aur [`DRF/`](DRF/) —
> taaki Django ka core-framework topic padhte waqt DRF ka API-layer content beech me na aaye (aur vice versa).
> Files number order me hain; neeche **theme-wise** group kiye hain.
>
> **Study order:** pehle [`Django/`](Django/) 00→09-range (core + ORM), fir [`DRF/`](DRF/) 02,07,18 (API basics),
> fir dono me topic-wise deep dive. Har `.md` ke saath uska code [`practical/`](practical/) me hai (Django `00` intro hai, uska practical nahi).
> Kuch original files (Django + DRF dono cover karte the) content-level split ho gaye — dono taraf cross-link diya hai.
>
> Parent: [00_Year0-2_Junior](../) · Related: [FastAPI](../06_FastAPI/) · [Database_SQL](../04_Database_SQL/) · [Framework-agnostic REST API concepts (versioning, idempotency, rate limiting, webhooks, HATEOAS...)](../../01_Year3-4_Mid/02_API_Design/)

---

## 🐍 [`Django/`](Django/) — Core Framework (34 topics)

### 1. Core Django (MVT, Forms, Basics)
| # | Topic |
|---|---|
| 00 | [Django Basics & Definition](Django/00_django_basics_definition.md) |
| 32 | [Django Forms — Deep](Django/32_django_forms_deep.md) |
| 37 | [URLs / Views / Templates / Apps — Deep](Django/37_django_urls_views_templates_apps_deep.md) |
| 38 | [Model Inheritance, Meta & Constraints](Django/38_django_model_inheritance_meta_constraints.md) |

### 2. ORM & Data Access
| # | Topic |
|---|---|
| 01 | [ORM Deep Dive](Django/01_orm_deep_dive.md) |
| 05 | [Custom Managers & QuerySets](Django/05_custom_managers_querysets.md) |
| 09 | [Advanced ORM — Subquery](Django/09_advanced_orm_subquery.md) |
| 15 | [N+1 Query Detection](Django/15_n_plus_one_detection.md) |
| 20 | [Generic Relations](Django/20_generic_relations.md) |
| 33 | [QuerySet Internals](Django/33_queryset_internals.md) |
| 34 | [Transactions — Deep](Django/34_transactions_deep.md) |
| 36 | [F() Expressions & Atomic Updates](Django/36_f_expressions_atomic_updates.md) |

### 3. Auth & Security (Django-level)
| # | Topic |
|---|---|
| 16 | [Security Hardening](Django/16_security_hardening.md) |
| 21 | [Audit Logging](Django/21_audit_logging.md) |
| 27 | [Custom User Model & Auth](Django/27_custom_user_model_auth.md) |
| 44 | [CORS Handling](Django/44_cors_handling.md) |

### 4. Async, Realtime & Tasks
| # | Topic |
|---|---|
| 03 | [Channels & Middleware](Django/03_django_channels_middleware.md) |
| 08 | [Internals — Signals & Async](Django/08_internals_signals_async.md) |
| 19 | [Async ORM (Django 5)](Django/19_async_orm_django5.md) |
| 30 | [Channels — Deep](Django/30_channels_deep.md) |
| 31 | [Celery + Django Integration](Django/31_celery_django_integration.md) |

### 5. Architecture & Scaling
| # | Topic |
|---|---|
| 04 | [Advanced Patterns (Custom User, Transactions, Caching, Admin)](Django/04_advanced_patterns.md) |
| 10 | [Multi-Tenant Architecture](Django/10_multitenant_architecture.md) |
| 12 | [Caching Framework](Django/12_caching_framework.md) |
| 13 | [Multi-DB Routing](Django/13_multi_db_routing.md) |
| 25 | [Zero-Downtime Migrations](Django/25_zero_downtime_migrations.md) |

### 6. Ops, Tooling & Admin
| # | Topic |
|---|---|
| 11 | [Management Commands](Django/11_management_commands.md) |
| 14 | [Admin Customization](Django/14_admin_customization.md) |
| 17 | [Storage Backends (S3)](Django/17_storage_backends_s3.md) |
| 23 | [Settings & 12-Factor](Django/23_settings_12factor.md) |
| 35 | [Django Email](Django/35_django_email.md) |
| 39 | [i18n / l10n](Django/39_django_i18n_l10n.md) |

### 7. Gap-Fill (later additions)
| # | Topic |
|---|---|
| 40 | [MVT, Fields & Relationships — gaps](Django/40_django_mvt_fields_relationships_gaps.md) |
| 41 | [Middleware, Signals & Testing — gaps](Django/41_django_middleware_signals_testing_gaps.md) |

---

## 🔌 [`DRF/`](DRF/) — Django REST Framework, API layer (13 topics)

### 1. Building APIs
| # | Topic |
|---|---|
| 02 | [ViewSets, Serializers & Auth](DRF/02_viewsets_serializers_auth.md) |
| 07 | [GenericAPIView & Mixins](DRF/07_genericapiview_mixins.md) |
| 18 | [DRF Advanced Patterns](DRF/18_drf_advanced_patterns.md) |
| 04 | [Advanced Patterns (Filtering, Nested Write, to_representation, Throttling)](DRF/04_advanced_patterns.md) |
| 42 | [DRF Serializers Advanced — gaps](DRF/42_drf_serializers_advanced_gaps.md) |

### 2. Requests, Files & Content
| # | Topic |
|---|---|
| 24 | [DRF File Uploads](DRF/24_drf_file_uploads.md) |
| 43 | [DRF Content Negotiation](DRF/43_drf_content_negotiation.md) |
| 29 | [DRF Filtering — Deep](DRF/29_drf_filtering_deep.md) |

### 3. Versioning, Errors & Permissions
| # | Topic |
|---|---|
| 26 | [DRF API Versioning](DRF/26_drf_api_versioning.md) |
| 28 | [DRF Custom Exception Handler](DRF/28_drf_exception_handler.md) |
| 22 | [Object-Level Permissions](DRF/22_object_level_permissions.md) |

### 4. Testing & Docs
| # | Topic |
|---|---|
| 06 | [API Testing — Complete Guide](DRF/06_testing.md) |
| 10 | [API Documentation (drf-spectacular)](DRF/10_api_documentation.md) |

---

*47 topics (34 Django + 13 DRF) grouped by framework, then by theme. Interview ke liye Django's group 2 (ORM) aur DRF's group 1 (Building APIs) + group 3 (Versioning/Errors/Permissions) sabse zyada matter karte hain. Runnable code (shared Django project, both Django and DRF scripts import from it) → [`practical/`](practical/). Framework-agnostic REST concepts (that apply to any framework, not just Django/DRF) → [`01_Year3-4_Mid/02_API_Design`](../../01_Year3-4_Mid/02_API_Design/).*
