"""
Redis Persistence & Memory — Production Patterns
"""

import redis
import gzip
import json
import time


r = redis.Redis(host='localhost', port=6379, decode_responses=False)


# ==========================================================================
# 1. CHECK PERSISTENCE STATE
# ==========================================================================

def check_persistence():
    info = r.info('persistence')
    print(f"AOF enabled: {info['aof_enabled']}")
    print(f"AOF current size: {info['aof_current_size']} bytes")
    print(f"AOF last rewrite time: {info['aof_last_rewrite_time_sec']}s")
    print(f"RDB last save: {time.ctime(info['rdb_last_save_time'])}")
    print(f"RDB last bgsave status: {info['rdb_last_bgsave_status']}")
    print(f"RDB changes since last save: {info['rdb_changes_since_last_save']}")


# Trigger backup
def trigger_backup():
    """Background save — non-blocking."""
    r.bgsave()
    while True:
        info = r.info('persistence')
        if info['rdb_bgsave_in_progress'] == 0:
            print(f"Backup done: {info['rdb_last_bgsave_status']}")
            break
        time.sleep(1)


def trigger_aof_rewrite():
    """Compact AOF in background."""
    r.bgrewriteaof()


# ==========================================================================
# 2. MEMORY INSPECTION
# ==========================================================================

def memory_overview():
    info = r.info('memory')
    print(f"Used memory: {info['used_memory_human']}")
    print(f"Peak: {info['used_memory_peak_human']}")
    print(f"RSS: {info['used_memory_rss_human']}")
    print(f"Fragmentation: {info['mem_fragmentation_ratio']:.2f}")
    print(f"Maxmemory: {info.get('maxmemory_human', 'unlimited')}")
    print(f"Policy: {info['maxmemory_policy']}")

    used = info['used_memory']
    maxmem = info.get('maxmemory', 0)
    if maxmem:
        pct = used * 100 / maxmem
        print(f"Memory used: {pct:.1f}%")
        if pct > 80:
            print("WARNING: above 80%")


def memory_usage_of_key(key):
    """Bytes used by one key."""
    return r.memory_usage(key)


# ==========================================================================
# 3. BIG KEYS DETECTION
# ==========================================================================

def find_big_keys(top_n=10, sample_limit=10000):
    """Scan + find largest keys."""
    largest = []  # (size, type, key)

    count = 0
    for key in r.scan_iter(count=100):
        if count >= sample_limit:
            break
        try:
            size = r.memory_usage(key)
            ktype = r.type(key).decode() if isinstance(r.type(key), bytes) else r.type(key)
            largest.append((size, ktype, key))
            largest.sort(reverse=True)
            largest = largest[:top_n]
            count += 1
        except Exception:
            continue

    return largest


def length_of_collection_keys(key, ktype):
    """For lists/sets/hashes/zsets — element count."""
    if ktype == 'list':
        return r.llen(key)
    if ktype == 'set':
        return r.scard(key)
    if ktype == 'hash':
        return r.hlen(key)
    if ktype == 'zset':
        return r.zcard(key)
    if ktype == 'stream':
        return r.xlen(key)
    return 0


# ==========================================================================
# 4. COMPRESSION FOR LARGE VALUES
# ==========================================================================

def compressed_set(key, value, ttl=None, threshold=1024):
    """Auto-compress values > threshold."""
    raw = json.dumps(value).encode()
    if len(raw) > threshold:
        data = b'\x01' + gzip.compress(raw, compresslevel=6)
    else:
        data = b'\x00' + raw
    if ttl:
        r.set(key, data, ex=ttl)
    else:
        r.set(key, data)


def compressed_get(key):
    data = r.get(key)
    if not data:
        return None
    if data[0:1] == b'\x01':
        raw = gzip.decompress(data[1:])
    else:
        raw = data[1:]
    return json.loads(raw)


# ==========================================================================
# 5. HASH-BASED RECORD STORAGE (memory-efficient)
# ==========================================================================

# BAD — many keys (more overhead)
def bad_user_storage(user_id, name, email, age):
    r.set(f'user:{user_id}:name', name)
    r.set(f'user:{user_id}:email', email)
    r.set(f'user:{user_id}:age', age)


# GOOD — single hash (uses listpack encoding if small)
def good_user_storage(user_id, name, email, age):
    r.hset(f'user:{user_id}', mapping={
        'name': name,
        'email': email,
        'age': age,
    })


# Bucketed for memory: group N users into one hash
def bucketed_storage(user_id, name, email, age):
    bucket = user_id // 1000
    r.hset(f'users:{bucket}', f'{user_id}:name', name)
    r.hset(f'users:{bucket}', f'{user_id}:email', email)


# ==========================================================================
# 6. TTL RANDOMIZATION (avoid bursty eviction)
# ==========================================================================

import random


def set_with_jitter(key, value, base_ttl, jitter_pct=0.2):
    """Add random jitter to TTL to spread expirations."""
    jitter = int(base_ttl * jitter_pct * (random.random() - 0.5))
    ttl = base_ttl + jitter
    r.set(key, value, ex=ttl)


# ==========================================================================
# 7. CHECK ENCODING TYPE
# ==========================================================================

def check_encoding(key):
    """See which encoding Redis uses for this key."""
    enc = r.object('encoding', key)
    return enc.decode() if isinstance(enc, bytes) else enc


# Encodings: ziplist, listpack, intset, hashtable, skiplist, raw, embstr
# Listpack/ziplist = memory-efficient small forms
# Hashtable/skiplist = larger, faster random access


# ==========================================================================
# 8. CONFIG SET TUNING (runtime, no restart)
# ==========================================================================

# Convert to compact encoding by tuning thresholds
r.config_set('hash-max-listpack-entries', '256')
r.config_set('hash-max-listpack-value', '128')
r.config_set('zset-max-listpack-entries', '256')
r.config_set('list-max-listpack-size', '-2')  # 8KB max


# Eviction policy
r.config_set('maxmemory', '4gb')
r.config_set('maxmemory-policy', 'allkeys-lru')
r.config_set('maxmemory-samples', '10')  # better LRU approximation


# Persistence
r.config_set('save', '3600 1 300 100 60 10000')
r.config_set('appendonly', 'yes')
r.config_set('appendfsync', 'everysec')


# Get current config
configs = r.config_get('maxmemory*')


# ==========================================================================
# 9. DEFRAG (manual + automatic)
# ==========================================================================

def defrag_status():
    info = r.info('memory')
    return {
        'active_defrag_running': info.get('active_defrag_running', 0),
        'mem_fragmentation_ratio': info.get('mem_fragmentation_ratio'),
    }


def enable_active_defrag():
    """Background defrag (CPU cost, but reclaims memory)."""
    r.config_set('activedefrag', 'yes')
    r.config_set('active-defrag-threshold-lower', '10')  # %  fragmentation to start
    r.config_set('active-defrag-threshold-upper', '100')  # % to max effort
    r.config_set('active-defrag-cycle-min', '5')  # CPU % min
    r.config_set('active-defrag-cycle-max', '50')  # CPU % max


def manual_purge():
    """Tell allocator to release fragmented memory."""
    r.memory_purge()


# ==========================================================================
# 10. SAMPLE PROD CONFIGS
# ==========================================================================

CACHE_CONFIG = """
# /etc/redis/redis.conf — Pure cache (data regeneratable)

bind 0.0.0.0
port 6379
protected-mode yes
requirepass strong-password

maxmemory 8gb
maxmemory-policy allkeys-lru
maxmemory-samples 10

# No persistence — fast
save ""
appendonly no

# Faster slow ops
hash-max-listpack-entries 256
hash-max-listpack-value 128
list-max-listpack-size -2
zset-max-listpack-entries 256
"""


SESSION_STORE_CONFIG = """
# /etc/redis/redis.conf — Session store

maxmemory 4gb
maxmemory-policy volatile-lru
appendonly yes
appendfsync everysec
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb

# Hybrid persistence (RDB preamble in AOF)
aof-use-rdb-preamble yes

save 3600 1
save 300 100
"""


CRITICAL_DATA_CONFIG = """
# /etc/redis/redis.conf — Critical state (financial)

maxmemory 16gb
maxmemory-policy noeviction   # fail writes when full, alert

appendonly yes
appendfsync always            # zero data loss
no-appendfsync-on-rewrite no  # full safety during rewrite

# Both AOF + RDB
save 1800 1
save 300 100

# Replication for HA
# min-replicas-to-write 1
# min-replicas-max-lag 10
"""
