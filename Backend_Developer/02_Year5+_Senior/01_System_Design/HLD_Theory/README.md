# 🏛️ HLD Theory — Mini-Index (67 topics)

> High-Level Design theory ki poori foundation — **interview ka sabse critical hissa**. Files number order (01→67) me build-up hain, par neeche **theme-wise** group kiye hain taaki topic dhoondhna aasan ho.
>
> **Study order:** pehli baar padho to **01→67 sequence me** jao (concepts stack karte hain). Revision me neeche wale groups se jump karo.
>
> Parent: [System Design](../) · Problems: [HLD_Problems](../HLD_Problems/) · Low-level: [LLD_Theory](../LLD_Theory/)

---

## 1. Foundations & Architecture Styles
| # | Topic |
|---|---|
| 01 | [Monolithic vs Microservices](01_Monolithic_vs_Microservices.md) |
| 02 | [REST / SOA / Microservices / Tier Architecture](02_REST_SOA_Microservices_Tier_Architecture.md) |
| 03 | [Web Server](03_Web_Server.md) |
| 55 | [Stateful vs Stateless Architecture](55_Stateful_vs_Stateless_Architecture.md) |
| 56 | [Serverless vs Traditional](56_Serverless_vs_Traditional.md) |

## 2. Scaling & Performance Metrics
| # | Topic |
|---|---|
| 04 | [Latency](04_Latency.md) |
| 05 | [Throughput](05_Throughput.md) |
| 06 | [Availability](06_Availability.md) |
| 10 | [Horizontal vs Vertical Scaling](10_Horizontal_vs_Vertical_Scaling.md) |
| 11 | [Redundancy vs Replication](11_Redundancy_vs_Replication.md) |
| 31 | [Back-of-Envelope Estimation](31_Back_of_Envelope_Estimation.md) |
| 57 | [Read-Heavy vs Write-Heavy](57_Read_Heavy_vs_Write_Heavy.md) |

## 3. Consistency, Time & Consensus
| # | Topic |
|---|---|
| 07 | [Consistency — Strong vs Eventual](07_Consistency_Strong_vs_Eventual.md) |
| 08 | [CAP Theorem](08_CAP_Theorem.md) |
| 09 | [Lamport Logical Clock](09_Lamport_Logical_Clock.md) |
| 29 | [ACID vs BASE](29_ACID_vs_BASE.md) |
| 44 | [Consistent Hashing — Theory](44_Consistent_Hashing_Theory.md) |
| 46 | [Vector Clocks & CRDTs](46_Vector_Clocks_CRDTs.md) |
| 62 | [Raft / Paxos Consensus](62_Raft_Paxos_Consensus.md) |
| 66 | [Dynamo-Style Consistency](66_Dynamo_Style_Consistency.md) |

## 4. Data & Storage
| # | Topic |
|---|---|
| 15 | [File-Based Storage](15_File_Based_Storage.md) |
| 16 | [RDBMS Horizontal Scaling](16_RDBMS_Horizontal_Scaling.md) |
| 17 | [NoSQL Types](17_NoSQL_Types.md) |
| 18 | [Polyglot Persistence](18_Polyglot_Persistence.md) |
| 19 | [Denormalization](19_Denormalization.md) |
| 20 | [Database Indexing](20_Database_Indexing.md) |
| 38 | [Database Sharding](38_Database_Sharding.md) |
| 58 | [Data Compression vs Deduplication](58_Data_Compression_vs_Deduplication.md) |
| 61 | [Read Replicas & WAL](61_Read_Replicas_WAL.md) |

## 5. Caching & CDN
| # | Topic |
|---|---|
| 13 | [Caching — Complete](13_Caching_Complete.md) |
| 14 | [Cache Eviction Techniques](14_Cache_Eviction_Techniques.md) |
| 32 | [CDN](32_CDN.md) |
| 42 | [Bloom Filters](42_Bloom_Filters.md) |
| 67 | [Probabilistic Data Structures — HLL, Count-Min, T-Digest](67_Probabilistic_Data_Structures.md) |

## 6. Load Balancing & Gateways
| # | Topic |
|---|---|
| 12 | [Load Balancer](12_Load_Balancer.md) |
| 28 | [Forward vs Reverse Proxy](28_Forward_vs_Reverse_Proxy.md) |
| 33 | [API Gateway](33_API_Gateway.md) |

## 7. Communication & Protocols
| # | Topic |
|---|---|
| 21 | [Synchronous vs Asynchronous](21_Synchronous_vs_Asynchronous.md) |
| 22 | [Message-Based Communication](22_Message_Based_Communication.md) |
| 23 | [Communication Protocols](23_Communication_Protocols.md) |
| 40 | [Webhooks Design](40_Webhooks_Design.md) |
| 48 | [HTTP Versions — Deep](48_HTTP_Versions_Deep.md) |
| 49 | [TCP / UDP — Deep](49_TCP_UDP_Deep.md) |
| 50 | [DNS — Deep](50_DNS_Deep.md) |
| 52 | [Serialization — Deep](52_Serialization_Deep.md) |
| 63 | [GraphQL vs REST vs gRPC](63_GraphQL_vs_REST_vs_gRPC.md) |

## 8. Async, Messaging & Distributed Coordination
| # | Topic |
|---|---|
| 34 | [Circuit Breaker & Event-Driven](34_Circuit_Breaker_Event_Driven.md) |
| 35 | [Service Discovery & Distributed Locking](35_Service_Discovery_Distributed_Locking.md) |
| 41 | [Data Pipelines & Streaming](41_Data_Pipelines_Streaming.md) |
| 51 | [Idempotency Tokens](51_Idempotency_Tokens.md) |
| 53 | [Big Data Distributed Processing](53_Big_Data_Distributed_Processing.md) |
| 59 | [Saga Pattern](59_Saga_Pattern.md) |
| 60 | [Two-Phase Commit](60_Two_Phase_Commit.md) |
| 65 | [Dead Letter Queue](65_Dead_Letter_Queue.md) |

## 9. Auth & Security
| # | Topic |
|---|---|
| 24 | [Authentication vs Authorization](24_Authentication_vs_Authorization.md) |
| 25 | [Basic Authentication](25_Basic_Authentication.md) |
| 26 | [Token-Based Authentication](26_Token_Based_Authentication.md) |
| 27 | [OAuth Authentication](27_OAuth_Authentication.md) |
| 36 | [RBAC Design](36_RBAC_Design.md) |

## 10. Reliability & Operations
| # | Topic |
|---|---|
| 30 | [SLA / SLO / SLI](30_SLA_SLO_SLI.md) |
| 37 | [Monitoring & Observability](37_Monitoring_Observability.md) |
| 39 | [Zero-Downtime Deployment](39_Zero_Downtime_Deployment.md) |
| 54 | [Heartbeat & Failure Detection](54_Heartbeat_Failure_Detection.md) |
| 64 | [Feature Flags & A/B Testing](64_Feature_Flags_AB_Testing.md) |

## 11. Specialized / Geospatial
| # | Topic |
|---|---|
| 43 | [Geohashing](43_Geohashing.md) |
| 45 | [Quad / KD Trees](45_Quad_KD_Trees.md) |
| 47 | [Multi-Tenancy Patterns](47_Multi_Tenancy_Patterns.md) |

---

*67 topics grouped into 11 themes. Har file standalone padhi ja sakti hai; interview se pehle groups 2, 3, 4, 5, 8 pe extra time do — yeh sabse zyada poochhe jaate hain.*
