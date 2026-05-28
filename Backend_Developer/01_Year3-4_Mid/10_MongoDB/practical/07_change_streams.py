"""
MongoDB Change Streams — Production Patterns
"""

import asyncio
import time
import logging
from typing import Any
from datetime import datetime

import pymongo
from pymongo import MongoClient
from motor.motor_asyncio import AsyncIOMotorClient


client = MongoClient("mongodb://localhost:27017/?replicaSet=rs0")
db = client.mydb

log = logging.getLogger(__name__)


# ==========================================================================
# 1. BASIC WATCH
# ==========================================================================

def watch_simple():
    """Print all changes to users collection."""
    with db.users.watch() as stream:
        for change in stream:
            print(f"{change['operationType']}: {change['documentKey']}")


# ==========================================================================
# 2. WATCH WITH FILTER (pipeline)
# ==========================================================================

def watch_filtered():
    """Only paid orders, only inserts."""
    pipeline = [
        {'$match': {
            'operationType': {'$in': ['insert', 'update']},
            'fullDocument.status': 'paid',
        }},
    ]
    with db.orders.watch(pipeline, full_document='updateLookup') as stream:
        for change in stream:
            order = change['fullDocument']
            print(f"Paid order: {order['_id']}, amount: {order['amount']}")


# ==========================================================================
# 3. RESUMABLE STREAM (with persistent resume token)
# ==========================================================================

import json


RESUME_TOKEN_FILE = '/tmp/mongo_resume_token.json'


def load_resume_token():
    try:
        with open(RESUME_TOKEN_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def save_resume_token(token):
    # Production: save to Redis/Mongo, not file
    with open(RESUME_TOKEN_FILE, 'w') as f:
        json.dump(token, f)


def resumable_watch():
    """Survives restart — resumes from last processed event."""
    while True:
        resume_token = load_resume_token()
        try:
            kwargs = {'full_document': 'updateLookup'}
            if resume_token:
                kwargs['resume_after'] = resume_token

            with db.orders.watch(**kwargs) as stream:
                log.info(f"Stream opened, resume_token: {resume_token}")
                for change in stream:
                    try:
                        process_change(change)
                        # Save token AFTER successful process
                        save_resume_token(change['_id'])
                    except Exception as e:
                        log.exception(f"Failed to process change: {e}")
                        # Don't save token — will reprocess on resume
        except pymongo.errors.PyMongoError as e:
            log.error(f"Stream error: {e}, reconnecting in 5s")
            time.sleep(5)


def process_change(change):
    op = change['operationType']
    if op == 'insert':
        handle_insert(change['fullDocument'])
    elif op == 'update':
        handle_update(change['fullDocument'], change.get('updateDescription'))
    elif op == 'delete':
        handle_delete(change['documentKey']['_id'])


def handle_insert(doc):
    log.info(f"New doc: {doc.get('_id')}")


def handle_update(doc, update_desc):
    log.info(f"Updated: {doc.get('_id')}, fields: {update_desc.get('updatedFields')}")


def handle_delete(doc_id):
    log.info(f"Deleted: {doc_id}")


# ==========================================================================
# 4. MONGODB → ELASTICSEARCH SYNC
# ==========================================================================

# from elasticsearch import AsyncElasticsearch
# es = AsyncElasticsearch()


async def sync_products_to_es():
    """Real-time sync of MongoDB products to Elasticsearch."""
    async_client = AsyncIOMotorClient("mongodb://localhost:27017/?replicaSet=rs0")
    async_db = async_client.mydb

    while True:
        resume_token = await load_resume_token_async()
        try:
            kwargs = {'full_document': 'updateLookup'}
            if resume_token:
                kwargs['resume_after'] = resume_token

            async with async_db.products.watch(**kwargs) as stream:
                async for change in stream:
                    try:
                        await sync_one(change)
                        await save_resume_token_async(change['_id'])
                    except Exception as e:
                        log.exception(f"Sync error: {e}")
        except Exception as e:
            log.error(f"Stream broken: {e}")
            await asyncio.sleep(5)


async def sync_one(change):
    op = change['operationType']
    doc_id = str(change['documentKey']['_id'])

    if op in {'insert', 'update', 'replace'}:
        doc = change['fullDocument']
        # await es.index(index='products', id=doc_id, document=doc)
        log.info(f"ES upsert: {doc_id}")
    elif op == 'delete':
        try:
            # await es.delete(index='products', id=doc_id)
            log.info(f"ES delete: {doc_id}")
        except Exception:
            pass


async def load_resume_token_async():
    return None  # placeholder


async def save_resume_token_async(token):
    pass


# ==========================================================================
# 5. CACHE INVALIDATION
# ==========================================================================

# import redis.asyncio as aioredis
# redis_client = aioredis.from_url("redis://localhost:6379")


async def invalidate_cache_on_change():
    async_client = AsyncIOMotorClient("mongodb://...")
    async_db = async_client.mydb

    async with async_db.users.watch(full_document='updateLookup') as stream:
        async for change in stream:
            op = change['operationType']
            user_id = str(change['documentKey']['_id'])

            if op in {'update', 'replace', 'delete'}:
                # await redis_client.delete(f'user:{user_id}')
                # await redis_client.delete(f'user:profile:{user_id}')
                log.info(f"Invalidated cache for user {user_id}")


# ==========================================================================
# 6. DATABASE-LEVEL WATCH (all collections)
# ==========================================================================

def watch_database():
    """Watch all collections in database."""
    with db.watch(full_document='updateLookup') as stream:
        for change in stream:
            collection = change['ns']['coll']
            op = change['operationType']
            print(f"{collection}: {op}")


# ==========================================================================
# 7. CLUSTER-LEVEL WATCH (all databases)
# ==========================================================================

def watch_cluster():
    """Admin watch — entire cluster."""
    with client.watch() as stream:
        for change in stream:
            print(f"{change['ns']['db']}.{change['ns']['coll']}: {change['operationType']}")


# ==========================================================================
# 8. PIPELINE EXAMPLES
# ==========================================================================

# Only specific operations
WATCH_INSERTS_ONLY = [{'$match': {'operationType': 'insert'}}]

# Specific field changed
WATCH_PRICE_CHANGES = [{
    '$match': {
        'operationType': 'update',
        'updateDescription.updatedFields.price': {'$exists': True},
    },
}]

# Specific values
WATCH_HIGH_VALUE_ORDERS = [{
    '$match': {
        'fullDocument.amount': {'$gte': 1000},
    },
}]

# Multiple operations + value filter
WATCH_PAID_OR_REFUNDED = [{
    '$match': {
        '$or': [
            {'fullDocument.status': 'paid'},
            {'fullDocument.status': 'refunded'},
        ],
    },
}]


# ==========================================================================
# 9. HANDLING PRE-IMAGE (Mongo 6+)
# ==========================================================================

# Enable pre-image on collection (run once)
"""
db.runCommand({
    collMod: 'users',
    changeStreamPreAndPostImages: { enabled: true }
})
"""


def watch_with_pre_image():
    """Get both old and new values."""
    with db.users.watch(
        full_document='updateLookup',
        full_document_before_change='whenAvailable',
    ) as stream:
        for change in stream:
            before = change.get('fullDocumentBeforeChange')
            after = change.get('fullDocument')
            if before and after:
                # Diff old vs new
                diff = {
                    k: (before.get(k), after.get(k))
                    for k in set(before) | set(after)
                    if before.get(k) != after.get(k)
                }
                print(f"Changes: {diff}")


# ==========================================================================
# 10. DECOUPLE: STREAM → QUEUE → WORKERS
# ==========================================================================

# Listener pushes to Redis queue; workers process.
# Why: stream handler must be fast (don't block stream).

import asyncio
# from redis.asyncio import Redis


async def stream_to_queue():
    """Forward changes to Redis stream — let workers handle business logic."""
    async_client = AsyncIOMotorClient("mongodb://...")
    db = async_client.mydb
    # redis_client = Redis.from_url("redis://localhost")

    async with db.orders.watch(full_document='updateLookup') as stream:
        async for change in stream:
            # Push to Redis stream (fast)
            event = {
                'op': change['operationType'],
                'doc_id': str(change['documentKey']['_id']),
                'doc': json.dumps(change.get('fullDocument', {}), default=str),
                'cluster_time': str(change['clusterTime']),
            }
            # await redis_client.xadd('events:orders', event, maxlen=10000)
            log.info(f"Queued: {event['op']} {event['doc_id']}")


# ==========================================================================
# 11. ERROR HANDLING — Invalidation
# ==========================================================================

def handle_invalidation():
    """Stream invalidated (collection dropped) — must reopen."""
    while True:
        try:
            with db.users.watch() as stream:
                for change in stream:
                    if change['operationType'] == 'invalidate':
                        log.warning("Stream invalidated — reopening")
                        break
                    process_change(change)
        except pymongo.errors.PyMongoError as e:
            log.error(f"Stream error: {e}")
            time.sleep(2)
