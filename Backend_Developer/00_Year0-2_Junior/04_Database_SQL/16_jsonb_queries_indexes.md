# JSONB Queries + Indexes

> **Interview angle:** "Flexible schema chahiye but SQL bhi. MongoDB chahiye ya Postgres JSONB?"

---

## 1. JSONB vs JSON vs TEXT

| Type | Storage | Index | Operations |
|---|---|---|---|
| `TEXT` | Raw text | None | None |
| `JSON` | Raw JSON text | Limited | Parse on read |
| `JSONB` | Binary parsed | GIN index | Fast queries |

**Always use `JSONB`.** JSON only if you need to preserve exact formatting.

---

## 2. Why JSONB?

✅ **Use JSONB when:**
- Schema varies per row (user preferences, settings)
- Polymorphic data (events with different shapes)
- API payloads (webhook bodies, integration data)
- Document-like data within relational schema
- Avoiding excessive joins

❌ **Don't use JSONB when:**
- Data is uniform (use columns)
- Heavy aggregations needed
- Complex relations (need foreign keys)
- Field is queried/filtered very frequently (column is better)

---

## 3. Schema + Insert

```sql
CREATE TABLE events (
    id BIGSERIAL PRIMARY KEY,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert
INSERT INTO events (event_type, payload) VALUES
('signup', '{"user_id": 42, "email": "a@x.com", "source": "web"}'),
('purchase', '{"user_id": 42, "items": [{"id": 1, "qty": 2}], "total": 99.99}'),
('click', '{"user_id": 42, "page": "/home", "device": "mobile"}');

-- Update single field
UPDATE events
SET payload = jsonb_set(payload, '{verified}', 'true')
WHERE id = 1;
```

---

## 4. JSONB Operators

```sql
-- -> returns JSONB
SELECT payload->'user_id' FROM events;
-- "42" (still JSONB)

-- ->> returns TEXT
SELECT payload->>'user_id' FROM events;
-- "42" (text)

-- Cast to int
SELECT (payload->>'user_id')::int FROM events;
-- 42 (int)

-- Nested
SELECT payload->'items'->0->>'id' FROM events;

-- Contains (@>)
SELECT * FROM events
WHERE payload @> '{"user_id": 42}';
-- Matches if all keys/values present

-- Contained by (<@)
SELECT * FROM events
WHERE '{"source": "web"}' <@ payload;

-- Key exists (?)
SELECT * FROM events WHERE payload ? 'verified';

-- Any key exists (?|)
SELECT * FROM events WHERE payload ?| array['verified', 'pending'];

-- All keys exist (?&)
SELECT * FROM events WHERE payload ?& array['user_id', 'email'];

-- Path operator (#>)
SELECT payload #> '{items,0,id}' FROM events;
SELECT payload #>> '{items,0,id}' FROM events;   -- as text
```

---

## 5. Indexes for JSONB

### GIN index (general-purpose)
```sql
-- Index all keys + values
CREATE INDEX idx_events_payload ON events USING GIN (payload);

-- Faster + smaller, only index for @> queries
CREATE INDEX idx_events_payload_path ON events USING GIN (payload jsonb_path_ops);
```

Now `@>` queries use index:
```sql
EXPLAIN ANALYZE
SELECT * FROM events WHERE payload @> '{"user_id": 42}';
-- Bitmap Index Scan on idx_events_payload
```

### Expression index (specific field)
```sql
-- Index specific field — fastest for equality lookups
CREATE INDEX idx_events_user_id ON events ((payload->>'user_id'));

SELECT * FROM events WHERE payload->>'user_id' = '42';
-- Index Scan ✅

-- Typed expression index
CREATE INDEX idx_events_user_id_int
    ON events (((payload->>'user_id')::int));

SELECT * FROM events
WHERE (payload->>'user_id')::int = 42;
```

### Trade-offs

| Index Type | Use For | Size | Speed |
|---|---|---|---|
| GIN (default) | Any @>, ?, ?\|, ?& | Large | Fast |
| GIN jsonb_path_ops | Only @> | Smaller | Faster for @> |
| Expression | Specific field lookup | Small | Fastest for that field |
| BRIN | Very large tables, naturally ordered | Tiny | OK |

---

## 6. Queries with Indexes

```sql
-- ✅ Uses GIN
SELECT * FROM events WHERE payload @> '{"user_id": 42}';

-- ✅ Uses expression index
SELECT * FROM events WHERE payload->>'user_id' = '42';

-- ❌ Sequential scan — function call breaks index
SELECT * FROM events WHERE jsonb_extract_path_text(payload, 'user_id') = '42';

-- ✅ Better
SELECT * FROM events WHERE payload->>'user_id' = '42';
```

---

## 7. Modifying JSONB

```sql
-- Set a key
UPDATE events SET payload = jsonb_set(payload, '{status}', '"active"');

-- Append to array
UPDATE events
SET payload = jsonb_set(payload, '{tags}',
                        (payload->'tags') || '"new_tag"'::jsonb)
WHERE id = 1;

-- Delete a key
UPDATE events SET payload = payload - 'status';

-- Delete nested key (path)
UPDATE events SET payload = payload #- '{user,address,zip}';

-- Merge two JSONB
SELECT '{"a": 1, "b": 2}'::jsonb || '{"b": 3, "c": 4}'::jsonb;
-- {"a": 1, "b": 3, "c": 4}
```

### Atomic JSONB increment
```sql
UPDATE counters
SET data = jsonb_set(
    data,
    '{count}',
    to_jsonb(COALESCE((data->>'count')::int, 0) + 1)
)
WHERE id = 1;
```

---

## 8. Aggregations on JSONB

```sql
-- Group by JSON field
SELECT
    payload->>'source' AS source,
    COUNT(*) AS event_count
FROM events
GROUP BY payload->>'source';

-- Aggregate values into JSONB array
SELECT jsonb_agg(payload) FROM events WHERE event_type = 'signup';

-- Build JSONB
SELECT jsonb_build_object(
    'total', SUM((payload->>'amount')::float),
    'count', COUNT(*),
    'users', jsonb_agg(DISTINCT payload->>'user_id')
) FROM events;

-- Expand array elements
SELECT
    id,
    jsonb_array_elements(payload->'items') AS item
FROM events
WHERE event_type = 'purchase';

-- Extract text values from array
SELECT
    id,
    jsonb_array_elements_text(payload->'tags') AS tag
FROM events
WHERE payload ? 'tags';
```

---

## 9. JSONB + Schema Validation (Postgres 16+)

```sql
-- JSON Schema validation
ALTER TABLE events ADD CONSTRAINT payload_schema CHECK (
    jsonb_typeof(payload) = 'object' AND
    payload ? 'user_id' AND
    (payload->>'user_id') ~ '^[0-9]+$'
);

-- Or with pg_jsonschema extension
CREATE EXTENSION pg_jsonschema;

ALTER TABLE events ADD CONSTRAINT payload_valid
    CHECK (jsonschema_is_valid(
        '{
            "type": "object",
            "required": ["user_id"],
            "properties": {
                "user_id": {"type": "integer"},
                "email": {"type": "string", "format": "email"}
            }
        }'::json,
        payload::json
    ));
```

---

## 10. Common Patterns

### Pattern 1: User preferences
```sql
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    email TEXT,
    preferences JSONB DEFAULT '{}'
);

CREATE INDEX ON users USING GIN (preferences);

-- Set preference
UPDATE users
SET preferences = jsonb_set(preferences, '{theme}', '"dark"')
WHERE id = 1;

-- Query users with dark theme
SELECT * FROM users WHERE preferences @> '{"theme": "dark"}';

-- Toggle notification setting
UPDATE users SET preferences = jsonb_set(
    preferences, '{notifications,email}',
    to_jsonb(NOT (preferences->'notifications'->>'email')::boolean)
);
```

### Pattern 2: Audit log
```sql
CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY,
    user_id INT,
    action TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ON audit_log USING GIN (metadata);

-- Find login events from suspicious IPs
SELECT * FROM audit_log
WHERE action = 'login'
  AND metadata->>'ip' IN ('1.2.3.4', '5.6.7.8');
```

### Pattern 3: Polymorphic events
```sql
CREATE TABLE events (
    id BIGSERIAL PRIMARY KEY,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL
);

-- Signup event
INSERT INTO events VALUES (DEFAULT, 'signup',
    '{"email": "x@y.com", "source": "google"}');

-- Purchase event (different shape)
INSERT INTO events VALUES (DEFAULT, 'purchase',
    '{"items": [{"id": 1, "price": 99}], "total": 99}');

-- Conditional queries
SELECT * FROM events
WHERE event_type = 'purchase'
  AND (payload->>'total')::float > 100;
```

### Pattern 4: Versioned config
```sql
CREATE TABLE app_config (
    id BIGSERIAL PRIMARY KEY,
    version INT NOT NULL,
    config JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Diff between versions
SELECT
    new.config - old.config AS added,
    old.config - new.config AS removed
FROM app_config new, app_config old
WHERE new.version = old.version + 1
  AND new.version = 5;
```

---

## 11. Python Integration

```python
from sqlalchemy import Column, BigInteger, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Event(Base):
    __tablename__ = "events"
    id = Column(BigInteger, primary_key=True)
    event_type = Column(String, nullable=False)
    # MutableDict enables tracking changes to nested dicts
    payload = Column(MutableDict.as_mutable(JSONB), default=dict)


# Insert
event = Event(
    event_type="signup",
    payload={"user_id": 42, "email": "a@x.com"},
)
session.add(event)
session.commit()


# Query — contains
results = session.query(Event).filter(
    Event.payload.contains({"user_id": 42})
).all()


# Query — specific key
results = session.query(Event).filter(
    Event.payload["user_id"].astext == "42"
).all()


# Query — typed (int)
results = session.query(Event).filter(
    Event.payload["user_id"].as_integer() > 100
).all()


# Update — set nested key
event.payload["verified"] = True
session.commit()    # MutableDict tracks change


# Multi-key search
from sqlalchemy import or_
results = session.query(Event).filter(
    or_(
        Event.payload.contains({"source": "web"}),
        Event.payload.contains({"source": "mobile"}),
    )
).all()
```

### Pydantic + JSONB
```python
from pydantic import BaseModel
from sqlalchemy.dialects.postgresql import JSONB

class UserPreferences(BaseModel):
    theme: str = "light"
    language: str = "en"
    notifications: dict[str, bool] = {}

class User(Base):
    __tablename__ = "users"
    id = Column(BigInteger, primary_key=True)
    preferences = Column(JSONB)

# Convert Pydantic ↔ JSONB
def set_prefs(user_id: int, prefs: UserPreferences, session):
    user = session.get(User, user_id)
    user.preferences = prefs.model_dump()
    session.commit()

def get_prefs(user_id: int, session) -> UserPreferences:
    user = session.get(User, user_id)
    return UserPreferences(**user.preferences) if user.preferences else UserPreferences()
```

---

## 12. Performance Tips

### 1. Use expression indexes for frequent lookups
```sql
-- Frequent: WHERE payload->>'user_id' = X
CREATE INDEX ON events ((payload->>'user_id'));
```

### 2. GIN jsonb_path_ops if only `@>` queries
Smaller index, faster.

### 3. Avoid huge JSONB (> 1MB)
Postgres compresses with TOAST, but huge JSONB slows queries.

### 4. Don't store arrays of arrays of arrays
Deep nesting = parser overhead.

### 5. JSONB vs separate columns
```sql
-- ❌ All fields in JSONB → no schema enforcement, harder queries
data JSONB

-- ✅ Common fields as columns, varying fields in JSONB
user_id INT,
event_type TEXT,
amount NUMERIC,
metadata JSONB
```

---

## 13. JSONB vs MongoDB

| Aspect | JSONB | MongoDB |
|---|---|---|
| Joins | ✅ Easy | ❌ Awkward |
| Transactions | ✅ ACID | ⚠️ Per-doc by default |
| Schema flexibility | ✅ | ✅ |
| Index types | GIN, BTREE, expression | Many |
| Aggregations | SQL GROUP BY | Aggregation pipeline |
| Scale (single node) | TB | TB |
| Scale (distributed) | Citus | Native sharding |
| Operational cost | One DB | Separate cluster |

**Choose JSONB when:**
- Already using Postgres
- Need joins + transactions
- Mostly relational with some flexible fields

**Choose MongoDB when:**
- Document-first design
- Very deep nesting
- Distributed by default needed

---

## 14. Common Pitfalls

### Pitfall 1: No index → slow queries
```sql
-- 10M row table without GIN index
WHERE payload @> '{"user_id": 42}'   -- Sequential scan!
```

### Pitfall 2: Wrong operator
```sql
-- = comparison treats JSONB as binary blob
WHERE payload = '{"a": 1}'    -- ❌ rarely what you want

-- Use @> for containment
WHERE payload @> '{"a": 1}'   -- ✅
```

### Pitfall 3: Casting performance
```sql
-- Function call in WHERE prevents index use
WHERE jsonb_extract_path_text(payload, 'user_id') = '42'

-- Use operator
WHERE payload->>'user_id' = '42'
```

### Pitfall 4: Updates rewrite whole JSONB
Updating one field = whole column rewritten + new row version. Postgres MVCC. Not in-place.

### Pitfall 5: Type confusion
```sql
payload->'count'    -- JSONB ("42")
payload->>'count'   -- TEXT  "42"
(payload->>'count')::int   -- INTEGER 42
```

---

## 15. Interview Questions

**Q1: JSON vs JSONB?**
JSON = raw text, parse on read. JSONB = binary parsed, indexable, fast. Always JSONB.

**Q2: Index for JSONB?**
GIN (general) or jsonb_path_ops (smaller, only @>) or expression index (specific field).

**Q3: -> vs ->>?**
-> returns JSONB. ->> returns TEXT.

**Q4: @> kya?**
Contains operator. Checks if all keys/values of right are in left. Index-aware.

**Q5: When NOT to use JSONB?**
Uniform data (use columns), heavy aggregations, complex relationships, sharded scale.

**Q6: Update single field in JSONB?**
```sql
SET col = jsonb_set(col, '{path,to,field}', '"new_value"')
```

**Q7: JSONB vs MongoDB?**
JSONB: relational + JSON, ACID, joins. MongoDB: document-first, sharding, schema-less.

---

## 16. Best Practices

1. **Always JSONB**, never JSON
2. **GIN index** on frequently-queried JSONB
3. **Expression index** for specific fields
4. **`@>` operator** uses index, `->>` casts don't (without expression index)
5. **Common fields as columns**, variable in JSONB
6. **Validate schema** via CHECK or pg_jsonschema
7. **Limit nesting depth** (3-4 levels max)
8. **MutableDict in SQLAlchemy** for change tracking
9. **Don't store huge JSON** — split into rows
10. **Monitor JSONB column size** — avoid >100KB rows

---

## Related
- [[01_postgresql_advanced]]
- [[13_postgresql_performance_tuning]]
- [[15_postgresql_fulltext_search]]
