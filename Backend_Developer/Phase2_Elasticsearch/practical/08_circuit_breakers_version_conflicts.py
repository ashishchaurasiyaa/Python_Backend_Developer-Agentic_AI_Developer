"""
ES Circuit Breakers & Version Conflicts — Production Patterns
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
