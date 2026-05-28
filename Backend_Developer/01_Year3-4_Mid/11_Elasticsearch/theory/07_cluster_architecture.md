# Elasticsearch Cluster Architecture

## Why It Matters

ES at scale = cluster of 100s of nodes. Senior backend must know:
- **Node roles** (master, data, ingest, coordinating)
- **Sharding strategy** (primary + replicas)
- **JVM tuning** (heap, GC)
- **Hot-warm-cold architecture**
- **Monitor + troubleshoot** (red cluster, unassigned shards)

Senior interview: "Cluster yellow ho gaya — debug?" → unassigned shards, disk full, master election.

---

## Core Concepts

### Node Roles

```yaml
# elasticsearch.yml
node.roles: [master, data, ingest]
```

- **master** — manages cluster state (recommended 3 dedicated)
- **data** — stores shards (most nodes)
- **data_hot, data_warm, data_cold, data_frozen** — tiered storage
- **ingest** — preprocesses documents (pipelines)
- **coordinating** — routing only (rare; usually any node coordinates)
- **ml** — machine learning workloads
- **transform** — continuous transforms

### Shards & Replicas

```json
PUT my-index
{
  "settings": {
    "number_of_shards": 5,
    "number_of_replicas": 1
  }
}
```

- 5 primary shards = data split into 5 parts
- 1 replica = 5 replica shards (copies)
- Total: 10 shards spread across nodes

**Shard sizing rule:** Each shard 10-50GB ideally. Too small (< 1GB) = overhead. Too large (> 100GB) = slow merges.

### Routing

Doc → shard via:
```
shard_id = hash(routing) % num_primary_shards
```

Default routing = doc `_id`. Can customize:

```python
es.index(index='users', id='alice', body={...}, routing='tenant_1')
# Ensures all of tenant_1's docs same shard
```

### Cluster State (Master Node)

Master holds cluster state:
- Index metadata (mappings, settings)
- Shard allocation (which shard on which node)
- Node membership

Replicated to all master-eligible nodes. Changes require majority vote.

### Discovery

```yaml
discovery.seed_hosts: ["host1", "host2", "host3"]
cluster.initial_master_nodes: ["master-1", "master-2", "master-3"]
```

3 master-eligible nodes for quorum. Avoid split-brain via voting config.

### JVM Heap

```bash
# jvm.options
-Xms16g
-Xmx16g
```

**Rules:**
- 50% of RAM max (other 50% for filesystem cache — critical for performance)
- 32GB max (compressed oops pointer optimization)
- For machines > 64GB RAM: run multiple ES instances, each with < 32GB heap

### File Descriptors + Memory Map

```bash
# /etc/security/limits.conf
elasticsearch  -  nofile  65535
elasticsearch  -  memlock unlimited
```

```bash
# /etc/sysctl.conf
vm.max_map_count = 262144  # mmap files limit
```

### Hot-Warm-Cold Architecture

```yaml
# Hot nodes — fast SSD, recent data
node.roles: [data_hot, data_content]
node.attr.data_tier: hot


# Warm nodes — HDDs, less queried
node.roles: [data_warm]
node.attr.data_tier: warm


# Cold nodes — cheap storage, archive
node.roles: [data_cold, data_frozen]
```

ILM (Index Lifecycle Management) moves indices across tiers automatically:

```json
PUT _ilm/policy/logs_policy
{
  "policy": {
    "phases": {
      "hot": {"actions": {"rollover": {"max_size": "50gb", "max_age": "7d"}}},
      "warm": {"min_age": "7d", "actions": {"allocate": {"include": {"data_tier": "warm"}}}},
      "cold": {"min_age": "30d", "actions": {"allocate": {"include": {"data_tier": "cold"}}}},
      "delete": {"min_age": "90d", "actions": {"delete": {}}}
    }
  }
}
```

### Cluster Health

```http
GET _cluster/health

{
  "status": "green",        // green/yellow/red
  "number_of_nodes": 6,
  "active_primary_shards": 50,
  "active_shards": 100,
  "unassigned_shards": 0
}
```

- **green** — all shards assigned (primary + replicas)
- **yellow** — all primaries OK, some replicas unassigned (lost redundancy)
- **red** — some primaries unassigned (data loss risk)

### Monitoring Commands

```http
GET _cat/nodes?v
GET _cat/indices?v
GET _cat/shards?v
GET _cat/recovery?v
GET _cat/thread_pool?v
GET _nodes/stats
GET _nodes/_local/jvm
```

### Cross-Cluster Replication (CCR)

Replicate indices across clusters (DR or geo):

```http
PUT my-follower-index/_ccr/follow
{
  "remote_cluster": "primary-cluster",
  "leader_index": "my-leader-index"
}
```

### Cross-Cluster Search (CCS)

Query multiple clusters at once:

```yaml
cluster.remote.cluster_two.seeds: ["host:9300"]
```

```http
GET cluster_one:my-index,cluster_two:my-index/_search
```

---

## How It Works Internally

### Allocation Algorithm

Master decides shard placement based on:
- Disk usage (`cluster.routing.allocation.disk.watermark.high` 85% — stops allocating)
- Node attributes (rack-awareness)
- Same shard's primary not on same node as its replica
- Custom allocation rules (data tier, region)

### Shard Recovery

When node joins or starts:
1. Identify shards it should have
2. For primary: read from local disk
3. For replica: sync from primary (file-based recovery)
4. Translog replay if needed

### Force Merge

Old, read-only indices: merge segments for query speed:

```http
POST my-index/_forcemerge?max_num_segments=1
```

Never run on actively written indices.

---

## Common Pitfalls

### 1. Heap Too Large

```
-Xmx64g
```

> 32GB = loses compressed oops. Worse: too little for filesystem cache → slow.

### 2. Too Many Shards

```
1000 indices × 5 shards × 1 replica = 10000 shards
```

Master overhead, slow recovery. Aim for < 1000 shards per node, < 5000 total.

### 3. Replicas = 0 in Prod

```json
{ "number_of_replicas": 0 }
```

Node fails → permanent data loss. Always ≥ 1 in prod.

### 4. No Dedicated Master Nodes

Data + master on same node = master under load when data busy. Always 3 dedicated masters.

### 5. Quorum Mismatch

```
4 master-eligible nodes (even) → split-brain risk
3, 5, 7 (odd) → clear quorum
```

### 6. Disk Watermark Breached

```
85% high watermark → ES stops allocating new shards
90% flood stage → index goes read-only
```

Monitor disk + alert at 70%.

### 7. Frozen Tier Without Searchable Snapshots

Frozen tier requires snapshots (S3). Without, data lost.

---

## Interview Q&A

**Q1:** ES cluster topology recommend karo for production.
**A:** 3 dedicated master-eligible nodes (small, no data). N data nodes (4-16 vCPU, 32-64GB RAM, NVMe SSD). 2-3 coordinating-only nodes (handle search aggregation). For tiered: hot nodes (SSD), warm (HDD), cold (cheap storage). All behind LB for client traffic.

**Q2:** Shard count kaise decide karoge?
**A:** Target shard size 10-50GB. Total data ÷ 30GB = approx primary shards. Plus 1+ replica for HA. Don't over-shard small indices. For time-series: rollover-based ILM with daily/weekly indices.

**Q3:** JVM heap sizing rule?
**A:** 50% of RAM, max 32GB. Other 50% for filesystem cache (ES relies heavily on OS cache for index files). > 32GB heap loses compressed oops (less efficient pointers). For 64GB machines: 31GB heap + 33GB filesystem cache.

**Q4:** Hot-Warm-Cold architecture?
**A:** Tiered storage by access pattern. Hot: recent + queried (SSD, smaller capacity). Warm: older, less queried (HDD, more capacity). Cold: archive (very cheap, may be slow). Frozen: searchable snapshots on S3. ILM moves indices automatically by age.

**Q5:** Unassigned shards reason kaise debug?
**A:** `GET _cluster/allocation/explain` — gives reason: disk full, mapping conflict, no eligible node, max_retries reached. Common: (1) disk watermark hit. (2) shard awareness rules violated. (3) replica conflicts with primary's node. (4) lost master.

**Q6:** Cross-cluster replication use case?
**A:** Disaster recovery (DR) — replicate prod to standby cluster, fail over on disaster. Geographic — replicate to closer region for low-latency reads. Compliance — replicate to local cluster for data residency. CCR is unidirectional + near-real-time.

**Q7:** Master election split-brain prevent kaise?
**A:** Discovery v2 (ES 7+) uses voting config — only certain nodes can vote. Quorum = (voters+1)/2. With 3 dedicated masters: quorum=2. Network partition → minority partition stops (no master). Never have even number of master-eligible.

**Q8:** Snapshot strategy production?
**A:** Schedule snapshots to S3 / shared filesystem (NFS). SLM (Snapshot Lifecycle Management) — daily snapshots, retain 30. Searchable snapshots for cold tier. Test restore quarterly. Cross-region S3 replication for catastrophe.

---

## Real-World Use Cases

### 1. Logging Cluster (Time-Series)

Hot (1-7 days) on SSD → Warm (7-30 days) on HDD → Cold (30-90 days) frozen snapshots → Delete. ILM rolls over daily.

### 2. Search Engine (Hot Only)

All data hot — search latency critical. Replicas = 2-3 for HA + read scaling.

### 3. Multi-Tenant SaaS

Custom routing: `routing=tenant_id` keeps all of one tenant's data on same shard. Faster tenant-scoped queries.

---

## References

- [ES Cluster Architecture](https://www.elastic.co/guide/en/elasticsearch/reference/current/modules-cluster.html)
- [Node Roles](https://www.elastic.co/guide/en/elasticsearch/reference/current/modules-node.html)
- [JVM Tuning](https://www.elastic.co/guide/en/elasticsearch/reference/current/heap-size.html)
- "Elasticsearch in Action" 2nd ed
