# Elasticsearch Circuit Breakers & Version Conflicts

## Why It Matters

Production ES errors:
- **OOM crashes** from massive queries → circuit breakers prevent
- **Concurrent updates** → version conflicts → must handle
- **Slow queries** crashing nodes → resource limits

Senior interview: "CircuitBreakingException — what + fix?" → memory limit hit, identify hot query.

---

## Circuit Breakers

### Types

| Breaker | Limits | Default |
|---|---|---|
| **parent** | Total of all breakers | 95% of heap (G1GC) |
| **request** | Single request memory | 60% of heap |
| **fielddata** | Field data cache | 40% of heap |
| **in_flight_requests** | Concurrent network buffers | 100% of heap |
| **accounting** | Lucene segments | 100% of heap |

### CircuitBreakingException

```
[parent] Data too large, data for [<reduce_aggs>] would be
[X bytes], which is larger than the limit of [Y bytes]
```

**Causes:**
- Aggregation over too many buckets
- Large `size` in search
- Fielddata cache full (text field sorting/aggregating without keyword)
- Many concurrent expensive queries

**Fixes:**
1. Add `track_total_hits: false` to skip count
2. Reduce aggregation `size`
3. Use `terms` field (not text) for aggregation
4. Increase heap (up to 50% RAM, max 32GB)
5. Add more nodes

### Configure Breakers

```http
PUT _cluster/settings
{
  "persistent": {
    "indices.breaker.fielddata.limit": "30%",
    "indices.breaker.request.limit": "50%",
    "indices.breaker.total.limit": "85%"
  }
}
```

Lower = safer (more rejection) but smaller usable queries.

### Watching Breaker Stats

```http
GET _nodes/stats/breaker

{
  "nodes": {
    "node1": {
      "breakers": {
        "parent": {
          "limit_size_in_bytes": 8589934592,
          "estimated_size_in_bytes": 4294967296,
          "tripped": 0
        },
        ...
      }
    }
  }
}
```

`tripped > 0` = breaker has rejected — investigate.

---

## Version Conflicts (Optimistic Concurrency)

### `if_seq_no` + `if_primary_term`

ES uses sequence number + primary term for OCC:

```python
# Get current
doc = es.get(index='users', id='alice')
seq_no = doc['_seq_no']
primary_term = doc['_primary_term']

# Update with version check
try:
    es.update(
        index='users',
        id='alice',
        if_seq_no=seq_no,
        if_primary_term=primary_term,
        body={'doc': {'balance': 100}},
    )
except elasticsearch.ConflictError:
    # Another update happened — retry
    pass
```

If `_seq_no` doesn't match → 409 Conflict.

### External Versioning

```python
es.index(
    index='items',
    id='item-1',
    version=time_microseconds,    # client-supplied
    version_type='external',
    body={...},
)
```

Useful when source-of-truth timestamps are external (DB primary key + updated_at).

### `update_by_query` with `conflicts="proceed"`

```python
es.update_by_query(
    index='users',
    body={
        'query': {'term': {'status': 'pending'}},
        'script': 'ctx._source.status = "active"',
    },
    conflicts='proceed',   # log + skip conflicts, don't abort entire op
)
```

Without `conflicts='proceed'`, single conflict aborts whole operation.

### Retry on Conflict

```python
es.update(
    index='counters',
    id='visits',
    retry_on_conflict=3,
    body={'script': 'ctx._source.count++'},
)
```

ES auto-retries up to N times.

### `version_type=internal` vs `external` vs `external_gte`

- `internal` (default) — ES manages version
- `external` — accept any version > current (manual)
- `external_gte` — accept >= current (idempotent index)

---

## Force Merge Cautions

```http
POST my-index/_forcemerge?max_num_segments=1
```

**WARNING:**
- Generates lots of I/O
- Should ONLY be on read-only indices
- On active indices: causes huge merges that may never end
- Don't run during high traffic

For ILM: use `forcemerge` action in `warm` phase only.

## Index Lifecycle Pitfalls

### Too Many Shards

```
1000 daily indices × 5 shards × 2 replicas = 10,000 shards
```

Master overhead, slow recovery. Use rollover by size, not strict daily.

### Oversharding Small Indices

```
1 GB index with 5 shards = 200 MB each = waste
```

For < 10GB indices: 1-2 shards.

### Reindex API

When mapping change needed:

```http
POST _reindex
{
  "source": { "index": "old-index" },
  "dest": { "index": "new-index" }
}
```

Heavy operation. Use `slices: auto` for parallelism. Or use `_update_by_query` if just script-based change.

---

## Common Pitfalls

### 1. Aggregation Without Bucket Limit

```json
{ "aggs": { "by_user": { "terms": { "field": "user_id", "size": 100000 }}}}
```

100K buckets × N fields each = OOM. Use `size: 100` + composite aggregation for pagination.

### 2. Sorting on Text Field

```json
"sort": [{"name": "asc"}]   // text field — needs keyword sub-field
```

Use `name.keyword`. Or set `fielddata: true` (bad — uses heap).

### 3. Deep Pagination

```json
{ "from": 10000, "size": 10 }   // slow
```

Use search_after or PIT (Point in Time) for deep pagination.

### 4. Refresh per Request

```python
es.index(index='X', document=doc, refresh=True)   # forces refresh — kills throughput
```

Use `refresh=False` (default) for bulk; ES refreshes every 1s.

### 5. Many Small Documents

100K docs of 100 bytes each = much worse than 100 docs of 100KB. Aggregate before indexing.

### 6. Update Conflicts Not Handled

```python
try:
    es.update(...)
except ConflictError:
    # ignored or unhandled — data lost
    pass
```

Always: retry with fresh seq_no, or use `retry_on_conflict`.

### 7. Reindex Without `slices`

```python
es.reindex(body=..., slices=1)   # single-threaded — slow
```

Use `slices='auto'` for parallel chunks.

---

## Interview Q&A

**Q1:** Circuit breaker types aur trip kab hote hain?
**A:** Parent (total), request (single query), fielddata (text aggregations), in_flight_requests (network buffers), accounting (Lucene segments). Trip when memory usage approaches limit. CircuitBreakingException thrown → query rejected to protect node from OOM.

**Q2:** Version conflict resolve kaise karoge?
**A:** Optimistic concurrency via `if_seq_no` + `if_primary_term`. On conflict: refetch doc with current seq_no, reapply changes, retry. Or use `retry_on_conflict=N` for ES auto-retry. For bulk: `conflicts='proceed'` to skip + continue.

**Q3:** Aggregation OOM crash kaise prevent?
**A:** (1) Limit `size` in terms aggregation (default 10, can grow). (2) Use composite aggregation for pagination. (3) Avoid fielddata on text — use keyword fields. (4) `track_total_hits=false` if exact count not needed. (5) Monitor + alert on `breakers.tripped`.

**Q4:** Force merge production-safe kaise?
**A:** Only on read-only indices (set `index.blocks.write=true` first). Run during low traffic. ILM warm phase: forcemerge after rollover. Don't run on active write indices — concurrent merges create huge non-mergeable segments.

**Q5:** External versioning use case?
**A:** ES as secondary index over external source (MongoDB, RDBMS). Use external version = source's modification timestamp. ES rejects out-of-order updates. Useful for CDC pipelines where messages may arrive out of order.

**Q6:** Reindex large index — strategy?
**A:** `_reindex` with `slices='auto'` (parallel chunks). Or split into time-bucketed sub-reindexes. Monitor via `_tasks` API. For zero-downtime migration: dual-write to old + new index, switch reads after backfill complete, then drop old.

**Q7:** Update_by_query vs Reindex?
**A:** `_update_by_query`: in-place updates to existing index via script. Faster, no new index. `_reindex`: copy to new index with possibly different mapping. Use _update_by_query for field value changes; _reindex for mapping/setting changes.

**Q8:** Hot search query crashes cluster — debug?
**A:** Use `_tasks` API to find long-running queries. Slow log: `index.search.slowlog.threshold.query.warn: 5s`. Profile API on suspect query. Common: deep `from`, expensive aggregations, large `size`, large terms set in `terms` filter.

---

## Real-World Use Cases

### 1. CDC Pipeline (DB → ES)

Use external versioning with DB's `updated_at_microseconds` as version. Out-of-order messages handled correctly.

### 2. Counter Updates

```python
es.update(
    index='counters',
    id='daily-visits',
    retry_on_conflict=10,
    body={'script': 'ctx._source.count++'},
)
```

10 retries handle concurrent increments.

### 3. Logs with ILM + Force Merge

Daily rollover. Warm phase: force merge to 1 segment (huge query speedup). Cold phase: searchable snapshot to S3.

---

## References

- [Circuit Breakers](https://www.elastic.co/guide/en/elasticsearch/reference/current/circuit-breaker.html)
- [Optimistic Concurrency](https://www.elastic.co/guide/en/elasticsearch/reference/current/optimistic-concurrency-control.html)
- [Force Merge](https://www.elastic.co/guide/en/elasticsearch/reference/current/indices-forcemerge.html)
- [Reindex API](https://www.elastic.co/guide/en/elasticsearch/reference/current/docs-reindex.html)
