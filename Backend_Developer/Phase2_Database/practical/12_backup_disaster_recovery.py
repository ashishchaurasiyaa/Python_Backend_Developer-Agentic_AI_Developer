"""
============================================================
POSTGRESQL BACKUP + DISASTER RECOVERY — Practical
============================================================
Scripts + bash templates for production backup workflows.
"""


# ============================================================
# 1. PG_DUMP SCRIPTS
# ============================================================
PG_DUMP_SCRIPTS = """
# Daily full dump (custom format, compressed)
#!/bin/bash
set -euo pipefail

DATE=$(date +%Y-%m-%d_%H-%M)
BACKUP_DIR=/backups/postgres
S3_BUCKET=s3://my-company-db-backups

# 1. Take dump
pg_dump -h db.internal -U postgres -Fc -Z 9 mydb > "$BACKUP_DIR/mydb_$DATE.dump"

# 2. Encrypt
gpg --encrypt --recipient backup@company.com "$BACKUP_DIR/mydb_$DATE.dump"

# 3. Upload to S3 with versioning
aws s3 cp "$BACKUP_DIR/mydb_$DATE.dump.gpg" \\
    "$S3_BUCKET/daily/mydb_$DATE.dump.gpg" \\
    --storage-class STANDARD_IA \\
    --server-side-encryption aws:kms

# 4. Verify upload
aws s3 ls "$S3_BUCKET/daily/mydb_$DATE.dump.gpg" > /dev/null

# 5. Cleanup local
rm "$BACKUP_DIR/mydb_$DATE.dump" "$BACKUP_DIR/mydb_$DATE.dump.gpg"

# 6. Metrics
echo "backup_success{db=\\"mydb\\"} 1 $(date +%s)" | \\
    curl --data-binary @- http://pushgateway:9091/metrics/job/backup
"""


# ============================================================
# 2. PG_BASEBACKUP + WAL ARCHIVING
# ============================================================
PG_BASEBACKUP_SCRIPT = """
#!/bin/bash
# Daily base backup with WAL streaming

DATE=$(date +%Y-%m-%d)
BACKUP_DIR=/backups/base/$DATE
S3_BUCKET=s3://my-company-db-backups

mkdir -p "$BACKUP_DIR"

pg_basebackup \\
    -h db.internal \\
    -U replicator \\
    -D "$BACKUP_DIR" \\
    -Ft \\                   # tar format
    -z \\                    # gzip compression
    -P \\                    # progress
    -X stream \\             # include WAL during backup
    -c fast \\               # fast checkpoint
    --label="daily_$DATE"

# Upload to S3
aws s3 sync "$BACKUP_DIR" "$S3_BUCKET/base/$DATE/" \\
    --storage-class STANDARD_IA

# Verify
aws s3 ls "$S3_BUCKET/base/$DATE/" | wc -l
"""


# ============================================================
# 3. POSTGRESQL.CONF — Enable WAL archiving
# ============================================================
POSTGRESQL_CONF = """
# /etc/postgresql/16/main/postgresql.conf

# WAL configuration
wal_level = replica                  # or 'logical' for logical replication
archive_mode = on
archive_timeout = 60                 # force WAL switch every 60s (RPO < 1min)

# Archive command — copy WAL to S3
archive_command = 'wal-g wal-push %p'

# Or AWS CLI:
# archive_command = 'aws s3 cp %p s3://my-bucket/wal/%f --storage-class STANDARD_IA'

# WAL retention
wal_keep_size = 4GB                  # keep at least 4GB on primary
max_wal_senders = 10
max_replication_slots = 10
"""


# ============================================================
# 4. WAL-G — Modern Backup Tool
# ============================================================
WAL_G_SETUP = """
# Install (Go binary)
go install github.com/wal-g/wal-g/cmd/pg@latest

# Configure (environment file: /etc/wal-g/env)
export WALG_S3_PREFIX=s3://my-bucket/postgres-backups
export AWS_REGION=us-east-1
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export WALG_COMPRESSION_METHOD=lz4  # or brotli, lzma
export WALG_DELTA_MAX_STEPS=6        # incremental backups
export WALG_S3_STORAGE_CLASS=STANDARD_IA
export WALG_S3_SSE_KMS_ID=arn:aws:kms:...

# Base backup
sudo -u postgres wal-g backup-push /var/lib/postgresql/16/main

# List backups
sudo -u postgres wal-g backup-list

# Cleanup old backups (keep last 7 daily + 4 weekly)
sudo -u postgres wal-g delete retain FULL 7 --confirm

# In postgresql.conf
archive_command = 'wal-g wal-push %p'

# Cron schedule
# /etc/cron.d/postgres-backup
0 2 * * *  postgres  /usr/local/bin/wal-g backup-push /var/lib/postgresql/16/main >> /var/log/wal-g.log 2>&1
0 4 * * 0  postgres  /usr/local/bin/wal-g delete retain FULL 14 --confirm
"""


# ============================================================
# 5. RESTORE SCRIPTS
# ============================================================
RESTORE_FULL = """
#!/bin/bash
# Restore latest backup to fresh Postgres instance

# 1. Stop Postgres
systemctl stop postgresql

# 2. Backup current data (just in case)
mv /var/lib/postgresql/16/main /var/lib/postgresql/16/main.broken.$(date +%s)

# 3. Restore base backup
mkdir -p /var/lib/postgresql/16/main
chown postgres:postgres /var/lib/postgresql/16/main
chmod 0700 /var/lib/postgresql/16/main
sudo -u postgres wal-g backup-fetch /var/lib/postgresql/16/main LATEST

# 4. Configure recovery
cat > /var/lib/postgresql/16/main/postgresql.auto.conf <<EOF
restore_command = 'wal-g wal-fetch %f %p'
recovery_target_action = 'promote'
EOF

# 5. Mark as ready for recovery
touch /var/lib/postgresql/16/main/recovery.signal

# 6. Start (will replay WAL automatically)
systemctl start postgresql

# 7. Wait for recovery
while sudo -u postgres psql -c "SELECT pg_is_in_recovery()" -t -A | grep -q t; do
    echo "Still recovering..."
    sleep 5
done

echo "✅ Recovery complete!"
"""

RESTORE_PITR = """
#!/bin/bash
# Point-In-Time Recovery to specific timestamp

TARGET_TIME="2024-05-15 14:30:00 IST"

systemctl stop postgresql
rm -rf /var/lib/postgresql/16/main
sudo -u postgres wal-g backup-fetch /var/lib/postgresql/16/main LATEST

cat > /var/lib/postgresql/16/main/postgresql.auto.conf <<EOF
restore_command = 'wal-g wal-fetch %f %p'
recovery_target_time = '$TARGET_TIME'
recovery_target_action = 'pause'    # pause so we can verify before promoting
EOF

touch /var/lib/postgresql/16/main/recovery.signal
systemctl start postgresql

# Postgres will replay WAL up to target time, then PAUSE.
# Verify data is correct:
#   psql -c "SELECT * FROM critical_table WHERE id = 12345"
# When satisfied, promote:
#   psql -c "SELECT pg_wal_replay_resume()"
#   psql -c "SELECT pg_promote()"
"""


# ============================================================
# 6. BACKUP VERIFICATION (Automated)
# ============================================================
import subprocess
import time
import os
from dataclasses import dataclass


@dataclass
class BackupVerificationResult:
    success: bool
    backup_size_mb: float
    restore_time_seconds: float
    row_count_diff: int
    error: str | None = None


def verify_backup_python(backup_name: str, baseline_row_count: int) -> BackupVerificationResult:
    """Spin up temp Postgres, restore backup, verify row count.

    In production: run nightly. Alert PagerDuty on failure.
    """
    container_name = f"pg-verify-{int(time.time())}"
    start = time.perf_counter()

    try:
        # 1. Start temp Postgres
        subprocess.run([
            "docker", "run", "-d", "--name", container_name,
            "-e", "POSTGRES_PASSWORD=test",
            "postgres:16",
        ], check=True)

        # Wait for ready
        time.sleep(5)

        # 2. Restore (placeholder — real code calls wal-g)
        # subprocess.run([
        #     "docker", "exec", container_name,
        #     "wal-g", "backup-fetch", "/var/lib/postgresql/data", backup_name,
        # ], check=True)

        # 3. Verify row count
        result = subprocess.run(
            ["docker", "exec", container_name, "psql", "-U", "postgres",
             "-c", "SELECT count(*) FROM critical_table"],
            capture_output=True, text=True, check=True,
        )
        actual_count = int(result.stdout.split()[-2])

        diff = abs(actual_count - baseline_row_count)
        success = diff < (baseline_row_count * 0.01)  # < 1% tolerance

        elapsed = time.perf_counter() - start
        return BackupVerificationResult(
            success=success,
            backup_size_mb=0,  # would query actual size
            restore_time_seconds=elapsed,
            row_count_diff=diff,
        )

    except Exception as e:
        return BackupVerificationResult(
            success=False, backup_size_mb=0, restore_time_seconds=0,
            row_count_diff=-1, error=str(e),
        )
    finally:
        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)


# ============================================================
# 7. AWS RDS AUTOMATED SNAPSHOTS
# ============================================================
RDS_BACKUP = """
# Enable backups when creating RDS
aws rds create-db-instance \\
    --db-instance-identifier my-app-db \\
    --backup-retention-period 30 \\        # keep 30 days
    --preferred-backup-window "03:00-04:00" \\
    --enable-iam-database-authentication

# Manual snapshot
aws rds create-db-snapshot \\
    --db-snapshot-identifier my-db-pre-migration \\
    --db-instance-identifier my-app-db

# List snapshots
aws rds describe-db-snapshots --db-instance-identifier my-app-db

# Restore to point in time (within retention window)
aws rds restore-db-instance-to-point-in-time \\
    --source-db-instance-identifier my-app-db \\
    --target-db-instance-identifier my-app-db-restored \\
    --restore-time "2024-05-15T14:30:00Z" \\
    --db-subnet-group-name default

# Cross-region copy (DR)
aws rds copy-db-snapshot \\
    --source-db-snapshot-identifier my-snap-2024-05 \\
    --target-db-snapshot-identifier my-snap-2024-05-eu \\
    --source-region us-east-1 \\
    --region eu-west-1 \\
    --kms-key-id arn:aws:kms:eu-west-1:...
"""


# ============================================================
# 8. DR DRILL CHECKLIST
# ============================================================
DR_DRILL_CHECKLIST = """
# Quarterly DR Drill — Run Through

PRE-FLIGHT
[ ] Notify team (drill, not real)
[ ] Verify backups exist for past 30 days
[ ] Run "backup-list" command to confirm

EXECUTION (target RTO: 30 minutes)
[ ] T+0:    Trigger drill — start timer
[ ] T+2:    Identify latest backup
[ ] T+5:    Spin up new Postgres instance
[ ] T+10:   Begin restore from S3
[ ] T+20:   Restore completes
[ ] T+22:   Apply WAL up to current time (PITR)
[ ] T+25:   Run smoke tests (key tables, counts, sample queries)
[ ] T+27:   App connects + works
[ ] T+30:   Drill complete

POST-DRILL
[ ] Record actual RTO vs target
[ ] Document any issues
[ ] Update runbook with learnings
[ ] Schedule next drill (90 days)

GAPS TO CHECK
[ ] Are backup credentials accessible during incident?
[ ] Is restore documented step-by-step?
[ ] Can multiple oncall engineers execute it?
[ ] Are app config + secrets backed up too?
[ ] Are DNS / load balancer changes documented?
"""


# ============================================================
# 9. PYTHON SCRIPT: Send Metrics to Prometheus
# ============================================================
BACKUP_METRICS_PYTHON = """
import requests
import time

def report_backup_metric(success: bool, size_bytes: int, duration_s: float):
    metrics = (
        f'postgres_backup_success {{db=\"mydb\"}} {1 if success else 0}\\n'
        f'postgres_backup_size_bytes {{db=\"mydb\"}} {size_bytes}\\n'
        f'postgres_backup_duration_seconds {{db=\"mydb\"}} {duration_s}\\n'
        f'postgres_backup_last_success_timestamp {{db=\"mydb\"}} {int(time.time())}\\n'
    )
    requests.post(
        'http://pushgateway:9091/metrics/job/postgres-backup',
        data=metrics,
    )

# Alert rule (prometheus.yml)
# - alert: PostgresBackupFailed
#   expr: postgres_backup_success == 0
#   for: 5m
#
# - alert: PostgresBackupStale
#   expr: time() - postgres_backup_last_success_timestamp > 86400
#   for: 5m
"""


# ============================================================
# 10. ENCRYPTION + COMPLIANCE
# ============================================================
ENCRYPTION_SETUP = """
# wal-g with KMS encryption
export WALG_S3_SSE_KMS_ID=arn:aws:kms:us-east-1:...
export WALG_LIBSODIUM_KEY=...

# Test encryption is working
wal-g backup-push /data
aws s3api head-object --bucket my-bucket --key "backups/base/..." | jq .ServerSideEncryption

# Key rotation procedure (yearly):
# 1. Create new KMS key
# 2. Update WALG_S3_SSE_KMS_ID
# 3. New backups use new key automatically
# 4. Old backups can still be decrypted with old key (KMS keeps old versions)

# GDPR — right to be forgotten approach:
# - Application encrypts PII columns with per-user key
# - User deletion → delete the encryption key
# - DB rows remain (with encrypted blob) — unreadable
# - Backups still contain rows, but PII unreadable
"""


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("POSTGRESQL BACKUP + DR — Scripts & Templates")
    print("=" * 60)

    print("\n--- pg_dump scripts ---")
    print(PG_DUMP_SCRIPTS)
    print("\n--- pg_basebackup ---")
    print(PG_BASEBACKUP_SCRIPT)
    print("\n--- postgresql.conf for WAL archiving ---")
    print(POSTGRESQL_CONF)
    print("\n--- WAL-G setup ---")
    print(WAL_G_SETUP)
    print("\n--- Restore (full) ---")
    print(RESTORE_FULL)
    print("\n--- Point-In-Time Recovery ---")
    print(RESTORE_PITR)
    print("\n--- AWS RDS ---")
    print(RDS_BACKUP)
    print("\n--- DR Drill checklist ---")
    print(DR_DRILL_CHECKLIST)
    print("\n--- Encryption ---")
    print(ENCRYPTION_SETUP)
