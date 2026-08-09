# 🔌 API Design

> **20 theory + 15 practical.** Yeh wo module hai jo tumhare daily kaam se sabse zyada match karta hai —
> aur interview me sabse zyada "design karke dikhao" isi se aata hai.
>
> Numbering me 03 aur 21 nahi hain (kabhi bane hi nahi) — koi file missing nahi hai.

---

## 🔴 Interview ke liye pehle yeh 6

| # | Topic | Classic question |
|---|---|---|
| [01](01_rest_best_practices.md) | **REST best practices** | Base — status codes, resource naming, errors |
| [16](16_versioning_strategies_deep.md) | **Versioning** | "API me breaking change kaise karoge?" |
| [18](18_conditional_requests_deep.md) | **Idempotency + conditional requests** | "Payment API do baar call ho gaya — kya hoga?" |
| [07](07_rate_limiting_deep.md) | **Rate limiting** | Token bucket vs sliding window, 429 + Retry-After |
| [12](12_webhook_design_deep.md) | **Webhooks** | "Webhook deliver nahi hua to?" — retry, signature, replay |
| [14](14_rest_graphql_grpc.md) | **REST vs GraphQL vs gRPC** | "Kaunsa kab chuno" — senior judgment question |

---

## 📚 Poori list

### Core REST
| # | Topic | Practical |
|---|---|---|
| [01](01_rest_best_practices.md) 🔴 | REST best practices | [`01_api_design_practical.py`](practical/01_api_design_practical.py) |
| [02](02_api_advanced_patterns.md) | Advanced patterns | — |
| [22](22_put_patch_method_semantics_deep.md) | PUT vs PATCH semantics | — |
| [05](05_content_negotiation_design_patterns.md) | Content negotiation | — |
| [09](09_hateoas_jsonapi.md) | HATEOAS + JSON:API | [`09_hateoas_jsonapi.py`](practical/09_hateoas_jsonapi.py) |
| [18](18_conditional_requests_deep.md) 🔴 | Conditional requests, ETag, idempotency | [`18_...py`](practical/18_conditional_requests_deep.py) |

### Evolution + scale
| # | Topic | Practical |
|---|---|---|
| [16](16_versioning_strategies_deep.md) 🔴 | Versioning strategies | [`16_...py`](practical/16_versioning_strategies_deep.py) |
| [10](10_bulk_operations_design.md) | Bulk operations | [`10_...py`](practical/10_bulk_operations_design.py) |
| [11](11_file_upload_api_design.md) | File upload API design | [`11_...py`](practical/11_file_upload_api_design.py) |
| [07](07_rate_limiting_deep.md) 🔴 | Rate limiting deep | [`07_...py`](practical/07_rate_limiting_deep.py) |
| [20](20_http3_quic.md) | HTTP/3 + QUIC | — |

### Event-driven + realtime
| # | Topic | Practical |
|---|---|---|
| [12](12_webhook_design_deep.md) 🔴 | Webhook design | [`12_...py`](practical/12_webhook_design_deep.py) |
| [17](17_async_api_patterns.md) | Async API patterns (202 + polling) | [`17_...py`](practical/17_async_api_patterns.py) |
| [19](19_asyncapi_event_driven_spec.md) | AsyncAPI spec | — |
| [04](04_cors_openapi_sse.md) | CORS, OpenAPI, SSE | [`02_graphql_sse_websocket_practical.py`](practical/02_graphql_sse_websocket_practical.py) |

### Architecture + ops
| # | Topic | Practical |
|---|---|---|
| [14](14_rest_graphql_grpc.md) 🔴 | REST vs GraphQL vs gRPC | [`14_...py`](practical/14_rest_graphql_grpc.py) |
| [15](15_bff_pattern.md) | BFF pattern | [`15_bff_pattern.py`](practical/15_bff_pattern.py) |
| [06](06_graphql_strawberry_advanced.md) | GraphQL + Strawberry | [`03_graphql_strawberry_app.py`](practical/03_graphql_strawberry_app.py) |
| [08](08_api_security_hardening.md) | API security hardening | [`08_...py`](practical/08_api_security_hardening.py) |
| [13](13_api_monitoring_slo.md) | Monitoring + SLOs | [`13_...py`](practical/13_api_monitoring_slo.py) |

**Related:** [03_Security](../03_Security/README.md) · [12_GraphQL](../12_GraphQL/README.md) · [06_gRPC](../06_gRPC/README.md) · [FastAPI](../../00_Year0-2_Junior/06_FastAPI/) · [HLD_Theory](../../02_Year5%2B_Senior/01_System_Design/HLD_Theory/)
