# Lecture 3: Offline-First & Data Synchronization

> *"Treat the network as optional, not a given."*

**Section 8 — UI Architecture Patterns for Apps**

---

## 🎯 Is Lecture Mein Kya Seekhenge?

- **Why offline-first** matters in modern apps
- **Core principles** — local-first interaction, decoupled sync
- **Local caching** — SQLite, IndexedDB, Realm
- **Sync queues** for outbound changes
- **Background sync strategies** (periodic, trigger-based, opportunistic)
- **Conflict scenarios** — concurrent edits, partitions, stale overwrites
- **Conflict resolution** — last-write-wins, merge, manual, CRDTs/OT
- **Sync directionality** — one-way, two-way, full vs incremental
- **Resilience & retry** — idempotency, backoff
- **Real-world case study** — offline chat app

---

## 1. Why Offline-First Matters

```
✓ Users expect reliability
   - Plane mode? Still works
   - Rural area? Still works
   - Bad signal? Still works

✓ Improves usability
   - Mobile & remote environments
   - Intermittent connectivity

✓ Builds trust
   - App that breaks offline → loses user trust

✗ But brings challenges
   - Data consistency
   - Reliable sync
   - Conflict handling
```

### Where Offline-First is Critical

```
✓ Travel + logistics apps
✓ Field service tools
✓ Chat systems
✓ CRMs
✓ Note-taking, drawing, productivity
✓ Anything used outside reliable wifi
```

---

## 2. Core Principles of Offline-First

### 1. Local-First Interaction Model

```
User action
    │
    ▼
┌──────────────┐
│  Local DB    │  ← Reads/writes happen HERE first
└──────┬───────┘
       │
       ▼
   UI re-renders
   (instant, no network wait)
```

### 2. Decoupled Asynchronous Sync

```
After local write:
   Change → Sync Queue → Background worker
                         (eventually pushes to server)

Sync NEVER blocks the UI.
```

### 3. Local Cache as Authoritative Source

```
While offline:
   Local cache = source of truth
   Sync = catch-up mechanism
```

### 4. Resilience to Failures

```
✓ Retry on network drop
✓ Backoff to avoid hammering
✓ No data loss on failure
✓ No user intervention required
```

---

## 3. Local Caching

### Tools by Platform

```
┌────────────┬──────────────────────────────────┐
│ Platform   │ Common Local Storage             │
├────────────┼──────────────────────────────────┤
│ Web        │ IndexedDB, LocalStorage          │
│ iOS        │ Core Data, Realm, SQLite         │
│ Android    │ Room (SQLite), Realm             │
│ Desktop    │ SQLite, file-based stores        │
│ Cross-platf│ WatermelonDB, RxDB, PouchDB      │
└────────────┴──────────────────────────────────┘
```

### Why Local Cache Works

```
✓ No network round-trip
✓ Instant reads + writes
✓ Snappy UX even on weak networks
✓ Powers offline scenarios entirely
```

### Versioning Strategy

```
Each record carries:
   ✓ version number (for OCC), OR
   ✓ updated_at timestamp, OR
   ✓ vector clock / Lamport clock (advanced)

Helps:
   - Detect conflicts
   - Order updates
   - Pick latest write
```

### Cache Invalidation

```
✓ TTL (time-to-live)
✓ Background refresh
✓ Push-based invalidation (server notifies client)
✓ Event-based invalidation
```

---

## 4. Synchronization Queues

### The Concept

```
User action (offline or online)
        │
        ▼
   Local write to cache
        │
        ▼
   Append change to SYNC QUEUE
        │
        ▼ (when online)
   Background worker drains queue
        │
        ▼
   POST/PUT/DELETE to server
        │
        ▼
   Mark item as synced, remove from queue
```

### Queue Item Structure

```python
{
    "id": "uuid",
    "operation": "create" | "update" | "delete",
    "entity": "todo",
    "payload": {...},
    "created_at": "...",
    "retries": 0,
    "last_error": null,
}
```

### Ordering Matters

```
✓ Process in order when operations depend on each other
   e.g., CREATE parent → then UPDATE child
✗ Out-of-order processing breaks invariants
```

### Retry on Failure

```
✓ Exponential backoff:
   1s → 2s → 4s → 8s → 16s → cap at 5min
✓ Avoid hammering server
✓ Conserve battery
✓ Don't drop items silently
```

---

## 5. Background Sync Strategies

```
┌──────────────────┬──────────────────────────────────────┐
│ Strategy         │ When It Fires                        │
├──────────────────┼──────────────────────────────────────┤
│ Periodic         │ Every N minutes / app launch          │
│ Trigger-based    │ Form submit, page switch              │
│ Opportunistic    │ Network recovers, app foregrounded    │
│ Platform native  │ Android WorkManager, iOS BG fetch     │
└──────────────────┴──────────────────────────────────────┘
```

### Best Practice

**Combine multiple strategies.**

```
✓ Periodic for steady-state freshness
✓ Trigger-based for critical user moments
✓ Opportunistic for retry-on-reconnect
✓ Platform native for OS-friendly scheduling
```

---

## 6. Conflict Scenarios

### Scenario 1: Concurrent Edits from Multiple Devices

```
   Phone (offline)              Laptop (offline)
        │                            │
   edit "Buy milk"             edit "Buy bread"
        │                            │
        └────── both reconnect ──────┘
                     │
                     ▼
              CONFLICT! Which wins?
```

### Scenario 2: Server Changes While Client is Offline

```
   Server: "Order shipped"
        │
   Client offline edits same order: "Cancel"
        │
   Client reconnects → conflict
```

### Scenario 3: Network Partition

```
   Device appears connected
   But sync isn't reliably going through
        │
   Updates delayed, arrive out of order
   May conflict with newer server changes
```

### Scenario 4: Stale Overwrite

```
   Client thinks its local copy is latest
   Pushes it → silently overwrites newer server data
```

These are **everyday realities of offline-first**, not rare edge cases.

---

## 7. Conflict Resolution Strategies

### 1. Last-Write-Wins (LWW)

```
✓ Simple — pick higher timestamp
✗ Risky — silently overrides valid edits
✗ Data loss possible
Best for: low-stakes data (UI preferences)
```

### 2. Merge

```
✓ Combine non-overlapping fields
   e.g., one user edits phone, other edits address → merge both

✗ Complex merge logic
✗ Doesn't work for same-field conflicts
Best for: structured records with independent fields
```

### 3. Manual Review

```
✓ Prompt user to pick a version
✓ Most reliable
✗ Interrupts UX
✗ Bad if conflicts are frequent
Best for: critical data (financial, legal)
```

### 4. CRDTs / Operational Transforms

```
✓ Multi-user concurrent editing
✓ Automatic merge, no data loss
✗ Complex implementation
✗ Specific data structure required (text, lists, sets, counters)
Best for: collaborative editors (Google Docs, Figma)
```

### Choice Criteria

```
Match strategy to:
   ✓ Data sensitivity
   ✓ User expectations
   ✓ Frequency of conflicts
   ✓ Engineering budget
```

---

## 8. Sync Directionality

### One-Way Sync

```
Cloud ──► Device

Examples: news feed, dashboards, catalogs
✓ Simple
✓ No conflicts
```

### Two-Way Sync

```
Cloud ◄──► Device

Examples: CRM, chat, productivity apps
✓ Powerful
✗ Needs conflict resolution
```

### Full vs Incremental Sync

```
Full Sync:
   Replaces all data
   ✗ Heavy + slow

Incremental Sync:
   Sends only changes since last_sync_at
   ✓ Efficient
   ✓ Lower bandwidth
```

### Pull / Push / Hybrid

```
Pull only   →  Device fetches from server
Push only   →  Device sends to server
Hybrid      →  Both directions
```

### Robust Offline-First =

```
✓ Hybrid
✓ Incremental
✓ Two-way
```

---

## 9. Designing for Resilience

### Server-Side Idempotency

```
Repeating the same request → same result
   ✓ Protects against duplicates on retry
   ✓ Use idempotency keys (UUID per operation)
```

### Exponential Backoff

```
Retry intervals:
   1s, 2s, 4s, 8s, 16s, 32s, ... (cap somewhere)

✓ Reduces server strain
✓ Conserves device battery
```

### Store Failed Payloads

```
✓ Sync queue persists across app restarts
✓ Persistent error log
✓ Manual retry option for failed items
✗ Never lose data silently
```

### Decouple Sync from App Logic

```
✓ Sync engine failure ≠ app failure
✓ User can keep working on cached data
✓ Improves resilience + maintainability
```

---

## 10. Real-World Case Study: Offline Chat (WhatsApp-like)

### Send Message Flow

```
1. User types and hits Send
        │
        ▼
2. Message saved to LOCAL DB
        │
        ▼
3. Appears IMMEDIATELY in UI
   (status: pending / clock icon)
        │
        ▼
4. Added to OUTBOX queue
        │
        ▼ (when online)
5. Worker pushes to server
        │
        ▼
6. Server ACKs
        │
        ▼
7. Update local message status: sent / delivered / seen
```

### Status Updates

```
Server pushes delivery events to other clients via:
   ✓ WebSocket (real-time)
   ✓ Background polling (fallback)
```

### Conflict Example

```
Two users edit same message offline:
   1. Detect conflict during sync
   2. Apply strategy (e.g., merge for text, prompt for critical)
```

### What This Demonstrates

```
✓ Local caching → instant UX
✓ Sync queue → reliable delivery
✓ Retry → handles network drops
✓ Conflict handling → consistency
✓ All together → trustworthy product
```

---

## 11. Summary

```
✓ Design for offline FROM THE BEGINNING
   - Affects schema, sync, UX
   - Cannot be retrofitted easily

✓ Three foundational components:
   1. Local cache → fast, responsive
   2. Sync queue → reliable outbound changes
   3. Conflict resolution → consistency

✓ Prioritize user experience
   - App must feel smooth, predictable, reliable
   - Even on bad networks

✓ Systems that handle offline gracefully
   build user trust.
```

---

## 🎤 Interview Q&A

**Q1. What's the difference between "online with cache" and "offline-first"?**

A: Online-with-cache treats network as primary and cache as a perf optimization. Offline-first inverts that: local cache is the source of truth, the network is a sync mechanism that may or may not be available. The mental model — and the architecture — are fundamentally different.

**Q2. How do you handle two users editing the same record offline?**

A: Depends on the data. For low-stakes fields, last-write-wins by timestamp. For structured records, field-level merge. For critical data, prompt the user. For collaborative text, use CRDTs (e.g., Yjs) or Operational Transforms.

**Q3. Why do sync operations need to be idempotent on the server?**

A: Because retries are inevitable. If the client times out after the server processed but before the response reached the client, the client retries. Without idempotency you get duplicates (double-charge, double-create). Idempotency keys make the second call a no-op.

**Q4. What's exponential backoff and why use it?**

A: After each failed retry, double the wait time (1s → 2s → 4s → ...). Without it, a flaky network causes a thundering herd of retries that overwhelms the server, burns battery, and never recovers. Backoff gives downstream systems time to heal.

**Q5. How would you design offline support for a chat app?**

A: (1) Local DB stores all messages including pending ones, (2) UI shows pending messages instantly with a "clock" status, (3) Outbox queue holds messages awaiting sync, (4) Background worker drains it with exponential backoff, (5) Server returns ACKs that update local status to sent/delivered/seen, (6) Conflicts on edits handled per-field or prompt, (7) Idempotency keys prevent duplicate messages on retry.

---

## 🔗 Related

- Previous: [02_MVU_VIPER.md](02_MVU_VIPER.md)
- Next: [04_Selecting_UI_Patterns_By_Platform.md](04_Selecting_UI_Patterns_By_Platform.md)
- Related: [Section 6 — Reactive Principles](../Section_06_Event_Driven_Reactive/03_Reactive_Principles.md)
