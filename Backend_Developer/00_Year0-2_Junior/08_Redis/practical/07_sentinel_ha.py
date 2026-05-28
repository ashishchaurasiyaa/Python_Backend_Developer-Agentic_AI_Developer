"""
Redis Sentinel — Production Patterns
"""

from redis.sentinel import Sentinel
import redis


# ==========================================================================
# 1. CONNECT VIA SENTINEL (auto-discovers master)
# ==========================================================================

sentinel = Sentinel(
    [
        ('sentinel-1.internal', 26379),
        ('sentinel-2.internal', 26379),
        ('sentinel-3.internal', 26379),
    ],
    socket_timeout=0.5,
    sentinel_kwargs={'socket_timeout': 0.5},
)


# Master connection (writes go here)
master = sentinel.master_for(
    'mymaster',
    socket_timeout=0.5,
    decode_responses=True,
    password='your-password',
)


# Replica connection (reads can go here)
replica = sentinel.slave_for(
    'mymaster',
    socket_timeout=0.5,
    decode_responses=True,
    password='your-password',
)


# Use like normal Redis
master.set('key', 'value')
val = replica.get('key')


# ==========================================================================
# 2. MASTER DISCOVERY (manual)
# ==========================================================================

def get_current_master():
    """Query Sentinel for current master's host/port."""
    host, port = sentinel.discover_master('mymaster')
    return host, port


def get_replica_list():
    """List of (host, port) replicas."""
    return sentinel.discover_slaves('mymaster')


# ==========================================================================
# 3. AUTO-RECONNECT ON FAILOVER
# ==========================================================================

import time


def resilient_set(key, value, max_retries=3):
    for attempt in range(max_retries):
        try:
            master_conn = sentinel.master_for('mymaster', socket_timeout=1)
            return master_conn.set(key, value)
        except (redis.ConnectionError, redis.TimeoutError):
            if attempt < max_retries - 1:
                time.sleep(0.5 * 2 ** attempt)
                continue
            raise


# ==========================================================================
# 4. READ-WRITE SPLIT PATTERN
# ==========================================================================

class RedisStore:
    """Reads from replica, writes to master — automatic failover."""

    def __init__(self, sentinel_hosts, service_name):
        self._sentinel = Sentinel(sentinel_hosts, socket_timeout=0.5)
        self._service = service_name

    @property
    def master(self):
        return self._sentinel.master_for(self._service, decode_responses=True)

    @property
    def replica(self):
        return self._sentinel.slave_for(self._service, decode_responses=True)

    def set(self, key, value, **kwargs):
        return self.master.set(key, value, **kwargs)

    def get(self, key):
        return self.replica.get(key)

    def get_consistent(self, key):
        """For critical reads — hit master, no stale data."""
        return self.master.get(key)


store = RedisStore(
    [('sentinel-1', 26379), ('sentinel-2', 26379), ('sentinel-3', 26379)],
    'mymaster',
)


# ==========================================================================
# 5. SENTINEL ADMIN COMMANDS
# ==========================================================================

def sentinel_status():
    """Query Sentinel for current cluster state."""
    s = redis.Redis(host='sentinel-1', port=26379, decode_responses=True)

    # Master info
    masters = s.execute_command('SENTINEL', 'MASTERS')
    for m in masters:
        info = dict(zip(m[::2], m[1::2]))
        print(f"Master: {info['name']} {info['ip']}:{info['port']} flags={info['flags']}")

    # Replicas for master
    slaves = s.execute_command('SENTINEL', 'SLAVES', 'mymaster')
    for slv in slaves:
        info = dict(zip(slv[::2], slv[1::2]))
        print(f"  Replica: {info['ip']}:{info['port']} flags={info['flags']}")

    # Other sentinels
    sentinels = s.execute_command('SENTINEL', 'SENTINELS', 'mymaster')
    for sen in sentinels:
        info = dict(zip(sen[::2], sen[1::2]))
        print(f"  Sentinel: {info['ip']}:{info['port']}")


# ==========================================================================
# 6. SUBSCRIBE TO FAILOVER EVENTS
# ==========================================================================

def listen_failover_events():
    """Subscribe to Sentinel events for monitoring."""
    s = redis.Redis(host='sentinel-1', port=26379, decode_responses=True)
    pubsub = s.pubsub()
    pubsub.subscribe('+sdown', '+odown', '+switch-master', '+failover-state-end')

    for msg in pubsub.listen():
        if msg['type'] == 'message':
            print(f"EVENT: {msg['channel']} - {msg['data']}")
            # Send to monitoring/alerts


# ==========================================================================
# 7. SENTINEL CONFIG (sentinel.conf)
# ==========================================================================

SENTINEL_CONF = """
port 26379
daemonize yes
logfile /var/log/redis/sentinel.log

# Watch master 'mymaster' at IP:PORT, quorum=2
sentinel monitor mymaster 10.0.0.1 6379 2

# Master considered down after 5s of failed PINGs
sentinel down-after-milliseconds mymaster 5000

# Failover process timeout
sentinel failover-timeout mymaster 30000

# Parallel resyncs during failover (lower = less spike, slower)
sentinel parallel-syncs mymaster 1

# Auth (if master uses password)
sentinel auth-pass mymaster YOUR_REDIS_PASSWORD

# Optional notifications via script (e.g. PagerDuty)
# sentinel notification-script mymaster /usr/local/bin/notify.sh

# Replica priority (lower = preferred for promotion; 0 = never promote)
# Set on each replica's redis.conf
# replica-priority 100
"""


# ==========================================================================
# 8. REDIS CONFIG for HA (on master + replicas)
# ==========================================================================

REDIS_HA_CONF = """
# redis.conf on master

# Don't accept writes if too few replicas connected (split-brain protection)
min-replicas-to-write 1
min-replicas-max-lag 10

# Persistence (don't lose data on failover)
appendonly yes
appendfsync everysec

# Listen on all interfaces for replicas
bind 0.0.0.0
protected-mode no

requirepass YOUR_PASSWORD
masterauth YOUR_PASSWORD


# redis.conf on each replica
replicaof 10.0.0.1 6379
replica-priority 100   # 0 = never promote, lower = preferred
masterauth YOUR_PASSWORD
requirepass YOUR_PASSWORD
"""


# ==========================================================================
# 9. APP-LEVEL FAILOVER HANDLER
# ==========================================================================

import logging


log = logging.getLogger(__name__)


class FailoverAwareRedis:
    """Wrapper that handles connection errors + master rediscovery."""

    def __init__(self, sentinel_hosts, service_name, password=None):
        self._sentinel = Sentinel(
            sentinel_hosts,
            sentinel_kwargs={'socket_timeout': 1, 'password': password},
        )
        self._service = service_name
        self._password = password
        self._master = None

    def _get_master(self):
        if self._master is None:
            self._master = self._sentinel.master_for(
                self._service,
                socket_timeout=1,
                password=self._password,
                decode_responses=True,
            )
        return self._master

    def _invalidate(self):
        log.warning("Invalidating master connection — failover detected")
        self._master = None

    def call(self, method_name, *args, max_retries=3, **kwargs):
        for attempt in range(max_retries):
            try:
                master = self._get_master()
                return getattr(master, method_name)(*args, **kwargs)
            except (redis.ConnectionError, redis.TimeoutError) as e:
                self._invalidate()
                if attempt < max_retries - 1:
                    log.warning(f"Retry {attempt + 1}: {e}")
                    time.sleep(0.5 * 2 ** attempt)
                    continue
                raise


# Usage
r = FailoverAwareRedis(
    [('sentinel-1', 26379), ('sentinel-2', 26379), ('sentinel-3', 26379)],
    'mymaster',
)
# r.call('set', 'k', 'v')


# ==========================================================================
# 10. PROD CHECKLIST
# ==========================================================================

PROD_CHECKLIST = """
[ ] 3+ Sentinels (quorum 2) on independent hosts
[ ] Sentinel not on same host as Redis master
[ ] AOF on master + all replicas
[ ] min-replicas-to-write + min-replicas-max-lag set on master
[ ] Replica priorities set (preferred replica = lower number)
[ ] Sentinel auth-pass + Redis requirepass + masterauth set
[ ] App uses Sentinel-aware client (not direct master IP)
[ ] Monitoring: subscribe to +sdown, +odown, +switch-master events
[ ] Alerts: replication lag, failover events, sentinel connection loss
[ ] Tested failover scenario in staging (kill master, verify auto-promotion)
[ ] Documented runbook for unplanned dual-master split-brain
"""
