# PostgreSQL Backup + Disaster Recovery

> **Interview angle:** "Database delete ho gaya — recover karne mein kitna time?"
> "Last backup kab tha? Customer ne 6 hours pehle data add kiya — wo bach jayega?"

---

## 1. Two Key Numbers: RPO & RTO

| Metric | Definition | Typical |
|---|---|---|
| **RPO** (Recovery Point Objective) | Max data loss tolerable | Minutes to hours |
| **RTO** (Recovery Time Objective) | Max downtime tolerable | Minutes to hours |

**Examples:**
- Finance app: RPO=0 (no loss), RTO=5min
- SaaS app: RPO=1hr, RTO=30min
- Blog: RPO=24hr, RTO=4hr

Backup strategy depends on these.

---

## 2. Backup Types

### Logical Backups (SQL dump)
- `pg_dump` — exports as SQL or custom format
- Per-table, per-DB, or cluster-wide
- Slower to restore (replays SQL)
- Cross-version compatible

### Physical Backups (file-level)
- `pg_basebackup` — copies data files directly
- Faster restore (just copy back)
- Same major version required
- Includes WAL for PITR

### Continuous Archiving (WAL archiving)
- Stream every WAL file to S3/storage
- Combined with base backup → Point-In-Time Recovery
- RPO < 1 minute

---

## 3. pg_dump (Logical)

```bash
# Plain SQL dump (huge text file)
pg_dump -h localhost -U postgres mydb > mydb.sql

# Custom format (compressed, faster restore)
pg_dump -Fc -h localhost mydb > mydb.dump

# Directory format (parallel)
pg_dump -Fd -j 4 -f /backup/mydb mydb

# Specific table
pg_dump -t users mydb > users.sql

# Only schema (no data)
pg_dump --schema-only mydb > schema.sql

# Only data (no schema)
pg_dump --data-only mydb > data.sql

# Restore
pg_restore -d mydb_new mydb.dump      # custom format
psql mydb_new < mydb.sql              # plain SQL
```

### Parallel pg_dump
```bash
pg_dump -Fd -j 8 -f /backup/mydb mydb     # 8 parallel jobs
pg_restore -j 8 -d new_db /backup/mydb    # parallel restore
```

### Pros
- Human-readable
- Cross-version restore (15 → 16)
- Easy partial restore (one table)

### Cons
- Slow for big DBs (TB takes hours)
- Locks rows during dump (uses snapshots actually, OK)
- Can't do PITR

---

## 4. pg_basebackup (Physical)

```bash
# Full base backup
pg_basebackup -h localhost -U replicator \
    -D /backup/base/$(date +%Y-%m-%d) \
    -Ft \                # tar format
    -P \                 # progress
    -z \                 # compress
    -X stream \          # include WAL during backup
    -c fast              # fast checkpoint

# Restore: copy back, configure recovery
tar xf base.tar -C /var/lib/postgresql/data
# Edit postgresql.conf, start
```

### Pros
- Fast (just file copy)
- Foundation for PITR
- Includes everything: data, WAL, configs

### Cons
- Same major version only
- Full DB only (no per-table)
- Larger files (no SQL compression)

---

## 5. Point-In-Time Recovery (PITR)

**Goal:** "Restore to exactly 2024-05-15 14:30:00".

### Setup
1. Enable WAL archiving on primary
2. Base backup periodically
3. Continuously stream WAL files

### `postgresql.conf`
```ini
wal_level = replica            # or logical
archive_mode = on
archive_command = 'aws s3 cp %p s3://my-bucket/wal/%f'
archive_timeout = 60           # force WAL switch every 60s if no activity
```

### Tools that automate this
- **WAL-G** (most popular) — designed for cloud
- **Barman** — full-featured, on-prem
- **pgBackRest** — supports parallel, compression, encryption

### Restore Procedure
1. Stop Postgres
2. Restore latest base backup
3. Configure `recovery.signal` + `restore_command`
4. Set `recovery_target_time = '2024-05-15 14:30:00 IST'`
5. Start Postgres → it replays WAL up to target time
6. Promote to read-write

```ini
# postgresql.conf (recovery)
restore_command = 'aws s3 cp s3://my-bucket/wal/%f %p'
recovery_target_time = '2024-05-15 14:30:00 IST'
recovery_target_action = 'promote'
```

---

## 6. WAL-G — Modern Backup Tool

```bash
# Install
go install github.com/wal-g/wal-g/cmd/pg@latest

# Configure
export WALG_S3_PREFIX=s3://my-bucket/db-backups
export AWS_REGION=us-east-1

# Take base backup
wal-g backup-push /var/lib/postgresql/data

# WAL archiving (in postgresql.conf)
archive_command = 'wal-g wal-push %p'

# List backups
wal-g backup-list

# Restore latest
wal-g backup-fetch /var/lib/postgresql/data LATEST

# Restore specific time
echo "restore_command = 'wal-g wal-fetch %f %p'" > recovery.conf
echo "recovery_target_time = '2024-05-15 14:30:00'" >> recovery.conf
```

---

## 7. Backup Schedule (Real Production)

```
00:00 daily   → Full pg_basebackup (compressed, encrypted)
00:00 weekly  → pg_dump for cross-version safety
24/7          → WAL archiving every 60s

Retention:
- Hourly:  24 hours
- Daily:   30 days
- Weekly:  3 months
- Monthly: 1 year
- Yearly:  7 years (compliance)
```

### Tiered storage (cost optimization)
- Recent: S3 Standard
- 30+ days: S3 Standard-IA
- 1+ year: S3 Glacier

---

## 8. Cloud-Managed Backups

### AWS RDS
- Automated daily snapshots (free, configurable retention 0-35 days)
- Manual snapshots (persist beyond retention)
- Multi-AZ replication (HA, not really backup)
- PITR within retention period (5 minute granularity)

```bash
# Create manual snapshot
aws rds create-db-snapshot --db-snapshot-identifier my-snap-2024-05 \
    --db-instance-identifier my-db

# Restore to specific time
aws rds restore-db-instance-to-point-in-time \
    --source-db-instance-identifier my-db \
    --target-db-instance-identifier my-db-restored \
    --restore-time "2024-05-15T14:30:00Z"
```

### GCP CloudSQL
- Automated backups + PITR up to 7 days
- Export to GCS bucket

---

## 9. Backup Verification (CRITICAL!)

**A backup not tested = no backup.**

### Daily Backup Test (Automated)
```bash
#!/bin/bash
# 1. Spin up temp Postgres instance
docker run -d --name pg-test postgres:16

# 2. Restore yesterday's backup
wal-g backup-fetch /var/lib/postgresql/data LATEST

# 3. Verify data
psql -c "SELECT count(*) FROM critical_table" > result.txt
expected=$(cat /baseline/critical_count.txt)
actual=$(cat result.txt)

if [ "$expected" != "$actual" ]; then
    pagerduty_alert "Backup verification FAILED"
fi

# 4. Cleanup
docker rm -f pg-test
```

### Quarterly Disaster Drill
- Restore full DB from scratch
- Time it (RTO measurement)
- Run app against restored DB
- Document gaps

---

## 10. What to Include in Backup

✅ **Always include:**
- Database data files
- WAL archives
- Configuration files (`postgresql.conf`, `pg_hba.conf`)
- Extension definitions

⚠️ **Often forgotten:**
- TLS certificates
- Encryption keys (KMS keys, etc.)
- Connection strings / secrets
- Custom functions/extensions
- pgbouncer config
- App-level data outside DB (S3 files, Redis)

### "DR Document" Should Cover
1. Where backups are stored
2. How to access backup keys
3. Step-by-step restore procedure
4. Who to contact (oncall + escalation)
5. Customer communication template
6. RPO/RTO commitments

---

## 11. Common Disaster Scenarios

### Scenario 1: Accidental DROP TABLE
- PITR to 1 minute before disaster
- Extract just that table
- Re-import to production

### Scenario 2: Ransomware encrypts DB
- Restore from offsite, immutable backup
- Disconnect compromised infra
- Forensic investigation

### Scenario 3: Region outage (AWS us-east-1 down)
- Failover to cross-region read replica
- Promote to primary
- Continue operations from another region
- Sync back when origin recovers

### Scenario 4: Human error — "DELETE without WHERE"
- PITR to 1 minute before query
- Or use logical decoding + reapply

### Scenario 5: Corruption
- Detected via consistency checks (`amcheck` extension)
- Restore from last verified backup
- Apply WAL up to last known-good point

---

## 12. Backup Anti-Patterns

❌ **Storing backups on same disk as DB**
If disk dies, both gone.

❌ **No encryption**
S3 leak = customer data leak.

❌ **Same region only**
Region outage = both gone.

❌ **Never testing restore**
Find out backup is broken during real outage.

❌ **Retention too short**
Bug introduced 60 days ago, only 30 days kept.

❌ **No monitoring**
Backups failing silently for weeks.

❌ **Application data ignored**
DB backup good, but S3 files weren't backed up.

---

## 13. Encryption + Compliance

### At rest
```bash
wal-g --use-storage-encryption=AES256 backup-push ...
# Or use S3 SSE-S3 / SSE-KMS
```

### In transit
- Use TLS for WAL streaming
- Use HTTPS for S3 uploads

### Compliance considerations
- **GDPR**: right to be forgotten — must purge from backups too
- **HIPAA**: encrypted backups, audit logs
- **PCI-DSS**: encryption + key rotation
- **SOC 2**: documented procedures, drills

### Backup deletion (right to be forgotten)
Hardest problem. Options:
1. Don't backup PII (encrypt at app level, deleted key = forgotten)
2. Application-level tombstones (DB keeps, app filters)
3. Periodic backup rotation (delete old backups after PII purge)

---

## 14. Backup Monitoring Metrics

```sql
-- Last backup time (custom metric)
SELECT pg_size_pretty(pg_database_size('mydb'));
```

### Key alerts
- Backup didn't complete in last 24h
- WAL archive failed
- Backup size deviation > 20% (could be corruption)
- Test restore failed
- S3 upload latency > threshold

### Prometheus exporter
- `postgres_exporter` + `wal_g_metrics`

---

## 15. Interview Questions

**Q1: RPO vs RTO?**
RPO = max acceptable data loss (minutes). RTO = max downtime (minutes). Backup strategy depends on these.

**Q2: pg_dump vs pg_basebackup?**
pg_dump = logical (SQL), cross-version, slow for big DBs. pg_basebackup = physical (files), faster, same version only.

**Q3: PITR kaise kaam karta?**
Base backup + continuous WAL archiving. Restore base → replay WAL up to target time.

**Q4: WAL archive frequency?**
`archive_timeout = 60` forces flush every 60s. RPO = 60s for active DBs, 0 if traffic constant.

**Q5: Backup testing critical kyu?**
Untested backups often broken. Run automated restore daily + quarterly full drill.

**Q6: Cross-region backup zaroori?**
Yes — region outage rare but devastating. Replicate to different region.

**Q7: GDPR + backups?**
Right to be forgotten conflicts with immutable backups. Use encryption-key-based deletion or rotation.

---

## 16. Best Practices

1. **Automate everything** — manual = forgotten = catastrophe
2. **Test restores daily** — automated verification
3. **3-2-1 rule:** 3 copies, 2 different media, 1 offsite
4. **Encrypt always** — at rest + in transit
5. **PITR setup** unless RPO > 24h is OK
6. **Document procedures** — anyone on team can restore
7. **Quarterly DR drills** — measure RTO
8. **Separate backup credentials** — limit blast radius
9. **Monitor backup success** — alert on failure
10. **Include app data** (S3, Redis state) in DR plan

---

## Related
- [[09_postgresql_ha_read_replicas]]
- [[13_postgresql_performance_tuning]]
- [[07_postgresql_internals]] — WAL
