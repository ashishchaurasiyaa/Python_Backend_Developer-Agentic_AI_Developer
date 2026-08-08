"""
MongoDB Data Modeling — Production Patterns

Run: python 08_data_modeling_patterns.py
Prereq: docker compose up -d   (see docker-compose.yml in this folder —
        transactions/change streams nahi chahiye is file ko, par consistency
        ke liye wahi lab instance use karte hain)
"""

import os
from datetime import datetime, timedelta
import random

from pymongo import MongoClient, ASCENDING, DESCENDING, TEXT


MONGO_URI = os.getenv("MONGO_LAB_URI", "mongodb://localhost:27018/?directConnection=true")
client = MongoClient(MONGO_URI)
db = client.mydb


# ==========================================================================
# 1. EMBEDDED vs REFERENCED
# ==========================================================================

# Embedded — 1:few (max bounded)
def create_user_embedded():
    db.users.insert_one({
        '_id': 'alice',
        'name': 'Alice',
        'email': 'a@example.com',
        # Embedded addresses (max ~5 per user)
        'addresses': [
            {'type': 'home', 'street': '123 Main', 'city': 'NY'},
            {'type': 'work', 'street': '456 Oak', 'city': 'LA'},
        ],
    })


# Referenced — 1:many (unbounded)
def create_post_referenced():
    user_id = 'alice'
    db.posts.insert_one({
        '_id': 'post_1',
        'user_id': user_id,         # reference
        'body': 'Hello world',
        'created_at': datetime.utcnow(),
    })


# Extended Reference — cache some fields
def create_post_extended_ref():
    user = db.users.find_one({'_id': 'alice'})
    db.posts.insert_one({
        '_id': 'post_1',
        'author': {
            'id': user['_id'],
            'name': user['name'],     # cached (denormalized)
            'avatar': user.get('avatar_url'),
        },
        'body': '...',
    })
# On user name change: update all their posts (or accept staleness)


# ==========================================================================
# 2. BUCKET PATTERN (time-series)
# ==========================================================================

def insert_sensor_reading_bucketed(device_id: str, value: float):
    """Group readings into hourly buckets."""
    now = datetime.utcnow()
    bucket_start = now.replace(minute=0, second=0, microsecond=0)

    db.sensor_data.update_one(
        {
            'device_id': device_id,
            'bucket_start': bucket_start,
        },
        {
            '$push': {
                'readings': {
                    'ts': now,
                    'value': value,
                },
            },
            '$inc': {'count': 1},
            '$min': {'min_value': value},
            '$max': {'max_value': value},
        },
        upsert=True,
    )


# Indexes for bucketed time-series
db.sensor_data.create_index([('device_id', 1), ('bucket_start', -1)])


# Or use MongoDB 5+ Time-Series Collection
"""
db.create_collection(
    'metrics',
    timeseries={
        'timeField': 'ts',
        'metaField': 'device_id',
        'granularity': 'hours',
    },
)

db.metrics.insert_one({
    'ts': datetime.utcnow(),
    'device_id': 'sensor_1',
    'temp': 22.5,
    'humidity': 45,
})
# MongoDB handles bucketing internally
"""


# ==========================================================================
# 3. SUBSET PATTERN (avoid huge embedded arrays)
# ==========================================================================

def add_review_with_subset(product_id: str, review: dict):
    """Add review — embed top 5 in product, store all in reviews collection."""

    # Insert into reviews collection
    db.reviews.insert_one({**review, 'product_id': product_id})

    # Update product with top reviews (most recent 5)
    db.products.update_one(
        {'_id': product_id},
        {
            '$push': {
                'top_reviews': {
                    '$each': [review],
                    '$slice': -5,   # keep last 5
                    '$sort': {'rating': -1},
                },
            },
            '$inc': {'review_count': 1, 'total_rating': review['rating']},
        },
    )
# Recompute avg_rating periodically: total_rating / review_count


# ==========================================================================
# 4. COMPUTED PATTERN (denormalized counters)
# ==========================================================================

def add_comment_with_counters(post_id: str, comment: dict):
    db.comments.insert_one({**comment, 'post_id': post_id})

    # Update post counter atomically
    db.posts.update_one(
        {'_id': post_id},
        {
            '$inc': {'comment_count': 1},
            '$set': {'last_comment_at': datetime.utcnow()},
        },
    )


# ==========================================================================
# 5. TREE: ARRAY OF ANCESTORS
# ==========================================================================

def insert_category(cat_id, name, parent_id=None):
    parent = db.categories.find_one({'_id': parent_id}) if parent_id else None
    ancestors = (parent.get('ancestors', []) + [parent_id]) if parent else []
    db.categories.insert_one({
        '_id': cat_id,
        'name': name,
        'parent': parent_id,
        'ancestors': ancestors,
    })


def find_all_descendants(cat_id):
    return list(db.categories.find({'ancestors': cat_id}))


def find_root_path(cat_id):
    cat = db.categories.find_one({'_id': cat_id})
    if not cat:
        return []
    return list(db.categories.find({'_id': {'$in': cat['ancestors']}}).sort('_id', 1))


# Index for descendants query
db.categories.create_index([('ancestors', 1)])


# ==========================================================================
# 6. MATERIALIZED PATH
# ==========================================================================

def insert_node_materialized(node_id, name, parent_path=''):
    """Path like ',root,a,b,'"""
    path = f'{parent_path}{node_id},'
    db.tree.insert_one({
        '_id': node_id,
        'name': name,
        'path': path,
    })


def find_descendants_materialized(node_id):
    return list(db.tree.find({'path': {'$regex': f',{node_id},'}}))


db.tree.create_index([('path', 1)])


# ==========================================================================
# 7. ATTRIBUTE PATTERN (sparse fields)
# ==========================================================================

def create_product_attrs(product_id, name, attrs):
    """Attrs as key-value array — supports any property."""
    db.products.insert_one({
        '_id': product_id,
        'name': name,
        'attributes': [{'k': k, 'v': v} for k, v in attrs.items()],
    })


# Index on attributes
db.products.create_index([('attributes.k', 1), ('attributes.v', 1)])


# Query
def find_by_attribute(key, value):
    return list(db.products.find({
        'attributes': {'$elemMatch': {'k': key, 'v': value}},
    }))


# create_product_attrs('p1', 'Laptop', {'cpu': 'i9', 'ram': 32, 'screen': 15})
# find_by_attribute('ram', 32)


# ==========================================================================
# 8. POLYMORPHIC SCHEMA
# ==========================================================================

def log_event(event_type, **fields):
    """One collection for all event types."""
    db.events.insert_one({
        'type': event_type,
        'timestamp': datetime.utcnow(),
        **fields,
    })


# log_event('pageview', url='/home', user_id='alice')
# log_event('purchase', order_id='X', amount=99, user_id='alice')
# log_event('click', element='btn-buy', user_id='alice')

# Index for type-specific queries
db.events.create_index([('type', 1), ('timestamp', -1)])
db.events.create_index([('user_id', 1), ('timestamp', -1)])


# ==========================================================================
# 9. OUTLIER PATTERN
# ==========================================================================

NORMAL_FOLLOWERS_LIMIT = 5000


def add_follower(user_id, follower_id):
    """Embed up to limit; overflow to extras collection."""
    user = db.users.find_one({'_id': user_id}, {'follower_count': 1, 'has_extras': 1})

    if user.get('follower_count', 0) < NORMAL_FOLLOWERS_LIMIT:
        # Embed
        db.users.update_one(
            {'_id': user_id},
            {
                '$push': {'followers': follower_id},
                '$inc': {'follower_count': 1},
            },
        )
    else:
        # Mark as outlier, store extras separately
        db.users.update_one(
            {'_id': user_id},
            {
                '$inc': {'follower_count': 1},
                '$set': {'has_extras': True},
            },
        )
        db.follower_extras.update_one(
            {'_id': user_id},
            {'$push': {'followers': follower_id}},
            upsert=True,
        )


# ==========================================================================
# 10. SCHEMA VERSIONING + MIGRATION
# ==========================================================================

def read_user(user_id):
    """Handle both old and new schema."""
    user = db.users.find_one({'_id': user_id})
    if not user:
        return None

    version = user.get('schema_version', 1)
    if version == 1:
        # Old shape — translate to new
        return {
            **user,
            'address': {
                'street': user.get('addr'),
                'city': user.get('city'),
            },
        }
    return user  # already v2


def migrate_users_to_v2(batch_size=1000):
    """Background migration."""
    while True:
        batch = list(db.users.find(
            {'schema_version': {'$ne': 2}},
            limit=batch_size,
        ))
        if not batch:
            break
        for user in batch:
            db.users.update_one(
                {'_id': user['_id']},
                {
                    '$set': {
                        'address': {
                            'street': user.get('addr'),
                            'city': user.get('city'),
                        },
                        'schema_version': 2,
                    },
                    '$unset': {'addr': '', 'city': ''},
                },
            )


# ==========================================================================
# 11. DECISION HELPER
# ==========================================================================

def schema_decision_tree(access_pattern: str, child_size: str, sharing: str):
    """Quick decision helper."""
    print(f"Access pattern: {access_pattern}")
    print(f"Child data size: {child_size}")
    print(f"Sharing: {sharing}")

    if access_pattern == 'together' and child_size == 'small' and sharing == 'no':
        return 'EMBED'
    if child_size == 'huge':
        return 'REFERENCE (with subset if hot path)'
    if sharing == 'yes':
        return 'REFERENCE'
    if child_size == 'unbounded':
        return 'REFERENCE + bucket pattern'
    return 'EMBED with extended reference'


# ==========================================================================
# 12. LAB DRIVER — pick embed vs reference, then PROVE the doc shape matches
# ==========================================================================

def choose_pattern(scenario: str) -> str:
    """
    Given an access-pattern scenario, return 'embed' or 'reference'.

    Scenarios:
      'post_comments'   — comments on a blog post: bounded (max ~50), almost
                           always read TOGETHER with the post.
      'customer_orders' — ALL orders a customer has EVER placed: unbounded,
                           keeps growing forever, rarely needs to load with
                           the customer profile.
    """
    if scenario == 'post_comments':
        return 'embed'
    elif scenario == 'customer_orders':
        # ─────────────────────────────────────────────────────────
        # TODO 3: 'customer_orders' unbounded hai — 'post_comments' jaisa
        #   bounded (~50) nahi. Correct pattern kya hai?
        #   Hint: unbounded array = document 16MB limit todne ka risk +
        #   MongoDB perf degrade jab array bada ho jaata hai. Separate
        #   collection + foreign key (customer_id) use karo.
        return 'embed'  # <-- WRONG placeholder, fix karo ('embed' or 'reference')
        # ─────────────────────────────────────────────────────────
    else:
        raise ValueError(f"unknown scenario: {scenario}")


def apply_pattern(scenario: str, pattern: str) -> None:
    """Chosen pattern ke hisaab se actual lab data likho — verification isi shape ko check karega."""
    if scenario == 'post_comments':
        if pattern == 'embed':
            db.posts_lab.update_one(
                {'_id': 'post_1'},
                {'$push': {'comments': {'text': 'nice post!', 'at': datetime.utcnow()}}},
                upsert=True,
            )
        else:
            db.comments_lab.insert_one({'post_id': 'post_1', 'text': 'nice post!'})
    elif scenario == 'customer_orders':
        if pattern == 'embed':
            db.customers_lab.update_one(
                {'_id': 'cust_1'},
                {'$push': {'orders': {'order_id': 'o1', 'amount': 99}}},
                upsert=True,
            )
        else:
            db.orders_lab.insert_one({'customer_id': 'cust_1', 'order_id': 'o1', 'amount': 99})


def main() -> None:
    print("MongoDB Data Modeling Lab — embed vs reference, per access pattern")

    print("\n[1] Connect + clean lab collections")
    client.admin.command('ping')
    for coll in ('posts_lab', 'comments_lab', 'customers_lab', 'orders_lab'):
        db[coll].drop()

    print("\n[2] Scenario: post_comments (bounded, read together)")
    p1 = choose_pattern('post_comments')
    print(f"    choose_pattern() → '{p1}'")
    apply_pattern('post_comments', p1)

    print("\n[3] Scenario: customer_orders (unbounded, rarely loaded together)")
    p2 = choose_pattern('customer_orders')
    print(f"    choose_pattern() → '{p2}'")
    apply_pattern('customer_orders', p2)

    print("\n" + "─" * 60)
    post = db.posts_lab.find_one({'_id': 'post_1'})
    post_ok = (p1 == 'embed' and post is not None
               and 'comments' in post and len(post['comments']) > 0)

    customer_doc = db.customers_lab.find_one({'_id': 'cust_1'})
    orders_separate = list(db.orders_lab.find({'customer_id': 'cust_1'}))
    orders_ok = (p2 == 'reference' and len(orders_separate) > 0
                 and (customer_doc is None or 'orders' not in customer_doc))

    if post_ok and orders_ok:
        print("✅ PASS — post_comments EMBED hua (bounded array directly on "
              "post doc), customer_orders REFERENCE hua (separate collection "
              "+ customer_id foreign key, unbounded growth safe).")
    elif not orders_ok:
        print(f"❌ FAIL — customer_orders ke liye pattern '{p2}' chuna gaya "
              f"(expected 'reference'). orders_lab me {len(orders_separate)} "
              f"docs mile, customers_lab doc = {customer_doc}. TODO 3 abhi "
              "unfilled hai — unbounded array document 16MB limit todh sakta "
              "hai; separate orders collection + customer_id FK use karo.")
    else:
        print(f"❌ FAIL — post_comments ke liye shape galat hai "
              f"(pattern={p1}, doc={post}).")

    print(f"""
SOCH (bolke jawab do):
  1. post_comments embed kiya — agar comments unbounded ho jayein (jaise
     Reddit thread, 10k+ comments), tab kya badalna padega? (Hint: subset
     pattern, section 3 upar — top-N embed + baaki separate collection)
  2. customer_orders reference kyun — embed karte to konsa MongoDB hard
     limit todne ka risk tha? (16MB doc size)
  3. Extended reference pattern (section 1, upar) kab use karoge jab pure
     reference bhi kaafi na ho (N+1 query problem se bachna ho)?
  4. schema_decision_tree() (section 11, upar) me post_comments aur
     customer_orders ke access_pattern/child_size/sharing values kya
     doge? Manually trace karo — kya wahi answer aata hai jo choose_pattern()
     me diya?
""")


if __name__ == "__main__":
    main()


# Examples
# schema_decision_tree('together', 'small', 'no')        # → EMBED
# schema_decision_tree('together', 'huge', 'no')         # → REFERENCE
# schema_decision_tree('separately', 'small', 'yes')     # → REFERENCE
