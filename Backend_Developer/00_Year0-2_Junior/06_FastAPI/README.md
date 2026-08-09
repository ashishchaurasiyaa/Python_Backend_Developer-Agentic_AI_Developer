# ⚡ FastAPI — Mini-Index (43 topics)

> FastAPI ka full backend coverage — routing basics se le kar ASGI internals, realtime, security, performance, aur LLM/AI backends tak. Files number order me hain; neeche **theme-wise** group kiye hain.
>
> **Study order:** pehli baar 01→13 sequence me (core → data → security → architecture → internals), fir topic-wise.
> Zyadatar `.md` ke saath code [`practical/`](practical/) me hai *(41 aur 42 ke practicals nahi hain — wo config/deployment topics hain)*.
>
> ## 🧪 Labs — [`labs/`](labs/)
> Padhne se kaam nahi banega. [`labs/`](labs/) me **5 TODO-stub exercises** hain (khud likho, self-verify hota hai) — [labs/README.md](labs/README.md) padho.
>
> Parent: [00_Year0-2_Junior](../) · Related: [Django_DRF](../07_Django_DRF/) · [Database_SQL](../04_Database_SQL/) · [Testing](../10_Testing/)

---

## 1. Core & Request Handling
| # | Topic |
|---|---|
| 01 | [Routing & Params](01_routing_params.md) |
| 02 | [Dependency Injection](02_dependency_injection.md) |
| 05 | [Exception Handling & Response Schema](05_exception_handling_response_schema.md) |
| 11 | [Forms, Cookies & OpenAPI](11_forms_cookies_openapi.md) |
| 21 | [RFC 7807 Problem Details](21_rfc7807_problem_details.md) |
| 29 | [DI — Advanced Patterns](29_di_advanced_patterns.md) |
| 42 | [StaticFiles & Mounting](42_fastapi_staticfiles_mount.md) |

## 2. Data & Persistence (SQLAlchemy / Pydantic)
| # | Topic |
|---|---|
| 04 | [Testing + SQLAlchemy](04_testing_sqlalchemy.md) |
| 08 | [Pydantic Settings & Alembic](08_pydantic_settings_alembic.md) |
| 09 | [SQLAlchemy Advanced](09_sqlalchemy_advanced.md) |
| 18 | [Pydantic v2 Advanced](18_pydantic_v2_advanced.md) |

## 3. Security
| # | Topic |
|---|---|
| 06 | [Security — JWT & RBAC](06_security_jwt_rbac.md) |
| 19 | [OAuth2 — Full Flows](19_oauth2_full_flows.md) |
| 20 | [OWASP API Top 10](20_owasp_api_top10.md) |
| 22 | [HMAC Webhooks & Idempotency](22_hmac_webhooks_idempotency.md) |

## 4. Realtime & Streaming
| # | Topic |
|---|---|
| 03 | [Middleware & WebSockets](03_middleware_websockets.md) |
| 15 | [WebSocket Scaling Patterns](15_websocket_scaling_patterns.md) |
| 26 | [SSE — Deep](26_sse_deep.md) |

## 5. API Protocols & Versioning
| # | Topic |
|---|---|
| 17 | [API Versioning & Streaming](17_api_versioning_streaming.md) |
| 27 | [GraphQL (Strawberry)](27_graphql_strawberry.md) |
| 28 | [gRPC + FastAPI Hybrid](28_grpc_fastapi_hybrid.md) |

## 6. Architecture & Scaling
| # | Topic |
|---|---|
| 07 | [Advanced Patterns](07_advanced_patterns.md) |
| 12 | [Clean Architecture & DDD](12_clean_architecture_ddd.md) |
| 16 | [Multi-Tenant Architecture](16_multi_tenant_architecture.md) |

## 7. Performance & Internals
| # | Topic |
|---|---|
| 13 | [ASGI Internals & Uvicorn Tuning](13_asgi_internals_uvicorn_tuning.md) |
| 23 | [FastAPI Caching](23_fastapi_caching.md) |
| 30 | [Performance Profiling](30_performance_profiling.md) |
| 39 | [async def vs def & Threadpool — Deep](39_async_def_vs_def_threadpool_deep.md) |
| 41 | [Rate Limiting](41_fastapi_rate_limiting.md) |

## 8. Ops & Observability
| # | Topic |
|---|---|
| 10 | [Webhooks, Scheduler & Monitoring](10_webhooks_scheduler_monitoring.md) |
| 14 | [OpenTelemetry & Distributed Tracing](14_opentelemetry_distributed_tracing.md) |
| 24 | [Health Checks & K8s](24_health_checks_k8s.md) |
| 25 | [Structured Logging](25_structured_logging.md) |

## 9. AI / LLM Backends
| # | Topic |
|---|---|
| 31 | [LLM Integration with FastAPI](31_llm_integration_fastapi.md) |
| 32 | [Function-Calling Endpoints](32_function_calling_endpoints.md) |
| 33 | [Prompt Injection Security](33_prompt_injection_security.md) |
| 34 | [RAG Backend Architecture](34_rag_backend_architecture.md) |
| 35 | [MCP Server Implementation](35_mcp_server_implementation.md) |
| 36 | [Local LLM Serving](36_local_llm_serving.md) |
| 37 | [Voice Agent Backend](37_voice_agent_backend.md) |

## 10. Domain & Gap-Fill
| # | Topic |
|---|---|
| 38 | [Payment Gateway — Stripe & Ledger](38_payment_gateway_stripe_ledger.md) |
| 40 | [Request Body Advanced — gaps](40_request_body_advanced_gaps.md) |
| 43 | [Flask essentials vs FastAPI](43_flask_essentials_vs_fastapi.md) |

> **43 kyun padho:** bahut se India JDs me Flask likha hota hai, aur screener ka stock question hai
> *"FastAPI over Flask — kyun?"*. Us jawab ko specifics ke saath dena isi file me hai.

---

*43 topics grouped into 10 themes. Interview ke liye groups 1 (Core), 3 (Security), 6 (Architecture) aur 7 (Performance/Internals) sabse zyada matter karte hain; group 9 (AI backends) tere agentic-AI track se seedha connect hota hai. Runnable code → [`practical/`](practical/).*
