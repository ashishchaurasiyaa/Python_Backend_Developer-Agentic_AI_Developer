"""
MongoDB Replication & Read Preferences — Production Patterns
"""

from pymongo import MongoClient, ReadPreference, WriteConcern, ReadConcern
from pymongo.errors import AutoReconnect
from motor.motor_asyncio import AsyncIOMotorClient


# ==========================================================================
# 1. CONNECT TO REPLICA SET
# ==========================================================================

# Direct list of all members
client = MongoClient(
    "mongodb://host1:27017,host2:27017,host3:27017/?replicaSet=rs0",
    readPreference='primary',
    w='majority',
)


# Or via SRV records (recommended for DNS-based discovery)
# client = MongoClient("mongodb+srv://cluster0.example.com/?retryWrites=true&w=majority")


db = client.mydb


# ==========================================================================
# 2. READ PREFERENCES (per-collection)
# ==========================================================================

# Default — read from primary
critical_collection = db.get_collection('orders')


# Secondary preferred — fallback primary if no secondary
analytics_collection = db.get_collection(
    'analytics',
    read_preference=ReadPreference.SECONDARY_PREFERRED,
)


# Nearest — lowest latency
global_collection = db.get_collection(
    'global_data',
    read_preference=ReadPreference.NEAREST,
)


# With tag — read from specific region
us_east_only = db.get_collection(
    'data',
    read_preference=ReadPreference.SECONDARY_PREFERRED.with_tag_sets([
        {'region': 'us-east'},
    ]),
)


# ==========================================================================
# 3. PER-OPERATION READ PREFERENCE
# ==========================================================================

# Force primary for critical read
user = db.users.find_one({'_id': user_id})  # default = primary


# Force secondary
analytics_data = db.events.with_options(
    read_preference=ReadPreference.SECONDARY,
).find({'type': 'pageview'})


# ==========================================================================
# 4. WRITE CONCERNS
# ==========================================================================

# Write to majority (durable across failover)
db.orders.with_options(
    write_concern=WriteConcern('majority', wtimeout=10000, j=True),
).insert_one({...})


# Fire and forget (only primary ack)
db.metrics.with_options(
    write_concern=WriteConcern(w=1),
).insert_one({...})


# Wait for all replicas
db.critical.with_options(
    write_concern=WriteConcern(w='all', wtimeout=30000),
).insert_one({...})


# Disable acknowledgement entirely (DANGEROUS for non-trivial data)
db.logs.with_options(
    write_concern=WriteConcern(w=0),
).insert_one({...})


# ==========================================================================
# 5. CAUSAL CONSISTENCY SESSION (read your own writes)
# ==========================================================================

def write_then_read_consistent():
    """Even when reading from secondary, see own writes."""
    with client.start_session(causal_consistency=True) as session:
        db.users.insert_one(
            {'_id': 'alice', 'balance': 100},
            session=session,
        )

        # Even from secondary, this sees the insert
        user = db.users.with_options(
            read_preference=ReadPreference.SECONDARY,
        ).find_one({'_id': 'alice'}, session=session)

        assert user is not None


# ==========================================================================
# 6. RETRYABLE WRITES (handle primary stepdown)
# ==========================================================================

# Default for replica sets — driver retries once on transient errors
client_retry = MongoClient(
    "mongodb://...",
    retryWrites=True,    # default in modern pymongo
    retryReads=True,
)


# Custom retry for manual operations
import time


def retry_op(func, max_attempts=3):
    for attempt in range(max_attempts):
        try:
            return func()
        except AutoReconnect:
            if attempt < max_attempts - 1:
                time.sleep(0.5 * 2 ** attempt)
                continue
            raise


# ==========================================================================
# 7. REPLICA SET STATUS MONITORING
# ==========================================================================

def get_rs_status():
    """Get replica set health."""
    admin = client.admin
    status = admin.command('replSetGetStatus')

    print(f"Set: {status['set']}")
    print(f"Date: {status['date']}")

    for member in status['members']:
        print(f"  {member['name']:<30} {member['stateStr']:<10} health={member['health']}")
        if 'optimeDate' in member:
            from datetime import datetime
            lag = (status['date'] - member['optimeDate']).total_seconds()
            print(f"    Lag: {lag:.1f}s")


def check_replication_lag(threshold_seconds: int = 10):
    """Alert if any secondary lagging too much."""
    status = client.admin.command('replSetGetStatus')

    primary_optime = None
    for m in status['members']:
        if m['stateStr'] == 'PRIMARY':
            primary_optime = m['optimeDate']
            break

    if not primary_optime:
        return {'ok': False, 'error': 'No primary'}

    issues = []
    for m in status['members']:
        if m['stateStr'] == 'SECONDARY' and 'optimeDate' in m:
            lag = (primary_optime - m['optimeDate']).total_seconds()
            if lag > threshold_seconds:
                issues.append({'name': m['name'], 'lag_seconds': lag})

    return {'ok': not issues, 'issues': issues}


# ==========================================================================
# 8. SECONDARY-ONLY READS for analytics
# ==========================================================================

class AnalyticsClient:
    """Always reads from secondaries — won't impact primary load."""

    def __init__(self, conn_string):
        self.client = MongoClient(
            conn_string,
            read_preference='secondary',
            readConcern=ReadConcern('majority'),
        )
        self.db = self.client.mydb

    def report_users_per_country(self):
        return list(self.db.users.aggregate([
            {'$group': {'_id': '$country', 'count': {'$sum': 1}}},
        ]))


# ==========================================================================
# 9. HIDDEN MEMBER FOR BACKUPS
# ==========================================================================

BACKUP_SETUP = """
# Add hidden member for backup (no client traffic)
rs.add({
    host: "backup-host:27017",
    priority: 0,
    hidden: true,
    votes: 1,
    tags: { role: "backup" }
})

# Run mongodump on hidden member — doesn't affect production
mongodump --host backup-host:27017 --out /backups/$(date +%Y%m%d)


# Or use file-system snapshot of dbPath after fsync lock
mongosh --host backup-host:27017 --eval "db.fsyncLock()"
# ... take EBS snapshot or rsync ...
mongosh --host backup-host:27017 --eval "db.fsyncUnlock()"
"""


# ==========================================================================
# 10. DELAYED MEMBER FOR DISASTER RECOVERY
# ==========================================================================

DELAYED_MEMBER_SETUP = """
# Add delayed member — applies oplog 1 hour behind
rs.add({
    host: "delayed-host:27017",
    priority: 0,
    hidden: true,
    votes: 1,
    slaveDelay: 3600   # 1 hour delay
})


# Use case: "We accidentally dropped a collection at 14:00"
# - At 14:30, delayed node hasn't applied the drop yet (only at 15:00)
# - Failover to delayed node to recover
# - Restore the collection from it
# - Then resync the rest of the cluster
"""


# ==========================================================================
# 11. WRITE-AFTER-READ + WRITE CONCERN MAJORITY
# ==========================================================================

def safe_critical_write(user_id, amount):
    """High-durability write — guaranteed to survive failover."""
    result = db.accounts.with_options(
        write_concern=WriteConcern('majority', wtimeout=10000, j=True),
        read_concern=ReadConcern('majority'),
    ).update_one(
        {'_id': user_id, 'balance': {'$gte': amount}},
        {'$inc': {'balance': -amount}},
    )

    if result.matched_count == 0:
        raise ValueError("Insufficient funds")

    # Even if primary crashes RIGHT after this returns, write is safe
    return True


# ==========================================================================
# 12. ASYNC EXAMPLE (motor)
# ==========================================================================

async_client = AsyncIOMotorClient(
    "mongodb://host1,host2,host3/?replicaSet=rs0",
    readPreference='secondaryPreferred',
    w='majority',
)
async_db = async_client.mydb


async def async_read_with_session():
    async with await async_client.start_session(causal_consistency=True) as session:
        await async_db.users.insert_one(
            {'_id': 'bob', 'balance': 50},
            session=session,
        )
        # Reads from secondary but sees the write
        user = await async_db.users.find_one({'_id': 'bob'}, session=session)


# ==========================================================================
# 13. CONFIGURATION REFERENCE
# ==========================================================================

CONNECTION_STRING_OPTIONS = """
Common URI options:

mongodb://host1,host2,host3/?
    replicaSet=rs0
    &readPreference=secondaryPreferred
    &readConcernLevel=majority
    &w=majority
    &wtimeoutMS=10000
    &retryWrites=true
    &retryReads=true
    &maxPoolSize=100
    &minPoolSize=10
    &maxIdleTimeMS=60000
    &serverSelectionTimeoutMS=10000
    &connectTimeoutMS=20000
    &socketTimeoutMS=30000
    &localThresholdMS=15
    &heartbeatFrequencyMS=10000
    &appName=myapp
"""
