# Pagination — Offset vs Keyset/Cursor

## 1. The Two Strategies

### LIMIT/OFFSET (Page-Number Pagination)

```sql
-- Page 1
SELECT * FROM posts ORDER BY created_at DESC LIMIT 20 OFFSET 0;

-- Page 2
SELECT * FROM posts ORDER BY created_at DESC LIMIT 20 OFFSET 20;

-- Page 100
SELECT * FROM posts ORDER BY created_at DESC LIMIT 20 OFFSET 1980;
```

### Keyset / Cursor Pagination

```sql
-- First page
SELECT * FROM posts ORDER BY created_at DESC, id DESC LIMIT 20;

-- Next page — use last seen values as cursor
SELECT * FROM posts
WHERE (created_at, id) < ('2026-08-15 10:30:00', 4521)
ORDER BY created_at DESC, id DESC
LIMIT 20;
```

---

## 2. Why LIMIT/OFFSET Breaks at Scale

### Problem 1: Deep pagination is slow

```sql
-- Page 50,000 (offset = 1,000,000)
SELECT * FROM posts ORDER BY created_at DESC LIMIT 20 OFFSET 1000000;
```

PostgreSQL must:
1. Sort (or scan index) to find the first 1,000,020 rows
2. Discard the first 1,000,000
3. Return 20

Even with an index on `created_at`, the database must traverse 1M index entries. At 10M rows, this is seconds of latency.

### Problem 2: Page drift (data shifts between requests)

```
Time 0: Table has posts [A, B, C, D, E, F, G, H, I, J]
User reads page 1: [A, B, C, D, E]    ← offset 0

Time 1: New post Z inserted → [Z, A, B, C, D, E, F, G, H, I, J]
User reads page 2: [D, E, F, G, H]    ← offset 5

Post D and E appear on BOTH pages. User sees them twice.
```

If posts are deleted between pages, the opposite: items are skipped entirely.

### Problem 3: COUNT(*) is expensive

Most pagination UIs show "Page 5 of 312". This requires:

```sql
SELECT COUNT(*) FROM posts WHERE status = 'published';
-- On 10M rows: full table scan or full index scan — expensive
```

---

## 3. Keyset Pagination — How It Works

```sql
-- First page: no cursor needed
SELECT id, title, created_at
FROM posts
WHERE status = 'published'
ORDER BY created_at DESC, id DESC
LIMIT 20;

-- Save last row: created_at='2026-08-10 09:15:00', id=8342

-- Next page: WHERE clause acts as cursor
SELECT id, title, created_at
FROM posts
WHERE status = 'published'
  AND (created_at, id) < ('2026-08-10 09:15:00', 8342)
ORDER BY created_at DESC, id DESC
LIMIT 20;
```

SQL: `WHERE (created_at, id) < (val1, val2)` is row comparison — uses composite index.

### Why this is fast

```sql
CREATE INDEX idx_posts_created_id ON posts(created_at DESC, id DESC);

-- The WHERE clause uses the index directly:
-- "Find the first entry < (val1, val2) in the B-Tree"
-- O(log N) lookup — no rows discarded
```

### Encoding the cursor for API

```python
import base64, json

def encode_cursor(created_at: str, post_id: int) -> str:
    payload = json.dumps({"created_at": created_at, "id": post_id})
    return base64.urlsafe_b64encode(payload.encode()).decode()

def decode_cursor(cursor: str) -> dict:
    payload = base64.urlsafe_b64decode(cursor.encode()).decode()
    return json.loads(payload)

# API response:
{
    "results": [...],
    "next_cursor": "eyJjcmVhdGVkX2F0IjogIjIwMjYtMDgtMTAiLCAiaWQiOiA4MzQyfQ=="
}
```

---

## 4. Keyset Requirements

### Ordering column must be stable and unique (or combination unique)

```sql
-- ❌ WRONG: created_at alone may have ties
ORDER BY created_at DESC

-- ✅ CORRECT: add id as tiebreaker (always unique)
ORDER BY created_at DESC, id DESC
```

Without a unique tiebreaker: two rows with the same `created_at` may cause the cursor to skip or repeat rows.

### You cannot jump to an arbitrary page

```
Page 1 → cursor_1
Page 2 → cursor_2
...
Page 50 → cannot reach without fetching pages 1–49 first
```

This is the trade-off: no "Jump to page 500" button with keyset pagination.

---

## 5. Comparison Table

| Feature | LIMIT/OFFSET | Keyset/Cursor |
|---------|-------------|----------------|
| Performance at page N | O(N) — scans N×page_size rows | O(log N) — index lookup |
| Page drift | Yes — inserts/deletes shift pages | No — cursor is position-stable |
| COUNT(*) / total pages | Easy (but expensive) | Not possible without COUNT |
| Random page access | Yes — jump to any page | No — must follow cursor chain |
| Implementation complexity | Simple | Moderate (encode/decode cursor) |
| Good for | Admin panels, small datasets | Feeds, infinite scroll, large datasets |
| DRF support | `PageNumberPagination` | `CursorPagination` |
| FastAPI support | Manual query param | Manual cursor encode/decode |

---

## 6. Hybrid Strategy (Production)

Many systems use both:

```
Admin panel:        LIMIT/OFFSET  (needs page jumping, small dataset)
Public API feed:    Keyset        (infinite scroll, 10M+ rows)
Export endpoint:    Keyset        (large data export without memory spike)
Search results:     LIMIT/OFFSET  (needs total count for "X results found")
```

---

## 7. DRF Implementation

```python
from rest_framework.pagination import CursorPagination, PageNumberPagination

class FeedCursorPagination(CursorPagination):
    page_size              = 20
    ordering               = '-created_at'  # must match DB index
    page_size_query_param  = 'page_size'
    max_page_size          = 100

class AdminPagePagination(PageNumberPagination):
    page_size              = 50
    page_size_query_param  = 'page_size'
    max_page_size          = 200
```

---

## 8. FastAPI / Raw SQL Implementation

```python
from fastapi import FastAPI, Query
from typing import Optional
import base64, json

app = FastAPI()

def encode_cursor(post_id: int, created_at: str) -> str:
    data = json.dumps({"id": post_id, "created_at": created_at})
    return base64.urlsafe_b64encode(data.encode()).decode()

def decode_cursor(cursor: str) -> dict:
    return json.loads(base64.urlsafe_b64decode(cursor).decode())

@app.get("/posts/")
async def list_posts(cursor: Optional[str] = None, limit: int = Query(20, le=100)):
    if cursor:
        c = decode_cursor(cursor)
        # Keyset WHERE clause
        rows = await db.fetch(
            """
            SELECT id, title, created_at FROM posts
            WHERE status = 'published'
              AND (created_at, id) < (:ca, :id)
            ORDER BY created_at DESC, id DESC
            LIMIT :limit
            """,
            ca=c["created_at"], id=c["id"], limit=limit + 1
        )
    else:
        rows = await db.fetch(
            "SELECT id, title, created_at FROM posts "
            "WHERE status = 'published' ORDER BY created_at DESC, id DESC LIMIT :limit",
            limit=limit + 1
        )

    has_next = len(rows) > limit
    items = rows[:limit]
    next_cursor = encode_cursor(items[-1]["id"], str(items[-1]["created_at"])) if has_next else None

    return {"results": items, "next_cursor": next_cursor}
```

---

## 9. Production Edge Cases

### Handling ties in created_at

```sql
-- Two posts created at exact same microsecond
-- Both have (created_at='2026-08-10 10:00:00.000000', id=[8341, 8342])
-- Cursor after id=8342:
WHERE (created_at, id) < ('2026-08-10 10:00:00.000000', 8342)
-- This correctly returns id=8341 (same timestamp, lower id)
-- id as tiebreaker saves us
```

### Deleted rows

Keyset is immune to delete-based drift — the cursor is a positional bookmark, not a page number.

### Bi-directional pagination (prev + next)

```sql
-- "previous" page: reverse the ordering and comparison
WHERE (created_at, id) > (:ca, :id)
ORDER BY created_at ASC, id ASC
LIMIT 20
-- Then reverse the result set in application code
```

---

## 10. Interview Questions

**Q: LIMIT/OFFSET deep pagination slow kyon hai?**
Database OFFSET N rows ko scan karta hai aur discard karta hai — koi shortcut nahi hai index se. OFFSET 1,000,000 = 1M rows process karne ke baad 20 return karna.

**Q: Page drift kya hai? Keyset se kaise solve hota hai?**
Offset-based mein agar koi row insert/delete ho toh baaki rows shift ho jaati hain — agle page pe duplicate ya missing items aate hain. Keyset mein cursor exact position pe hai, shifting se affect nahi hota.

**Q: Keyset pagination ki limitation kya hai?**
Arbitrary page pe jump nahi kar sakte ("Go to page 500" impossible). Total count nahi milta. Complex filters ke saath cursor encoding complex ho jaata hai.

**Q: Instagram/Twitter-style feed mein kaunsa pagination use karte ho?**
Cursor/keyset — infinite scroll, billions of posts, real-time inserts — OFFSET kaam hi nahi karta iss scale pe.

**Q: Ordering column unique hona kyon zaroori hai cursor pagination mein?**
Agar ties hain (same created_at) aur no tiebreaker, cursor unn rows ke beech kisi bhi point pe land kar sakta hai — rows skip ya repeat ho sakte hain. `id` as tiebreaker (always unique + sequential) guarantee karta hai stable cursor position.
