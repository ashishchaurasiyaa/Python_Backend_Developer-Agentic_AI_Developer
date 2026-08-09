# ⚡ gRPC

> **13 theory + 5 practical + 4 runnable labs** (asli `.proto` + generated stubs ke saath).
> Internal service-to-service communication ka standard. JD me `gRPC` dikhe to yeh module utha lo.

---

## 🔴 Pehle yeh 4

| # | Topic | Classic question |
|---|---|---|
| [01](01_grpc_python.md) | **gRPC in Python** | Base — proto, stubs, 4 RPC types |
| [07](07_protobuf_advanced.md) | **Protobuf advanced** | "Schema evolve kaise karoge bina consumer tode?" — field numbers, reserved |
| [04](04_grpc_resilience_retries.md) | **Deadlines + retries** | "Deadline propagate kyun karte hain?" 🔥 |
| [09](09_grpc_streaming_patterns.md) | **Streaming patterns** | Server/client/bidi — kab kaunsa |

---

## 📚 Poori list

### Core
| # | Topic | # | Topic |
|---|---|---|---|
| [01](01_grpc_python.md) 🔴 | gRPC in Python | [07](07_protobuf_advanced.md) 🔴 | Protobuf advanced |
| [09](09_grpc_streaming_patterns.md) 🔴 | Streaming patterns | [04](04_grpc_resilience_retries.md) 🔴 | Resilience, deadlines, retries |

### Production
| # | Topic | # | Topic |
|---|---|---|---|
| [02](02_grpc_production_deployment.md) | Production deployment | [03](03_grpc_security_mtls.md) | Security + mTLS |
| [05](05_grpc_observability.md) | Observability | [06](06_grpc_testing.md) | Testing |
| [08](08_grpc_performance_tuning.md) | Performance tuning | [13](13_grpc_client_side_load_balancing.md) | Client-side load balancing |
| [12](12_grpc_aws_deployment.md) | AWS deployment | | |

### Interop
| # | Topic | # | Topic |
|---|---|---|---|
| [10](10_grpc_web_browser.md) | gRPC-Web (browser) | [11](11_grpc_gateway_hybrid.md) | gRPC-gateway (REST + gRPC hybrid) |

---

## 🧪 Labs — [`labs/`](labs/)

Asli `user_service.proto` + committed `pb2` stubs — `protoc` chalane ki zaroorat nahi, seedha code likho.

| Lab | Kya |
|---|---|
| [01_unary_rpc](labs/01_unary_rpc.py) | Simple request/response |
| [02_server_streaming](labs/02_server_streaming.py) | Server streaming |
| [03_deadlines_retries](labs/03_deadlines_retries.py) | Deadline propagation + retry policy |
| [04_interceptor_auth](labs/04_interceptor_auth.py) | Interceptor se auth (middleware ka gRPC version) |

Runnable reference: [`practical/`](practical/) (5 files)

---

## ⚔️ Interview me: gRPC vs REST kab?

| Chuno | Kab |
|---|---|
| **gRPC** | Internal service-to-service, low latency, streaming, strict contract, polyglot teams |
| **REST** | Public API, browser clients, cacheable, debugging aasan, wide tooling |
| **GraphQL** | Client ko flexible query chahiye, multiple resources ek call me |

Poora comparison → [14_rest_graphql_grpc.md](../02_API_Design/14_rest_graphql_grpc.md)

**Related:** [02_API_Design](../02_API_Design/README.md) · [05_Microservices](../05_Microservices/README.md) · [HLD 63](../../02_Year5%2B_Senior/01_System_Design/HLD_Theory/63_GraphQL_vs_REST_vs_gRPC.md)
