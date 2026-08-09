# 🕸️ GraphQL

> **8 theory + 5 practical.** JD me GraphQL dikhe to yeh module utha lo.
> Interview me sabse zyada poocha jane wala: **N+1 problem** — aur uska DataLoader wala jawab.

---

## 🔴 Pehle yeh 3

| # | Topic | Classic question |
|---|---|---|
| [03](03_n_plus_one_dataloader.md) | **N+1 + DataLoader** | 🔥 "100 posts, har post ka author — kitni DB query?" |
| [06](06_security_best_practices.md) | **Security** | "Client `depth 50` ki query bhej de to?" — depth/complexity limit |
| [01](01_graphql_fundamentals.md) | **Fundamentals** | Schema, resolvers, query vs mutation vs subscription |

---

## 📚 Poori list

| # | Topic | Practical |
|---|---|---|
| [01](01_graphql_fundamentals.md) 🔴 | Fundamentals — schema, types, resolvers | — |
| [02](02_strawberry_fastapi.md) | Strawberry + FastAPI | [`02_strawberry_fastapi.py`](practical/02_strawberry_fastapi.py) |
| [03](03_n_plus_one_dataloader.md) 🔴 | N+1 problem + DataLoader | [`03_n_plus_one_dataloader.py`](practical/03_n_plus_one_dataloader.py) |
| [04](04_subscriptions_realtime.md) | Subscriptions (realtime) | [`04_subscriptions_realtime.py`](practical/04_subscriptions_realtime.py) |
| [05](05_federation_gateway.md) | Federation + gateway | [`05_federation_gateway.py`](practical/05_federation_gateway.py) |
| [06](06_security_best_practices.md) 🔴 | Security — depth/complexity limits, auth | [`06_...py`](practical/06_security_best_practices.py) |
| [07](07_federation_v2_persisted_queries.md) | Federation v2 + persisted queries | — |
| [08](08_error_handling_conventions.md) | Error handling conventions | — |

---

## 🎯 Do sawal jo pakka aayenge

**1. "N+1 kya hai, kaise fix karoge?"**
> Har `post.author` resolver alag DB query karta hai → 1 + N queries. **DataLoader** ek event-loop tick ke saare requests batch karke ek `WHERE id IN (...)` me badal deta hai, aur per-request cache rakhta hai. → [03](03_n_plus_one_dataloader.md)

**2. "REST pe GraphQL ka fayda kya, aur nuksan?"**

| Fayda | Nuksan |
|---|---|
| Client exactly wahi maangta hai jo chahiye (no over/under-fetching) | HTTP caching mushkil (sab POST `/graphql`) |
| Ek call me multiple resources | Rate limiting complex — query cost calculate karna padta hai |
| Strongly typed schema, self-documenting | N+1 easily aa jata hai |
| Frontend backend pe blocked nahi hota | Depth/complexity attacks ka risk |

**Senior line:** *"Public API pe REST rakhta hoon (cacheable, simple). GraphQL tab jab multiple clients ke alag-alag data needs hon — mobile aur web ek hi backend pe."*

**Related:** [02_API_Design](../02_API_Design/README.md) · [14_rest_graphql_grpc](../02_API_Design/14_rest_graphql_grpc.md) · [13_WebSocket_SSE](../13_WebSocket_SSE/README.md) · [FastAPI GraphQL](../../00_Year0-2_Junior/06_FastAPI/)
