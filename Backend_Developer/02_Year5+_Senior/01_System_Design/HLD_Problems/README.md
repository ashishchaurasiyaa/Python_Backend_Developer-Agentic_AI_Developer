# 🏗️ HLD Problems — Mini-Index (37 designs)

> System Design ke **practice problems** — har file ek complete "design X" walkthrough. Theory se alag: yahan tu **bolke design karna** practice karta hai (requirements → estimation → API → data model → scaling → bottlenecks).
>
> **Kaise use karo:** file kholne se pehle **khud whiteboard pe design karne ki koshish karo**, fir note se compare. Neeche category-wise + interview-frequency order me group kiye hain.
>
> Foundations pehle: [HLD_Theory](../HLD_Theory/) · Parent: [System Design](../)

---

## 1. Classic Warm-Ups (start here — highest frequency) 🔴
| Design | |
|---|---|
| [URL Shortener](URL_Shortener.md) | TinyURL — hashing, redirects, scale |
| [Pastebin](Design_Pastebin.md) | text storage, expiry, read-heavy |
| [Search Autocomplete](Design_Search_Autocomplete.md) | typeahead, tries, ranking |
| [Web Crawler](Design_Web_Crawler.md) | BFS at scale, dedup, politeness |
| [Payment Gateway](Design_Payment_Gateway.md) 🔴 | UPI-scale — idempotency, double-entry ledger, T+1 reconciliation, PSP routing. India fintech loops (Razorpay/PhonePe/Juspay) isko poochte hain. |

## 2. Infrastructure & Platform 🔴
| Design | |
|---|---|
| [API Gateway](Design_API_Gateway.md) | routing, auth, rate limit |
| [Distributed Cache](Design_Distributed_Cache.md) | consistent hashing, eviction |
| [Distributed Logging](Design_Distributed_Logging.md) | ingestion, aggregation, search |
| [Multi-Tenant SaaS](Design_Multi_Tenant_SaaS.md) | isolation, noisy-neighbour |
| [Distributed Message Queue](Design_Distributed_Message_Queue.md) | Kafka-from-scratch: segments, ISR, offsets |

## 3. Social & Feed 🔴
| Design | |
|---|---|
| [Twitter / X](Design_Twitter_X.md) | fan-out, timeline, celebrity problem |
| [Instagram News Feed](Design_Instagram_NewsFeed.md) | feed ranking, push vs pull |
| [Reddit](Design_Reddit.md) | voting, comments tree, ranking |
| [Quora](Design_Quora.md) | Q&A, feed, recommendation |

## 4. Messaging & Collaboration
| Design | |
|---|---|
| [WhatsApp Chat](Design_WhatsApp_Chat.md) | delivery, presence, E2E |
| [Slack](Design_Slack.md) | channels, realtime, search |
| [Google Docs](Design_Google_Docs.md) | OT / CRDT, concurrent edit |
| [Online Code Editor](Design_Online_Code_Editor.md) | sandboxing, collab, execution |

## 5. Media & Streaming
| Design | |
|---|---|
| [YouTube](Design_YouTube.md) | upload, transcode, CDN, views |
| [Netflix](Design_Netflix.md) | streaming, ABR, recommendation |
| [Spotify](Design_Spotify.md) | audio delivery, playlists |

## 6. Location & Marketplace
| Design | |
|---|---|
| [Uber / Maps](Design_Uber_Maps.md) | matching, geospatial, ETA |
| [Google Maps](Design_Google_Maps.md) | routing, tiles, geohash |
| [Tinder](Design_Tinder.md) | matching, geo, swipe scale |
| [Airbnb](Design_Airbnb.md) | search, availability, booking |

## 7. Commerce & Trading
| Design | |
|---|---|
| [Amazon E-commerce](Design_Amazon_Ecommerce.md) | catalog, cart, inventory |
| [eBay Auction](Design_eBay_Auction.md) | bidding, concurrency, closing |
| [BookMyShow](Design_BookMyShow.md) | seat locking, concurrency |
| [Stock Exchange](Design_Stock_Exchange.md) | matching engine, low latency |

## 8. Search, Storage & Analytics
| Design | |
|---|---|
| [Dropbox](Design_Dropbox.md) | file sync, chunking, dedup |
| [Search Engine](Design_Search_Engine.md) | inverted index, ranking |
| [Real-Time Analytics](Design_Real_Time_Analytics.md) | streaming, aggregation |
| [Ad Server](Design_AdServer.md) | targeting, budget, low latency |
| [Gaming Leaderboard](Design_Gaming_Leaderboard.md) | Redis ZSET, rank, score-range sharding |

## 9. AI / LLM (modern — high interview value now) 🔴
| Design | |
|---|---|
| [ChatGPT Backend](Design_ChatGPT_Backend.md) | inference serving, streaming, context |
| [RAG System](Design_RAG_System.md) | retrieval, vector DB, grounding |
| [Agent Orchestration](Design_Agent_Orchestration.md) | tool calling, planning, state |

---

*37 designs grouped into 9 categories. Interview prep order: Group 1 (warm-ups) → 3 (social/feed) → 2 (infra) → 9 (AI, agar AI role ho). Group 4's Google Docs (OT/CRDT) aur Group 7's BookMyShow/Stock Exchange (concurrency) sabse zyada distinguishing hote hain senior interviews me.*
