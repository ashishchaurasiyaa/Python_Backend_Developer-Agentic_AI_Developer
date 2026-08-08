# gRPC Labs — Runnable Exercises

> `../practical/` me production-quality **reference modules** hain (padhne ke liye) — lekin unme koi
> real `.proto` nahi hai, sirf hand-rolled fake `GrpcServer`/`RpcContext` classes hain (except
> `03_grpc_observability_testing_practical.py`, jo real `grpc` + in-process server use karta hai).
> Yeh folder **chalane** ke liye hai: ek REAL `.proto` file, `grpc_tools.protoc` se generate hue
> REAL stubs (`user_service_pb2.py` / `user_service_pb2_grpc.py`), aur in-process gRPC server jo har
> lab khud start/stop karta hai (no docker-compose needed — the gRPC server IS the infra).

## Setup (ek baar)

```bash
cd Backend_Developer/01_Year3-4_Mid/06_gRPC/labs
pip install grpcio grpcio-tools
```

Stubs already committed hain — chalane ke liye kuch regenerate nahi karna. Agar tum
`user_service.proto` edit karo, regenerate karo:

```bash
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. user_service.proto
```

Yeh `user_service_pb2.py` (messages) aur `user_service_pb2_grpc.py` (stub + servicer base
class) overwrite kar dega.

> **Version note:** generated `_pb2_grpc.py` file me ek runtime check hai — jis `grpcio` version se
> generate hua, us se **purana** `grpcio` installed hone pe `RuntimeError` aayega. `pip install
> grpcio grpcio-tools` dono ek saath install karo taaki versions match rahein.

## Labs

| # | Lab | Kya sikhata hai | Verify kaise |
|---|---|---|---|
| 1 | [01_unary_rpc](01_unary_rpc.py) | Unary RPC basics: servicer methods, in-memory store, `context.abort(NOT_FOUND)` | CreateUser → GetUser round-trip, fields exactly match |
| 2 | [02_server_streaming](02_server_streaming.py) | Server-streaming: `yield` multiple responses, client `for` iteration | N users, IN ORDER, arrival timestamps prove genuine streaming (not one batch) |
| 3 | [03_deadlines_retries](03_deadlines_retries.py) | Client `timeout=`, `DEADLINE_EXCEEDED`, retry-with-backoff on `UNAVAILABLE` | Deadline actually fires; retry succeeds on the exact expected attempt |
| 4 | [04_interceptor_auth](04_interceptor_auth.py) | Server `grpc.ServerInterceptor` for auth via metadata | Call without header → `UNAUTHENTICATED`; with correct header → succeeds (servicer has zero auth logic of its own — only the interceptor can be making it pass) |

Har file me **TODO** blocks hain — pehle khud bharo, phir `python 0N_....py` chalao. Har lab apna
verification khud print karta hai (✅/❌), aur unfilled TODO chhodne pe **loud, specific failure**
deta hai (exact TODO number bata ke) — silently pass nahi hota.

## Protocol

```
1. Lab file kholo, docstring me OBJECTIVE + TASK padho
2. TODO bharo (reference: user_service.proto, ../practical/03_grpc_observability_testing_practical.py
   real grpc usage ke liye — baaki practical/*.py sirf simulation hain)
3. Chalao → ✅ mile to agla lab; ❌ mile to output padho, fix karo
4. Lab ke end me "SOCH" section hota hai — usme diye sawaalon ka
   jawab bolke do. Interview me yahi poocha jaata hai, code nahi.
```

## Files

```
user_service.proto          ← source of truth: UserService (GetUser, CreateUser, ListUsers)
user_service_pb2.py         ← generated: message classes (User, GetUserRequest, ...)
user_service_pb2_grpc.py    ← generated: UserServiceStub, UserServiceServicer, add_..._to_server
01_unary_rpc.py
02_server_streaming.py
03_deadlines_retries.py
04_interceptor_auth.py
```

Har lab apna server khud start karta hai (`grpc.server(futures.ThreadPoolExecutor(...))`,
`add_insecure_port("[::]:0")` = random free port) as a background thread pool inside the same
process — no separate terminal, no docker.

## Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError: user_service_pb2` | Same directory se chalao, ya check karo `sys.path.insert` line file me hai |
| `RuntimeError: ... depends on grpcio>=X` | `pip install --upgrade grpcio` (ya `grpcio grpcio-tools` dono fresh install karo, saath saath) |
| Lab 03 deadline test flaky (galat pass/fail) | Slow machine pe `CLIENT_DEADLINE`/`SLOW_DELAY` gap badhao (file ke top pe constants) |
| `Address already in use` nahi aana chahiye | Har lab `[::]:0` use karta hai (random port) — agar phir bhi issue ho, doosra `python` process check karo |

---

**Related:** [theory files](../) · [reference modules](../practical/) · [Kafka labs](../../07_Kafka/labs/) · [RabbitMQ exercises](../../08_RabbitMQ/exercises/)
