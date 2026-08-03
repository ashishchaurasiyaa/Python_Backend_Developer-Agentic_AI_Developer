# Cloud (AWS) — Storage & Database: S3, EBS, EFS, RDS, DynamoDB, Aurora
**DevOps Track · Phase 7: Cloud (AWS)**

## Quick Concepts

- **S3** = Simple Storage Service — object storage, virtually unlimited, accessed over HTTP(S)
- **Object** = a file + its metadata, stored flat inside a bucket (no real directory tree, just key prefixes)
- **EBS** = Elastic Block Store — a virtual hard disk attached to exactly one EC2 instance at a time (mostly)
- **EFS** = Elastic File System — a network filesystem (NFS) mountable by many instances simultaneously
- **RDS** = Relational Database Service — managed Postgres/MySQL/MariaDB/SQL Server/Oracle
- **Multi-AZ (RDS)** = a synchronous standby replica in a different AZ for failover, not for read scaling
- **Read Replica** = an asynchronous, read-only copy used to offload read traffic, not for failover safety
- **DynamoDB** = fully managed NoSQL key-value/document store, scales horizontally by design
- **Partition key** = the attribute DynamoDB hashes to decide which physical partition stores an item
- **Aurora** = AWS's own MySQL/Postgres-compatible engine with a re-architected storage layer

---

## S3 — Object Storage

### Core Model

```
Bucket    → globally unique name, region-scoped, holds objects
Object    → key (full "path" string) + value (bytes) + metadata, up to 5TB per object
Key       → "orders/2026/07/invoice-882.pdf" — looks like a path, is actually just a string;
            the "folder" structure in the S3 console is a UI illusion over flat key prefixes
```

```bash
aws s3api create-bucket --bucket my-app-uploads --region ap-south-1 \
  --create-bucket-configuration LocationConstraint=ap-south-1
aws s3api list-buckets --query 'Buckets[].Name'      # or: aws s3 ls

aws s3 ls s3://my-app-uploads/                          # list objects at the bucket root
aws s3 ls s3://my-app-uploads/reports/ --recursive        # list everything under a prefix

aws s3 cp report.pdf s3://my-app-uploads/reports/2026/report.pdf
aws s3 cp s3://my-app-uploads/reports/2026/report.pdf ./     # download instead of upload
aws s3 sync ./dist s3://my-static-site-bucket --delete          # mirror a local dir TO a bucket,
                                                                   # --delete removes objects in
                                                                   # the bucket that no longer
                                                                   # exist locally (careful — this
                                                                   # is destructive on the remote side)

aws s3 rm s3://my-app-uploads/reports/2026/report.pdf     # delete ONE object
aws s3 rm s3://my-app-uploads/reports/ --recursive          # delete everything under a prefix
aws s3 rb s3://my-app-uploads --force                         # delete the BUCKET itself
                                                                 # (--force needed if it's non-empty)
```

### Storage Classes — Cost vs Access Pattern

| Class | Use Case | Retrieval | Relative Cost |
|---|---|---|---|
| **S3 Standard** | Frequently accessed, active data | Milliseconds | Highest of the "hot" tiers |
| **S3 Intelligent-Tiering** | Unknown/changing access pattern | Milliseconds | Auto-moves objects between tiers, small monitoring fee |
| **S3 Standard-IA** | Infrequent access, needed fast when accessed | Milliseconds | ~45% cheaper than Standard, retrieval fee per GB |
| **S3 One Zone-IA** | Infrequent, recreatable data (single AZ, less durable) | Milliseconds | Cheaper than Standard-IA |
| **S3 Glacier Instant Retrieval** | Archive accessed ~quarterly | Milliseconds | Much cheaper, still instant |
| **S3 Glacier Flexible Retrieval** | Archive, rarely accessed | Minutes to hours | Very cheap |
| **S3 Glacier Deep Archive** | Compliance/regulatory, 7-10yr retention | Up to 12 hours | Cheapest storage AWS offers |

**Interview pattern**: "we have 5 years of audit logs nobody reads unless there's a compliance investigation" → Glacier Deep Archive. "We have user profile photos accessed daily" → Standard, possibly fronted by CloudFront cache.

### Versioning

```
Off (default)  → PUT with same key overwrites the object, old bytes gone
On             → every PUT creates a new version, "delete" just adds a
                  delete marker (soft delete) — the actual bytes are still
                  there and recoverable until you purge a specific version

Enable when: accidental overwrite/delete is a real risk (source of truth
buckets, Terraform state buckets, compliance data)

Cost consequence: every version is billed storage — pair with a lifecycle
policy so old versions don't accumulate forever
```

```bash
aws s3api put-bucket-versioning --bucket my-app-uploads \
  --versioning-configuration Status=Enabled
```

### Lifecycle Policies — Automate the Storage Class Ladder

```json
{
  "Rules": [
    {
      "ID": "move-old-logs-to-glacier",
      "Filter": {"Prefix": "logs/"},
      "Status": "Enabled",
      "Transitions": [
        {"Days": 30, "StorageClass": "STANDARD_IA"},
        {"Days": 90, "StorageClass": "GLACIER"}
      ],
      "Expiration": {"Days": 2555}
    },
    {
      "ID": "cleanup-old-versions",
      "Filter": {},
      "Status": "Enabled",
      "NoncurrentVersionExpiration": {"NoncurrentDays": 30}
    }
  ]
}
```

Read as: logs younger than 30 days stay in Standard (fast, expensive), 30-90 days move to Standard-IA, past 90 days move to Glacier, and everything is deleted after ~7 years (2555 days). Old object *versions* (from versioning) get purged after 30 days regardless. This is the standard pattern for turning a manual "someone should clean up S3" task into something that runs itself.

---

## EBS — Elastic Block Store

### Volume Types

| Type | Best For | Baseline / Max IOPS | Notes |
|---|---|---|---|
| **gp3** | General purpose — default choice today | 3,000 IOPS baseline, up to 16,000 | IOPS and throughput priced/provisioned independently of size (unlike gp2) |
| **gp2** | Legacy general purpose | 3 IOPS per GB, up to 16,000 | IOPS scales with volume size — a 10GB gp2 volume is IOPS-starved |
| **io2 / io2 Block Express** | High-performance databases, low-latency critical workloads | Up to 256,000 IOPS | Higher durability (99.999%), higher cost, provisioned IOPS |
| **st1** | Throughput-heavy sequential workloads (big data, log processing) | Throughput-optimized, not IOPS | Cheap per GB, HDD-backed |
| **sc1** | Cold, infrequently accessed data | Lowest cost | HDD-backed, lowest performance tier |

**Interview-relevant**: gp3 is the near-default recommendation now — it decouples IOPS/throughput from volume size, so you're not forced to over-provision a 500GB volume just to get more IOPS the way gp2 required. Reach for io2 specifically when a database's p99 latency is IOPS-bound and cannot tolerate variance.

### Snapshots

```
An EBS snapshot is an incremental, point-in-time backup stored in S3
(you don't see the S3 bucket — it's AWS-managed).

  - First snapshot        → full copy of all used blocks
  - Every snapshot after  → only the CHANGED blocks since the last snapshot
  - Restoring a snapshot   → creates a NEW volume, doesn't touch the original

Automate with AWS Backup or Data Lifecycle Manager — don't rely on
someone remembering to click "create snapshot" before a risky deploy.
```

```bash
aws ec2 create-snapshot --volume-id vol-0123456789abcdef0 \
  --description "pre-migration backup $(date +%F)"

aws ec2 create-volume --snapshot-id snap-0abc123 --availability-zone ap-south-1a
```

---

## EFS — Elastic File System

### EBS vs EFS — When to Use Which

| | EBS | EFS |
|---|---|---|
| Protocol | Block storage (raw disk) | NFS (network file share) |
| Attach to | One instance at a time (one exception: io2 Multi-Attach) | Many instances/AZs simultaneously |
| Scaling | Manual — resize the volume | Automatic — grows/shrinks with usage, no provisioning |
| Typical use | Database data directory, root volume | Shared config, shared uploads directory across a fleet, WordPress-style shared content |
| AZ scope | Single AZ (must match the instance) | Regional — mountable from any AZ in the region |
| Cost model | Pay for provisioned size | Pay for what's actually stored (Standard) plus optional IA tier |

**The decision in one line**: if two or more instances need to read/write the *same* files concurrently (shared uploads folder, shared media library, a scaling web tier that needs identical config on every node), that's EFS. If it's a database's own data directory attached to one instance, that's EBS — databases manage their own consistency and generally should not sit on a shared network filesystem.

---

## RDS — Relational Database Service

### What Managed Actually Buys You

```
AWS handles: OS patching, DB engine patching (in the maintenance window),
             automated backups, point-in-time restore, storage scaling
             (with storage autoscaling enabled), Multi-AZ failover orchestration

You still handle: schema design, query performance, indexing, connection
             pooling, application-level retry logic
```

### Multi-AZ vs Read Replicas — the Interview Question That Trips People Up

| | Multi-AZ | Read Replica |
|---|---|---|
| Purpose | **High availability / failover** | **Read scaling** |
| Replication | Synchronous | Asynchronous |
| Standby usable for reads? | No (standby is not accessible directly) | Yes — that's the whole point |
| Failover | Automatic, DNS endpoint flips to standby, ~60-120s | Manual promotion required to become writable |
| Data loss on primary failure | None (synchronous) | Possible — replication lag means some recent writes may not have propagated |
| Where | Different AZ, same region | Same region OR cross-region |

The trap: people say "Multi-AZ gives us read scaling" — it does not, the standby is invisible to your application except during failover. If you need both HA *and* read scaling, you run Multi-AZ **and** one or more read replicas together — they solve different problems and are not substitutes for each other.

```bash
aws rds create-db-instance \
  --db-instance-identifier prod-orders-db \
  --engine postgres \
  --engine-version 16.3 \
  --db-instance-class db.r6g.large \
  --allocated-storage 100 \
  --storage-type gp3 \
  --multi-az \
  --master-username admin \
  --manage-master-user-password \
  --vpc-security-group-ids sg-0db0123456789ab \
  --backup-retention-period 7

aws rds create-db-instance-read-replica \
  --db-instance-identifier prod-orders-db-replica-1 \
  --source-db-instance-identifier prod-orders-db
```

`--manage-master-user-password` delegates the DB password to Secrets Manager with automatic rotation instead of a plaintext master password on the CLI — the modern default, tie this back to the Secrets Manager section in `05_monitoring_messaging_secrets.md`.

---

## DynamoDB — NoSQL at AWS Scale

### Core Concepts

```
Table         → schema-less collection of items (roughly: rows)
Item          → a single record, up to 400KB, made of attributes (roughly: columns)
Partition key → REQUIRED, DynamoDB hashes this to pick which physical
                partition stores the item — this is the single most
                important design decision in a DynamoDB table
Sort key      → OPTIONAL, orders items sharing the same partition key
                (partition key + sort key together = composite primary key)
```

### Partition Key Design — Why It's Not Optional to Think About

```
BAD:  partition key = "status"  (values: "pending", "shipped", "delivered")
      → only 3 distinct values ever, all "pending" orders pile onto ONE
        partition → hot partition → throttling under load, no matter
        how much capacity you provision

GOOD: partition key = "order_id" (UUID, effectively unlimited cardinality)
      → writes/reads spread evenly across many partitions
```

The rule: pick a partition key with high cardinality and even access distribution. A key that funnels most traffic onto a small number of values (status, boolean flags, a fixed small enum) creates a hot partition regardless of table-level throughput settings.

### On-Demand vs Provisioned Capacity

| | On-Demand | Provisioned |
|---|---|---|
| You specify | Nothing — pay per request | Read/Write Capacity Units (RCU/WCU) ahead of time |
| Scaling | Instant, automatic | Manual, or Auto Scaling attached to a target utilization |
| Cost profile | Higher per-request cost, zero idle cost | Cheaper at steady, predictable load |
| Best for | Spiky/unknown traffic, new tables, dev/test | Stable, well-understood, high-volume steady traffic |

```bash
aws dynamodb create-table \
  --table-name Orders \
  --attribute-definitions AttributeName=order_id,AttributeType=S \
  --key-schema AttributeName=order_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST
```

---

## Aurora — RDS, Re-Architected

### Aurora vs Standard RDS

```
Standard RDS (e.g. RDS for PostgreSQL)
  → runs the actual open-source engine, storage is EBS-backed, replication
    to standby/replicas ships whole WAL/binlog segments over the network

Aurora (MySQL- or PostgreSQL-compatible)
  → storage layer is a proprietary, distributed, self-healing system spread
    across 3 AZs (6 copies of data) — the compute (database engine) layer
    is decoupled from storage
  → replicas share the SAME underlying storage volume as the writer, so
    replica lag is typically much lower (often <100ms) than standard
    asynchronous RDS read replicas, because replicas aren't re-applying
    the whole write stream, just catching up on already-durable storage
  → supports up to 15 read replicas (vs 5 for standard RDS engines) and
    Aurora Serverless v2 for auto-scaling compute capacity
  → storage auto-grows in 10GB increments up to 128TB, no manual resizing
```

**When to reach for Aurora over RDS-Postgres**: read-heavy workloads needing many low-lag replicas, unpredictable/spiky compute needs (Serverless v2), or when the faster failover (typically <30s) matters more than the modest cost premium over standard RDS.

---

## Senior Tip

```
"We store user uploads in S3" is a junior-level sentence.

"User uploads go to S3 Standard behind a lifecycle policy that moves
 anything untouched for 90 days to Glacier Instant Retrieval, versioning
 is on with a 30-day noncurrent-version expiration so accidental
 overwrites are recoverable but don't balloon storage cost, and the
 bucket policy denies any PutObject that isn't SSE-KMS encrypted" —
 is the senior-level version of the same sentence.

Same pattern for RDS: don't just say "Multi-AZ" — say WHY (failover,
not read scaling) and pair it correctly with read replicas if reads
are the actual bottleneck you're solving for.
```

## Interview Angle

**Q: Your app writes are timing out on a DynamoDB table that has plenty of provisioned capacity. Why?**

Almost always a hot partition — check CloudWatch's `ThrottledRequests` and look at which partition key values dominate write volume. Provisioned *table-level* capacity doesn't help if one partition (bound by a much lower per-partition limit) is absorbing a disproportionate share of the traffic. Fix is a better partition key design (higher cardinality, or a write-sharding suffix on a hot key), not just raising capacity.

---

## Related

- [01_iam_compute_ec2.md](01_iam_compute_ec2.md) — IAM roles for accessing these services securely
- [03_networking_dns_lb.md](03_networking_dns_lb.md) — VPC placement for RDS, security group rules for DB access
- [05_monitoring_messaging_secrets.md](05_monitoring_messaging_secrets.md) — Secrets Manager for DB credentials, CloudWatch alarms on DB metrics
- [../../Backend_Developer/01_Year3-4_Mid/04_DevOps/04_aws_ec2_s3_rds.md](../../Backend_Developer/01_Year3-4_Mid/04_DevOps/04_aws_ec2_s3_rds.md) — boto3 S3 upload/download code, app-side usage
