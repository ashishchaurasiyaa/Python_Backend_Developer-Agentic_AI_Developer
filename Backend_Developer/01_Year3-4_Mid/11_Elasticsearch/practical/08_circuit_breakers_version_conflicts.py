"""
ES Circuit Breakers & Version Conflicts — Production Patterns

Run: python 08_circuit_breakers_version_conflicts.py
Prereq: docker compose up -d   (see docker-compose.yml in this folder)
"""

import time
from elasticsearch import Elasticsearch, ConflictError, RequestError


es = Elasticsearch("http://localhost:9200")


# ==========================================================================
# 1. MONITOR CIRCUIT BREAKERS
# ==========================================================================

def check_breakers():
    stats = es.nodes.stats(metric='breaker')
    for node_id, node in stats['nodes'].items():
        breakers = node['breakers']
        for name, b in breakers.items():
            usage_pct = b['estimated_size_in_bytes'] / b['limit_size_in_bytes'] * 100 if b['limit_size_in_bytes'] else 0
            tripped = b['tripped']
            print(f"{node['name']} {name}: {usage_pct:.1f}% used, tripped={tripped}")
            if tripped > 0:
                print(f"  ALERT: {name} breaker has tripped {tripped} times")


# ==========================================================================
# 2. CONFIGURE BREAKER LIMITS
# ==========================================================================

def configure_breakers():
    es.cluster.put_settings(
        persistent={
            "indices.breaker.total.limit": "85%",
            "indices.breaker.request.limit": "50%",
            "indices.breaker.fielddata.limit": "30%",
        },
    )


# ==========================================================================
# 3. OPTIMISTIC CONCURRENCY (if_seq_no + if_primary_term)
# ==========================================================================

def update_with_occ(index: str, doc_id: str, updates: dict, max_retries: int = 5):
    """Update with version check + retry."""
    for attempt in range(max_retries):
        # Read current
        try:
            current = es.get(index=index, id=doc_id)
        except elasticsearch.NotFoundError:
            return None

        seq_no = current['_seq_no']
        primary_term = current['_primary_term']

        try:
            es.update(
                index=index,
                id=doc_id,
                if_seq_no=seq_no,
                if_primary_term=primary_term,
                body={'doc': updates},
            )
            return True
        except ConflictError:
            if attempt < max_retries - 1:
                time.sleep(0.05 * 2 ** attempt)
                continue
            raise
    return False


# ==========================================================================
# 4. BUILT-IN retry_on_conflict
# ==========================================================================

def increment_counter(index: str, doc_id: str):
    """Atomic increment with auto-retry."""
    es.update(
        index=index,
        id=doc_id,
        retry_on_conflict=10,
        body={
            'script': {
                'source': 'ctx._source.count = (ctx._source.count ?: 0) + 1',
                'lang': 'painless',
            },
            'upsert': {'count': 1},
        },
    )


# ==========================================================================
# 5. EXTERNAL VERSIONING (idempotent indexing)
# ==========================================================================

def index_with_external_version(index: str, doc_id: str, doc: dict, version: int):
    """Useful for CDC: use DB's updated_at_microseconds as version."""
    try:
        es.index(
            index=index,
            id=doc_id,
            version=version,
            version_type='external',
            document=doc,
        )
        return True
    except RequestError as e:
        if 'version_conflict_engine_exception' in str(e):
            # Out-of-order message — current version is newer, skip
            return False
        raise


# ==========================================================================
# 6. UPDATE_BY_QUERY WITH conflicts="proceed"
# ==========================================================================

def bulk_update_skip_conflicts(index: str, query: dict, script: str):
    """Update many docs — skip conflicting ones instead of aborting."""
    return es.update_by_query(
        index=index,
        body={
            'query': query,
            'script': {'source': script, 'lang': 'painless'},
        },
        conflicts='proceed',
        slices='auto',
        wait_for_completion=False,  # async
    )


# Check task progress
def task_status(task_id):
    return es.tasks.get(task_id=task_id)


# ==========================================================================
# 7. SAFE QUERIES (don't trip breakers)
# ==========================================================================

def safe_aggregation(index: str, field: str):
    """Bounded aggregation — won't OOM."""
    return es.search(
        index=index,
        size=0,                        # don't return docs
        track_total_hits=False,        # skip count
        aggregations={
            'by_field': {
                'terms': {
                    'field': field + '.keyword',  # keyword, not text
                    'size': 100,                  # cap buckets
                },
            },
        },
    )


def composite_aggregation_paginated(index: str, field: str, after_key: dict = None):
    """Composite aggregation — supports pagination of buckets."""
    agg_body = {
        'composite': {
            'sources': [{'fld': {'terms': {'field': field + '.keyword'}}}],
            'size': 1000,
        },
    }
    if after_key:
        agg_body['composite']['after'] = after_key

    result = es.search(
        index=index,
        size=0,
        aggregations={'paginated': agg_body},
    )
    return result['aggregations']['paginated']


# ==========================================================================
# 8. SEARCH_AFTER (deep pagination)
# ==========================================================================

def deep_paginate(index: str, page_size: int = 100):
    """Iterate ALL results without 'from' (which is slow + bounded)."""
    last_sort = None

    while True:
        body = {
            'size': page_size,
            'sort': [{'created_at': 'asc'}, {'_id': 'asc'}],
            'query': {'match_all': {}},
        }
        if last_sort:
            body['search_after'] = last_sort

        result = es.search(index=index, body=body)
        hits = result['hits']['hits']
        if not hits:
            break

        for hit in hits:
            yield hit

        last_sort = hits[-1]['sort']


# ==========================================================================
# 9. PIT (Point in Time) — consistent pagination
# ==========================================================================

def pit_paginate(index: str, page_size: int = 100):
    """Consistent snapshot for pagination — won't change mid-iteration."""
    pit = es.open_point_in_time(index=index, keep_alive='5m')
    pit_id = pit['id']

    try:
        last_sort = None
        while True:
            body = {
                'size': page_size,
                'sort': [{'created_at': 'asc'}, {'_id': 'asc'}],
                'pit': {'id': pit_id, 'keep_alive': '5m'},
                'query': {'match_all': {}},
            }
            if last_sort:
                body['search_after'] = last_sort

            result = es.search(body=body)
            hits = result['hits']['hits']
            if not hits:
                break

            for hit in hits:
                yield hit

            last_sort = hits[-1]['sort']
            pit_id = result.get('pit_id', pit_id)
    finally:
        es.close_point_in_time(body={'id': pit_id})


# ==========================================================================
# 10. SAFE FORCE MERGE (read-only first)
# ==========================================================================

def safe_force_merge(index: str):
    """Set read-only → merge → keep read-only."""
    # Make read-only
    es.indices.put_settings(
        index=index,
        settings={"index.blocks.write": True},
    )

    # Merge segments
    es.indices.forcemerge(
        index=index,
        max_num_segments=1,
        wait_for_completion=True,
    )

    # Refresh
    es.indices.refresh(index=index)

    # Optionally re-enable writes (or leave read-only for warm tier)
    # es.indices.put_settings(index=index, settings={"index.blocks.write": False})


# ==========================================================================
# 11. REINDEX with PARALLELISM
# ==========================================================================

def reindex_with_slices(source: str, dest: str):
    """Parallel reindex — much faster."""
    result = es.reindex(
        body={
            "source": {"index": source, "size": 1000},
            "dest": {"index": dest},
        },
        slices='auto',           # parallel chunks based on shards
        refresh=True,
        wait_for_completion=False,  # async task
    )
    task_id = result.get('task')
    return task_id


# Monitor
def monitor_reindex(task_id: str):
    while True:
        task = es.tasks.get(task_id=task_id)
        status = task['task']['status']
        completed = task['completed']
        if completed:
            print("Reindex done")
            break
        print(f"Reindex progress: {status['updated']}/{status['total']}")
        time.sleep(5)


# ==========================================================================
# 12. SLOW LOG CONFIG
# ==========================================================================

def configure_slow_logs(index: str):
    es.indices.put_settings(
        index=index,
        settings={
            "index.search.slowlog.threshold.query.warn": "5s",
            "index.search.slowlog.threshold.query.info": "2s",
            "index.search.slowlog.threshold.fetch.warn": "1s",
            "index.indexing.slowlog.threshold.index.warn": "1s",
        },
    )


# ==========================================================================
# 13. DETECT HOT QUERIES
# ==========================================================================

def find_long_running_queries():
    """Show currently running search tasks."""
    tasks = es.tasks.list(actions='*search*', detailed=True)
    for node_id, node in tasks['nodes'].items():
        for task_id, task in node['tasks'].items():
            running_ms = task['running_time_in_nanos'] / 1e6
            if running_ms > 5000:
                print(f"Long query ({running_ms:.0f}ms): {task['description'][:200]}")


def kill_long_query(task_id: str):
    """Cancel a running task."""
    es.tasks.cancel(task_id=task_id)


# ==========================================================================
# 14. PROD CHECKLIST
# ==========================================================================

PROD_CHECKLIST = """
[ ] Circuit breaker alerts (parent.tripped, fielddata.tripped)
[ ] Sort/aggregation on keyword fields (not text)
[ ] Bounded aggregations (terms size <= 1000)
[ ] track_total_hits=false when count unimportant
[ ] retry_on_conflict for counter-like updates
[ ] External versioning for CDC pipelines
[ ] Slow log enabled at 5s warn / 1s info
[ ] Force merge only on read-only indices
[ ] Reindex with slices='auto'
[ ] PIT for consistent deep pagination
[ ] from+size capped (use search_after for deep)
[ ] Monitor: search latency P95, indexing rate, JVM heap, fielddata usage
"""


# ==========================================================================
# 15. LAB DRIVER — force a real optimistic-concurrency conflict, then fix it
# ==========================================================================

LAB_INDEX = "occ_lab"
LAB_DOC_ID = "counter_1"


def conflicting_update(index: str, doc_id: str, correct_seq_no: int,
                        correct_primary_term: int, updates: dict):
    """
    Jaan-bujh kar GALAT if_seq_no bhejo — taaki ES version conflict detect
    kare aur ConflictError (HTTP 409) raise kare. Yeh optimistic concurrency
    control ka poora point hai: "maine jo doc padha tha, kya wo abhi bhi
    same hai?" — agar seq_no match nahi karta, ES update REJECT kar deta hai.
    """
    # ─────────────────────────────────────────────────────────────
    # TODO 6: neeche wrong_seq_no ko GALAT set karo (correct_seq_no NAHI —
    #   koi aisi value jo kabhi match nahi karegi, taaki conflict trigger ho).
    #   Hint: `wrong_seq_no = correct_seq_no + 999`
    wrong_seq_no = correct_seq_no  # <-- WRONG placeholder (yeh to sahi hi hai — conflict trigger NAHI karega), fix karo
    # ─────────────────────────────────────────────────────────────
    return es.update(
        index=index, id=doc_id,
        if_seq_no=wrong_seq_no, if_primary_term=correct_primary_term,
        doc=updates,
    )


def main() -> None:
    print("Elasticsearch OCC Lab — force a real version conflict, then fix it correctly")

    print("\n[1] Connect + create lab doc")
    if es.indices.exists(index=LAB_INDEX):
        es.indices.delete(index=LAB_INDEX)
    es.indices.create(index=LAB_INDEX)
    es.index(index=LAB_INDEX, id=LAB_DOC_ID, document={"count": 1}, refresh=True)

    current = es.get(index=LAB_INDEX, id=LAB_DOC_ID)
    seq_no, primary_term = current["_seq_no"], current["_primary_term"]
    print(f"    doc created: count=1, seq_no={seq_no}, primary_term={primary_term}")

    print("\n[2] Attempt update with a DELIBERATELY WRONG if_seq_no")
    conflict_raised = False
    try:
        conflicting_update(LAB_INDEX, LAB_DOC_ID, seq_no, primary_term, {"count": 2})
        print("    no exception raised — update went through (should NOT have)")
    except ConflictError as e:
        conflict_raised = True
        print(f"    caught ConflictError as expected: {e.meta.status if hasattr(e, 'meta') else e}")

    print("\n[3] Fetch FRESH seq_no/primary_term, then update CORRECTLY")
    fresh = es.get(index=LAB_INDEX, id=LAB_DOC_ID)
    fresh_seq_no, fresh_primary_term = fresh["_seq_no"], fresh["_primary_term"]
    print(f"    fresh: count={fresh['_source']['count']}, seq_no={fresh_seq_no}")
    es.update(
        index=LAB_INDEX, id=LAB_DOC_ID,
        if_seq_no=fresh_seq_no, if_primary_term=fresh_primary_term,
        doc={"count": 2},
    )
    final = es.get(index=LAB_INDEX, id=LAB_DOC_ID)
    print(f"    after correct update: count={final['_source']['count']}")

    print("\n" + "─" * 60)
    update_succeeded = final["_source"]["count"] == 2
    if conflict_raised and update_succeeded:
        print("✅ PASS — galat if_seq_no ne real ConflictError (409) diya, "
              "aur fresh seq_no ke saath correct update safalta se apply hua.")
    elif not conflict_raised:
        print(f"❌ FAIL — koi ConflictError raise nahi hua (count ab "
              f"{final['_source']['count']} hai). TODO 6 abhi unfilled hai — "
              "wrong_seq_no abhi bhi correct_seq_no ke barabar hai, isliye "
              "ES ko conflict dikhta hi nahi.")
    else:
        print(f"❌ FAIL — conflict to raise hua par final correct update "
              f"apply nahi hua (count={final['_source']['count']}, expected 2).")

    print(f"""
SOCH (bolke jawab do):
  1. if_seq_no + if_primary_term dono kyun chahiye, sirf seq_no kyun nahi?
     (Hint: primary_term shard leadership change track karta hai — seq_no
     akela reused ho sakta hai naye primary term me)
  2. retry_on_conflict (section 4, upar) OCC se kaise alag hai? Konsa
     use-case ke liye better hai — counter increment vs "read-modify-write
     business logic"?
  3. External versioning (section 5, upar) OCC se kaise alag hai — CDC
     pipeline me kyun better fit hai?
  4. Is lab me conflict manually trigger kiya — real production race
     condition kaise create hoti hai (do concurrent requests same doc pe)?
     update_with_occ() (section 3, upar) retry loop kyun zaroori hai us
     case me?
""")


if __name__ == "__main__":
    main()
