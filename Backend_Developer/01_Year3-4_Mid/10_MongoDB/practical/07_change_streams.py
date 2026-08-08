"""
MongoDB Change Streams — Production Patterns

Run: python 07_change_streams.py
Prereq: docker compose up -d   (see docker-compose.yml — change streams,
        transactions ki tarah, replica set ke bina bilkul kaam nahi karte)
"""

import os
import asyncio
import time
import logging
import threading
import uuid
from typing import Any
from datetime import datetime

import pymongo
from pymongo import MongoClient
from motor.motor_asyncio import AsyncIOMotorClient


MONGO_URI = os.getenv("MONGO_LAB_URI", "mongodb://localhost:27018/?directConnection=true")
client = MongoClient(MONGO_URI)
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


# ==========================================================================
# 12. LAB DRIVER — open a REAL stream, write in another thread, prove it fired
# ==========================================================================

def open_watch_stream(collection, pipeline=None):
    """
    Real change stream kholo, given collection pe, optional pipeline filter
    ke saath.
    """
    # ─────────────────────────────────────────────────────────────
    # TODO 1: actual watch() call missing hai. Collection pe change stream
    #   kholo — pipeline (agar diya gaya) apply hona chahiye, aur insert ke
    #   liye fullDocument already poora available hota hai.
    #   Hint: `return collection.watch(pipeline=pipeline, full_document='updateLookup')`
    raise NotImplementedError(
        "TODO 1 unfilled: open_watch_stream() me collection.watch(...) "
        "call missing hai — is function ko poora likho."
    )
    # ─────────────────────────────────────────────────────────────


def _watch_and_capture(collection, pipeline, result_box, timeout_s=8):
    """Background thread: stream khol ke rakho, pehla matching change capture karo."""
    try:
        stream = open_watch_stream(collection, pipeline=pipeline)
    except NotImplementedError as e:
        result_box['error'] = str(e)
        result_box['ready'].set()
        return

    result_box['ready'].set()   # signal: stream is open, safe to write now
    deadline = time.time() + timeout_s
    with stream:
        while time.time() < deadline:
            change = stream.try_next()
            if change is not None:
                result_box['change'] = change
                return
    result_box['change'] = None


def main() -> None:
    print("MongoDB Change Streams Lab — open watch(), write elsewhere, prove it fired")

    print("\n[1] Connect + clean lab collection")
    client.admin.command('ping')
    db.change_lab.delete_many({})

    marker = str(uuid.uuid4())
    pipeline = [{'$match': {'operationType': 'insert'}}]

    print("\n[2] Open change stream in a background thread")
    result_box = {'ready': threading.Event()}
    t = threading.Thread(target=_watch_and_capture, args=(db.change_lab, pipeline, result_box))
    t.start()
    stream_opened = result_box['ready'].wait(timeout=5)

    print("\n[3] Insert a document on the MAIN thread (stream should see it)")
    if stream_opened and 'error' not in result_box:
        # small buffer — try_next() polling needs at least one cycle after open
        time.sleep(0.5)
        db.change_lab.insert_one({'marker': marker, 'kind': 'lab_doc'})
    t.join(timeout=10)

    print("\n" + "─" * 60)
    if result_box.get('error'):
        print(f"❌ FAIL — {result_box['error']}")
    else:
        change = result_box.get('change')
        if change is None:
            print("❌ FAIL — koi change event capture nahi hua (timeout). "
                  "Stream sahi collection watch kar raha hai? Pipeline filter check karo.")
        else:
            op_ok = change.get('operationType') == 'insert'
            doc_ok = change.get('fullDocument', {}).get('marker') == marker
            if op_ok and doc_ok:
                print(f"✅ PASS — change stream ne asli insert event capture kiya "
                      f"(operationType='{change['operationType']}', "
                      f"marker match: {change['fullDocument']['marker'] == marker}).")
            else:
                print(f"❌ FAIL — event mila par mismatch — "
                      f"operationType={change.get('operationType')!r} "
                      f"(expected 'insert'), fullDocument={change.get('fullDocument')}")

    print(f"""
SOCH (bolke jawab do):
  1. Is lab me try_next() polling use kiya (max_await_time_ms jaisa kuch
     nahi diya) — production me `for change in stream:` blocking iteration
     kyun better hota hai ek dedicated worker process me?
  2. Agar insert se PEHLE stream open na hota (race condition), to event
     miss ho jaata — real system me isko kaise handle karte hain? (Hint:
     resume_token persist karna, section 3 upar)
  3. pipeline=[{{'$match': {{'operationType': 'insert'}}}}] hata dete to
     kya extra events aate? update/delete filter karne ka use case socho.
  4. Collection drop ho jaye to stream 'invalidate' event deta hai aur band
     ho jaata hai (section 11) — is lab ke simple try_next() loop me agar
     collection drop hoti to kya hota? Production handler alag kyun hai?
""")


if __name__ == "__main__":
    main()
