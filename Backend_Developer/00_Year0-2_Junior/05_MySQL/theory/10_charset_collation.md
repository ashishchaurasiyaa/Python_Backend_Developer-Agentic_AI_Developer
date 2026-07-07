# MySQL Character Set & Collation (utf8 vs utf8mb4)

## Why It Matters

This is the single most common **production gotcha** in MySQL, more than a
theory topic — the kind of bug that actually happens to real teams, not just
an interview question. MySQL's `utf8` charset is **not real UTF-8** (a
historical naming mistake MySQL never fixed for backward compatibility) — it
only supports 3-byte characters, silently breaking on emoji and many
non-Latin scripts. Every team that's shipped a MySQL-backed app with user
input has either hit this or is one emoji-in-a-username away from hitting it.

Senior interview: "A user's bio field with an emoji fails to insert with a
cryptic 'Incorrect string value' error — why, and how do you fix it?" →
table is on `utf8`, not `utf8mb4`; emoji need 4 bytes.

---

## The core problem

```sql
-- MySQL's "utf8" charset is a LIE — it's really "UTF-8 but max 3 bytes per char"
-- Introduced before the full 4-byte UTF-8 spec was common; kept for compat.

CREATE TABLE users (
    bio VARCHAR(255) CHARACTER SET utf8   -- ⚠️ WRONG for modern text
);

INSERT INTO users (bio) VALUES ('Loving this! 😀');
-- ERROR 1366 (HY000): Incorrect string value: '\xF0\x9F\x98\x80' for column 'bio'
-- The emoji is 4 bytes in real UTF-8 — utf8 (3-byte) charset rejects it.
```

**Fix:** always use `utf8mb4` (MySQL's name for actual, full UTF-8) for any
new table.

```sql
CREATE TABLE users (
    bio VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
);

-- Set database-level default so every new table inherits it
ALTER DATABASE myapp CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

```sql
-- Migrating an EXISTING table from utf8 to utf8mb4
ALTER TABLE users
    CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
-- Note: this can be slow on large tables (full table rewrite) — plan
-- as an online migration on production (pt-online-schema-change / gh-ost).
```

---

## Collation — how strings compare/sort, not just storage

```sql
-- Collation controls case-sensitivity and sort order for string comparisons
-- utf8mb4_general_ci   → case-insensitive, faster, less linguistically accurate
-- utf8mb4_unicode_ci   → case-insensitive, follows Unicode collation rules (better for i18n)
-- utf8mb4_bin          → byte-for-byte comparison, CASE-SENSITIVE

SELECT 'Ashish' = 'ashish' COLLATE utf8mb4_general_ci;  -- 1 (true, case-insensitive)
SELECT 'Ashish' = 'ashish' COLLATE utf8mb4_bin;         -- 0 (false, case-sensitive)
```

### The production bug this causes

```sql
-- If your `email` column uses a case-insensitive collation (the default!):
SELECT * FROM users WHERE email = 'User@Example.com';
-- ALSO matches a row stored as 'user@example.com' — often desired for email,
-- but if you assumed case-SENSITIVE uniqueness for something like API keys
-- or usernames, a case-insensitive collation silently creates duplicate-looking
-- "unique" values that actually collide.

CREATE TABLE api_keys (
    key_value VARCHAR(64) COLLATE utf8mb4_bin UNIQUE  -- explicit: case matters here
);
```

**Interview-correct rule of thumb:** default (`_general_ci`/`_unicode_ci`) for
human-facing text like names/emails; explicit `_bin` for anything where case
must be preserved as a distinct value (API keys, hashes, case-sensitive slugs).

---

## Connection-level charset (the other place this bites you)

```python
# Python (PyMySQL/mysqlclient) — if the CONNECTION charset doesn't match
# the column's, you get mangled data even when the schema is correct
import pymysql

conn = pymysql.connect(
    host="localhost", user="app", password="secret", db="myapp",
    charset="utf8mb4",   # ⚠️ must match table charset, or bytes get mangled
)
```

```python
# Django settings.py
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "OPTIONS": {"charset": "utf8mb4"},
    }
}
```

Mismatched connection charset is a separate failure mode from column
charset — you can have `utf8mb4` columns but still corrupt data if the
client connection negotiates `latin1` or plain `utf8`.

---

## Interview Q&A

**Q: What's wrong with MySQL's `utf8` charset?**
A: Despite the name, it only supports up to 3 bytes per character — it
predates full 4-byte UTF-8 adoption and was never renamed for backward
compatibility. Emoji, many CJK extension characters, and some symbols need 4
bytes and will fail to insert. Always use `utf8mb4` instead.

**Q: `utf8mb4_general_ci` vs `utf8mb4_unicode_ci` — which do you pick?**
A: `_unicode_ci` follows proper Unicode collation rules (more linguistically
correct sorting/comparison for accented/non-Latin text) at a small
performance cost; `_general_ci` is faster but less accurate. For most
applications, correctness wins — default to `_unicode_ci` (or MySQL 8's
newer `utf8mb4_0900_ai_ci` if on 8.0+).

**Q: Column is `utf8mb4` but data still looks corrupted — what else to check?**
A: The client connection's charset. Schema-level charset and connection-level
charset are independent settings; a mismatch mangles bytes even with the
correct column type.

---

Related: `01_basics_installation_crud.md` (where charset is set at table
creation time — this file was previously the only place it was mentioned).
