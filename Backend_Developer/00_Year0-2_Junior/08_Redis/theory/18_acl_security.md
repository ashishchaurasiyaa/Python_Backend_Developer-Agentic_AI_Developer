# Redis ACL & Security

## Why It Matters (Senior 5 YOE Context)

`01_basics_installation_cli.md` and `02_pipeline_connection_pool.md`
mention `requirepass`/`AUTH` in passing — a single shared password on the
connection. That's the ENTIRE security model most people ship with, and
it's also the exact reason "Redis ransomware" became a recurring headline:
thousands of internet-exposed Redis instances with no password at all on
the `default` user got scanned, wiped, and held for ransom (`FLUSHALL`
followed by a ransom note key). This isn't a hypothetical — it's one of
the most common real-world Redis compromise patterns, and it's a direct
consequence of treating `requirepass` as "done" instead of asking who
should be able to run `FLUSHALL`/`CONFIG`/`SHUTDOWN` at all.

Redis 6 introduced ACLs specifically to close this gap: instead of one
password granting full access to everything, you get per-user identities
with fine-grained permissions — which commands, which key patterns. This
is the difference between "the app has the Redis password" and "the
reporting service can only read `report:*` keys and nothing else."

Senior interview: "Your Redis instance got wiped by ransomware — what
went wrong and how do you prevent it next time?" → `default` user had no
password (or a weak one) and was reachable from the internet with full
command access including `FLUSHALL`/`CONFIG SET`/`DEBUG`. Fix: ACLs with
least-privilege per-service users, `default` user disabled or heavily
restricted, TLS on the wire, and the instance not directly internet-facing
in the first place (bind to private network / security group rules).

---

## Core Concepts

### Legacy AUTH — `requirepass` (pre-6, still works in 6+)

```conf
requirepass yourStrongPassword
```

```bash
AUTH yourStrongPassword
```

One password, full access, shared by every client. Limitations:

- **No per-user permissions** — anyone with the password can run
  `FLUSHALL`, `CONFIG SET`, `SHUTDOWN`, read every key.
- **One password for everyone** — a reporting dashboard and the payment
  service authenticate identically; a leak from the least-trusted
  consumer compromises everything.
- **Hard to rotate/audit** — rotating means updating every client
  simultaneously (no gradual rollout), and there's no way to tell which
  service issued which command — `CLIENT LIST`/logs show the same
  identity for all.

Under the hood in Redis 6+, `requirepass` is just sugar for setting the
**`default` user's** password — it's not a separate legacy mechanism,
it's ACLs with one user.

### ACL (Redis 6+) — per-user, fine-grained

```bash
ACL SETUSER myuser on >mypassword ~report:* +@read -@dangerous
```

Reading the syntax left to right:

| Piece | Meaning |
|---|---|
| `SETUSER myuser` | Create the user if new, or edit if exists |
| `on` / `off` | Enable/disable login for this user |
| `>password` | Add this password (plaintext here, SHA-256 hashed internally) |
| `nopass` | No password required (dangerous — combine only with tight restrictions, or never use in prod) |
| `~pattern` | Key pattern this user may touch — `~report:*` = only keys starting `report:`, `~*` = all keys |
| `%RW~pattern` / `%R~pattern` / `%W~pattern` | Redis 7+: separate read vs write key patterns |
| `+@category` | Allow a whole command category, e.g. `+@read` |
| `-@category` | Deny a whole command category, e.g. `-@dangerous` |
| `+command` / `-command` | Allow/deny one specific command, e.g. `+get -flushall` |
| `resetkeys` | Clear previously granted key patterns before adding new ones |
| `resetpass` | Clear previously set passwords |

Order matters left-to-right — later rules override earlier ones for the
same command/category, which is how `+@read -@dangerous` combos with a
specific `+flushdb` exception if you ever needed one.

### Built-in command categories

Redis groups every command into categories so you don't have to allow/deny
commands one at a time:

```bash
ACL CAT                      # list all categories
ACL CAT read                 # list every command inside @read
```

Common categories you'll actually use:

| Category | Contains |
|---|---|
| `@read` | `GET`, `HGET`, `SCAN`, `MGET`, ... (non-mutating) |
| `@write` | `SET`, `DEL`, `HSET`, `EXPIRE`, ... (mutating) |
| `@admin` | `CONFIG`, `SHUTDOWN`, `DEBUG`, `MONITOR`, ... |
| `@dangerous` | `FLUSHALL`, `FLUSHDB`, `KEYS`, `SHUTDOWN`, `CONFIG`, `CLUSTER`, ... (superset of things that can hurt you) |
| `@keyspace` | Commands that touch key metadata: `EXPIRE`, `TTL`, `TYPE`, `DEL`, ... |
| `@connection` | `AUTH`, `PING`, `HELLO`, `SELECT`, ... |
| `@pubsub` | `PUBLISH`, `SUBSCRIBE`, `PSUBSCRIBE`, ... |
| `@scripting` | `EVAL`, `EVALSHA`, `FUNCTION`, ... |

A typical safe application user starts from `+@read +@write -@admin
-@dangerous` and then punches specific holes back open only if truly
needed (e.g. `+flushdb` for a test-only user, never in prod).

### The `default` user

Every fresh Redis install has an implicit `default` user. Historically
(and still today unless you touch it) that user is `on`, `nopass`, `~*`,
`+@all` — enabled, no password, every key, every command. If the instance
is reachable from the internet (or even just a flat internal network) with
that default untouched, anyone who can open a TCP connection to port 6379
has full control — this is precisely the ransomware pattern from Why It
Matters. Two ways to fix it:

```bash
# Option A: give default a strong password (minimum bar)
ACL SETUSER default on >aStrongPassword ~* +@all

# Option B: disable default entirely, force everyone through named users
ACL SETUSER default off
```

Option B is the stronger posture for production — no fallback shared
identity at all, every client must authenticate as a specific named user
with scoped permissions.

### Inspecting and managing ACLs

```bash
ACL WHOAMI                   # which user is THIS connection authenticated as
ACL LIST                     # every user, as SETUSER-reproducible rule strings
ACL GETUSER myuser           # structured detail: flags, passwords (hashed), keys, commands
ACL USERS                    # just the usernames
ACL DELUSER myuser           # remove a user
ACL CAT                      # list command categories
ACL CAT read                 # commands inside a category
```

### Persisting ACLs — config-only vs `aclfile`

ACL changes made via `ACL SETUSER` at runtime are **in-memory only** by
default — a `redis-server` restart reverts to whatever `users.acl`/config
had at startup, silently discarding every ACL change you made live. Two
ways to persist:

```bash
# 1. Save current in-memory ACL state to the configured aclfile
ACL SAVE

# 2. redis.conf must point at an aclfile for SAVE/load to work at all
aclfile /etc/redis/users.acl
```

Without `aclfile` configured, `ACL SAVE` errors out — you're limited to
defining users directly in `redis.conf` via `user` directives (loaded only
at startup, edited by hand, no live `ACL SAVE`).

### Least-privilege application design

Give every microservice/role its own ACL user scoped to exactly what it
needs — the point is that a compromised service (leaked credentials, RCE,
SSRF into internal network) can only damage its own slice of the keyspace:

```bash
# Reporting/BI service — read-only, only report:* keys
ACL SETUSER reporting_svc on >pw1 ~report:* +@read -@dangerous

# Order-write service — read+write, only orders:* keys
ACL SETUSER order_svc on >pw2 ~orders:* +@read +@write -@admin -@dangerous

# Cache-invalidation admin tool — needs FLUSHDB but ONLY on a sandbox DB pattern
ACL SETUSER cache_admin on >pw3 ~cache:* +@read +@write +flushdb -@admin
```

If `reporting_svc`'s password leaks, the blast radius is "can read
`report:*` keys" — not "can `FLUSHALL` the entire production dataset."

### TLS — encrypting the wire

ACLs and passwords protect WHO can run commands; TLS protects the wire
itself so credentials and data aren't sniffable in transit — matters for
any network-exposed Redis (cross-AZ, cross-region, any hop outside a
single trusted host/VPC), skippable only on a fully trusted, single-host
loopback setup.

```conf
tls-port 6380
port 0                          # optionally disable plaintext port entirely
tls-cert-file /etc/redis/redis.crt
tls-key-file /etc/redis/redis.key
tls-ca-cert-file /etc/redis/ca.crt
```

```python
import redis

r = redis.Redis(
    host="redis.internal",
    port=6380,
    ssl=True,
    ssl_ca_certs="/etc/redis/ca.crt",
    username="order_svc",
    password="pw2",
    decode_responses=True,
)
```

---

## How It Works Internally

- Each ACL user is a set of rules stored in Redis's in-memory ACL table:
  enabled flag, password hash(es) (SHA-256, never plaintext at rest),
  selectors (key patterns + allowed commands/categories). A connection
  authenticates via `AUTH username password` (or `HELLO ... AUTH`), which
  looks up the user, verifies the password hash, and attaches that user's
  permission set to the connection for its lifetime.
- Every command Redis executes on that connection is checked against the
  user's command permissions (walked in rule-definition order — later
  rules win) AND, for commands that take keys, against the user's key
  patterns. A `GET orders:1` on a user scoped to `~report:*` fails at the
  key-pattern check even if `@read`/`GET` itself is allowed.
- `+@category`/`-@category` are resolved against Redis's static internal
  command-to-category table (the same table `ACL CAT <category>` prints) —
  categories aren't dynamic/computed, they're a fixed classification
  shipped with each Redis version, so `ACL CAT` is the ground truth for
  "what's actually in `@dangerous`" on your exact version.
- `ACL SAVE` serializes the current in-memory user table to the configured
  `aclfile` in the same `user ...` directive syntax you'd hand-write in
  `redis.conf`. On startup, if `aclfile` is set, Redis loads users from
  it instead of (not in addition to) `user` lines in `redis.conf` — mixing
  both is a startup error.
- ACL changes are NOT automatically replicated to replicas as ACL state —
  they propagate as the `ACL SETUSER`/`ACL DELUSER` commands themselves
  through the normal replication stream, so a replica catches up the same
  way it catches up on data writes.

---

## Common Pitfalls

### 1. `default` user with no password on an internet-exposed port

The single most common real-world Redis compromise vector — `nopass`,
`~*`, `+@all` default user reachable from 0.0.0.0. Scanners find it in
minutes. Fix: `ACL SETUSER default off` (or at minimum a strong password)
AND don't expose port 6379/6380 to the internet in the first place —
security group / firewall rules are the first line of defense, ACLs are
defense-in-depth, not a substitute for network isolation.

### 2. `~*` granted too broadly

```bash
# BAD — "just get it working" scoping that never gets tightened
ACL SETUSER order_svc on >pw ~* +@read +@write -@admin
```

Every service defaults to `~*` during development and it quietly survives
into production. Scope key patterns to the actual prefix the service
owns from day one — retrofitting least-privilege after an incident is
much more painful than starting with it.

### 3. Forgetting `ACL SAVE`/`aclfile`

```bash
ACL SETUSER order_svc on >pw ~orders:* +@read +@write
# ... works fine in prod for weeks ...
# redis-server restarts (deploy, crash, maintenance)
# order_svc no longer exists — AUTH fails — service outage
```

If ACL changes matter beyond the current process lifetime, either
configure `aclfile` and call `ACL SAVE` after every change, or define
users as `user` directives directly in `redis.conf` so they're re-created
identically on every startup.

### 4. Confusing `requirepass` with a full ACL setup

Setting `requirepass` feels like "I added security" but it's exactly one
user (`default`) with exactly one capability tier: all-or-nothing. Teams
sometimes stop there and assume they have per-service isolation because
"there's a password" — there isn't any isolation until you create named
users with scoped `~pattern`/`+@category` rules.

### 5. Denying a category but forgetting a specific command escape hatch

```bash
ACL SETUSER svc on >pw ~orders:* +@read +@write -@dangerous +flushdb
```

`-@dangerous` denies `FLUSHDB` (it's in `@dangerous`), but the explicit
`+flushdb` after it re-allows it because later rules win. Read `ACL
GETUSER svc` after composing rules like this to confirm the net effect
rather than assuming the category deny "wins."

---

## Interview Q&A

**Q: `requirepass` vs full ACL setup — what's actually different?**
A: `requirepass` sets a single password on the implicit `default` user,
who by default has access to every key and every command — it's an
all-or-nothing gate. ACLs (Redis 6+) let you create named users each with
their own password, key-pattern restrictions (`~pattern`), and
command/category allow-lists (`+@read`, `-@dangerous`, etc.) — so
different services can have genuinely different, minimal permissions
instead of sharing one all-powerful credential. Under the hood
`requirepass` is implemented as ACL rules on `default`, not a separate
mechanism.

**Q: Why is the `default` user specifically dangerous, and what's the fix?**
A: It's created automatically, enabled by default, with `nopass` and
`+@all ~*` unless configured otherwise — so an internet-exposed instance
with an untouched `default` user gives full read/write/admin access
(including `FLUSHALL`, `CONFIG SET`, `SHUTDOWN`) to anyone who can open a
TCP connection. This exact pattern drove real-world Redis ransomware
incidents. Fix: either `ACL SETUSER default off` and force all clients
through named least-privilege users, or at minimum give `default` a
strong password — plus don't expose the port to the internet regardless.

**Q: How would you design ACL users for a multi-service architecture?**
A: One ACL user per service/role, scoped to only the key prefixes and
command categories that service needs — e.g. a reporting service gets
`+@read ~report:*`, an order-write service gets `+@read +@write
~orders:*`, both explicitly `-@admin -@dangerous`. That way a compromised
or buggy service can only touch its own slice of the keyspace, not
`FLUSHALL` or read another service's data. Combine with TLS if traffic
crosses untrusted network boundaries, and persist the ACL config via
`aclfile` + `ACL SAVE` so it survives restarts.

**Q: You ran `ACL SETUSER` a bunch of times in production and then Redis
restarted — the new users are gone. What happened?**
A: `ACL SETUSER`/`ACL DELUSER` mutate Redis's in-memory ACL table only.
Unless `aclfile` is configured in `redis.conf` AND you explicitly ran
`ACL SAVE` after making changes (or the users were defined as `user`
lines in `redis.conf` directly), none of it persists across a restart —
Redis reloads whatever the config/aclfile said at startup and the
in-memory changes are gone.

**Q: What's the difference between `+@read` and `+get`?**
A: `+@read` allows the entire `@read` command category — every command
Redis classifies as non-mutating (`GET`, `MGET`, `HGET`, `SCAN`, `TTL`,
etc. — check the exact set with `ACL CAT read` on your version).
`+get` allows only the single `GET` command. Category grants are coarser
and easier to maintain as Redis adds commands; specific command grants
are tighter but need updating if the app starts using a new read command
that wasn't explicitly allowed.

---

## Real-World Use Cases

### 1. Multi-tenant SaaS — scoped user per backend service

```bash
ACL SETUSER billing_svc   on >pw1 ~billing:*   +@read +@write -@admin -@dangerous
ACL SETUSER notif_svc     on >pw2 ~notif:*     +@read +@write -@admin -@dangerous
ACL SETUSER reporting_svc on >pw3 ~*           +@read -@dangerous
ACL SETUSER default off
```

Each backend service authenticates as its own user with its own
credential and its own key namespace. A leaked `notif_svc` password can't
touch `billing:*` keys. `default` is disabled entirely so there's no
fallback identity a misconfigured client could accidentally fall back to.

### 2. Read-only ACL user for a BI/reporting tool

```bash
ACL SETUSER bi_tool on >pw ~* +@read -@dangerous
```

A dashboard/analytics tool (Grafana, a custom BI service, an ad-hoc
`redis-cli` session for an on-call engineer investigating an incident)
gets visibility into the whole keyspace for debugging/reporting but
cannot `SET`, `DEL`, `FLUSHALL`, or `CONFIG SET` anything — a compromised
or buggy dashboard integration is read-only by construction, not by
convention.

---

## References

- [Redis ACL](https://redis.io/docs/management/security/acl/)
- [ACL command reference](https://redis.io/commands/?group=acl)
- [Redis Security](https://redis.io/docs/management/security/)
- [TLS support](https://redis.io/docs/management/security/encryption/)
- redis-py `Redis(username=..., password=..., ssl=...)` connection docs
- Related: `01_basics_installation_cli.md` (`requirepass` config basics),
  `02_pipeline_connection_pool.md` (`AUTH` in the connection lifecycle),
  `09_persistence_memory.md` (persisting config generally — same
  in-memory-vs-file distinction applies to ACLs)
