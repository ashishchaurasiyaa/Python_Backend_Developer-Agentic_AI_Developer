# Database Security — PostgreSQL

## 1. Users, Roles, and Least Privilege

PostgreSQL uses **roles** for both users and groups. A role can log in (user) or be used as a group.

```sql
-- Create a role that can log in (= user)
CREATE ROLE app_user LOGIN PASSWORD 'strong_password_here';

-- Create a group role (no login)
CREATE ROLE readonly_role;
CREATE ROLE readwrite_role;

-- Grant group to user
GRANT readonly_role TO app_user;
```

### Principle of Least Privilege

```sql
-- ❌ BAD: Application user has superuser or too many privileges
CREATE ROLE app LOGIN SUPERUSER;

-- ✅ GOOD: Only what the app needs
CREATE ROLE app_api LOGIN PASSWORD 'secure123';
GRANT CONNECT ON DATABASE mydb TO app_api;
GRANT USAGE ON SCHEMA public TO app_api;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_api;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_api;

-- Reporting / analytics user — only reads
CREATE ROLE reporting LOGIN PASSWORD 'read_only_pass';
GRANT CONNECT ON DATABASE mydb TO reporting;
GRANT USAGE ON SCHEMA public TO reporting;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO reporting;
```

---

## 2. GRANT / REVOKE Reference

```sql
-- Grant specific privileges
GRANT SELECT ON users TO reporting;
GRANT SELECT, INSERT ON orders TO app_api;
GRANT ALL PRIVILEGES ON orders TO admin_role;

-- Revoke
REVOKE DELETE ON users FROM app_api;

-- Grant on future tables too (otherwise new tables need manual GRANT)
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO reporting;

-- Revoke all from public (secure default)
REVOKE ALL ON SCHEMA public FROM PUBLIC;
```

---

## 3. Row-Level Security (RLS)

RLS lets you write policies that filter rows based on who is querying. Even if a user has SELECT on the table, they only see rows that pass the policy.

```sql
-- Step 1: Enable RLS on the table
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;

-- Step 2: Create policies
-- Users can only see their own orders
CREATE POLICY user_sees_own_orders ON orders
    FOR SELECT
    USING (user_id = current_setting('app.current_user_id')::int);

-- Admins see everything (bypass RLS)
ALTER TABLE orders FORCE ROW LEVEL SECURITY;
-- (superusers bypass by default; use FORCE to apply to table owner too)

-- Admin policy
CREATE POLICY admin_sees_all ON orders
    FOR ALL
    TO admin_role
    USING (true);
```

### Set the session variable per-request (application side)

```python
# Django / SQLAlchemy — set before each request
await session.execute(
    text("SET LOCAL app.current_user_id = :uid"),
    {"uid": request.user.id}
)
# SET LOCAL scopes to the current transaction only — safe
```

### RLS Policy Types

```sql
-- SELECT policy
CREATE POLICY read_own ON documents FOR SELECT USING (owner_id = current_user_id());

-- INSERT policy (WITH CHECK — applies to new row)
CREATE POLICY insert_own ON documents FOR INSERT WITH CHECK (owner_id = current_user_id());

-- UPDATE policy (USING = which rows can be updated, WITH CHECK = what new values allowed)
CREATE POLICY update_own ON documents FOR UPDATE
    USING (owner_id = current_user_id())
    WITH CHECK (owner_id = current_user_id());  -- can't change owner_id to someone else

-- Combined policy
CREATE POLICY manage_own ON documents FOR ALL
    USING (owner_id = current_user_id())
    WITH CHECK (owner_id = current_user_id());
```

---

## 4. SQL Injection Prevention

### ❌ BAD — String interpolation (never do this)

```python
# VULNERABLE — user_input can be: "'; DROP TABLE users; --"
query = f"SELECT * FROM users WHERE email = '{user_input}'"
await session.execute(text(query))
```

### ✅ GOOD — Parameterized queries (always)

```python
# SQLAlchemy ORM — always parameterized automatically
user = await session.get(User, user_id)
users = await session.execute(select(User).where(User.email == email))

# SQLAlchemy raw SQL — use :param syntax
await session.execute(
    text("SELECT * FROM users WHERE email = :email"),
    {"email": email}
)

# psycopg3 — use %s placeholders
await conn.execute("SELECT * FROM users WHERE email = %s", (email,))

# ❌ WRONG even with text() — still vulnerable
await session.execute(text(f"SELECT * FROM users WHERE email = '{email}'"))
```

### Django ORM — safe by default

```python
# All ORM queries are parameterized
User.objects.filter(email=email)  # safe
User.objects.raw("SELECT * FROM users WHERE email = %s", [email])  # safe
User.objects.raw(f"SELECT * FROM users WHERE email = '{email}'")  # UNSAFE
```

---

## 5. SSL / TLS

```ini
# postgresql.conf
ssl = on
ssl_cert_file = '/etc/ssl/certs/server.crt'
ssl_key_file  = '/etc/ssl/private/server.key'
ssl_ca_file   = '/etc/ssl/certs/ca.crt'

# pg_hba.conf — require SSL for all connections
hostssl  all  all  0.0.0.0/0  scram-sha-256
```

```python
# SQLAlchemy — enforce SSL
engine = create_async_engine(
    "postgresql+asyncpg://user:pass@host/db",
    connect_args={"ssl": "require"}
)
```

---

## 6. Encryption

### Encryption at rest

- Use filesystem-level encryption: AWS RDS encrypts volumes with KMS by default
- pgcrypto extension for column-level encryption:

```sql
CREATE EXTENSION pgcrypto;

-- Encrypt on insert
INSERT INTO secrets (data) VALUES (pgp_sym_encrypt('my secret', 'passphrase'));

-- Decrypt on read
SELECT pgp_sym_decrypt(data, 'passphrase') FROM secrets WHERE id = 1;
```

### Encryption in transit

Always use SSL (see section 5). Never send credentials over plaintext connections.

### Hashing passwords (application level)

```python
# ❌ NEVER store plain text or MD5
# ✅ Use bcrypt / argon2 in the application layer
from passlib.context import CryptContext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

hashed = pwd_context.hash("user_password")
is_valid = pwd_context.verify("user_password", hashed)
```

---

## 7. Auditing with pg_audit

```sql
-- Install pgaudit extension
CREATE EXTENSION pgaudit;

-- postgresql.conf
pgaudit.log = 'write, ddl'  -- log all writes and DDL changes

-- Per-role auditing
SET pgaudit.log = 'read';  -- log all SELECT by this session
```

### Django / SQLAlchemy application-level audit log

```python
# Simpler: log every mutation in a middleware or ORM event
@event.listens_for(Session, "after_bulk_update")
def after_bulk_update(update_context):
    logger.info("BULK UPDATE: %s", update_context.statement)
```

---

## 8. Secrets Management

```python
# ❌ BAD — secrets in code or .env committed to git
DATABASE_URL = "postgresql://admin:password123@localhost/prod"

# ✅ GOOD — environment variables from a secrets manager
import os
DATABASE_URL = os.environ["DATABASE_URL"]  # injected by AWS Secrets Manager / Vault

# Django settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ['DB_NAME'],
        'USER': os.environ['DB_USER'],
        'PASSWORD': os.environ['DB_PASSWORD'],
        'HOST': os.environ['DB_HOST'],
    }
}
```

---

## 9. Security Checklist — Production

```
□ Application role has ONLY needed privileges (no superuser)
□ Each service has its own DB role (API, worker, reporting all separate)
□ RLS enabled on multi-tenant tables
□ All queries parameterized (no f-string SQL)
□ SSL enforced in pg_hba.conf (hostssl line)
□ Secrets in environment variables / secrets manager (not in code)
□ Passwords hashed with bcrypt/argon2 (not MD5, not SHA-256 plain)
□ pg_audit enabled for write + DDL logging
□ Public schema access revoked from PUBLIC role
□ DB not exposed to public internet (VPC / security groups)
□ Regular backups + restore tested
□ Database user passwords rotated periodically
```

---

## 10. Interview Questions

**Q: Least privilege kya hai? Application DB user ke liye kya permissions deni chahiye?**
Sirf wahi privileges jo app ko chahiye — CONNECT, USAGE on schema, SELECT/INSERT/UPDATE/DELETE on specific tables. Superuser kabhi nahi dena chahiye application user ko.

**Q: SQL injection kaise prevent karte ho?**
Hamesha parameterized queries use karo — ORM ya `text()` with `:param` syntax. Kabhi f-string se SQL mat banao.

**Q: RLS kya hai aur kab use karo?**
Row-Level Security — table pe policy define karo jo filter kare ki kaun sa row kaun dekh sakta hai. Multi-tenant apps mein use karo jahan ek table mein multiple tenants ka data ho.

**Q: Encryption at rest vs in transit?**
At rest — filesystem/disk encryption (AWS KMS, pgcrypto). In transit — SSL/TLS enforced via pg_hba.conf `hostssl`. Dono zaroori hain production mein.

**Q: Ek service ka DB compromised ho gaya — blast radius kaise limit karo?**
Least privilege: har service ka alag DB role. Ek service ka role compromise hone se sirf uski tables accessible hongi. Superuser role compromise = full database access.
