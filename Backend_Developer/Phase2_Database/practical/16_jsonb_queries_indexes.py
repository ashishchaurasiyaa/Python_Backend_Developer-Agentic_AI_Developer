"""
============================================================
JSONB QUERIES + INDEXES — Practical
============================================================
SQL templates + SQLAlchemy patterns for JSONB.
"""


# ============================================================
# 1. SCHEMA
# ============================================================
SCHEMA = """
-- Events table with JSONB payload
CREATE TABLE events (
    id BIGSERIAL PRIMARY KEY,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Schema validation (Postgres 16+)
ALTER TABLE events ADD CONSTRAINT payload_is_object
    CHECK (jsonb_typeof(payload) = 'object');

-- User preferences
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    email TEXT UNIQUE,
    preferences JSONB DEFAULT '{}'::jsonb,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Audit log
CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY,
    actor_id BIGINT,
    action TEXT NOT NULL,
    target_type TEXT,
    target_id BIGINT,
    changes JSONB NOT NULL DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
"""


# ============================================================
# 2. INDEX STRATEGIES
# ============================================================
INDEXES = """
-- ===== 1. GIN INDEX (general-purpose) =====
-- Supports: @>, ?, ?|, ?&
CREATE INDEX idx_events_payload_gin ON events USING GIN (payload);

-- ===== 2. GIN with jsonb_path_ops (smaller, faster for @>) =====
-- Only supports @>, but ~50% smaller and faster
CREATE INDEX idx_events_payload_path ON events USING GIN (payload jsonb_path_ops);

-- ===== 3. EXPRESSION INDEX (specific field, fastest for equality) =====
-- Best for: WHERE payload->>'user_id' = X
CREATE INDEX idx_events_user_id ON events ((payload->>'user_id'));

-- Typed version (for numeric comparisons)
CREATE INDEX idx_events_user_id_int ON events (((payload->>'user_id')::bigint));

-- Numeric range queries
CREATE INDEX idx_events_amount ON events (((payload->>'amount')::numeric));

-- ===== 4. PARTIAL INDEX (subset of rows) =====
-- Index only events with errors
CREATE INDEX idx_events_errors ON events USING GIN (payload)
    WHERE event_type = 'error';

-- ===== 5. COMPOSITE INDEX =====
-- For combined filters
CREATE INDEX idx_events_type_user ON events (event_type, ((payload->>'user_id')));

-- ===== INDEX SIZE COMPARISON =====
SELECT
    schemaname, tablename, indexname,
    pg_size_pretty(pg_relation_size(indexrelid)) AS size
FROM pg_stat_user_indexes
WHERE tablename = 'events'
ORDER BY pg_relation_size(indexrelid) DESC;
"""


# ============================================================
# 3. QUERY PATTERNS
# ============================================================
QUERIES = """
-- ===== EXTRACTING VALUES =====
SELECT payload->'user_id' FROM events;          -- JSONB ("42")
SELECT payload->>'user_id' FROM events;         -- TEXT  "42"
SELECT (payload->>'user_id')::bigint FROM events;  -- INT 42

-- Nested
SELECT payload->'user'->>'email' FROM events;
SELECT payload->'items'->0->>'name' FROM events;  -- first item name

-- Path operators
SELECT payload #> '{items,0,id}' FROM events;     -- JSONB
SELECT payload #>> '{items,0,id}' FROM events;    -- TEXT

-- ===== CONTAINMENT =====
-- @> = contains (left has right inside it)
SELECT * FROM events WHERE payload @> '{"user_id": 42}';

SELECT * FROM events WHERE payload @> '{"items": [{"id": 5}]}';
-- Matches any event with item id=5 in items array

-- <@ = contained by (left is inside right)
SELECT * FROM events WHERE '{"user_id": 42}'::jsonb <@ payload;

-- ===== KEY EXISTENCE =====
-- Key exists
SELECT * FROM events WHERE payload ? 'verified';

-- ANY of these keys
SELECT * FROM events WHERE payload ?| ARRAY['verified', 'pending'];

-- ALL of these keys
SELECT * FROM events WHERE payload ?& ARRAY['user_id', 'email'];

-- ===== EQUALITY ON FIELD =====
SELECT * FROM events WHERE payload->>'user_id' = '42';

-- With expression index — fast!
SELECT * FROM events WHERE (payload->>'user_id')::int = 42;

-- ===== NUMERIC COMPARISON =====
SELECT * FROM events
WHERE (payload->>'amount')::numeric > 100;

-- Sum
SELECT SUM((payload->>'amount')::numeric)
FROM events
WHERE event_type = 'purchase';

-- ===== ARRAY OPERATIONS =====
-- Array length
SELECT jsonb_array_length(payload->'items') FROM events;

-- Array contains element
SELECT * FROM events WHERE payload->'tags' ? 'urgent';

-- Expand array
SELECT id, jsonb_array_elements(payload->'items') AS item
FROM events WHERE event_type = 'purchase';

-- Filter array elements
SELECT id, jsonb_path_query(payload, '$.items[*] ? (@.price > 50)') AS expensive_items
FROM events;

-- ===== TEXT SEARCH WITHIN JSONB =====
-- Convert to text for LIKE/ILIKE
SELECT * FROM events WHERE payload::text ILIKE '%error%';

-- Better: index specific field
SELECT * FROM events WHERE payload->>'message' ILIKE '%error%';
-- + create GIN trigram index on payload->>'message'

-- ===== JSON PATH (Postgres 12+) =====
-- Powerful query language
SELECT * FROM events
WHERE payload @? '$.items[*] ? (@.price > 100)';

SELECT jsonb_path_query_array(payload, '$.items[*].id')
FROM events WHERE event_type = 'purchase';
"""


# ============================================================
# 4. MODIFICATION
# ============================================================
MODIFICATIONS = """
-- ===== SET A KEY =====
UPDATE events SET payload = jsonb_set(payload, '{verified}', 'true'::jsonb)
WHERE id = 1;

-- Create if missing (creates nested path)
UPDATE events SET payload = jsonb_set(payload, '{user,address,city}', '"Bangalore"', true)
WHERE id = 1;

-- ===== DELETE A KEY =====
UPDATE events SET payload = payload - 'temp_field';

-- Delete nested
UPDATE events SET payload = payload #- '{user,address,zip}';

-- Delete multiple
UPDATE events SET payload = payload - ARRAY['key1', 'key2'];

-- ===== MERGE / CONCAT =====
-- Right-hand keys overwrite left
SELECT '{"a": 1, "b": 2}'::jsonb || '{"b": 3, "c": 4}'::jsonb;
-- Result: {"a": 1, "b": 3, "c": 4}

UPDATE users SET preferences = preferences || '{"theme": "dark"}'::jsonb;

-- ===== APPEND TO ARRAY =====
UPDATE events
SET payload = jsonb_set(
    payload, '{tags}',
    (payload->'tags') || '"new"'::jsonb
)
WHERE id = 1;

-- Initialize array if null
UPDATE events
SET payload = jsonb_set(
    COALESCE(payload, '{}'::jsonb),
    '{tags}',
    COALESCE(payload->'tags', '[]'::jsonb) || '"new"'::jsonb,
    true
)
WHERE id = 1;

-- ===== ATOMIC INCREMENT =====
UPDATE counters
SET data = jsonb_set(
    data, '{count}',
    to_jsonb(COALESCE((data->>'count')::int, 0) + 1)
)
WHERE id = 1;
"""


# ============================================================
# 5. AGGREGATIONS
# ============================================================
AGGREGATIONS = """
-- ===== GROUP BY JSONB FIELD =====
SELECT
    payload->>'source' AS source,
    COUNT(*) AS event_count,
    AVG((payload->>'amount')::numeric) AS avg_amount
FROM events
GROUP BY payload->>'source'
ORDER BY event_count DESC;

-- ===== AGGREGATE TO JSONB =====
-- All payloads as array
SELECT jsonb_agg(payload) FROM events WHERE event_type = 'signup';

-- Build aggregated JSONB
SELECT jsonb_build_object(
    'total_events', COUNT(*),
    'total_amount', SUM((payload->>'amount')::numeric),
    'unique_users', COUNT(DISTINCT payload->>'user_id'),
    'top_sources', jsonb_agg(DISTINCT payload->>'source')
) FROM events;

-- ===== UNNEST ARRAYS =====
SELECT
    e.id,
    item->>'name' AS item_name,
    (item->>'price')::numeric AS price
FROM events e,
     jsonb_array_elements(e.payload->'items') AS item
WHERE e.event_type = 'purchase';

-- ===== GROUP BY NESTED FIELD =====
SELECT
    item->>'category' AS category,
    SUM((item->>'price')::numeric) AS total_revenue
FROM events e,
     jsonb_array_elements(e.payload->'items') AS item
WHERE e.event_type = 'purchase'
GROUP BY item->>'category';
"""


# ============================================================
# 6. PYTHON: SQLAlchemy
# ============================================================
PYTHON_SQLALCHEMY = '''
from sqlalchemy import Column, BigInteger, String, func, cast, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Event(Base):
    __tablename__ = "events"
    id = Column(BigInteger, primary_key=True)
    event_type = Column(String, nullable=False)
    # MutableDict tracks nested changes (so SQLAlchemy knows to UPDATE)
    payload = Column(MutableDict.as_mutable(JSONB), default=dict)


class User(Base):
    __tablename__ = "users"
    id = Column(BigInteger, primary_key=True)
    email = Column(String, unique=True)
    preferences = Column(MutableDict.as_mutable(JSONB), default=dict)


# ===== INSERT =====
event = Event(event_type="signup", payload={
    "user_id": 42, "email": "a@x.com", "source": "web"
})
session.add(event)
session.commit()


# ===== QUERY: containment =====
results = session.query(Event).filter(
    Event.payload.contains({"user_id": 42})
).all()


# ===== QUERY: specific field equality =====
results = session.query(Event).filter(
    Event.payload["user_id"].astext == "42"
).all()


# ===== QUERY: numeric comparison =====
results = session.query(Event).filter(
    Event.payload["amount"].astext.cast(Integer) > 100
).all()

# Or use as_integer/as_float helpers
results = session.query(Event).filter(
    Event.payload["amount"].as_integer() > 100
).all()


# ===== QUERY: key exists =====
results = session.query(Event).filter(
    Event.payload.has_key("verified")
).all()


# ===== UPDATE =====
event = session.query(Event).first()
event.payload["verified"] = True   # MutableDict tracks change
session.commit()    # automatically detected dirty

# Or atomic UPDATE
session.query(Event).filter(Event.id == 1).update({
    "payload": func.jsonb_set(Event.payload, "{verified}", "true")
}, synchronize_session=False)
session.commit()


# ===== AGGREGATE =====
# Group by JSON field
result = session.query(
    Event.payload["source"].astext.label("source"),
    func.count(Event.id).label("count"),
).group_by(Event.payload["source"].astext).all()


# ===== JSONB PATH QUERY =====
results = session.execute(text("""
    SELECT * FROM events
    WHERE payload @? '$.items[*] ? (@.price > :min_price)'
"""), {"min_price": 100}).all()
'''


# ============================================================
# 7. FASTAPI INTEGRATION
# ============================================================
FASTAPI_INTEGRATION = '''
from fastapi import FastAPI, Query, Body, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, cast, Integer
from sqlalchemy.dialects.postgresql import JSONB

app = FastAPI()


class UserPreferences(BaseModel):
    """Type-safe schema for JSONB field."""
    theme: str = "light"
    language: str = "en"
    notifications: dict[str, bool] = {}
    timezone: str = "UTC"


@app.get("/users/{user_id}/preferences", response_model=UserPreferences)
async def get_preferences(user_id: int, db: AsyncSession = Depends(get_db)):
    user = await db.get(User, user_id)
    return UserPreferences(**user.preferences) if user.preferences else UserPreferences()


@app.put("/users/{user_id}/preferences", response_model=UserPreferences)
async def update_preferences(
    user_id: int,
    prefs: UserPreferences,
    db: AsyncSession = Depends(get_db),
):
    """Replace entire preferences."""
    user = await db.get(User, user_id)
    user.preferences = prefs.model_dump()
    await db.commit()
    return prefs


@app.patch("/users/{user_id}/preferences/{key}")
async def patch_preference(
    user_id: int,
    key: str,
    value: dict = Body(...),
    db: AsyncSession = Depends(get_db),
):
    """Atomic update of single key (no race condition)."""
    sql = text("""
        UPDATE users
        SET preferences = jsonb_set(preferences, ARRAY[:key], :value::jsonb, true)
        WHERE id = :user_id
        RETURNING preferences
    """)
    result = await db.execute(sql, {
        "user_id": user_id,
        "key": key,
        "value": json.dumps(value["value"]),
    })
    await db.commit()
    return result.scalar()


@app.get("/events/search")
async def search_events(
    user_id: int | None = None,
    event_type: str | None = None,
    min_amount: float | None = None,
    source: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Flexible JSONB-based filtering."""
    query = select(Event)

    if event_type:
        query = query.where(Event.event_type == event_type)
    if user_id:
        query = query.where(Event.payload["user_id"].as_integer() == user_id)
    if min_amount:
        query = query.where(Event.payload["amount"].as_float() >= min_amount)
    if source:
        query = query.where(Event.payload["source"].astext == source)

    result = await db.execute(query)
    return result.scalars().all()


@app.post("/events/{event_id}/tag")
async def add_tag(
    event_id: int,
    tag: str,
    db: AsyncSession = Depends(get_db),
):
    """Atomic array append."""
    sql = text("""
        UPDATE events
        SET payload = jsonb_set(
            COALESCE(payload, '{}'::jsonb),
            '{tags}',
            COALESCE(payload->'tags', '[]'::jsonb) || to_jsonb(:tag::text),
            true
        )
        WHERE id = :event_id
        RETURNING payload->'tags' AS tags
    """)
    result = await db.execute(sql, {"event_id": event_id, "tag": tag})
    await db.commit()
    return {"tags": result.scalar()}
'''


# ============================================================
# 8. SCHEMA VALIDATION
# ============================================================
VALIDATION = """
-- Postgres 16+: native JSON Schema (pg_jsonschema extension)
CREATE EXTENSION pg_jsonschema;

ALTER TABLE events ADD CONSTRAINT payload_schema
    CHECK (jsonschema_is_valid(
        '{
            "type": "object",
            "required": ["user_id"],
            "properties": {
                "user_id": {"type": "integer", "minimum": 1},
                "email": {"type": "string", "format": "email"},
                "amount": {"type": "number", "minimum": 0}
            }
        }'::json,
        payload::json
    ));

-- Simpler: CHECK constraints
ALTER TABLE events ADD CONSTRAINT payload_user_id_present
    CHECK (payload ? 'user_id');

ALTER TABLE events ADD CONSTRAINT payload_user_id_numeric
    CHECK ((payload->>'user_id') ~ '^[0-9]+$');

ALTER TABLE events ADD CONSTRAINT payload_amount_positive
    CHECK (
        (payload->>'amount') IS NULL OR
        (payload->>'amount')::numeric > 0
    );
"""


# ============================================================
# 9. PERFORMANCE COMPARISON
# ============================================================
PERFORMANCE_GUIDE = """
================================================================
JSONB INDEX PERFORMANCE COMPARISON
================================================================

Workload: 1M rows, payload like {"user_id": int, "email": str, "items": [...]}

Query: WHERE payload @> '{"user_id": 42}'

| Index Type             | Build Time | Size | Query Time |
|------------------------|------------|------|------------|
| No index               | -          | 0    | 5,000 ms   |
| GIN jsonb_ops          | 60s        | 600MB| 5 ms       |
| GIN jsonb_path_ops     | 40s        | 250MB| 3 ms       |
| Expression (user_id)   | 5s         | 50MB | 1 ms       |

Query: WHERE payload->>'user_id' = '42'

| Index Type             | Query Time |
|------------------------|------------|
| No index               | 5,000 ms   |
| GIN jsonb_ops          | 5,000 ms   |  (doesn't help!)
| Expression (user_id)   | 1 ms       |  ✅

LESSON: Use expression indexes for specific frequently-queried fields.
        Use GIN for arbitrary @> queries.
================================================================
"""


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("JSONB QUERIES + INDEXES — Practical")
    print("=" * 60)

    print("\n--- SCHEMA ---")
    print(SCHEMA)
    print("\n--- INDEXES ---")
    print(INDEXES)
    print("\n--- QUERIES ---")
    print(QUERIES)
    print("\n--- MODIFICATIONS ---")
    print(MODIFICATIONS)
    print("\n--- AGGREGATIONS ---")
    print(AGGREGATIONS)
    print("\n--- PYTHON SQLALCHEMY ---")
    print(PYTHON_SQLALCHEMY)
    print("\n--- FASTAPI INTEGRATION ---")
    print(FASTAPI_INTEGRATION)
    print("\n--- VALIDATION ---")
    print(VALIDATION)
    print(PERFORMANCE_GUIDE)
