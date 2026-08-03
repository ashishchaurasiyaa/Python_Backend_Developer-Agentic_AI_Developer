# Databases — Hands-On Lab
**DevOps Track · Phase 15 Practical**

## Prerequisites

Everything in this lab runs locally with Docker — no cloud spend needed.

- Docker + Docker Compose installed (`docker --version`, `docker compose version`)
- `psql` and `mysql` CLI clients on your host (or exec into the containers — both work; commands below assume host CLI clients where convenient, container `exec` where it matters for replication)
- `mongosh` for the MongoDB sections (or `docker exec` into the mongo container)
- `redis-cli` for the Redis sections (or `docker exec` into the redis container)
- Basic familiarity with `docker compose up -d`, `docker exec -it <container> bash`
- Free disk space: these labs create/destroy small volumes repeatedly — nothing exceeds a few hundred MB

If you don't want to install client tools on your host, every command below also works prefixed with `docker exec -it <container_name> <command>` — the lesson files use bare commands, so this lab does too, but note where you'd substitute the exec form.

---

## Lab 1: Stand Up MySQL + Postgres, Take Logical Backups, Restore

**Objective:** Get comfortable with the basic backup/restore cycle for both engines — the thing you'll do constantly as an ops person, and the first thing anyone asks about in an interview.

**Task:**
1. Write a `docker-compose.yml` that starts a MySQL 8 container and a Postgres 16 container, each with a named volume, exposed on `3306` and `5432`.
2. Create a database `shop` in each engine. In MySQL create a table `orders(id INT PRIMARY KEY, customer VARCHAR(50), amount DECIMAL(10,2))` and insert 5 rows. Do the same in Postgres.
3. Take a logical backup of the MySQL `shop` database using `mysqldump` with `--single-transaction`.
4. Take a logical backup of the Postgres `shop` database using `pg_dump` in custom format (`-Fc`).
5. Drop both databases entirely (`DROP DATABASE shop;`).
6. Restore both from your backups and verify the 5 rows are back with a `SELECT COUNT(*)`.

<details>
<summary>Solution / walkthrough</summary>

```yaml
# docker-compose.yml
services:
  mysql:
    image: mysql:8
    environment:
      MYSQL_ROOT_PASSWORD: rootpass
      MYSQL_DATABASE: shop
    ports: ["3306:3306"]
    volumes: ["mysql_data:/var/lib/mysql"]
  postgres:
    image: postgres:16
    environment:
      POSTGRES_PASSWORD: rootpass
      POSTGRES_DB: shop
    ports: ["5432:5432"]
    volumes: ["pg_data:/var/lib/postgresql/data"]
volumes:
  mysql_data:
  pg_data:
```

```bash
docker compose up -d
```

```sql
-- MySQL: docker exec -it <mysql_container> mysql -uroot -prootpass shop
CREATE TABLE orders (id INT PRIMARY KEY, customer VARCHAR(50), amount DECIMAL(10,2));
INSERT INTO orders VALUES (1,'a',10.00),(2,'b',20.00),(3,'c',30.00),(4,'d',40.00),(5,'e',50.00);
```

```sql
-- Postgres: docker exec -it <pg_container> psql -U postgres shop
CREATE TABLE orders (id INT PRIMARY KEY, customer VARCHAR(50), amount DECIMAL(10,2));
INSERT INTO orders VALUES (1,'a',10.00),(2,'b',20.00),(3,'c',30.00),(4,'d',40.00),(5,'e',50.00);
```

```bash
# Logical backups — --single-transaction avoids locking the whole DB during backup on InnoDB
mysqldump -h 127.0.0.1 -u root -prootpass --single-transaction shop > shop_mysql.sql

# -Fc = custom format, compressed, supports selective restore and parallel restore
pg_dump -h 127.0.0.1 -U postgres -Fc shop > shop_pg.dump
```

```sql
-- Drop and prove data is gone
DROP DATABASE shop;  -- run in both mysql and psql (recreate empty shop DB after for pg, since pg_restore needs a target db)
```

```bash
# Restore MySQL — recreate the DB first, mysqldump output is plain SQL
mysql -h 127.0.0.1 -u root -prootpass -e "CREATE DATABASE shop;"
mysql -h 127.0.0.1 -u root -prootpass shop < shop_mysql.sql

# Restore Postgres — custom format needs pg_restore, not psql
psql -h 127.0.0.1 -U postgres -c "CREATE DATABASE shop;"
pg_restore -h 127.0.0.1 -U postgres -d shop shop_pg.dump

# Verify
mysql -h 127.0.0.1 -u root -prootpass shop -e "SELECT COUNT(*) FROM orders;"
psql -h 127.0.0.1 -U postgres shop -c "SELECT COUNT(*) FROM orders;"
```

Why this matters: `mysqldump`/`pg_dump` are the tools you reach for first in any incident that needs "restore this one table/database," and knowing the exact restore command cold (not "I'd look it up") is the difference in an on-call situation at 3am.
</details>

---

## Lab 2: Postgres Streaming Replication — Build a Primary + Replica Locally

**Objective:** Set up real streaming replication between two Postgres containers and observe replication lag, per the mechanics in `01_sql_mysql_postgresql.md`.

**Task:**
1. Start a "primary" Postgres container with `wal_level = replica` and `max_wal_senders = 5` configured, plus a replication user.
2. Take a `pg_basebackup` of the primary into a new data directory for the replica.
3. Start a second Postgres container using that base backup as its data directory, configured to stream from the primary (`primary_conninfo`, `standby.signal`).
4. Confirm the replica is receiving WAL: query `pg_stat_replication` on the primary and `pg_last_xact_replay_timestamp()` on the replica.
5. Insert a row on the primary, and confirm it appears on the replica within a second or two.
6. Deliberately stop the primary container and measure replication lag right before you do — what's the most recent value `pg_wal_lsn_diff` reported?

<details>
<summary>Solution / walkthrough</summary>

```bash
# 1. Primary container with a distinct data dir/volume
docker run -d --name pg-primary \
  -e POSTGRES_PASSWORD=rootpass \
  -p 5433:5432 \
  postgres:16 \
  -c wal_level=replica -c max_wal_senders=5 -c hot_standby=on
```

```sql
-- create replication user (docker exec -it pg-primary psql -U postgres)
CREATE ROLE replicator WITH REPLICATION LOGIN PASSWORD 'replpass';
```

```conf
# pg_hba.conf inside pg-primary (append, then reload)
host replication replicator 0.0.0.0/0 md5
```

```bash
docker exec -it pg-primary psql -U postgres -c "SELECT pg_reload_conf();"

# 2. Base backup — this becomes the replica's starting data directory
docker run --rm --link pg-primary -v replica_data:/replica_out postgres:16 \
  pg_basebackup -h pg-primary -D /replica_out -U replicator -Fp -Xs -P -R
# -R writes standby.signal + primary_conninfo automatically — this is the key flag
# that turns a plain base backup into a ready-to-start replica

# 3. Start the replica container pointed at that volume
docker run -d --name pg-replica \
  -v replica_data:/var/lib/postgresql/data \
  -p 5434:5432 \
  postgres:16
```

```sql
-- 4. On primary
SELECT client_addr, state, sent_lsn, replay_lsn,
       pg_wal_lsn_diff(sent_lsn, replay_lsn) AS lag_bytes
FROM pg_stat_replication;

-- On replica
SELECT now() - pg_last_xact_replay_timestamp() AS replication_lag;
```

```sql
-- 5. Insert on primary, read on replica
-- primary:
CREATE TABLE t (id serial primary key, val text);
INSERT INTO t (val) VALUES ('hello-from-primary');
-- replica (read-only, will error on write attempts — that's expected, standbys reject writes):
SELECT * FROM t;
```

```bash
# 6. Check lag, then kill primary
docker exec pg-primary psql -U postgres -c \
  "SELECT pg_wal_lsn_diff(sent_lsn, replay_lsn) AS lag_bytes FROM pg_stat_replication;"
docker stop pg-primary
```

Why this matters: this is the exact mechanic behind every managed "Multi-AZ" database offering. Doing it by hand once means you actually understand what `pg_basebackup -R` does instead of treating replication as a checkbox in an RDS console.
</details>

---

## Lab 3: Production-Style — PITR After a Bad `DELETE`, and a Manual Failover

**Objective:** Simulate the real incident described in the lesson file — "a bad migration or `DELETE FROM orders` without a WHERE clause runs at 14:32" — and recover using Point-in-Time Recovery. Then simulate a primary failure and promote the replica.

**Task:**

**Part A — PITR:**
1. On a fresh Postgres container, enable WAL archiving (`archive_mode = on`, `archive_command` writing to a local `/archive` directory).
2. Take a base backup.
3. Create a table, insert 10 rows, note the exact timestamp (`SELECT now();`).
4. Wait a few seconds, then run a "bad" `DELETE FROM orders;` (no WHERE clause) — simulate the incident.
5. Stop Postgres. Restore the base backup into a new data directory, set `recovery_target_time` to the timestamp from step 3 (a couple seconds after your inserts, a couple seconds before the DELETE), create `recovery.signal`, and start Postgres.
6. Confirm the 10 rows are back and the DELETE never happened in this restored copy.

**Part B — Manual failover:**
1. Using the primary+replica pair from Lab 2 (or rebuild it), stop the primary container to simulate a crash.
2. On the replica, run `SELECT pg_promote();` to promote it to a standalone writable primary.
3. Confirm you can now write to what was the replica.
4. Write down what data (if any) was lost — compare the last insert you made before killing the primary against what the promoted replica has, and explain why (async replication lag).

<details>
<summary>Solution / walkthrough</summary>

**Part A:**

```bash
docker run -d --name pg-pitr -e POSTGRES_PASSWORD=rootpass -p 5435:5432 \
  -v pitr_archive:/archive \
  postgres:16 \
  -c wal_level=replica -c archive_mode=on -c "archive_command=cp %p /archive/%f"
```

```bash
# base backup
docker exec pg-pitr pg_basebackup -D /tmp/basebackup -Fp -Xs -U postgres
```

```sql
CREATE TABLE orders (id serial primary key, customer text);
INSERT INTO orders (customer) SELECT 'cust-' || g FROM generate_series(1,10) g;
SELECT now();   -- note this timestamp, e.g. 2026-07-25 10:15:32.123456+00
```

```sql
-- wait a few seconds, then the "incident"
DELETE FROM orders;   -- no WHERE clause, all 10 rows gone
```

```bash
docker stop pg-pitr
# copy /tmp/basebackup out to host, start a NEW container using it as the data dir
```

```ini
# postgresql.conf in the restored data dir
restore_command = 'cp /archive/%f %p'
recovery_target_time = '2026-07-25 10:15:32.123456+00'
```

```bash
touch /path/to/restored/data/recovery.signal
# start postgres pointed at the restored data dir — it replays WAL up to
# recovery_target_time, which is AFTER the inserts but BEFORE the delete,
# then pauses in recovery (or promotes, depending on recovery_target_action)
```

```sql
SELECT COUNT(*) FROM orders;  -- should be 10 — the delete never gets replayed
```

**Part B:**

```bash
docker stop pg-primary   # simulate crash
```

```sql
-- on pg-replica
SELECT pg_promote();
-- after promotion, standby.signal is removed and the node accepts writes
INSERT INTO t (val) VALUES ('post-failover-write');   -- now succeeds
```

Data-loss check: any insert on the primary that hadn't yet shipped its WAL to the replica before the crash is gone — this is exactly the async-replication risk called out in the lesson file. If this were a real incident with `synchronous_commit = remote_apply` and a `synchronous_standby_names` set, that specific write would have been guaranteed present on the replica before the primary ever confirmed it to the client, at the cost of every write being slower.

Why this matters: knowing PITR and manual promotion cold — not "there's probably a way to do this" — is the difference between a data-loss incident lasting 10 minutes vs. losing a day of data because nobody had ever tested the restore path.
</details>

---

## Lab 4: Troubleshooting — Diagnose a Connection Exhaustion Incident

**Objective:** Reproduce the "50 pods × 10-20 idle connections = DB falls over" scenario from the lesson, then fix it with PgBouncer.

**Task:**
1. Start a Postgres container with `max_connections = 20` (deliberately low, to make the scenario reproducible fast).
2. Write a tiny Python script (or use `pgbench -c 30 -T 30`) that opens 30 concurrent connections and holds them open for 10+ seconds each.
3. Observe the failure: what error does Postgres return once connections are exhausted? Check `SELECT count(*) FROM pg_stat_activity;` right before it happens.
4. Stand up a PgBouncer container in front of Postgres with `pool_mode = transaction` and `default_pool_size = 10`.
5. Point your 30-connection script at PgBouncer's port instead, and confirm it no longer exhausts Postgres's `max_connections` — check `SHOW POOLS;` on the PgBouncer admin console while the script runs.

<details>
<summary>Solution / walkthrough</summary>

```bash
docker run -d --name pg-lowconn -e POSTGRES_PASSWORD=rootpass -p 5436:5432 \
  postgres:16 -c max_connections=20
```

```bash
# reproduce exhaustion directly
pgbench -h 127.0.0.1 -p 5436 -U postgres -c 30 -j 4 -T 15 postgres
# expect: "FATAL: sorry, too many clients already" errors partway through
```

```sql
-- run this in a separate psql session WHILE pgbench is running
SELECT count(*) FROM pg_stat_activity;   -- climbs toward 20, then new conns fail
```

```ini
# pgbouncer.ini
[databases]
postgres = host=pg-lowconn port=5432 dbname=postgres

[pgbouncer]
listen_port = 6432
listen_addr = *
auth_type = trust
pool_mode = transaction
default_pool_size = 10
max_client_conn = 200
```

```bash
docker run -d --name pgbouncer --link pg-lowconn \
  -v $(pwd)/pgbouncer.ini:/etc/pgbouncer/pgbouncer.ini \
  -p 6432:6432 edoburu/pgbouncer

# now point pgbench at PgBouncer's port instead
pgbench -h 127.0.0.1 -p 6432 -U postgres -c 30 -j 4 -T 15 postgres
# succeeds — 30 client connections multiplexed onto 10 real DB connections
```

```bash
psql -h 127.0.0.1 -p 6432 pgbouncer -c "SHOW POOLS;"
# cl_active climbs toward 30, sv_active stays capped near 10 — this is the
# multiplexing in action, and it's the number you'd screenshot in an incident writeup
```

Why this matters: "add a connection pooler" is a common interview answer, but actually watching `max_connections` errors happen and then watching PgBouncer absorb them is what makes the concept stick — and it's exactly what you'd do on a real incident bridge.
</details>

---

## Self-Check Checklist

- [ ] Can you explain, without looking it up, the difference between async, semi-sync, and synchronous (`remote_apply`) replication and when you'd choose each?
- [ ] Can you write a `pg_dump`/`pg_restore` command from memory, including the flag for custom format?
- [ ] Can you set up Postgres streaming replication from scratch (primary config, `pg_basebackup -R`, standby.signal) without referencing the lesson file?
- [ ] Can you explain what `pg_promote()` does and what data is at risk when you use it after an async-replicated primary crash?
- [ ] Can you write a PITR recovery config (`recovery_target_time`, `recovery.signal`) and explain why it needs a base backup PLUS archived WAL, not just one or the other?
- [ ] Can you explain why `pool_mode = transaction` in PgBouncer breaks session-scoped features like prepared statements and `LISTEN/NOTIFY`?
- [ ] Given `SHOW REPLICA STATUS\G` output on MySQL, can you identify which field tells you replication lag and which two tell you if replication threads are actually running?
- [ ] Can you explain the tradeoff between logical (`mysqldump`/`pg_dump`) and physical (XtraBackup/`pg_basebackup`) backups for a 500GB database, unprompted?
- [ ] Can you diagnose "app can't connect to DB" as a connection-exhaustion problem from `pg_stat_activity` output alone, and name the fix?
- [ ] Can you state the two ops metrics the lesson calls out as turning "degraded" into "down" fastest, and why they're dangerous specifically because they're silent?
