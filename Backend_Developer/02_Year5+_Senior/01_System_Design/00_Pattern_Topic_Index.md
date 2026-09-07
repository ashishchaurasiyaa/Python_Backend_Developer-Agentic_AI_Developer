# 🧩 System Design — Pattern/Concept → Problems Index

> DSA me jaise `01_DSA/00_Coding_Patterns_Index.md` **pattern → questions** map karta hai
> ("yeh sliding window hai" pehchan lo, solution flow apne aap aa jaata hai) — System Design me
> wahi lens **do jagah** chahiye: **LLD me design pattern pehchano**, **HLD me concept/technique pehchano**.
>
> **Yeh reverse-index hai** — `LLD_Problems/*.md` aur `HLD_Problems/*.md` ko **grep karke** banaya
> (guess nahi), taaki pata chale kaunsa pattern/concept kis real problem me **actually** use hota hai.
> Kuch problems me pattern named nahi hai par implicit hai — wo alag se **"Implicit"** tag ke saath hai.
>
> **Use kaise karo:** pattern/concept ka theory note padho ("Kab" + "Trick" ratto) → neeche diye
> problems me se ek attempt karo → check karo ki tune wahi pattern pehchana ya nahi.

**Legend:** 🔴 = high interview frequency

---

## ⚡ Quick Map

| Layer | Theory | Problems | Reverse-index (this file) |
|---|---|---|---|
| LLD (class design) | [`LLD_Theory/`](LLD_Theory/) — 21 GoF patterns + OOP/SOLID | [`LLD_Problems/`](LLD_Problems/) — 20 machine-coding problems | Part A below |
| HLD (system design) | [`HLD_Theory/`](HLD_Theory/) — 67 topics, 11 themes | [`HLD_Problems/`](HLD_Problems/) — 37 designs | Part B below |

---

# PART A — LLD: Design Pattern → Problems

## Creational

### 1. Singleton → [`LLD_Theory/01_Singleton_Pattern.md`](LLD_Theory/01_Singleton_Pattern.md)
**Kab:** exactly-one-instance chahiye — connection pool, config, a shared counter/registry.
**Trick:** private constructor + static `get_instance()`; thread-safety ke liye double-checked locking ya module-level (Python me trivial hai).

| Problem | Kahan use hua |
|---|---|
| [LRU_Cache](LLD_Problems/LRU_Cache.md) 🔴 | cache instance |
| [Parking_Lot_System](LLD_Problems/Parking_Lot_System.md) 🔴 | `ParkingLot` ek hi instance |
| [Payment_System](LLD_Problems/Payment_System.md) 🔴 | payment gateway registry |
| [Vending_Machine](LLD_Problems/Vending_Machine.md) | machine instance |

### 2. Factory / Abstract Factory → [`02_Factory_Pattern.md`](LLD_Theory/02_Factory_Pattern.md) · [`03_Abstract_Factory_Pattern.md`](LLD_Theory/03_Abstract_Factory_Pattern.md)
**Kab:** object banane ka logic caller se chhupana hai — "kaunsa concrete class banega" runtime pe decide hota hai.
**Trick:** ek `create_x()` method jo type/enum dekh ke sahi subclass return kare.

| Problem | Kahan use hua |
|---|---|
| [Booking_System](LLD_Problems/Booking_System.md) | booking-type factory |
| [Notification_System](LLD_Problems/Notification_System.md) | channel factory (SMS/email/push families) — Abstract Factory |

### 3. Builder → [`04_Builder_Pattern.md`](LLD_Theory/04_Builder_Pattern.md)
**Kab:** multi-step construction, optional fields bahut saare (complex request/query object).
**Trick:** fluent `.with_x()` chain, end me `.build()`.
> LLD_Problems me directly named nahi mila — practice `Design_Patterns_Code/06_builder/` me (query builder ke liye).

## Structural

### 4. Facade → [`13_Facade_Pattern.md`](LLD_Theory/13_Facade_Pattern.md)
**Kab:** complex subsystem (scheduling + dispatch + door-control) ko ek simple interface se chhupana.
**Trick:** ek class jo andar 3-4 subsystems ko coordinate karke ek clean method expose kare.

| Problem | Kahan use hua |
|---|---|
| [Elevator_System](LLD_Problems/Elevator_System.md) 🔴 | scheduler facade over dispatch + door + motor logic |

### 5. Composite → [`Command_Composite_Proxy_Flyweight_Patterns.md`](LLD_Theory/Command_Composite_Proxy_Flyweight_Patterns.md)
**Kab:** tree structure — "part-whole" — file/folder, org chart, UI components.
**Trick:** leaf aur container dono same interface implement karein, so caller ko farak na pade.

| Problem | Kahan use hua |
|---|---|
| [File_Storage_System](LLD_Problems/File_Storage_System.md) 🔴 | file/folder tree — same `Node` interface |

## Behavioural

### 6. Strategy → [`07_Strategy_Pattern.md`](LLD_Theory/07_Strategy_Pattern.md) 🔴 (sabse zyada reused)
**Kab:** ek hi kaam ke multiple algorithms interchangeable chahiye — pricing, matching, auth.
**Trick:** interface + concrete strategies + context class jo runtime pe strategy inject leta hai.

| Problem | Kahan use hua |
|---|---|
| [Parking_Lot_System](LLD_Problems/Parking_Lot_System.md) 🔴 | pricing strategy (hourly/flat/vehicle-type) |
| [Booking_System](LLD_Problems/Booking_System.md) | slot-allocation strategy |
| [Library_Management_System](LLD_Problems/Library_Management_System.md) | fine-calculation strategy |
| [Online_Shopping_Cart](LLD_Problems/Online_Shopping_Cart.md) | discount/pricing rule strategy |
| [Payment_System](LLD_Problems/Payment_System.md) 🔴 | payment-method strategy (UPI/card/wallet) |
| [Ride_Booking_System](LLD_Problems/Ride_Booking_System.md) | driver-matching / pricing strategy |
| [Splitwise](LLD_Problems/Splitwise.md) 🔴 | split strategy (equal/percentage/exact) |
| [Tic_Tac_Toe_Chess](LLD_Problems/Tic_Tac_Toe_Chess.md) | move-validation strategy per piece |
| [Elevator_System](LLD_Problems/Elevator_System.md) | scheduling strategy (SCAN/nearest-first) |
| *Implicit:* [Login_System](LLD_Problems/Login_System.md) | auth strategy (password/OTP/OAuth) |
| *Implicit:* [Rate_Limiter](LLD_Problems/Rate_Limiter.md) 🔴 | algorithm strategy (token bucket/sliding window/leaky bucket) |

### 7. Observer → [`08_Observer_Pattern.md`](LLD_Theory/08_Observer_Pattern.md) 🔴
**Kab:** ek event, multiple listeners react karte hain — webhooks, notifications, signals.
**Trick:** subject `attach()/notify()` observers ko; observer `update()` implement kare.

| Problem | Kahan use hua |
|---|---|
| [Notification_System](LLD_Problems/Notification_System.md) 🔴 | event → multi-channel fan-out |
| [Parking_Lot_System](LLD_Problems/Parking_Lot_System.md) | slot-availability listeners |
| [Booking_System](LLD_Problems/Booking_System.md) | booking-confirmed listeners |
| *Implicit:* [Splitwise](LLD_Problems/Splitwise.md) | balance-changed → notify group members |

### 8. State → [`18_State_Pattern.md`](LLD_Theory/18_State_Pattern.md) 🔴
**Kab:** object ka behaviour uske current "state" pe depend karta hai — state transitions clean chahiye.
**Trick:** har state apni class; transition = `self.state = NextState()`.

| Problem | Kahan use hua |
|---|---|
| [ATM_System](LLD_Problems/ATM_System.md) 🔴 | idle → card-inserted → pin → dispensing |
| [Vending_Machine](LLD_Problems/Vending_Machine.md) 🔴 | idle → selected → dispensing → out-of-stock |
| [Parking_Lot_System](LLD_Problems/Parking_Lot_System.md) | slot free/occupied/reserved |
| *Implicit:* [Payment_System](LLD_Problems/Payment_System.md) 🔴 | pending → authorized → captured → refunded/failed |
| *Implicit:* [Ride_Booking_System](LLD_Problems/Ride_Booking_System.md) | requested → matched → ongoing → completed |
| *Implicit:* [Stock_Trading_System](LLD_Problems/Stock_Trading_System.md) | order open → partially-filled → filled/cancelled |
| *Implicit:* [Elevator_System](LLD_Problems/Elevator_System.md) | idle → moving → door-open |

### 9. Template Method → [`09_Template_Method_Pattern.md`](LLD_Theory/09_Template_Method_Pattern.md)
**Kab:** ek algorithm ka skeleton fixed hai, kuch steps subclass override karein.
**Trick:** base class ka `process()` final steps call kare; ek-do `abstract` hooks subclass fill kare.

| Problem | Kahan use hua |
|---|---|
| [Payment_System](LLD_Problems/Payment_System.md) 🔴 | validate → charge → notify skeleton, gateway-specific step overridden |
| [Notification_System](LLD_Problems/Notification_System.md) | build → format → send skeleton per channel |
| [Booking_System](LLD_Problems/Booking_System.md) | validate → reserve → confirm skeleton |
| [Parking_Lot_System](LLD_Problems/Parking_Lot_System.md) | entry → assign → exit skeleton |

### 10. Chain of Responsibility → [`17_Chain_of_Responsibility_Pattern.md`](LLD_Theory/17_Chain_of_Responsibility_Pattern.md)
**Kab:** request ko handlers ki chain se guzarna hai, jo handle kar sake wo kare, warna aage pass ho.
**Trick:** har handler `set_next()` + "can I handle? no → self.next.handle()".

| Problem | Kahan use hua |
|---|---|
| [Notification_System](LLD_Problems/Notification_System.md) | fallback chain — SMS fail → email try |

### 11. Command → [`Command_Composite_Proxy_Flyweight_Patterns.md`](LLD_Theory/Command_Composite_Proxy_Flyweight_Patterns.md)
**Kab:** action ko object bana ke queue/undo/log karna hai.
**Trick:** `Command.execute()` + optional `undo()`; invoker command ko decouple rakhta hai receiver se.

| Problem | Kahan use hua |
|---|---|
| [Tic_Tac_Toe_Chess](LLD_Problems/Tic_Tac_Toe_Chess.md) | move-as-command → undo/redo, move history |
| *Implicit:* [Task_Queue_Job_Scheduler](LLD_Problems/Task_Queue_Job_Scheduler.md) 🔴 | job = command object queued for a worker |

## Patterns without a direct LLD_Problems demo (practice via Design_Patterns_Code/)

| Pattern | Theory | Practice |
|---|---|---|
| Decorator | [05](LLD_Theory/05_Decorator_Pattern.md) | middleware/retry-wrapper — `Design_Patterns_Code/04_observer`-adjacent, or Rate_Limiter ko decorator se wrap karke dekho |
| Adapter | [06](LLD_Theory/06_Adapter_Pattern.md) | third-party SDK wrap — koi bhi payment/notification provider integration me try karo |
| Prototype | [12](LLD_Theory/12_Prototype_Pattern.md) | `Design_Patterns_Code/15_prototype/` |
| Iterator | [14](LLD_Theory/14_Iterator_Pattern.md) | `Design_Patterns_Code/17_iterator/` — pagination cursor |
| Mediator | [15](LLD_Theory/15_Mediator_Pattern.md) | `Design_Patterns_Code/18_mediator/` — chat-room orchestration |
| Visitor | [16](LLD_Theory/16_Visitor_Pattern.md) | `Design_Patterns_Code/19_visitor/` |
| Memento | [19](LLD_Theory/19_Memento_Pattern.md) | undo/snapshot — try adding to Splitwise (undo last expense) |
| Bridge | [20](LLD_Theory/20_Bridge_Pattern.md) | abstraction/impl split — try Notification_System (channel abstraction vs provider impl) |
| Interpreter | [21](LLD_Theory/21_Interpreter_Pattern.md) | rule/DSL eval — try Rate_Limiter (rule expression) or Splitwise (split-rule DSL) |
| Proxy / Flyweight | [Command_Composite_Proxy_Flyweight](LLD_Theory/Command_Composite_Proxy_Flyweight_Patterns.md) | Flyweight → Tic_Tac_Toe_Chess piece objects reused; Proxy → add an access-control proxy in front of Login_System |

---

# PART B — HLD: Concept Cluster → Problems

> HLD_Theory ke 67 topics [already theme-wise grouped hain](HLD_Theory/README.md). Yahan **reverse
> direction** hai: ek concept lo, dekho kaunse 37 designs me wo **actually** aata hai — taaki
> "iss concept ka interview me sawaal aaya to main kaunsa example bol sakta hoon" turant pata ho.

### 1. Caching, Eviction & CDN → [`13`](HLD_Theory/13_Caching_Complete.md)·[`14`](HLD_Theory/14_Cache_Eviction_Techniques.md)·[`32`](HLD_Theory/32_CDN.md)·[`42`](HLD_Theory/42_Bloom_Filters.md)
**Kab:** read-heavy system, static/media content, "duplicate check without huge memory".
**Trick:** cache-aside for hot keys, CDN for static assets, Bloom filter for "definitely-not-present" checks.

| Concept | Problems |
|---|---|
| LRU/eviction | [Distributed_Cache](HLD_Problems/Design_Distributed_Cache.md) 🔴, [Gaming_Leaderboard](HLD_Problems/Design_Gaming_Leaderboard.md), [Twitter_X](HLD_Problems/Design_Twitter_X.md), [Airbnb](HLD_Problems/Design_Airbnb.md), [URL_Shortener](HLD_Problems/URL_Shortener.md) |
| CDN | [Netflix](HLD_Problems/Design_Netflix.md), [YouTube](HLD_Problems/Design_YouTube.md), [Instagram_NewsFeed](HLD_Problems/Design_Instagram_NewsFeed.md), [Spotify](HLD_Problems/Design_Spotify.md), [Reddit](HLD_Problems/Design_Reddit.md), [Pastebin](HLD_Problems/Design_Pastebin.md), [AdServer](HLD_Problems/Design_AdServer.md) — most media/feed designs |
| Bloom filter | [Search_Engine](HLD_Problems/Design_Search_Engine.md) 🔴, [Web_Crawler](HLD_Problems/Design_Web_Crawler.md) 🔴 (seen-URL dedup), [Airbnb](HLD_Problems/Design_Airbnb.md) |

### 2. Consistent Hashing & Sharding → [`38`](HLD_Theory/38_Database_Sharding.md)·[`44`](HLD_Theory/44_Consistent_Hashing_Theory.md)
**Kab:** data ek node pe fit nahi hoti, ya nodes add/remove hote rehte hain bina full re-shuffle ke.
**Trick:** consistent hashing = ring + virtual nodes (rebalance touches minimal keys); sharding = partition key choose karo jo hotspot na banaye.

| Concept | Problems |
|---|---|
| Consistent hashing | [Distributed_Cache](HLD_Problems/Design_Distributed_Cache.md) 🔴, [Uber_Maps](HLD_Problems/Design_Uber_Maps.md) 🔴, [Google_Docs](HLD_Problems/Design_Google_Docs.md), [Web_Crawler](HLD_Problems/Design_Web_Crawler.md) |
| Sharding | [Twitter_X](HLD_Problems/Design_Twitter_X.md) 🔴, [WhatsApp_Chat](HLD_Problems/Design_WhatsApp_Chat.md), [Uber_Maps](HLD_Problems/Design_Uber_Maps.md), [Payment_Gateway](HLD_Problems/Design_Payment_Gateway.md) 🔴, [Reddit](HLD_Problems/Design_Reddit.md), [Quora](HLD_Problems/Design_Quora.md), [RAG_System](HLD_Problems/Design_RAG_System.md), [Stock_Exchange](HLD_Problems/Design_Stock_Exchange.md), [Gaming_Leaderboard](HLD_Problems/Design_Gaming_Leaderboard.md), [Airbnb](HLD_Problems/Design_Airbnb.md), [Distributed_Logging](HLD_Problems/Design_Distributed_Logging.md) |

### 3. Consistency, CAP & Consensus → [`07`](HLD_Theory/07_Consistency_Strong_vs_Eventual.md)·[`08`](HLD_Theory/08_CAP_Theorem.md)·[`46`](HLD_Theory/46_Vector_Clocks_CRDTs.md)·[`62`](HLD_Theory/62_Raft_Paxos_Consensus.md)·[`66`](HLD_Theory/66_Dynamo_Style_Consistency.md)
**Kab:** "kya har read latest write dikhaye, ya thoda stale chalega?" — trade-off explicitly bolna hai.
**Trick:** money/booking = strong consistency; social feed/counts = eventual; concurrent edits = CRDT/vector clock; leader-based coordination = Raft/Paxos.

| Concept | Problems |
|---|---|
| Strong consistency | [BookMyShow](HLD_Problems/Design_BookMyShow.md) 🔴 (seat lock), [WhatsApp_Chat](HLD_Problems/Design_WhatsApp_Chat.md), [Airbnb](HLD_Problems/Design_Airbnb.md), [eBay_Auction](HLD_Problems/Design_eBay_Auction.md) 🔴 |
| Eventual consistency | [Twitter_X](HLD_Problems/Design_Twitter_X.md), [URL_Shortener](HLD_Problems/URL_Shortener.md), [AdServer](HLD_Problems/Design_AdServer.md), [Airbnb](HLD_Problems/Design_Airbnb.md), [eBay_Auction](HLD_Problems/Design_eBay_Auction.md) |
| Vector clock / CRDT | [Google_Docs](HLD_Problems/Design_Google_Docs.md) 🔴, [Slack](HLD_Problems/Design_Slack.md), [Online_Code_Editor](HLD_Problems/Design_Online_Code_Editor.md), [Spotify](HLD_Problems/Design_Spotify.md) |
| Consensus (Raft/Paxos) | [Distributed_Message_Queue](HLD_Problems/Design_Distributed_Message_Queue.md) 🔴 (leader election, ISR), [Agent_Orchestration](HLD_Problems/Design_Agent_Orchestration.md) |

### 4. Messaging, Streaming & Reliability Patterns → [`22`](HLD_Theory/22_Message_Based_Communication.md)·[`34`](HLD_Theory/34_Circuit_Breaker_Event_Driven.md)·[`59`](HLD_Theory/59_Saga_Pattern.md)·[`60`](HLD_Theory/60_Two_Phase_Commit.md)·[`65`](HLD_Theory/65_Dead_Letter_Queue.md)
**Kab:** service-to-service call fail ho sakta hai, ya multi-step transaction cross services span kare.
**Trick:** circuit breaker = fail-fast on downstream trouble; saga = local transactions + compensating actions; 2PC = strong but blocking; DLQ = poison-message parking.

| Concept | Problems |
|---|---|
| Kafka / message queue (almost universal) | 30+ of the 37 designs — see individual files; canonical: [Distributed_Message_Queue](HLD_Problems/Design_Distributed_Message_Queue.md) 🔴 (Kafka-from-scratch) |
| Circuit breaker | [API_Gateway](HLD_Problems/Design_API_Gateway.md) 🔴, [Payment_Gateway](HLD_Problems/Design_Payment_Gateway.md) 🔴, [Stock_Exchange](HLD_Problems/Design_Stock_Exchange.md) |
| Saga pattern | [Amazon_Ecommerce](HLD_Problems/Design_Amazon_Ecommerce.md) 🔴 (order→payment→inventory), [Agent_Orchestration](HLD_Problems/Design_Agent_Orchestration.md) |
| Two-phase commit | [Payment_Gateway](HLD_Problems/Design_Payment_Gateway.md) 🔴 |
| Dead letter queue | [Distributed_Message_Queue](HLD_Problems/Design_Distributed_Message_Queue.md) |
| Fan-out (push vs pull) | [Twitter_X](HLD_Problems/Design_Twitter_X.md) 🔴, [Instagram_NewsFeed](HLD_Problems/Design_Instagram_NewsFeed.md) 🔴, [WhatsApp_Chat](HLD_Problems/Design_WhatsApp_Chat.md), [Slack](HLD_Problems/Design_Slack.md), [Reddit](HLD_Problems/Design_Reddit.md), [Quora](HLD_Problems/Design_Quora.md), [Payment_Gateway](HLD_Problems/Design_Payment_Gateway.md), [eBay_Auction](HLD_Problems/Design_eBay_Auction.md) |

### 5. Rate Limiting, Idempotency & API Gateway → [`04`](HLD_Theory/04_Latency.md)·[`33`](HLD_Theory/33_API_Gateway.md)·[`51`](HLD_Theory/51_Idempotency_Tokens.md)
**Kab:** public API, retries possible, payment/money endpoints, abuse-prone endpoints.
**Trick:** idempotency key on the client → server dedups retried requests; rate limit = token/leaky bucket or sliding window, enforced at the gateway.

| Concept | Problems |
|---|---|
| Rate limiting | [API_Gateway](HLD_Problems/Design_API_Gateway.md) 🔴, [Amazon_Ecommerce](HLD_Problems/Design_Amazon_Ecommerce.md), [BookMyShow](HLD_Problems/Design_BookMyShow.md), [Twitter_X](HLD_Problems/Design_Twitter_X.md), [Uber_Maps](HLD_Problems/Design_Uber_Maps.md), [Quora](HLD_Problems/Design_Quora.md), [Reddit](HLD_Problems/Design_Reddit.md), [Web_Crawler](HLD_Problems/Design_Web_Crawler.md), [Multi_Tenant_SaaS](HLD_Problems/Design_Multi_Tenant_SaaS.md), [Real_Time_Analytics](HLD_Problems/Design_Real_Time_Analytics.md), [RAG_System](HLD_Problems/Design_RAG_System.md), [ChatGPT_Backend](HLD_Problems/Design_ChatGPT_Backend.md), [Pastebin](HLD_Problems/Design_Pastebin.md), [eBay_Auction](HLD_Problems/Design_eBay_Auction.md), [Search_Engine](HLD_Problems/Design_Search_Engine.md), [URL_Shortener](HLD_Problems/URL_Shortener.md) |
| Idempotency | [Payment_Gateway](HLD_Problems/Design_Payment_Gateway.md) 🔴, [API_Gateway](HLD_Problems/Design_API_Gateway.md), [Amazon_Ecommerce](HLD_Problems/Design_Amazon_Ecommerce.md), [BookMyShow](HLD_Problems/Design_BookMyShow.md), [Uber_Maps](HLD_Problems/Design_Uber_Maps.md), [Dropbox](HLD_Problems/Design_Dropbox.md), [Twitter_X](HLD_Problems/Design_Twitter_X.md), [Reddit](HLD_Problems/Design_Reddit.md), [Quora](HLD_Problems/Design_Quora.md), [Real_Time_Analytics](HLD_Problems/Design_Real_Time_Analytics.md), [eBay_Auction](HLD_Problems/Design_eBay_Auction.md) |

### 6. Real-Time & WebSockets → [`21`](HLD_Theory/21_Synchronous_vs_Asynchronous.md)·[`23`](HLD_Theory/23_Communication_Protocols.md)
**Kab:** bidirectional push chahiye — chat, live updates, presence, live-bidding.
**Trick:** WebSocket/long-poll + a connection-registry service to route messages to the right server holding that socket.

| Problems |
|---|
| [WhatsApp_Chat](HLD_Problems/Design_WhatsApp_Chat.md) 🔴, [Slack](HLD_Problems/Design_Slack.md) 🔴, [Stock_Exchange](HLD_Problems/Design_Stock_Exchange.md) 🔴, [BookMyShow](HLD_Problems/Design_BookMyShow.md), [eBay_Auction](HLD_Problems/Design_eBay_Auction.md), [Uber_Maps](HLD_Problems/Design_Uber_Maps.md), [Tinder](HLD_Problems/Design_Tinder.md), [Google_Docs](HLD_Problems/Design_Google_Docs.md), [Online_Code_Editor](HLD_Problems/Design_Online_Code_Editor.md), [ChatGPT_Backend](HLD_Problems/Design_ChatGPT_Backend.md) (token streaming), [Twitter_X](HLD_Problems/Design_Twitter_X.md), [Reddit](HLD_Problems/Design_Reddit.md), [Quora](HLD_Problems/Design_Quora.md), [Instagram_NewsFeed](HLD_Problems/Design_Instagram_NewsFeed.md), [Airbnb](HLD_Problems/Design_Airbnb.md), [Dropbox](HLD_Problems/Design_Dropbox.md), [Spotify](HLD_Problems/Design_Spotify.md) |

### 7. Geospatial → [`43`](HLD_Theory/43_Geohashing.md)·[`45`](HLD_Theory/45_Quad_KD_Trees.md)
**Kab:** "nearby X find karo" — driver matching, maps, dating.
**Trick:** geohash = string-prefix proximity (easy to shard by prefix); quad/KD-tree = exact spatial range query.

| Problems |
|---|
| [Uber_Maps](HLD_Problems/Design_Uber_Maps.md) 🔴 (geohash), [Google_Maps](HLD_Problems/Design_Google_Maps.md) 🔴 (tiles/routing), [Tinder](HLD_Problems/Design_Tinder.md) (geo-swipe), [Airbnb](HLD_Problems/Design_Airbnb.md) (geo search), [Search_Engine](HLD_Problems/Design_Search_Engine.md) (spatial index variant) |

### 8. Search, Ranking & Vector Retrieval
**Kab:** free-text search, feed ranking, "find similar" (embeddings).
**Trick:** inverted index for keyword search; vector DB + ANN for semantic/embedding search; ranking = feature score + recency decay.

| Problems |
|---|
| [Search_Engine](HLD_Problems/Design_Search_Engine.md) 🔴 (inverted index), [Search_Autocomplete](HLD_Problems/Design_Search_Autocomplete.md) 🔴 (trie), [AdServer](HLD_Problems/Design_AdServer.md) (inverted index for targeting), [RAG_System](HLD_Problems/Design_RAG_System.md) 🔴 (vector search), [Quora](HLD_Problems/Design_Quora.md) (vector search for recs) |

### 9. Auth, Security & Multi-Tenancy → [`24`](HLD_Theory/24_Authentication_vs_Authorization.md)–[`27`](HLD_Theory/27_OAuth_Authentication.md)·[`36`](HLD_Theory/36_RBAC_Design.md)·[`47`](HLD_Theory/47_Multi_Tenancy_Patterns.md)
| Concept | Problems |
|---|---|
| OAuth | [API_Gateway](HLD_Problems/Design_API_Gateway.md), [Online_Code_Editor](HLD_Problems/Design_Online_Code_Editor.md) |
| RBAC | [Agent_Orchestration](HLD_Problems/Design_Agent_Orchestration.md) (tool-permission scoping) |
| Multi-tenancy | [Multi_Tenant_SaaS](HLD_Problems/Design_Multi_Tenant_SaaS.md) 🔴 — the dedicated deep-dive |

### 10. Estimation & Reliability (SLA/SLO, back-of-envelope) → [`30`](HLD_Theory/30_SLA_SLO_SLI.md)·[`31`](HLD_Theory/31_Back_of_Envelope_Estimation.md)
**Kab:** every single design starts here — QPS/storage/bandwidth math + explicit SLA numbers.
**Trick:** this isn't one problem's signature, it's the opening move of **all 37**. Drill it separately via [`PRACTICE_DRILLS.md`](PRACTICE_DRILLS.md) and [`SYSTEM_DESIGN_CHECKLIST.md`](SYSTEM_DESIGN_CHECKLIST.md) rather than hunting one example.

---

## 🎯 Suggested revision order

1. **LLD Week 1:** Strategy + Observer + State (patterns 6-8) — cover ~12 of the 20 problems between them.
2. **LLD Week 2:** Singleton/Factory/Template Method/Facade/Composite/Chain/Command — the rest.
3. **HLD Week 1:** Clusters 1-2 (caching, sharding, consistent hashing) — asked in almost every design.
4. **HLD Week 2:** Clusters 3-4 (consistency/CAP, messaging/reliability) — the senior-signal differentiators.
5. **HLD Week 3:** Clusters 5-9 (rate limit/idempotency, real-time, geospatial, search, auth) — role-specific depth.

> Same rule as DSA: pattern/concept ka **name bolna** interviewer ko convince karta hai tu isko
> pehchan raha hai, na ki bas ratt ke aaya hai. Jis problem me "Implicit" likha hai, wahi asli test hai —
> khud identify karo pattern bina kisi ne bataye.
